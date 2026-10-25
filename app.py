import os
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from fpdf import FPDF

# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

OUTPUT_DIR = BASE_DIR / "generated_stories"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="AI Story Generator", page_icon="📖", layout="wide")


# ============================================================
# 2. AI HELPERS
# ============================================================

def get_llm(api_key, model_name, temperature):
    return ChatGroq(
        model=model_name,
        api_key=api_key,
        temperature=temperature,
        max_tokens=1800,
        timeout=120,
        max_retries=2,
    )


def ask_ai(llm, prompt, retries=4):
    """Retry temporary failures with exponential backoff."""
    for attempt in range(retries):
        try:
            response = llm.invoke(prompt)
            return str(response.content).strip()
        except Exception as exc:
            message = str(exc).lower()
            temporary = any(
                w in message
                for w in ["rate_limit", "429", "timeout",
                          "temporarily unavailable", "503", "502"]
            )
            if not temporary or attempt == retries - 1:
                raise
            wait_seconds = min(10 * (2 ** attempt), 60)
            st.toast(f"Temporary API issue. Retrying in {wait_seconds}s...")
            time.sleep(wait_seconds)


def generate_outline(llm, s):
    prompt = f"""
You are a professional screenplay writer and storyteller.

Create an original story outline using these settings:

Language: {s['language']}
Genre: {s['genre']}
Target duration: {s['duration']}
Number of scenes: exactly {s['scenes']}
Audience: {s['audience']}
Writing style: {s['style']}
Ending: {s['ending']}
Format: {s['story_format']}
Characters: {s['characters']}
Setting: {s['setting']}
Story idea: {s['plot']}

Requirements:
1. Write entirely in {s['language']}, except unavoidable proper nouns.
2. Create a compelling title.
3. Introduce consistent characters with names and motivations.
4. Provide exactly {s['scenes']} numbered scenes.
5. Give each scene a location, key action, and purpose in the plot.
6. Build tension and continuity between scenes.
7. Make the ending fit the requested ending type.
8. Respect the target audience.
9. Avoid repeating the same events across scenes.
10. Return only the title and numbered outline, without commentary.
"""
    return ask_ai(llm, prompt)


def generate_scene(llm, s, outline, scene_number, words_per_scene):
    prompt = f"""
You are writing a complete scene for a coherent screenplay.

LANGUAGE: {s['language']}
GENRE: {s['genre']}
AUDIENCE: {s['audience']}
STYLE: {s['style']}
ENDING TYPE: {s['ending']}
FORMAT: {s['story_format']}
CHARACTER REQUIREMENT: {s['characters']}
SETTING: {s['setting']}
TARGET DURATION: {s['duration']}

FULL STORY OUTLINE:
{outline}

ORIGINAL STORY IDEA:
{s['plot']}

Write scene {scene_number} of exactly {s['scenes']} scenes.

Instructions:
- Write in {s['language']}.
- Aim for approximately {words_per_scene} words for this scene.
- Keep character names, personalities, and events consistent.
- Follow the outline and advance the story.
- Include scene heading and location.
- Use natural dialogue when the selected format requires it.
- Use narration and atmosphere when appropriate.
- For horror, build suspense through pacing, sensory details, and uncertainty.
- Do not write the other scenes.
- Do not repeat the full outline.
- Do not add explanations outside the scene.
- If this is not the final scene, leave a natural continuation.
- If this is the final scene, deliver the requested ending.
"""
    return ask_ai(llm, prompt)


def generate_title(llm, s, outline):
    prompt = f"""
Give only a short story title in {s['language']}
based on this outline. Do not include quotation marks.

{outline}
"""
    return ask_ai(llm, prompt).strip().strip('"')


# ============================================================
# 3. EXPORT
# ============================================================

def find_font(language, uploaded_font_bytes=None):
    """Return a path to a usable TTF font."""
    if uploaded_font_bytes:
        path = OUTPUT_DIR / "_uploaded_font.ttf"
        path.write_bytes(uploaded_font_bytes)
        return path

    candidates = [
        BASE_DIR / "NotoSansDevanagari-Regular.ttf",
        BASE_DIR / "Nirmala.ttf",
        Path("C:/Windows/Fonts/Nirmala.ttf"),
        Path("C:/Windows/Fonts/mangal.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return p

    if language in ("Marathi", "Hindi"):
        raise FileNotFoundError(
            "A Devanagari font was not found. Upload "
            "NotoSansDevanagari-Regular.ttf in the sidebar, or place it "
            f"next to app.py ({BASE_DIR})."
        )

    for p in [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]:
        if p.exists():
            return p

    raise FileNotFoundError(
        "No suitable font found. Upload a .ttf font in the sidebar."
    )


def build_pdf(s, title, outline, scenes_text, font_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font(family="StoryFont", fname=str(font_path))

    if s["language"] in ("Marathi", "Hindi"):
        pdf.set_text_shaping(True)

    def write(text, size, h, align="L"):
        pdf.set_font("StoryFont", size=size)
        pdf.multi_cell(0, h, text, align=align,
                       new_x="LMARGIN", new_y="NEXT")

    write(title, 18, 12, "C")
    pdf.ln(5)
    write(
        f"Genre: {s['genre']} | Duration: {s['duration']} | "
        f"Language: {s['language']}", 11, 7,
    )
    pdf.ln(5)
    write("Story Outline", 14, 9)
    write(outline, 11, 7)
    pdf.add_page()

    for scene in scenes_text:
        lines = scene.splitlines()
        write(lines[0], 14, 9)
        write("\n".join(lines[2:]), 11, 7)
        pdf.ln(5)

    return bytes(pdf.output())


def build_txt(s, title, outline, scenes_text):
    content = [
        "AI STORY GENERATOR",
        "=" * 50,
        title,
        f"Language: {s['language']}",
        f"Genre: {s['genre']}",
        f"Duration: {s['duration']}",
        "",
        "STORY OUTLINE",
        "=" * 50,
        outline,
        "",
        "COMPLETE STORY",
        "=" * 50,
        "\n\n".join(scenes_text),
    ]
    return "\n".join(content).encode("utf-8")


# ============================================================
# 4. SESSION STATE
# ============================================================

for key, default in {
    "settings": None,
    "outline": None,
    "scenes": None,
    "title": None,
}.items():
    st.session_state.setdefault(key, default)


def reset():
    for k in ("settings", "outline", "scenes", "title"):
        st.session_state[k] = None


# ============================================================
# 5. SIDEBAR
# ============================================================

with st.sidebar:
    st.header("⚙️ Configuration")

    api_key = st.text_input(
        "Groq API key",
        value=os.getenv("GROQ_API_KEY", ""),
        type="password",
        help="Loaded from .env if GROQ_API_KEY is set.",
    )

    model_name = st.text_input(
    "Model",
    value=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    )
    
    temperature = st.slider("Creativity (temperature)", 0.0, 1.5, 0.7, 0.1)

    st.divider()
    font_upload = st.file_uploader(
        "PDF font (.ttf) — optional",
        type=["ttf"],
        help="Needed for Marathi/Hindi PDFs if no Devanagari font is found "
             "(e.g. NotoSansDevanagari-Regular.ttf).",
    )

    st.divider()
    if st.button("🔄 Start over", use_container_width=True):
        reset()
        st.rerun()


# ============================================================
# 6. MAIN UI
# ============================================================

st.title("📖 AI Story Generator")
st.caption("Generate multi-scene stories in Marathi, Hindi or English and "
           "export them as PDF or TXT.")

# ---------- Step 1: settings ----------

if st.session_state.outline is None:
    with st.form("settings_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            language = st.selectbox("Story language",
                                    ["Marathi", "Hindi", "English"])
            genre = st.selectbox("Genre", [
                "Horror", "Mystery", "Thriller", "Comedy", "Adventure",
                "Fantasy", "Romance", "Emotional", "Moral", "Custom"])
            custom_genre = st.text_input(
                "Custom genre (if selected)", "Supernatural horror")
            scenes = st.slider("Number of scenes", 1, 20, 5)
            duration = st.selectbox(
                "Target duration",
                ["1 minute", "3 minutes", "5 minutes",
                 "10 minutes", "15 minutes", "30 minutes"],
                index=1)

        with c2:
            audience = st.selectbox(
                "Target audience",
                ["Children", "Teenagers", "General audience", "Adults"],
                index=2)
            style = st.selectbox("Writing style", [
                "Cinematic", "Narrative", "Realistic",
                "Traditional folklore", "YouTube narration"])
            ending = st.selectbox("Ending type", [
                "Happy ending", "Sad ending", "Unexpected twist",
                "Open ending", "Moral lesson"], index=2)
            story_format = st.selectbox("Story format", [
                "Dialogue and narration", "Narration only",
                "Dialogue only"])

        with c3:
            characters = st.selectbox("Main characters", [
                "1 character", "2–4 characters",
                "5 or more characters", "AI decides"], index=1)
            setting = st.selectbox("Story setting", [
                "Village", "City", "Forest", "Old mansion",
                "Historical period", "Future or science fiction",
                "AI decides"])
            output_format = st.selectbox(
                "Export format", ["PDF", "TXT", "PDF and TXT"])

        plot = st.text_area(
            "Story idea or plot (optional)",
            placeholder="Leave empty for a completely original plot.",
        )

        submitted = st.form_submit_button(
            "✨ Generate outline", type="primary")

    if submitted:
        if not api_key:
            st.error("Please enter your Groq API key in the sidebar.")
            st.stop()

        settings = {
            "language": language,
            "genre": (custom_genre.strip() or "Supernatural horror")
            if genre == "Custom" else genre,
            "scenes": scenes,
            "duration": duration,
            "audience": audience,
            "style": style,
            "ending": ending,
            "story_format": story_format,
            "characters": characters,
            "setting": setting,
            "plot": plot.strip() or "Create a completely original plot.",
            "output_format": output_format,
        }

        try:
            with st.spinner("Generating story outline..."):
                llm = get_llm(api_key, model_name, temperature)
                outline = generate_outline(llm, settings)
        except Exception as exc:
            st.error(f"Could not generate the outline: {exc}")
            st.stop()

        st.session_state.settings = settings
        st.session_state.outline = outline
        st.rerun()


# ---------- Step 2: review outline & generate scenes ----------

elif st.session_state.scenes is None:
    s = st.session_state.settings

    st.subheader("Step 2 — Review the outline")
    with st.expander("Your settings", expanded=False):
        st.json(s)

    edited = st.text_area(
        "Edit the outline if you like, then approve it.",
        value=st.session_state.outline,
        height=380,
    )

    c1, c2, _ = st.columns([1, 1, 3])
    regenerate = c1.button("🔁 Regenerate outline")
    approve = c2.button("✅ Approve & write story", type="primary")

    if regenerate:
        if not api_key:
            st.error("Please enter your Groq API key in the sidebar.")
            st.stop()
        try:
            with st.spinner("Regenerating outline..."):
                llm = get_llm(api_key, model_name, temperature)
                st.session_state.outline = generate_outline(llm, s)
        except Exception as exc:
            st.error(f"Could not regenerate the outline: {exc}")
            st.stop()
        st.rerun()

    if approve:
        if not api_key:
            st.error("Please enter your Groq API key in the sidebar.")
            st.stop()

        outline = edited.strip()
        st.session_state.outline = outline

        duration_minutes = int(s["duration"].split()[0])
        words_per_scene = max(50, duration_minutes * 130 // s["scenes"])

        llm = get_llm(api_key, model_name, temperature)
        scenes_text = []
        progress = st.progress(0.0, text="Starting...")

        try:
            for n in range(1, s["scenes"] + 1):
                progress.progress(
                    (n - 1) / s["scenes"],
                    text=f"Writing scene {n} of {s['scenes']}...",
                )
                scene = generate_scene(llm, s, outline, n, words_per_scene)
                scenes_text.append(f"SCENE {n}\n\n{scene}")
                if n < s["scenes"]:
                    time.sleep(2)

            progress.progress(1.0, text="Creating title...")
            st.session_state.title = generate_title(llm, s, outline)
        except Exception as exc:
            st.error(
                f"Generation stopped at scene {len(scenes_text) + 1}: {exc}"
            )
            st.stop()

        st.session_state.scenes = scenes_text
        st.rerun()


# ---------- Step 3: result & downloads ----------

else:
    s = st.session_state.settings
    title = st.session_state.title or "Untitled Story"
    outline = st.session_state.outline
    scenes_text = st.session_state.scenes
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.success("Your story is ready!")
    st.header(title)
    st.caption(f"{s['genre']} • {s['duration']} • {s['language']}")

    tab_story, tab_outline = st.tabs(["📖 Story", "🗂️ Outline"])

    with tab_story:
        for scene in scenes_text:
            lines = scene.splitlines()
            st.subheader(lines[0])
            st.write("\n".join(lines[2:]))
            st.divider()

    with tab_outline:
        st.write(outline)

    st.subheader("⬇️ Download")
    d1, d2 = st.columns(2)

    if s["output_format"] in ("TXT", "PDF and TXT"):
        d1.download_button(
            "Download TXT",
            data=build_txt(s, title, outline, scenes_text),
            file_name=f"Story_{stamp}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    if s["output_format"] in ("PDF", "PDF and TXT"):
        try:
            font_path = find_font(
                s["language"],
                font_upload.getvalue() if font_upload else None,
            )
            pdf_bytes = build_pdf(s, title, outline, scenes_text, font_path)
            d2.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"Story_{stamp}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except FileNotFoundError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"PDF export failed: {exc}")

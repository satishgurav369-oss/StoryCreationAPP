# AI Story Generator — Streamlit

A configurable story-generation app built with Streamlit, LangChain, Groq, and FPDF2.

## Features
- Language, genre, scene count, duration, audience, style, ending, story format, characters, setting
- Optional plot seed (AI creates a plot if blank)
- Generate and edit an outline before writing scenes
- Scene-by-scene generation with progress
- Download PDF and/or UTF-8 TXT
- Marathi/Hindi PDF support with a Devanagari TTF font and HarfBuzz shaping

## Setup on Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Put your actual Groq API key in `.env`.

Download a Devanagari font such as Noto Sans Devanagari Regular and save it as
`NotoSansDevanagari-Regular.ttf` beside `app.py`.

Run:

```powershell
streamlit run app.py
```

Never commit `.env` to GitHub. Change `GROQ_MODEL` to a model currently available to your Groq account if needed.

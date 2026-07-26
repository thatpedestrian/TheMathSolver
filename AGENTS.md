# AGENTS.md

## Project

Python CLI that sends math exercise PDFs/images to Gemini 3.5 Flash, solves them, and outputs LaTeX compiled to PDF via XeLaTeX.

## Quick start

```bash
pip install -r requirements.txt
# Copy .env.example to .env and add GEMINI_API_KEY
python solver.py exercises.pdf
```

## Key commands

- `python solver.py <file>` — full pipeline (solve + compile)
- `python solver.py --no-compile <file>` — generate `.tex` only, skip XeLaTeX
- `python solver.py` — interactive prompt for file path

## Environment

- **Python 3.12+**
- **XeLaTeX** required at runtime (auto-detected from MiKTeX default install path if not in PATH)
- **API key**: stored in `.env` as `GEMINI_API_KEY=...` (gitignored). Loaded via `python-dotenv`.
- **Windows-only**: uses ANSI escape workaround (`os.system("")`) for colored output. Spinner uses ASCII chars (`| / - \\`) to avoid cp1252 encoding errors on Windows console.

## Architecture

- `solver.py` — single-file CLI, no packages/modules
- `prompts/solve_pdf.txt`, `prompts/solve_image.txt` — system prompts loaded at runtime. Edit these to tune Gemini output format without touching Python.
- `.env` — API key (gitignored)
- `install_xelatex.bat` — MiKTeX installer helper

## Gotchas

- XeLaTeX may not be in PATH on Windows. `solver.py` checks known MiKTeX install locations (`~/AppData/Local/Programs/MiKTeX/miktex/bin/x64/`) as fallback.
- Gemini response is parsed for LaTeX: first tries markdown code fences, then looks for `\documentclass...\end{document}`, falls back to raw response.
- After compilation, auxiliary files (`.aux`, `.log`, `.synctex.gz`, etc.) are auto-deleted — only `.tex` and `.pdf` remain.
- Both prompts require: `fontspec`, `polyglossia`, `bidi` packages. Font is `Latin Modern Roman` for English, `Arial` for Arabic.
- PDF size limit: 50MB. Image size limit: 20MB.

## Conventions

- **`patches.md`** must be updated at the end of every session that makes changes. Add a new entry under `[Unreleased]` with `Added`, `Changed`, or `Fixed` bullets describing what was done. This is mandatory — never skip it.

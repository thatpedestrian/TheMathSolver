# Patches

All notable changes to TheMathSolver are documented here.

## [Unreleased]

### Added
- `patches.md` — this file, tracks all changes per session.
- `pyproject.toml` — package config with `solve` console script entry point.
- `--clipboard` flag — grabs image from clipboard automatically.
- Auto-detect mode — when no file is given, checks clipboard for image or file path before prompting.
- `Pillow` dependency for clipboard image support.
- `solve` global command — run from any directory after `pip install -e .`.

### Changed
- `AGENTS.md` — added convention: must update `patches.md` at end of every session.
- `requirements.txt` — added `Pillow>=10.0.0`.
- `solver.py` — clipboard now asks for confirmation (`[Y/n]`) before solving, preventing accidental solves.

## [0.1.0] — 2026-07-26

### Added
- `solver.py` — main CLI: accepts PDFs and images, sends to Gemini 3.5 Flash, extracts LaTeX, compiles via XeLaTeX.
- `prompts/solve_pdf.txt`, `prompts/solve_image.txt` — system prompts for Gemini, editable without touching Python.
- `.env.example` — template for `GEMINI_API_KEY`.
- `.gitignore` — excludes `.env`, `__pycache__`, LaTeX auxiliary files, `$tmp/`.
- `install_xelatex.bat` — helper to install MiKTeX via winget on Windows.
- `requirements.txt` — `google-genai`, `python-dotenv`.
- `AGENTS.md` — agent instruction file for future sessions.
- `README.md` — project documentation.

### Features
- Auto-detects file type (PDF vs image) by extension.
- Auto-finds XeLaTeX in MiKTeX default install path if not in PATH.
- Animated CLI: step counters `[1/5]`, spinner during Gemini/XeLaTeX, colored output.
- Arabic + mixed-language support via `polyglossia` and `bidi`. English uses Latin Modern Roman, Arabic uses Arial.
- Auto-cleans auxiliary files after compilation (only `.tex` and `.pdf` remain).

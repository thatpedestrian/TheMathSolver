# TheMathSolver

A Python CLI that takes PDFs or images of math exercises, solves them using Google's Gemini 3.5 Flash, and outputs a clean PDF of step-by-step solutions — compiled from LaTeX via XeLaTeX.

## Features

- **PDF or image input** — feed it a photo of your homework, a screenshot, or a full PDF of exercises
- **AI-powered solving** — sends the document to Gemini 3.5 Flash (free tier) which reads and solves every problem
- **LaTeX output** — solutions are typeset in proper LaTeX and compiled to a professional PDF
- **Arabic support** — handles Arabic and mixed Arabic/English documents via `polyglossia` and `bidi`
- **Auto cleanup** — only your `.tex` and `.pdf` remain; all auxiliary files are deleted after compilation

## Requirements

- **Python 3.12+**
- **XeLaTeX** (included in [MiKTeX](https://miktex.org/download) or [TeX Live](https://www.tug.org/texlive/))
- **Google Gemini API key** (free at [AI Studio](https://aistudio.google.com/apikey))

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your API key:
   ```
   GEMINI_API_KEY=your-key-here
   ```

3. If XeLaTeX is not in your PATH, run:
   ```bash
   install_xelatex.bat
   ```

## Usage

```bash
# Solve exercises from a PDF
python solver.py homework.pdf

# Solve from a screenshot or photo
python solver.py screenshot.png

# Interactive mode — prompts for file path
python solver.py

# Generate .tex only, skip PDF compilation
python solver.py --no-compile exercises.pdf
```

Output files (`.tex` and `.pdf`) are saved alongside the input file.

## Project Structure

```
.
├── solver.py              # Main CLI
├── requirements.txt       # Dependencies
├── .env                   # API key (gitignored)
├── .env.example           # Template
├── install_xelatex.bat    # MiKTeX installer (Windows)
└── prompts/
    ├── solve_pdf.txt      # System prompt for PDF input
    └── solve_image.txt    # System prompt for image input
```

## Customization

Edit the prompt files in `prompts/` to change how Gemini approaches the problems — no Python changes needed. You can adjust the output format, add constraints, or tune the solution style.

## How It Works

1. **Detect input type** — determines if the file is a PDF or image
2. **Send to Gemini** — uploads the file with a system prompt asking for step-by-step LaTeX solutions
3. **Extract LaTeX** — parses Gemini's response, stripping any markdown fences
4. **Write .tex** — saves the LaTeX source next to the input file
5. **Compile** — runs XeLaTeX to produce the final PDF
6. **Cleanup** — removes all auxiliary files (`.aux`, `.log`, etc.)

## License

MIT

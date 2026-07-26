#!/usr/bin/env python3
"""Math exercise solver: reads PDFs/images of math exercises, solves them via Gemini, outputs LaTeX + PDF."""

import argparse
import itertools
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SUPPORTED_PDF_EXT = {".pdf"}
ALL_SUPPORTED = SUPPORTED_PDF_EXT | SUPPORTED_IMAGE_EXT

MAX_PDF_SIZE_MB = 50
MAX_IMAGE_SIZE_MB = 20

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

# Safe symbols (ASCII fallback for Windows console encoding issues)
SYM_SPINNER = ["|", "/", "-", "\\"]
SYM_CHECK = "[ok]"
SYM_ARROW = ">"
SYM_WARN = "!"
SYM_CROSS = "[FAIL]"


class Spinner:
    """Animated spinner that runs in a background thread."""

    def __init__(self, message: str):
        self.message = message
        self.running = False
        self.thread = None
        self.start_time = None

    def _animate(self):
        for frame in itertools.cycle(SYM_SPINNER):
            if not self.running:
                break
            elapsed = time.time() - self.start_time
            sys.stdout.write(f"\r  {CYAN}{frame}{RESET} {self.message} {DIM}({elapsed:.1f}s){RESET}  ")
            sys.stdout.flush()
            time.sleep(0.1)

    def __enter__(self):
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.2)
        elapsed = time.time() - self.start_time
        sys.stdout.write(f"\r{'':80}\r")
        sys.stdout.flush()


def step(num: int, total: int, label: str):
    """Print a step header."""
    print(f"\n{BOLD}{CYAN}[{num}/{total}]{RESET} {BOLD}{label}{RESET}")


def success(msg: str):
    print(f"  {GREEN}{SYM_CHECK}{RESET} {msg}")


def info(msg: str):
    print(f"  {DIM}{SYM_ARROW}{RESET} {msg}")


def warn(msg: str):
    print(f"  {YELLOW}{SYM_WARN}{RESET} {msg}")


def error(msg: str):
    print(f"  {RED}{SYM_CROSS}{RESET} {msg}")


def load_api_key() -> str:
    """Load the Gemini API key from the .env file."""
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    import os
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        error("GEMINI_API_KEY not found.")
        info(f"Create a .env file at {env_path} with:")
        print(f"    GEMINI_API_KEY=your-key-here")
        info("Get a free key at https://aistudio.google.com/apikey")
        sys.exit(1)
    return key


def grab_clipboard_image() -> Path | None:
    """Try to grab an image from the Windows clipboard. Returns path to temp file or None."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
        if img is None:
            return None
        tmp = Path(tempfile.gettempdir()) / "solver_clipboard.png"
        img.save(tmp, "PNG")
        return tmp
    except Exception:
        return None


def grab_clipboard_file() -> Path | None:
    """Check if the clipboard contains a file path (e.g. copied from Explorer). Returns Path or None."""
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5
        )
        clipboard_text = result.stdout.strip()
        if not clipboard_text:
            return None
        # Handle multiple paths (one per line)
        first_line = clipboard_text.splitlines()[0].strip().strip('"').strip("'")
        p = Path(first_line)
        if p.exists() and p.suffix.lower() in ALL_SUPPORTED:
            return p
        return None
    except Exception:
        return None


def detect_file_type(file_path: Path) -> str:
    """Detect whether the file is a PDF or image. Returns 'pdf' or 'image'."""
    ext = file_path.suffix.lower()
    if ext in SUPPORTED_PDF_EXT:
        return "pdf"
    elif ext in SUPPORTED_IMAGE_EXT:
        return "image"
    else:
        supported = ", ".join(sorted(ALL_SUPPORTED))
        error(f"Unsupported file type '{ext}'.")
        info(f"Supported types: {supported}")
        sys.exit(1)


def validate_file(file_path: Path, file_type: str) -> None:
    """Check file exists and is within size limits."""
    if not file_path.exists():
        error(f"File not found: {file_path}")
        sys.exit(1)

    size_mb = file_path.stat().st_size / (1024 * 1024)
    max_mb = MAX_PDF_SIZE_MB if file_type == "pdf" else MAX_IMAGE_SIZE_MB
    if size_mb > max_mb:
        error(f"File is {size_mb:.1f}MB, max allowed is {max_mb}MB.")
        sys.exit(1)


def find_xelatex() -> str | None:
    """Find xelatex executable. Checks PATH first, then known MiKTeX install locations."""
    path = shutil.which("xelatex")
    if path:
        return path

    import os
    home = Path.home()
    candidates = [
        home / "AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe",
        Path("C:/Program Files/MiKTeX/miktex/bin/x64/xelatex.exe"),
        Path("C:/Program Files (x86)/MiKTeX/miktex/bin/x64/xelatex.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            bin_dir = str(candidate.parent)
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            return str(candidate)

    return None


def check_xelatex() -> str:
    """Verify XeLaTeX is available. Returns the path to xelatex."""
    xelatex_path = find_xelatex()
    if xelatex_path is None:
        error("XeLaTeX not found.")
        info("MiKTeX may not be installed, or its binaries are not in PATH.")
        info("Fix options:")
        print("    1. Add MiKTeX to PATH: C:\\Users\\prett\\AppData\\Local\\Programs\\MiKTeX\\miktex\\bin\\x64")
        print("    2. Run: install_xelatex.bat")
        print("    3. Visit: https://miktex.org/download")
        info("After fixing, restart your terminal and try again.")
        sys.exit(1)
    return xelatex_path


def load_prompt(file_type: str, prompt_dir: Path) -> str:
    """Load the system prompt file for the given input type."""
    prompt_file = prompt_dir / f"solve_{file_type}.txt"
    if not prompt_file.exists():
        error(f"Prompt file not found: {prompt_file}")
        sys.exit(1)
    return prompt_file.read_text(encoding="utf-8")


def extract_latex(response_text: str) -> str:
    """Extract LaTeX source from the model response, stripping any markdown fences."""
    text = response_text.strip()

    fence_pattern = r"```(?:latex)?\s*\n(.*?)```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    doc_pattern = r"(\\documentclass.*?\\end\{document\})"
    match = re.search(doc_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return text


def call_gemini(api_key: str, file_path: Path, file_type: str, prompt: str) -> str:
    """Send the file + prompt to Gemini and return the response text."""
    client = genai.Client(api_key=api_key)

    file_bytes = file_path.read_bytes()
    mime_type = MIME_TYPES[file_path.suffix.lower()]

    info(f"Sending {file_type} to Gemini ({file_path.name}, {len(file_bytes)/1024:.0f}KB)")

    with Spinner("Gemini is solving your exercises..."):
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                prompt,
            ],
        )

    return response.text


def compile_latex(tex_path: Path, xelatex_path: str) -> bool:
    """Compile a .tex file with XeLaTeX. Returns True if PDF was produced."""
    output_dir = tex_path.parent
    pdf_path = tex_path.with_suffix(".pdf")
    info(f"Running XeLaTeX on {tex_path.name}...")

    with Spinner("Compiling LaTeX to PDF..."):
        result = subprocess.run(
            [
                xelatex_path,
                "-interaction=nonstopmode",
                f"-output-directory={output_dir}",
                str(tex_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

    # XeLaTeX returns non-zero on warnings too — check if PDF actually exists
    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        return True

    error("XeLaTeX compilation failed — no PDF produced.")
    print(f"\n{DIM}--- XeLaTeX output ---{RESET}")
    print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
    print(f"{DIM}--- end ---{RESET}")
    return False


def cleanup_aux_files(tex_path: Path):
    """Remove XeLaTeX auxiliary files, keeping only .tex and .pdf."""
    aux_exts = {".aux", ".log", ".synctex.gz", ".out", ".toc", ".fls",
                ".fdb_latexmk", ".bcf", ".run.xml", ".blg", ".bbl",
                ".nav", ".snm", ".vrb", ".idx", ".ilg", ".ind", ".glg",
                ".glo", ".gls", ".ist", ".acn", ".acr", ".alg"}
    base = tex_path.with_suffix("")
    removed = 0
    for f in tex_path.parent.iterdir():
        if f.suffix in aux_exts and f.stem == base.name:
            f.unlink()
            removed += 1
    if removed > 0:
        info(f"Cleaned up {removed} auxiliary file(s)")


def cleanup_temp_file(path: Path):
    """Remove a temporary file if it exists."""
    try:
        if path.exists() and path.parent == Path(tempfile.gettempdir()):
            path.unlink()
    except Exception:
        pass


def enable_ansi_windows():
    """Enable ANSI escape codes on Windows terminals."""
    import os
    if os.name == "nt":
        os.system("")


def main():
    enable_ansi_windows()

    parser = argparse.ArgumentParser(
        description="Solve math exercises from PDFs or images using Gemini."
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to PDF or image file containing exercises",
    )
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Grab image from clipboard instead of file",
    )
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        default=Path(__file__).parent / "prompts",
        help="Directory containing prompt files (default: ./prompts)",
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="Skip XeLaTeX compilation (only generate .tex file)",
    )
    args = parser.parse_args()

    # Header
    print(f"\n{BOLD}{CYAN}{'='*50}{RESET}")
    print(f"{BOLD}{CYAN}  Exercise Solver — Gemini 3.5 Flash{RESET}")
    print(f"{BOLD}{CYAN}{'='*50}{RESET}")

    total_steps = 5 if not args.no_compile else 4
    current_step = 0

    # Step 1: Get file path
    current_step += 1
    step(current_step, total_steps, "Loading input")

    file_path = None
    tmp_file = None

    if args.clipboard:
        # Clipboard mode: try image first, then file path
        info("Checking clipboard...")
        clip_img = grab_clipboard_image()
        clip_file = grab_clipboard_file()
        if clip_img:
            tmp_file = clip_img
            success(f"Image found on clipboard ({clip_img.stat().st_size//1024}KB)")
            confirm = input(f"  Solve this image? [Y/n] ").strip().lower()
            if confirm and confirm != "y":
                info("Skipping clipboard content.")
                user_input = input("  Enter path to PDF or image file: ").strip()
                file_path = Path(user_input).resolve()
                success(f"Input: {file_path.name}")
            else:
                file_path = clip_img
        elif clip_file:
            success(f"File found on clipboard: {clip_file.name}")
            confirm = input(f"  Solve {clip_file.name}? [Y/n] ").strip().lower()
            if confirm and confirm != "y":
                info("Skipping clipboard content.")
                user_input = input("  Enter path to PDF or image file: ").strip()
                file_path = Path(user_input).resolve()
                success(f"Input: {file_path.name}")
            else:
                file_path = clip_file
        else:
            error("Clipboard is empty or contains unsupported content.")
            user_input = input("  Enter path to PDF or image file: ").strip()
            file_path = Path(user_input).resolve()
            success(f"Input: {file_path.name}")
    elif args.file:
        # Direct file argument
        file_path = Path(args.file).resolve()
        success(f"Input: {file_path.name}")
    else:
        # Auto-detect: check clipboard first, then prompt
        info("Checking clipboard...")
        clip_img = grab_clipboard_image()
        clip_file = grab_clipboard_file()
        if clip_img:
            tmp_file = clip_img
            success(f"Image found on clipboard ({clip_img.stat().st_size//1024}KB)")
            confirm = input(f"  Solve this image? [Y/n] ").strip().lower()
            if confirm and confirm != "y":
                info("Skipping clipboard content.")
                user_input = input("  Enter path to PDF or image file: ").strip()
                file_path = Path(user_input).resolve()
                success(f"Input: {file_path.name}")
            else:
                file_path = clip_img
        elif clip_file:
            success(f"File found on clipboard: {clip_file.name}")
            confirm = input(f"  Solve {clip_file.name}? [Y/n] ").strip().lower()
            if confirm and confirm != "y":
                info("Skipping clipboard content.")
                user_input = input("  Enter path to PDF or image file: ").strip()
                file_path = Path(user_input).resolve()
                success(f"Input: {file_path.name}")
            else:
                file_path = clip_file
        else:
            info("Clipboard has no image or file — prompting for input.")
            user_input = input("  Enter path to PDF or image file: ").strip()
            file_path = Path(user_input).resolve()
            success(f"Input: {file_path.name}")

    # Step 2: Load API key + detect type
    current_step += 1
    step(current_step, total_steps, "Validating")

    api_key = load_api_key()
    success("API key loaded from .env")

    file_type = detect_file_type(file_path)
    validate_file(file_path, file_type)
    success(f"File type: {file_type.upper()} ({file_path.suffix})")

    if not args.no_compile:
        xelatex_path = check_xelatex()
        success(f"XeLaTeX found")

    # Step 3: Load prompt
    current_step += 1
    step(current_step, total_steps, "Preparing prompt")

    prompt = load_prompt(file_type, args.prompt_dir)
    success(f"Loaded prompts/solve_{file_type}.txt ({len(prompt)} chars)")

    # Step 4: Call Gemini
    current_step += 1
    step(current_step, total_steps, "Solving with Gemini")

    start_time = time.time()
    response_text = call_gemini(api_key, file_path, file_type, prompt)
    elapsed = time.time() - start_time
    success(f"Gemini responded in {elapsed:.1f}s ({len(response_text)} chars)")

    # Extract LaTeX
    latex_source = extract_latex(response_text)
    if not latex_source:
        error("No LaTeX content found in the response.")
        info("Raw response:")
        print(f"    {response_text[:500]}")
        cleanup_temp_file(tmp_file)
        sys.exit(1)
    success("LaTeX extracted from response")

    # Step 5: Write .tex + compile
    current_step += 1
    step(current_step, total_steps, "Generating output")

    # Output next to the original file (or current dir for clipboard)
    if tmp_file:
        # Clipboard image: output to current working directory
        output_name = "clipboard_exercise"
        tex_path = Path.cwd() / f"{output_name}.tex"
    else:
        tex_path = file_path.with_suffix(".tex")

    tex_path.write_text(latex_source, encoding="utf-8")
    success(f"Written: {tex_path.name}")

    if not args.no_compile:
        success_compile = compile_latex(tex_path, xelatex_path)
        if success_compile:
            cleanup_aux_files(tex_path)
            pdf_path = tex_path.with_suffix(".pdf")
            success(f"PDF ready: {pdf_path}")
        else:
            error(f"Compilation failed. Check {tex_path.name} to debug.")
            cleanup_temp_file(tmp_file)
            sys.exit(1)
    else:
        info("Skipping XeLaTeX (--no-compile)")

    # Cleanup temp file
    cleanup_temp_file(tmp_file)

    # Done
    print(f"\n{BOLD}{GREEN}{'='*50}{RESET}")
    print(f"{BOLD}{GREEN}  Done!{RESET}")
    print(f"{BOLD}{GREEN}{'='*50}{RESET}\n")


if __name__ == "__main__":
    main()

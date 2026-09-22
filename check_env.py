#!/usr/bin/env python3
"""Verify the environment is ready to run the AI Video Assistant.

Run with the SAME Python interpreter that launches Streamlit:

    python check_env.py
    python check_env.py --deep   # also imports each package (slower, catches
                                  # more than "is it installed")

Checks:
  - Every package requirements.txt lists is importable
  - ffmpeg / ffprobe are on PATH
  - .streamlit... no, .env exists and the keys the app cares about are SET
    (never prints their values)
  - Reports the installed Streamlit version, since it decides which theme
    options are available in Phase 3

Exits non-zero if anything required is missing, so it's CI/script-friendly.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys

# import name -> (pip package name, required for the app to *run at all*)
PACKAGES = {
    "streamlit": ("streamlit", True),
    "dotenv": ("python-dotenv", True),
    "langchain_core": ("langchain-core", True),
    "langchain_groq": ("langchain-groq", True),
    "langchain_text_splitters": ("langchain-text-splitters", True),
    "langchain_chroma": ("langchain-chroma", True),
    "langchain_huggingface": ("langchain-huggingface", True),
    "chromadb": ("chromadb", True),
    "sentence_transformers": ("sentence-transformers", True),
    "whisper": ("openai-whisper", True),
    "pydub": ("pydub", True),
    "requests": ("requests", True),
    "yt_dlp": ("yt-dlp", True),
    "fpdf": ("fpdf2", True),
    "pandas": ("pandas", True),
    "plotly": ("plotly", True),
    "bcrypt": ("bcrypt", False),  # Phase 2
    "itsdangerous": ("itsdangerous", False),  # Phase 2
}


def check_packages(deep: bool) -> list[str]:
    problems = []
    for import_name, (pip_name, required) in PACKAGES.items():
        try:
            mod = importlib.import_module(import_name)
        except Exception as exc:  # noqa: BLE001 -- report, don't crash
            level = "MISSING" if required else "missing (optional, Phase 2)"
            print(f"  [{level:>24}]  {pip_name:<28} ({import_name}: {exc})")
            if required:
                problems.append(pip_name)
            continue

        version = getattr(mod, "__version__", "unknown")
        print(f"  [{'ok':>24}]  {pip_name:<28} {version}")

        if deep:
            # A second, harder check: some packages import fine but blow up
            # on first real use (native extension mismatch, etc). Poke at
            # something cheap and side-effect-free where we can.
            try:
                if import_name == "chromadb":
                    from chromadb.config import Settings  # noqa: F401
                elif import_name == "whisper":
                    whisper_module = mod
                    assert hasattr(whisper_module, "load_model")
            except Exception as exc:  # noqa: BLE001
                print(f"      -> deep check failed: {exc}")
                if required:
                    problems.append(f"{pip_name} (deep check)")
    return problems


def check_ffmpeg() -> list[str]:
    problems = []
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if path:
            try:
                out = subprocess.run(
                    [tool, "-version"], capture_output=True, text=True, timeout=5
                )
                first_line = out.stdout.splitlines()[0] if out.stdout else "(no output)"
            except Exception as exc:  # noqa: BLE001
                first_line = f"(couldn't run: {exc})"
            print(f"  [{'ok':>24}]  {tool:<28} {path} -- {first_line}")
        else:
            print(f"  [{'MISSING':>24}]  {tool:<28} not found on PATH")
            problems.append(tool)
    return problems


def check_env_file() -> list[str]:
    """Reports which keys are set/unset. Never prints values."""
    try:
        from config.settings import Settings
    except Exception as exc:  # noqa: BLE001
        print(f"  Could not import config.settings: {exc}")
        return ["config.settings import failed"]

    s = Settings()
    checks = [
        ("GROQ_API_KEY", bool(s.groq_api_key), True),
        ("SARVAM_API_KEY", bool(s.sarvam_api_key), False),
        ("SECRET_KEY", bool(s.secret_key), False),
    ]
    problems = []
    for name, is_set, required in checks:
        status = "set" if is_set else ("MISSING" if required else "not set (optional for now)")
        print(f"  [{status:>28}]  {name}")
        if required and not is_set:
            problems.append(name)
    return problems


def main() -> int:
    deep = "--deep" in sys.argv

    print(f"Python: {sys.executable} ({sys.version.split()[0]})\n")

    print("== Packages ==")
    pkg_problems = check_packages(deep)

    print("\n== System dependencies ==")
    sys_problems = check_ffmpeg()

    print("\n== .env ==")
    env_problems = check_env_file()

    try:
        import streamlit

        print(f"\nStreamlit version: {streamlit.__version__}")
    except Exception:  # noqa: BLE001
        pass

    all_problems = pkg_problems + sys_problems + env_problems
    print()
    if all_problems:
        print(f"FAILED -- {len(all_problems)} problem(s):")
        for p in all_problems:
            print(f"  - {p}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

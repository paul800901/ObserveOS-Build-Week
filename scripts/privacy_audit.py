from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TEXT_EXTENSIONS = {".py", ".js", ".css", ".html", ".json", ".md", ".ps1", ".cmd", ".txt", ".toml"}
SKIP_PARTS = {".git", "__pycache__", "runtime_data", "dist"}
SKIP_FILES = {"privacy_audit.py"}
PATTERNS = {
    "private Windows path": re.compile(r"(?i)[A-Z]:\\(?:Users\\[^\\\s]+|CaseAgent|ObserveOpsControl|VoiceLab|錄音轉文字|我的雲端硬碟)"),
    "OpenAI-style secret": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "Google-style secret": re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
    "filled OPENAI_API_KEY": re.compile(r"OPENAI_API_KEY\s*=\s*\S+"),
    "embedded api_key JSON": re.compile(r"(?i)\"api_key\"\s*:\s*\"[^\"]+\""),
    "known private mailbox shape": re.compile(r"(?i)(?:sl\d{6}|observe\d{5})@gmail\.com"),
}


def audit_repo(root: Path) -> list[dict[str, object]]:
    root = Path(root).resolve()
    findings: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        relative = path.relative_to(root)
        if path.name in SKIP_FILES:
            continue
        if path.name in {".env", ".env.local"} or (path.name.startswith(".env.") and path.name != ".env.example"):
            findings.append({"file": str(relative), "line": 0, "rule": "secret-bearing env file"})
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            findings.append({"file": str(relative), "line": 0, "rule": "non-UTF-8 text file"})
            continue
        for line_number, line in enumerate(lines, start=1):
            for rule, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append({"file": str(relative), "line": line_number, "rule": rule})
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan the public submission tree for obvious private paths and secrets.")
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    findings = audit_repo(args.root)
    print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()

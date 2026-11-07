#!/usr/bin/env python3
"""Validate the portable plugin package without third-party dependencies."""

from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FORBIDDEN_TEXT = (
    re.compile(r"/Users/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\", re.IGNORECASE),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)
FORBIDDEN_SUFFIXES = {
    ".env",
    ".key",
    ".p12",
    ".pfx",
    ".pem",
    ".pptx",
    ".docx",
    ".xlsx",
    ".zip",
}
MAX_FILE_BYTES = 5 * 1024 * 1024


def error(errors: list[str], message: str) -> None:
    errors.append(message)


def read_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        error(errors, f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        error(errors, f"{path.relative_to(ROOT)}: expected a JSON object")
        return {}
    return value


def frontmatter(path: Path, errors: list[str]) -> tuple[str | None, str | None]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        error(errors, f"{path.relative_to(ROOT)}: missing YAML frontmatter")
        return None, None
    block = match.group(1)
    name_match = re.search(r"^name:\s*['\"]?([^'\"\n]+)", block, re.MULTILINE)
    description_match = re.search(r"^description:\s*(.*)$", block, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else None
    description = description_match.group(1).strip() if description_match else None
    if description in {">", "|", ">-", "|-"}:
        description = " ".join(
            line.strip()
            for line in block[description_match.end() :].splitlines()
            if line.startswith((" ", "\t")) and line.strip()
        )
    if not name:
        error(errors, f"{path.relative_to(ROOT)}: missing skill name")
    if not description:
        error(errors, f"{path.relative_to(ROOT)}: missing skill description")
    return name, description


def validate_manifest(errors: list[str]) -> None:
    manifest = read_json(ROOT / "plugin.json", errors)
    if manifest.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        error(errors, "plugin.json: unsupported or missing Agent Plugins schema")
    name = manifest.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        error(errors, "plugin.json: name must be kebab-case")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        error(errors, "plugin.json: version must be semantic x.y.z")
    if not manifest.get("description"):
        error(errors, "plugin.json: description is required")
    extension = manifest.get("extensions", {}).get("com.openai", {})
    interface = extension.get("interface", {})
    if not str(interface.get("displayName", "")).startswith("SC: "):
        error(errors, "plugin.json: interface.displayName must start with 'SC: '")
    for key in ("composerIcon", "logo"):
        value = interface.get(key)
        if value:
            if not isinstance(value, str) or not value.startswith("./") or ".." in Path(value).parts:
                error(errors, f"plugin.json: invalid {key} path")
            elif not (ROOT / value).is_file():
                error(errors, f"plugin.json: missing {key} file {value}")

    compatibility = read_json(ROOT / ".codex-plugin" / "plugin.json", errors)
    for key in ("name", "version", "description", "repository", "license"):
        if compatibility.get(key) != manifest.get(key):
            error(errors, f"compatibility manifest differs at {key}")
    if compatibility.get("skills") != "./skills/":
        error(errors, "compatibility manifest must declare ./skills/")

    marketplace = read_json(ROOT / ".agents" / "plugins" / "marketplace.json", errors)
    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        error(errors, "marketplace.json must contain exactly one plugin entry")
    elif entries[0].get("name") != manifest.get("name"):
        error(errors, "marketplace plugin name differs from plugin.json")


def validate_skills(errors: list[str]) -> None:
    skill_dirs = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
    if not skill_dirs:
        error(errors, "no skills found")
    for skill_dir in skill_dirs:
        entrypoint = skill_dir / "SKILL.md"
        if not entrypoint.is_file():
            error(errors, f"skills/{skill_dir.name}: missing SKILL.md")
            continue
        name, _ = frontmatter(entrypoint, errors)
        if name != skill_dir.name:
            error(errors, f"{entrypoint.relative_to(ROOT)}: name must match directory")
        if name and not NAME_RE.fullmatch(name):
            error(errors, f"{entrypoint.relative_to(ROOT)}: invalid skill name")
        text = entrypoint.read_text(encoding="utf-8")
        if re.search(r"\b(?:TODO|TBD|PLACEHOLDER)\b", text, re.IGNORECASE):
            error(errors, f"{entrypoint.relative_to(ROOT)}: unfinished placeholder")
        for target in LINK_RE.findall(text):
            if re.match(r"(?:https?|mailto):", target) or target.startswith("#"):
                continue
            relative = target.split("#", 1)[0]
            if relative and not (skill_dir / relative).exists():
                error(errors, f"{entrypoint.relative_to(ROOT)}: broken link {target}")
        ui = skill_dir / "agents" / "openai.yaml"
        if ui.is_file():
            ui_text = ui.read_text(encoding="utf-8")
            match = re.search(r"^\s*display_name:\s*['\"]?([^'\"\n]+)", ui_text, re.MULTILINE)
            if not match or not match.group(1).strip().startswith("SC: "):
                error(errors, f"{ui.relative_to(ROOT)}: display_name must start with 'SC: '")


def validate_files(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            error(errors, f"{relative}: symlinks are not allowed")
        if path.stat().st_size > MAX_FILE_BYTES:
            error(errors, f"{relative}: file exceeds 5 MiB")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            error(errors, f"{relative}: binary/private document type is not allowed")
        if path.suffix.lower() in {".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt"} or path.name in {"LICENSE", ".gitignore"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                error(errors, f"{relative}: expected UTF-8 text")
                continue
            # The validator necessarily contains the credential signatures it
            # searches for; avoid self-matching those literal patterns.
            if relative != Path("tools/validate_plugin.py"):
                for pattern in FORBIDDEN_TEXT:
                    if pattern.search(text):
                        error(errors, f"{relative}: contains a sensitive path or credential pattern")
                        break
        if path.suffix == ".json":
            read_json(path, errors)
        elif path.suffix == ".py":
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                error(errors, f"{relative}: Python syntax error: {exc.msg}")
        elif path.suffix == ".sh":
            result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            if result.returncode:
                error(errors, f"{relative}: Bash syntax error: {result.stderr.strip()}")


def main() -> int:
    errors: list[str] = []
    validate_manifest(errors)
    validate_skills(errors)
    validate_files(errors)
    if errors:
        print("Plugin validation failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1
    skill_count = len(list((ROOT / "skills").glob("*/SKILL.md")))
    file_count = sum(1 for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)
    print(f"Plugin validation passed: {skill_count} skills, {file_count} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

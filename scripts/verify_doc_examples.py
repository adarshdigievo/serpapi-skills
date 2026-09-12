#!/usr/bin/env python3
"""Check Markdown links and executable examples without making API calls."""

from __future__ import annotations

import concurrent.futures
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

from doc_contracts import DOCUMENTS, ROOT, SKILL_ROOTS, code_blocks, links, load_yaml, unclosed_fences, validate_skill


EXTERNAL_SCHEMES = ("http://", "https://")
COMMANDS = {"bash": "bash", "sh": "bash", "js": "node", "javascript": "node", "ruby": "ruby", "go": "gofmt"}
POWERSHELL_PARSE = "$tokens = $null; $errors = $null; [System.Management.Automation.Language.Parser]::ParseFile($args[0], [ref]$tokens, [ref]$errors) | Out-Null; if ($errors.Count) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"


def report_error(errors: list[str], path: Path, message: str) -> None:
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def run_syntax_check(language: str, source: str) -> str | None:
    if language == "toml":
        try:
            tomllib.loads(source)
        except tomllib.TOMLDecodeError as error:
            return f"invalid TOML: {error}"
        return None
    if language in {"yaml", "yml"}:
        try:
            load_yaml(source)
        except Exception as error:
            return f"invalid YAML: {error}"
        return None
    if language == "json":
        try:
            json.loads(source)
        except json.JSONDecodeError as error:
            return f"invalid JSON: {error}"
        return None
    if language == "python":
        try:
            compile(source, "<documentation>", "exec")
        except SyntaxError as error:
            return f"invalid Python: {error.msg} at line {error.lineno}"
        return None
    command = "pwsh" if language == "powershell" else COMMANDS.get(language)
    if command is None:
        return None
    executable = shutil.which(command)
    if executable is None:
        return f"cannot check {language}: {command} is not installed"
    suffix = ".mjs" if language in {"js", "javascript"} else f".{language}"
    with tempfile.TemporaryDirectory(prefix="serpapi-syntax-") as directory:
        snippet = Path(directory) / ("example" + suffix)
        snippet.write_text(source)
        if language in {"bash", "sh"}:
            args = [executable, "-n", str(snippet)]
        elif language in {"js", "javascript"}:
            args = [executable, "--check", str(snippet)]
        elif language == "ruby":
            args = [executable, "-c", str(snippet)]
        elif language == "powershell":
            parser = Path(str(snippet) + ".ps1")
            try:
                parser.write_text(POWERSHELL_PARSE)
                result = subprocess.run([executable, "-NoProfile", "-File", str(parser), str(snippet)], text=True, capture_output=True, timeout=20)
            finally:
                parser.unlink(missing_ok=True)
            return None if result.returncode == 0 else f"invalid PowerShell: {result.stderr.strip()}"
        else:
            args = [executable, str(snippet)]
        result = subprocess.run(args, text=True, capture_output=True, timeout=20)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1]
        return f"invalid {language}: {detail}"
    return None


def check_external_link(url: str) -> tuple[str, str | None]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/html,text/plain,*/*;q=0.8", "User-Agent": "Mozilla/5.0 serpapi-skills-doc-check/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status >= 400:
                return url, f"HTTP {response.status}"
    except urllib.error.HTTPError as error:
        if error.code in {403, 429}:
            print(f"WARNING external link could not be checked (HTTP {error.code}): {url}")
            return url, None
        return url, f"HTTP {error.code}"
    except Exception as error:
        return url, f"{type(error).__name__}: {error}"
    return url, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="check local links and syntax without fetching external links")
    parser.add_argument("--require-powershell", action="store_true", help="fail if pwsh is unavailable")
    args = parser.parse_args()
    errors: list[str] = []
    external_sources: dict[str, list[Path]] = {}
    checked_blocks = 0

    for skill_root in SKILL_ROOTS:
        for error in validate_skill(skill_root / "SKILL.md", (skill_root / "SKILL.md").read_text()):
            report_error(errors, skill_root / "SKILL.md", error)

    for path in DOCUMENTS:
        text = path.read_text()
        for line in unclosed_fences(text):
            report_error(errors, path, f"unclosed fenced code block at line {line}")
        for block in code_blocks(text):
            language = block.language
            if language == "powershell" and not shutil.which("pwsh") and not args.require_powershell:
                print(f"SKIP {path.relative_to(ROOT)}:{block.line}: PowerShell syntax (pwsh unavailable)")
                continue
            error = run_syntax_check(language, block.source)
            if error:
                report_error(errors, path, error)
            if language in {*COMMANDS, "json", "python", "yaml", "yml", "toml", "powershell"}:
                checked_blocks += 1
        for target in links(text):
            target = target.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(EXTERNAL_SCHEMES):
                external_sources.setdefault(target, []).append(path)
                continue
            if target.startswith(("#", "mailto:")):
                continue
            local_target = target.split("#", 1)[0]
            if local_target and not (path.parent / local_target).resolve().exists():
                report_error(errors, path, f"missing local link target {target}")

    if not args.offline:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for url, error in executor.map(check_external_link, external_sources):
                if error:
                    sources = ", ".join(str(path.relative_to(ROOT)) for path in external_sources[url])
                    errors.append(f"{sources}: external link {url} failed ({error})")

    if errors:
        print("Documentation checks failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        f"Syntax-checked {len(DOCUMENTS)} Markdown files, {checked_blocks} code blocks, "
        f"and {'skipped' if args.offline else 'checked'} {len(external_sources)} external links."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

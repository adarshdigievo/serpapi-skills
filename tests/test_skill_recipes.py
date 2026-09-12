import json
import os
import shlex
import shutil
import subprocess
import sys

import pytest

from doc_contracts import ROOT, SKILL_ROOT, code_blocks, links, validate_skill


def test_copied_skill_bundle_has_no_repository_dependencies(tmp_path):
    for source in (ROOT / "skills").iterdir():
        if source.is_dir():
            shutil.copytree(source, tmp_path / source.name)
    for path in tmp_path.rglob("*.md"):
        if path.name == "SKILL.md":
            assert not validate_skill(path, path.read_text())
        for target in links(path.read_text()):
            if target.startswith(("https://", "http://", "#")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.is_relative_to(tmp_path.resolve()), (path, target)
            assert resolved.exists(), (path, target)


@pytest.mark.skipif(sys.platform == "win32", reason="Bash parallel recipe")
@pytest.mark.parametrize("failure", ["", "google_finance", "google_news_light", "both"])
def test_documented_parallel_recipe_propagates_failures_and_cleans_up(tmp_path, failure):
    source = next(block.source for block in code_blocks((SKILL_ROOT / "references/recipes.md").read_text()) if "serpapi_finance_pid" in block.source)
    binary = tmp_path / "serpapi"
    binary.write_text('''#!/usr/bin/env python3
import json, os, sys, time
engine = next(arg.split("=", 1)[1] for arg in sys.argv if arg.startswith("engine="))
time.sleep(0.1 if engine == "google_news_light" else 0)
with open(os.path.join(os.environ["AUDIT_DIR"], engine), "w") as f: f.write("completed")
if os.environ["AUDIT_FAILURE"] in (engine, "both"): sys.exit(7)
print(json.dumps({engine: "ok"}))
''')
    binary.chmod(0o755)
    run_dir = tmp_path / "responses"
    run_dir.mkdir()
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"], "TMPDIR": str(run_dir), "AUDIT_DIR": str(tmp_path), "AUDIT_FAILURE": failure}
    result = subprocess.run(["bash", "-c", source], env=env, text=True, capture_output=True, timeout=5)
    assert (result.returncode != 0) == bool(failure), result.stdout + result.stderr
    assert (tmp_path / "google_finance").exists() and (tmp_path / "google_news_light").exists()
    assert not list(run_dir.iterdir())
    if failure:
        assert '"ok"' not in result.stdout
    else:
        assert "Finance response:" in result.stdout and "News response:" in result.stdout


@pytest.mark.parametrize("data, expected", [({}, []), ({"place_results": {"title": "Place"}}, ["Place"]), ({"local_results": [{"title": "First"}, {"title": "Second"}]}, ["First", "Second"])])
@pytest.mark.skipif(not shutil.which("jq"), reason="jq is required for extraction checks; see AGENTS.md")
def test_actual_maps_extraction_handles_both_shapes(data, expected):
    source = next(block.source for block in code_blocks((SKILL_ROOT / "references/recipes.md").read_text()) if "--jq" in block.source and "engine=google_maps " in block.source)
    tokens = shlex.split(source)
    result = subprocess.run(["jq", tokens[tokens.index("--jq") + 1]], input=json.dumps(data), capture_output=True, text=True, check=True)
    assert [item["title"] for item in json.loads(result.stdout)] == expected

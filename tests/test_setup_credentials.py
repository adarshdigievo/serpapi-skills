import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/serpapi-setup/scripts/save-key.sh"
FAKE_KEY = "fake-key-for-credential-tests"
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX credential helper")


def save(tmp_path, key=FAKE_KEY, *, config=None, args=(), trace=False):
    env = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(config or tmp_path / ".config"), "SERPAPI_KEY": key}
    return subprocess.run(["bash", *(["-x"] if trace else []), str(SCRIPT), *args], env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)


def test_private_store_exact_bytes_and_no_secret_output(tmp_path):
    result = save(tmp_path, trace=True)
    key_file = tmp_path / ".config/serpapi/api_key"
    assert result.returncode == 0, result.stderr
    assert key_file.read_bytes() == FAKE_KEY.encode()
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(key_file.parent.stat().st_mode) == 0o700
    assert FAKE_KEY not in result.stdout + result.stderr
    assert not list(key_file.parent.glob(".api_key.*"))


def test_existing_key_is_never_overwritten(tmp_path):
    assert save(tmp_path).returncode == 0
    result = save(tmp_path, key="replacement-key")
    assert result.returncode != 0
    assert (tmp_path / ".config/serpapi/api_key").read_text() == FAKE_KEY
    assert "replacement-key" not in result.stdout + result.stderr


@pytest.mark.parametrize("level", ["config", "directory", "file"])
def test_symlink_store_locations_are_rejected(tmp_path, level):
    target = tmp_path / "target"
    target.mkdir()
    config = tmp_path / ".config"
    if level == "config":
        config.symlink_to(target, target_is_directory=True)
    elif level == "directory":
        config.mkdir()
        (config / "serpapi").symlink_to(target, target_is_directory=True)
    else:
        (config / "serpapi").mkdir(parents=True)
        (config / "serpapi/api_key").symlink_to(target / "missing-key")
    result = save(tmp_path)
    assert result.returncode != 0
    assert not list(target.iterdir())
    assert FAKE_KEY not in result.stdout + result.stderr


def test_relative_config_is_rejected(tmp_path):
    result = save(tmp_path, config="relative-config")
    assert result.returncode != 0
    assert FAKE_KEY not in result.stdout + result.stderr


@pytest.mark.parametrize("key", ["with a space", "with\na-newline", "with\ta-tab"])
def test_malformed_key_does_not_create_store_or_echo_input(tmp_path, key):
    result = save(tmp_path, key=key)
    assert result.returncode != 0
    assert not (tmp_path / ".config/serpapi/api_key").exists()
    assert key not in result.stdout + result.stderr


def test_key_content_is_never_evaluated_as_shell_code(tmp_path):
    sentinel = tmp_path / "should-not-exist"
    key = f"$(touch${{IFS}}{sentinel})"
    result = save(tmp_path, key=key)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".config/serpapi/api_key").read_text() == key
    assert not sentinel.exists()
    assert key not in result.stdout + result.stderr


def test_key_argument_is_rejected_without_echo(tmp_path):
    result = save(tmp_path, args=(FAKE_KEY,))
    assert result.returncode != 0
    assert FAKE_KEY not in result.stdout + result.stderr


@pytest.mark.parametrize("git_marker", ["directory", "file", "symlink"])
def test_git_worktree_destination_is_rejected(tmp_path, git_marker):
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = repo / ".git"
    if git_marker == "directory":
        marker.mkdir()
    elif git_marker == "file":
        marker.write_text("gitdir: /missing/worktree-metadata")
    else:
        marker.symlink_to(tmp_path / "missing-git")
    result = save(tmp_path, config=repo / "nested/config")
    assert result.returncode != 0
    assert not (repo / "nested").exists()
    assert FAKE_KEY not in result.stdout + result.stderr


def test_symlinked_ancestor_cannot_hide_worktree(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    alias = tmp_path / "alias"
    alias.symlink_to(repo, target_is_directory=True)
    result = save(tmp_path, config=alias / "new/config")
    assert result.returncode != 0
    assert not (repo / "new").exists()


@pytest.mark.parametrize("marker_kind", ["directory", "file"])
def test_store_directory_itself_cannot_be_a_git_worktree(tmp_path, marker_kind):
    store = tmp_path / ".config/serpapi"
    store.mkdir(parents=True)
    marker = store / ".git"
    if marker_kind == "directory":
        marker.mkdir()
    else:
        marker.write_text("gitdir: /missing/worktree-metadata")
    result = save(tmp_path)
    assert result.returncode != 0
    assert not (store / "api_key").exists()
    assert FAKE_KEY not in result.stdout + result.stderr


@pytest.mark.parametrize("suffix", ["/./config", "/child/../config"])
def test_dot_components_are_rejected(tmp_path, suffix):
    result = save(tmp_path, config=str(tmp_path) + suffix)
    assert result.returncode != 0
    assert not (tmp_path / "config").exists()


def test_shared_config_parent_is_rejected(tmp_path):
    parent = tmp_path / "shared"
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    result = save(tmp_path, config=parent / "config")
    assert result.returncode != 0
    assert not list(parent.iterdir())


def test_concurrent_writers_never_replace_a_key(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    keys = ["first-test-key", "second-test-key"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda key: save(tmp_path, key), keys))
    assert sum(result.returncode == 0 for result in results) == 1
    winner = keys[next(i for i, result in enumerate(results) if result.returncode == 0)]
    key_file = tmp_path / ".config/serpapi/api_key"
    assert key_file.read_text() == winner
    assert not list(key_file.parent.glob(".api_key.*"))
    assert all(key not in result.stdout + result.stderr for key in keys for result in results)


def test_interactive_prompt_hides_input_and_saves_exact_key(tmp_path):
    import errno
    import fcntl
    import pty
    import select
    import termios
    import time

    master, slave = pty.openpty()
    def controlling_terminal():
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
    env = {**os.environ, "HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / ".config")}
    env.pop("SERPAPI_KEY", None)
    process = subprocess.Popen(["bash", str(SCRIPT)], stdin=slave, stdout=slave, stderr=slave, env=env, preexec_fn=controlling_terminal)
    os.close(slave)
    output = b""
    entered = False
    deadline = time.monotonic() + 5
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 4096)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                output += chunk
                if b"SerpApi API key: " in output and not entered:
                    os.write(master, FAKE_KEY.encode() + b"\n")
                    entered = True
            elif process.poll() is not None:
                break
        assert entered, output.decode()
        assert process.wait(timeout=1) == 0, output.decode()
        assert FAKE_KEY.encode() not in output
        assert (tmp_path / ".config/serpapi/api_key").read_bytes() == FAKE_KEY.encode()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        os.close(master)

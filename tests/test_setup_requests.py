import json
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from doc_contracts import ROOT, code_blocks
from verify_doc_examples import run_syntax_check

GUIDE = ROOT / 'skills/serpapi-setup/references/curl.md'
FAKE_KEY = 'test-key-quote"and\\slash'
GOOD_BODY = {"search_metadata": {"status": "Success"}, "organic_results": [{"title": "Coffee", "link": "https://example.com"}]}


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX cURL examples')
@pytest.mark.parametrize('route', ['stdin', 'file'])
@pytest.mark.parametrize('exit_code', [0, 22, 28])
def test_actual_curl_examples_keep_key_out_of_arguments(tmp_path, route, exit_code):
    snippets = [block.source for block in code_blocks(GUIDE.read_text()) if block.language == 'bash' and 'curl -q' in block.source]
    source = snippets[0 if route == 'stdin' else 1]
    binary = tmp_path / 'curl'
    binary.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
assert args[0] == '-q'
assert os.environ['SERPAPI_KEY'] not in '\\n'.join(args)
auth = next(arg for arg in args if arg.startswith('api_key@'))
key = sys.stdin.read() if auth == 'api_key@-' else pathlib.Path(auth.split('@',1)[1]).read_text()
assert key == os.environ['SERPAPI_KEY']
response = pathlib.Path(args[args.index('--output')+1])
response.write_text('{"organic_results":[{"title":"Coffee","link":"https://example.com"}]}')
pathlib.Path(os.environ['AUDIT_CAPTURE']).write_text(str(response))
exit_code = int(os.environ['AUDIT_EXIT'])
if exit_code == 22 and '--fail' not in args:
    print('HTTP 401')
    sys.exit(0)
if exit_code: sys.exit(exit_code)
print('HTTP 200')
''')
    binary.chmod(0o755)
    store = tmp_path / 'config/serpapi'
    store.mkdir(parents=True)
    store.chmod(0o700)
    (store / 'api_key').write_text(FAKE_KEY)
    (store / 'api_key').chmod(0o600)
    capture = tmp_path / 'capture'
    env = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'], 'TMPDIR': str(tmp_path), 'XDG_CONFIG_HOME': str(tmp_path / 'config'), 'SERPAPI_KEY': FAKE_KEY, 'AUDIT_CAPTURE': str(capture), 'AUDIT_EXIT': str(exit_code)}
    result = subprocess.run(['bash', '-c', source + '\nserpapi_status=$?; printf "SHELL_ALIVE\\n"; exit "$serpapi_status"'], env=env, capture_output=True, text=True, timeout=5)
    assert (result.returncode != 0) == bool(exit_code), result.stderr
    assert 'SHELL_ALIVE' in result.stdout
    assert FAKE_KEY not in result.stdout + result.stderr
    response = Path(capture.read_text())
    if exit_code:
        assert not response.exists()
    else:
        assert response.stat().st_mode & 0o777 == 0o600
        assert json.loads(response.read_text())['organic_results'][0]['title'] == 'Coffee'
        response.unlink()


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX credential loading')
@pytest.mark.parametrize('command', ['security find-generic-password', 'secret-tool lookup', 'cat '])
@pytest.mark.parametrize('failure', [False, True])
def test_credential_loaders_preserve_terminal_and_clear_failed_keys(tmp_path, command, failure):
    guide = ROOT / 'skills/serpapi-setup/references/credentials.md'
    source = next(block.source for block in code_blocks(guide.read_text()) if block.language == 'bash' and command in block.source)
    for name in ['security', 'secret-tool']:
        binary = tmp_path / name
        binary.write_text('#!/usr/bin/env bash\nif [ "$AUDIT_FAILURE" = yes ]; then exit 1; fi\nprintf "%s" "$AUDIT_KEY"\n')
        binary.chmod(0o755)
    store = tmp_path / 'config/serpapi'
    store.mkdir(parents=True, mode=0o700)
    if not failure:
        (store / 'api_key').write_text(FAKE_KEY)
        (store / 'api_key').chmod(0o600)
    env = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'], 'XDG_CONFIG_HOME': str(tmp_path / 'config'), 'SERPAPI_KEY': 'stale-test-key', 'AUDIT_KEY': FAKE_KEY, 'AUDIT_FAILURE': 'yes' if failure else 'no'}
    source += '\nserpapi_status=$?\nprintf "SHELL_ALIVE\\n"\nif [ "$serpapi_status" -eq 0 ]; then test "$SERPAPI_KEY" = "$AUDIT_KEY" || exit 9; else test "${SERPAPI_KEY+x}" != x || exit 9; fi\nexit "$serpapi_status"\n'
    result = subprocess.run(['bash', '-c', source], env=env, text=True, capture_output=True, timeout=5)
    assert result.returncode == (1 if failure else 0), result.stderr
    assert 'SHELL_ALIVE' in result.stdout
    assert FAKE_KEY not in result.stdout + result.stderr


@pytest.mark.skipif(not shutil.which('jq'), reason='jq is required for extraction checks; see AGENTS.md')
@pytest.mark.parametrize('body, success', [(GOOD_BODY, True), ({}, False), ({'error': FAKE_KEY}, False), ({'search_metadata': {'status': 'Processing'}, 'organic_results': GOOD_BODY['organic_results']}, False), ({'search_metadata': {'status': 'Success'}, 'organic_results': [{'title': '', 'link': 'https://example.com'}]}, False)])
def test_cli_probe_filter_rejects_incomplete_or_error_responses(body, success):
    guide = ROOT / 'skills/serpapi-setup/references/cli.md'
    line = next(line for block in code_blocks(guide.read_text()) for line in block.source.splitlines() if line.startswith('serpapi search '))
    tokens = shlex.split(line)
    result = subprocess.run(['jq', tokens[tokens.index('--jq') + 1]], input=json.dumps(body), text=True, capture_output=True)
    assert (result.returncode == 0) == success
    assert FAKE_KEY not in result.stdout + result.stderr


@pytest.mark.skipif(not shutil.which('pwsh'), reason='PowerShell runtime unavailable; required in Windows CI')
def test_powershell_parser_checks_actual_examples_and_rejects_invalid_syntax():
    for path in (ROOT / 'skills/serpapi-setup').rglob('*.md'):
        for block in code_blocks(path.read_text()):
            if block.language == 'powershell':
                assert not run_syntax_check('powershell', block.source), path
    assert run_syntax_check('powershell', 'if ( {')


@pytest.mark.skipif(not shutil.which('pwsh'), reason='PowerShell runtime unavailable; required in Windows CI')
@pytest.mark.parametrize('body, http, exit_code, success', [(GOOD_BODY, '200', 0, True), ({'error': 'test error'}, '200', 0, False), ({}, '200', 0, False), ('not-json', '200', 0, False), (GOOD_BODY, '401', 0, False), (GOOD_BODY, '200', 28, False)])
def test_actual_powershell_probe_checks_response_and_cleans_up(tmp_path, body, http, exit_code, success):
    source = next(block.source for block in code_blocks(GUIDE.read_text()) if block.language == 'powershell')
    mock = r'''
function curl.exe {
  $config = $input | Out-String
  if (($args -join ' ').Contains($env:SERPAPI_KEY)) { throw 'Key leaked into arguments' }
  $expectedKey = $env:SERPAPI_KEY.Replace('\', '\\').Replace('"', '\"')
  if (-not $config.Contains('api_key=' + $expectedKey)) { throw 'Incorrect stdin authentication' }
  $outputPath = $args[[Array]::IndexOf($args, '--output') + 1]
  [System.IO.File]::WriteAllText($outputPath, $env:AUDIT_BODY)
  [System.IO.File]::WriteAllText($env:AUDIT_CAPTURE, $outputPath)
  $global:LASTEXITCODE = [int]$env:AUDIT_EXIT
  Write-Output $env:AUDIT_HTTP
}
'''
    script = tmp_path / 'probe.ps1'
    script.write_text(mock + source)
    capture = tmp_path / 'capture'
    env = {**os.environ, 'SERPAPI_KEY': FAKE_KEY, 'AUDIT_BODY': json.dumps(body) if not isinstance(body, str) else body, 'AUDIT_HTTP': http, 'AUDIT_EXIT': str(exit_code), 'AUDIT_CAPTURE': str(capture)}
    result = subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], env=env, text=True, capture_output=True, timeout=20)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    assert FAKE_KEY not in result.stdout + result.stderr
    assert capture.exists(), result.stderr
    assert not Path(capture.read_text()).exists()


@pytest.mark.skipif(not shutil.which('pwsh'), reason='PowerShell runtime unavailable; required in Windows CI')
@pytest.mark.parametrize('ending', [b'', b'\n', b'\r\n'], ids=['no-newline', 'lf', 'crlf'])
def test_powershell_credential_file_round_trip_with_line_endings(tmp_path, ending):
    path = ROOT / 'skills/serpapi-setup/references/credentials.md'
    store, load = [block.source for block in code_blocks(path.read_text()) if block.language == 'powershell']
    script = tmp_path / 'credentials.ps1'
    mock = "function Read-Host { ConvertTo-SecureString $env:AUDIT_KEY -AsPlainText -Force }\n"
    env = {**os.environ, 'LOCALAPPDATA': str(tmp_path), 'AUDIT_KEY': FAKE_KEY, 'SERPAPI_KEY': ''}
    script.write_text(mock + store)
    first = subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], env=env, capture_output=True, text=True, timeout=20)
    assert first.returncode == 0, first.stderr
    key_file = tmp_path / 'SerpApi/api-key.dpapi'
    serialized = key_file.read_bytes()
    assert serialized and not serialized.endswith((b'\r', b'\n'))
    key_file.write_bytes(serialized + ending)
    # File parsing is portable; DPAPI protection is checked separately on Windows.
    script.write_text(load + "\nif ($env:SERPAPI_KEY -ne $env:AUDIT_KEY) { throw 'Round trip failed' }\n")
    second = subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], env=env, capture_output=True, text=True, timeout=20)
    assert second.returncode == 0, second.stderr
    assert FAKE_KEY not in first.stdout + first.stderr + second.stdout + second.stderr


@pytest.mark.skipif(sys.platform != 'win32', reason='DPAPI requires native Windows; exercised in Windows CI')
def test_windows_dpapi_round_trip_and_existing_key_refusal(tmp_path):
    path = ROOT / 'skills/serpapi-setup/references/credentials.md'
    snippets = [block.source for block in code_blocks(path.read_text()) if block.language == 'powershell']
    store, load = snippets
    script = tmp_path / 'dpapi.ps1'
    # Replace only interactive input, leaving the documented DPAPI/file operations intact.
    mock = "function Read-Host { ConvertTo-SecureString $env:AUDIT_KEY -AsPlainText -Force }\n"
    script.write_text(mock + store + '\n' + load + "\nif ($env:SERPAPI_KEY -ne $env:AUDIT_KEY) { throw 'Round trip failed' }\n")
    env = {**os.environ, 'LOCALAPPDATA': str(tmp_path), 'AUDIT_KEY': FAKE_KEY}
    first = subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], env=env, capture_output=True, text=True, timeout=20)
    assert first.returncode == 0, first.stderr
    encrypted = (tmp_path / 'SerpApi/api-key.dpapi').read_bytes()
    assert FAKE_KEY.encode() not in encrypted
    second = subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], env=env, capture_output=True, text=True, timeout=20)
    assert second.returncode != 0
    assert (tmp_path / 'SerpApi/api-key.dpapi').read_bytes() == encrypted
    assert FAKE_KEY not in first.stdout + first.stderr + second.stdout + second.stderr

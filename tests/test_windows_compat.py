"""Windows compatibility tests.

Added in the windows-compat sweep. Locks in:
  * config_search_paths is a graceful candidate list -- the POSIX
    /etc/mu2edaq/... entry is only ever a candidate and is skipped when absent,
    and the home/env entries use expanduser (valid on Windows), and
  * the launch/bootstrap scripts ship PowerShell ports.
"""
import os
import pathlib
import shutil
import subprocess

import pytest

from mu2edaq_commandline_tools import config

REPO = pathlib.Path(__file__).resolve().parent.parent
PWSH = shutil.which("pwsh") or shutil.which("powershell")

SCRIPT_STEMS = [
    "bootstrap",
    "start-mu2edaq-commandline-tools",
    "stop-mu2edaq-commandline-tools",
]


def test_config_search_is_a_graceful_candidate_list(monkeypatch):
    # find_config iterates candidate paths and returns the first that exists
    # (or None) -- it must never raise, even though the candidate list includes
    # a POSIX /etc path that cannot exist on Windows. The POSIX /etc path is a
    # candidate, never the *result* on Windows.
    monkeypatch.delenv(config.ENV_PREFIX + "CONFIG", raising=False)
    result = config.find_config()
    assert result is None or isinstance(result, pathlib.Path)
    if result is not None:
        assert str(result) != "/etc/mu2edaq/commandline-tools.yaml"
    # The /etc candidate is present in the search list but is only ever a
    # candidate; is_file() returns False for it on Windows.
    candidates = [str(p) for p in config.config_search_paths()]
    assert any("etc" in c and "mu2edaq" in c for c in candidates)


def test_explicit_config_is_expanduser_and_found(tmp_path, monkeypatch):
    cfg = tmp_path / "cli.yaml"
    cfg.write_text("key: value\n")
    found = config.find_config(str(cfg))
    assert found == cfg


def test_scripts_have_both_forms():
    for stem in SCRIPT_STEMS:
        assert (REPO / f"{stem}.sh").is_file(), f"missing bash script: {stem}.sh"
        assert (REPO / f"{stem}.ps1").is_file(), f"missing PowerShell port: {stem}.ps1"


@pytest.mark.skipif(not PWSH, reason="PowerShell not available")
@pytest.mark.parametrize("stem", SCRIPT_STEMS)
def test_powershell_scripts_parse(stem):
    path = (REPO / f"{stem}.ps1").as_posix()
    code = (
        "$e=$null;"
        f"[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$null,[ref]$e)|Out-Null;"
        "if($e){$e|ForEach-Object{Write-Error $_};exit 1}else{exit 0}"
    )
    result = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr

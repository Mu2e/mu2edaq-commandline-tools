"""Smoke tests for the mu2edaq-tools dispatcher."""

import json

import pytest

from mu2edaq_commandline_tools import __version__, cli


def test_no_command_prints_help(capsys):
    assert cli.main([]) == 2
    assert "usage:" in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_version_command(capsys):
    assert cli.main(["version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_list_shows_every_command(capsys):
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    for name in cli.COMMANDS:
        assert name in out


def test_config_json_reflects_cli_override(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MU2EDAQ_TOOLS_CONFIG", raising=False)
    assert cli.main(["--cluster", "testbed", "config", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["values"]["cluster"] == "testbed"


def test_config_reports_the_file_in_use(tmp_path, capsys):
    path = tmp_path / "tools.yaml"
    path.write_text("cluster: from-file\n", encoding="utf-8")
    assert cli.main(["--config", str(path), "config"]) == 0
    out = capsys.readouterr().out
    assert str(path) in out
    assert "from-file" in out


def test_bad_config_file_exits_nonzero(tmp_path, capsys):
    path = tmp_path / "tools.yaml"
    path.write_text("- not a mapping\n", encoding="utf-8")
    assert cli.main(["--config", str(path), "config"]) == 1
    assert "must be a mapping" in capsys.readouterr().err


def test_every_command_has_help_text():
    for name, cmd in cli.COMMANDS.items():
        assert cmd.help, "%s has no help text" % name
        assert callable(cmd.run)

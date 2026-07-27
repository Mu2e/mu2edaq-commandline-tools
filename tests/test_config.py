"""Config precedence: command line > environment > config file > defaults."""

import pytest

from mu2edaq_commandline_tools import config as configmod


@pytest.fixture()
def cfg_file(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text(
        "cluster: from-file\n"
        "discovery_timeout: 7.5\n"
        "log_level: WARNING\n",
        encoding="utf-8",
    )
    return path


def test_defaults_only(tmp_path, monkeypatch):
    # No file anywhere on the search path: the defaults stand on their own.
    monkeypatch.setattr(configmod, "config_search_paths",
                        lambda explicit=None: iter([tmp_path / "absent.yaml"]))
    cfg = configmod.load(environ={})
    assert cfg["cluster"] == configmod.DEFAULTS["cluster"]
    assert cfg["_config_file"] is None


def test_checkout_config_is_on_the_search_path(tmp_path, monkeypatch):
    # The reference copy shipped in the checkout is the fallback for a dev
    # install, so it is found even from an unrelated working directory.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MU2EDAQ_TOOLS_CONFIG", raising=False)
    found = configmod.find_config()
    assert found is not None
    assert found.name == "mu2edaq-commandline-tools.yaml"


def test_file_beats_defaults(cfg_file):
    cfg = configmod.load(str(cfg_file), environ={})
    assert cfg["cluster"] == "from-file"
    assert cfg["discovery_timeout"] == 7.5
    assert cfg["_config_file"] == str(cfg_file)


def test_env_beats_file(cfg_file):
    cfg = configmod.load(str(cfg_file), environ={"MU2EDAQ_TOOLS_CLUSTER": "from-env"})
    assert cfg["cluster"] == "from-env"
    assert cfg["log_level"] == "WARNING"  # untouched by the environment


def test_cli_beats_env(cfg_file):
    cfg = configmod.load(
        str(cfg_file),
        overrides={"cluster": "from-cli"},
        environ={"MU2EDAQ_TOOLS_CLUSTER": "from-env"},
    )
    assert cfg["cluster"] == "from-cli"


def test_unset_cli_option_does_not_clobber(cfg_file):
    cfg = configmod.load(str(cfg_file), overrides={"cluster": None}, environ={})
    assert cfg["cluster"] == "from-file"


def test_env_values_are_coerced():
    cfg = configmod.load(
        environ={"MU2EDAQ_TOOLS_DISCOVERY_TIMEOUT": "5", "MU2EDAQ_TOOLS_COLOR": "no"}
    )
    assert cfg["discovery_timeout"] == 5.0
    assert cfg["color"] is False


def test_unknown_keys_in_file_are_ignored(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text("cluster: ok\nnot_a_setting: 1\n", encoding="utf-8")
    cfg = configmod.load(str(path), environ={})
    assert cfg["cluster"] == "ok"
    assert "not_a_setting" not in cfg


def test_non_mapping_file_is_rejected(tmp_path):
    path = tmp_path / "tools.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        configmod.load(str(path), environ={})


def test_missing_explicit_file_falls_back_to_defaults(tmp_path):
    cfg = configmod.load(str(tmp_path / "nope.yaml"), environ={})
    assert cfg["cluster"] == configmod.DEFAULTS["cluster"]
    assert cfg["_config_file"] is None

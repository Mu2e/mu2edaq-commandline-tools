"""Named profile, URL derivation, TLS, and credential tests."""

from pathlib import Path

import pytest

from mu2edaq_commandline_tools.otsdaq import OtsdaqConfigError, resolve_instance


def base_cfg():
    return {
        "otsdaq": {
            "default_instance": "crv",
            "timeout": 10.0,
            "verify_tls": False,
            "instances": {
                "crv": {
                    "gateway_url": "https://daq.example:8443",
                }
            },
        }
    }


def test_profile_and_service_url_derivation():
    instance = resolve_instance(base_cfg(), environ={})
    assert instance.name == "crv"
    assert instance.gateway_url == "https://daq.example:8443"
    assert instance.slow_controls_url == "https://daq.example:8444"
    assert instance.tfm_url == "https://daq.example:3047"
    assert instance.timeout == 10.0
    assert instance.requests_verify is False


def test_explicit_service_urls_and_cli_values_win():
    cfg = base_cfg()
    cfg["otsdaq"]["instances"]["crv"].update(
        {
            "slow_controls_url": "http://slow.example:5000",
            "tfm_url": "http://tfm.example:5001",
            "timeout": 4,
            "verify_tls": True,
        }
    )
    instance = resolve_instance(
        cfg,
        gateway_url="http://override.example:7000",
        timeout=2,
        verify_tls=False,
        environ={},
    )
    assert instance.gateway_url == "http://override.example:7000"
    assert instance.slow_controls_url == "http://slow.example:5000"
    assert instance.tfm_url == "http://tfm.example:5001"
    assert instance.timeout == 2
    assert instance.verify_tls is False


def test_environment_overrides_profile():
    instance = resolve_instance(
        base_cfg(),
        environ={
            "MU2EDAQ_TOOLS_OTSDAQ_GATEWAY_URL": "http://env.example:9000",
            "MU2EDAQ_TOOLS_OTSDAQ_TIMEOUT": "3.5",
            "MU2EDAQ_TOOLS_OTSDAQ_VERIFY_TLS": "true",
        },
    )
    assert instance.gateway_url == "http://env.example:9000"
    assert instance.timeout == 3.5
    assert instance.verify_tls is True


def test_gateway_override_can_be_ephemeral():
    instance = resolve_instance(
        {"otsdaq": {"instances": {}}},
        gateway_url="http://localhost:3075",
        environ={},
    )
    assert instance.name == "<override>"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://daq.example:8443",
        "https://user:pass@daq.example:8443",
        "https://daq.example:8443/path",
        "https://daq.example:bad",
    ],
)
def test_invalid_origins_are_rejected(url):
    with pytest.raises(OtsdaqConfigError):
        resolve_instance(
            {"otsdaq": {"instances": {}}},
            gateway_url=url,
            environ={},
        )


def test_missing_and_unknown_instances_are_errors():
    with pytest.raises(OtsdaqConfigError, match="no otsdaq instance"):
        resolve_instance({"otsdaq": {"instances": {}}}, environ={})
    with pytest.raises(OtsdaqConfigError, match="unknown otsdaq instance"):
        resolve_instance(base_cfg(), instance="tracker", environ={})


def test_cookie_environment_wins_over_owner_only_file(tmp_path):
    path = tmp_path / "cookie"
    path.write_text("from-file\n", encoding="utf-8")
    path.chmod(0o600)
    cfg = base_cfg()
    cfg["otsdaq"]["instances"]["crv"]["cookie_file"] = str(path)
    instance = resolve_instance(
        cfg, environ={"MU2EDAQ_TOOLS_OTSDAQ_COOKIE": "from-env"}
    )
    assert instance.cookie_code == "from-env"


def test_cookie_file_must_be_owner_only(tmp_path):
    path = tmp_path / "cookie"
    path.write_text("secret\n", encoding="utf-8")
    path.chmod(0o644)
    cfg = base_cfg()
    cfg["otsdaq"]["instances"]["crv"]["cookie_file"] = str(path)
    with pytest.raises(OtsdaqConfigError, match="chmod 600"):
        resolve_instance(cfg, environ={})


def test_ca_bundle_enables_verification(tmp_path):
    bundle = tmp_path / "ca.pem"
    bundle.write_text("not used by this unit test", encoding="utf-8")
    instance = resolve_instance(base_cfg(), ca_bundle=str(bundle), environ={})
    assert instance.verify_tls is True
    assert instance.requests_verify == str(bundle)

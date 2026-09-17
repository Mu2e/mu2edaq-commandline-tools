"""Configuration loading for the mu2edaq command line tools.

Precedence, highest first:

    1. command line options
    2. environment variables (MU2EDAQ_TOOLS_*)
    3. YAML config file
    4. built-in defaults

The YAML file is looked up in this order unless an explicit path is given:

    $MU2EDAQ_TOOLS_CONFIG
    ./mu2edaq-commandline-tools.yaml
    ./config/mu2edaq-commandline-tools.yaml
    <package checkout>/config/mu2edaq-commandline-tools.yaml
    ~/.config/mu2edaq/commandline-tools.yaml
    /etc/mu2edaq/commandline-tools.yaml

Nothing here is required: with no config file and no environment at all the
defaults are a usable configuration.
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    import yaml
except ImportError:  # PyYAML is a declared dependency, but stay usable without it
    yaml = None

ENV_PREFIX = "MU2EDAQ_TOOLS_"

#: Built-in defaults. The original flat keys map 1:1 onto
#: MU2EDAQ_TOOLS_<KEY>; otsdaq has its own documented nested overrides.
OTSDAQ_DEFAULTS: Dict[str, Any] = {
    "default_instance": None,
    "timeout": 10.0,
    "verify_tls": False,
    "ca_bundle": None,
    "gateway_url": None,
    "slow_controls_url": None,
    "tfm_url": None,
    "cookie_file": None,
    "instances": {},
}

DEFAULTS: Dict[str, Any] = {
    "cluster": "mu2edaq",
    "discovery_timeout": 2.0,
    "log_level": "INFO",
    "log_dir": "logs",
    "color": True,
    "otsdaq": OTSDAQ_DEFAULTS,
}

#: Coercion applied to values coming from YAML or the environment, so that
#: MU2EDAQ_TOOLS_DISCOVERY_TIMEOUT=5 lands as a float and not the string "5".
_COERCE = {
    "discovery_timeout": float,
    "color": lambda v: str(v).strip().lower() in ("1", "true", "yes", "on"),
}

_OTSDAQ_ENV = {
    "INSTANCE": ("default_instance", str),
    "TIMEOUT": ("timeout", float),
    "VERIFY_TLS": (
        "verify_tls",
        lambda v: str(v).strip().lower() in ("1", "true", "yes", "on"),
    ),
    "CA_BUNDLE": ("ca_bundle", str),
    "GATEWAY_URL": ("gateway_url", str),
    "SLOW_CONTROLS_URL": ("slow_controls_url", str),
    "TFM_URL": ("tfm_url", str),
    "COOKIE_FILE": ("cookie_file", str),
}


def _coerce(key: str, value: Any) -> Any:
    fn = _COERCE.get(key)
    if fn is None or value is None:
        return value
    try:
        return fn(value)
    except (TypeError, ValueError):
        return value


def _merge_otsdaq(base: Dict[str, Any], update: Any) -> Dict[str, Any]:
    """Merge the supported nested otsdaq configuration keys."""
    out = deepcopy(base)
    if not isinstance(update, dict):
        return out
    for key in OTSDAQ_DEFAULTS:
        if key not in update:
            continue
        if key == "instances":
            if isinstance(update[key], dict):
                out[key] = deepcopy(update[key])
        elif key == "timeout":
            try:
                out[key] = float(update[key])
            except (TypeError, ValueError):
                out[key] = update[key]
        elif key == "verify_tls":
            out[key] = str(update[key]).strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        else:
            out[key] = update[key]
    return out


def config_search_paths(explicit: Optional[str] = None) -> Iterable[Path]:
    """Yield candidate config file locations, most specific first."""
    if explicit:
        yield Path(explicit).expanduser()
        return
    env_path = os.environ.get(ENV_PREFIX + "CONFIG")
    if env_path:
        yield Path(env_path).expanduser()
    yield Path.cwd() / "mu2edaq-commandline-tools.yaml"
    yield Path.cwd() / "config" / "mu2edaq-commandline-tools.yaml"
    yield Path(__file__).resolve().parents[2] / "config" / "mu2edaq-commandline-tools.yaml"
    yield Path.home() / ".config" / "mu2edaq" / "commandline-tools.yaml"
    yield Path("/etc/mu2edaq/commandline-tools.yaml")


def find_config(explicit: Optional[str] = None) -> Optional[Path]:
    """Return the first config file that exists, or None."""
    for path in config_search_paths(explicit):
        if path.is_file():
            return path
    return None


def load_file(path: Optional[Path]) -> Dict[str, Any]:
    """Read a YAML config file into a flat dict. Missing file -> empty dict."""
    if path is None or not path.is_file():
        return {}
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to read %s (pip install PyYAML)" % path
        )
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s: top level of the config file must be a mapping" % path)
    out = {k: _coerce(k, v) for k, v in data.items() if k in DEFAULTS and k != "otsdaq"}
    if "otsdaq" in data:
        if not isinstance(data["otsdaq"], dict):
            raise ValueError("%s: otsdaq must be a mapping" % path)
        instances = data["otsdaq"].get("instances")
        if instances is not None:
            if not isinstance(instances, dict):
                raise ValueError("%s: otsdaq.instances must be a mapping" % path)
            for name, profile in instances.items():
                if not isinstance(profile, dict):
                    raise ValueError(
                        "%s: otsdaq instance %r must be a mapping" % (path, name)
                    )
        out["otsdaq"] = _merge_otsdaq(OTSDAQ_DEFAULTS, data["otsdaq"])
    return out


def load_env(environ: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Collect MU2EDAQ_TOOLS_* overrides for known keys."""
    environ = os.environ if environ is None else environ
    out: Dict[str, Any] = {}
    for key in DEFAULTS:
        if key == "otsdaq":
            continue
        raw = environ.get(ENV_PREFIX + key.upper())
        if raw is not None and raw != "":
            out[key] = _coerce(key, raw)
    otsdaq = {}
    for suffix, (key, coerce) in _OTSDAQ_ENV.items():
        raw = environ.get(ENV_PREFIX + "OTSDAQ_" + suffix)
        if raw is None or raw == "":
            continue
        try:
            otsdaq[key] = coerce(raw)
        except (TypeError, ValueError):
            otsdaq[key] = raw
    if otsdaq:
        out["otsdaq"] = otsdaq
    return out


def load(
    explicit_path: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    environ: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build the effective configuration.

    `overrides` carries the command line values and wins over everything;
    entries whose value is None are ignored so that an unset argparse option
    does not clobber a lower-precedence source.
    """
    cfg = deepcopy(DEFAULTS)
    path = find_config(explicit_path)
    file_values = load_file(path)
    env_values = load_env(environ)
    for values in (file_values, env_values):
        otsdaq = values.pop("otsdaq", None)
        cfg.update(values)
        if otsdaq is not None:
            cfg["otsdaq"] = _merge_otsdaq(cfg["otsdaq"], otsdaq)
    for key, value in (overrides or {}).items():
        if value is not None and key in DEFAULTS:
            if key == "otsdaq":
                cfg[key] = _merge_otsdaq(cfg[key], value)
            else:
                cfg[key] = value
    cfg["_config_file"] = str(path) if path else None
    return cfg

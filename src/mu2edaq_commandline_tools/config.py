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
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:
    import yaml
except ImportError:  # PyYAML is a declared dependency, but stay usable without it
    yaml = None

ENV_PREFIX = "MU2EDAQ_TOOLS_"

#: Built-in defaults. Keys map 1:1 onto MU2EDAQ_TOOLS_<KEY> environment
#: variables and onto top-level keys in the YAML config file.
DEFAULTS: Dict[str, Any] = {
    "cluster": "mu2edaq",
    "discovery_timeout": 2.0,
    "log_level": "INFO",
    "log_dir": "logs",
    "color": True,
}

#: Coercion applied to values coming from YAML or the environment, so that
#: MU2EDAQ_TOOLS_DISCOVERY_TIMEOUT=5 lands as a float and not the string "5".
_COERCE = {
    "discovery_timeout": float,
    "color": lambda v: str(v).strip().lower() in ("1", "true", "yes", "on"),
}


def _coerce(key: str, value: Any) -> Any:
    fn = _COERCE.get(key)
    if fn is None or value is None:
        return value
    try:
        return fn(value)
    except (TypeError, ValueError):
        return value


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
    return {k: _coerce(k, v) for k, v in data.items() if k in DEFAULTS}


def load_env(environ: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Collect MU2EDAQ_TOOLS_* overrides for known keys."""
    environ = os.environ if environ is None else environ
    out: Dict[str, Any] = {}
    for key in DEFAULTS:
        raw = environ.get(ENV_PREFIX + key.upper())
        if raw is not None and raw != "":
            out[key] = _coerce(key, raw)
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
    cfg = dict(DEFAULTS)
    path = find_config(explicit_path)
    cfg.update(load_file(path))
    cfg.update(load_env(environ))
    for key, value in (overrides or {}).items():
        if value is not None and key in DEFAULTS:
            cfg[key] = value
    cfg["_config_file"] = str(path) if path else None
    return cfg

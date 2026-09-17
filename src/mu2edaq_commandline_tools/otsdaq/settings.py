"""Resolve named otsdaq connection profiles."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .models import OtsdaqConfigError


@dataclass(frozen=True)
class InstanceConfig:
    """Fully resolved origins and request settings for one otsdaq instance."""

    name: str
    gateway_url: str
    slow_controls_url: str
    tfm_url: str
    timeout: float
    verify_tls: bool
    ca_bundle: Optional[str] = None
    cookie_code: Optional[str] = None

    @property
    def requests_verify(self) -> object:
        return self.ca_bundle or self.verify_tls

    def origin_for(self, lid: int, service: Optional[str] = None) -> str:
        if service == "slow-controls" or (service is None and lid == 282):
            return self.slow_controls_url
        if service == "tfm" or (service is None and lid == 302):
            return self.tfm_url
        return self.gateway_url


def _origin(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OtsdaqConfigError("%s is required" % field)
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise OtsdaqConfigError("%s must be an http(s) origin: %s" % (field, value))
    if parsed.username or parsed.password:
        raise OtsdaqConfigError("%s must not contain credentials" % field)
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise OtsdaqConfigError("%s must not contain a path, query, or fragment" % field)
    try:
        parsed.port
    except ValueError as exc:
        raise OtsdaqConfigError("%s has an invalid port: %s" % (field, exc)) from exc
    return value


def _with_port(origin: str, port: int) -> str:
    parsed = urlsplit(origin)
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = "[%s]" % hostname
    netloc = "%s:%d" % (hostname, port)
    return urlunsplit(SplitResult(parsed.scheme, netloc, "", "", ""))


def _derived_slow_controls(gateway: str) -> str:
    parsed = urlsplit(gateway)
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    if port >= 65535:
        raise OtsdaqConfigError("gateway port cannot be incremented for Slow Controls")
    return _with_port(gateway, port + 1)


def _read_cookie(path_value: Any) -> Optional[str]:
    if not path_value:
        return None
    path = Path(str(path_value)).expanduser()
    try:
        info = path.stat()
    except OSError as exc:
        raise OtsdaqConfigError("cannot read otsdaq cookie file %s: %s" % (path, exc)) from exc
    if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
        raise OtsdaqConfigError(
            "otsdaq cookie file %s must be owner-only (chmod 600)" % path
        )
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise OtsdaqConfigError("cannot read otsdaq cookie file %s: %s" % (path, exc)) from exc
    if not value:
        raise OtsdaqConfigError("otsdaq cookie file %s is empty" % path)
    return value


def resolve_instance(
    cfg: Mapping[str, Any],
    *,
    instance: Optional[str] = None,
    gateway_url: Optional[str] = None,
    slow_controls_url: Optional[str] = None,
    tfm_url: Optional[str] = None,
    timeout: Optional[float] = None,
    verify_tls: Optional[bool] = None,
    ca_bundle: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> InstanceConfig:
    """Resolve a named profile plus environment/CLI connection overrides."""
    otsdaq = cfg.get("otsdaq") or {}
    if not isinstance(otsdaq, dict):
        raise OtsdaqConfigError("otsdaq configuration must be a mapping")
    instances = otsdaq.get("instances") or {}
    if not isinstance(instances, dict):
        raise OtsdaqConfigError("otsdaq.instances must be a mapping")

    environ = os.environ if environ is None else environ
    name = (
        instance
        or environ.get("MU2EDAQ_TOOLS_OTSDAQ_INSTANCE")
        or otsdaq.get("default_instance")
    )
    profile: Dict[str, Any] = {}
    if name:
        if name not in instances:
            raise OtsdaqConfigError("unknown otsdaq instance %r" % name)
        if not isinstance(instances[name], dict):
            raise OtsdaqConfigError("otsdaq instance %r must be a mapping" % name)
        profile.update(instances[name])
    elif not (
        gateway_url
        or environ.get("MU2EDAQ_TOOLS_OTSDAQ_GATEWAY_URL")
        or otsdaq.get("gateway_url")
    ):
        raise OtsdaqConfigError(
            "no otsdaq instance selected; set otsdaq.default_instance or use --instance"
        )
    else:
        name = "<override>"

    # Global YAML settings are defaults for profiles. Environment and explicit
    # function arguments then override the selected profile.
    merged: Dict[str, Any] = {}
    for key in (
        "gateway_url",
        "slow_controls_url",
        "tfm_url",
        "timeout",
        "verify_tls",
        "ca_bundle",
        "cookie_file",
    ):
        if otsdaq.get(key) is not None:
            merged[key] = otsdaq[key]
    merged.update(profile)
    env_keys = {
        "gateway_url": "MU2EDAQ_TOOLS_OTSDAQ_GATEWAY_URL",
        "slow_controls_url": "MU2EDAQ_TOOLS_OTSDAQ_SLOW_CONTROLS_URL",
        "tfm_url": "MU2EDAQ_TOOLS_OTSDAQ_TFM_URL",
        "timeout": "MU2EDAQ_TOOLS_OTSDAQ_TIMEOUT",
        "verify_tls": "MU2EDAQ_TOOLS_OTSDAQ_VERIFY_TLS",
        "ca_bundle": "MU2EDAQ_TOOLS_OTSDAQ_CA_BUNDLE",
        "cookie_file": "MU2EDAQ_TOOLS_OTSDAQ_COOKIE_FILE",
    }
    for key, env_name in env_keys.items():
        if environ.get(env_name):
            merged[key] = environ[env_name]
    explicit = {
        "gateway_url": gateway_url,
        "slow_controls_url": slow_controls_url,
        "tfm_url": tfm_url,
        "timeout": timeout,
        "verify_tls": verify_tls,
        "ca_bundle": ca_bundle,
    }
    for key, value in explicit.items():
        if value is not None:
            merged[key] = value

    gateway = _origin(merged.get("gateway_url"), "gateway_url")
    slow = merged.get("slow_controls_url") or _derived_slow_controls(gateway)
    tfm = merged.get("tfm_url") or _with_port(gateway, 3047)
    slow = _origin(slow, "slow_controls_url")
    tfm = _origin(tfm, "tfm_url")

    try:
        request_timeout = float(merged.get("timeout", 10.0))
    except (TypeError, ValueError) as exc:
        raise OtsdaqConfigError("otsdaq timeout must be a number") from exc
    if request_timeout <= 0:
        raise OtsdaqConfigError("otsdaq timeout must be greater than zero")

    verify_value = merged.get("verify_tls", False)
    verify = (
        verify_value
        if isinstance(verify_value, bool)
        else str(verify_value).strip().lower() in ("1", "true", "yes", "on")
    )
    bundle = merged.get("ca_bundle")
    if bundle:
        bundle_path = Path(str(bundle)).expanduser()
        if not bundle_path.is_file():
            raise OtsdaqConfigError("CA bundle does not exist: %s" % bundle_path)
        bundle = str(bundle_path)
        verify = True

    cookie = environ.get("MU2EDAQ_TOOLS_OTSDAQ_COOKIE") or _read_cookie(
        merged.get("cookie_file")
    )
    return InstanceConfig(
        name=str(name),
        gateway_url=gateway,
        slow_controls_url=slow,
        tfm_url=tfm,
        timeout=request_timeout,
        verify_tls=verify,
        ca_bundle=bundle,
        cookie_code=cookie,
    )

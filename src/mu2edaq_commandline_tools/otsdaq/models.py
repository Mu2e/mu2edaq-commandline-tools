"""Data models and exceptions for the otsdaq client."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


class OtsdaqError(RuntimeError):
    """Base class for user-facing otsdaq failures."""


class OtsdaqConfigError(OtsdaqError):
    """The selected otsdaq connection is not usable."""


class OtsdaqTransportError(OtsdaqError):
    """The HTTP request could not be completed."""


class OtsdaqHTTPError(OtsdaqError):
    """The server returned a non-success HTTP status."""


class OtsdaqProtocolError(OtsdaqError):
    """The server response did not match the otsdaq protocol."""


@dataclass(frozen=True)
class FEMacro:
    """One macro advertised by Macro Maker."""

    macro_type: str
    name: str
    required_permissions: str
    inputs: List[str]
    outputs: List[str]
    supervisor: Optional[str] = None
    lid: Optional[int] = None
    fe_class: Optional[str] = None
    fe_uid: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OtsdaqResponse:
    """Both exact and parsed forms of an otsdaq HTTP response."""

    status_code: int
    url: str
    xml: str
    normalized: Dict[str, Any]
    data: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return self.normalized

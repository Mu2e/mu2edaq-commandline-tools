"""Read-only otsdaq HTTP client support."""

from .client import OtsdaqClient
from .models import (
    FEMacro,
    OtsdaqConfigError,
    OtsdaqError,
    OtsdaqHTTPError,
    OtsdaqProtocolError,
    OtsdaqResponse,
    OtsdaqTransportError,
)
from .settings import InstanceConfig, resolve_instance

__all__ = [
    "FEMacro",
    "InstanceConfig",
    "OtsdaqClient",
    "OtsdaqConfigError",
    "OtsdaqError",
    "OtsdaqHTTPError",
    "OtsdaqProtocolError",
    "OtsdaqResponse",
    "OtsdaqTransportError",
    "resolve_instance",
]

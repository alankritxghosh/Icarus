"""Read-only repository decision intelligence."""

from .contracts import ErrorCode, InspectionError
from .inspector import inspect_repository

__all__ = ["ErrorCode", "InspectionError", "inspect_repository"]
__version__ = "0.1.0"

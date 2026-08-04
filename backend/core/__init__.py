"""
Core application components.
"""
from backend.core.config import get_settings
from backend.core.startup import initialize_application

__all__ = [
    "get_settings",
    "initialize_application",
]

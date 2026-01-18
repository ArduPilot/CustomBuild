"""
Core application components.
"""
from .config import get_settings
from .startup import initialize_application

__all__ = [
    "get_settings",
    "initialize_application",
]

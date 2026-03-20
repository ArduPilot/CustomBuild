"""
Core application components.
"""
from web.core.config import get_settings
from web.core.startup import initialize_application

__all__ = [
    "get_settings",
    "initialize_application",
]

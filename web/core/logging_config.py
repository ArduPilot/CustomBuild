"""
Logging configuration for the application.
"""
import logging
import logging.config
import os
import sys


def setup_logging(log_level: str = None):
    """
    Configure logging for the application and all imported modules.

    This must be called BEFORE importing any modules that use logging,
    to ensure they all use the same logging configuration.

    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   If None, reads from CBS_LOG_LEVEL environment variable.
    """
    if log_level is None:
        log_level = os.getenv('CBS_LOG_LEVEL', default='INFO')

    # Configure logging with dictConfig for consistency with Flask app
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': (
                    '[%(asctime)s] %(levelname)s in %(module)s: '
                    '%(message)s'
                ),
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'detailed': {
                'format': (
                    '[%(asctime)s] %(levelname)s '
                    '[%(name)s.%(funcName)s:%(lineno)d] %(message)s'
                ),
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,
                'formatter': 'default',
                'level': log_level.upper(),
            },
        },
        'root': {
            'level': log_level.upper(),
            'handlers': ['console'],
        },
        'loggers': {
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'uvicorn.access': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'uvicorn.error': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'fastapi': {
                'level': log_level.upper(),
                'handlers': ['console'],
                'propagate': False,
            },
        },
    }

    logging.config.dictConfig(logging_config)

    # Log that logging has been configured
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level.upper()}")
    logger.info(f"Python version: {sys.version}")

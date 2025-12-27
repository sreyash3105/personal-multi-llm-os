"""
Observability Configuration for Local AI OS

Provides consistent logging schema, correlation IDs, and structured observability
across all components.
"""

import logging
import logging.config
import sys
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional, Dict, Any

# Context variables for execution correlation
execution_id: ContextVar[Optional[str]] = ContextVar('execution_id', default=None)
session_id: ContextVar[Optional[str]] = ContextVar('session_id', default=None)

class ExecutionIdFilter(logging.Filter):
    """Add execution ID to all log records."""

    def filter(self, record):
        record.execution_id = execution_id.get() or "no-execution"
        record.session_id = session_id.get() or "no-session"
        return True

class ComponentAdapter(logging.LoggerAdapter):
    """Logger adapter that adds component context."""

    def __init__(self, logger, component: str):
        super().__init__(logger, {'component': component})

    def process(self, msg, kwargs):
        # Add component to all messages
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        if self.extra and 'component' in self.extra:
            kwargs['extra']['component'] = self.extra['component']
        return msg, kwargs

def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """
    Configure logging for entire application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging output
    """

    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'execution_id': {
                '()': ExecutionIdFilter,
            },
        },
        'formatters': {
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(component)s %(name)s %(execution_id)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'simple': {
                'format': '[%(levelname)s] %(component)s - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': level,
                'formatter': 'simple',
                'stream': sys.stdout,
                'filters': ['execution_id']
            }
        },
        'root': {
            'level': level,
            'handlers': ['console']
        },
        'loggers': {
            # Specific loggers for different components
            'ai_os.runner': {'level': level, 'propagate': True},
            'ai_os.models': {'level': level, 'propagate': True},
            'ai_os.queue': {'level': level, 'propagate': True},
            'ai_os.storage': {'level': level, 'propagate': True},
            'ai_os.security': {'level': level, 'propagate': True},
        }
    }

    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        config['handlers']['file'] = {
            'class': 'logging.FileHandler',
            'level': level,
            'formatter': 'detailed',
            'filename': str(log_file),
            'filters': ['execution_id']
        }
        config['root']['handlers'].append('file')

    logging.config.dictConfig(config)

def get_logger(component: str) -> ComponentAdapter:
    """
    Get a logger for a specific component.

    Args:
        component: Component name (e.g., 'runner', 'models.llm', 'queue.manager')

    Returns:
        Logger adapter with component context
    """
    logger = logging.getLogger(f'ai_os.{component}')
    return ComponentAdapter(logger, component)

def set_execution_context(execution_id_val: Optional[str] = None,
                         session_id_val: Optional[str] = None) -> None:
    """Set execution and session context for logging."""
    if execution_id_val:
        execution_id.set(execution_id_val)
    if session_id_val:
        session_id.set(session_id_val)

def generate_execution_id() -> str:
    """Generate a new execution ID."""
    return str(uuid.uuid4())[:8]

# Convenience functions for common logging patterns
def log_execution(component: str, operation: str,
                 context_id: Optional[str] = None, **kwargs) -> ComponentAdapter:
    """Log execution with structured context."""
    logger = get_logger(f'runner.{component}')
    logger.info(f"Execution {operation}",
               extra={'execution_id': context_id or 'no-exec', **kwargs})
    return logger

def log_model_inference(model_name: str, operation: str,
                   input_tokens: Optional[int] = None,
                   **kwargs) -> ComponentAdapter:
    """Log model inference with performance context."""
    logger = get_logger(f'models.{model_name}')
    logger.info(f"Model {operation}",
               extra={'input_tokens': input_tokens, **kwargs})
    return logger

def log_queue_operation(operation: str, job_id: Optional[str] = None,
                   profile_id: Optional[str] = None, **kwargs) -> ComponentAdapter:
    """Log queue operations with job context."""
    logger = get_logger('queue.manager')
    logger.info(f"Queue {operation}",
               extra={'job_id': job_id, 'profile_id': profile_id, **kwargs})
    return logger

def log_security_event(event_type: str, severity: str = "INFO",
                      profile_id: Optional[str] = None, **kwargs) -> ComponentAdapter:
    """Log security events with appropriate severity."""
    logger = get_logger('security.events')
    log_method = getattr(logger, severity.lower(), logger.info)
    log_method(f"Security {event_type}",
               extra={'profile_id': profile_id or 'system', **kwargs})
    return logger

# Performance timing utilities
class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, logger: ComponentAdapter, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: float = 0.0

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"Starting {self.operation}",
                         extra={'operation': self.operation, **self.context})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            self.logger.error(f"Failed {self.operation} in {duration:.3f}s",
                            extra={'operation': self.operation, 'duration': duration,
                                   'error': str(exc_val), **self.context})
        else:
            self.logger.info(f"Completed {self.operation} in {duration:.3f}s",
                           extra={'operation': self.operation, 'duration': duration,
                                  **self.context})

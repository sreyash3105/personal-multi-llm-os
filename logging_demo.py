#!/usr/bin/env python3
"""
Demonstration of the Local AI OS Logging System

Run with: python logging_demo.py
"""

import sys
import time
sys.path.append('.')

from backend.core.observability import (
    setup_logging, get_logger, set_request_context, generate_request_id,
    log_api_request, log_model_inference, log_queue_operation,
    log_security_event, PerformanceTimer
)

def demo_basic_logging():
    """Demonstrate basic component logging."""
    print("=== Basic Component Logging ===")

    # Setup logging
    setup_logging("INFO")

    # Get component loggers
    api_logger = get_logger('api.code')
    model_logger = get_logger('models.llm')
    queue_logger = get_logger('queue.manager')

    # Basic logging
    api_logger.info("API endpoint initialized")
    model_logger.info("Model cache loaded", extra={'model_count': 5})
    queue_logger.warning("Queue backlog detected", extra={'queue_depth': 15})

def demo_request_correlation():
    """Demonstrate request correlation and context."""
    print("\n=== Request Correlation ===")

    setup_logging("INFO")

    # Simulate API request
    request_id = generate_request_id()
    set_request_context(request_id, "session_abc123")

    api_logger = log_api_request('code', 'POST', '/api/code',
                                user_id="user123", prompt_length=150)

    # Simulate model inference
    model_logger = log_model_inference("qwen2.5-coder", "code_generation",
                                     input_tokens=512)

    time.sleep(0.1)  # Simulate processing

    model_logger.info("Model inference completed",
                     extra={'output_tokens': 256, 'duration': 1.23})

    api_logger.info("Request completed successfully",
                   extra={'duration': 1.45, 'status': 'success'})

def demo_performance_timing():
    """Demonstrate performance timing."""
    print("\n=== Performance Timing ===")

    setup_logging("DEBUG")

    logger = get_logger('api.vision')

    # Simulate vision processing
    with PerformanceTimer(logger, "image_analysis",
                         image_size="1920x1080", format="png") as timer:

        time.sleep(0.5)  # Simulate processing
        timer.context['objects_detected'] = 12
        timer.context['confidence'] = 0.89

def demo_security_logging():
    """Demonstrate security event logging."""
    print("\n=== Security Event Logging ===")

    setup_logging("INFO")

    # Security events
    log_security_event("authentication_success", "INFO",
                      user_id="user123", method="token")

    log_security_event("path_traversal_attempted", "WARNING",
                      user_id="attacker456", path="../../../etc/passwd",
                      blocked=True, reason="directory_traversal")

    log_security_event("rate_limit_exceeded", "WARNING",
                      user_id="user789", endpoint="/api/code",
                      requests_per_minute=150, limit=100)

def demo_error_handling():
    """Demonstrate error handling and logging."""
    print("\n=== Error Handling ===")

    setup_logging("ERROR")  # Only show errors

    logger = get_logger('storage.database')

    try:
        # Simulate database error
        raise ConnectionError("Database connection timeout")
    except Exception as e:
        logger.error("Database operation failed",
                    extra={'operation': 'user_query', 'error_type': type(e).__name__,
                          'retry_count': 2, 'user_id': 'user123'})

def main():
    """Run all logging demonstrations."""
    print("Local AI OS - Logging System Demonstration")
    print("=" * 50)

    demo_basic_logging()
    demo_request_correlation()
    demo_performance_timing()
    demo_security_logging()
    demo_error_handling()

    print("\n" + "=" * 50)
    print("Demo completed! Check the log output above.")
    print("\nKey features demonstrated:")
    print("- Component-based logging hierarchy")
    print("- Request correlation with IDs")
    print("- Structured logging with extra fields")
    print("- Performance timing")
    print("- Security event logging")
    print("- Error handling with context")

if __name__ == "__main__":
    main()
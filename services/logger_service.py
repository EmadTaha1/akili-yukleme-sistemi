"""
====================================================================
Centralized Logging Service
====================================================================
Responsibilities:
1. Managing rolling text logs for various operations (system, attendance, AI, performance)
2. Custom stream handlers for neat console tracking
3. Performance timing decorator for automated profiling
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler


def get_logs_dir():
    """Returns the logging directory, creating it if necessary."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


# Global dictionary to track initialized loggers and prevent duplicate handlers
_loggers = {}


def get_logger(name="system"):
    """
    Retrieves or creates a named logger with rotating file and stdout console handlers.
    Recommended loggers: 'system', 'attendance', 'ai', 'performance'
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate logs in parent handlers
    logger.propagate = False
    
    # ============ File Handler (Detailed Logging) ============
    logs_dir = get_logs_dir()
    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, f"{name}.log"),
        maxBytes=10*1024*1024,  # 10 MB limit
        backupCount=5,           # Hold up to 5 rotating logs
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # ============ Console Handler (Terminal Output) ============
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # ============ Formatters ============
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-12s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    _loggers[name] = logger
    return logger


def log_performance(operation_name, duration_ms, **kwargs):
    """Logs detailed performance measurements."""
    perf_logger = get_logger("performance")
    extras = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
    perf_logger.info(f"⚡ {operation_name} | {duration_ms:.2f}ms | {extras}")


def log_attendance_event(event_type, student_id, **details):
    """Logs high-level attendance events (recognition, marking present)."""
    att_logger = get_logger("attendance")
    extras = " | ".join([f"{k}={v}" for k, v in details.items()])
    att_logger.info(f"📋 {event_type} | student_id={student_id} | {extras}")


def log_ai_event(event_type, **details):
    """Logs deep learning/AI events (training completions, face captures)."""
    ai_logger = get_logger("ai")
    extras = " | ".join([f"{k}={v}" for k, v in details.items()])
    ai_logger.info(f"🧠 {event_type} | {extras}")


def measure_time(operation_name=None):
    """
    Decorator to automatically measure and log the execution time of any function.
    Usage:
        @measure_time("model_loading")
        def load_my_model():
            ...
    """
    import time
    import functools
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start) * 1000
                log_performance(op_name, duration, status="success")
                return result
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_performance(op_name, duration, status="error", error=str(e))
                raise
        return wrapper
    return decorator


# Quick verification
if __name__ == "__main__":
    logger = get_logger("test")
    logger.debug("Debug mesajı")
    logger.info("Sistem çalışıyor")
    logger.warning("Basit uyarı")
    logger.error("Burada hata var!")
    
    log_performance("test_operation", 12.5, frames=30, fps=30)
    log_attendance_event("RECOGNIZED", 123, name="Test Student", distance=0.42)
    log_ai_event("MODEL_LOADED", model="OpenFace", embeddings=360)
    
    print(f"\n✅ Test tamamlandı. Şuradaki log dosyalarını kontrol edin:\n   {get_logs_dir()}")
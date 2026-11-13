"""
Signal Engine package.
Generates, aggregates, and validates trade signals.
"""

from app.signals.signal_generator import Signal, SignalGenerator
from app.signals.signal_validator import SignalValidator, ValidationResult

__all__ = [
    "Signal",
    "SignalGenerator",
    "SignalValidator",
    "ValidationResult",
]

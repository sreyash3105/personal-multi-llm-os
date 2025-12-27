"""
MEK-1: Observer Wiring

Forward AIOS observations into MEK Observation Hook.
Observers are passive, removable without effect.
"""

from __future__ import annotations

from typing import Any
import threading


class AIOSObserverBridge:
    """
    Bridge AIOS observation system to MEK Observer Hook.

    I6: OBSERVATION NEVER CONTROLS
    - Observers are passive
    - Failures never affect execution
    - Removable without behavior change
    """

    def __init__(self):
        self._mek_observer_registered = False
        self._lock = threading.Lock()

    def register_aios_observer_as_mek_observer(self, aios_observer: Any) -> None:
        """
        Register an AIOS observer with MEK.

        The observer becomes passive - cannot affect control flow.
        """
        from mek0.kernel import get_observer_hub

        mek_hub = get_observer_hub()

        # Wrap AIOS observer as MEK observer
        mek_observer = MEKWrappedObserver(aios_observer)

        mek_hub.register(mek_observer)

        with self._lock:
            self._mek_observer_registered = True

    def clear_mek_observers(self) -> None:
        """
        Clear all MEK observers.

        This proves observers are removable without effect.
        """
        from mek0.kernel import get_observer_hub

        mek_hub = get_observer_hub()
        mek_hub.clear()

        with self._lock:
            self._mek_observer_registered = False

    def is_registered(self) -> bool:
        """
        Check if AIOS observer is registered with MEK.
        """
        with self._lock:
            return self._mek_observer_registered


class MEKWrappedObserver:
    """
    Wrapper that makes AIOS observer passive for MEK.

    Ensures:
    - Observer failures never affect execution
    - Observer cannot control flow
    - Observer cannot veto decisions
    """

    def __init__(self, aios_observer: Any):
        self._aios_observer = aios_observer

    def on_event(self, event_type: str, details: dict) -> None:
        """
        Forward event to AIOS observer.

        Wraps in try/except to ensure observer failures
        never affect MEK execution.

        I6: OBSERVATION NEVER CONTROLS
        """
        try:
            # Forward to AIOS observer if it has on_event method
            if hasattr(self._aios_observer, 'on_event'):
                self._aios_observer.on_event(event_type, details)
            # Or log method
            elif hasattr(self._aios_observer, 'log'):
                self._aios_observer.log(event_type, details)
        except Exception as e:
            # I6: Observer failures never affect execution
            # This is silent by design
            pass


class LoggingObserver:
    """
    Simple logging observer for MEK events.

    Passive - cannot affect control flow.
    Removable without behavior change.
    """

    def __init__(self):
        self._events = []

    def on_event(self, event_type: str, details: dict) -> None:
        """
        Log MEK events (passive).

        Does not affect control flow.
        """
        self._events.append({
            "type": event_type,
            "details": details,
            "timestamp": __import__('time').time(),
        })

    def get_events(self) -> list:
        """
        Get logged events (read-only).
        """
        return list(self._events)

    def clear(self) -> None:
        """
        Clear event log.
        """
        self._events = []

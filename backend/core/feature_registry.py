"""
Centralized Feature Capability Registry

Tracks availability of optional dependencies and features across the application.
Provides clear warnings when features are disabled and centralized capability checking.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class FeatureRegistry:
    """Central registry for tracking optional features and dependencies."""

    def __init__(self):
        self._capabilities: Dict[str, Dict[str, Any]] = {}

    def register_feature(self, name: str, available: bool, description: str,
                        install_hint: str = "", fallback_behavior: str = ""):
        """Register a feature capability."""
        self._capabilities[name] = {
            "available": available,
            "description": description,
            "install_hint": install_hint,
            "fallback_behavior": fallback_behavior
        }

        if available:
            logger.info(f"Feature '{name}' available: {description}")
        else:
            warning_msg = f"Feature '{name}' unavailable: {description}"
            if fallback_behavior:
                warning_msg += f" (fallback: {fallback_behavior})"
            if install_hint:
                warning_msg += f" - Install with: {install_hint}"
            logger.warning(warning_msg)

    def is_available(self, name: str) -> bool:
        """Check if a feature is available."""
        return self._capabilities.get(name, {}).get("available", False)

    def get_capability_info(self, name: str) -> Dict[str, Any]:
        """Get detailed information about a feature."""
        return self._capabilities.get(name, {})

    def get_unavailable_features(self) -> Dict[str, Dict[str, Any]]:
        """Get all unavailable features."""
        return {name: info for name, info in self._capabilities.items() if not info["available"]}

    def log_status_summary(self):
        """Log a summary of all feature statuses."""
        available = sum(1 for info in self._capabilities.values() if info["available"])
        total = len(self._capabilities)

        logger.info(f"Feature capability summary: {available}/{total} features available")

        unavailable = self.get_unavailable_features()
        if unavailable:
            logger.info("Unavailable features:")
            for name, info in unavailable.items():
                logger.info(f"  - {name}: {info.get('fallback_behavior', 'disabled')}")

# Global registry instance
feature_registry = FeatureRegistry()

# Convenience functions
def register_feature(*args, **kwargs):
    """Register a feature (convenience function)."""
    feature_registry.register_feature(*args, **kwargs)

def is_feature_available(name: str) -> bool:
    """Check if a feature is available (convenience function)."""
    return feature_registry.is_available(name)

def log_feature_status():
    """Log feature status summary (convenience function)."""
    feature_registry.log_status_summary()
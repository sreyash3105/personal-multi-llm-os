"""
FAILURE CLASSIFICATION SCHEMA

AIOS Failure Articulation Layer - Artifact 2

This schema defines REQUIRED metadata for every failure event.

NO OPTIONAL FIELDS.
NO INFERRED VALUES.
AUTO-POPULATION IS FORBIDDEN.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class FailureType(Enum):
    """
    Failure types - must match taxonomy.

    Note: Full taxonomy is imported separately to avoid circular imports.
    This is a minimal subset for type checking.
    """
    AUTHORITY_LEAKAGE = "AUTHORITY_LEAKAGE"
    AUTHORITY_CONCENTRATION = "AUTHORITY_CONCENTRATION"
    AUTHORITY_AMBIGUITY = "AUTHORITY_AMBIGUITY"
    HIDDEN_GOVERNANCE = "HIDDEN_GOVERNANCE"
    TEMPORAL_DRIFT = "TEMPORAL_DRIFT"
    TEMPORAL_MISALIGNMENT = "TEMPORAL_MISALIGNMENT"
    TEMPORAL_STALENESS = "TEMPORAL_STALENESS"
    BOUNDARY_VIOLATION = "BOUNDARY_VIOLATION"
    ABSTRACTION_WRONG = "ABSTRACTION_WRONG"
    BOUNDARY_LEAK = "BOUNDARY_LEAK"
    SCALAR_COLLAPSE = "SCALAR_COLLAPSE"
    HUMAN_FATIGUE = "HUMAN_FATIGUE"
    HUMAN_RUBBER_STAMP = "HUMAN_RUBBER_STAMP"
    EPISTEMIC_OVERCONFIDENCE = "EPISTEMIC_OVERCONFIDENCE"
    COGNITIVE_FRAMING = "COGNITIVE_FRAMING"
    HUMAN_BOTTLENECK = "HUMAN_BOTTLENECK"
    FALSE_CAUSALITY = "FALSE_CAUSALITY"
    NARRATIVE_FRAGILITY = "NARRATIVE_FRAGILITY"
    INVISIBLE_FAILURE = "INVISIBLE_FAILURE"
    OBSERVABILITY_GAP = "OBSERVABILITY_GAP"
    INTENT_AMBIGUITY = "INTENT_AMBIGUITY"
    FALLTHROUGH_FAILURE = "FALLTHROUGH_FAILURE"
    INTENT_EXHAUSTION = "INTENT_EXHAUSTION"
    META_AUTHORITY = "META_AUTHORITY"
    GOVERNANCE_DRIFT = "GOVERNANCE_DRIFT"
    POLICY_CEREMONIALITY = "POLICY_CEREMONIALITY"
    SCALING_OVERFLOW = "SCALING_OVERFLOW"
    COMPLEXITY_EXPLOSION = "COMPLEXITY_EXPLOSION"
    FRAGMENTATION = "FRAGMENTATION"
    OVER_SAFETY_AVERSION = "OVER_SAFETY_AVERSION"
    FAIL_OPEN_PRESSURE = "FAIL_OPEN_PRESSURE"
    RISK_TUNING_SENSITIVITY = "RISK_TUNING_SENSITIVITY"
    ABOUNDED_EXECUTION = "ABOUNDED_EXECUTION"
    IMPACT_VS_COUNT_ERROR = "IMPACT_VS_COUNT_ERROR"
    REALITY_MISMATCH = "REALITY_MISMATCH"


class Severity(Enum):
    """
    Severity levels for failure events.

    These levels guide execution impact and human notification requirements.
    They are NOT ordered by technical impact alone; they account for
    governance implications.
    """

    LOW = "LOW"
    """
    Informational failure.
    System continues execution.
    Human notification optional.
    Example: minor observability gap.
    """

    MEDIUM = "MEDIUM"
    """
    Moderate failure requiring attention.
    Execution may continue with caution.
    Human notification recommended.
    Example: temporal drift within acceptable range.
    """

    HIGH = "HIGH"
    """
    Significant failure affecting correctness or authority.
    Execution decision depends on failure type.
    Human notification required.
    Example: authority ambiguity.
    """

    CRITICAL = "CRITICAL"
    """
    Severe failure that must halt execution immediately.
    Human notification mandatory.
    System must NOT continue.
    Example: hidden governance in enforcement path.
    """


class ExecutionImpact(Enum):
    """
    Defines what happens to execution when failure occurs.

    This is determined by failure type AND severity.
    It is NOT a decision point for auto-recovery.
    """

    HALT = "HALT"
    """
    Execution MUST stop immediately.
    No retry allowed.
    No auto-continue allowed.
    Human intervention required.
    """

    CONTINUE = "CONTINUE"
    """
    Execution MAY continue.
    System does NOT attempt auto-repair.
    Failure is logged and surfaced.
    Human may be notified based on visibility requirements.
    """

    GRACEFUL_DEGRADE = "GRACEFUL_DEGRADE"
    """
    Execution continues with reduced capability.
    Degradation is explicit and documented.
    Failure is surfaced with clear indication of limitation.
    """


class HumanVisibility(Enum):
    """
    Defines whether and how human is notified of failure.

    This is NOT a recommendation; it is a requirement.
    """

    REQUIRED = "REQUIRED"
    """
    Human MUST be notified.
    Failure surfaces to UI immediately.
    No dismissal without acknowledgment.
    """

    OPTIONAL = "OPTIONAL"
    """
    Human MAY be notified.
    Failure appears in logs/observability.
    No immediate UI interruption.
    """

    DEFERRED = "DEFERRED"
    """
    Notification may be delayed.
    Failure appears in audit trail.
    No immediate action required.
    """

    NONE = "NONE"
    """
    No human notification.
    Failure is internal only.
    Use ONLY for non-impacting observability issues.
    """


class OriginComponent(Enum):
    """
    Enumeration of all components that can originate failures.

    This list is exhaustive. Any new component must be added here.
    """

    # Core Components
    PLANNER = "planner"
    ROUTER = "router"
    SECURITY_ENGINE = "security_engine"
    PERMISSION_ENFORCER = "permission_enforcer"
    PERMISSION_MANAGER = "permission_manager"

    # Pipeline Components
    CHAT_PIPELINE = "chat_pipeline"
    CODE_PIPELINE = "code_pipeline"
    AUTOMATION_EXECUTOR = "automation_executor"

    # Input/Output Components
    STT_SERVICE = "stt_service"
    TTS_SERVICE = "tts_service"
    VISION_PIPELINE = "vision_pipeline"

    # Tools
    TOOLS_RUNTIME = "tools_runtime"

    # Storage and Observability
    HISTORY_LOGGER = "history_logger"
    SECURITY_SESSIONS = "security_sessions"

    # UI
    CHAT_UI = "chat_ui"

    # Configuration
    CONFIG = "config"

    # Unknown (last resort)
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureEvent:
    """
    Complete classification of a failure event.

    This dataclass is FROZEN to prevent mutation.
    Once created, a failure event is immutable.

    ALL FIELDS ARE REQUIRED.
    """

    # Required fields (no defaults)
    failure_type: FailureType
    severity: Severity
    execution_impact: ExecutionImpact
    human_visibility: HumanVisibility
    origin_component: OriginComponent
    description: str

    # Optional fields with defaults
    failure_id: str = field(default_factory=lambda: str(uuid4()))
    related_attack: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    related_failure_ids: List[str] = field(default_factory=list)
    audit_traceback: Optional[str] = None

    def __post_init__(self):
        """
        Validate that all required fields are properly populated.

        Raises ValueError if any validation fails.
        """
        # Validate severity/impact combinations
        if self.severity == Severity.CRITICAL and self.execution_impact != ExecutionImpact.HALT:
            raise ValueError(
                f"CRITICAL severity MUST have HALT execution_impact. "
                f"Got: {self.execution_impact}"
            )

        # Validate critical failures require human visibility
        if self.severity == Severity.CRITICAL and self.human_visibility not in [
            HumanVisibility.REQUIRED,
        ]:
            raise ValueError(
                f"CRITICAL severity MUST have REQUIRED human_visibility. "
                f"Got: {self.human_visibility}"
            )

        # Validate description is not empty
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for logging and storage.

        NO field renaming.
        NO field omission.
        NO transformation.
        """
        return {
            "failure_id": self.failure_id,
            "failure_type": self.failure_type.name,
            "severity": self.severity.value,
            "execution_impact": self.execution_impact.value,
            "human_visibility": self.human_visibility.value,
            "origin_component": self.origin_component.value,
            "related_attack": self.related_attack,
            "timestamp": self.timestamp,
            "context_snapshot": self.context_snapshot,
            "related_failure_ids": self.related_failure_ids,
            "description": self.description,
            "audit_traceback": self.audit_traceback,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureEvent":
        """
        Reconstruct FailureEvent from dictionary.

        NO field inference.
        NO default value substitution.
        Raises ValueError if required fields missing.
        """
        required_fields = [
            "failure_type",
            "severity",
            "execution_impact",
            "human_visibility",
            "origin_component",
            "description",
        ]

        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Convert enum values
        failure_type = FailureType[data["failure_type"]]
        severity = Severity[data["severity"]]
        execution_impact = ExecutionImpact[data["execution_impact"]]
        human_visibility = HumanVisibility[data["human_visibility"]]
        origin_component = OriginComponent[data["origin_component"]]

        return cls(
            failure_id=data.get("failure_id", str(uuid4())),
            failure_type=failure_type,
            severity=severity,
            execution_impact=execution_impact,
            human_visibility=human_visibility,
            origin_component=origin_component,
            related_attack=data.get("related_attack"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            context_snapshot=data.get("context_snapshot", {}),
            related_failure_ids=data.get("related_failure_ids", []),
            description=data["description"],
            audit_traceback=data.get("audit_traceback"),
        )


# Schema Version
FAILURE_SCHEMA_VERSION = "1.0"
FAILURE_SCHEMA_REQUIRED_FIELDS = [
    "failure_type",
    "severity",
    "execution_impact",
    "human_visibility",
    "origin_component",
    "description",
]

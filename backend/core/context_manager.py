import threading
import uuid
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExecutionContext:
    context_id: str
    profile_id: Optional[str] = None
    session_id: Optional[str] = None
    mode: str = "unknown"
    created_at: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)
    risk_context: Dict[str, Any] = field(default_factory=dict)
    security_context: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def set_risk(self, key: str, value: Any) -> None:
        self.risk_context[key] = value

    def get_risk(self, key: str, default: Any = None) -> Any:
        return self.risk_context.get(key, default)

    def set_security(self, key: str, value: Any) -> None:
        self.security_context[key] = value

    def get_security(self, key: str, default: Any = None) -> Any:
        return self.security_context.get(key, default)


class ContextManager:
    _contexts: Dict[str, ExecutionContext] = {}
    _lock = threading.Lock()
    _thread_local = threading.local()

    @classmethod
    def create_context(
        cls,
        profile_id: Optional[str] = None,
        session_id: Optional[str] = None,
        mode: str = "unknown"
    ) -> ExecutionContext:
        context_id = str(uuid.uuid4())
        context = ExecutionContext(
            context_id=context_id,
            profile_id=profile_id,
            session_id=session_id,
            mode=mode
        )
        with cls._lock:
            cls._contexts[context_id] = context
        return context

    @classmethod
    def get_context(cls, context_id: str) -> Optional[ExecutionContext]:
        with cls._lock:
            return cls._contexts.get(context_id)

    @classmethod
    def set_current_context(cls, context: ExecutionContext) -> None:
        cls._thread_local.current_context = context

    @classmethod
    def get_current_context(cls) -> Optional[ExecutionContext]:
        return getattr(cls._thread_local, "current_context", None)

    @classmethod
    def destroy_context(cls, context_id: str) -> bool:
        with cls._lock:
            return cls._contexts.pop(context_id, None) is not None

    @classmethod
    def cleanup_expired(cls, max_age_seconds: float = 3600) -> int:
        now = datetime.utcnow().timestamp()
        expired = []
        with cls._lock:
            for cid, ctx in cls._contexts.items():
                if now - ctx.created_at > max_age_seconds:
                    expired.append(cid)
            for cid in expired:
                cls._contexts.pop(cid, None)
        return len(expired)

    @classmethod
    def list_contexts(cls) -> List[ExecutionContext]:
        with cls._lock:
            return list(cls._contexts.values())

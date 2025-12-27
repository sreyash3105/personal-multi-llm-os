from __future__ import annotations
from typing import Dict, Any, Optional, List
import asyncio
from functools import partial

from backend.core.context_manager import ContextManager, ExecutionContext
from backend.core.config import (
    VISION_ENABLED,
    CODER_MODEL_NAME,
    REVIEWER_MODEL_NAME,
    JUDGE_MODEL_NAME,
    JUDGE_ENABLED,
    STUDY_MODEL_NAME,
    VISION_MODEL_NAME,
)

from backend.modules.code.pipeline import (
    run_coder,
    run_reviewer,
    run_judge,
    run_study,
    extract_mode_and_prompt,
    build_history_context,
    extract_study_style_and_prompt,
)

from backend.modules.telemetry.history import history_logger
from backend.modules.vision.vision_pipeline import run_vision
from backend.modules.tools.tools_runtime import execute_tool
from backend.modules.telemetry.risk import assess_risk
from backend.modules.security.security_sessions import create_security_session

from backend.modules.chat.chat_pipeline import run_chat_smart
from backend.modules.chat.chat_ui import handle_chat_turn
from backend.modules.code.pipeline import run_smart_code_pipeline
from backend.modules.automation.executor import plan_and_execute

from backend.modules.stt.stt_service import STTService

try:
    from backend.modules.tts.tts_service import tts_service as _tts_service
except ImportError:
    _tts_service = None


class LocalRunner:
    def __init__(self):
        self.stt_service = STTService()

    def _create_context(self, profile_id: Optional[str], session_id: Optional[str], mode: str) -> ExecutionContext:
        context = ContextManager.create_context(profile_id=profile_id, session_id=session_id, mode=mode)
        ContextManager.set_current_context(context)
        return context

    def _destroy_context(self, context_id: str) -> bool:
        return ContextManager.destroy_context(context_id)

    def should_escalate(self, judge_result: Dict[str, Any]) -> tuple[bool, str]:
        """
        BLOCKED: Autonomous escalation is prohibited.

        INVARIANT 7: NO AUTONOMY, EVER
        - No automatic escalation to heavy review
        - No inference that more review is needed
        - Escalation must be explicit user choice
        """
        from backend.core.negative_capability import ProhibitedBehaviorError

        raise ProhibitedBehaviorError(
            "INVARIANT_7_VIOLATION: Autonomous escalation is prohibited. "
            "The 'should_escalate' method is structurally blocked. "
            "Escalation to heavy review must be an explicit user decision, "
            "not an automatic response to confidence/conflict scores. "
            "This is an invariant - the system does NOT escalate autonomously."
        )

    def inject_escalation_comment(self, code: str, reason: str) -> str:
        """
        BLOCKED: Autonomous escalation is prohibited.

        INVARIANT 7: NO AUTONOMY, EVER
        - No automatic escalation comments
        - No injection of escalation markers
        """
        from backend.core.negative_capability import ProhibitedBehaviorError

        raise ProhibitedBehaviorError(
            "INVARIANT_7_VIOLATION: Autonomous escalation is prohibited. "
            "The 'inject_escalation_comment' method is structurally blocked. "
            "Escalation markers cannot be automatically injected. "
            "This is an invariant - no autonomous escalation."
        )

    def execute_code(
        self,
        prompt: str,
        profile_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, session_id, "code")
        context_id = context.context_id

        mode, normalized_prompt = extract_mode_and_prompt(prompt)

        if not normalized_prompt:
            self._destroy_context(context_id)
            return {"output": "(Empty prompt)", "context_id": context_id}

        coder_output = None
        reviewer_output = None
        final_output = None
        judge_result: Dict[str, Any] = {}

        if mode == "code_raw":
            coder_output = run_coder(normalized_prompt)
            final_output = coder_output

            try:
                judge_result = run_judge(
                    original_prompt=prompt,
                    coder_output=coder_output or "",
                    reviewer_output=final_output or "",
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Judge evaluation failed: {e}")
                judge_result = {"confidence_score": 0.0, "conflict_score": 0.0, "judgement_summary": f"Judge failed: {e}", "judge_error": True}

        elif mode == "review_only":
            try:
                reviewer_output = run_reviewer("", normalized_prompt)
                final_output = reviewer_output
            except Exception:
                final_output = normalized_prompt

            try:
                judge_result = run_judge(
                    original_prompt=prompt,
                    coder_output="",
                    reviewer_output=final_output or "",
                )
            except Exception as e:
                judge_result = {"confidence_score": None, "conflict_score": None, "judgement_summary": f"Judge failed: {e}", "raw_response": "", "parse_error": str(e)}

        elif mode == "code_reviewed_ctx":
            history_ctx = build_history_context(max_items=5)
            prompt_with_ctx = normalized_prompt
            if history_ctx:
                prompt_with_ctx = (
                    "Here are some recent interactions between the user and the assistant.\n"
                    "Use them as context, but treat the CURRENT REQUEST as primary.\n\n"
                    + history_ctx
                    + "\n\nCURRENT REQUEST:\n"
                    + normalized_prompt
                )

            coder_output = run_coder(prompt_with_ctx)
            final_output = coder_output

            try:
                judge_result = run_judge(
                    original_prompt=prompt_with_ctx,
                    coder_output=coder_output or "",
                    reviewer_output=coder_output or "",
                )
            except Exception as e:
                judge_result = {"confidence_score": None, "conflict_score": None, "judgement_summary": f"Judge failed: {e}", "raw_response": "", "parse_error": str(e)}

        else:
            coder_output = run_coder(normalized_prompt)
            final_output = coder_output

            try:
                judge_result = run_judge(
                    original_prompt=prompt,
                    coder_output=coder_output or "",
                    reviewer_output=coder_output or "",
                )
            except Exception as e:
                judge_result = {"confidence_score": None, "conflict_score": None, "judgement_summary": f"Judge failed: {e}", "raw_response": "", "parse_error": str(e)}

        try:
            risk_info = assess_risk(
                "code",
                {
                    "mode": mode,
                    "original_prompt": prompt,
                    "normalized_prompt": normalized_prompt,
                    "final_output": final_output or "",
                },
            )
        except Exception:
            risk_info = {"risk_level": 1, "tags": [], "reasons": "Risk assessment failed; defaulting to MINOR risk.", "kind": "code"}

        history_logger.log(
            {
                "mode": mode,
                "original_prompt": prompt,
                "normalized_prompt": normalized_prompt,
                "coder_output": coder_output,
                "reviewer_output": reviewer_output,
                "final_output": final_output,
                "judge": {
                    "confidence_score": judge_result.get("confidence_score") if judge_result else None,
                    "conflict_score": judge_result.get("conflict_score") if judge_result else None,
                    "judgement_summary": judge_result.get("judgement_summary") if judge_result else None,
                },
                "risk": risk_info,
                "models": {
                    "coder": CODER_MODEL_NAME,
                    "reviewer": REVIEWER_MODEL_NAME,
                    "judge": JUDGE_MODEL_NAME if JUDGE_ENABLED else None,
                },
                "context_id": context_id,
            }
        )

        self._destroy_context(context_id)
        return {"output": final_output or "", "context_id": context_id}

    def execute_study(
        self,
        prompt: str,
        profile_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, session_id, "study")
        context_id = context.context_id

        style, normalized_prompt = extract_study_style_and_prompt(prompt)

        if not normalized_prompt:
            self._destroy_context(context_id)
            return {"output": "(Empty study prompt)", "context_id": context_id}

        study_output = run_study(normalized_prompt, style=style)

        history_logger.log(
            {
                "mode": f"study_{style}",
                "original_prompt": prompt,
                "normalized_prompt": normalized_prompt,
                "final_output": study_output,
                "models": {"study": STUDY_MODEL_NAME},
                "context_id": context_id,
            }
        )

        self._destroy_context(context_id)
        return {"output": study_output, "context_id": context_id}

    async def execute_vision(
        self,
        image_bytes: bytes,
        user_prompt: str = "",
        mode: str = "auto",
        profile_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, session_id, "vision")
        context_id = context.context_id

        if not VISION_ENABLED:
            self._destroy_context(context_id)
            return {"output": "Vision is disabled in config (VISION_ENABLED = False).", "context_id": context_id}

        if not image_bytes:
            self._destroy_context(context_id)
            return {"output": "(No image data received.)", "context_id": context_id}

        loop = asyncio.get_event_loop()
        vision_output = await loop.run_in_executor(
            None,
            partial(run_vision, image_bytes=image_bytes, user_prompt=user_prompt or "", mode=mode or "auto")
        )

        history_logger.log(
            {
                "mode": f"vision_{mode or 'auto'}",
                "original_prompt": user_prompt,
                "normalized_prompt": user_prompt,
                "final_output": vision_output,
                "models": {"vision": VISION_MODEL_NAME},
                "context_id": context_id,
            }
        )

        self._destroy_context(context_id)
        return {"output": vision_output, "context_id": context_id}

    def execute_tool(
        self,
        tool: str,
        args: Dict[str, Any] | None = None,
        profile_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, session_id, "tools")
        context_id = context.context_id

        context_obj = {"source": "local_runner.tools.execute", "context_id": context_id}
        record = execute_tool(tool, args or {}, context_obj)

        self._destroy_context(context_id)
        return {
            "ok": bool(record.get("ok")),
            "tool": record.get("tool") or tool,
            "result": record.get("result"),
            "error": record.get("error"),
            "risk": record.get("risk"),
            "context_id": context_id,
        }

    def create_security_session(
        self,
        profile_id: str,
        scope: str,
        auth_level: int,
        ttl_seconds: int = 300,
        max_uses: int = 1,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, None, "security")
        context_id = context.context_id

        try:
            session = create_security_session(
                profile_id=profile_id,
                scope=scope,
                auth_level=int(auth_level),
                ttl_seconds=ttl_seconds,
                max_uses=max_uses,
                secret=secret,
            )
            self._destroy_context(context_id)
            return {"ok": True, "session": session, "context_id": context_id}
        except Exception as exc:
            self._destroy_context(context_id)
            return {"ok": False, "error": str(exc), "context_id": context_id}

    def execute_chat(
        self,
        profile_id: str,
        chat_id: str,
        user_input: str,
        smart_mode: bool = False,
        mode_override: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, None, "chat")
        context_id = context.context_id

        result = handle_chat_turn(
            profile_id=profile_id,
            chat_id=chat_id,
            user_input=user_input,
            smart=smart_mode,
        )

        self._destroy_context(context_id)
        return result

    def execute_smart_code(
        self,
        prompt: str,
        profile_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, None, "code_smart")
        context_id = context.context_id

        result = run_smart_code_pipeline(prompt, profile_id)

        self._destroy_context(context_id)
        return {
            "ok": True,
            "code": result["final_code"],
            "trace": result,
            "context_id": context_id,
        }

    def execute_automation(
        self,
        prompt: str,
        profile_id: Optional[str] = None,
        execute: bool = False
    ) -> Dict[str, Any]:
        context = self._create_context(profile_id, None, "automation")
        context_id = context.context_id

        result = plan_and_execute(prompt, context={"profile_id": profile_id, "context_id": context_id}, execute=execute)

        self._destroy_context(context_id)
        return result

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(None, None, "stt")
        context_id = context.context_id

        result = self.stt_service.transcribe_bytes(audio_bytes, language=language, prompt=prompt)

        self._destroy_context(context_id)
        return result

    def synthesize_tts(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self._create_context(None, None, "tts")
        context_id = context.context_id

        if _tts_service is None:
            self._destroy_context(context_id)
            return {"ok": False, "error": "TTS service is unavailable"}

        try:
            result = _tts_service.synthesize(text, voice)
            self._destroy_context(context_id)
            return {
                "ok": True,
                "audio_b64": result.get("audio_b64"),
                "duration_s": result.get("duration_s"),
                "voice": result.get("voice"),
                "text_length": result.get("text_length"),
                "context_id": context_id,
            }
        except Exception as e:
            self._destroy_context(context_id)
            return {"ok": False, "error": f"TTS synthesis failed: {str(e)}"}


_runner_instance: Optional[LocalRunner] = None


def get_runner() -> LocalRunner:
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = LocalRunner()
    return _runner_instance

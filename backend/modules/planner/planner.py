"""
planner.py

Centralized Planner System (3.0 → 4.0)

The Planner is the reasoning brain of the Local AI OS.
It THINKS but does not execute.

Responsibilities:
- Intent detection (chat, code, automation, email, file ops, etc.)
- Mode selection (normal, smart, raw, review, etc.)
- Risk estimation (0-10 scale)
- Prompt construction and normalization
- Route selection (chat model, coder, automation executor, etc.)
- Model selection based on task complexity

Output JSON format:
{
  "intent": "code|chat|automation|vision|tool|file_op|email|internal",
  "action_type": "write|execute|analyze|generate|etc",
  "risk_hint": 0-10,
  "planner_confidence": 0-10,
  "normalized_prompt": "...",
  "selected_models": ["model1", "model2"],
  "route": "chat|code|automation|vision|tools",
  "metadata": {...}
}

Integration:
- Called by Router for initial classification
- Used by chat_pipeline for smart mode planning
- Feeds into Judge for validation
- Guides execution without performing it
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.core.config import (
    CODER_MODEL_NAME,
    REVIEWER_MODEL_NAME,
    JUDGE_MODEL_NAME,
    STUDY_MODEL_NAME,
    CHAT_MODEL_NAME,
    SMART_CHAT_MODEL_NAME,
    VISION_MODEL_NAME,
    STT_MODEL_NAME,
    AVAILABLE_MODELS,
)
from backend.modules.code.pipeline import call_ollama
from backend.modules.telemetry.history import history_logger

logger = logging.getLogger(__name__)

# Planner system prompt
PLANNER_SYSTEM_PROMPT = """
You are the central Planner for a Local AI Operating System.

Your role is to analyze user input and plan how the system should respond.
You THINK and REASON, but you do NOT execute any actions.

Analyze the user's request and output a JSON plan with these fields:

{
  "intent": "code|chat|automation|vision|tool|file_op|email|internal|study",
  "action_type": "write|execute|analyze|generate|review|transcribe|describe|etc",
  "risk_hint": 0-10 (0=safe, 10=extremely risky),
  "planner_confidence": 0-10 (how confident you are in this plan),
  "normalized_prompt": "cleaned and normalized version of the user request",
  "selected_models": ["primary_model", "secondary_model_if_needed"],
  "route": "chat|code|automation|vision|tools|stt",
  "metadata": {
    "complexity": "simple|medium|complex",
    "requires_judge": true|false,
    "escalation_needed": true|false,
    "reasoning": "brief explanation of your thought process"
  }
}

Intent categories:
- code: writing, editing, debugging code
- chat: general conversation, questions
- automation: PC control, file operations, system tasks
- vision: image analysis, OCR, screenshots
- tool: using local tools
- file_op: file management
- email: email related tasks
- internal: system commands, status
- study: learning, teaching, quizzes

Risk hints:
- 0-2: Safe operations (reading, simple chat)
- 3-5: Medium risk (code generation, file reading)
- 6-8: High risk (file writing, system commands)
- 9-10: Critical (deletion, system changes, network)

Return ONLY valid JSON. No explanations outside the JSON.
"""

DEFAULT_PLANNER_MODEL = CHAT_MODEL_NAME  # Use chat model for planning


class Planner:
    """
    Centralized reasoning brain for the Local AI OS.

    Singleton pattern - use Planner.shared() to get instance.
    """

    _shared_instance: Optional["Planner"] = None

    def __init__(self):
        self.model_name = DEFAULT_PLANNER_MODEL

    @classmethod
    def shared(cls) -> "Planner":
        """Get shared Planner instance."""
        if cls._shared_instance is None:
            cls._shared_instance = cls()
        return cls._shared_instance

    def plan_request(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main planning method.

        Args:
            user_input: Raw user input text
            context: Optional context dict with profile_id, chat_id, source, etc.

        Returns:
            Planning result dict with intent, risk_hint, confidence, etc.
        """
        context = context or {}

        # Build planning prompt
        prompt = self._build_planning_prompt(user_input, context)

        # Call LLM for planning
        try:
            raw_response = call_ollama(prompt, self.model_name)
            plan_result = self._parse_plan_response(raw_response)
        except Exception as e:
            logger.exception("Planner LLM call failed: %s", e)
            # Fallback to rule-based planning
            plan_result = self._fallback_plan(user_input, context)

        # Validate and enhance the plan
        plan_result = self._validate_and_enhance_plan(plan_result, user_input, context)

        # Log planning result
        self._log_planning_result(plan_result, user_input, context)

        return plan_result

    def _build_planning_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """Build the planning prompt for the LLM."""
        profile_info = ""
        if context.get("profile_id"):
            profile_info = f"Profile: {context.get('profile_id')}"

        source_info = ""
        if context.get("source"):
            source_info = f"Source: {context.get('source')}"

        context_str = f"{profile_info} {source_info}".strip()

        prompt = f"""{PLANNER_SYSTEM_PROMPT}

User Input: {user_input}

Context: {context_str or "None"}

Plan the response:"""

        return prompt

    def _parse_plan_response(self, raw_response: str) -> Dict[str, Any]:
        """Parse the JSON response from the planner LLM."""
        if not raw_response:
            return self._default_plan()

        # Try to extract JSON from response
        raw = str(raw_response).strip()
        if "{" in raw and "}" in raw:
            try:
                candidate = raw[raw.find("{"):raw.rfind("}") + 1]
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                logger.debug("Planner JSON parse failed: %s", e)

        # Try parsing entire response as JSON
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # Fallback
        logger.warning("Planner returned invalid JSON, using fallback")
        return self._default_plan()

    def _default_plan(self) -> Dict[str, Any]:
        """Return a safe default plan."""
        return {
            "intent": "chat",
            "action_type": "respond",
            "risk_hint": 1,
            "planner_confidence": 5,
            "normalized_prompt": "",
            "selected_models": [CHAT_MODEL_NAME],
            "route": "chat",
            "metadata": {
                "complexity": "simple",
                "requires_judge": False,
                "escalation_needed": False,
                "reasoning": "Default fallback plan"
            }
        }

    def _fallback_plan(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback planning when LLM fails."""
        text = (user_input or "").lower()

        # Simple rule-based intent detection
        if any(keyword in text for keyword in ["write code", "code", "function", "class", "script", "program"]):
            intent = "code"
            route = "code"
            models = [CODER_MODEL_NAME, REVIEWER_MODEL_NAME]
            risk = 3
        elif any(keyword in text for keyword in ["automate", "click", "open", "run", "execute", "file", "delete", "move"]):
            intent = "automation"
            route = "automation"
            models = [CHAT_MODEL_NAME]  # Could use specialized automation model
            risk = 6
        elif any(keyword in text for keyword in ["see", "look", "image", "screenshot", "ocr", "vision"]):
            intent = "vision"
            route = "vision"
            models = [VISION_MODEL_NAME]
            risk = 2
        elif any(keyword in text for keyword in ["tool", "///tool"]):
            intent = "tool"
            route = "tools"
            models = [CHAT_MODEL_NAME]
            risk = 4
        elif any(keyword in text for keyword in ["study", "learn", "teach", "quiz", "explain"]):
            intent = "study"
            route = "code"  # Study uses code pipeline
            models = [STUDY_MODEL_NAME]
            risk = 1
        else:
            intent = "chat"
            route = "chat"
            models = [CHAT_MODEL_NAME]
            risk = 1

        return {
            "intent": intent,
            "action_type": "generate",
            "risk_hint": risk,
            "planner_confidence": 6,
            "normalized_prompt": user_input,
            "selected_models": models,
            "route": route,
            "metadata": {
                "complexity": "medium",
                "requires_judge": risk > 3,
                "escalation_needed": risk > 7,
                "reasoning": "Rule-based fallback planning"
            }
        }

    def _validate_and_enhance_plan(self, plan: Dict[str, Any], user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the plan and add enhancements."""
        # Ensure required fields exist
        defaults = self._default_plan()
        for key, default_value in defaults.items():
            if key not in plan:
                plan[key] = default_value

        # Normalize values
        plan["intent"] = plan.get("intent", "chat").lower()
        plan["action_type"] = plan.get("action_type", "respond").lower()
        plan["risk_hint"] = max(0, min(10, int(plan.get("risk_hint", 1))))
        plan["planner_confidence"] = max(0, min(10, int(plan.get("planner_confidence", 5))))
        plan["normalized_prompt"] = plan.get("normalized_prompt", user_input).strip()

        # Ensure selected_models is a list
        models = plan.get("selected_models", [])
        if not isinstance(models, list):
            models = [str(models)]
        if not models:
            models = [CHAT_MODEL_NAME]
        plan["selected_models"] = models

        # Validate route
        valid_routes = ["chat", "code", "automation", "vision", "tools", "stt"]
        if plan.get("route") not in valid_routes:
            # Auto-determine route from intent
            intent_to_route = {
                "code": "code",
                "automation": "automation",
                "vision": "vision",
                "tool": "tools",
                "file_op": "automation",
                "email": "chat",  # Could be specialized later
                "internal": "chat",
                "study": "code",
            }
            plan["route"] = intent_to_route.get(plan["intent"], "chat")

        # Ensure metadata exists
        if "metadata" not in plan:
            plan["metadata"] = {}
        meta = plan["metadata"]
        meta.setdefault("complexity", "medium")
        meta.setdefault("requires_judge", plan["risk_hint"] > 3)
        meta.setdefault("escalation_needed", plan["risk_hint"] > 7)
        meta.setdefault("reasoning", "Enhanced by validation")

        return plan

    def _log_planning_result(self, plan: Dict[str, Any], user_input: str, context: Dict[str, Any]):
        """Log the planning result for telemetry."""
        try:
            history_logger.log({
                "kind": "planner_result",
                "user_input": user_input,
                "intent": plan.get("intent"),
                "action_type": plan.get("action_type"),
                "risk_hint": plan.get("risk_hint"),
                "planner_confidence": plan.get("planner_confidence"),
                "route": plan.get("route"),
                "selected_models": plan.get("selected_models"),
                "profile_id": context.get("profile_id"),
                "chat_id": context.get("chat_id"),
                "source": context.get("source"),
                "metadata": plan.get("metadata"),
            })
        except Exception as e:
            logger.exception("Failed to log planner result: %s", e)

    # Public convenience methods

    def is_high_risk(self, plan: Dict[str, Any]) -> bool:
        """Check if a plan indicates high risk."""
        return plan.get("risk_hint", 0) >= 6

    def requires_judge(self, plan: Dict[str, Any]) -> bool:
        """Check if a plan requires judge validation."""
        return plan.get("metadata", {}).get("requires_judge", False)

    def get_route(self, plan: Dict[str, Any]) -> str:
        """Get the routing destination for a plan."""
        return plan.get("route", "chat")

    def get_models(self, plan: Dict[str, Any]) -> List[str]:
        """Get the selected models for a plan."""
        return plan.get("selected_models", [CHAT_MODEL_NAME])

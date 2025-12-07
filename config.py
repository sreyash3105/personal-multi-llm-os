"""
Central configuration for the local AI assistant.
Model names, URLs, and general constants live here.

You can register ALL your local models in AVAILABLE_MODELS
and then pick which ones are active for coder/reviewer/judge/study/chat/vision.
"""

# Ollama HTTP endpoint
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


# ---- Model registry ----
# All models detected from `ollama list`
AVAILABLE_MODELS = {
    "qwen25_coder_7b": "qwen2.5-coder:7b",
    "llava_7b": "llava:7b",
    "phi3_3_8b": "phi3:3.8b",
    "llama31_8b": "llama3.1:8b",
    "qwen25_7b": "qwen2.5:7b",
    "qwen25_14b": "qwen2.5:14b",
    "codestral_22b": "codestral:22b",
    "deepseek_coder_v2_16b": "deepseek-coder-v2:16b",
    "llama3_8b": "llama3:8b",
}


# ---- Active model selection ----
# Choose which model should play each role

# Fast coder (you can switch to "phi3_3_8b" if you prefer max speed)
ACTIVE_CODER_MODEL_KEY = "qwen25_coder_7b"
# ACTIVE_CODER_MODEL_KEY = "phi3_3_8b"

# Reviewer: heavy, high-quality code reviewer
ACTIVE_REVIEWER_MODEL_KEY = "codestral_22b"

# Judge: light general reasoner to score confidence/conflict
ACTIVE_JUDGE_MODEL_KEY = "qwen25_7b"

# Study / teaching model: deeper reasoning, good explanations
ACTIVE_STUDY_MODEL_KEY = "qwen25_14b"


def _get_model(name_key: str) -> str:
    try:
        return AVAILABLE_MODELS[name_key]
    except KeyError:
        raise RuntimeError(
            f"Model key '{name_key}' is not defined in AVAILABLE_MODELS. "
            f"Please add it or fix ACTIVE_*_MODEL_KEY in config.py."
        )


CODER_MODEL_NAME = _get_model(ACTIVE_CODER_MODEL_KEY)
REVIEWER_MODEL_NAME = _get_model(ACTIVE_REVIEWER_MODEL_KEY)
JUDGE_MODEL_NAME = _get_model(ACTIVE_JUDGE_MODEL_KEY)
STUDY_MODEL_NAME = _get_model(ACTIVE_STUDY_MODEL_KEY)


# ---- Feature toggles ----
# Judge stage can be turned off anytime without code edits
JUDGE_ENABLED = True

# Auto-escalation: use judge scores to decide whether to call heavy reviewer
ESCALATION_ENABLED = True
# If confidence < this threshold, we escalate to reviewer
ESCALATION_CONFIDENCE_THRESHOLD = 8
# If conflict > this threshold, we escalate to reviewer
ESCALATION_CONFLICT_THRESHOLD = 6


# ---- Request / pipeline settings ----
REQUEST_TIMEOUT = 600
DEFAULT_MODE = "code_reviewed"


# ---- History / logging ----
HISTORY_DIR = "history"
HISTORY_MAX_ENTRIES = 1000


# ---- Chat model ----
# Default chat model for the multi-profile chat workspace.
# You can change this to any value from AVAILABLE_MODELS or a raw Ollama name.
CHAT_MODEL_NAME = AVAILABLE_MODELS.get("llama3_8b", "llama3:8b")

# Smarter / heavier chat model for the "Smart" button in the UI.
# If qwen2.5:14b is not available, falls back to default chat model.
SMART_CHAT_MODEL_NAME = AVAILABLE_MODELS.get("qwen25_14b", CHAT_MODEL_NAME)


# ---- Vision settings ----
# Vision (LLaVA) model for /api/vision and chat vision
VISION_MODEL_NAME = AVAILABLE_MODELS.get("llava_7b", "llava:7b")

# Toggle to disable vision quickly if needed
VISION_ENABLED = True


# ---- Tools runtime settings ----
# Global feature flag: when False, tools are never executed.
TOOLS_RUNTIME_ENABLED = True

# If True, tools runtime will emit trace records into history.
TOOLS_RUNTIME_LOGGING = True

# Allow chat messages to directly trigger tools with the "///tool" command.
# When False, chat behaves exactly as before and ignores tool tags.
TOOLS_IN_CHAT_ENABLED = True
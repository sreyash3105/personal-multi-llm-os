"""
Central configuration for the local AI assistant.

All model names, ports, file limits, and feature toggles live here.
This file is imported everywhere but holds NO heavy logic.
"""

# ----- OLLAMA API -----
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


# ----- AVAILABLE MODEL REGISTRY -----
# These names must match the output of `ollama list`
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


# ----- ACTIVE MODELS (roles) -----
# You can switch any role anytime without modifying pipeline logic
ACTIVE_CODER_MODEL_KEY = "qwen25_coder_7b"
ACTIVE_REVIEWER_MODEL_KEY = "codestral_22b"
ACTIVE_JUDGE_MODEL_KEY = "qwen25_7b"
ACTIVE_STUDY_MODEL_KEY = "qwen25_14b"
ACTIVE_CHAT_MODEL_KEY = "llama3_8b"
ACTIVE_VISION_MODEL_KEY = "llava_7b"


def _get(name_key: str) -> str:
    if name_key not in AVAILABLE_MODELS:
        raise RuntimeError(
            f"Model key '{name_key}' not found in AVAILABLE_MODELS. "
            "Fix ACTIVE_*_MODEL_KEY in config.py"
        )
    return AVAILABLE_MODELS[name_key]


# Final resolved names
CODER_MODEL_NAME = _get(ACTIVE_CODER_MODEL_KEY)
REVIEWER_MODEL_NAME = _get(ACTIVE_REVIEWER_MODEL_KEY)
JUDGE_MODEL_NAME = _get(ACTIVE_JUDGE_MODEL_KEY)
STUDY_MODEL_NAME = _get(ACTIVE_STUDY_MODEL_KEY)
CHAT_MODEL_NAME = _get(ACTIVE_CHAT_MODEL_KEY)
VISION_MODEL_NAME = _get(ACTIVE_VISION_MODEL_KEY)


# ----- SYSTEM BEHAVIOR TOGGLES -----
JUDGE_ENABLED = True
ESCALATION_ENABLED = True
ESCALATION_CONFIDENCE_THRESHOLD = 8
ESCALATION_CONFLICT_THRESHOLD = 6


# ----- TIMEOUTS -----
REQUEST_TIMEOUT = 600  # seconds


# ----- HISTORY -----
HISTORY_DIR = "history"
HISTORY_MAX_ENTRIES = 1000


# ----- VISION FEATURE -----
VISION_ENABLED = True

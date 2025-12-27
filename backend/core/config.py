import os
from pathlib import Path

"""
Central configuration for the local AI assistant.
Model names, URLs, and general constants live here.

HARDNING BASE:
- Phase 2 introduces concurrency + timeout guardrails:
  - MAX_CONCURRENT_HEAVY_REQUESTS
  - OLLAMA_REQUEST_TIMEOUT_SECONDS
  - TOOLS_MAX_RUNTIME_SECONDS
"""

# Ollama HTTP endpoint
OLLAMA_URL = "http://127.0.0.1:11434"

# ---- Model registry ----
# All models detected from `ollama list`
AVAILABLE_MODELS = {
    "qwen25_coder_7b": "qwen2.5-coder:7b",
    "llava_phi3": "llava-phi3:latest",
    "phi3": "phi3:latest",
    "llama31_8b": "llama3.1:8b",
    "qwen2_7b": "qwen2:7b",
    "qwen25_7b": "qwen2.5:7b",
    "starcoder2_7b": "starcoder2:7b",
    "starcoder2_3b": "starcoder2:3b",
    "codellama_7b": "codellama:7b",
    "deepseek_coder_67b": "deepseek-coder:6.7b",
    "deepseek_r1_7b": "deepseek-r1:7b",
    "mistral": "mistral:latest",
    "gemma2_9b": "gemma2:9b",
    "gemma2_2b": "gemma2:2b",
    "llama32": "llama3.2:latest",
    "nomic_embed": "nomic-embed-text:latest",
}

# ---- Active model selection ----
ACTIVE_CODER_MODEL_KEY = "qwen25_coder_7b"
ACTIVE_REVIEWER_MODEL_KEY = "deepseek_coder_67b"
ACTIVE_JUDGE_MODEL_KEY = "deepseek_r1_7b"
ACTIVE_STUDY_MODEL_KEY = "gemma2_9b"

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
JUDGE_ENABLED = True
ESCALATION_ENABLED = True
ESCALATION_CONFIDENCE_THRESHOLD = 0.8  # Normalized 0.0-1.0 usually preferred, but 8 is fine if judge logic handles it
ESCALATION_CONFLICT_THRESHOLD = 0.6    # Normalized 0.0-1.0 usually preferred

# ---- Request / pipeline settings ----
REQUEST_TIMEOUT = 600
DEFAULT_MODE = "code_reviewed"

# ---- History / logging ----
HISTORY_DIR = "history"
HISTORY_MAX_ENTRIES = 1000

# ---- Chat model ----
CHAT_MODEL_NAME = AVAILABLE_MODELS.get("llama31_8b", "llama3.1:8b")
SMART_CHAT_MODEL_NAME = AVAILABLE_MODELS.get("deepseek_r1_7b", "deepseek-r1:7b")

# ---- Vision settings ----
VISION_MODEL_NAME = AVAILABLE_MODELS.get("llava_phi3", "llava-phi3:latest")
VISION_ENABLED = True

# ---- Speech-to-text (Whisper / STT) ----
STT_ENABLED = True
STT_MODEL_NAME = "small"
STT_ENGINE = "whisper"
STT_DEVICE = "cuda"
STT_COMPUTE_TYPE = "float16"

# ---- Tools runtime settings ----
TOOLS_RUNTIME_ENABLED = True
TOOLS_RUNTIME_LOGGING = True
TOOLS_IN_CHAT_ENABLED = True
TOOLS_CHAT_HYBRID_ENABLED = True

# ---- Security enforcement settings (V3.7) ----
SECURITY_ENFORCEMENT_MODE = "off"
SECURITY_MIN_ENFORCED_LEVEL = 4
SECURITY_RISK_THRESHOLDS = {}
SECURITY_TOOL_OVERRIDES = {}
SECURITY_OPERATION_OVERRIDES = {}

# ---- Phase B: Perception confidence thresholds ----
PERCEPTION_CONFIDENCE_LOW_THRESHOLD = 0.3
PERCEPTION_CONFIDENCE_MEDIUM_THRESHOLD = 0.6
PERCEPTION_CONFIDENCE_HIGH_THRESHOLD = 0.8
PERCEPTION_CONFIRM_REQUIRED = True

# ---- Phase B: Confirmation lifecycle ----
CONFIRMATION_TTL_SECONDS = 300  # 5 minutes default
CONFIRMATION_CLEANUP_INTERVAL_SECONDS = 30  # Cleanup every 30 seconds for better responsiveness

# ---- Phase C: Permission system ----
PERMISSION_SYSTEM_ENABLED = True  # Dry-run mode: logs permission decisions but does not enforce

# ---- HARDNING BASE · Phase 2 — Concurrency & timeouts ----
# Maximum number of heavy operations (LLM, Vision, STT) that can run at the same time.
MAX_CONCURRENT_HEAVY_REQUESTS = 2

# Timeout for individual Ollama model calls (in seconds).
OLLAMA_REQUEST_TIMEOUT_SECONDS = 120

# Maximum allowed runtime for a single tool execution (in seconds).
TOOLS_MAX_RUNTIME_SECONDS = 60
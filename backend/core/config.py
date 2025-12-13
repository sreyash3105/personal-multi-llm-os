"""
Central configuration for the local AI assistant.
Model names, URLs, and general constants live here.

You can register ALL your local models in AVAILABLE_MODELS
and then pick which ones are active for coder/reviewer/judge/study/chat/vision.

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
# Choose which model should play each role

# Fast coder (you can switch to "phi3" if you prefer max speed)
ACTIVE_CODER_MODEL_KEY = "qwen25_coder_7b"

# Reviewer: heavy, high-quality code reviewer
ACTIVE_REVIEWER_MODEL_KEY = "deepseek_coder_67b"

# Judge: Uses DeepSeek R1 for superior reasoning and logic verification [UPDATED]
ACTIVE_JUDGE_MODEL_KEY = "deepseek_r1_7b"

# Study / teaching model: deeper reasoning, good explanations
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
# Judge stage can be turned off anytime without code edits
JUDGE_ENABLED = True

# Auto-escalation: use judge scores to decide whether to call heavy reviewer
ESCALATION_ENABLED = True
# If confidence < this threshold, we escalate to reviewer
ESCALATION_CONFIDENCE_THRESHOLD = 8
# If conflict > this threshold, we escalate to reviewer
ESCALATION_CONFLICT_THRESHOLD = 6


# ---- Request / pipeline settings ----
# Legacy global timeout for long-running requests (in seconds).
# Specific per-model / per-tool timeouts are defined below in HARDNING BASE guardrails.
REQUEST_TIMEOUT = 600
DEFAULT_MODE = "code_reviewed"


# ---- History / logging ----
HISTORY_DIR = "history"
HISTORY_MAX_ENTRIES = 1000


# ---- Chat model ----
# Default chat model for the multi-profile chat workspace.
CHAT_MODEL_NAME = AVAILABLE_MODELS.get("llama31_8b", "llama3.1:8b")

# Smarter / heavier chat model for the "Smart" button in the UI.
# [UPDATED] Using DeepSeek R1 for better planning and reasoning
SMART_CHAT_MODEL_NAME = AVAILABLE_MODELS.get("deepseek_r1_7b", "deepseek-r1:7b")


# ---- Vision settings ----
# Vision (LLaVA) model for /api/vision and chat vision
VISION_MODEL_NAME = AVAILABLE_MODELS.get("llava_phi3", "llava-phi3:latest")

# Toggle to disable vision quickly if needed
VISION_ENABLED = True

# ---- Speech-to-text (Whisper / STT) ----
STT_ENABLED = True
STT_MODEL_NAME = "small"      # or "base" if you prefer
STT_ENGINE = "whisper"
STT_DEVICE = "cuda"           # "cuda" for GPU, "cpu" for CPU
STT_COMPUTE_TYPE = "float16"  # use "float32" if fp16 causes issues


# ---- Tools runtime settings ----
# Global feature flag: when False, tools are never executed.
TOOLS_RUNTIME_ENABLED = True

# If True, tools runtime will emit trace records into history.
TOOLS_RUNTIME_LOGGING = True

# Allow chat messages to directly trigger tools with the "///tool" command.
TOOLS_IN_CHAT_ENABLED = True

# When enabled, the special "///tool+chat TOOL_NAME" command in chat will:
#   1) Execute the tool
#   2) Feed the tool result into the chat model
#   3) Return a natural language summary instead of raw JSON.
TOOLS_CHAT_HYBRID_ENABLED = True

# ---- Security enforcement settings (V3.7) ----
# Global mode for using SecurityEngine + sessions.
# "off"    -> current behavior (log-only, never block anything).
# "soft"   -> high-risk operations can return "security_approval_required"
# "strict" -> reserved for future; can be used to hard-block without approval.
SECURITY_ENFORCEMENT_MODE = "off"

# Minimum auth level that triggers enforcement when mode != "off".
# 4 = CONFIRM_SENSITIVE (allows minor/safe stuff, blocks risky/system stuff)
SECURITY_MIN_ENFORCED_LEVEL = 4

# Optional: extra tuning knobs for SecurityEngine.
SECURITY_RISK_THRESHOLDS = {}
SECURITY_TOOL_OVERRIDES = {}
SECURITY_OPERATION_OVERRIDES = {}


# ---- HARDNING BASE · Phase 2 — Concurrency & timeouts ----
# These guardrails are used by pipeline.py, vision_pipeline.py, tools_runtime.py, etc.

# Maximum number of heavy operations that can run at the same time.
MAX_CONCURRENT_HEAVY_REQUESTS = 2

# Timeout for individual Ollama model calls (in seconds).
# DeepSeek R1 can be verbose, so 120s is a good safety margin.
OLLAMA_REQUEST_TIMEOUT_SECONDS = 120

# Maximum allowed runtime for a single tool execution (in seconds).
TOOLS_MAX_RUNTIME_SECONDS = 60
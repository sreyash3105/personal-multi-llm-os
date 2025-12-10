# backend/modules/router/classifier.py
import logging
from typing import Dict, Optional

from backend.modules.router.rules import rule_based_intent

logger = logging.getLogger(__name__)

# Tunables
LLM_ENABLED = True  # set to False to skip LLM calls (safe offline)
LLM_WEIGHT = 0.6    # relative weight of LLM vs rules (0..1); rules weight = 1-LLM_WEIGHT

def llm_intent_score(text: str) -> Optional[Dict]:
    """
    Optional LLM-based classifier hook. Tries to call an available LLM helper in your
    codebase; if none found, returns None. The function should return:
      {"intent": "chat"|"code"|..., "score": 0.0-1.0, "explain": "..."}

    Implemented as a best-effort: tries common pipeline helper names, otherwise None.
    """
    if not LLM_ENABLED:
        return None

    try:
        # Try to reuse an existing pipeline classifier if present. Several choices:
        # 1) backend.chat_pipeline.classify_intent_llm
        # 2) backend.pipeline.classify_with_llm
        import importlib
        candidates = [
            "backend.chat_pipeline",
            "backend.pipeline",
            "backend.modules.router.llm_stub"
        ]
        for modname in candidates:
            try:
                mod = importlib.import_module(modname)
            except Exception:
                continue
            # try common function names
            for fn in ("classify_intent_llm", "run_intent_llm", "classify_with_llm"):
                fnobj = getattr(mod, fn, None)
                if callable(fnobj):
                    logger.debug("Using LLM function %s.%s for intent classification", modname, fn)
                    out = fnobj(text)
                    # Expect out as dict {"intent":..., "score":...}
                    if isinstance(out, dict) and "intent" in out:
                        return out
        # fallback: no available function
        return None
    except Exception as e:
        logger.exception("LLM intent scorer failed: %s", e)
        return None

def merge_scores(rule: Dict, llm: Optional[Dict]) -> Dict:
    """
    Merge rule and llm signals into final decision.
    Uses weighted average of confidences and rule override for strong rule hits.
    """
    rule_intent = rule.get("intent", "unknown")
    rule_score = float(rule.get("score", 0.0))

    if llm is None:
        return {"intent": rule_intent, "confidence": rule_score, "evidence": {"rule": rule, "llm": None}}

    llm_intent = llm.get("intent", "unknown")
    llm_score = float(llm.get("score", 0.0))

    # If a rule has very high confidence, prefer it
    if rule_score >= 0.94:
        final_intent = rule_intent
        final_conf = max(rule_score, llm_score * 0.9)
    else:
        # weighted merge favoring llm_weight
        final_conf_by_llm = LLM_WEIGHT * llm_score + (1 - LLM_WEIGHT) * rule_score
        # if intents agree, boost confidence slightly
        if rule_intent == llm_intent:
            final_intent = rule_intent
            final_conf = min(1.0, final_conf_by_llm + 0.05)
        else:
            # choose the higher scored intent but allow tie-breaker favoring llm for ambiguous cases
            if llm_score + 0.02 >= rule_score:
                final_intent = llm_intent
                final_conf = final_conf_by_llm
            else:
                final_intent = rule_intent
                final_conf = final_conf_by_llm * 0.95

    return {"intent": final_intent, "confidence": float(round(final_conf, 4)), "evidence": {"rule": rule, "llm": llm}}

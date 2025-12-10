# backend/modules/router/rules.py
import re
from typing import Tuple, Dict

# Simple rule patterns with intent and a confidence boost (0-1)
_RULES = [
    # explicit tool prefix
    (re.compile(r'^\s*///|^\s*/tool\b|^\s*tool:' , re.I), ("tool", 0.99)),
    # code-like content (python/ js / html markers)
    (re.compile(r'\b(def |class |import |from |console\.log|<script|</html>|function\(|var )', re.I), ("code", 0.92)),
    # automation patterns (mouse, click, press, open, close, shutdown)
    (re.compile(r'\b(open|close|launch|start|stop|shutdown|restart|click|double click|move mouse|move cursor|press |type |scroll|drag)\b', re.I), ("automation", 0.88)),
    # file operations
    (re.compile(r'\b(read file|write file|delete file|create file|move file|copy file|mkdir|rm |del )\b', re.I), ("file_op", 0.9)),
    # search / query
    (re.compile(r'\b(search|find|lookup|what is|who is|how to|explain|define)\b', re.I), ("chat", 0.75)),
    # email / send
    (re.compile(r'\b(send email|email to|compose email|mail)\b', re.I), ("tool", 0.8)),
    # risky keywords
    (re.compile(r'\b(format disk|delete all|factory reset|rm -rf|wipe)\b', re.I), ("unsafe", 0.99)),
]

def rule_based_intent(text: str) -> Dict:
    """
    Returns a dict: {"intent": str, "score": float, "matches": [patterns]}
    """
    text = text or ""
    best_intent = "unknown"
    best_score = 0.0
    matches = []
    for patt, (intent, weight) in _RULES:
        if patt.search(text):
            matches.append({"pattern": patt.pattern, "intent": intent, "weight": weight})
            if weight > best_score:
                best_score = weight
                best_intent = intent
    if best_score == 0.0:
        return {"intent": "unknown", "score": 0.0, "matches": matches}
    return {"intent": best_intent, "score": best_score, "matches": matches}

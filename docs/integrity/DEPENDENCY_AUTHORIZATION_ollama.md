# DEPENDENCY INTRODUCTION: ollama Python Library

## Authorization
Option A: Selective Dependency Introduction
Justification: Replace custom HTTP requests to Ollama with official library

---

## DEPENDENCY TO ADD

**Package: ollama**

**Version: ^0.3.0**

**Purpose:**
Simplify HTTP requests to local Ollama API using official Python client library.

**Benefits:**
1. Removes custom request wrapping code
2. Standardizes error handling
3. Simplifies retry logic
4. Improves maintainability
5. Maintains local-first design (ollama talks to local server)

**Replaces:**
- `requests.post()` calls in:
  - backend/modules/code/pipeline.py (line 71)
  - backend/modules/kb/vector_store.py (line 47)
  - backend/modules/vision/vision_pipeline.py (line 97)

**Impact on LOC:**
- Removes ~50 lines of custom request handling
- Replaces with library calls
- Net: -50 LOC

**Behavioral Impact:**
- No behavioral changes
- Same API calls to local Ollama
- Same timeout handling
- Same JSON serialization

**Integrity Impact:**
- NONE: Local-first design preserved
- NONE: Observability preserved
- NONE: Failure handling preserved

---

## JUSTIFICATION

Current code uses `requests.post()` to call local Ollama API:

```python
resp = requests.post(url, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)
```

This requires:
- Custom URL construction
- Manual JSON serialization
- Manual timeout handling
- Manual error checking

Using `ollama` library provides:

```python
from ollama import Client

client = Client(host='http://localhost:11434')
response = client.chat(model_name, messages)
```

Benefits:
- Official client library
- Built-in timeout handling
- Built-in error handling
- Type hints
- Cleaner code

**Classification:**
- BEHAVIORAL_SHIFT (EXPECTED)
- Not regression: Simplification, not removal of capability
- No authority impact: Same local Ollama calls

---

## REQUIRED FILES

**Update:**
- backend/requirements.txt

**Implementation Required (NOT IN THIS PHASE):**
- backend/modules/code/pipeline.py
- backend/modules/kb/vector_store.py
- backend/modules/vision/vision_pipeline.py

Implementation files will be updated in separate PR/phase.

**This phase adds dependency authorization only.**

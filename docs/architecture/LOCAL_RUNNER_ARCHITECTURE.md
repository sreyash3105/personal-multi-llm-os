# LOCAL RUNNER

## FastAPI-Free Transition

Local runner for invoking AIOS core functionality directly without HTTP/API layer.

### Files to Remove
- backend/code_server.py (502 lines)
- backend/modules/router/api_router.py
- backend/modules/router/approval_router.py
- backend/modules/router/confirmation_router.py
- backend/modules/router/permission_router.py
- backend/modules/router/stt_router.py
- backend/modules/router/tts_router.py
- backend/modules/automation/router.py
- backend/modules/chat/chat_ui.py
- backend/modules/telemetry/dashboard.py

**Total LOC to remove: ~1,200 lines**

### Architecture
OLD: FastAPI → Routers → Core Modules
NEW: Local Runner → Core Modules

Core modules remain unchanged:
- backend/modules/code/pipeline.py
- backend/modules/tools/tools_runtime.py
- backend/modules/vision/vision_pipeline.py
- backend/core/*.py
- All pattern aggregation layer

### Core Module Interfaces

Core modules expose:
- run_coder(), run_reviewer(), run_judge(), run_study()
- execute_tool(tool, args, context)
- run_vision(image_bytes, user_prompt, mode)

These are direct Python functions.
No HTTP layer required.

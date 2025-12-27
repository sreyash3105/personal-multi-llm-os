# Personal Multi-LLM Operating System Documentation

## Overview

The Personal Multi-LLM Operating System is a local-first, privacy-preserving AI assistant that runs entirely on your own machine. It acts as a desktop AI OS with a code pipeline, study mode, multimodal chat, vision AI, per-profile memory, tools runtime, and an observability dashboard — all powered by local LLMs via Ollama.

### Key Features

- **🔧 Code AI**: Coder → Reviewer → Judge → Final decision cycle
- **📚 Study Mode**: ///short, ///deep, ///quiz, or default teaching
- **🧠 Multimodal Chat**: Multi-profile, multi-chat workspace with model overrides
- **👁 Vision AI**: OCR / UI debug / code from screenshot / detailed image description
- **🧩 Tools Runtime**: Run local tools from chat via ///tool and ///tool+chat
- **🗄 Memory**: Per-profile knowledge base (SQLite) with context retrieval
- **📊 Dashboard**: Full trace of every AI interaction (coder / reviewer / judge flow)
- **🔒 Offline**: Nothing leaves your device — no cloud calls at any stage
- **🏗 Architecture**: Client (Laptop / Browser) ↔ LAN HTTP ↔ FastAPI Backend ↔ SQLite (Chat / KB / History) ↔ Ollama

## Architecture

### Core Components

1. **FastAPI Backend** (`code_server.py`): Main application server handling all API endpoints
2. **Modules Directory**: Organized functionality into specialized modules
3. **Configuration System** (`config.py`): Centralized configuration for models, features, and settings
4. **Database Layer**: SQLite databases for chat history, knowledge base, and telemetry

### Module Structure

```
backend/modules/
├── automation/     # Workflow automation and step execution
├── chat/          # Multi-profile chat interface and API
├── code/          # Code generation pipeline (coder/reviewer/judge)
├── common/        # Shared utilities and guardrails
├── jobs/          # Background job management
├── kb/            # Knowledge base and profile memory
├── router/        # Intent classification and request routing
├── security/      # Security engine and session management
├── stt/           # Speech-to-text processing
├── telemetry/     # Logging, history, and dashboard
├── tools/         # Local tools runtime and file operations
└── vision/        # Vision AI and image processing
```

## Setup and Installation

### Requirements

- Python 3.10+
- Ollama installed and running
- At least one LLM pulled (e.g., `ollama pull qwen2.5-coder:7b`)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Pull required Ollama models:
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama pull deepseek-coder:6.7b
   ollama pull qwen2.5:7b
   ollama pull llama3.1:8b
   ollama pull llava-phi3:latest
   ```

### Launch

```bash
uvicorn code_server:app --host 0.0.0.0 --port 8000
```

### Interfaces

- **Chat UI**: http://localhost:8000/chat
- **Dashboard**: http://localhost:8000/dashboard

## Configuration

### Model Configuration

The system supports multiple models for different roles:

```python
# Active model selection
ACTIVE_CODER_MODEL_KEY = "qwen25_coder_7b"      # Fast coding
ACTIVE_REVIEWER_MODEL_KEY = "deepseek_coder_67b" # Quality review
ACTIVE_JUDGE_MODEL_KEY = "qwen25_7b"           # Confidence/conflict scoring
ACTIVE_STUDY_MODEL_KEY = "gemma2_9b"           # Teaching/explanation
VISION_MODEL_NAME = "llava_phi3:latest"        # Vision processing
CHAT_MODEL_NAME = "llama31_8b"                 # Default chat
SMART_CHAT_MODEL_NAME = "gemma2_9b"            # Advanced chat
```

### Feature Toggles

```python
JUDGE_ENABLED = True                    # Enable judge stage
ESCALATION_ENABLED = True              # Auto-escalate based on judge scores
VISION_ENABLED = True                  # Enable vision processing
TOOLS_RUNTIME_ENABLED = True           # Enable tools execution
TOOLS_IN_CHAT_ENABLED = True           # Allow ///tool commands in chat
STT_ENABLED = True                     # Enable speech-to-text
SECURITY_ENFORCEMENT_MODE = "off"      # Security enforcement level
```

### Guardrails and Limits

```python
MAX_CONCURRENT_HEAVY_REQUESTS = 2      # Concurrency control
OLLAMA_REQUEST_TIMEOUT_SECONDS = 120   # Request timeouts
TOOLS_MAX_RUNTIME_SECONDS = 60         # Tool execution limits
ESCALATION_CONFIDENCE_THRESHOLD = 8    # Judge escalation thresholds
ESCALATION_CONFLICT_THRESHOLD = 6
```

## API Endpoints

### Code Generation

**POST /api/code**
- Generate code with coder → reviewer → judge pipeline
- Modes: default, ///raw, ///review-only, ///ctx, ///continue
- Auto-escalation based on judge confidence scores

### Study/Teaching

**POST /api/study**
- Educational content generation
- Styles: ///short, ///deep, ///quiz, default

### Vision Processing

**POST /api/vision**
- Image analysis and OCR
- Modes: auto, describe, ocr, code, debug

### Tools Runtime

**POST /api/tools/execute**
- Execute local tools and utilities
- Manual execution endpoint

### Chat System

**POST /api/chat**
- Multi-profile chat with model overrides
- Supports ///tool and ///tool+chat commands
- Vision integration in chat

**Chat Management APIs:**
- GET/POST/PATCH/DELETE /api/chat/profiles
- GET/POST/PATCH/DELETE /api/chat/chats
- GET /api/chat/messages
- POST /api/chat/profile_summary
- POST /api/chat/profile_kb_auto
- GET/POST/DELETE /api/chat/profile_kb*

### Security

**POST /api/security/auth**
- Create authorization sessions for sensitive operations

### Speech-to-Text

**POST /api/stt/transcribe**
- Audio transcription with language detection

### Dashboard

**GET /dashboard**
- Observability dashboard for all AI interactions

## Module Details

### Code Pipeline (`modules/code/`)

**pipeline.py**: Core AI logic with guardrails
- **Coder Stage**: Fast code generation
- **Reviewer Stage**: Quality improvement and fixes
- **Judge Stage**: Confidence/conflict scoring (0-10 scale)
- **Study Stage**: Educational content generation

**prompts.py**: System prompts for different stages

### Chat System (`modules/chat/`)

**chat_ui.py**: Main chat interface and API
- Multi-profile workspace
- Chat/message management
- Knowledge base integration
- Tool execution in chat
- Vision support

**chat_pipeline.py**: Smart chat processing

**chat_storage.py**: SQLite-based chat persistence

### Router (`modules/router/`)

**router.py**: Intent classification and routing
- Hybrid classification (rules + LLM)
- Routes to: tools, code, automation, chat
- Security integration

**classifier.py**: LLM-based intent scoring

**rules.py**: Rule-based intent detection

### Tools Runtime (`modules/tools/`)

**tools_runtime.py**: Tool execution engine
- Registry system for local tools
- Security assessment and enforcement
- Concurrency and timeout management

**file_tools.py**: File operation tools
- Profile note management
- Knowledge base CRUD operations

### Vision (`modules/vision/`)

**vision_pipeline.py**: Image processing pipeline
- OCR text extraction
- UI debugging
- Code generation from screenshots
- Detailed image descriptions

### Knowledge Base (`modules/kb/`)

**profile_kb.py**: Per-profile memory system
- SQLite-based knowledge storage
- Context retrieval for chat
- Snippet search and management

### Security (`modules/security/`)

**security_engine.py**: Security evaluation
- Risk assessment for operations
- Authorization levels and enforcement

**security_sessions.py**: Session management for approvals

### Telemetry (`modules/telemetry/`)

**history.py**: Interaction logging
- SQLite-based history storage
- JSONL fallback logging

**dashboard.py**: Web dashboard for traces

**risk.py**: Risk assessment utilities

### Automation (`modules/automation/`)

**executor.py**: Workflow execution

**router.py**: Automation routing

**step_sanitizer.py**: Safety checks for automation steps

### STT (`modules/stt/`)

**stt_service.py**: Speech-to-text processing
- Whisper model integration
- Audio decoding and transcription

**stt_router.py**: STT API endpoints

### Common Utilities (`modules/common/`)

**io_guards.py**: Input/output sanitization

**timeout_policy.py**: Timeout management

### Jobs (`modules/jobs/`)

**queue_manager.py**: Background job processing

## Usage Examples

### Code Generation

```bash
# Default mode (coder + reviewer + judge)
curl -X POST http://localhost:8000/api/code \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a Python function to calculate fibonacci numbers"}'

# Raw mode (coder only)
curl -X POST http://localhost:8000/api/code \
  -H "Content-Type: application/json" \
  -d '{"prompt": "///raw Write a hello world in C"}'
```

### Chat with Tools

```bash
# Execute tool in chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "default",
    "prompt": "///tool ping {\"message\": \"hello\"}"
  }'
```

### Vision Processing

```bash
# Upload image for analysis
curl -X POST http://localhost:8000/api/vision \
  -F "file=@screenshot.png" \
  -F "prompt=Describe this UI" \
  -F "mode=debug"
```

## Security and Privacy

- **Local-Only**: All processing happens on-device
- **No Cloud Dependencies**: No external API calls
- **SQLite Storage**: Local database for all data
- **Security Engine**: Risk assessment and enforcement
- **Session-Based Authorization**: For sensitive operations

## Development

### Adding New Tools

1. Register tool in `tools_runtime.py`
2. Implement tool function
3. Add security assessment
4. Test execution

### Extending the Router

1. Add new intent patterns in `rules.py`
2. Update classifier if needed
3. Add routing logic in `router.py`

### Custom Models

1. Add model to `AVAILABLE_MODELS` in `config.py`
2. Pull model via Ollama
3. Assign to appropriate role

## Troubleshooting

### Common Issues

- **Model not found**: Ensure Ollama models are pulled
- **Timeout errors**: Adjust timeout settings in config
- **Memory issues**: Reduce concurrent requests
- **Security blocks**: Check security enforcement mode

### Logs and Debugging

- Check dashboard at `/dashboard` for interaction traces
- Review history logs in `history/` directory
- Enable debug logging for detailed information

## Roadmap

- **V3.2**: Multimodal chat + tools + vision (Current)
- **V3.4**: Schedulers & automation
- **V3.6**: Embedding-based memory
- **V4.0**: Multi-agent orchestration

## License

Personal-Use Open License (non-commercial)

You may:
- Download, modify, run locally
- Build your own local AI OS

You may not:
- Resell or commercialize
- Host as a paid service

Commercial licensing available if needed.

## Contributing

- Fork the repository
- Learn from the architecture
- Build your own personal AI OS
- PRs reviewed based on available time

⭐ Star the repo and share what you build with it!

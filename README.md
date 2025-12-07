Personal Local Multi-LLM Operating System (Local AI OS)

A local-first, privacy-preserving AI assistant that runs entirely on your own machine — no cloud, no API keys, no external data sharing.

This system acts as a desktop AI OS with a code pipeline, study mode, multimodal chat, vision AI, per-profile memory, tools runtime, and an observability dashboard — all powered by local LLMs via Ollama.

🚀 Core Features
Module	Description
🔧 Code AI	Coder → Reviewer → Judge → Final decision cycle
📚 Study Mode	///short, ///deep, ///quiz, or default teaching
🧠 Multimodal Chat	Multi-profile, multi-chat workspace with model overrides
👁 Vision AI	OCR / UI debug / code from screenshot / detailed image description
🧩 Tools Runtime	Run local tools from chat via ///tool and ///tool+chat
🗄 Memory	Per-profile knowledge base (SQLite) with context retrieval
📊 Dashboard	Full trace of every AI interaction (coder / reviewer / judge flow)
🔒 Offline	Nothing leaves your device — no cloud calls at any stage
🏗 Architecture Overview
Client (Laptop / Browser)
        │
LAN HTTP
        │
FastAPI Backend  ←→  SQLite (Chat / KB / History)
        │
        ├── Code Pipeline (Coder / Reviewer / Judge)
        ├── Study Pipeline
        ├── Vision Pipeline (LLaVA)
        ├── Tools Runtime (local functions and utilities)
        └── Multimodal Chat Workspace
                 • Profiles
                 • Chats
                 • Vision messages
                 • Tool triggers


Ollama provides all model execution — no remote inference:

qwen2.5-coder
codestral
llama3.1
qwen2.5 (14B)
llava (vision)
phi3
deepseek-coder-v2
...

🖥 Running Locally
Requirements

Python 3.10+

Ollama installed

At least one LLM pulled (example: ollama pull qwen2.5-coder:7b)

Setup
pip install -r requirements.txt

Launch
uvicorn code_server:app --host 0.0.0.0 --port 8000

Interfaces
URL	Purpose
http://localhost:8000/chat	Multimodal chat workspace
http://localhost:8000/dashboard	Trace dashboard (history of all interactions)
⚙ Tools Runtime — Example

Inside chat, execute local tools directly:

///tool ping
{"message": "hello world"}


or with hybrid mode:

///tool+chat system_info


→ runs the tool and then asks a stronger model to summarize the result.

🧠 Vision Examples
/api/vision + image → OCR text
/api/vision + image → UI debugging
///vision inside chat (if enabled)


Vision messages are stored as captions, not raw base64 — keeping chat context clean.

🔐 Privacy & Local-Only Design

This repository does not include:

personal chat logs

history records

knowledge base content

internal documentation

All data stays local and never leaves your machine.

📝 License

Personal-Use Open License (non-commercial)
You may:

download

modify

run locally

build your own local AI OS

You may not:

resell

commercialize

host as a paid service

Commercial licensing is possible if needed.

⚠ Disclaimer

This is a personal research project, actively evolving.
Expect fast development, experimental modules, and refactoring across versions.

⭐ Contributions / Forking

Anyone is welcome to:

fork the repo

learn from the architecture

build their own personal AI OS on top of it

PRs may be reviewed based on available time.

🧭 Roadmap (High-Level)
Version	Goal
V3.2	Multimodal chat + tools + vision
V3.4	Schedulers & automation
V3.6	Embedding-based memory
V4.0	Multi-agent orchestration (optional)

If you like this project, star the repo ⭐
and feel free to share what you build with it.

End of README
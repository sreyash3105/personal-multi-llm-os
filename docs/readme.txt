# Local AI Operating System — Personal Developer Workspace

A fully local, privacy-first AI development environment designed to speed up engineering and automation work by acting as:
- A **code generation pipeline** (coder → reviewer → judge → escalation)
- A **multi-profile, multi-chat AI workspace** (project-oriented memory)
- A **vision-enabled assistant** (image analysis inside chats)
- A **LAN-accessible personal AI server** for desktop + laptop workflows

Runs **100% locally** using Ollama models — no cloud dependency, no telemetry.

---

## 🔥 Core Features

| Category | Features |
|---------|----------|
| Coding Assistant | Coder → Reviewer → Judge pipeline with auto-escalation |
| Multi-Chat AI | Profiles for projects + separate chats per profile |
| Memory | Full chat history + context preserved |
| Model Control | Default model config + profile override + chat override |
| Vision | Upload image → parse → respond in chat with stored thumbnail |
| Storage | All history stored locally in rotating logs + chat folders |
| LAN UI | Modern Web interface with WhatsApp-style chat UX |
| Privacy | No data leaves the machine |

---

## 🚀 Quick Start

### 1. Launch server
```sh
uvicorn code_server:app --host 0.0.0.0 --port 8100 --reload
Open the UI
http://<your_pc_ip>:8100/chat


Example LAN:

http://10.1.80.233:8100/chat

3. Dashboard
http://<your_pc_ip>:8100/dashboard

📁 Source Structure
Folder / File	Purpose
code_server.py	API server + routes
pipeline.py	coder / reviewer / judge logic
vision_pipeline.py	image → text processing
config.py	model registry + configuration
history.py	rotating logs for pipeline history
chat_storage.py	disk storage for profiles + chats
dashboard.py	web dashboard for pipeline logs
chat_ui.py	chat Web UI HTML + JS
prompts.py	system prompts (coder / reviewer / judge / tutor / chat)
🧠 Model Roles (from config.py)
Role	Description
CODER	Fast draft code generator
REVIEWER	Larger model to fix/upgrade code
JUDGE	Numerical confidence + conflict evaluator
STUDY	Long-form tutoring and explanation
CHAT	Default conversational model
VISION	Model for image parsing (optional & replaceable)

Override rules:

chat override > profile override > global default

🌐 API Overview
Area	Endpoints
Code	/api/code /api/study
Chat	/api/chat + profile/chat CRUD
Vision	/api/chat/vision
Dashboard	/api/dashboard/history (internal)

Detailed API signatures are documented in API_REFERENCE.md

🔐 Privacy

This system:

Runs locally

Stores all files locally

Never sends data to external services

💾 Persistence & Recovery

All data is stored on disk:

Chat workspace → reopens exactly where you left

Model overrides preserved

History files rotated to prevent size explosion

Safe for long-term project memory.

🗺 Roadmap Summary

(Full list in ROADMAP.md)

Future Area	Potential Upgrade
Agents	Autonomous task executor
Tools	Database + browser plug-ins
Teams	Shared LAN profiles / role-based access
Mobile	Optional phone UI over LAN
🧑‍💻 Primary Audience

This AI OS is for:

Solo developers

Project maintainers

Freelancers juggling multiple clients

Engineers who prefer local AI over cloud AI

⚠ Disclaimer

This is not a “product” — it's a personal productivity platform.
Freedom > perfection. Add, remix, experiment.
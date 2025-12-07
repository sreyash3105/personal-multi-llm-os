\# chat module



This package provides the chat UI and backend logic for the Local Personal AI OS.



Components:

\- `router.py` → Chat API `/api/chat` + web page `/chat`

\- `storage.py` → In-memory message history (per-session only)

\- `\_\_init\_\_.py` → Package marker



All chat messages stay \*\*local\*\* and \*\*never leave the PC\*\*.



The web UI does not depend on the code pipeline, tools, or vision system.

Only the chat model defined in `config.py` (CHAT\_MODEL\_NAME) is used.




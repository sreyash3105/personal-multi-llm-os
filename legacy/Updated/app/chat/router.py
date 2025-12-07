from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .storage import (
    create_chat,
    get_chat_messages,
    append_chat_message,
)

router = APIRouter()


@router.get("/chat", response_class=HTMLResponse)
def chat_ui_page():
    """
    Serves the chat UI (static HTML).
    """
    from pathlib import Path

    html_path = Path(__file__).parent / "chat_ui.html"
    if not html_path.exists():
        return HTMLResponse("<h3>chat_ui.html missing</h3>")

    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@router.post("/api/chat/new")
async def api_chat_new():
    """
    Create a new conversation and return its chat_id.
    """
    chat_id = create_chat()
    return {
        "ok": True,
        "chat_id": chat_id,
    }


@router.post("/api/chat/{chat_id}")
async def api_chat_send(chat_id: str, req: Request):
    """
    Append a user message to chat, and return full message history.
    """
    data = await req.json()
    text = (data.get("message") or "").strip()
    if not text:
        return JSONResponse({"ok": False, "error": "Empty message"}, status_code=400)

    append_chat_message(chat_id, role="user", text=text)
    messages = get_chat_messages(chat_id)

    return {
        "ok": True,
        "messages": messages,
    }


@router.get("/api/chat/{chat_id}")
async def api_chat_history(chat_id: str):
    """
    Return full chat history.
    """
    messages = get_chat_messages(chat_id)
    return {
        "ok": True,
        "messages": messages,
    }

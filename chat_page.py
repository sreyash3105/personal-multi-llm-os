from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/chat", response_class=HTMLResponse)
def chat_page() -> HTMLResponse:
    html = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Local Chat Workspace</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #020617;
      --bg-elevated: #020617;
      --border-subtle: #1f2937;
      --border-strong: #111827;
      --accent: #22c55e;
      --accent-soft: rgba(34,197,94,0.16);
      --accent-strong: rgba(34,197,94,0.55);
      --accent2: #0ea5e9;
      --accent2-soft: rgba(14,165,233,0.16);
      --text-muted: #9ca3af;
      --text-soft: #6b7280;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top left, #020617 0, #020617 40%, #020617 100%);
      color: #e5e7eb;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      padding: 8px 14px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .avatar {
      width: 26px;
      height: 26px;
      border-radius: 999px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      background: radial-gradient(circle at 30% 0%, #22c55e, #0f172a);
    }
    .title {
      font-size: 14px;
      font-weight: 500;
    }
    .subtitle {
      font-size: 11px;
      color: var(--text-muted);
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 11px;
      color: var(--text-muted);
    }
    main {
      flex: 1;
      display: flex;
      overflow: hidden;
    }
    .col {
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--border-subtle);
      background: rgba(2,6,23,0.98);
    }
    .col.profiles {
      width: 180px;
    }
    .col.chats {
      width: 220px;
    }
    .col.chat-window {
      flex: 1;
      border-right: none;
      background: radial-gradient(circle at top, rgba(15,23,42,0.85), #020617 60%, #020617 100%);
    }
    .col-header {
      padding: 6px 10px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--text-muted);
    }
    .col-header button,
    .pill-btn,
    .danger-btn {
      border: 1px solid var(--border-subtle);
      background: #020617;
      color: var(--text-muted);
      border-radius: 999px;
      font-size: 11px;
      padding: 3px 8px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: background 0.08s ease, border-color 0.08s ease, transform 0.08s ease, box-shadow 0.08s ease;
    }
    .col-header button:hover,
    .pill-btn:hover {
      border-color: rgba(148,163,184,0.9);
      background: rgba(15,23,42,0.9);
      transform: translateY(-0.5px);
      box-shadow: 0 2px 5px rgba(0,0,0,0.4);
    }
    .danger-btn {
      border-color: rgba(248,113,113,0.5);
      color: #fca5a5;
    }
    .danger-btn:hover {
      background: rgba(127,29,29,0.6);
      border-color: rgba(252,165,165,0.9);
    }
    .list {
      flex: 1;
      overflow-y: auto;
    }
    .item {
      padding: 6px 8px;
      font-size: 12px;
      border-bottom: 1px solid var(--border-subtle);
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .item.active {
      background: rgba(37,99,235,0.35);
      border-left: 2px solid #3b82f6;
    }
    .item .name-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 4px;
    }
    .item .name {
      font-weight: 500;
    }
    .item .meta {
      font-size: 10px;
      color: var(--text-soft);
      display: flex;
      justify-content: space-between;
      gap: 4px;
    }
    .small-tag {
      font-size: 10px;
      padding: 1px 6px;
      border-radius: 999px;
      border: 1px solid var(--border-subtle);
      color: var(--text-soft);
    }
    /* Chat window */
    .chat-header {
      padding: 6px 10px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      font-size: 11px;
    }
    .chat-header-left {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .chat-header-names {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
    }
    .chat-header-names span.profile {
      font-weight: 500;
    }
    .chat-header-names span.chat {
      color: var(--text-muted);
    }
    .chat-header-sub {
      color: var(--text-soft);
    }
    .chat-header-right {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .chat-header-right select {
      background: #020617;
      border-radius: 999px;
      border: 1px solid var(--border-subtle);
      color: #e5e7eb;
      font-size: 11px;
      padding: 3px 8px;
      outline: none;
    }
    .chat-header-right select:focus {
      border-color: rgba(59,130,246,0.8);
      box-shadow: 0 0 0 1px rgba(59,130,246,0.5);
    }
    .chat-summary-btn {
      border-radius: 999px;
      font-size: 11px;
      padding: 3px 8px;
      cursor: pointer;
      border: 1px solid rgba(34,197,94,0.6);
      background: rgba(21,128,61,0.3);
      color: #bbf7d0;
    }
    .chat-summary-btn:hover {
      background: rgba(22,163,74,0.6);
    }
    /* Messages */
    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 10px 10px 4px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .msg-row {
      display: flex;
      width: 100%;
    }
    .msg-row.user {
      justify-content: flex-end;
    }
    .msg-row.assistant {
      justify-content: flex-start;
    }
    .msg-bubble {
      max-width: 78%;
      padding: 7px 10px 4px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.4;
      white-space: pre-wrap;
      word-wrap: break-word;
      box-shadow: 0 1px 0 rgba(0,0,0,0.45);
      position: relative;
    }
    .msg-bubble.user {
      background: var(--accent-soft);
      border: 1px solid rgba(34,197,94,0.5);
      border-bottom-right-radius: 2px;
    }
    .msg-bubble.assistant {
      background: var(--accent2-soft);
      border: 1px solid rgba(56,189,248,0.6);
      border-bottom-left-radius: 2px;
    }
    .msg-bubble img.chat-thumb {
      max-width: 160px;
      border-radius: 10px;
      display: block;
      margin-bottom: 4px;
    }
    .msg-ts {
      font-size: 9px;
      color: var(--text-soft);
      margin-top: 2px;
      text-align: right;
    }
    /* Input */
    .chat-input {
      border-top: 1px solid var(--border-subtle);
      padding: 6px 8px;
      display: flex;
      align-items: flex-end;
      gap: 6px;
      background: radial-gradient(circle at top, rgba(15,23,42,0.9), #020617);
    }
    #prompt {
      flex: 1;
      resize: none;
      min-height: 32px;
      max-height: 80px;
      padding: 8px 10px;
      border-radius: 999px;
      border: 1px solid var(--border-subtle);
      background: #020617;
      color: #e5e7eb;
      font-size: 13px;
      line-height: 1.4;
      outline: none;
    }
    #prompt:focus {
      border-color: rgba(59,130,246,0.8);
      box-shadow: 0 0 0 1px rgba(59,130,246,0.5);
    }
    #send-btn {
      border: none;
      border-radius: 999px;
      padding: 0 18px;
      height: 34px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      background: linear-gradient(135deg, #22c55e, #16a34a);
      color: #020617;
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 70px;
      transition: transform 0.08s ease, box-shadow 0.08s ease, filter 0.08s ease;
    }
    #send-btn:disabled {
      opacity: 0.5;
      cursor: default;
      transform: none;
      box-shadow: none;
      filter: grayscale(0.3);
    }
    #send-btn:not(:disabled):hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 10px rgba(0,0,0,0.7);
    }
    /* Overlay for summary */
    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(15,23,42,0.84);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 30;
    }
    .overlay-inner {
      width: min(720px, 96vw);
      max-height: 80vh;
      background: #020617;
      border-radius: 16px;
      border: 1px solid var(--border-strong);
      box-shadow: 0 20px 60px rgba(0,0,0,0.9);
      display: flex;
      flex-direction: column;
    }
    .overlay-header {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
    }
    .overlay-body {
      padding: 10px 12px 12px;
      font-size: 12px;
      line-height: 1.5;
      overflow-y: auto;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .overlay-close {
      border-radius: 999px;
      border: 1px solid var(--border-subtle);
      background: #020617;
      color: var(--text-muted);
      font-size: 11px;
      padding: 3px 10px;
      cursor: pointer;
    }
    .overlay-close:hover {
      border-color: rgba(248,250,252,0.8);
      color: #e5e7eb;
    }
    .badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 999px;
      background: rgba(37,99,235,0.2);
      border: 1px solid rgba(59,130,246,0.6);
      color: #bfdbfe;
    }
    @media (max-width: 960px) {
      .col.profiles { display: none; }
      .col.chats { width: 190px; }
    }
    @media (max-width: 720px) {
      header { display: none; }
      main { flex-direction: column; }
      .col.profiles { display: none; }
      .col.chats { display: none; }
      .col.chat-window { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="avatar">AI</div>
      <div>
        <div class="title">Local Chat Workspace</div>
        <div class="subtitle">Profiles · Multi-chats · Model override · LAN-only</div>
      </div>
    </div>
    <div class="header-right">
      <span id="status-text">Ready</span>
    </div>
  </header>
  <main>
    <!-- Profiles column -->
    <div class="col profiles">
      <div class="col-header">
        <span>Profiles</span>
        <button id="add-profile-btn">+ New</button>
      </div>
      <div class="list" id="profiles-list"></div>
      <div style="padding: 6px 8px; border-top: 1px solid var(--border-subtle); display:flex; gap:4px;">
        <button class="pill-btn" id="rename-profile-btn">Rename</button>
        <button class="danger-btn" id="delete-profile-btn">Delete</button>
      </div>
    </div>

    <!-- Chats column -->
    <div class="col chats">
      <div class="col-header">
        <span>Chats</span>
        <button id="add-chat-btn">+ New</button>
      </div>
      <div class="list" id="chats-list"></div>
      <div style="padding: 6px 8px; border-top: 1px solid var(--border-subtle); display:flex; gap:4px;">
        <button class="pill-btn" id="rename-chat-btn">Rename</button>
        <button class="danger-btn" id="delete-chat-btn">Delete</button>
      </div>
    </div>

    <!-- Chat window -->
    <div class="col chat-window">
      <div class="chat-header">
        <div class="chat-header-left">
          <div class="chat-header-names">
            <span class="profile" id="active-profile-name">Profile: -</span>
            <span class="chat" id="active-chat-name">Chat: -</span>
          </div>
          <div class="chat-header-sub" id="chat-header-sub">
            Model: <span id="model-label">-</span>
          </div>
        </div>
        <div class="chat-header-right">
          <select id="model-select">
            <option value="">Default (config)</option>
          </select>
          <button class="chat-summary-btn" id="summary-btn">Summarize Profile</button>
        </div>
      </div>
      <div class="messages" id="messages"></div>
      <div class="chat-input">
        <button type="button" id="attach-btn" title="Attach image"
                style="border:1px solid var(--border-subtle);background:#020617;
                       border-radius:999px;width:34px;height:34px;
                       display:flex;align-items:center;justify-content:center;
                       font-size:15px;cursor:pointer;">
          📎
        </button>
        <input type="file" id="image-input" accept="image/*" style="display:none;" />
        <textarea id="prompt" placeholder="Type a message or add an image..." ></textarea>
        <button id="send-btn">Send</button>
      </div>
    </div>
  </main>

  <!-- Summary overlay -->
  <div class="overlay" id="summary-overlay">
    <div class="overlay-inner">
      <div class="overlay-header">
        <div>
          <span>Profile Summary</span>
          <span class="badge" id="summary-profile-label"></span>
        </div>
        <button class="overlay-close" id="summary-close-btn">Close</button>
      </div>
      <div class="overlay-body" id="summary-body"></div>
    </div>
  </div>

  <script>
    const profilesListEl = document.getElementById("profiles-list");
    const chatsListEl = document.getElementById("chats-list");
    const messagesEl = document.getElementById("messages");
    const promptEl = document.getElementById("prompt");
    const sendBtn = document.getElementById("send-btn");
    const statusTextEl = document.getElementById("status-text");

    const activeProfileNameEl = document.getElementById("active-profile-name");
    const activeChatNameEl = document.getElementById("active-chat-name");
    const modelLabelEl = document.getElementById("model-label");
    const modelSelectEl = document.getElementById("model-select");

    const addProfileBtn = document.getElementById("add-profile-btn");
    const renameProfileBtn = document.getElementById("rename-profile-btn");
    const deleteProfileBtn = document.getElementById("delete-profile-btn");

    const addChatBtn = document.getElementById("add-chat-btn");
    const renameChatBtn = document.getElementById("rename-chat-btn");
    const deleteChatBtn = document.getElementById("delete-chat-btn");

    const summaryBtn = document.getElementById("summary-btn");
    const summaryOverlay = document.getElementById("summary-overlay");
    const summaryBodyEl = document.getElementById("summary-body");
    const summaryProfileLabelEl = document.getElementById("summary-profile-label");
    const summaryCloseBtn = document.getElementById("summary-close-btn");

    const attachBtn = document.getElementById("attach-btn");
    const imageInput = document.getElementById("image-input");
    let pendingFile = null;

    let state = {
      profiles: [],
      chats: [],
      activeProfileId: null,
      activeChatId: null,
      models: [],
      defaultModel: null,
      loading: false,
    };

    function setStatus(text) {
      statusTextEl.textContent = text;
    }

    async function fetchJSON(url, options = {}) {
      const resp = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error("HTTP " + resp.status + ": " + text);
      }
      return resp.json();
    }

    function saveActiveIds() {
      if (state.activeProfileId) {
        localStorage.setItem("chat.activeProfileId", state.activeProfileId);
      }
      if (state.activeProfileId && state.activeChatId) {
        localStorage.setItem("chat.activeChatId." + state.activeProfileId, state.activeChatId);
      }
    }

    function restoreActiveIds() {
      const p = localStorage.getItem("chat.activeProfileId");
      if (p) state.activeProfileId = p;
      if (state.activeProfileId) {
        const c = localStorage.getItem("chat.activeChatId." + state.activeProfileId);
        if (c) state.activeChatId = c;
      }
    }

    function renderProfiles() {
      profilesListEl.innerHTML = "";
      state.profiles.forEach((p) => {
        const div = document.createElement("div");
        div.className = "item" + (p.id === state.activeProfileId ? " active" : "");
        div.dataset.id = p.id;

        const nameRow = document.createElement("div");
        nameRow.className = "name-row";

        const nameSpan = document.createElement("span");
        nameSpan.className = "name";
        nameSpan.textContent = p.display_name || p.id;

        const tagSpan = document.createElement("span");
        tagSpan.className = "small-tag";
        tagSpan.textContent = p.id;

        nameRow.appendChild(nameSpan);
        nameRow.appendChild(tagSpan);

        const metaDiv = document.createElement("div");
        metaDiv.className = "meta";
        metaDiv.textContent = p.created_at || "";

        div.appendChild(nameRow);
        div.appendChild(metaDiv);

        div.addEventListener("click", () => {
          if (state.activeProfileId !== p.id) {
            state.activeProfileId = p.id;
            state.activeChatId = null;
            saveActiveIds();
            refresh();
          }
        });

        profilesListEl.appendChild(div);
      });
    }

    function renderChats() {
      chatsListEl.innerHTML = "";
      const chats = state.chats || [];
      chats.forEach((c) => {
        const div = document.createElement("div");
        div.className = "item" + (c.id === state.activeChatId ? " active" : "");
        div.dataset.id = c.id;

        const nameRow = document.createElement("div");
        nameRow.className = "name-row";

        const nameSpan = document.createElement("span");
        nameSpan.className = "name";
        nameSpan.textContent = c.display_name || c.id;

        const tagSpan = document.createElement("span");
        tagSpan.className = "small-tag";
        tagSpan.textContent = c.id;

        nameRow.appendChild(nameSpan);
        nameRow.appendChild(tagSpan);

        const metaDiv = document.createElement("div");
        metaDiv.className = "meta";
        const msgCount = (c.message_count || 0) + " msg";
        const modelTag = c.model_override ? c.model_override : "default";
        metaDiv.innerHTML = "<span>" + msgCount + "</span><span>" + modelTag + "</span>";

        div.appendChild(nameRow);
        div.appendChild(metaDiv);

        div.addEventListener("click", () => {
          if (state.activeChatId !== c.id) {
            state.activeChatId = c.id;
            saveActiveIds();
            loadMessages();
          }
        });

        chatsListEl.appendChild(div);
      });
    }

    function renderMessages(messages) {
      messagesEl.innerHTML = "";
      (messages || []).forEach((m) => {
        const role = (m.role || "user").toLowerCase();
        const row = document.createElement("div");
        row.className = "msg-row " + (role === "assistant" ? "assistant" : "user");

        const bubble = document.createElement("div");
        bubble.className = "msg-bubble " + (role === "assistant" ? "assistant" : "user");

        const rawText = m.text || "";
        let mainText = rawText;

        if (rawText.startsWith("__IMG__")) {
          const newlineIdx = rawText.indexOf("\\n");
          const header = newlineIdx === -1 ? rawText : rawText.slice(0, newlineIdx);
          const body = newlineIdx === -1 ? "" : rawText.slice(newlineIdx + 1);

          const meta = header.substring("__IMG__".length); // mime|b64
          const parts = meta.split("|", 2);
          if (parts.length === 2) {
            const mime = parts[0] || "image/png";
            const b64 = parts[1] || "";
            const img = document.createElement("img");
            img.className = "chat-thumb";
            img.src = "data:" + mime + ";base64," + b64;
            bubble.appendChild(img);
          }

          if (body) {
            const captionDiv = document.createElement("div");
            captionDiv.textContent = body;
            bubble.appendChild(captionDiv);
          }

          mainText = ""; // already rendered
        }

        if (mainText && !rawText.startsWith("__IMG__")) {
          const textDiv = document.createElement("div");
          textDiv.textContent = mainText;
          bubble.appendChild(textDiv);
        }

        const ts = document.createElement("div");
        ts.className = "msg-ts";
        ts.textContent = m.ts || "";
        bubble.appendChild(ts);

        row.appendChild(bubble);
        messagesEl.appendChild(row);
      });
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function updateHeader() {
      const prof = state.profiles.find((p) => p.id === state.activeProfileId);
      const chat = state.chats.find((c) => c.id === state.activeChatId);

      activeProfileNameEl.textContent = "Profile: " + (prof ? (prof.display_name || prof.id) : "-");
      activeChatNameEl.textContent = "Chat: " + (chat ? (chat.display_name || chat.id) : "-");

      let label = "";
      if (chat && chat.model_override) {
        label = chat.model_override + " (chat override)";
      } else if (prof && prof.model_override) {
        label = prof.model_override + " (profile default)";
      } else if (state.defaultModel) {
        label = state.defaultModel + " (global default)";
      } else {
        label = "default";
      }
      modelLabelEl.textContent = label;

      const current = chat ? (chat.model_override || "") : "";
      modelSelectEl.value = current;
    }

    async function loadModels() {
      try {
        const data = await fetchJSON("/api/chat/models");
        state.defaultModel = data.default_model || null;
        state.models = data.available_models || [];

        modelSelectEl.innerHTML = "";
        const optDefault = document.createElement("option");
        optDefault.value = "";
        optDefault.textContent = state.defaultModel
          ? "Default (" + state.defaultModel + ")"
          : "Default (config)";
        modelSelectEl.appendChild(optDefault);

        state.models.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m;
          opt.textContent = m;
          modelSelectEl.appendChild(opt);
        });
      } catch (err) {
        console.error("Failed to load models", err);
      }
    }

    async function loadProfiles() {
      const data = await fetchJSON("/api/chat/profiles");
      state.profiles = data.profiles || [];

      if (!state.profiles.length) {
        const created = await fetchJSON("/api/chat/profiles", {
          method: "POST",
          body: JSON.stringify({}),
        });
        state.profiles = [created];
      }

      if (!state.activeProfileId || !state.profiles.find((p) => p.id === state.activeProfileId)) {
        state.activeProfileId = state.profiles[0].id;
      }

      renderProfiles();
    }

    async function loadChats() {
      if (!state.activeProfileId) return;
      const data = await fetchJSON("/api/chat/chats?profile_id=" + encodeURIComponent(state.activeProfileId));
      state.chats = data.chats || [];

      if (!state.chats.length) {
        const created = await fetchJSON("/api/chat/chats", {
          method: "POST",
          body: JSON.stringify({ profile_id: state.activeProfileId }),
        });
        state.chats = [created];
      }

      if (!state.activeChatId || !state.chats.find((c) => c.id === state.activeChatId)) {
        state.activeChatId = state.chats[0].id;
      }

      renderChats();
      updateHeader();
    }

    async function loadMessages() {
      if (!state.activeProfileId || !state.activeChatId) return;
      setStatus("Loading messages...");
      try {
        const data = await fetchJSON(
          "/api/chat/messages?profile_id=" +
            encodeURIComponent(state.activeProfileId) +
            "&chat_id=" +
            encodeURIComponent(state.activeChatId)
        );
        renderMessages(data.messages || []);
        updateHeader();
        setStatus("Ready");
      } catch (err) {
        console.error(err);
        setStatus("Failed to load messages");
      }
    }

    async function refresh() {
      try {
        saveActiveIds();
        await loadProfiles();
        await loadChats();
        await loadMessages();
      } catch (err) {
        console.error(err);
        setStatus("Error refreshing");
      }
    }

    function formatNowTs() {
      const d = new Date();
      return d.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      });
    }

    async function sendMessage() {
      const text = promptEl.value.trim();
      const hasText = !!text;
      const hasImage = !!pendingFile;

      if (!hasText && !hasImage) return;
      if (state.loading || !state.activeProfileId || !state.activeChatId) return;

      state.loading = true;
      sendBtn.disabled = true;

      const tsNow = formatNowTs();

      // optimistic user bubble (text-only or "[Image]" placeholder)
      const row = document.createElement("div");
      row.className = "msg-row user";
      const bubble = document.createElement("div");
      bubble.className = "msg-bubble user";
      const contentDiv = document.createElement("div");
      contentDiv.textContent = hasImage ? (text || "[Image]") : text;
      bubble.appendChild(contentDiv);
      const ts = document.createElement("div");
      ts.className = "msg-ts";
      ts.textContent = tsNow;
      bubble.appendChild(ts);
      row.appendChild(bubble);
      messagesEl.appendChild(row);
      messagesEl.scrollTop = messagesEl.scrollHeight;

      promptEl.value = "";
      promptEl.style.height = "32px";

      try {
        if (hasImage) {
          setStatus("Sending image to vision...");
          const formData = new FormData();
          formData.append("profile_id", state.activeProfileId);
          formData.append("chat_id", state.activeChatId);
          formData.append("prompt", text);
          formData.append("mode", "auto");
          formData.append("file", pendingFile);

          const resp = await fetch("/api/chat/vision", {
            method: "POST",
            body: formData,
          });
          if (!resp.ok) {
            const errText = await resp.text();
            throw new Error("Vision error: " + errText);
          }
          const data = await resp.json();
          state.activeProfileId = data.profile_id;
          state.activeChatId = data.chat_id;
          pendingFile = null;
          imageInput.value = "";
        } else {
          setStatus("Sending...");
          const payload = {
            prompt: text,
            profile_id: state.activeProfileId,
            chat_id: state.activeChatId,
          };
          const data = await fetchJSON("/api/chat", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          state.activeProfileId = data.profile_id;
          state.activeChatId = data.chat_id;
        }

        saveActiveIds();
        await loadChats();
        await loadMessages();
        setStatus("Ready");
      } catch (err) {
        console.error(err);
        setStatus("Error sending");
        const row = document.createElement("div");
        row.className = "msg-row assistant";
        const bubble = document.createElement("div");
        bubble.className = "msg-bubble assistant";
        bubble.textContent = "(Error: " + (err.message || "send failed") + ")";
        const ts = document.createElement("div");
        ts.className = "msg-ts";
        ts.textContent = tsNow;
        bubble.appendChild(ts);
        row.appendChild(bubble);
        messagesEl.appendChild(row);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      } finally {
        state.loading = false;
        sendBtn.disabled = false;
        promptEl.focus();
      }
    }

    // Event wiring
    sendBtn.addEventListener("click", (e) => {
      e.preventDefault();
      sendMessage();
    });

    promptEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    attachBtn.addEventListener("click", () => {
      imageInput.click();
    });

    imageInput.addEventListener("change", () => {
      const file = imageInput.files && imageInput.files[0];
      pendingFile = file || null;
      if (pendingFile) {
        setStatus("Image attached: " + pendingFile.name);
      } else {
        setStatus("Ready");
      }
    });

    // Profile buttons
    addProfileBtn.addEventListener("click", async () => {
      const name = prompt("Profile name (optional):", "");
      try {
        const created = await fetchJSON("/api/chat/profiles", {
          method: "POST",
          body: JSON.stringify({ display_name: name || null }),
        });
        state.activeProfileId = created.id;
        state.activeChatId = null;
        await refresh();
      } catch (err) {
        console.error(err);
        alert("Failed to create profile");
      }
    });

    renameProfileBtn.addEventListener("click", async () => {
      if (!state.activeProfileId) return;
      const prof = state.profiles.find((p) => p.id === state.activeProfileId);
      const currentName = prof ? (prof.display_name || prof.id) : "";
      const name = prompt("New profile name:", currentName);
      if (name === null) return;
      try {
        await fetchJSON("/api/chat/profiles/" + encodeURIComponent(state.activeProfileId), {
          method: "PATCH",
          body: JSON.stringify({ display_name: name }),
        });
        await refresh();
      } catch (err) {
        console.error(err);
        alert("Failed to rename profile");
      }
    });

    deleteProfileBtn.addEventListener("click", async () => {
      if (!state.activeProfileId) return;
      if (!confirm("Delete this profile and all its chats?")) return;
      try {
        await fetchJSON("/api/chat/profiles/" + encodeURIComponent(state.activeProfileId), {
          method: "DELETE",
        });
        state.activeProfileId = null;
        state.activeChatId = null;
        await refresh();
      } catch (err) {
        console.error(err);
        alert("Failed to delete profile");
      }
    });

    // Chat buttons
    addChatBtn.addEventListener("click", async () => {
      if (!state.activeProfileId) return;
      const name = prompt("Chat name (optional):", "");
      try {
        const created = await fetchJSON("/api/chat/chats", {
          method: "POST",
          body: JSON.stringify({
            profile_id: state.activeProfileId,
            display_name: name || null,
          }),
        });
        state.activeChatId = created.id;
        saveActiveIds();
        await refresh();
      } catch (err) {
        console.error(err);
        alert("Failed to create chat");
      }
    });

    renameChatBtn.addEventListener("click", async () => {
      if (!state.activeProfileId || !state.activeChatId) return;
      const chat = state.chats.find((c) => c.id === state.activeChatId);
      const currentName = chat ? (chat.display_name || chat.id) : "";
      const name = prompt("New chat name:", currentName);
      if (name === null) return;
      try {
        await fetchJSON(
          "/api/chat/chats/" +
            encodeURIComponent(state.activeProfileId) +
            "/" +
            encodeURIComponent(state.activeChatId),
          {
            method: "PATCH",
            body: JSON.stringify({ display_name: name }),
          }
        );
        await refresh();
      } catch (err) {
        console.error(err);
        alert("Failed to rename chat");
      }
    });

    deleteChatBtn.addEventListener("click", async () => {
      if (!state.activeProfileId || !state.activeChatId) return;
      if (!confirm("Delete this chat?")) return;
      try {
        await fetchJSON(
          "/api/chat/chats/" +
            encodeURIComponent(state.activeProfileId) +
            "/" +
            encodeURIComponent(state.activeChatId),
          {
            method: "DELETE",
          }
        );
        state.activeChatId = null;
        saveActiveIds();
        await refresh();
      } catch (err) {
        console.error(err);
        alert("Failed to delete chat");
      }
    });

    // Model select
    modelSelectEl.addEventListener("change", async () => {
      if (!state.activeProfileId || !state.activeChatId) return;
      const override = modelSelectEl.value || null;
      try {
        await fetchJSON(
          "/api/chat/chats/" +
            encodeURIComponent(state.activeProfileId) +
            "/" +
            encodeURIComponent(state.activeChatId),
          {
            method: "PATCH",
            body: JSON.stringify({ model_override: override }),
          }
        );
        await loadChats();
        updateHeader();
      } catch (err) {
        console.error(err);
        alert("Failed to update model override");
      }
    });

    // Summary overlay
    summaryBtn.addEventListener("click", async () => {
      if (!state.activeProfileId) return;
      summaryBtn.disabled = true;
      summaryBtn.textContent = "Summarizing...";
      setStatus("Summarizing profile...");

      try {
        const data = await fetchJSON("/api/chat/profile_summary", {
          method: "POST",
          body: JSON.stringify({ profile_id: state.activeProfileId }),
        });
        summaryProfileLabelEl.textContent =
          state.activeProfileId + (data.profile_name ? " · " + data.profile_name : "");
        summaryBodyEl.textContent = data.summary || "(No summary returned)";
        summaryOverlay.style.display = "flex";
        setStatus("Ready");
      } catch (err) {
        console.error(err);
        alert("Failed to summarize profile");
        setStatus("Summary failed");
      } finally {
        summaryBtn.disabled = false;
        summaryBtn.textContent = "Summarize Profile";
      }
    });

    summaryCloseBtn.addEventListener("click", () => {
      summaryOverlay.style.display = "none";
    });
    summaryOverlay.addEventListener("click", (e) => {
      if (e.target === summaryOverlay) {
        summaryOverlay.style.display = "none";
      }
    });

    // Init
    window.addEventListener("load", async () => {
      restoreActiveIds();
      await loadModels();
      await refresh();
      promptEl.focus();
    });
  </script>
</body>
</html>
'''
    return HTMLResponse(content=html)

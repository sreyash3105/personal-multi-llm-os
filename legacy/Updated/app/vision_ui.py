from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/vision", response_class=HTMLResponse)
def vision_page():
    """
    Minimal local Vision UI (frontend only).
    The backend logic is implemented in /api/vision.
    """
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Local Vision Assistant</title>
  <style>
    :root { color-scheme: dark; }
    body {
      margin: 0; padding: 0;
      background: radial-gradient(circle at top left, #020617 0, #020617 40%, #020617 100%);
      color: #e5e7eb; font-family: system-ui, -apple-system, BlinkMacSystemFont;
    }
    header {
      padding: 12px 16px; border-bottom: 1px solid #111827;
      display: flex; align-items: center; gap: 8px;
    }
    .avatar {
      width: 26px; height: 26px; border-radius: 999px;
      background: radial-gradient(circle at 30% 0, #22c55e, #0f172a);
      display: flex; align-items: center; justify-content: center;
      font-size: 14px;
    }
    .title-block { display: flex; flex-direction: column; gap: 2px; }
    .title { font-size: 14px; font-weight: 500; }
    .subtitle { font-size: 11px; color: #9ca3af; }

    main {
      padding: 12px 14px;
      display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
      gap: 10px;
    }
    @media(max-width: 900px) { main { grid-template-columns: minmax(0,1fr); } }

    .card {
      border-radius: 14px; border: 1px solid #111827;
      background: radial-gradient(circle at top left, rgba(15,23,42,0.8) 0, #020617 55%);
      padding: 10px 12px;
    }
    .card h2 {
      margin: 0 0 6px; font-size: 13px; text-transform: uppercase;
      letter-spacing: .12em; color: #9ca3af;
    }
    label {
      font-size: 11px; color: #9ca3af; display: block; margin-bottom: 3px;
    }
    input[type="file"] { font-size: 11px; color: #e5e7eb; }
    textarea {
      width: 100%; min-height: 70px; max-height: 180px; resize: vertical;
      border-radius: 10px; border: 1px solid #1f2937;
      background: #020617; color: #e5e7eb; font-size: 12px;
      padding: 6px 8px; outline: none;
    }
    textarea:focus { border-color: rgba(59,130,246,.8); box-shadow: 0 0 0 1px rgba(59,130,246,.5); }
    select {
      width: 100%; border-radius: 999px; border: 1px solid #1f2937;
      background: #020617; color: #e5e7eb; font-size: 11px;
      padding: 4px 8px; outline: none;
    }
    button {
      margin-top: 8px; border: none; border-radius: 999px;
      padding: 6px 16px; font-size: 13px; font-weight: 500; cursor: pointer;
      background: linear-gradient(135deg, #22c55e, #16a34a); color: #020617;
      transition: transform .08s, box-shadow .08s, filter .08s;
    }
    button:disabled { opacity: .5; cursor: default; }
    button:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,.7); }
    .status { font-size: 11px; color: #9ca3af; margin-top: 4px; }

    .preview {
      margin-top: 6px; border-radius: 10px; overflow: hidden;
      border: 1px solid #1f2937; max-height: 260px;
      display: none; align-items: center; justify-content: center;
      background: #020617;
    }
    .preview img { max-width: 100%; max-height: 260px; display: block; }

    .output-area {
      margin-top: 4px; font-size: 12px; line-height: 1.5;
      white-space: pre-wrap; word-wrap: break-word;
    }
  </style>
</head>
<body>
  <header>
    <div class="avatar">👁</div>
    <div class="title-block">
      <div class="title">Local Vision Assistant</div>
      <div class="subtitle">Screenshots · OCR · UI · Debug · Offline</div>
    </div>
  </header>

  <main>
    <div class="card">
      <h2>Input</h2>
      <form id="vision-form">
        <label>Image file</label>
        <input type="file" id="file-input" accept="image/*" required />

        <label style="margin-top:8px;">Prompt (optional)</label>
        <textarea id="prompt" placeholder="Describe / ask a question about the screenshot..."></textarea>

        <label style="margin-top:8px;">Mode</label>
        <select id="mode">
          <option value="auto">Auto</option>
          <option value="describe">Describe</option>
          <option value="ocr">OCR (extract text)</option>
          <option value="code">Developer View</option>
          <option value="debug">Debug Errors</option>
        </select>

        <button type="submit" id="submit-btn">Run Vision</button>
        <div class="status" id="status">Ready</div>
      </form>
      <div class="preview" id="preview">
        <img id="preview-img" src="" alt="Preview" />
      </div>
    </div>

    <div class="card">
      <h2>Output</h2>
      <div class="output-area" id="output">(Results appear here)</div>
    </div>
  </main>

  <script>
    const fileInput = document.getElementById("file-input");
    const formEl = document.getElementById("vision-form");
    const promptEl = document.getElementById("prompt");
    const modeEl = document.getElementById("mode");
    const statusEl = document.getElementById("status");
    const outputEl = document.getElementById("output");
    const preview = document.getElementById("preview");
    const previewImg = document.getElementById("preview-img");
    const submitBtn = document.getElementById("submit-btn");

    fileInput.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (!file) { preview.style.display = "none"; return; }
      const reader = new FileReader();
      reader.onload = e => {
        previewImg.src = e.target.result;
        preview.style.display = "flex";
      };
      reader.readAsDataURL(file);
    });

    formEl.addEventListener("submit", async e => {
      e.preventDefault();
      const file = fileInput.files?.[0];
      if (!file) return alert("Choose an image first");

      const formData = new FormData();
      formData.append("file", file);
      formData.append("prompt", promptEl.value || "");
      formData.append("mode", modeEl.value || "auto");

      submitBtn.disabled = true;
      statusEl.textContent = "Processing...";
      outputEl.textContent = "";

      try {
        const resp = await fetch("/api/vision", { method: "POST", body: formData });
        const data = resp.ok ? await resp.json() : { output: "(Request failed)" };
        outputEl.textContent = data.output || "(Empty response)";
        statusEl.textContent = "Done";
      } catch {
        statusEl.textContent = "Error";
        outputEl.textContent = "(Network error)";
      } finally {
        submitBtn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""
    return HTMLResponse(html)

from fastapi import FastAPI
from pydantic import BaseModel
import requests

# ---- CONFIG ----
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:7b"
# ----------------

app = FastAPI(title="Local Code Assistant")


class CodeRequest(BaseModel):
    prompt: str


class CodeResponse(BaseModel):
    output: str


def call_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    # Ollama /api/generate returns { "response": "...", ... }
    return data.get("response", "").strip()


@app.post("/api/code", response_model=CodeResponse)
def generate_code(req: CodeRequest):
    prompt = req.prompt.strip()
    if not prompt:
        return CodeResponse(output="(Empty prompt)")
    output = call_ollama(prompt)
    return CodeResponse(output=output)

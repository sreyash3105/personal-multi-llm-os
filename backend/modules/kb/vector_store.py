"""
vector_store.py

The "Librarian" module.
Handles semantic vector embeddings using 'nomic-embed-text'.

Features:
- Generates embeddings via Ollama API.
- Computes Cosine Similarity to find relevant memories.
- Safe fallback if the model is missing.
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import List, Dict, Any, Optional

import requests
import numpy as np

from backend.core.config import OLLAMA_URL, OLLAMA_REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# The specific model we want to use for embeddings
EMBEDDING_MODEL = "nomic-embed-text:latest"

def get_embedding(text: str) -> Optional[List[float]]:
    """
    Call Ollama to get the vector representation of text.
    Returns a list of floats (e.g., 768 dimensions), or None on failure.
    """
    text = (text or "").strip()
    if not text:
        return None

    url = f"{OLLAMA_URL}/api/embeddings"
    payload = {
        "model": EMBEDDING_MODEL,
        "prompt": text,
    }

    try:
        resp = requests.post(url, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        return data.get("embedding")
    except Exception as e:
        logger.warning(f"Vector embedding failed for model '{EMBEDDING_MODEL}': {e}")
        return None

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    Returns 0.0 to 1.0 (1.0 = identical meaning).
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    
    # Use numpy for speed if available, else manual
    try:
        a = np.array(v1)
        b = np.array(v2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    except Exception:
        # Fallback manual calculation
        dot_product = sum(a*b for a,b in zip(v1, v2))
        norm_a = math.sqrt(sum(a*a for a in v1))
        norm_b = math.sqrt(sum(b*b for b in v2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
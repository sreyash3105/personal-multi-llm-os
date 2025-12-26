"""
Per-profile knowledge base (SQLite + Vector Search).

UPGRADES:
- Now stores 'embedding_json' for every snippet.
- 'search_snippets' performs Hybrid Search (Keyword + Semantic Vector).
- Uses 'vector_store.py' to drive the 'nomic-embed-text' model.
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# DB file lives under the project root data/ folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "profile_kb.sqlite3"
logger = logging.getLogger(__name__)

from backend.core.feature_registry import register_feature

# Safe import of vector store with capability detection
try:
    from backend.modules.kb.vector_store import get_embedding, cosine_similarity
    register_feature(
        "vector_store",
        True,
        "Semantic vector search for knowledge base",
        install_hint="pip install requests numpy",
        fallback_behavior="keyword-only search"
    )
except ImportError as e:
    register_feature(
        "vector_store",
        False,
        "Semantic vector search for knowledge base",
        install_hint="pip install requests numpy",
        fallback_behavior="keyword-only search"
    )
    # Provide fallback implementations
    def get_embedding(text: str):
        logger.debug("get_embedding called but vector_store unavailable")
        return None

    def cosine_similarity(a, b):
        logger.debug("cosine_similarity called but vector_store unavailable")
        return 0.0

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError:
        pass
    return conn

def _init_db() -> None:
    with _get_conn() as conn:
        # V1 Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_snippets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id TEXT NOT NULL,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        # V2 Upgrade: Add embedding column if missing
        try:
            conn.execute("ALTER TABLE profile_snippets ADD COLUMN embedding_json TEXT")
        except sqlite3.OperationalError:
            pass # Column likely exists
        conn.commit()

# Initialize schema at import time
_init_db()

def add_snippet(profile_id: str, title: str, content: str) -> int:
    """
    Create a new snippet and generate its vector embedding.
    """
    profile_id = (profile_id or "").strip()
    title = (title or "").strip()
    content = (content or "").strip()

    if not profile_id or not title or not content:
        return 0

    # 🧠 Generate Embedding
    full_text = f"{title}\n{content}"
    vector = get_embedding(full_text)
    vector_json = json.dumps(vector) if vector else None

    now = datetime.now().isoformat(timespec="seconds")
    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO profile_snippets (profile_id, title, content, created_at, updated_at, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (profile_id, title, content, now, now, vector_json),
        )
        conn.commit()
        return int(cur.lastrowid)

def update_snippet(snippet_id: int, new_content: str) -> bool:
    new_content = (new_content or "").strip()
    if not new_content:
        return False

    # Fetch existing title to re-embed
    current = get_snippet(snippet_id)
    title = current['title'] if current else ""
    
    # 🧠 Re-generate Embedding
    vector = get_embedding(f"{title}\n{new_content}")
    vector_json = json.dumps(vector) if vector else None

    now = datetime.now().isoformat(timespec="seconds")
    with _get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE profile_snippets
            SET content = ?, updated_at = ?, embedding_json = ?
            WHERE id = ?
            """,
            (new_content, now, vector_json, snippet_id),
        )
        conn.commit()
        return cur.rowcount > 0

def delete_snippet(snippet_id: int) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM profile_snippets WHERE id = ?", (int(snippet_id),))
        conn.commit()
        return cur.rowcount > 0

def list_snippets(profile_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    profile_id = (profile_id or "").strip()
    if not profile_id: return []

    with _get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, profile_id, title, content, created_at, updated_at
            FROM profile_snippets
            WHERE profile_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (profile_id, int(limit)),
        )
        rows = cur.fetchall()

    return [dict(r) for r in rows]

def search_snippets(profile_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    HYBRID SEARCH:
    1. Generates embedding for the query.
    2. Scans all snippets for this profile (in-memory cosine similarity).
    3. Returns top matches.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id: return []
    query = (query or "").strip().lower()
    if not query: return list_snippets(profile_id, limit)

    # 1. Get Query Vector
    query_vec = get_embedding(query)
    
    # 2. Fetch all candidates
    with _get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM profile_snippets WHERE profile_id = ?", 
            (profile_id,)
        )
        rows = cur.fetchall()

    if not rows:
        return []

    scored_results = []

    for r in rows:
        score = 0.0
        
        # A. Keyword Boost (Simple exact match)
        row_text = (r["title"] + " " + r["content"]).lower()
        if query in row_text:
            score += 0.3  # Boost for exact keyword hit
            
        # B. Vector Score (Semantic match)
        if query_vec and r["embedding_json"]:
            try:
                doc_vec = json.loads(r["embedding_json"])
                sim = cosine_similarity(query_vec, doc_vec)
                score += sim
            except Exception:
                pass
        
        if score > 0.0:
            item = dict(r)
            item["score"] = score
            scored_results.append(item)

    # Sort by score descending
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    return scored_results[:limit]

def get_snippet(snippet_id: int) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.execute("SELECT * FROM profile_snippets WHERE id = ?", (int(snippet_id),))
        row = cur.fetchone()
    return dict(row) if row else None

def build_profile_context(profile_id: str, query: str, max_snippets: int = 5) -> str:
    """
    Context builder that uses the new Semantic Search.
    """
    if not query:
        snippets = list_snippets(profile_id, limit=max_snippets)
    else:
        snippets = search_snippets(profile_id, query, limit=max_snippets)

    if not snippets:
        return ""

    blocks = []
    for s in snippets:
        blocks.append(f"[KB MEMORY: {s['title']}]\n{s['content'].strip()}")

    return "\n\n".join(blocks)

# Preview helper
def build_profile_preview(profile_id: str, limit: int = 20) -> Dict[str, Any]:
    items = list_snippets(profile_id, limit)
    return {
        "profile_id": profile_id,
        "total": len(items),
        "snippets": [
            {
                "id": x["id"],
                "title": x["title"],
                "preview": x["content"][:100] + "...",
                "created_at": x["created_at"]
            } for x in items
        ]
    }
# backend/modules/telemetry/dashboard.py
"""
Advanced Dashboard.
Visualizes the full AI Chain of Thought: Planner -> Worker -> Risk.
"""
from __future__ import annotations
from fastapi import APIRouter
from html import escape
import json
from typing import Any

from backend.modules.telemetry.history import load_recent_records, DB_PATH

try:
    from backend.modules.security.security_sessions import get_active_sessions_for_profile
except ImportError:
    def get_active_sessions_for_profile(*args, **kwargs): return []

def _safe(val: Any) -> str:
    if isinstance(val, (dict, list)):
        return escape(json.dumps(val, indent=2, ensure_ascii=False))
    return escape(str(val)) if val is not None else ""

def _shorten(text: Any, limit: int = 80) -> str:
    s = str(text or "")
    return s if len(s) <= limit else s[:limit-3] + "..."

def render_dashboard(limit: int = 50) -> str:
    records = load_recent_records(limit=limit)
    
    rows_html = ""
    for idx, rec in enumerate(records):
        ts = rec.get("ts", "")
        mode = rec.get("mode", "unknown")
        original = rec.get("original_prompt", "")
        
        # Extract Trace Data
        trace = rec.get("trace", {})
        
        # 1. Planner Data
        planner = trace.get("planner", {})
        plan_title = planner.get("title", "No Plan")
        confidence = planner.get("confidence", 0)
        
        # 2. Worker/Execution Data
        worker_results = trace.get("worker", [])
        result_count = len(worker_results) if isinstance(worker_results, list) else 0
        
        # 3. Risk Data
        risk = trace.get("risk_assessment", {}) or rec.get("risk", {})
        risk_lvl = risk.get("risk_level", 1.0)
        risk_color = "#4ade80" # green
        if risk_lvl >= 3: risk_color = "#facc15" # yellow
        if risk_lvl >= 5: risk_color = "#f87171" # red
        
        # Summary Row
        rows_html += f"""
        <tr class="summary-row" onclick="toggleDetails(this)">
            <td><span class="ts">{ts[11:19]}</span></td>
            <td><span class="badge mode-{mode}">{mode}</span></td>
            <td>{_shorten(original)}</td>
            <td>{_shorten(plan_title, 30)}</td>
            <td style="color: {risk_color}; font-weight:bold;">{risk_lvl}</td>
        </tr>
        <tr class="detail-row">
            <td colspan="5">
                <div class="chain-container">
                    <div class="node">
                        <div class="node-title">🧠 Planner</div>
                        <div class="node-content">
                            <strong>Title:</strong> {plan_title}<br>
                            <strong>Conf:</strong> {confidence}<br>
                            <details><summary>Raw Plan</summary><pre>{_safe(planner)}</pre></details>
                        </div>
                    </div>
                    
                    <div class="arrow">➔</div>

                    <div class="node">
                        <div class="node-title">🛠️ Worker</div>
                        <div class="node-content">
                            <strong>Steps executed:</strong> {result_count}<br>
                            <details><summary>Results</summary><pre>{_safe(worker_results)}</pre></details>
                        </div>
                    </div>

                    <div class="arrow">➔</div>

                    <div class="node">
                        <div class="node-title">🛡️ Risk Assessment</div>
                        <div class="node-content">
                            <strong>Level:</strong> {risk_lvl}<br>
                            <strong>Tags:</strong> {_safe(risk.get('tags', []))}<br>
                            <strong>Reason:</strong> {risk.get('reasons', 'None')}
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 15px; border-top: 1px solid #333; padding-top: 10px;">
                    <strong>Full Prompt:</strong><br>
                    <pre style="background: #000; color: #ccc;">{_safe(original)}</pre>
                </div>
            </td>
        </tr>
        """

    return HTML_TEMPLATE.format(
        db_path=_safe(DB_PATH),
        count=len(records),
        rows=rows_html
    )

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <title>AI OS Black Box</title>
    <style>
        body { background: #0f172a; color: #cbd5e1; font-family: 'Segoe UI', monospace; padding: 20px; }
        h1 { color: #38bdf8; letter-spacing: 2px; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #1e293b; border-radius: 8px; overflow: hidden; }
        th { text-align: left; padding: 12px; background: #0f172a; color: #94a3b8; border-bottom: 2px solid #334155; }
        td { padding: 12px; border-bottom: 1px solid #334155; vertical-align: middle; }
        
        .summary-row:hover { background: #334155; cursor: pointer; }
        .ts { color: #64748b; font-size: 0.9em; }
        
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.8em; text-transform: uppercase; font-weight: bold; }
        .mode-automation { background: #6366f1; color: white; }
        .mode-chat { background: #10b981; color: white; }
        .mode-error { background: #ef4444; color: white; }
        
        .detail-row { display: none; background: #020617; }
        .chain-container { display: flex; align-items: stretch; gap: 10px; padding: 20px; }
        
        .node { flex: 1; background: #1e293b; border: 1px solid #475569; border-radius: 6px; padding: 0; display: flex; flex-direction: column; }
        .node-title { background: #334155; padding: 8px; font-weight: bold; border-bottom: 1px solid #475569; }
        .node-content { padding: 10px; font-size: 0.9em; overflow-y: auto; max-height: 200px; }
        
        .arrow { display: flex; align-items: center; color: #64748b; font-size: 1.5em; }
        
        pre { white-space: pre-wrap; word-wrap: break-word; font-size: 0.85em; color: #93c5fd; }
        details { cursor: pointer; color: #38bdf8; margin-top: 5px; }
    </style>
    <script>
        function toggleDetails(row) {
            let next = row.nextElementSibling;
            next.style.display = next.style.display === 'table-row' ? 'none' : 'table-row';
        }
    </script>
</head>
<body>
    <h1>SYSTEM BLACK BOX</h1>
    <div style="color: #64748b;">Database: {db_path} | Records: {count}</div>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Mode</th>
                <th>Prompt</th>
                <th>Plan</th>
                <th>Risk</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
</body>
</html>
"""

security_router = APIRouter()
@security_router.get("/api/dashboard/security_sessions")
def get_sessions(profile_id: str):
    return get_active_sessions_for_profile(profile_id)
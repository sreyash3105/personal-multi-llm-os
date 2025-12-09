"""
dashboard.py

Simple HTML dashboard for inspecting recent history records.

- Used by /dashboard endpoint via code_server.render_dashboard()
- Reads records from history.load_recent_records(limit=N)
- Renders as a single static HTML page (no external assets)

V3.4.x additions:
- Shows model-used telemetry from the "models" field.
- Adds client-side filters:
    - by mode
    - by model (from chat_model_used + models dict)
    - free-text search over prompt/output/judge/risk

V3.5 additions (security phase, read-only):
- Surfaces tool-level security metadata (if present) from tool_record.security:
    - auth_level / auth_label / policy / tags
- Shows tool name for tool_execution records.
- Everything is read-only: this does NOT change how anything executes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple
from html import escape

from fastapi import APIRouter

from backend.modules.telemetry.history import load_recent_records
from backend.modules.security.security_sessions import get_active_sessions_for_profile


def _safe(val: Any) -> str:
    if val is None:
        return ""
    return escape(str(val))


def _shorten(text: Any, limit: int = 240) -> str:
    if text is None:
        return ""
    s = str(text)
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def _collect_mode_and_models(records: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    modes: Set[str] = set()
    models: Set[str] = set()

    for r in records:
        mode = r.get("mode")
        if mode:
            modes.add(str(mode))

        chat_model = r.get("chat_model_used")
        if chat_model:
            models.add(str(chat_model))

        m_dict = r.get("models") or {}
        if isinstance(m_dict, dict):
            for v in m_dict.values():
                if v:
                    models.add(str(v))

    mode_list = sorted(modes)
    model_list = sorted(models)
    return mode_list, model_list


def render_dashboard(limit: int = 50) -> str:
    records = load_recent_records(limit=limit)
    modes, models = _collect_mode_and_models(records)

    # Build <option> lists for filters
    mode_options_html = '<option value="">(all modes)</option>'
    for m in modes:
        mode_options_html += f'<option value="{escape(m)}">{escape(m)}</option>'

    model_options_html = '<option value="">(all models)</option>'
    for m in models:
        model_options_html += f'<option value="{escape(m)}">{escape(m)}</option>'

    # Build table rows
    rows_html_parts: List[str] = []

    for idx, rec in enumerate(records):
        ts = rec.get("ts") or rec.get("timestamp") or ""
        mode = rec.get("mode") or ""
        kind = rec.get("kind") or ""

        original = _shorten(rec.get("original_prompt"))
        final_output = _shorten(rec.get("final_output"))

        chat_profile_name = rec.get("chat_profile_name") or rec.get("profile_name") or ""
        chat_id = rec.get("chat_id") or ""
        chat_model_used = rec.get("chat_model_used") or ""

        judge = rec.get("judge") or {}
        risk = rec.get("risk") or {}

        # -------- Tool + security metadata (if present) --------
        tool_record = rec.get("tool_record") or {}
        tool_name = ""
        security = {}
        security_level = ""
        security_label = ""
        security_policy = ""
        security_tags = ""

        if isinstance(tool_record, dict):
            tool_name = tool_record.get("tool") or ""

            # If top-level risk is missing, fall back to tool_record.risk
            if not risk and isinstance(tool_record.get("risk"), dict):
                risk = tool_record.get("risk") or {}

            sec = tool_record.get("security") or {}
            if isinstance(sec, dict):
                security = sec
                security_level = sec.get("auth_level", "")
                security_label = sec.get("auth_label", "")
                security_policy = sec.get("policy", "")
                tags = sec.get("tags") or []
                if isinstance(tags, list):
                    security_tags = ", ".join(str(t) for t in tags)

        # For older tool_execution entries that didn't set "kind"
        if not kind and mode == "tool_execution":
            kind = "tool"

        # -------- Judge fields --------
        judge_conf = ""
        judge_conflict = ""
        judge_summary = ""
        if isinstance(judge, dict):
            judge_conf = judge.get("confidence_score", "")
            judge_conflict = judge.get("conflict_score", "")
            judge_summary = _shorten(judge.get("judgement_summary"))

        # -------- Risk fields --------
        risk_level = ""
        risk_tags = ""
        risk_reasons = ""
        if isinstance(risk, dict):
            risk_level = risk.get("risk_level", "")
            tags = risk.get("tags") or []
            if isinstance(tags, list):
                risk_tags = ", ".join(str(t) for t in tags)
            risk_reasons = _shorten(risk.get("reasons"))

        # Models dictionary
        models_dict = rec.get("models") or {}
        if isinstance(models_dict, dict):
            models_text = ", ".join(
                f"{k}:{v}" for k, v in models_dict.items() if v
            )
        else:
            models_text = ""

        # Data attributes for filtering
        data_mode = escape(str(mode))
        data_model = escape(str(chat_model_used))
        data_models = escape(models_text)

        # Security summary text (for quick scanning + search)
        if security_policy:
            sec_notes = security_policy
        elif security_tags:
            sec_notes = security_tags
        else:
            sec_notes = ""

        row_html = f"""
        <tr
          data-mode="{data_mode}"
          data-model="{data_model}"
          data-models="{data_models}"
        >
          <td>{_safe(ts)}</td>
          <td>{_safe(mode)}</td>
          <td>{_safe(kind)}</td>
          <td>{_safe(chat_profile_name)}</td>
          <td>{_safe(chat_id)}</td>
          <td>{_safe(chat_model_used)}</td>
          <td>{_safe(models_text)}</td>
          <td class="mono">{_safe(original)}</td>
          <td class="mono">{_safe(final_output)}</td>
          <td>{_safe(judge_conf)}</td>
          <td>{_safe(judge_conflict)}</td>
          <td class="mono">{_safe(judge_summary)}</td>
          <td>{_safe(risk_level)}</td>
          <td class="mono">{_safe(risk_tags)}</td>
          <td class="mono">{_safe(risk_reasons)}</td>
          <td>{_safe(tool_name)}</td>
          <td>{_safe(security_level)}</td>
          <td class="mono">{_safe(security_label)}</td>
          <td class="mono">{_safe(sec_notes)}</td>
        </tr>
        """
        rows_html_parts.append(row_html)

    rows_html = "\n".join(rows_html_parts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Local AI OS — Dashboard</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 0;
      background: #0b0c10;
      color: #f5f5f5;
    }}
    header {{
      padding: 16px 24px;
      border-bottom: 1px solid #20232a;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
    }}
    header h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }}
    header .meta {{
      font-size: 12px;
      opacity: 0.7;
      margin-left: auto;
    }}
    main {{
      padding: 12px 16px 24px 16px;
    }}
    .filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
      align-items: center;
    }}
    .filters label {{
      font-size: 12px;
      opacity: 0.85;
    }}
    select, input[type="text"] {{
      background: #11141c;
      border-radius: 6px;
      border: 1px solid #2b2f3a;
      color: #f5f5f5;
      padding: 4px 8px;
      font-size: 12px;
      min-width: 120px;
    }}
    input[type="text"] {{
      min-width: 220px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
      table-layout: fixed;
    }}
    th, td {{
      border-bottom: 1px solid #1c1f26;
      padding: 6px 8px;
      vertical-align: top;
    }}
    th {{
      text-align: left;
      background: #11141c;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    tbody tr:nth-child(even) {{
      background: #10131a;
    }}
    tbody tr:nth-child(odd) {{
      background: #0c0f15;
    }}
    tbody tr:hover {{
      background: #1b2230;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      white-space: pre-wrap;
      word-wrap: break-word;
    }}
    .pill {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 999px;
      border: 1px solid #333745;
      font-size: 10px;
      opacity: 0.85;
    }}
    .pill.mode {{
      background: #151b28;
    }}
    .pill.model {{
      background: #152820;
    }}
    .pill.risk-high {{
      background: #3b1a1a;
      border-color: #e57373;
    }}
    .pill.risk-medium {{
      background: #332a13;
      border-color: #ffb74d;
    }}
    .pill.risk-low {{
      background: #12261b;
      border-color: #81c784;
    }}
    .toolbar-note {{
      font-size: 11px;
      opacity: 0.7;
      margin-left: 4px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Local AI OS — Dashboard</h1>
    <div class="meta">
      Showing latest {len(records)} records · Limit = {limit}
    </div>
  </header>
  <main>
    <div class="filters">
      <label>
        Mode:
        <select id="modeFilter">
          {mode_options_html}
        </select>
      </label>
      <label>
        Model:
        <select id="modelFilter">
          {model_options_html}
        </select>
      </label>
      <label>
        Search:
        <input
          type="text"
          id="searchInput"
          placeholder="Search prompt, output, judge, risk, security..."
        />
      </label>
      <span class="toolbar-note">
        Filters are client-side only (no extra load on backend).
      </span>
    </div>
    <div style="overflow-x:auto; max-height: calc(100vh - 120px);">
      <table id="recordsTable">
        <thead>
          <tr>
            <th style="width:120px;">Timestamp</th>
            <th style="width:90px;">Mode</th>
            <th style="width:70px;">Kind</th>
            <th style="width:120px;">Profile</th>
            <th style="width:80px;">Chat ID</th>
            <th style="width:110px;">Chat Model</th>
            <th style="width:150px;">Models (telemetry)</th>
            <th style="width:260px;">Original Prompt</th>
            <th style="width:260px;">Final Output</th>
            <th style="width:60px;">Judge&nbsp;Conf</th>
            <th style="width:60px;">Judge&nbsp;Conflicts</th>
            <th style="width:220px;">Judge Summary</th>
            <th style="width:70px;">Risk Level</th>
            <th style="width:140px;">Risk Tags</th>
            <th style="width:220px;">Risk Reasons</th>
            <th style="width:120px;">Tool</th>
            <th style="width:80px;">Sec Level</th>
            <th style="width:140px;">Sec Label</th>
            <th style="width:220px;">Sec Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </main>

  <script>
    (function() {{
      const modeFilter = document.getElementById('modeFilter');
      const modelFilter = document.getElementById('modelFilter');
      const searchInput = document.getElementById('searchInput');
      const table = document.getElementById('recordsTable');
      const tbody = table.querySelector('tbody');

      function normalize(s) {{
        return (s || '').toString().toLowerCase();
      }}

      function applyFilters() {{
        const modeValue = modeFilter.value;
        const modelValue = modelFilter.value;
        const searchValue = normalize(searchInput.value);

        const rows = tbody.querySelectorAll('tr');
        rows.forEach(row => {{
          const rowMode = row.getAttribute('data-mode') || '';
          const rowModel = row.getAttribute('data-model') || '';
          const rowModels = row.getAttribute('data-models') || '';

          let visible = true;

          if (modeValue && rowMode !== modeValue) {{
            visible = false;
          }}

          if (visible && modelValue) {{
            if (rowModel !== modelValue && !rowModels.split(',').some(m => m.trim() === modelValue)) {{
              visible = false;
            }}
          }}

          if (visible && searchValue) {{
            const text = normalize(row.textContent);
            if (!text.includes(searchValue)) {{
              visible = false;
            }}
          }}

          row.style.display = visible ? '' : 'none';
        }});
      }}

      modeFilter.addEventListener('change', applyFilters);
      modelFilter.addEventListener('change', applyFilters);
      searchInput.addEventListener('input', applyFilters);
    }})();
  </script>
</body>
</html>
"""
    return html


# ==========================================
# SECURITY SESSIONS PANEL (V3.6)
# ==========================================
# Read-only endpoint — does not affect runtime or telemetry.

security_router = APIRouter()


@security_router.get("/api/dashboard/security_sessions")
def dashboard_security_sessions(profile_id: str, include_expired: bool = False):
    try:
        sessions = get_active_sessions_for_profile(
            profile_id,
            include_expired=bool(include_expired),
        )
        return {
            "ok": True,
            "sessions": sessions,
            "profile_id": profile_id,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "profile_id": profile_id,
        }


# Do NOT reference `app` here. Just expose the router.
# code_server.py will include: app.include_router(security_router)
__all__ = ["security_router", "render_dashboard"]

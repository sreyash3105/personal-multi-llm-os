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

V3.7 dashboard refresh:
- Compact summary row + expandable details per record (click row to expand).
- Summary columns:
    - timestamp
    - kind
    - mode
    - chat model (if any)
    - models (telemetry)
    - judge confidence (0.00–10.00)
    - judge conflict (0.00–10.00)
    - risk tags
    - risk level (1.00–6.00)
- All scores are treated as floats for display; existing data is preserved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple
from html import escape

from backend.modules.telemetry.history import load_recent_records


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


def _fmt_score(val: Any, *, default: str = "") -> str:
    """
    Format a numeric score as a float with 2 decimals.

    - For judge scores: expected 0.00–10.00
    - For risk_level: expected 1.00–6.00

    If conversion fails, falls back to string or default.
    """
    if val is None or val == "":
        return default
    try:
        f = float(val)
        return f"{f:.2f}"
    except Exception:
        # Preserve whatever came back from the pipeline
        return str(val)


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

    # Build rows (summary + expandable details)
    rows_html_parts: List[str] = []

    for idx, rec in enumerate(records):
        ts = rec.get("ts") or rec.get("timestamp") or ""
        mode = rec.get("mode") or ""
        kind = rec.get("kind") or ""

        original_full = rec.get("original_prompt")
        final_full = rec.get("final_output")

        # Short versions for any list / preview we might want later
        original_short = _shorten(original_full)
        final_short = _shorten(final_full)

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
                # Prefer explicit policy_name if present
                security_policy = sec.get("policy_name") or sec.get("policy") or ""
                tags = sec.get("tags") or []
                if isinstance(tags, list):
                    security_tags = ", ".join(str(t) for t in tags)

        # For older tool_execution entries that didn't set "kind"
        if not kind and mode == "tool_execution":
            kind = "tool"

        # -------- Judge fields (float semantics) --------
        judge_conf_raw = ""
        judge_conflict_raw = ""
        judge_summary = ""

        if isinstance(judge, dict):
            judge_conf_raw = judge.get("confidence_score", "")
            judge_conflict_raw = judge.get("conflict_score", "")
            judge_summary = _shorten(judge.get("judgement_summary"))

        judge_conf = _fmt_score(judge_conf_raw)
        judge_conflict = _fmt_score(judge_conflict_raw)

        # -------- Risk fields (float semantics, but 1.00–6.00 range) --------
        risk_level_raw = ""
        risk_tags = ""
        risk_reasons = ""
        if isinstance(risk, dict):
            risk_level_raw = risk.get("risk_level", "")
            tags = risk.get("tags") or []
            if isinstance(tags, list):
                risk_tags = ", ".join(str(t) for t in tags)
            risk_reasons = _shorten(risk.get("reasons"))

        risk_level = _fmt_score(risk_level_raw)

        # Models dictionary (telemetry)
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

        # Security summary for quick glance in expanded view
        if security_policy:
            sec_notes = security_policy
        elif security_tags:
            sec_notes = security_tags
        else:
            sec_notes = ""

        # Summary row (clickable)
        summary_row_html = f"""
        <tr
          class="summary-row"
          data-idx="{idx}"
          data-mode="{data_mode}"
          data-model="{data_model}"
          data-models="{data_models}"
        >
          <td>{_safe(ts)}</td>
          <td>{_safe(kind)}</td>
          <td>{_safe(mode)}</td>
          <td>{_safe(chat_model_used)}</td>
          <td>{_safe(models_text)}</td>
          <td>{_safe(judge_conf)}</td>
          <td>{_safe(judge_conflict)}</td>
          <td class="mono">{_safe(risk_tags)}</td>
          <td>{_safe(risk_level)}</td>
        </tr>
        """

        # Detail row (hidden by default, toggled via JS)
        detail_row_html = f"""
        <tr class="detail-row" data-idx="{idx}" style="display:none;">
          <td colspan="9">
            <div class="detail-container">
              <div class="detail-meta">
                <div><strong>Profile:</strong> {_safe(chat_profile_name) or "-"}</div>
                <div><strong>Chat ID:</strong> {_safe(chat_id) or "-"}</div>
              </div>

              <div class="detail-grid">
                <div class="detail-section">
                  <div class="detail-title">Original prompt</div>
                  <pre class="mono detail-pre">{_safe(original_full)}</pre>
                </div>
                <div class="detail-section">
                  <div class="detail-title">Final output</div>
                  <pre class="mono detail-pre">{_safe(final_full)}</pre>
                </div>
              </div>

              <div class="detail-grid">
                <div class="detail-section">
                  <div class="detail-title">Judge</div>
                  <div class="detail-kv"><span>Confidence:</span> <span>{_safe(judge_conf)}</span></div>
                  <div class="detail-kv"><span>Conflict:</span> <span>{_safe(judge_conflict)}</span></div>
                  <div class="detail-kv"><span>Summary:</span> <span>{_safe(judge_summary)}</span></div>
                </div>
                <div class="detail-section">
                  <div class="detail-title">Risk</div>
                  <div class="detail-kv"><span>Level:</span> <span>{_safe(risk_level)}</span></div>
                  <div class="detail-kv"><span>Tags:</span> <span>{_safe(risk_tags)}</span></div>
                  <div class="detail-kv"><span>Reasons:</span> <span>{_safe(risk_reasons)}</span></div>
                </div>
              </div>

              <div class="detail-grid">
                <div class="detail-section">
                  <div class="detail-title">Models (telemetry)</div>
                  <pre class="mono detail-pre">{_safe(models_text)}</pre>
                </div>
                <div class="detail-section">
                  <div class="detail-title">Tool / Security</div>
                  <div class="detail-kv"><span>Tool:</span> <span>{_safe(tool_name)}</span></div>
                  <div class="detail-kv"><span>Sec level:</span> <span>{_safe(security_level)}</span></div>
                  <div class="detail-kv"><span>Sec label:</span> <span>{_safe(security_label)}</span></div>
                  <div class="detail-kv"><span>Sec notes:</span> <span>{_safe(sec_notes)}</span></div>
                </div>
              </div>
            </div>
          </td>
        </tr>
        """

        rows_html_parts.append(summary_row_html)
        rows_html_parts.append(detail_row_html)

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
      background: #020617;
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
      background: #020617;
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
      background: #020617;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    tbody tr.summary-row:nth-child(4n+1),
    tbody tr.summary-row:nth-child(4n+3) {{
      background: #020617;
    }}
    tbody tr.summary-row:hover {{
      background: #0f172a;
      cursor: pointer;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      white-space: pre-wrap;
      word-wrap: break-word;
    }}
    .toolbar-note {{
      font-size: 11px;
      opacity: 0.7;
      margin-left: 4px;
    }}
    .detail-row td {{
      background: #020617;
      border-top: none;
      border-bottom: 1px solid #111827;
    }}
    .detail-container {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      font-size: 11px;
    }}
    .detail-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      opacity: 0.85;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 8px;
    }}
    @media (max-width: 900px) {{
      .detail-grid {{
        grid-template-columns: minmax(0, 1fr);
      }}
    }}
    .detail-section {{
      border-radius: 8px;
      border: 1px solid #1f2937;
      padding: 6px 8px;
      background: #020617;
    }}
    .detail-title {{
      font-size: 11px;
      font-weight: 600;
      margin-bottom: 4px;
      color: #e5e7eb;
    }}
    .detail-pre {{
      margin: 0;
      max-height: 220px;
      overflow-y: auto;
      font-size: 11px;
    }}
    .detail-kv {{
      display: flex;
      justify-content: space-between;
      gap: 6px;
      font-size: 10px;
      margin-bottom: 2px;
    }}
    .detail-kv span:first-child {{
      opacity: 0.75;
    }}
    .summary-row td:first-child::before {{
      content: "▸";
      display: inline-block;
      margin-right: 4px;
      opacity: 0.6;
      transition: transform 0.15s ease;
    }}
    .summary-row.expanded td:first-child::before {{
      transform: rotate(90deg);
      opacity: 0.9;
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
        Click a row to expand details. Filters are client-side only.
      </span>
    </div>
    <div style="overflow-x:auto; max-height: calc(100vh - 120px);">
      <table id="recordsTable">
        <thead>
          <tr>
            <th style="width:130px;">Timestamp</th>
            <th style="width:70px;">Kind</th>
            <th style="width:90px;">Mode</th>
            <th style="width:120px;">Chat Model</th>
            <th style="width:160px;">Models (telemetry)</th>
            <th style="width:80px;">Judge Conf</th>
            <th style="width:90px;">Judge Conflict</th>
            <th style="width:180px;">Risk Tags</th>
            <th style="width:70px;">Risk Level</th>
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

      function getSummaryRows() {{
        return Array.from(tbody.querySelectorAll('tr.summary-row'));
      }}

      function getDetailRowFor(summaryRow) {{
        const idx = summaryRow.getAttribute('data-idx');
        if (!idx) return null;
        return tbody.querySelector('tr.detail-row[data-idx="' + idx + '"]');
      }}

      function applyFilters() {{
        const modeValue = modeFilter.value;
        const modelValue = modelFilter.value;
        const searchValue = normalize(searchInput.value);

        const summaryRows = getSummaryRows();
        summaryRows.forEach(row => {{
          const rowMode = row.getAttribute('data-mode') || '';
          const rowModel = row.getAttribute('data-model') || '';
          const rowModels = row.getAttribute('data-models') || '';

          let visible = true;

          if (modeValue && rowMode !== modeValue) {{
            visible = false;
          }}

          if (visible && modelValue) {{
            const modelsList = rowModels.split(',').map(m => m.trim()).filter(Boolean);
            if (rowModel !== modelValue && !modelsList.includes(modelValue)) {{
              visible = false;
            }}
          }}

          if (visible && searchValue) {{
            const text = normalize(row.textContent);
            if (!text.includes(searchValue)) {{
              visible = false;
            }}
          }}

          const detailRow = getDetailRowFor(row);
          row.style.display = visible ? '' : 'none';
          if (detailRow) {{
            // Hide detail row if summary is hidden
            detailRow.style.display = (visible && row.classList.contains('expanded')) ? '' : 'none';
          }}
        }});
      }}

      function toggleRow(summaryRow) {{
        const detailRow = getDetailRowFor(summaryRow);
        if (!detailRow) return;
        const isExpanded = summaryRow.classList.contains('expanded');
        if (isExpanded) {{
          summaryRow.classList.remove('expanded');
          detailRow.style.display = 'none';
        }} else {{
          summaryRow.classList.add('expanded');
          detailRow.style.display = '';
        }}
      }}

      tbody.addEventListener('click', (e) => {{
        const tr = e.target.closest('tr.summary-row');
        if (!tr) return;
        toggleRow(tr);
      }});

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

from fastapi import APIRouter
from backend.modules.security.security_sessions import get_active_sessions_for_profile

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


__all__ = ["security_router", "render_dashboard"]
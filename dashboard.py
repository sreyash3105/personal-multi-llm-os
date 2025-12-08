from typing import Any, Dict, List
from html import escape

from fastapi.responses import HTMLResponse

from history import load_recent_records


def _score_label(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return str(int(value))
    except Exception:
        return escape(str(value))


def _escalation_label(escalated: bool, mode: str) -> str:
    mode = mode or ""
    if mode.startswith("study"):
        return "Study"
    if mode == "chat":
        return "Chat"
    if escalated:
        return "Yes"
    return "No"


def _truncate(text: str, limit: int = 120) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _build_rows_html(
    records: List[Dict[str, Any]],
    row_prefix: str,
    empty_message: str,
) -> str:
    rows_html: List[str] = []

    # newest first
    records = list(reversed(records))

    for idx, rec in enumerate(records):
        rec_id = f"{row_prefix}-{idx}"
        ts = escape(str(rec.get("ts", "")))
        mode = str(rec.get("mode", "") or "")
        mode_safe = escape(mode)

        prompt = rec.get("normalized_prompt") or rec.get("original_prompt") or ""
        final_output = rec.get("final_output") or ""
        coder_output = rec.get("coder_output") or ""
        reviewer_output = rec.get("reviewer_output") or ""
        escalated = bool(rec.get("escalated"))
        escalation_reason = rec.get("escalation_reason") or ""

        judge = rec.get("judge")
        if isinstance(judge, dict):
            confidence = judge.get("confidence_score")
            conflict = judge.get("conflict_score")
            raw_summary = judge.get("judgement_summary")
            j_raw = judge.get("raw_response")
            j_err = judge.get("parse_error")
        else:
            confidence = None
            conflict = None
            raw_summary = ""
            j_raw = ""
            j_err = ""

        # --- Risk info (top-level, for code/study/chat) ---
        risk = rec.get("risk") if isinstance(rec.get("risk"), dict) else None
        risk_level = risk.get("risk_level") if risk else None
        risk_tags = risk.get("tags") if risk else None
        risk_reasons = risk.get("reasons") if risk else None
        risk_kind = risk.get("kind") if risk else None

        # --- Tool risk (inside tool_record, e.g. mode == tool_execution) ---
        tool_record = rec.get("tool_record") if isinstance(rec.get("tool_record"), dict) else None
        tool_risk = tool_record.get("risk") if (tool_record and isinstance(tool_record.get("risk"), dict)) else None
        tool_risk_level = tool_risk.get("risk_level") if tool_risk else None
        tool_risk_tags = tool_risk.get("tags") if tool_risk else None
        tool_risk_reasons = tool_risk.get("reasons") if tool_risk else None
        tool_risk_kind = tool_risk.get("kind") if tool_risk else None

        # Force everything to safe strings
        prompt_str = str(prompt or "")
        final_str = str(final_output or "")
        coder_str = str(coder_output or "")
        reviewer_str = str(reviewer_output or "")
        j_summary = str(raw_summary or "")
        j_raw_str = str(j_raw or "")
        j_err_str = str(j_err or "")
        esc_reason_str = str(escalation_reason or "")

        prompt_preview = escape(_truncate(prompt_str.replace("\n", " "), 120))
        final_preview = escape(_truncate(final_str.replace("\n", " "), 120))
        j_summary_safe = escape(_truncate(j_summary.replace("\n", " "), 120))

        if mode.startswith("study") or mode == "chat":
            conf_label = "-"
            confct_label = "-"
        else:
            conf_label = _score_label(confidence)
            confct_label = _score_label(conflict)

        # Risk cell: prefer top-level risk; fallback to tool_risk; else "-"
        if risk_level is not None:
            risk_label = _score_label(risk_level)
        elif tool_risk_level is not None:
            risk_label = _score_label(tool_risk_level)
        else:
            risk_label = "-"

        esc_label = _escalation_label(escalated, mode)

        coder_escaped = escape(coder_str)
        reviewer_escaped = escape(reviewer_str)
        final_escaped = escape(final_str)
        j_raw_escaped = escape(j_raw_str)
        j_err_escaped = escape(j_err_str)
        esc_reason_escaped = escape(esc_reason_str)

        # --- Render risk as compact text blocks for details view ---
        if risk_level is not None or risk_tags or risk_reasons:
            risk_block = (
                f"risk_kind: {escape(str(risk_kind or 'code'))}\n"
                f"risk_level: {escape(str(risk_level))}\n"
                f"risk_tags: {escape(str(risk_tags))}\n"
                f"risk_reasons: {escape(str(risk_reasons or ''))}\n"
            )
        else:
            risk_block = "risk: (no risk info for this record)\n"

        if tool_risk_level is not None or tool_risk_tags or tool_risk_reasons:
            tool_risk_block = (
                f"tool_risk_kind: {escape(str(tool_risk_kind or 'tool'))}\n"
                f"tool_risk_level: {escape(str(tool_risk_level))}\n"
                f"tool_risk_tags: {escape(str(tool_risk_tags))}\n"
                f"tool_risk_reasons: {escape(str(tool_risk_reasons or ''))}\n"
            )
        else:
            tool_risk_block = ""

        row = f"""
<tr onclick="toggleDetails('{rec_id}')" class="main-row">
  <td>{ts}</td>
  <td>{mode_safe}</td>
  <td>{esc_label}</td>
  <td>{prompt_preview}</td>
  <td>{final_preview}</td>
  <td>{conf_label}</td>
  <td>{confct_label}</td>
  <td>{risk_label}</td>
  <td>{j_summary_safe}</td>
</tr>
<tr id="{rec_id}" class="details-row">
  <td colspan="9">
    <div class="details">
      <div class="block">
        <h3>Prompt</h3>
        <pre>{escape(prompt_str)}</pre>
      </div>
      <div class="block">
        <h3>Coder Output</h3>
        <pre>{coder_escaped}</pre>
      </div>
      <div class="block">
        <h3>Reviewer / Final Output</h3>
        <pre>{reviewer_escaped or final_escaped}</pre>
      </div>
      <div class="block">
        <h3>Judge / Study Meta</h3>
        <pre>mode: {mode_safe}
escalated: {str(escalated)}
escalation_reason: {esc_reason_escaped}

confidence_score: {escape(str(confidence))}
conflict_score: {escape(str(conflict))}
judgement_summary: {escape(j_summary)}

raw_response:
{j_raw_escaped}

parse_error:
{j_err_escaped}

{risk_block}{tool_risk_block}</pre>
      </div>
    </div>
  </td>
</tr>
"""
        rows_html.append(row)

    if not rows_html:
        return f"""
<tr>
  <td colspan="9" style="text-align:center; padding: 24px; color: #9ca3af;">
    {empty_message}
  </td>
</tr>
"""

    return "\n".join(rows_html)


def _build_timing_rows_html(
    records: List[Dict[str, Any]],
    row_prefix: str,
    empty_message: str,
) -> str:
    """
    Build rows for system performance timings (pipeline_timing, tool_timing).
    """
    rows_html: List[str] = []

    # newest first
    records = list(reversed(records))

    for idx, rec in enumerate(records):
        rec_id = f"{row_prefix}-{idx}"
        ts = escape(str(rec.get("ts", "")))
        kind = str(rec.get("kind", "") or "")
        status = str(rec.get("status", "") or "")
        duration = rec.get("duration_s")
        error = str(rec.get("error", "") or "")

        if kind == "pipeline_timing":
            stage = str(rec.get("stage", "") or "")
            target = str(rec.get("model", "") or "")
            type_label = stage or "pipeline"
        elif kind == "tool_timing":
            stage = "tool"
            target = str(rec.get("tool", "") or "")
            type_label = "tool"
        else:
            # Not a timing record we recognize; skip
            continue

        type_safe = escape(type_label)
        target_safe = escape(target)
        status_safe = escape(status or "-")
        duration_label = "-" if duration is None else f"{float(duration):.3f}"
        duration_safe = escape(duration_label)
        error_preview = escape(_truncate(error.replace("\n", " "), 100))
        error_full = escape(error)

        row = f"""
<tr onclick="toggleDetails('{rec_id}')" class="main-row">
  <td>{ts}</td>
  <td>{type_safe}</td>
  <td>{target_safe}</td>
  <td>{duration_safe}</td>
  <td>{status_safe}</td>
  <td>{error_preview}</td>
</tr>
<tr id="{rec_id}" class="details-row">
  <td colspan="6">
    <div class="details">
      <div class="block">
        <h3>Timing Record</h3>
        <pre>kind: {escape(kind)}
type: {type_safe}
target: {target_safe}
status: {status_safe}
duration_s: {duration_safe}

error:
{error_full}</pre>
      </div>
    </div>
  </td>
</tr>
"""
        rows_html.append(row)

    if not rows_html:
        return f"""
<tr>
  <td colspan="6" style="text-align:center; padding: 24px; color: #9ca3af;">
    {empty_message}
  </td>
</tr>
"""

    return "\n".join(rows_html)


def render_dashboard(limit: int = 50) -> HTMLResponse:
    """
    Build and return the dashboard HTML as an HTMLResponse.
    Main board: code + study.
    Chat board: only mode == "chat".
    Performance board: timing entries from pipeline/tools.
    """
    records = load_recent_records(limit=limit)

    main_records: List[Dict[str, Any]] = []
    chat_records: List[Dict[str, Any]] = []
    timing_records: List[Dict[str, Any]] = []

    for rec in records:
        kind = str(rec.get("kind", "") or "")
        if kind in ("pipeline_timing", "tool_timing"):
            timing_records.append(rec)
            continue

        mode = str(rec.get("mode", "") or "")
        if mode == "chat":
            chat_records.append(rec)
        else:
            main_records.append(rec)

    rows_main = _build_rows_html(
        main_records,
        row_prefix="main-rec",
        empty_message="No code / study history yet. Make a request via /api/code or /api/study and refresh this page.",
    )
    rows_chat = _build_rows_html(
        chat_records,
        row_prefix="chat-rec",
        empty_message="No chat history yet. Open /chat and send a message.",
    )
    rows_timing = _build_timing_rows_html(
        timing_records,
        row_prefix="timing-rec",
        empty_message="No performance timings yet. Trigger /api/code, /api/vision, or tools to see activity.",
    )

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Local AI Trace Dashboard</title>
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      margin: 0;
      padding: 0;
      background: radial-gradient(circle at top left, #020617 0, #020617 40%, #020617 100%);
      color: #e5e7eb;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 14px 22px;
      border-bottom: 1px solid #111827;
      background: linear-gradient(90deg, #020617, #020617 40%, #020617 100%);
    }}
    header h1 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #e5e7eb;
    }}
    header p {{
      margin: 4px 0 0;
      font-size: 11px;
      color: #9ca3af;
    }}
    main {{
      padding: 14px 20px 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .section-title {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: #9ca3af;
      margin-bottom: 6px;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: #9ca3af;
      margin-bottom: 8px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid #1f2937;
      background: #020617;
    }}
    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #22c55e;
      box-shadow: 0 0 0 3px rgba(34,197,94,0.25);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid #111827;
      background: #020617;
    }}
    thead {{
      background: #020617;
      position: sticky;
      top: 0;
      z-index: 5;
    }}
    thead th {{
      padding: 8px 10px;
      text-align: left;
      font-weight: 500;
      color: #9ca3af;
      border-bottom: 1px solid #111827;
      background: rgba(2,6,23,0.95);
      backdrop-filter: blur(4px);
    }}
    tbody tr.main-row {{
      cursor: pointer;
      transition: background 0.12s ease, transform 0.08s ease;
    }}
    tbody tr.main-row:nth-child(4n+1) {{
      background: rgba(15,23,42,0.62);
    }}
    tbody tr.main-row:nth-child(4n+3) {{
      background: rgba(15,23,42,0.45);
    }}
    tbody tr.main-row:hover {{
      background: rgba(37,99,235,0.55);
      transform: translateY(-1px);
    }}
    tbody td {{
      padding: 7px 9px;
      border-bottom: 1px solid #111827;
      vertical-align: top;
      max-width: 260px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    tr.details-row {{
      display: none;
      background: #020617;
    }}
    tr.details-row td {{
      padding: 10px 12px 12px;
      border-bottom: 1px solid #111827;
    }}
    .details {{
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.1fr);
      gap: 10px;
    }}
    @media (max-width: 960px) {{
      .details {{
        grid-template-columns: minmax(0, 1fr);
      }}
    }}
    .block {{
      border-radius: 10px;
      border: 1px solid #1f2937;
      background: radial-gradient(circle at top left, rgba(15,23,42,0.8) 0, #020617 55%);
      padding: 6px 8px 8px;
    }}
    .block h3 {{
      margin: 0 0 4px;
      font-size: 11px;
      font-weight: 500;
      color: #e5e7eb;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .block pre {{
      margin: 0;
      padding: 6px 8px;
      border-radius: 8px;
      border: 1px solid #0f172a;
      background: #020617;
      font-size: 11px;
      line-height: 1.4;
      white-space: pre-wrap;
      word-wrap: break-word;
      max-height: 260px;
      overflow: auto;
    }}
  </style>
</head>
<body>
  <header>
    <h1>LOCAL AI TRACE</h1>
    <p>PC brain &mdash; code &amp; study &mdash; LAN-only</p>
  </header>
  <main>
    <section>
      <div class="section-title">CODE / STUDY PIPELINE</div>
      <div class="meta">
        <div class="pill">
          <span class="dot"></span>
          <span>Server online &bull; showing last {len(main_records)} interactions</span>
        </div>
        <div>Click any row to expand full details</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Mode</th>
            <th>Esc / Type</th>
            <th>Prompt (preview)</th>
            <th>Final (preview)</th>
            <th>Conf</th>
            <th>Conflic</th>
            <th>Risk</th>
            <th>Judge summary</th>
          </tr>
        </thead>
        <tbody>
          {rows_main}
        </tbody>
      </table>
    </section>

    <section>
      <div class="section-title" style="margin-top: 10px;">CHAT HISTORY</div>
      <div class="meta" style="margin-bottom: 6px;">
        <div style="font-size: 11px; color: #9ca3af;">
          From /chat and /api/chat &bull; last {len(chat_records)} messages
        </div>
        <div style="font-size: 11px; color: #6b7280;">
          Chat entries are kept separate from code / study.
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Mode</th>
            <th>Type</th>
            <th>Prompt (preview)</th>
            <th>Final (preview)</th>
            <th>Conf</th>
            <th>Conflic</th>
            <th>Risk</th>
            <th>Judge summary</th>
          </tr>
        </thead>
        <tbody>
          {rows_chat}
        </tbody>
      </table>
    </section>

    <section>
      <div class="section-title" style="margin-top: 12px;">SYSTEM PERFORMANCE</div>
      <div class="meta" style="margin-bottom: 6px;">
        <div style="font-size: 11px; color: #9ca3af;">
          Timing from code, vision, and tools &bull; up to last {len(timing_records)} entries
        </div>
        <div style="font-size: 11px; color: #6b7280;">
          Use this to spot slow models, timeouts, or failing tools.
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Type</th>
            <th>Target</th>
            <th>Duration (s)</th>
            <th>Status</th>
            <th>Error (preview)</th>
          </tr>
        </thead>
        <tbody>
          {rows_timing}
        </tbody>
      </table>
    </section>
  </main>
  <script>
    function toggleDetails(id) {{
      var row = document.getElementById(id);
      if (!row) return;
      if (row.style.display === "table-row") {{
        row.style.display = "none";
      }} else {{
        row.style.display = "table-row";
      }}
    }}
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

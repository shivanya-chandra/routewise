from fastapi.responses import HTMLResponse


def dashboard_response() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RouteWise Operations</title>
  <style>
    :root { color-scheme: light; --ink: #17202a; --muted: #667085; --line: #d9dee7; --paper: #f5f7fa; --panel: #fff; --green: #147d64; --amber: #a15c00; --red: #b42318; }
    * { box-sizing: border-box; }
    body { margin: 0; min-width: 320px; background: var(--paper); color: var(--ink); font: 14px/1.45 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 0; }
    header { border-bottom: 1px solid var(--line); background: var(--panel); }
    .bar, main { width: min(1180px, calc(100% - 32px)); margin: 0 auto; }
    .bar { min-height: 64px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
    .brand { font-size: 20px; font-weight: 750; }
    .brand span { color: var(--muted); font-size: 13px; font-weight: 500; margin-left: 10px; }
    button { min-height: 36px; border: 1px solid #9aa4b2; border-radius: 6px; background: #fff; color: var(--ink); padding: 0 14px; font: inherit; font-weight: 650; cursor: pointer; }
    button:hover { border-color: var(--green); color: var(--green); }
    main { padding: 28px 0 48px; }
    .status { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin-bottom: 16px; }
    h1 { margin: 0; font-size: 26px; }
    h2 { margin: 0 0 12px; font-size: 16px; }
    .muted { color: var(--muted); }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 28px; }
    .metric { min-width: 0; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); padding: 16px; }
    .metric dt { color: var(--muted); font-size: 12px; }
    .metric dd { margin: 5px 0 0; font-size: 24px; font-weight: 740; overflow-wrap: anywhere; }
    section { margin-top: 28px; }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); }
    table { width: 100%; border-collapse: collapse; min-width: 720px; }
    th, td { padding: 11px 13px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; font-weight: 700; }
    tr:last-child td { border-bottom: 0; }
    .ok { color: var(--green); } .warning { color: var(--amber); } .error { color: var(--red); }
    .recommendations { display: grid; gap: 8px; }
    .recommendation { border-left: 3px solid var(--green); background: var(--panel); padding: 11px 14px; }
    .recommendation.warning { border-left-color: var(--amber); }
    #error { display: none; border-left: 3px solid var(--red); background: #fff; color: var(--red); padding: 12px 14px; margin-bottom: 16px; }
    @media (max-width: 800px) { .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .brand span { display: block; margin: 0; } }
    @media (max-width: 460px) { .bar, main { width: min(100% - 20px, 1180px); } .metrics { grid-template-columns: 1fr; } .status { align-items: flex-start; flex-direction: column; } }
  </style>
</head>
<body>
  <header><div class="bar"><div class="brand">RouteWise <span>Operations</span></div><button id="refresh" type="button">Refresh</button></div></header>
  <main>
    <div class="status"><div><h1>Routing overview</h1><div id="updated" class="muted">Loading current data...</div></div></div>
    <div id="error"></div>
    <dl class="metrics" id="metrics"></dl>
    <section><h2>Recommendations</h2><div class="recommendations" id="recommendations"></div></section>
    <section><h2>Model performance</h2><div class="table-wrap"><table><thead><tr><th>Model</th><th>Calls</th><th>Success</th><th>Tokens</th><th>Avg latency</th><th>Cost</th></tr></thead><tbody id="models"></tbody></table></div></section>
    <section><h2>Recent requests</h2><div class="table-wrap"><table><thead><tr><th>Time</th><th>Status</th><th>Route</th><th>Cache</th><th>Latency</th><th>Quality</th></tr></thead><tbody id="requests"></tbody></table></div></section>
  </main>
  <script>
    const text = value => value === null || value === undefined ? "-" : String(value);
    const percent = value => `${(Number(value || 0) * 100).toFixed(1)}%`;
    const metric = (label, value) => `<div class="metric"><dt>${label}</dt><dd>${value}</dd></div>`;
    const escapeHtml = value => text(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    async function load() {
      const error = document.querySelector('#error'); error.style.display = 'none';
      try {
        const response = await fetch('/metrics/report');
        if (!response.ok) throw new Error(`Report request failed (${response.status})`);
        const report = await response.json(), s = report.summary;
        document.querySelector('#updated').textContent = `Updated ${new Date(report.generated_at).toLocaleString()}`;
        document.querySelector('#metrics').innerHTML = [
          metric('Requests', s.total_requests), metric('Cache hit rate', percent(s.cache_hit_rate)),
          metric('Model success', `${s.successful_model_calls}/${s.successful_model_calls + s.failed_model_calls}`),
          metric('Estimated cost', `$${Number(s.estimated_cost_usd || 0).toFixed(6)}`),
          metric('Tokens', s.total_tokens), metric('Words saved', s.prompt_words_saved),
          metric('Avg request', s.average_request_latency_ms == null ? '-' : `${s.average_request_latency_ms} ms`),
          metric('Fallbacks', s.total_fallbacks)
        ].join('');
        document.querySelector('#recommendations').innerHTML = report.recommendations.map(item => `<div class="recommendation ${escapeHtml(item.severity)}">${escapeHtml(item.message)}</div>`).join('');
        document.querySelector('#models').innerHTML = report.models.map(item => `<tr><td>${escapeHtml(item.model)}</td><td>${item.total_calls}</td><td class="${item.success_rate >= .8 ? 'ok' : 'warning'}">${percent(item.success_rate)}</td><td>${item.total_tokens}</td><td>${text(item.average_latency_ms)} ms</td><td>$${Number(item.estimated_cost_usd || 0).toFixed(6)}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">No model calls recorded</td></tr>';
        document.querySelector('#requests').innerHTML = report.recent_requests.map(item => `<tr><td>${item.created_at ? new Date(item.created_at).toLocaleString() : '-'}</td><td>${escapeHtml(item.request_status)}</td><td>${escapeHtml(item.selected_model)} -&gt; ${escapeHtml(item.final_model)}</td><td>${item.semantic_cache_hit ? 'semantic' : item.cache_hit ? 'exact' : 'miss'}</td><td>${text(item.latency_ms)} ms</td><td>${escapeHtml(item.quality_label)}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">No requests recorded</td></tr>';
      } catch (cause) { error.textContent = cause.message; error.style.display = 'block'; }
    }
    document.querySelector('#refresh').addEventListener('click', load); load();
  </script>
</body>
</html>"""

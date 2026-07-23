from fastapi.responses import HTMLResponse


def playground_response() -> HTMLResponse:
    return HTMLResponse(PLAYGROUND_HTML)


PLAYGROUND_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RouteWise Playground</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17211d;
      --muted: #66736c;
      --line: #d8dedb;
      --paper: #f3f6f4;
      --panel: #ffffff;
      --green: #176b4d;
      --green-dark: #0f523a;
      --green-soft: #e8f3ed;
      --blue: #285f8f;
      --blue-soft: #eaf1f8;
      --amber: #8b5b12;
      --amber-soft: #fbf2df;
      --red: #b42318;
      --red-soft: #fff0ee;
      --shadow: 0 1px 2px rgba(18, 32, 24, 0.07);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background: var(--paper);
      color: var(--ink);
      font: 14px/1.5 ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    button, input, select, textarea { font: inherit; letter-spacing: 0; }
    button, select, input[type="number"], input[type="password"], input[type="text"], textarea {
      border: 1px solid #aeb8b2;
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
    }
    button { min-height: 38px; padding: 0 14px; font-weight: 700; cursor: pointer; }
    button:hover:not(:disabled) { border-color: var(--green); color: var(--green-dark); }
    button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, a:focus-visible {
      outline: 3px solid rgba(40, 95, 143, 0.24);
      outline-offset: 2px;
    }
    button:disabled { cursor: not-allowed; opacity: 0.52; }
    .primary { border-color: var(--green); background: var(--green); color: #fff; }
    .primary:hover:not(:disabled) { border-color: var(--green-dark); background: var(--green-dark); color: #fff; }
    .danger { color: var(--red); }
    .shell { width: min(1280px, calc(100% - 36px)); margin: 0 auto; }
    .topbar { border-bottom: 1px solid var(--line); background: var(--panel); }
    .topbar-inner { min-height: 62px; display: flex; align-items: center; gap: 28px; }
    .brand { color: var(--ink); font-size: 20px; font-weight: 800; text-decoration: none; }
    nav { display: flex; align-items: stretch; align-self: stretch; gap: 4px; }
    nav a { display: flex; align-items: center; padding: 0 12px; border-bottom: 2px solid transparent; color: var(--muted); font-weight: 650; text-decoration: none; }
    nav a[aria-current="page"] { border-bottom-color: var(--green); color: var(--green-dark); }
    .service-state { margin-left: auto; }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      border-radius: 999px;
      padding: 0 10px;
      background: #edf0ee;
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }
    .badge.ok { background: var(--green-soft); color: var(--green-dark); }
    .badge.warning { background: var(--amber-soft); color: var(--amber); }
    main { padding: 26px 0 56px; }
    .page-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 18px; }
    h1 { margin: 0; font-size: 28px; line-height: 1.2; }
    h2 { margin: 0; font-size: 16px; line-height: 1.3; }
    .muted { color: var(--muted); }
    .user-tools { display: flex; align-items: end; gap: 8px; }
    .user-field { min-width: 230px; }
    label { display: block; margin-bottom: 6px; color: #445149; font-size: 12px; font-weight: 750; }
    select, input[type="number"], input[type="password"], input[type="text"] { width: 100%; min-height: 40px; padding: 0 10px; }
    #notice { display: none; margin-bottom: 16px; border-left: 3px solid var(--red); background: var(--red-soft); color: #8a1c13; padding: 11px 14px; }
    #notice.ok { border-color: var(--green); background: var(--green-soft); color: var(--green-dark); }
    .workspace { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(310px, 0.75fr); gap: 16px; align-items: start; }
    .main-column, .side-column { display: grid; gap: 16px; min-width: 0; }
    .panel { min-width: 0; border: 1px solid var(--line); border-radius: 7px; background: var(--panel); box-shadow: var(--shadow); }
    .panel-head { min-height: 51px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding: 0 16px; }
    .panel-body { padding: 16px; }
    textarea { display: block; width: 100%; min-height: 230px; resize: vertical; padding: 14px; line-height: 1.55; }
    textarea::placeholder { color: #8a948e; }
    .composer-meta { min-height: 30px; display: flex; justify-content: space-between; gap: 12px; padding-top: 8px; color: var(--muted); font-size: 12px; }
    .actions { display: flex; justify-content: flex-end; gap: 8px; }
    .settings { display: grid; gap: 16px; }
    .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .range-row { display: grid; grid-template-columns: 1fr 44px; align-items: center; gap: 10px; }
    input[type="range"] { width: 100%; accent-color: var(--green); }
    output { color: var(--green-dark); font-weight: 800; text-align: right; }
    .checks { display: grid; gap: 9px; }
    .check { display: flex; align-items: center; gap: 9px; color: #39463f; cursor: pointer; }
    .check input { width: 17px; height: 17px; margin: 0; accent-color: var(--green); }
    .model-current { border-left: 3px solid var(--blue); background: var(--blue-soft); padding: 10px 12px; }
    .model-current strong, .model-current span { display: block; overflow-wrap: anywhere; }
    .model-current span { margin-top: 2px; color: #486071; font-size: 12px; }
    .catalog { display: grid; }
    .catalog-row { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 10px; padding: 11px 0; border-bottom: 1px solid var(--line); }
    .catalog-row:last-child { border-bottom: 0; padding-bottom: 0; }
    .catalog-row:first-child { padding-top: 0; }
    .tier { align-self: start; color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; }
    .catalog-model { font-weight: 700; overflow-wrap: anywhere; }
    .catalog-price { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    details { border-top: 1px solid var(--line); padding-top: 12px; }
    summary { color: #445149; font-size: 12px; font-weight: 750; cursor: pointer; }
    .access-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; margin-top: 10px; }
    .estimate-empty, .response-empty { min-height: 118px; display: grid; place-items: center; color: var(--muted); text-align: center; }
    .estimate-grid, .result-stats { display: grid; }
    .estimate-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .result-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .estimate-item, .result-stat { min-width: 0; padding: 12px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
    .estimate-item:nth-child(3n), .result-stat:nth-child(3n) { border-right: 0; }
    .estimate-item:nth-last-child(-n+3), .result-stat:nth-last-child(-n+3) { border-bottom: 0; }
    .estimate-item:nth-child(3n) { border-right: 1px solid var(--line); }
    .estimate-item:nth-child(2n) { border-right: 0; }
    .estimate-item:nth-last-child(-n+3) { border-bottom: 1px solid var(--line); }
    .estimate-item:nth-last-child(-n+2) { border-bottom: 0; }
    .stat-label { color: var(--muted); font-size: 11px; font-weight: 750; text-transform: uppercase; }
    .stat-value { margin-top: 3px; font-size: 15px; font-weight: 800; overflow-wrap: anywhere; }
    .answer { min-height: 130px; padding: 18px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px; line-height: 1.65; }
    .result-flags { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 14px; }
    .flag { border-radius: 999px; padding: 4px 9px; background: #edf0ee; color: #46534c; font-size: 11px; font-weight: 750; }
    .flag.cache { background: var(--green-soft); color: var(--green-dark); }
    .flag.cost { background: var(--amber-soft); color: var(--amber); }
    .reason { border-top: 1px solid var(--line); padding: 12px 16px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .history { margin-top: 16px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; min-width: 720px; border-collapse: collapse; }
    th, td { padding: 11px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    tr:last-child td { border-bottom: 0; }
    dialog { width: min(430px, calc(100% - 28px)); border: 1px solid var(--line); border-radius: 8px; padding: 0; box-shadow: 0 20px 60px rgba(14, 28, 20, 0.24); }
    dialog::backdrop { background: rgba(18, 28, 23, 0.42); }
    .dialog-head { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); padding: 14px 16px; }
    .dialog-body { padding: 18px 16px; }
    .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
    .close { min-width: 38px; width: 38px; padding: 0; font-size: 20px; line-height: 1; }
    .spinner { display: inline-block; width: 14px; height: 14px; margin-right: 7px; border: 2px solid rgba(255,255,255,.42); border-top-color: #fff; border-radius: 50%; vertical-align: -2px; animation: spin .8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 940px) {
      .workspace { grid-template-columns: 1fr; }
      .side-column { grid-template-columns: 1fr 1fr; }
      .side-column .panel:first-child { grid-row: span 2; }
    }
    @media (max-width: 680px) {
      .shell { width: min(100% - 20px, 1280px); }
      .topbar-inner { min-height: 56px; gap: 14px; }
      nav a { padding: 0 7px; font-size: 12px; }
      .service-state { display: none; }
      main { padding-top: 18px; }
      .page-head { align-items: stretch; flex-direction: column; }
      .user-tools { align-items: stretch; flex-wrap: wrap; }
      .user-field { flex: 1 1 100%; min-width: 0; }
      .user-tools button { flex: 1; }
      .side-column { grid-template-columns: 1fr; }
      .side-column .panel:first-child { grid-row: auto; }
      .field-row { grid-template-columns: 1fr; }
      .estimate-grid, .result-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .estimate-item:nth-child(3n), .result-stat:nth-child(3n) { border-right: 1px solid var(--line); }
      .estimate-item:nth-child(2n), .result-stat:nth-child(2n) { border-right: 0; }
      .estimate-item:nth-last-child(-n+3), .result-stat:nth-last-child(-n+3) { border-bottom: 1px solid var(--line); }
      .estimate-item:nth-last-child(-n+2), .result-stat:nth-last-child(-n+2) { border-bottom: 0; }
      .actions { flex-direction: column-reverse; }
      .actions button { width: 100%; }
    }
    @media (max-width: 390px) {
      .brand { font-size: 18px; }
      nav a:last-child { display: none; }
      .estimate-grid, .result-stats { grid-template-columns: 1fr; }
      .estimate-item, .estimate-item:nth-child(2n), .estimate-item:nth-child(3n),
      .result-stat, .result-stat:nth-child(2n), .result-stat:nth-child(3n) { border-right: 0; border-bottom: 1px solid var(--line); }
      .estimate-item:last-child, .result-stat:last-child { border-bottom: 0; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="shell topbar-inner">
      <a class="brand" href="/">RouteWise</a>
      <nav aria-label="Primary">
        <a href="/" aria-current="page">Playground</a>
        <a href="/dashboard">Operations</a>
        <a href="/docs">API</a>
      </nav>
      <span class="badge service-state" id="service-state">Checking service</span>
    </div>
  </header>
  <main class="shell">
    <div class="page-head">
      <h1>Playground</h1>
      <div class="user-tools">
        <div class="user-field">
          <label for="user-select">User</label>
          <select id="user-select" aria-label="Selected user"><option value="">Loading users...</option></select>
        </div>
        <button id="new-user" type="button">New user</button>
        <button id="delete-user" class="danger" type="button" disabled>Delete</button>
      </div>
    </div>
    <div id="notice" role="alert"></div>

    <div class="workspace">
      <div class="main-column">
        <section class="panel">
          <div class="panel-head"><h2>Prompt</h2><span class="muted" id="active-user">No user selected</span></div>
          <div class="panel-body">
            <textarea id="prompt" maxlength="100000" placeholder="Enter a prompt..." aria-label="Prompt"></textarea>
            <div class="composer-meta"><span id="word-count">0 words</span><span id="char-count">0 / 100000</span></div>
            <div class="actions">
              <button id="estimate" type="button" disabled>Estimate</button>
              <button id="run" class="primary" type="button" disabled>Run prompt</button>
            </div>
          </div>
        </section>

        <section class="panel" aria-live="polite">
          <div class="panel-head"><h2>Response</h2><span class="muted" id="response-status">Waiting</span></div>
          <div id="response-content" class="response-empty">No response yet</div>
        </section>
      </div>

      <aside class="side-column">
        <section class="panel">
          <div class="panel-head"><h2>Routing controls</h2></div>
          <div class="panel-body settings">
            <div>
              <label for="tier">Maximum model</label>
              <select id="tier"></select>
            </div>
            <div id="selected-model" class="model-current"><strong>Loading model catalog...</strong></div>
            <div class="field-row">
              <div>
                <label for="policy">Routing policy</label>
                <select id="policy">
                  <option value="balanced">Balanced</option>
                  <option value="cost_first">Cost first</option>
                  <option value="quality_first">Quality first</option>
                </select>
              </div>
              <div>
                <label for="budget">Cost limit (USD)</label>
                <input id="budget" type="number" min="0" step="0.000001" placeholder="No limit">
              </div>
            </div>
            <div class="field-row">
              <div>
                <label for="quality">Quality target</label>
                <div class="range-row">
                  <input id="quality" type="range" min="0" max="1" step="0.05" value="0.65">
                  <output id="quality-value" for="quality">0.65</output>
                </div>
              </div>
              <div>
                <label for="output-limit">Maximum answer tokens</label>
                <select id="output-limit">
                  <option value="32">32 - fastest</option>
                  <option value="64" selected>64 - quick</option>
                  <option value="128">128 - standard</option>
                  <option value="256">256 - detailed</option>
                  <option value="512">512 - long</option>
                </select>
              </div>
            </div>
            <div class="checks">
              <label class="check"><input id="semantic-cache" type="checkbox"> Allow similar cached answers</label>
              <label class="check"><input id="bypass-cache" type="checkbox"> Force a fresh response</label>
            </div>
            <details>
              <summary>API access</summary>
              <div class="access-row">
                <input id="api-key" type="password" autocomplete="off" placeholder="X-API-Key">
                <button id="apply-key" type="button">Apply</button>
              </div>
            </details>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head"><h2>Cost estimate</h2><span class="muted" id="estimate-status">Not calculated</span></div>
          <div id="estimate-content" class="estimate-empty">Run an estimate</div>
        </section>

        <section class="panel">
          <div class="panel-head"><h2>Models and pricing</h2></div>
          <div class="panel-body catalog" id="catalog"><div class="muted">Loading catalog...</div></div>
        </section>
      </aside>
    </div>

    <section class="panel history">
      <div class="panel-head"><h2>Recent user requests</h2><button id="refresh-history" type="button">Refresh</button></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Status</th><th>Model</th><th>Cache</th><th>Tokens</th><th>Cost</th><th>Latency</th></tr></thead>
          <tbody id="history"><tr><td colspan="7" class="muted">Select a user</td></tr></tbody>
        </table>
      </div>
    </section>
  </main>

  <dialog id="user-dialog">
    <div class="dialog-head"><h2>Create user</h2><button class="close" id="close-dialog" type="button" aria-label="Close" title="Close">&times;</button></div>
    <form id="user-form" class="dialog-body">
      <label for="display-name">Display name</label>
      <input id="display-name" name="display_name" type="text" maxlength="80" autocomplete="name" required>
      <div class="dialog-actions">
        <button id="cancel-user" type="button">Cancel</button>
        <button class="primary" type="submit">Create user</button>
      </div>
    </form>
  </dialog>

  <script>
    const state = { users: [], models: [], busy: false };
    const byId = id => document.getElementById(id);
    const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

    function apiKey() {
      return sessionStorage.getItem('routewise.apiKey') || '';
    }

    async function apiFetch(path, options = {}) {
      const headers = new Headers(options.headers || {});
      const key = apiKey();
      if (key) headers.set('X-API-Key', key);
      const response = await fetch(path, {...options, headers});
      if (response.status === 204) return null;
      const type = response.headers.get('content-type') || '';
      const body = type.includes('application/json') ? await response.json() : await response.text();
      if (!response.ok) {
        const detail = body && typeof body === 'object' ? body.detail : body;
        throw new Error(detail || `Request failed (${response.status})`);
      }
      return body;
    }

    function showNotice(message, type = 'error') {
      const notice = byId('notice');
      notice.textContent = message;
      notice.className = type === 'ok' ? 'ok' : '';
      notice.style.display = 'block';
    }

    function clearNotice() {
      byId('notice').style.display = 'none';
    }

    function formatMoney(value) {
      if (value === null || value === undefined || value === '') return 'Unknown';
      const number = Number(value);
      if (!Number.isFinite(number)) return 'Unknown';
      return `$${number.toFixed(6)}`;
    }

    function formatPrice(model) {
      if (model.input_price_per_1k === null || model.output_price_per_1k === null) return 'Price unavailable';
      if (Number(model.input_price_per_1k) === 0 && Number(model.output_price_per_1k) === 0) return 'Local, $0 per 1K tokens';
      return `${formatMoney(model.input_price_per_1k)} input / ${formatMoney(model.output_price_per_1k)} output per 1K`;
    }

    function availabilityText(model) {
      if (model.available) return 'Ready';
      return model.required_env_var ? `${model.required_env_var} required` : 'Unavailable';
    }

    function selectedUser() {
      return state.users.find(user => user.id === byId('user-select').value);
    }

    function updateControls() {
      const hasUser = Boolean(byId('user-select').value);
      const hasPrompt = Boolean(byId('prompt').value.trim());
      byId('run').disabled = state.busy || !hasUser || !hasPrompt;
      byId('estimate').disabled = state.busy || !hasUser || !hasPrompt;
      byId('delete-user').disabled = state.busy || !hasUser;
      const user = selectedUser();
      byId('active-user').textContent = user ? user.display_name : 'No user selected';
    }

    async function checkService() {
      const badge = byId('service-state');
      try {
        const readiness = await apiFetch('/readiness');
        badge.textContent = readiness.status === 'ready' ? 'Service ready' : 'Needs attention';
        badge.className = `badge service-state ${readiness.status === 'ready' ? 'ok' : 'warning'}`;
      } catch {
        badge.textContent = 'Service unavailable';
        badge.className = 'badge service-state warning';
      }
    }

    function renderCatalog() {
      byId('tier').innerHTML = state.models.map(model => {
        const price = model.input_price_per_1k === null ? 'price unavailable' :
          Number(model.input_price_per_1k) === 0 && Number(model.output_price_per_1k) === 0 ? '$0 local' : 'priced';
        return `<option value="${escapeHtml(model.tier)}">${escapeHtml(model.tier[0].toUpperCase() + model.tier.slice(1))} - ${escapeHtml(model.model)} - ${price} - ${escapeHtml(availabilityText(model))}</option>`;
      }).join('');
      const savedTier = localStorage.getItem('routewise.tier') || 'small';
      if (state.models.some(model => model.tier === savedTier)) byId('tier').value = savedTier;
      byId('catalog').innerHTML = state.models.map(model => `
        <div class="catalog-row">
          <div class="tier">${escapeHtml(model.tier)}</div>
          <div><div class="catalog-model">${escapeHtml(model.model)}</div><div class="catalog-price">${escapeHtml(formatPrice(model))} | ${escapeHtml(availabilityText(model))}</div></div>
        </div>`).join('');
      renderSelectedModel();
    }

    function renderSelectedModel() {
      const model = state.models.find(item => item.tier === byId('tier').value);
      if (!model) return;
      byId('selected-model').innerHTML = `<strong>${escapeHtml(model.model)}</strong><span>${escapeHtml(formatPrice(model))} | ${escapeHtml(availabilityText(model))}</span>`;
      localStorage.setItem('routewise.tier', model.tier);
    }

    async function loadModels() {
      try {
        const result = await apiFetch('/models/catalog');
        state.models = result.models;
        renderCatalog();
      } catch (error) {
        showNotice(error.message);
        byId('catalog').innerHTML = '<div class="muted">Catalog unavailable</div>';
      }
    }

    async function loadUsers(preferredId = null) {
      try {
        const result = await apiFetch('/users');
        state.users = result.users;
        const savedId = preferredId || localStorage.getItem('routewise.userId') || '';
        byId('user-select').innerHTML = state.users.length
          ? state.users.map(user => `<option value="${escapeHtml(user.id)}">${escapeHtml(user.display_name)}</option>`).join('')
          : '<option value="">Create a user to begin</option>';
        if (state.users.some(user => user.id === savedId)) byId('user-select').value = savedId;
        const currentId = byId('user-select').value;
        if (currentId) localStorage.setItem('routewise.userId', currentId);
        updateControls();
        await loadHistory();
      } catch (error) {
        state.users = [];
        byId('user-select').innerHTML = '<option value="">Users unavailable</option>';
        updateControls();
        showNotice(error.message);
      }
    }

    function requestPayload() {
      const budgetValue = byId('budget').value.trim();
      return {
        user_id: byId('user-select').value,
        messages: [{role: 'user', content: byId('prompt').value.trim()}],
        quality_target: Number(byId('quality').value),
        max_cost_tier: byId('tier').value,
        routing_policy: byId('policy').value,
        allow_semantic_cache: byId('semantic-cache').checked,
        bypass_cache: byId('bypass-cache').checked,
        max_estimated_cost_usd: budgetValue === '' ? null : Number(budgetValue),
        max_completion_tokens: Number(byId('output-limit').value)
      };
    }

    function renderEstimate(data) {
      byId('estimate-status').textContent = data.budget_exceeded ? 'Over budget' : data.budget_status.replaceAll('_', ' ');
      byId('estimate-content').className = '';
      byId('estimate-content').innerHTML = `<div class="estimate-grid">
        <div class="estimate-item"><div class="stat-label">Selected route</div><div class="stat-value">${escapeHtml(data.selected_model)}</div></div>
        <div class="estimate-item"><div class="stat-label">Model status</div><div class="stat-value">${data.model_available ? 'Ready' : 'Unavailable'}</div></div>
        <div class="estimate-item"><div class="stat-label">Estimated cost</div><div class="stat-value">${escapeHtml(formatMoney(data.estimated_total_cost_usd))}</div></div>
        <div class="estimate-item"><div class="stat-label">Estimated tokens</div><div class="stat-value">${data.estimated_total_tokens}</div></div>
        <div class="estimate-item"><div class="stat-label">Answer limit</div><div class="stat-value">${data.estimated_completion_tokens}</div></div>
        <div class="estimate-item"><div class="stat-label">Cache</div><div class="stat-value">${escapeHtml(data.cache_status)}</div></div>
        <div class="estimate-item"><div class="stat-label">Budget</div><div class="stat-value">${escapeHtml(data.budget_status.replaceAll('_', ' '))}</div></div>
        <div class="estimate-item"><div class="stat-label">Price source</div><div class="stat-value">${escapeHtml(data.price_source.replaceAll('_', ' '))}</div></div>
      </div>`;
    }

    function invalidateEstimate() {
      clearNotice();
      byId('estimate-status').textContent = 'Not calculated';
      byId('estimate-content').className = 'estimate-empty';
      byId('estimate-content').textContent = 'Run an estimate';
      if (byId('response-status').textContent === 'Failed') {
        byId('response-status').textContent = 'Waiting';
      }
    }

    function renderResponse(data) {
      const cacheType = data.semantic_cache_hit ? 'semantic cache' : data.cache_hit ? 'exact cache' : 'fresh model call';
      byId('response-status').textContent = 'Complete';
      byId('response-content').className = '';
      byId('response-content').innerHTML = `
        <div class="answer">${escapeHtml(data.answer)}</div>
        <div class="result-flags">
          <span class="flag">${escapeHtml(data.final_model)}</span>
          <span class="flag cache">${escapeHtml(cacheType)}</span>
          <span class="flag cost">${escapeHtml(formatMoney(data.estimated_cost_usd))}</span>
          <span class="flag">${escapeHtml(data.quality_label || 'not scored')}</span>
        </div>
        <div class="result-stats">
          <div class="result-stat"><div class="stat-label">Prompt tokens</div><div class="stat-value">${data.prompt_tokens ?? '-'}</div></div>
          <div class="result-stat"><div class="stat-label">Answer tokens</div><div class="stat-value">${data.completion_tokens ?? '-'}</div></div>
          <div class="result-stat"><div class="stat-label">Total tokens</div><div class="stat-value">${data.total_tokens ?? '-'}</div></div>
          <div class="result-stat"><div class="stat-label">Quality</div><div class="stat-value">${data.quality_score ?? '-'}</div></div>
          <div class="result-stat"><div class="stat-label">Fallbacks</div><div class="stat-value">${data.fallback_count}</div></div>
          <div class="result-stat"><div class="stat-label">Cached for reuse</div><div class="stat-value">${data.response_cached ? 'Yes' : 'No'}</div></div>
        </div>
        <div class="reason">${escapeHtml(data.route_reason)}</div>`;
    }

    async function calculateEstimate() {
      clearNotice();
      const data = await apiFetch('/route/estimate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(requestPayload())
      });
      renderEstimate(data);
      return data;
    }

    async function runAction(kind) {
      state.busy = true;
      updateControls();
      const runButton = byId('run');
      const originalRunLabel = runButton.textContent;
      if (kind === 'run') {
        runButton.innerHTML = '<span class="spinner"></span>Running';
        byId('response-status').textContent = 'Running';
      } else {
        byId('estimate-status').textContent = 'Calculating';
      }
      try {
        const estimate = await calculateEstimate();
        if (kind === 'run') {
          if (!estimate.model_available) throw new Error(estimate.model_availability_reason || 'The selected model is unavailable.');
          if (estimate.budget_exceeded) throw new Error('Estimated model cost exceeds the configured limit.');
          const data = await apiFetch('/route', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(requestPayload())
          });
          renderResponse(data);
          await loadHistory();
        }
      } catch (error) {
        if (kind === 'run') byId('response-status').textContent = 'Failed';
        showNotice(error.message);
      } finally {
        state.busy = false;
        runButton.textContent = originalRunLabel;
        updateControls();
      }
    }

    async function loadHistory() {
      const userId = byId('user-select').value;
      if (!userId) {
        byId('history').innerHTML = '<tr><td colspan="7" class="muted">Select a user</td></tr>';
        return;
      }
      try {
        const result = await apiFetch('/requests?limit=100');
        const requests = result.requests.filter(item => item.user_id === userId).slice(0, 12);
        byId('history').innerHTML = requests.length ? requests.map(item => {
          const cache = item.semantic_cache_hit ? 'semantic' : item.cache_hit ? 'exact' : item.cache_bypassed ? 'bypassed' : 'miss';
          return `<tr>
            <td>${item.created_at ? escapeHtml(new Date(item.created_at).toLocaleString()) : '-'}</td>
            <td>${escapeHtml(item.request_status)}</td>
            <td>${escapeHtml(item.final_model)}</td>
            <td>${escapeHtml(cache)}</td>
            <td>${item.total_tokens ?? '-'}</td>
            <td>${escapeHtml(formatMoney(item.estimated_cost_usd))}</td>
            <td>${item.latency_ms ?? '-'} ms</td>
          </tr>`;
        }).join('') : '<tr><td colspan="7" class="muted">No requests for this user</td></tr>';
      } catch (error) {
        byId('history').innerHTML = `<tr><td colspan="7" class="muted">${escapeHtml(error.message)}</td></tr>`;
      }
    }

    byId('prompt').addEventListener('input', () => {
      const value = byId('prompt').value;
      const words = value.trim() ? value.trim().split(/\\s+/).length : 0;
      byId('word-count').textContent = `${words} ${words === 1 ? 'word' : 'words'}`;
      byId('char-count').textContent = `${value.length} / 100000`;
      invalidateEstimate();
      updateControls();
    });
    byId('quality').addEventListener('input', event => {
      byId('quality-value').value = Number(event.target.value).toFixed(2);
      invalidateEstimate();
    });
    byId('tier').addEventListener('change', () => {
      renderSelectedModel();
      invalidateEstimate();
    });
    ['policy', 'output-limit', 'semantic-cache', 'bypass-cache'].forEach(id => {
      byId(id).addEventListener('change', invalidateEstimate);
    });
    byId('budget').addEventListener('input', invalidateEstimate);
    byId('user-select').addEventListener('change', async event => {
      localStorage.setItem('routewise.userId', event.target.value);
      invalidateEstimate();
      updateControls();
      await loadHistory();
    });
    byId('estimate').addEventListener('click', () => runAction('estimate'));
    byId('run').addEventListener('click', () => runAction('run'));
    byId('refresh-history').addEventListener('click', loadHistory);

    const dialog = byId('user-dialog');
    byId('new-user').addEventListener('click', () => {
      clearNotice();
      byId('display-name').value = '';
      dialog.showModal();
      byId('display-name').focus();
    });
    byId('close-dialog').addEventListener('click', () => dialog.close());
    byId('cancel-user').addEventListener('click', () => dialog.close());
    byId('user-form').addEventListener('submit', async event => {
      event.preventDefault();
      try {
        const user = await apiFetch('/users', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({display_name: byId('display-name').value})
        });
        dialog.close();
        clearNotice();
        await loadUsers(user.id);
        showNotice(`${user.display_name} created.`, 'ok');
      } catch (error) {
        showNotice(error.message);
        dialog.close();
      }
    });
    byId('delete-user').addEventListener('click', async () => {
      const user = selectedUser();
      if (!user || !confirm(`Delete ${user.display_name}? Request history will be kept.`)) return;
      try {
        await apiFetch(`/users/${encodeURIComponent(user.id)}`, {method: 'DELETE'});
        localStorage.removeItem('routewise.userId');
        await loadUsers();
        showNotice(`${user.display_name} deleted.`, 'ok');
      } catch (error) {
        showNotice(error.message);
      }
    });
    byId('api-key').value = apiKey();
    byId('apply-key').addEventListener('click', async () => {
      const value = byId('api-key').value.trim();
      if (value) sessionStorage.setItem('routewise.apiKey', value);
      else sessionStorage.removeItem('routewise.apiKey');
      clearNotice();
      await loadUsers();
    });

    Promise.all([checkService(), loadModels(), loadUsers()]);
  </script>
</body>
</html>"""

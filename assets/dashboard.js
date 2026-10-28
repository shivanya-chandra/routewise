const historyKey = "routewise-hosted-history-v1";
const $ = (id) => document.getElementById(id);

function history() {
  try { return JSON.parse(localStorage.getItem(historyKey) || "[]"); } catch { return []; }
}

function money(value, digits = 4) { return `$${value.toFixed(digits)}`; }
function safe(value) { return value.replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }

function render() {
  const items = history();
  const spend = items.reduce((sum, item) => sum + item.cost, 0);
  const savings = items.reduce((sum, item) => sum + (item.savings || 0), 0);
  const latency = items.length ? Math.round(items.reduce((sum, item) => sum + item.latency, 0) / items.length) : 0;
  $("requests").textContent = items.length.toLocaleString();
  $("spend").textContent = money(spend);
  $("savings").textContent = money(savings);
  $("latency").textContent = items.length ? `${latency} ms` : "—";

  const counts = { small: 0, medium: 0, frontier: 0 };
  items.forEach((item) => counts[item.tier] = (counts[item.tier] || 0) + 1);
  const max = Math.max(1, ...Object.values(counts));
  $("distribution").innerHTML = Object.entries(counts).map(([tier, count], index) => `
    <div><div class="bar-label"><span>${tier[0].toUpperCase() + tier.slice(1)} tier</span><span>${count}</span></div><div class="bar-track"><div class="bar-fill ${index === 1 ? "blue" : ""}" style="width:${count / max * 100}%"></div></div></div>`).join("");

  $("timeline").innerHTML = items.length ? items.slice(0, 5).map((item, index) => `
    <div class="timeline-item"><div class="timeline-rail"><span class="timeline-dot"></span>${index < Math.min(items.length, 5) - 1 ? '<span class="timeline-line"></span>' : ''}</div><div class="timeline-copy"><strong>${safe(item.model)}</strong><span>${safe(item.prompt)} · ${new Date(item.at).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}</span></div></div>`).join("") : `<div class="empty">No routing decisions yet.</div>`;

  $("ledger").innerHTML = items.length ? items.map((item) => `<tr><td>${safe(item.prompt)}</td><td>${safe(item.model)}</td><td>${safe(item.tier)}</td><td>${safe(item.policy)}</td><td>${money(item.cost, 6)}</td><td>${item.latency} ms</td></tr>`).join("") : `<tr><td colspan="6" class="muted">Run a prompt in the playground to populate this ledger.</td></tr>`;
}

$("refresh").addEventListener("click", render);
render();

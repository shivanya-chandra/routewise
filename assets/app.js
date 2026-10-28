const models = {
  llama: { tier: "small", label: "Small", family: "Local Llama", name: "llama-3.2-3b", input: 0.0000001, output: 0.0000001, quality: 0.58, latency: 410 },
  qwen: { tier: "medium", label: "Medium", family: "Qwen", name: "qwen2.5-72b-instruct", input: 0.0000002, output: 0.0000006, quality: 0.83, latency: 760 },
  gptMini: { tier: "medium", label: "Medium", family: "OpenAI", name: "gpt-4.1-mini", input: 0.0000004, output: 0.0000016, quality: 0.79, latency: 820 },
  gptFrontier: { tier: "frontier", label: "Frontier", family: "OpenAI", name: "gpt-4.1", input: 0.000002, output: 0.000008, quality: 0.94, latency: 1480 }
};

const tierOrder = ["small", "medium", "frontier"];
const catalogOrder = ["llama", "qwen", "gptMini", "gptFrontier"];
const $ = (id) => document.getElementById(id);
const promptEl = $("prompt");
const tierEl = $("tier");
const providerEl = $("provider");
const policyEl = $("policy");
const qualityEl = $("quality");
const budgetEl = $("budget");
const outputEl = $("output-limit");
const historyKey = "routewise-hosted-history-v1";

function words(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function tokenEstimate(text) {
  return Math.max(1, Math.ceil(text.length / 4));
}

function complexity(text) {
  const lower = text.toLowerCase();
  let score = Math.min(1, words(text) / 220);
  if (/compare|analy[sz]e|architecture|trade-?off|debug|prove|strategy|design/.test(lower)) score += .22;
  if (/```|function |class |select |curl |api|database|distributed/.test(lower)) score += .18;
  if (/step.by.step|recommend|evaluate|security|production/.test(lower)) score += .12;
  return Math.min(1, score);
}

function hasQwenSignal(text) {
  return /code|function|python|javascript|sql|math|reason|translate|multilingual|chinese|中文|cost|budget/i.test(text);
}

function modelForTier(tier, text, policy, preference) {
  if (preference === "local") return models.llama;
  if (preference === "qwen") return tier === "small" ? models.llama : models.qwen;
  if (preference === "openai") return tier === "frontier" ? models.gptFrontier : tier === "medium" ? models.gptMini : models.llama;
  if (tier === "small") return models.llama;
  if (tier === "frontier") return models.gptFrontier;
  return hasQwenSignal(text) || policy === "cost_first" ? models.qwen : models.gptMini;
}

function chooseRoute(text) {
  const score = complexity(text);
  const maxIndex = tierOrder.indexOf(tierEl.value);
  const policy = policyEl.value;
  const target = Number(qualityEl.value);
  let desired = score < .33 ? 0 : score < .7 ? 1 : 2;
  if (policy === "cost_first") desired -= 1;
  if (policy === "quality_first") desired += 1;
  if (target >= .85) desired = Math.max(desired, 2);
  if (target >= .7) desired = Math.max(desired, 1);
  if (maxIndex >= 1 && (providerEl.value === "qwen" || (providerEl.value === "auto" && hasQwenSignal(text)))) {
    desired = Math.max(desired, 1);
  }
  desired = Math.max(0, Math.min(maxIndex, desired));
  const selectedTier = tierOrder[desired] || tierOrder[maxIndex];
  let model = modelForTier(selectedTier, text, policy, providerEl.value);
  const outputTokens = Number(outputEl.value);
  const inputTokens = tokenEstimate(text);
  const budget = Number(budgetEl.value || 0);
  if (budget > 0) {
    while (tierOrder.indexOf(model.tier) > 0) {
      const cost = inputTokens * model.input + outputTokens * model.output;
      if (cost <= budget) break;
      const cheaperTier = tierOrder[tierOrder.indexOf(model.tier) - 1];
      model = modelForTier(cheaperTier, text, policy, providerEl.value);
    }
  }
  return { tier: model.tier, model, score, inputTokens, outputTokens };
}

function estimate(text) {
  const route = chooseRoute(text);
  const model = route.model;
  const cost = route.inputTokens * model.input + route.outputTokens * model.output;
  const maxModel = modelForTier(tierEl.value, text, "quality_first", providerEl.value);
  const maxCost = route.inputTokens * maxModel.input + route.outputTokens * maxModel.output;
  const latency = Math.round(model.latency + route.inputTokens * 1.6 + route.outputTokens * 1.1);
  return { ...route, model, cost, maxCost, savings: Math.max(0, maxCost - cost), latency };
}

function money(value) {
  if (value === 0) return "$0.000000";
  return `$${value.toFixed(6)}`;
}

function renderCatalog() {
  $("catalog").innerHTML = catalogOrder.map((key) => {
    const model = models[key];
    return `<div class="catalog-row"><span class="tier">${model.family}</span><div><div class="catalog-model">${model.name}</div><div class="catalog-price">${model.label} tier · demo estimate $${(model.input * 1e6).toFixed(2)} in / $${(model.output * 1e6).toFixed(2)} out per 1M tokens</div></div></div>`;
  }).join("");
}

function updateComposer() {
  const text = promptEl.value;
  const count = words(text);
  $("word-count").textContent = `${count} ${count === 1 ? "word" : "words"}`;
  $("char-count").textContent = `${text.length.toLocaleString()} / 100,000`;
  $("estimate").disabled = !text.trim();
  $("run").disabled = !text.trim();
  updateCandidate();
}

function updateCandidate() {
  const route = chooseRoute(promptEl.value || "short prompt");
  const model = route.model;
  $("selected-model").innerHTML = `<strong>${model.name}</strong><span>${model.family} · ${model.label} tier · ${(route.score * 100).toFixed(0)}% prompt complexity</span>`;
}

function renderEstimate() {
  const result = estimate(promptEl.value);
  $("estimate-status").textContent = `${result.model.label} route`;
  $("estimate-content").className = "stats two";
  $("estimate-content").innerHTML = `
    <div class="stat"><div class="stat-label">Selected model</div><div class="stat-value">${result.model.name}</div></div>
    <div class="stat"><div class="stat-label">Estimated cost</div><div class="stat-value">${money(result.cost)}</div></div>
    <div class="stat"><div class="stat-label">Input tokens</div><div class="stat-value">${result.inputTokens.toLocaleString()}</div></div>
    <div class="stat"><div class="stat-label">Expected latency</div><div class="stat-value">${result.latency} ms</div></div>`;
  return result;
}

function demoAnswer(text, result) {
  const topic = text.trim().replace(/\s+/g, " ").slice(0, 150);
  const policy = policyEl.options[policyEl.selectedIndex].text;
  return `
    <div class="response">
      <p><strong>RouteWise selected ${result.model.name}</strong> because this prompt scored ${(result.score * 100).toFixed(0)}% on the complexity heuristic under the ${policy.toLowerCase()} policy.</p>
      <p>The hosted demo does not send your prompt to a model. In the production gateway, the selected provider would now receive:</p>
      <ul><li>${escapeHtml(topic)}${text.length > 150 ? "…" : ""}</li><li>Completion budget: ${result.outputTokens} tokens</li><li>Quality target: ${Number(qualityEl.value).toFixed(2)}</li></ul>
    </div>
    <div class="flags"><span class="flag green">${result.model.label} tier</span><span class="flag">${policy}</span><span class="flag amber">${money(result.cost)} estimate</span></div>`;
}

function escapeHtml(value) {
  return value.replace(/[&<>"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[char]));
}

function getHistory() {
  try { return JSON.parse(localStorage.getItem(historyKey) || "[]"); } catch { return []; }
}

function saveHistory(item) {
  const history = [item, ...getHistory()].slice(0, 20);
  localStorage.setItem(historyKey, JSON.stringify(history));
  renderHistory();
}

function renderHistory() {
  const history = getHistory();
  $("history-body").innerHTML = history.length ? history.map((item) => `
    <tr><td>${escapeHtml(item.prompt)}</td><td>${item.model}</td><td>${item.policy}</td><td>${money(item.cost)}</td><td>${item.latency} ms</td><td>${new Date(item.at).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}</td></tr>`).join("") : `<tr><td colspan="6" class="muted">No requests in this browser session yet.</td></tr>`;
}

async function runDemo() {
  const result = renderEstimate();
  $("run").disabled = true;
  $("response-status").textContent = "Routing…";
  $("response-content").className = "empty";
  $("response-content").textContent = "Scoring prompt and selecting a model…";
  await new Promise((resolve) => setTimeout(resolve, 520));
  $("response-content").className = "";
  $("response-content").innerHTML = demoAnswer(promptEl.value, result);
  $("response-status").textContent = `${result.model.name} · ${result.latency} ms`;
  $("run").disabled = false;
  saveHistory({ prompt: promptEl.value.trim().slice(0, 88), model: result.model.name, tier: result.tier, policy: policyEl.options[policyEl.selectedIndex].text, cost: result.cost, savings: result.savings, latency: result.latency, at: new Date().toISOString() });
}

promptEl.addEventListener("input", updateComposer);
[tierEl, providerEl, policyEl, qualityEl, budgetEl, outputEl].forEach((control) => control.addEventListener("input", () => {
  $("quality-value").value = Number(qualityEl.value).toFixed(2);
  updateCandidate();
}));
$("estimate").addEventListener("click", renderEstimate);
$("run").addEventListener("click", runDemo);
$("clear-session").addEventListener("click", () => {
  localStorage.removeItem(historyKey);
  renderHistory();
  $("response-content").className = "empty";
  $("response-content").textContent = "Session cleared. Enter a prompt to begin again.";
  $("response-status").textContent = "Waiting";
});

renderCatalog();
renderHistory();
updateComposer();

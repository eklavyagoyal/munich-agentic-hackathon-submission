const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const NS = "http://www.w3.org/2000/svg";

const state = {
  overview: null,
  game: null,
  caseData: null,
  selectedGame: null,
  selectedItem: null,
  raceIndex: 0,
  raceTimer: null,
  liveSeq: 0,
  nextRound: null,
  serverClockOffset: 0,
  loadGeneration: 0,
  ledgerFilter: "all",
  ledgerSort: "item",
  compareGame: null,
  comparePayload: null,
  commandResults: [],
  commandIndex: 0,
  livePaused: false,
  tapePaused: false,
  watches: new Set(),
  overviewRefreshPending: null,
  lastOverviewRefresh: 0,
  landscapeSource: "all",
  landscapeBucket: "all",
  landscapeStatus: "all",
  selectedRiskCell: null,
  dossierTeam: null,
  robustnessMode: "medianPaceTotal",
  selectedRuleId: null,
  ruleTransition: "all",
  portfolioRuleId: null,
  portfolioGate: "none",
  portfolioSource: "all",
  portfolioDirection: "any",
  capitalSort: "gross",
  roundMapFilter: "all",
  replayGame: null,
  replayIndex: 0,
  replayTimer: null,
  replaySpeed: 1,
  evidenceMode: "hidden-field",
  forecastWindow: "all",
  forecastRuns: 5000,
  forecastSeed: 20260823,
  forecastTarget: 3,
  forecastEdge: 0,
  forecastResult: null,
  forecastValidation: null,
  reviewerLab: null,
  reviewerWindow: "all",
  reviewerOpponent: "all",
  reviewerSource: "all",
  reviewerClass: "all",
  reviewerShifts: {"0–50": 0, "50–400": 0, "400–1200": 0, "1200+": 0},
  reviewerResult: null,
  reviewerRenderPending: null,
  cohortA: {window: "previous-10", source: "all", bucket: "all", status: "all"},
  cohortB: {window: "last-10", source: "all", bucket: "all", status: "all"},
  cohortRuns: 5000,
  cohortSeed: 20260824,
  cohortResult: null,
  market: null,
  marketTeam: "Oasis",
  marketMode: "settlement",
  marketPeer: null,
  marketReplayMode: "cumulative",
  marketReplayGame: null,
  marketReplayIndex: 0,
  marketReplayTimer: null,
  marketFramesByGame: new Map(),
  marketViewCache: new Map(),
  operations: null,
  driftMetric: "net",
  driftWindow: 10,
  driftSensitivity: 3,
  driftAnalysis: null,
  sourceDrift: null,
  rivalTeam: null,
  rivalWindow: "all",
  rivalResult: null,
  calibrationCoverage: .90,
  calibrationSource: "all",
  calibrationBucket: "all",
  calibrationWindow: "all",
  calibrationResult: null,
  regretWindow: "all",
  regretSource: "all",
  regretBucket: "all",
  regretFocus: "combined",
  regretResult: null,
  peerCohort: "source-bucket",
  peerMetric: "combined",
  peerResult: null,
  peerRegretCache: null,
  watchboardSort: "triage",
  watchboardResult: null,
};

const palette = ["#7f8d98", "#877f98", "#748b8a", "#96816e", "#778493", "#8b7890", "#7d8e72", "#8c8880"];
const colors = {
  cyan: "#65d6d0", amber: "#f2b84b", red: "#ef6a67", green: "#82d39b",
  blue: "#7fa9ff", violet: "#b89cff", muted: "#64717b", grid: "rgba(171,188,199,.13)",
};

function element(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = String(value);
    else if (key.startsWith("aria-")) node.setAttribute(key, String(value));
    else if (key === "dataset") Object.assign(node.dataset, value);
    else node.setAttribute(key, String(value));
  }
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child === null || child === undefined) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svgElement(tag, attrs = {}, text = null) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== null) node.textContent = String(text);
  return node;
}

function svgRoot(width, height, label) {
  return svgElement("svg", {viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": label});
}

function clear(node) { node.replaceChildren(); }
function clamp(value, lo, hi) { return Math.min(hi, Math.max(lo, value)); }
function safeNumber(value, fallback = 0) { return Number.isFinite(Number(value)) ? Number(value) : fallback; }
function signed(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "unknown";
  return `${Number(value) >= 0 ? "+" : "−"}${formatCurrency(Math.abs(Number(value)))}`;
}
function formatCurrency(value, compact = false) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "unknown";
  const options = compact && Math.abs(value) >= 1000
    ? {style: "currency", currency: "EUR", notation: "compact", maximumFractionDigits: 1}
    : {style: "currency", currency: "EUR", maximumFractionDigits: 0};
  return new Intl.NumberFormat("en-GB", options).format(value);
}
function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("en-GB", {maximumFractionDigits: digits}).format(value);
}
function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "unknown";
  return new Intl.NumberFormat("en-GB", {style: "percent", maximumFractionDigits: digits}).format(value);
}
function formatDurationMs(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "not logged";
  const ms = Math.max(0, Number(value));
  if (ms < 1000) return `${formatNumber(ms, ms < 100 ? 1 : 0)} ms`;
  if (ms < 60000) return `${formatNumber(ms / 1000, ms < 10000 ? 2 : 1)} s`;
  const minutes = Math.floor(ms / 60000);
  return `${minutes}m ${formatNumber((ms - minutes * 60000) / 1000, 1)}s`;
}
function formatUtcTime(value) {
  if (!value) return "timestamp not logged";
  const moment = new Date(value);
  if (!Number.isFinite(moment.getTime())) return "timestamp invalid";
  return `${moment.toLocaleTimeString([], {hour12: false, timeZone: "UTC"})} UTC`;
}
function medianNumber(values) {
  const clean = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!clean.length) return null;
  const middle = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[middle] : (clean[middle - 1] + clean[middle]) / 2;
}
function itemLink(game, item = null, label = null) {
  const gameNumber = Number(game), itemNumber = item === null ? null : Number(item);
  const text = label || (itemNumber === null ? `game ${gameNumber}` : `game ${gameNumber} item ${itemNumber}`);
  const button = element("button", {type: "button", class: "table-link", text});
  button.addEventListener("click", async () => {
    await selectGame(gameNumber);
    if (Number.isInteger(itemNumber)) await selectItem(itemNumber, {scroll: true});
    else $("#game").scrollIntoView({behavior: "smooth", block: "start"});
  });
  return button;
}
function cssStatus(status) { return String(status || "unknown").replace(/[^a-z0-9-]/gi, "-").toLowerCase(); }
function prettyStatus(status) {
  const names = {
    under: "provably under", over: "provably over", "inside-bracket": "inside bracket",
    "above-floor-open-ceiling": "above floor · ceiling open", unlabelled: "no proven bracket",
  };
  return names[status] || String(status || "unknown").replaceAll("-", " ");
}

function watchKey(game, item) { return `${Number(game)}:${Number(item)}`; }
function isWatched(game, item) { return state.watches.has(watchKey(game, item)); }
function loadWatches() {
  try {
    const parsed = JSON.parse(localStorage.getItem("oasis-viz-watchlist") || "[]");
    state.watches = new Set(Array.isArray(parsed) ? parsed.filter(value => /^\d{1,3}:\d{1,3}$/.test(value)) : []);
  } catch {
    state.watches = new Set();
  }
}
function saveWatches() {
  try { localStorage.setItem("oasis-viz-watchlist", JSON.stringify([...state.watches].sort())); }
  catch { toast("This browser blocked local watchlist storage."); }
  $("#watchlist-count").textContent = String(state.watches.size);
}

function sparkline(values, color = colors.cyan) {
  const box = element("span", {class: "briefing-spark", "aria-hidden": "true"});
  if (!values?.length) return box;
  const width = 70, height = 28;
  const min = Math.min(...values), max = Math.max(...values);
  const points = values.map((value, index) => [
    values.length === 1 ? width / 2 : index / (values.length - 1) * width,
    3 + (max - value) / (max - min || 1) * (height - 6),
  ]);
  const svg = svgRoot(width, height, "");
  svg.setAttribute("aria-hidden", "true");
  svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: color, "stroke-width": 1.7, "stroke-linecap": "round"}));
  box.append(svg);
  return box;
}

async function api(path, {timeout = 12000, retries = 1} = {}) {
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(path, {headers: {Accept: "application/json"}, signal: controller.signal});
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const error = new Error(payload?.detail || `HTTP ${response.status}`);
        error.retryable = response.status === 429 || response.status >= 500;
        throw error;
      }
      return payload;
    } catch (error) {
      lastError = error.name === "AbortError" ? new Error(`Timed out after ${timeout / 1000}s`) : error;
      const retryable = error.name === "AbortError" || error.retryable || error instanceof TypeError;
      if (!retryable || attempt >= retries) throw lastError;
      const delay = 160 * (2 ** attempt) + Math.random() * 120;
      await new Promise(resolve => setTimeout(resolve, delay));
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastError || new Error("Local API request failed");
}

let toastTimer = null;
function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 6500);
}

function showSystemState(dependencies) {
  const banner = $("#system-banner");
  const bad = Object.entries(dependencies?.items || {}).filter(([, row]) => !row.ok);
  if (!bad.length) {
    banner.hidden = true;
    return;
  }
  const names = bad.map(([name]) => name).join(", ");
  banner.textContent = dependencies.ready
    ? `DEGRADED · ${names} unavailable; cached/historical views remain active.`
    : `NOT READY · critical read-only data unavailable: ${names}.`;
  banner.hidden = false;
}

function addTooltip(target, content) {
  target.addEventListener("pointerenter", event => showTooltip(event, content));
  target.addEventListener("pointermove", event => moveTooltip(event));
  target.addEventListener("pointerleave", hideTooltip);
  target.addEventListener("focus", event => showTooltip(event, content));
  target.addEventListener("blur", hideTooltip);
}

let tooltipNode = null;
function showTooltip(event, content) {
  if (!tooltipNode) {
    tooltipNode = element("div", {class: "tooltip"});
    document.body.append(tooltipNode);
  }
  tooltipNode.replaceChildren();
  const lines = typeof content === "function" ? content() : content;
  for (const [index, line] of [].concat(lines).entries()) {
    const row = element("div");
    if (index === 0) row.append(element("strong", {text: line}));
    else row.textContent = line;
    tooltipNode.append(row);
  }
  tooltipNode.hidden = false;
  moveTooltip(event);
}
function moveTooltip(event) {
  if (!tooltipNode || tooltipNode.hidden) return;
  const x = Math.min(window.innerWidth - tooltipNode.offsetWidth - 12, (event.clientX || 20) + 14);
  const y = Math.min(window.innerHeight - tooltipNode.offsetHeight - 12, (event.clientY || 20) + 14);
  tooltipNode.style.left = `${Math.max(8, x)}px`;
  tooltipNode.style.top = `${Math.max(8, y)}px`;
}
function hideTooltip() { if (tooltipNode) tooltipNode.hidden = true; }

function chartScaffold(svg, width, height, margin, min, max, ticks = 5) {
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const span = max - min || 1;
  for (let i = 0; i <= ticks; i++) {
    const y = margin.top + plotH * i / ticks;
    const value = max - span * i / ticks;
    svg.append(svgElement("line", {x1: margin.left, y1: y, x2: width - margin.right, y2: y, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 9, y: y + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true)));
  }
  return {
    x: (index, count) => margin.left + (count <= 1 ? plotW / 2 : plotW * index / (count - 1)),
    y: value => margin.top + plotH * (max - value) / span,
    plotW, plotH,
  };
}

function linePath(points) {
  return points.map((point, i) => `${i ? "L" : "M"}${point[0].toFixed(2)},${point[1].toFixed(2)}`).join(" ");
}

function areaPath(top, bottom) {
  if (!top.length) return "";
  const forward = top.map((point, i) => `${i ? "L" : "M"}${point[0].toFixed(2)},${point[1].toFixed(2)}`).join(" ");
  const reverse = [...bottom].reverse().map(point => `L${point[0].toFixed(2)},${point[1].toFixed(2)}`).join(" ");
  return `${forward} ${reverse} Z`;
}

function seededGenerator(seed) {
  let value = Number(seed) >>> 0;
  return () => {
    value += 0x6D2B79F5;
    let mixed = value;
    mixed = Math.imul(mixed ^ mixed >>> 15, mixed | 1);
    mixed ^= mixed + Math.imul(mixed ^ mixed >>> 7, mixed | 61);
    return ((mixed ^ mixed >>> 14) >>> 0) / 4294967296;
  };
}

function numericQuantile(values, probability) {
  const clean = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!clean.length) return null;
  const position = clamp(Number(probability), 0, 1) * (clean.length - 1);
  const lower = Math.floor(position), upper = Math.ceil(position);
  if (lower === upper) return clean[lower];
  return clean[lower] + (clean[upper] - clean[lower]) * (position - lower);
}

function rankForScores(scores, selectedIndex) {
  const selected = Number(scores[selectedIndex]);
  if (!Number.isFinite(selected)) return null;
  return 1 + scores.reduce((count, score, index) => (
    index !== selectedIndex && Number.isFinite(Number(score)) && Number(score) > selected ? count + 1 : count
  ), 0);
}

function forecastWindowLength(mode, available) {
  const requested = {"last-5": 5, "last-10": 10, "last-20": 20}[mode];
  return requested ? Math.min(requested, available) : available;
}

function completeRoundVectors(race, end, mode) {
  const teams = race?.series || [];
  const safeEnd = Math.max(0, Math.min(Number(end) || 0, ...teams.map(row => row.rounds?.length || 0)));
  const length = forecastWindowLength(mode, safeEnd);
  const start = Math.max(0, safeEnd - length);
  const rows = [];
  for (let index = start; index < safeEnd; index++) {
    const values = teams.map(team => Number(team.rounds?.[index]));
    if (values.every(Number.isFinite)) rows.push({index, values});
  }
  return rows;
}

function simulateTournamentFinish(race, options = {}) {
  const teams = race?.series?.map(row => row.team) || [];
  const oasisIndex = teams.indexOf("Oasis");
  const played = Math.min(race?.gameIds?.length || 0, ...((race?.series || []).map(row => row.rounds?.length || 0)));
  const latestGame = played ? Number(race.gameIds[played - 1]) : 0;
  const remaining = Math.max(0, 100 - latestGame);
  const vectors = completeRoundVectors(race, played, options.window || "all");
  if (oasisIndex < 0 || !played || !vectors.length) {
    return {available: false, reason: "A complete Oasis race history is unavailable."};
  }
  const current = race.series.map(team => {
    const cumulative = Number(team.scores?.[played - 1]);
    return Number.isFinite(cumulative)
      ? cumulative
      : team.rounds.slice(0, played).reduce((sum, value) => sum + safeNumber(value), 0);
  });
  const runs = clamp(Math.trunc(Number(options.runs) || 5000), 100, 20000);
  const seed = clamp(Math.trunc(Number(options.seed) || 1), 1, 2147483646);
  const edge = clamp(Number(options.edge) || 0, -100000, 100000);
  const rng = seededGenerator(seed);
  const pathSamples = Array.from({length: remaining + 1}, () => []);
  const finalScores = [];
  const rankCounts = Array(teams.length).fill(0);
  const aboveCounts = Array(teams.length).fill(0);
  const requiredTargets = [1, 3, 5, 10];
  const requiredEdges = Object.fromEntries(requiredTargets.map(target => [target, []]));
  const sampledVectors = Array(vectors.length).fill(0);
  let rankTotal = 0;
  for (let run = 0; run < runs; run++) {
    const totals = [...current];
    pathSamples[0].push(totals[oasisIndex]);
    for (let step = 1; step <= remaining; step++) {
      const vectorIndex = Math.min(vectors.length - 1, Math.floor(rng() * vectors.length));
      sampledVectors[vectorIndex] += 1;
      const vector = vectors[vectorIndex].values;
      for (let teamIndex = 0; teamIndex < teams.length; teamIndex++) totals[teamIndex] += vector[teamIndex];
      totals[oasisIndex] += edge;
      pathSamples[step].push(totals[oasisIndex]);
    }
    const finalRank = rankForScores(totals, oasisIndex);
    rankCounts[finalRank - 1] += 1;
    rankTotal += finalRank;
    finalScores.push(totals[oasisIndex]);
    teams.forEach((_, index) => {
      if (index !== oasisIndex && totals[oasisIndex] > totals[index]) aboveCounts[index] += 1;
    });
    const baseOasis = totals[oasisIndex] - edge * remaining;
    const opponents = totals.filter((_, index) => index !== oasisIndex).sort((a, b) => b - a);
    requiredTargets.forEach(target => {
      const threshold = opponents[target - 1];
      const totalGap = Number.isFinite(threshold) ? Math.max(0, threshold - baseOasis + .01) : 0;
      requiredEdges[target].push(remaining ? totalGap / remaining : 0);
    });
  }
  const cone = pathSamples.map((samples, step) => ({
    game: latestGame + step,
    p10: numericQuantile(samples, .10), p25: numericQuantile(samples, .25),
    p50: numericQuantile(samples, .50), p75: numericQuantile(samples, .75),
    p90: numericQuantile(samples, .90),
  }));
  const distribution = rankCounts.map((paths, index) => ({rank: index + 1, paths, probability: paths / runs}));
  const currentRanks = current.map((_, index) => rankForScores(current, index));
  const rivals = teams.map((team, index) => ({
    team, currentRank: currentRanks[index], pathsAbove: index === oasisIndex ? runs : aboveCounts[index],
    probabilityAbove: index === oasisIndex ? 1 : aboveCounts[index] / runs,
    currentScore: current[index],
  })).filter(row => row.team !== "Oasis").sort((a, b) => a.currentRank - b.currentRank);
  const edgeRequirements = Object.fromEntries(requiredTargets.map(target => [target, {
    p50: numericQuantile(requiredEdges[target], .50),
    p90: numericQuantile(requiredEdges[target], .90),
  }]));
  return {
    available: true, teams, oasisIndex, played, latestGame, remaining, runs, seed, edge,
    window: options.window || "all", vectors: vectors.length,
    vectorGames: vectors.map(row => Number(race.gameIds[row.index])),
    sampledVectorCounts: sampledVectors,
    currentScore: current[oasisIndex], currentRank: currentRanks[oasisIndex],
    cone, distribution, rivals, edgeRequirements,
    expectedRank: rankTotal / runs,
    winProbability: distribution[0]?.probability || 0,
    podiumProbability: distribution.slice(0, 3).reduce((sum, row) => sum + row.probability, 0),
    topFiveProbability: distribution.slice(0, 5).reduce((sum, row) => sum + row.probability, 0),
    finalP10: numericQuantile(finalScores, .10), finalP50: numericQuantile(finalScores, .50),
    finalP90: numericQuantile(finalScores, .90),
    monteCarloMargin95: 1.96 * .5 / Math.sqrt(runs),
    sampledRoundVectors: runs * remaining,
  };
}

function walkForwardTournament(race, options = {}) {
  const teams = race?.series?.map(row => row.team) || [];
  const oasisIndex = teams.indexOf("Oasis");
  const played = Math.min(race?.gameIds?.length || 0, ...((race?.series || []).map(row => row.rounds?.length || 0)));
  if (oasisIndex < 0 || played < 7) return {available: false, rows: []};
  const rows = [];
  for (let nextIndex = 6; nextIndex < played; nextIndex++) {
    const history = completeRoundVectors(race, nextIndex, options.window || "all");
    if (history.length < 5) continue;
    const current = race.series.map(team => Number(team.scores[nextIndex - 1]));
    const actual = race.series.map(team => Number(team.scores[nextIndex]));
    if (![...current, ...actual].every(Number.isFinite)) continue;
    const currentRank = rankForScores(current, oasisIndex);
    const actualRank = rankForScores(actual, oasisIndex);
    const candidateRanks = history.map(row => rankForScores(
      current.map((score, index) => score + row.values[index]), oasisIndex,
    ));
    const improvementProbability = candidateRanks.filter(rank => rank < currentRank).length / candidateRanks.length;
    const improved = actualRank < currentRank;
    const oasisHistory = history.map(row => row.values[oasisIndex]);
    const actualRound = Number(race.series[oasisIndex].rounds[nextIndex]);
    const p10 = numericQuantile(oasisHistory, .10), p50 = numericQuantile(oasisHistory, .50), p90 = numericQuantile(oasisHistory, .90);
    rows.push({
      game: Number(race.gameIds[nextIndex]), samples: history.length,
      p10, p50, p90, actualRound,
      intervalHit: actualRound >= p10 && actualRound <= p90,
      absoluteMedianError: Math.abs(actualRound - p50),
      currentRank, actualRank, improvementProbability, improved,
      brier: (improvementProbability - Number(improved)) ** 2,
    });
  }
  if (!rows.length) return {available: false, rows};
  const prevalence = rows.filter(row => row.improved).length / rows.length;
  const brier = rows.reduce((sum, row) => sum + row.brier, 0) / rows.length;
  const baselineBrier = rows.reduce((sum, row) => sum + (prevalence - Number(row.improved)) ** 2, 0) / rows.length;
  return {
    available: true, rows, predictions: rows.length,
    intervalHits: rows.filter(row => row.intervalHit).length,
    intervalCoverage: rows.filter(row => row.intervalHit).length / rows.length,
    medianAbsoluteError: medianNumber(rows.map(row => row.absoluteMedianError)),
    brier, baselineBrier,
    brierSkill: baselineBrier > 0 ? 1 - brier / baselineBrier : null,
    improvementPrevalence: prevalence,
    historicalVectorUses: rows.reduce((sum, row) => sum + row.samples, 0),
  };
}

function raceAt(index) {
  const race = state.overview?.race;
  if (!race?.series?.length) return;
  state.raceIndex = clamp(index, 0, race.gameIds.length - 1);
  const gameId = race.gameIds[state.raceIndex];
  $("#race-game").textContent = gameId;
  $("#race-progress").textContent = `${gameId} / 100`;
  $("#race-slider").value = String(state.raceIndex);
  $("#race-subtitle").textContent = `Positions after game ${gameId} · ${race.teamCount} teams · click a spike for its round`;
  renderRaceChart();
  renderRaceRanks();
  renderRaceKpis();
  renderRaceTable();
}

function renderRaceChart() {
  const host = $("#race-chart");
  clear(host);
  const race = state.overview.race;
  const count = state.raceIndex + 1;
  const width = 1280, height = 510;
  const margin = {top: 26, right: 128, bottom: 44, left: 88};
  const visibleValues = race.series.flatMap(series => series.scores.slice(0, count));
  let min = Math.min(0, ...visibleValues), max = Math.max(0, ...visibleValues);
  const pad = (max - min || 1) * .09;
  min -= pad; max += pad;
  const svg = svgRoot(width, height, `Cumulative tournament scores through game ${race.gameIds[state.raceIndex]}`);
  const scale = chartScaffold(svg, width, height, margin, min, max, 6);
  const zeroY = scale.y(0);
  svg.append(svgElement("line", {x1: margin.left, y1: zeroY, x2: width - margin.right, y2: zeroY, stroke: colors.muted, "stroke-width": 1.2}));

  const ordered = [...race.series].sort((a, b) => (a.team === "Oasis") - (b.team === "Oasis"));
  ordered.forEach((series, order) => {
    const oasis = series.team === "Oasis";
    const stroke = oasis ? colors.cyan : palette[order % palette.length];
    const points = series.scores.slice(0, count).map((value, i) => [scale.x(i, count), scale.y(value)]);
    const path = svgElement("path", {
      d: linePath(points), fill: "none", stroke,
      "stroke-width": oasis ? 3.2 : 1.2, "stroke-opacity": oasis ? 1 : .48,
      "stroke-linecap": "round", "stroke-linejoin": "round",
    });
    addTooltip(path, () => [series.team, `Game ${race.gameIds[state.raceIndex]} · ${formatCurrency(series.scores[state.raceIndex])}`]);
    svg.append(path);
    const abs = series.rounds.slice(0, count).map(Math.abs).sort((a, b) => a - b);
    const spikeCut = abs[Math.floor(abs.length * .94)] || Infinity;
    series.rounds.slice(0, count).forEach((round, i) => {
      if (Math.abs(round) < spikeCut || Math.abs(round) < 5000) return;
      const dot = svgElement("circle", {
        cx: scale.x(i, count), cy: scale.y(series.scores[i]), r: oasis ? 4.5 : 3,
        fill: stroke, "fill-opacity": oasis ? 1 : .7, class: "interactive", tabindex: 0,
      });
      addTooltip(dot, [series.team, `Game ${race.gameIds[i]} · round ${signed(round)}`, `Cumulative ${formatCurrency(series.scores[i])}`]);
      dot.addEventListener("click", () => selectGame(race.gameIds[i], {scroll: true}));
      svg.append(dot);
    });
  });

  const current = race.series.map(series => ({...series, current: series.scores[state.raceIndex]}))
    .sort((a, b) => b.current - a.current);
  const labels = current.filter((row, index) => index < 6 || row.team === "Oasis");
  const used = [];
  labels.forEach(row => {
    let y = scale.y(row.current);
    while (used.some(other => Math.abs(other - y) < 14)) y += 14;
    used.push(y);
    const oasis = row.team === "Oasis";
    svg.append(svgElement("line", {x1: width - margin.right, y1: scale.y(row.current), x2: width - margin.right + 12, y2: y, stroke: oasis ? colors.cyan : colors.muted, "stroke-width": oasis ? 2 : 1}));
    svg.append(svgElement("text", {x: width - margin.right + 17, y: y + 3, fill: oasis ? colors.cyan : "#98a4ad", "font-size": oasis ? 11 : 9, "font-family": "var(--mono)"}, row.team));
  });
  host.append(svg);
}

function renderRaceRanks() {
  const host = $("#race-rank-strip");
  clear(host);
  const ranked = state.overview.race.series
    .map(series => ({team: series.team, score: series.scores[state.raceIndex]}))
    .sort((a, b) => b.score - a.score);
  ranked.forEach((row, index) => {
    const chip = element("span", {class: `rank-chip ${row.team === "Oasis" ? "oasis" : ""}`}, [
      element("strong", {text: String(index + 1).padStart(2, "0")}),
      element("span", {text: row.team}),
      element("span", {text: formatCurrency(row.score, true)}),
    ]);
    host.append(chip);
  });
}

function renderRaceKpis() {
  const host = $("#hero-kpis");
  clear(host);
  const ranked = state.overview.race.series
    .map(series => ({...series, score: series.scores[state.raceIndex]}))
    .sort((a, b) => b.score - a.score);
  const oasisRank = ranked.findIndex(row => row.team === "Oasis") + 1;
  const oasis = ranked.find(row => row.team === "Oasis");
  const leader = ranked[0];
  const stats = [
    ["Oasis rank", `${oasisRank} / ${ranked.length}`, `through game ${state.overview.race.gameIds[state.raceIndex]}`],
    ["Oasis score", signed(oasis?.score || 0), "cumulative EUR"],
    ["Gap to leader", formatCurrency(Math.max(0, (leader?.score || 0) - (oasis?.score || 0)), true), leader?.team || "—"],
    ["Leader spike share", formatPercent(leader?.top3AbsoluteShare || 0), `median ${formatCurrency(leader?.medianRound || 0, true)} · mean ${formatCurrency(leader?.meanRound || 0, true)}`],
  ];
  stats.forEach(([label, value, note]) => host.append(element("div", {class: "hero-stat"}, [
    element("span", {text: label}), element("strong", {text: value}), element("small", {text: note}),
  ])));
}

function renderRaceTable() {
  const body = $("#race-data-table");
  if (!body || !state.overview) return;
  clear(body);
  const ranked = state.overview.race.series
    .map(series => ({...series, score: series.scores[state.raceIndex], round: series.rounds[state.raceIndex]}))
    .sort((a, b) => b.score - a.score);
  ranked.forEach((row, index) => body.append(element("tr", {}, [
    element("td", {text: index + 1}), element("td", {text: row.team}),
    element("td", {class: "money", text: formatCurrency(row.score)}),
    element("td", {class: `money ${row.round >= 0 ? "positive" : "negative"}`, text: signed(row.round)}),
    element("td", {class: "money", text: formatCurrency(row.medianRound)}),
    element("td", {class: "money", text: formatCurrency(row.meanRound)}),
  ])));
}

function forecastTargetLabel(target) {
  return ({1: "win", 3: "podium", 5: "top five", 10: "top ten"})[Number(target)] || `top ${target}`;
}

function renderForecastCone(result) {
  const host = $("#forecast-cone"); clear(host);
  const table = $("#forecast-cone-table"); clear(table);
  if (!result?.available) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: result?.reason || "No complete round vectors are available."})]));
    return;
  }
  const oasis = state.overview.race.series.find(row => row.team === "Oasis");
  const historyStart = Math.max(0, result.played - 10);
  const history = oasis.scores.slice(historyStart, result.played).map((score, offset) => ({
    game: Number(state.overview.race.gameIds[historyStart + offset]), score: Number(score),
  }));
  const allValues = [...history.map(row => row.score), ...result.cone.flatMap(row => [row.p10, row.p90])].filter(Number.isFinite);
  let min = Math.min(0, ...allValues), max = Math.max(0, ...allValues);
  const pad = (max - min || 1) * .10; min -= pad; max += pad;
  const width = 1040, height = 430, margin = {left: 92, right: 38, top: 54, bottom: 55};
  const firstGame = history[0]?.game ?? result.latestGame;
  const x = game => margin.left + (Number(game) - firstGame) / (100 - firstGame || 1) * (width - margin.left - margin.right);
  const y = value => margin.top + (max - Number(value)) / (max - min || 1) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, `Oasis cumulative score through game ${result.latestGame} and bootstrap percentiles through game 100`);
  for (let tick = 0; tick <= 5; tick++) {
    const value = min + (max - min) * tick / 5;
    const yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 9, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true)));
  }
  const cone90Top = result.cone.map(row => [x(row.game), y(row.p90)]);
  const cone90Bottom = result.cone.map(row => [x(row.game), y(row.p10)]);
  const cone50Top = result.cone.map(row => [x(row.game), y(row.p75)]);
  const cone50Bottom = result.cone.map(row => [x(row.game), y(row.p25)]);
  svg.append(svgElement("path", {d: areaPath(cone90Top, cone90Bottom), fill: colors.violet, "fill-opacity": .10}));
  svg.append(svgElement("path", {d: areaPath(cone50Top, cone50Bottom), fill: colors.cyan, "fill-opacity": .18}));
  if (history.length) svg.append(svgElement("path", {d: linePath(history.map(row => [x(row.game), y(row.score)])), fill: "none", stroke: colors.muted, "stroke-width": 1.8, "stroke-linecap": "round"}));
  const medianPath = result.cone.map(row => [x(row.game), y(row.p50)]);
  svg.append(svgElement("path", {d: linePath(medianPath), fill: "none", stroke: colors.cyan, "stroke-width": 2.7, "stroke-linecap": "round", "stroke-dasharray": "6 5"}));
  const boundaryX = x(result.latestGame);
  svg.append(svgElement("line", {x1: boundaryX, y1: margin.top - 10, x2: boundaryX, y2: height - margin.bottom, stroke: colors.amber, "stroke-width": 1.2, "stroke-dasharray": "3 4"}));
  svg.append(svgElement("text", {x: boundaryX + 7, y: margin.top - 21, fill: colors.amber, "font-size": 9, "font-family": "var(--mono)"}, `OBSERVED → RESAMPLED · G${result.latestGame}`));
  for (let game = Math.ceil(firstGame / 10) * 10; game <= 100; game += 10) {
    svg.append(svgElement("text", {x: x(game), y: height - 24, class: "axis-label", "text-anchor": "middle"}, `G${game}`));
  }
  const last = result.cone.at(-1);
  [
    ["P90", last.p90, colors.violet], ["P50", last.p50, colors.cyan], ["P10", last.p10, colors.violet],
  ].forEach(([label, value, color]) => {
    const marker = svgElement("circle", {cx: x(100), cy: y(value), r: 4, fill: color, tabindex: 0, class: "interactive"});
    addTooltip(marker, [`${label} final cumulative`, formatCurrency(value), `${result.runs.toLocaleString()} bootstrap paths`]);
    svg.append(marker);
  });
  svg.append(svgElement("text", {x: margin.left, y: 20, class: "axis-label"}, "HISTORICAL CUMULATIVE · SOLID"));
  svg.append(svgElement("text", {x: margin.left + 190, y: 20, fill: colors.cyan, "font-size": 9, "font-family": "var(--mono)"}, "P50 · DASHED"));
  svg.append(svgElement("text", {x: margin.left + 290, y: 20, fill: colors.violet, "font-size": 9, "font-family": "var(--mono)"}, "P10–P90 / P25–P75 BANDS"));
  host.append(svg);
  result.cone.forEach(row => table.append(element("tr", {}, [
    element("td", {text: row.game}), element("td", {class: "money", text: formatCurrency(row.p10)}),
    element("td", {class: "money", text: formatCurrency(row.p25)}), element("td", {class: "money", text: formatCurrency(row.p50)}),
    element("td", {class: "money", text: formatCurrency(row.p75)}), element("td", {class: "money", text: formatCurrency(row.p90)}),
  ])));
}

function renderForecastRanks(result) {
  const host = $("#forecast-ranks"); clear(host);
  const body = $("#forecast-rank-table"); clear(body);
  if (!result?.available) return;
  const width = 620, height = 520, margin = {left: 62, right: 90, top: 34, bottom: 32};
  const rowHeight = (height - margin.top - margin.bottom) / result.distribution.length;
  const maxProbability = Math.max(.01, ...result.distribution.map(row => row.probability));
  const svg = svgRoot(width, height, "Oasis finish-rank bootstrap probability distribution");
  result.distribution.forEach((row, index) => {
    const y = margin.top + index * rowHeight;
    const barWidth = row.probability / maxProbability * (width - margin.left - margin.right);
    const tone = row.rank <= 3 ? colors.cyan : row.rank <= 5 ? colors.green : row.rank <= 10 ? colors.amber : colors.red;
    svg.append(svgElement("text", {x: margin.left - 12, y: y + rowHeight * .68, class: "axis-label", "text-anchor": "end"}, `R${row.rank}`));
    svg.append(svgElement("line", {x1: margin.left, y1: y + rowHeight, x2: width - margin.right, y2: y + rowHeight, class: "grid-line"}));
    const bar = svgElement("rect", {x: margin.left, y: y + 5, width: Math.max(0, barWidth), height: Math.max(3, rowHeight - 9), rx: 3, fill: tone, "fill-opacity": row.probability ? .76 : .12, tabindex: row.probability ? 0 : -1, class: row.probability ? "interactive" : ""});
    if (row.probability) addTooltip(bar, [`Finish rank ${row.rank}`, `${formatPercent(row.probability)} · ${formatNumber(row.paths)} paths`, `Denominator ${formatNumber(result.runs)} bootstrap paths`]);
    svg.append(bar);
    svg.append(svgElement("text", {x: width - margin.right + 10, y: y + rowHeight * .68, fill: row.probability ? tone : colors.muted, "font-size": 9, "font-family": "var(--mono)"}, formatPercent(row.probability)));
    body.append(element("tr", {}, [element("td", {text: row.rank}), element("td", {text: formatNumber(row.paths)}), element("td", {text: formatPercent(row.probability)})]));
  });
  host.append(svg);
}

function renderForecastRivals(result) {
  const host = $("#forecast-rivals"); clear(host);
  const body = $("#forecast-rival-table"); clear(body);
  if (!result?.available) return;
  result.rivals.forEach(row => {
    const meter = element("span", {class: "forecast-rival-meter", "aria-hidden": "true"});
    meter.style.setProperty("--probability", `${clamp(row.probabilityAbove, 0, 1) * 100}%`);
    host.append(element("div", {class: "forecast-rival-row"}, [
      element("span", {class: "forecast-rival-rank", text: `R${row.currentRank}`}),
      element("strong", {text: row.team}), meter,
      element("span", {class: row.probabilityAbove >= .5 ? "positive" : "negative", text: formatPercent(row.probabilityAbove)}),
    ]));
    body.append(element("tr", {}, [
      element("td", {text: row.team}), element("td", {text: row.currentRank}),
      element("td", {text: formatPercent(row.probabilityAbove)}), element("td", {text: `${formatNumber(row.pathsAbove)} / ${formatNumber(result.runs)}`}),
    ]));
  });
}

function renderForecastValidation(validation) {
  const kpis = $("#forecast-validation-kpis"); clear(kpis);
  const host = $("#forecast-validation-chart"); clear(host);
  const body = $("#forecast-validation-table"); clear(body);
  if (!validation?.available) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "At least seven complete rounds are required for walk-forward validation."})]));
    return;
  }
  const specs = [
    ["Temporal predictions", formatNumber(validation.predictions), `${formatNumber(validation.historicalVectorUses)} historical vector uses`],
    ["P10–P90 coverage", formatPercent(validation.intervalCoverage), `${validation.intervalHits} / ${validation.predictions} actual next-round scores`],
    ["Median absolute error", formatCurrency(validation.medianAbsoluteError, true), "actual round vs historical median · per predicted game"],
    ["Rank Brier score", formatNumber(validation.brier, 3), `baseline ${formatNumber(validation.baselineBrier, 3)} · skill ${validation.brierSkill === null ? "unknown" : formatPercent(validation.brierSkill)} · lower is better`],
  ];
  specs.forEach(([label, value, note]) => kpis.append(element("div", {class: "forecast-validation-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
  const rows = validation.rows.slice(-30);
  const values = rows.flatMap(row => [row.p10, row.p90, row.actualRound]);
  let min = Math.min(0, ...values), max = Math.max(0, ...values);
  const pad = (max - min || 1) * .10; min -= pad; max += pad;
  const width = 940, height = 360, margin = {left: 82, right: 26, top: 35, bottom: 50};
  const x = index => margin.left + (rows.length <= 1 ? 0 : index / (rows.length - 1)) * (width - margin.left - margin.right);
  const y = value => margin.top + (max - value) / (max - min || 1) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Strictly temporal one-round prediction intervals and actual Oasis round scores");
  for (let tick = 0; tick <= 4; tick++) {
    const value = min + (max - min) * tick / 4, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true)));
  }
  rows.forEach((row, index) => {
    const xx = x(index), hit = row.intervalHit;
    svg.append(svgElement("line", {x1: xx, y1: y(row.p10), x2: xx, y2: y(row.p90), stroke: hit ? colors.cyan : colors.red, "stroke-width": 2, "stroke-opacity": .45}));
    const dot = svgElement("circle", {cx: xx, cy: y(row.actualRound), r: hit ? 3.5 : 5, fill: hit ? colors.green : colors.red, tabindex: 0, class: "interactive"});
    addTooltip(dot, [`Predicted game ${row.game}`, `Actual ${signed(row.actualRound)} · ${hit ? "inside" : "outside"} P10–P90`, `History ${row.samples} complete rounds · median ${signed(row.p50)}`, `P(rank improves) ${formatPercent(row.improvementProbability)} · actual R${row.currentRank} → R${row.actualRank}`]);
    svg.append(dot);
    if (index % Math.max(1, Math.ceil(rows.length / 6)) === 0 || index === rows.length - 1) {
      svg.append(svgElement("text", {x: xx, y: height - 20, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    }
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, class: "axis-label"}, "WHISKER P10–P90 · DOT ACTUAL · RED = MISS"));
  host.append(svg);
  validation.rows.forEach(row => body.append(element("tr", {}, [
    element("td", {text: row.game}), element("td", {text: row.samples}),
    element("td", {class: "money", text: signed(row.p10)}), element("td", {class: "money", text: signed(row.p50)}),
    element("td", {class: "money", text: signed(row.p90)}), element("td", {class: `money ${row.intervalHit ? "positive" : "negative"}`, text: signed(row.actualRound)}),
    element("td", {text: formatPercent(row.improvementProbability)}), element("td", {text: `R${row.currentRank} → R${row.actualRank}${row.improved ? " · improved" : ""}`}),
  ])));
}

function renderFinishSimulator() {
  if (!state.overview?.race?.series?.length) return;
  $("#forecast-window").value = state.forecastWindow;
  $("#forecast-runs").value = String(state.forecastRuns);
  $("#forecast-seed").value = String(state.forecastSeed);
  $("#forecast-target").value = String(state.forecastTarget);
  $("#forecast-edge").value = String(state.forecastEdge);
  $("#forecast-edge-output").textContent = signed(state.forecastEdge);
  const result = simulateTournamentFinish(state.overview.race, {
    window: state.forecastWindow, runs: state.forecastRuns,
    seed: state.forecastSeed, edge: state.forecastEdge,
  });
  const validation = walkForwardTournament(state.overview.race, {window: state.forecastWindow});
  state.forecastResult = result;
  state.forecastValidation = validation;
  const kpis = $("#forecast-kpis"); clear(kpis);
  if (!result.available) {
    $("#forecast-status").textContent = "INSUFFICIENT COMPLETE HISTORY";
    $("#forecast-headline").textContent = "—";
    renderForecastCone(result); renderForecastRanks(result); renderForecastRivals(result); renderForecastValidation(validation);
    return;
  }
  const target = Number(state.forecastTarget);
  const targetProbability = result.distribution.slice(0, target).reduce((sum, row) => sum + row.probability, 0);
  const required = result.edgeRequirements[target];
  $("#forecast-status").textContent = `FROM GAME ${result.latestGame} · ${result.remaining} ROUNDS REMAIN`;
  $("#forecast-headline").textContent = `${formatPercent(targetProbability)} ${forecastTargetLabel(target)}`;
  $("#forecast-cone-denominator").textContent = `${formatNumber(result.runs)} paths · ${formatNumber(result.vectors)} joint vectors`;
  $("#forecast-rank-denominator").textContent = `${formatNumber(result.runs)} complete futures`;
  const specs = [
    ["Target probability", formatPercent(targetProbability), `${forecastTargetLabel(target)} · ${formatNumber(result.runs)} paths`, targetProbability >= .5 ? "positive" : "warning"],
    ["Expected finish", `R${formatNumber(result.expectedRank, 1)}`, `current R${result.currentRank} · one rank per simulated future`, ""],
    ["Median final score", signed(result.finalP50), `P10 ${formatCurrency(result.finalP10, true)} · P90 ${formatCurrency(result.finalP90, true)}`, result.finalP50 >= result.currentScore ? "positive" : "negative"],
    ["P50 edge required", signed(required?.p50 || 0), `${forecastTargetLabel(target)} · extra Oasis score per remaining round from zero-edge baseline`, "cyan"],
    ["P90 edge required", signed(required?.p90 || 0), `sufficient in 90% of resampled futures · descriptive threshold`, "warning"],
    ["Monte Carlo precision", `±${formatPercent(result.monteCarloMargin95)}`, `worst-case 95% sampling margin · seed ${result.seed}`, ""],
  ];
  specs.forEach(([label, value, note, tone]) => kpis.append(metricCard(label, value, note, tone)));
  renderForecastCone(result);
  renderForecastRanks(result);
  renderForecastRivals(result);
  renderForecastValidation(validation);
}

async function copyForecastReceipt() {
  const result = state.forecastResult;
  const validation = state.forecastValidation;
  if (!result?.available) {
    toast("No complete finish simulation is available to copy.");
    return;
  }
  const target = Number(state.forecastTarget);
  const targetProbability = result.distribution.slice(0, target).reduce((sum, row) => sum + row.probability, 0);
  const receipt = {
    version: 1,
    status: "offline-descriptive-scenario-only",
    materializedAt: state.overview.generatedAt,
    evidence: {
      throughGame: result.latestGame,
      remainingGames: result.remaining,
      teamCount: result.teams.length,
      completeHistoricalRoundVectors: result.vectors,
      window: result.window,
    },
    method: {
      unit: "one complete simultaneous all-team historical round vector",
      horizonGame: 100,
      paths: result.runs,
      seed: result.seed,
      oasisScoreEdgePerRemainingRound: result.edge,
      worstCaseMonteCarloMargin95: result.monteCarloMargin95,
    },
    target: {
      rankAtOrAbove: target,
      probability: targetProbability,
      p50RequiredOasisEdgePerRound: result.edgeRequirements[target]?.p50 ?? null,
      p90RequiredOasisEdgePerRound: result.edgeRequirements[target]?.p90 ?? null,
    },
    result: {
      currentRank: result.currentRank,
      expectedRank: result.expectedRank,
      winProbability: result.winProbability,
      podiumProbability: result.podiumProbability,
      topFiveProbability: result.topFiveProbability,
      finalCumulativeScoreP10: result.finalP10,
      finalCumulativeScoreP50: result.finalP50,
      finalCumulativeScoreP90: result.finalP90,
      rankDistribution: result.distribution.map(row => ({rank: row.rank, paths: row.paths, probability: row.probability})),
    },
    temporalAudit: validation?.available ? {
      predictions: validation.predictions,
      historicalVectorUses: validation.historicalVectorUses,
      p10P90Coverage: validation.intervalCoverage,
      medianAbsoluteRoundScoreError: validation.medianAbsoluteError,
      rankImprovementBrier: validation.brier,
      constantRateBrier: validation.baselineBrier,
    } : {available: false},
    boundaries: [
      "resampling stress test, not a future-performance claim",
      "selected past window is assumed representative",
      "does not model strategy changes, future case mix, or opponent adaptation",
      "Oasis edge is a hypothetical score adjustment and is never submitted",
    ],
  };
  try {
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    toast("Claim-free finish-simulation receipt copied with seed, denominators, audit, and caveats.");
  } catch (error) {
    toast(`Simulation receipt could not be copied: ${error.message}`);
  }
}

function robustnessSpec() {
  const specs = {
    medianPaceTotal: {label: "Median pace", note: "median round × games played"},
    winsorizedTotal: {label: "Winsorised", note: "each team capped at its own P10/P90"},
    withoutTop3Positive: {label: "Remove 3 best", note: "three largest positive rounds removed"},
    withoutWorst3Negative: {label: "Remove 3 worst", note: "three most negative rounds removed"},
  };
  return specs[state.robustnessMode] || specs.medianPaceTotal;
}

function renderRobustness() {
  if (!state.overview) return;
  const field = state.robustnessMode;
  const spec = robustnessSpec();
  $$('[data-robustness]').forEach(button => {
    const active = button.dataset.robustness === field;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const official = [...state.overview.race.series].sort((a, b) => b.total - a.total);
  const adjusted = [...state.overview.race.series].sort((a, b) => safeNumber(b[field]) - safeNumber(a[field]));
  const officialRank = new Map(official.map((row, index) => [row.team, index + 1]));
  const adjustedRank = new Map(adjusted.map((row, index) => [row.team, index + 1]));
  const oasis = official.find(row => row.team === "Oasis");
  const adjustedLeader = adjusted[0];
  const oasisRankDelta = adjustedRank.get("Oasis") - officialRank.get("Oasis");
  const oasisRankMovement = oasisRankDelta === 0
    ? "rank unchanged under lens"
    : `${Math.abs(oasisRankDelta)} ${Math.abs(oasisRankDelta) === 1 ? "place" : "places"} ${oasisRankDelta < 0 ? "higher" : "lower"} under lens`;
  const summary = $("#robustness-summary"); clear(summary);
  const specs = [
    ["Active lens", spec.label, spec.note],
    ["Oasis rank", `${officialRank.get("Oasis")} → ${adjustedRank.get("Oasis")}`, oasisRankMovement],
    ["Oasis score delta", signed(safeNumber(oasis?.[field]) - safeNumber(oasis?.total)), `${formatCurrency(oasis?.total)} official → ${formatCurrency(oasis?.[field])}`],
    ["Adjusted leader", adjustedLeader?.team || "—", adjustedLeader ? `${formatCurrency(adjustedLeader[field], true)} · official rank ${officialRank.get(adjustedLeader.team)}` : "no score data"],
  ];
  specs.forEach(([label, value, note]) => summary.append(element("div", {class: "robustness-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));

  const host = $("#robustness-chart"); clear(host);
  const values = official.flatMap(row => [row.total, safeNumber(row[field])]);
  const rawMin = Math.min(0, ...values), rawMax = Math.max(0, ...values);
  const padding = (rawMax - rawMin || 1) * .08;
  const min = rawMin - padding, max = rawMax + padding;
  const width = 1180, rowHeight = 39, height = 82 + official.length * rowHeight;
  const margin = {left: 170, right: 105, top: 54, bottom: 28};
  const plotW = width - margin.left - margin.right;
  const x = value => margin.left + (value - min) / (max - min || 1) * plotW;
  const svg = svgRoot(width, height, `Official standings against ${spec.label.toLowerCase()} adjusted standings`);
  for (let tick = 0; tick <= 5; tick++) {
    const value = min + (max - min) * tick / 5;
    const position = x(value);
    svg.append(svgElement("line", {x1: position, y1: margin.top - 16, x2: position, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("text", {x: position, y: 22, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true)));
  }
  svg.append(svgElement("circle", {cx: margin.left, cy: 39, r: 4, fill: colors.cyan}));
  svg.append(svgElement("text", {x: margin.left + 10, y: 42, class: "axis-label"}, "OFFICIAL · CIRCLE"));
  svg.append(svgElement("rect", {x: margin.left + 112, y: 35, width: 8, height: 8, fill: colors.amber, transform: `rotate(45 ${margin.left + 116} 39)`}));
  svg.append(svgElement("text", {x: margin.left + 127, y: 42, class: "axis-label"}, `${spec.label.toUpperCase()} · DIAMOND`));
  official.forEach((row, index) => {
    const y = margin.top + index * rowHeight + rowHeight / 2;
    const officialX = x(row.total), adjustedX = x(safeNumber(row[field]));
    const oasisRow = row.team === "Oasis";
    svg.append(svgElement("line", {x1: margin.left, y1: y + rowHeight / 2, x2: width - margin.right, y2: y + rowHeight / 2, stroke: colors.grid}));
    svg.append(svgElement("text", {x: margin.left - 13, y: y + 3, fill: oasisRow ? colors.cyan : "#98a4ad", "font-family": "var(--mono)", "font-size": oasisRow ? 11 : 9, "text-anchor": "end"}, `${String(index + 1).padStart(2, "0")}  ${row.team}`));
    svg.append(svgElement("line", {x1: Math.min(officialX, adjustedX), y1: y, x2: Math.max(officialX, adjustedX), y2: y, stroke: oasisRow ? colors.cyan : colors.muted, "stroke-width": oasisRow ? 2.2 : 1.2, "stroke-opacity": oasisRow ? .8 : .5}));
    const actual = svgElement("circle", {cx: officialX, cy: y, r: oasisRow ? 5 : 4, fill: colors.cyan, tabindex: 0, class: "interactive", role: "img", "aria-label": `${row.team}, official rank ${officialRank.get(row.team)}, ${formatCurrency(row.total)}`});
    addTooltip(actual, [row.team, `Official rank ${officialRank.get(row.team)} · ${formatCurrency(row.total)}`, `Best round game ${row.bestRound?.game ?? "unknown"} · ${signed(row.bestRound?.score || 0)}`, `Top-three positive share ${formatPercent(row.positiveTop3Share)}`]);
    svg.append(actual);
    const diamond = svgElement("rect", {x: adjustedX - 4, y: y - 4, width: 8, height: 8, fill: colors.amber, transform: `rotate(45 ${adjustedX} ${y})`, tabindex: 0, class: "interactive", role: "img", "aria-label": `${row.team}, ${spec.label.toLowerCase()} rank ${adjustedRank.get(row.team)}, ${formatCurrency(row[field])}`});
    addTooltip(diamond, [row.team, `${spec.label} rank ${adjustedRank.get(row.team)} · ${formatCurrency(row[field])}`, `Difference from official ${signed(row[field] - row.total)}`, spec.note]);
    svg.append(diamond);
    svg.append(svgElement("text", {x: width - margin.right + 10, y: y + 3, fill: adjustedRank.get(row.team) < officialRank.get(row.team) ? colors.green : adjustedRank.get(row.team) > officialRank.get(row.team) ? colors.red : colors.muted, "font-family": "var(--mono)", "font-size": 9}, `R${adjustedRank.get(row.team)}  ${signed(row[field] - row.total)}`));
  });
  host.append(svg);

  const body = $("#robustness-data-table"); clear(body);
  official.forEach(row => body.append(element("tr", {}, [
    element("td", {text: officialRank.get(row.team)}), element("td", {text: adjustedRank.get(row.team)}),
    element("td", {text: row.team}), element("td", {class: "money", text: formatCurrency(row.total)}),
    element("td", {class: "money", text: formatCurrency(row[field])}),
    element("td", {class: `money ${row[field] - row.total >= 0 ? "positive" : "negative"}`, text: signed(row[field] - row.total)}),
    element("td", {text: formatPercent(row.positiveTop3Share)}),
  ])));
}

function renderMarketTape() {
  const host = $("#market-tape"); clear(host);
  const briefing = state.overview.intelligence.briefing;
  const latest = state.overview.trends.economics.at(-1);
  const items = [
    ["RANK", `${briefing.currentRank} / 17`, briefing.rankChange5 > 0 ? "good" : briefing.rankChange5 < 0 ? "bad" : ""],
    ["SCORE", signed(briefing.score), briefing.score >= 0 ? "good" : "bad"],
    ["LEADER GAP", formatCurrency(briefing.gapToLeader, true), "bad"],
    ["5-GAME TAPE", signed(briefing.momentum5), briefing.momentum5 >= 0 ? "good" : "bad"],
    ["LATEST", latest ? signed(latest.net) : "—", latest?.net >= 0 ? "good" : "bad"],
    ["PROVEN FOREGONE", formatCurrency(briefing.provenForegone, true), "bad"],
    ["HIDDEN CHARGES", formatNumber(briefing.hiddenCharges), "warn"],
    ["BRACKETS", formatNumber(state.overview.thresholdCount), ""],
  ];
  const makeTrack = hidden => {
    const track = element("div", {class: "tape-track", "aria-hidden": hidden ? "true" : "false"});
    items.forEach(([label, value, tone]) => track.append(element("span", {class: "tape-item", dataset: {tone}}, [
      element("span", {text: label}), element("strong", {text: value}),
    ])));
    return track;
  };
  host.append(makeTrack(false), makeTrack(true));
}

function renderBriefing() {
  const host = $("#briefing-grid"); clear(host);
  const briefing = state.overview.intelligence.briefing;
  const economics = state.overview.trends.economics;
  const stream = state.overview.trends.decisionStream;
  const specs = [
    {
      label: "Position pressure", value: `${briefing.currentRank} / 17`,
      note: `${briefing.rankChange5 >= 0 ? "+" : ""}${briefing.rankChange5} ranks over five games · ${formatCurrency(briefing.gapToLeader, true)} to ${briefing.leader}`,
      color: briefing.rankChange5 >= 0 ? colors.cyan : colors.red,
      spark: state.overview.intelligence.rankDynamics.teams.find(row => row.team === "Oasis")?.ranks.map(value => -value),
    },
    {
      label: "Five-game momentum", value: signed(briefing.momentum5),
      note: `${signed(briefing.momentumDelta)} versus the preceding five-game block`,
      color: briefing.momentum5 >= 0 ? colors.green : colors.red,
      spark: economics.map(row => row.net).slice(-12),
    },
    {
      label: "Proven income foregone", value: formatCurrency(briefing.provenForegone, true),
      note: `${briefing.provenForegoneItems} undercharged items · fixed 16-reviewer denominator`,
      color: colors.red,
      spark: state.overview.trends.concentration.items.slice(0, 12).map(row => row.foregoneLowerBound).reverse(),
    },
    {
      label: "Error-cost asymmetry", value: briefing.errorCostRatio ? `${formatNumber(briefing.errorCostRatio, 1)}×` : "—",
      note: `${formatCurrency(briefing.fairRejectionCost, true)} fair-rejection cost vs ${formatCurrency(briefing.fraudAcceptanceCost, true)} accepted-fraud cost`,
      color: colors.amber,
      spark: stream.slice(-12).map(row => row.rejectFair.euros - row.acceptFraud.euros),
    },
  ];
  specs.forEach(spec => {
    const card = element("article", {class: "briefing-card"}, [
      element("span", {text: spec.label}), element("strong", {text: spec.value}), element("small", {text: spec.note}),
      sparkline(spec.spark, spec.color),
    ]);
    card.style.setProperty("--brief-color", spec.color);
    host.append(card);
  });
  renderMarketTape();
}

function renderRankHeatmap() {
  const host = $("#rank-heatmap"); clear(host);
  const data = state.overview.intelligence.rankDynamics;
  const games = data.gameIds;
  if (!games.length) return;
  const width = Math.max(1040, games.length * 17 + 160);
  const rowH = 25, margin = {left: 116, right: 40, top: 35, bottom: 48};
  const height = margin.top + data.teams.length * rowH + margin.bottom;
  const plotW = width - margin.left - margin.right, cellW = plotW / games.length;
  const svg = svgRoot(width, height, "Rank of every team in every played game");
  data.teams.forEach((team, rowIndex) => {
    const y = margin.top + rowIndex * rowH;
    svg.append(svgElement("text", {x: margin.left - 9, y: y + rowH * .67, fill: team.team === "Oasis" ? colors.cyan : "#98a4ad", "font-size": team.team === "Oasis" ? 10 : 8.5, "font-family": "monospace", "text-anchor": "end"}, team.team));
    team.ranks.forEach((rank, index) => {
      const x = margin.left + index * cellW;
      const goodness = 1 - (rank - 1) / 16;
      const fill = team.team === "Oasis" ? colors.cyan : goodness > .66 ? colors.green : goodness > .33 ? colors.blue : colors.red;
      const rect = svgElement("rect", {x, y: y + 1, width: Math.max(1, cellW - .7), height: rowH - 2, fill, "fill-opacity": team.team === "Oasis" ? .2 + goodness * .65 : .06 + goodness * .36, tabindex: 0, class: "interactive"});
      addTooltip(rect, [team.team, `Game ${games[index]} · rank ${rank} / 17`, `Score ${formatCurrency(state.overview.race.series.find(row => row.team === team.team).scores[index])}`, `Five-game momentum ${signed(team.momentum5)}`]);
      rect.addEventListener("click", () => selectGame(games[index], {scroll: true}));
      svg.append(rect);
      if (cellW >= 13 || team.team === "Oasis") svg.append(svgElement("text", {x: x + cellW / 2, y: y + rowH * .66, fill: team.team === "Oasis" ? "#061110" : "#d5d8d9", "fill-opacity": team.team === "Oasis" ? .9 : .58, "font-size": Math.min(8, cellW * .58), "font-family": "monospace", "text-anchor": "middle", "pointer-events": "none"}, rank));
    });
  });
  [0, Math.floor(games.length / 2), games.length - 1].forEach(index => svg.append(svgElement("text", {x: margin.left + cellW * (index + .5), y: height - 23, class: "axis-label", "text-anchor": "middle"}, `G${games[index]}`)));
  host.append(svg);
}

function anomalyLabel(row) {
  const labels = {
    undercharge: "Proven issuer undercharge",
    overcharge: "Proven issuer overcharge",
    "fair-rejection-cost": "Fair-rejection cost spike",
    "round-shock": "Oasis round shock",
  };
  return labels[row.type] || row.type;
}

function renderAnomalies() {
  const host = $("#anomaly-list"); clear(host);
  let rows = state.overview.intelligence.anomalies;
  if (state.anomalyCriticalOnly) rows = rows.filter(row => row.severity === "critical");
  rows.slice(0, 18).forEach(row => {
    const value = row.unit.startsWith("EUR") ? (row.magnitude >= 0 ? formatCurrency(row.magnitude, true) : signed(row.magnitude)) : `${formatNumber(row.magnitude, 2)}×`;
    const button = element("button", {type: "button", class: `anomaly-row ${row.severity}`}, [
      element("span", {class: "anomaly-severity", "aria-hidden": "true"}),
      element("span", {}, [element("strong", {text: anomalyLabel(row)}), element("small", {text: `game ${row.game}${row.item ? ` item ${row.item}` : ""} · ${row.unit}`})]),
      element("span", {class: "anomaly-value", text: value}),
    ]);
    button.addEventListener("click", async () => {
      await selectGame(row.game);
      if (row.item) await selectItem(row.item, {scroll: true});
      else $("#game").scrollIntoView({behavior: "smooth"});
    });
    host.append(button);
  });
  if (!rows.length) host.append(element("div", {class: "empty-state"}, [element("p", {text: "No anomalies match this evidence filter."})]));
  $("#anomaly-filter").textContent = state.anomalyCriticalOnly ? "Show all" : "Critical only";
}

function startRace() {
  if (state.raceTimer) {
    clearInterval(state.raceTimer);
    state.raceTimer = null;
    $("#race-play").textContent = "Play race";
    return;
  }
  stopReplay();
  stopMarketReplay();
  if (state.raceIndex >= state.overview.race.gameIds.length - 1) raceAt(0);
  $("#race-play").textContent = "Pause";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  state.raceTimer = setInterval(() => {
    if (state.raceIndex >= state.overview.race.gameIds.length - 1) {
      clearInterval(state.raceTimer);
      state.raceTimer = null;
      $("#race-play").textContent = "Replay";
      return;
    }
    raceAt(state.raceIndex + 1);
  }, reduced ? 650 : 180);
}

function metricCard(label, value, note, tone = "") {
  return element("div", {class: "metric-card"}, [
    element("span", {text: label}), element("strong", {text: value, class: tone}), element("small", {text: note}),
  ]);
}

function syncInvestigationUrl(section = null) {
  if (!state.selectedGame) return;
  const url = new URL(window.location.href);
  url.searchParams.set("game", String(state.selectedGame));
  if (state.selectedItem) url.searchParams.set("item", String(state.selectedItem));
  else url.searchParams.delete("item");
  if (state.compareGame && state.compareGame !== state.selectedGame) url.searchParams.set("compare", String(state.compareGame));
  else url.searchParams.delete("compare");
  if (state.landscapeSource !== "all") url.searchParams.set("source", state.landscapeSource);
  else url.searchParams.delete("source");
  if (state.landscapeBucket !== "all") url.searchParams.set("bucket", state.landscapeBucket);
  else url.searchParams.delete("bucket");
  if (state.landscapeStatus !== "all") url.searchParams.set("status", state.landscapeStatus);
  else url.searchParams.delete("status");
  if (state.dossierTeam) url.searchParams.set("opponent", state.dossierTeam);
  else url.searchParams.delete("opponent");
  if (state.robustnessMode !== "medianPaceTotal") url.searchParams.set("robust", state.robustnessMode);
  else url.searchParams.delete("robust");
  if (state.selectedRuleId) url.searchParams.set("rule", state.selectedRuleId);
  else url.searchParams.delete("rule");
  if (state.portfolioRuleId) url.searchParams.set("prule", state.portfolioRuleId);
  else url.searchParams.delete("prule");
  if (state.portfolioGate !== "none") url.searchParams.set("pgate", state.portfolioGate);
  else url.searchParams.delete("pgate");
  if (state.portfolioDirection !== "any") url.searchParams.set("pdir", state.portfolioDirection);
  else url.searchParams.delete("pdir");
  if (state.portfolioSource !== "all") url.searchParams.set("psource", state.portfolioSource);
  else url.searchParams.delete("psource");
  if (state.capitalSort !== "gross") url.searchParams.set("capital", state.capitalSort);
  else url.searchParams.delete("capital");
  if (state.roundMapFilter !== "all") url.searchParams.set("roundmap", state.roundMapFilter);
  else url.searchParams.delete("roundmap");
  if (state.evidenceMode !== "hidden-field") url.searchParams.set("evidence", state.evidenceMode);
  else url.searchParams.delete("evidence");
  const driftDefaults = state.driftMetric === "net" && state.driftWindow === 10 && state.driftSensitivity === 3;
  if (!driftDefaults) url.searchParams.set("drift", [state.driftMetric, state.driftWindow, state.driftSensitivity].join(","));
  else url.searchParams.delete("drift");
  const forecastDefaults = state.forecastWindow === "all" && state.forecastRuns === 5000 &&
    state.forecastSeed === 20260823 && state.forecastTarget === 3 && state.forecastEdge === 0;
  if (!forecastDefaults) url.searchParams.set("forecast", [state.forecastWindow, state.forecastRuns, state.forecastSeed, state.forecastTarget, state.forecastEdge].join(","));
  else url.searchParams.delete("forecast");
  const reviewerDefaults = state.reviewerWindow === "all" && state.reviewerOpponent === "all" &&
    state.reviewerSource === "all" && state.reviewerClass === "all" &&
    Object.values(state.reviewerShifts).every(value => value === 0);
  if (!reviewerDefaults) url.searchParams.set("reviewer", [
    state.reviewerWindow, state.reviewerClass,
    encodeURIComponent(state.reviewerOpponent), encodeURIComponent(state.reviewerSource),
    state.reviewerShifts["0–50"], state.reviewerShifts["50–400"],
    state.reviewerShifts["400–1200"], state.reviewerShifts["1200+"],
  ].join("~"));
  else url.searchParams.delete("reviewer");
  const defaultCohortA = state.cohortA.window === "previous-10" && state.cohortA.source === "all" &&
    state.cohortA.bucket === "all" && state.cohortA.status === "all";
  const defaultCohortB = state.cohortB.window === "last-10" && state.cohortB.source === "all" &&
    state.cohortB.bucket === "all" && state.cohortB.status === "all";
  const cohortDefaults = defaultCohortA && defaultCohortB && state.cohortRuns === 5000 && state.cohortSeed === 20260824;
  if (!cohortDefaults) {
    const encodeCohortToken = value => encodeURIComponent(String(value)).replaceAll("~", "%7E");
    url.searchParams.set("cohort", [
      state.cohortA.window, state.cohortA.source, state.cohortA.bucket, state.cohortA.status,
      state.cohortB.window, state.cohortB.source, state.cohortB.bucket, state.cohortB.status,
      state.cohortRuns, state.cohortSeed,
    ].map(encodeCohortToken).join("~"));
  } else url.searchParams.delete("cohort");
  const marketAtLatest = state.market
    ? state.marketReplayIndex >= state.market.gameIds.length - 1
    : state.marketReplayGame === null;
  if (state.marketTeam !== "Oasis" || state.marketMode !== "settlement" || state.marketPeer ||
      state.marketReplayMode !== "cumulative" || !marketAtLatest) {
    const encodeMarketToken = value => encodeURIComponent(String(value)).replaceAll("~", "%7E");
    url.searchParams.set("market", [
      state.marketTeam, state.marketMode, state.marketPeer || "",
      state.marketReplayMode, state.marketReplayGame ?? "",
    ].map(encodeMarketToken).join("~"));
  } else url.searchParams.delete("market");
  const defaultRival = rivalLeader();
  if (state.rivalWindow !== "all" || (state.rivalTeam && state.rivalTeam !== defaultRival)) {
    const encodeRivalToken = value => encodeURIComponent(String(value)).replaceAll("~", "%7E");
    url.searchParams.set("rival", [state.rivalTeam || "", state.rivalWindow].map(encodeRivalToken).join("~"));
  } else url.searchParams.delete("rival");
  const calibrationDefaults = state.calibrationCoverage === .9 && state.calibrationSource === "all" &&
    state.calibrationBucket === "all" && state.calibrationWindow === "all";
  if (!calibrationDefaults) {
    const encodeCalibrationToken = value => encodeURIComponent(String(value)).replaceAll("~", "%7E");
    url.searchParams.set("calibration", [state.calibrationCoverage, state.calibrationSource, state.calibrationBucket, state.calibrationWindow].map(encodeCalibrationToken).join("~"));
  } else url.searchParams.delete("calibration");
  const regretDefaults = state.regretWindow === "all" && state.regretSource === "all" && state.regretBucket === "all" && state.regretFocus === "combined";
  if (!regretDefaults) {
    const encodeRegretToken = value => encodeURIComponent(String(value)).replaceAll("~", "%7E");
    url.searchParams.set("regret", [state.regretWindow, state.regretSource, state.regretBucket, state.regretFocus].map(encodeRegretToken).join("~"));
  } else url.searchParams.delete("regret");
  const peerDefaults = state.peerCohort === "source-bucket" && state.peerMetric === "combined";
  if (!peerDefaults) {
    const encodePeerToken = value => encodeURIComponent(String(value)).replaceAll("~", "%7E");
    url.searchParams.set("peer", [state.peerCohort, state.peerMetric].map(encodePeerToken).join("~"));
  } else url.searchParams.delete("peer");
  if (section) url.hash = section;
  history.replaceState({game: state.selectedGame, item: state.selectedItem}, "", url);
}

async function copyInvestigationLink() {
  const activeSection = $(".topnav a.active")?.dataset.section || (state.selectedItem ? "item" : "game");
  syncInvestigationUrl(activeSection);
  try {
    await navigator.clipboard.writeText(window.location.href);
    toast("Local investigation link copied. It contains analytical identifiers and filters, never claim text.");
  } catch {
    toast("Clipboard access was blocked. The address bar now contains the exact local investigation link.");
  }
}

async function selectGame(game, {scroll = false} = {}) {
  const gameNumber = Number(game);
  if (!Number.isInteger(gameNumber)) return;
  const generation = ++state.loadGeneration;
  state.selectedGame = gameNumber;
  state.selectedItem = null;
  state.itemDetail = null;
  if (state.overview) renderRoundMap();
  $("#item-empty").hidden = false;
  $("#item-workspace").hidden = true;
  $("#game-select").value = String(gameNumber);
  $("#item-ledger").replaceChildren(element("div", {class: "empty-state"}, [element("p", {text: `Materialising game ${gameNumber}…`})]));
  try {
    const payload = await api(`/api/game?id=${gameNumber}`);
    if (generation !== state.loadGeneration) return;
    state.game = payload;
    state.caseData = null;
    renderGame();
    if (scroll) $("#game").scrollIntoView({behavior: "smooth", block: "start"});
    syncInvestigationUrl(scroll ? "game" : null);
    loadCase(gameNumber, generation);
  } catch (error) {
    toast(`Game ${gameNumber} unavailable: ${error.message}`);
  }
}

async function loadCase(game, generation = state.loadGeneration) {
  $("#document-empty").hidden = false;
  $("#document-workspace").hidden = true;
  const availability = state.overview?.games?.find(row => row.id === game)?.documentsAvailable;
  if (availability === false) {
    state.caseData = null;
    $("#document-empty p").textContent = `Documents unavailable for game ${game}: a complete local key/archive pair is not cached. Analytical views remain complete.`;
    return;
  }
  $("#document-empty p").textContent = `Decrypting game ${game} locally…`;
  try {
    const payload = await api(`/api/case?game=${game}`, {timeout: 50000, retries: 0});
    if (generation !== state.loadGeneration || state.selectedGame !== game) return;
    state.caseData = payload;
    renderLedger();
    renderDocuments();
    if (state.selectedItem) renderItem();
  } catch (error) {
    if (generation !== state.loadGeneration) return;
    state.caseData = null;
    $("#document-empty").hidden = false;
    $("#document-empty p").textContent = `Documents unavailable for game ${game}: ${error.message}`;
  }
}

function renderGame() {
  const econ = state.game.economics;
  const reconciliation = state.game.scoreReconciliationDelta;
  const reconciled = reconciliation !== null && reconciliation !== undefined &&
    Number.isFinite(Number(reconciliation)) && Math.abs(Number(reconciliation)) <= .011;
  const kpis = $("#game-kpis");
  clear(kpis);
  kpis.append(
    metricCard("Issuer income", formatCurrency(econ.income), "paid to Oasis · all opponent reviewers", "positive"),
    metricCard("Reviewer cost", formatCurrency(econ.cost), "paid by Oasis · settlement matrix", "negative"),
    metricCard("Net score", signed(econ.net), `game ${state.game.game} · ${reconciled ? "reconciled to official score" : "official reconciliation unavailable"}`, econ.net >= 0 ? "positive" : "negative"),
    metricCard("Hidden fraud", formatNumber(econ.hiddenFraud), "rejected opponent charges · amount invisible", "warning"),
  );
  renderWaterfall();
  renderMatrix();
  renderFlightRecorder();
  renderReplayTheatre();
  renderCapitalFlow();
  renderLedger();
  syncCompareOptions();
  if (state.comparePayload && state.comparePayload.game !== state.selectedGame) renderComparison();
}

function flightStyle(type) {
  const specs = {
    "round.scheduled": ["INGEST", "Round scheduled", "SCHEDULE", colors.muted],
    "key.received": ["INGEST", "Key received", "KEY", colors.blue],
    "case.decrypted": ["INGEST", "Case decrypted", "DECRYPT", colors.blue],
    "case.parsed": ["INGEST", "Case parsed", "PARSE", colors.cyan],
    "prior.prefetched": ["REASON", "Prior prefetched", "PREFETCH", colors.violet],
    "item.belief": ["REASON", "Belief activity", "BELIEFS", colors.violet],
    "rule.fired": ["REASON", "Rule activity", "RULES", colors.amber],
    "item.decided": ["REASON", "Decision activity", "DECISIONS", colors.cyan],
    "submission.built": ["SUBMIT", "Submission built", "BUILD", colors.green],
    "submission.sent": ["SUBMIT", "Submission sent", "SEND", colors.green],
    "submission.verified": ["SUBMIT", "Submission verified", "VERIFY", colors.green],
    "round.closed": ["SUBMIT", "Round closed", "CLOSE", colors.muted],
    "round.played": ["SETTLE", "Round played marker", "PLAYED", colors.amber],
  };
  const [family, label, short, color] = specs[type] || ["OTHER", type, type, colors.muted];
  return {family, label, short, color};
}

function flightMetadata(row) {
  const parts = [];
  if (Number.isFinite(row.reportedMs)) parts.push(`reported ${formatDurationMs(row.reportedMs)}`);
  if (Number.isFinite(row.latencyMs)) parts.push(`call latency ${formatDurationMs(row.latencyMs)}`);
  if (Number.isFinite(row.files)) parts.push(`${row.files} files`);
  if (Number.isFinite(row.items)) parts.push(`${row.items} items`);
  if (Number.isFinite(row.tier)) parts.push(`tier ${row.tier}`);
  if (Number.isFinite(row.status)) parts.push(`HTTP ${row.status}`);
  if (typeof row.ok === "boolean") parts.push(row.ok ? "reported OK" : "reported failure");
  if (Number.isFinite(row.elapsedSeconds)) parts.push(`reported elapsed ${formatNumber(row.elapsedSeconds, 2)} s`);
  if (Number.isFinite(row.playedCount)) parts.push(`played counter ${formatNumber(row.playedCount)}`);
  if (Number.isFinite(row.totalA) || Number.isFinite(row.totalB)) {
    parts.push(`Σa ${formatCurrency(row.totalA)} · Σb ${formatCurrency(row.totalB)} · decision totals, not payoff`);
  }
  if (Number.isFinite(row.count)) parts.push(`${formatNumber(row.count)} logged events`);
  if (row.type === "item.belief" || row.type === "rule.fired" || row.type === "item.decided") {
    parts.push(`observed activity span ${formatDurationMs(row.durationMs)}`);
  }
  return parts.join(" · ") || "no additional metadata logged";
}

function renderFlightChart(flight) {
  const host = $("#flight-chart"); clear(host);
  const milestones = flight.milestones.filter(row => Number.isFinite(row.elapsedFromStartMs));
  const activities = flight.activities.filter(row => Number.isFinite(row.elapsedFromStartMs));
  const allEnds = [
    ...milestones.map(row => row.elapsedFromStartMs),
    ...activities.map(row => row.elapsedFromStartMs + safeNumber(row.durationMs)),
  ];
  if (!allEnds.length) {
    host.append(element("div", {class: "flight-empty"}, [element("div", {}, [
      element("strong", {text: "Events exist, but no valid timestamps were logged."}),
      element("p", {text: "The event ledger remains available below; this chart will not fabricate chronology from sequence numbers."}),
    ])]));
    return;
  }
  const width = 1080, height = 430;
  const margin = {left: 105, right: 35, top: 62, bottom: 92};
  const lanes = ["INGEST", "REASON", "SUBMIT", "SETTLE"];
  const laneGap = 62, maxElapsed = Math.max(1000, ...allEnds) * 1.04;
  const plotW = width - margin.left - margin.right;
  const x = value => margin.left + clamp(safeNumber(value) / maxElapsed, 0, 1) * plotW;
  const y = family => margin.top + lanes.indexOf(family) * laneGap + laneGap / 2;
  const svg = svgRoot(width, height, `Game ${flight.game} sanitized decision-pipeline chronology`);
  for (let tick = 0; tick <= 5; tick++) {
    const value = maxElapsed * tick / 5;
    const position = x(value);
    svg.append(svgElement("line", {x1: position, y1: margin.top - 18, x2: position, y2: margin.top + laneGap * lanes.length, class: "grid-line"}));
    svg.append(svgElement("text", {x: position, y: 29, class: "axis-label", "text-anchor": "middle"}, formatDurationMs(value)));
  }
  lanes.forEach(family => {
    const position = y(family);
    svg.append(svgElement("text", {x: margin.left - 14, y: position + 3, class: "axis-label", "text-anchor": "end"}, family));
    svg.append(svgElement("line", {x1: margin.left, y1: position, x2: width - margin.right, y2: position, stroke: colors.grid}));
  });
  activities.forEach(row => {
    const style = flightStyle(row.type), position = y(style.family);
    const start = x(row.elapsedFromStartMs), end = x(row.elapsedFromStartMs + safeNumber(row.durationMs));
    const rect = svgElement("rect", {x: start, y: position - 10, width: Math.max(5, end - start), height: 20, rx: 9, fill: style.color, "fill-opacity": .26, stroke: style.color, "stroke-opacity": .74, tabindex: 0, role: "img", "aria-label": `${style.label}, ${row.count} events over ${formatDurationMs(row.durationMs)}`});
    addTooltip(rect, [style.label, `${row.count} events · seq ${row.firstSeq}–${row.lastSeq}`, `Starts ${formatDurationMs(row.elapsedFromStartMs)} from first boundary`, `Observed span ${formatDurationMs(row.durationMs)}`]);
    svg.append(rect);
    if (end - start > 58) svg.append(svgElement("text", {x: (start + end) / 2, y: position + 3, fill: style.color, "font-family": "var(--mono)", "font-size": 8, "text-anchor": "middle", "pointer-events": "none"}, `${style.short} ×${row.count}`));
  });
  milestones.forEach((row, index) => {
    const style = flightStyle(row.type), position = y(style.family), markerX = x(row.elapsedFromStartMs);
    const failed = row.ok === false || Number.isFinite(row.status) && row.status >= 400;
    const marker = failed
      ? svgElement("rect", {x: markerX - 5, y: position - 5, width: 10, height: 10, fill: colors.red, transform: `rotate(45 ${markerX} ${position})`, tabindex: 0, role: "img", "aria-label": `${style.label}, failed, ${formatDurationMs(row.elapsedFromStartMs)} from start`})
      : svgElement("circle", {cx: markerX, cy: position, r: 5, fill: style.color, stroke: "#091012", "stroke-width": 2, tabindex: 0, role: "img", "aria-label": `${style.label}, ${formatDurationMs(row.elapsedFromStartMs)} from start`});
    addTooltip(marker, [style.label, `Seq ${row.seq} · ${formatUtcTime(row.ts)}`, `${formatDurationMs(row.elapsedFromStartMs)} from first logged boundary`, `${formatDurationMs(row.elapsedFromPreviousMs)} since previous milestone`, flightMetadata(row)]);
    svg.append(marker);
    const tier = Number.isFinite(row.tier) ? ` T${row.tier}` : "";
    const labelY = position + (index % 2 ? 23 : -16);
    svg.append(svgElement("text", {x: markerX, y: labelY, fill: failed ? colors.red : style.color, "font-family": "var(--mono)", "font-size": 7.5, "text-anchor": "middle", "pointer-events": "none"}, `${style.short}${tier}`));
  });

  const budgetY = height - 48;
  const tierTwo = milestones.find(row => row.type === "submission.sent" && row.tier === 2);
  svg.append(svgElement("text", {x: margin.left - 14, y: budgetY + 4, class: "axis-label", "text-anchor": "end"}, "T2 WALL"));
  svg.append(svgElement("rect", {x: margin.left, y: budgetY - 5, width: plotW, height: 10, rx: 5, fill: colors.grid}));
  svg.append(svgElement("rect", {x: margin.left, y: budgetY - 5, width: plotW, height: 10, rx: 5, fill: colors.green, "fill-opacity": .24}));
  if (tierTwo && Number.isFinite(tierTwo.elapsedFromStartMs)) {
    const fraction = tierTwo.elapsedFromStartMs / 52000;
    const budgetX = margin.left + clamp(fraction, 0, 1) * plotW;
    const marker = svgElement("circle", {cx: budgetX, cy: budgetY, r: 6, fill: fraction <= 1 ? colors.green : colors.red, tabindex: 0, role: "img", "aria-label": `Tier 2 sent at ${formatDurationMs(tierTwo.elapsedFromStartMs)} against the 52 second wall`});
    addTooltip(marker, [`Tier 2 timing`, `Sent ${formatDurationMs(tierTwo.elapsedFromStartMs)} from first logged boundary`, fraction <= 1 ? `${formatDurationMs(52000 - tierTwo.elapsedFromStartMs)} observed headroom` : `${formatDurationMs(tierTwo.elapsedFromStartMs - 52000)} beyond wall`]);
    svg.append(marker);
  }
  svg.append(svgElement("text", {x: margin.left, y: height - 20, class: "axis-label"}, "0 s"));
  svg.append(svgElement("text", {x: width - margin.right, y: height - 20, class: "axis-label", "text-anchor": "end"}, "52 s HARD WALL"));
  host.append(svg);
}

function renderFlightLedger(flight) {
  const records = [
    ...flight.milestones.map(row => ({...row, activity: false, firstSeq: row.seq})),
    ...flight.activities.map(row => ({...row, activity: true})),
  ].sort((a, b) => a.firstSeq - b.firstSeq);
  const list = $("#flight-event-list"); clear(list);
  const body = $("#flight-data-table"); clear(body);
  records.forEach(row => {
    const style = flightStyle(row.type);
    const delta = row.activity ? `${formatDurationMs(row.durationMs)} span` : formatDurationMs(row.elapsedFromPreviousMs);
    const meta = flightMetadata(row);
    const first = element("div", {}, [
      element("i", {class: "flight-event-dot", "aria-hidden": "true"}),
      element("div", {}, [element("strong", {text: `${style.label}${Number.isFinite(row.tier) ? ` · T${row.tier}` : ""}`}), element("small", {text: `${row.activity ? `seq ${row.firstSeq}–${row.lastSeq}` : `seq ${row.seq}`} · ${row.activity ? `${formatUtcTime(row.firstTs)} → ${formatUtcTime(row.lastTs)}` : formatUtcTime(row.ts)}`})]),
    ]);
    first.querySelector("i").style.setProperty("--flight-color", style.color);
    list.append(element("div", {class: "flight-event-row"}, [first, element("span", {class: "flight-event-delta", text: delta}), element("span", {class: "flight-event-meta", text: meta})]));
    body.append(element("tr", {}, [
      element("td", {text: row.activity ? `${row.firstSeq}–${row.lastSeq}` : row.seq}),
      element("td", {text: `${style.label}${Number.isFinite(row.tier) ? ` · tier ${row.tier}` : ""}`}),
      element("td", {text: row.activity ? `${formatUtcTime(row.firstTs)} → ${formatUtcTime(row.lastTs)}` : formatUtcTime(row.ts)}),
      element("td", {text: formatDurationMs(row.elapsedFromStartMs)}),
      element("td", {text: delta}), element("td", {text: meta}),
    ]));
  });
}

function renderFlightRecorder() {
  const flight = state.game?.flight;
  const kpis = $("#flight-kpis"); clear(kpis);
  const chart = $("#flight-chart"); clear(chart);
  clear($("#flight-event-list")); clear($("#flight-data-table"));
  if (!flight?.available) {
    $("#flight-state").textContent = "NOT RECORDED";
    const latest = flight?.latestRecordedGame;
    const content = element("div", {}, [
      element("strong", {text: `No local pipeline record for game ${state.game.game}.`}),
      element("p", {text: "Settlement analytics remain available. The flight recorder refuses to infer missing operational history from transaction rows."}),
    ]);
    if (Number.isInteger(latest) && latest !== state.game.game) {
      const button = element("button", {type: "button", text: `Open latest recorded game ${latest}`});
      button.addEventListener("click", () => selectGame(latest));
      content.append(button);
    }
    chart.append(element("div", {class: "flight-empty"}, [content]));
    return;
  }
  $("#flight-state").textContent = `${flight.observedCoreStages} / ${flight.coreStageDenominator} CORE`;
  const sends = flight.milestones.filter(row => row.type === "submission.sent" && Number.isFinite(row.elapsedFromStartMs));
  const firstSend = sends.sort((a, b) => a.elapsedFromStartMs - b.elapsedFromStartMs)[0];
  const tierTwo = sends.find(row => row.tier === 2);
  const headroom = tierTwo ? 52000 - tierTwo.elapsedFromStartMs : null;
  const alerts = Object.values(flight.alerts || {}).reduce((sum, value) => sum + safeNumber(value), 0);
  const specs = [
    ["Recorder coverage", formatPercent(flight.completeness), `${flight.observedCoreStages} / ${flight.coreStageDenominator} core event types`],
    ["Observed span", formatDurationMs(flight.observedSpanMs), `${flight.eventCount} sanitized events · ${alerts} alerts (severity only)`],
    ["First send", firstSend ? formatDurationMs(firstSend.elapsedFromStartMs) : "not logged", firstSend ? `tier ${firstSend.tier ?? "unknown"} · HTTP ${firstSend.status ?? "unknown"}` : "submission boundary absent"],
    ["Tier 2 headroom", headroom === null ? "not logged" : headroom >= 0 ? formatDurationMs(headroom) : `−${formatDurationMs(Math.abs(headroom))}`, "against 52 s hard wall · from first logged boundary"],
  ];
  specs.forEach(([label, value, note]) => kpis.append(element("div", {class: "flight-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
  renderFlightChart(flight);
  renderFlightLedger(flight);
}

function roundReplayEvents(game = state.game) {
  if (!game) return [];
  const milestones = (game.flight?.milestones || []).map(row => ({...row, replayKind: "milestone", item: null}));
  const itemEvents = (game.replay?.events || []).map(row => ({...row, replayKind: "item"}));
  return [...milestones, ...itemEvents].sort((left, right) => left.seq - right.seq);
}

function replayEventStyle(row) {
  if (row.type === "item.belief") return {family: "BELIEF", label: "Belief emitted", short: "BELIEF", color: colors.violet};
  if (row.type === "rule.fired") return {family: "RULE", label: row.shadow ? "SHADOW rule fired" : "Active rule fired", short: row.shadow ? "SHADOW" : "RULE", color: row.shadow ? colors.violet : colors.amber};
  if (row.type === "item.decided") return {family: "DECIDE", label: "Item decision emitted", short: "DECIDE", color: colors.cyan};
  const flight = flightStyle(row.type);
  return {...flight, family: flight.family === "REASON" ? "BELIEF" : flight.family};
}

function deriveReplayFrame(events, index, itemIds = []) {
  const bounded = Math.max(0, Math.min(Number(index) || 0, Math.max(0, events.length - 1)));
  const visible = events.slice(0, bounded + 1);
  const ids = new Set(itemIds);
  visible.forEach(row => { if (Number.isInteger(row.item)) ids.add(row.item); });
  const states = new Map([...ids].sort((a, b) => a - b).map(item => [item, {
    item, belief: null, rules: [], decision: null, lastSeq: null,
  }]));
  let beliefEvents = 0, ruleEvents = 0, decisionEvents = 0, shadowEvents = 0;
  visible.forEach(row => {
    if (!Number.isInteger(row.item)) return;
    if (!states.has(row.item)) states.set(row.item, {item: row.item, belief: null, rules: [], decision: null, lastSeq: null});
    const item = states.get(row.item);
    item.lastSeq = row.seq;
    if (row.type === "item.belief") { item.belief = row; beliefEvents += 1; }
    else if (row.type === "rule.fired") { item.rules.push(row); ruleEvents += 1; shadowEvents += Number(Boolean(row.shadow)); }
    else if (row.type === "item.decided") { item.decision = row; decisionEvents += 1; }
  });
  return {
    index: bounded, current: events[bounded] || null, visible,
    items: [...states.values()], beliefEvents, ruleEvents, decisionEvents, shadowEvents,
    decidedItems: [...states.values()].filter(row => row.decision).length,
    believedItems: [...states.values()].filter(row => row.belief).length,
  };
}

function replayEventDetail(row) {
  if (!row) return "No replay boundary selected";
  if (row.type === "item.belief") return `median ${formatCurrency(row.median)} · sigma ${formatNumber(row.sigma, 3)} · source ${row.source || "unknown"}`;
  if (row.type === "rule.fired") return `${row.shadow ? "SHADOW · counterfactual" : "ACTIVE · production path"} · ${row.rule || "unnamed"} · ${pairText(row.from)} → ${pairText(row.to)}`;
  if (row.type === "item.decided") return `a ${formatCurrency(row.a)} · b ${formatCurrency(row.b)} · ${row.covered ? "covered" : "not covered"}`;
  return flightMetadata(row);
}

function stopReplay() {
  if (state.replayTimer) clearInterval(state.replayTimer);
  state.replayTimer = null;
  $("#replay-play").textContent = "Replay round";
  $("#replay-play").setAttribute("aria-pressed", "false");
}

function setReplayIndex(index) {
  const events = roundReplayEvents();
  state.replayIndex = clamp(Number(index) || 0, 0, Math.max(0, events.length - 1));
  renderReplayFrame(events);
}

function toggleReplay() {
  const events = roundReplayEvents();
  if (!events.length) return;
  if (state.replayTimer) {
    stopReplay();
    return;
  }
  stopMarketReplay();
  if (state.raceTimer) {
    clearInterval(state.raceTimer);
    state.raceTimer = null;
    $("#race-play").textContent = "Play race";
  }
  if (state.replayIndex >= events.length - 1) state.replayIndex = 0;
  renderReplayFrame(events);
  $("#replay-play").textContent = "Pause replay";
  $("#replay-play").setAttribute("aria-pressed", "true");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const interval = (reduced ? 1100 : 720) / state.replaySpeed;
  state.replayTimer = setInterval(() => {
    if (state.replayIndex >= events.length - 1) {
      stopReplay();
      return;
    }
    state.replayIndex += 1;
    renderReplayFrame(events);
  }, interval);
}

function renderReplayChart(events, frame) {
  const host = $("#replay-chart"); clear(host);
  if (!events.length) return;
  const width = 1080, height = 405, margin = {left: 88, right: 30, top: 50, bottom: 62};
  const lanes = ["INGEST", "BELIEF", "RULE", "DECIDE", "SUBMIT", "SETTLE"];
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const allTimed = events.every(row => Number.isFinite(row.elapsedFromStartMs));
  const maxElapsed = Math.max(1, ...events.map(row => safeNumber(row.elapsedFromStartMs)));
  const seqMin = Math.min(...events.map(row => row.seq)), seqMax = Math.max(...events.map(row => row.seq));
  const x = (row, index) => margin.left + (allTimed ? safeNumber(row.elapsedFromStartMs) / maxElapsed : events.length <= 1 ? .5 : index / (events.length - 1)) * plotW;
  const y = family => margin.top + (lanes.indexOf(family) + .5) / lanes.length * plotH;
  const svg = svgRoot(width, height, `Game ${state.game.game} replay at event ${frame.index + 1} of ${events.length}`);
  lanes.forEach(lane => {
    const position = y(lane);
    svg.append(svgElement("text", {x: margin.left - 12, y: position + 3, class: "axis-label", "text-anchor": "end"}, lane));
    svg.append(svgElement("line", {x1: margin.left, y1: position, x2: width - margin.right, y2: position, stroke: colors.grid}));
  });
  for (let tick = 0; tick <= 5; tick++) {
    const position = margin.left + plotW * tick / 5;
    svg.append(svgElement("line", {x1: position, y1: margin.top - 15, x2: position, y2: height - margin.bottom, class: "grid-line"}));
    const label = allTimed ? formatDurationMs(maxElapsed * tick / 5) : `SEQ ${Math.round(seqMin + (seqMax - seqMin) * tick / 5)}`;
    svg.append(svgElement("text", {x: position, y: height - 30, class: "axis-label", "text-anchor": "middle"}, label));
  }
  const points = events.map((row, index) => {
    const style = replayEventStyle(row);
    return {row, index, style, x: x(row, index), y: y(style.family)};
  });
  svg.append(svgElement("path", {d: linePath(points.map(point => [point.x, point.y])), fill: "none", stroke: colors.muted, "stroke-width": 1, "stroke-opacity": .22}));
  points.forEach(point => {
    const past = point.index <= frame.index;
    const current = point.index === frame.index;
    const radius = current ? 8 : point.row.replayKind === "item" ? 4.5 : 5.5;
    const marker = svgElement("circle", {cx: point.x, cy: point.y, r: radius, fill: point.style.color, "fill-opacity": past ? current ? 1 : .68 : .1, stroke: current ? "#f5fbff" : point.style.color, "stroke-width": current ? 2.5 : 1, "stroke-opacity": past ? 1 : .16, tabindex: 0, class: "interactive", role: "button", "aria-label": `Replay event ${point.index + 1}, ${point.style.label}${Number.isInteger(point.row.item) ? `, item ${point.row.item}` : ""}`});
    addTooltip(marker, [`Event ${point.index + 1} / ${events.length} · seq ${point.row.seq}`, `${point.style.label}${Number.isInteger(point.row.item) ? ` · item ${point.row.item}` : ""}`, allTimed ? `${formatDurationMs(point.row.elapsedFromStartMs)} from first boundary` : "Timestamp incomplete · sequence scale", replayEventDetail(point.row)]);
    marker.addEventListener("click", () => { stopReplay(); setReplayIndex(point.index); });
    svg.append(marker);
  });
  const cursor = points[frame.index];
  if (cursor) {
    svg.append(svgElement("line", {x1: cursor.x, y1: margin.top - 18, x2: cursor.x, y2: height - margin.bottom, stroke: colors.cyan, "stroke-width": 1.2, "stroke-dasharray": "4 4", "pointer-events": "none"}));
    svg.append(svgElement("text", {x: cursor.x, y: 23, fill: colors.cyan, "font-family": "var(--mono)", "font-size": 8, "text-anchor": "middle"}, `CURSOR · ${cursor.style.short}`));
  }
  svg.append(svgElement("text", {x: margin.left, y: height - 9, class: "axis-label"}, allTimed ? "TIMESTAMP SCALE · DISTANCE FROM FIRST LOGGED BOUNDARY" : "SEQUENCE SCALE · ONE OR MORE TIMESTAMPS MISSING"));
  host.append(svg);
}

function renderReplayItems(frame) {
  const host = $("#replay-item-grid"); clear(host);
  frame.items.forEach(item => {
    const current = frame.current?.item === item.item;
    const activeRules = item.rules.filter(row => !row.shadow).length;
    const shadowRules = item.rules.filter(row => row.shadow).length;
    const button = element("button", {type: "button", class: `replay-item-card ${item.decision ? "decided" : item.belief ? "believed" : "waiting"} ${current ? "current" : ""}`, "aria-label": `Open game ${state.game.game} item ${item.item}, ${item.decision ? "decision visible" : item.belief ? "belief visible" : "awaiting evidence"}`}, [
      element("div", {class: "replay-item-title"}, [element("strong", {text: `ITEM ${String(item.item).padStart(2, "0")}`}), element("span", {text: item.decision ? "DECIDED" : item.belief ? "BELIEF" : "WAITING"})]),
      element("div", {class: "replay-item-pipeline", "aria-hidden": "true"}, [element("i", {class: item.belief ? "on" : ""}), element("i", {class: item.rules.length ? "on" : ""}), element("i", {class: item.decision ? "on" : ""})]),
      element("small", {text: item.belief ? `${formatCurrency(item.belief.median)} · ${item.belief.source || "unknown"}` : "belief not yet logged"}),
      element("small", {text: `${activeRules} active · ${shadowRules} shadow firings visible`}),
      element("span", {class: "replay-item-decision", text: item.decision ? `a ${formatCurrency(item.decision.a)} · b ${formatCurrency(item.decision.b)}` : "decision pending"}),
    ]);
    button.addEventListener("click", () => selectItem(item.item, {scroll: true}));
    host.append(button);
  });
  if (!frame.items.length) host.append(element("div", {class: "empty-state"}, [element("p", {text: "No item identifiers were logged in this round."})]));
}

function renderReplayFocus(frame, events) {
  const row = frame.current;
  const host = $("#replay-focus-card"); clear(host);
  if (!row) return;
  const style = replayEventStyle(row);
  $("#replay-focus-family").textContent = style.family;
  host.append(
    element("span", {class: "replay-focus-seq", text: `SEQ ${row.seq} · EVENT ${frame.index + 1} / ${events.length}`}),
    element("h4", {text: style.label}),
    element("p", {text: replayEventDetail(row)}),
    element("dl", {}, [
      element("dt", {text: "Logged UTC"}), element("dd", {text: formatUtcTime(row.ts)}),
      element("dt", {text: "Elapsed"}), element("dd", {text: Number.isFinite(row.elapsedFromStartMs) ? formatDurationMs(row.elapsedFromStartMs) : "timestamp unavailable"}),
      element("dt", {text: "Sequence position"}), element("dd", {text: `${formatPercent((frame.index + 1) / events.length)} of sanitized boundaries`}),
    ]),
  );
  if (Number.isInteger(row.item)) {
    const open = element("button", {type: "button", class: "button", text: `Open game ${state.game.game} item ${row.item}`});
    open.addEventListener("click", () => selectItem(row.item, {scroll: true}));
    host.append(open);
  }
}

function renderReplayLedger(events, frame) {
  const body = $("#replay-data-table"); clear(body);
  events.forEach((row, index) => {
    const style = replayEventStyle(row);
    const open = Number.isInteger(row.item) ? element("button", {type: "button", class: "table-link", text: `item ${row.item}`}) : null;
    if (open) open.addEventListener("click", () => selectItem(row.item, {scroll: true}));
    const tr = element("tr", {class: index === frame.index ? "replay-current-row" : index > frame.index ? "replay-future-row" : ""}, [
      element("td", {text: row.seq}), element("td", {text: Number.isFinite(row.elapsedFromStartMs) ? formatDurationMs(row.elapsedFromStartMs) : "unavailable"}),
      element("td", {text: style.family}), element("td", {text: style.label}),
      element("td", {}, open ? [open] : ["—"]), element("td", {text: replayEventDetail(row)}),
    ]);
    tr.addEventListener("click", event => { if (event.target === open) return; stopReplay(); setReplayIndex(index); });
    body.append(tr);
  });
}

function renderReplayFrame(events = roundReplayEvents()) {
  if (!events.length) return;
  const itemIds = (state.game?.items || []).map(row => row.idx);
  const frame = deriveReplayFrame(events, state.replayIndex, itemIds);
  state.replayIndex = frame.index;
  $("#replay-slider").value = String(frame.index);
  $("#replay-position").textContent = `EVENT ${frame.index + 1} / ${events.length}`;
  const elapsed = Number.isFinite(frame.current?.elapsedFromStartMs) ? formatDurationMs(frame.current.elapsedFromStartMs) : "sequence only";
  const host = $("#replay-kpis"); clear(host);
  const specs = [
    ["Cursor", `SEQ ${frame.current?.seq ?? "—"}`, `${elapsed} from first boundary`],
    ["Beliefs visible", `${frame.believedItems} / ${frame.items.length}`, `${frame.beliefEvents} belief events observed`],
    ["Rules visible", formatNumber(frame.ruleEvents), `${frame.shadowEvents} SHADOW · ${frame.ruleEvents - frame.shadowEvents} active`],
    ["Items decided", `${frame.decidedItems} / ${frame.items.length}`, `${frame.decisionEvents} decision events observed`],
    ["Sequence coverage", formatPercent((frame.index + 1) / events.length), `${events.length - frame.index - 1} boundaries remain`],
  ];
  specs.forEach(([label, value, note]) => host.append(element("div", {class: "replay-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
  renderReplayChart(events, frame);
  renderReplayItems(frame);
  renderReplayFocus(frame, events);
  renderReplayLedger(events, frame);
}

function renderReplayTheatre() {
  const events = roundReplayEvents();
  if (state.replayGame !== state.game?.game) {
    stopReplay();
    state.replayGame = state.game?.game ?? null;
    state.replayIndex = Math.max(0, events.length - 1);
  }
  $("#replay-slider").max = String(Math.max(0, events.length - 1));
  $("#replay-state").textContent = events.length ? `${events.length} BOUNDARIES · ${state.game.replay?.eventCount || 0} ITEM EVENTS` : "NOT RECORDED";
  if (!events.length) {
    clear($("#replay-kpis")); clear($("#replay-chart")); clear($("#replay-item-grid")); clear($("#replay-focus-card")); clear($("#replay-data-table"));
    const content = element("div", {}, [element("strong", {text: `No item-level replay for game ${state.game.game}.`}), element("p", {text: "The theatre remains empty rather than reconstructing decisions from settlement rows."})]);
    const latest = state.game.flight?.latestRecordedGame;
    if (Number.isInteger(latest) && latest !== state.game.game) {
      const button = element("button", {type: "button", text: `Open latest replayable game ${latest}`});
      button.addEventListener("click", () => selectGame(latest, {scroll: true}));
      content.append(button);
    }
    $("#replay-chart").append(element("div", {class: "flight-empty"}, [content]));
    $("#replay-position").textContent = "EVENT — / —";
    return;
  }
  renderReplayFrame(events);
}

function capitalRows() {
  const field = {gross: "grossObservedFlow", net: "netContribution", cost: "reviewerCost", income: "issuerIncome"}[state.capitalSort] || "grossObservedFlow";
  return [...(state.game?.items || [])].sort((left, right) => {
    const a = safeNumber(left.economics?.[field]);
    const b = safeNumber(right.economics?.[field]);
    const primary = state.capitalSort === "net" ? Math.abs(b) - Math.abs(a) : b - a;
    return primary || left.idx - right.idx;
  });
}

function renderCapitalFlow() {
  if (!state.game) return;
  $$('[data-capital-sort]').forEach(button => {
    const active = button.dataset.capitalSort === state.capitalSort;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const rows = capitalRows();
  const summary = $("#capital-flow-summary"); clear(summary);
  const gross = rows.reduce((sum, row) => sum + safeNumber(row.economics?.grossObservedFlow), 0);
  const absoluteNet = rows.reduce((sum, row) => sum + Math.abs(safeNumber(row.economics?.netContribution)), 0);
  const topThreeGross = [...rows].sort((a, b) => safeNumber(b.economics?.grossObservedFlow) - safeNumber(a.economics?.grossObservedFlow)).slice(0, 3).reduce((sum, row) => sum + safeNumber(row.economics?.grossObservedFlow), 0);
  const hidden = rows.reduce((sum, row) => sum + safeNumber(row.economics?.hiddenFraud), 0);
  const specs = [
    ["Gross observed flow", formatCurrency(gross), `income + reviewer cost · ${rows.length} items`],
    ["Top-three concentration", gross ? formatPercent(topThreeGross / gross) : "unknown", "share of gross observed item flow"],
    ["Absolute net movement", formatCurrency(absoluteNet), "Σ |item income − item cost|"],
    ["Hidden fraud groups", formatNumber(hidden), "rejected · attempted amount unavailable"],
  ];
  specs.forEach(([label, value, note]) => summary.append(element("div", {class: "capital-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));

  const host = $("#capital-flow-chart"); clear(host);
  const visible = rows.slice(0, 15);
  if (!visible.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No item-level settlement rows are available for this game."})]));
  } else {
    const width = 720, rowHeight = 34, height = 106 + visible.length * rowHeight;
    const margin = {left: 82, right: 62, top: 68, bottom: 35};
    const center = margin.left + (width - margin.left - margin.right) / 2;
    const half = (width - margin.left - margin.right) / 2;
    const maximum = Math.max(1, ...visible.flatMap(row => [safeNumber(row.economics?.issuerIncome), safeNumber(row.economics?.reviewerCost), Math.abs(safeNumber(row.economics?.netContribution))]));
    const scale = value => Math.abs(safeNumber(value)) / maximum * half;
    const svg = svgRoot(width, height, `Game ${state.game.game} item-level observed capital flow`);
    svg.append(svgElement("text", {x: center - 16, y: 20, fill: colors.red, "font-family": "var(--mono)", "font-size": 8, "text-anchor": "end"}, "← REVIEWER COST"));
    svg.append(svgElement("text", {x: center + 16, y: 20, fill: colors.green, "font-family": "var(--mono)", "font-size": 8}, "ISSUER INCOME →"));
    svg.append(svgElement("text", {x: center, y: 39, fill: colors.amber, "font-family": "var(--mono)", "font-size": 7.5, "text-anchor": "middle"}, "DIAMOND = NET CONTRIBUTION"));
    svg.append(svgElement("line", {x1: center, y1: margin.top - 16, x2: center, y2: height - margin.bottom, stroke: colors.muted, "stroke-opacity": .65}));
    visible.forEach((row, index) => {
      const econ = row.economics || {}, y = margin.top + index * rowHeight + rowHeight / 2;
      const income = safeNumber(econ.issuerIncome), cost = safeNumber(econ.reviewerCost), net = safeNumber(econ.netContribution);
      const selected = row.idx === state.selectedItem;
      const group = svgElement("g", {tabindex: 0, role: "button", class: "interactive", "aria-label": `Open item ${row.idx}: issuer income ${formatCurrency(income)}, reviewer cost ${formatCurrency(cost)}, net ${signed(net)}`});
      group.append(svgElement("rect", {x: margin.left, y: y - rowHeight / 2, width: width - margin.left - margin.right, height: rowHeight, fill: selected ? colors.cyan : "transparent", "fill-opacity": selected ? .07 : 0}));
      group.append(svgElement("line", {x1: margin.left, y1: y + rowHeight / 2, x2: width - margin.right, y2: y + rowHeight / 2, stroke: colors.grid}));
      group.append(svgElement("text", {x: margin.left - 10, y: y + 3, fill: selected ? colors.cyan : "#98a4ad", "font-family": "var(--mono)", "font-size": selected ? 10 : 8.5, "text-anchor": "end"}, `I${String(row.idx).padStart(2, "0")}`));
      group.append(svgElement("rect", {x: center - scale(cost), y: y - 7, width: scale(cost), height: 14, rx: 3, fill: colors.red, "fill-opacity": .62}));
      group.append(svgElement("rect", {x: center, y: y - 7, width: scale(income), height: 14, rx: 3, fill: colors.green, "fill-opacity": .62}));
      const netX = center + (net >= 0 ? 1 : -1) * scale(net);
      group.append(svgElement("rect", {x: netX - 4, y: y - 4, width: 8, height: 8, fill: colors.amber, transform: `rotate(45 ${netX} ${y})`}));
      group.append(svgElement("text", {x: width - margin.right + 8, y: y + 3, fill: net >= 0 ? colors.green : colors.red, "font-family": "var(--mono)", "font-size": 8}, signed(net)));
      addTooltip(group, [`Game ${state.game.game} item ${row.idx}`, `Issuer income ${formatCurrency(income)} · reviewer cost ${formatCurrency(cost)}`, `Net contribution ${signed(net)} · gross observed flow ${formatCurrency(econ.grossObservedFlow)}`, `${prettyStatus(row.status)} · ${econ.hiddenFraud || 0} hidden fraud groups`]);
      group.addEventListener("click", () => selectItem(row.idx, {scroll: true}));
      svg.append(group);
    });
    svg.append(svgElement("text", {x: margin.left, y: height - 11, class: "axis-label"}, `${visible.length} shown / ${rows.length} items · selected sort ${state.capitalSort}`));
    host.append(svg);
  }

  const body = $("#capital-flow-table"); clear(body);
  rows.forEach(row => {
    const econ = row.economics || {};
    const open = element("button", {type: "button", class: "table-link", text: `game ${state.game.game} item ${row.idx}`});
    open.addEventListener("click", () => selectItem(row.idx, {scroll: true}));
    body.append(element("tr", {}, [
      element("td", {}, [open]), element("td", {class: "money", text: formatCurrency(econ.issuerIncome)}),
      element("td", {class: "money", text: formatCurrency(econ.reviewerCost)}),
      element("td", {class: `money ${safeNumber(econ.netContribution) >= 0 ? "positive" : "negative"}`, text: signed(safeNumber(econ.netContribution))}),
      element("td", {class: "money", text: formatCurrency(econ.grossObservedFlow)}),
      element("td", {text: prettyStatus(row.status)}), element("td", {text: formatNumber(econ.hiddenFraud)}),
    ]));
  });
}

function syncCompareOptions() {
  const select = $("#compare-game");
  if (!select || !state.overview) return;
  const previous = state.compareGame;
  clear(select);
  select.append(element("option", {value: "", text: "Choose game"}));
  state.overview.games.filter(game => game.played && game.id !== state.selectedGame).forEach(game => {
    select.append(element("option", {value: game.id, text: `Game ${game.id} · ${signed(game.net)}`}));
  });
  if (previous && previous !== state.selectedGame) select.value = String(previous);
  else {
    state.compareGame = null;
    state.comparePayload = null;
    $("#game-compare-panel").hidden = true;
  }
}

async function loadComparison(game) {
  if (!game) {
    state.compareGame = null;
    state.comparePayload = null;
    $("#game-compare-panel").hidden = true;
    syncInvestigationUrl();
    return;
  }
  try {
    const payload = await api(`/api/game?id=${Number(game)}`);
    if (state.selectedGame === payload.game) return;
    state.compareGame = payload.game;
    state.comparePayload = payload;
    renderComparison();
    syncInvestigationUrl();
  } catch (error) {
    toast(`Comparison unavailable: ${error.message}`);
  }
}

function comparisonMetrics(payload) {
  const econ = payload.economics;
  return [
    {key: "net", label: "Net score", value: econ.net, unit: "EUR"},
    {key: "income", label: "Issuer income", value: econ.income, unit: "EUR"},
    {key: "cost", label: "Reviewer cost", value: econ.cost, unit: "EUR"},
    {key: "rejectFair", label: "Reject-fair cost", value: econ.matrix.rejectFair.cost, unit: "EUR"},
    {key: "acceptFraud", label: "Accept-fraud cost", value: econ.matrix.acceptFraud.cost, unit: "EUR"},
    {key: "hidden", label: "Hidden fraud", value: econ.hiddenFraud, unit: "count"},
    {key: "items", label: "Line items", value: payload.items.length, unit: "count"},
  ];
}

function renderComparison() {
  if (!state.game || !state.comparePayload) return;
  const panel = $("#game-compare-panel"); panel.hidden = false;
  $("#compare-subtitle").textContent = `Game ${state.game.game} against game ${state.comparePayload.game} · selected game in cyan`;
  const current = comparisonMetrics(state.game);
  const other = comparisonMetrics(state.comparePayload);
  const host = $("#compare-chart"); clear(host);
  const width = 700, height = 340, cx = width / 2, cy = height / 2 + 6, radius = 120;
  const svg = svgRoot(width, height, `Fingerprint comparison of game ${state.game.game} and game ${state.comparePayload.game}`);
  const point = (index, fraction) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / current.length;
    return [cx + Math.cos(angle) * radius * fraction, cy + Math.sin(angle) * radius * fraction];
  };
  for (let level = 1; level <= 4; level++) {
    const points = current.map((_, index) => point(index, level / 4));
    svg.append(svgElement("path", {d: `${linePath(points)} Z`, fill: "none", stroke: colors.grid, "stroke-width": 1}));
  }
  current.forEach((metric, index) => {
    const end = point(index, 1);
    svg.append(svgElement("line", {x1: cx, y1: cy, x2: end[0], y2: end[1], class: "grid-line"}));
    const label = point(index, 1.22);
    svg.append(svgElement("text", {x: label[0], y: label[1], class: "axis-label", "text-anchor": label[0] < cx - 10 ? "end" : label[0] > cx + 10 ? "start" : "middle"}, metric.label));
  });
  const normalised = metrics => metrics.map((metric, index) => {
    const max = Math.max(1, Math.abs(current[index].value), Math.abs(other[index].value));
    const fraction = metric.key === "net"
      ? clamp(.5 + metric.value / (2 * max), 0, 1)
      : Math.abs(metric.value) / max;
    return point(index, fraction);
  });
  [[other, colors.violet, .14], [current, colors.cyan, .17]].forEach(([metrics, color, opacity]) => {
    const points = normalised(metrics);
    svg.append(svgElement("path", {d: `${linePath(points)} Z`, fill: color, "fill-opacity": opacity, stroke: color, "stroke-width": 2}));
    points.forEach((coords, index) => {
      const dot = svgElement("circle", {cx: coords[0], cy: coords[1], r: 4, fill: color, tabindex: 0, class: "interactive"});
      addTooltip(dot, [`Game ${metrics === current ? state.game.game : state.comparePayload.game} · ${metrics[index].label}`, metrics[index].unit === "EUR" ? formatCurrency(metrics[index].value) : `${formatNumber(metrics[index].value)} ${metrics[index].unit}`]);
      svg.append(dot);
    });
  });
  host.append(svg);
  const metricsHost = $("#compare-metrics"); clear(metricsHost);
  const lowerIsBetter = new Set(["cost", "rejectFair", "acceptFraud", "hidden"]);
  current.forEach((metric, index) => {
    const delta = metric.value - other[index].value;
    const good = metric.key === "items" ? null : lowerIsBetter.has(metric.key) ? delta <= 0 : delta >= 0;
    metricsHost.append(element("div", {class: "compare-row"}, [
      element("span", {text: metric.label}),
      element("strong", {text: metric.unit === "EUR" ? formatCurrency(metric.value) : formatNumber(metric.value)}),
      element("output", {class: good === null ? "" : good ? "positive" : "negative", text: metric.unit === "EUR" ? signed(delta) : `${delta >= 0 ? "+" : ""}${formatNumber(delta)}`}),
    ]));
  });
}

function renderWaterfall() {
  const host = $("#waterfall-chart"); clear(host);
  const econ = state.game.economics;
  const matrix = econ.matrix;
  const stages = [
    {name: "Income", delta: econ.income, kind: "total", color: colors.green},
    {name: "Accept fair", delta: -matrix.acceptFair.cost, color: colors.blue},
    {name: "Reject fair", delta: -matrix.rejectFair.cost, color: colors.red},
    {name: "Accept fraud", delta: -matrix.acceptFraud.cost, color: colors.amber},
    {name: "Unresolved", delta: -econ.unresolved.cost, color: colors.muted},
    {name: "Net", delta: econ.net, kind: "end", color: econ.net >= 0 ? colors.cyan : colors.red},
  ];
  let running = 0;
  const bounds = [0, econ.income];
  stages.slice(1, -1).forEach(stage => { running += stage.delta; bounds.push(econ.income + running); });
  bounds.push(econ.net);
  const min = Math.min(0, ...bounds), max = Math.max(0, ...bounds);
  const width = 760, height = 340, margin = {top: 30, right: 25, bottom: 70, left: 78};
  const svg = svgRoot(width, height, `Game ${state.game.game} waterfall from income to net`);
  const scale = chartScaffold(svg, width, height, margin, min, max, 5);
  const barW = scale.plotW / stages.length * .62;
  running = 0;
  stages.forEach((stage, i) => {
    let start, end;
    if (stage.kind === "total") { start = 0; end = stage.delta; running = end; }
    else if (stage.kind === "end") { start = 0; end = stage.delta; }
    else { start = running; end = running + stage.delta; running = end; }
    const y = Math.min(scale.y(start), scale.y(end));
    const h = Math.max(2, Math.abs(scale.y(start) - scale.y(end)));
    const x = margin.left + scale.plotW * (i + .5) / stages.length - barW / 2;
    const rect = svgElement("rect", {x, y, width: barW, height: h, rx: 4, fill: stage.color, "fill-opacity": stage.kind ? .82 : .62, tabindex: 0, class: "interactive"});
    addTooltip(rect, [stage.name, `${stage.delta >= 0 ? "+" : "−"}${formatCurrency(Math.abs(stage.delta))}`, stage.kind ? `level ${formatCurrency(end)}` : `running ${formatCurrency(end)}`]);
    svg.append(rect);
    if (i < stages.length - 1 && stage.kind !== "end") {
      svg.append(svgElement("line", {x1: x + barW, y1: scale.y(end), x2: margin.left + scale.plotW * (i + 1.5) / stages.length - barW / 2, y2: scale.y(end), stroke: colors.muted, "stroke-dasharray": "3 4", "stroke-opacity": .5}));
    }
    svg.append(svgElement("text", {x: x + barW / 2, y: height - 39, class: "axis-label", "text-anchor": "middle"}, stage.name));
  });
  host.append(svg);
}

function renderMatrix() {
  const host = $("#decision-matrix"); clear(host);
  const cells = state.game.economics.matrix;
  const specs = [
    ["acceptFair", "Accept / fair", colors.green], ["acceptFraud", "Accept / fraud", colors.amber],
    ["rejectFair", "Reject / fair", colors.red], ["rejectFraud", "Reject / fraud", colors.blue],
  ];
  const max = Math.max(1, ...specs.map(([key]) => cells[key].cost));
  specs.forEach(([key, label, color]) => {
    const row = cells[key];
    const cell = element("div", {class: "matrix-cell", tabindex: "0"}, [
      element("span", {text: label}), element("strong", {text: formatCurrency(row.cost)}),
      element("small", {text: `${formatNumber(row.count)} decisions`}),
    ]);
    cell.style.setProperty("--cell-color", color);
    cell.style.setProperty("--heat", String(.06 + .48 * Math.sqrt(row.cost / max)));
    host.append(cell);
  });
  const econ = state.game.economics;
  $("#matrix-foot").textContent = `${econ.unresolved.count} unresolved decisions / ${formatCurrency(econ.unresolved.cost)} · ${econ.hiddenFraud} rejected-fraud charges with invisible size.`;
}

function caseItem(idx) { return state.caseData?.items?.find(row => row.idx === idx) || null; }
function indexItem(game, item) { return state.overview?.itemIndex?.find(row => row.game === game && row.item === item) || null; }

function rangePosition(value, max) {
  if (value === null || value === undefined || value < 0) return null;
  return clamp(Math.log1p(value) / Math.log1p(Math.max(1, max)) * 100, 0, 100);
}

function rangeVisual(item, {large = false} = {}) {
  const decision = item.decision || {};
  const threshold = item.threshold || {};
  const values = [decision.a, decision.b, threshold.tLo, threshold.tHi,
    ...item.opponents.map(row => row.charge)].filter(value => Number.isFinite(value));
  const max = Math.max(10, ...values) * 1.12;
  const viz = element("div", {class: "range-viz", "aria-label": `Valuation field for item ${item.idx}`});
  viz.append(element("div", {class: "range-axis"}));
  if (Number.isFinite(threshold.tLo)) {
    const left = rangePosition(threshold.tLo, max);
    const right = Number.isFinite(threshold.tHi) ? rangePosition(threshold.tHi, max) : 100;
    const proven = element("div", {class: `range-proven ${threshold.tHi === null ? "open" : ""}`});
    proven.style.left = `${left}%`;
    proven.style.width = `${Math.max(1, right - left)}%`;
    proven.title = threshold.tHi === null
      ? `t ≥ ${formatCurrency(threshold.tLo)}; upper bound unknown`
      : `${formatCurrency(threshold.tLo)} ≤ t < ${formatCurrency(threshold.tHi)}`;
    viz.append(proven);
  }
  [["a", decision.a], ["b", decision.b]].forEach(([kind, value]) => {
    if (!Number.isFinite(value)) return;
    const marker = element("span", {class: `range-marker ${kind}`, title: `${kind} · ${formatCurrency(value)}`});
    marker.style.left = `${rangePosition(value, max)}%`;
    viz.append(marker);
  });
  item.opponents.forEach(row => {
    if (row.charge === null || row.charge === undefined) return;
    const marker = element("span", {class: `range-marker opponent ${cssStatus(row.chargeKind)}`, title: `${row.team} · ${row.chargeKind.replaceAll("_", " ")} ${formatCurrency(row.charge)}`});
    marker.style.left = `${rangePosition(row.charge, max)}%`;
    viz.append(marker);
  });
  if (large) {
    [0, max / 4, max / 2, max].forEach(value => {
      const label = element("span", {class: "range-label", text: formatCurrency(value, true)});
      label.style.left = `${rangePosition(value, max)}%`;
      viz.append(label);
    });
  }
  return viz;
}

function renderLedger() {
  if (!state.game) return;
  const host = $("#item-ledger"); clear(host);
  const query = $("#ledger-search")?.value.trim().toLocaleLowerCase() || "";
  let items = state.game.items.filter(item => {
    const parsed = caseItem(item.idx);
    const watched = isWatched(state.selectedGame, item.idx);
    const matchesQuery = !query || String(item.idx).includes(query) || parsed?.description.toLocaleLowerCase().includes(query);
    const matchesFilter = state.ledgerFilter === "all" ||
      state.ledgerFilter === "watched" && watched ||
      state.ledgerFilter === "open" && item.status === "above-floor-open-ceiling" ||
      item.status === state.ledgerFilter;
    return matchesQuery && matchesFilter;
  });
  items = [...items].sort((left, right) => {
    const a = indexItem(state.selectedGame, left.idx) || {};
    const b = indexItem(state.selectedGame, right.idx) || {};
    if (state.ledgerSort === "loss") return safeNumber(b.foregoneLowerBound) - safeNumber(a.foregoneLowerBound) || left.idx - right.idx;
    if (state.ledgerSort === "error") return Math.abs(safeNumber(b.logError)) - Math.abs(safeNumber(a.logError)) || left.idx - right.idx;
    if (state.ledgerSort === "field") return safeNumber(b.field?.hidden) - safeNumber(a.field?.hidden) || left.idx - right.idx;
    return left.idx - right.idx;
  });
  if (!items.length) {
    host.append(element("div", {class: "empty-state"}, [element("span", {class: "empty-glyph", "aria-hidden": "true"}), element("p", {text: "No line items match the current search and evidence filters."})]));
    return;
  }
  items.forEach(item => {
    const parsed = caseItem(item.idx);
    const decision = item.decision || {};
    const row = element("button", {type: "button", class: `ledger-row ${state.selectedItem === item.idx ? "selected" : ""} ${isWatched(state.selectedGame, item.idx) ? "watched" : ""}`, role: "listitem"});
    row.append(
      element("div", {class: "ledger-item"}, [
        element("strong", {text: `${isWatched(state.selectedGame, item.idx) ? "WATCHED · " : ""}ITEM ${String(item.idx).padStart(2, "0")}`}),
        element("span", {text: parsed?.description || (state.caseData ? "Parsed row unavailable" : "Load local case to reveal description")}),
      ]),
      element("div", {class: "ledger-numbers"}, [
        element("span", {}, ["a", element("strong", {text: formatCurrency(decision.a)})]),
        element("span", {}, ["b", element("strong", {text: formatCurrency(decision.b)})]),
      ]),
      rangeVisual(item),
      element("div", {}, [element("span", {class: `status-pill ${cssStatus(item.status)}`, text: prettyStatus(item.status)})]),
    );
    row.addEventListener("click", () => selectItem(item.idx, {scroll: true}));
    host.append(row);
  });
}

async function selectItem(item, {scroll = false} = {}) {
  state.selectedItem = Number(item);
  renderLedger();
  renderCapitalFlow();
  try {
    const detail = await api(`/api/item?game=${state.selectedGame}&item=${state.selectedItem}`);
    if (state.selectedItem !== detail.idx || state.selectedGame !== detail.game) return;
    state.itemDetail = detail;
    $("#policy-search").value = "";
    renderItem();
    renderDocuments();
    if (scroll) $("#item").scrollIntoView({behavior: "smooth", block: "start"});
    syncInvestigationUrl(scroll ? "item" : null);
  } catch (error) {
    toast(`Item detail unavailable: ${error.message}`);
  }
}

function renderItem() {
  const item = state.itemDetail;
  if (!item || item.game !== state.selectedGame || item.idx !== state.selectedItem) return;
  const parsed = caseItem(item.idx);
  $("#item-empty").hidden = true;
  $("#item-workspace").hidden = false;
  $("#item-game").textContent = item.game;
  $("#item-index").textContent = item.idx;
  $("#item-description").textContent = parsed?.description || "Description unavailable until local case decryption succeeds";
  $("#item-meta").textContent = parsed
    ? `PRINTED POSITION ${parsed.pos} · QTY ${formatNumber(parsed.qty, 3)} ${parsed.unit}${parsed.sourcePage ? ` · PDF PAGE ${parsed.sourcePage}` : ""}`
    : "PARSED SOURCE UNAVAILABLE";
  const status = $("#item-status"); clear(status);
  status.append(element("span", {class: `status-pill ${cssStatus(item.status)}`, text: prettyStatus(item.status)}));
  const belief = $("#item-belief"); clear(belief);
  const b = item.belief;
  belief.append(
    element("div", {class: "belief-value"}, [element("span", {text: "BELIEF MEDIAN"}), element("strong", {text: formatCurrency(b?.median)})]),
    element("div", {class: "belief-value"}, [element("span", {text: "LOG SIGMA"}), element("strong", {text: b ? formatNumber(b.sigma, 3) : "—"})]),
    element("div", {class: "belief-source", text: `SOURCE · ${b?.source || "no logged belief"}`}),
  );
  renderItemInterval();
  renderRules();
  renderOpponentTable();
  renderWatchState();
  setupScenario();
  renderPeerForensics();
}

function peerMetricSpec(key) { return PEER_METRICS.find(row => row.key === key) || PEER_METRICS.find(row => row.key === "combined"); }
function peerMetricText(key, value, compact = false) {
  if (!Number.isFinite(value)) return "unavailable";
  const unit = peerMetricSpec(key).unit;
  if (unit === "eur") return formatCurrency(value, compact);
  if (unit === "count") return formatNumber(value, value % 1 ? 2 : 0);
  if (unit === "ratio") return `${value >= 0 ? "+" : "−"}${formatNumber(Math.abs(value), compact ? 2 : 3)}`;
  return formatNumber(value, compact ? 2 : 3);
}

function allPeerRegretRows() {
  if (!state.overview || !state.reviewerLab) return [];
  const lastCell = state.reviewerLab.cells?.at(-1);
  const revision = `${state.overview.generatedAt}:${state.reviewerLab.cells?.length || 0}:${lastCell?.game || 0}:${lastCell?.item || 0}`;
  if (state.peerRegretCache?.revision === revision) return state.peerRegretCache.rows;
  const result = buildRegretCartography(state.overview.itemIndex, state.reviewerLab.cells || [], state.overview.race.gameIds, {window: "all", source: "all", bucket: "all", focus: "combined"});
  state.peerRegretCache = {revision, rows: result.rows};
  return result.rows;
}

function populatePeerControls() {
  state.peerCohort = PEER_COHORTS.has(state.peerCohort) ? state.peerCohort : "source-bucket";
  state.peerMetric = PEER_METRICS.some(row => row.key === state.peerMetric) ? state.peerMetric : "combined";
  $("#peer-cohort").value = state.peerCohort; $("#peer-metric").value = state.peerMetric;
}

function renderPeerNarrative(result) {
  const host = $("#peer-narrative"); clear(host); const selectedMetric = result.metrics.find(row => row.key === result.metric);
  const cohortLabel = ({"source-bucket": "same source + floor regime", "source-only": "same logged source", "bucket-only": "same sanctioned-floor regime"})[result.cohort];
  const priorState = result.denominator.priorPeers >= 5 ? "historical context available" : result.denominator.priorPeers ? "thin prior context" : "cold start · no prior peer";
  host.dataset.tone = result.denominator.priorPeers >= 5 ? "context" : "warning";
  host.append(
    element("div", {class: "peer-narrative-primary"}, [element("span", {text: "RETROSPECTIVE PEER CONTRACT"}), element("strong", {text: `${cohortLabel} · ${priorState}`}), element("small", {text: `${result.selected.source} · ${result.selected.bucket} · selected game ${result.selected.game} item ${result.selected.item}`})]),
    element("div", {class: "peer-narrative-fact"}, [element("span", {text: "STRICT TEMPORAL WALL"}), element("strong", {text: `${result.denominator.priorPeers} lower-game peers`}), element("small", {text: `only games < ${result.selected.game} enter prior percentiles and envelopes`})]),
    element("div", {class: "peer-narrative-fact"}, [element("span", {text: "HINDSIGHT SEPARATED"}), element("strong", {text: `${result.denominator.sameGamePeers + result.denominator.futurePeers} ghosted peers`}), element("small", {text: `${result.denominator.sameGamePeers} same-game · ${result.denominator.futurePeers} future · excluded from prior summaries`})]),
    element("div", {class: "peer-narrative-fact"}, [element("span", {text: result.reviewerEvidenceAvailable ? "SELECTED TAPE METRIC" : "DEGRADED · ISSUER GEOMETRY ONLY"}), element("strong", {text: peerMetricText(result.metric, selectedMetric?.selectedValue)}), element("small", {text: result.reviewerEvidenceAvailable ? `${peerMetricSpec(result.metric).label} · ${selectedMetric?.prior.observations || 0} prior metric observations` : "reviewer-cost, combined-load, and hidden-group fields remain unavailable until the reviewer ledger recovers"})]),
  );
}

function renderPeerKpis(result) {
  const host = $("#peer-kpis"); clear(host); const metric = result.metrics.find(row => row.key === result.metric);
  const priorAnalogue = result.priorAnalogues[0];
  const cards = [
    ["Prior peer universe", formatNumber(result.denominator.priorPeers), `strictly lower game IDs · ${metric?.prior.observations || 0} with selected metric`, ""],
    ["All peer universe", formatNumber(result.denominator.allPeers), `${result.denominator.sameGamePeers} same-game · ${result.denominator.futurePeers} future hindsight`, ""],
    ["Prior percentile", formatPercent(metric?.prior.percentile), `${peerMetricSpec(result.metric).label} · empirical midrank`, "accent"],
    ["All-peer percentile", formatPercent(metric?.all.percentile), "hindsight context including same-game and future peers", ""],
    ["Nearest prior geometry", priorAnalogue ? formatNumber(priorAnalogue.distance, 3) : "unavailable", priorAnalogue ? `game ${priorAnalogue.game} item ${priorAnalogue.item} · ${priorAnalogue.dimensions} common dimensions` : "no prior numeric analogue with ≥2 common dimensions", ""],
    ["Metric completeness", formatPercent(result.denominator.priorPeers ? metric?.prior.observations / result.denominator.priorPeers : null), `${metric?.prior.observations || 0} / ${result.denominator.priorPeers} prior peers`, result.denominator.priorPeers && metric?.prior.observations < result.denominator.priorPeers ? "warning" : ""],
  ];
  cards.forEach(([label, value, note, tone]) => host.append(element("div", {class: "peer-kpi"}, [element("span", {text: label}), element("strong", {class: tone, text: value}), element("small", {text: note})])));
}

function renderPeerFingerprint(result) {
  const host = $("#peer-fingerprint-chart"); clear(host); const rows = result.metrics;
  const width = 820, rowHeight = 59, height = rows.length * rowHeight + 76, margin = {left: 205, right: 116, top: 46, bottom: 38};
  const x = value => margin.left + clamp(safeNumber(value), 0, 1) * (width - margin.left - margin.right);
  const svg = svgRoot(width, height, "Selected item empirical percentile against prior and all numeric peers");
  [0,.25,.5,.75,1].forEach(value => { const xx=x(value);svg.append(svgElement("line",{x1:xx,y1:margin.top,x2:xx,y2:height-margin.bottom,class:"grid-line"}));svg.append(svgElement("text",{x:xx,y:height-15,class:"axis-label","text-anchor":"middle"},formatPercent(value))); });
  rows.forEach((row,index) => {
    const yy=margin.top+index*rowHeight+18;
    svg.append(svgElement("text",{x:margin.left-12,y:yy+3,class:"axis-label","text-anchor":"end"},row.label.toLocaleUpperCase()));
    svg.append(svgElement("line",{x1:margin.left,y1:yy,x2:width-margin.right,y2:yy,stroke:"rgba(171,188,199,.16)","stroke-width":2}));
    if(row.all.percentile!==null){const xx=x(row.all.percentile);svg.append(svgElement("rect",{x:xx-4,y:yy-4,width:8,height:8,fill:colors.violet,transform:`rotate(45 ${xx} ${yy})`,"fill-opacity":.72}));}
    if(row.prior.percentile!==null)svg.append(svgElement("circle",{cx:x(row.prior.percentile),cy:yy,r:5,fill:colors.cyan,stroke:"#0b0d10","stroke-width":2}));
    svg.append(svgElement("text",{x:width-margin.right+10,y:yy+3,fill:colors.muted,"font-size":8,"font-family":"var(--mono)"},`${peerMetricText(row.key,row.selectedValue,true)} · n ${row.prior.observations}/${row.all.observations}`));
  });
  svg.append(svgElement("circle",{cx:margin.left,cy:18,r:4,fill:colors.cyan}));svg.append(svgElement("text",{x:margin.left+10,y:21,fill:colors.cyan,"font-size":8,"font-family":"var(--mono)"},"STRICTLY PRIOR"));
  svg.append(svgElement("rect",{x:margin.left+119,y:14,width:8,height:8,fill:colors.violet,transform:`rotate(45 ${margin.left+123} 18)`}));svg.append(svgElement("text",{x:margin.left+135,y:21,fill:colors.violet,"font-size":8,"font-family":"var(--mono)"},"ALL PEERS · HINDSIGHT")); host.append(svg);
}

function renderPeerEnvelope(result) {
  const host = $("#peer-envelope-chart"); clear(host); const rows = result.metrics;
  const width=820,rowHeight=59,height=rows.length*rowHeight+76,margin={left:205,right:116,top:46,bottom:38};
  const svg=svgRoot(width,height,"Prior and all-history peer quantile envelopes with selected item markers");
  rows.forEach((row,index)=>{
    const yy=margin.top+index*rowHeight+18;
    const values=[row.selectedValue,row.prior.p10,row.prior.median,row.prior.p90,row.all.p10,row.all.median,row.all.p90].filter(Number.isFinite);
    svg.append(svgElement("text",{x:margin.left-12,y:yy+3,class:"axis-label","text-anchor":"end"},row.label.toLocaleUpperCase()));
    if(!values.length){svg.append(svgElement("text",{x:margin.left,y:yy+3,fill:colors.muted,"font-size":8,"font-family":"var(--mono)"},"NO COMPARABLE OBSERVATIONS"));return;}
    let minimum=Math.min(...values),maximum=Math.max(...values);if(minimum===maximum){const spread=Math.max(1,Math.abs(minimum)*.1);minimum-=spread;maximum+=spread;}
    const x=value=>margin.left+(value-minimum)/(maximum-minimum)*(width-margin.left-margin.right);
    svg.append(svgElement("line",{x1:margin.left,y1:yy,x2:width-margin.right,y2:yy,stroke:"rgba(171,188,199,.12)"}));
    if(Number.isFinite(row.all.p10)){svg.append(svgElement("line",{x1:x(row.all.p10),y1:yy+6,x2:x(row.all.p90),y2:yy+6,stroke:colors.violet,"stroke-width":5,"stroke-opacity":.28,"stroke-linecap":"round"}));svg.append(svgElement("circle",{cx:x(row.all.median),cy:yy+6,r:3,fill:colors.violet}));}
    if(Number.isFinite(row.prior.p10)){svg.append(svgElement("line",{x1:x(row.prior.p10),y1:yy-6,x2:x(row.prior.p90),y2:yy-6,stroke:colors.cyan,"stroke-width":5,"stroke-opacity":.58,"stroke-linecap":"round"}));svg.append(svgElement("circle",{cx:x(row.prior.median),cy:yy-6,r:3,fill:colors.cyan}));}
    if(Number.isFinite(row.selectedValue)){const marker=svgElement("path",{d:`M${x(row.selectedValue)},${yy-10} l6,10 l-6,10 l-6,-10 z`,fill:colors.amber,stroke:"#0b0d10","stroke-width":1,tabindex:0,role:"img","aria-label":`${row.label}, selected ${peerMetricText(row.key,row.selectedValue)}`});addTooltip(marker,[row.label,`selected ${peerMetricText(row.key,row.selectedValue)}`,`prior P10–P90 ${peerMetricText(row.key,row.prior.p10)} to ${peerMetricText(row.key,row.prior.p90)} · n ${row.prior.observations}`,`all-peer P10–P90 ${peerMetricText(row.key,row.all.p10)} to ${peerMetricText(row.key,row.all.p90)} · n ${row.all.observations}`]);svg.append(marker);}
    svg.append(svgElement("text",{x:width-margin.right+10,y:yy+3,fill:colors.muted,"font-size":8,"font-family":"var(--mono)"},peerMetricText(row.key,row.selectedValue,true)));
  });
  svg.append(svgElement("text",{x:margin.left,y:19,fill:colors.cyan,"font-size":8,"font-family":"var(--mono)"},"UPPER RAIL = STRICTLY PRIOR P10–P90"));svg.append(svgElement("text",{x:margin.left+245,y:19,fill:colors.violet,"font-size":8,"font-family":"var(--mono)"},"LOWER RAIL = ALL-PEER HINDSIGHT"));svg.append(svgElement("text",{x:margin.left,y:height-13,class:"axis-title"},"ROW-LOCAL RAW-UNIT SCALE · ENVELOPES ARE DESCRIPTIVE, NOT PREDICTION INTERVALS"));host.append(svg);
}

function peerTemporalTransform(value, unit) {
  if (!Number.isFinite(value)) return null;
  if (unit === "eur" || unit === "count") return Math.log1p(Math.max(0, value));
  return Math.asinh(value);
}
function peerTemporalInverse(value, unit) { return unit === "eur" || unit === "count" ? Math.expm1(value) : Math.sinh(value); }

function renderPeerTemporal(result) {
  const host=$("#peer-temporal-chart"),body=$("#peer-temporal-table");clear(host);clear(body);const spec=peerMetricSpec(result.metric);
  const all=[...result.peerRows,result.selected].map(row=>({...row,value:peerMetricValue(row,result.metric),temporalSide:row.game<result.selected.game?"strictly-prior":row.game===result.selected.game&&row.item!==result.selected.item?"same-game-hindsight":row.game>result.selected.game?"future-hindsight":"selected"})).filter(row=>Number.isFinite(row.value)).sort((a,b)=>a.game-b.game||a.item-b.item);
  $("#peer-temporal-caption").textContent=`${spec.label} · prior cyan · same-game/future hindsight ghosted · ${all.length} metric observations`;
  host.setAttribute("aria-label",`${spec.label} across prior, selected, same-game, and future numeric peers`);
  if(!all.length){host.append(element("div",{class:"empty-state"},[element("p",{text:"The selected metric is unavailable across this peer cohort."})]));return;}
  const width=Math.max(900,(Math.max(...all.map(row=>row.game))-Math.min(...all.map(row=>row.game))+1)*18+120),height=420,margin={left:78,right:30,top:42,bottom:54};
  const transformed=all.map(row=>peerTemporalTransform(row.value,spec.unit));let minimum=Math.min(...transformed),maximum=Math.max(...transformed);
  if(minimum===maximum){const padding=Math.max(.25,Math.abs(minimum)*.1);minimum=spec.unit==="eur"||spec.unit==="count"?Math.max(0,minimum-padding):minimum-padding;maximum+=padding;}
  const span=Math.max(1e-9,maximum-minimum),minGame=Math.min(...all.map(row=>row.game)),maxGame=Math.max(...all.map(row=>row.game));
  const x=game=>margin.left+(game-minGame)/Math.max(1,maxGame-minGame)*(width-margin.left-margin.right),y=value=>height-margin.bottom-(peerTemporalTransform(value,spec.unit)-minimum)/span*(height-margin.top-margin.bottom);
  const svg=svgRoot(width,height,`${spec.label} peer temporal tape`);
  [0,.25,.5,.75,1].forEach(part=>{const transformedValue=minimum+span*part,value=peerTemporalInverse(transformedValue,spec.unit),yy=height-margin.bottom-part*(height-margin.top-margin.bottom);svg.append(svgElement("line",{x1:margin.left,y1:yy,x2:width-margin.right,y2:yy,class:"grid-line"}));svg.append(svgElement("text",{x:margin.left-9,y:yy+3,class:"axis-label","text-anchor":"end"},peerMetricText(result.metric,value,true)));});
  const selectedX=x(result.selected.game);svg.append(svgElement("line",{x1:selectedX,y1:margin.top,x2:selectedX,y2:height-margin.bottom,stroke:colors.amber,"stroke-width":1,"stroke-dasharray":"4 4","stroke-opacity":.7}));
  all.forEach(row=>{const color=row.temporalSide==="strictly-prior"?colors.cyan:row.temporalSide==="selected"?colors.amber:colors.violet,opacity=row.temporalSide.includes("hindsight")?.28:.82;const point=svgElement("circle",{cx:x(row.game),cy:y(row.value),r:row.temporalSide==="selected"?7:4,fill:color,"fill-opacity":opacity,stroke:row.temporalSide==="selected"?"#0b0d10":"transparent","stroke-width":2,tabindex:0,role:"button",class:"interactive","aria-label":`Open game ${row.game} item ${row.item}`});addTooltip(point,[`Game ${row.game} item ${row.item} · ${row.temporalSide.replaceAll("-"," ")}`,`${spec.label} ${peerMetricText(result.metric,row.value)}`,`${row.source} · ${row.bucket} · ${prettyStatus(row.status)}`]);point.addEventListener("click",async()=>{await selectGame(row.game);await selectItem(row.item,{scroll:true});});point.addEventListener("keydown",async event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();await selectGame(row.game);await selectItem(row.item,{scroll:true});}});svg.append(point);
    body.append(element("tr",{},[element("td",{},[itemLink(row.game,row.item)]),element("td",{text:row.temporalSide.replaceAll("-"," ")}),element("td",{text:peerMetricText(result.metric,row.value)}),element("td",{text:row.source}),element("td",{text:row.bucket}),element("td",{text:prettyStatus(row.status)})]));});
  svg.append(svgElement("text",{x:margin.left,y:18,fill:colors.cyan,"font-size":8,"font-family":"var(--mono)"},"STRICTLY PRIOR"));svg.append(svgElement("text",{x:margin.left+112,y:18,fill:colors.amber,"font-size":8,"font-family":"var(--mono)"},"SELECTED"));svg.append(svgElement("text",{x:margin.left+190,y:18,fill:colors.violet,"font-size":8,"font-family":"var(--mono)"},"HINDSIGHT · GHOSTED"));host.append(svg);
}

function renderPeerAnalogues(result) {
  const list=$("#peer-analogue-list"),body=$("#peer-analogue-table");clear(list);clear(body);
  result.analogues.slice(0,12).forEach((row,index)=>{const button=element("button",{type:"button",class:`peer-analogue-row peer-${row.temporalSide}`},[element("span",{text:`#${index+1}`}),element("div",{},[element("strong",{text:`Game ${row.game} item ${row.item}`}),element("small",{text:`${row.temporalSide.replaceAll("-"," ")} · ${row.dimensions} common dimensions · ${row.source}`})]),element("strong",{text:formatNumber(row.distance,3)})]);button.addEventListener("click",async()=>{await selectGame(row.game);await selectItem(row.item,{scroll:true});});list.append(button);});
  if(!result.analogues.length)list.append(element("div",{class:"empty-state"},[element("p",{text:"No numeric peer shares at least two decision-geometry dimensions."})]));
  result.analogues.forEach(row=>body.append(element("tr",{},[element("td",{},[itemLink(row.game,row.item)]),element("td",{text:row.temporalSide.replaceAll("-"," ")}),element("td",{text:formatNumber(row.distance,4)}),element("td",{text:row.dimensions}),element("td",{text:peerMetricText("charge-floor",peerMetricValue(row,"charge-floor"))}),element("td",{text:peerMetricText("belief-floor",peerMetricValue(row,"belief-floor"))}),element("td",{text:peerMetricText("limit-floor",peerMetricValue(row,"limit-floor"))}),element("td",{class:"money",text:peerMetricText("issuer",row.issuerForegoneLowerBound)}),element("td",{class:"money",text:peerMetricText("reviewer",row.wrongReviewerCost)}),element("td",{text:peerMetricText("hidden",row.hiddenFraudGroups)})])));
}

function renderPeerContract(result) {
  const host=$("#peer-contract-card");clear(host);const label=({"source-bucket":"source + floor regime","source-only":"source only","bucket-only":"floor regime only"})[result.cohort];
  host.append(element("div",{class:"peer-contract-head"},[element("span",{text:"COHORT CONTRACT"}),element("strong",{text:label}),element("small",{text:`${result.selected.source} · ${result.selected.bucket}`})]),element("div",{class:"peer-contract-denoms"},[element("div",{},[element("span",{text:"PRIOR"}),element("strong",{text:result.denominator.priorPeers})]),element("div",{},[element("span",{text:"SAME GAME"}),element("strong",{text:result.denominator.sameGamePeers})]),element("div",{},[element("span",{text:"FUTURE"}),element("strong",{text:result.denominator.futurePeers})]),element("div",{},[element("span",{text:"ALL PEERS"}),element("strong",{text:result.denominator.allPeers})])]),element("p",{text:result.reviewerEvidenceAvailable?"Reviewer evidence is available; every reviewer-derived metric still keeps its own observation denominator.":"Degraded mode: reviewer evidence is unavailable. Charge, belief, limit, and issuer-floor metrics remain active; reviewer, combined, and hidden metrics stay missing."}),element("p",{text:result.denominator.priorPeers<5?"Denominator warning: fewer than five prior peers. Treat every prior percentile and envelope as thin context.":"Prior context contains at least five peers; this still does not make the cohort semantic or causal."}),element("p",{text:"Analogue distance uses charge/floor log, belief/floor log, normalised b−floor, and sigma where at least two dimensions overlap. The nearest-prior KPI is scaled only on prior rows; the full ledger uses all peers and is hindsight."}));
}

function renderPeerMetricTable(result){const body=$("#peer-metric-table");clear(body);result.metrics.forEach(row=>body.append(element("tr",{},[element("td",{text:row.label}),element("td",{text:peerMetricText(row.key,row.selectedValue)}),element("td",{text:row.prior.observations}),element("td",{text:formatPercent(row.prior.percentile)}),element("td",{text:peerMetricText(row.key,row.prior.p10)}),element("td",{text:peerMetricText(row.key,row.prior.median)}),element("td",{text:peerMetricText(row.key,row.prior.p90)}),element("td",{text:row.all.observations}),element("td",{text:formatPercent(row.all.percentile)}),element("td",{text:peerMetricText(row.key,row.all.p10)}),element("td",{text:peerMetricText(row.key,row.all.median)}),element("td",{text:peerMetricText(row.key,row.all.p90)})])));}

async function copyPeerReceipt(){if(!state.peerResult||!state.overview){toast("Peer forensic evidence is unavailable to copy.");return;}try{await navigator.clipboard.writeText(JSON.stringify(buildPeerReceipt(state.peerResult,state.overview.generatedAt),null,2));toast("Claim-free peer forensic receipt copied.");}catch(error){toast(`Peer receipt could not be copied: ${error.message}`);}}

function renderPeerForensics(){
  if(!state.itemDetail||!state.overview)return;
  populatePeerControls();const result=buildPeerForensics(state.overview.itemIndex,allPeerRegretRows(),state.selectedGame,state.selectedItem,{cohort:state.peerCohort,metric:state.peerMetric,reviewerAvailable:Boolean(state.reviewerLab)});state.peerResult=result;
  if(!result.available){$("#peer-empty").hidden=false;$("#peer-workspace").hidden=true;$("#peer-status").textContent="ITEM INDEX UNAVAILABLE";$("#peer-empty p").textContent="This selected item is absent from the description-free global index.";return;}
  $("#peer-empty").hidden=true;$("#peer-workspace").hidden=false;$("#peer-status").textContent=result.reviewerEvidenceAvailable?`${result.denominator.priorPeers} PRIOR · ${result.denominator.allPeers} ALL PEERS · STRICT GAME WALL`:`DEGRADED · ISSUER GEOMETRY · ${result.denominator.priorPeers} PRIOR PEERS`;
  renderPeerNarrative(result);renderPeerKpis(result);renderPeerFingerprint(result);renderPeerEnvelope(result);renderPeerTemporal(result);renderPeerAnalogues(result);renderPeerContract(result);renderPeerMetricTable(result);
}

function renderWatchState() {
  const button = $("#watch-item");
  if (!button || !state.itemDetail) return;
  const watched = isWatched(state.itemDetail.game, state.itemDetail.idx);
  button.setAttribute("aria-pressed", String(watched));
  $("span:last-child", button).textContent = watched ? "Watching item" : "Watch item";
}

function toggleSelectedWatch() {
  if (!state.selectedGame || !state.selectedItem) return;
  const key = watchKey(state.selectedGame, state.selectedItem);
  if (state.watches.has(key)) state.watches.delete(key);
  else state.watches.add(key);
  saveWatches();
  renderWatchState();
  renderLedger();
  renderWatchlist();
}

function watchboardModeLabel(mode) {
  return ({
    "two-role-collision": "two-role collision", "issuer-burden": "issuer burden",
    "reviewer-burden": "reviewer burden", "hidden-only": "hidden-only evidence",
    "priced-evidence-quiet": "priced evidence quiet", "issuer-only-degraded": "issuer burden · reviewer unavailable",
    "reviewer-unavailable": "reviewer unavailable", "not-materialised": "not materialised",
  })[mode] || String(mode || "unknown").replaceAll("-", " ");
}

function watchboardSortLabel(sort) {
  return ({triage: "additive evidence load", issuer: "issuer shortfall lower bound", reviewer: "observed wrong-review cost", hidden: "hidden rejected-fraud groups", value: "sanctioned floor value", recent: "most recent game"})[sort] || sort;
}

function watchboardPriorityText(row, sort) {
  if (!row.materialized || !Number.isFinite(row.priority)) return "unavailable";
  if (sort === "hidden") return `${formatNumber(row.priority)} groups`;
  if (sort === "recent") return `game ${formatNumber(row.game)}`;
  if (["triage", "issuer", "reviewer", "value"].includes(sort)) return formatCurrency(row.priority, true);
  return formatNumber(row.priority, 2);
}

async function openWatchboardItem(row) {
  if (!row.materialized) { toast(`Game ${row.game} item ${row.item} is not in the current materialized index.`); return; }
  $("#watchlist-dialog").close();
  await selectGame(row.game);
  await selectItem(row.item, {scroll: true});
}

function renderWatchboardNarrative(result) {
  const host = $("#watchboard-narrative"); clear(host);
  const lead = result.rows.find(row => row.materialized);
  const focusValue = result.reviewerAvailable ? result.totals.combinedEvidenceLoad : result.totals.issuerForegoneLowerBound;
  host.dataset.tone = result.totals.unavailableItems ? "warning" : result.totals.itemsWithPositivePriority ? "evidence" : "quiet";
  host.append(
    element("div", {class: "watchboard-narrative-primary"}, [
      element("span", {text: result.reviewerAvailable ? "FIXED WATCHED UNIVERSE · TWO-ROLE EVIDENCE" : "DEGRADED · ISSUER EVIDENCE ONLY"}),
      element("strong", {text: `${formatNumber(result.totals.materializedItems)} of ${formatNumber(result.totals.requestedIdentifiers)} watched identifiers materialised`}),
      element("small", {text: `${watchboardSortLabel(result.sort)} lens · ${formatCurrency(focusValue)} selected evidence${result.reviewerAvailable ? " load" : " lower bound"} · sorting changes order only`}),
    ]),
    element("div", {class: "watchboard-narrative-fact"}, [
      element("span", {text: "FIRST ATTENTION ROW"}),
      element("strong", {text: lead ? `Game ${lead.game} item ${lead.item}` : "no materialized item"}),
      element("small", {text: lead ? `${watchboardModeLabel(lead.mode)} · ${watchboardPriorityText(lead, result.sort)} under current lens` : "the fixed identifier universe remains visible below"}),
    ]),
    element("div", {class: "watchboard-narrative-fact"}, [
      element("span", {text: "STRICTLY PRIOR CONTEXT"}),
      element("strong", {text: `${formatNumber(result.totals.itemsWithPriorMetric)} / ${formatNumber(result.totals.materializedItems)} items have metric observations`}),
      element("small", {text: `${formatNumber(result.totals.thinPriorContext)} watched items have fewer than five matching prior peers · no semantic matching`}),
    ]),
    element("div", {class: "watchboard-narrative-fact"}, [
      element("span", {text: "INVISIBLE / MISSING EVIDENCE"}),
      element("strong", {text: result.reviewerAvailable ? `${formatNumber(result.totals.hiddenFraudGroups)} hidden rejected-fraud groups` : "reviewer ledger unavailable"}),
      element("small", {text: `${formatNumber(result.totals.unavailableItems)} identifier rows are not materialized · no hidden attempted amount is inferred`}),
    ]),
  );
}

function renderWatchboardKpis(result) {
  const host = $("#watchboard-kpis"); clear(host); const totals = result.totals;
  const cards = [
    ["Fixed identifiers", formatNumber(totals.requestedIdentifiers), `${formatNumber(totals.materializedItems)} materialized · ${formatNumber(totals.unavailableItems)} unavailable`, ""],
    ["Issuer shortfall LB", formatCurrency(totals.issuerForegoneLowerBound), `${formatNumber(totals.labelledItems)} / ${formatNumber(totals.materializedItems)} watched items carry a sanctioned floor`, "negative"],
    ["Observed wrong review", result.reviewerAvailable ? formatCurrency(totals.wrongReviewerCost) : "unavailable", result.reviewerAvailable ? `${formatNumber(totals.collisions)} same-item two-role collisions` : "degraded mode preserves missingness", result.reviewerAvailable ? "negative" : "warning"],
    ["Hidden fraud groups", result.reviewerAvailable ? formatNumber(totals.hiddenFraudGroups) : "unavailable", "attempted amounts remain invisible and unpriced", "warning"],
    ["Top-item concentration", formatPercent(totals.topOneShare), `top three ${formatPercent(totals.topThreeShare)} · denominator ${formatNumber(totals.itemsWithPositivePriority)} positive-priority items`, ""],
    ["Prior context coverage", formatPercent(totals.materializedItems ? totals.itemsWithPriorMetric / totals.materializedItems : null), `${formatNumber(totals.itemsWithPriorMetric)} watched items with non-missing prior metric`, ""],
  ];
  cards.forEach(([label, value, note, tone]) => host.append(element("div", {class: "watchboard-kpi"}, [element("span", {text: label}), element("strong", {class: tone, text: value}), element("small", {text: note})])));
}

function renderWatchboardAtlas(result) {
  const host = $("#watchboard-atlas-chart"); clear(host);
  const rows = result.rows.filter(row => row.materialized);
  if (!rows.length) { host.append(element("div", {class: "empty-state"}, [element("p", {text: "No watched identifier is present in the current materialized item index."})])); return; }
  const width = 720, height = 410, margin = {left: 75, right: 28, top: 48, bottom: 61};
  const maxX = Math.max(1, ...rows.map(row => Math.max(0, safeNumber(row.issuerForegoneLowerBound))));
  const maxY = result.reviewerAvailable ? Math.max(1, ...rows.map(row => Math.max(0, safeNumber(row.wrongReviewerCost)))) : 1;
  const x = value => margin.left + Math.log1p(Math.max(0, safeNumber(value))) / Math.log1p(maxX) * (width - margin.left - margin.right);
  const y = value => result.reviewerAvailable ? height - margin.bottom - Math.log1p(Math.max(0, safeNumber(value))) / Math.log1p(maxY) * (height - margin.top - margin.bottom) : (margin.top + height - margin.bottom) / 2;
  const svg = svgRoot(width, height, "Watched-item two-role priority atlas");
  [0,.25,.5,.75,1].forEach(part => {
    const xv = Math.expm1(Math.log1p(maxX) * part), xx = x(xv);
    svg.append(svgElement("line", {x1: xx, y1: margin.top, x2: xx, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("text", {x: xx, y: height - 34, class: "axis-label", "text-anchor": "middle"}, formatCurrency(xv, true)));
    if (result.reviewerAvailable) {
      const yv = Math.expm1(Math.log1p(maxY) * part), yy = y(yv);
      svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
      svg.append(svgElement("text", {x: margin.left - 9, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(yv, true)));
    }
  });
  const modeColors = {"two-role-collision": colors.red, "issuer-burden": colors.amber, "reviewer-burden": colors.violet, "hidden-only": colors.blue, "priced-evidence-quiet": colors.green, "issuer-only-degraded": colors.amber, "reviewer-unavailable": colors.muted};
  rows.forEach(row => {
    const hidden = Math.max(0, safeNumber(row.hiddenFraudGroups));
    const point = svgElement("circle", {cx: x(row.issuerForegoneLowerBound), cy: y(row.wrongReviewerCost), r: 5 + Math.min(6, Math.sqrt(hidden)), fill: modeColors[row.mode] || colors.muted, "fill-opacity": .78, stroke: hidden ? colors.violet : "rgba(255,255,255,.34)", "stroke-width": hidden ? 2 : 1, "stroke-dasharray": hidden ? "3 2" : "none", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game} item ${row.item}`});
    addTooltip(point, [`Game ${row.game} item ${row.item} · ${watchboardModeLabel(row.mode)}`, `issuer lower bound ${formatCurrency(row.issuerForegoneLowerBound)} · wrong-review ${result.reviewerAvailable ? formatCurrency(row.wrongReviewerCost) : "unavailable"}`, `${result.reviewerAvailable ? formatNumber(row.hiddenFraudGroups) : "unknown"} hidden groups · ${row.priorMetricObservations} prior metric observations`, `${watchboardSortLabel(result.sort)} priority ${watchboardPriorityText(row, result.sort)}`]);
    point.addEventListener("click", () => openWatchboardItem(row));
    point.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openWatchboardItem(row); } });
    svg.append(point);
  });
  if (!result.reviewerAvailable) svg.append(svgElement("text", {x: width / 2, y: margin.top + 14, fill: colors.amber, "font-size": 8, "font-family": "var(--mono)", "text-anchor": "middle"}, "REVIEWER AXIS UNAVAILABLE · POINTS RETAIN ISSUER POSITION ONLY"));
  svg.append(svgElement("text", {x: width / 2, y: height - 7, class: "axis-title", "text-anchor": "middle"}, "PROVABLE ISSUER SHORTFALL LOWER BOUND · EUR · LOG1P"));
  svg.append(svgElement("text", {x: 16, y: height / 2, class: "axis-title", transform: `rotate(-90 16 ${height / 2})`, "text-anchor": "middle"}, result.reviewerAvailable ? "OBSERVED WRONG-REVIEW SETTLEMENT · EUR · LOG1P" : "REVIEWER EVIDENCE UNAVAILABLE"));
  host.append(svg);
}

function renderWatchboardGeometry(result) {
  const host = $("#watchboard-geometry-chart"); clear(host);
  const allRows = result.rows.filter(row => row.materialized);
  const rows = allRows.slice(0, 30);
  $("#watchboard-geometry-caption").textContent = `${rows.length} of ${allRows.length} materialized rows under ${watchboardSortLabel(result.sort)} lens · ledger retains all`;
  const values = rows.flatMap(row => [row.a, row.b, row.median, row.tLo, row.tHi]).filter(value => Number(value) > 0).map(Number);
  if (!rows.length || !values.length) { host.append(element("div", {class: "empty-state"}, [element("p", {text: "No positive watched decision geometry is materialized."})])); return; }
  let min = Math.min(...values), max = Math.max(...values);
  if (min === max) { min /= 1.2; max *= 1.2; }
  const logMin = Math.log(Math.max(.01, min)), logMax = Math.log(Math.max(.011, max));
  const width = 820, rowHeight = 31, height = 62 + rows.length * rowHeight, margin = {left: 92, right: 42, top: 36, bottom: 36};
  const x = value => margin.left + (Math.log(Math.max(.01, value)) - logMin) / (logMax - logMin || 1) * (width - margin.left - margin.right);
  const svg = svgRoot(width, height, "Watched-item decision geometry on shared log-EUR axis");
  rows.forEach((row, index) => {
    const yy = margin.top + index * rowHeight + 10;
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 9, y: yy + 3, class: "axis-label", "text-anchor": "end"}, `G${row.game}:I${row.item}`));
    if (row.tLo > 0 && row.tHi > 0) svg.append(svgElement("line", {x1: x(row.tLo), y1: yy + 7, x2: x(row.tHi), y2: yy + 7, stroke: colors.green, "stroke-width": 3, "stroke-linecap": "round", "stroke-opacity": .72}));
    if (row.tLo > 0) svg.append(svgElement("line", {x1: x(row.tLo), y1: yy + 2, x2: x(row.tLo), y2: yy + 12, stroke: colors.green, "stroke-width": 2}));
    if (row.tHi > 0) svg.append(svgElement("line", {x1: x(row.tHi), y1: yy + 2, x2: x(row.tHi), y2: yy + 12, stroke: colors.green, "stroke-width": 2}));
    else if (row.tLo > 0) svg.append(svgElement("text", {x: Math.min(width - margin.right - 4, x(row.tLo) + 7), y: yy + 11, fill: colors.faint || colors.muted, "font-size": 6.5, "font-family": "var(--mono)"}, "CEILING ?"));
    if (row.a > 0) svg.append(svgElement("circle", {cx: x(row.a), cy: yy - 3, r: 4, fill: colors.red}));
    if (row.b > 0) svg.append(svgElement("rect", {x: x(row.b) - 3.5, y: yy - 6.5, width: 7, height: 7, fill: colors.amber}));
    if (row.median > 0) svg.append(svgElement("rect", {x: x(row.median) - 3.5, y: yy - 6.5, width: 7, height: 7, fill: colors.cyan, transform: `rotate(45 ${x(row.median)} ${yy - 3})`}));
    const hit = svgElement("rect", {x: margin.left, y: yy - rowHeight / 2, width: width - margin.left - margin.right, height: rowHeight, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game} item ${row.item} decision geometry`});
    addTooltip(hit, [`Game ${row.game} item ${row.item} · ${prettyStatus(row.status)}`, `charge ${formatCurrency(row.a)} · b ${formatCurrency(row.b)} · belief ${formatCurrency(row.median)}`, row.tLo === null ? "sanctioned floor unavailable" : row.tHi === null ? `floor ${formatCurrency(row.tLo)} · ceiling unknown` : `finite bracket ${formatCurrency(row.tLo)}–${formatCurrency(row.tHi)}`, `${row.source} · ${row.bucket}`]);
    hit.addEventListener("click", () => openWatchboardItem(row));
    hit.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openWatchboardItem(row); } });
    svg.append(hit);
  });
  [0,.25,.5,.75,1].forEach(part => { const value = Math.exp(logMin + (logMax - logMin) * part); svg.append(svgElement("text", {x: margin.left + part * (width - margin.left - margin.right), y: height - 12, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true))); });
  svg.append(svgElement("text", {x: margin.left, y: 16, fill: colors.red, "font-size": 7, "font-family": "var(--mono)"}, "● CHARGE"));
  svg.append(svgElement("text", {x: margin.left + 74, y: 16, fill: colors.amber, "font-size": 7, "font-family": "var(--mono)"}, "■ b"));
  svg.append(svgElement("text", {x: margin.left + 118, y: 16, fill: colors.cyan, "font-size": 7, "font-family": "var(--mono)"}, "◆ BELIEF"));
  svg.append(svgElement("text", {x: margin.left + 210, y: 16, fill: colors.green, "font-size": 7, "font-family": "var(--mono)"}, "GREEN RAIL = FINITE PROVEN BRACKET · LONE TICK = CEILING UNKNOWN"));
  host.append(svg);
}

function renderWatchboardQueue(result) {
  const host = $("#watchlist-items"); clear(host);
  result.rows.forEach((row, index) => {
    const shell = element("div", {class: `watchlist-row mode-${cssStatus(row.mode)}`});
    shell.append(element("span", {class: "watchlist-rank", text: `#${index + 1}`}));
    const open = element("button", {type: "button", class: "watchlist-open", disabled: row.materialized ? null : true}, [
      element("strong", {text: `game ${row.game} item ${row.item}`}),
      element("small", {text: row.materialized ? `${watchboardModeLabel(row.mode)} · ${row.source} · ${row.bucket}` : "identifier absent from current materialized index"}),
    ]);
    if (row.materialized) open.addEventListener("click", () => openWatchboardItem(row));
    const priority = element("div", {class: "watchlist-priority"}, [element("strong", {text: watchboardPriorityText(row, result.sort)}), element("small", {text: watchboardSortLabel(result.sort)})]);
    const remove = element("button", {type: "button", class: "watchlist-remove", text: "Remove", "aria-label": `Remove game ${row.game} item ${row.item} from watchlist`});
    remove.addEventListener("click", () => {
      state.watches.delete(watchKey(row.game, row.item));
      saveWatches(); renderWatchlist(); renderWatchState(); renderLedger();
    });
    shell.append(open, priority, remove); host.append(shell);
  });
}

function renderWatchboardContract(result) {
  const host = $("#watchboard-contract-card"); clear(host);
  const modes = Object.entries(result.modeCounts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  host.append(
    element("span", {text: "BOARD CONTRACT"}),
    element("strong", {text: `${formatNumber(result.totals.requestedIdentifiers)} fixed identifiers`}),
    element("p", {text: `${formatNumber(result.totals.materializedItems)} materialized · ${formatNumber(result.totals.unavailableItems)} unavailable · current sort never changes this denominator.`}),
    element("div", {class: "watchboard-mode-list"}, modes.map(([mode, count]) => element("div", {}, [element("span", {text: watchboardModeLabel(mode)}), element("strong", {text: count})]))),
    element("p", {text: result.reviewerAvailable ? "Reviewer evidence is joined transiently. Every hidden rejected-fraud group stays count-only." : "Degraded mode: reviewer-derived economics and hidden-group counts stay unavailable; issuer lower bounds and decision geometry remain readable."}),
    element("p", {text: "Peer context is source × sanctioned-floor regime and strictly lower-game only. It is numeric context—not semantic matching or a valuation recommendation."}),
  );
}

function renderWatchboardLedger(result) {
  const body = $("#watchboard-ledger"); clear(body);
  result.rows.forEach((row, index) => body.append(element("tr", {}, [
    element("td", {text: `#${index + 1} · ${watchboardPriorityText(row, result.sort)}`}),
    element("td", {}, [row.materialized ? itemLink(row.game, row.item) : element("span", {text: `game ${row.game} item ${row.item}`})]),
    element("td", {text: watchboardModeLabel(row.mode)}), element("td", {text: row.materialized ? row.source : "unavailable"}),
    element("td", {text: row.materialized ? row.bucket : "unavailable"}), element("td", {text: row.materialized ? prettyStatus(row.status) : "unavailable"}),
    element("td", {class: "money", text: row.materialized ? formatCurrency(row.a) : "unavailable"}),
    element("td", {class: "money", text: row.materialized ? formatCurrency(row.b) : "unavailable"}),
    element("td", {class: "money", text: row.materialized ? formatCurrency(row.median) : "unavailable"}),
    element("td", {class: "money", text: row.materialized ? formatCurrency(row.tLo) : "unavailable"}),
    element("td", {class: "money", text: row.materialized ? (row.tHi === null ? "unknown" : formatCurrency(row.tHi)) : "unavailable"}),
    element("td", {class: "money", text: row.materialized ? formatCurrency(row.issuerForegoneLowerBound) : "unavailable"}),
    element("td", {class: "money", text: row.materialized && result.reviewerAvailable ? formatCurrency(row.wrongReviewerCost) : "unavailable"}),
    element("td", {text: row.materialized && result.reviewerAvailable ? formatNumber(row.hiddenFraudGroups) : "unavailable"}),
    element("td", {text: row.materialized ? formatPercent(row.priorPercentile) : "unavailable"}),
    element("td", {text: row.materialized ? `${formatNumber(row.priorMetricObservations)} / ${formatNumber(row.priorPeerCount)} peers` : "unavailable"}),
  ])));
}

async function copyWatchboardReceipt() {
  if (!state.watchboardResult || !state.overview) { toast("Watchboard evidence is unavailable to copy."); return; }
  try { await navigator.clipboard.writeText(JSON.stringify(buildWatchboardReceipt(state.watchboardResult, state.overview.generatedAt), null, 2)); toast("Identifier-only watchboard receipt copied."); }
  catch (error) { toast(`Watchboard receipt could not be copied: ${error.message}`); }
}

function renderWatchlist() {
  state.watchboardSort = WATCHBOARD_SORTS.has(state.watchboardSort) ? state.watchboardSort : "triage";
  $("#watchboard-sort").value = state.watchboardSort;
  const result = buildWatchboard(state.overview?.itemIndex || [], allPeerRegretRows(), [...state.watches], {sort: state.watchboardSort, reviewerAvailable: Boolean(state.reviewerLab)});
  state.watchboardResult = result;
  $("#watchboard-denominator").textContent = `${formatNumber(result.totals.requestedIdentifiers)} identifiers`;
  $("#watchboard-status").textContent = !result.available ? "EMPTY · IDENTIFIER-ONLY" : result.reviewerAvailable ? `${formatNumber(result.totals.materializedItems)} MATERIALIZED · REVIEWER JOIN ACTIVE` : `${formatNumber(result.totals.materializedItems)} MATERIALIZED · REVIEWER JOIN DEGRADED`;
  $("#watchboard-empty").hidden = result.available;
  $("#watchboard-workspace").hidden = !result.available;
  if (!result.available) return;
  renderWatchboardNarrative(result); renderWatchboardKpis(result); renderWatchboardAtlas(result);
  renderWatchboardGeometry(result); renderWatchboardQueue(result); renderWatchboardContract(result); renderWatchboardLedger(result);
}

function scenarioDomain(item) {
  const values = [item.decision?.a, item.decision?.b, item.belief?.median,
    item.threshold?.tLo, item.threshold?.tHi,
    ...(item.opponentDecisions || []).map(row => row.charge)].filter(Number.isFinite);
  return Math.max(100, ...values) * 1.6;
}

function setupScenario() {
  const item = state.itemDetail;
  if (!item) return;
  const charge = $("#scenario-charge"), limit = $("#scenario-limit");
  const max = Math.ceil(scenarioDomain(item));
  charge.max = String(max); limit.max = String(max);
  charge.step = String(Math.max(1, Math.round(max / 1200)));
  limit.step = charge.step;
  charge.value = String(clamp(safeNumber(item.decision?.a), 0, max));
  limit.value = String(clamp(safeNumber(item.decision?.b), 0, max));
  renderScenario();
}

function applyScenarioPreset(preset) {
  const item = state.itemDetail;
  if (!item) return;
  const charge = $("#scenario-charge"), limit = $("#scenario-limit");
  if (preset === "actual") {
    charge.value = String(item.decision?.a || 0); limit.value = String(item.decision?.b || 0);
  } else if (preset === "floor") {
    if (Number.isFinite(item.threshold?.tLo)) charge.value = String(item.threshold.tLo);
  } else if (preset === "median") {
    if (Number.isFinite(item.belief?.median)) charge.value = String(item.belief.median);
  } else if (preset === "reject-hidden") {
    limit.value = "0";
  }
  renderScenario();
}

function scenarioEvaluation(a, b) {
  const item = state.itemDetail;
  const threshold = item.threshold;
  let issuerState = "unprovable";
  let provenIncome = null;
  if (threshold && a <= threshold.tLo) {
    issuerState = "certainly fair";
    provenIncome = 16 * a;
  } else if (threshold?.tHi !== null && threshold?.tHi !== undefined && a > threshold.tHi) {
    issuerState = "certainly fraud";
    provenIncome = 0;
  }
  let exactFairCost = 0, actualFairCost = 0, fairAccepted = 0, fairRejected = 0;
  let unpricedFraud = 0, definitelyRejectedFraud = 0;
  for (const row of item.opponentDecisions || []) {
    if (row.classification === "fair" && Number.isFinite(row.charge)) {
      const accept = row.charge <= b;
      exactFairCost += row.charge * (accept ? 1 : 1.5);
      actualFairCost += safeNumber(row.ourReviewerCost);
      if (accept) fairAccepted++; else fairRejected++;
    } else if (row.classification === "fraud") {
      if (row.chargeKind === "lower_bound" && b < row.charge || b <= 0) definitelyRejectedFraud++;
      else unpricedFraud++;
    }
  }
  const currentA = item.decision?.a;
  const currentFair = threshold && Number.isFinite(currentA) && currentA <= threshold.tLo;
  const candidateFair = issuerState === "certainly fair";
  const provenDelta = currentFair && candidateFair ? 16 * (a - currentA) : null;
  return {issuerState, provenIncome, exactFairCost, actualFairCost, fairAccepted,
          fairRejected, unpricedFraud, definitelyRejectedFraud, provenDelta};
}

function renderScenario() {
  const item = state.itemDetail;
  if (!item) return;
  const a = safeNumber($("#scenario-charge").value);
  const b = safeNumber($("#scenario-limit").value);
  $("#scenario-charge-output").textContent = formatCurrency(a);
  $("#scenario-limit-output").textContent = formatCurrency(b);
  const evaluation = scenarioEvaluation(a, b);
  const host = $("#scenario-chart"); clear(host);
  const width = 650, height = 340, margin = {left: 65, right: 35, top: 45, bottom: 55};
  const max = scenarioDomain(item), plotW = width - margin.left - margin.right;
  const x = value => margin.left + Math.log1p(Math.max(0, value)) / Math.log1p(max) * plotW;
  const svg = svgRoot(width, height, "Client-only counterfactual decision against proven evidence");
  for (let index = 0; index <= 4; index++) {
    const value = max * index / 4, px = x(value);
    svg.append(svgElement("line", {x1: px, y1: margin.top, x2: px, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("text", {x: px, y: height - 31, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true)));
  }
  if (item.threshold) {
    const lo = x(item.threshold.tLo);
    const end = Number.isFinite(item.threshold.tHi) ? x(item.threshold.tHi) : width - margin.right;
    svg.append(svgElement("rect", {x: lo, y: 126, width: Math.max(2, end - lo), height: 54, rx: 7, fill: colors.blue, "fill-opacity": .16, stroke: colors.blue, "stroke-dasharray": item.threshold.tHi === null ? "5 5" : "0"}));
    svg.append(svgElement("text", {x: lo, y: 112, fill: colors.blue, "font-family": "monospace", "font-size": 10}, `PROVEN FLOOR ${formatCurrency(item.threshold.tLo)}`));
  }
  [["candidate a", a, colors.violet, 82], ["candidate b", b, colors.amber, 218], ["actual a", item.decision?.a, colors.cyan, 54]].forEach(([label, value, color, y]) => {
    if (!Number.isFinite(value)) return;
    svg.append(svgElement("line", {x1: x(value), y1: y, x2: x(value), y2: y + 58, stroke: color, "stroke-width": label.startsWith("actual") ? 1.2 : 3, "stroke-dasharray": label.startsWith("actual") ? "3 4" : "0"}));
    svg.append(svgElement("text", {x: x(value), y: y - 8, fill: color, "font-family": "monospace", "font-size": 9, "text-anchor": "middle"}, `${label} ${formatCurrency(value)}`));
  });
  host.append(svg);
  const results = $("#scenario-results"); clear(results);
  const specs = [
    ["Issuer proof state", evaluation.issuerState, evaluation.provenIncome === null ? "No euro credit: charge lies in an unprovable interval." : `Conservative proven income ${formatCurrency(evaluation.provenIncome)}.`],
    ["Proven issuer delta", evaluation.provenDelta === null ? "unpriced" : signed(evaluation.provenDelta), "Comparable only when actual and candidate charges are both certainly fair."],
    ["Exact fair reviewer cost", formatCurrency(evaluation.exactFairCost), `${evaluation.fairAccepted} accepted · ${evaluation.fairRejected} rejected · actual ${formatCurrency(evaluation.actualFairCost)}`],
    ["Invisible fraud exposure", `${evaluation.unpricedFraud} unpriced`, `${evaluation.definitelyRejectedFraud} proven to remain rejected; no hidden amount was invented.`],
  ];
  specs.forEach(([label, value, note]) => results.append(element("div", {class: "scenario-result"}, [
    element("span", {text: label}), element("strong", {text: value}), element("small", {text: note}),
  ])));
}

function renderItemInterval() {
  const host = $("#item-interval"); clear(host);
  const item = state.itemDetail;
  const decision = item.decision || {};
  const threshold = item.threshold || {};
  const rows = item.opponents || [];
  const values = [decision.a, decision.b, threshold.tLo, threshold.tHi, ...rows.map(row => row.charge)]
    .filter(Number.isFinite);
  const max = Math.max(10, ...values) * 1.16;
  const width = 820, height = 330, margin = {left: 76, right: 35, top: 35, bottom: 54};
  const plotW = width - margin.left - margin.right;
  const x = value => margin.left + Math.log1p(Math.max(0, value)) / Math.log1p(max) * plotW;
  const svg = svgRoot(width, height, `Valuation evidence for game ${item.game} item ${item.idx}`);
  for (let i = 0; i <= 4; i++) {
    const value = max * i / 4;
    const px = x(value);
    svg.append(svgElement("line", {x1: px, y1: margin.top, x2: px, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("text", {x: px, y: height - 30, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true)));
  }
  const lo = threshold.tLo;
  const hi = threshold.tHi;
  if (Number.isFinite(lo)) {
    const end = Number.isFinite(hi) ? x(hi) : width - margin.right;
    svg.append(svgElement("rect", {x: x(lo), y: 120, width: Math.max(2, end - x(lo)), height: 40, rx: 6, fill: colors.blue, "fill-opacity": .18, stroke: colors.blue, "stroke-dasharray": hi === null ? "0 7 2 7" : "0"}));
    svg.append(svgElement("text", {x: x(lo), y: 111, class: "series-label"}, `t ≥ ${formatCurrency(lo)}`));
    if (Number.isFinite(hi)) svg.append(svgElement("text", {x: x(hi), y: 111, class: "series-label", "text-anchor": "end"}, `t < ${formatCurrency(hi)}`));
    else svg.append(svgElement("text", {x: width - margin.right, y: 111, class: "series-label", "text-anchor": "end"}, "ceiling unknown →"));
  }
  [["a · charge", decision.a, colors.cyan, 77], ["b · limit", decision.b, colors.amber, 188]].forEach(([label, value, color, y]) => {
    if (!Number.isFinite(value)) return;
    svg.append(svgElement("line", {x1: x(value), y1: y - 18, x2: x(value), y2: y + 35, stroke: color, "stroke-width": 3}));
    svg.append(svgElement("text", {x: x(value), y: y - 25, fill: color, "font-family": "var(--mono)", "font-size": 11, "text-anchor": "middle"}, `${label} ${formatCurrency(value)}`));
  });
  rows.forEach((row, index) => {
    if (!Number.isFinite(row.charge)) return;
    const cy = 240 + (index % 3) * 10;
    const marker = svgElement("circle", {cx: x(row.charge), cy, r: 3.5, fill: row.classification === "fraud" ? colors.red : row.classification === "fair" ? colors.green : colors.muted, "fill-opacity": .75, tabindex: 0, class: "interactive"});
    addTooltip(marker, [row.team, `${row.chargeKind.replaceAll("_", " ")} · ${formatCurrency(row.charge)}`, `proven side · ${row.classification}`]);
    svg.append(marker);
  });
  svg.append(svgElement("text", {x: margin.left, y: 269, class: "axis-label"}, "FIELD CHARGES · jittered for visibility"));
  host.append(svg);
}

function pairText(pair) { return pair ? `a ${formatCurrency(pair[0])} · b ${formatCurrency(pair[1])}` : "decision unavailable"; }
function renderRules() {
  const host = $("#rule-tape"); clear(host);
  const rules = state.itemDetail.rules || [];
  $("#rule-count").textContent = `${rules.length} firing${rules.length === 1 ? "" : "s"}`;
  if (!rules.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No rule.fired events were logged for this item."})]));
    return;
  }
  rules.forEach(rule => {
    host.append(element("div", {class: `rule-row ${rule.shadow ? "ghost" : ""}`}, [
      element("span", {class: "rule-node", "aria-hidden": "true"}),
      element("div", {class: "rule-name"}, [rule.rule, element("small", {text: rule.shadow ? "SHADOW · counterfactual only" : "PRODUCTION PATH"})]),
      element("div", {class: "rule-values"}, [element("span", {text: pairText(rule.from)}), element("br"), element("strong", {text: `→ ${pairText(rule.to)}`})]),
    ]));
  });
}

function chargeEvidence(row) {
  if (row.chargeKind === "exact") return formatCurrency(row.charge);
  if (row.chargeKind === "lower_bound") return `≥ ${formatCurrency(row.charge)}`;
  if (row.chargeKind === "observed_payout") return `payout ${formatCurrency(row.charge)}`;
  return "hidden";
}

function renderOpponentTable() {
  const body = $("#opponent-table"); clear(body);
  const rows = state.itemDetail.opponentDecisions || [];
  rows.forEach(row => {
    const accepted = row.weAccepted;
    body.append(element("tr", {}, [
      element("td", {text: row.team}),
      element("td", {class: "money", text: chargeEvidence(row)}),
      element("td", {}, [element("span", {class: `truth ${row.classification === "fraud" ? "negative" : row.classification === "fair" ? "positive" : "warning"}`, text: row.classification})]),
      element("td", {text: accepted === null ? "no row" : accepted ? "accepted" : "rejected"}),
      element("td", {class: "money", text: formatCurrency(row.issuerPayout)}),
      element("td", {class: "money", text: formatCurrency(row.ourReviewerCost)}),
    ]));
  });
}

function renderDocuments() {
  const data = state.caseData;
  if (!data) return;
  $("#document-empty").hidden = true;
  $("#document-workspace").hidden = false;
  const sourceHost = $("#source-items"); clear(sourceHost);
  data.items.forEach(item => {
    const button = element("button", {type: "button", class: `source-item ${item.idx === state.selectedItem ? "selected" : ""}`}, [
      element("strong", {text: item.idx}),
      element("span", {}, [item.description, element("small", {text: `POS ${item.pos} · ${formatNumber(item.qty, 3)} ${item.unit}${item.sourcePage ? ` · PAGE ${item.sourcePage}` : ""}`})]),
    ]);
    button.addEventListener("click", () => selectItem(item.idx));
    sourceHost.append(button);
  });
  const selected = data.items.find(row => row.idx === state.selectedItem) || data.items[0];
  const pdf = data.pdfs?.[0];
  const frame = $("#invoice-frame");
  if (pdf) {
    const page = selected?.sourcePage || 1;
    const nextSrc = `${pdf.url}#page=${page}&view=FitH`;
    if (frame.dataset.base !== pdf.url || frame.dataset.page !== String(page)) {
      frame.src = nextSrc;
      frame.dataset.base = pdf.url;
      frame.dataset.page = String(page);
    }
    frame.hidden = false;
    $("#invoice-page-label").textContent = `Native text-layer PDF · ${data.invoicePageCount || "?"} page${data.invoicePageCount === 1 ? "" : "s"} · showing ${page}`;
  } else {
    frame.hidden = true;
    $("#invoice-page-label").textContent = "No PDF discovered in extracted case";
  }
  renderPolicy();
  $("#damage-description").textContent = data.damageDescription || "No separate damage description was found.";
  const grid = $("#photo-grid"); clear(grid);
  (data.images || []).forEach((image, index) => {
    const img = element("img", {src: image.url, alt: `Damage photograph ${index + 1}`, loading: "lazy"});
    const button = element("button", {type: "button", class: "photo-button", "aria-label": `Open damage photograph ${index + 1}`}, [img]);
    button.addEventListener("click", () => openLightbox(image.url, image.name));
    grid.append(button);
  });
  if (!data.images?.length) grid.append(element("p", {class: "micro-note", text: "No damage photographs found."}));
}

function relevantTerms() {
  const description = caseItem(state.selectedItem)?.description || "";
  const stop = new Set(["with", "from", "this", "that", "und", "oder", "eine", "einer", "the", "for"]);
  return [...new Set(description.toLocaleLowerCase().match(/[\p{L}\p{N}]{5,}/gu) || [])]
    .filter(word => !stop.has(word)).slice(0, 3);
}

function renderPolicy(explicit = null) {
  const host = $("#policy-text"); clear(host);
  const text = state.caseData?.policyText || "No policy text was found.";
  const input = $("#policy-search");
  if (explicit === null && !input.value && state.selectedItem) input.value = relevantTerms().join(" ");
  const terms = (explicit ?? input.value).toLocaleLowerCase().match(/[\p{L}\p{N}]{3,}/gu) || [];
  if (!terms.length) { host.textContent = text; return; }
  const pattern = new RegExp(`(${terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "giu");
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    host.append(document.createTextNode(text.slice(cursor, match.index)));
    host.append(element("mark", {text: match[0]}));
    cursor = match.index + match[0].length;
  }
  host.append(document.createTextNode(text.slice(cursor)));
}

function openLightbox(url, caption) {
  $("#lightbox-image").src = url;
  $("#lightbox-caption").textContent = caption;
  $("#lightbox").showModal();
}

function renderEconomics() {
  const host = $("#economics-chart"); clear(host);
  const rows = state.overview.trends.economics;
  if (!rows.length) return;
  const width = 900, height = 350, margin = {top: 24, right: 30, bottom: 48, left: 78};
  const values = rows.flatMap(row => [row.income, -row.cost, row.net, row.rollingMedian5]);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const svg = svgRoot(width, height, "Oasis income, cost, net and rolling median by game");
  const scale = chartScaffold(svg, width, height, margin, min, max, 5);
  const specs = [
    ["Income", row => row.income, colors.green, "3 5"],
    ["Cost", row => -row.cost, colors.red, "3 5"],
    ["Net", row => row.net, colors.cyan, ""],
    ["Rolling median", row => row.rollingMedian5, colors.amber, ""],
  ];
  specs.forEach(([name, accessor, color, dash], index) => {
    const points = rows.map((row, i) => [scale.x(i, rows.length), scale.y(accessor(row))]);
    svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: color, "stroke-width": index > 1 ? 2.4 : 1.3, "stroke-dasharray": dash, "stroke-opacity": index > 1 ? .95 : .55}));
    svg.append(svgElement("text", {x: margin.left + index * 120, y: 14, fill: color, "font-family": "var(--mono)", "font-size": 9}, name.toUpperCase()));
  });
  rows.forEach((row, i) => {
    const target = svgElement("rect", {x: scale.x(i, rows.length) - 6, y: margin.top, width: 12, height: scale.plotH, fill: "transparent", tabindex: 0, class: "interactive"});
    addTooltip(target, [`Game ${row.game}`, `Income ${formatCurrency(row.income)} · cost ${formatCurrency(row.cost)}`, `Net ${signed(row.net)} · 5-game median ${signed(row.rollingMedian5)}`]);
    target.addEventListener("click", () => selectGame(row.game, {scroll: true}));
    svg.append(target);
  });
  host.append(svg);
  const body = $("#economics-data-table"); clear(body);
  rows.forEach(row => body.append(element("tr", {}, [
    element("td", {text: row.game}), element("td", {class: "money", text: formatCurrency(row.income)}),
    element("td", {class: "money", text: formatCurrency(row.cost)}),
    element("td", {class: `money ${row.net >= 0 ? "positive" : "negative"}`, text: signed(row.net)}),
    element("td", {class: "money", text: signed(row.rollingMedian5)}),
  ])));
}

function incomeCostFrontier(rows) {
  return rows.filter(row => !rows.some(other => other !== row &&
    safeNumber(other.income) >= safeNumber(row.income) &&
    safeNumber(other.cost) <= safeNumber(row.cost) &&
    (safeNumber(other.income) > safeNumber(row.income) || safeNumber(other.cost) < safeNumber(row.cost))));
}

function renderRoundMap() {
  const all = state.overview.trends.economics.map(row => ({...row}));
  const quality = new Map(state.overview.intelligence.quality.map(row => [row.game, row]));
  const frontier = incomeCostFrontier(all);
  const frontierGames = new Set(frontier.map(row => row.game));
  const recentGames = new Set(all.slice(-10).map(row => row.game));
  const filterLabels = {all: "All games", recent: "Last 10", positive: "Net positive", frontier: "Pareto frontier"};
  const filtered = all.filter(row => state.roundMapFilter === "all" ||
    state.roundMapFilter === "recent" && recentGames.has(row.game) ||
    state.roundMapFilter === "positive" && row.net > 0 ||
    state.roundMapFilter === "frontier" && frontierGames.has(row.game));
  const visibleGames = new Set(filtered.map(row => row.game));
  $$('[data-round-map]').forEach(button => {
    const active = button.dataset.roundMap === state.roundMapFilter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  const latest = all.at(-1);
  const efficientBest = [...frontier].sort((a, b) => b.net - a.net)[0];
  const summary = $("#round-map-summary"); clear(summary);
  [
    ["Active cohort", `${filtered.length} / ${all.length}`, `${filterLabels[state.roundMapFilter]} · denominator played games`],
    ["Non-dominated", `${frontier.length} / ${all.length}`, "maximise observed income · minimise observed reviewer cost"],
    ["Best frontier net", efficientBest ? signed(efficientBest.net) : "unknown", efficientBest ? `game ${efficientBest.game} · observed game EUR` : "no played games"],
    ["Latest round", latest ? `G${latest.game} · ${signed(latest.net)}` : "unknown", latest ? `${formatCurrency(latest.income)} income · ${formatCurrency(latest.cost)} cost` : "no played games"],
  ].forEach(([label, value, note]) => summary.append(element("div", {class: "round-map-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));

  const host = $("#round-phase-chart"); clear(host);
  if (!all.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No played-game economics are available."})]));
    return;
  }
  const width = 1120, height = 610, margin = {left: 88, right: 48, top: 48, bottom: 76};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const maxIncome = Math.max(1, ...all.map(row => row.income)) * 1.06;
  const maxCost = Math.max(1, ...all.map(row => row.cost)) * 1.06;
  const x = value => margin.left + Math.log1p(Math.max(0, safeNumber(value))) / Math.log1p(maxIncome) * plotW;
  const y = value => margin.top + (1 - Math.log1p(Math.max(0, safeNumber(value))) / Math.log1p(maxCost)) * plotH;
  const svg = svgRoot(width, height, "Played-game income versus reviewer-cost phase space with Pareto frontier");
  for (let tick = 0; tick <= 5; tick++) {
    const fraction = tick / 5;
    const income = Math.expm1(Math.log1p(maxIncome) * fraction);
    const cost = Math.expm1(Math.log1p(maxCost) * fraction);
    const tickX = margin.left + plotW * fraction, tickY = margin.top + plotH * (1 - fraction);
    svg.append(svgElement("line", {x1: tickX, y1: margin.top, x2: tickX, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("line", {x1: margin.left, y1: tickY, x2: width - margin.right, y2: tickY, class: "grid-line"}));
    svg.append(svgElement("text", {x: tickX, y: height - margin.bottom + 24, class: "axis-label", "text-anchor": "middle"}, formatCurrency(income, true)));
    svg.append(svgElement("text", {x: margin.left - 11, y: tickY + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(cost, true)));
  }
  const breakEvenMax = Math.min(maxIncome, maxCost);
  const breakEven = Array.from({length: 61}, (_, index) => breakEvenMax * index / 60).map(value => [x(value), y(value)]);
  svg.append(svgElement("path", {d: linePath(breakEven), fill: "none", stroke: colors.amber, "stroke-width": 1.4, "stroke-dasharray": "6 6", "stroke-opacity": .7}));
  svg.append(svgElement("text", {x: x(breakEvenMax * .72), y: y(breakEvenMax * .72) - 9, fill: colors.amber, "font-family": "var(--mono)", "font-size": 8, "text-anchor": "middle"}, "BREAK-EVEN · INCOME = COST"));
  svg.append(svgElement("text", {x: width - margin.right, y: margin.top - 17, fill: colors.green, "font-family": "var(--mono)", "font-size": 8, "text-anchor": "end"}, "IDEAL DIRECTION ↗ INCOME / ↘ COST"));

  const trajectory = all.map(row => [x(row.income), y(row.cost)]);
  svg.append(svgElement("path", {d: linePath(trajectory), fill: "none", stroke: colors.muted, "stroke-width": 1, "stroke-opacity": .28}));
  const frontierPath = [...frontier].sort((a, b) => a.income - b.income).map(row => [x(row.income), y(row.cost)]);
  svg.append(svgElement("path", {d: linePath(frontierPath), fill: "none", stroke: colors.violet, "stroke-width": 2.2, "stroke-opacity": .85}));

  all.forEach((row, index) => {
    const selected = row.game === state.selectedGame;
    const included = visibleGames.has(row.game);
    const onFrontier = frontierGames.has(row.game);
    const items = safeNumber(quality.get(row.game)?.items);
    const radius = 3.5 + Math.min(7, Math.sqrt(items) * .72);
    const fill = row.net >= 0 ? colors.green : colors.red;
    const dot = svgElement("circle", {cx: x(row.income), cy: y(row.cost), r: selected ? radius + 3 : radius, fill, "fill-opacity": included ? .72 : .08, stroke: selected ? colors.cyan : onFrontier ? colors.violet : fill, "stroke-width": selected ? 3 : onFrontier ? 2 : 1, "stroke-opacity": included ? .95 : .13, tabindex: 0, class: "interactive", role: "button", "aria-label": `Open game ${row.game}: income ${formatCurrency(row.income)}, reviewer cost ${formatCurrency(row.cost)}, net ${signed(row.net)}${onFrontier ? ", Pareto frontier" : ""}`});
    addTooltip(dot, [`Game ${row.game}${onFrontier ? " · PARETO FRONTIER" : ""}`, `Income ${formatCurrency(row.income)} · reviewer cost ${formatCurrency(row.cost)}`, `Net ${signed(row.net)} · ${items} items`, `Trajectory position ${index + 1} / ${all.length} played games`]);
    dot.addEventListener("click", () => selectGame(row.game, {scroll: true}));
    svg.append(dot);
  });
  svg.append(svgElement("text", {x: margin.left + plotW / 2, y: height - 19, class: "axis-label", "text-anchor": "middle"}, "OBSERVED OASIS ISSUER INCOME · log1p EUR →"));
  svg.append(svgElement("text", {x: 20, y: margin.top + plotH / 2, class: "axis-label", "text-anchor": "middle", transform: `rotate(-90 20 ${margin.top + plotH / 2})`}, "OBSERVED OASIS REVIEWER COST · log1p EUR →"));
  host.append(svg);

  const body = $("#round-map-table"); clear(body);
  filtered.forEach(row => {
    const items = safeNumber(quality.get(row.game)?.items);
    const ratio = row.cost > 0 ? row.income / row.cost : null;
    const open = element("button", {type: "button", class: "table-link", text: `game ${row.game}`});
    open.addEventListener("click", () => selectGame(row.game, {scroll: true}));
    body.append(element("tr", {}, [
      element("td", {}, [open]), element("td", {class: "money", text: formatCurrency(row.income)}),
      element("td", {class: "money", text: formatCurrency(row.cost)}),
      element("td", {class: `money ${row.net >= 0 ? "positive" : "negative"}`, text: signed(row.net)}),
      element("td", {text: formatNumber(items)}), element("td", {text: frontierGames.has(row.game) ? "non-dominated" : "dominated"}),
      element("td", {text: ratio === null ? "no observed cost" : `${formatNumber(ratio, 3)}×`}),
    ]));
  });
}

function renderPhases() {
  const host = $("#phase-chart"); clear(host);
  const rows = state.overview.intelligence.phases;
  if (!rows.length) return;
  const width = 850, height = 340, margin = {left: 76, right: 35, top: 30, bottom: 57};
  const values = rows.flatMap(row => [row.net, row.meanNet, row.medianNet]);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const svg = svgRoot(width, height, "Ten-game performance phases");
  const scale = chartScaffold(svg, width, height, margin, min, max, 5);
  const step = scale.plotW / rows.length;
  rows.forEach((row, index) => {
    const x = margin.left + step * (index + .16), barW = step * .42;
    const zero = scale.y(0), y = scale.y(row.net);
    const rect = svgElement("rect", {x, y: Math.min(y, zero), width: barW, height: Math.max(2, Math.abs(zero - y)), rx: 4, fill: row.net >= 0 ? colors.green : colors.red, "fill-opacity": .62, tabindex: 0, class: "interactive"});
    addTooltip(rect, [row.label, `Net ${signed(row.net)} · mean ${signed(row.meanNet)} · median ${signed(row.medianNet)}`, `Positive games ${formatPercent(row.positiveRate)} · volatility ${formatCurrency(row.volatility)}`]);
    svg.append(rect);
    const rateY = margin.top + scale.plotH * (1 - row.positiveRate);
    svg.append(svgElement("circle", {cx: x + barW / 2, cy: rateY, r: 4, fill: colors.cyan, stroke: "#090b0d", "stroke-width": 2}));
    svg.append(svgElement("text", {x: x + barW / 2, y: height - 31, class: "axis-label", "text-anchor": "middle"}, row.label));
  });
  svg.append(svgElement("text", {x: margin.left, y: 15, fill: colors.cyan, "font-family": "monospace", "font-size": 9}, "DOT · POSITIVE-GAME RATE (0% BOTTOM / 100% TOP)"));
  host.append(svg);
  const list = $("#phase-list"); clear(list);
  rows.forEach(row => list.append(element("div", {class: "phase-row"}, [
    element("strong", {text: row.label}), element("span", {text: `${formatPercent(row.positiveRate)} positive · volatility ${formatCurrency(row.volatility, true)}`}),
    element("span", {text: `median ${signed(row.medianNet)}`}), element("strong", {class: row.net >= 0 ? "positive" : "negative", text: signed(row.net)}),
  ])));
}

function renderSources() {
  const host = $("#source-chart"); clear(host);
  const rows = state.overview.intelligence.sources;
  if (!rows.length) return;
  const width = 850, height = Math.max(330, rows.length * 45 + 80), margin = {left: 190, right: 30, top: 28, bottom: 43};
  const plotW = width - margin.left - margin.right, rowH = (height - margin.top - margin.bottom) / rows.length;
  const svg = svgRoot(width, height, "Belief-source item states and labelled coverage");
  rows.forEach((row, index) => {
    const y = margin.top + index * rowH + rowH * .22, h = rowH * .56;
    svg.append(svgElement("text", {x: margin.left - 10, y: y + h * .72, class: "axis-label", "text-anchor": "end"}, row.source.length > 24 ? `${row.source.slice(0, 23)}…` : row.source));
    const segments = [["under", row.under, colors.red], ["inside", row.inside, colors.green], ["over", row.over, colors.blue], ["unlabelled", Math.max(0, row.items - row.under - row.inside - row.over), colors.muted]];
    let offset = 0;
    segments.forEach(([label, value, color]) => {
      const segmentW = plotW * value / Math.max(1, row.items);
      const rect = svgElement("rect", {x: margin.left + offset, y, width: Math.max(0, segmentW), height: h, fill: color, "fill-opacity": label === "unlabelled" ? .18 : .62, tabindex: value ? 0 : -1, class: value ? "interactive" : ""});
      if (value) addTooltip(rect, [row.source, `${label} · ${value} / ${row.items} items`, `Labelled ${row.labelled} · median |log error| ${formatNumber(row.medianAbsoluteLogError, 2)}`]);
      svg.append(rect); offset += segmentW;
    });
  });
  [[colors.red, "UNDER"], [colors.green, "INSIDE / OPEN"], [colors.blue, "OVER"], [colors.muted, "UNLABELLED"]].forEach(([color, label], index) => svg.append(svgElement("text", {x: margin.left + index * 105, y: 15, fill: color, "font-family": "monospace", "font-size": 8}, label)));
  host.append(svg);
  const list = $("#source-list"); clear(list);
  rows.forEach(row => list.append(element("div", {class: "source-row"}, [
    element("strong", {text: row.source}), element("span", {text: `${row.labelled}/${row.items} labelled`}),
    element("span", {text: `|log e| ${formatNumber(row.medianAbsoluteLogError, 2)}`}),
    element("strong", {class: row.foregoneLowerBound ? "negative" : "", text: formatCurrency(row.foregoneLowerBound, true)}),
  ])));
}

function renderQuality() {
  const host = $("#quality-chart"); clear(host);
  const rows = state.overview.intelligence.quality;
  if (!rows.length) return;
  const metrics = [
    ["BELIEFS", row => row.beliefCoverage, false],
    ["DECISIONS", row => row.decisionCoverage, false],
    ["RULE TRACE", row => row.ruleTraceCoverage, false],
    ["ITEM REPLAY", row => row.replayCoverage, false],
    ["THRESHOLDS", row => row.thresholdCoverage, false],
    ["FIELD GROUPS", row => row.fieldCoverage, false],
    ["TWO-SIDED", row => row.items ? row.twoSided / row.items : 0, false],
    ["HIDDEN", row => row.items ? row.hiddenCharges / (row.items * 16) : 0, true],
    ["DOCUMENTS", row => row.documentsAvailable ? 1 : 0, false],
    ["RECONCILED", row => row.reconciled ? 1 : 0, false],
  ];
  const width = Math.max(1080, rows.length * 24 + 170), rowH = 43;
  const margin = {left: 112, right: 30, top: 32, bottom: 52}, height = margin.top + metrics.length * rowH + margin.bottom;
  const plotW = width - margin.left - margin.right, cellW = plotW / rows.length;
  const svg = svgRoot(width, height, "Evidence completeness and integrity by game");
  metrics.forEach(([label, accessor, inverse], metricIndex) => {
    const y = margin.top + metricIndex * rowH;
    svg.append(svgElement("text", {x: margin.left - 10, y: y + rowH * .61, class: "axis-label", "text-anchor": "end"}, label));
    rows.forEach((row, index) => {
      const value = clamp(accessor(row), 0, 1), quality = inverse ? 1 - value : value;
      const color = quality >= .96 ? colors.green : quality >= .7 ? colors.amber : colors.red;
      const rect = svgElement("rect", {x: margin.left + index * cellW, y: y + 3, width: Math.max(1, cellW - 1), height: rowH - 6, rx: 2, fill: color, "fill-opacity": .12 + .7 * (inverse ? value : quality), tabindex: 0, class: "interactive"});
      addTooltip(rect, [`Game ${row.game} · ${label.toLocaleLowerCase()}`, `${formatPercent(value)} · ${row.items} items · ${row.transactionRows} transaction rows`, `${row.beliefs} beliefs · ${row.decisions} decisions · ${row.ruleTraces} rule-traced · ${row.replayedItems} replayed`, `${row.twoSided} two-sided · ${row.openCeilings} open ceilings · ${row.hiddenCharges} hidden charges`, `Documents ${row.documentsAvailable ? "available locally" : "unavailable"} · score ${row.reconciled ? "reconciled within €0.01" : "not reconciled"}`]);
      rect.addEventListener("click", () => selectGame(row.game, {scroll: true}));
      svg.append(rect);
      if (cellW >= 20) svg.append(svgElement("text", {x: margin.left + cellW * (index + .5), y: y + rowH * .61, fill: "#f1eee6", "fill-opacity": .8, "font-family": "monospace", "font-size": 6.5, "text-anchor": "middle", "pointer-events": "none"}, `${Math.round(value * 100)}`));
    });
  });
  [0, Math.floor(rows.length / 2), rows.length - 1].forEach(index => svg.append(svgElement("text", {x: margin.left + cellW * (index + .5), y: height - 27, class: "axis-label", "text-anchor": "middle"}, `G${rows[index].game}`)));
  host.append(svg);
  const summary = $("#quality-summary"); clear(summary);
  const specs = [
    ["Reconciled games", `${rows.filter(row => row.reconciled).length} / ${rows.length}`],
    ["Median threshold coverage", formatPercent(median(rows.map(row => row.thresholdCoverage)))],
    ["Median belief coverage", formatPercent(median(rows.map(row => row.beliefCoverage)))],
    ["Median replay coverage", formatPercent(median(rows.map(row => row.replayCoverage)))],
    ["Documents available", `${rows.filter(row => row.documentsAvailable).length} / ${rows.length}`],
    ["Hidden field charges", formatNumber(rows.reduce((sum, row) => sum + row.hiddenCharges, 0))],
  ];
  specs.forEach(([label, value]) => summary.append(element("div", {class: "quality-stat"}, [element("span", {text: label}), element("strong", {text: value})])));
}

function evidenceLens(mode) {
  const fieldTotal = row => Object.values(row.field || {}).reduce((sum, value) => sum + safeNumber(value), 0);
  const specs = {
    "hidden-field": {
      label: "Hidden opponent charges", denominator: "items with at least one opponent charge group",
      eligible: row => fieldTotal(row) > 0,
      issue: row => safeNumber(row.field?.hidden) > 0,
      severity: row => safeNumber(row.field?.hidden) / Math.max(1, fieldTotal(row)),
      state: row => `${formatNumber(row.field?.hidden)} / ${formatNumber(fieldTotal(row))} opponent charge groups hidden`,
    },
    "unresolved-field": {
      label: "Unresolved opponent charges", denominator: "items with at least one opponent charge group",
      eligible: row => fieldTotal(row) > 0,
      issue: row => safeNumber(row.field?.unresolved) > 0,
      severity: row => safeNumber(row.field?.unresolved) / Math.max(1, fieldTotal(row)),
      state: row => `${formatNumber(row.field?.unresolved)} / ${formatNumber(fieldTotal(row))} opponent charge groups unresolved`,
    },
    "open-ceiling": {
      label: "Missing proven ceiling", denominator: "items with a sanctioned proven floor",
      eligible: row => row.tLo !== null,
      issue: row => row.tLo !== null && row.tHi === null,
      severity: row => Number(row.tLo !== null && row.tHi === null),
      state: row => row.tHi === null ? `floor ${formatCurrency(row.tLo)} · ceiling unknown` : `two-sided bracket closes at ${formatCurrency(row.tHi)}`,
    },
    "missing-belief": {
      label: "Missing logged belief", denominator: "all indexed game/items",
      eligible: () => true, issue: row => row.median === null,
      severity: row => Number(row.median === null),
      state: row => row.median === null ? "no item.belief record" : `${formatCurrency(row.median)} · ${row.source || "unknown"}`,
    },
    "missing-decision": {
      label: "Missing Oasis decision", denominator: "all indexed game/items",
      eligible: () => true, issue: row => row.a === null || row.b === null,
      severity: row => Number(row.a === null || row.b === null),
      state: row => row.a === null || row.b === null ? "no item.decided record" : `a ${formatCurrency(row.a)} · b ${formatCurrency(row.b)}`,
    },
    "missing-rule": {
      label: "Missing rule trace", denominator: "items with a logged Oasis decision",
      eligible: row => row.a !== null && row.b !== null,
      issue: row => row.a !== null && row.b !== null && !row.ruleCount,
      severity: row => Number(row.a !== null && row.b !== null && !row.ruleCount),
      state: row => row.ruleCount ? `${formatNumber(row.ruleCount)} rule firings · ${formatNumber(row.shadowCount)} SHADOW` : "decision exists without a rule.fired trace",
    },
    "missing-replay": {
      label: "Missing item replay", denominator: "items with a logged Oasis decision",
      eligible: row => row.a !== null && row.b !== null,
      issue: row => row.a !== null && row.b !== null && !row.replayCount,
      severity: row => Number(row.a !== null && row.b !== null && !row.replayCount),
      state: row => row.replayCount ? `${formatNumber(row.replayCount)} sanitized item events` : "decision exists without replayable item events",
    },
    "missing-docs": {
      label: "Documents unavailable", denominator: "all indexed items; availability inherited from game",
      eligible: () => true, issue: row => !row.documentsAvailable,
      severity: row => Number(!row.documentsAvailable),
      state: row => row.documentsAvailable ? "local key/archive pair available" : "complete local key/archive pair unavailable",
    },
  };
  return specs[mode] || specs["hidden-field"];
}

function evidenceAtlasRows(mode, rows) {
  const lens = evidenceLens(mode);
  return rows.map(row => ({...row, evidenceEligible: Boolean(lens.eligible(row)), evidenceIssue: Boolean(lens.issue(row)), evidenceSeverity: clamp(safeNumber(lens.severity(row)), 0, 1), evidenceState: lens.state(row)}));
}

function renderEvidenceAtlas() {
  const lens = evidenceLens(state.evidenceMode);
  const rows = evidenceAtlasRows(state.evidenceMode, state.overview.itemIndex);
  const eligible = rows.filter(row => row.evidenceEligible);
  const issues = eligible.filter(row => row.evidenceIssue);
  const games = [...new Set(rows.map(row => row.game))].sort((a, b) => a - b);
  const maxItem = Math.max(1, ...rows.map(row => row.item));
  $("#evidence-mode").value = state.evidenceMode;

  const summary = $("#evidence-atlas-summary"); clear(summary);
  const byGame = new Map(games.map(game => [game, {game, eligible: 0, issues: 0}]));
  eligible.forEach(row => {
    const group = byGame.get(row.game);
    group.eligible += 1;
    group.issues += Number(row.evidenceIssue);
  });
  const affectedGames = [...byGame.values()].filter(row => row.issues > 0);
  const worstGame = [...affectedGames].sort((a, b) => b.issues / Math.max(1, b.eligible) - a.issues / Math.max(1, a.eligible) || b.issues - a.issues)[0];
  const specs = [
    ["Selected lens", lens.label, lens.denominator],
    ["Eligible denominator", formatNumber(eligible.length), "one indexed game/item"],
    ["Evidence gaps", `${formatNumber(issues.length)} · ${formatPercent(issues.length / Math.max(1, eligible.length))}`, "issue items / eligible items"],
    ["Affected games", `${affectedGames.length} / ${games.length}`, "games containing at least one selected gap"],
    ["Worst game rate", worstGame ? formatPercent(worstGame.issues / Math.max(1, worstGame.eligible)) : "none", worstGame ? `game ${worstGame.game} · ${worstGame.issues} / ${worstGame.eligible}` : "no selected evidence gaps"],
  ];
  specs.forEach(([label, value, note]) => summary.append(element("div", {class: "evidence-atlas-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));

  const host = $("#evidence-atlas-chart"); clear(host);
  const width = Math.max(1080, games.length * 17 + 130), height = Math.max(480, maxItem * 17 + 90);
  const margin = {left: 78, right: 26, top: 34, bottom: 55};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const cellW = plotW / Math.max(1, games.length), cellH = plotH / maxItem;
  const gameIndex = new Map(games.map((game, index) => [game, index]));
  const svg = svgRoot(width, height, `${lens.label} across ${eligible.length} eligible game/items`);
  rows.forEach(row => {
    const x = margin.left + gameIndex.get(row.game) * cellW;
    const y = margin.top + (row.item - 1) * cellH;
    const fill = !row.evidenceEligible ? colors.muted : row.evidenceIssue ? colors.red : colors.green;
    const opacity = !row.evidenceEligible ? .035 : row.evidenceIssue ? .24 + .68 * row.evidenceSeverity : .1;
    const rect = svgElement("rect", {x: x + .7, y: y + .7, width: Math.max(1, cellW - 1.4), height: Math.max(1, cellH - 1.4), rx: 1.5, fill, "fill-opacity": opacity, tabindex: 0, class: "interactive", role: "button", "aria-label": `Open game ${row.game} item ${row.item}: ${row.evidenceEligible ? row.evidenceState : `outside ${lens.denominator}`}`});
    addTooltip(rect, [`Game ${row.game} item ${row.item} · ${lens.label}`, row.evidenceEligible ? row.evidenceIssue ? "EVIDENCE GAP" : "EVIDENCE PRESENT" : "OUTSIDE ELIGIBLE DENOMINATOR", row.evidenceState, `Field: ${row.field.exact} exact · ${row.field.lowerBound} lower-bound · ${row.field.hidden} hidden · ${row.field.unresolved} unresolved`]);
    rect.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    svg.append(rect);
  });
  games.forEach((game, index) => {
    if (index % Math.max(1, Math.ceil(games.length / 12)) && index !== games.length - 1) return;
    svg.append(svgElement("text", {x: margin.left + (index + .5) * cellW, y: height - 30, class: "axis-label", "text-anchor": "middle"}, `G${game}`));
  });
  for (let item = 1; item <= maxItem; item++) {
    if ((item - 1) % Math.max(1, Math.ceil(maxItem / 12)) && item !== maxItem) continue;
    svg.append(svgElement("text", {x: margin.left - 10, y: margin.top + (item - .5) * cellH + 3, class: "axis-label", "text-anchor": "end"}, `ITEM ${item}`));
  }
  svg.append(svgElement("text", {x: margin.left, y: 17, fill: colors.red, "font-family": "var(--mono)", "font-size": 8}, "BRIGHT RED · SELECTED EVIDENCE GAP"));
  svg.append(svgElement("text", {x: width - margin.right, y: 17, fill: colors.green, "font-family": "var(--mono)", "font-size": 8, "text-anchor": "end"}, "DIM GREEN · EVIDENCE PRESENT"));
  host.append(svg);

  const tail = $("#evidence-atlas-tail"); clear(tail);
  tail.append(element("div", {class: "evidence-atlas-tail-head"}, [element("strong", {text: "Selected evidence gaps"}), element("span", {text: `${formatNumber(issues.length)} issue items · click for the complete receipt`})]));
  [...issues].sort((a, b) => b.evidenceSeverity - a.evidenceSeverity || b.game - a.game || a.item - b.item).slice(0, 14).forEach((row, index) => {
    const button = element("button", {type: "button", class: "evidence-atlas-tail-row"}, [element("span", {text: `#${index + 1}`}), element("span", {}, [element("strong", {text: `game ${row.game} item ${row.item}`}), element("small", {text: row.evidenceState})]), element("span", {text: formatPercent(row.evidenceSeverity, 0)})]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    tail.append(button);
  });
  if (!issues.length) tail.append(element("div", {class: "empty-state"}, [element("p", {text: "No indexed item fails this evidence lens."})]));

  const body = $("#evidence-atlas-data-table"); clear(body);
  issues.slice().sort((a, b) => b.evidenceSeverity - a.evidenceSeverity || a.game - b.game || a.item - b.item).forEach(row => {
    const open = element("button", {type: "button", class: "table-link", text: `game ${row.game} item ${row.item}`});
    open.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    body.append(element("tr", {}, [element("td", {}, [open]), element("td", {text: lens.label}), element("td", {text: row.evidenceState}), element("td", {text: formatPercent(row.evidenceSeverity)}), element("td", {text: formatNumber(row.field.exact)}), element("td", {text: formatNumber(row.field.lowerBound)}), element("td", {text: formatNumber(row.field.hidden)}), element("td", {text: formatNumber(row.field.unresolved)})]));
  });
}

function median(values) {
  const clean = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!clean.length) return null;
  const mid = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[mid] : (clean[mid - 1] + clean[mid]) / 2;
}

function renderStream() {
  const host = $("#stream-chart"); clear(host);
  const rows = state.overview.trends.decisionStream;
  const width = 760, height = 350, margin = {top: 32, right: 22, bottom: 48, left: 48};
  const svg = svgRoot(width, height, "Normalised reviewer-cost share for four decision classes");
  const keys = [
    ["acceptFair", colors.green, "ACCEPT FAIR"], ["rejectFair", colors.red, "REJECT FAIR"],
    ["acceptFraud", colors.amber, "ACCEPT FRAUD"], ["rejectFraud", colors.blue, "REJECT FRAUD"],
  ];
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  for (let i = 0; i <= 4; i++) {
    const y = margin.top + plotH * i / 4;
    svg.append(svgElement("line", {x1: margin.left, y1: y, x2: width - margin.right, y2: y, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: y + 3, class: "axis-label", "text-anchor": "end"}, formatPercent(1 - i / 4, 0)));
  }
  const baseline = new Array(rows.length).fill(0);
  keys.forEach(([key, color, label], keyIndex) => {
    const bottom = baseline.map((v, i) => [margin.left + plotW * i / Math.max(1, rows.length - 1), margin.top + plotH * (1 - v)]);
    rows.forEach((row, i) => { baseline[i] += row[key].share; });
    const top = baseline.map((v, i) => [margin.left + plotW * i / Math.max(1, rows.length - 1), margin.top + plotH * (1 - v)]);
    svg.append(svgElement("path", {d: areaPath(top, bottom), fill: color, "fill-opacity": keyIndex === 3 ? .35 : .55, stroke: color, "stroke-width": .7}));
    svg.append(svgElement("text", {x: margin.left + keyIndex * 130, y: 15, fill: color, "font-family": "var(--mono)", "font-size": 8}, label));
  });
  rows.forEach((row, i) => {
    const x = margin.left + plotW * i / Math.max(1, rows.length - 1);
    const target = svgElement("rect", {x: x - 5, y: margin.top, width: 10, height: plotH, fill: "transparent", tabindex: 0, class: "interactive"});
    addTooltip(target, [`Game ${row.game} · denominator ${formatCurrency(row.denominatorEuros)}`, `reject fair ${formatPercent(row.rejectFair.share)} · ${row.rejectFair.count} decisions`, `accept fraud ${formatPercent(row.acceptFraud.share)} · ${row.acceptFraud.count} decisions`, `hidden rejected fraud ${row.hiddenFraud}`]);
    svg.append(target);
  });
  host.append(svg);
}

function histogram(values, bins, min, max) {
  const counts = new Array(bins).fill(0);
  for (const value of values) {
    const index = clamp(Math.floor((value - min) / (max - min || 1) * bins), 0, bins - 1);
    counts[index]++;
  }
  return counts;
}

function renderRidgeline() {
  const host = $("#ridgeline-chart"); clear(host);
  const rows = state.overview.trends.estimationErrors.filter(row => row.count);
  if (!rows.length) return;
  const all = rows.flatMap(row => row.values).sort((a, b) => a - b);
  const lo = Math.min(-2.5, all[Math.floor(all.length * .02)] || -2.5);
  const hi = Math.max(2.5, all[Math.floor(all.length * .98)] || 2.5);
  const width = Math.max(1060, rows.length * 23), height = 540;
  const margin = {top: 34, right: 25, bottom: 60, left: 70};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const svg = svgRoot(width, height, "Distribution of log charge to proven floor by game");
  const x = value => margin.left + (value - lo) / (hi - lo) * plotW;
  const zero = x(0);
  svg.append(svgElement("line", {x1: zero, y1: margin.top, x2: zero, y2: height - margin.bottom, stroke: colors.cyan, "stroke-width": 1.2, "stroke-dasharray": "4 4"}));
  svg.append(svgElement("text", {x: zero + 5, y: 18, fill: colors.cyan, "font-family": "var(--mono)", "font-size": 9}, "a = t_lo"));
  rows.forEach((row, index) => {
    const baseY = margin.top + plotH * (index + .8) / rows.length;
    const counts = histogram(row.values, 22, lo, hi);
    const peak = Math.max(1, ...counts);
    const points = counts.map((count, bin) => [margin.left + plotW * (bin + .5) / counts.length, baseY - count / peak * Math.min(38, plotH / rows.length * 2.3)]);
    const area = `${linePath(points)} L${points.at(-1)[0]},${baseY} L${points[0][0]},${baseY} Z`;
    const path = svgElement("path", {d: area, fill: row.median < 0 ? colors.red : colors.blue, "fill-opacity": .2, stroke: row.median < 0 ? colors.red : colors.blue, "stroke-width": .8, tabindex: 0, class: "interactive"});
    addTooltip(path, [`Game ${row.game}`, `${row.count} labelled items · median log error ${formatNumber(row.median, 2)}`, `median ratio ${formatNumber(Math.exp(row.median), 2)}× proven floor`]);
    path.addEventListener("click", () => selectGame(row.game, {scroll: true}));
    svg.append(path);
    if (index % Math.max(1, Math.floor(rows.length / 12)) === 0) svg.append(svgElement("text", {x: margin.left - 8, y: baseY + 3, class: "axis-label", "text-anchor": "end"}, `G${row.game}`));
  });
  for (let value = Math.ceil(lo); value <= Math.floor(hi); value++) {
    svg.append(svgElement("text", {x: x(value), y: height - 34, class: "axis-label", "text-anchor": "middle"}, String(value)));
  }
  host.append(svg);
}

function renderBuckets() {
  const host = $("#bucket-chart"); clear(host);
  const buckets = state.overview.trends.valueBuckets;
  const games = state.overview.race.gameIds;
  const width = 760, height = 330, margin = {left: 82, right: 18, top: 30, bottom: 48};
  const plotW = width - margin.left - margin.right, rowH = (height - margin.top - margin.bottom) / buckets.length;
  const svg = svgRoot(width, height, "Under and over rate by proven value bucket and game");
  buckets.forEach((bucket, rowIndex) => {
    const byGame = new Map(bucket.games.map(row => [row.game, row]));
    svg.append(svgElement("text", {x: margin.left - 10, y: margin.top + rowH * (rowIndex + .55), class: "axis-label", "text-anchor": "end"}, bucket.bucket));
    games.forEach((game, index) => {
      const row = byGame.get(game);
      const cellW = plotW / games.length;
      const x = margin.left + index * cellW;
      const median = row?.medianLogError ?? 0;
      const color = median < 0 ? colors.red : colors.blue;
      const opacity = row ? .13 + Math.min(.72, Math.abs(median) / 2.5 * .72) : .025;
      const rect = svgElement("rect", {x, y: margin.top + rowIndex * rowH + 2, width: Math.max(1, cellW - 1), height: rowH - 4, fill: color, "fill-opacity": opacity, tabindex: row ? 0 : -1, class: row ? "interactive" : ""});
      if (row) {
        addTooltip(rect, [`Game ${game} · ${bucket.bucket}`, `${row.count} bracketed items`, `under ${formatPercent(row.underRate)} · over ${formatPercent(row.overRate)}`, `median log(a/t_lo) ${formatNumber(row.medianLogError, 2)}`]);
        rect.addEventListener("click", () => selectGame(game, {scroll: true}));
      }
      svg.append(rect);
    });
  });
  [0, Math.floor(games.length / 2), games.length - 1].forEach(index => svg.append(svgElement("text", {x: margin.left + plotW * index / Math.max(1, games.length - 1), y: height - 25, class: "axis-label", "text-anchor": "middle"}, `G${games[index]}`)));
  svg.append(svgElement("text", {x: margin.left, y: 15, fill: colors.red, "font-family": "var(--mono)", "font-size": 9}, "LOW / UNDERCHARGE"));
  svg.append(svgElement("text", {x: margin.left + 145, y: 15, fill: colors.blue, "font-family": "var(--mono)", "font-size": 9}, "HIGH / OVERCHARGE"));
  host.append(svg);
}

function renderOvercharge() {
  const host = $("#overcharge-chart"); clear(host);
  const rows = state.overview.trends.overchargeCurve;
  const width = 760, height = 330, margin = {left: 65, right: 20, top: 32, bottom: 58};
  const svg = svgRoot(width, height, "Acceptance rate by overcharge ratio bucket");
  const max = Math.max(.25, ...rows.flatMap(row => [row.acceptRate || 0, row.referenceRate || 0]));
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  for (let i = 0; i <= 4; i++) {
    const y = margin.top + plotH * i / 4;
    svg.append(svgElement("line", {x1: margin.left, y1: y, x2: width - margin.right, y2: y, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: y + 3, class: "axis-label", "text-anchor": "end"}, formatPercent(max * (1 - i / 4), 0)));
  }
  const step = plotW / rows.length;
  rows.forEach((row, index) => {
    const x = margin.left + step * (index + .18), barW = step * .48;
    const value = row.acceptRate || 0;
    const y = margin.top + plotH * (1 - value / max);
    const rect = svgElement("rect", {x, y, width: barW, height: margin.top + plotH - y, rx: 4, fill: colors.amber, "fill-opacity": row.acceptRate === null ? .1 : .7, tabindex: 0, class: "interactive"});
    addTooltip(rect, [row.label, row.acceptRate === null ? "No current observations" : `Current ${formatPercent(row.acceptRate)} · ${row.decisions} reviewer decisions`, `${row.items} line items`]);
    svg.append(rect);
    if (row.referenceRate !== null) {
      const refY = margin.top + plotH * (1 - row.referenceRate / max);
      svg.append(svgElement("line", {x1: x - 4, y1: refY, x2: x + barW + 4, y2: refY, stroke: colors.cyan, "stroke-width": 2}));
    }
    svg.append(svgElement("text", {x: x + barW / 2, y: height - 31, class: "axis-label", "text-anchor": "middle"}, row.label));
  });
  svg.append(svgElement("text", {x: margin.left, y: 16, fill: colors.amber, "font-family": "var(--mono)", "font-size": 9}, "CURRENT BARS"));
  svg.append(svgElement("text", {x: margin.left + 110, y: 16, fill: colors.cyan, "font-family": "var(--mono)", "font-size": 9}, "MEASURED REFERENCE TICKS"));
  host.append(svg);
}

function renderPareto() {
  const host = $("#pareto-chart"); clear(host);
  const data = state.overview.trends.concentration;
  const items = data.items;
  const width = 760, height = 330, margin = {left: 65, right: 25, top: 25, bottom: 48};
  const svg = svgRoot(width, height, "Cumulative share of proven foregone income by ranked line item");
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  for (let i = 0; i <= 4; i++) {
    const y = margin.top + plotH * i / 4;
    svg.append(svgElement("line", {x1: margin.left, y1: y, x2: width - margin.right, y2: y, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: y + 3, class: "axis-label", "text-anchor": "end"}, formatPercent(1 - i / 4, 0)));
  }
  const points = items.map((row, i) => [margin.left + plotW * i / Math.max(1, items.length - 1), margin.top + plotH * (1 - row.cumulativeShare)]);
  svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: colors.red, "stroke-width": 2.4}));
  [0, 9, 49].filter(index => items[index]).forEach(index => {
    const row = items[index], point = points[index];
    const dot = svgElement("circle", {cx: point[0], cy: point[1], r: 4, fill: colors.red, tabindex: 0, class: "interactive"});
    addTooltip(dot, [`Top ${index + 1} items`, `${formatPercent(row.cumulativeShare)} of ${formatCurrency(data.totalLowerBound)}`, `through game ${row.game} item ${row.item}`]);
    svg.append(dot);
  });
  svg.append(svgElement("text", {x: margin.left, y: height - 25, class: "axis-label"}, "highest-cost item"));
  svg.append(svgElement("text", {x: width - margin.right, y: height - 25, class: "axis-label", "text-anchor": "end"}, `${items.length} shown / ${data.itemCount} total`));
  host.append(svg);
  const list = $("#pareto-list"); clear(list);
  items.slice(0, 12).forEach(row => {
    const button = element("button", {type: "button", class: "pareto-row"}, [
      element("span", {text: `#${row.rank}`}), element("span", {text: `game ${row.game} item ${row.item}`}),
      element("strong", {text: formatCurrency(row.foregoneLowerBound)}), element("span", {text: formatPercent(row.cumulativeShare)}),
    ]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    list.append(button);
  });
}

function renderOpponents() {
  const host = $("#opponent-chart"); clear(host);
  const rows = state.overview.trends.opponents;
  const ratios = rows.map(row => row.medianObservedChargeToFloor).filter(Number.isFinite);
  const balances = rows.map(row => row.netExchange);
  const xMax = Math.max(2, ...ratios) * 1.08;
  const yMin = Math.min(0, ...balances), yMax = Math.max(0, ...balances);
  const width = 760, height = 330, margin = {left: 72, right: 25, top: 30, bottom: 55};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const x = value => margin.left + safeNumber(value) / xMax * plotW;
  const y = value => margin.top + (yMax - value) / (yMax - yMin || 1) * plotH;
  const svg = svgRoot(width, height, "Opponent observed charge aggression against net exchange with Oasis");
  svg.append(svgElement("line", {x1: margin.left, y1: y(0), x2: width - margin.right, y2: y(0), class: "grid-line"}));
  svg.append(svgElement("line", {x1: x(1), y1: margin.top, x2: x(1), y2: height - margin.bottom, stroke: colors.cyan, "stroke-dasharray": "4 5", "stroke-opacity": .55}));
  rows.forEach(row => {
    if (!Number.isFinite(row.medianObservedChargeToFloor)) return;
    const dot = svgElement("circle", {cx: x(row.medianObservedChargeToFloor), cy: y(row.netExchange), r: 4 + 8 * Math.sqrt(row.aggressionCoverage), fill: row.netExchange >= 0 ? colors.green : colors.red, "fill-opacity": .65, stroke: row.netExchange >= 0 ? colors.green : colors.red, tabindex: 0, class: "interactive"});
    addTooltip(dot, [row.team, `Observed charge / floor ${formatNumber(row.medianObservedChargeToFloor, 2)}× · coverage ${formatPercent(row.aggressionCoverage)}`, `Net exchange ${signed(row.netExchange)} · accepts us ${formatPercent(row.acceptRateAgainstUs)}`]);
    svg.append(dot);
  });
  svg.append(svgElement("text", {x: margin.left, y: 16, class: "axis-label"}, "NET EXCHANGE ↑ PAYS US / ↓ COSTS US"));
  svg.append(svgElement("text", {x: width - margin.right, y: height - 26, class: "axis-label", "text-anchor": "end"}, "observed charge / t_lo →"));
  host.append(svg);
  const list = $("#opponent-list"); clear(list);
  [...rows].sort((a, b) => a.netExchange - b.netExchange).forEach(row => list.append(element("div", {class: "opponent-row"}, [
    element("strong", {text: row.team}), element("span", {text: `${formatPercent(row.acceptRateAgainstUs)} accepts`}),
    element("span", {text: `${formatPercent(row.aggressionCoverage)} visible`}),
    element("strong", {class: row.netExchange >= 0 ? "positive" : "negative", text: signed(row.netExchange)}),
  ])));
}

const MARKET_TIMELINE_COLUMNS = [
  "game", "issuerIndex", "reviewerIndex", "decisions", "accepted",
  "issuerIncome", "reviewerCost", "penaltyWedge", "wrongCost",
  "unresolvedCount", "unresolvedCost", "hiddenFraud",
  "acceptFairCount", "acceptFairCost", "rejectFairCount", "rejectFairCost",
  "acceptFraudCount", "acceptFraudCost", "rejectFraudCount", "rejectFraudCost",
];
const MARKET_EDGE_SUM_FIELDS = MARKET_TIMELINE_COLUMNS.slice(3);
const MARKET_OUTCOMES = ["acceptFair", "rejectFair", "acceptFraud", "rejectFraud"];
const MARKET_EDGE_COUNT_FIELDS = [
  "decisions", "accepted", "unresolvedCount", "hiddenFraud",
  ...MARKET_OUTCOMES.map(outcome => `${outcome}Count`),
];

function decodeMarketFrames(payload) {
  if (!Array.isArray(payload.teams) || payload.teams.length < 2 ||
      payload.teams.some(team => typeof team !== "string" || !team.trim() || team.length > 100) ||
      new Set(payload.teams).size !== payload.teams.length) throw new Error("market team identities are malformed");
  if (!Array.isArray(payload.gameIds) || !payload.gameIds.length ||
      payload.gameIds.some(game => !Number.isInteger(game) || game < 0 || game > 100) ||
      new Set(payload.gameIds).size !== payload.gameIds.length) throw new Error("market game identities are malformed");
  const teamSet = new Set(payload.teams);
  const edgeKeys = new Set();
  if (!Array.isArray(payload.edges) || payload.edges.length !== payload.teams.length * (payload.teams.length - 1)) {
    throw new Error("all-history market edge ledger is incomplete");
  }
  payload.edges.forEach((edge, index) => {
    const key = `${edge?.issuer}\u0000${edge?.reviewer}`;
    const classified = edge ? MARKET_OUTCOMES.reduce((sum, outcome) => sum + edge[`${outcome}Count`], 0) : -1;
    if (!edge || !teamSet.has(edge.issuer) || !teamSet.has(edge.reviewer) || edge.issuer === edge.reviewer || edgeKeys.has(key) ||
        MARKET_EDGE_SUM_FIELDS.some(field => typeof edge[field] !== "number" || !Number.isFinite(edge[field])) ||
        MARKET_EDGE_COUNT_FIELDS.some(field => !Number.isInteger(edge[field]) || edge[field] < 0) ||
        classified + edge.unresolvedCount !== edge.decisions || edge.accepted > edge.decisions ||
        (edge.acceptRate !== null && (typeof edge.acceptRate !== "number" || edge.acceptRate < 0 || edge.acceptRate > 1)) ||
        typeof edge.netExchange !== "number" || !Number.isFinite(edge.netExchange)) {
      throw new Error(`all-history market edge ${index} is malformed`);
    }
    edgeKeys.add(key);
  });
  if (!Array.isArray(payload.summaries) || payload.summaries.length !== payload.teams.length ||
      new Set(payload.summaries.map(row => row?.team)).size !== payload.teams.length ||
      payload.summaries.some(row => !teamSet.has(row?.team)) ||
      !Array.isArray(payload.timeline) || payload.timeline.length !== payload.teams.length * payload.gameIds.length ||
      new Set(payload.timeline.map(row => `${row?.team}\u0000${row?.game}`)).size !== payload.timeline.length ||
      payload.timeline.some(row => !teamSet.has(row?.team) || !payload.gameIds.includes(row?.game))) {
    throw new Error("market team summaries or timeline are incomplete");
  }
  const finiteOrNull = value => value === null || (typeof value === "number" && Number.isFinite(value));
  const summaryNumbers = ["issuedIncome", "reviewerCost", "net", "issuedDecisions", "reviewedDecisions", "acceptedByMarket", "reviewerAccepts", "wrongReviewCost", "rejectFairCount", "rejectFairCost", "acceptFraudCount", "acceptFraudCost", "hiddenFraud", "chargeGroups", "aggressionObservations", "aggressionCoverage"];
  if (payload.summaries.some(row => summaryNumbers.some(field => typeof row[field] !== "number" || !Number.isFinite(row[field])) ||
      !finiteOrNull(row.marketAcceptRate) || !finiteOrNull(row.reviewerAcceptRate) ||
      !finiteOrNull(row.medianChargeToFloor) || !finiteOrNull(row.officialTotal) ||
      !finiteOrNull(row.scoreReconciliationDelta))) throw new Error("market team summaries contain invalid measures");
  const timelineNumbers = ["issuedIncome", "reviewerCost", "net", "cumulativeNet", "issuedDecisions", "acceptedByMarket", "reviewedDecisions", "reviewerAccepts"];
  if (payload.timeline.some(row => timelineNumbers.some(field => typeof row[field] !== "number" || !Number.isFinite(row[field])) ||
      !finiteOrNull(row.marketAcceptRate) || !finiteOrNull(row.reviewerAcceptRate) ||
      !finiteOrNull(row.officialScore) || !finiteOrNull(row.officialCumulativeScore) ||
      !finiteOrNull(row.scoreReconciliationDelta))) throw new Error("market timeline contains invalid measures");
  const cube = payload.edgeTimeline;
  if (!cube || cube.encoding !== "dense-array-v1" ||
      JSON.stringify(cube.columns) !== JSON.stringify(MARKET_TIMELINE_COLUMNS) ||
      !Array.isArray(cube.rows)) throw new Error("market replay cube contract mismatch");
  const expected = payload.gameIds.length * payload.teams.length * Math.max(0, payload.teams.length - 1);
  if (cube.rows.length !== expected) throw new Error(`market replay cube is incomplete (${cube.rows.length} / ${expected} frames)`);
  const gameSet = new Set(payload.gameIds);
  const seen = new Set();
  const byGame = new Map(payload.gameIds.map(game => [game, []]));
  let frameDecisions = 0;
  cube.rows.forEach((raw, rowIndex) => {
    if (!Array.isArray(raw) || raw.length !== MARKET_TIMELINE_COLUMNS.length ||
        raw.some(value => typeof value !== "number" || !Number.isFinite(value))) {
      throw new Error(`market replay frame ${rowIndex} is malformed`);
    }
    const frame = Object.fromEntries(MARKET_TIMELINE_COLUMNS.map((column, index) => [column, raw[index]]));
    if (!Number.isInteger(frame.game) || !gameSet.has(frame.game) ||
        !Number.isInteger(frame.issuerIndex) || !Number.isInteger(frame.reviewerIndex) ||
        frame.issuerIndex < 0 || frame.issuerIndex >= payload.teams.length ||
        frame.reviewerIndex < 0 || frame.reviewerIndex >= payload.teams.length ||
        frame.issuerIndex === frame.reviewerIndex) throw new Error(`market replay frame ${rowIndex} has an invalid identity`);
    const key = `${frame.game}:${frame.issuerIndex}:${frame.reviewerIndex}`;
    if (seen.has(key)) throw new Error(`duplicate market replay frame ${key}`);
    seen.add(key);
    const classified = MARKET_OUTCOMES.reduce((sum, outcome) => sum + frame[`${outcome}Count`], 0);
    if (!Number.isInteger(frame.decisions) || !Number.isInteger(frame.accepted) ||
        frame.decisions < 0 || frame.accepted < 0 || frame.accepted > frame.decisions ||
        MARKET_EDGE_COUNT_FIELDS.some(field => !Number.isInteger(frame[field]) || frame[field] < 0) ||
        classified + frame.unresolvedCount !== frame.decisions) {
      throw new Error(`market replay frame ${key} fails its decision partition`);
    }
    frame.issuer = payload.teams[frame.issuerIndex];
    frame.reviewer = payload.teams[frame.reviewerIndex];
    frameDecisions += frame.decisions;
    byGame.get(frame.game).push(frame);
  });
  const aggregateDecisions = payload.edges.reduce((sum, edge) => sum + safeNumber(edge.decisions), 0);
  if (frameDecisions !== aggregateDecisions) throw new Error("market replay decisions do not reconcile to all-history edges");
  return byGame;
}

const RIVAL_WINDOWS = new Set(["all", "last-10", "last-20", "first-half", "second-half"]);

function rivalGameIds(gameIds, window = "all") {
  const games = [...new Set((gameIds || []).map(Number).filter(Number.isInteger))].sort((a, b) => a - b);
  if (window === "last-10") return games.slice(-10);
  if (window === "last-20") return games.slice(-20);
  const split = Math.ceil(games.length / 2);
  if (window === "first-half") return games.slice(0, split);
  if (window === "second-half") return games.slice(split);
  return games;
}

function rivalRiskForGame(framesByGame, game, team) {
  const incoming = (framesByGame?.get(game) || []).filter(row => row.reviewer === team);
  return {
    wrongCost: incoming.reduce((sum, row) => sum + safeNumber(row.wrongCost), 0),
    hiddenFraud: incoming.reduce((sum, row) => sum + safeNumber(row.hiddenFraud), 0),
    rejectFairCost: incoming.reduce((sum, row) => sum + safeNumber(row.rejectFairCost), 0),
    acceptFraudCost: incoming.reduce((sum, row) => sum + safeNumber(row.acceptFraudCost), 0),
  };
}

function rivalSideSummary(rows, side) {
  const sum = field => rows.reduce((total, row) => total + safeNumber(row[side][field]), 0);
  const issuedIncome = sum("income"), reviewerCost = sum("cost"), net = sum("net");
  const issuedDecisions = sum("issuedDecisions"), reviewedDecisions = sum("reviewedDecisions");
  const acceptedByMarket = sum("acceptedByMarket"), reviewerAccepts = sum("reviewerAccepts");
  const wrongCost = sum("wrongCost"), hiddenFraud = sum("hiddenFraud");
  const roundValues = rows.map(row => row[side].net);
  const meanRound = roundValues.length ? net / roundValues.length : null;
  const variance = roundValues.length && meanRound !== null
    ? roundValues.reduce((total, value) => total + (value - meanRound) ** 2, 0) / roundValues.length : null;
  return {
    issuedIncome, reviewerCost, net, issuedDecisions, reviewedDecisions,
    acceptedByMarket, reviewerAccepts, wrongCost, hiddenFraud,
    incomePerIssuedDecision: issuedDecisions ? issuedIncome / issuedDecisions : null,
    costPerReviewedDecision: reviewedDecisions ? reviewerCost / reviewedDecisions : null,
    wrongCostPerReviewedDecision: reviewedDecisions ? wrongCost / reviewedDecisions : null,
    marketAcceptRate: issuedDecisions ? acceptedByMarket / issuedDecisions : null,
    reviewerAcceptRate: reviewedDecisions ? reviewerAccepts / reviewedDecisions : null,
    positiveRoundRate: rows.length ? rows.filter(row => row[side].net > 0).length / rows.length : null,
    meanRound, medianRound: medianNumber(roundValues),
    roundVolatility: variance === null ? null : Math.sqrt(variance),
  };
}

function pairedRivalBootstrap(rows, runs = 5000, seed = 20260825) {
  const count = rows.length, draws = clamp(Math.trunc(safeNumber(runs, 5000)), 1000, 10000);
  const normalizedSeed = clamp(Math.trunc(safeNumber(seed, 20260825)), 1, 2147483646);
  if (!count) return {runs: draws, seed: normalizedSeed, games: 0, observedMean: null, p2_5: null, p50: null, p97_5: null, probabilityOasisMeanAhead: null, monteCarloMargin95: 1.96 * .5 / Math.sqrt(draws)};
  const random = seededGenerator(normalizedSeed), means = [];
  for (let run = 0; run < draws; run += 1) {
    let total = 0;
    for (let index = 0; index < count; index += 1) total += rows[Math.floor(random() * count)].gap;
    means.push(total / count);
  }
  return {
    runs: draws, seed: normalizedSeed, games: count,
    observedMean: rows.reduce((sum, row) => sum + row.gap, 0) / count,
    p2_5: numericQuantile(means, .025), p50: numericQuantile(means, .5), p97_5: numericQuantile(means, .975),
    probabilityOasisMeanAhead: means.filter(value => value > 0).length / draws,
    monteCarloMargin95: 1.96 * .5 / Math.sqrt(draws),
  };
}

function buildRivalBenchmark(market, framesByGame, rivalTeam, window = "all") {
  if (!market || !Array.isArray(market.teams) || !market.teams.includes("Oasis")) throw new Error("rival benchmark market evidence unavailable");
  if (!market.teams.includes(rivalTeam) || rivalTeam === "Oasis") throw new Error("rival benchmark team is invalid");
  const normalizedWindow = RIVAL_WINDOWS.has(window) ? window : "all";
  const games = rivalGameIds(market.gameIds, normalizedWindow), selected = new Set(games);
  const timelines = new Map(market.timeline.filter(row => selected.has(row.game)).map(row => [`${row.team}\0${row.game}`, row]));
  let cumulativeGap = 0;
  const rows = games.map(game => {
    const oasisRow = timelines.get(`Oasis\0${game}`), rivalRow = timelines.get(`${rivalTeam}\0${game}`);
    if (!oasisRow || !rivalRow) throw new Error(`paired rival timeline missing game ${game}`);
    const oasisRisk = rivalRiskForGame(framesByGame, game, "Oasis");
    const rivalRisk = rivalRiskForGame(framesByGame, game, rivalTeam);
    const oasis = {
      income: safeNumber(oasisRow.issuedIncome), cost: safeNumber(oasisRow.reviewerCost), net: safeNumber(oasisRow.net),
      issuedDecisions: safeNumber(oasisRow.issuedDecisions), reviewedDecisions: safeNumber(oasisRow.reviewedDecisions),
      acceptedByMarket: safeNumber(oasisRow.acceptedByMarket), reviewerAccepts: safeNumber(oasisRow.reviewerAccepts),
      officialScore: oasisRow.officialScore, wrongCost: oasisRisk.wrongCost, hiddenFraud: oasisRisk.hiddenFraud,
    };
    const rival = {
      income: safeNumber(rivalRow.issuedIncome), cost: safeNumber(rivalRow.reviewerCost), net: safeNumber(rivalRow.net),
      issuedDecisions: safeNumber(rivalRow.issuedDecisions), reviewedDecisions: safeNumber(rivalRow.reviewedDecisions),
      acceptedByMarket: safeNumber(rivalRow.acceptedByMarket), reviewerAccepts: safeNumber(rivalRow.reviewerAccepts),
      officialScore: rivalRow.officialScore, wrongCost: rivalRisk.wrongCost, hiddenFraud: rivalRisk.hiddenFraud,
    };
    const incomeEdge = oasis.income - rival.income;
    const costEdge = rival.cost - oasis.cost;
    const gap = oasis.net - rival.net;
    const officialGap = Number.isFinite(Number(oasis.officialScore)) && Number.isFinite(Number(rival.officialScore))
      ? Number(oasis.officialScore) - Number(rival.officialScore) : null;
    cumulativeGap += gap;
    return {
      game, oasis, rival, incomeEdge, costEdge, gap, cumulativeGap,
      officialGap, reconciliationDelta: officialGap === null ? null : gap - officialGap,
      grossObservedFlow: oasis.income + oasis.cost + rival.income + rival.cost,
    };
  });
  const oasis = rivalSideSummary(rows, "oasis"), rival = rivalSideSummary(rows, "rival");
  const incomeEdge = oasis.issuedIncome - rival.issuedIncome;
  const costEdge = rival.reviewerCost - oasis.reviewerCost;
  const scoreGap = oasis.net - rival.net;
  const officialRows = rows.filter(row => row.officialGap !== null);
  const officialGap = officialRows.length === rows.length ? officialRows.reduce((sum, row) => sum + row.officialGap, 0) : null;
  const absoluteTotal = rows.reduce((sum, row) => sum + Math.abs(row.gap), 0);
  const byImpact = [...rows].sort((left, right) => Math.abs(right.gap) - Math.abs(left.gap) || left.game - right.game);
  const ranks = [...market.summaries].sort((a, b) => b.net - a.net || a.team.localeCompare(b.team));
  const best = [...rows].sort((a, b) => b.gap - a.gap || a.game - b.game)[0] || null;
  const worst = [...rows].sort((a, b) => a.gap - b.gap || a.game - b.game)[0] || null;
  return {
    rivalTeam, window: normalizedWindow, games, rows, oasis, rival,
    summary: {
      games: rows.length, incomeEdge, costEdge, scoreGap, officialGap,
      reconciliationDelta: officialGap === null ? null : scoreGap - officialGap,
      maxRoundReconciliationDelta: officialRows.length ? Math.max(...officialRows.map(row => Math.abs(row.reconciliationDelta))) : null,
      oasisRoundWins: rows.filter(row => row.gap > 0).length,
      rivalRoundWins: rows.filter(row => row.gap < 0).length,
      tiedRounds: rows.filter(row => row.gap === 0).length,
      meanGap: rows.length ? scoreGap / rows.length : null,
      medianGap: medianNumber(rows.map(row => row.gap)),
      absoluteGapFlow: absoluteTotal,
      topOneAbsoluteShare: absoluteTotal ? Math.abs(byImpact[0]?.gap || 0) / absoluteTotal : null,
      topFiveAbsoluteShare: absoluteTotal ? byImpact.slice(0, 5).reduce((sum, row) => sum + Math.abs(row.gap), 0) / absoluteTotal : null,
      gapWithoutBestRound: best ? scoreGap - best.gap : scoreGap,
      gapWithoutWorstRound: worst ? scoreGap - worst.gap : scoreGap,
      best, worst,
      oasisRank: ranks.findIndex(row => row.team === "Oasis") + 1,
      rivalRank: ranks.findIndex(row => row.team === rivalTeam) + 1,
    },
    decisive: byImpact,
    bootstrap: pairedRivalBootstrap(rows),
  };
}

function buildRivalReceipt(result, materializedAt) {
  return {
    version: 1, status: "offline-paired-rival-accounting-evidence-only", materializedAt,
    comparison: {team: "Oasis", rival: result.rivalTeam, window: result.window, gameIds: [...result.games]},
    denominator: {
      pairedGames: result.summary.games,
      oasisIssuedDecisions: result.oasis.issuedDecisions, rivalIssuedDecisions: result.rival.issuedDecisions,
      oasisReviewedDecisions: result.oasis.reviewedDecisions, rivalReviewedDecisions: result.rival.reviewedDecisions,
      officialScoreObservedGames: result.rows.filter(row => row.officialGap !== null).length,
    },
    decomposition: {
      oasisMinusRivalIncome: result.summary.incomeEdge,
      rivalMinusOasisReviewerCost: result.summary.costEdge,
      oasisMinusRivalScore: result.summary.scoreGap,
      officialScoreGap: result.summary.officialGap,
      reconciliationDelta: result.summary.reconciliationDelta,
      maxPerGameOfficialReconciliationDelta: result.summary.maxRoundReconciliationDelta,
    },
    pairedBootstrap: {...result.bootstrap},
    concentration: {
      absoluteGapFlow: result.summary.absoluteGapFlow,
      topOneAbsoluteShare: result.summary.topOneAbsoluteShare,
      topFiveAbsoluteShare: result.summary.topFiveAbsoluteShare,
      gapWithoutBestRound: result.summary.gapWithoutBestRound,
      gapWithoutWorstRound: result.summary.gapWithoutWorstRound,
    },
    efficiencies: {oasis: {...result.oasis}, rival: {...result.rival}},
    decisiveGames: result.decisive.slice(0, 20).map(row => ({
      game: row.game, incomeEdge: row.incomeEdge, costEdge: row.costEdge,
      scoreGap: row.gap, cumulativeGap: row.cumulativeGap,
    })),
    boundaries: [
      "every row compares both teams on the same played game; no unmatched rounds enter",
      "score gap equals issuer-income edge plus reviewer-cost edge exactly; residuals against displayed official round scores are reported separately",
      "paired bootstrap resamples whole matched games and measures historical sampling instability, not future or causal performance",
      "different claims and opponent strategies across games remain uncontrolled; attribution is payoff accounting, not model causality",
      "reviewer costs and wrong-decision costs exclude attempted sizes of rejected fraudulent charges",
      "no process, charge, limit, rule, model, or submission is modified",
    ],
  };
}

function emptyMarketEdge(issuer, reviewer) {
  const row = {issuer, reviewer};
  MARKET_EDGE_SUM_FIELDS.forEach(field => { row[field] = 0; });
  return row;
}

function addMarketFrame(target, frame) {
  MARKET_EDGE_SUM_FIELDS.forEach(field => { target[field] += safeNumber(frame[field]); });
}

function finalizeMarketEdge(row) {
  row.acceptRate = row.decisions ? row.accepted / row.decisions : null;
  row.netExchange = row.issuerIncome - row.reviewerCost;
  return row;
}

function marketReplaySelection() {
  const games = state.market?.gameIds || [];
  const index = clamp(state.marketReplayIndex, 0, Math.max(0, games.length - 1));
  return {index, game: games[index] ?? null, games};
}

function marketSummaryFromEdges(team, edges, selection) {
  const issued = edges.filter(row => row.issuer === team);
  const reviewed = edges.filter(row => row.reviewer === team);
  const sum = (rows, field) => rows.reduce((total, row) => total + safeNumber(row[field]), 0);
  const base = state.market.summaries.find(row => row.team === team) || {};
  const includedGames = new Set(selection.games.slice(0, selection.index + 1));
  const points = state.market.timeline.filter(row => row.team === team && includedGames.has(row.game));
  const selectedPoint = state.market.timeline.find(row => row.team === team && row.game === selection.game);
  const officialTotal = state.marketReplayMode === "round"
    ? selectedPoint?.officialScore ?? null
    : selectedPoint?.officialCumulativeScore ?? null;
  const issuedIncome = sum(issued, "issuerIncome");
  const reviewerCost = sum(reviewed, "reviewerCost");
  const issuedDecisions = sum(issued, "decisions");
  const reviewedDecisions = sum(reviewed, "decisions");
  const acceptedByMarket = sum(issued, "accepted");
  const reviewerAccepts = sum(reviewed, "accepted");
  const net = issuedIncome - reviewerCost;
  return {
    team, issuedIncome, reviewerCost, net, issuedDecisions, reviewedDecisions,
    acceptedByMarket, reviewerAccepts,
    marketAcceptRate: issuedDecisions ? acceptedByMarket / issuedDecisions : null,
    reviewerAcceptRate: reviewedDecisions ? reviewerAccepts / reviewedDecisions : null,
    wrongReviewCost: sum(reviewed, "wrongCost"),
    rejectFairCount: sum(reviewed, "rejectFairCount"),
    rejectFairCost: sum(reviewed, "rejectFairCost"),
    acceptFraudCount: sum(reviewed, "acceptFraudCount"),
    acceptFraudCost: sum(reviewed, "acceptFraudCost"),
    hiddenFraud: sum(reviewed, "hiddenFraud"),
    chargeGroups: base.chargeGroups ?? 0,
    aggressionObservations: base.aggressionObservations ?? 0,
    medianChargeToFloor: base.medianChargeToFloor ?? null,
    aggressionCoverage: base.aggressionCoverage ?? 0,
    officialTotal,
    scoreReconciliationDelta: officialTotal === null ? null : net - officialTotal,
  };
}

function currentMarketView() {
  if (!state.market) return {edges: [], edgeMap: new Map(), summaries: [], decisions: 0, game: null, index: 0, frameCount: 0};
  const selection = marketReplaySelection();
  const key = `${state.marketReplayMode}:${selection.index}`;
  const cached = state.marketViewCache.get(key);
  if (cached) return cached;
  const accumulatedEdges = new Map();
  state.market.teams.forEach(issuer => state.market.teams.forEach(reviewer => {
    if (issuer !== reviewer) accumulatedEdges.set(`${issuer}\u0000${reviewer}`, emptyMarketEdge(issuer, reviewer));
  }));
  const frameGames = state.marketReplayMode === "round"
    ? [selection.game] : selection.games.slice(0, selection.index + 1);
  frameGames.forEach(game => (state.marketFramesByGame.get(game) || []).forEach(frame => {
    addMarketFrame(accumulatedEdges.get(`${frame.issuer}\u0000${frame.reviewer}`), frame);
  }));
  const edges = [...accumulatedEdges.values()].map(finalizeMarketEdge);
  const edgeMap = new Map(edges.map(row => [`${row.issuer}\u0000${row.reviewer}`, row]));
  const summaries = state.market.teams.map(team => marketSummaryFromEdges(team, edges, selection));
  const view = {
    ...selection, edges, edgeMap, summaries,
    decisions: edges.reduce((sum, edge) => sum + edge.decisions, 0),
    frameCount: state.marketReplayMode === "round" ? 1 : selection.index + 1,
  };
  state.marketViewCache.set(key, view);
  if (state.marketViewCache.size > 12) state.marketViewCache.delete(state.marketViewCache.keys().next().value);
  return view;
}

function marketEdge(issuer, reviewer) {
  return currentMarketView().edgeMap.get(`${issuer}\u0000${reviewer}`) || null;
}

function marketMetricSpec() {
  const specs = {
    settlement: {field: "reviewerCost", label: "Reviewer settlement", unit: "EUR", color: "239,106,103", note: "payoff-matrix reviewer cost"},
    acceptance: {field: "acceptRate", label: "Acceptance rate", unit: "rate", color: "101,214,208", note: "accepted decisions / edge decisions"},
    wrong: {field: "wrongCost", label: "Wrong-decision cost", unit: "EUR", color: "242,184,75", note: "reject-fair + accept-fraud observed cost"},
    wedge: {field: "penaltyWedge", label: "Penalty wedge", unit: "EUR", color: "184,156,255", note: "reviewer cost − issuer income"},
  };
  return specs[state.marketMode] || specs.settlement;
}

function marketShortName(team) {
  const words = String(team || "").split(/[^A-Za-z0-9]+/).filter(Boolean);
  if (words.length > 1) return words.map(word => word[0]).join("").slice(0, 4).toUpperCase();
  return String(team || "—").slice(0, 4).toUpperCase();
}

function populateMarketControls() {
  if (!state.market) return;
  const select = $("#market-team"); clear(select);
  state.market.teams.forEach(team => select.append(element("option", {value: team, text: team})));
  if (!state.market.teams.includes(state.marketTeam)) state.marketTeam = "Oasis";
  if (!state.market.teams.includes(state.marketPeer) || state.marketPeer === state.marketTeam) {
    state.marketPeer = [...marketCounterparties(state.marketTeam)].sort((a, b) => a.net - b.net)[0]?.team || null;
  }
  select.value = state.marketTeam;
  $$('[data-market-mode]').forEach(button => {
    const active = button.dataset.marketMode === state.marketMode;
    button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
  });
  $$('[data-market-replay-mode]').forEach(button => {
    const active = button.dataset.marketReplayMode === state.marketReplayMode;
    button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
  });
}

function selectedMarketSummary() {
  return currentMarketView().summaries.find(row => row.team === state.marketTeam) || null;
}

function renderMarketReplayControls() {
  const view = currentMarketView();
  const slider = $("#market-replay-slider");
  slider.max = String(Math.max(0, view.games.length - 1));
  slider.value = String(view.index);
  $("#market-replay-start").textContent = view.games.length ? `G${view.games[0]}` : "G—";
  $("#market-replay-end").textContent = view.games.length ? `G${view.games.at(-1)}` : "G—";
  $("#market-replay-progress").textContent = `${view.index + 1} / ${view.games.length}`;
  const frameLabel = state.marketReplayMode === "round" ? "SINGLE-ROUND FRAME" : "CUMULATIVE MARKET";
  $("#market-replay-label").textContent = `${frameLabel} · GAME ${view.game ?? "—"}`;
  $("#market-replay-subtitle").textContent = state.marketReplayMode === "round"
    ? `${formatNumber(view.decisions)} observed decisions in exactly one played game`
    : `${formatNumber(view.decisions)} observed decisions through ${formatNumber(view.frameCount)} played games`;
  $("#market-replay-prev").disabled = view.index <= 0;
  $("#market-replay-next").disabled = view.index >= view.games.length - 1;
  $$('[data-market-replay-mode]').forEach(button => {
    const active = button.dataset.marketReplayMode === state.marketReplayMode;
    button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
  });
}

function stopMarketReplay({sync = false} = {}) {
  if (state.marketReplayTimer) clearInterval(state.marketReplayTimer);
  state.marketReplayTimer = null;
  const button = $("#market-replay-play");
  if (button) {
    button.textContent = "Play market";
    button.setAttribute("aria-pressed", "false");
  }
  $("#market-panel")?.querySelector(".market-replay")?.classList.remove("is-playing");
  if (sync && state.market) syncInvestigationUrl("trends");
}

function setMarketReplayIndex(index, {sync = true, stop = true} = {}) {
  if (!state.market?.gameIds?.length) return;
  if (stop) stopMarketReplay();
  state.marketReplayIndex = clamp(Number(index) || 0, 0, state.market.gameIds.length - 1);
  state.marketReplayGame = state.market.gameIds[state.marketReplayIndex];
  renderMarket();
  if (sync) syncInvestigationUrl("trends");
}

function toggleMarketReplay() {
  if (!state.market?.gameIds?.length) return;
  if (state.marketReplayTimer) { stopMarketReplay({sync: true}); return; }
  stopReplay();
  if (state.raceTimer) {
    clearInterval(state.raceTimer); state.raceTimer = null;
    $("#race-play").textContent = "Play race";
  }
  if (state.marketReplayIndex >= state.market.gameIds.length - 1) {
    state.marketReplayIndex = 0;
    state.marketReplayGame = state.market.gameIds[0];
    renderMarket();
  }
  const button = $("#market-replay-play");
  button.textContent = "Pause market";
  button.setAttribute("aria-pressed", "true");
  $("#market-panel").querySelector(".market-replay").classList.add("is-playing");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  state.marketReplayTimer = setInterval(() => {
    if (state.marketReplayIndex >= state.market.gameIds.length - 1) {
      stopMarketReplay({sync: true}); return;
    }
    setMarketReplayIndex(state.marketReplayIndex + 1, {sync: false, stop: false});
  }, reduced ? 1100 : 420);
}

function marketCounterparties(team = state.marketTeam) {
  return (state.market?.teams || []).filter(name => name !== team).map(counterparty => {
    const issued = marketEdge(team, counterparty);
    const reviewed = marketEdge(counterparty, team);
    return {
      team: counterparty,
      incomeFrom: safeNumber(issued?.issuerIncome),
      costTo: safeNumber(reviewed?.reviewerCost),
      net: safeNumber(issued?.issuerIncome) - safeNumber(reviewed?.reviewerCost),
      acceptsUs: issued?.acceptRate ?? null,
      weAccept: reviewed?.acceptRate ?? null,
      wrongByThem: safeNumber(issued?.wrongCost),
      wrongByUs: safeNumber(reviewed?.wrongCost),
      hiddenAgainstUs: safeNumber(reviewed?.hiddenFraud),
      issuedDecisions: safeNumber(issued?.decisions),
      reviewedDecisions: safeNumber(reviewed?.decisions),
    };
  });
}

function renderMarketKpis() {
  const row = selectedMarketSummary();
  if (!row) return;
  const view = currentMarketView();
  const host = $("#market-kpis"); clear(host);
  const ranked = [...view.summaries].sort((a, b) => b.net - a.net || a.team.localeCompare(b.team));
  const rank = ranked.findIndex(candidate => candidate.team === row.team) + 1;
  const windowLabel = state.marketReplayMode === "round" ? `game ${view.game}` : `games ${view.games[0]}–${view.game}`;
  const officialNote = row.officialTotal === null
    ? "official score unavailable for this frame"
    : `${formatCurrency(row.officialTotal)} official · reconciliation ${signed(row.scoreReconciliationDelta)}`;
  const specs = [
    [`${state.marketReplayMode === "round" ? "Round" : "Cumulative"} rank by net`, `${rank} / ${ranked.length}`, officialNote, row.team === "Oasis" ? "cyan" : ""],
    ["Issued income", formatCurrency(row.issuedIncome, true), `${formatNumber(row.issuedDecisions)} issuer→reviewer decisions`, "positive"],
    ["Reviewer cost", formatCurrency(row.reviewerCost, true), `${formatNumber(row.reviewedDecisions)} reviewer cells`, "negative"],
    ["Net score", signed(row.net), `issued income − reviewer cost · ${windowLabel}`, row.net >= 0 ? "positive" : "negative"],
    ["Wrong-review cost", formatCurrency(row.wrongReviewCost, true), `${row.rejectFairCount} fair rejects · ${row.acceptFraudCount} fraud accepts`, row.wrongReviewCost ? "warning" : "positive"],
    ["Accept behavior", `${formatPercent(row.marketAcceptRate)} / ${formatPercent(row.reviewerAcceptRate)}`, "market accepts this team / this team accepts market", ""],
    ["All-history aggression", row.medianChargeToFloor === null ? "unknown" : `${formatNumber(row.medianChargeToFloor, 2)}×`, `${formatPercent(row.aggressionCoverage)} observable charge-group coverage · not replay-filtered`, ""],
  ];
  specs.forEach(([label, value, note, tone]) => host.append(metricCard(label, value, note, tone)));
  $("#market-status").textContent = `${state.market.teams.length} TEAMS · G${view.game} ${state.marketReplayMode.toUpperCase()} · ${formatNumber(view.decisions)} DECISIONS`;
}

function renderMarketPair() {
  const host = $("#market-pair"); clear(host);
  const peer = marketCounterparties().find(row => row.team === state.marketPeer);
  if (!peer) return;
  const outgoing = marketEdge(state.marketTeam, peer.team);
  const incoming = marketEdge(peer.team, state.marketTeam);
  const identity = element("div", {class: "market-pair-identity"}, [
    element("span", {text: "FOCUSED BILATERAL"}),
    element("div", {}, [element("strong", {text: state.marketTeam}), element("i", {text: "↔"}), element("strong", {text: peer.team})]),
    element("small", {text: `${formatNumber(outgoing.decisions)} decisions issued toward peer · ${formatNumber(incoming.decisions)} reviewed from peer`}),
  ]);
  const stats = [
    ["Income from peer", formatCurrency(peer.incomeFrom, true), "selected team as issuer"],
    ["Reviewer cost to peer", formatCurrency(peer.costTo, true), "selected team as reviewer"],
    ["Bilateral net", signed(peer.net), "income from − reviewer cost to"],
    ["Acceptance", `${formatPercent(peer.acceptsUs)} / ${formatPercent(peer.weAccept)}`, "peer accepts us / we accept peer"],
    ["Wrong-review cost", `${formatCurrency(peer.wrongByThem, true)} / ${formatCurrency(peer.wrongByUs, true)}`, "by peer / by selected team"],
    ["Hidden against us", formatNumber(peer.hiddenAgainstUs), "rejected fraudulent groups · attempted EUR unknown"],
  ];
  const cards = element("div", {class: "market-pair-stats"}, stats.map(([label, value, note]) => element("div", {}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
  const actions = element("div", {class: "market-pair-actions"});
  const reverse = element("button", {type: "button", class: "button", text: "Reverse viewpoint"});
  reverse.addEventListener("click", () => selectMarketTeam(peer.team, state.marketTeam));
  actions.append(reverse);
  host.append(identity, cards, actions);
}

function renderMarketMatrix() {
  const host = $("#market-matrix"); clear(host);
  const legend = $("#market-legend"); clear(legend);
  const teams = state.market.teams;
  const spec = marketMetricSpec();
  const values = currentMarketView().edges.map(row => row[spec.field]).filter(value => value !== null && Number.isFinite(Number(value)));
  const max = spec.unit === "rate" ? 1 : Math.max(1, ...values.map(value => Math.abs(value)));
  host.style.gridTemplateColumns = `126px repeat(${teams.length},minmax(43px,1fr))`;
  host.append(element("div", {class: "market-corner", text: "ISSUER ↓ / REVIEWER →"}));
  teams.forEach(team => {
    const header = element("button", {type: "button", class: `market-column-head ${team === state.marketTeam ? "selected" : ""}`, title: team, "aria-label": `Inspect ${team}`, text: marketShortName(team)});
    header.addEventListener("click", () => selectMarketTeam(team, null)); host.append(header);
  });
  teams.forEach(issuer => {
    const rowHeader = element("button", {type: "button", class: `market-row-head ${issuer === state.marketTeam ? "selected" : ""}`, title: issuer, text: issuer});
    rowHeader.addEventListener("click", () => selectMarketTeam(issuer, null)); host.append(rowHeader);
    teams.forEach(reviewer => {
      if (issuer === reviewer) {
        host.append(element("div", {class: "market-cell self", "aria-label": `${issuer} does not review its own charge`, text: "—"}));
        return;
      }
      const edge = marketEdge(issuer, reviewer);
      const raw = edge?.[spec.field];
      const numeric = raw === null || raw === undefined ? null : safeNumber(raw);
      const intensity = numeric === null ? 0 : spec.unit === "rate" ? clamp(numeric, 0, 1) : Math.sqrt(Math.abs(numeric) / max);
      const textValue = numeric === null ? "?" : spec.unit === "rate" ? `${formatNumber(numeric * 100, 0)}%` : formatCurrency(numeric, true).replace("€", "");
      const selected = issuer === state.marketTeam || reviewer === state.marketTeam;
      const focused = (issuer === state.marketTeam && reviewer === state.marketPeer) || (issuer === state.marketPeer && reviewer === state.marketTeam);
      const cell = element("button", {type: "button", class: `market-cell ${selected ? "selected-axis" : ""} ${focused ? "focused-edge" : ""}`, text: textValue,
        "aria-label": `${issuer} issued and ${reviewer} reviewed: ${spec.label} ${formatCohortMetric(numeric, spec.unit === "rate" ? "rate" : "EUR")}`});
      cell.style.backgroundColor = `rgba(${spec.color},${.025 + intensity * .68})`;
      addTooltip(cell, [`${issuer} → ${reviewer}`, `${spec.label} ${formatCohortMetric(numeric, spec.unit === "rate" ? "rate" : "EUR")}`, `${edge.decisions} decisions · ${formatPercent(edge.acceptRate)} accepted`, `Issuer income ${formatCurrency(edge.issuerIncome)} · reviewer cost ${formatCurrency(edge.reviewerCost)}`, `Wrong cost ${formatCurrency(edge.wrongCost)} · penalty wedge ${formatCurrency(edge.penaltyWedge)} · ${edge.hiddenFraud} hidden rejected-fraud groups`]);
      cell.addEventListener("click", () => selectMarketTeam(issuer, reviewer));
      host.append(cell);
    });
  });
  legend.append(
    element("div", {class: "market-legend-scale"}, [element("span", {text: "LOW"}), element("i"), element("span", {text: "HIGH"})]),
    element("strong", {text: spec.label}),
    element("p", {text: `${spec.note}. Range: ${spec.unit === "rate" ? "0–100%" : `${formatCurrency(0)}–${formatCurrency(max, true)}`}. Empty self-cells are structurally ineligible.`}),
    element("small", {text: "Rows issue. Columns review. Highlighted axes involve the selected team."}),
  );
  legend.querySelector("i").style.background = `linear-gradient(90deg,rgba(${spec.color},.03),rgba(${spec.color},.72))`;
}

function renderMarketOutcome() {
  const host = $("#market-outcome"); clear(host);
  const incoming = currentMarketView().edges.filter(row => row.reviewer === state.marketTeam);
  const keys = [
    ["acceptFair", "ACCEPT × FAIR", colors.green], ["acceptFraud", "ACCEPT × FRAUD", colors.amber],
    ["rejectFair", "REJECT × FAIR", colors.red], ["rejectFraud", "REJECT × FRAUD", colors.blue],
  ];
  const totalCost = incoming.reduce((sum, edge) => sum + edge.reviewerCost, 0);
  keys.forEach(([key, label, color]) => {
    const count = incoming.reduce((sum, edge) => sum + edge[`${key}Count`], 0);
    const cost = incoming.reduce((sum, edge) => sum + edge[`${key}Cost`], 0);
    const card = element("div", {class: `market-outcome-cell ${key}`}, [element("span", {text: label}), element("strong", {text: formatCurrency(cost, true)}), element("small", {text: `${formatNumber(count)} decisions · ${formatPercent(totalCost ? cost / totalCost : 0)} of observed reviewer cost`})]);
    card.style.setProperty("--market-outcome-color", color); host.append(card);
  });
  const unresolvedCount = incoming.reduce((sum, edge) => sum + edge.unresolvedCount, 0);
  const unresolvedCost = incoming.reduce((sum, edge) => sum + edge.unresolvedCost, 0);
  host.append(element("div", {class: "market-outcome-unresolved"}, [element("span", {text: "UNRESOLVED EVIDENCE"}), element("strong", {text: `${formatNumber(unresolvedCount)} decisions · ${formatCurrency(unresolvedCost)} observed cost`})]));
}

function renderMarketBilateral() {
  const host = $("#market-bilateral-chart"); clear(host);
  const rows = marketCounterparties().sort((a, b) => a.net - b.net || a.team.localeCompare(b.team));
  const width = 920, rowHeight = 31, height = 52 + rows.length * rowHeight, margin = {left: 142, right: 105, top: 28, bottom: 26};
  const center = margin.left + (width - margin.left - margin.right) / 2;
  const half = (width - margin.left - margin.right) / 2;
  const max = Math.max(1, ...rows.flatMap(row => [row.incomeFrom, row.costTo]));
  const scale = value => value / max * half * .92;
  const svg = svgRoot(width, height, `Bilateral income and reviewer cost for ${state.marketTeam}`);
  svg.append(svgElement("line", {x1: center, y1: margin.top - 10, x2: center, y2: height - margin.bottom, stroke: colors.muted, "stroke-width": 1}));
  svg.append(svgElement("text", {x: center - 9, y: 15, fill: colors.red, "font-size": 8, "font-family": "var(--mono)", "text-anchor": "end"}, "REVIEWER COST TO TEAM"));
  svg.append(svgElement("text", {x: center + 9, y: 15, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)"}, "ISSUER INCOME FROM TEAM"));
  rows.forEach((row, index) => {
    const y = margin.top + index * rowHeight + rowHeight / 2;
    svg.append(svgElement("line", {x1: margin.left, y1: y + rowHeight / 2, x2: width - margin.right, y2: y + rowHeight / 2, class: "grid-line"}));
    const label = svgElement("text", {x: margin.left - 10, y: y + 3, fill: row.team === "Oasis" ? colors.cyan : "#98a4ad", "font-size": 8.5, "font-family": "var(--mono)", "text-anchor": "end", tabindex: 0, class: "interactive", role: "button"}, row.team);
    label.addEventListener("click", () => selectMarketTeam(row.team, state.marketTeam)); svg.append(label);
    const costWidth = scale(row.costTo), incomeWidth = scale(row.incomeFrom);
    const cost = svgElement("rect", {x: center - costWidth, y: y - 5, width: costWidth, height: 10, rx: 2, fill: colors.red, "fill-opacity": .7, tabindex: 0, class: "interactive"});
    const income = svgElement("rect", {x: center, y: y - 5, width: incomeWidth, height: 10, rx: 2, fill: colors.cyan, "fill-opacity": .7, tabindex: 0, class: "interactive"});
    const tooltip = [`${state.marketTeam} ↔ ${row.team}`, `Income from ${row.team}: ${formatCurrency(row.incomeFrom)} · ${row.issuedDecisions} decisions`, `Reviewer cost to ${row.team}: ${formatCurrency(row.costTo)} · ${row.reviewedDecisions} decisions`, `Bilateral net ${signed(row.net)} · accepts us ${formatPercent(row.acceptsUs)} · we accept ${formatPercent(row.weAccept)}`, `Wrong cost by us ${formatCurrency(row.wrongByUs)} · ${row.hiddenAgainstUs} hidden rejected-fraud groups against us`];
    addTooltip(cost, tooltip); addTooltip(income, tooltip);
    [cost, income].forEach(marker => marker.addEventListener("click", () => selectMarketTeam(state.marketTeam, row.team)));
    if (row.team === state.marketPeer) { cost.setAttribute("stroke", colors.cyan); cost.setAttribute("stroke-width", "1.5"); income.setAttribute("stroke", colors.cyan); income.setAttribute("stroke-width", "1.5"); }
    svg.append(cost, income);
    svg.append(svgElement("text", {x: width - margin.right + 9, y: y + 3, fill: row.net >= 0 ? colors.green : colors.red, "font-size": 8.5, "font-family": "var(--mono)"}, signed(row.net)));
  });
  host.append(svg);
}

function marketFrameEdge(game, issuer, reviewer) {
  return (state.marketFramesByGame.get(game) || []).find(
    row => row.issuer === issuer && row.reviewer === reviewer
  ) || emptyMarketEdge(issuer, reviewer);
}

function marketPairTimeline() {
  let cumulative = 0;
  return (state.market?.gameIds || []).map(game => {
    const outgoing = marketFrameEdge(game, state.marketTeam, state.marketPeer);
    const incoming = marketFrameEdge(game, state.marketPeer, state.marketTeam);
    const income = safeNumber(outgoing.issuerIncome);
    const cost = safeNumber(incoming.reviewerCost);
    const net = income - cost;
    cumulative += net;
    return {
      game, income, cost, net, cumulative,
      peerAcceptRate: outgoing.decisions ? outgoing.accepted / outgoing.decisions : null,
      teamAcceptRate: incoming.decisions ? incoming.accepted / incoming.decisions : null,
      wrongByTeam: safeNumber(incoming.wrongCost),
      hiddenAgainstTeam: safeNumber(incoming.hiddenFraud),
      issuedDecisions: safeNumber(outgoing.decisions),
      reviewedDecisions: safeNumber(incoming.decisions),
    };
  });
}

function renderMarketPairTrajectory() {
  const host = $("#market-pair-trajectory"); clear(host);
  const body = $("#market-pair-timeline-table"); clear(body);
  const rows = marketPairTimeline();
  if (!rows.length || !state.marketPeer) return;
  const view = currentMarketView();
  const width = Math.max(1080, rows.length * 16 + 120), height = 390;
  const margin = {left: 70, right: 32, top: 42, bottom: 45};
  const flowBottom = 225, cumulativeTop = 270, cumulativeBottom = height - margin.bottom;
  const maxAbs = Math.max(1, ...rows.map(row => Math.abs(row.net)));
  const cumulativeValues = rows.map(row => row.cumulative);
  const cumulativeMin = Math.min(0, ...cumulativeValues), cumulativeMax = Math.max(0, ...cumulativeValues);
  const x = index => margin.left + index / Math.max(1, rows.length - 1) * (width - margin.left - margin.right);
  const zeroY = margin.top + (flowBottom - margin.top) / 2;
  const yNet = value => zeroY - value / maxAbs * (flowBottom - margin.top) * .44;
  const yCumulative = value => cumulativeTop + (cumulativeMax - value) / (cumulativeMax - cumulativeMin || 1) * (cumulativeBottom - cumulativeTop);
  const svg = svgRoot(width, height, `${state.marketTeam} and ${state.marketPeer} bilateral economics by game`);
  svg.append(svgElement("line", {x1: margin.left, y1: zeroY, x2: width - margin.right, y2: zeroY, stroke: colors.muted, "stroke-width": 1}));
  svg.append(svgElement("line", {x1: margin.left, y1: yCumulative(0), x2: width - margin.right, y2: yCumulative(0), class: "grid-line"}));
  const barWidth = Math.max(2.5, Math.min(9, (width - margin.left - margin.right) / rows.length * .56));
  rows.forEach((row, index) => {
    const xx = x(index), yy = yNet(row.net);
    const bar = svgElement("rect", {
      x: xx - barWidth / 2, y: Math.min(zeroY, yy), width: barWidth,
      height: Math.max(1, Math.abs(yy - zeroY)), rx: 1.5,
      fill: row.net >= 0 ? colors.cyan : colors.red, "fill-opacity": .56,
    });
    svg.append(bar);
  });
  svg.append(svgElement("path", {d: linePath(rows.map((row, index) => [x(index), yCumulative(row.cumulative)])), fill: "none", stroke: colors.violet, "stroke-width": 2.2}));
  const cursorX = x(view.index);
  svg.append(svgElement("line", {x1: cursorX, y1: margin.top - 12, x2: cursorX, y2: cumulativeBottom, stroke: colors.cyan, "stroke-width": 1.4, "stroke-dasharray": "3 4", class: "market-replay-cursor"}));
  svg.append(svgElement("circle", {cx: cursorX, cy: yCumulative(rows[view.index].cumulative), r: 4.5, fill: colors.cyan, stroke: "#07100f", "stroke-width": 1.5, class: "market-replay-cursor"}));
  rows.forEach((row, index) => {
    const hit = svgElement("rect", {x: x(index) - 7, y: margin.top - 10, width: 14, height: cumulativeBottom - margin.top + 12, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Inspect focused pair at game ${row.game}`});
    addTooltip(hit, [
      `${state.marketTeam} ↔ ${state.marketPeer} · game ${row.game}`,
      `Income from peer ${formatCurrency(row.income)} · reviewer cost to peer ${formatCurrency(row.cost)}`,
      `Bilateral net ${signed(row.net)} · cumulative ${signed(row.cumulative)}`,
      `Peer accepts team ${formatPercent(row.peerAcceptRate)} · team accepts peer ${formatPercent(row.teamAcceptRate)}`,
      `Wrong cost by team ${formatCurrency(row.wrongByTeam)} · ${row.hiddenAgainstTeam} hidden rejected-fraud groups`,
    ]);
    hit.addEventListener("click", () => setMarketReplayIndex(index));
    hit.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setMarketReplayIndex(index); } });
    svg.append(hit);
    if (index % Math.max(1, Math.ceil(rows.length / 12)) === 0 || index === rows.length - 1) {
      svg.append(svgElement("text", {x: x(index), y: height - 20, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    }
    body.append(element("tr", {class: index === view.index ? "selected-row" : ""}, [
      element("td", {text: row.game}), element("td", {class: "money", text: formatCurrency(row.income)}),
      element("td", {class: "money", text: formatCurrency(row.cost)}), element("td", {class: "money", text: signed(row.net)}),
      element("td", {class: "money", text: signed(row.cumulative)}), element("td", {text: formatPercent(row.peerAcceptRate)}),
      element("td", {text: formatPercent(row.teamAcceptRate)}), element("td", {class: "money", text: formatCurrency(row.wrongByTeam)}),
      element("td", {text: row.hiddenAgainstTeam}),
    ]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 17, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)"}, "PER-GAME BILATERAL NET · POSITIVE PAYS SELECTED TEAM"));
  svg.append(svgElement("text", {x: margin.left, y: cumulativeTop - 10, fill: colors.violet, "font-size": 8, "font-family": "var(--mono)"}, "CUMULATIVE BILATERAL NET · SEPARATE SCALE"));
  host.append(svg);
  $("#market-pair-trajectory-caption").textContent = `${state.marketTeam} ↔ ${state.marketPeer} · cursor G${view.game} · ${state.marketReplayMode === "round" ? "matrix shows only this game" : "matrix accumulates through this game"}`;
}

function renderMarketTimeline() {
  const host = $("#market-timeline-chart"); clear(host);
  const body = $("#market-timeline-table"); clear(body);
  const rows = state.market.timeline.filter(row => row.team === state.marketTeam).sort((a, b) => a.game - b.game);
  if (!rows.length) return;
  const view = currentMarketView();
  const width = Math.max(1080, rows.length * 17 + 120), height = 500;
  const margin = {left: 72, right: 30, top: 38, bottom: 48};
  const topBottom = 325, lowerTop = 365, lowerBottom = height - margin.bottom;
  const maxIncome = Math.max(1, ...rows.map(row => row.issuedIncome));
  const maxCost = Math.max(1, ...rows.map(row => row.reviewerCost));
  const x = index => margin.left + index / Math.max(1, rows.length - 1) * (width - margin.left - margin.right);
  const zeroY = margin.top + (maxIncome / (maxIncome + maxCost)) * (topBottom - margin.top);
  const yFlow = value => value >= 0 ? zeroY - value / maxIncome * (zeroY - margin.top) : zeroY + Math.abs(value) / maxCost * (topBottom - zeroY);
  const cumulative = rows.map(row => row.cumulativeNet);
  const cumMin = Math.min(0, ...cumulative), cumMax = Math.max(0, ...cumulative);
  const yCum = value => lowerTop + (cumMax - value) / (cumMax - cumMin || 1) * (lowerBottom - lowerTop);
  const svg = svgRoot(width, height, `Market economics over time for ${state.marketTeam}`);
  svg.append(svgElement("line", {x1: margin.left, y1: zeroY, x2: width - margin.right, y2: zeroY, stroke: colors.muted, "stroke-width": 1}));
  rows.forEach((row, index) => {
    const xx = x(index), barWidth = Math.max(2, (width - margin.left - margin.right) / rows.length * .58);
    svg.append(svgElement("rect", {x: xx - barWidth / 2, y: yFlow(row.issuedIncome), width: barWidth, height: zeroY - yFlow(row.issuedIncome), fill: colors.cyan, "fill-opacity": .38}));
    svg.append(svgElement("rect", {x: xx - barWidth / 2, y: zeroY, width: barWidth, height: yFlow(-row.reviewerCost) - zeroY, fill: colors.red, "fill-opacity": .38}));
  });
  const netPoints = rows.map((row, index) => [x(index), yFlow(row.net)]);
  svg.append(svgElement("path", {d: linePath(netPoints), fill: "none", stroke: colors.green, "stroke-width": 1.8}));
  const cumulativePoints = rows.map((row, index) => [x(index), yCum(row.cumulativeNet)]);
  svg.append(svgElement("path", {d: linePath(cumulativePoints), fill: "none", stroke: colors.violet, "stroke-width": 2.2}));
  svg.append(svgElement("line", {x1: margin.left, y1: yCum(0), x2: width - margin.right, y2: yCum(0), class: "grid-line"}));
  const cursorX = x(view.index);
  svg.append(svgElement("line", {x1: cursorX, y1: margin.top - 12, x2: cursorX, y2: lowerBottom, stroke: colors.cyan, "stroke-width": 1.4, "stroke-dasharray": "3 4", class: "market-replay-cursor"}));
  svg.append(svgElement("circle", {cx: cursorX, cy: yCum(rows[view.index].cumulativeNet), r: 4.5, fill: colors.cyan, stroke: "#07100f", "stroke-width": 1.5, class: "market-replay-cursor"}));
  rows.forEach((row, index) => {
    const hit = svgElement("rect", {x: x(index) - 6, y: margin.top, width: 12, height: lowerBottom - margin.top, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Inspect market at game ${row.game}`});
    addTooltip(hit, [`${state.marketTeam} · game ${row.game}`, `Income ${formatCurrency(row.issuedIncome)} · reviewer cost ${formatCurrency(row.reviewerCost)} · round net ${signed(row.net)}`, `Official round ${signed(row.officialScore)} · reconciliation ${signed(row.scoreReconciliationDelta)}`, `Cumulative net ${signed(row.cumulativeNet)} · official cumulative ${signed(row.officialCumulativeScore)}`, `${row.issuedDecisions} issued / ${row.reviewedDecisions} reviewed decisions · market accepts ${formatPercent(row.marketAcceptRate)} · reviewer accepts ${formatPercent(row.reviewerAcceptRate)}`]);
    hit.addEventListener("click", () => setMarketReplayIndex(index));
    hit.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setMarketReplayIndex(index); } });
    svg.append(hit);
    if (index % Math.max(1, Math.ceil(rows.length / 12)) === 0 || index === rows.length - 1) svg.append(svgElement("text", {x: x(index), y: height - 23, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    body.append(element("tr", {class: index === view.index ? "selected-row" : ""}, [element("td", {text: row.game}), element("td", {class: "money", text: formatCurrency(row.issuedIncome)}), element("td", {class: "money", text: formatCurrency(row.reviewerCost)}), element("td", {class: "money", text: signed(row.net)}), element("td", {class: "money", text: signed(row.cumulativeNet)}), element("td", {text: formatPercent(row.marketAcceptRate)}), element("td", {text: formatPercent(row.reviewerAcceptRate)}), element("td", {class: "money", text: signed(row.officialScore)}), element("td", {class: "money", text: signed(row.officialCumulativeScore)}), element("td", {class: "money", text: signed(row.scoreReconciliationDelta)})]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 17, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)"}, "INCOME + · COST − · NET LINE"));
  svg.append(svgElement("text", {x: margin.left, y: lowerTop - 10, fill: colors.violet, "font-size": 8, "font-family": "var(--mono)"}, "CUMULATIVE NET · SEPARATE SCALE"));
  host.append(svg);
}

function renderMarketTables() {
  const view = currentMarketView();
  const edgeBody = $("#market-edge-table"); clear(edgeBody);
  [...view.edges].sort((a, b) => b.wrongCost - a.wrongCost || b.reviewerCost - a.reviewerCost).forEach(row => edgeBody.append(element("tr", {}, [element("td", {text: row.issuer}), element("td", {text: row.reviewer}), element("td", {text: row.decisions}), element("td", {text: row.accepted}), element("td", {text: formatPercent(row.acceptRate)}), element("td", {class: "money", text: formatCurrency(row.issuerIncome)}), element("td", {class: "money", text: formatCurrency(row.reviewerCost)}), element("td", {class: "money", text: formatCurrency(row.wrongCost)}), element("td", {class: "money", text: formatCurrency(row.penaltyWedge)}), element("td", {text: row.hiddenFraud})])));
  const teamBody = $("#market-team-table"); clear(teamBody);
  [...view.summaries].sort((a, b) => b.net - a.net).forEach(row => teamBody.append(element("tr", {}, [element("td", {text: row.team}), element("td", {class: "money", text: formatCurrency(row.issuedIncome)}), element("td", {class: "money", text: formatCurrency(row.reviewerCost)}), element("td", {class: "money", text: signed(row.net)}), element("td", {text: formatPercent(row.marketAcceptRate)}), element("td", {text: formatPercent(row.reviewerAcceptRate)}), element("td", {class: "money", text: formatCurrency(row.wrongReviewCost)}), element("td", {text: row.medianChargeToFloor === null ? "unknown" : `${formatNumber(row.medianChargeToFloor, 2)}×`}), element("td", {text: `${formatPercent(row.aggressionCoverage)} all-history`}), element("td", {class: "money", text: row.scoreReconciliationDelta === null ? "unknown" : signed(row.scoreReconciliationDelta)})])));
}

function renderMarket() {
  if (!state.market) return;
  renderMarketReplayControls(); renderMarketKpis(); renderMarketPair();
  renderMarketPairTrajectory(); renderMarketMatrix(); renderMarketOutcome();
  renderMarketBilateral(); renderMarketTimeline(); renderMarketTables();
}

function selectMarketTeam(team, peer = null) {
  if (!state.market?.teams?.includes(team)) return;
  state.marketTeam = team; state.marketPeer = peer;
  populateMarketControls(); renderMarket(); syncInvestigationUrl("trends");
}

function rivalLeader() {
  return [...(state.market?.summaries || [])].filter(row => row.team !== "Oasis")
    .sort((a, b) => b.net - a.net || a.team.localeCompare(b.team))[0]?.team || null;
}

function populateRivalControls() {
  if (!state.market) return;
  const select = $("#rival-team"), previous = state.rivalTeam; clear(select);
  const ranked = [...state.market.summaries].sort((a, b) => b.net - a.net || a.team.localeCompare(b.team));
  ranked.filter(row => row.team !== "Oasis").forEach((row, index) => {
    const rank = ranked.findIndex(candidate => candidate.team === row.team) + 1;
    select.append(element("option", {value: row.team, text: `#${rank} · ${row.team} · ${signed(row.net)}`}));
  });
  state.rivalTeam = state.market.teams.includes(previous) && previous !== "Oasis" ? previous : rivalLeader();
  if (state.rivalTeam) select.value = state.rivalTeam;
  if (!RIVAL_WINDOWS.has(state.rivalWindow)) state.rivalWindow = "all";
  $("#rival-window").value = state.rivalWindow;
}

function rivalWindowLabel(result) {
  if (!result.games.length) return "no paired games";
  return `${result.summary.games} paired games · G${result.games[0]}–G${result.games.at(-1)}`;
}

async function openRivalGame(game) {
  await selectGame(game);
  $("#game").scrollIntoView({behavior: "smooth", block: "start"});
}

function renderRivalNarrative(result) {
  const host = $("#rival-narrative"); clear(host);
  const gap = result.summary.scoreGap;
  host.dataset.tone = gap >= 0 ? "ahead" : "behind";
  const dominant = Math.abs(result.summary.incomeEdge) >= Math.abs(result.summary.costEdge) ? "issuer income" : "reviewer cost";
  const leadText = gap >= 0 ? `OASIS LEADS ${result.rivalTeam.toUpperCase()} BY ${formatCurrency(Math.abs(gap))}` : `OASIS TRAILS ${result.rivalTeam.toUpperCase()} BY ${formatCurrency(Math.abs(gap))}`;
  host.append(element("div", {class: "rival-narrative-primary"}, [
    element("span", {text: `${rivalWindowLabel(result)} · MATCHED ONLY`}),
    element("strong", {text: leadText}),
    element("small", {text: `${dominant} is the larger accounting component · displayed-official residual ${result.summary.reconciliationDelta === null ? "unavailable" : signed(result.summary.reconciliationDelta)} total / ${result.summary.maxRoundReconciliationDelta === null ? "unavailable" : formatCurrency(result.summary.maxRoundReconciliationDelta)} max per game`}),
  ]));
  const facts = [
    ["INCOME EDGE", signed(result.summary.incomeEdge), "Oasis income − rival income"],
    ["COST EDGE", signed(result.summary.costEdge), "rival cost − Oasis cost"],
    ["ALL-HISTORY RANKS", `#${result.summary.oasisRank} / #${result.summary.rivalRank}`, `Oasis / ${result.rivalTeam}`],
  ];
  facts.forEach(([label, value, note]) => host.append(element("div", {class: "rival-narrative-fact"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
}

function renderRivalKpis(result) {
  const host = $("#rival-kpis"); clear(host);
  const bootstrap = result.bootstrap;
  const specs = [
    ["PAIRED SCORE GAP", signed(result.summary.scoreGap), `${rivalWindowLabel(result)} · Oasis − rival`, result.summary.scoreGap >= 0 ? "positive" : "negative"],
    ["ROUND RECORD", `${result.summary.oasisRoundWins}–${result.summary.rivalRoundWins}–${result.summary.tiedRounds}`, "Oasis-ahead / rival-ahead / tied matched games", ""],
    ["MEDIAN ROUND GAP", signed(result.summary.medianGap), "one paired game · robust centre", result.summary.medianGap >= 0 ? "positive" : "negative"],
    ["TOP-1 CONCENTRATION", formatPercent(result.summary.topOneAbsoluteShare), `${formatPercent(result.summary.topFiveAbsoluteShare)} in five largest |gaps|`, ""],
    ["BOOTSTRAP P(MEAN > 0)", formatPercent(bootstrap.probabilityOasisMeanAhead), `${formatNumber(bootstrap.runs)} paired-game draws · seed ${bootstrap.seed}`, ""],
    ["WRONG-COST EDGE", signed(result.rival.wrongCost - result.oasis.wrongCost), `${formatCurrency(result.oasis.wrongCost)} Oasis vs ${formatCurrency(result.rival.wrongCost)} rival · observed`, result.oasis.wrongCost <= result.rival.wrongCost ? "positive" : "negative"],
  ];
  specs.forEach(([label, value, note, tone]) => host.append(element("div", {class: "rival-kpi"}, [element("span", {text: label}), element("strong", {text: value, class: tone}), element("small", {text: note})])));
}

function renderRivalBridge(result) {
  const host = $("#rival-bridge-chart"); clear(host);
  const width = 760, height = 355, margin = {left: 78, right: 35, top: 44, bottom: 65};
  const steps = [
    {label: "INCOME EDGE", from: 0, to: result.summary.incomeEdge, value: result.summary.incomeEdge, kind: "step"},
    {label: "COST EDGE", from: result.summary.incomeEdge, to: result.summary.scoreGap, value: result.summary.costEdge, kind: "step"},
    {label: "SCORE GAP", from: 0, to: result.summary.scoreGap, value: result.summary.scoreGap, kind: "total"},
  ];
  const values = [0, ...steps.flatMap(row => [row.from, row.to])];
  let min = Math.min(...values), max = Math.max(...values); const pad = (max - min || 1) * .16; min -= pad; max += pad;
  const y = value => margin.top + (max - value) / (max - min) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, `Oasis score gap to ${result.rivalTeam} decomposed into income and reviewer-cost edges`);
  for (let tick = 0; tick <= 4; tick += 1) {
    const value = min + (max - min) * tick / 4, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 10, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true)));
  }
  const centers = [180, 385, 590], barWidth = 112;
  steps.forEach((row, index) => {
    const x = centers[index], top = y(Math.max(row.from, row.to)), bottom = y(Math.min(row.from, row.to));
    const color = row.kind === "total" ? colors.blue : row.value >= 0 ? colors.green : colors.red;
    const rect = svgElement("rect", {x: x - barWidth / 2, y: top, width: barWidth, height: Math.max(2, bottom - top), rx: 3, fill: color, "fill-opacity": row.kind === "total" ? .72 : .58, tabindex: 0, class: "interactive", role: "img", "aria-label": `${row.label.toLocaleLowerCase()}, ${signed(row.value)} Oasis edge`});
    addTooltip(rect, [row.label.replaceAll(" EDGE", ""), `${signed(row.value)} Oasis edge`, row.kind === "total" ? "income edge + cost edge" : row.label === "INCOME EDGE" ? "Oasis issued income − rival issued income" : "rival reviewer cost − Oasis reviewer cost", rivalWindowLabel(result)]); svg.append(rect);
    svg.append(svgElement("text", {x, y: Math.min(top - 10, bottom - 10), fill: color, "font-size": 11, "font-family": "var(--mono)", "font-weight": 650, "text-anchor": "middle"}, signed(row.value)));
    svg.append(svgElement("text", {x, y: height - 28, class: "axis-label", "text-anchor": "middle"}, row.label));
    if (index < 2) svg.append(svgElement("line", {x1: x + barWidth / 2, y1: y(row.to), x2: centers[index + 1] - barWidth / 2, y2: y(row.to), stroke: colors.muted, "stroke-width": 1, "stroke-dasharray": "3 3"}));
  });
  svg.append(svgElement("line", {x1: margin.left, y1: y(0), x2: width - margin.right, y2: y(0), stroke: colors.muted, "stroke-width": 1.2}));
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)"}, "EXACT IDENTITY · INCOME EDGE + COST EDGE = SCORE GAP · POSITIVE HELPS OASIS"));
  host.append(svg);
}

function renderRivalBootstrap(result) {
  const host = $("#rival-bootstrap"); clear(host);
  const boot = result.bootstrap;
  const range = Math.max(Math.abs(safeNumber(boot.p2_5)), Math.abs(safeNumber(boot.p97_5)), Math.abs(safeNumber(boot.observedMean)), 1);
  const position = value => clamp((safeNumber(value) + range) / (2 * range) * 100, 0, 100);
  const interval = element("div", {class: "rival-bootstrap-interval"}, [
    element("span", {text: "PAIRED MEAN GAP · 95% RESAMPLE INTERVAL"}),
    element("div", {class: "rival-bootstrap-track"}, [
      element("i", {style: `left:${position(boot.p2_5)}%;width:${Math.max(.8, position(boot.p97_5) - position(boot.p2_5))}%`}),
      element("b", {style: `left:${position(boot.observedMean)}%`, title: "Observed paired mean"}),
      element("em", {style: "left:50%", title: "Parity"}),
    ]),
    element("div", {class: "rival-bootstrap-labels"}, [element("span", {text: formatCurrency(boot.p2_5)}), element("strong", {text: `OBS ${signed(boot.observedMean)}`}), element("span", {text: formatCurrency(boot.p97_5)})]),
  ]);
  host.append(interval);
  const cards = [
    ["P(MEAN EDGE > 0)", formatPercent(boot.probabilityOasisMeanAhead), `${boot.runs} draws · MC margin ≤ ${formatPercent(boot.monteCarloMargin95)}`],
    ["TOP ROUND SHARE", formatPercent(result.summary.topOneAbsoluteShare), `of ${formatCurrency(result.summary.absoluteGapFlow)} total absolute paired-gap flow`],
    ["WITHOUT BEST ROUND", signed(result.summary.gapWithoutBestRound), result.summary.best ? `remove Oasis-favourable G${result.summary.best.game}` : "no paired games"],
    ["WITHOUT WORST ROUND", signed(result.summary.gapWithoutWorstRound), result.summary.worst ? `remove Oasis-adverse G${result.summary.worst.game}` : "no paired games"],
  ];
  const grid = element("div", {class: "rival-stability-grid"});
  cards.forEach(([label, value, note]) => grid.append(element("div", {}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})]))); host.append(grid);
}

function renderRivalGap(result) {
  const host = $("#rival-gap-chart"); clear(host); const decisive = $("#rival-decisive"); clear(decisive);
  const rows = result.rows, width = Math.max(1080, rows.length * 16 + 130), height = 430;
  const margin = {left: 76, right: 32, top: 43, bottom: 48}, barBottom = 260, cumulativeTop = 308, cumulativeBottom = height - margin.bottom;
  const x = index => margin.left + index / Math.max(1, rows.length - 1) * (width - margin.left - margin.right);
  const maxAbs = Math.max(1, ...rows.map(row => Math.abs(row.gap))), zero = margin.top + (barBottom - margin.top) / 2;
  const yGap = value => zero - value / maxAbs * (barBottom - margin.top) * .46;
  const cumulativeValues = rows.map(row => row.cumulativeGap), cumMin = Math.min(0, ...cumulativeValues), cumMax = Math.max(0, ...cumulativeValues);
  const yCum = value => cumulativeTop + (cumMax - value) / (cumMax - cumMin || 1) * (cumulativeBottom - cumulativeTop);
  const svg = svgRoot(width, height, `Paired per-game and cumulative Oasis score gap to ${result.rivalTeam}`);
  svg.append(svgElement("line", {x1: margin.left, y1: zero, x2: width - margin.right, y2: zero, stroke: colors.muted, "stroke-width": 1}));
  svg.append(svgElement("line", {x1: margin.left, y1: yCum(0), x2: width - margin.right, y2: yCum(0), class: "grid-line"}));
  const barWidth = Math.max(2.5, Math.min(9, (width - margin.left - margin.right) / Math.max(1, rows.length) * .56));
  rows.forEach((row, index) => {
    const xx = x(index), yy = yGap(row.gap);
    svg.append(svgElement("rect", {x: xx - barWidth / 2, y: Math.min(zero, yy), width: barWidth, height: Math.max(1, Math.abs(yy - zero)), rx: 1.3, fill: row.gap >= 0 ? colors.green : colors.red, "fill-opacity": .56}));
  });
  svg.append(svgElement("path", {d: linePath(rows.map((row, index) => [x(index), yCum(row.cumulativeGap)])), fill: "none", stroke: colors.violet, "stroke-width": 2.2}));
  rows.forEach((row, index) => {
    const hit = svgElement("rect", {x: x(index) - 7, y: margin.top - 10, width: 14, height: cumulativeBottom - margin.top + 12, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open paired evidence for game ${row.game}`});
    addTooltip(hit, [`Game ${row.game} · Oasis versus ${result.rivalTeam}`, `Income edge ${signed(row.incomeEdge)} · cost edge ${signed(row.costEdge)}`, `Round score gap ${signed(row.gap)} · cumulative ${signed(row.cumulativeGap)}`, `Oasis net ${signed(row.oasis.net)} · rival net ${signed(row.rival.net)}`, `Official reconciliation ${row.reconciliationDelta === null ? "unavailable" : signed(row.reconciliationDelta)}`]);
    hit.addEventListener("click", () => openRivalGame(row.game)); svg.append(hit);
    if (index % Math.max(1, Math.ceil(rows.length / 13)) === 0 || index === rows.length - 1) svg.append(svgElement("text", {x: x(index), y: height - 20, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.green, "font-size": 8, "font-family": "var(--mono)"}, "BAR = MATCHED ROUND SCORE GAP · POSITIVE HELPS OASIS"));
  svg.append(svgElement("text", {x: margin.left, y: cumulativeTop - 10, fill: colors.violet, "font-size": 8, "font-family": "var(--mono)"}, "LINE = WINDOW-CUMULATIVE GAP · SEPARATE SCALE")); host.append(svg);
  result.decisive.slice(0, 10).forEach((row, index) => {
    const button = element("button", {type: "button", class: "rival-decisive-row"}, [
      element("span", {text: `#${index + 1}`}),
      element("div", {}, [element("strong", {text: `Game ${row.game}`}), element("small", {text: `income ${signed(row.incomeEdge)} · cost ${signed(row.costEdge)}`})]),
      element("strong", {class: row.gap >= 0 ? "positive" : "negative", text: signed(row.gap)}),
    ]);
    button.addEventListener("click", () => openRivalGame(row.game)); decisive.append(button);
  });
}

function renderRivalQuadrant(result) {
  const host = $("#rival-quadrant-chart"); clear(host);
  const rows = result.rows, width = 760, height = 470, margin = {left: 82, right: 42, top: 42, bottom: 62};
  const bound = Math.max(1, ...rows.flatMap(row => [Math.abs(row.incomeEdge), Math.abs(row.costEdge)])) * 1.12;
  const x = value => margin.left + (value + bound) / (2 * bound) * (width - margin.left - margin.right);
  const y = value => margin.top + (bound - value) / (2 * bound) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, `Matched games by Oasis income and reviewer-cost edge to ${result.rivalTeam}`);
  [-1, -.5, 0, .5, 1].forEach(portion => {
    const value = bound * portion;
    svg.append(svgElement("line", {x1: x(value), y1: margin.top, x2: x(value), y2: height - margin.bottom, class: portion === 0 ? "axis-line" : "grid-line"}));
    svg.append(svgElement("line", {x1: margin.left, y1: y(value), x2: width - margin.right, y2: y(value), class: portion === 0 ? "axis-line" : "grid-line"}));
    svg.append(svgElement("text", {x: x(value), y: height - 35, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true)));
  });
  svg.append(svgElement("line", {x1: x(-bound), y1: y(bound), x2: x(bound), y2: y(-bound), stroke: colors.amber, "stroke-width": 1.2, "stroke-dasharray": "5 5", "stroke-opacity": .75}));
  const maxFlow = Math.max(1, ...rows.map(row => row.grossObservedFlow));
  rows.forEach(row => {
    const xx = x(row.incomeEdge), yy = y(row.costEdge), radius = clamp(3 + Math.sqrt(row.grossObservedFlow / maxFlow) * 8, 4, 11);
    let marker;
    const markerAttributes = {fill: row.gap > 0 ? colors.green : row.gap < 0 ? colors.red : colors.amber, "fill-opacity": .7, tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game}: Oasis score edge ${signed(row.gap)}, income edge ${signed(row.incomeEdge)}, cost edge ${signed(row.costEdge)}`};
    if (row.gap > 0) marker = svgElement("path", {...markerAttributes, d: `M${xx},${yy - radius} L${xx + radius},${yy + radius * .8} L${xx - radius},${yy + radius * .8} Z`});
    else if (row.gap < 0) marker = svgElement("path", {...markerAttributes, d: `M${xx},${yy - radius} L${xx + radius},${yy} L${xx},${yy + radius} L${xx - radius},${yy} Z`});
    else marker = svgElement("circle", {...markerAttributes, cx: xx, cy: yy, r: radius});
    addTooltip(marker, [`Game ${row.game} · ${row.gap >= 0 ? "Oasis ahead" : "rival ahead"}`, `Income edge ${signed(row.incomeEdge)} · cost edge ${signed(row.costEdge)}`, `Score gap ${signed(row.gap)} = x + y`, `Gross observed four-flow denominator ${formatCurrency(row.grossObservedFlow)}`]);
    marker.addEventListener("click", () => openRivalGame(row.game));
    marker.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openRivalGame(row.game); }
    });
    svg.append(marker);
  });
  svg.append(svgElement("text", {x: width - margin.right, y: height - 14, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)", "text-anchor": "end"}, "INCOME EDGE → OASIS MINUS RIVAL"));
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.green, "font-size": 8, "font-family": "var(--mono)"}, "UP = LOWER OASIS REVIEW COST · RIGHT = HIGHER OASIS INCOME · AMBER DIAGONAL = SCORE PARITY")); host.append(svg);
}

function rivalEfficiencyRows(result) {
  return [
    {label: "Income / issued decision", denominator: `${result.oasis.issuedDecisions} / ${result.rival.issuedDecisions} issuer decisions`, oasis: result.oasis.incomePerIssuedDecision, rival: result.rival.incomePerIssuedDecision, unit: "eur", direction: "high"},
    {label: "Review cost / decision", denominator: `${result.oasis.reviewedDecisions} / ${result.rival.reviewedDecisions} reviewer decisions`, oasis: result.oasis.costPerReviewedDecision, rival: result.rival.costPerReviewedDecision, unit: "eur", direction: "low"},
    {label: "Wrong cost / decision", denominator: `${result.oasis.reviewedDecisions} / ${result.rival.reviewedDecisions} reviewer decisions`, oasis: result.oasis.wrongCostPerReviewedDecision, rival: result.rival.wrongCostPerReviewedDecision, unit: "eur", direction: "low"},
    {label: "Market accepts issued", denominator: `${result.oasis.issuedDecisions} / ${result.rival.issuedDecisions} issuer decisions`, oasis: result.oasis.marketAcceptRate, rival: result.rival.marketAcceptRate, unit: "share", direction: "neutral"},
    {label: "Reviewer acceptance", denominator: `${result.oasis.reviewedDecisions} / ${result.rival.reviewedDecisions} reviewer decisions`, oasis: result.oasis.reviewerAcceptRate, rival: result.rival.reviewerAcceptRate, unit: "share", direction: "neutral"},
    {label: "Positive-round rate", denominator: `${result.summary.games} paired games each`, oasis: result.oasis.positiveRoundRate, rival: result.rival.positiveRoundRate, unit: "share", direction: "high"},
    {label: "Median round", denominator: `${result.summary.games} paired games each`, oasis: result.oasis.medianRound, rival: result.rival.medianRound, unit: "eur", direction: "high"},
    {label: "Mean round", denominator: `${result.summary.games} paired games each`, oasis: result.oasis.meanRound, rival: result.rival.meanRound, unit: "eur", direction: "high"},
    {label: "Round volatility", denominator: `${result.summary.games} paired games each · population σ`, oasis: result.oasis.roundVolatility, rival: result.rival.roundVolatility, unit: "eur", direction: "neutral"},
  ];
}

function rivalMetricValue(value, unit) { return unit === "share" ? formatPercent(value) : formatCurrency(value); }

function renderRivalEfficiency(result) {
  const host = $("#rival-efficiency"); clear(host);
  rivalEfficiencyRows(result).forEach(row => {
    const min = Math.min(0, safeNumber(row.oasis), safeNumber(row.rival)), max = Math.max(0, safeNumber(row.oasis), safeNumber(row.rival));
    const position = value => (safeNumber(value) - min) / (max - min || 1) * 100;
    const delta = safeNumber(row.oasis) - safeNumber(row.rival);
    const favourable = row.direction === "neutral" ? null : row.direction === "high" ? delta >= 0 : delta <= 0;
    host.append(element("div", {class: "rival-efficiency-row"}, [
      element("div", {class: "rival-efficiency-label"}, [element("strong", {text: row.label}), element("small", {text: row.denominator})]),
      element("div", {class: "rival-efficiency-track"}, [element("i", {style: `left:${Math.min(position(row.oasis), position(row.rival))}%;width:${Math.abs(position(row.oasis) - position(row.rival))}%`}), element("b", {class: "oasis", style: `left:${position(row.oasis)}%`, title: "Oasis"}), element("b", {class: "rival", style: `left:${position(row.rival)}%`, title: result.rivalTeam})]),
      element("div", {class: "rival-efficiency-values"}, [element("span", {text: `O ${rivalMetricValue(row.oasis, row.unit)}`}), element("span", {text: `R ${rivalMetricValue(row.rival, row.unit)}`}), element("strong", {class: favourable === null ? "" : favourable ? "positive" : "negative", text: `Δ ${row.unit === "share" ? `${delta >= 0 ? "+" : "−"}${formatPercent(Math.abs(delta))}` : signed(delta)}`})]),
    ]));
  });
}

function renderRivalTables(result) {
  const decomposition = $("#rival-decomposition-table"); clear(decomposition);
  const decompositionRows = [
    ["Issuer income", result.oasis.issuedIncome, result.rival.issuedIncome, result.summary.incomeEdge, "Oasis − rival"],
    ["Reviewer cost", result.oasis.reviewerCost, result.rival.reviewerCost, result.summary.costEdge, "rival − Oasis"],
    ["Net score", result.oasis.net, result.rival.net, result.summary.scoreGap, "income edge + cost edge"],
  ];
  decompositionRows.forEach(row => decomposition.append(element("tr", {}, [element("td", {text: row[0]}), element("td", {class: "money", text: formatCurrency(row[1])}), element("td", {class: "money", text: formatCurrency(row[2])}), element("td", {class: `money ${row[3] >= 0 ? "positive" : "negative"}`, text: signed(row[3])}), element("td", {text: row[4]})])));
  const efficiency = $("#rival-efficiency-table"); clear(efficiency);
  rivalEfficiencyRows(result).forEach(row => {
    const delta = safeNumber(row.oasis) - safeNumber(row.rival);
    efficiency.append(element("tr", {}, [element("td", {text: row.label}), element("td", {text: row.denominator}), element("td", {text: rivalMetricValue(row.oasis, row.unit)}), element("td", {text: rivalMetricValue(row.rival, row.unit)}), element("td", {text: row.unit === "share" ? `${delta >= 0 ? "+" : "−"}${formatPercent(Math.abs(delta))}` : signed(delta)}), element("td", {text: row.direction})]));
  });
  const rounds = $("#rival-round-table"); clear(rounds);
  result.rows.forEach(row => rounds.append(element("tr", {}, [
    element("td", {}, [itemLink(row.game, null, `Game ${row.game}`)]),
    element("td", {class: "money", text: formatCurrency(row.oasis.income)}), element("td", {class: "money", text: formatCurrency(row.rival.income)}), element("td", {class: "money", text: signed(row.incomeEdge)}),
    element("td", {class: "money", text: formatCurrency(row.oasis.cost)}), element("td", {class: "money", text: formatCurrency(row.rival.cost)}), element("td", {class: "money", text: signed(row.costEdge)}),
    element("td", {class: `money ${row.gap >= 0 ? "positive" : "negative"}`, text: signed(row.gap)}), element("td", {class: "money", text: signed(row.cumulativeGap)}),
    element("td", {class: "money", text: row.officialGap === null ? "unavailable" : signed(row.officialGap)}), element("td", {class: "money", text: row.reconciliationDelta === null ? "unavailable" : signed(row.reconciliationDelta)}),
  ])));
}

function renderRivalBenchmark() {
  if (!state.market || !state.rivalTeam) return;
  try {
    const result = buildRivalBenchmark(state.market, state.marketFramesByGame, state.rivalTeam, state.rivalWindow);
    state.rivalResult = result;
    $("#rival-empty").hidden = true; $("#rival-workspace").hidden = false;
    $("#rival-status").textContent = `${result.summary.games} PAIRED GAMES · OASIS #${result.summary.oasisRank} VS ${result.rivalTeam.toUpperCase()} #${result.summary.rivalRank}`;
    renderRivalNarrative(result); renderRivalKpis(result); renderRivalBridge(result);
    renderRivalBootstrap(result); renderRivalGap(result); renderRivalQuadrant(result);
    renderRivalEfficiency(result); renderRivalTables(result);
  } catch (error) {
    state.rivalResult = null; $("#rival-workspace").hidden = true; $("#rival-empty").hidden = false;
    $("#rival-status").textContent = "PAIRED EVIDENCE UNAVAILABLE";
    $("#rival-empty p").textContent = `Rival benchmark unavailable: ${error.message}`;
  }
}

async function copyRivalReceipt() {
  if (!state.rivalResult || !state.market) { toast("Paired rival evidence is unavailable to copy."); return; }
  try {
    await navigator.clipboard.writeText(JSON.stringify(buildRivalReceipt(state.rivalResult, state.market.generatedAt), null, 2));
    toast("Claim-free paired rival receipt copied.");
  } catch (error) { toast(`Rival benchmark receipt could not be copied: ${error.message}`); }
}

async function loadMarket() {
  $("#market-empty").hidden = false; $("#market-workspace").hidden = true;
  try {
    const previousGames = state.market?.gameIds || [];
    const wasAtLatest = Boolean(previousGames.length) && state.marketReplayIndex >= previousGames.length - 1;
    const requestedGame = state.marketReplayGame;
    const payload = await api("/api/market", {timeout: 30000, retries: 0});
    if (payload.schemaVersion !== 2 || !Array.isArray(payload.gameIds) || !payload.gameIds.length ||
        !Array.isArray(payload.teams) || !Array.isArray(payload.edges) ||
        !Array.isArray(payload.summaries) || !Array.isArray(payload.timeline)) throw new Error("market evidence schema mismatch");
    const framesByGame = decodeMarketFrames(payload);
    stopMarketReplay();
    state.market = payload;
    state.marketFramesByGame = framesByGame;
    state.marketViewCache.clear();
    const requestedIndex = payload.gameIds.indexOf(requestedGame);
    state.marketReplayIndex = wasAtLatest || requestedIndex < 0
      ? payload.gameIds.length - 1 : requestedIndex;
    state.marketReplayGame = payload.gameIds[state.marketReplayIndex];
    populateMarketControls();
    populateRivalControls();
    $("#market-empty").hidden = true; $("#market-workspace").hidden = false; renderMarket(); renderRivalBenchmark();
  } catch (error) {
    stopMarketReplay(); state.market = null; state.marketFramesByGame = new Map(); state.marketViewCache.clear();
    $("#market-status").textContent = "MARKET EVIDENCE UNAVAILABLE";
    $("#market-empty p").textContent = `Market microstructure unavailable: ${error.message}`;
    state.rivalResult = null; $("#rival-workspace").hidden = true; $("#rival-empty").hidden = false;
    $("#rival-status").textContent = "PAIRED EVIDENCE UNAVAILABLE";
    $("#rival-empty p").textContent = `Rival benchmark unavailable: ${error.message}`;
  }
}

async function copyMarketReceipt() {
  const summary = selectedMarketSummary();
  if (!state.market || !summary) { toast("Market evidence is not available to copy."); return; }
  const view = currentMarketView();
  const receipt = {
    version: 2, status: "offline-observed-market-accounting-only",
    materializedAt: state.market.generatedAt, selectedTeam: state.marketTeam,
    selectedCounterparty: state.marketPeer, matrixLens: state.marketMode,
    replay: {mode: state.marketReplayMode, throughGame: view.game, includedGames: view.frameCount},
    denominator: {teams: state.market.teams.length, directedEdges: view.edges.length, includedGames: view.frameCount, availableGames: state.market.gameIds.length, decisions: view.decisions},
    selectedTeamSummary: {...summary},
    bilateral: marketCounterparties().map(row => ({
      team: row.team, issuerIncomeFromTeam: row.incomeFrom,
      reviewerCostToTeam: row.costTo, bilateralNet: row.net,
      marketAcceptRate: row.acceptsUs, reviewerAcceptRate: row.weAccept,
      wrongCostBySelectedTeam: row.wrongByUs,
      hiddenRejectedFraudAgainstSelectedTeam: row.hiddenAgainstUs,
    })),
    boundaries: [
      "observed settlement accounting, not causal exploitation or counterfactual tournament impact",
      "issuer income and reviewer cost are separate payoff quantities and need not be zero-sum",
      "rejected fraudulent attempted amounts are invisible, so wrong-cost and flow views are lower bounds",
      "charge aggression excludes hidden charges and always reports its observation coverage",
      "the replay changes the observed temporal denominator; it does not simulate alternate decisions",
      "no charge, limit, rule, model, process, or submission is modified",
    ],
  };
  try {
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    toast("Claim-free market receipt copied with reconciliation and observability boundaries.");
  } catch (error) { toast(`Market receipt could not be copied: ${error.message}`); }
}

function valueBucket(floor) {
  if (!Number.isFinite(Number(floor))) return null;
  if (floor < 50) return "0–50";
  if (floor < 400) return "50–400";
  if (floor < 1200) return "400–1200";
  return "1200+";
}

function isNotProvenWrong(row) {
  return row.status === "inside-bracket" || row.status === "above-floor-open-ceiling";
}

function evaluateReviewerPolicy(cells, options = {}) {
  const shifts = {"0–50": 0, "50–400": 0, "400–1200": 0, "1200+": 0, ...(options.shifts || {})};
  const latestGame = Math.max(0, ...cells.map(row => safeNumber(row.game)));
  const windowStart = options.window === "last-10" ? latestGame - 9
    : options.window === "last-20" ? latestGame - 19 : 0;
  const selected = cells.filter(row => {
    if (safeNumber(row.game) < windowStart) return false;
    if (options.window === "logged-era" && row.b === null) return false;
    if (options.opponent && options.opponent !== "all" && row.opponent !== options.opponent) return false;
    const source = row.source || "__unlogged__";
    if (options.source && options.source !== "all" && source !== options.source) return false;
    const proven = ["fair", "fraud"].includes(row.provenClass) ? row.provenClass : "unproven";
    return !options.provenClass || options.provenClass === "all" || proven === options.provenClass;
  });
  const bucketNames = ["0–50", "50–400", "400–1200", "1200+"];
  const buckets = Object.fromEntries(bucketNames.map(bucket => [bucket, {
    bucket, shift: safeNumber(shifts[bucket]), cells: 0, observedCost: 0,
    pricedCells: 0, pricedBaselineCost: 0, pricedCandidateCost: 0, pricedDelta: 0,
    fairSwitches: 0, fraudSwitches: 0, hiddenExposures: 0, unpricedChanged: 0,
  }]));
  const matrix = Object.fromEntries(["acceptFair", "rejectFair", "acceptFraud", "rejectFraud", "unproven"].map(key => [key, {key, count: 0, cost: 0}]));
  const gameMap = new Map();
  const transitions = [];
  const margins = [];
  const totals = {
    cells: selected.length, observedCost: 0, pricedCells: 0,
    pricedBaselineCost: 0, pricedCandidateCost: 0, pricedDelta: 0,
    fairDelta: 0, fraudDelta: 0, fairSwitches: 0, fraudSwitches: 0,
    hiddenExposures: 0, unpricedChanged: 0, missingLimits: 0,
    unlabelledBucketCells: 0,
  };
  selected.forEach(row => {
    const bucket = buckets[row.valueBucket];
    const shift = bucket ? bucket.shift : 0;
    const actualCost = safeNumber(row.actualCost);
    const game = safeNumber(row.game);
    const gameRow = gameMap.get(game) || {
      game, cells: 0, pricedCells: 0, pricedDelta: 0, fairSwitches: 0,
      fraudSwitches: 0, hiddenExposures: 0, unpricedChanged: 0,
    };
    gameRow.cells += 1;
    totals.observedCost += actualCost;
    if (bucket) {
      bucket.cells += 1;
      bucket.observedCost += actualCost;
    } else totals.unlabelledBucketCells += 1;
    const matrixKey = row.outcome && matrix[row.outcome] ? row.outcome : "unproven";
    matrix[matrixKey].count += 1;
    matrix[matrixKey].cost += actualCost;
    if (row.b === null) totals.missingLimits += 1;
    const candidateB = row.b === null ? null : Math.max(0, safeNumber(row.b) + shift);
    let priced = false;
    let candidateCost = null;
    let candidateOutcome = null;
    let transitionKind = null;
    let hiddenExposure = false;
    let unpricedChanged = false;
    if (row.fairExactEligible && candidateB !== null && row.charge !== null) {
      const candidateAccepted = safeNumber(row.charge) <= candidateB;
      candidateCost = candidateAccepted === row.actualAccepted
        ? actualCost
        : candidateAccepted ? safeNumber(row.charge) : 1.5 * safeNumber(row.charge);
      candidateOutcome = `${candidateAccepted ? "accept" : "reject"}Fair`;
      priced = true;
      if (candidateAccepted !== row.actualAccepted) transitionKind = "fair-switch";
    } else if (row.fraudDownshiftEligible && candidateB !== null && row.charge !== null) {
      if (shift === 0) {
        candidateCost = actualCost;
        candidateOutcome = "acceptFraud";
        priced = true;
      } else if (candidateB < safeNumber(row.charge)) {
        candidateCost = 0;
        candidateOutcome = "rejectFraud";
        priced = true;
        transitionKind = "fraud-switch";
      } else {
        unpricedChanged = true;
        candidateOutcome = "unresolvedFraud";
        transitionKind = "lower-bound-uncertainty";
      }
    } else if (row.hiddenFraudEligible && candidateB !== null && shift > 0 &&
               candidateB > safeNumber(row.tLo)) {
      hiddenExposure = true;
      candidateOutcome = "hiddenExposure";
      transitionKind = "hidden-exposure";
    } else if (shift !== 0 && row.b !== null && row.provenClass !== "unproven" &&
               row.provenClass !== "conflict") {
      unpricedChanged = true;
      candidateOutcome = "unpriced";
      transitionKind = "evidence-insufficient";
    }
    if (priced) {
      const delta = candidateCost - actualCost;
      totals.pricedCells += 1;
      totals.pricedBaselineCost += actualCost;
      totals.pricedCandidateCost += candidateCost;
      totals.pricedDelta += delta;
      gameRow.pricedCells += 1;
      gameRow.pricedDelta += delta;
      if (bucket) {
        bucket.pricedCells += 1;
        bucket.pricedBaselineCost += actualCost;
        bucket.pricedCandidateCost += candidateCost;
        bucket.pricedDelta += delta;
      }
      if (transitionKind === "fair-switch") {
        totals.fairSwitches += 1; totals.fairDelta += delta; gameRow.fairSwitches += 1;
        if (bucket) bucket.fairSwitches += 1;
      } else if (transitionKind === "fraud-switch") {
        totals.fraudSwitches += 1; totals.fraudDelta += delta; gameRow.fraudSwitches += 1;
        if (bucket) bucket.fraudSwitches += 1;
      }
    }
    if (hiddenExposure) {
      totals.hiddenExposures += 1; gameRow.hiddenExposures += 1;
      if (bucket) bucket.hiddenExposures += 1;
    }
    if (unpricedChanged) {
      totals.unpricedChanged += 1; gameRow.unpricedChanged += 1;
      if (bucket) bucket.unpricedChanged += 1;
    }
    if (transitionKind) transitions.push({
      ...row, shift, candidateB, candidateCost,
      candidateOutcome, transitionKind,
      pricedDelta: priced ? candidateCost - actualCost : null,
    });
    if (row.b !== null && row.charge !== null && row.tLo > 0 &&
        (row.fairExactEligible || row.chargeKind === "lower_bound")) {
      margins.push({
        game: row.game, item: row.item, opponent: row.opponent,
        provenClass: row.provenClass,
        kind: row.fairExactEligible ? "exact" : "upper-bound",
        margin: (safeNumber(row.b) - safeNumber(row.charge)) / safeNumber(row.tLo),
        candidateMargin: (candidateB - safeNumber(row.charge)) / safeNumber(row.tLo),
      });
    }
    gameMap.set(game, gameRow);
  });
  const roundMoney = row => {
    ["observedCost", "pricedBaselineCost", "pricedCandidateCost", "pricedDelta"].forEach(key => {
      if (key in row) row[key] = Math.round(safeNumber(row[key]) * 100) / 100;
    });
    return row;
  };
  roundMoney(totals);
  totals.fairDelta = Math.round(totals.fairDelta * 100) / 100;
  totals.fraudDelta = Math.round(totals.fraudDelta * 100) / 100;
  Object.values(matrix).forEach(roundMoney);
  const bucketRows = Object.values(buckets).map(roundMoney);
  const games = [...gameMap.values()].sort((a, b) => a.game - b.game).map(roundMoney);
  transitions.sort((left, right) => {
    const leftSeverity = Math.abs(safeNumber(left.pricedDelta)) + (left.transitionKind === "hidden-exposure" ? 1e9 : 0);
    const rightSeverity = Math.abs(safeNumber(right.pricedDelta)) + (right.transitionKind === "hidden-exposure" ? 1e9 : 0);
    return rightSeverity - leftSeverity || right.game - left.game || right.item - left.item;
  });
  return {selected, totals, matrix, buckets: bucketRows, games, transitions, margins, latestGame};
}

function reviewerPolicySweep(cells, options = {}) {
  const specs = {
    "0–50": [-100, -75, -50, -25, 0, 25, 50, 75, 100],
    "50–400": [-400, -300, -200, -100, 0, 100, 200, 300, 400],
    "400–1200": [-1200, -900, -600, -300, 0, 300, 600, 900, 1200],
    "1200+": [-5000, -3750, -2500, -1250, 0, 2500, 5000, 7500, 10000],
  };
  return Object.entries(specs).map(([bucket, basePoints]) => {
    const selectedShift = safeNumber(options.shifts?.[bucket]);
    const points = [...new Set([...basePoints, selectedShift])].sort((a, b) => a - b);
    return {
      bucket, selectedShift,
      points: points.map(shift => {
        const evaluated = evaluateReviewerPolicy(cells, {
          ...options,
          shifts: {"0–50": 0, "50–400": 0, "400–1200": 0, "1200+": 0, [bucket]: shift},
        });
        const row = evaluated.buckets.find(candidate => candidate.bucket === bucket);
        return {
          shift, cells: row?.cells || 0, pricedCells: row?.pricedCells || 0,
          pricedDelta: row?.pricedDelta || 0,
          fairSwitches: row?.fairSwitches || 0, fraudSwitches: row?.fraudSwitches || 0,
          hiddenExposures: row?.hiddenExposures || 0,
          unpricedChanged: row?.unpricedChanged || 0,
        };
      }),
    };
  });
}

function cohortGameIds(allGameIds, window) {
  const games = [...new Set((allGameIds || []).map(Number).filter(Number.isFinite))].sort((a, b) => a - b);
  if (window === "last-10") return games.slice(-10);
  if (window === "previous-10") return games.slice(-20, -10);
  if (window === "first-half") return games.slice(0, Math.ceil(games.length / 2));
  if (window === "second-half") return games.slice(Math.ceil(games.length / 2));
  return games;
}

function cohortItemMatches(row, spec, gameSet) {
  if (!gameSet.has(Number(row.game))) return false;
  const source = row.source || "__unlogged__";
  if (spec.source !== "all" && source !== spec.source) return false;
  const bucket = valueBucket(row.tLo) || "unlabelled";
  if (spec.bucket !== "all" && bucket !== spec.bucket) return false;
  if (spec.status === "under" && row.status !== "under") return false;
  if (spec.status === "over" && row.status !== "over") return false;
  if (spec.status === "not-proven-wrong" && !isNotProvenWrong(row)) return false;
  if (spec.status === "open" && row.status !== "above-floor-open-ceiling") return false;
  if (spec.status === "unlabelled" && row.status !== "unlabelled") return false;
  return true;
}

function emptyCohortContribution(game) {
  return {
    game, items: 0, decidedItems: 0, labelledItems: 0, bestPossible: 0,
    provenIncome: 0, excludedItems: 0, underItems: 0, overItems: 0,
    foregoneLowerBound: 0, logErrors: [], reviewerCells: 0, provenReviewerCells: 0,
    reviewerCost: 0, rejectFairCount: 0, rejectFairCost: 0,
    acceptFairCount: 0, acceptFraudCount: 0, acceptFraudCost: 0,
    rejectFraudCount: 0,
  };
}

function aggregateCohortContributions(rows) {
  const total = emptyCohortContribution(null);
  rows.forEach(row => {
    Object.keys(total).forEach(key => {
      if (key === "game" || key === "logErrors") return;
      total[key] += safeNumber(row[key]);
    });
    total.logErrors.push(...(row.logErrors || []));
  });
  const fairCells = total.acceptFairCount + total.rejectFairCount;
  const fraudCells = total.acceptFraudCount + total.rejectFraudCount;
  return {
    ...total,
    gameCount: rows.length,
    score: total.bestPossible > 0 ? total.provenIncome / total.bestPossible : null,
    underRate: total.labelledItems ? total.underItems / total.labelledItems : null,
    overRate: total.labelledItems ? total.overItems / total.labelledItems : null,
    excludedRate: total.labelledItems ? total.excludedItems / total.labelledItems : null,
    foregonePerLabelledItem: total.labelledItems ? total.foregoneLowerBound / total.labelledItems : null,
    medianLogError: numericQuantile(total.logErrors, .5),
    wrongReviewerCost: total.rejectFairCost + total.acceptFraudCost,
    wrongCostPerProvenReview: total.provenReviewerCells
      ? (total.rejectFairCost + total.acceptFraudCost) / total.provenReviewerCells : null,
    fairRejectRate: fairCells ? total.rejectFairCount / fairCells : null,
    fraudAcceptRate: fraudCells ? total.acceptFraudCount / fraudCells : null,
  };
}

function evaluateCohort(itemIndex, reviewerCells, spec, allGameIds) {
  const gameIds = cohortGameIds(allGameIds, spec.window);
  const gameSet = new Set(gameIds);
  const contributions = new Map(gameIds.map(game => [game, emptyCohortContribution(game)]));
  const items = (itemIndex || []).filter(row => cohortItemMatches(row, spec, gameSet));
  const itemKeys = new Set(items.map(row => `${row.game}:${row.item}`));
  items.forEach(row => {
    const target = contributions.get(Number(row.game));
    if (!target) return;
    target.items += 1;
    target.decidedItems += Number(row.a !== null);
    if (row.tLo === null || row.a === null) return;
    const floor = safeNumber(row.tLo), charge = safeNumber(row.a);
    target.labelledItems += 1;
    target.bestPossible += 16 * floor;
    if (charge <= floor) target.provenIncome += 16 * charge;
    else if (!(row.tHi !== null && charge > safeNumber(row.tHi))) target.excludedItems += 1;
    if (charge < floor) {
      target.underItems += 1;
      target.foregoneLowerBound += 16 * (floor - charge);
    } else if (row.tHi !== null && charge > safeNumber(row.tHi)) target.overItems += 1;
    if (floor > 0 && charge > 0) target.logErrors.push(Math.log(charge / floor));
  });
  const reviews = (reviewerCells || []).filter(row => itemKeys.has(`${row.game}:${row.item}`));
  reviews.forEach(row => {
    const target = contributions.get(Number(row.game));
    if (!target) return;
    target.reviewerCells += 1;
    target.reviewerCost += safeNumber(row.actualCost);
    if (["fair", "fraud"].includes(row.provenClass)) target.provenReviewerCells += 1;
    if (row.outcome === "acceptFair") target.acceptFairCount += 1;
    else if (row.outcome === "rejectFair") {
      target.rejectFairCount += 1; target.rejectFairCost += safeNumber(row.actualCost);
    } else if (row.outcome === "acceptFraud") {
      target.acceptFraudCount += 1; target.acceptFraudCost += safeNumber(row.actualCost);
    } else if (row.outcome === "rejectFraud") target.rejectFraudCount += 1;
  });
  const contributionRows = [...contributions.values()];
  return {
    spec: {...spec}, gameIds, items, reviews, itemKeys,
    contributions: contributionRows,
    metrics: aggregateCohortContributions(contributionRows),
  };
}

function bootstrapCohortComparison(cohortA, cohortB, options = {}) {
  const runs = clamp(Math.trunc(Number(options.runs) || 5000), 200, 20000);
  const seed = clamp(Math.trunc(Number(options.seed) || 1), 1, 2147483646);
  const rng = seededGenerator(seed);
  const paired = cohortA.gameIds.length === cohortB.gameIds.length &&
    cohortA.gameIds.every((game, index) => game === cohortB.gameIds[index]);
  const descriptors = [
    {key: "score", label: "Valuation SCORE", unit: "rate", direction: "higher"},
    {key: "underRate", label: "Provably-under rate", unit: "rate", direction: "lower"},
    {key: "overRate", label: "Provably-over rate", unit: "rate", direction: "lower"},
    {key: "foregonePerLabelledItem", label: "Foregone lower bound / item", unit: "EUR/item", direction: "lower"},
    {key: "wrongCostPerProvenReview", label: "Wrong-decision cost / proven review", unit: "EUR/cell", direction: "lower"},
    {key: "fairRejectRate", label: "Fair rejection rate", unit: "rate", direction: "lower"},
    {key: "fraudAcceptRate", label: "Fraud acceptance rate", unit: "rate", direction: "lower"},
  ];
  const draws = Object.fromEntries(descriptors.map(row => [row.key, []]));
  const sampleRows = rows => rows.length
    ? Array.from({length: rows.length}, () => rows[Math.min(rows.length - 1, Math.floor(rng() * rows.length))])
    : [];
  for (let run = 0; run < runs; run++) {
    let sampleA, sampleB;
    if (paired) {
      const indexes = Array.from({length: cohortA.contributions.length}, () => Math.min(cohortA.contributions.length - 1, Math.floor(rng() * cohortA.contributions.length)));
      sampleA = indexes.map(index => cohortA.contributions[index]);
      sampleB = indexes.map(index => cohortB.contributions[index]);
    } else {
      sampleA = sampleRows(cohortA.contributions);
      sampleB = sampleRows(cohortB.contributions);
    }
    const metricsA = aggregateCohortContributions(sampleA);
    const metricsB = aggregateCohortContributions(sampleB);
    descriptors.forEach(({key}) => {
      const left = metricsA[key], right = metricsB[key];
      if (Number.isFinite(left) && Number.isFinite(right)) draws[key].push(right - left);
    });
  }
  const results = descriptors.map(descriptor => {
    const values = draws[descriptor.key];
    const observedA = cohortA.metrics[descriptor.key], observedB = cohortB.metrics[descriptor.key];
    const observedDelta = Number.isFinite(observedA) && Number.isFinite(observedB) ? observedB - observedA : null;
    const better = values.filter(value => descriptor.direction === "higher" ? value > 0 : value < 0).length;
    const worse = values.filter(value => descriptor.direction === "higher" ? value < 0 : value > 0).length;
    return {
      ...descriptor, observedA, observedB, observedDelta,
      draws: values.length, p025: numericQuantile(values, .025),
      p50: numericQuantile(values, .5), p975: numericQuantile(values, .975),
      probabilityBetter: values.length ? better / values.length : null,
      probabilityWorse: values.length ? worse / values.length : null,
      intervalExcludesZero: values.length ? numericQuantile(values, .025) > 0 || numericQuantile(values, .975) < 0 : false,
    };
  });
  return {runs, seed, paired, results, scoreDraws: draws.score};
}

function cohortOverlap(cohortA, cohortB, universe) {
  const a = cohortA.itemKeys, b = cohortB.itemKeys;
  let both = 0, aOnly = 0, bOnly = 0, neither = 0;
  (universe || []).forEach(row => {
    const key = `${row.game}:${row.item}`;
    if (a.has(key) && b.has(key)) both += 1;
    else if (a.has(key)) aOnly += 1;
    else if (b.has(key)) bOnly += 1;
    else neither += 1;
  });
  return {both, aOnly, bOnly, neither, universe: both + aOnly + bOnly + neither};
}

function reviewerOutcomeLabel(value) {
  return ({
    acceptFair: "accepted fair", rejectFair: "rejected fair",
    acceptFraud: "accepted fraud", rejectFraud: "rejected fraud",
    unresolvedFraud: "fraud outcome unresolved", hiddenExposure: "potential hidden exposure",
    unpriced: "unpriced", unproven: "unproven",
  })[value] || String(value || "unresolved").replaceAll("-", " ");
}

function reviewerPolicyOptions() {
  return {
    window: state.reviewerWindow, opponent: state.reviewerOpponent,
    source: state.reviewerSource, provenClass: state.reviewerClass,
    shifts: state.reviewerShifts,
  };
}

function populateReviewerControls() {
  if (!state.reviewerLab) return;
  const cells = state.reviewerLab.cells || [];
  const opponent = $("#reviewer-opponent"); clear(opponent);
  opponent.append(element("option", {value: "all", text: "All opponents"}));
  [...new Set(cells.map(row => row.opponent))].sort((a, b) => a.localeCompare(b)).forEach(name => {
    opponent.append(element("option", {value: name, text: name}));
  });
  if (![...opponent.options].some(row => row.value === state.reviewerOpponent)) state.reviewerOpponent = "all";
  opponent.value = state.reviewerOpponent;
  const source = $("#reviewer-source"); clear(source);
  source.append(element("option", {value: "all", text: "All sources"}));
  const sources = [...new Set(cells.map(row => row.source || "__unlogged__"))].sort((a, b) => a.localeCompare(b));
  sources.forEach(name => source.append(element("option", {value: name, text: name === "__unlogged__" ? "No logged belief source" : name})));
  if (![...source.options].some(row => row.value === state.reviewerSource)) state.reviewerSource = "all";
  source.value = state.reviewerSource;
  $("#reviewer-window").value = state.reviewerWindow;
  $$('[data-reviewer-class]').forEach(button => {
    const active = button.dataset.reviewerClass === state.reviewerClass;
    button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
  });
  const inputs = {
    "0–50": ["#reviewer-shift-cheap", "#reviewer-shift-cheap-output"],
    "50–400": ["#reviewer-shift-low", "#reviewer-shift-low-output"],
    "400–1200": ["#reviewer-shift-mid", "#reviewer-shift-mid-output"],
    "1200+": ["#reviewer-shift-high", "#reviewer-shift-high-output"],
  };
  Object.entries(inputs).forEach(([bucket, [input, output]]) => {
    $(input).value = String(state.reviewerShifts[bucket]);
    $(output).textContent = signed(state.reviewerShifts[bucket]);
  });
}

function renderReviewerKpis(result) {
  const host = $("#reviewer-kpis"); clear(host);
  const totals = result.totals;
  const specs = [
    ["Selected decisions", formatNumber(totals.cells), "one Oasis review × opponent charge group", ""],
    ["Observed reviewer cost", formatCurrency(totals.observedCost, true), "selected cells · rejected hidden fraud remains €0", ""],
    ["Priced policy Δ", signed(totals.pricedDelta), `${formatNumber(totals.pricedCells)} paired cells with known candidate cost`, totals.pricedDelta <= 0 ? "positive" : "negative"],
    ["Fair switches", formatNumber(totals.fairSwitches), `${signed(totals.fairDelta)} known cost Δ`, totals.fairDelta <= 0 ? "positive" : "negative"],
    ["Fraud switches", formatNumber(totals.fraudSwitches), `${signed(totals.fraudDelta)} known cost Δ · payout lower-bound crossed`, totals.fraudDelta <= 0 ? "positive" : "negative"],
    ["Potential hidden exposure", formatNumber(totals.hiddenExposures), "unpriced rejected-fraud groups · candidate b above floor", "warning"],
    ["Unpriced changed cells", formatNumber(totals.unpricedChanged), `${formatNumber(totals.missingLimits)} selected cells lack logged b`, "warning"],
  ];
  specs.forEach(([label, value, note, tone]) => host.append(metricCard(label, value, note, tone)));
}

function renderReviewerMatrix(result) {
  const host = $("#reviewer-matrix"); clear(host);
  const table = $("#reviewer-matrix-table"); clear(table);
  const specs = [
    ["acceptFair", "ACCEPT × FAIR", "correct", colors.green],
    ["acceptFraud", "ACCEPT × FRAUD", "wrong acceptance", colors.red],
    ["rejectFair", "REJECT × FAIR", "wrong rejection", colors.red],
    ["rejectFraud", "REJECT × FRAUD", "correct", colors.green],
  ];
  specs.forEach(([key, label, stateLabel, color]) => {
    const row = result.matrix[key];
    const card = element("div", {class: `reviewer-matrix-cell ${key}`}, [
      element("span", {text: label}), element("strong", {text: formatCurrency(row.cost, true)}),
      element("small", {text: `${formatNumber(row.count)} cells · ${stateLabel} · avg ${formatCurrency(row.cost / Math.max(1, row.count), true)}`}),
    ]);
    card.style.setProperty("--matrix-color", color);
    host.append(card);
    table.append(element("tr", {}, [
      element("td", {text: label}), element("td", {text: formatNumber(row.count)}),
      element("td", {class: "money", text: formatCurrency(row.cost)}),
      element("td", {class: "money", text: formatCurrency(row.cost / Math.max(1, row.count))}),
    ]));
  });
  const unproven = result.matrix.unproven;
  host.append(element("div", {class: "reviewer-matrix-unproven"}, [
    element("strong", {text: `${formatNumber(unproven.count)} unproven cells`}),
    element("span", {text: `${formatCurrency(unproven.cost)} observed cost · excluded from fair/fraud matrix`}),
  ]));
  table.append(element("tr", {}, [
    element("td", {text: "UNPROVEN"}), element("td", {text: formatNumber(unproven.count)}),
    element("td", {class: "money", text: formatCurrency(unproven.cost)}),
    element("td", {class: "money", text: formatCurrency(unproven.cost / Math.max(1, unproven.count))}),
  ]));
}

function renderReviewerWaterfall(result) {
  const host = $("#reviewer-waterfall"); clear(host);
  const totals = result.totals;
  const values = [
    {label: "PAIRED BASELINE", start: 0, end: totals.pricedBaselineCost, tone: colors.muted},
    {label: "FAIR SWITCHES", start: totals.pricedBaselineCost, end: totals.pricedBaselineCost + totals.fairDelta, tone: totals.fairDelta <= 0 ? colors.green : colors.red},
    {label: "FRAUD SWITCHES", start: totals.pricedBaselineCost + totals.fairDelta, end: totals.pricedCandidateCost, tone: totals.fraudDelta <= 0 ? colors.green : colors.red},
    {label: "PAIRED CANDIDATE", start: 0, end: totals.pricedCandidateCost, tone: colors.cyan},
  ];
  const all = values.flatMap(row => [row.start, row.end]);
  let min = Math.min(0, ...all), max = Math.max(0, ...all);
  const pad = (max - min || 1) * .12; min -= pad; max += pad;
  const width = 760, height = 390, margin = {left: 78, right: 30, top: 38, bottom: 80};
  const plotW = width - margin.left - margin.right, slot = plotW / values.length;
  const y = value => margin.top + (max - value) / (max - min || 1) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Known paired reviewer-cost waterfall under the selected bucket policy");
  for (let tick = 0; tick <= 4; tick++) {
    const value = min + (max - min) * tick / 4, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true)));
  }
  values.forEach((row, index) => {
    const x = margin.left + slot * index + slot * .18, barW = slot * .64;
    const top = y(Math.max(row.start, row.end)), bottom = y(Math.min(row.start, row.end));
    const rect = svgElement("rect", {x, y: top, width: barW, height: Math.max(2, bottom - top), rx: 4, fill: row.tone, "fill-opacity": .78, tabindex: 0, class: "interactive"});
    const delta = row.end - row.start;
    addTooltip(rect, [row.label, index === 0 || index === 3 ? formatCurrency(row.end) : signed(delta), `${formatNumber(totals.pricedCells)} paired cells · hidden exposure excluded`]);
    svg.append(rect);
    if (index > 0) svg.append(svgElement("line", {x1: margin.left + slot * (index - 1) + slot * .82, y1: y(row.start), x2: x, y2: y(row.start), stroke: colors.muted, "stroke-width": 1, "stroke-dasharray": "3 3"}));
    svg.append(svgElement("text", {x: x + barW / 2, y: height - 42, class: "axis-label", "text-anchor": "middle"}, row.label.split(" ")[0]));
    svg.append(svgElement("text", {x: x + barW / 2, y: height - 29, class: "axis-label", "text-anchor": "middle"}, row.label.split(" ").slice(1).join(" ")));
    svg.append(svgElement("text", {x: x + barW / 2, y: top - 8, fill: row.tone, "font-size": 9, "font-family": "var(--mono)", "text-anchor": "middle"}, index === 0 || index === 3 ? formatCurrency(row.end, true) : signed(delta)));
  });
  host.append(svg);
}

function renderReviewerBuckets(result) {
  const host = $("#reviewer-buckets"); clear(host);
  const table = $("#reviewer-bucket-table"); clear(table);
  result.buckets.forEach(row => {
    const tone = row.pricedDelta < 0 ? "positive" : row.pricedDelta > 0 ? "negative" : "";
    host.append(element("article", {class: "reviewer-bucket-card"}, [
      element("div", {class: "reviewer-bucket-heading"}, [element("span", {text: `T_LO ${row.bucket}`}), element("strong", {text: signed(row.shift)})]),
      element("div", {class: "reviewer-bucket-impact"}, [element("strong", {class: tone, text: signed(row.pricedDelta)}), element("span", {text: "priced reviewer-cost Δ"})]),
      element("dl", {}, [
        element("dt", {text: "Selected"}), element("dd", {text: formatNumber(row.cells)}),
        element("dt", {text: "Paired"}), element("dd", {text: formatNumber(row.pricedCells)}),
        element("dt", {text: "Fair / fraud switches"}), element("dd", {text: `${row.fairSwitches} / ${row.fraudSwitches}`}),
        element("dt", {text: "Potential hidden"}), element("dd", {class: row.hiddenExposures ? "warning" : "", text: formatNumber(row.hiddenExposures)}),
        element("dt", {text: "Unpriced changed"}), element("dd", {text: formatNumber(row.unpricedChanged)}),
      ]),
    ]));
    table.append(element("tr", {}, [
      element("td", {text: row.bucket}), element("td", {text: formatNumber(row.cells)}),
      element("td", {class: "money", text: signed(row.shift)}), element("td", {text: formatNumber(row.pricedCells)}),
      element("td", {class: `money ${tone}`, text: signed(row.pricedDelta)}), element("td", {text: formatNumber(row.hiddenExposures)}),
      element("td", {text: formatNumber(row.unpricedChanged)}),
    ]));
  });
}

function reviewerMarginDistribution(margins) {
  const bins = [
    {label: "<−1", lo: null, hi: -1}, {label: "−1–−0.5", lo: -1, hi: -.5},
    {label: "−0.5–0", lo: -.5, hi: 0}, {label: "0–0.5", lo: 0, hi: .5},
    {label: "0.5–1", lo: .5, hi: 1}, {label: "1–2", lo: 1, hi: 2},
    {label: "2+", lo: 2, hi: null},
  ].map(row => ({...row, fairActual: 0, fairCandidate: 0, fraudActual: 0, fraudCandidate: 0}));
  const add = (value, key) => {
    const bin = bins.find(row => (row.lo === null || value >= row.lo) && (row.hi === null || value < row.hi));
    if (bin) bin[key] += 1;
  };
  margins.forEach(row => {
    const prefix = row.provenClass === "fair" ? "fair" : "fraud";
    add(row.margin, `${prefix}Actual`); add(row.candidateMargin, `${prefix}Candidate`);
  });
  return bins;
}

function renderReviewerMargins(result) {
  const host = $("#reviewer-margin-chart"); clear(host);
  const body = $("#reviewer-margin-table"); clear(body);
  const bins = reviewerMarginDistribution(result.margins);
  const width = 820, height = 390, margin = {left: 58, right: 25, top: 56, bottom: 64};
  const max = Math.max(1, ...bins.flatMap(row => [row.fairActual, row.fairCandidate, row.fraudActual, row.fraudCandidate]));
  const slot = (width - margin.left - margin.right) / bins.length;
  const y = value => margin.top + (max - value) / max * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Actual and candidate decision-margin distributions for exact fair and lower-bound fraud evidence");
  for (let tick = 0; tick <= 4; tick++) {
    const value = max * tick / 4, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatNumber(value)));
  }
  bins.forEach((row, index) => {
    const x = margin.left + index * slot, barW = slot * .18;
    const bars = [
      [row.fairActual, colors.green, .22, 0, "fair actual"], [row.fairCandidate, colors.green, .86, 1, "fair candidate"],
      [row.fraudActual, colors.red, .22, 2.4, "fraud-bound actual"], [row.fraudCandidate, colors.red, .86, 3.4, "fraud-bound candidate"],
    ];
    bars.forEach(([value, color, opacity, offset, label]) => {
      const rect = svgElement("rect", {x: x + slot * .11 + barW * offset, y: y(value), width: barW, height: Math.max(1, y(0) - y(value)), fill: color, "fill-opacity": opacity, tabindex: value ? 0 : -1, class: value ? "interactive" : ""});
      if (value) addTooltip(rect, [row.label, `${label} · ${formatNumber(value)} cells`, `Margin denominator: ${formatNumber(result.margins.length)} visible evidence cells`]);
      svg.append(rect);
    });
    svg.append(svgElement("text", {x: x + slot / 2, y: height - 30, class: "axis-label", "text-anchor": "middle"}, row.label));
    body.append(element("tr", {}, [element("td", {text: row.label}), element("td", {text: row.fairActual}), element("td", {text: row.fairCandidate}), element("td", {text: row.fraudActual}), element("td", {text: row.fraudCandidate})]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 20, fill: colors.green, "font-size": 9, "font-family": "var(--mono)"}, "FAIR EXACT"));
  svg.append(svgElement("text", {x: margin.left + 95, y: 20, fill: colors.red, "font-size": 9, "font-family": "var(--mono)"}, "FRAUD MARGIN UPPER BOUND"));
  svg.append(svgElement("text", {x: margin.left, y: 36, class: "axis-label"}, "FAINT = ACTUAL · SOLID = CANDIDATE · ZERO IS ACCEPT/REJECT BOUNDARY"));
  host.append(svg);
}

function renderReviewerTemporal(result) {
  const host = $("#reviewer-temporal-chart"); clear(host);
  const body = $("#reviewer-temporal-table"); clear(body);
  const rows = result.games;
  if (!rows.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No reviewer cells match this cohort."})]));
    return;
  }
  const width = Math.max(920, rows.length * 17 + 90), height = 390, margin = {left: 74, right: 30, top: 48, bottom: 58};
  const values = rows.map(row => row.pricedDelta);
  let min = Math.min(0, ...values), max = Math.max(0, ...values);
  const pad = (max - min || 1) * .12; min -= pad; max += pad;
  const x = index => margin.left + (index + .5) / rows.length * (width - margin.left - margin.right);
  const slot = (width - margin.left - margin.right) / rows.length;
  const y = value => margin.top + (max - value) / (max - min || 1) * (height - margin.top - margin.bottom);
  const zero = y(0);
  const svg = svgRoot(width, height, "Per-game priced reviewer-cost delta and potentially exposed hidden fraud groups");
  for (let tick = 0; tick <= 4; tick++) {
    const value = min + (max - min) * tick / 4, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true)));
  }
  rows.forEach((row, index) => {
    const xx = x(index), yy = y(row.pricedDelta), tone = row.pricedDelta <= 0 ? colors.green : colors.red;
    const bar = svgElement("rect", {x: xx - slot * .3, y: Math.min(zero, yy), width: Math.max(2, slot * .6), height: Math.max(1, Math.abs(zero - yy)), fill: tone, "fill-opacity": .68, tabindex: 0, class: "interactive"});
    addTooltip(bar, [`Game ${row.game}`, `Priced reviewer-cost Δ ${signed(row.pricedDelta)} · ${row.pricedCells} paired cells`, `${row.fairSwitches} fair switches · ${row.fraudSwitches} fraud switches`, `${row.hiddenExposures} potentially exposed hidden groups · ${row.unpricedChanged} other unpriced changes`]);
    svg.append(bar);
    if (row.hiddenExposures) {
      const diamondY = margin.top + 10;
      const diamond = svgElement("rect", {x: xx - 4, y: diamondY - 4, width: 8, height: 8, fill: colors.amber, transform: `rotate(45 ${xx} ${diamondY})`, tabindex: 0, class: "interactive"});
      addTooltip(diamond, [`Game ${row.game}`, `${row.hiddenExposures} potentially exposed hidden fraud groups`, "Amounts and crossings unpriced"]);
      svg.append(diamond);
      if (row.hiddenExposures > 1) svg.append(svgElement("text", {x: xx + 7, y: diamondY + 3, fill: colors.amber, "font-size": 8, "font-family": "var(--mono)"}, row.hiddenExposures));
    }
    if (index % Math.max(1, Math.ceil(rows.length / 10)) === 0 || index === rows.length - 1) {
      svg.append(svgElement("text", {x: xx, y: height - 24, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    }
    body.append(element("tr", {}, [
      element("td", {text: row.game}), element("td", {text: row.cells}), element("td", {text: row.pricedCells}),
      element("td", {class: `money ${row.pricedDelta <= 0 ? "positive" : "negative"}`, text: signed(row.pricedDelta)}),
      element("td", {text: row.fairSwitches}), element("td", {text: row.fraudSwitches}),
      element("td", {text: row.hiddenExposures}), element("td", {text: row.unpricedChanged}),
    ]));
  });
  svg.append(svgElement("line", {x1: margin.left, y1: zero, x2: width - margin.right, y2: zero, stroke: colors.muted, "stroke-width": 1.3}));
  svg.append(svgElement("text", {x: margin.left, y: 20, class: "axis-label"}, "BAR = PRICED Δ EUR · AMBER DIAMOND = POTENTIAL HIDDEN EXPOSURE, UNPRICED"));
  host.append(svg);
}

function renderReviewerSweep() {
  const host = $("#reviewer-sweep-chart"); clear(host);
  const body = $("#reviewer-sweep-table"); clear(body);
  if (!state.reviewerLab) return;
  const rows = reviewerPolicySweep(state.reviewerLab.cells || [], reviewerPolicyOptions());
  const width = 1120, laneHeight = 152, height = 34 + laneHeight * rows.length + 32;
  const margin = {left: 130, right: 82, top: 31, bottom: 30};
  const plotW = width - margin.left - margin.right;
  const svg = svgRoot(width, height, "Isolated reviewer policy sensitivity by sanctioned value bucket");
  rows.forEach((row, rowIndex) => {
    const laneTop = margin.top + rowIndex * laneHeight;
    const values = row.points.map(point => point.pricedDelta);
    let min = Math.min(0, ...values), max = Math.max(0, ...values);
    const pad = (max - min || 1) * .14; min -= pad; max += pad;
    const minShift = row.points[0].shift, maxShift = row.points.at(-1).shift;
    const x = shift => margin.left + (shift - minShift) / (maxShift - minShift || 1) * plotW;
    const y = value => laneTop + 20 + (max - value) / (max - min || 1) * (laneHeight - 48);
    const zero = y(0);
    svg.append(svgElement("line", {x1: margin.left, y1: laneTop + laneHeight, x2: width - margin.right, y2: laneTop + laneHeight, class: "grid-line"}));
    svg.append(svgElement("line", {x1: margin.left, y1: zero, x2: width - margin.right, y2: zero, stroke: colors.muted, "stroke-width": 1, "stroke-dasharray": "3 3"}));
    svg.append(svgElement("text", {x: margin.left - 14, y: laneTop + 35, fill: colors.text || "#d8e0e5", "font-size": 11, "font-family": "var(--mono)", "text-anchor": "end"}, `T_LO ${row.bucket}`));
    svg.append(svgElement("text", {x: margin.left - 14, y: laneTop + 53, class: "axis-label", "text-anchor": "end"}, `${formatCurrency(min, true)} → ${formatCurrency(max, true)}`));
    const points = row.points.map(point => [x(point.shift), y(point.pricedDelta)]);
    svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: colors.cyan, "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round"}));
    row.points.forEach(point => {
      const selected = point.shift === row.selectedShift;
      const tone = point.pricedDelta <= 0 ? colors.green : colors.red;
      const marker = svgElement("circle", {cx: x(point.shift), cy: y(point.pricedDelta), r: selected ? 6 : 3.5, fill: tone, stroke: selected ? colors.cyan : "none", "stroke-width": selected ? 2.5 : 0, tabindex: 0, class: "interactive"});
      addTooltip(marker, [`Floor ${row.bucket} · Δb ${signed(point.shift)}`, `Priced reviewer-cost Δ ${signed(point.pricedDelta)} · ${point.pricedCells} paired cells`, `${point.fairSwitches} fair switches · ${point.fraudSwitches} fraud switches`, `${point.hiddenExposures} potentially exposed hidden groups · ${point.unpricedChanged} other unpriced changes`, selected ? "Selected shift" : "Isolated sweep point; all other bucket shifts = €0"]);
      svg.append(marker);
      if (point.hiddenExposures) {
        const exposureY = laneTop + 15;
        const exposure = svgElement("circle", {cx: x(point.shift), cy: exposureY, r: clamp(2.5 + Math.sqrt(point.hiddenExposures), 3, 9), fill: colors.amber, "fill-opacity": .7, tabindex: 0, class: "interactive"});
        addTooltip(exposure, [`Δb ${signed(point.shift)} · floor ${row.bucket}`, `${point.hiddenExposures} potentially exposed hidden fraud groups`, "Amounts, crossings, and euro impact unpriced"]);
        svg.append(exposure);
      }
      svg.append(svgElement("text", {x: x(point.shift), y: laneTop + laneHeight - 10, class: "axis-label", "text-anchor": "middle"}, signed(point.shift).replace("€", "")));
      body.append(element("tr", {}, [
        element("td", {text: row.bucket}), element("td", {class: "money", text: signed(point.shift)}),
        element("td", {text: point.cells}), element("td", {text: point.pricedCells}),
        element("td", {class: `money ${point.pricedDelta <= 0 ? "positive" : "negative"}`, text: signed(point.pricedDelta)}),
        element("td", {text: point.fairSwitches}), element("td", {text: point.fraudSwitches}),
        element("td", {text: point.hiddenExposures}), element("td", {text: point.unpricedChanged}),
      ]));
    });
  });
  svg.append(svgElement("text", {x: margin.left, y: 17, class: "axis-label"}, "LINE = PRICED COST Δ · LARGE OUTLINE = SELECTED SHIFT · AMBER BUBBLE = POTENTIAL HIDDEN EXPOSURE"));
  host.append(svg);
}

function renderReviewerBreakpoints(result) {
  const host = $("#reviewer-breakpoint-list"); clear(host);
  const body = $("#reviewer-breakpoint-table"); clear(body);
  const rows = result.transitions.slice(0, 1000);
  $("#reviewer-breakpoint-count").textContent = `${formatNumber(result.transitions.length)} evidence transitions${result.transitions.length > rows.length ? ` · first ${rows.length} rendered` : ""}`;
  rows.slice(0, 80).forEach(row => {
    const tone = row.transitionKind === "hidden-exposure" ? "warning" : row.pricedDelta === null ? "" : row.pricedDelta <= 0 ? "positive" : "negative";
    const button = element("button", {type: "button", class: "reviewer-breakpoint-row"}, [
      element("span", {text: `G${row.game} · I${row.item}`}),
      element("div", {}, [element("strong", {text: row.opponent}), element("small", {text: `${row.valueBucket} · ${row.transitionKind.replaceAll("-", " ")} · ${row.evidenceKind.replaceAll("-", " ")}`})]),
      element("span", {text: `${reviewerOutcomeLabel(row.outcome)} → ${reviewerOutcomeLabel(row.candidateOutcome)}`}),
      element("strong", {class: tone, text: row.pricedDelta === null ? "UNPRICED" : signed(row.pricedDelta)}),
    ]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item); $("#item").scrollIntoView({behavior: "smooth"}); });
    host.append(button);
  });
  if (!rows.length) host.append(element("div", {class: "empty-state"}, [element("p", {text: "No evidence state changes under the selected policy."})]));
  rows.forEach(row => body.append(element("tr", {}, [
    element("td", {}, [itemLink(row.game, row.item)]), element("td", {text: row.opponent}),
    element("td", {text: row.valueBucket}), element("td", {text: row.evidenceKind.replaceAll("-", " ")}),
    element("td", {text: reviewerOutcomeLabel(row.outcome)}), element("td", {text: reviewerOutcomeLabel(row.candidateOutcome)}),
    element("td", {class: "money", text: row.pricedDelta === null ? "unpriced" : signed(row.pricedDelta)}),
    element("td", {text: row.limitAudit}),
  ])));
}

function renderReviewerLab() {
  if (!state.reviewerLab) return;
  const result = evaluateReviewerPolicy(state.reviewerLab.cells || [], reviewerPolicyOptions());
  state.reviewerResult = result;
  $("#reviewer-lab-status").textContent = `${formatNumber(result.totals.cells)} CELLS · ${formatNumber(result.totals.pricedCells)} PAIRED · ${formatNumber(result.totals.hiddenExposures)} HIDDEN EXPOSURES`;
  renderReviewerKpis(result); renderReviewerMatrix(result); renderReviewerWaterfall(result);
  renderReviewerBuckets(result); renderReviewerMargins(result); renderReviewerTemporal(result);
  renderReviewerSweep();
  renderReviewerBreakpoints(result);
}

function scheduleReviewerRender() {
  clearTimeout(state.reviewerRenderPending);
  state.reviewerRenderPending = setTimeout(() => {
    state.reviewerRenderPending = null;
    renderReviewerLab();
    syncInvestigationUrl("strategy");
  }, 80);
}

async function loadReviewerLab() {
  $("#reviewer-lab-empty").hidden = false;
  $("#reviewer-lab-workspace").hidden = true;
  $("#cohort-empty").hidden = false;
  $("#cohort-workspace").hidden = true;
  $("#regret-empty").hidden = false;
  $("#regret-workspace").hidden = true;
  state.peerRegretCache = null;
  if (state.itemDetail) { $("#peer-empty").hidden = false; $("#peer-workspace").hidden = true; $("#peer-status").textContent = "REFRESHING REVIEWER EVIDENCE"; }
  try {
    const payload = await api("/api/reviewer", {timeout: 50000, retries: 0});
    if (payload.schemaVersion !== 1 || !Array.isArray(payload.cells)) throw new Error("reviewer evidence schema mismatch");
    state.reviewerLab = payload;
    populateReviewerControls();
    populateCohortControls();
    $("#reviewer-lab-empty").hidden = true;
    $("#reviewer-lab-workspace").hidden = false;
    $("#cohort-empty").hidden = true;
    $("#cohort-workspace").hidden = false;
    $("#regret-empty").hidden = true;
    $("#regret-workspace").hidden = false;
    renderReviewerLab();
    renderCohortStudio();
    renderRegretCartography();
    renderPeerForensics();
    if ($("#watchlist-dialog").open) renderWatchlist();
  } catch (error) {
    state.reviewerLab = null;
    $("#reviewer-lab-status").textContent = "EVIDENCE UNAVAILABLE";
    $("#reviewer-lab-empty p").textContent = `Reviewer laboratory unavailable: ${error.message}`;
    $("#cohort-status").textContent = "EVIDENCE UNAVAILABLE";
    $("#cohort-empty p").textContent = `Cohort comparison unavailable: ${error.message}`;
    $("#regret-status").textContent = "EVIDENCE UNAVAILABLE";
    $("#regret-empty p").textContent = `Two-role cartography unavailable: ${error.message}`;
    if (state.itemDetail) renderPeerForensics();
    if ($("#watchlist-dialog").open) renderWatchlist();
  }
}

async function copyReviewerReceipt() {
  const result = state.reviewerResult;
  if (!result || !state.reviewerLab) {
    toast("Reviewer evidence is not available to copy.");
    return;
  }
  const receipt = {
    version: 1,
    status: "offline-partial-observed-cost-counterfactual-only",
    materializedAt: state.reviewerLab.generatedAt,
    filters: {
      temporalCohort: state.reviewerWindow,
      opponent: state.reviewerOpponent,
      source: state.reviewerSource,
      provenClass: state.reviewerClass,
    },
    bucketLimitShifts: {...state.reviewerShifts},
    denominator: {
      selectedReviewerCells: result.totals.cells,
      pairedKnownCandidateCostCells: result.totals.pricedCells,
      potentiallyExposedHiddenFraudGroups: result.totals.hiddenExposures,
      otherUnpricedChangedCells: result.totals.unpricedChanged,
      missingLoggedLimits: result.totals.missingLimits,
    },
    pricedObservedCostResult: {
      pairedBaselineCost: result.totals.pricedBaselineCost,
      pairedCandidateCost: result.totals.pricedCandidateCost,
      pairedCostDelta: result.totals.pricedDelta,
      fairSwitches: result.totals.fairSwitches,
      fairCostDelta: result.totals.fairDelta,
      fraudSwitches: result.totals.fraudSwitches,
      fraudCostDelta: result.totals.fraudDelta,
    },
    bySanctionedFloorBucket: result.buckets.map(row => ({
      bucket: row.bucket, limitShift: row.shift, reviewerCells: row.cells,
      pairedCells: row.pricedCells, pairedCostDelta: row.pricedDelta,
      potentiallyExposedHiddenFraudGroups: row.hiddenExposures,
      otherUnpricedChangedCells: row.unpricedChanged,
    })),
    boundaries: [
      "not tournament impact, expected value, or a production recommendation",
      "priced delta covers only cells whose candidate cost is proven from visible evidence",
      "hidden rejected-fraud amounts and candidate crossings remain unpriced",
      "filters and value buckets are retrospective evidence cohorts",
      "no policy change is submitted or written by this local interface",
    ],
  };
  try {
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    toast("Claim-free reviewer-policy audit receipt copied with denominators and unknown exposure.");
  } catch (error) {
    toast(`Reviewer audit receipt could not be copied: ${error.message}`);
  }
}

function cohortMetricDescriptors() {
  return [
    {key: "score", label: "Valuation SCORE", unit: "rate", direction: "higher"},
    {key: "underRate", label: "Provably-under rate", unit: "rate", direction: "lower"},
    {key: "overRate", label: "Provably-over rate", unit: "rate", direction: "lower"},
    {key: "foregonePerLabelledItem", label: "Foregone lower bound / item", unit: "EUR/item", direction: "lower"},
    {key: "wrongCostPerProvenReview", label: "Wrong-decision cost / proven review", unit: "EUR/cell", direction: "lower"},
    {key: "fairRejectRate", label: "Fair rejection rate", unit: "rate", direction: "lower"},
    {key: "fraudAcceptRate", label: "Fraud acceptance rate", unit: "rate", direction: "lower"},
  ];
}

function formatCohortMetric(value, unit) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "unknown";
  return unit === "rate" ? formatPercent(value) : formatCurrency(value);
}

function formatCohortDelta(value, unit) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "unknown";
  if (unit === "rate") return `${value >= 0 ? "+" : "−"}${formatNumber(Math.abs(value) * 100, 1)} pp`;
  return signed(value);
}

function cohortSpecLabel(spec, gameIds) {
  const games = cohortGameIds(gameIds, spec.window);
  const range = games.length ? `G${games[0]}–G${games.at(-1)}` : "no games";
  const qualifiers = [spec.source !== "all" ? spec.source : null, spec.bucket !== "all" ? spec.bucket : null, spec.status !== "all" ? spec.status : null].filter(Boolean);
  return `${range}${qualifiers.length ? ` · ${qualifiers.join(" · ")}` : " · all item evidence"}`;
}

function populateCohortControls() {
  if (!state.overview) return;
  const sources = [...new Set(state.overview.itemIndex.map(row => row.source || "__unlogged__"))].sort((a, b) => a.localeCompare(b));
  ["a", "b"].forEach(side => {
    const spec = side === "a" ? state.cohortA : state.cohortB;
    const source = $(`#cohort-${side}-source`); clear(source);
    source.append(element("option", {value: "all", text: "All sources"}));
    sources.forEach(name => source.append(element("option", {value: name, text: name === "__unlogged__" ? "No logged source" : name})));
    if (![...source.options].some(row => row.value === spec.source)) spec.source = "all";
    source.value = spec.source;
    $(`#cohort-${side}-window`).value = spec.window;
    $(`#cohort-${side}-bucket`).value = spec.bucket;
    $(`#cohort-${side}-status`).value = spec.status;
  });
  $("#cohort-runs").value = String(state.cohortRuns);
  $("#cohort-seed").value = String(state.cohortSeed);
}

function cohortComparisonResult() {
  if (!state.overview || !state.reviewerLab) return null;
  const gameIds = state.overview.race.gameIds;
  const a = evaluateCohort(state.overview.itemIndex, state.reviewerLab.cells, state.cohortA, gameIds);
  const b = evaluateCohort(state.overview.itemIndex, state.reviewerLab.cells, state.cohortB, gameIds);
  const bootstrap = bootstrapCohortComparison(a, b, {runs: state.cohortRuns, seed: state.cohortSeed});
  return {a, b, bootstrap, overlap: cohortOverlap(a, b, state.overview.itemIndex)};
}

function renderCohortKpis(result) {
  const host = $("#cohort-kpis"); clear(host);
  const score = result.bootstrap.results.find(row => row.key === "score");
  const wrong = result.bootstrap.results.find(row => row.key === "wrongCostPerProvenReview");
  const union = result.overlap.aOnly + result.overlap.bOnly + result.overlap.both;
  const specs = [
    ["Cohort B SCORE", formatCohortMetric(result.b.metrics.score, "rate"), `${formatCurrency(result.b.metrics.provenIncome, true)} proven / ${formatCurrency(result.b.metrics.bestPossible, true)} best possible`, "cyan"],
    ["Observed SCORE Δ", formatCohortDelta(score?.observedDelta, "rate"), "B − A · different item mix may contribute", score?.observedDelta >= 0 ? "positive" : "negative"],
    ["P(B SCORE higher)", formatPercent(score?.probabilityBetter), `${formatNumber(score?.draws)} ${result.bootstrap.paired ? "paired" : "independent"} game-cluster draws`, score?.probabilityBetter >= .5 ? "positive" : "warning"],
    ["Wrong-review cost Δ", formatCohortDelta(wrong?.observedDelta, "EUR/cell"), "EUR per proven reviewer cell · B − A", wrong?.observedDelta <= 0 ? "positive" : "negative"],
    ["Item overlap", formatPercent(union ? result.overlap.both / union : null), `${result.overlap.both} shared / ${union} union game-items`, ""],
    ["Bootstrap design", result.bootstrap.paired ? "PAIRED" : "INDEPENDENT", `${result.a.gameIds.length} A games · ${result.b.gameIds.length} B games · seed ${result.bootstrap.seed}`, ""],
  ];
  specs.forEach(([label, value, note, tone]) => host.append(metricCard(label, value, note, tone)));
  $("#cohort-status").textContent = `${formatNumber(result.a.metrics.items)} A ITEMS · ${formatNumber(result.b.metrics.items)} B ITEMS · ${formatNumber(result.bootstrap.runs)} DRAWS`;
}

function cohortScoreCard(label, cohort, tone) {
  const metrics = cohort.metrics;
  return element("article", {class: `cohort-scorecard ${tone}`}, [
    element("div", {class: "cohort-scorecard-head"}, [element("span", {text: label}), element("strong", {text: formatPercent(metrics.score)})]),
    element("small", {text: cohortSpecLabel(cohort.spec, state.overview.race.gameIds)}),
    element("div", {class: "cohort-score-fraction"}, [
      element("span", {text: formatCurrency(metrics.provenIncome, true)}),
      element("i", {"aria-hidden": "true"}),
      element("span", {text: formatCurrency(metrics.bestPossible, true)}),
    ]),
    element("dl", {}, [
      element("dt", {text: "Items / labelled"}), element("dd", {text: `${metrics.items} / ${metrics.labelledItems}`}),
      element("dt", {text: "Under / over / excluded"}), element("dd", {text: `${metrics.underItems} / ${metrics.overItems} / ${metrics.excludedItems}`}),
      element("dt", {text: "Foregone lower bound"}), element("dd", {text: formatCurrency(metrics.foregoneLowerBound, true)}),
      element("dt", {text: "Proven reviewer cells"}), element("dd", {text: formatNumber(metrics.provenReviewerCells)}),
      element("dt", {text: "Wrong-review cost / cell"}), element("dd", {text: formatCurrency(metrics.wrongCostPerProvenReview, true)}),
      element("dt", {text: "Fair reject / fraud accept"}), element("dd", {text: `${formatPercent(metrics.fairRejectRate)} / ${formatPercent(metrics.fraudAcceptRate)}`}),
    ]),
  ]);
}

function renderCohortScorecards(result) {
  const host = $("#cohort-scorecards"); clear(host);
  host.append(cohortScoreCard("COHORT A · REFERENCE", result.a, "a"), cohortScoreCard("COHORT B · CANDIDATE", result.b, "b"));
}

function renderCohortForest(result) {
  const host = $("#cohort-forest-chart"); clear(host);
  const metricTable = $("#cohort-metric-table"); clear(metricTable);
  const bootstrapTable = $("#cohort-bootstrap-table"); clear(bootstrapTable);
  const rows = result.bootstrap.results;
  const width = 900, rowHeight = 67, height = 58 + rows.length * rowHeight;
  const margin = {left: 215, right: 130, top: 38, bottom: 25};
  const center = margin.left + (width - margin.left - margin.right) / 2;
  const half = (width - margin.left - margin.right) / 2;
  const svg = svgRoot(width, height, "Observed cohort differences with 95 percent game-cluster bootstrap intervals");
  svg.append(svgElement("line", {x1: center, y1: margin.top - 15, x2: center, y2: height - margin.bottom, stroke: colors.muted, "stroke-width": 1.2}));
  svg.append(svgElement("text", {x: center - 8, y: 17, class: "axis-label", "text-anchor": "end"}, "A BETTER"));
  svg.append(svgElement("text", {x: center + 8, y: 17, class: "axis-label"}, "B BETTER"));
  rows.forEach((row, index) => {
    const y = margin.top + index * rowHeight + rowHeight / 2;
    const values = [row.p025, row.p975, row.observedDelta].filter(Number.isFinite);
    const maxAbs = Math.max(...values.map(Math.abs), row.unit === "rate" ? .01 : 1);
    const directional = value => row.direction === "higher" ? value : -value;
    const x = value => center + directional(value) / maxAbs * half * .88;
    svg.append(svgElement("line", {x1: margin.left, y1: y + rowHeight / 2, x2: width - margin.right, y2: y + rowHeight / 2, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 12, y: y + 3, fill: "#98a4ad", "font-size": 10, "font-family": "var(--mono)", "text-anchor": "end"}, row.label));
    if (Number.isFinite(row.p025) && Number.isFinite(row.p975)) {
      const loX = x(row.p025), hiX = x(row.p975);
      svg.append(svgElement("line", {x1: Math.min(loX, hiX), y1: y, x2: Math.max(loX, hiX), y2: y, stroke: row.intervalExcludesZero ? colors.cyan : colors.muted, "stroke-width": row.intervalExcludesZero ? 3 : 2, "stroke-linecap": "round"}));
      [loX, hiX].forEach(xx => svg.append(svgElement("line", {x1: xx, y1: y - 6, x2: xx, y2: y + 6, stroke: row.intervalExcludesZero ? colors.cyan : colors.muted, "stroke-width": 1.4})));
      const observedX = x(row.observedDelta);
      const better = row.direction === "higher" ? row.observedDelta >= 0 : row.observedDelta <= 0;
      const diamond = svgElement("rect", {x: observedX - 5, y: y - 5, width: 10, height: 10, fill: better ? colors.green : colors.red, transform: `rotate(45 ${observedX} ${y})`, tabindex: 0, class: "interactive"});
      addTooltip(diamond, [row.label, `Observed B − A ${formatCohortDelta(row.observedDelta, row.unit)}`, `95% interval ${formatCohortDelta(row.p025, row.unit)} to ${formatCohortDelta(row.p975, row.unit)}`, `P(B better) ${formatPercent(row.probabilityBetter)} · ${row.draws} draws`, result.bootstrap.paired ? "Paired whole-game resampling" : "Independent whole-game resampling"]);
      svg.append(diamond);
    }
    svg.append(svgElement("text", {x: width - margin.right + 10, y: y + 3, fill: row.intervalExcludesZero ? colors.cyan : colors.muted, "font-size": 9, "font-family": "var(--mono)"}, formatCohortDelta(row.observedDelta, row.unit)));
    metricTable.append(element("tr", {}, [
      element("td", {text: row.label}), element("td", {text: formatCohortMetric(row.observedA, row.unit)}),
      element("td", {text: formatCohortMetric(row.observedB, row.unit)}), element("td", {text: formatCohortDelta(row.observedDelta, row.unit)}),
    ]));
    bootstrapTable.append(element("tr", {}, [
      element("td", {text: row.label}), element("td", {text: formatNumber(row.draws)}),
      element("td", {text: formatCohortDelta(row.p025, row.unit)}), element("td", {text: formatCohortDelta(row.p50, row.unit)}),
      element("td", {text: formatCohortDelta(row.p975, row.unit)}), element("td", {text: formatPercent(row.probabilityBetter)}),
      element("td", {text: row.intervalExcludesZero ? "yes" : "no"}),
    ]));
  });
  host.append(svg);
}

function renderCohortBootstrap(result) {
  const host = $("#cohort-bootstrap-chart"); clear(host);
  const values = result.bootstrap.scoreDraws.filter(Number.isFinite);
  $("#cohort-bootstrap-denominator").textContent = `${formatNumber(values.length)} ${result.bootstrap.paired ? "paired" : "independent"} draws`;
  if (!values.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "Both cohorts need positive fixed valuation denominators."})]));
    return;
  }
  const min = Math.min(...values, 0), max = Math.max(...values, 0);
  const binCount = 28, span = max - min || 1;
  const bins = Array.from({length: binCount}, (_, index) => ({lo: min + span * index / binCount, hi: min + span * (index + 1) / binCount, count: 0}));
  values.forEach(value => bins[Math.min(binCount - 1, Math.floor((value - min) / span * binCount))].count += 1);
  const width = 740, height = 475, margin = {left: 62, right: 28, top: 52, bottom: 58};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const x = value => margin.left + (value - min) / span * plotW;
  const maxCount = Math.max(1, ...bins.map(row => row.count));
  const y = count => margin.top + (maxCount - count) / maxCount * plotH;
  const svg = svgRoot(width, height, "Bootstrap distribution of Cohort B minus A valuation SCORE");
  bins.forEach(row => {
    const xx = x(row.lo), barW = Math.max(1, x(row.hi) - xx - 1);
    const tone = (row.lo + row.hi) / 2 >= 0 ? colors.green : colors.red;
    const bar = svgElement("rect", {x: xx, y: y(row.count), width: barW, height: plotH - (y(row.count) - margin.top), fill: tone, "fill-opacity": .65, tabindex: row.count ? 0 : -1, class: row.count ? "interactive" : ""});
    if (row.count) addTooltip(bar, [`SCORE Δ ${formatCohortDelta(row.lo, "rate")} to ${formatCohortDelta(row.hi, "rate")}`, `${row.count} / ${values.length} game-cluster draws`, `${formatPercent(row.count / values.length)} of bootstrap denominator`]);
    svg.append(bar);
  });
  const zeroX = x(0);
  svg.append(svgElement("line", {x1: zeroX, y1: margin.top - 12, x2: zeroX, y2: height - margin.bottom, stroke: colors.cyan, "stroke-width": 1.4, "stroke-dasharray": "4 4"}));
  for (let tick = 0; tick <= 4; tick++) {
    const value = min + span * tick / 4;
    svg.append(svgElement("text", {x: x(value), y: height - 27, class: "axis-label", "text-anchor": "middle"}, formatCohortDelta(value, "rate")));
  }
  const score = result.bootstrap.results.find(row => row.key === "score");
  svg.append(svgElement("text", {x: margin.left, y: 20, class: "axis-label"}, `${result.bootstrap.paired ? "PAIRED" : "INDEPENDENT"} WHOLE-GAME RESAMPLING · SEED ${result.bootstrap.seed}`));
  svg.append(svgElement("text", {x: width - margin.right, y: 20, fill: colors.cyan, "font-size": 9, "font-family": "var(--mono)", "text-anchor": "end"}, `P(B>A) ${formatPercent(score?.probabilityBetter)}`));
  host.append(svg);
}

function renderCohortTemporal(result) {
  const host = $("#cohort-temporal-chart"); clear(host);
  const body = $("#cohort-temporal-table"); clear(body);
  const rows = [
    ...result.a.contributions.map(row => ({...row, cohort: "A", tone: colors.violet})),
    ...result.b.contributions.map(row => ({...row, cohort: "B", tone: colors.cyan})),
  ];
  const games = [...new Set(rows.map(row => row.game))].sort((a, b) => a - b);
  if (!games.length) return;
  const width = Math.max(980, games.length * 24 + 130), height = 430, margin = {left: 74, right: 40, top: 47, bottom: 58};
  const x = game => margin.left + (games.indexOf(game) + .5) / games.length * (width - margin.left - margin.right);
  const y = value => margin.top + (1 - clamp(value, 0, 1)) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Per-game cohort valuation SCORE with wrong-review cost encoded by marker radius");
  for (let tick = 0; tick <= 4; tick++) {
    const value = tick / 4, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatPercent(value, 0)));
  }
  ["A", "B"].forEach(cohortName => {
    const cohortRows = rows.filter(row => row.cohort === cohortName && row.bestPossible > 0).map(row => ({...row, score: row.provenIncome / row.bestPossible}));
    if (cohortRows.length > 1) svg.append(svgElement("path", {d: linePath(cohortRows.map(row => [x(row.game), y(row.score)])), fill: "none", stroke: cohortRows[0].tone, "stroke-width": 2, "stroke-opacity": .65, "stroke-dasharray": cohortName === "A" ? "4 4" : "none"}));
    cohortRows.forEach(row => {
      const wrongCost = row.rejectFairCost + row.acceptFraudCost;
      const marker = svgElement("circle", {cx: x(row.game), cy: y(row.score), r: clamp(3 + Math.sqrt(wrongCost) / 18, 3, 12), fill: row.tone, "fill-opacity": .76, stroke: cohortName === "A" ? colors.violet : colors.cyan, "stroke-width": 1, tabindex: 0, class: "interactive"});
      addTooltip(marker, [`Cohort ${cohortName} · game ${row.game}`, `Valuation SCORE ${formatPercent(row.score)} · ${row.labelledItems} labelled items`, `${formatCurrency(row.provenIncome)} proven / ${formatCurrency(row.bestPossible)} best possible`, `Wrong-review cost ${formatCurrency(wrongCost)} · ${row.provenReviewerCells} proven review cells`]);
      svg.append(marker);
    });
  });
  games.forEach((game, index) => {
    if (index % Math.max(1, Math.ceil(games.length / 10)) === 0 || index === games.length - 1) svg.append(svgElement("text", {x: x(game), y: height - 26, class: "axis-label", "text-anchor": "middle"}, `G${game}`));
  });
  svg.append(svgElement("text", {x: margin.left, y: 19, fill: colors.violet, "font-size": 9, "font-family": "var(--mono)"}, "A · DASHED"));
  svg.append(svgElement("text", {x: margin.left + 85, y: 19, fill: colors.cyan, "font-size": 9, "font-family": "var(--mono)"}, "B · SOLID"));
  svg.append(svgElement("text", {x: margin.left + 165, y: 19, class: "axis-label"}, "MARKER AREA ∝ WRONG-REVIEW COST · OBSERVED EUR"));
  host.append(svg);
  rows.sort((a, b) => a.game - b.game || a.cohort.localeCompare(b.cohort)).forEach(row => {
    const score = row.bestPossible > 0 ? row.provenIncome / row.bestPossible : null;
    body.append(element("tr", {}, [
      element("td", {text: row.cohort}), element("td", {text: row.game}), element("td", {text: row.items}),
      element("td", {text: row.labelledItems}), element("td", {class: "money", text: formatCurrency(row.bestPossible)}),
      element("td", {class: "money", text: formatCurrency(row.provenIncome)}), element("td", {text: formatPercent(score)}),
      element("td", {class: "money", text: formatCurrency(row.rejectFairCost + row.acceptFraudCost)}), element("td", {text: row.provenReviewerCells}),
    ]));
  });
}

function renderCohortOverlap(result) {
  const host = $("#cohort-overlap"); clear(host);
  const rows = [
    ["A only", result.overlap.aOnly, colors.violet], ["Both", result.overlap.both, colors.cyan],
    ["B only", result.overlap.bOnly, colors.green], ["Neither", result.overlap.neither, colors.muted],
  ];
  const total = Math.max(1, result.overlap.universe);
  const bar = element("div", {class: "cohort-overlap-bar", "aria-label": "Item universe membership"});
  rows.forEach(([label, count, color]) => {
    if (!count) return;
    const segment = element("span", {title: `${label}: ${count}`});
    segment.style.width = `${count / total * 100}%`; segment.style.background = color;
    bar.append(segment);
  });
  const union = result.overlap.aOnly + result.overlap.both + result.overlap.bOnly;
  host.append(bar, element("div", {class: "cohort-overlap-stats"}, rows.map(([label, count, color]) => {
    const card = element("div", {}, [element("span", {text: label}), element("strong", {text: formatNumber(count)}), element("small", {text: `${formatPercent(count / total)} of ${total} indexed items`})]);
    card.style.setProperty("--overlap-color", color); return card;
  })), element("p", {class: "cohort-overlap-note", text: `Jaccard overlap ${formatPercent(union ? result.overlap.both / union : null)} · identifier membership only, not matched repeated observations.`}));
}

function renderCohortDivergence(result) {
  const host = $("#cohort-divergence-list"); clear(host);
  const body = $("#cohort-divergence-table"); clear(body);
  const tail = cohort => [...cohort.items].filter(row => row.tLo !== null && row.a !== null).sort((a, b) => safeNumber(b.foregoneLowerBound) - safeNumber(a.foregoneLowerBound) || Math.abs(safeNumber(b.logError)) - Math.abs(safeNumber(a.logError))).slice(0, 12);
  const rows = [...tail(result.a).map(row => ({...row, cohort: "A"})), ...tail(result.b).map(row => ({...row, cohort: "B"}))]
    .sort((a, b) => safeNumber(b.foregoneLowerBound) - safeNumber(a.foregoneLowerBound));
  $("#cohort-divergence-count").textContent = `${rows.length} tail records · proven loss first`;
  rows.slice(0, 18).forEach(row => {
    const button = element("button", {type: "button", class: `cohort-divergence-row cohort-${row.cohort.toLowerCase()}`}, [
      element("span", {text: row.cohort}), element("strong", {text: `Game ${row.game} item ${row.item}`}),
      element("span", {text: `${row.source || "unlogged"} · ${valueBucket(row.tLo) || "unlabelled"} · ${prettyStatus(row.status)}`}),
      element("strong", {class: row.foregoneLowerBound > 0 ? "negative" : "", text: row.foregoneLowerBound > 0 ? formatCurrency(row.foregoneLowerBound, true) : formatNumber(row.logError, 2)}),
    ]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item); $("#item").scrollIntoView({behavior: "smooth"}); });
    host.append(button);
  });
  if (!rows.length) host.append(element("div", {class: "empty-state"}, [element("p", {text: "No decided, sanctioned-floor items are in these cohorts."})]));
  rows.forEach(row => body.append(element("tr", {}, [
    element("td", {text: row.cohort}), element("td", {}, [itemLink(row.game, row.item)]),
    element("td", {text: row.source || "unlogged"}), element("td", {text: valueBucket(row.tLo) || "unlabelled"}),
    element("td", {text: prettyStatus(row.status)}), element("td", {class: "money", text: formatCurrency(row.tLo)}),
    element("td", {class: "money", text: formatCurrency(row.a)}), element("td", {class: "money", text: formatCurrency(row.foregoneLowerBound)}),
  ])));
}

function renderCohortStudio() {
  if (!state.overview || !state.reviewerLab) return;
  const result = cohortComparisonResult();
  state.cohortResult = result;
  renderCohortKpis(result); renderCohortScorecards(result); renderCohortForest(result);
  renderCohortBootstrap(result); renderCohortTemporal(result); renderCohortOverlap(result);
  renderCohortDivergence(result);
}

async function copyCohortReceipt() {
  const result = state.cohortResult;
  if (!result) { toast("Cohort evidence is not available to copy."); return; }
  const compactMetrics = cohort => ({
    games: cohort.gameIds, items: cohort.metrics.items, labelledItems: cohort.metrics.labelledItems,
    provenIncome: cohort.metrics.provenIncome, bestPossible: cohort.metrics.bestPossible,
    valuationScore: cohort.metrics.score, underRate: cohort.metrics.underRate,
    overRate: cohort.metrics.overRate, excludedItems: cohort.metrics.excludedItems,
    foregoneLowerBound: cohort.metrics.foregoneLowerBound,
    provenReviewerCells: cohort.metrics.provenReviewerCells,
    wrongReviewerCost: cohort.metrics.wrongReviewerCost,
    wrongCostPerProvenReview: cohort.metrics.wrongCostPerProvenReview,
    fairRejectRate: cohort.metrics.fairRejectRate,
    fraudAcceptRate: cohort.metrics.fraudAcceptRate,
  });
  const receipt = {
    version: 1, status: "offline-retrospective-cohort-comparison-only",
    materializedAt: state.overview.generatedAt,
    cohortA: {filters: {...state.cohortA}, metrics: compactMetrics(result.a)},
    cohortB: {filters: {...state.cohortB}, metrics: compactMetrics(result.b)},
    overlap: result.overlap,
    clusterBootstrap: {
      design: result.bootstrap.paired ? "paired-whole-game" : "independent-whole-game",
      draws: result.bootstrap.runs, seed: result.bootstrap.seed,
      differences: result.bootstrap.results.map(row => ({
        key: row.key, unit: row.unit, directionBetter: row.direction,
        observedBMinusA: row.observedDelta, p025: row.p025, median: row.p50,
        p975: row.p975, probabilityBBetter: row.probabilityBetter,
      })),
    },
    boundaries: [
      "retrospective filtered cohorts, not randomized treatments or causal effects",
      "each cohort has its own fixed 16 × sanctioned-floor valuation denominator",
      "whole-game resampling measures sampling instability under observed games only",
      "hidden rejected-fraud amounts are absent from reviewer-cost metrics",
      "no model, rule, acceptance limit, charge, or submission is modified",
    ],
  };
  try {
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    toast("Claim-free cohort research receipt copied with fixed denominators and cluster-bootstrap uncertainty.");
  } catch (error) { toast(`Cohort receipt could not be copied: ${error.message}`); }
}

function populateStrategyControls() {
  const source = $("#landscape-source");
  const previousSource = state.landscapeSource;
  clear(source);
  source.append(element("option", {value: "all", text: "All sources"}));
  state.overview.intelligence.valueRisk.sources.forEach(name => {
    source.append(element("option", {value: name, text: name}));
  });
  state.landscapeSource = [...source.options].some(row => row.value === previousSource) ? previousSource : "all";
  source.value = state.landscapeSource;
  $("#landscape-bucket").value = state.landscapeBucket;
  $$("[data-landscape-status]").forEach(button => {
    const active = button.dataset.landscapeStatus === state.landscapeStatus;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  const dossier = $("#dossier-team");
  const previousTeam = state.dossierTeam;
  clear(dossier);
  const opponents = [...state.overview.trends.opponents].sort((a, b) => a.team.localeCompare(b.team));
  opponents.forEach(row => dossier.append(element("option", {value: row.team, text: row.team})));
  const defaultTeam = [...opponents].sort((a, b) => a.netExchange - b.netExchange)[0]?.team || null;
  state.dossierTeam = opponents.some(row => row.team === previousTeam) ? previousTeam : defaultTeam;
  if (state.dossierTeam) dossier.value = state.dossierTeam;
  populateRuleControl();
  populatePortfolioControls();
}

function hydrateAnalyticalUrlState() {
  const params = new URLSearchParams(window.location.search);
  const bucket = params.get("bucket");
  const status = params.get("status");
  state.landscapeSource = params.get("source") || "all";
  state.landscapeBucket = ["0–50", "50–400", "400–1200", "1200+"].includes(bucket) ? bucket : "all";
  state.landscapeStatus = ["under", "over", "not-proven-wrong"].includes(status) ? status : "all";
  state.dossierTeam = params.get("opponent") || null;
  const robust = params.get("robust");
  state.robustnessMode = ["medianPaceTotal", "winsorizedTotal", "withoutTop3Positive", "withoutWorst3Negative"].includes(robust) ? robust : "medianPaceTotal";
  state.selectedRuleId = params.get("rule") || null;
  state.ruleTransition = "all";
  state.portfolioRuleId = params.get("prule") || null;
  const portfolioGate = params.get("pgate");
  state.portfolioGate = ["no-opposition", "consensus", "no-b-raise", "stable-only"].includes(portfolioGate) ? portfolioGate : "none";
  const portfolioDirection = params.get("pdir");
  state.portfolioDirection = ["raise", "lower"].includes(portfolioDirection) ? portfolioDirection : "any";
  state.portfolioSource = params.get("psource") || "all";
  const capital = params.get("capital");
  state.capitalSort = ["gross", "net", "cost", "income"].includes(capital) ? capital : "gross";
  const roundMap = params.get("roundmap");
  state.roundMapFilter = ["all", "recent", "positive", "frontier"].includes(roundMap) ? roundMap : "all";
  const evidence = params.get("evidence");
  state.evidenceMode = ["hidden-field", "unresolved-field", "open-ceiling", "missing-belief", "missing-decision", "missing-rule", "missing-replay", "missing-docs"].includes(evidence) ? evidence : "hidden-field";
  const drift = (params.get("drift") || "").split(",");
  state.driftMetric = Object.hasOwn(DRIFT_METRICS, drift[0]) ? drift[0] : "net";
  state.driftWindow = drift[1] === "all" ? "all" : [5, 10, 20].includes(Number(drift[1])) ? Number(drift[1]) : 10;
  state.driftSensitivity = [2, 3, 4].includes(Number(drift[2])) ? Number(drift[2]) : 3;
  const forecast = (params.get("forecast") || "").split(",");
  state.forecastWindow = ["all", "last-5", "last-10", "last-20"].includes(forecast[0]) ? forecast[0] : "all";
  state.forecastRuns = [1000, 5000, 10000].includes(Number(forecast[1])) ? Number(forecast[1]) : 5000;
  const forecastSeed = Number(forecast[2]);
  state.forecastSeed = Number.isInteger(forecastSeed) && forecastSeed >= 1 && forecastSeed <= 2147483646 ? forecastSeed : 20260823;
  state.forecastTarget = [1, 3, 5, 10].includes(Number(forecast[3])) ? Number(forecast[3]) : 3;
  const forecastEdge = Number(forecast[4]);
  state.forecastEdge = Number.isFinite(forecastEdge) && forecastEdge >= -10000 && forecastEdge <= 100000 && forecastEdge % 250 === 0 ? forecastEdge : 0;
  const reviewer = (params.get("reviewer") || "").split("~");
  state.reviewerWindow = ["all", "last-10", "last-20", "logged-era"].includes(reviewer[0]) ? reviewer[0] : "all";
  state.reviewerClass = ["all", "fair", "fraud", "unproven"].includes(reviewer[1]) ? reviewer[1] : "all";
  const decodeReviewerToken = value => {
    try {
      const decoded = decodeURIComponent(String(value || ""));
      return decoded.length <= 100 && !/[\u0000-\u001f\u007f]/.test(decoded) ? decoded : "all";
    } catch { return "all"; }
  };
  state.reviewerOpponent = decodeReviewerToken(reviewer[2]) || "all";
  state.reviewerSource = decodeReviewerToken(reviewer[3]) || "all";
  const reviewerShiftSpecs = [
    ["0–50", reviewer[4], -100, 100, 5], ["50–400", reviewer[5], -400, 400, 25],
    ["400–1200", reviewer[6], -1200, 1200, 50], ["1200+", reviewer[7], -5000, 10000, 250],
  ];
  reviewerShiftSpecs.forEach(([bucket, raw, lo, hi, step]) => {
    const value = Number(raw);
    state.reviewerShifts[bucket] = Number.isFinite(value) && value >= lo && value <= hi && value % step === 0 ? value : 0;
  });
  const cohort = (params.get("cohort") || "").split("~");
  const decodeCohortToken = value => {
    try {
      const decoded = decodeURIComponent(String(value || ""));
      return decoded.length <= 100 && !/[\u0000-\u001f\u007f]/.test(decoded) ? decoded : "";
    } catch { return ""; }
  };
  const windows = new Set(["all", "previous-10", "last-10", "first-half", "second-half"]);
  const buckets = new Set(["all", "0–50", "50–400", "400–1200", "1200+", "unlabelled"]);
  const statuses = new Set(["all", "under", "over", "not-proven-wrong", "open", "unlabelled"]);
  const hydrateCohortSpec = (offset, defaults) => {
    const window = decodeCohortToken(cohort[offset]);
    const source = decodeCohortToken(cohort[offset + 1]);
    const bucketValue = decodeCohortToken(cohort[offset + 2]);
    const statusValue = decodeCohortToken(cohort[offset + 3]);
    return {
      window: windows.has(window) ? window : defaults.window,
      source: source || defaults.source,
      bucket: buckets.has(bucketValue) ? bucketValue : defaults.bucket,
      status: statuses.has(statusValue) ? statusValue : defaults.status,
    };
  };
  state.cohortA = hydrateCohortSpec(0, {window: "previous-10", source: "all", bucket: "all", status: "all"});
  state.cohortB = hydrateCohortSpec(4, {window: "last-10", source: "all", bucket: "all", status: "all"});
  const cohortRuns = Number(decodeCohortToken(cohort[8]));
  state.cohortRuns = [1000, 5000, 10000].includes(cohortRuns) ? cohortRuns : 5000;
  const cohortSeed = Number(decodeCohortToken(cohort[9]));
  state.cohortSeed = Number.isInteger(cohortSeed) && cohortSeed >= 1 && cohortSeed <= 2147483646 ? cohortSeed : 20260824;
  const market = (params.get("market") || "").split("~");
  state.marketTeam = decodeCohortToken(market[0]) || "Oasis";
  const marketMode = decodeCohortToken(market[1]);
  state.marketMode = ["settlement", "acceptance", "wrong", "wedge"].includes(marketMode) ? marketMode : "settlement";
  state.marketPeer = decodeCohortToken(market[2]) || null;
  const marketReplayMode = decodeCohortToken(market[3]);
  state.marketReplayMode = ["cumulative", "round"].includes(marketReplayMode) ? marketReplayMode : "cumulative";
  const marketReplayToken = decodeCohortToken(market[4]);
  const marketReplayGame = marketReplayToken === "" ? Number.NaN : Number(marketReplayToken);
  state.marketReplayGame = Number.isInteger(marketReplayGame) && marketReplayGame >= 0 && marketReplayGame <= 100
    ? marketReplayGame : null;
  const rival = (params.get("rival") || "").split("~");
  state.rivalTeam = decodeCohortToken(rival[0]) || null;
  const rivalWindow = decodeCohortToken(rival[1]);
  state.rivalWindow = RIVAL_WINDOWS.has(rivalWindow) ? rivalWindow : "all";
  const calibration = (params.get("calibration") || "").split("~");
  state.calibrationCoverage = calibrationCoverage(Number(decodeCohortToken(calibration[0])));
  state.calibrationSource = decodeCohortToken(calibration[1]) || "all";
  const calibrationBucket = decodeCohortToken(calibration[2]);
  state.calibrationBucket = CALIBRATION_BUCKETS.includes(calibrationBucket) ? calibrationBucket : "all";
  const calibrationWindow = decodeCohortToken(calibration[3]);
  state.calibrationWindow = CALIBRATION_WINDOWS.has(calibrationWindow) ? calibrationWindow : "all";
  const regret = (params.get("regret") || "").split("~");
  const regretWindow = decodeCohortToken(regret[0]);
  state.regretWindow = REGRET_WINDOWS.has(regretWindow) ? regretWindow : "all";
  state.regretSource = decodeCohortToken(regret[1]) || "all";
  const regretBucket = decodeCohortToken(regret[2]);
  state.regretBucket = REGRET_BUCKETS.includes(regretBucket) ? regretBucket : "all";
  const regretFocus = decodeCohortToken(regret[3]);
  state.regretFocus = REGRET_FOCUS.has(regretFocus) ? regretFocus : "combined";
  const peer = (params.get("peer") || "").split("~");
  const peerCohort = decodeCohortToken(peer[0]);
  state.peerCohort = PEER_COHORTS.has(peerCohort) ? peerCohort : "source-bucket";
  const peerMetric = decodeCohortToken(peer[1]);
  state.peerMetric = PEER_METRICS.some(row => row.key === peerMetric) ? peerMetric : "combined";
}

function renderStrategyKpis() {
  const host = $("#strategy-kpis"); clear(host);
  const rows = state.overview.itemIndex.filter(row => row.tLo !== null && row.a !== null);
  const high = rows.filter(row => row.tLo >= 1200 && row.b !== null);
  const highMedian = medianNumber(high.map(row => row.b - row.tLo));
  const highBelow = high.filter(row => row.b < row.tLo).length;
  const under = rows.filter(row => row.status === "under");
  const over = rows.filter(row => row.status === "over");
  const open = rows.filter(row => row.status === "above-floor-open-ceiling");
  const worst = [...under].sort((a, b) => b.foregoneLowerBound - a.foregoneLowerBound)[0];
  const totalForegone = under.reduce((sum, row) => sum + row.foregoneLowerBound, 0);
  const specs = [
    ["Decided + bracketed", formatNumber(rows.length), "one item denominator"],
    ["Provably under", formatPercent(under.length / Math.max(1, rows.length)), `${under.length} items · ${formatCurrency(totalForegone)} lower bound`],
    ["Provably over", formatPercent(over.length / Math.max(1, rows.length)), `${over.length} items with a known ceiling`],
    ["High-value b − floor", highMedian === null ? "unknown" : signed(highMedian), `${highBelow} / ${high.length} limits below floor · t_lo ≥ €1,200`],
    ["Largest concentration", worst && totalForegone ? formatPercent(worst.foregoneLowerBound / totalForegone) : "unknown", worst ? `game ${worst.game} item ${worst.item} · ${open.length} open-bound items` : "no proven undercharge"],
  ];
  specs.forEach(([label, value, note], index) => host.append(metricCard(label, value, note, index === 1 || index === 4 ? "negative" : "")));
}

function filteredLandscapeRows() {
  return state.overview.itemIndex.filter(row => {
    if (!(row.tLo > 0 && row.a > 0)) return false;
    if (state.landscapeSource !== "all" && row.source !== state.landscapeSource) return false;
    if (state.landscapeBucket !== "all" && valueBucket(row.tLo) !== state.landscapeBucket) return false;
    if (state.landscapeStatus === "not-proven-wrong" && !isNotProvenWrong(row)) return false;
    if (!["all", "not-proven-wrong"].includes(state.landscapeStatus) && row.status !== state.landscapeStatus) return false;
    return true;
  });
}

function landscapeMarker(row, x, y) {
  const tone = row.status === "under" ? colors.amber : row.status === "over" ? colors.red :
    row.status === "inside-bracket" ? colors.green : colors.violet;
  let marker;
  if (row.status === "over") {
    marker = svgElement("path", {d: `M ${x} ${y - 5} L ${x + 5} ${y + 4} L ${x - 5} ${y + 4} Z`, fill: tone});
  } else if (row.status === "inside-bracket") {
    marker = svgElement("rect", {x: x - 4, y: y - 4, width: 8, height: 8, fill: tone, transform: `rotate(45 ${x} ${y})`});
  } else if (row.status === "above-floor-open-ceiling") {
    marker = svgElement("rect", {x: x - 4, y: y - 4, width: 8, height: 8, fill: "none", stroke: tone, "stroke-width": 1.5});
  } else {
    marker = svgElement("circle", {cx: x, cy: y, r: clamp(3 + Math.log10(1 + row.foregoneLowerBound) * .45, 3, 6), fill: tone});
  }
  marker.setAttribute("fill-opacity", row.status === "above-floor-open-ceiling" ? "1" : ".67");
  marker.setAttribute("tabindex", "0");
  marker.setAttribute("class", "interactive");
  marker.setAttribute("role", "button");
  marker.setAttribute("aria-label", `Open game ${row.game} item ${row.item}: ${prettyStatus(row.status)}, charge ${formatCurrency(row.a)}, proven floor ${formatCurrency(row.tLo)}`);
  addTooltip(marker, [
    `Game ${row.game} item ${row.item}`,
    `${prettyStatus(row.status)} · source ${row.source || "unknown"}`,
    `Floor ${formatCurrency(row.tLo)} · charge ${formatCurrency(row.a)} · ${formatNumber(row.a / row.tLo, 2)}× floor`,
    row.tHi === null ? "Ceiling unknown" : `Ceiling ${formatCurrency(row.tHi)}`,
  ]);
  marker.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
  return marker;
}

function renderValuationLandscape() {
  const host = $("#valuation-landscape"); clear(host);
  const rows = filteredLandscapeRows();
  const width = 1080, height = 560, margin = {left: 82, right: 28, top: 38, bottom: 65};
  const svg = svgRoot(width, height, `Oasis charge-to-proven-floor ratio for ${rows.length} filtered items`);
  const allFloor = state.overview.itemIndex.filter(row => row.tLo > 0 && row.a > 0).map(row => row.tLo);
  const xMin = Math.log10(Math.max(.1, Math.min(...allFloor, 1)));
  const xMax = Math.log10(Math.max(10, ...allFloor)) + .08;
  const yMin = -5, yMax = 5;
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const x = value => margin.left + (Math.log10(value) - xMin) / (xMax - xMin || 1) * plotW;
  const y = ratio => margin.top + (yMax - clamp(Math.log2(ratio), yMin, yMax)) / (yMax - yMin) * plotH;
  [-4, -2, 0, 2, 4].forEach(power => {
    const position = margin.top + (yMax - power) / (yMax - yMin) * plotH;
    svg.append(svgElement("line", {x1: margin.left, y1: position, x2: width - margin.right, y2: position, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 10, y: position + 3, class: "axis-label", "text-anchor": "end"}, `${formatNumber(2 ** power, power < 0 ? 2 : 0)}×`));
  });
  const floorTicks = [1, 10, 50, 100, 400, 1200, 5000, 10000, 50000].filter(value => Math.log10(value) >= xMin && Math.log10(value) <= xMax);
  floorTicks.forEach(value => {
    const position = x(value);
    svg.append(svgElement("line", {x1: position, y1: margin.top, x2: position, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("text", {x: position, y: height - 36, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true)));
  });
  const equalY = y(1);
  svg.append(svgElement("line", {x1: margin.left, y1: equalY, x2: width - margin.right, y2: equalY, stroke: colors.cyan, "stroke-width": 1.7, "stroke-dasharray": "6 5"}));
  svg.append(svgElement("text", {x: width - margin.right, y: equalY - 7, fill: colors.cyan, "font-family": "var(--mono)", "font-size": 9, "text-anchor": "end"}, "a = PROVEN FLOOR"));
  svg.append(svgElement("text", {x: margin.left, y: 17, class: "axis-label"}, "CHARGE / FLOOR ↑  · LOG₂ SCALE"));
  svg.append(svgElement("text", {x: width - margin.right, y: height - 12, class: "axis-label", "text-anchor": "end"}, "PROVEN FLOOR t_lo → · LOG₁₀ SCALE"));
  rows.forEach(row => svg.append(landscapeMarker(row, x(row.tLo), y(row.a / row.tLo))));
  if (!rows.length) svg.append(svgElement("text", {x: width / 2, y: height / 2, class: "series-label", "text-anchor": "middle"}, "NO ITEMS MATCH THIS EVIDENCE FILTER"));
  host.append(svg);

  const summary = $("#landscape-summary"); clear(summary);
  const under = rows.filter(row => row.status === "under");
  const over = rows.filter(row => row.status === "over");
  const uncertain = rows.filter(row => row.status === "above-floor-open-ceiling");
  const foregone = under.reduce((sum, row) => sum + row.foregoneLowerBound, 0);
  [["Shown", formatNumber(rows.length), "all"], ["Under", `${under.length} · ${formatCurrency(foregone)}`, "under"], ["Over", formatNumber(over.length), "over"], ["Open ceiling", formatNumber(uncertain.length), "open"]].forEach(([label, value, tone]) => {
    summary.append(element("span", {class: `landscape-stat ${tone}`}, [label, element("strong", {text: value})]));
  });

  const tail = $("#landscape-tail"); clear(tail);
  tail.append(element("div", {class: "landscape-tail-head"}, [element("strong", {text: "Largest filtered departures"}), element("span", {text: "Click through to the complete evidence receipt"})]));
  [...rows].sort((a, b) => {
    const aMagnitude = a.status === "under" ? a.foregoneLowerBound : Math.abs(a.logError || 0) * 1000;
    const bMagnitude = b.status === "under" ? b.foregoneLowerBound : Math.abs(b.logError || 0) * 1000;
    return bMagnitude - aMagnitude;
  }).slice(0, 10).forEach((row, index) => {
    const button = element("button", {type: "button", class: "landscape-tail-row"}, [
      element("span", {text: `#${index + 1}`}),
      element("span", {}, [element("strong", {text: `game ${row.game} item ${row.item}`}), element("small", {text: `${prettyStatus(row.status)} · ${formatNumber(row.a / row.tLo, 2)}× floor`})]),
      element("span", {text: row.foregoneLowerBound ? formatCurrency(row.foregoneLowerBound, true) : `${formatNumber(Math.exp(Math.abs(row.logError || 0)), 1)}×`} ),
    ]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    tail.append(button);
  });

  const body = $("#landscape-data-table"); clear(body);
  rows.slice().sort((a, b) => b.foregoneLowerBound - a.foregoneLowerBound || Math.abs(b.logError || 0) - Math.abs(a.logError || 0)).slice(0, 150).forEach(row => {
    const link = element("button", {type: "button", class: "table-link", text: `game ${row.game} item ${row.item}`});
    link.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    body.append(element("tr", {}, [
      element("td", {}, [link]), element("td", {text: row.source || "unknown"}),
      element("td", {class: "money", text: formatCurrency(row.tLo)}), element("td", {class: "money", text: formatCurrency(row.a)}),
      element("td", {text: `${formatNumber(row.a / row.tLo, 2)}×`}), element("td", {text: prettyStatus(row.status)}),
      element("td", {class: "money", text: row.foregoneLowerBound ? formatCurrency(row.foregoneLowerBound) : "—"}),
    ]));
  });
}

function renderRiskLattice() {
  const host = $("#risk-lattice"); clear(host);
  const risk = state.overview.intelligence.valueRisk;
  host.append(element("div", {class: "risk-header", text: "Belief source"}));
  risk.buckets.forEach(bucket => host.append(element("div", {class: "risk-header", text: `${bucket} EUR floor`})));
  risk.sources.forEach(source => {
    host.append(element("div", {class: "risk-source", text: source}));
    risk.buckets.forEach(bucket => {
      const cell = risk.cells.find(row => row.source === source && row.bucket === bucket);
      if (!cell) {
        host.append(element("div", {class: "risk-cell empty", text: "No evidence"}));
        return;
      }
      const selected = state.selectedRiskCell === `${source}|${bucket}`;
      const button = element("button", {type: "button", class: `risk-cell ${selected ? "selected" : ""}`, "aria-pressed": String(selected), "aria-label": `${source}, ${bucket} euros: ${formatPercent(cell.wrongRate)} provably wrong across ${cell.decisions} decisions`}, [
        element("strong", {text: formatPercent(cell.wrongRate)}),
        element("span", {text: `${cell.under} under · ${cell.over} over · ${cell.decisions} decided`}),
        element("small", {text: `${formatCurrency(cell.foregoneLowerBound, true)} foregone LB`}),
      ]);
      const intensity = .035 + safeNumber(cell.wrongRate) * .17;
      button.style.backgroundColor = `rgba(239,106,103,${intensity})`;
      button.addEventListener("click", () => {
        state.selectedRiskCell = `${source}|${bucket}`;
        state.landscapeSource = source; state.landscapeBucket = bucket;
        $("#landscape-source").value = source; $("#landscape-bucket").value = bucket;
        renderRiskLattice(); renderValuationLandscape();
        syncInvestigationUrl("strategy");
      });
      host.append(button);
    });
  });
  const selected = risk.cells.find(row => `${row.source}|${row.bucket}` === state.selectedRiskCell) ||
    [...risk.cells].sort((a, b) => b.foregoneLowerBound - a.foregoneLowerBound)[0];
  const detail = $("#risk-detail"); clear(detail);
  if (selected) detail.append(
    element("strong", {text: `${selected.source} · ${selected.bucket} EUR`}),
    document.createTextNode(` — median |log error| ${formatNumber(selected.medianAbsoluteLogError, 2)} across ${selected.decisions} decisions; median b − floor ${selected.medianLimitMinusFloor === null ? "unknown" : signed(selected.medianLimitMinusFloor)} across ${selected.limits} limits; ${formatPercent(selected.limitBelowFloorRate)} of those limits sit below the proven floor.`),
  );
}

function evaluatePayoff(t, a, b, c) {
  const cap = Math.max(Number(c), 4 * Number(t));
  const fair = Number(a) <= Number(t);
  const accepted = Number(a) <= Number(b);
  let cost = 0;
  if (fair) cost = accepted ? Number(a) : 1.5 * Number(a);
  else cost = accepted ? Math.min(Number(a), cap) : 0;
  const regret = fair && !accepted ? .5 * Number(a) : !fair && accepted ? Math.min(Number(a), cap) : 0;
  return {t: Number(t), a: Number(a), b: Number(b), c: cap, fair, accepted, cost, regret};
}

function payoffState() {
  const t = safeNumber($("#payoff-t").value);
  const a = safeNumber($("#payoff-a").value);
  const b = safeNumber($("#payoff-b").value);
  const capInput = $("#payoff-c");
  const row = evaluatePayoff(t, a, b, safeNumber(capInput.value));
  if (safeNumber(capInput.value) !== row.c) capInput.value = String(row.c);
  return row;
}

function applyPayoffPreset(name) {
  const specs = {
    "correct-fair": {t: 800, a: 700, b: 900, c: 4000},
    "wrong-reject": {t: 800, a: 700, b: 500, c: 4000},
    "wrong-accept": {t: 600, a: 1200, b: 1400, c: 2400},
    "correct-fraud": {t: 600, a: 1200, b: 800, c: 2400},
  };
  const row = specs[name];
  if (!row) return;
  for (const key of ["t", "a", "b", "c"]) $(`#payoff-${key}`).value = String(row[key]);
  renderPayoff();
}

function renderPayoff() {
  const row = payoffState();
  for (const key of ["t", "a", "b", "c"]) $(`#payoff-${key}-output`).textContent = formatCurrency(row[key]);
  const matrix = $("#payoff-matrix"); clear(matrix);
  const specs = [
    ["", "FAIR · a ≤ t", "FRAUD · a > t"],
    ["ACCEPT · a ≤ b", "Reviewer pays a", "Reviewer pays min(a,c)"],
    ["REJECT · a > b", "Reviewer pays 1.5a", "Reviewer pays 0"],
  ];
  specs.forEach((line, rowIndex) => line.forEach((label, columnIndex) => {
    if (rowIndex === 0 || columnIndex === 0) {
      matrix.append(element("div", {class: "payoff-axis", text: label}));
      return;
    }
    const active = (row.accepted === (rowIndex === 1)) && (row.fair === (columnIndex === 1));
    const formula = rowIndex === 1 && columnIndex === 1 ? `a = ${formatCurrency(row.a)}` :
      rowIndex === 1 && columnIndex === 2 ? `min(a,c) = ${formatCurrency(Math.min(row.a, row.c))}` :
      rowIndex === 2 && columnIndex === 1 ? `1.5a = ${formatCurrency(1.5 * row.a)}` : "€0";
    matrix.append(element("div", {class: `payoff-cell ${active ? "active" : ""}`}, [element("strong", {text: label}), element("span", {text: formula})]));
  }));
  const results = $("#payoff-results"); clear(results);
  const truth = row.fair ? "FAIR" : "FRAUD";
  const verdict = row.accepted ? "ACCEPT" : "REJECT";
  [
    ["Active branch", `${verdict} × ${truth}`, `a ${row.a <= row.b ? "≤" : ">"} b and a ${row.a <= row.t ? "≤" : ">"} t`],
    ["Reviewer settlement", formatCurrency(row.cost), "exact for this one decision under the stated matrix"],
    ["Avoidable regret", formatCurrency(row.regret), row.regret ? (row.fair ? "extra 0.5a from rejecting fair" : "fraud settlement avoided by rejection") : "decision matches the zero-regret action"],
  ].forEach(([label, value, note]) => results.append(element("div", {class: "payoff-result"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
}

function renderDossierTimeline(row) {
  const host = $("#dossier-timeline"); clear(host);
  const timeline = row.timeline || [];
  if (!timeline.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No bilateral settlements are materialised for this opponent."})]));
    return;
  }
  const width = 780, height = 330, margin = {left: 75, right: 25, top: 28, bottom: 50};
  const values = timeline.map(point => point.cumulativeNet);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const svg = svgRoot(width, height, `Cumulative bilateral exchange between Oasis and ${row.team}`);
  const scale = chartScaffold(svg, width, height, margin, min, max, 5);
  const zeroY = scale.y(0);
  svg.append(svgElement("line", {x1: margin.left, y1: zeroY, x2: width - margin.right, y2: zeroY, stroke: colors.muted, "stroke-dasharray": "4 5"}));
  const points = timeline.map((point, index) => [scale.x(index, timeline.length), scale.y(point.cumulativeNet)]);
  svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: row.netExchange >= 0 ? colors.green : colors.red, "stroke-width": 2.3}));
  timeline.forEach((point, index) => {
    const dot = svgElement("circle", {cx: points[index][0], cy: points[index][1], r: 3.5, fill: point.netExchange >= 0 ? colors.green : colors.red, tabindex: 0, class: "interactive", role: "button", "aria-label": `Open game ${point.game}, bilateral exchange ${signed(point.netExchange)}, cumulative ${signed(point.cumulativeNet)}`});
    addTooltip(dot, [`Game ${point.game}`, `Round exchange ${signed(point.netExchange)}`, `Income from team ${formatCurrency(point.incomeFromTeam)} · cost to team ${formatCurrency(point.costToTeam)}`, `Cumulative ${signed(point.cumulativeNet)}`]);
    dot.addEventListener("click", () => selectGame(point.game, {scroll: true}));
    svg.append(dot);
  });
  svg.append(svgElement("text", {x: margin.left, y: height - 19, class: "axis-label"}, `GAME ${timeline[0].game}`));
  svg.append(svgElement("text", {x: width - margin.right, y: height - 19, class: "axis-label", "text-anchor": "end"}, `GAME ${timeline.at(-1).game}`));
  host.append(svg);
}

function renderDossier() {
  const rows = state.overview.trends.opponents;
  const row = rows.find(candidate => candidate.team === state.dossierTeam) || rows[0];
  if (!row) return;
  state.dossierTeam = row.team;
  $("#dossier-team").value = row.team;
  const hero = $("#dossier-hero"); clear(hero);
  hero.append(element("div", {class: "dossier-identity"}, [element("span", {text: "Selected counterparty"}), element("strong", {text: row.team})]));
  const fairDenominator = row.reviewCells.acceptFair.count + row.reviewCells.rejectFair.count;
  const fraudDenominator = row.reviewCells.acceptFraud.count + row.reviewCells.rejectFraud.count;
  [
    ["Net exchange", signed(row.netExchange), `${formatCurrency(row.incomeFromTeam)} paid us · ${formatCurrency(row.costToTeam)} cost us`],
    ["Accepts Oasis", formatPercent(row.acceptRateAgainstUs), `${row.reviewDecisions} review decisions`],
    ["Wrong fair rejects", formatPercent(row.fairRejectRateAgainstUs), `${row.reviewCells.rejectFair.count} / ${fairDenominator} proven-fair reviews`],
    ["Wrong fraud accepts", formatPercent(row.fraudAcceptRateAgainstUs), `${row.reviewCells.acceptFraud.count} / ${fraudDenominator} proven-fraud reviews`],
    ["Charge aggression", row.medianObservedChargeToFloor === null ? "unknown" : `${formatNumber(row.medianObservedChargeToFloor, 2)}×`, `${formatPercent(row.aggressionCoverage)} of ${row.chargeGroups} issued groups observable`],
  ].forEach(([label, value, note]) => hero.append(element("div", {class: "dossier-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
  renderDossierTimeline(row);

  const review = $("#dossier-review-matrix"); clear(review);
  const reviewSpecs = [
    ["acceptFair", "ACCEPT × FAIR"], ["acceptFraud", "ACCEPT × FRAUD"],
    ["rejectFair", "REJECT × FAIR"], ["rejectFraud", "REJECT × FRAUD"],
  ];
  reviewSpecs.forEach(([key, label]) => {
    const cell = row.reviewCells[key];
    review.append(element("div", {class: "dossier-review-cell"}, [element("span", {text: label}), element("strong", {text: formatCurrency(cell.euros)}), element("small", {text: `${cell.count} proven decisions · reviewer settlement EUR`})]));
  });

  const issued = $("#dossier-issue-bars"); clear(issued);
  const total = Math.max(1, row.issuedEvidence.labelled);
  const categories = [
    ["under", "Provably under", colors.amber], ["over", "Provably over", colors.red],
    ["inside", "Inside bracket", colors.green], ["open", "Above floor · open", colors.violet],
    ["unobservable", "Unobservable", colors.muted],
  ];
  categories.forEach(([key, label, color]) => {
    const count = row.issuedEvidence[key];
    const wrap = element("div", {class: "issue-bar"}, [
      element("div", {}, [element("span", {text: label}), element("strong", {text: `${count} · ${formatPercent(count / total)}`})]),
      element("span", {class: "issue-track"}, [element("i")]),
    ]);
    wrap.querySelector("i").style.width = `${count / total * 100}%`;
    wrap.querySelector("i").style.setProperty("--bar-color", color);
    issued.append(wrap);
  });
}

function ruleStateLabel(value) {
  const labels = {
    "at-or-under-floor": "At / under floor",
    "unprovable": "Between evidence",
    "above-ceiling": "Above ceiling",
    "unlabelled": "No bracket",
    "invalid": "Invalid",
  };
  return labels[value] || String(value || "unknown");
}

function evaluatePortfolio(primaryRecords, allRecords, options = {}) {
  const gate = options.gate || "none";
  const source = options.source || "all";
  const direction = options.direction || "any";
  const byItem = new Map();
  allRecords.forEach(row => {
    const key = `${row.game}:${row.item}`;
    if (!byItem.has(key)) byItem.set(key, []);
    byItem.get(key).push(row);
  });

  const metric = (rows, choose) => {
    let items = 0, bestPossible = 0, provenIncome = 0, excluded = 0;
    let atOrUnderFloor = 0, aboveCeiling = 0, unprovable = 0;
    rows.forEach((row, index) => {
      if (row.bestPossible === null || !Number.isFinite(row.bestPossible)) return;
      items += 1;
      bestPossible += row.bestPossible;
      const side = typeof choose === "function" ? choose(row, index) : choose;
      const income = side === "after" ? row.afterProvenIncome : row.beforeProvenIncome;
      const evidenceState = side === "after" ? row.afterState : row.beforeState;
      if (income === null || !Number.isFinite(income)) excluded += 1;
      else provenIncome += income;
      if (evidenceState === "at-or-under-floor") atOrUnderFloor += 1;
      else if (evidenceState === "above-ceiling") aboveCeiling += 1;
      else unprovable += 1;
    });
    return {
      items, bestPossible, provenIncome,
      score: bestPossible > 0 ? provenIncome / bestPossible : null,
      excluded, atOrUnderFloor, aboveCeiling, unprovable,
    };
  };

  const routes = primaryRecords.map(row => {
    const peers = (byItem.get(`${row.game}:${row.item}`) || []).filter(peer => peer.id !== row.id);
    const primarySign = Math.sign(row.aDelta || 0);
    const comparable = primarySign === 0 ? [] : peers.filter(peer => Math.sign(peer.aDelta || 0) !== 0);
    const opposition = comparable.filter(peer => Math.sign(peer.aDelta) !== primarySign);
    const agreement = comparable.filter(peer => Math.sign(peer.aDelta) === primarySign);
    const rowSource = row.source || "unknown";
    const sourcePass = source === "all" || rowSource === source;
    const directionPass = direction === "any" || direction === "raise" && primarySign > 0 || direction === "lower" && primarySign < 0;
    let gatePass = true;
    let reason = "applied";
    if (!sourcePass) reason = "filtered-source";
    else if (!directionPass) reason = "filtered-direction";
    else if (gate === "no-opposition" && opposition.length) { gatePass = false; reason = "blocked-opposition"; }
    else if (gate === "consensus" && (primarySign === 0 || !comparable.length || opposition.length)) { gatePass = false; reason = "blocked-no-consensus"; }
    else if (gate === "no-b-raise" && row.bDelta > 0) { gatePass = false; reason = "blocked-b-raise"; }
    else if (gate === "stable-only" && row.candidateStable !== true) { gatePass = false; reason = "blocked-unstable"; }
    const apply = sourcePass && directionPass && gatePass;
    const beforeIncome = Number.isFinite(row.beforeProvenIncome) ? row.beforeProvenIncome : null;
    const afterIncome = Number.isFinite(row.afterProvenIncome) ? row.afterProvenIncome : null;
    const candidateDelta = beforeIncome !== null && afterIncome !== null ? afterIncome - beforeIncome : null;
    return {
      ...row, apply, reason, peers: peers.length, comparablePeers: comparable.length,
      peerAgreement: agreement.length, peerOpposition: opposition.length,
      candidateDelta, routedDelta: apply ? candidateDelta : 0,
    };
  });
  const routeByKey = new Map(routes.map(row => [`${row.game}:${row.item}`, row]));
  const before = metric(primaryRecords, "before");
  const full = metric(primaryRecords, "after");
  const routed = metric(primaryRecords, row => routeByKey.get(`${row.game}:${row.item}`)?.apply ? "after" : "before");
  return {
    before, full, routed, routes,
    applied: routes.filter(row => row.apply).length,
    fallback: routes.filter(row => !row.apply).length,
    sourceFiltered: routes.filter(row => row.reason === "filtered-source").length,
    directionFiltered: routes.filter(row => row.reason === "filtered-direction").length,
    safetyBlocked: routes.filter(row => row.reason.startsWith("blocked-")).length,
    provableApplied: routes.filter(row => row.apply && Number.isFinite(row.afterProvenIncome)).length,
    bRaisesApplied: routes.filter(row => row.apply && row.bDelta > 0).length,
    hiddenGroupsOnAppliedBRaises: routes.filter(row => row.apply && row.bDelta > 0).reduce((sum, row) => sum + (row.hiddenCharges || 0), 0),
  };
}

function portfolioData() {
  return state.overview?.intelligence?.rules?.portfolios || {rules: [], records: [], overlaps: []};
}

function populatePortfolioControls() {
  const data = portfolioData();
  const ruleSelect = $("#portfolio-rule");
  clear(ruleSelect);
  data.rules.forEach((row, index) => ruleSelect.append(element("option", {
    value: row.id,
    text: `${index === 0 ? "HINDSIGHT LEADER · " : ""}${row.rule} · ${row.uniqueItems} items · ${signed(row.provenIncomeDelta)}`,
  })));
  if (!data.rules.some(row => row.id === state.portfolioRuleId)) state.portfolioRuleId = data.rules[0]?.id || null;
  if (state.portfolioRuleId) ruleSelect.value = state.portfolioRuleId;

  const sourceSelect = $("#portfolio-source");
  const sources = [...new Set(data.records.filter(row => row.id === state.portfolioRuleId).map(row => row.source || "unknown"))].sort();
  clear(sourceSelect);
  sourceSelect.append(element("option", {value: "all", text: "All observed sources"}));
  sources.forEach(value => sourceSelect.append(element("option", {value, text: value})));
  if (!sources.includes(state.portfolioSource)) state.portfolioSource = "all";
  sourceSelect.value = state.portfolioSource;
  $("#portfolio-gate").value = state.portfolioGate;
  $$('[data-portfolio-direction]').forEach(button => {
    const active = button.dataset.portfolioDirection === state.portfolioDirection;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function selectedPortfolioRule() {
  return portfolioData().rules.find(row => row.id === state.portfolioRuleId) || null;
}

function portfolioEvaluation() {
  const data = portfolioData();
  return evaluatePortfolio(
    data.records.filter(row => row.id === state.portfolioRuleId),
    data.records,
    {gate: state.portfolioGate, source: state.portfolioSource, direction: state.portfolioDirection},
  );
}

function renderPortfolioFunnel(rule, evaluation) {
  const host = $("#portfolio-funnel"); clear(host);
  if (!rule) return;
  const stages = [
    ["Paired firings", rule.pairedFirings, `${rule.duplicateFirings} repeated beyond one/item`],
    ["Unique candidates", rule.uniqueItems, `${rule.unstableItems} changed across repeats`],
    ["Sanctioned floor", evaluation.before.items, `${rule.uniqueItems - evaluation.before.items} items unlabelled`],
    ["Routed to candidate", evaluation.applied, `${evaluation.fallback} fall back to before`],
    ["Candidate side proven", evaluation.provableApplied, `${evaluation.applied - evaluation.provableApplied} routed outcomes excluded`],
  ];
  stages.forEach(([label, value, note]) => host.append(element("div", {class: "portfolio-stage"}, [element("span", {text: label}), element("strong", {text: formatNumber(value)}), element("small", {text: note})])));
}

function renderPortfolioKpis(rule, evaluation) {
  const host = $("#portfolio-kpis"); clear(host);
  if (!rule) return;
  const routedDelta = evaluation.routed.provenIncome - evaluation.before.provenIncome;
  const specs = [
    ["Primary rule", rule.rule, "retrospectively ranked by deduped candidate Δ"],
    ["Dedupe", `${rule.uniqueItems} / ${rule.pairedFirings}`, `${rule.duplicateFirings} repeat firings removed · latest seq retained`],
    ["Before SCORE", formatPercent(evaluation.before.score), `${formatCurrency(evaluation.before.provenIncome, true)} / ${formatCurrency(evaluation.before.bestPossible, true)} fixed best`],
    ["Full candidate", formatPercent(evaluation.full.score), `${evaluation.full.excluded} excluded · no routing gate`],
    ["Routed SCORE", formatPercent(evaluation.routed.score), `${evaluation.routed.excluded} excluded · ${evaluation.applied} items changed`],
    ["Routed proven-income Δ", signed(routedDelta), `metric EUR on ${evaluation.routed.items} labelled primary items`],
    ["Applied b raises", formatNumber(evaluation.bRaisesApplied), `${evaluation.hiddenGroupsOnAppliedBRaises} hidden opposing charge groups · amounts unpriced`],
  ];
  specs.forEach(([label, value, note], index) => host.append(metricCard(label, value, note, index === 5 ? routedDelta > 0 ? "positive" : routedDelta < 0 ? "negative" : "" : "")));
}

function renderPortfolioScore(evaluation) {
  const host = $("#portfolio-score-chart"); clear(host);
  const rows = [
    ["BEFORE", evaluation.before, colors.muted],
    ["FULL CANDIDATE", evaluation.full, colors.violet],
    ["ROUTED", evaluation.routed, evaluation.routed.score >= evaluation.before.score ? colors.green : colors.red],
  ];
  rows.forEach(([label, metric, color]) => {
    const bar = element("div", {class: "portfolio-score-row"}, [
      element("div", {class: "portfolio-score-label"}, [element("strong", {text: label}), element("span", {text: `${formatCurrency(metric.provenIncome, true)} proven · ${metric.excluded} excluded`})]),
      element("div", {class: "portfolio-score-track", role: "meter", "aria-label": `${label} score`, "aria-valuemin": "0", "aria-valuemax": "1", "aria-valuenow": safeNumber(metric.score)}, [element("i")]),
      element("strong", {class: "portfolio-score-value", text: formatPercent(metric.score)}),
    ]);
    bar.querySelector("i").style.width = `${clamp(safeNumber(metric.score) * 100, 0, 100)}%`;
    bar.querySelector("i").style.backgroundColor = color;
    host.append(bar);
  });
  host.append(element("p", {class: "portfolio-score-denominator", text: `Every bar uses the same ${formatCurrency(evaluation.before.bestPossible, true)} best-possible denominator across ${evaluation.before.items} labelled primary items.`}));
}

function renderPortfolioRouteAnatomy(evaluation) {
  const host = $("#portfolio-route-anatomy"); clear(host);
  const rows = [
    ["Candidate applied", evaluation.applied, "after decision selected"],
    ["Production fallback", evaluation.fallback, "before decision retained"],
    ["Source filtered", evaluation.sourceFiltered, "observable source mismatch"],
    ["Direction filtered", evaluation.directionFiltered, "observable Δa mismatch"],
    ["Safety blocked", evaluation.safetyBlocked, "gate rejected candidate"],
    ["b raises applied", evaluation.bRaisesApplied, `${evaluation.hiddenGroupsOnAppliedBRaises} hidden groups unpriced`],
  ];
  rows.forEach(([label, value, note], index) => host.append(element("div", {class: `portfolio-route-row ${index === 0 ? "apply" : index === 1 ? "fallback" : ""}`}, [element("span", {text: label}), element("strong", {text: formatNumber(value)}), element("small", {text: note})])));
}

function renderPortfolioGateSweep() {
  const data = portfolioData();
  const primary = data.records.filter(row => row.id === state.portfolioRuleId);
  const gates = [
    ["none", "No gate", "maximum candidate coverage"],
    ["no-opposition", "Block opposition", "fallback when a peer moves a the other way"],
    ["consensus", "Require consensus", "at least one peer; every direction agrees"],
    ["no-b-raise", "Never raise b", "zero newly crossed hidden groups by construction"],
    ["stable-only", "Block changed repeats", "fallback only when repeated candidates changed"],
  ];
  const rows = gates.map(([gate, label, note]) => ({
    gate, label, note,
    evaluation: evaluatePortfolio(primary, data.records, {gate, source: state.portfolioSource, direction: state.portfolioDirection}),
  }));
  const host = $("#portfolio-gate-sweep"); clear(host);
  rows.forEach(row => {
    const delta = row.evaluation.routed.provenIncome - row.evaluation.before.provenIncome;
    const button = element("button", {type: "button", class: `portfolio-gate-card ${row.gate === state.portfolioGate ? "active" : ""}`, "aria-pressed": String(row.gate === state.portfolioGate)}, [
      element("span", {text: row.label}),
      element("strong", {text: formatPercent(row.evaluation.routed.score)}),
      element("small", {text: `${row.evaluation.applied} applied · ${signed(delta)} metric EUR`}),
      element("em", {text: `${row.evaluation.hiddenGroupsOnAppliedBRaises} hidden groups · ${row.note}`}),
    ]);
    button.addEventListener("click", () => {
      state.portfolioGate = row.gate;
      $("#portfolio-gate").value = row.gate;
      renderPortfolioComposer();
      syncInvestigationUrl("strategy");
    });
    host.append(button);
  });
  const body = $("#portfolio-gate-data-table"); clear(body);
  rows.forEach(row => {
    const metric = row.evaluation.routed;
    const delta = metric.provenIncome - row.evaluation.before.provenIncome;
    body.append(element("tr", {}, [element("td", {text: row.label}), element("td", {text: formatNumber(row.evaluation.applied)}), element("td", {text: formatPercent(metric.score)}), element("td", {class: "money", text: signed(delta)}), element("td", {text: formatNumber(metric.excluded)}), element("td", {text: formatNumber(row.evaluation.bRaisesApplied)}), element("td", {text: formatNumber(row.evaluation.hiddenGroupsOnAppliedBRaises)})]));
  });
}

function portfolioTemporalRows(evaluation) {
  const grouped = new Map();
  evaluation.routes.forEach(row => {
    if (row.bestPossible === null || !Number.isFinite(row.bestPossible)) return;
    if (!grouped.has(row.game)) grouped.set(row.game, {game: row.game, items: 0, applied: 0, bestPossible: 0, beforeIncome: 0, routedIncome: 0, excluded: 0});
    const game = grouped.get(row.game);
    game.items += 1;
    game.applied += Number(row.apply);
    game.bestPossible += row.bestPossible;
    if (Number.isFinite(row.beforeProvenIncome)) game.beforeIncome += row.beforeProvenIncome;
    const chosenIncome = row.apply ? row.afterProvenIncome : row.beforeProvenIncome;
    if (Number.isFinite(chosenIncome)) game.routedIncome += chosenIncome;
    else game.excluded += 1;
  });
  let cumulativeDelta = 0;
  return [...grouped.values()].sort((left, right) => left.game - right.game).map(row => {
    row.beforeScore = row.bestPossible > 0 ? row.beforeIncome / row.bestPossible : null;
    row.routedScore = row.bestPossible > 0 ? row.routedIncome / row.bestPossible : null;
    row.delta = row.routedIncome - row.beforeIncome;
    cumulativeDelta += row.delta;
    row.cumulativeDelta = cumulativeDelta;
    return row;
  });
}

function renderPortfolioTemporal(evaluation) {
  const rows = portfolioTemporalRows(evaluation);
  const host = $("#portfolio-temporal-chart"); clear(host);
  const summary = $("#portfolio-temporal-summary"); clear(summary);
  const table = $("#portfolio-temporal-data-table"); clear(table);
  if (!rows.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No labelled games exist for this primary candidate."})]));
    return;
  }
  const totalDelta = rows.at(-1).cumulativeDelta;
  const absoluteDelta = rows.reduce((sum, row) => sum + Math.abs(row.delta), 0);
  const worstConcentration = absoluteDelta ? Math.max(...rows.map(row => Math.abs(row.delta))) / absoluteDelta : 0;
  const recentDelta = rows.slice(-10).reduce((sum, row) => sum + row.delta, 0);
  const specs = [
    ["Positive games", rows.filter(row => row.delta > 0).length, `${rows.filter(row => row.delta < 0).length} negative · ${rows.filter(row => row.delta === 0).length} flat`],
    ["Median game Δ", signed(medianNumber(rows.map(row => row.delta)) || 0), "metric EUR · per candidate-affected game"],
    ["Recent ≤10 Δ", signed(recentDelta), `${Math.min(10, rows.length)} latest affected games`],
    ["Largest-game share", formatPercent(worstConcentration), "share of absolute per-game routed Δ"],
  ];
  specs.forEach(([label, value, note]) => summary.append(element("div", {class: "portfolio-temporal-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));

  const width = 1040, height = 370, margin = {left: 72, right: 86, top: 40, bottom: 54};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const maxDelta = Math.max(1, ...rows.map(row => Math.abs(row.delta))) * 1.08;
  const cumulativeValues = [0, ...rows.map(row => row.cumulativeDelta)];
  const cumulativeMin = Math.min(...cumulativeValues), cumulativeMax = Math.max(...cumulativeValues);
  const cumulativeSpan = Math.max(1, cumulativeMax - cumulativeMin);
  const x = index => margin.left + (index + .5) / rows.length * plotW;
  const yDelta = value => margin.top + (maxDelta - value) / (2 * maxDelta) * plotH;
  const yCumulative = value => margin.top + (cumulativeMax - value) / cumulativeSpan * plotH;
  const zero = yDelta(0);
  const svg = svgRoot(width, height, `Per-game routed proven-income delta and cumulative delta across ${rows.length} affected games`);
  [-maxDelta, 0, maxDelta].forEach(value => {
    const y = yDelta(value);
    svg.append(svgElement("line", {x1: margin.left, y1: y, x2: width - margin.right, y2: y, stroke: value === 0 ? colors.cyan : colors.grid, "stroke-width": value === 0 ? 1.3 : 1, "stroke-dasharray": value === 0 ? "5 5" : "0"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: y + 3, class: "axis-label", "text-anchor": "end"}, value === 0 ? "€0" : signed(value)));
  });
  const step = plotW / rows.length;
  rows.forEach((row, index) => {
    const y = yDelta(row.delta);
    const bar = svgElement("rect", {x: x(index) - Math.min(8, step * .34), y: Math.min(y, zero), width: Math.max(2, Math.min(16, step * .68)), height: Math.max(1, Math.abs(zero - y)), rx: 1.5, fill: row.delta >= 0 ? colors.green : colors.red, "fill-opacity": .72, tabindex: 0, class: "interactive", role: "button", "aria-label": `Game ${row.game}, routed delta ${signed(row.delta)}`});
    addTooltip(bar, [`Game ${row.game} · ${row.items} labelled primary items`, `Routed ${row.applied} · ${row.excluded} excluded`, `Before ${formatPercent(row.beforeScore)} · routed ${formatPercent(row.routedScore)}`, `Δ ${signed(row.delta)} · cumulative ${signed(row.cumulativeDelta)}`]);
    bar.addEventListener("click", () => selectGame(row.game, {scroll: true}));
    svg.append(bar);
  });
  const cumulativePoints = rows.map((row, index) => [x(index), yCumulative(row.cumulativeDelta)]);
  svg.append(svgElement("path", {d: linePath(cumulativePoints), fill: "none", stroke: colors.violet, "stroke-width": 2.2}));
  cumulativePoints.forEach(([cx, cy], index) => svg.append(svgElement("circle", {cx, cy, r: 2.5, fill: colors.violet, "fill-opacity": index === cumulativePoints.length - 1 ? 1 : .45})));
  [cumulativeMin, cumulativeMax].forEach(value => svg.append(svgElement("text", {x: width - margin.right + 8, y: yCumulative(value) + 3, fill: colors.violet, "font-family": "var(--mono)", "font-size": 8}, signed(value))));
  const tickEvery = Math.max(1, Math.ceil(rows.length / 9));
  rows.forEach((row, index) => {
    if (index % tickEvery && index !== rows.length - 1) return;
    svg.append(svgElement("text", {x: x(index), y: height - 29, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.green, "font-family": "var(--mono)", "font-size": 8}, "BARS · PER-GAME ROUTED Δ"));
  svg.append(svgElement("text", {x: width - margin.right, y: 18, fill: colors.violet, "font-family": "var(--mono)", "font-size": 8, "text-anchor": "end"}, `LINE · CUMULATIVE ${signed(totalDelta)}`));
  host.append(svg);

  rows.forEach(row => table.append(element("tr", {}, [element("td", {text: `game ${row.game}`}), element("td", {text: formatNumber(row.items)}), element("td", {text: formatNumber(row.applied)}), element("td", {class: "money", text: formatCurrency(row.bestPossible)}), element("td", {text: formatPercent(row.beforeScore)}), element("td", {text: formatPercent(row.routedScore)}), element("td", {class: "money", text: signed(row.delta)}), element("td", {class: "money", text: signed(row.cumulativeDelta)})])));
}

function renderPortfolioReadiness(rule, evaluation) {
  const host = $("#portfolio-readiness"); clear(host);
  if (!rule) {
    $("#portfolio-firewall-status").textContent = "CLOSED · NO PAIRED CANDIDATE";
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No paired SHADOW candidate can be evaluated."})]));
    return;
  }
  const temporal = portfolioTemporalRows(evaluation);
  const positiveGames = temporal.filter(row => row.delta > 0).length;
  const negativeGames = temporal.filter(row => row.delta < 0).length;
  const delta = evaluation.routed.provenIncome - evaluation.before.provenIncome;
  const denominatorMatches = evaluation.before.items === evaluation.full.items && evaluation.before.items === evaluation.routed.items && evaluation.before.bestPossible === evaluation.full.bestPossible && evaluation.before.bestPossible === evaluation.routed.bestPossible;
  const specs = [
    ["verified", "Item-level denominator", `${rule.uniqueItems} unique = ${rule.pairedFirings} firings − ${rule.duplicateFirings} repeats`],
    [denominatorMatches ? "verified" : "block", "Fixed denominator", denominatorMatches ? `${evaluation.before.items} labelled items · ${formatCurrency(evaluation.before.bestPossible, true)} across every arm` : "before/full/routed denominator mismatch"],
    [delta > 0 ? "support" : "block", "Retrospective metric sign", `${signed(delta)} proven-income Δ · supportive only, not causal`],
    [positiveGames > negativeGames ? "support" : "warning", "Temporal breadth", `${positiveGames} positive / ${negativeGames} negative affected games · not a holdout`],
    [evaluation.hiddenGroupsOnAppliedBRaises === 0 ? "verified" : "block", "Unpriced b exposure", evaluation.hiddenGroupsOnAppliedBRaises === 0 ? "zero hidden groups associated with applied b raises" : `${evaluation.hiddenGroupsOnAppliedBRaises} hidden groups associated with ${evaluation.bRaisesApplied} applied b raises`],
    ["unresolved", "Strict temporal evaluation", "train games 1…k, test only k+1…n has not been established by this surface"],
    ["unresolved", "Expensive-item precision", "≥ 0.90 routing precision must be measured against sanctioned proof masks"],
    ["unresolved", "Deadline budget", "per-item p50/p95 and worst-case 39-item wall time are not present in the logs"],
    ["unresolved", "Provider failure fallback", "price-book abstention on timeout/outage is not validated by retrospective candidates"],
  ];
  const blocks = specs.filter(([status]) => status === "block").length;
  const unresolved = specs.filter(([status]) => status === "unresolved").length;
  $("#portfolio-firewall-status").textContent = `CLOSED · ${blocks} BLOCK${blocks === 1 ? "" : "S"} · ${unresolved} UNRESOLVED`;
  specs.forEach(([status, label, note]) => host.append(element("div", {class: `portfolio-readiness-card ${status}`}, [element("span", {class: "readiness-state", text: status}), element("strong", {text: label}), element("small", {text: note})])));
}

function selectPortfolioRule(ruleId) {
  state.portfolioRuleId = ruleId;
  state.portfolioSource = "all";
  populatePortfolioControls();
  renderPortfolioComposer();
  syncInvestigationUrl("strategy");
}

function renderPortfolioOverlap() {
  const data = portfolioData();
  const host = $("#portfolio-overlap-matrix"); clear(host);
  const rules = data.rules;
  host.style.gridTemplateColumns = `minmax(128px,1.25fr) repeat(${rules.length}, minmax(76px,1fr))`;
  host.append(element("div", {class: "portfolio-matrix-axis", text: "PRIMARY ↓ / PEER →"}));
  rules.forEach(rule => host.append(element("div", {class: "portfolio-matrix-axis", title: rule.rule, text: rule.rule.replaceAll("_", " ")})));
  const findOverlap = (left, right) => data.overlaps.find(row => row.left === left && row.right === right || row.left === right && row.right === left);
  rules.forEach(primary => {
    const label = element("button", {type: "button", class: `portfolio-matrix-rule ${primary.id === state.portfolioRuleId ? "active" : ""}`, text: primary.rule.replaceAll("_", " "), "aria-pressed": String(primary.id === state.portfolioRuleId)});
    label.addEventListener("click", () => selectPortfolioRule(primary.id));
    host.append(label);
    rules.forEach(peer => {
      if (primary.id === peer.id) {
        const cell = element("button", {type: "button", class: "portfolio-matrix-cell diagonal", "aria-label": `${primary.rule}: ${primary.uniqueItems} unique item candidates`, title: `${primary.rule} · ${primary.uniqueItems} unique items`}, [element("strong", {text: formatNumber(primary.uniqueItems)}), element("span", {text: "unique"})]);
        cell.addEventListener("click", () => selectPortfolioRule(primary.id));
        host.append(cell);
        return;
      }
      const overlap = findOverlap(primary.id, peer.id);
      const oppositionRate = overlap?.directionComparable ? overlap.directionOpposition / overlap.directionComparable : 0;
      const cell = element("button", {type: "button", class: "portfolio-matrix-cell", "aria-label": overlap ? `${primary.rule} and ${peer.rule}: ${overlap.items} shared items, ${formatPercent(oppositionRate)} opposite among ${overlap.directionComparable} direction-comparable items` : `${primary.rule} and ${peer.rule}: no shared items`}, [element("strong", {text: formatNumber(overlap?.items || 0)}), element("span", {text: overlap?.directionComparable ? `${formatPercent(oppositionRate, 0)} oppose` : "no signal"})]);
      cell.style.backgroundColor = `rgba(239,106,103,${.025 + oppositionRate * .22})`;
      cell.addEventListener("click", () => selectPortfolioRule(primary.id));
      host.append(cell);
    });
  });

  const body = $("#portfolio-overlap-data-table"); clear(body);
  data.overlaps.forEach(row => {
    const left = data.rules.find(rule => rule.id === row.left)?.rule || row.left;
    const right = data.rules.find(rule => rule.id === row.right)?.rule || row.right;
    body.append(element("tr", {}, [element("td", {text: left}), element("td", {text: right}), element("td", {text: formatNumber(row.items)}), element("td", {text: formatNumber(row.directionComparable)}), element("td", {text: formatNumber(row.directionOpposition)}), element("td", {text: formatPercent(row.directionAgreementRate)})]));
  });
}

function renderPortfolioLedger(evaluation) {
  const body = $("#portfolio-ledger-table"); clear(body);
  const reasonLabels = {
    applied: "APPLY CANDIDATE", "filtered-source": "FALLBACK · SOURCE", "filtered-direction": "FALLBACK · DIRECTION",
    "blocked-opposition": "BLOCK · OPPOSITION", "blocked-no-consensus": "BLOCK · NO CONSENSUS",
    "blocked-b-raise": "BLOCK · b RAISE", "blocked-unstable": "BLOCK · UNSTABLE",
  };
  const rows = [...evaluation.routes].sort((a, b) => Math.abs(b.candidateDelta ?? -1) - Math.abs(a.candidateDelta ?? -1) || b.hiddenCharges - a.hiddenCharges || a.game - b.game || a.item - b.item);
  $("#portfolio-ledger-count").textContent = `${rows.length} unique item candidates · latest-seq policy`;
  rows.slice(0, 180).forEach(row => {
    const open = element("button", {type: "button", class: "table-link", text: `game ${row.game} item ${row.item}`});
    open.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    const peerSignal = row.comparablePeers ? `${row.peerAgreement} agree · ${row.peerOpposition} oppose` : `${row.peers} peers · no directional signal`;
    body.append(element("tr", {class: row.apply ? "portfolio-ledger-applied" : ""}, [
      element("td", {}, [open, element("small", {class: "table-subline", text: row.repeatFirings > 1 ? `${row.repeatFirings} repeats · ${row.candidateStable ? "stable" : "changed"}` : "one firing"})]),
      element("td", {}, [element("span", {class: `route-pill ${row.apply ? "applied" : "fallback"}`, text: reasonLabels[row.reason] || row.reason})]),
      element("td", {class: "money", text: pairText(row.before)}),
      element("td", {class: "money", text: pairText(row.after)}),
      element("td", {text: `${ruleStateLabel(row.beforeState)} → ${ruleStateLabel(row.afterState)}`}),
      element("td", {class: "money", text: row.candidateDelta === null ? "excluded / unpriced" : signed(row.candidateDelta)}),
      element("td", {text: peerSignal}),
      element("td", {text: `${signed(row.bDelta)} · ${row.hiddenCharges || 0} hidden`}),
    ]));
  });
}

function renderPortfolioComposer() {
  const rule = selectedPortfolioRule();
  const evaluation = portfolioEvaluation();
  renderPortfolioFunnel(rule, evaluation);
  renderPortfolioKpis(rule, evaluation);
  renderPortfolioScore(evaluation);
  renderPortfolioRouteAnatomy(evaluation);
  renderPortfolioGateSweep();
  renderPortfolioTemporal(evaluation);
  renderPortfolioReadiness(rule, evaluation);
  renderPortfolioOverlap();
  renderPortfolioLedger(evaluation);
}

async function copyPortfolioReceipt() {
  const rule = selectedPortfolioRule();
  const evaluation = portfolioEvaluation();
  if (!rule) {
    toast("No paired SHADOW candidate is available for a handoff receipt.");
    return;
  }
  const receipt = {
    schema: 1,
    status: "offline-retrospective-evidence-only",
    primaryRule: rule.rule,
    primaryRuleId: rule.id,
    dedupePolicy: portfolioData().dedupePolicy,
    route: {source: state.portfolioSource, chargeDirection: state.portfolioDirection, safetyGate: state.portfolioGate},
    denominator: {unit: "deduplicated-labelled-primary-item", items: evaluation.routed.items, bestPossibleEur: evaluation.routed.bestPossible},
    evidence: {
      uniqueCandidates: rule.uniqueItems, applied: evaluation.applied,
      beforeScore: evaluation.before.score, fullCandidateScore: evaluation.full.score,
      routedScore: evaluation.routed.score,
      routedProvenIncomeEur: evaluation.routed.provenIncome,
      routedProvenIncomeDeltaEur: evaluation.routed.provenIncome - evaluation.before.provenIncome,
      excluded: evaluation.routed.excluded,
      bRaisesApplied: evaluation.bRaisesApplied,
      hiddenOpposingChargeGroupsUnpriced: evaluation.hiddenGroupsOnAppliedBRaises,
    },
    caveats: [
      "not tournament score or realised impact",
      "not a temporal train/test backtest",
      "thresholds used only for retrospective evaluation",
      "candidate availability and latency not established",
      "expensive-item routing precision at or above 0.90 not established",
      "provider failure fallback not established",
      "hidden opposing charge amounts remain unpriced",
    ],
  };
  try {
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    toast("Claim-free portfolio handoff receipt copied. It contains rule identifiers, aggregate evidence, and caveats only.");
  } catch (error) {
    toast(`Portfolio receipt was not copied: ${error?.message || "clipboard access blocked"}. No file was written.`);
  }
}

function populateRuleControl() {
  const select = $("#rule-select"); clear(select);
  const rules = state.overview.intelligence.rules.rules;
  rules.forEach(row => select.append(element("option", {
    value: row.id,
    text: `${row.shadow ? "SHADOW" : "ACTIVE"} · ${row.rule} · ${row.paired}/${row.firings} paired`,
  })));
  if (!rules.some(row => row.id === state.selectedRuleId)) {
    state.selectedRuleId = rules.find(row => row.shadow && row.paired)?.id || rules[0]?.id || null;
  }
  if (state.selectedRuleId) select.value = state.selectedRuleId;
}

function selectedRule() {
  return state.overview.intelligence.rules.rules.find(row => row.id === state.selectedRuleId) || null;
}

function renderRuleFunnel(rule) {
  const host = $("#rule-funnel"); clear(host);
  if (!rule) return;
  const stages = [
    ["Logged firings", rule.firings, `${rule.games} games`],
    ["Paired from / to", rule.paired, `${formatPercent(rule.paired / Math.max(1, rule.firings))} of firings`],
    ["Sanctioned bracket", rule.after.items, `${rule.paired - rule.after.items} paired without a floor`],
    ["Candidate side proven", rule.after.items - rule.after.excluded, `${rule.after.excluded} excluded / unprovable`],
  ];
  stages.forEach(([label, value, note]) => host.append(element("div", {class: "rule-stage"}, [element("span", {text: label}), element("strong", {text: formatNumber(value)}), element("small", {text: note})])));
}

function renderRuleKpis(rule) {
  const host = $("#rule-kpis"); clear(host);
  if (!rule) return;
  const incomeDelta = rule.provenIncomeDelta;
  const specs = [
    ["Variant", rule.shadow ? "SHADOW" : "ACTIVE", rule.paired ? "counterfactual pairs logged" : "count-only · no from/to pairs"],
    ["Before SCORE", rule.before.score === null ? "unavailable" : formatPercent(rule.before.score), `${formatCurrency(rule.before.provenIncome, true)} proven income / ${formatCurrency(rule.before.bestPossible, true)} fixed best`],
    ["Candidate SCORE", rule.after.score === null ? "unavailable" : formatPercent(rule.after.score), `${formatCurrency(rule.after.provenIncome, true)} proven income · ${rule.after.excluded} excluded`],
    ["Proven-income Δ", rule.paired ? signed(incomeDelta) : "unavailable", "metric EUR on this rule-firing denominator · not realised impact"],
    ["b movement", `${rule.limitRaises} ↑ / ${rule.limitLowers} ↓`, `median ${rule.medianLimitDelta === null ? "unknown" : signed(rule.medianLimitDelta)}`],
    ["Unpriced on b raises", formatNumber(rule.hiddenChargesOnLimitRaises), `${rule.limitRaises} raising firings · opposing charge groups with hidden amounts`],
  ];
  specs.forEach(([label, value, note], index) => host.append(metricCard(label, value, note, index === 3 && incomeDelta < 0 ? "negative" : index === 3 && incomeDelta > 0 ? "positive" : "")));
}

function renderRuleIncome(rule) {
  const host = $("#rule-income-chart"); clear(host);
  if (!rule?.paired || rule.before.score === null || rule.after.score === null) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No paired from/to evidence was logged for this active rule."})]));
    return;
  }
  const width = 520, height = 330, margin = {left: 120, right: 32, top: 42, bottom: 38};
  const svg = svgRoot(width, height, `Before and candidate proven-income score for ${rule.rule}`);
  const rows = [["BEFORE", rule.before.score, colors.muted], ["CANDIDATE", rule.after.score, rule.after.score >= rule.before.score ? colors.green : colors.red]];
  [0, .25, .5, .75, 1].forEach(value => {
    const x = margin.left + value * (width - margin.left - margin.right);
    svg.append(svgElement("line", {x1: x, y1: margin.top - 12, x2: x, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("text", {x, y: 23, class: "axis-label", "text-anchor": "middle"}, formatPercent(value, 0)));
  });
  rows.forEach(([label, value, color], index) => {
    const y = margin.top + 48 + index * 100;
    const barWidth = value * (width - margin.left - margin.right);
    svg.append(svgElement("text", {x: margin.left - 12, y: y + 4, class: "axis-label", "text-anchor": "end"}, label));
    svg.append(svgElement("rect", {x: margin.left, y: y - 14, width: width - margin.left - margin.right, height: 28, rx: 5, fill: colors.grid}));
    svg.append(svgElement("rect", {x: margin.left, y: y - 14, width: barWidth, height: 28, rx: 5, fill: color, "fill-opacity": .78}));
    svg.append(svgElement("text", {x: Math.min(width - margin.right - 4, margin.left + barWidth + 8), y: y + 4, fill: color, "font-family": "var(--mono)", "font-size": 11}, formatPercent(value)));
  });
  svg.append(svgElement("text", {x: margin.left, y: height - 12, class: "axis-label"}, `${rule.after.items} labelled paired firings · fixed best ${formatCurrency(rule.after.bestPossible, true)}`));
  host.append(svg);
}

function renderRuleTransitions(rule) {
  const host = $("#rule-transition-matrix"); clear(host);
  const states = ["at-or-under-floor", "unprovable", "above-ceiling"];
  const counts = new Map((rule?.transitions || []).map(row => [`${row.from}>${row.to}`, row.items]));
  host.append(element("div", {class: "transition-axis", text: "FROM ↓ / TO →"}));
  states.forEach(value => host.append(element("div", {class: "transition-axis", text: ruleStateLabel(value)})));
  states.forEach(from => {
    host.append(element("div", {class: "transition-axis", text: ruleStateLabel(from)}));
    states.forEach(to => {
      const key = `${from}>${to}`;
      const count = counts.get(key) || 0;
      if (!count) {
        host.append(element("div", {class: "transition-cell"}, [element("strong", {text: "0"}), element("span", {text: "firings"})]));
        return;
      }
      const active = state.ruleTransition === key;
      const button = element("button", {type: "button", class: `transition-cell ${active ? "active" : ""}`, "aria-pressed": String(active), "aria-label": `${count} firings moved from ${ruleStateLabel(from)} to ${ruleStateLabel(to)}`}, [element("strong", {text: count}), element("span", {text: "firings"})]);
      button.addEventListener("click", () => { state.ruleTransition = active ? "all" : key; renderRuleTransitions(rule); renderRuleRecords(rule); });
      host.append(button);
    });
  });
}

function renderRuleLimitBuckets(rule) {
  const host = $("#rule-limit-buckets"); clear(host);
  if (!rule?.bucketLimitMoves?.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No paired, bracketed b movements are available."})]));
    return;
  }
  host.append(element("div", {class: "rule-limit-policy"}, [
    element("strong", {text: "Measured maximin constraint · not this rule's result"}),
    element("span", {text: "Raise b: below 400 adverse · 400–1200 conditional (~2.1× fraud-size break-even) · 1200+ positive through 4× the observed fraud mean."}),
  ]));
  const regimes = {
    "0–50": {tone: "danger", label: "raise b · catastrophic regime"},
    "50–400": {tone: "danger", label: "raise b · adverse regime"},
    "400–1200": {tone: "caution", label: "raise b · conditional regime"},
    "1200+": {tone: "favourable", label: "raise b · maximin-positive regime"},
  };
  rule.bucketLimitMoves.forEach(row => {
    const total = Math.max(1, row.items);
    const regime = regimes[row.bucket];
    const track = element("span", {class: "rule-limit-track", "aria-label": `${row.bucket}: ${row.raise} acceptance-limit raises, ${row.lower} lowers, ${row.same} unchanged`}, [element("i", {class: `raise ${regime?.tone || ""}`}), element("i", {class: "lower"}), element("i", {class: "same"})]);
    track.children[0].style.width = `${row.raise / total * 100}%`;
    track.children[1].style.width = `${row.lower / total * 100}%`;
    track.children[2].style.width = `${row.same / total * 100}%`;
    host.append(element("div", {class: "rule-limit-row"}, [
      element("div", {class: "rule-limit-meta"}, [element("strong", {text: row.bucket}), element("span", {text: `${row.raise} raise · ${row.lower} lower · ${row.same} same`}), element("span", {class: `rule-regime ${regime?.tone || ""}`, text: regime?.label || "raise b · unclassified"})]),
      track,
      element("div", {class: "rule-limit-meta"}, [element("span", {text: `median Δb ${row.medianDelta === null ? "unknown" : signed(row.medianDelta)}`}), element("span", {text: `${row.hiddenChargesOnRaises} opposing charge groups on raises`}), element("span", {text: "amounts unpriced"})]),
    ]));
  });
}

function renderRuleTimeline(rule) {
  const host = $("#rule-timeline-chart"); clear(host);
  const rows = (rule?.timeline || []).filter(row => row.beforeScore !== null || row.afterScore !== null);
  if (!rows.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No per-game paired score evidence is available for this rule."})]));
    return;
  }
  const width = 1040, height = 370, margin = {left: 66, right: 28, top: 35, bottom: 52};
  const max = Math.max(.1, ...rows.flatMap(row => [safeNumber(row.beforeScore), safeNumber(row.afterScore)])) * 1.08;
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const x = index => margin.left + (rows.length <= 1 ? plotW / 2 : index / (rows.length - 1) * plotW);
  const y = value => margin.top + (max - safeNumber(value)) / max * plotH;
  const svg = svgRoot(width, height, `${rule.rule} before and candidate proven-income scores by game`);
  for (let tick = 0; tick <= 4; tick++) {
    const value = max * (1 - tick / 4), position = margin.top + plotH * tick / 4;
    svg.append(svgElement("line", {x1: margin.left, y1: position, x2: width - margin.right, y2: position, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 8, y: position + 3, class: "axis-label", "text-anchor": "end"}, formatPercent(value, 0)));
  }
  const beforePoints = rows.map((row, index) => [x(index), y(row.beforeScore)]);
  const afterPoints = rows.map((row, index) => [x(index), y(row.afterScore)]);
  svg.append(svgElement("path", {d: linePath(beforePoints), fill: "none", stroke: colors.muted, "stroke-width": 1.7, "stroke-dasharray": "5 5"}));
  svg.append(svgElement("path", {d: linePath(afterPoints), fill: "none", stroke: colors.violet, "stroke-width": 2.2}));
  rows.forEach((row, index) => {
    const point = svgElement("circle", {cx: afterPoints[index][0], cy: afterPoints[index][1], r: 4, fill: row.provenIncomeDelta >= 0 ? colors.green : colors.red, tabindex: 0});
    addTooltip(point, [`Game ${row.game}`, `Before ${formatPercent(row.beforeScore)} · candidate ${formatPercent(row.afterScore)}`, `Proven-income delta ${signed(row.provenIncomeDelta)} on firing denominator`, `${row.afterExcluded} candidate exclusions · b ${row.bRaises} up / ${row.bLowers} down`]);
    svg.append(point);
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.muted, "font-family": "var(--mono)", "font-size": 8}, "BEFORE · DASHED"));
  svg.append(svgElement("text", {x: margin.left + 105, y: 18, fill: colors.violet, "font-family": "var(--mono)", "font-size": 8}, "CANDIDATE · SOLID"));
  svg.append(svgElement("text", {x: margin.left, y: height - 20, class: "axis-label"}, `GAME ${rows[0].game}`));
  svg.append(svgElement("text", {x: width - margin.right, y: height - 20, class: "axis-label", "text-anchor": "end"}, `GAME ${rows.at(-1).game}`));
  host.append(svg);
}

function ruleBracket(row) {
  if (row.tLo === null || row.tLo === undefined) return "no sanctioned bracket";
  return row.tHi === null ? `[${formatCurrency(row.tLo)}, ceiling open]` : `[${formatCurrency(row.tLo)}, ${formatCurrency(row.tHi)}]`;
}

function renderRuleRecords(rule) {
  const all = state.overview.intelligence.rules.records.filter(row => row.id === rule?.id);
  const rows = all.filter(row => state.ruleTransition === "all" || `${row.beforeState}>${row.afterState}` === state.ruleTransition)
    .sort((a, b) => Math.abs(b.aDelta) + Math.abs(b.bDelta) - Math.abs(a.aDelta) - Math.abs(a.bDelta));
  $("#rule-record-count").textContent = `${rows.length} / ${all.length} paired firings`;
  const list = $("#rule-record-list"); clear(list);
  rows.slice(0, 40).forEach((row, index) => {
    const button = element("button", {type: "button", class: "rule-record-row"}, [
      element("span", {text: `#${index + 1}`}),
      element("span", {}, [element("strong", {text: `game ${row.game} item ${row.item}`}), element("small", {text: `${ruleStateLabel(row.beforeState)} → ${ruleStateLabel(row.afterState)}`})]),
      element("span", {text: `Δa ${signed(row.aDelta)}\nΔb ${signed(row.bDelta)}`}),
    ]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    list.append(button);
  });
  if (!rows.length) list.append(element("div", {class: "empty-state"}, [element("p", {text: rule?.paired ? "No paired firing matches this transition filter." : "This active rule logged no reconstructable from/to pair."})]));

  const body = $("#rule-data-table"); clear(body);
  rows.slice(0, 160).forEach(row => {
    const open = element("button", {type: "button", class: "table-link", text: `game ${row.game} item ${row.item}`});
    open.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    body.append(element("tr", {}, [
      element("td", {}, [open]), element("td", {class: "money", text: pairText(row.before)}),
      element("td", {class: "money", text: pairText(row.after)}), element("td", {text: ruleBracket(row)}),
      element("td", {text: `${ruleStateLabel(row.beforeState)} → ${ruleStateLabel(row.afterState)}`}),
      element("td", {text: formatNumber(row.hiddenCharges)}),
    ]));
  });
}

function renderRuleObservatory() {
  const rule = selectedRule();
  renderRuleFunnel(rule); renderRuleKpis(rule); renderRuleIncome(rule);
  renderRuleTransitions(rule); renderRuleLimitBuckets(rule); renderRuleTimeline(rule);
  renderRuleRecords(rule);
}

function renderStrategy() {
  renderStrategyKpis();
  renderValuationLandscape();
  renderRiskLattice();
  renderPayoff();
  renderDossier();
  renderPortfolioComposer();
  renderRuleObservatory();
}

const BELIEF_INTERVAL_Z = Object.freeze({
  "0.5": .6744897501960817,
  "0.8": 1.2815515655446004,
  "0.9": 1.6448536269514722,
  "0.95": 1.959963984540054,
  "0.99": 2.5758293035489004,
});
const BELIEF_INTERVAL_LEVELS = Object.freeze([.5, .8, .9, .95, .99]);
const CALIBRATION_WINDOWS = new Set(["all", "last-10", "last-20", "first-half", "second-half"]);
const CALIBRATION_BUCKETS = Object.freeze(["0–50", "50–400", "400–1200", "1200+"]);

function calibrationCoverage(value) {
  const numeric = Number(value);
  return BELIEF_INTERVAL_LEVELS.includes(numeric) ? numeric : .9;
}

function calibrationValueBucket(floor) {
  const value = Number(floor);
  if (!Number.isFinite(value) || value < 0) return null;
  if (value < 50) return "0–50";
  if (value < 400) return "50–400";
  if (value < 1200) return "400–1200";
  return "1200+";
}

function calibrationGameIds(rows, window = "all") {
  const games = [...new Set((rows || []).map(row => Number(row.game)).filter(Number.isInteger))].sort((a, b) => a - b);
  if (window === "last-10") return games.slice(-10);
  if (window === "last-20") return games.slice(-20);
  const split = Math.ceil(games.length / 2);
  if (window === "first-half") return games.slice(0, split);
  if (window === "second-half") return games.slice(split);
  return games;
}

function beliefIntervalRow(row, coverage = .9) {
  const level = calibrationCoverage(coverage), z = BELIEF_INTERVAL_Z[String(level)];
  const median = Number(row.median), sigma = Number(row.sigma), tLo = Number(row.tLo);
  const tHi = row.tHi === null || row.tHi === undefined ? null : Number(row.tHi);
  if (!(median > 0) || !(sigma > 0) || !(tLo > 0) || !Number.isFinite(tHi === null ? 0 : tHi)) return null;
  const qLow = median * Math.exp(-z * sigma), qHigh = median * Math.exp(z * sigma);
  let intervalState = "compatible";
  if (qHigh < tLo) intervalState = "forced-low";
  else if (tHi !== null && qLow > tHi) intervalState = "forced-high";
  else if (tHi !== null && qLow <= tLo && qHigh >= tHi) intervalState = "guaranteed";
  let medianState = "compatible";
  if (median < tLo) medianState = "proven-low";
  else if (tHi !== null && median > tHi) medianState = "proven-high";
  const severity = intervalState === "forced-low" ? Math.log(tLo / qHigh)
    : intervalState === "forced-high" ? Math.log(qLow / tHi) : 0;
  return {
    game: Number(row.game), item: Number(row.item), source: row.source || "belief-source-missing",
    bucket: calibrationValueBucket(tLo), median, sigma, tLo, tHi, coverage, z,
    qLow, qHigh, logWidth: 2 * z * sigma, widthFactor: qHigh / qLow,
    intervalState, medianState, severity,
  };
}

function beliefCalibrationSummary(rows) {
  const total = rows.length, twoSided = rows.filter(row => row.tHi !== null).length;
  const forcedLow = rows.filter(row => row.intervalState === "forced-low").length;
  const forcedHigh = rows.filter(row => row.intervalState === "forced-high").length;
  const guaranteed = rows.filter(row => row.intervalState === "guaranteed").length;
  const compatibleUnresolved = rows.filter(row => row.intervalState === "compatible").length;
  const forcedMisses = forcedLow + forcedHigh;
  return {
    total, twoSided, floorOnly: total - twoSided, forcedLow, forcedHigh, forcedMisses,
    guaranteed, compatibleUnresolved,
    forcedMissRate: total ? forcedMisses / total : null,
    compatibleUpperRate: total ? (total - forcedMisses) / total : null,
    guaranteedCaptureRate: twoSided ? guaranteed / twoSided : null,
    medianSigma: medianNumber(rows.map(row => row.sigma)),
    medianWidthFactor: medianNumber(rows.map(row => row.widthFactor)),
    medianToFloor: medianNumber(rows.map(row => row.median / row.tLo)),
    medianProvenLow: rows.filter(row => row.medianState === "proven-low").length,
    medianProvenHigh: rows.filter(row => row.medianState === "proven-high").length,
  };
}

function calibrationGroupRows(rows, field) {
  const groups = new Map();
  rows.forEach(row => {
    const key = row[field] || "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  });
  return [...groups].map(([key, members]) => ({key, ...beliefCalibrationSummary(members)}))
    .sort((a, b) => b.total - a.total || String(a.key).localeCompare(String(b.key)));
}

function buildBeliefCalibration(itemIndex, options = {}) {
  const coverage = calibrationCoverage(options.coverage), window = CALIBRATION_WINDOWS.has(options.window) ? options.window : "all";
  const source = typeof options.source === "string" && options.source ? options.source : "all";
  const bucket = options.bucket === "all" || CALIBRATION_BUCKETS.includes(options.bucket) ? options.bucket : "all";
  const eligibleRaw = (itemIndex || []).filter(row => Number(row.median) > 0 && Number(row.sigma) > 0 && Number(row.tLo) > 0);
  const games = calibrationGameIds(eligibleRaw, window), selectedGames = new Set(games);
  const selectedRaw = eligibleRaw.filter(row => selectedGames.has(Number(row.game)) &&
    (source === "all" || (row.source || "belief-source-missing") === source) &&
    (bucket === "all" || calibrationValueBucket(row.tLo) === bucket));
  const makeRows = level => selectedRaw.map(row => beliefIntervalRow(row, level)).filter(Boolean);
  const rows = makeRows(coverage), summary = beliefCalibrationSummary(rows);
  const observedGames = [...new Set(rows.map(row => row.game))].sort((a, b) => a - b);
  const curve = BELIEF_INTERVAL_LEVELS.map(level => {
    const levelRows = makeRows(level), levelSummary = beliefCalibrationSummary(levelRows);
    return {coverage: level, nominalMissRate: 1 - level, ...levelSummary};
  });
  const nominalMissRate = 1 - coverage;
  const excessForcedMiss = summary.forcedMissRate === null ? null : summary.forcedMissRate - nominalMissRate;
  return {
    coverage, window, source, bucket, games, observedGames, rows,
    summary: {...summary, nominalMissRate, excessForcedMiss,
      verdict: excessForcedMiss !== null && excessForcedMiss > 0 ? "proven-undercoverage" : "unresolved-by-bounds"},
    curve,
    sources: calibrationGroupRows(rows, "source"),
    buckets: calibrationGroupRows(rows, "bucket"),
    gamesSummary: calibrationGroupRows(rows, "game").sort((a, b) => Number(a.key) - Number(b.key)),
    misses: rows.filter(row => row.intervalState.startsWith("forced-"))
      .sort((a, b) => b.severity - a.severity || a.game - b.game || a.item - b.item),
  };
}

function buildCalibrationReceipt(result, materializedAt) {
  return {
    version: 1, status: "offline-bounded-belief-calibration-evidence-only", materializedAt,
    specification: {centralCoverage: result.coverage, window: result.window, source: result.source, valueBucket: result.bucket, eligibleWindowGameIds: [...result.games], distribution: "lognormal-gross-EUR"},
    denominator: {beliefsWithPositiveMedianSigmaAndSanctionedFloor: result.summary.total, representedBeliefGames: result.observedGames.length, twoSidedBrackets: result.summary.twoSided, floorOnlyBrackets: result.summary.floorOnly},
    boundedResult: {
      forcedMissLowerBound: result.summary.forcedMisses,
      forcedMissRateLowerBound: result.summary.forcedMissRate,
      compatibleCoverageUpperBound: result.summary.compatibleUpperRate,
      guaranteedCaptureLowerBoundOnTwoSided: result.summary.guaranteed,
      guaranteedCaptureRateOnTwoSided: result.summary.guaranteedCaptureRate,
      nominalMissRate: result.summary.nominalMissRate,
      verdict: result.summary.verdict,
    },
    intervalFrontier: result.curve.map(row => ({centralCoverage: row.coverage, nominalMissRate: row.nominalMissRate, forcedMisses: row.forcedMisses, forcedMissRateLowerBound: row.forcedMissRate, guaranteedCaptures: row.guaranteed, twoSidedBrackets: row.twoSided})),
    sourceSummary: result.sources.map(row => ({source: row.key, beliefs: row.total, forcedLow: row.forcedLow, forcedHigh: row.forcedHigh, guaranteed: row.guaranteed, twoSided: row.twoSided, medianSigma: row.medianSigma})),
    boundaries: [
      "sanctioned threshold brackets are bounds on the secret fair value, never exact target labels",
      "a forced miss is proven only when the entire lognormal interval lies below the floor or above a known ceiling",
      "overlap is compatible coverage, not proof that the unknown fair value lies inside the interval",
      "guaranteed capture is measurable only when a finite two-sided bracket lies fully inside the interval",
      "this is retrospective calibration evidence on logged beliefs, not a temporal holdout or causal source comparison",
      "no process, belief, charge, limit, rule, model, or submission is modified",
    ],
  };
}

function calibrationStateLabel(stateName) {
  return ({"forced-low": "forced miss · below floor", "forced-high": "forced miss · above ceiling", guaranteed: "guaranteed bracket capture", compatible: "compatible · unresolved"})[stateName] || "unknown";
}

function populateCalibrationControls() {
  if (!state.overview) return;
  const sourceControl = $("#calibration-source"), previous = state.calibrationSource; clear(sourceControl);
  sourceControl.append(element("option", {value: "all", text: "All logged sources"}));
  const sources = [...new Set(state.overview.itemIndex.filter(row => Number(row.median) > 0 && Number(row.sigma) > 0 && Number(row.tLo) > 0).map(row => row.source || "belief-source-missing"))].sort();
  sources.forEach(source => sourceControl.append(element("option", {value: source, text: source})));
  state.calibrationSource = sources.includes(previous) ? previous : "all";
  state.calibrationCoverage = calibrationCoverage(state.calibrationCoverage);
  if (!CALIBRATION_BUCKETS.includes(state.calibrationBucket)) state.calibrationBucket = "all";
  if (!CALIBRATION_WINDOWS.has(state.calibrationWindow)) state.calibrationWindow = "all";
  sourceControl.value = state.calibrationSource;
  $("#calibration-coverage").value = String(state.calibrationCoverage);
  $("#calibration-bucket").value = state.calibrationBucket;
  $("#calibration-window").value = state.calibrationWindow;
}

function renderCalibrationNarrative(result) {
  const host = $("#calibration-narrative"); clear(host);
  const summary = result.summary, proven = summary.verdict === "proven-undercoverage";
  host.dataset.tone = proven ? "warning" : "unresolved";
  if (!summary.total) {
    host.append(element("div", {class: "calibration-narrative-primary"}, [element("span", {text: "NO MATCHING BOUNDED BELIEFS"}), element("strong", {text: "THIS FILTER HAS NO EVALUABLE ITEMS"}), element("small", {text: "An evaluable item needs a positive logged median, positive log σ, and a sanctioned positive floor."})]));
    return;
  }
  const headline = proven ? `PROVEN UNDER-COVERAGE AT ${formatPercent(result.coverage)}` : `UNDER-COVERAGE NOT PROVEN AT ${formatPercent(result.coverage)}`;
  host.append(element("div", {class: "calibration-narrative-primary"}, [
    element("span", {text: `${summary.total} BOUNDED BELIEFS · ${result.observedGames.length} REPRESENTED / ${result.games.length} WINDOW GAMES`}),
    element("strong", {text: headline}),
    element("small", {text: `${formatPercent(summary.forcedMissRate)} forced-miss lower bound versus ${formatPercent(summary.nominalMissRate)} nominal miss · ${summary.floorOnly} floor-only items cannot prove high-side capture`}),
  ]));
  const facts = [
    ["FORCED DIRECTION", `${summary.forcedLow} low / ${summary.forcedHigh} high`, "entire interval outside a proven bound"],
    ["COVERAGE CEILING", formatPercent(summary.compatibleUpperRate), "not forced to miss · not proof of capture"],
    ["GUARANTEED FLOOR", `${summary.guaranteed} / ${summary.twoSided}`, "finite brackets fully enclosed"],
  ];
  facts.forEach(([label, value, note]) => host.append(element("div", {class: "calibration-narrative-fact"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
}

function renderCalibrationKpis(result) {
  const host = $("#calibration-kpis"); clear(host); const summary = result.summary;
  const specs = [
    ["EVALUABLE BELIEFS", formatNumber(summary.total), `${summary.twoSided} two-sided · ${summary.floorOnly} floor-only items`],
    ["FORCED MISS LB", formatPercent(summary.forcedMissRate), `${summary.forcedMisses} / ${summary.total} items · nominal miss ${formatPercent(summary.nominalMissRate)}`],
    ["EXCESS MISS LB", summary.excessForcedMiss === null ? "unavailable" : `${summary.excessForcedMiss >= 0 ? "+" : "−"}${formatPercent(Math.abs(summary.excessForcedMiss))}`, "forced-miss lower bound − nominal miss rate"],
    ["COMPATIBLE UB", formatPercent(summary.compatibleUpperRate), "interval overlaps admissible value region · upper bound only"],
    ["GUARANTEED / 2-SIDED", formatPercent(summary.guaranteedCaptureRate), `${summary.guaranteed} / ${summary.twoSided} finite brackets enclosed`],
    ["MEDIAN WIDTH", summary.medianWidthFactor === null ? "unavailable" : `${formatNumber(summary.medianWidthFactor, 2)}×`, `q${formatNumber((1 - result.coverage) / 2 * 100, 1)}–q${formatNumber((1 + result.coverage) / 2 * 100, 1)} multiplicative span · median σ ${formatNumber(summary.medianSigma, 3)}`],
  ];
  specs.forEach(([label, value, note], index) => host.append(element("div", {class: "calibration-kpi"}, [element("span", {text: label}), element("strong", {class: index === 1 && summary.verdict === "proven-undercoverage" ? "negative" : "", text: value}), element("small", {text: note})])));
}

function renderCalibrationFrontier(result) {
  const host = $("#calibration-frontier-chart"); clear(host); const body = $("#calibration-frontier-table"); clear(body);
  const rows = result.curve, width = 720, height = 390, margin = {left: 72, right: 31, top: 42, bottom: 55};
  const maxRate = Math.max(.5, ...rows.flatMap(row => [safeNumber(row.forcedMissRate), row.nominalMissRate])) * 1.06;
  const x = coverage => margin.left + (coverage - .5) / .49 * (width - margin.left - margin.right);
  const y = rate => margin.top + (maxRate - rate) / maxRate * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Forced belief interval miss lower bound versus nominal miss rate");
  for (let tick = 0; tick <= 5; tick += 1) { const value = maxRate * tick / 5, yy = y(value); svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"})); svg.append(svgElement("text", {x: margin.left - 10, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatPercent(value))); }
  const nominalPoints = rows.map(row => [x(row.coverage), y(row.nominalMissRate)]), forcedPoints = rows.map(row => [x(row.coverage), y(safeNumber(row.forcedMissRate))]);
  svg.append(svgElement("path", {d: linePath(nominalPoints), fill: "none", stroke: colors.muted, "stroke-width": 1.7, "stroke-dasharray": "5 5"}));
  svg.append(svgElement("path", {d: linePath(forcedPoints), fill: "none", stroke: colors.red, "stroke-width": 2.5}));
  rows.forEach((row, index) => {
    const xx = x(row.coverage), yy = y(safeNumber(row.forcedMissRate)), exceeds = safeNumber(row.forcedMissRate) > row.nominalMissRate;
    const marker = exceeds ? svgElement("path", {d: `M${xx},${yy - 6} L${xx + 6},${yy + 5} L${xx - 6},${yy + 5} Z`, fill: colors.red, tabindex: 0, role: "img", "aria-label": `${formatPercent(row.coverage)} interval forced miss lower bound ${formatPercent(row.forcedMissRate)}, above nominal miss ${formatPercent(row.nominalMissRate)}`}) : svgElement("circle", {cx: xx, cy: yy, r: 4, fill: colors.amber, tabindex: 0, role: "img", "aria-label": `${formatPercent(row.coverage)} interval forced miss lower bound ${formatPercent(row.forcedMissRate)}`});
    addTooltip(marker, [`${formatPercent(row.coverage)} central interval`, `Forced miss lower bound ${formatPercent(row.forcedMissRate)} · ${row.forcedMisses} / ${row.total} items`, `Nominal miss ${formatPercent(row.nominalMissRate)} · ${exceeds ? "lower bound already exceeds nominal" : "bounds do not prove nominal under-coverage"}`, `${row.guaranteed} / ${row.twoSided} finite brackets guaranteed captured`]); svg.append(marker);
    svg.append(svgElement("text", {x: xx, y: height - 26, class: "axis-label", "text-anchor": "middle"}, formatPercent(row.coverage)));
    body.append(element("tr", {}, [element("td", {text: formatPercent(row.coverage)}), element("td", {text: formatPercent(row.nominalMissRate)}), element("td", {text: row.total}), element("td", {text: row.forcedLow}), element("td", {text: row.forcedHigh}), element("td", {text: `${row.forcedMisses} · ${formatPercent(row.forcedMissRate)}`}), element("td", {text: `${row.guaranteed} / ${row.twoSided}`})]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.red, "font-size": 8, "font-family": "var(--mono)"}, "SOLID = PROVEN MISS LOWER BOUND · DASHED = NOMINAL MISS · TRIANGLE = LOWER BOUND EXCEEDS NOMINAL")); host.append(svg);
}

function intervalStateSegments(row) {
  return [
    {key: "forcedLow", label: "forced low", value: row.forcedLow, color: colors.amber},
    {key: "compatibleUnresolved", label: "compatible unresolved", value: row.compatibleUnresolved, color: colors.violet},
    {key: "guaranteed", label: "guaranteed", value: row.guaranteed, color: colors.green},
    {key: "forcedHigh", label: "forced high", value: row.forcedHigh, color: colors.red},
  ];
}

function renderCalibrationStacked(hostSelector, rows, label, tableSelector = null) {
  const host = $(hostSelector); clear(host); const body = tableSelector ? $(tableSelector) : null; if (body) clear(body);
  if (!rows.length) { host.append(element("div", {class: "empty-state"}, [element("p", {text: `No ${label.toLowerCase()} calibration rows match.`})])); return; }
  const width = 760, rowHeight = 37, height = 57 + rows.length * rowHeight, margin = {left: 171, right: 51, top: 27, bottom: 30};
  const svg = svgRoot(width, height, `Bounded belief interval states by ${label.toLowerCase()}`), plotW = width - margin.left - margin.right;
  rows.forEach((row, index) => {
    const y = margin.top + index * rowHeight + 7;
    svg.append(svgElement("text", {x: margin.left - 10, y: y + 10, fill: "#98a4ad", "font-size": 8, "font-family": "var(--mono)", "text-anchor": "end"}, String(row.key).length > 22 ? `${String(row.key).slice(0, 21)}…` : String(row.key)));
    let offset = 0;
    intervalStateSegments(row).forEach(segment => { const barWidth = row.total ? segment.value / row.total * plotW : 0; if (barWidth > 0) { const rect = svgElement("rect", {x: margin.left + offset, y, width: barWidth, height: 15, fill: segment.color, "fill-opacity": .68, tabindex: 0, role: "img", "aria-label": `${row.key}, ${segment.label}, ${segment.value} of ${row.total}`}); addTooltip(rect, [`${row.key} · ${segment.label}`, `${segment.value} / ${row.total} items · ${formatPercent(segment.value / row.total)}`, `median log σ ${formatNumber(row.medianSigma, 3)} · interval width ${formatNumber(row.medianWidthFactor, 2)}×`]); svg.append(rect); } offset += barWidth; });
    svg.append(svgElement("text", {x: width - margin.right + 8, y: y + 10, fill: colors.faint || colors.muted, "font-size": 8, "font-family": "var(--mono)"}, `n=${row.total}`));
    if (body) body.append(element("tr", {}, [element("td", {text: row.key}), element("td", {text: row.total}), element("td", {text: row.forcedLow}), element("td", {text: row.compatibleUnresolved}), element("td", {text: row.guaranteed}), element("td", {text: row.forcedHigh}), element("td", {text: formatNumber(row.medianSigma, 3)}), element("td", {text: `${formatNumber(row.medianWidthFactor, 2)}×`})]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 15, fill: colors.muted, "font-size": 8, "font-family": "var(--mono)"}, "AMBER FORCED LOW · VIOLET COMPATIBLE/UNRESOLVED · GREEN GUARANTEED · RED FORCED HIGH")); host.append(svg);
}

function renderCalibrationGeometry(result) {
  const host = $("#calibration-geometry-chart"); clear(host); const list = $("#calibration-miss-list"); clear(list);
  const candidates = result.misses.length ? result.misses.slice(0, 32) : [...result.rows].sort((a, b) => Math.abs(Math.log(b.median / b.tLo)) - Math.abs(Math.log(a.median / a.tLo))).slice(0, 32);
  if (!candidates.length) { host.append(element("div", {class: "empty-state"}, [element("p", {text: "No bounded belief geometry matches this filter."})])); list.append(element("div", {class: "empty-state"}, [element("p", {text: "No forced interval misses."})])); return; }
  const values = candidates.flatMap(row => [row.qLow, row.qHigh, row.tLo, row.tHi]).filter(value => Number(value) > 0).map(Math.log);
  let min = Math.min(...values), max = Math.max(...values); const pad = Math.max(.08, (max - min) * .06); min -= pad; max += pad;
  const width = 1050, rowHeight = 29, height = 65 + candidates.length * rowHeight, margin = {left: 102, right: 44, top: 32, bottom: 40};
  const x = value => margin.left + (Math.log(value) - min) / (max - min || 1) * (width - margin.left - margin.right);
  const svg = svgRoot(width, height, "Logged lognormal belief intervals and sanctioned fair-value brackets");
  candidates.forEach((row, index) => {
    const y = margin.top + index * rowHeight + rowHeight / 2, tone = row.intervalState === "forced-low" ? colors.amber : row.intervalState === "forced-high" ? colors.red : row.intervalState === "guaranteed" ? colors.green : colors.violet;
    svg.append(svgElement("line", {x1: margin.left, y1: y + rowHeight / 2, x2: width - margin.right, y2: y + rowHeight / 2, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 9, y: y + 3, fill: tone, "font-size": 8, "font-family": "var(--mono)", "text-anchor": "end"}, `G${row.game}:I${row.item}`));
    svg.append(svgElement("line", {x1: x(row.qLow), y1: y, x2: x(row.qHigh), y2: y, stroke: colors.cyan, "stroke-width": 4, "stroke-linecap": "round", "stroke-opacity": .5}));
    svg.append(svgElement("line", {x1: x(row.qLow), y1: y - 5, x2: x(row.qLow), y2: y + 5, stroke: colors.cyan, "stroke-width": 1.2}));
    svg.append(svgElement("line", {x1: x(row.qHigh), y1: y - 5, x2: x(row.qHigh), y2: y + 5, stroke: colors.cyan, "stroke-width": 1.2}));
    svg.append(svgElement("rect", {x: x(row.median) - 3.5, y: y - 3.5, width: 7, height: 7, fill: colors.cyan, transform: `rotate(45 ${x(row.median)} ${y})`}));
    if (row.tHi !== null) svg.append(svgElement("line", {x1: x(row.tLo), y1: y + 7, x2: x(row.tHi), y2: y + 7, stroke: tone, "stroke-width": 2.2, "stroke-opacity": .85}));
    svg.append(svgElement("line", {x1: x(row.tLo), y1: y + 2, x2: x(row.tLo), y2: y + 12, stroke: tone, "stroke-width": 2}));
    if (row.tHi !== null) svg.append(svgElement("line", {x1: x(row.tHi), y1: y + 2, x2: x(row.tHi), y2: y + 12, stroke: tone, "stroke-width": 2}));
    else svg.append(svgElement("text", {x: x(row.tLo) + 7, y: y + 11, fill: colors.faint || colors.muted, "font-size": 7, "font-family": "var(--mono)"}, "CEILING OPEN"));
    const hit = svgElement("rect", {x: margin.left, y: y - rowHeight / 2, width: width - margin.left - margin.right, height: rowHeight, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game} item ${row.item}, ${calibrationStateLabel(row.intervalState)}`});
    addTooltip(hit, [`Game ${row.game} item ${row.item} · ${calibrationStateLabel(row.intervalState)}`, `${formatPercent(row.coverage)} interval ${formatCurrency(row.qLow)}–${formatCurrency(row.qHigh)} · median ${formatCurrency(row.median)} · log σ ${formatNumber(row.sigma, 3)}`, row.tHi === null ? `proven floor ${formatCurrency(row.tLo)} · ceiling unknown` : `proven bracket ${formatCurrency(row.tLo)}–${formatCurrency(row.tHi)}`, `source ${row.source} · severity ${formatNumber(row.severity, 3)} log units`]);
    hit.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    hit.addEventListener("keydown", async event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); await selectGame(row.game); await selectItem(row.item, {scroll: true}); } }); svg.append(hit);
  });
  [0, .25, .5, .75, 1].forEach(portion => { const value = Math.exp(min + (max - min) * portion); svg.append(svgElement("text", {x: margin.left + portion * (width - margin.left - margin.right), y: height - 15, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true))); });
  svg.append(svgElement("text", {x: margin.left, y: 15, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)"}, "CYAN = LOGNORMAL INTERVAL + MEDIAN · LOWER RAIL = SANCTIONED BRACKET · LOG EUR AXIS")); host.append(svg);
  result.misses.slice(0, 16).forEach((row, index) => {
    const button = element("button", {type: "button", class: "calibration-miss-row"}, [element("span", {text: `#${index + 1}`}), element("div", {}, [element("strong", {text: `Game ${row.game} item ${row.item}`}), element("small", {text: `${calibrationStateLabel(row.intervalState)} · ${row.source}`})]), element("strong", {text: `${formatNumber(Math.exp(row.severity), 2)}×`})]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); }); list.append(button);
  });
  if (!result.misses.length) list.append(element("div", {class: "empty-state"}, [element("p", {text: "No interval is provably outside the sanctioned bounds under this filter."})]));
}

function renderCalibrationTemporal(result) {
  const host = $("#calibration-temporal-chart"); clear(host); const body = $("#calibration-temporal-table"); clear(body); const rows = result.gamesSummary;
  if (!rows.length) { host.append(element("div", {class: "empty-state"}, [element("p", {text: "No belief-observed games match this filter."})])); return; }
  const width = Math.max(760, rows.length * 28 + 110), height = 360, margin = {left: 70, right: 30, top: 36, bottom: 50};
  const maxCount = Math.max(1, ...rows.map(row => row.total)), x = index => margin.left + index / Math.max(1, rows.length - 1) * (width - margin.left - margin.right), y = rate => margin.top + (1 - safeNumber(rate)) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Forced belief interval miss lower bound by logged game");
  [0,.25,.5,.75,1].forEach(value => { const yy=y(value);svg.append(svgElement("line", {x1:margin.left,y1:yy,x2:width-margin.right,y2:yy,class:"grid-line"}));svg.append(svgElement("text", {x:margin.left-9,y:yy+3,class:"axis-label","text-anchor":"end"},formatPercent(value))); });
  const points = rows.map((row, index) => [x(index), y(row.forcedMissRate)]); svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: colors.red, "stroke-width": 2.2}));
  rows.forEach((row, index) => { const xx=x(index), yy=y(row.forcedMissRate), radius=3+Math.sqrt(row.total/maxCount)*5; const marker=svgElement("circle", {cx:xx,cy:yy,r:radius,fill:row.forcedMisses?colors.red:colors.green,"fill-opacity":.72,tabindex:0,role:"button",class:"interactive","aria-label":`Open game ${row.key}, forced interval miss lower bound ${formatPercent(row.forcedMissRate)}`}); addTooltip(marker,[`Game ${row.key} · ${row.total} bounded beliefs`,`Forced miss lower bound ${formatPercent(row.forcedMissRate)} · ${row.forcedLow} low / ${row.forcedHigh} high`,`${row.guaranteed} / ${row.twoSided} finite brackets guaranteed enclosed`]); marker.addEventListener("click",()=>openDriftGame(Number(row.key))); marker.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();openDriftGame(Number(row.key));}});svg.append(marker); if(index%Math.max(1,Math.ceil(rows.length/12))===0||index===rows.length-1)svg.append(svgElement("text",{x:xx,y:height-20,class:"axis-label","text-anchor":"middle"},`G${row.key}`)); body.append(element("tr",{},[element("td",{},[itemLink(Number(row.key),null,`Game ${row.key}`)]),element("td",{text:row.total}),element("td",{text:row.forcedLow}),element("td",{text:row.forcedHigh}),element("td",{text:formatPercent(row.forcedMissRate)}),element("td",{text:`${row.guaranteed} / ${row.twoSided}`})])); });
  svg.append(svgElement("text", {x: margin.left, y: 16, fill: colors.red, "font-size": 8, "font-family": "var(--mono)"}, "FORCED MISS LOWER BOUND · MARKER AREA ∝ BOUNDED BELIEF COUNT · RETROSPECTIVE LOGGED GAMES")); host.append(svg);
}

function renderCalibrationTables(result) {
  const bucketBody = $("#calibration-bucket-table"); clear(bucketBody);
  result.buckets.forEach(row => bucketBody.append(element("tr", {}, [element("td", {text: row.key}), element("td", {text: row.total}), element("td", {text: `${row.forcedMisses} · ${formatPercent(row.forcedMissRate)}`}), element("td", {text: formatPercent(row.compatibleUpperRate)}), element("td", {text: `${row.guaranteed} / ${row.twoSided}`}), element("td", {text: formatNumber(row.medianSigma, 3)})])));
  const itemBody = $("#calibration-item-table"); clear(itemBody);
  [...result.rows].sort((a, b) => b.severity - a.severity || a.game - b.game || a.item - b.item).forEach(row => itemBody.append(element("tr", {}, [element("td", {}, [itemLink(row.game, row.item)]), element("td", {text: row.source}), element("td", {text: row.bucket}), element("td", {class: "money", text: formatCurrency(row.median)}), element("td", {text: formatNumber(row.sigma, 3)}), element("td", {class: "money", text: formatCurrency(row.qLow)}), element("td", {class: "money", text: formatCurrency(row.qHigh)}), element("td", {class: "money", text: formatCurrency(row.tLo)}), element("td", {class: "money", text: row.tHi === null ? "unknown" : formatCurrency(row.tHi)}), element("td", {text: calibrationStateLabel(row.intervalState)}), element("td", {text: row.severity ? `${formatNumber(Math.exp(row.severity), 2)}×` : "—"})])));
}

async function copyCalibrationReceipt() {
  if (!state.calibrationResult || !state.overview) { toast("Bounded calibration evidence is unavailable to copy."); return; }
  try { await navigator.clipboard.writeText(JSON.stringify(buildCalibrationReceipt(state.calibrationResult, state.overview.generatedAt), null, 2)); toast("Claim-free bounded calibration receipt copied."); }
  catch (error) { toast(`Calibration receipt could not be copied: ${error.message}`); }
}

function renderCalibrationStudio() {
  if (!state.overview) return;
  populateCalibrationControls();
  const result = buildBeliefCalibration(state.overview.itemIndex, {coverage: state.calibrationCoverage, source: state.calibrationSource, bucket: state.calibrationBucket, window: state.calibrationWindow});
  state.calibrationResult = result;
  $("#calibration-status").textContent = `${result.summary.total} BOUNDED BELIEFS · ${result.observedGames.length} REPRESENTED GAMES · ${formatPercent(result.coverage)} CENTRAL`;
  renderCalibrationNarrative(result); renderCalibrationKpis(result); renderCalibrationFrontier(result);
  renderCalibrationStacked("#calibration-source-chart", result.sources, "Source", "#calibration-source-table");
  renderCalibrationGeometry(result);
  renderCalibrationStacked("#calibration-bucket-chart", result.buckets, "Value bucket");
  renderCalibrationTemporal(result); renderCalibrationTables(result);
}

const PEER_COHORTS = new Set(["source-bucket", "source-only", "bucket-only"]);
const PEER_METRICS = Object.freeze([
  {key: "charge-floor", label: "log charge / floor", unit: "log-ratio"},
  {key: "belief-floor", label: "log belief median / floor", unit: "log-ratio"},
  {key: "limit-floor", label: "normalised b − floor", unit: "ratio"},
  {key: "issuer", label: "issuer shortfall lower bound", unit: "eur"},
  {key: "reviewer", label: "observed wrong-review cost", unit: "eur"},
  {key: "combined", label: "additive evidence load", unit: "eur"},
  {key: "hidden", label: "hidden rejected-fraud groups", unit: "count"},
]);

function peerValueBucket(floor) {
  if (floor === null || floor === undefined || !Number.isFinite(Number(floor))) return "unlabelled";
  const value = Number(floor);
  if (value < 50) return "0–50";
  if (value < 400) return "50–400";
  if (value < 1200) return "400–1200";
  return "1200+";
}

function peerQuantile(values, probability) {
  const clean = (values || []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!clean.length) return null;
  const position = Math.min(1, Math.max(0, probability)) * (clean.length - 1);
  const lower = Math.floor(position), upper = Math.ceil(position);
  if (lower === upper) return clean[lower];
  return clean[lower] + (clean[upper] - clean[lower]) * (position - lower);
}

function peerMidrank(values, selected) {
  if (!Number.isFinite(selected)) return null;
  const clean = (values || []).map(Number).filter(Number.isFinite);
  if (!clean.length) return null;
  const epsilon = Math.max(1e-12, Math.abs(selected) * 1e-12);
  const lower = clean.filter(value => value < selected - epsilon).length;
  const equal = clean.filter(value => Math.abs(value - selected) <= epsilon).length;
  return (lower + .5 * equal) / clean.length;
}

function peerMetricValue(row, key) {
  if (key === "charge-floor") return row.tLo > 0 && row.a > 0 ? Math.log(row.a / row.tLo) : null;
  if (key === "belief-floor") return row.tLo > 0 && row.median > 0 ? Math.log(row.median / row.tLo) : null;
  if (key === "limit-floor") return row.tLo > 0 && Number.isFinite(row.b) ? (row.b - row.tLo) / row.tLo : null;
  if (key === "issuer") return Number.isFinite(row.issuerForegoneLowerBound) ? row.issuerForegoneLowerBound : null;
  if (key === "reviewer") return Number.isFinite(row.wrongReviewerCost) ? row.wrongReviewerCost : null;
  if (key === "combined") return Number.isFinite(row.combinedEvidenceLoad) ? row.combinedEvidenceLoad : null;
  if (key === "hidden") return Number.isFinite(row.hiddenFraudGroups) ? row.hiddenFraudGroups : null;
  return null;
}

function peerDistribution(peers, selectedValue, metricKey) {
  const values = peers.map(row => peerMetricValue(row, metricKey)).filter(Number.isFinite);
  return {
    observations: values.length,
    percentile: peerMidrank(values, selectedValue),
    p10: peerQuantile(values, .1), p25: peerQuantile(values, .25),
    median: peerQuantile(values, .5), p75: peerQuantile(values, .75), p90: peerQuantile(values, .9),
    minimum: values.length ? Math.min(...values) : null,
    maximum: values.length ? Math.max(...values) : null,
  };
}

function peerEnrichedRows(itemIndex, regretRows) {
  const regrets = new Map((regretRows || []).map(row => [`${Number(row.game)}:${Number(row.item)}`, row]));
  return (itemIndex || []).map(row => {
    const regret = regrets.get(`${Number(row.game)}:${Number(row.item)}`);
    const numeric = value => value === null || value === undefined || !Number.isFinite(Number(value)) ? null : Number(value);
    return {
      game: Number(row.game), item: Number(row.item), source: row.source || "belief-source-missing",
      bucket: peerValueBucket(row.tLo), status: row.status || "unknown",
      a: numeric(row.a), b: numeric(row.b), tLo: numeric(row.tLo), tHi: numeric(row.tHi),
      median: numeric(row.median), sigma: numeric(row.sigma),
      issuerForegoneLowerBound: regret ? Math.max(0, safeNumber(regret.issuerForegoneLowerBound)) : numeric(row.foregoneLowerBound),
      wrongReviewerCost: regret ? Math.max(0, safeNumber(regret.wrongReviewerCost)) : null,
      combinedEvidenceLoad: regret ? Math.max(0, safeNumber(regret.combinedEvidenceLoad)) : null,
      hiddenFraudGroups: regret ? Math.max(0, safeNumber(regret.hiddenFraudGroups)) : null,
    };
  });
}

function peerAnalogueVector(row) {
  return {
    charge: peerMetricValue(row, "charge-floor"), belief: peerMetricValue(row, "belief-floor"),
    limit: peerMetricValue(row, "limit-floor"), sigma: Number.isFinite(row.sigma) ? row.sigma : null,
  };
}

function peerNumericAnalogues(selected, peers) {
  const features = ["charge", "belief", "limit", "sigma"], selectedVector = peerAnalogueVector(selected);
  const scales = Object.fromEntries(features.map(feature => {
    const values = [selected, ...peers].map(row => peerAnalogueVector(row)[feature]).filter(Number.isFinite);
    const iqr = peerQuantile(values, .75) - peerQuantile(values, .25);
    const minimumScale = feature === "sigma" ? .05 : feature === "limit" ? .2 : .12;
    return [feature, Math.max(minimumScale, Number.isFinite(iqr) ? iqr : 0)];
  }));
  return peers.map(row => {
    const vector = peerAnalogueVector(row), differences = features.filter(feature => Number.isFinite(selectedVector[feature]) && Number.isFinite(vector[feature]))
      .map(feature => (vector[feature] - selectedVector[feature]) / scales[feature]);
    if (differences.length < 2) return null;
    return {...row, distance: Math.sqrt(differences.reduce((sum, value) => sum + value * value, 0) / differences.length), dimensions: differences.length,
      temporalSide: row.game < selected.game ? "strictly-prior" : row.game === selected.game ? "same-game-hindsight" : "future-hindsight"};
  }).filter(Boolean).sort((a, b) => a.distance - b.distance || a.game - b.game || a.item - b.item).slice(0, 20);
}

function buildPeerForensics(itemIndex, regretRows, selectedGame, selectedItem, options = {}) {
  const cohort = PEER_COHORTS.has(options.cohort) ? options.cohort : "source-bucket";
  const metric = PEER_METRICS.some(row => row.key === options.metric) ? options.metric : "combined";
  const reviewerEvidenceAvailable = options.reviewerAvailable === undefined ? Boolean((regretRows || []).length) : options.reviewerAvailable === true;
  const rows = peerEnrichedRows(itemIndex, regretRows);
  const selected = rows.find(row => row.game === Number(selectedGame) && row.item === Number(selectedItem)) || null;
  if (!selected) return {available: false, reviewerEvidenceAvailable, cohort, metric, selected: null, denominator: {allPeers: 0, priorPeers: 0, sameGamePeers: 0, futurePeers: 0}, metrics: [], analogues: [], priorAnalogues: [], peerRows: []};
  const cohortMatches = row => {
    const sourceMatch = row.source === selected.source, bucketMatch = row.bucket === selected.bucket;
    return cohort === "source-only" ? sourceMatch : cohort === "bucket-only" ? bucketMatch : sourceMatch && bucketMatch;
  };
  const peerRows = rows.filter(row => !(row.game === selected.game && row.item === selected.item) && cohortMatches(row));
  const priorPeers = peerRows.filter(row => row.game < selected.game);
  const sameGamePeers = peerRows.filter(row => row.game === selected.game);
  const futurePeers = peerRows.filter(row => row.game > selected.game);
  const metrics = PEER_METRICS.map(spec => {
    const selectedValue = peerMetricValue(selected, spec.key);
    return {...spec, selectedValue, prior: peerDistribution(priorPeers, selectedValue, spec.key), all: peerDistribution(peerRows, selectedValue, spec.key)};
  });
  return {
    available: true, reviewerEvidenceAvailable, cohort, metric, selected, peerRows, priorPeers, sameGamePeers, futurePeers, metrics,
    denominator: {allPeers: peerRows.length, priorPeers: priorPeers.length, sameGamePeers: sameGamePeers.length, futurePeers: futurePeers.length},
    analogues: peerNumericAnalogues(selected, peerRows),
    priorAnalogues: peerNumericAnalogues(selected, priorPeers),
  };
}

function buildPeerReceipt(result, materializedAt) {
  return {
    version: 1, status: "offline-item-peer-forensics-evidence-only", materializedAt,
    selected: result.selected ? {game: result.selected.game, item: result.selected.item, source: result.selected.source, bucket: result.selected.bucket} : null,
    filters: {cohort: result.cohort, metric: result.metric}, reviewerEvidenceAvailable: result.reviewerEvidenceAvailable, denominator: {...result.denominator},
    metrics: result.metrics.map(row => ({key: row.key, unit: row.unit, selectedValue: row.selectedValue, prior: {...row.prior}, all: {...row.all}})),
    analogues: result.analogues.map(row => ({game: row.game, item: row.item, temporalSide: row.temporalSide, distance: row.distance, dimensions: row.dimensions})),
    priorAnalogues: result.priorAnalogues.map(row => ({game: row.game, item: row.item, temporalSide: row.temporalSide, distance: row.distance, dimensions: row.dimensions})),
    boundaries: [
      "same source and sanctioned-floor regime is a retrospective numeric cohort, not a semantic item class",
      "strictly prior peers use only lower game identifiers; the selected and every later game are excluded",
      "future and same-game peers are hindsight context only and never enter prior summaries",
      "numeric analogues are not semantic, causal, or substitutable items; prior analogue scaling excludes same-game and future peers",
      "sanctioned floors remain proof bounds rather than exact fair-value labels",
      "each metric reports its own non-missing observation denominator; reviewer-derived fields remain missing when that ledger is unavailable",
      "no process, belief, charge, limit, rule, model, or submission is modified",
    ],
  };
}

const WATCHBOARD_SORTS = new Set(["triage", "issuer", "reviewer", "hidden", "value", "recent"]);

function watchboardIdentifiers(values) {
  const identifiers = new Map();
  for (const value of values || []) {
    if (typeof value !== "string" || !/^\d{1,3}:\d{1,3}$/.test(value)) continue;
    const [game, item] = value.split(":").map(Number);
    if (!Number.isInteger(game) || !Number.isInteger(item) || game < 1 || item < 1) continue;
    identifiers.set(`${game}:${item}`, {key: `${game}:${item}`, game, item});
  }
  return [...identifiers.values()].sort((a, b) => a.game - b.game || a.item - b.item);
}

function watchboardEvidenceMode(row, reviewerAvailable = true) {
  if (!row.materialized) return "not-materialised";
  const issuer = Math.max(0, safeNumber(row.issuerForegoneLowerBound));
  if (!reviewerAvailable) return issuer > 0 ? "issuer-only-degraded" : "reviewer-unavailable";
  const reviewer = Math.max(0, safeNumber(row.wrongReviewerCost));
  if (issuer > 0 && reviewer > 0) return "two-role-collision";
  if (issuer > 0) return "issuer-burden";
  if (reviewer > 0) return "reviewer-burden";
  if (safeNumber(row.hiddenFraudGroups) > 0) return "hidden-only";
  return "priced-evidence-quiet";
}

function watchboardPriorityValue(row, sort = "triage") {
  if (!row.materialized) return Number.NEGATIVE_INFINITY;
  if (sort === "issuer") return Math.max(0, safeNumber(row.issuerForegoneLowerBound));
  if (sort === "reviewer") return row.wrongReviewerCost === null ? Number.NEGATIVE_INFINITY : Math.max(0, safeNumber(row.wrongReviewerCost));
  if (sort === "hidden") return row.hiddenFraudGroups === null ? Number.NEGATIVE_INFINITY : Math.max(0, safeNumber(row.hiddenFraudGroups));
  if (sort === "value") return row.tLo === null ? Number.NEGATIVE_INFINITY : row.tLo;
  if (sort === "recent") return row.game;
  return row.combinedEvidenceLoad === null ? Math.max(0, safeNumber(row.issuerForegoneLowerBound)) : Math.max(0, safeNumber(row.combinedEvidenceLoad));
}

function buildWatchboard(itemIndex, regretRows, watchedValues, options = {}) {
  const sort = WATCHBOARD_SORTS.has(options.sort) ? options.sort : "triage";
  const reviewerAvailable = options.reviewerAvailable === true;
  const identifiers = watchboardIdentifiers(watchedValues);
  const enriched = peerEnrichedRows(itemIndex, regretRows);
  const byKey = new Map(enriched.map(row => [`${row.game}:${row.item}`, row]));
  const rows = identifiers.map(identifier => {
    const indexed = byKey.get(identifier.key);
    if (!indexed) return {...identifier, materialized: false, mode: "not-materialised", priority: Number.NEGATIVE_INFINITY};
    const peerResult = buildPeerForensics(itemIndex, regretRows, identifier.game, identifier.item, {
      cohort: "source-bucket",
      metric: reviewerAvailable ? "combined" : "issuer",
      reviewerAvailable,
    });
    const metricKey = reviewerAvailable ? "combined" : "issuer";
    const metric = peerResult.metrics.find(candidate => candidate.key === metricKey);
    const row = {
      ...indexed, ...identifier, materialized: true,
      wrongReviewerCost: reviewerAvailable ? indexed.wrongReviewerCost : null,
      combinedEvidenceLoad: reviewerAvailable ? indexed.combinedEvidenceLoad : null,
      hiddenFraudGroups: reviewerAvailable ? indexed.hiddenFraudGroups : null,
      priorPeerCount: peerResult.denominator.priorPeers,
      priorMetric: metricKey,
      priorMetricObservations: metric?.prior.observations || 0,
      priorPercentile: metric?.prior.percentile ?? null,
      nearestPriorDistance: peerResult.priorAnalogues[0]?.distance ?? null,
    };
    row.mode = watchboardEvidenceMode(row, reviewerAvailable);
    row.priority = watchboardPriorityValue(row, sort);
    return row;
  }).sort((a, b) => b.priority - a.priority || b.game - a.game || a.item - b.item);

  const materialized = rows.filter(row => row.materialized);
  const sum = field => materialized.reduce((total, row) => total + Math.max(0, safeNumber(row[field])), 0);
  const totals = {
    requestedIdentifiers: identifiers.length,
    materializedItems: materialized.length,
    unavailableItems: rows.length - materialized.length,
    labelledItems: materialized.filter(row => row.tLo !== null).length,
    decidedItems: materialized.filter(row => row.a !== null && row.b !== null).length,
    issuerForegoneLowerBound: sum("issuerForegoneLowerBound"),
    wrongReviewerCost: reviewerAvailable ? sum("wrongReviewerCost") : null,
    combinedEvidenceLoad: reviewerAvailable ? sum("combinedEvidenceLoad") : null,
    hiddenFraudGroups: reviewerAvailable ? sum("hiddenFraudGroups") : null,
    collisions: reviewerAvailable ? materialized.filter(row => row.mode === "two-role-collision").length : null,
    itemsWithPriorMetric: materialized.filter(row => row.priorMetricObservations > 0).length,
    thinPriorContext: materialized.filter(row => row.priorPeerCount < 5).length,
  };
  const loads = materialized.map(row => reviewerAvailable ? row.combinedEvidenceLoad : row.issuerForegoneLowerBound)
    .filter(value => Number.isFinite(value) && value > 0).sort((a, b) => b - a);
  const totalLoad = loads.reduce((total, value) => total + value, 0);
  totals.itemsWithPositivePriority = loads.length;
  totals.topOneShare = totalLoad > 0 ? loads[0] / totalLoad : null;
  totals.topThreeShare = totalLoad > 0 ? loads.slice(0, 3).reduce((total, value) => total + value, 0) / totalLoad : null;
  const modeCounts = Object.fromEntries([...new Set(rows.map(row => row.mode))].sort().map(mode => [mode, rows.filter(row => row.mode === mode).length]));
  return {available: rows.length > 0, reviewerAvailable, sort, identifiers, rows, totals, modeCounts};
}

function buildWatchboardReceipt(result, materializedAt) {
  return {
    version: 1,
    status: "offline-identifier-only-watchboard-evidence",
    materializedAt,
    reviewerEvidenceAvailable: result.reviewerAvailable,
    sort: result.sort,
    denominator: {...result.totals},
    modeCounts: {...result.modeCounts},
    items: result.rows.map(row => ({
      game: row.game, item: row.item, materialized: row.materialized, mode: row.mode,
      source: row.materialized ? row.source : null, bucket: row.materialized ? row.bucket : null,
      status: row.materialized ? row.status : null, charge: row.materialized ? row.a : null,
      acceptanceLimit: row.materialized ? row.b : null, beliefMedian: row.materialized ? row.median : null,
      floor: row.materialized ? row.tLo : null, ceiling: row.materialized ? row.tHi : null,
      issuerForegoneLowerBound: row.materialized ? row.issuerForegoneLowerBound : null,
      wrongReviewerCost: row.materialized ? row.wrongReviewerCost : null,
      hiddenFraudGroups: row.materialized ? row.hiddenFraudGroups : null,
      priorMetric: row.materialized ? row.priorMetric : null,
      priorMetricObservations: row.materialized ? row.priorMetricObservations : 0,
      priorPercentile: row.materialized ? row.priorPercentile : null,
    })),
    boundaries: [
      "browser persistence contains game and item identifiers only",
      "sorting preserves one fixed requested-identifier universe and never filters quiet or unavailable rows",
      "additive evidence load is a retrospective triage index rather than causal, avoidable, or recoverable impact",
      "issuer evidence is a proven lower bound and reviewer evidence is observed settlement on proven decision classes",
      "rejected fraudulent attempted amounts remain invisible and contribute counts only",
      "reviewer-derived values remain missing when the reviewer ledger is unavailable",
      "strictly prior peer context uses only lower game identifiers and is descriptive rather than semantic",
      "no process, belief, charge, limit, rule, model, or submission is modified",
    ],
  };
}

const REGRET_WINDOWS = new Set(["all", "last-10", "last-20", "first-half", "second-half"]);
const REGRET_BUCKETS = Object.freeze(["0–50", "50–400", "400–1200", "1200+", "unlabelled"]);
const REGRET_FOCUS = new Set(["combined", "issuer", "reviewer", "hidden"]);

function regretGameIds(gameIds, window = "all") {
  const games = [...new Set((gameIds || []).map(Number).filter(Number.isInteger))].sort((a, b) => a - b);
  const selectedWindow = REGRET_WINDOWS.has(window) ? window : "all";
  if (selectedWindow === "last-10") return games.slice(-10);
  if (selectedWindow === "last-20") return games.slice(-20);
  const middle = Math.ceil(games.length / 2);
  if (selectedWindow === "first-half") return games.slice(0, middle);
  if (selectedWindow === "second-half") return games.slice(middle);
  return games;
}

function regretValueBucket(floor) {
  if (floor === null || floor === undefined || !Number.isFinite(Number(floor))) return "unlabelled";
  const value = Number(floor);
  if (value < 50) return "0–50";
  if (value < 400) return "50–400";
  if (value < 1200) return "400–1200";
  return "1200+";
}

function regretIssuerStatus(row) {
  if (row.tLo === null || row.tLo === undefined || row.a === null || row.a === undefined) return "unlabelled";
  if (row.status === "under") return "under";
  if (row.status === "over") return "over";
  if (row.status === "above-floor-open-ceiling") return "open";
  if (["inside-bracket", "not-proven-wrong"].includes(row.status)) return "inside";
  return "unresolved";
}

function regretReviewerDirection(row) {
  const rejectFair = row.rejectFairCount > 0;
  const acceptFraud = row.acceptFraudCount > 0;
  if (rejectFair && acceptFraud) return "mixed";
  if (rejectFair) return "reject-fair";
  if (acceptFraud) return "accept-fraud";
  if (row.hiddenFraudGroups > 0) return "hidden-only";
  return "none";
}

function regretAggregateRows(rows) {
  const totals = {
    items: rows.length, decidedItems: 0, labelledItems: 0, reviewerCells: 0,
    provenReviewerCells: 0, issuerForegoneLowerBound: 0, rejectFairCost: 0,
    acceptFraudCost: 0, wrongReviewerCost: 0, observedReviewerCost: 0,
    combinedEvidenceLoad: 0, hiddenFraudGroups: 0, overlapItems: 0,
    rejectFairCount: 0, acceptFraudCount: 0,
  };
  rows.forEach(row => {
    if (row.a !== null) totals.decidedItems += 1;
    if (row.tLo !== null) totals.labelledItems += 1;
    totals.reviewerCells += row.reviewerCells;
    totals.provenReviewerCells += row.provenReviewerCells;
    totals.issuerForegoneLowerBound += row.issuerForegoneLowerBound;
    totals.rejectFairCost += row.rejectFairCost;
    totals.acceptFraudCost += row.acceptFraudCost;
    totals.wrongReviewerCost += row.wrongReviewerCost;
    totals.observedReviewerCost += row.observedReviewerCost;
    totals.combinedEvidenceLoad += row.combinedEvidenceLoad;
    totals.hiddenFraudGroups += row.hiddenFraudGroups;
    totals.rejectFairCount += row.rejectFairCount;
    totals.acceptFraudCount += row.acceptFraudCount;
    if (row.issuerForegoneLowerBound > 0 && row.wrongReviewerCost > 0) totals.overlapItems += 1;
  });
  const ranked = rows.map(row => row.combinedEvidenceLoad).filter(value => value > 0).sort((a, b) => b - a);
  totals.itemsWithEvidenceLoad = ranked.length;
  const gameLoads = new Map();
  rows.forEach(row => gameLoads.set(row.game, safeNumber(gameLoads.get(row.game)) + row.combinedEvidenceLoad));
  totals.representedGames = gameLoads.size;
  totals.evidenceLoadPerItem = totals.items ? totals.combinedEvidenceLoad / totals.items : null;
  totals.topGameShare = totals.combinedEvidenceLoad > 0 ? Math.max(0, ...gameLoads.values()) / totals.combinedEvidenceLoad : null;
  totals.topOneShare = totals.combinedEvidenceLoad > 0 ? safeNumber(ranked[0]) / totals.combinedEvidenceLoad : null;
  totals.topTenShare = totals.combinedEvidenceLoad > 0 ? ranked.slice(0, 10).reduce((sum, value) => sum + value, 0) / totals.combinedEvidenceLoad : null;
  totals.wrongReviewerCostShare = totals.observedReviewerCost > 0 ? totals.wrongReviewerCost / totals.observedReviewerCost : null;
  return totals;
}

function regretGroupedRows(rows, fields) {
  const groups = new Map();
  rows.forEach(row => {
    const key = fields.map(field => String(row[field])).join("\u001f");
    if (!groups.has(key)) groups.set(key, {values: fields.map(field => row[field]), rows: []});
    groups.get(key).rows.push(row);
  });
  return [...groups.values()].map(group => {
    const record = Object.fromEntries(fields.map((field, index) => [field, group.values[index]]));
    return {...record, ...regretAggregateRows(group.rows)};
  });
}

function buildRegretCartography(itemIndex, reviewerCells, allGameIds, options = {}) {
  const window = REGRET_WINDOWS.has(options.window) ? options.window : "all";
  const source = typeof options.source === "string" && options.source ? options.source : "all";
  const bucket = options.bucket === "all" || REGRET_BUCKETS.includes(options.bucket) ? options.bucket : "all";
  const focus = REGRET_FOCUS.has(options.focus) ? options.focus : "combined";
  const gameIds = regretGameIds(allGameIds, window), selectedGames = new Set(gameIds);
  const rows = (itemIndex || []).filter(row => {
    if (!selectedGames.has(Number(row.game))) return false;
    if (source !== "all" && (row.source || "belief-source-missing") !== source) return false;
    return bucket === "all" || regretValueBucket(row.tLo) === bucket;
  }).map(row => ({
    game: Number(row.game), item: Number(row.item), source: row.source || "belief-source-missing",
    bucket: regretValueBucket(row.tLo), issuerStatus: regretIssuerStatus(row),
    a: row.a === null || row.a === undefined ? null : Number(row.a),
    b: row.b === null || row.b === undefined ? null : Number(row.b),
    tLo: row.tLo === null || row.tLo === undefined ? null : Number(row.tLo),
    tHi: row.tHi === null || row.tHi === undefined ? null : Number(row.tHi),
    issuerForegoneLowerBound: Math.max(0, safeNumber(row.foregoneLowerBound)),
    reviewerCells: 0, provenReviewerCells: 0, observedReviewerCost: 0,
    rejectFairCost: 0, acceptFraudCost: 0, wrongReviewerCost: 0,
    rejectFairCount: 0, acceptFraudCount: 0, hiddenFraudGroups: 0,
  }));
  const byItem = new Map(rows.map(row => [`${row.game}:${row.item}`, row]));
  (reviewerCells || []).forEach(cell => {
    const row = byItem.get(`${Number(cell.game)}:${Number(cell.item)}`);
    if (!row) return;
    row.reviewerCells += 1;
    if (["fair", "fraud"].includes(cell.provenClass)) row.provenReviewerCells += 1;
    row.observedReviewerCost += Math.max(0, safeNumber(cell.actualCost));
    if (cell.outcome === "rejectFair") {
      row.rejectFairCount += 1;
      row.rejectFairCost += Math.max(0, safeNumber(cell.actualCost));
    } else if (cell.outcome === "acceptFraud") {
      row.acceptFraudCount += 1;
      row.acceptFraudCost += Math.max(0, safeNumber(cell.actualCost));
    }
    const hiddenRejectedFraud = cell.outcome === "rejectFraud" && cell.provenClass === "fraud" &&
      (cell.chargeKind === "hidden" || cell.evidenceKind === "unpaid-rejection-hidden" || cell.hiddenFraudEligible === true);
    if (hiddenRejectedFraud) row.hiddenFraudGroups += 1;
  });
  rows.forEach(row => {
    row.wrongReviewerCost = row.rejectFairCost + row.acceptFraudCost;
    row.combinedEvidenceLoad = row.issuerForegoneLowerBound + row.wrongReviewerCost;
    row.reviewerDirection = regretReviewerDirection(row);
  });
  const totals = regretAggregateRows(rows);
  const games = regretGroupedRows(rows, ["game"]).sort((a, b) => Number(a.game) - Number(b.game));
  const taxonomy = regretGroupedRows(rows, ["issuerStatus", "reviewerDirection"])
    .sort((a, b) => b.combinedEvidenceLoad - a.combinedEvidenceLoad || b.items - a.items);
  const sources = regretGroupedRows(rows, ["source"])
    .sort((a, b) => b.combinedEvidenceLoad - a.combinedEvidenceLoad || b.items - a.items);
  const bucketOrder = new Map(REGRET_BUCKETS.map((value, index) => [value, index]));
  const buckets = regretGroupedRows(rows, ["bucket"])
    .sort((a, b) => safeNumber(bucketOrder.get(a.bucket), 99) - safeNumber(bucketOrder.get(b.bucket), 99));
  const sourceBuckets = regretGroupedRows(rows, ["source", "bucket"])
    .sort((a, b) => String(a.source).localeCompare(String(b.source)) || safeNumber(bucketOrder.get(a.bucket), 99) - safeNumber(bucketOrder.get(b.bucket), 99));
  const focusedRows = rows.filter(row => focus === "combined" ? row.combinedEvidenceLoad > 0
    : focus === "issuer" ? row.issuerForegoneLowerBound > 0
    : focus === "reviewer" ? row.wrongReviewerCost > 0
    : row.hiddenFraudGroups > 0);
  return {
    filters: {window, source, bucket, focus}, gameIds, rows, focusedRows, totals, games, taxonomy, sources, buckets, sourceBuckets,
    ranked: [...rows].sort((a, b) => b.combinedEvidenceLoad - a.combinedEvidenceLoad || b.hiddenFraudGroups - a.hiddenFraudGroups || a.game - b.game || a.item - b.item),
  };
}

function regretRecurrenceEvidence(rows, focus = "combined") {
  const focusValue = row => focus === "issuer" ? row.issuerForegoneLowerBound
    : focus === "reviewer" ? row.wrongReviewerCost
    : focus === "hidden" ? row.hiddenFraudGroups : row.combinedEvidenceLoad;
  const byGame = new Map();
  (rows || []).forEach(row => byGame.set(row.game, safeNumber(byGame.get(row.game)) + Math.max(0, safeNumber(focusValue(row)))));
  const total = [...byGame.values()].reduce((sum, value) => sum + value, 0);
  const positiveGames = [...byGame.values()].filter(value => value > 0).length;
  const topGameShare = total > 0 ? Math.max(0, ...byGame.values()) / total : null;
  let recurrence = "repeated evidence";
  if (!(total > 0)) recurrence = "no positive focus";
  else if ((rows || []).length < 5 || byGame.size < 3) recurrence = "sparse denominator";
  else if (topGameShare > .65) recurrence = "game-concentrated";
  else if (positiveGames < 3) recurrence = "limited recurrence";
  return {items: (rows || []).length, representedGames: byGame.size, positiveGames, topGameShare, recurrence};
}

function buildRegretReceipt(result, materializedAt) {
  return {
    version: 1, status: "offline-two-role-bounded-observed-evidence-only", materializedAt,
    filters: {...result.filters}, games: result.gameIds,
    denominator: {
      items: result.totals.items,
      reviewerCells: result.totals.reviewerCells,
      provenReviewerCells: result.totals.provenReviewerCells,
    },
    totals: {...result.totals},
    sourceReconciliation: result.reconciliation ? {...result.reconciliation} : null,
    gamesEvidence: result.games.map(row => ({
      game: Number(row.game), items: row.items,
      issuerForegoneLowerBound: row.issuerForegoneLowerBound,
      wrongReviewerCost: row.wrongReviewerCost,
      hiddenFraudGroups: row.hiddenFraudGroups,
      combinedEvidenceLoad: row.combinedEvidenceLoad,
    })),
    leadingItems: result.ranked.slice(0, 20).map(row => ({
      game: row.game, item: row.item, issuerStatus: row.issuerStatus,
      reviewerDirection: row.reviewerDirection,
      issuerForegoneLowerBound: row.issuerForegoneLowerBound,
      wrongReviewerCost: row.wrongReviewerCost,
      hiddenFraudGroups: row.hiddenFraudGroups,
      combinedEvidenceLoad: row.combinedEvidenceLoad,
    })),
    boundaries: [
      "issuer component is a proven lower bound: 16 × (sanctioned floor − Oasis charge) only when charge is at or below that floor",
      "reviewer component is observed wrong-decision settlement cost for proven reject-fair and accept-fraud groups",
      "the arithmetic sum is an evidence-load index, not causal avoidable loss or a tournament counterfactual",
      "rejected fraudulent charge sizes remain unpriced; only their group count is reported",
      "inside, open-ceiling, unresolved, and unlabelled states are never promoted into exact fair-value labels",
      "filters define retrospective evidence slices and do not create temporal holdouts or matched treatments",
      "no process, belief, charge, limit, rule, model, or submission is modified",
    ],
  };
}

function regretIssuerLabel(status) {
  return ({under: "provably under", over: "provably over", inside: "inside finite bracket", open: "above floor · ceiling open", unresolved: "bounded unresolved", unlabelled: "no sanctioned floor"})[status] || status;
}

function regretReviewerLabel(direction) {
  return ({"reject-fair": "reject fair", "accept-fraud": "accept fraud", mixed: "both wrong directions", "hidden-only": "hidden rejected fraud only", none: "no priced wrong review"})[direction] || direction;
}

function populateRegretControls() {
  if (!state.overview) return;
  const control = $("#regret-source"), previous = state.regretSource;
  const sources = [...new Set(state.overview.itemIndex.map(row => row.source || "belief-source-missing"))].sort((a, b) => a.localeCompare(b));
  clear(control); control.append(element("option", {value: "all", text: "All belief sources"}));
  sources.forEach(source => control.append(element("option", {value: source, text: source})));
  state.regretSource = previous === "all" || sources.includes(previous) ? previous : "all";
  state.regretWindow = REGRET_WINDOWS.has(state.regretWindow) ? state.regretWindow : "all";
  state.regretBucket = state.regretBucket === "all" || REGRET_BUCKETS.includes(state.regretBucket) ? state.regretBucket : "all";
  state.regretFocus = REGRET_FOCUS.has(state.regretFocus) ? state.regretFocus : "combined";
  control.value = state.regretSource;
  $("#regret-window").value = state.regretWindow;
  $("#regret-bucket").value = state.regretBucket;
  $$('[data-regret-focus]').forEach(button => {
    const active = button.dataset.regretFocus === state.regretFocus;
    button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
  });
}

function renderRegretNarrative(result) {
  const host = $("#regret-narrative"); clear(host); const totals = result.totals;
  const issuerShare = totals.combinedEvidenceLoad > 0 ? totals.issuerForegoneLowerBound / totals.combinedEvidenceLoad : null;
  const rejectAverage = totals.rejectFairCount ? totals.rejectFairCost / totals.rejectFairCount : null;
  const acceptAverage = totals.acceptFraudCount ? totals.acceptFraudCost / totals.acceptFraudCount : null;
  const asymmetry = rejectAverage !== null && acceptAverage > 0 ? rejectAverage / acceptAverage : null;
  const primary = totals.combinedEvidenceLoad > 0
    ? `${formatCurrency(totals.combinedEvidenceLoad)} additive bounded / observed evidence load`
    : "No priced two-role evidence load in this retrospective slice";
  host.dataset.tone = totals.combinedEvidenceLoad > 0 ? "evidence" : "quiet";
  host.append(
    element("div", {class: "regret-narrative-primary"}, [element("span", {text: "TWO-ROLE ACCOUNTING · NOT CAUSAL REGRET"}), element("strong", {text: primary}), element("small", {text: `${formatNumber(totals.items)} indexed items · issuer component ${formatPercent(issuerShare)} · reviewer component ${formatPercent(issuerShare === null ? null : 1 - issuerShare)}`})]),
    element("div", {class: "regret-narrative-fact"}, [element("span", {text: "SAME-ITEM COLLISION"}), element("strong", {text: `${formatNumber(totals.overlapItems)} items`}), element("small", {text: "positive provable issuer shortfall and observed wrong-review cost on the same game/item identifier"})]),
    element("div", {class: "regret-narrative-fact"}, [element("span", {text: "FILTERED ERROR ASYMMETRY"}), element("strong", {text: asymmetry === null ? "insufficient priced cells" : `${formatNumber(asymmetry, 2)}× reject-fair / accept-fraud`}), element("small", {text: `${formatNumber(totals.rejectFairCount)} reject-fair vs ${formatNumber(totals.acceptFraudCount)} accept-fraud reviewer groups · observed averages only`})]),
    element("div", {class: "regret-narrative-fact"}, [element("span", {text: "INVISIBLE TAIL · SOURCE AUDIT"}), element("strong", {text: `${formatNumber(totals.hiddenFraudGroups)} groups stay unpriced`}), element("small", {text: result.reconciliation?.maxMoneyResidual === null ? "attempted amounts are never inferred · source-summary audit applies only to the unfiltered ledger" : `attempted amounts are never inferred · max source-summary rounding residual ${formatCurrency(result.reconciliation?.maxMoneyResidual)}`})]),
  );
}

function renderRegretKpis(result) {
  const host = $("#regret-kpis"); clear(host); const totals = result.totals;
  const cards = [
    ["Fixed item universe", formatNumber(totals.items), `${formatNumber(totals.decidedItems)} decided · ${formatNumber(totals.labelledItems)} with sanctioned floor`, ""],
    ["Issuer shortfall LB", formatCurrency(totals.issuerForegoneLowerBound), "16 × (floor − charge), provably undercharged items only", "negative"],
    ["Observed wrong-review", formatCurrency(totals.wrongReviewerCost), `${formatCurrency(totals.rejectFairCost)} reject-fair · ${formatCurrency(totals.acceptFraudCost)} accept-fraud`, "negative"],
    ["Additive evidence load", formatCurrency(totals.combinedEvidenceLoad), "issuer lower bound + observed wrong-review settlement · not recoverable impact", ""],
    ["Heavy-tail concentration", formatPercent(totals.topOneShare), `top one item · top ten ${formatPercent(totals.topTenShare)} of additive load`, ""],
    ["Hidden rejected fraud", formatNumber(totals.hiddenFraudGroups), `unpriced groups across ${formatNumber(totals.reviewerCells)} reviewer cells`, "warning"],
  ];
  cards.forEach(([label, value, note, tone]) => host.append(element("div", {class: "regret-kpi"}, [element("span", {text: label}), element("strong", {class: tone, text: value}), element("small", {text: note})])));
}

function regretFocusValue(row, focus = state.regretFocus) {
  if (focus === "issuer") return row.issuerForegoneLowerBound;
  if (focus === "reviewer") return row.wrongReviewerCost;
  if (focus === "hidden") return row.hiddenFraudGroups;
  return row.combinedEvidenceLoad;
}

function renderRegretAtlas(result) {
  const host = $("#regret-atlas-chart"); clear(host); const rows = result.rows;
  if (!rows.length) { host.append(element("div", {class: "empty-state"}, [element("p", {text: "No indexed items match this evidence slice."})])); return; }
  const width = 930, height = 530, margin = {left: 78, right: 35, top: 42, bottom: 64};
  const maxX = Math.max(1, ...rows.map(row => row.issuerForegoneLowerBound));
  const maxY = Math.max(1, ...rows.map(row => row.wrongReviewerCost));
  const x = value => margin.left + Math.log1p(Math.max(0, value)) / Math.log1p(maxX) * (width - margin.left - margin.right);
  const y = value => height - margin.bottom - Math.log1p(Math.max(0, value)) / Math.log1p(maxY) * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Item-level two-role evidence atlas");
  const tickValues = maximum => [...new Set([0, .25, .5, .75, 1].map(part => Math.expm1(Math.log1p(maximum) * part)))];
  tickValues(maxX).forEach(value => { const xx = x(value); svg.append(svgElement("line", {x1: xx, y1: margin.top, x2: xx, y2: height - margin.bottom, class: "grid-line"})); svg.append(svgElement("text", {x: xx, y: height - 35, class: "axis-label", "text-anchor": "middle"}, formatCurrency(value, true))); });
  tickValues(maxY).forEach(value => { const yy = y(value); svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"})); svg.append(svgElement("text", {x: margin.left - 10, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true))); });
  const statusColor = {under: colors.red, over: colors.amber, inside: colors.green, open: colors.blue, unresolved: colors.violet, unlabelled: colors.muted};
  const focused = new Set(result.focusedRows.map(row => `${row.game}:${row.item}`));
  [...rows].sort((a, b) => regretFocusValue(a) - regretFocusValue(b)).forEach(row => {
    const key = `${row.game}:${row.item}`, active = focused.has(key), value = Math.max(0, regretFocusValue(row));
    const radius = 3 + (value > 0 ? Math.min(7, Math.log1p(value) / Math.log1p(Math.max(1, ...rows.map(candidate => regretFocusValue(candidate)))) * 7) : 0);
    const point = svgElement("circle", {cx: x(row.issuerForegoneLowerBound), cy: y(row.wrongReviewerCost), r: radius, fill: statusColor[row.issuerStatus] || colors.muted, "fill-opacity": active ? .82 : .18, stroke: row.hiddenFraudGroups ? colors.violet : active ? "rgba(255,255,255,.35)" : "transparent", "stroke-width": row.hiddenFraudGroups ? 1.7 : .8, "stroke-dasharray": row.hiddenFraudGroups ? "3 2" : "none", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game} item ${row.item}`});
    addTooltip(point, [`Game ${row.game} item ${row.item}`, `issuer ${formatCurrency(row.issuerForegoneLowerBound)} lower bound · wrong review ${formatCurrency(row.wrongReviewerCost)} observed`, `${regretIssuerLabel(row.issuerStatus)} · ${regretReviewerLabel(row.reviewerDirection)}`, `${row.hiddenFraudGroups} hidden rejected-fraud groups · additive evidence ${formatCurrency(row.combinedEvidenceLoad)}`]);
    point.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); });
    point.addEventListener("keydown", async event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); await selectGame(row.game); await selectItem(row.item, {scroll: true}); } });
    svg.append(point);
  });
  svg.append(svgElement("text", {x: width / 2, y: height - 8, class: "axis-title", "text-anchor": "middle"}, "PROVABLE ISSUER SHORTFALL LOWER BOUND · EUR · LOG1P SPACING"));
  svg.append(svgElement("text", {x: 17, y: height / 2, class: "axis-title", transform: `rotate(-90 17 ${height / 2})`, "text-anchor": "middle"}, "OBSERVED WRONG-REVIEW SETTLEMENT · EUR · LOG1P"));
  const legend = [["under", "UNDER"], ["over", "OVER"], ["inside", "INSIDE"], ["open", "OPEN"], ["unresolved", "UNRESOLVED"], ["unlabelled", "UNLABELLED"]];
  legend.forEach(([status, label], index) => { const xx = margin.left + index * 108; svg.append(svgElement("circle", {cx: xx + 4, cy: 14, r: 3.5, fill: statusColor[status]})); svg.append(svgElement("text", {x: xx + 12, y: 17, fill: colors.muted, "font-size": 7, "font-family": "var(--mono)"}, label)); });
  svg.append(svgElement("text", {x: width - margin.right, y: 31, fill: colors.violet, "font-size": 7, "font-family": "var(--mono)", "text-anchor": "end"}, "DASHED RING = HIDDEN REJECTED FRAUD · DIM = OUTSIDE ACTIVE FOCUS"));
  host.append(svg);
}

function renderRegretConcentration(result) {
  const host = $("#regret-concentration-chart"), list = $("#regret-tail-list"); clear(host); clear(list);
  const focus = result.filters.focus;
  const rows = [...result.rows].filter(row => regretFocusValue(row, focus) > 0).sort((a, b) => regretFocusValue(b, focus) - regretFocusValue(a, focus) || a.game - b.game || a.item - b.item);
  const total = rows.reduce((sum, row) => sum + regretFocusValue(row, focus), 0);
  const focusLabel = ({combined: "additive evidence load", issuer: "issuer shortfall lower bound", reviewer: "observed wrong-review cost", hidden: "hidden rejected-fraud group count"})[focus];
  const displayValue = value => focus === "hidden" ? formatNumber(value) : formatCurrency(value, true);
  $("#regret-concentration-caption").textContent = `ranked ${focusLabel} · selected item universe stays fixed`;
  host.setAttribute("aria-label", `Cumulative concentration of ${focusLabel}`);
  if (!rows.length || !(total > 0)) { host.append(element("div", {class: "empty-state"}, [element("p", {text: `No positive ${focusLabel} exists in this slice.`})])); return; }
  const width = 760, height = 300, margin = {left: 58, right: 24, top: 34, bottom: 46}; let running = 0;
  const points = [[margin.left, height - margin.bottom]];
  rows.forEach((row, index) => { running += regretFocusValue(row, focus); points.push([margin.left + (index + 1) / rows.length * (width - margin.left - margin.right), margin.top + (1 - running / total) * (height - margin.top - margin.bottom)]); });
  const svg = svgRoot(width, height, "Cumulative concentration of additive item evidence load");
  [0,.25,.5,.75,1].forEach(value => { const yy = margin.top + (1 - value) * (height - margin.top - margin.bottom), xx = margin.left + value * (width - margin.left - margin.right); svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"})); svg.append(svgElement("text", {x: margin.left - 8, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatPercent(value))); svg.append(svgElement("text", {x: xx, y: height - 20, class: "axis-label", "text-anchor": "middle"}, formatPercent(value))); });
  svg.append(svgElement("path", {d: `M${margin.left},${height - margin.bottom} L${width - margin.right},${margin.top}`, fill: "none", stroke: colors.muted, "stroke-width": 1, "stroke-dasharray": "3 5"}));
  svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: colors.cyan, "stroke-width": 2.6}));
  [1, 10, 50].filter(rank => rank <= rows.length).forEach(rank => { const point = points[rank]; const cumulative = rows.slice(0, rank).reduce((sum, row) => sum + regretFocusValue(row, focus), 0) / total; svg.append(svgElement("circle", {cx: point[0], cy: point[1], r: 4, fill: colors.amber})); svg.append(svgElement("text", {x: point[0] + 7, y: point[1] - 7, fill: colors.amber, "font-size": 8, "font-family": "var(--mono)"}, `TOP ${rank} · ${formatPercent(cumulative)}`)); });
  svg.append(svgElement("text", {x: width / 2, y: height - 4, class: "axis-title", "text-anchor": "middle"}, `ITEM RANK SHARE · ${rows.length} ITEMS · ${focusLabel.toLocaleUpperCase()}`)); host.append(svg);
  rows.slice(0, 12).forEach((row, index) => {
    const button = element("button", {type: "button", class: "regret-tail-row"}, [element("span", {text: `#${index + 1}`}), element("div", {}, [element("strong", {text: `Game ${row.game} item ${row.item}`}), element("small", {text: `${regretIssuerLabel(row.issuerStatus)} · ${regretReviewerLabel(row.reviewerDirection)}`})]), element("strong", {text: displayValue(regretFocusValue(row, focus))})]);
    button.addEventListener("click", async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); }); list.append(button);
  });
}

function renderRegretTemporal(result) {
  const host = $("#regret-temporal-chart"); clear(host); const rows = result.games;
  if (!rows.length) { host.append(element("div", {class: "empty-state"}, [element("p", {text: "No played games match this slice."})])); return; }
  const width = Math.max(920, rows.length * 20 + 105), height = 430, margin = {left: 72, right: 24, top: 42, bottom: 54};
  const maxTotal = Math.max(1, ...rows.map(row => row.combinedEvidenceLoad)), plotHeight = height - margin.top - margin.bottom;
  const step = (width - margin.left - margin.right) / rows.length, barWidth = Math.max(5, step * .62), y = value => height - margin.bottom - value / maxTotal * plotHeight;
  const svg = svgRoot(width, height, "Per-game two-role evidence load");
  [0,.25,.5,.75,1].forEach(part => { const value = maxTotal * part, yy = y(value); svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"})); svg.append(svgElement("text", {x: margin.left - 9, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatCurrency(value, true))); });
  rows.forEach((row, index) => {
    const xx = margin.left + (index + .5) * step, issuerTop = y(row.issuerForegoneLowerBound), combinedTop = y(row.combinedEvidenceLoad);
    if (row.issuerForegoneLowerBound > 0) svg.append(svgElement("rect", {x: xx - barWidth / 2, y: issuerTop, width: barWidth, height: Math.max(1, height - margin.bottom - issuerTop), fill: colors.red, "fill-opacity": .72}));
    if (row.wrongReviewerCost > 0) svg.append(svgElement("rect", {x: xx - barWidth / 2, y: combinedTop, width: barWidth, height: Math.max(1, issuerTop - combinedTop), fill: colors.amber, "fill-opacity": .8}));
    if (row.hiddenFraudGroups > 0) svg.append(svgElement("circle", {cx: xx, cy: Math.max(margin.top + 3, combinedTop - 7), r: Math.min(8, 2.5 + Math.sqrt(row.hiddenFraudGroups)), fill: "none", stroke: colors.violet, "stroke-width": 1.5}));
    const hit = svgElement("rect", {x: xx - step / 2, y: margin.top, width: step, height: plotHeight, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game}`});
    addTooltip(hit, [`Game ${row.game} · ${row.items} items`, `issuer shortfall lower bound ${formatCurrency(row.issuerForegoneLowerBound)}`, `wrong-review cost ${formatCurrency(row.wrongReviewerCost)} · reject fair ${formatCurrency(row.rejectFairCost)} · accept fraud ${formatCurrency(row.acceptFraudCost)}`, `${row.hiddenFraudGroups} hidden rejected-fraud groups · additive evidence ${formatCurrency(row.combinedEvidenceLoad)}`]);
    hit.addEventListener("click", () => openDriftGame(Number(row.game))); hit.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openDriftGame(Number(row.game)); } }); svg.append(hit);
    if (index % Math.max(1, Math.ceil(rows.length / 14)) === 0 || index === rows.length - 1) svg.append(svgElement("text", {x: xx, y: height - 22, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.red, "font-size": 8, "font-family": "var(--mono)"}, "RED = ISSUER LOWER BOUND"));
  svg.append(svgElement("text", {x: margin.left + 150, y: 18, fill: colors.amber, "font-size": 8, "font-family": "var(--mono)"}, "AMBER = OBSERVED WRONG REVIEW"));
  svg.append(svgElement("text", {x: margin.left + 345, y: 18, fill: colors.violet, "font-size": 8, "font-family": "var(--mono)"}, "VIOLET RING = HIDDEN GROUP COUNT · NOT EUR")); host.append(svg);
}

function renderRegretTaxonomy(result) {
  const host = $("#regret-taxonomy"); clear(host); const body = $("#regret-taxonomy-table"); clear(body);
  const statuses = ["under", "over", "inside", "open", "unresolved", "unlabelled"];
  const directions = ["reject-fair", "accept-fraud", "mixed", "hidden-only", "none"];
  const cells = new Map(result.taxonomy.map(row => [`${row.issuerStatus}:${row.reviewerDirection}`, row]));
  const maximum = Math.max(1, ...result.taxonomy.map(row => row.combinedEvidenceLoad));
  host.style.gridTemplateColumns = `minmax(125px,.9fr) repeat(${directions.length},minmax(105px,1fr))`;
  host.append(element("div", {class: "regret-taxonomy-corner", text: "ISSUER ↓ / REVIEWER →"}));
  directions.forEach(direction => host.append(element("div", {class: "regret-taxonomy-head", text: regretReviewerLabel(direction)})));
  statuses.forEach(status => {
    host.append(element("div", {class: "regret-taxonomy-side", text: regretIssuerLabel(status)}));
    directions.forEach(direction => {
      const row = cells.get(`${status}:${direction}`) || {items: 0, combinedEvidenceLoad: 0, issuerForegoneLowerBound: 0, wrongReviewerCost: 0, hiddenFraudGroups: 0};
      const size = row.combinedEvidenceLoad > 0 ? 18 + Math.sqrt(row.combinedEvidenceLoad / maximum) * 52 : 0;
      const cell = element("div", {class: `regret-taxonomy-cell ${row.items ? "has-data" : ""}`, role: "gridcell", "aria-label": `${regretIssuerLabel(status)}, ${regretReviewerLabel(direction)}: ${row.items} items, ${formatCurrency(row.combinedEvidenceLoad)} additive evidence load`}, [element("span", {class: "regret-taxonomy-bubble"}), element("strong", {text: formatNumber(row.items)}), element("small", {text: row.items ? `${formatCurrency(row.combinedEvidenceLoad, true)} · ${row.hiddenFraudGroups} hidden` : "—"})]);
      cell.style.setProperty("--bubble-size", `${size}px`); host.append(cell);
    });
  });
  result.taxonomy.forEach(row => body.append(element("tr", {}, [element("td", {text: regretIssuerLabel(row.issuerStatus)}), element("td", {text: regretReviewerLabel(row.reviewerDirection)}), element("td", {text: row.items}), element("td", {class: "money", text: formatCurrency(row.issuerForegoneLowerBound)}), element("td", {class: "money", text: formatCurrency(row.wrongReviewerCost)}), element("td", {text: row.hiddenFraudGroups}), element("td", {class: "money", text: formatCurrency(row.combinedEvidenceLoad)})])));
}

function renderRegretValueRegimes(result) {
  const host = $("#regret-value-chart"), body = $("#regret-value-table"); clear(host); clear(body);
  const byBucket = new Map(result.buckets.map(row => [row.bucket, row]));
  const rows = REGRET_BUCKETS.map(bucket => byBucket.get(bucket) || {bucket, items: 0, overlapItems: 0, issuerForegoneLowerBound: 0, rejectFairCost: 0, acceptFraudCost: 0, wrongReviewerCost: 0, combinedEvidenceLoad: 0, hiddenFraudGroups: 0});
  const width = 850, rowHeight = 74, height = rows.length * rowHeight + 66, margin = {left: 126, right: 96, top: 34, bottom: 40};
  const maximum = Math.max(1, ...rows.map(row => row.combinedEvidenceLoad)), scale = value => Math.max(0, value) / maximum * (width - margin.left - margin.right);
  const svg = svgRoot(width, height, "Two-role evidence burden by sanctioned-floor value regime");
  rows.forEach((row, index) => {
    const yy = margin.top + index * rowHeight, components = [["issuer", row.issuerForegoneLowerBound, colors.red], ["reject fair", row.rejectFairCost, colors.amber], ["accept fraud", row.acceptFraudCost, colors.violet]];
    let cursor = margin.left;
    components.forEach(([label, value, color]) => { const barWidth = scale(value); if (barWidth > 0) { const bar = svgElement("rect", {x: cursor, y: yy + 14, width: Math.max(1, barWidth), height: 19, rx: 2, fill: color, "fill-opacity": .78}); addTooltip(bar, [`${row.bucket} · ${label}`, `${formatCurrency(value)} on ${row.items} selected items`, `${row.overlapItems} same-item two-role collisions · ${row.hiddenFraudGroups} hidden rejected-fraud groups`]); svg.append(bar); } cursor += barWidth; });
    svg.append(svgElement("text", {x: margin.left - 10, y: yy + 25, class: "axis-label", "text-anchor": "end"}, row.bucket));
    svg.append(svgElement("text", {x: margin.left, y: yy + 49, fill: colors.muted, "font-size": 8, "font-family": "var(--mono)"}, `${row.items} ITEMS · ${row.representedGames || 0} GAMES · TOP GAME ${formatPercent(row.topGameShare)}`));
    svg.append(svgElement("text", {x: width - margin.right + 8, y: yy + 25, fill: "#d5dde3", "font-size": 8, "font-family": "var(--mono)"}, formatCurrency(row.combinedEvidenceLoad, true)));
    if (row.hiddenFraudGroups > 0) { svg.append(svgElement("circle", {cx: width - 29, cy: yy + 23, r: Math.min(9, 3 + Math.sqrt(row.hiddenFraudGroups) / 2), fill: "none", stroke: colors.violet, "stroke-width": 1.4})); svg.append(svgElement("text", {x: width - 29, y: yy + 49, fill: colors.violet, "font-size": 7, "font-family": "var(--mono)", "text-anchor": "middle"}, `${row.hiddenFraudGroups} HIDDEN`)); }
    body.append(element("tr", {}, [element("td", {text: row.bucket}), element("td", {text: row.items}), element("td", {text: row.representedGames || 0}), element("td", {text: formatPercent(row.topGameShare)}), element("td", {text: row.overlapItems}), element("td", {class: "money", text: formatCurrency(row.issuerForegoneLowerBound)}), element("td", {class: "money", text: formatCurrency(row.rejectFairCost)}), element("td", {class: "money", text: formatCurrency(row.acceptFraudCost)}), element("td", {text: row.hiddenFraudGroups}), element("td", {class: "money", text: formatCurrency(row.combinedEvidenceLoad)})]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 16, fill: colors.red, "font-size": 8, "font-family": "var(--mono)"}, "ISSUER LOWER BOUND"));
  svg.append(svgElement("text", {x: margin.left + 142, y: 16, fill: colors.amber, "font-size": 8, "font-family": "var(--mono)"}, "REJECT-FAIR COST"));
  svg.append(svgElement("text", {x: margin.left + 276, y: 16, fill: colors.violet, "font-size": 8, "font-family": "var(--mono)"}, "ACCEPT-FRAUD COST"));
  svg.append(svgElement("text", {x: margin.left, y: height - 11, class: "axis-title"}, `LINEAR EUR SCALE · MAX REGIME ${formatCurrency(maximum)} · ABSENT REGIMES STAY ZERO`)); host.append(svg);
}

function regretRouteEvidence(result, source, bucket) {
  const rows = result.rows.filter(row => row.source === source && row.bucket === bucket);
  return regretRecurrenceEvidence(rows, result.filters.focus);
}

function renderRegretRoutingLattice(result) {
  const host = $("#regret-routing-lattice"), body = $("#regret-routing-table"); clear(host); clear(body);
  const focus = result.filters.focus, valueLabel = ({combined: "additive load", issuer: "issuer lower bound", reviewer: "wrong-review cost", hidden: "hidden groups"})[focus];
  const sources = [...new Set(result.rows.map(row => row.source))].sort((a, b) => a.localeCompare(b));
  const groups = new Map(result.sourceBuckets.map(row => [`${row.source}\u001f${row.bucket}`, row]));
  const cellRows = sources.flatMap(source => REGRET_BUCKETS.map(bucket => groups.get(`${source}\u001f${bucket}`) || {source, bucket, items: 0, representedGames: 0, topGameShare: null, overlapItems: 0, issuerForegoneLowerBound: 0, wrongReviewerCost: 0, combinedEvidenceLoad: 0, hiddenFraudGroups: 0}));
  const rate = row => row.items ? regretFocusValue(row, focus) / row.items : 0;
  const maximum = Math.max(1e-9, ...cellRows.map(rate));
  const valueText = value => focus === "hidden" ? `${formatNumber(value, 2)} groups/item` : `${formatCurrency(value, true)}/item`;
  $("#regret-routing-caption").textContent = `cell intensity = ${valueLabel} per selected item · totals, overlap, and hidden counts remain explicit`;
  host.setAttribute("aria-label", `Belief source by value regime matrix, intensity by ${valueLabel} per selected item`);
  host.style.gridTemplateColumns = `minmax(170px,1.25fr) repeat(${REGRET_BUCKETS.length},minmax(132px,1fr))`;
  host.append(element("div", {class: "regret-route-corner", text: "SOURCE ↓ / FLOOR →"}));
  REGRET_BUCKETS.forEach(bucket => host.append(element("div", {class: "regret-route-head", text: bucket})));
  sources.forEach(source => {
    const sourceSummary = result.sources.find(row => row.source === source);
    host.append(element("div", {class: "regret-route-side"}, [element("strong", {text: source}), element("small", {text: `${sourceSummary?.items || 0} items · ${formatCurrency(sourceSummary?.combinedEvidenceLoad || 0, true)} load`})]));
    REGRET_BUCKETS.forEach(bucket => {
      const row = groups.get(`${source}\u001f${bucket}`) || {source, bucket, items: 0, representedGames: 0, topGameShare: null, overlapItems: 0, issuerForegoneLowerBound: 0, wrongReviewerCost: 0, combinedEvidenceLoad: 0, hiddenFraudGroups: 0};
      const evidence = regretRouteEvidence(result, source, bucket);
      const intensity = Math.sqrt(rate(row) / maximum);
      const cell = element("div", {class: `regret-route-cell focus-${focus} ${row.items ? "has-data" : ""}`, role: "gridcell", "aria-label": `${source}, ${bucket}: ${row.items} items in ${evidence.representedGames} games, ${valueText(rate(row))}, ${evidence.recurrence}, top-game share ${formatPercent(evidence.topGameShare)}, ${row.overlapItems} collisions, ${row.hiddenFraudGroups} hidden groups`}, [element("strong", {text: row.items ? valueText(rate(row)) : "—"}), element("span", {text: row.items ? `${focus === "hidden" ? formatNumber(regretFocusValue(row, focus)) : formatCurrency(regretFocusValue(row, focus), true)} total` : "no selected items"}), element("small", {text: row.items ? `${evidence.recurrence} · ${evidence.representedGames}G · top ${formatPercent(evidence.topGameShare)} · ${formatPercent(row.overlapItems / row.items)} collide` : "fixed empty cell"})]);
      cell.style.setProperty("--route-alpha", String(.025 + intensity * .28)); host.append(cell);
      body.append(element("tr", {}, [element("td", {text: source}), element("td", {text: bucket}), element("td", {text: row.items}), element("td", {text: evidence.representedGames}), element("td", {text: evidence.recurrence}), element("td", {text: formatPercent(evidence.topGameShare)}), element("td", {text: row.overlapItems}), element("td", {text: valueText(rate(row))}), element("td", {class: "money", text: formatCurrency(row.issuerForegoneLowerBound)}), element("td", {class: "money", text: formatCurrency(row.wrongReviewerCost)}), element("td", {text: row.hiddenFraudGroups}), element("td", {class: "money", text: formatCurrency(row.combinedEvidenceLoad)})]));
    });
  });
  if (!sources.length) host.append(element("div", {class: "empty-state"}, [element("p", {text: "No belief-source rows match this slice."})]));
}

function renderRegretTables(result) {
  const itemBody = $("#regret-item-table"), gameBody = $("#regret-game-table"); clear(itemBody); clear(gameBody);
  [...result.rows].sort((a, b) => regretFocusValue(b, result.filters.focus) - regretFocusValue(a, result.filters.focus) || b.combinedEvidenceLoad - a.combinedEvidenceLoad || a.game - b.game || a.item - b.item).forEach(row => itemBody.append(element("tr", {}, [element("td", {}, [itemLink(row.game, row.item)]), element("td", {text: row.source}), element("td", {text: row.bucket}), element("td", {text: regretIssuerLabel(row.issuerStatus)}), element("td", {text: regretReviewerLabel(row.reviewerDirection)}), element("td", {class: "money", text: formatCurrency(row.issuerForegoneLowerBound)}), element("td", {class: "money", text: formatCurrency(row.rejectFairCost)}), element("td", {class: "money", text: formatCurrency(row.acceptFraudCost)}), element("td", {class: "money", text: formatCurrency(row.wrongReviewerCost)}), element("td", {text: row.hiddenFraudGroups}), element("td", {class: "money", text: formatCurrency(row.combinedEvidenceLoad)})])));
  result.games.forEach(row => gameBody.append(element("tr", {}, [element("td", {}, [itemLink(Number(row.game), null, `Game ${row.game}`)]), element("td", {text: row.items}), element("td", {text: row.reviewerCells}), element("td", {class: "money", text: formatCurrency(row.issuerForegoneLowerBound)}), element("td", {class: "money", text: formatCurrency(row.rejectFairCost)}), element("td", {class: "money", text: formatCurrency(row.acceptFraudCost)}), element("td", {class: "money", text: formatCurrency(row.wrongReviewerCost)}), element("td", {text: row.hiddenFraudGroups}), element("td", {class: "money", text: formatCurrency(row.combinedEvidenceLoad)})])));
}

async function copyRegretReceipt() {
  if (!state.regretResult || !state.overview) { toast("Two-role evidence is unavailable to copy."); return; }
  try { await navigator.clipboard.writeText(JSON.stringify(buildRegretReceipt(state.regretResult, state.overview.generatedAt), null, 2)); toast("Claim-free two-role evidence receipt copied."); }
  catch (error) { toast(`Two-role receipt could not be copied: ${error.message}`); }
}

function renderRegretCartography() {
  if (!state.overview || !state.reviewerLab) return;
  populateRegretControls();
  const result = buildRegretCartography(state.overview.itemIndex, state.reviewerLab.cells || [], state.overview.race.gameIds, {window: state.regretWindow, source: state.regretSource, bucket: state.regretBucket, focus: state.regretFocus});
  const matrix = state.reviewerLab.summary?.matrix || {};
  const sourceWrong = safeNumber(matrix.rejectFair?.cost) + safeNumber(matrix.acceptFraud?.cost);
  const residuals = {
    reviewerCells: result.totals.reviewerCells - safeNumber(state.reviewerLab.summary?.cells),
    observedReviewerCost: result.totals.observedReviewerCost - safeNumber(state.reviewerLab.summary?.observedReviewerCost),
    rejectFairCost: result.totals.rejectFairCost - safeNumber(matrix.rejectFair?.cost),
    acceptFraudCost: result.totals.acceptFraudCost - safeNumber(matrix.acceptFraud?.cost),
    wrongReviewerCost: result.totals.wrongReviewerCost - sourceWrong,
  };
  const fullSourceLedger = result.filters.window === "all" && result.filters.source === "all" && result.filters.bucket === "all";
  result.reconciliation = fullSourceLedger
    ? {scope: "all-source-ledger", ...residuals, maxMoneyResidual: Math.max(...[residuals.observedReviewerCost, residuals.rejectFairCost, residuals.acceptFraudCost, residuals.wrongReviewerCost].map(Math.abs))}
    : {scope: "filtered-slice-not-comparable-to-all-source-summary", maxMoneyResidual: null};
  state.regretResult = result;
  $("#regret-status").textContent = `${formatNumber(result.totals.items)} ITEMS · ${formatNumber(result.totals.reviewerCells)} REVIEWER CELLS · ${result.gameIds.length} GAMES · ${state.regretFocus.toLocaleUpperCase()} FOCUS`;
  renderRegretNarrative(result); renderRegretKpis(result); renderRegretAtlas(result);
  renderRegretConcentration(result); renderRegretTemporal(result); renderRegretTaxonomy(result);
  renderRegretValueRegimes(result); renderRegretRoutingLattice(result); renderRegretTables(result);
}

const DRIFT_METRICS = Object.freeze({
  net: {label: "Net score", unit: "eur", direction: "high", denominator: "one played game"},
  income: {label: "Issuer income", unit: "eur", direction: "high", denominator: "one played game"},
  "reviewer-cost": {label: "Reviewer cost", unit: "eur", direction: "low", denominator: "one played game · observed settlement EUR"},
  "wrong-cost-share": {label: "Wrong-decision cost share", unit: "share", direction: "low", denominator: "observed proven reviewer-cost EUR per game"},
  "valuation-error": {label: "Median absolute valuation error", unit: "abs-log", direction: "low", denominator: "items with Oasis charge and positive sanctioned floor per game"},
  "threshold-coverage": {label: "Sanctioned-floor coverage", unit: "share", direction: "high", denominator: "materialized items per played game"},
});

function driftQuantile(values, probability) {
  const clean = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!clean.length) return null;
  const position = clamp(probability, 0, 1) * (clean.length - 1);
  const lower = Math.floor(position), upper = Math.ceil(position);
  if (lower === upper) return clean[lower];
  return clean[lower] + (clean[upper] - clean[lower]) * (position - lower);
}

function driftMetricRows(overview, metricKey) {
  const metric = DRIFT_METRICS[metricKey] || DRIFT_METRICS.net;
  const gameIds = [...(overview?.race?.gameIds || [])].map(Number).filter(Number.isInteger).sort((a, b) => a - b);
  const economics = new Map((overview?.trends?.economics || []).map(row => [Number(row.game), row]));
  const streams = new Map((overview?.trends?.decisionStream || []).map(row => [Number(row.game), row]));
  const errors = new Map((overview?.trends?.estimationErrors || []).map(row => [Number(row.game), row]));
  const quality = new Map((overview?.intelligence?.quality || []).map(row => [Number(row.game), row]));
  return gameIds.map(game => {
    let value = null, denominatorValue = null;
    if (["net", "income", "reviewer-cost"].includes(metricKey)) {
      const row = economics.get(game);
      const field = metricKey === "reviewer-cost" ? "cost" : metricKey;
      if (row && Number.isFinite(Number(row[field]))) value = Number(row[field]);
      denominatorValue = value === null ? null : 1;
    } else if (metricKey === "wrong-cost-share") {
      const row = streams.get(game), denominator = Number(row?.denominatorEuros);
      if (Number.isFinite(denominator) && denominator > 0) {
        value = (safeNumber(row?.rejectFair?.euros) + safeNumber(row?.acceptFraud?.euros)) / denominator;
        denominatorValue = denominator;
      }
    } else if (metricKey === "valuation-error") {
      const values = (errors.get(game)?.values || []).map(Number).filter(Number.isFinite).map(Math.abs);
      value = medianNumber(values);
      denominatorValue = values.length || null;
    } else if (metricKey === "threshold-coverage") {
      const row = quality.get(game);
      if (Number.isFinite(Number(row?.thresholdCoverage))) value = Number(row.thresholdCoverage);
      denominatorValue = Number.isFinite(Number(row?.items)) ? Number(row.items) : null;
    }
    return {game, value, denominatorValue, denominator: metric.denominator};
  });
}

function robustControlSeries(rows, windowSize = 10, sensitivity = 3) {
  const window = windowSize === "all" ? null : clamp(Math.trunc(safeNumber(windowSize, 10)), 5, 100);
  const sigma = clamp(safeNumber(sensitivity, 3), 2, 4);
  const prior = [];
  return rows.map(row => {
    const value = Number(row.value);
    const finite = row.value !== null && Number.isFinite(value);
    const baselineRows = window === null ? prior : prior.slice(-window);
    let baseline = null, scale = null, lower = null, upper = null, robustZ = null;
    let status = finite ? "warm-up" : "missing";
    if (finite && baselineRows.length >= 5) {
      const baselineValues = baselineRows.map(entry => entry.value);
      baseline = medianNumber(baselineValues);
      const mad = medianNumber(baselineValues.map(entry => Math.abs(entry - baseline)));
      const iqr = safeNumber(driftQuantile(baselineValues, .75)) - safeNumber(driftQuantile(baselineValues, .25));
      scale = Math.max(1.4826 * safeNumber(mad), iqr / 1.349);
      if (Number.isFinite(scale) && scale > 1e-12) {
        lower = baseline - sigma * scale;
        upper = baseline + sigma * scale;
        robustZ = (value - baseline) / scale;
        status = Math.abs(robustZ) > sigma ? "signal" : "in-control";
      } else {
        scale = 0;
        lower = baseline;
        upper = baseline;
        status = Math.abs(value - baseline) <= 1e-12 ? "in-control" : "variance-zero";
      }
    }
    const result = {
      ...row, value: finite ? value : null, baseline, scale, lower, upper, robustZ, status,
      baselineObservations: baselineRows.length,
      baselineStartGame: baselineRows[0]?.game ?? null,
      baselineEndGame: baselineRows.at(-1)?.game ?? null,
    };
    if (finite) prior.push({game: row.game, value});
    return result;
  });
}

function buildDriftAnalysis(overview, metricKey = "net", windowSize = 10, sensitivity = 3) {
  const normalizedMetricKey = DRIFT_METRICS[metricKey] ? metricKey : "net";
  const metric = DRIFT_METRICS[normalizedMetricKey];
  const points = robustControlSeries(driftMetricRows(overview, normalizedMetricKey), windowSize, sensitivity).map(row => {
    let signal = "none";
    if (row.status === "signal" && row.robustZ !== null) {
      const favourable = metric.direction === "high" ? row.robustZ > 0 : row.robustZ < 0;
      signal = favourable ? "favourable" : "adverse";
    } else if (row.status === "variance-zero") signal = "variance-zero";
    return {...row, signal};
  });
  const observed = points.filter(row => row.value !== null);
  const evaluable = points.filter(row => ["in-control", "signal", "variance-zero"].includes(row.status));
  const flagged = points.filter(row => ["adverse", "favourable", "variance-zero"].includes(row.signal));
  const latest = [...evaluable].at(-1) || null;
  const largest = [...evaluable].filter(row => row.robustZ !== null).sort((a, b) => Math.abs(b.robustZ) - Math.abs(a.robustZ))[0] || null;
  let inControlStreak = 0;
  for (const row of [...points].reverse()) {
    if (row.value === null || row.status === "warm-up") continue;
    if (row.signal !== "none") break;
    inControlStreak += 1;
  }
  return {
    metricKey: normalizedMetricKey, metric,
    window: windowSize === "all" ? "all" : clamp(Math.trunc(safeNumber(windowSize, 10)), 5, 100),
    sensitivity: clamp(safeNumber(sensitivity, 3), 2, 4), points,
    summary: {
      games: points.length, observed: observed.length, evaluable: evaluable.length,
      flagged: flagged.length, adverse: flagged.filter(row => row.signal === "adverse").length,
      favourable: flagged.filter(row => row.signal === "favourable").length,
      varianceZero: flagged.filter(row => row.signal === "variance-zero").length,
      inControlStreak, latest, largest,
    },
  };
}

function jensenShannonDivergence(leftCounts, rightCounts) {
  const keys = new Set([...Object.keys(leftCounts || {}), ...Object.keys(rightCounts || {})]);
  const leftTotal = [...keys].reduce((sum, key) => sum + Math.max(0, safeNumber(leftCounts?.[key])), 0);
  const rightTotal = [...keys].reduce((sum, key) => sum + Math.max(0, safeNumber(rightCounts?.[key])), 0);
  if (!leftTotal || !rightTotal) return null;
  let divergence = 0;
  keys.forEach(key => {
    const p = Math.max(0, safeNumber(leftCounts?.[key])) / leftTotal;
    const q = Math.max(0, safeNumber(rightCounts?.[key])) / rightTotal;
    const midpoint = (p + q) / 2;
    if (p > 0) divergence += .5 * p * Math.log2(p / midpoint);
    if (q > 0) divergence += .5 * q * Math.log2(q / midpoint);
  });
  return clamp(divergence, 0, 1);
}

function buildSourceMixDrift(itemIndex, gameIds, windowSize = 10) {
  const window = windowSize === "all" ? null : clamp(Math.trunc(safeNumber(windowSize, 10)), 5, 100);
  const byGame = new Map();
  (itemIndex || []).forEach(row => {
    const game = Number(row.game);
    if (!Number.isInteger(game)) return;
    const source = typeof row.source === "string" && row.source.trim() ? row.source.trim().slice(0, 100) : "belief-missing";
    const counts = byGame.get(game) || {};
    counts[source] = (counts[source] || 0) + 1;
    byGame.set(game, counts);
  });
  const history = [];
  return [...(gameIds || [])].map(Number).filter(Number.isInteger).sort((a, b) => a - b).map(game => {
    const current = byGame.get(game) || {};
    const currentItems = Object.values(current).reduce((sum, value) => sum + value, 0);
    const baselineGames = (window === null ? history : history.slice(-window)).filter(row => row.items > 0);
    const baseline = {};
    baselineGames.forEach(row => Object.entries(row.counts).forEach(([source, count]) => { baseline[source] = (baseline[source] || 0) + count; }));
    const baselineItems = Object.values(baseline).reduce((sum, value) => sum + value, 0);
    const score = currentItems > 0 && baselineGames.length >= 5
      ? jensenShannonDivergence(current, baseline) : null;
    const sources = new Set([...Object.keys(current), ...Object.keys(baseline)]);
    const movers = [...sources].map(source => ({
      source,
      currentShare: currentItems ? safeNumber(current[source]) / currentItems : 0,
      baselineShare: baselineItems ? safeNumber(baseline[source]) / baselineItems : 0,
    })).map(row => ({...row, delta: row.currentShare - row.baselineShare}))
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta) || a.source.localeCompare(b.source));
    const result = {
      game, score, status: !currentItems ? "missing" : score === null ? "warm-up" : "observed",
      currentItems, baselineItems, baselineGames: baselineGames.length,
      baselineStartGame: baselineGames[0]?.game ?? null,
      baselineEndGame: baselineGames.at(-1)?.game ?? null,
      topMover: movers[0] || null,
      currentCounts: current, baselineCounts: baseline,
    };
    history.push({game, items: currentItems, counts: current});
    return result;
  });
}

function driftValue(value, metric) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "unobserved";
  if (metric.unit === "eur") return formatCurrency(value);
  if (metric.unit === "share") return formatPercent(value);
  return formatNumber(value, 3);
}

function driftDenominator(value, metricKey) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "unobserved denominator";
  if (metricKey === "wrong-cost-share") return `${formatCurrency(value)} observed proven reviewer cost`;
  if (["valuation-error", "threshold-coverage"].includes(metricKey)) return `${formatNumber(value)} items`;
  return `${formatNumber(value)} played game`;
}

function driftSegments(rows, predicate) {
  const segments = [], current = [];
  rows.forEach((row, index) => {
    if (predicate(row)) current.push({row, index});
    else if (current.length) segments.push(current.splice(0));
  });
  if (current.length) segments.push(current);
  return segments;
}

async function openDriftGame(game) {
  await selectGame(game);
  $("#game").scrollIntoView({behavior: "smooth", block: "start"});
}

function renderDriftNarrative(analysis, sourceRows) {
  const host = $("#drift-narrative"); clear(host);
  const latest = analysis.summary.latest;
  const largest = analysis.summary.largest;
  const latestSource = [...sourceRows].filter(row => row.score !== null).at(-1) || null;
  host.dataset.tone = latest?.signal || "none";
  if (!latest) {
    host.append(element("div", {}, [element("strong", {text: "Baseline still warming up"}), element("span", {text: `No ${analysis.metric.label.toLowerCase()} observation yet has five earlier observed values.`})]));
    return;
  }
  const status = latest.signal === "adverse" ? "adverse signal" : latest.signal === "favourable" ? "favourable signal" : latest.signal === "variance-zero" ? "zero-variance break" : "inside robust band";
  const detail = latest.baseline === null
    ? "prior baseline unavailable"
    : `${driftValue(latest.value, analysis.metric)} versus prior median ${driftValue(latest.baseline, analysis.metric)}${latest.robustZ === null ? "" : ` · robust z ${formatNumber(latest.robustZ, 2)}`}`;
  host.append(element("div", {class: "drift-narrative-primary"}, [
    element("span", {text: `LATEST EVALUABLE · GAME ${latest.game}`}),
    element("strong", {text: status.toUpperCase()}), element("small", {text: detail}),
  ]));
  const facts = [
    ["PRIOR WINDOW", latest.baselineStartGame === null ? "unavailable" : `G${latest.baselineStartGame}–G${latest.baselineEndGame} · n=${latest.baselineObservations}`],
    ["LARGEST |Z|", largest ? `G${largest.game} · ${formatNumber(Math.abs(largest.robustZ), 2)}` : "unavailable"],
    ["SOURCE MIX", latestSource ? `G${latestSource.game} · JSD ${formatNumber(latestSource.score, 4)}` : "warming up"],
  ];
  facts.forEach(([label, value]) => host.append(element("div", {class: "drift-narrative-fact"}, [element("span", {text: label}), element("strong", {text: value})])));
}

function renderDriftKpis(analysis) {
  const host = $("#drift-kpis"); clear(host);
  const {summary, metric} = analysis;
  const latest = summary.latest;
  const specs = [
    ["OBSERVED ROUNDS", `${summary.observed} / ${summary.games}`, metric.denominator],
    ["LAGGED BASELINE", `${summary.evaluable} rounds`, `${analysis.window === "all" ? "all" : `last ${analysis.window}`} prior observed rounds · minimum 5`],
    ["ROBUST SIGNALS", `${summary.flagged}`, `${summary.adverse} adverse · ${summary.favourable} favourable · ${summary.varianceZero} zero-variance`],
    ["LATEST OBSERVATION", latest ? driftValue(latest.value, metric) : "unavailable", latest ? `game ${latest.game} · ${driftDenominator(latest.denominatorValue, analysis.metricKey)}` : "no baseline-evaluable game"],
    ["LATEST ROBUST Z", latest?.robustZ === null || latest?.robustZ === undefined ? "unavailable" : formatNumber(latest.robustZ, 2), latest ? latest.signal === "variance-zero" ? "prior dispersion is zero · reported without an invented z" : `${latest.signal === "none" ? "inside" : latest.signal} · ${analysis.sensitivity}σ rule` : "strictly prior baseline"],
    ["CURRENT QUIET RUN", `${summary.inControlStreak} rounds`, "consecutive observed, baseline-evaluable rounds without a signal"],
  ];
  specs.forEach(([label, value, note], index) => host.append(element("div", {class: "drift-kpi"}, [
    element("span", {text: label}), element("strong", {text: value, class: index === 2 && summary.adverse ? "negative" : ""}), element("small", {text: note}),
  ])));
}

function renderDriftControlChart(analysis) {
  const host = $("#drift-control-chart"); clear(host);
  const body = $("#drift-control-table"); clear(body);
  const rows = analysis.points, width = 1180, height = 390;
  const margin = {left: 88, right: 35, top: 43, bottom: 48};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const domainValues = [];
  rows.forEach(row => [row.value, row.lower, row.upper].forEach(value => { if (value !== null && Number.isFinite(value)) domainValues.push(value); }));
  if (analysis.metric.unit === "eur") domainValues.push(0);
  if (analysis.metric.unit === "share") domainValues.push(0, 1);
  if (analysis.metric.unit === "abs-log") domainValues.push(0);
  let min = Math.min(...domainValues), max = Math.max(...domainValues);
  if (!Number.isFinite(min) || !Number.isFinite(max)) { min = 0; max = 1; }
  const pad = (max - min || Math.max(1, Math.abs(max))) * .09;
  if (analysis.metric.unit !== "share") { min -= pad; max += pad; }
  const x = index => margin.left + index / Math.max(1, rows.length - 1) * plotW;
  const y = value => margin.top + (max - value) / Math.max(1e-12, max - min) * plotH;
  const svg = svgRoot(width, height, `${analysis.metric.label} against a strictly lagged robust control band`);
  for (let tick = 0; tick <= 5; tick += 1) {
    const value = min + (max - min) * tick / 5, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 12, y: yy + 3, class: "axis-label", "text-anchor": "end"}, driftValue(value, analysis.metric)));
  }
  driftSegments(rows, row => row.lower !== null && row.upper !== null).forEach(segment => {
    const upper = segment.map(({row, index}) => `${x(index)},${y(row.upper)}`);
    const lower = [...segment].reverse().map(({row, index}) => `${x(index)},${y(row.lower)}`);
    svg.append(svgElement("path", {d: `M${upper.join(" L")} L${lower.join(" L")} Z`, fill: colors.violet, "fill-opacity": .09, stroke: "none"}));
    svg.append(svgElement("path", {d: linePath(segment.map(({row, index}) => [x(index), y(row.baseline)])), fill: "none", stroke: colors.violet, "stroke-width": 1.4, "stroke-dasharray": "5 5"}));
  });
  driftSegments(rows, row => row.value !== null).forEach(segment => {
    svg.append(svgElement("path", {d: linePath(segment.map(({row, index}) => [x(index), y(row.value)])), fill: "none", stroke: colors.cyan, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round"}));
  });
  rows.forEach((row, index) => {
    const xx = x(index);
    if (row.value === null) {
      svg.append(svgElement("path", {d: `M${xx - 3},${height - margin.bottom - 4} L${xx + 3},${height - margin.bottom + 2} M${xx + 3},${height - margin.bottom - 4} L${xx - 3},${height - margin.bottom + 2}`, stroke: colors.muted, "stroke-width": 1}));
    } else {
      const yy = y(row.value);
      let marker;
      if (row.signal === "adverse") marker = svgElement("path", {d: `M${xx},${yy - 7} L${xx + 7},${yy} L${xx},${yy + 7} L${xx - 7},${yy} Z`, fill: colors.red});
      else if (row.signal === "favourable") marker = svgElement("path", {d: `M${xx},${yy - 7} L${xx + 7},${yy + 6} L${xx - 7},${yy + 6} Z`, fill: colors.green});
      else if (row.signal === "variance-zero") marker = svgElement("rect", {x: xx - 5, y: yy - 5, width: 10, height: 10, fill: colors.amber});
      else marker = svgElement("circle", {cx: xx, cy: yy, r: row.status === "warm-up" ? 3.6 : 3, fill: row.status === "warm-up" ? "transparent" : colors.cyan, stroke: row.status === "warm-up" ? colors.muted : "none", "stroke-width": 1.3});
      svg.append(marker);
    }
    if (index % Math.max(1, Math.ceil(rows.length / 14)) === 0 || index === rows.length - 1) {
      svg.append(svgElement("text", {x: xx, y: height - 18, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    }
    const hit = svgElement("rect", {x: xx - Math.max(5, plotW / Math.max(1, rows.length) / 2), y: margin.top, width: Math.max(10, plotW / Math.max(1, rows.length)), height: plotH, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game} drift evidence`});
    const baseline = row.baseline === null ? "baseline warming up" : `prior median ${driftValue(row.baseline, analysis.metric)} · ${row.baselineObservations} observations`;
    const signal = row.signal === "none" ? row.status.replaceAll("-", " ") : row.signal.replaceAll("-", " ");
    addTooltip(hit, [`Game ${row.game} · ${analysis.metric.label}`, `${driftValue(row.value, analysis.metric)} · ${signal}`, baseline, row.robustZ === null ? `${analysis.sensitivity}σ score unavailable` : `robust z ${formatNumber(row.robustZ, 2)} · band ${driftValue(row.lower, analysis.metric)} to ${driftValue(row.upper, analysis.metric)}`, `${driftDenominator(row.denominatorValue, analysis.metricKey)} · ${row.denominator}`]);
    hit.addEventListener("click", () => openDriftGame(row.game)); svg.append(hit);
    body.append(element("tr", {}, [
      element("td", {}, [itemLink(row.game, null, `Game ${row.game}`)]),
      element("td", {text: driftValue(row.value, analysis.metric)}),
      element("td", {text: driftDenominator(row.denominatorValue, analysis.metricKey)}),
      element("td", {text: row.baseline === null ? "warm-up" : driftValue(row.baseline, analysis.metric)}),
      element("td", {text: row.baselineObservations}),
      element("td", {text: row.robustZ === null ? "unavailable" : formatNumber(row.robustZ, 3)}),
      element("td", {text: signal}),
      element("td", {text: row.baselineStartGame === null ? "—" : `G${row.baselineStartGame}–G${row.baselineEndGame}`}),
    ]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)"}, "CYAN OBSERVED · VIOLET PRIOR-ONLY MEDIAN + ROBUST BAND · RED DIAMOND ADVERSE · GREEN TRIANGLE FAVOURABLE"));
  host.append(svg);
}

function renderSourceDrift(sourceRows) {
  const host = $("#source-drift-chart"); clear(host);
  const summary = $("#source-drift-summary"); clear(summary);
  const body = $("#source-drift-table"); clear(body);
  const width = 1180, height = 300, margin = {left: 74, right: 35, top: 38, bottom: 45};
  const plotW = width - margin.left - margin.right, plotH = height - margin.top - margin.bottom;
  const observed = sourceRows.filter(row => row.score !== null);
  const domainMax = Math.min(1, Math.max(.1, ...observed.map(row => row.score * 1.15)));
  const x = index => margin.left + index / Math.max(1, sourceRows.length - 1) * plotW;
  const y = value => margin.top + (domainMax - value) / domainMax * plotH;
  const svg = svgRoot(width, height, "Jensen-Shannon divergence of each game belief-source mix from its strictly prior baseline");
  for (let tick = 0; tick <= 4; tick += 1) {
    const value = domainMax * tick / 4, yy = y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "grid-line"}));
    svg.append(svgElement("text", {x: margin.left - 10, y: yy + 3, class: "axis-label", "text-anchor": "end"}, formatNumber(value, 3)));
  }
  driftSegments(sourceRows, row => row.score !== null).forEach(segment => {
    const points = segment.map(({row, index}) => [x(index), y(row.score)]);
    const area = `${linePath(points)} L${points.at(-1)[0]},${y(0)} L${points[0][0]},${y(0)} Z`;
    svg.append(svgElement("path", {d: area, fill: colors.blue, "fill-opacity": .08, stroke: "none"}));
    svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: colors.blue, "stroke-width": 2}));
  });
  sourceRows.forEach((row, index) => {
    const xx = x(index);
    let tooltipLines = null;
    if (row.score !== null) {
      const marker = svgElement("rect", {x: xx - 3.5, y: y(row.score) - 3.5, width: 7, height: 7, rx: 1, fill: colors.blue});
      const mover = row.topMover;
      const moverDelta = mover ? `${mover.delta >= 0 ? "+" : "−"}${formatPercent(Math.abs(mover.delta))}` : null;
      tooltipLines = [`Game ${row.game} · source-mix JSD ${formatNumber(row.score, 4)}`, `${row.currentItems} current items · ${row.baselineItems} items across ${row.baselineGames} prior games`, mover ? `${mover.source}: ${formatPercent(mover.baselineShare)} → ${formatPercent(mover.currentShare)} (${moverDelta})` : "no source mover", `prior-only window G${row.baselineStartGame}–G${row.baselineEndGame}`];
      svg.append(marker);
    }
    if (index % Math.max(1, Math.ceil(sourceRows.length / 14)) === 0 || index === sourceRows.length - 1) svg.append(svgElement("text", {x: xx, y: height - 16, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    const hit = svgElement("rect", {x: xx - 6, y: margin.top, width: 12, height: plotH, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game} source composition evidence`});
    if (tooltipLines) addTooltip(hit, tooltipLines);
    hit.addEventListener("click", () => openDriftGame(row.game)); svg.append(hit);
    body.append(element("tr", {}, [
      element("td", {}, [itemLink(row.game, null, `Game ${row.game}`)]), element("td", {text: row.currentItems}),
      element("td", {text: row.baselineGames}), element("td", {text: row.baselineItems}),
      element("td", {text: row.score === null ? row.status : formatNumber(row.score, 4)}),
      element("td", {text: row.topMover?.source || "unavailable"}),
      element("td", {text: row.topMover ? formatPercent(row.topMover.baselineShare) : "—"}),
      element("td", {text: row.topMover ? formatPercent(row.topMover.currentShare) : "—"}),
    ]));
  });
  svg.append(svgElement("text", {x: margin.left, y: 17, fill: colors.blue, "font-size": 8, "font-family": "var(--mono)"}, "JENSEN–SHANNON DIVERGENCE · 0 IDENTICAL · 1 DISJOINT · EACH GAME COMPARED ONLY WITH PRIOR SOURCE COUNTS"));
  host.append(svg);
  const latest = [...observed].at(-1);
  if (!latest) {
    summary.append(element("div", {class: "empty-state"}, [element("p", {text: "At least five prior games with item beliefs are required for source-mix drift."})]));
    return;
  }
  const currentTotal = latest.currentItems, baselineTotal = latest.baselineItems;
  const sources = new Set([...Object.keys(latest.currentCounts), ...Object.keys(latest.baselineCounts)]);
  const rows = [...sources].map(source => ({source, current: safeNumber(latest.currentCounts[source]) / currentTotal, baseline: safeNumber(latest.baselineCounts[source]) / baselineTotal}))
    .map(row => ({...row, delta: row.current - row.baseline})).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 6);
  summary.append(element("div", {class: "source-drift-summary-head"}, [
    element("span", {text: `LATEST EVALUABLE · GAME ${latest.game}`}),
    element("strong", {text: `JSD ${formatNumber(latest.score, 4)}`}),
    element("small", {text: `${currentTotal} current items versus ${baselineTotal} prior-window items`}),
  ]));
  rows.forEach(row => summary.append(element("div", {class: "source-drift-row"}, [
    element("span", {text: row.source}),
    element("div", {class: "source-drift-track"}, [element("i", {style: `width:${clamp(row.baseline * 100, 0, 100)}%`}), element("b", {style: `width:${clamp(row.current * 100, 0, 100)}%`})]),
    element("strong", {class: row.delta > 0 ? "positive" : row.delta < 0 ? "negative" : "", text: `${formatPercent(row.baseline)} → ${formatPercent(row.current)}`}),
  ])));
}

function buildDriftReceipt(analysis, sourceRows, materializedAt) {
  const flagged = analysis.points.filter(row => row.signal !== "none").map(row => ({
    game: row.game, value: row.value, priorMedian: row.baseline,
    robustScale: row.scale, robustZ: row.robustZ, signal: row.signal,
    baselineObservations: row.baselineObservations,
    baselineStartGame: row.baselineStartGame, baselineEndGame: row.baselineEndGame,
    denominatorValue: row.denominatorValue,
  }));
  const latestSource = [...sourceRows].filter(row => row.score !== null).at(-1);
  return {
    version: 1, status: "offline-strictly-temporal-monitoring-evidence-only", materializedAt,
    specification: {
      metric: analysis.metricKey, unit: analysis.metric.unit, denominator: analysis.metric.denominator,
      favourableDirection: analysis.metric.direction, priorWindow: analysis.window,
      sensitivityRobustSigma: analysis.sensitivity, minimumPriorObservations: 5,
      scale: "max(1.4826 × MAD, IQR / 1.349)", signalRule: "absolute robust z strictly exceeds sensitivity",
      zeroVarianceRule: "when prior scale is zero, a changed current value is reported separately without an invented z-score",
    },
    summary: {
      games: analysis.summary.games, observed: analysis.summary.observed,
      baselineEvaluable: analysis.summary.evaluable, signals: analysis.summary.flagged,
      adverseSignals: analysis.summary.adverse, favourableSignals: analysis.summary.favourable,
      zeroVarianceSignals: analysis.summary.varianceZero, currentQuietRun: analysis.summary.inControlStreak,
    },
    signals: flagged,
    latestSourceMix: latestSource ? {
      game: latestSource.game, jensenShannonDivergence: latestSource.score,
      currentItems: latestSource.currentItems, baselineItems: latestSource.baselineItems,
      baselineGames: latestSource.baselineGames,
      topMover: latestSource.topMover ? {...latestSource.topMover} : null,
    } : null,
    boundaries: [
      "every baseline contains only earlier observed games; the monitored game never trains its own limit",
      "signals are descriptive process-control flags, not causal change points or model-performance claims",
      "missing metric values remain missing and never enter the lagged baseline",
      "source-mix divergence measures composition change, not source quality or treatment effect",
      "observed reviewer cost excludes attempted sizes of rejected fraudulent charges",
      "no process, charge, limit, rule, model, or submission is modified",
    ],
  };
}

async function copyDriftReceipt() {
  if (!state.driftAnalysis || !state.sourceDrift) { toast("Temporal drift evidence is unavailable to copy."); return; }
  try {
    const receipt = buildDriftReceipt(state.driftAnalysis, state.sourceDrift, state.overview.generatedAt);
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    toast("Claim-free strictly temporal drift receipt copied.");
  } catch (error) { toast(`Temporal drift receipt could not be copied: ${error.message}`); }
}

function renderDriftObservatory() {
  if (!state.overview) return;
  const metric = DRIFT_METRICS[state.driftMetric] ? state.driftMetric : "net";
  state.driftMetric = metric;
  const analysis = buildDriftAnalysis(state.overview, metric, state.driftWindow, state.driftSensitivity);
  const sourceRows = buildSourceMixDrift(state.overview.itemIndex, state.overview.race.gameIds, state.driftWindow);
  state.driftAnalysis = analysis; state.sourceDrift = sourceRows;
  $("#drift-metric").value = metric;
  $("#drift-window").value = String(state.driftWindow);
  $("#drift-sensitivity").value = String(state.driftSensitivity);
  $("#drift-status").textContent = `STRICTLY TEMPORAL · ${analysis.summary.evaluable} EVALUABLE / ${analysis.summary.games} GAMES`;
  $("#drift-control-caption").textContent = `${analysis.metric.label} · ${analysis.metric.denominator} · ${analysis.window === "all" ? "all earlier observed games" : `last ${analysis.window} earlier observed games`}`;
  renderDriftNarrative(analysis, sourceRows); renderDriftKpis(analysis);
  renderDriftControlChart(analysis); renderSourceDrift(sourceRows);
}

function renderTrends() {
  renderEconomics(); renderRoundMap(); renderStream(); renderPhases(); renderSources();
  renderRidgeline(); renderBuckets(); renderOvercharge(); renderPareto();
  renderOpponents(); renderDriftObservatory(); renderCalibrationStudio(); renderRegretCartography(); renderQuality(); renderEvidenceAtlas();
}

const OPERATIONS_STAGES = [
  "round.scheduled", "key.received", "case.decrypted", "case.parsed",
  "item.belief", "item.decided", "submission.built", "submission.sent",
  "submission.verified", "round.played",
];
const OPERATIONS_GAME_FIELDS = [
  "game", "played", "recorded", "coreCoverage", "eventCount",
  "observedStages", "stageTimesMs", "firstSendMs", "tier1SendMs",
  "tier2SendMs", "tier1TargetStatus", "tier2DeadlineStatus",
  "submissionCalls", "successfulCalls", "failedCalls", "alerts",
  "roundPlayedObserved", "lastStage", "lastStageAt", "lastElapsedMs",
  "observedSpanMs",
];
const OPERATIONS_PAYLOAD_FIELDS = [
  "schemaVersion", "stages", "telemetryStatus", "latestPlayedGame",
  "latestRecordedGame", "lagPlayedGames", "latestEventAt",
  "latestEventAgeSeconds", "latestSubmissionAt", "latestSubmissionAgeSeconds",
  "games", "stageEnvelope", "summary",
];
const OPERATIONS_SUMMARY_FIELDS = [
  "playedGames", "pipelineGames", "recordedPlayedGames", "missingPlayedGames",
  "recordedCoverage", "completeCoreGames", "meanCoreCoverage",
  "tier1Observed", "tier1AtOrUnderTarget", "tier1TargetRate", "tier1P50Ms",
  "tier1P95Ms", "tier2Observed", "tier2AtOrUnderDeadline",
  "tier2DeadlineRate", "tier2P50Ms", "tier2P95Ms",
  "failedSubmissionCalls", "alerts",
];
const OPERATIONS_CLOCK_STALE_SECONDS = 757.6 * 2;

function operationStageLabel(stage) {
  const labels = {
    "round.scheduled": "SCHEDULE", "key.received": "KEY",
    "case.decrypted": "DECRYPT", "case.parsed": "PARSE",
    "item.belief": "BELIEF", "item.decided": "DECIDE",
    "submission.built": "BUILD", "submission.sent": "SEND",
    "submission.verified": "VERIFY", "round.played": "SETTLE",
  };
  return labels[stage] || String(stage || "UNKNOWN").toUpperCase();
}

function validateOperations(payload) {
  const statuses = new Set(["current", "stale-played-rounds", "stale-clock", "timestamp-unavailable", "unavailable"]);
  const timingStatuses = new Set(["met", "late", "unobserved", "timing-unavailable"]);
  const finiteOrNull = value => value === null || (typeof value === "number" && Number.isFinite(value));
  const nonNegativeOrNull = value => value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0);
  const close = (actual, expected) => actual !== null && Math.abs(actual - expected) <= 0.00011;
  const ratio = (numerator, denominator) => denominator ? Math.round(numerator / denominator * 10_000) / 10_000 : null;
  const validTimestampOrNull = value => value === null || (typeof value === "string" && value.length > 0 && Number.isFinite(Date.parse(value)));
  if (!payload || JSON.stringify(Object.keys(payload).sort()) !== JSON.stringify([...OPERATIONS_PAYLOAD_FIELDS].sort()) ||
      payload.schemaVersion !== 1 || !statuses.has(payload.telemetryStatus) ||
      JSON.stringify(payload.stages) !== JSON.stringify(OPERATIONS_STAGES) ||
      !Array.isArray(payload.games) || !Array.isArray(payload.stageEnvelope) ||
      typeof payload.summary !== "object" || payload.summary === null ||
      JSON.stringify(Object.keys(payload.summary).sort()) !== JSON.stringify([...OPERATIONS_SUMMARY_FIELDS].sort()) ||
      !Number.isInteger(payload.lagPlayedGames) || payload.lagPlayedGames < 0 ||
      ["latestPlayedGame", "latestRecordedGame"].some(field => payload[field] !== null && (!Number.isInteger(payload[field]) || payload[field] < 0 || payload[field] > 100)) ||
      ["latestEventAgeSeconds", "latestSubmissionAgeSeconds"].some(field => !nonNegativeOrNull(payload[field])) ||
      ["latestEventAt", "latestSubmissionAt"].some(field => !validTimestampOrNull(payload[field])) ||
      OPERATIONS_SUMMARY_FIELDS.some(field => !finiteOrNull(payload.summary[field]))) {
    throw new Error("operations telemetry schema mismatch");
  }
  const summaryCounts = ["playedGames", "pipelineGames", "recordedPlayedGames", "missingPlayedGames", "completeCoreGames", "tier1Observed", "tier1AtOrUnderTarget", "tier2Observed", "tier2AtOrUnderDeadline", "failedSubmissionCalls", "alerts"];
  const summaryRates = ["recordedCoverage", "meanCoreCoverage", "tier1TargetRate", "tier2DeadlineRate"];
  if (summaryCounts.some(field => !Number.isInteger(payload.summary[field]) || payload.summary[field] < 0) ||
      summaryRates.some(field => payload.summary[field] !== null && (payload.summary[field] < 0 || payload.summary[field] > 1))) {
    throw new Error("operations summary domains are invalid");
  }
  const seenGames = new Set();
  payload.games.forEach((row, index) => {
    const observed = Array.isArray(row?.observedStages) ? row.observedStages : [];
    if (!row || JSON.stringify(Object.keys(row).sort()) !== JSON.stringify([...OPERATIONS_GAME_FIELDS].sort()) ||
        !Number.isInteger(row.game) || row.game < 0 || row.game > 100 || seenGames.has(row.game) ||
        typeof row.played !== "boolean" || typeof row.recorded !== "boolean" ||
        typeof row.coreCoverage !== "number" || row.coreCoverage < 0 || row.coreCoverage > 1 ||
        !Number.isInteger(row.eventCount) || row.eventCount < 0 ||
        !Array.isArray(row.observedStages) || row.observedStages.some(stage => !OPERATIONS_STAGES.includes(stage)) ||
        new Set(row.observedStages).size !== row.observedStages.length ||
        !row.stageTimesMs || JSON.stringify(Object.keys(row.stageTimesMs).sort()) !== JSON.stringify([...OPERATIONS_STAGES].sort()) ||
        Object.values(row.stageTimesMs).some(value => !nonNegativeOrNull(value)) ||
        OPERATIONS_STAGES.some(stage => row.stageTimesMs[stage] !== null && !observed.includes(stage)) ||
        !timingStatuses.has(row.tier1TargetStatus) || !timingStatuses.has(row.tier2DeadlineStatus) ||
        ["submissionCalls", "successfulCalls", "failedCalls", "alerts"].some(field => !Number.isInteger(row[field]) || row[field] < 0) ||
        row.successfulCalls + row.failedCalls > row.submissionCalls ||
        ["firstSendMs", "tier1SendMs", "tier2SendMs", "lastElapsedMs", "observedSpanMs"].some(field => !nonNegativeOrNull(row[field])) ||
        typeof row.roundPlayedObserved !== "boolean" || row.roundPlayedObserved !== observed.includes("round.played") ||
        Math.abs(row.coreCoverage - observed.length / OPERATIONS_STAGES.length) > 0.00011 ||
        (row.recorded !== (row.eventCount > 0)) ||
        (!row.recorded && (observed.length || row.submissionCalls || row.alerts)) ||
        (row.tier1SendMs === null ? !["unobserved", "timing-unavailable"].includes(row.tier1TargetStatus) : row.tier1TargetStatus !== (row.tier1SendMs <= 2_000 ? "met" : "late")) ||
        (row.tier2SendMs === null ? !["unobserved", "timing-unavailable"].includes(row.tier2DeadlineStatus) : row.tier2DeadlineStatus !== (row.tier2SendMs <= 52_000 ? "met" : "late")) ||
        (row.lastStage !== null && !OPERATIONS_STAGES.includes(row.lastStage)) ||
        typeof row.lastStageAt !== "string" || (row.lastStageAt && !Number.isFinite(Date.parse(row.lastStageAt))) ||
        ((row.lastStage === null) !== (row.lastElapsedMs === null)) ||
        ((row.lastStage === null) !== (row.lastStageAt === ""))) throw new Error(`operations game row ${index} is malformed`);
    seenGames.add(row.game);
  });
  if (payload.stageEnvelope.length !== OPERATIONS_STAGES.length ||
      payload.stageEnvelope.some((row, index) => !row || JSON.stringify(Object.keys(row).sort()) !== JSON.stringify(["stage", "observations", "p10Ms", "p50Ms", "p90Ms"].sort()) || row.stage !== OPERATIONS_STAGES[index] ||
        !Number.isInteger(row.observations) || row.observations < 0 ||
        ["p10Ms", "p50Ms", "p90Ms"].some(field => !nonNegativeOrNull(row[field])) ||
        row.observations !== payload.games.filter(game => game.stageTimesMs[row.stage] !== null).length ||
        (row.observations === 0 && [row.p10Ms, row.p50Ms, row.p90Ms].some(value => value !== null)) ||
        (row.observations > 0 && (row.p10Ms === null || row.p50Ms === null || row.p90Ms === null || row.p10Ms > row.p50Ms || row.p50Ms > row.p90Ms)))) {
    throw new Error("operations stage envelope is malformed");
  }
  const played = payload.games.filter(row => row.played);
  const recorded = payload.games.filter(row => row.recorded);
  const recordedPlayed = payload.games.filter(row => row.recorded && row.played);
  const tierOne = payload.games.filter(row => row.tier1SendMs !== null);
  const tierTwo = payload.games.filter(row => row.tier2SendMs !== null);
  const latestPlayed = played.length ? Math.max(...played.map(row => row.game)) : null;
  const latestRecorded = recorded.length ? Math.max(...recorded.map(row => row.game)) : null;
  const lag = latestRecorded === null ? played.length : played.filter(row => row.game > latestRecorded).length;
  const complete = recorded.filter(row => row.coreCoverage === 1).length;
  const meanCoverage = recorded.length ? ratio(recorded.reduce((sum, row) => sum + row.coreCoverage, 0), recorded.length) : null;
  const expectedStatus = !recorded.length ? "unavailable"
    : lag > 0 ? "stale-played-rounds"
      : payload.latestEventAgeSeconds === null ? "timestamp-unavailable"
        : payload.latestEventAgeSeconds > OPERATIONS_CLOCK_STALE_SECONDS ? "stale-clock" : "current";
  if (payload.latestPlayedGame !== latestPlayed || payload.latestRecordedGame !== latestRecorded || payload.lagPlayedGames !== lag || payload.telemetryStatus !== expectedStatus ||
      payload.summary.playedGames !== played.length ||
      payload.summary.recordedPlayedGames !== recordedPlayed.length ||
      payload.summary.missingPlayedGames !== payload.summary.playedGames - recordedPlayed.length ||
      payload.summary.pipelineGames !== recorded.length ||
      payload.summary.completeCoreGames !== complete ||
      (recorded.length ? !close(payload.summary.meanCoreCoverage, meanCoverage) : payload.summary.meanCoreCoverage !== null) ||
      (played.length ? !close(payload.summary.recordedCoverage, ratio(recordedPlayed.length, played.length)) : payload.summary.recordedCoverage !== null) ||
      payload.summary.tier1Observed !== tierOne.length ||
      payload.summary.tier1AtOrUnderTarget !== tierOne.filter(row => row.tier1SendMs <= 2000).length ||
      (tierOne.length ? !close(payload.summary.tier1TargetRate, ratio(payload.summary.tier1AtOrUnderTarget, tierOne.length)) : payload.summary.tier1TargetRate !== null) ||
      payload.summary.tier2Observed !== tierTwo.length ||
      payload.summary.tier2AtOrUnderDeadline !== tierTwo.filter(row => row.tier2SendMs <= 52000).length ||
      (tierTwo.length ? !close(payload.summary.tier2DeadlineRate, ratio(payload.summary.tier2AtOrUnderDeadline, tierTwo.length)) : payload.summary.tier2DeadlineRate !== null) ||
      payload.summary.failedSubmissionCalls !== recorded.reduce((sum, row) => sum + row.failedCalls, 0) ||
      payload.summary.alerts !== recorded.reduce((sum, row) => sum + row.alerts, 0)) {
    throw new Error("operations telemetry denominators do not reconcile");
  }
  return payload;
}

async function openOperationGame(game) {
  await selectGame(game);
  $(".flight-panel").scrollIntoView({behavior: "smooth", block: "start"});
}

function operationFreshnessCopy(operations) {
  if (operations.telemetryStatus === "current") return {
    title: "LOCAL RECORDER CURRENT", tone: "ok",
    detail: `Latest pipeline game ${operations.latestRecordedGame} matches the played horizon.`,
  };
  if (operations.telemetryStatus === "stale-played-rounds") return {
    title: `LOCAL RECORDER ${operations.lagPlayedGames} PLAYED GAMES BEHIND`, tone: "stale",
    detail: `Latest recorded pipeline: game ${operations.latestRecordedGame ?? "unknown"} · latest played: game ${operations.latestPlayedGame ?? "unknown"}. Tournament activity may exist elsewhere; this local recorder cannot see it.`,
  };
  if (operations.telemetryStatus === "stale-clock") return {
    title: "LOCAL RECORDER CLOCK-STALE", tone: "stale",
    detail: `No timestamped local boundary has arrived for ${formatDurationMs(safeNumber(operations.latestEventAgeSeconds) * 1000)}.`,
  };
  return {
    title: "LOCAL RECORDER EVIDENCE UNAVAILABLE", tone: "missing",
    detail: "The historical dashboard remains usable, but current pipeline activity cannot be established from this file.",
  };
}

function renderOperationsFreshness(operations) {
  const host = $("#operations-freshness"); clear(host);
  const copy = operationFreshnessCopy(operations);
  host.dataset.tone = copy.tone;
  const identity = element("div", {}, [
    element("span", {text: "RECORDER TRUTH"}), element("strong", {text: copy.title}),
    element("small", {text: copy.detail}),
  ]);
  const clocks = element("div", {class: "operations-freshness-clocks"}, [
    element("div", {}, [element("span", {text: "Latest event age"}), element("strong", {text: operations.latestEventAgeSeconds === null ? "unknown" : formatDurationMs(operations.latestEventAgeSeconds * 1000)})]),
    element("div", {}, [element("span", {text: "Latest send age"}), element("strong", {text: operations.latestSubmissionAgeSeconds === null ? "unknown" : formatDurationMs(operations.latestSubmissionAgeSeconds * 1000)})]),
  ]);
  host.append(identity, clocks);
  const status = $("#operations-status");
  status.textContent = operations.telemetryStatus.replaceAll("-", " ").toUpperCase();
  status.dataset.tone = copy.tone;
}

function renderOperationsKpis(operations) {
  const host = $("#operations-kpis"); clear(host);
  const summary = operations.summary;
  const calls = operations.games.reduce((sum, row) => sum + row.submissionCalls, 0);
  const specs = [
    ["Recorder coverage", formatPercent(summary.recordedCoverage), `${summary.recordedPlayedGames} / ${summary.playedGames} played games`, summary.missingPlayedGames ? "negative" : "positive"],
    ["Core-complete", `${summary.completeCoreGames} / ${summary.pipelineGames}`, `${formatPercent(summary.meanCoreCoverage)} mean ten-stage coverage`, ""],
    ["Tier 1 ≤ 2s target", formatPercent(summary.tier1TargetRate), `${summary.tier1AtOrUnderTarget} / ${summary.tier1Observed} timed sends · P50 ${formatDurationMs(summary.tier1P50Ms)}`, summary.tier1TargetRate === 1 ? "positive" : "warning"],
    ["Tier 2 ≤ 52s wall", formatPercent(summary.tier2DeadlineRate), `${summary.tier2AtOrUnderDeadline} / ${summary.tier2Observed} timed sends · P95 ${formatDurationMs(summary.tier2P95Ms)}`, summary.tier2DeadlineRate === 1 ? "positive" : "negative"],
    ["Failed send calls", formatNumber(summary.failedSubmissionCalls), `${formatNumber(calls)} observed calls · HTTP outcome only`, summary.failedSubmissionCalls ? "negative" : "positive"],
    ["Alert events", formatNumber(summary.alerts), "severity counts only · messages withheld", summary.alerts ? "warning" : "positive"],
  ];
  specs.forEach(([label, value, note, tone]) => host.append(metricCard(label, value, note, tone)));
}

function renderOperationsHorizon(operations) {
  const host = $("#operations-current"); clear(host);
  const latest = operations.games.find(row => row.game === operations.latestRecordedGame);
  if (!latest) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No local pipeline round is available."})]));
    return;
  }
  const identity = element("div", {class: "operations-horizon-identity"}, [
    element("span", {text: "LATEST LOCAL PIPELINE"}),
    element("strong", {text: `GAME ${latest.game}`}),
    element("small", {text: `${formatPercent(latest.coreCoverage)} core coverage · ${latest.eventCount} sanitized events · ${latest.submissionCalls} send calls`}),
    element("small", {text: latest.lastStage ? `Last core boundary: ${operationStageLabel(latest.lastStage)} at ${formatDurationMs(latest.lastElapsedMs)}` : "No timestamped core boundary"}),
  ]);
  const rail = element("div", {class: "operations-stage-rail"});
  OPERATIONS_STAGES.forEach((stage, index) => {
    const observed = latest.observedStages.includes(stage);
    const timed = latest.stageTimesMs[stage] !== null;
    rail.append(element("div", {class: `operations-stage-node ${observed ? timed ? "timed" : "untimed" : "missing"}`}, [
      element("i", {"aria-hidden": "true"}),
      element("span", {text: `${String(index + 1).padStart(2, "0")} ${operationStageLabel(stage)}`}),
      element("strong", {text: observed ? timed ? formatDurationMs(latest.stageTimesMs[stage]) : "OBSERVED · NO TIME" : "MISSING"}),
    ]));
  });
  const action = element("div", {class: "operations-horizon-action"}, [
    element("span", {text: `G${latest.game} RECORDED → G${operations.latestPlayedGame ?? "—"} PLAYED`}),
    element("strong", {text: operations.lagPlayedGames ? `${operations.lagPlayedGames} game telemetry gap` : "horizons aligned"}),
  ]);
  const button = element("button", {type: "button", class: "button", text: "Open latest flight record"});
  button.addEventListener("click", () => openOperationGame(latest.game)); action.append(button);
  host.append(identity, rail, action);
  $("#operations-horizon-caption").textContent = `latest local pipeline G${latest.game} · latest played G${operations.latestPlayedGame ?? "—"} · ${operations.lagPlayedGames} played games beyond recorder`;
}

function renderOperationsStageChart(operations) {
  const host = $("#operations-stage-chart"); clear(host);
  const rows = operations.games.filter(row => row.played);
  if (!rows.length) return;
  const cellW = 20, cellH = 27, width = Math.max(1180, 168 + rows.length * cellW), height = 68 + OPERATIONS_STAGES.length * cellH;
  const margin = {left: 150, right: 18, top: 43, bottom: 24};
  const svg = svgRoot(width, height, "Local pipeline stage coverage for every played game");
  OPERATIONS_STAGES.forEach((stage, stageIndex) => {
    const y = margin.top + stageIndex * cellH;
    svg.append(svgElement("text", {x: margin.left - 12, y: y + 17, fill: "#8f9aa3", "font-size": 8, "font-family": "var(--mono)", "text-anchor": "end"}, operationStageLabel(stage)));
    rows.forEach((row, gameIndex) => {
      const x = margin.left + gameIndex * cellW;
      const observed = row.observedStages.includes(stage);
      const timed = row.stageTimesMs[stage] !== null;
      const fill = !row.recorded ? "rgba(239,106,103,.055)" : observed ? timed ? "rgba(101,214,208,.55)" : "rgba(242,184,75,.48)" : "rgba(255,255,255,.018)";
      svg.append(svgElement("rect", {x, y, width: cellW - 2, height: cellH - 2, rx: 2, fill, stroke: observed ? timed ? colors.cyan : colors.amber : "rgba(171,188,199,.12)", "stroke-width": .6}));
      if (!row.recorded) {
        svg.append(svgElement("line", {x1: x + 4, y1: y + 5, x2: x + cellW - 6, y2: y + cellH - 7, stroke: colors.red, "stroke-opacity": .34}));
        svg.append(svgElement("line", {x1: x + cellW - 6, y1: y + 5, x2: x + 4, y2: y + cellH - 7, stroke: colors.red, "stroke-opacity": .34}));
      } else if (observed) {
        svg.append(timed
          ? svgElement("circle", {cx: x + (cellW - 2) / 2, cy: y + (cellH - 2) / 2, r: 2.4, fill: "#061110"})
          : svgElement("rect", {x: x + 7, y: y + 10, width: 5, height: 5, fill: "none", stroke: "#18130a", transform: `rotate(45 ${x + 9.5} ${y + 12.5})`}));
      }
    });
  });
  rows.forEach((row, index) => {
    const x = margin.left + index * cellW + (cellW - 2) / 2;
    if (index % Math.max(1, Math.ceil(rows.length / 16)) === 0 || index === rows.length - 1) {
      svg.append(svgElement("text", {x, y: 27, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    }
    const hit = svgElement("rect", {x: x - cellW / 2, y: margin.top, width: cellW, height: OPERATIONS_STAGES.length * cellH, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open pipeline record for game ${row.game}`});
    addTooltip(hit, [`Game ${row.game} · ${row.recorded ? "local pipeline recorded" : "no local pipeline record"}`, `${row.observedStages.length} / ${OPERATIONS_STAGES.length} core stages · ${formatPercent(row.coreCoverage)} coverage`, `Tier 1 ${row.tier1SendMs === null ? row.tier1TargetStatus : formatDurationMs(row.tier1SendMs)} · tier 2 ${row.tier2SendMs === null ? row.tier2DeadlineStatus : formatDurationMs(row.tier2SendMs)}`, `${row.failedCalls} failed calls · ${row.alerts} alert events (severity count only)`]);
    hit.addEventListener("click", () => openOperationGame(row.game));
    svg.append(hit);
  });
  svg.append(svgElement("text", {x: margin.left, y: height - 5, class: "axis-label"}, "FILLED DOT = TIMED · DIAMOND = OBSERVED WITHOUT TIME · OUTLINE = STAGE MISSING · X = ROUND UNRECORDED"));
  host.append(svg);
}

function renderOperationsDeadlineChart(operations) {
  const host = $("#operations-deadline-chart"); clear(host);
  const rows = operations.games.filter(row => row.recorded);
  if (!rows.length) return;
  const width = Math.max(900, rows.length * 21 + 110), height = 390, margin = {left: 68, right: 28, top: 38, bottom: 58};
  const maxMs = Math.max(55_000, ...rows.flatMap(row => [row.tier1SendMs, row.tier2SendMs]).filter(Number.isFinite)) * 1.04;
  const x = index => margin.left + index / Math.max(1, rows.length - 1) * (width - margin.left - margin.right);
  const y = value => margin.top + (maxMs - value) / maxMs * (height - margin.top - margin.bottom);
  const svg = svgRoot(width, height, "Observed tier send timing by locally recorded game");
  [[2_000, "T1 2s target", colors.cyan], [52_000, "T2 52s wall", colors.red]].forEach(([value, label, color]) => {
    svg.append(svgElement("line", {x1: margin.left, y1: y(value), x2: width - margin.right, y2: y(value), stroke: color, "stroke-width": 1, "stroke-dasharray": "5 5", "stroke-opacity": .75}));
    svg.append(svgElement("text", {x: width - margin.right, y: y(value) - 6, fill: color, "font-size": 8, "font-family": "var(--mono)", "text-anchor": "end"}, label));
  });
  rows.forEach((row, index) => {
    const xx = x(index);
    if (row.tier1SendMs !== null) {
      const marker = svgElement("circle", {cx: xx, cy: y(row.tier1SendMs), r: 4, fill: row.tier1TargetStatus === "met" ? colors.cyan : colors.amber, tabindex: 0, class: "interactive"});
      addTooltip(marker, [`Game ${row.game} · tier 1`, `${formatDurationMs(row.tier1SendMs)} from first logged boundary`, `2s target ${row.tier1TargetStatus} · ${row.submissionCalls} total send calls`]); svg.append(marker);
    }
    if (row.tier2SendMs !== null) {
      const marker = svgElement("rect", {x: xx - 4, y: y(row.tier2SendMs) - 4, width: 8, height: 8, rx: 1, fill: row.tier2DeadlineStatus === "met" ? colors.green : colors.red, tabindex: 0, class: "interactive"});
      const marginLabel = row.tier2SendMs <= 52_000
        ? `${formatDurationMs(52_000 - row.tier2SendMs)} observed headroom`
        : `${formatDurationMs(row.tier2SendMs - 52_000)} beyond wall`;
      addTooltip(marker, [`Game ${row.game} · tier 2`, `${formatDurationMs(row.tier2SendMs)} from first logged boundary`, `52s wall ${row.tier2DeadlineStatus} · ${marginLabel}`]); svg.append(marker);
    }
    if (index % Math.max(1, Math.ceil(rows.length / 12)) === 0 || index === rows.length - 1) svg.append(svgElement("text", {x: xx, y: height - 28, class: "axis-label", "text-anchor": "middle"}, `G${row.game}`));
    const hit = svgElement("rect", {x: xx - 7, y: margin.top, width: 14, height: height - margin.top - margin.bottom, fill: "transparent", tabindex: 0, role: "button", class: "interactive", "aria-label": `Open game ${row.game} operational timing`});
    hit.addEventListener("click", () => openOperationGame(row.game)); svg.append(hit);
  });
  svg.append(svgElement("text", {x: margin.left, y: 18, fill: colors.cyan, "font-size": 8, "font-family": "var(--mono)"}, "CIRCLE TIER 1 · SQUARE TIER 2 · MISSING MARKER = UNOBSERVED"));
  host.append(svg);
}

function renderOperationsEnvelope(operations) {
  const host = $("#operations-envelope-chart"); clear(host);
  const rows = operations.stageEnvelope;
  const width = 920, rowHeight = 34, height = 64 + rows.length * rowHeight, margin = {left: 130, right: 55, top: 34, bottom: 30};
  const maxMs = Math.max(52_000, ...rows.map(row => safeNumber(row.p90Ms)));
  const x = value => margin.left + Math.log1p(Math.max(0, value)) / Math.log1p(maxMs) * (width - margin.left - margin.right);
  const svg = svgRoot(width, height, "P10 median and P90 arrival time for local pipeline boundaries");
  [0, 500, 2_000, 10_000, 52_000].filter(value => value <= maxMs).forEach(value => {
    const xx = x(value); svg.append(svgElement("line", {x1: xx, y1: margin.top - 8, x2: xx, y2: height - margin.bottom, class: "grid-line"}));
    svg.append(svgElement("text", {x: xx, y: height - 9, class: "axis-label", "text-anchor": "middle"}, value ? `${formatNumber(value / 1000, 1)}s` : "0"));
  });
  rows.forEach((row, index) => {
    const y = margin.top + index * rowHeight + rowHeight / 2;
    svg.append(svgElement("text", {x: margin.left - 10, y: y + 3, fill: "#98a4ad", "font-size": 8.5, "font-family": "var(--mono)", "text-anchor": "end"}, operationStageLabel(row.stage)));
    if (row.observations && row.p10Ms !== null && row.p90Ms !== null) {
      svg.append(svgElement("line", {x1: x(row.p10Ms), y1: y, x2: x(row.p90Ms), y2: y, stroke: colors.violet, "stroke-width": 5, "stroke-linecap": "round", "stroke-opacity": .38}));
      svg.append(svgElement("circle", {cx: x(row.p10Ms), cy: y, r: 2.7, fill: colors.violet}));
      svg.append(svgElement("circle", {cx: x(row.p90Ms), cy: y, r: 2.7, fill: colors.violet}));
      const median = svgElement("rect", {x: x(row.p50Ms) - 4, y: y - 4, width: 8, height: 8, fill: colors.cyan, transform: `rotate(45 ${x(row.p50Ms)} ${y})`, tabindex: 0, class: "interactive"});
      addTooltip(median, [operationStageLabel(row.stage), `P10 ${formatDurationMs(row.p10Ms)} · median ${formatDurationMs(row.p50Ms)} · P90 ${formatDurationMs(row.p90Ms)}`, `${row.observations} timestamped round boundaries · log-time axis`]); svg.append(median);
    } else {
      svg.append(svgElement("text", {x: margin.left + 8, y: y + 3, fill: colors.faint || colors.muted, "font-size": 8, "font-family": "var(--mono)"}, "UNOBSERVED"));
    }
    svg.append(svgElement("text", {x: width - margin.right + 9, y: y + 3, fill: "#65717b", "font-size": 8, "font-family": "var(--mono)"}, `n=${row.observations}`));
  });
  svg.append(svgElement("text", {x: margin.left, y: 15, fill: colors.violet, "font-size": 8, "font-family": "var(--mono)"}, "WHISKER P10–P90 · DIAMOND MEDIAN · LOG(1+MS) AXIS"));
  host.append(svg);
}

function renderOperationsTable(operations) {
  const body = $("#operations-data-table"); clear(body);
  [...operations.games].sort((a, b) => b.game - a.game).forEach(row => {
    const gameButton = element("button", {type: "button", class: "table-link", text: `Game ${row.game}`});
    gameButton.addEventListener("click", () => openOperationGame(row.game));
    body.append(element("tr", {}, [
      element("td", {}, gameButton), element("td", {text: row.played ? "yes" : "no"}),
      element("td", {text: row.recorded ? "yes" : "no"}), element("td", {text: formatPercent(row.coreCoverage)}),
      element("td", {text: `${row.observedStages.length} / ${OPERATIONS_STAGES.length}`}),
      element("td", {text: row.tier1SendMs === null ? "unknown" : formatDurationMs(row.tier1SendMs)}),
      element("td", {text: row.tier1TargetStatus}), element("td", {text: row.tier2SendMs === null ? "unknown" : formatDurationMs(row.tier2SendMs)}),
      element("td", {text: row.tier2DeadlineStatus}), element("td", {text: row.submissionCalls}),
      element("td", {text: row.failedCalls}), element("td", {text: row.alerts}),
      element("td", {text: row.lastStage ? operationStageLabel(row.lastStage) : "unknown"}),
    ]));
  });
}

function renderOperations(raw) {
  try {
    const operations = validateOperations(raw);
    state.operations = operations;
    renderOperationsFreshness(operations); renderOperationsKpis(operations);
    renderOperationsHorizon(operations); renderOperationsStageChart(operations);
    renderOperationsDeadlineChart(operations); renderOperationsEnvelope(operations);
    renderOperationsTable(operations);
  } catch (error) {
    state.operations = null;
    $("#operations-status").textContent = "TELEMETRY CONTRACT FAILED";
    const host = $("#operations-freshness"); clear(host); host.dataset.tone = "missing";
    host.setAttribute("role", "alert");
    host.append(element("div", {}, [element("strong", {text: "Operations evidence unavailable"}), element("small", {text: error.message})]));
    ["#operations-kpis", "#operations-current", "#operations-stage-chart", "#operations-deadline-chart", "#operations-envelope-chart", "#operations-data-table"].forEach(selector => clear($(selector)));
  }
}

async function copyOperationsReceipt() {
  if (!state.operations) { toast("Operations evidence is unavailable to copy."); return; }
  const operations = state.operations;
  const latest = operations.games.find(row => row.game === operations.latestRecordedGame) || null;
  const receipt = {
    version: 1, status: "offline-local-recorder-evidence-only",
    materializedAt: state.overview.generatedAt,
    freshness: {
      telemetryStatus: operations.telemetryStatus,
      latestPlayedGame: operations.latestPlayedGame,
      latestRecordedGame: operations.latestRecordedGame,
      lagPlayedGames: operations.lagPlayedGames,
      latestEventAgeSeconds: operations.latestEventAgeSeconds,
      latestSubmissionAgeSeconds: operations.latestSubmissionAgeSeconds,
    },
    summary: {...operations.summary},
    latestRecordedPipeline: latest ? {...latest} : null,
    stageEnvelope: operations.stageEnvelope.map(row => ({...row})),
    boundaries: [
      "one local append-only recorder, not proof of daemon or separate-repository activity",
      "missing boundaries are unknown and never converted into failed or absent submissions",
      "elapsed values begin at the first timestamped local boundary and do not attribute CPU time",
      "tier-one uses a two-second observed target; tier-two uses the fifty-two-second operational wall",
      "alert messages and claim fields are excluded; only severity counts remain",
      "no process, charge, limit, rule, model, or submission is modified",
    ],
  };
  try {
    await navigator.clipboard.writeText(JSON.stringify(receipt, null, 2));
    toast("Claim-free operations receipt copied with freshness and timing boundaries.");
  } catch (error) { toast(`Operations receipt could not be copied: ${error.message}`); }
}

function updateClock() {
  const targets = [$("#countdown"), $("#live-countdown")];
  if (!state.nextRound?.startTime) {
    targets.forEach(node => { node.textContent = "—:—"; });
    return;
  }
  const ms = new Date(state.nextRound.startTime).getTime() - (Date.now() + state.serverClockOffset);
  if (!Number.isFinite(ms)) return;
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  const label = `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  targets.forEach(node => { node.textContent = label; });
  $("#round-label").textContent = `GAME ${state.nextRound.game} IN`;
  $("#live-next-label").textContent = `game ${state.nextRound.game} · ${new Date(state.nextRound.startTime).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"})}`;
}

function applyLiveContext(context, dependencies) {
  if (context?.serverNow) state.serverClockOffset = new Date(context.serverNow).getTime() - Date.now();
  state.nextRound = context?.nextRound || state.nextRound;
  showSystemState(dependencies);
  renderDependencies(dependencies);
  renderLatency(context?.telemetry);
  renderOperations(context?.operations);
  updateClock();
}

function renderLatency(telemetry) {
  const host = $("#latency-chart"); clear(host);
  const kpis = $("#latency-kpis"); clear(kpis);
  const rows = (telemetry?.timeline || []).filter(row => Number.isFinite(row.latencyMs));
  if (!rows.length) {
    host.append(element("div", {class: "empty-state"}, [element("p", {text: "No submission latency events are available in the current tail window."})]));
    return;
  }
  const width = 920, height = 340, margin = {left: 72, right: 28, top: 30, bottom: 55};
  const values = rows.map(row => row.latencyMs);
  const max = Math.max(...values, safeNumber(telemetry.p95LatencyMs)) * 1.14;
  const svg = svgRoot(width, height, "Observed submission latency over recent events");
  const scale = chartScaffold(svg, width, height, margin, 0, max, 5);
  const tierColors = {1: colors.cyan, 2: colors.amber};
  const pointsByTier = new Map();
  rows.forEach((row, index) => {
    const point = [scale.x(index, rows.length), scale.y(row.latencyMs)];
    if (!pointsByTier.has(row.tier)) pointsByTier.set(row.tier, []);
    pointsByTier.get(row.tier).push(point);
  });
  for (const [tier, points] of pointsByTier) {
    svg.append(svgElement("path", {d: linePath(points), fill: "none", stroke: tierColors[tier] || colors.violet, "stroke-width": 1.3, "stroke-opacity": .45, "stroke-dasharray": tier === 2 ? "4 4" : "0"}));
  }
  [[telemetry.p50LatencyMs, "P50", colors.green], [telemetry.p95LatencyMs, "P95", colors.red]].forEach(([value, label, color]) => {
    if (!Number.isFinite(value)) return;
    const y = scale.y(value);
    svg.append(svgElement("line", {x1: margin.left, y1: y, x2: width - margin.right, y2: y, stroke: color, "stroke-width": 1, "stroke-dasharray": "5 5"}));
    svg.append(svgElement("text", {x: width - margin.right, y: y - 5, fill: color, "font-family": "monospace", "font-size": 8, "text-anchor": "end"}, `${label} ${formatNumber(value)} ms`));
  });
  rows.forEach((row, index) => {
    const x = scale.x(index, rows.length), y = scale.y(row.latencyMs), color = tierColors[row.tier] || colors.violet;
    const marker = row.ok
      ? svgElement("circle", {cx: x, cy: y, r: 4, fill: color, tabindex: 0, class: "interactive"})
      : svgElement("rect", {x: x - 5, y: y - 5, width: 10, height: 10, fill: colors.red, transform: `rotate(45 ${x} ${y})`, tabindex: 0, class: "interactive"});
    addTooltip(marker, [`Game ${row.game} · tier ${row.tier ?? "unknown"}`, `${formatNumber(row.latencyMs, 1)} ms · ${row.ok ? "successful" : "failed"}`, `HTTP ${row.status ?? "not logged"} · event seq ${row.seq}`]);
    svg.append(marker);
  });
  svg.append(svgElement("text", {x: margin.left, y: height - 28, class: "axis-label"}, `oldest · ${rows.length} observed submissions`));
  svg.append(svgElement("text", {x: width - margin.right, y: height - 28, class: "axis-label", "text-anchor": "end"}, "newest"));
  host.append(svg);
  const specs = [
    ["Success rate", formatPercent(telemetry.successRate), `${telemetry.submissions} recent calls`],
    ["P50 latency", `${formatNumber(telemetry.p50LatencyMs)} ms`, "median logged wall-clock"],
    ["P95 latency", `${formatNumber(telemetry.p95LatencyMs)} ms`, "tail latency"],
    ["Last call", `${formatNumber(telemetry.lastLatencyMs)} ms`, telemetry.tiers.map(row => `T${row.tier} ${formatPercent(row.successRate)}`).join(" · ")],
  ];
  specs.forEach(([label, value, note]) => kpis.append(element("div", {class: "latency-stat"}, [element("span", {text: label}), element("strong", {text: value}), element("small", {text: note})])));
}

function renderLive(events, {append = false} = {}) {
  const host = $("#live-ticker");
  const merged = append ? [...(state.liveEvents || []), ...events] : events;
  const unique = [...new Map(merged.map(row => [row.seq, row])).values()].sort((a, b) => b.seq - a.seq).slice(0, 100);
  state.liveEvents = unique;
  clear(host);
  unique.forEach(row => {
    const time = row.ts ? new Date(row.ts).toLocaleTimeString([], {hour12: false}) : "—";
    const kind = row.type.replace("submission.", "").replace("round.", "round ");
    const outcome = row.ok === undefined ? (row.level || "event") : row.ok ? "OK" : "FAIL";
    host.append(element("div", {class: `ticker-row ${row.type === "alert" ? "alert" : ""}`}, [
      element("span", {text: time}), element("strong", {text: `G${row.game}`}),
      element("span", {text: kind}), element("span", {class: row.ok === false ? "fail" : row.ok ? "ok" : "", text: outcome}),
      element("span", {text: row.latencyMs ? `${formatNumber(row.latencyMs)} ms` : row.tier ? `tier ${row.tier}` : `seq ${row.seq}`}),
    ]));
  });
  if (!unique.length) host.append(element("div", {class: "empty-state"}, [element("p", {text: "No submission events in the current tail window."})]));
  $("#event-seq").textContent = `SEQ ${state.liveSeq || "—"}`;
}

function renderDependencies(dependencies) {
  const host = $("#dependency-list"); clear(host);
  for (const [name, row] of Object.entries(dependencies?.items || {})) {
    const mode = row.mode || row.error || "unknown";
    host.append(element("div", {class: "dependency-row"}, [
      element("span", {class: `dependency-dot ${row.ok ? "ok" : ""}`, "aria-hidden": "true"}),
      element("div", {class: "dependency-name"}, [name, element("small", {text: mode})]),
      element("span", {class: "dependency-state", text: row.ok ? (row.critical ? "ready" : "online") : row.critical ? "blocked" : "degraded"}),
    ]));
  }
}

async function pollLive() {
  try {
    const payload = await api(`/api/live?after=${state.liveSeq}`, {timeout: 8000, retries: 0});
    state.liveSeq = Math.max(state.liveSeq, payload.maxSeq || 0);
    if (!state.livePaused) renderLive(payload.events || [], {append: true});
    else {
      const merged = [...(state.liveEvents || []), ...(payload.events || [])];
      state.liveEvents = [...new Map(merged.map(row => [row.seq, row])).values()].sort((a, b) => b.seq - a.seq).slice(0, 100);
    }
    applyLiveContext(payload.context, payload.dependencies);
    if ((payload.events || []).some(row => row.type === "round.played") ||
        payload.overviewRevision && payload.overviewRevision !== state.overview.generatedAt) {
      scheduleOverviewRefresh();
    }
  } catch (error) {
    showSystemState({ready: false, items: {dashboard: {ok: false}}});
  }
}

function scheduleOverviewRefresh() {
  if (state.overviewRefreshPending) return;
  state.overviewRefreshPending = setTimeout(async () => {
    state.overviewRefreshPending = null;
    await refreshOverview();
  }, 2800);
}

async function refreshOverview() {
  if (Date.now() - state.lastOverviewRefresh < 2500) return;
  state.lastOverviewRefresh = Date.now();
  try {
    const oldLength = state.overview.race.gameIds.length;
    const atLatest = state.raceIndex === oldLength - 1;
    const overview = await api("/api/overview", {timeout: 30000, retries: 0});
    if (overview.schemaVersion !== 7) throw new Error("Live materialisation schema changed");
    state.overview = overview;
    $("#generated-at").textContent = `MATERIALISED ${new Date(overview.generatedAt).toLocaleString()}`;
    $("#race-slider").max = String(Math.max(0, overview.race.gameIds.length - 1));
    raceAt(atLatest ? overview.race.gameIds.length - 1 : Math.min(state.raceIndex, overview.race.gameIds.length - 1));
    renderBriefing(); renderRankHeatmap(); renderAnomalies(); renderRobustness(); renderFinishSimulator(); renderTrends();
    populateStrategyControls(); renderStrategy();
    void loadReviewerLab();
    void loadMarket();
    populateGameOptions();
    applyLiveContext(overview.live, overview.dependencies);
    if (overview.race.gameIds.length > oldLength) toast(`Game ${overview.race.gameIds.at(-1)} is now materialised across the observatory.`);
  } catch (error) {
    toast(`Live analytical refresh deferred: ${error.message}`);
  }
}

function commandActions() {
  return [
    {kind: "command", index: "L", label: "Open latest played game", subtitle: "Jump to the newest complete anatomy", meta: "ACTION", action: async () => { await selectGame(state.overview.race.gameIds.at(-1), {scroll: true}); }},
    {kind: "command", index: "T", label: "Open temporal intelligence", subtitle: "Jump to trends, phase ledger, and evidence integrity", meta: "ACTION", action: () => $("#trends").scrollIntoView({behavior: "smooth"})},
    {kind: "command", index: "M", label: "Open finish-line simulator", subtitle: "Joint-round bootstrap, finish cone, rival probabilities, and temporal validation", meta: "ACTION", action: () => $("#finish-simulator").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "X", label: "Open the evidence-loss atlas", subtitle: "Explore missing and hidden evidence for every game and item", meta: "ACTION", action: () => $(".evidence-atlas-panel").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "G", label: "Open temporal drift observatory", subtitle: "Strictly lagged robust limits, unusual rounds, and belief-source composition shift", meta: "ACTION", action: () => $("#drift-observatory").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "I", label: "Open bounded belief calibration", subtitle: "Audit lognormal intervals against sanctioned floors and finite ceilings without inventing point labels", meta: "ACTION", action: () => $("#calibration-studio").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "Z", label: "Open two-role regret cartography", subtitle: "Join provable issuer shortfall to observed reviewer mistakes on the same item identifiers", meta: "ACTION", action: () => $("#regret-cartography").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "H", label: "Open selected-item peer forensics", subtitle: "Compare strictly prior numeric peers with separated same-game and future hindsight", meta: "ACTION", action: () => $("#peer-forensics").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "N", label: "Open market microstructure", subtitle: "Inspect all 272 issuer→reviewer edges and exact settlement reconciliation", meta: "ACTION", action: () => $("#market-panel").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "Q", label: "Open rival gap studio", subtitle: "Decompose the same-game Oasis score gap into income and reviewer-cost edges", meta: "ACTION", action: () => $("#rival-benchmark").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "O", label: "Open live operations command deck", subtitle: "Audit recorder freshness, stage coverage, and observed deadline evidence", meta: "ACTION", action: () => $("#operations-war-room").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "A", label: "Show critical anomalies", subtitle: "Filter the anomaly radar to the hardest evidence", meta: "ACTION", action: () => { state.anomalyCriticalOnly = true; renderAnomalies(); $("#race").scrollIntoView({behavior: "smooth"}); }},
    {kind: "command", index: "S", label: "Open the strategy laboratory", subtitle: "Global valuation landscape, payoff instrument, and counterparties", meta: "ACTION", action: () => $("#strategy").scrollIntoView({behavior: "smooth"})},
    {kind: "command", index: "D", label: "Open reviewer decision laboratory", subtitle: "Bucket-specific limits, decision margins, breakpoints, and hidden exposure", meta: "ACTION", action: () => $("#reviewer-lab").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "B", label: "Open cohort comparison studio", subtitle: "Fixed-denominator before/now evidence with whole-game bootstrap uncertainty", meta: "ACTION", action: () => $("#cohort-studio").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "P", label: "Open the SHADOW portfolio composer", subtitle: "Deduplicated candidates, routing gates, overlap, and falsification ledger", meta: "ACTION", action: () => $("#shadow-portfolio").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "F", label: "Open the round flight recorder", subtitle: "Inspect sanitized pipeline timing and item capital flow", meta: "ACTION", action: () => $(".flight-panel").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "Y", label: "Open the round replay theatre", subtitle: "Scrub exact beliefs, rule firings, decisions, and submission boundaries", meta: "ACTION", action: () => $(".replay-panel").scrollIntoView({behavior: "smooth", block: "start"})},
    {kind: "command", index: "E", label: "Open the evidence dictionary", subtitle: "Definitions, formulas, denominators, and observability states", meta: "ACTION", action: () => $("#evidence-dialog").showModal()},
    {kind: "command", index: "C", label: "Copy current investigation link", subtitle: "Identifier-only local deep link", meta: "ACTION", action: copyInvestigationLink},
    {kind: "command", index: "W", label: "Open investigation watchboard", subtitle: "Compare watched identifiers across proof, decision, and two-role evidence", meta: "ACTION", action: () => { renderWatchlist(); $("#watchlist-dialog").showModal(); }},
    {kind: "command", index: "V", label: state.livePaused ? "Resume live tape" : "Pause live tape", subtitle: "Control visual updates without touching the event writer", meta: "ACTION", action: toggleLivePause},
    {kind: "command", index: "R", label: "Replay the score race", subtitle: "Animate all rank changes from the first game", meta: "ACTION", action: () => { raceAt(0); $("#race").scrollIntoView({behavior: "smooth"}); startRace(); }},
  ];
}

function commandCandidates(query) {
  const q = query.trim().toLocaleLowerCase();
  const tokens = q.split(/\s+/).filter(Boolean);
  const candidates = [];
  const actions = commandActions().filter(row => !q || `${row.label} ${row.subtitle}`.toLocaleLowerCase().includes(q));
  candidates.push(...actions);
  for (const game of state.overview.games.filter(row => row.played)) {
    const haystack = `game ${game.id} ${game.net >= 0 ? "positive win" : "negative loss"}`;
    if (!q && game.id < state.overview.race.gameIds.at(-1) - 4) continue;
    if (q && !tokens.every(token => haystack.includes(token))) continue;
    candidates.push({kind: "game", index: `G${game.id}`, label: `Game ${game.id}`, subtitle: `Income ${formatCurrency(game.income)} · cost ${formatCurrency(game.cost)}`, meta: signed(game.net), action: async () => selectGame(game.id, {scroll: true})});
  }
  for (const row of state.overview.itemIndex) {
    const haystack = `game ${row.game} item ${row.item} ${row.status} ${row.source || ""} ${row.bracketKind}`.toLocaleLowerCase();
    if (q && !tokens.every(token => haystack.includes(token))) continue;
    if (!q && !row.foregoneLowerBound) continue;
    candidates.push({kind: "item", index: `${row.game}:${row.item}`, label: `Game ${row.game} item ${row.item}`, subtitle: `${prettyStatus(row.status)} · source ${row.source || "unknown"} · ${row.bracketKind}`, meta: row.foregoneLowerBound ? `${formatCurrency(row.foregoneLowerBound, true)} foregone` : `a ${formatCurrency(row.a)}`, action: async () => { await selectGame(row.game); await selectItem(row.item, {scroll: true}); }});
  }
  for (const row of state.overview.race.series) {
    if (q && !row.team.toLocaleLowerCase().includes(q)) continue;
    if (!q) continue;
    candidates.push({kind: "team", index: String(state.overview.race.series.indexOf(row) + 1), label: row.team, subtitle: `Median round ${formatCurrency(row.medianRound)} · mean ${formatCurrency(row.meanRound)}`, meta: signed(row.total), action: () => $("#race").scrollIntoView({behavior: "smooth"})});
  }
  const kindOrder = {command: 0, game: 1, item: 2, team: 3};
  return candidates.sort((a, b) => {
    const kindDelta = kindOrder[a.kind] - kindOrder[b.kind];
    if (kindDelta) return kindDelta;
    if (a.kind === "item") {
      const [aGame, aItem] = a.index.split(":").map(Number);
      const [bGame, bItem] = b.index.split(":").map(Number);
      return safeNumber(indexItem(bGame, bItem)?.foregoneLowerBound) -
        safeNumber(indexItem(aGame, aItem)?.foregoneLowerBound);
    }
    return a.label.localeCompare(b.label);
  }).slice(0, 24);
}

function renderCommandResults() {
  const host = $("#command-results"); clear(host);
  state.commandResults = commandCandidates($("#command-search").value);
  state.commandIndex = clamp(state.commandIndex, 0, Math.max(0, state.commandResults.length - 1));
  let lastKind = null;
  state.commandResults.forEach((row, index) => {
    if (row.kind !== lastKind) {
      host.append(element("div", {class: "command-group-label", text: row.kind === "command" ? "Commands" : `${row.kind}s`}));
      lastKind = row.kind;
    }
    const button = element("button", {type: "button", class: `command-result ${index === state.commandIndex ? "selected" : ""}`, role: "option", "aria-selected": String(index === state.commandIndex)}, [
      element("span", {class: "command-result-index", text: row.index}),
      element("span", {}, [element("strong", {text: row.label}), element("small", {text: row.subtitle})]),
      element("span", {class: "command-result-meta", text: row.meta}),
    ]);
    button.addEventListener("pointerenter", () => {
      state.commandIndex = index;
      $$(".command-result", host).forEach((candidate, candidateIndex) => {
        candidate.classList.toggle("selected", candidateIndex === index);
        candidate.setAttribute("aria-selected", String(candidateIndex === index));
      });
    });
    button.addEventListener("click", () => runCommand(index));
    host.append(button);
  });
  if (!state.commandResults.length) host.append(element("div", {class: "empty-state"}, [element("span", {class: "empty-glyph", "aria-hidden": "true"}), element("p", {text: "No materialised games, items, teams, or commands match."})]));
  $("#command-context").textContent = `${state.commandResults.length} results · descriptions remain inside decrypted game views, never this global index.`;
}

function openCommand() {
  if (!state.overview) return;
  state.commandIndex = 0;
  $("#command-search").value = "";
  renderCommandResults();
  $("#command-palette").showModal();
  requestAnimationFrame(() => $("#command-search").focus());
}

async function runCommand(index = state.commandIndex) {
  const row = state.commandResults[index];
  if (!row) return;
  $("#command-palette").close();
  await row.action();
}

function toggleLivePause() {
  state.livePaused = !state.livePaused;
  const button = $("#live-pause");
  button.setAttribute("aria-pressed", String(state.livePaused));
  button.textContent = state.livePaused ? "Resume tape" : "Pause tape";
  if (!state.livePaused) renderLive([], {append: true});
}

function updateScrollProgress() {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  $("#scroll-progress").style.width = `${max > 0 ? clamp(window.scrollY / max * 100, 0, 100) : 0}%`;
}

function setupNavigation() {
  const links = $$(".topnav a");
  const sections = links.map(link => document.getElementById(link.dataset.section));
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!visible) return;
    links.forEach(link => link.classList.toggle("active", link.dataset.section === visible.target.id));
  }, {rootMargin: "-30% 0px -55%", threshold: [0, .15, .4]});
  sections.forEach(section => observer.observe(section));
  document.addEventListener("keydown", event => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;
    const modalOpen = Boolean($("dialog[open]"));
    if (target instanceof SVGElement && target.classList.contains("interactive") &&
        (event.key === "Enter" || event.code === "Space")) {
      event.preventDefault();
      target.dispatchEvent(new MouseEvent("click", {bubbles: true}));
    } else if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k" && !modalOpen) {
      event.preventDefault();
      if (!$("#command-palette").open) openCommand();
    } else if (event.key >= "1" && event.key <= "7" && !typing && !modalOpen) {
      event.preventDefault();
      sections[Number(event.key) - 1]?.scrollIntoView({behavior: "smooth"});
    } else if (event.key === "/" && !typing && !modalOpen) {
      event.preventDefault(); $("#game-select").focus();
    } else if ((event.key.toLowerCase() === "j" || event.key.toLowerCase() === "k") && !typing && !modalOpen && state.game?.items?.length) {
      event.preventDefault();
      const index = Math.max(0, state.game.items.findIndex(row => row.idx === state.selectedItem));
      const delta = event.key.toLowerCase() === "j" ? 1 : -1;
      selectItem(state.game.items[clamp(index + delta, 0, state.game.items.length - 1)].idx);
    } else if (event.key.toLowerCase() === "w" && !typing && !modalOpen) {
      event.preventDefault(); toggleSelectedWatch();
    } else if (event.key.toLowerCase() === "e" && !typing && !modalOpen) {
      event.preventDefault();
      if (!$("#evidence-dialog").open) $("#evidence-dialog").showModal();
    } else if ((event.key === "[" || event.key === "]") && !typing && !modalOpen && roundReplayEvents().length) {
      event.preventDefault();
      stopReplay();
      setReplayIndex(state.replayIndex + (event.key === "]" ? 1 : -1));
    } else if ((event.key === "," || event.key === ".") && !typing && !modalOpen && state.market?.gameIds?.length) {
      event.preventDefault();
      setMarketReplayIndex(state.marketReplayIndex + (event.key === "." ? 1 : -1));
    } else if (event.code === "Space" && event.shiftKey && !typing && !modalOpen) {
      event.preventDefault(); toggleReplay();
    } else if (event.code === "Space" && !typing && !modalOpen) {
      event.preventDefault(); startRace();
    }
  });
  window.addEventListener("scroll", updateScrollProgress, {passive: true});
  updateScrollProgress();
}

function wireControls() {
  $("#race-play").addEventListener("click", startRace);
  $("#forecast-edge").addEventListener("input", event => {
    $("#forecast-edge-output").textContent = signed(Number(event.target.value));
  });
  $("#forecast-form").addEventListener("submit", event => {
    event.preventDefault();
    state.forecastWindow = $("#forecast-window").value;
    state.forecastRuns = Number($("#forecast-runs").value);
    state.forecastSeed = clamp(Math.trunc(Number($("#forecast-seed").value) || 20260823), 1, 2147483646);
    state.forecastTarget = Number($("#forecast-target").value);
    state.forecastEdge = Number($("#forecast-edge").value);
    const button = $("#forecast-run");
    button.disabled = true; button.textContent = "Running…";
    requestAnimationFrame(() => {
      renderFinishSimulator();
      syncInvestigationUrl("race");
      button.disabled = false; button.textContent = "Run scenario";
    });
  });
  $("#forecast-reset").addEventListener("click", () => {
    state.forecastWindow = "all"; state.forecastRuns = 5000; state.forecastSeed = 20260823;
    state.forecastTarget = 3; state.forecastEdge = 0;
    renderFinishSimulator();
    syncInvestigationUrl("race");
  });
  $("#forecast-copy").addEventListener("click", copyForecastReceipt);
  $("#replay-play").addEventListener("click", toggleReplay);
  $("#replay-back").addEventListener("click", () => { stopReplay(); setReplayIndex(state.replayIndex - 1); });
  $("#replay-next").addEventListener("click", () => { stopReplay(); setReplayIndex(state.replayIndex + 1); });
  $("#replay-slider").addEventListener("input", event => { stopReplay(); setReplayIndex(Number(event.target.value)); });
  $$('[data-replay-speed]').forEach(button => button.addEventListener("click", () => {
    const wasPlaying = Boolean(state.replayTimer);
    stopReplay();
    state.replaySpeed = Number(button.dataset.replaySpeed) || 1;
    $$('[data-replay-speed]').forEach(candidate => {
      const active = candidate === button;
      candidate.classList.toggle("active", active);
      candidate.setAttribute("aria-pressed", String(active));
    });
    if (wasPlaying) toggleReplay();
  }));
  $("#race-reset").addEventListener("click", () => raceAt(state.overview.race.gameIds.length - 1));
  $("#race-slider").addEventListener("input", event => raceAt(Number(event.target.value)));
  $$('[data-robustness]').forEach(button => button.addEventListener("click", () => {
    state.robustnessMode = button.dataset.robustness;
    renderRobustness();
    syncInvestigationUrl("race");
  }));
  $$('[data-capital-sort]').forEach(button => button.addEventListener("click", () => {
    state.capitalSort = button.dataset.capitalSort;
    renderCapitalFlow();
    syncInvestigationUrl("game");
  }));
  $$('[data-round-map]').forEach(button => button.addEventListener("click", () => {
    state.roundMapFilter = button.dataset.roundMap;
    renderRoundMap();
    syncInvestigationUrl("trends");
  }));
  $("#evidence-mode").addEventListener("change", event => {
    state.evidenceMode = event.target.value;
    renderEvidenceAtlas();
    syncInvestigationUrl("trends");
  });
  const updateDriftControls = () => {
    state.driftMetric = $("#drift-metric").value;
    state.driftWindow = $("#drift-window").value === "all" ? "all" : Number($("#drift-window").value);
    state.driftSensitivity = Number($("#drift-sensitivity").value);
    renderDriftObservatory(); syncInvestigationUrl("trends");
  };
  [$("#drift-metric"), $("#drift-window"), $("#drift-sensitivity")].forEach(control => control.addEventListener("change", updateDriftControls));
  $("#drift-reset").addEventListener("click", () => {
    state.driftMetric = "net"; state.driftWindow = 10; state.driftSensitivity = 3;
    renderDriftObservatory(); syncInvestigationUrl("trends");
  });
  $("#drift-copy").addEventListener("click", copyDriftReceipt);
  const updateCalibration = () => {
    state.calibrationCoverage = calibrationCoverage(Number($("#calibration-coverage").value));
    state.calibrationSource = $("#calibration-source").value;
    state.calibrationBucket = $("#calibration-bucket").value;
    state.calibrationWindow = $("#calibration-window").value;
    renderCalibrationStudio(); syncInvestigationUrl("trends");
  };
  [$("#calibration-coverage"), $("#calibration-source"), $("#calibration-bucket"), $("#calibration-window")].forEach(control => control.addEventListener("change", updateCalibration));
  $("#calibration-reset").addEventListener("click", () => {
    state.calibrationCoverage = .9; state.calibrationSource = "all";
    state.calibrationBucket = "all"; state.calibrationWindow = "all";
    renderCalibrationStudio(); syncInvestigationUrl("trends");
  });
  $("#calibration-copy").addEventListener("click", copyCalibrationReceipt);
  const updateRegret = () => {
    state.regretWindow = $("#regret-window").value;
    state.regretSource = $("#regret-source").value;
    state.regretBucket = $("#regret-bucket").value;
    renderRegretCartography(); syncInvestigationUrl("trends");
  };
  [$("#regret-window"), $("#regret-source"), $("#regret-bucket")].forEach(control => control.addEventListener("change", updateRegret));
  $$('[data-regret-focus]').forEach(button => button.addEventListener("click", () => {
    state.regretFocus = button.dataset.regretFocus;
    renderRegretCartography(); syncInvestigationUrl("trends");
  }));
  $("#regret-reset").addEventListener("click", () => {
    state.regretWindow = "all"; state.regretSource = "all"; state.regretBucket = "all"; state.regretFocus = "combined";
    renderRegretCartography(); syncInvestigationUrl("trends");
  });
  $("#regret-copy").addEventListener("click", copyRegretReceipt);
  const updatePeerForensics = () => {
    state.peerCohort = $("#peer-cohort").value; state.peerMetric = $("#peer-metric").value;
    renderPeerForensics(); syncInvestigationUrl("item");
  };
  [$("#peer-cohort"), $("#peer-metric")].forEach(control => control.addEventListener("change", updatePeerForensics));
  $("#peer-reset").addEventListener("click", () => {
    state.peerCohort = "source-bucket"; state.peerMetric = "combined";
    renderPeerForensics(); syncInvestigationUrl("item");
  });
  $("#peer-copy").addEventListener("click", copyPeerReceipt);
  $("#market-team").addEventListener("change", event => selectMarketTeam(event.target.value));
  $$('[data-market-mode]').forEach(button => button.addEventListener("click", () => {
    state.marketMode = button.dataset.marketMode;
    populateMarketControls(); renderMarket(); syncInvestigationUrl("trends");
  }));
  $$('[data-market-replay-mode]').forEach(button => button.addEventListener("click", () => {
    stopMarketReplay(); state.marketReplayMode = button.dataset.marketReplayMode;
    populateMarketControls(); renderMarket(); syncInvestigationUrl("trends");
  }));
  $("#market-replay-prev").addEventListener("click", () => setMarketReplayIndex(state.marketReplayIndex - 1));
  $("#market-replay-next").addEventListener("click", () => setMarketReplayIndex(state.marketReplayIndex + 1));
  $("#market-replay-play").addEventListener("click", toggleMarketReplay);
  $("#market-replay-slider").addEventListener("input", event => setMarketReplayIndex(Number(event.target.value)));
  $("#market-copy").addEventListener("click", copyMarketReceipt);
  $("#rival-team").addEventListener("change", event => {
    state.rivalTeam = event.target.value;
    renderRivalBenchmark(); syncInvestigationUrl("race");
  });
  $("#rival-window").addEventListener("change", event => {
    state.rivalWindow = event.target.value;
    renderRivalBenchmark(); syncInvestigationUrl("race");
  });
  $("#rival-reset").addEventListener("click", () => {
    state.rivalTeam = rivalLeader(); state.rivalWindow = "all";
    populateRivalControls(); renderRivalBenchmark(); syncInvestigationUrl("race");
  });
  $("#rival-copy").addEventListener("click", copyRivalReceipt);
  $("#game-select").addEventListener("change", event => selectGame(Number(event.target.value)));
  $("#policy-search").addEventListener("input", event => renderPolicy(event.target.value));
  $("#command-button").addEventListener("click", openCommand);
  $("#copy-link").addEventListener("click", copyInvestigationLink);
  $("#help-button").addEventListener("click", () => $("#keyboard-dialog").showModal());
  $("#watchlist-button").addEventListener("click", () => { renderWatchlist(); $("#watchlist-dialog").showModal(); });
  $("#watch-item").addEventListener("click", toggleSelectedWatch);
  $("#watchboard-sort").addEventListener("change", event => { state.watchboardSort = event.target.value; renderWatchlist(); });
  $("#watchboard-copy").addEventListener("click", copyWatchboardReceipt);
  $("#anomaly-filter").addEventListener("click", () => { state.anomalyCriticalOnly = !state.anomalyCriticalOnly; renderAnomalies(); });
  $("#tape-pause").addEventListener("click", () => {
    state.tapePaused = !state.tapePaused;
    $(".intel-tape").classList.toggle("paused", state.tapePaused);
    $("#tape-pause").setAttribute("aria-pressed", String(state.tapePaused));
    $("#tape-pause").textContent = state.tapePaused ? "Resume" : "Pause";
  });
  $("#live-pause").addEventListener("click", toggleLivePause);
  $("#operations-copy").addEventListener("click", copyOperationsReceipt);
  $("#ledger-search").addEventListener("input", renderLedger);
  $("#ledger-sort").addEventListener("change", event => { state.ledgerSort = event.target.value; renderLedger(); });
  $$("#ledger-filters button").forEach(button => button.addEventListener("click", () => {
    state.ledgerFilter = button.dataset.filter;
    $$("#ledger-filters button").forEach(row => { row.classList.toggle("active", row === button); row.setAttribute("aria-pressed", String(row === button)); });
    renderLedger();
  }));
  $("#compare-game").addEventListener("change", event => loadComparison(event.target.value));
  $("#close-compare").addEventListener("click", () => { $("#compare-game").value = ""; loadComparison(null); });
  [$("#scenario-charge"), $("#scenario-limit")].forEach(input => input.addEventListener("input", renderScenario));
  $$("[data-scenario]").forEach(button => button.addEventListener("click", () => applyScenarioPreset(button.dataset.scenario)));
  $("#landscape-source").addEventListener("change", event => { state.landscapeSource = event.target.value; state.selectedRiskCell = null; renderValuationLandscape(); renderRiskLattice(); syncInvestigationUrl("strategy"); });
  $("#landscape-bucket").addEventListener("change", event => { state.landscapeBucket = event.target.value; state.selectedRiskCell = null; renderValuationLandscape(); renderRiskLattice(); syncInvestigationUrl("strategy"); });
  $$("[data-landscape-status]").forEach(button => button.addEventListener("click", () => {
    state.landscapeStatus = button.dataset.landscapeStatus;
    $$("[data-landscape-status]").forEach(candidate => { candidate.classList.toggle("active", candidate === button); candidate.setAttribute("aria-pressed", String(candidate === button)); });
    renderValuationLandscape();
    syncInvestigationUrl("strategy");
  }));
  $("#landscape-reset").addEventListener("click", () => {
    state.landscapeSource = "all";
    state.landscapeBucket = "all";
    state.landscapeStatus = "all";
    state.selectedRiskCell = null;
    $("#landscape-source").value = "all";
    $("#landscape-bucket").value = "all";
    $$("[data-landscape-status]").forEach(button => { const active = button.dataset.landscapeStatus === "all"; button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active)); });
    renderValuationLandscape();
    renderRiskLattice();
    syncInvestigationUrl("strategy");
  });
  [$("#payoff-t"), $("#payoff-a"), $("#payoff-b"), $("#payoff-c")].forEach(input => input.addEventListener("input", renderPayoff));
  $$("[data-payoff]").forEach(button => button.addEventListener("click", () => applyPayoffPreset(button.dataset.payoff)));
  $("#dossier-team").addEventListener("change", event => { state.dossierTeam = event.target.value; renderDossier(); syncInvestigationUrl("strategy"); });
  $("#reviewer-policy-form").addEventListener("submit", event => event.preventDefault());
  $("#reviewer-window").addEventListener("change", event => { state.reviewerWindow = event.target.value; renderReviewerLab(); syncInvestigationUrl("strategy"); });
  $("#reviewer-opponent").addEventListener("change", event => { state.reviewerOpponent = event.target.value; renderReviewerLab(); syncInvestigationUrl("strategy"); });
  $("#reviewer-source").addEventListener("change", event => { state.reviewerSource = event.target.value; renderReviewerLab(); syncInvestigationUrl("strategy"); });
  $$('[data-reviewer-class]').forEach(button => button.addEventListener("click", () => {
    state.reviewerClass = button.dataset.reviewerClass;
    $$('[data-reviewer-class]').forEach(candidate => {
      const active = candidate === button;
      candidate.classList.toggle("active", active); candidate.setAttribute("aria-pressed", String(active));
    });
    renderReviewerLab(); syncInvestigationUrl("strategy");
  }));
  const reviewerShiftControls = {
    "#reviewer-shift-cheap": ["0–50", "#reviewer-shift-cheap-output"],
    "#reviewer-shift-low": ["50–400", "#reviewer-shift-low-output"],
    "#reviewer-shift-mid": ["400–1200", "#reviewer-shift-mid-output"],
    "#reviewer-shift-high": ["1200+", "#reviewer-shift-high-output"],
  };
  Object.entries(reviewerShiftControls).forEach(([selector, [bucket, output]]) => {
    $(selector).addEventListener("input", event => {
      state.reviewerShifts[bucket] = Number(event.target.value);
      $(output).textContent = signed(state.reviewerShifts[bucket]);
      scheduleReviewerRender();
    });
  });
  $("#reviewer-reset").addEventListener("click", () => {
    state.reviewerWindow = "all"; state.reviewerOpponent = "all";
    state.reviewerSource = "all"; state.reviewerClass = "all";
    state.reviewerShifts = {"0–50": 0, "50–400": 0, "400–1200": 0, "1200+": 0};
    populateReviewerControls(); renderReviewerLab(); syncInvestigationUrl("strategy");
  });
  $("#reviewer-copy").addEventListener("click", copyReviewerReceipt);
  ["a", "b"].forEach(side => {
    ["window", "source", "bucket", "status"].forEach(field => {
      $(`#cohort-${side}-${field}`).addEventListener("change", event => {
        const spec = side === "a" ? state.cohortA : state.cohortB;
        spec[field] = event.target.value;
        renderCohortStudio();
        syncInvestigationUrl("strategy");
      });
    });
  });
  $("#cohort-runs").addEventListener("change", event => {
    state.cohortRuns = [1000, 5000, 10000].includes(Number(event.target.value)) ? Number(event.target.value) : 5000;
    populateCohortControls(); renderCohortStudio(); syncInvestigationUrl("strategy");
  });
  $("#cohort-seed").addEventListener("change", event => {
    const seed = Number(event.target.value);
    state.cohortSeed = Number.isInteger(seed) && seed >= 1 && seed <= 2147483646 ? seed : 20260824;
    populateCohortControls(); renderCohortStudio(); syncInvestigationUrl("strategy");
  });
  $("#cohort-swap").addEventListener("click", () => {
    [state.cohortA, state.cohortB] = [{...state.cohortB}, {...state.cohortA}];
    populateCohortControls(); renderCohortStudio(); syncInvestigationUrl("strategy");
  });
  $("#cohort-reset").addEventListener("click", () => {
    state.cohortA = {window: "previous-10", source: "all", bucket: "all", status: "all"};
    state.cohortB = {window: "last-10", source: "all", bucket: "all", status: "all"};
    state.cohortRuns = 5000; state.cohortSeed = 20260824;
    populateCohortControls(); renderCohortStudio(); syncInvestigationUrl("strategy");
  });
  $("#cohort-copy").addEventListener("click", copyCohortReceipt);
  $("#portfolio-rule").addEventListener("change", event => selectPortfolioRule(event.target.value));
  $("#portfolio-copy").addEventListener("click", copyPortfolioReceipt);
  $("#portfolio-gate").addEventListener("change", event => {
    state.portfolioGate = event.target.value;
    renderPortfolioComposer();
    syncInvestigationUrl("strategy");
  });
  $("#portfolio-source").addEventListener("change", event => {
    state.portfolioSource = event.target.value;
    renderPortfolioComposer();
    syncInvestigationUrl("strategy");
  });
  $$('[data-portfolio-direction]').forEach(button => button.addEventListener("click", () => {
    state.portfolioDirection = button.dataset.portfolioDirection;
    $$('[data-portfolio-direction]').forEach(candidate => {
      const active = candidate === button;
      candidate.classList.toggle("active", active);
      candidate.setAttribute("aria-pressed", String(active));
    });
    renderPortfolioComposer();
    syncInvestigationUrl("strategy");
  }));
  $("#portfolio-reset").addEventListener("click", () => {
    state.portfolioGate = "none";
    state.portfolioSource = "all";
    state.portfolioDirection = "any";
    populatePortfolioControls();
    renderPortfolioComposer();
    syncInvestigationUrl("strategy");
  });
  $("#rule-select").addEventListener("change", event => {
    state.selectedRuleId = event.target.value;
    state.ruleTransition = "all";
    renderRuleObservatory();
    syncInvestigationUrl("strategy");
  });
  $("#command-search").addEventListener("input", () => { state.commandIndex = 0; renderCommandResults(); });
  $("#command-search").addEventListener("keydown", event => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      state.commandIndex = clamp(state.commandIndex + (event.key === "ArrowDown" ? 1 : -1), 0, Math.max(0, state.commandResults.length - 1));
      renderCommandResults();
      $(".command-result.selected")?.scrollIntoView({block: "nearest"});
    } else if (event.key === "Enter") {
      event.preventDefault(); runCommand();
    }
  });
  $("#lightbox").addEventListener("click", event => { if (event.target === $("#lightbox")) $("#lightbox").close(); });
}

function populateGameOptions() {
  const select = $("#game-select"); clear(select);
  const played = state.overview.games.filter(game => game.played);
  played.forEach(game => select.append(element("option", {value: game.id, text: `Game ${game.id} · ${signed(game.net)} · ${game.documentsAvailable ? "docs ready" : "docs unavailable"}`})));
  if (state.selectedGame && played.some(game => game.id === state.selectedGame)) select.value = String(state.selectedGame);
  syncCompareOptions();
  return played;
}

async function setupGames() {
  const played = populateGameOptions();
  const latest = played.at(-1)?.id ?? state.overview.race.gameIds.at(-1);
  const params = new URLSearchParams(window.location.search);
  const requestedGame = Number(params.get("game"));
  const initialGame = Number.isInteger(requestedGame) && played.some(row => row.id === requestedGame)
    ? requestedGame : latest;
  if (initialGame === undefined) return;
  await selectGame(initialGame);
  const requestedItem = Number(params.get("item"));
  if (Number.isInteger(requestedItem) && state.game?.items?.some(row => row.idx === requestedItem)) {
    await selectItem(requestedItem);
  }
  const requestedCompare = Number(params.get("compare"));
  if (Number.isInteger(requestedCompare) && requestedCompare !== initialGame &&
      played.some(row => row.id === requestedCompare)) {
    await loadComparison(requestedCompare);
    $("#compare-game").value = String(requestedCompare);
  }
}

async function initialise() {
  loadWatches();
  saveWatches();
  setupNavigation();
  wireControls();
  try {
    const overview = await api("/api/overview", {timeout: 50000});
    if (overview.schemaVersion !== 7) throw new Error(`Unsupported dashboard schema ${overview.schemaVersion ?? "missing"}`);
    state.overview = overview;
    state.liveSeq = overview.live?.eventsMaxSeq || 0;
    state.liveEvents = overview.live?.recent || [];
    $("#generated-at").textContent = `MATERIALISED ${new Date(overview.generatedAt).toLocaleString()}`;
    $("#race-slider").max = String(Math.max(0, overview.race.gameIds.length - 1));
    raceAt(Math.max(0, overview.race.gameIds.length - 1));
    renderRobustness();
    renderBriefing();
    renderRankHeatmap();
    renderAnomalies();
    hydrateAnalyticalUrlState();
    renderRobustness();
    renderFinishSimulator();
    populateStrategyControls();
    await setupGames();
    renderTrends();
    renderStrategy();
    void loadReviewerLab();
    void loadMarket();
    renderLive(state.liveEvents);
    applyLiveContext(overview.live, overview.dependencies);
    setInterval(updateClock, 1000);
    setInterval(pollLive, 5000);
  } catch (error) {
    toast(`Observatory could not initialise: ${error.message}`);
    const banner = $("#system-banner");
    banner.textContent = `NOT READY · ${error.message}`;
    banner.hidden = false;
  }
}

window.addEventListener("popstate", async () => {
  if (!state.overview) return;
  hydrateAnalyticalUrlState();
  populateStrategyControls();
  renderRobustness();
  renderFinishSimulator();
  renderStrategy();
  if (state.reviewerLab) {
    populateReviewerControls(); renderReviewerLab();
    populateCohortControls(); renderCohortStudio();
  }
  if (state.market) {
    stopMarketReplay();
    const marketIndex = state.market.gameIds.indexOf(state.marketReplayGame);
    state.marketReplayIndex = marketIndex >= 0 ? marketIndex : state.market.gameIds.length - 1;
    state.marketReplayGame = state.market.gameIds[state.marketReplayIndex];
    populateMarketControls(); renderMarket();
    populateRivalControls(); renderRivalBenchmark();
  }
  renderCapitalFlow();
  renderRoundMap();
  renderDriftObservatory();
  renderCalibrationStudio();
  renderRegretCartography();
  renderPeerForensics();
  const params = new URLSearchParams(window.location.search);
  const game = Number(params.get("game"));
  const item = Number(params.get("item"));
  if (Number.isInteger(game) && game !== state.selectedGame) await selectGame(game);
  if (Number.isInteger(item) && item !== state.selectedItem && state.game?.items?.some(row => row.idx === item)) {
    await selectItem(item);
  }
});

initialise();

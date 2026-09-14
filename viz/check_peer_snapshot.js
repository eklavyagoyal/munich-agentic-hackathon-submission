#!/usr/bin/env node

// Claim-free, read-only verification of the peer-forensics contracts against the
// current materialized snapshot. This deliberately consumes only the global
// description-free item index and reviewer evidence cache.

const {readFileSync} = require("node:fs");
const {resolve} = require("node:path");

const root = resolve(__dirname, "..");
const appSource = readFileSync(resolve(root, "viz/static/app.js"), "utf8");
const overview = JSON.parse(readFileSync(resolve(root, "viz/runtime/cache/overview.json"), "utf8"));
const reviewer = JSON.parse(readFileSync(resolve(root, "viz/runtime/cache/reviewer.json"), "utf8"));

const peerStart = appSource.indexOf("const PEER_COHORTS");
const receiptStart = appSource.indexOf("function buildRegretReceipt", peerStart);
if (peerStart < 0 || receiptStart < 0) throw new Error("Peer/regret analysis functions were not found in app.js");

const analysisFunctions = new Function(
  "itemIndex",
  "reviewerCells",
  "gameIds",
  "safeNumber",
  `${appSource.slice(peerStart, receiptStart)}
   const regret = buildRegretCartography(itemIndex, reviewerCells, gameIds, {
     window: "all", source: "all", bucket: "all", focus: "combined"
   });
   return {buildPeerForensics, regretRows: regret.rows, regretTotals: regret.totals};`,
);

const safeNumber = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const gameIds = overview.games.filter(row => row.played).map(row => Number(row.id));
const {buildPeerForensics, regretRows, regretTotals} = analysisFunctions(
  overview.itemIndex,
  reviewer.cells,
  gameIds,
  safeNumber,
);

const violations = [];
if (regretRows.length !== overview.itemIndex.length) violations.push("regret:item-universe-mismatch");
const cohortStats = {};
for (const cohort of ["source-bucket", "source-only", "bucket-only"]) {
  const priorCounts = [];
  const allCounts = [];
  let metricObservations = 0;
  let metricCapacity = 0;
  let analogueEligible = 0;

  for (const item of overview.itemIndex) {
    const result = buildPeerForensics(overview.itemIndex, regretRows, item.game, item.item, {
      cohort,
      metric: "combined",
      reviewerAvailable: true,
    });
    const selectedKey = `${item.game}:${item.item}`;
    const peerKeys = new Set(result.peerRows.map(row => `${row.game}:${row.item}`));
    if (!result.available || !result.selected) violations.push(`${cohort}:missing-selected`);
    if (peerKeys.has(selectedKey)) violations.push(`${cohort}:selected-in-peer-set`);
    if (result.denominator.allPeers !== result.denominator.priorPeers + result.denominator.sameGamePeers + result.denominator.futurePeers) {
      violations.push(`${cohort}:temporal-partition`);
    }
    if (result.priorPeers.some(row => row.game >= item.game)) violations.push(`${cohort}:future-in-prior`);
    if (result.sameGamePeers.some(row => row.game !== item.game)) violations.push(`${cohort}:bad-same-game`);
    if (result.futurePeers.some(row => row.game <= item.game)) violations.push(`${cohort}:bad-future`);
    for (const metric of result.metrics) {
      metricCapacity += result.denominator.priorPeers;
      metricObservations += metric.prior.observations;
      if (metric.prior.observations > result.denominator.priorPeers || metric.all.observations > result.denominator.allPeers) {
        violations.push(`${cohort}:metric-denominator`);
      }
      if (metric.prior.percentile !== null && (metric.prior.percentile < 0 || metric.prior.percentile > 1)) {
        violations.push(`${cohort}:prior-percentile`);
      }
    }
    for (const analogue of result.priorAnalogues) {
      if (analogue.game >= item.game) violations.push(`${cohort}:future-prior-analogue`);
      if (analogue.game === item.game && analogue.item === item.item) violations.push(`${cohort}:selected-prior-analogue`);
      if (analogue.dimensions < 2) violations.push(`${cohort}:thin-prior-analogue`);
    }
    for (const analogue of result.analogues) {
      const expectedSide = analogue.game < item.game ? "strictly-prior"
        : analogue.game === item.game ? "same-game-hindsight" : "future-hindsight";
      if (analogue.temporalSide !== expectedSide) violations.push(`${cohort}:analogue-temporal-label`);
      if (analogue.game === item.game && analogue.item === item.item) violations.push(`${cohort}:selected-analogue`);
      if (analogue.dimensions < 2) violations.push(`${cohort}:thin-analogue`);
    }
    if (result.analogues.length) analogueEligible += 1;
    priorCounts.push(result.denominator.priorPeers);
    allCounts.push(result.denominator.allPeers);
  }

  priorCounts.sort((a, b) => a - b);
  allCounts.sort((a, b) => a - b);
  const quantile = (values, probability) => values[Math.floor((values.length - 1) * probability)] ?? null;
  cohortStats[cohort] = {
    itemsChecked: priorCounts.length,
    zeroPriorPeers: priorCounts.filter(value => value === 0).length,
    fewerThanFivePriorPeers: priorCounts.filter(value => value < 5).length,
    priorPeerP50: quantile(priorCounts, .5),
    priorPeerP90: quantile(priorCounts, .9),
    priorPeerMax: priorCounts.at(-1) ?? null,
    allPeerP50: quantile(allCounts, .5),
    allPeerP90: quantile(allCounts, .9),
    allPeerMax: allCounts.at(-1) ?? null,
    itemsWithNumericAnalogues: analogueEligible,
    priorMetricCoverage: metricCapacity ? metricObservations / metricCapacity : null,
  };
}

const output = {
  ok: violations.length === 0,
  schemaVersion: overview.schemaVersion,
  materializedAt: overview.generatedAt,
  indexedItems: overview.itemIndex.length,
  reviewerCells: reviewer.cells.length,
  regretRows: regretRows.length,
  reviewerEvidenceLoad: {
    issuerLowerBound: regretTotals.issuerForegoneLowerBound,
    observedWrongReview: regretTotals.wrongReviewerCost,
    combinedEvidenceIndex: regretTotals.combinedEvidenceLoad,
    hiddenRejectedFraudGroups: regretTotals.hiddenFraudGroups,
  },
  cohorts: cohortStats,
  violations: [...new Set(violations)].sort(),
};

process.stdout.write(`${JSON.stringify(output)}\n`);
if (!output.ok) process.exitCode = 1;

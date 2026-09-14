from __future__ import annotations

import json
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path


VIZ = Path(__file__).resolve().parents[1]


class _MarkupInventory(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.images_without_alt: list[str] = []
        self.inputs: list[dict[str, str]] = []
        self.labels_for: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        row = {key: value or "" for key, value in attrs}
        if row.get("id"):
            self.ids.append(row["id"])
        if tag == "img" and "alt" not in row:
            self.images_without_alt.append(row.get("id", "<anonymous>"))
        if tag in {"input", "select"}:
            self.inputs.append(row)
        if tag == "label" and row.get("for"):
            self.labels_for.add(row["for"])


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (VIZ / "static" / "index.html").read_text()
        cls.javascript = (VIZ / "static" / "app.js").read_text()
        cls.css = (VIZ / "static" / "styles.css").read_text()
        cls.inventory = _MarkupInventory()
        cls.inventory.feed(cls.html)

    def test_html_ids_are_unique_and_all_javascript_id_refs_exist(self) -> None:
        self.assertEqual(len(self.inventory.ids), len(set(self.inventory.ids)))
        refs = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)', self.javascript))
        self.assertEqual(refs - set(self.inventory.ids), set())

    def test_css_braces_are_balanced(self) -> None:
        self.assertEqual(self.css.count("{"), self.css.count("}"))

    def test_images_have_alt_text_and_controls_have_names(self) -> None:
        self.assertEqual(self.inventory.images_without_alt, [])
        labelled = self.inventory.labels_for
        for row in self.inventory.inputs:
            if row.get("type") == "hidden":
                continue
            self.assertTrue(row.get("aria-label") or row.get("id") in labelled,
                            f"unlabelled control: {row.get('id')}")

    def test_no_dynamic_html_sink_or_emoji_placeholders(self) -> None:
        self.assertNotIn("innerHTML", self.javascript)
        self.assertNotIn("↳", self.html)
        self.assertNotIn("⌁", self.html)

    def test_tooltips_iterate_complete_lines_and_strategy_has_table_fallback(self) -> None:
        self.assertIn("[].concat(lines).entries()", self.javascript)
        self.assertIn('id="valuation-landscape"', self.html)
        self.assertIn('id="landscape-data-table"', self.html)
        self.assertIn('id="risk-lattice"', self.html)
        self.assertIn('id="robustness-data-table"', self.html)
        self.assertIn('id="rule-data-table"', self.html)
        self.assertIn('id="rule-transition-matrix"', self.html)
        self.assertIn('id="flight-data-table"', self.html)
        self.assertIn('id="capital-flow-table"', self.html)
        self.assertIn('id="flight-chart"', self.html)
        self.assertIn('id="capital-flow-chart"', self.html)
        self.assertIn('id="replay-chart"', self.html)
        self.assertIn('id="replay-data-table"', self.html)
        self.assertIn('id="replay-item-grid"', self.html)
        self.assertIn('id="evidence-atlas-chart"', self.html)
        self.assertIn('id="evidence-atlas-data-table"', self.html)
        self.assertIn('id="round-map-table"', self.html)
        self.assertIn('id="round-phase-chart"', self.html)
        self.assertIn('id="portfolio-overlap-data-table"', self.html)
        self.assertIn('id="portfolio-ledger-table"', self.html)
        self.assertIn('id="portfolio-score-chart"', self.html)
        self.assertIn('id="portfolio-gate-data-table"', self.html)
        self.assertIn('id="portfolio-temporal-data-table"', self.html)
        self.assertIn('id="portfolio-temporal-chart"', self.html)
        self.assertIn('id="portfolio-readiness"', self.html)
        self.assertIn('id="finish-simulator"', self.html)
        self.assertIn('id="forecast-cone"', self.html)
        self.assertIn('id="forecast-ranks"', self.html)
        self.assertIn('id="forecast-rivals"', self.html)
        self.assertIn('id="forecast-validation-chart"', self.html)
        self.assertIn('id="forecast-cone-table"', self.html)
        self.assertIn('id="forecast-rank-table"', self.html)
        self.assertIn('id="forecast-rival-table"', self.html)
        self.assertIn('id="forecast-validation-table"', self.html)
        self.assertIn('id="reviewer-lab"', self.html)
        self.assertIn('id="reviewer-matrix"', self.html)
        self.assertIn('id="reviewer-waterfall"', self.html)
        self.assertIn('id="reviewer-buckets"', self.html)
        self.assertIn('id="reviewer-margin-chart"', self.html)
        self.assertIn('id="reviewer-temporal-chart"', self.html)
        self.assertIn('id="reviewer-sweep-chart"', self.html)
        self.assertIn('id="reviewer-sweep-table"', self.html)
        self.assertIn('id="reviewer-breakpoint-table"', self.html)
        self.assertIn('id="reviewer-margin-table"', self.html)
        self.assertIn('id="peer-forensics"', self.html)
        self.assertIn('id="peer-fingerprint-chart"', self.html)
        self.assertIn('id="peer-envelope-chart"', self.html)
        self.assertIn('id="peer-temporal-chart"', self.html)
        self.assertIn('id="peer-analogue-table"', self.html)
        self.assertIn('id="peer-metric-table"', self.html)
        self.assertIn('id="cohort-studio"', self.html)
        self.assertIn('id="cohort-forest-chart"', self.html)
        self.assertIn('id="cohort-bootstrap-chart"', self.html)
        self.assertIn('id="cohort-temporal-chart"', self.html)
        self.assertIn('id="cohort-overlap"', self.html)
        self.assertIn('id="cohort-metric-table"', self.html)
        self.assertIn('id="cohort-bootstrap-table"', self.html)
        self.assertIn('id="cohort-temporal-table"', self.html)
        self.assertIn('id="cohort-divergence-table"', self.html)
        self.assertIn('id="market-panel"', self.html)
        self.assertIn('id="market-matrix"', self.html)
        self.assertIn('id="market-outcome"', self.html)
        self.assertIn('id="market-bilateral-chart"', self.html)
        self.assertIn('id="market-timeline-chart"', self.html)
        self.assertIn('id="market-replay-slider"', self.html)
        self.assertIn('id="market-pair-trajectory"', self.html)
        self.assertIn('id="market-pair-timeline-table"', self.html)
        self.assertIn('id="market-edge-table"', self.html)
        self.assertIn('id="market-team-table"', self.html)
        self.assertIn('id="market-timeline-table"', self.html)
        self.assertIn('id="rival-benchmark"', self.html)
        self.assertIn('id="rival-bridge-chart"', self.html)
        self.assertIn('id="rival-gap-chart"', self.html)
        self.assertIn('id="rival-quadrant-chart"', self.html)
        self.assertIn('id="rival-efficiency"', self.html)
        self.assertIn('id="rival-decomposition-table"', self.html)
        self.assertIn('id="rival-efficiency-table"', self.html)
        self.assertIn('id="rival-round-table"', self.html)
        self.assertIn('id="drift-observatory"', self.html)
        self.assertIn('id="drift-control-chart"', self.html)
        self.assertIn('id="source-drift-chart"', self.html)
        self.assertIn('id="drift-control-table"', self.html)
        self.assertIn('id="source-drift-table"', self.html)
        self.assertIn('id="calibration-studio"', self.html)
        self.assertIn('id="calibration-frontier-chart"', self.html)
        self.assertIn('id="calibration-source-chart"', self.html)
        self.assertIn('id="calibration-geometry-chart"', self.html)
        self.assertIn('id="calibration-bucket-chart"', self.html)
        self.assertIn('id="calibration-temporal-chart"', self.html)
        self.assertIn('id="calibration-frontier-table"', self.html)
        self.assertIn('id="calibration-source-table"', self.html)
        self.assertIn('id="calibration-item-table"', self.html)
        self.assertIn('id="calibration-bucket-table"', self.html)
        self.assertIn('id="calibration-temporal-table"', self.html)
        self.assertIn('id="regret-cartography"', self.html)
        self.assertIn('id="regret-atlas-chart"', self.html)
        self.assertIn('id="regret-temporal-chart"', self.html)
        self.assertIn('id="regret-taxonomy"', self.html)
        self.assertIn('id="regret-concentration-chart"', self.html)
        self.assertIn('id="regret-value-chart"', self.html)
        self.assertIn('id="regret-routing-lattice"', self.html)
        self.assertIn('id="regret-item-table"', self.html)
        self.assertIn('id="regret-game-table"', self.html)
        self.assertIn('id="regret-taxonomy-table"', self.html)
        self.assertIn('id="regret-value-table"', self.html)
        self.assertIn('id="regret-routing-table"', self.html)
        self.assertIn('id="operations-war-room"', self.html)
        self.assertIn('id="operations-stage-chart"', self.html)
        self.assertIn('id="operations-deadline-chart"', self.html)
        self.assertIn('id="operations-envelope-chart"', self.html)
        self.assertIn('id="operations-data-table"', self.html)

    def test_frontend_and_materialiser_schema_versions_match(self) -> None:
        backend = (VIZ / "data_layer.py").read_text()
        backend_version = re.search(r'"schemaVersion":\s*(\d+)', backend)
        frontend_version = re.search(r'overview\.schemaVersion\s*!==\s*(\d+)', self.javascript)
        self.assertIsNotNone(backend_version)
        self.assertIsNotNone(frontend_version)
        self.assertEqual(backend_version.group(1), frontend_version.group(1))

    def test_deep_links_contain_identifiers_not_claim_content(self) -> None:
        self.assertIn('url.searchParams.set("game"', self.javascript)
        self.assertIn('url.searchParams.set("drift"', self.javascript)
        self.assertIn('url.searchParams.set("item"', self.javascript)
        sync_body = self.javascript.split("function syncInvestigationUrl", 1)[1].split(
            "async function copyInvestigationLink", 1
        )[0]
        self.assertNotIn("description", sync_body)
        self.assertNotIn("policy", sync_body)
        self.assertIn('url.searchParams.set("robust"', sync_body)
        self.assertIn('url.searchParams.set("rule"', sync_body)
        self.assertIn('url.searchParams.set("capital"', sync_body)
        self.assertIn('url.searchParams.set("roundmap"', sync_body)
        self.assertIn('url.searchParams.set("prule"', sync_body)
        self.assertIn('url.searchParams.set("pgate"', sync_body)
        self.assertIn('url.searchParams.set("evidence"', sync_body)
        self.assertIn('url.searchParams.set("cohort"', sync_body)
        self.assertIn('url.searchParams.set("market"', sync_body)
        self.assertIn('url.searchParams.set("rival"', sync_body)
        self.assertIn('url.searchParams.set("calibration"', sync_body)
        self.assertIn('url.searchParams.set("regret"', sync_body)
        self.assertIn('url.searchParams.set("peer"', sync_body)
        server = (VIZ / "server.py").read_text()
        limit = int(re.search(r"MAX_QUERY_FIELDS\s*=\s*(\d+)", server).group(1))
        encoded_fields = set(re.findall(r'url\.searchParams\.set\("([a-z]+)"', sync_body))
        self.assertLessEqual(len(encoded_fields), limit)
        self.assertEqual(encoded_fields, {
            "game", "item", "compare", "source", "bucket", "status", "opponent",
            "robust", "rule", "capital", "roundmap", "prule", "pgate", "pdir",
            "psource", "evidence", "forecast", "reviewer", "cohort", "market",
            "drift", "rival", "calibration", "regret", "peer",
        })

    def test_reviewer_policy_evaluator_prices_only_proven_candidate_costs(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
const start = source.indexOf("function evaluateReviewerPolicy");
const end = source.indexOf("\nfunction reviewerOutcomeLabel", start);
if (start < 0 || end < 0) throw new Error("reviewer policy evaluator not found");
eval(source.slice(start,end));
const cells = [
 {game:9,item:1,opponent:"A",source:"s",valueBucket:"50–400",provenClass:"fair",outcome:"rejectFair",actualAccepted:false,actualCost:150,b:80,charge:100,tLo:120,chargeKind:"exact",fairExactEligible:true,fraudDownshiftEligible:false,hiddenFraudEligible:false},
 {game:9,item:2,opponent:"A",source:"s",valueBucket:"0–50",provenClass:"fair",outcome:"acceptFair",actualAccepted:true,actualCost:40,b:50,charge:40,tLo:45,chargeKind:"exact",fairExactEligible:true,fraudDownshiftEligible:false,hiddenFraudEligible:false},
 {game:10,item:1,opponent:"B",source:"s",valueBucket:"400–1200",provenClass:"fraud",outcome:"acceptFraud",actualAccepted:true,actualCost:500,b:600,charge:500,tLo:450,chargeKind:"lower_bound",fairExactEligible:false,fraudDownshiftEligible:true,hiddenFraudEligible:false},
 {game:10,item:2,opponent:"B",source:"s",valueBucket:"50–400",provenClass:"fraud",outcome:"rejectFraud",actualAccepted:false,actualCost:0,b:100,charge:null,tLo:80,chargeKind:"hidden",fairExactEligible:false,fraudDownshiftEligible:false,hiddenFraudEligible:true},
 {game:10,item:3,opponent:"C",source:null,valueBucket:"unlabelled",provenClass:"unproven",outcome:null,actualAccepted:true,actualCost:75,b:90,charge:75,tLo:null,chargeKind:"observed_payout",fairExactEligible:false,fraudDownshiftEligible:false,hiddenFraudEligible:false},
 {game:10,item:4,opponent:"C",source:null,valueBucket:"1200+",provenClass:"fair",outcome:"acceptFair",actualAccepted:true,actualCost:2000,b:null,charge:2000,tLo:1800,chargeKind:"exact",fairExactEligible:false,fraudDownshiftEligible:false,hiddenFraudEligible:false},
];
const zero=evaluateReviewerPolicy(cells,{window:"all",opponent:"all",source:"all",provenClass:"all",shifts:{}});
const changed=evaluateReviewerPolicy(cells,{window:"all",opponent:"all",source:"all",provenClass:"all",shifts:{"0–50":-15,"50–400":25,"400–1200":-150,"1200+":0}});
const hidden=changed.transitions.find(row=>row.transitionKind==="hidden-exposure");
const fraud=evaluateReviewerPolicy(cells,{window:"all",opponent:"all",source:"all",provenClass:"fraud",shifts:{"50–400":25,"400–1200":-150}});
const sweep=reviewerPolicySweep(cells,{window:"all",opponent:"all",source:"all",provenClass:"all",shifts:{"50–400":25}});
const lowSweep=sweep.find(row=>row.bucket==="50–400").points;
process.stdout.write(JSON.stringify({zero:zero.totals,changed:changed.totals,hidden,fraud:fraud.totals,buckets:changed.buckets,transitions:changed.transitions.length,margins:changed.margins.length,sweepZeroes:sweep.map(row=>row.points.find(point=>point.shift===0).pricedDelta),hiddenSweep:lowSweep.filter(row=>row.shift>=0).map(row=>row.hiddenExposures)}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual((payload["zero"]["pricedCells"], payload["zero"]["pricedDelta"],
                          payload["zero"]["hiddenExposures"]), (3, 0, 0))
        self.assertEqual((payload["changed"]["pricedCells"],
                          payload["changed"]["pricedDelta"],
                          payload["changed"]["fairSwitches"],
                          payload["changed"]["fraudSwitches"]), (3, -530, 2, 1))
        self.assertEqual((payload["changed"]["fairDelta"],
                          payload["changed"]["fraudDelta"],
                          payload["changed"]["hiddenExposures"]), (-30, -500, 1))
        self.assertIsNone(payload["hidden"]["charge"])
        self.assertIsNone(payload["hidden"]["pricedDelta"])
        self.assertEqual((payload["fraud"]["cells"], payload["fraud"]["pricedDelta"],
                          payload["fraud"]["hiddenExposures"]), (2, -500, 1))
        self.assertEqual(payload["transitions"], 4)
        self.assertEqual(payload["margins"], 3)
        self.assertEqual(payload["sweepZeroes"], [0, 0, 0, 0])
        self.assertEqual(payload["hiddenSweep"], sorted(payload["hiddenSweep"]))

    def test_reviewer_receipt_is_claim_free_and_keeps_unknown_exposure_unpriced(self) -> None:
        body = self.javascript.split("async function copyReviewerReceipt", 1)[1].split(
            "function populateStrategyControls", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('status: "offline-partial-observed-cost-counterfactual-only"', body)
        self.assertIn("potentiallyExposedHiddenFraudGroups", body)
        self.assertIn('"hidden rejected-fraud amounts and candidate crossings remain unpriced"', body)
        self.assertIn('"no policy change is submitted or written by this local interface"', body)
        self.assertIn("catch (error)", body)

    def test_cohort_comparator_uses_fixed_item_denominators_and_game_cluster_bootstrap(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function clamp(value,lo,hi){return Math.min(hi,Math.max(lo,value));}
function valueBucket(floor){if(!Number.isFinite(Number(floor)))return null;if(floor<50)return"0–50";if(floor<400)return"50–400";if(floor<1200)return"400–1200";return"1200+";}
function isNotProvenWrong(row){return row.status==="inside-bracket"||row.status==="above-floor-open-ceiling";}
function seededGenerator(seed){let value=Number(seed)>>>0;return()=>{value+=0x6D2B79F5;let mixed=value;mixed=Math.imul(mixed^mixed>>>15,mixed|1);mixed^=mixed+Math.imul(mixed^mixed>>>7,mixed|61);return((mixed^mixed>>>14)>>>0)/4294967296;};}
function numericQuantile(values,p){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const pos=clamp(Number(p),0,1)*(clean.length-1),lo=Math.floor(pos),hi=Math.ceil(pos);return lo===hi?clean[lo]:clean[lo]+(clean[hi]-clean[lo])*(pos-lo);}
const start=source.indexOf("function cohortGameIds");
const end=source.indexOf("\nfunction reviewerOutcomeLabel",start);
if(start<0||end<0)throw new Error("cohort functions not found");
eval(source.slice(start,end));
const items=[
 {game:1,item:1,source:"s",status:"under",tLo:100,tHi:120,a:50,foregoneLowerBound:800},
 {game:2,item:1,source:"s",status:"over",tLo:100,tHi:120,a:130,foregoneLowerBound:0},
 {game:3,item:1,source:"s",status:"inside-bracket",tLo:100,tHi:120,a:100,foregoneLowerBound:0},
 {game:4,item:1,source:"s",status:"inside-bracket",tLo:200,tHi:240,a:200,foregoneLowerBound:0},
];
const reviews=[
 {game:1,item:1,outcome:"rejectFair",provenClass:"fair",actualCost:150},
 {game:2,item:1,outcome:"acceptFraud",provenClass:"fraud",actualCost:130},
 {game:3,item:1,outcome:"acceptFair",provenClass:"fair",actualCost:100},
 {game:4,item:1,outcome:"rejectFraud",provenClass:"fraud",actualCost:0},
];
const games=[1,2,3,4];
const spec={source:"all",bucket:"all",status:"all"};
const a=evaluateCohort(items,reviews,{...spec,window:"first-half"},games);
const b=evaluateCohort(items,reviews,{...spec,window:"second-half"},games);
const boot=bootstrapCohortComparison(a,b,{runs:600,seed:77});
const repeat=bootstrapCohortComparison(a,b,{runs:600,seed:77});
const same=bootstrapCohortComparison(evaluateCohort(items,reviews,{...spec,window:"all"},games),evaluateCohort(items,reviews,{...spec,window:"all"},games),{runs:300,seed:9});
const overlap=cohortOverlap(a,b,items);
process.stdout.write(JSON.stringify({a:a.metrics,b:b.metrics,boot:{paired:boot.paired,runs:boot.runs,score:boot.results.find(r=>r.key==="score"),wrong:boot.results.find(r=>r.key==="wrongCostPerProvenReview")},deterministic:JSON.stringify(boot)===JSON.stringify(repeat),same:{paired:same.paired,deltas:same.results.map(r=>r.observedDelta)},overlap}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual((payload["a"]["bestPossible"], payload["a"]["provenIncome"],
                          payload["a"]["score"]), (3200, 800, 0.25))
        self.assertEqual((payload["a"]["underRate"], payload["a"]["overRate"],
                          payload["a"]["wrongCostPerProvenReview"]), (0.5, 0.5, 140))
        self.assertEqual((payload["b"]["bestPossible"], payload["b"]["provenIncome"],
                          payload["b"]["score"]), (4800, 4800, 1))
        self.assertFalse(payload["boot"]["paired"])
        self.assertEqual(payload["boot"]["runs"], 600)
        self.assertEqual(payload["boot"]["score"]["observedDelta"], 0.75)
        self.assertEqual(payload["boot"]["wrong"]["observedDelta"], -140)
        self.assertTrue(payload["deterministic"])
        self.assertTrue(payload["same"]["paired"])
        self.assertEqual(payload["same"]["deltas"], [0] * 7)
        self.assertEqual(payload["overlap"], {"both": 0, "aOnly": 2, "bOnly": 2,
                                               "neither": 0, "universe": 4})

    def test_cohort_receipt_is_claim_free_reproducible_and_noncausal(self) -> None:
        body = self.javascript.split("async function copyCohortReceipt", 1)[1].split(
            "function populateStrategyControls", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('status: "offline-retrospective-cohort-comparison-only"', body)
        self.assertIn("bestPossible: cohort.metrics.bestPossible", body)
        self.assertIn("draws: result.bootstrap.runs, seed: result.bootstrap.seed", body)
        self.assertIn('"retrospective filtered cohorts, not randomized treatments or causal effects"', body)
        self.assertIn('"hidden rejected-fraud amounts are absent from reviewer-cost metrics"', body)
        self.assertIn('"no model, rule, acceptance limit, charge, or submission is modified"', body)
        self.assertIn("catch (error)", body)

    def test_market_receipt_is_claim_free_reconciled_and_observability_bounded(self) -> None:
        body = self.javascript.split("async function copyMarketReceipt", 1)[1].split(
            "function valueBucket", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('status: "offline-observed-market-accounting-only"', body)
        self.assertIn("replay: {mode: state.marketReplayMode, throughGame: view.game, includedGames: view.frameCount}", body)
        self.assertIn("selectedTeamSummary: {...summary}", body)
        self.assertIn("hiddenRejectedFraudAgainstSelectedTeam", body)
        self.assertIn('"observed settlement accounting, not causal exploitation or counterfactual tournament impact"', body)
        self.assertIn('"rejected fraudulent attempted amounts are invisible, so wrong-cost and flow views are lower bounds"', body)
        self.assertIn('"the replay changes the observed temporal denominator; it does not simulate alternate decisions"', body)
        self.assertIn('"no charge, limit, rule, model, process, or submission is modified"', body)
        self.assertIn("catch (error)", body)

    def test_market_replay_uses_dense_validated_frames_and_exact_temporal_windows(self) -> None:
        script = r'''
const fs=require("fs");
const source=fs.readFileSync(process.argv[1],"utf8");
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function clamp(value,lo,hi){return Math.min(hi,Math.max(lo,value));}
const state={market:null,marketReplayMode:"cumulative",marketReplayIndex:0,marketFramesByGame:new Map(),marketViewCache:new Map()};
const start=source.indexOf("const MARKET_TIMELINE_COLUMNS");
const end=source.indexOf("\nfunction marketMetricSpec",start);
if(start<0||end<0)throw new Error("market replay functions not found");
eval(source.slice(start,end));
const columns=["game","issuerIndex","reviewerIndex","decisions","accepted","issuerIncome","reviewerCost","penaltyWedge","wrongCost","unresolvedCount","unresolvedCost","hiddenFraud","acceptFairCount","acceptFairCost","rejectFairCount","rejectFairCost","acceptFraudCount","acceptFraudCost","rejectFraudCount","rejectFraudCost"];
const teams=["A","B","C"],games=[1,2];
function encoded(game,issuerIndex,reviewerIndex,patch={}){
  const base=Object.fromEntries(columns.map(column=>[column,0]));
  Object.assign(base,{game,issuerIndex,reviewerIndex},patch);
  return columns.map(column=>base[column]);
}
const rows=[];
for(const game of games)for(let issuer=0;issuer<teams.length;issuer++)for(let reviewer=0;reviewer<teams.length;reviewer++){
  if(issuer===reviewer)continue;
  let patch={};
  if(game===1&&issuer===0&&reviewer===1)patch={decisions:2,accepted:1,issuerIncome:100,reviewerCost:150,penaltyWedge:50,wrongCost:150,acceptFairCount:1,acceptFairCost:0,rejectFairCount:1,rejectFairCost:150};
  if(game===2&&issuer===0&&reviewer===1)patch={decisions:1,accepted:1,issuerIncome:80,reviewerCost:80,acceptFairCount:1,acceptFairCost:80};
  rows.push(encoded(game,issuer,reviewer,patch));
}
const payload={schemaVersion:2,teams,gameIds:games,edgeTimeline:{encoding:"dense-array-v1",columns,rows},edges:[]};
payload.edges=teams.flatMap((issuer,issuerIndex)=>teams.flatMap((reviewer,reviewerIndex)=>{
  if(issuer===reviewer)return[];
  const edge={issuer,reviewer};columns.slice(3).forEach(field=>edge[field]=0);
  rows.filter(raw=>raw[1]===issuerIndex&&raw[2]===reviewerIndex).forEach(raw=>columns.slice(3).forEach((field,offset)=>edge[field]+=raw[offset+3]));
  edge.acceptRate=edge.decisions?edge.accepted/edge.decisions:null;edge.netExchange=edge.issuerIncome-edge.reviewerCost;
  return[edge];
}));
payload.summaries=teams.map(team=>({team,issuedIncome:0,reviewerCost:0,net:0,issuedDecisions:0,reviewedDecisions:0,acceptedByMarket:0,reviewerAccepts:0,marketAcceptRate:null,reviewerAcceptRate:null,wrongReviewCost:0,rejectFairCount:0,rejectFairCost:0,acceptFraudCount:0,acceptFraudCost:0,hiddenFraud:0,chargeGroups:0,aggressionObservations:0,medianChargeToFloor:null,aggressionCoverage:0,officialTotal:0,scoreReconciliationDelta:0}));
payload.timeline=teams.flatMap(team=>games.map(game=>({team,game,issuedIncome:0,reviewerCost:0,net:0,cumulativeNet:0,issuedDecisions:0,acceptedByMarket:0,reviewedDecisions:0,reviewerAccepts:0,marketAcceptRate:null,reviewerAcceptRate:null,officialScore:0,officialCumulativeScore:0,scoreReconciliationDelta:0})));
const byGame=decodeMarketFrames(payload);
const fullEdges=teams.flatMap(issuer=>teams.filter(reviewer=>reviewer!==issuer).map(reviewer=>{
  const edge=emptyMarketEdge(issuer,reviewer);
  games.forEach(game=>(byGame.get(game)||[]).filter(frame=>frame.issuer===issuer&&frame.reviewer===reviewer).forEach(frame=>addMarketFrame(edge,frame)));
  return finalizeMarketEdge(edge);
}));
payload.edges=fullEdges;
payload.timeline=teams.flatMap(team=>games.map(game=>{
  const frames=byGame.get(game);
  const issuedIncome=frames.filter(row=>row.issuer===team).reduce((sum,row)=>sum+row.issuerIncome,0);
  const reviewerCost=frames.filter(row=>row.reviewer===team).reduce((sum,row)=>sum+row.reviewerCost,0);
  return {team,game,issuedIncome,reviewerCost,net:issuedIncome-reviewerCost,cumulativeNet:0,issuedDecisions:0,acceptedByMarket:0,reviewedDecisions:0,reviewerAccepts:0,marketAcceptRate:null,reviewerAcceptRate:null,officialScore:issuedIncome-reviewerCost,officialCumulativeScore:0,scoreReconciliationDelta:0};
}));
state.market=payload;state.marketFramesByGame=byGame;
const first=currentMarketView();
const firstEdge=first.edgeMap.get("A\u0000B");
state.marketReplayMode="round";state.marketReplayIndex=1;
const second=currentMarketView();
const secondEdge=second.edgeMap.get("A\u0000B");
state.marketReplayMode="cumulative";state.marketReplayIndex=1;
const cumulative=currentMarketView();
const cumulativeEdge=cumulative.edgeMap.get("A\u0000B");
const bad=JSON.parse(JSON.stringify(payload));bad.edgeTimeline.rows[0][3]=1;
let malformedRejected=false;try{decodeMarketFrames(bad);}catch{malformedRejected=true;}
process.stdout.write(JSON.stringify({frames:[...byGame.values()].reduce((sum,value)=>sum+value.length,0),first:{decisions:firstEdge.decisions,income:firstEdge.issuerIncome,cost:firstEdge.reviewerCost,aNet:first.summaries.find(row=>row.team==="A").net,bNet:first.summaries.find(row=>row.team==="B").net},second:{decisions:secondEdge.decisions,income:secondEdge.issuerIncome,cost:secondEdge.reviewerCost},cumulative:{decisions:cumulativeEdge.decisions,income:cumulativeEdge.issuerIncome,cost:cumulativeEdge.reviewerCost},malformedRejected}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["frames"], 12)
        self.assertEqual(payload["first"], {
            "decisions": 2, "income": 100, "cost": 150,
            "aNet": 100, "bNet": -150,
        })
        self.assertEqual(payload["second"], {"decisions": 1, "income": 80, "cost": 80})
        self.assertEqual(payload["cumulative"], {"decisions": 3, "income": 180, "cost": 230})
        self.assertTrue(payload["malformedRejected"])

    def test_operations_contract_rejects_hidden_fields_and_reconciles_deadlines(self) -> None:
        script = r'''
const fs=require("fs");const source=fs.readFileSync(process.argv[1],"utf8");
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function formatDurationMs(value){return String(value);}function formatPercent(value){return String(value);}
const start=source.indexOf("const OPERATIONS_STAGES");const end=source.indexOf("\nfunction updateClock",start);
if(start<0||end<0)throw new Error("operations functions not found");eval(source.slice(start,end));
const stages=["round.scheduled","key.received","case.decrypted","case.parsed","item.belief","item.decided","submission.built","submission.sent","submission.verified","round.played"];
const times=value=>Object.fromEntries(stages.map(stage=>[stage,value]));
function game(game,patch={}){return {game,played:true,recorded:false,coreCoverage:0,eventCount:0,observedStages:[],stageTimesMs:times(null),firstSendMs:null,tier1SendMs:null,tier2SendMs:null,tier1TargetStatus:"unobserved",tier2DeadlineStatus:"unobserved",submissionCalls:0,successfulCalls:0,failedCalls:0,alerts:0,roundPlayedObserved:false,lastStage:null,lastStageAt:"",lastElapsedMs:null,observedSpanMs:null,...patch};}
const games=[
 game(1,{recorded:true,coreCoverage:1,eventCount:12,observedStages:[...stages],stageTimesMs:Object.fromEntries(stages.map((stage,index)=>[stage,index*500])),firstSendMs:1800,tier1SendMs:1800,tier2SendMs:50000,tier1TargetStatus:"met",tier2DeadlineStatus:"met",submissionCalls:2,successfulCalls:2,roundPlayedObserved:true,lastStage:"round.played",lastStageAt:"2026-01-01T00:00:50+00:00",lastElapsedMs:50000,observedSpanMs:50000}),
 game(2,{recorded:true,coreCoverage:.2,eventCount:2,observedStages:["round.scheduled","submission.sent"],stageTimesMs:{...times(null),"round.scheduled":0,"submission.sent":2500},firstSendMs:2500,tier1SendMs:2500,tier1TargetStatus:"late",submissionCalls:1,failedCalls:1,alerts:1,lastStage:"submission.sent",lastStageAt:"2026-01-01T00:13:00+00:00",lastElapsedMs:2500,observedSpanMs:2500}),
 game(3),
];
const envelope=stages.map((stage,index)=>{const observations=games.filter(row=>row.stageTimesMs[stage]!==null).length;return {stage,observations,p10Ms:index*400,p50Ms:index*500,p90Ms:index*600};});
const summary={playedGames:3,pipelineGames:2,recordedPlayedGames:2,missingPlayedGames:1,recordedCoverage:2/3,completeCoreGames:1,meanCoreCoverage:.6,tier1Observed:2,tier1AtOrUnderTarget:1,tier1TargetRate:.5,tier1P50Ms:2150,tier1P95Ms:2465,tier2Observed:1,tier2AtOrUnderDeadline:1,tier2DeadlineRate:1,tier2P50Ms:50000,tier2P95Ms:50000,failedSubmissionCalls:1,alerts:1};
const payload={schemaVersion:1,stages,telemetryStatus:"stale-played-rounds",latestPlayedGame:3,latestRecordedGame:2,lagPlayedGames:1,latestEventAt:"2026-01-01T00:13:00+00:00",latestEventAgeSeconds:600,latestSubmissionAt:"2026-01-01T00:13:00+00:00",latestSubmissionAgeSeconds:600,games,stageEnvelope:envelope,summary};
const valid=validateOperations(payload);let hiddenRejected=false,denominatorRejected=false,freshnessRejected=false,envelopeRejected=false;
const hidden=structuredClone(payload);hidden.games[0].description="forbidden";try{validateOperations(hidden);}catch{hiddenRejected=true;}
const broken=structuredClone(payload);broken.summary.tier1Observed=1;try{validateOperations(broken);}catch{denominatorRejected=true;}
const fresh=structuredClone(payload);fresh.telemetryStatus="current";try{validateOperations(fresh);}catch{freshnessRejected=true;}
const badEnvelope=structuredClone(payload);badEnvelope.stageEnvelope[0].observations=1;try{validateOperations(badEnvelope);}catch{envelopeRejected=true;}
process.stdout.write(JSON.stringify({status:valid.telemetryStatus,lag:valid.lagPlayedGames,recorded:valid.summary.recordedPlayedGames,tier1:valid.summary.tier1AtOrUnderTarget,tier2:valid.summary.tier2AtOrUnderDeadline,hiddenRejected,denominatorRejected,freshnessRejected,envelopeRejected}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload, {
            "status": "stale-played-rounds", "lag": 1, "recorded": 2,
            "tier1": 1, "tier2": 1, "hiddenRejected": True,
            "denominatorRejected": True, "freshnessRejected": True,
            "envelopeRejected": True,
        })

    def test_operations_receipt_is_claim_free_and_never_claims_daemon_health(self) -> None:
        body = self.javascript.split("async function copyOperationsReceipt", 1)[1].split(
            "function updateClock", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('status: "offline-local-recorder-evidence-only"', body)
        self.assertIn('"one local append-only recorder, not proof of daemon or separate-repository activity"', body)
        self.assertIn('"missing boundaries are unknown and never converted into failed or absent submissions"', body)
        self.assertIn('"no process, charge, limit, rule, model, or submission is modified"', body)
        self.assertIn("catch (error)", body)

    def test_drift_contract_is_strictly_temporal_robust_and_source_bounded(self) -> None:
        script = r'''
const fs=require("fs");const source=fs.readFileSync(process.argv[1],"utf8");
function clamp(value,lo,hi){return Math.min(hi,Math.max(lo,value));}
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function medianNumber(values){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const m=Math.floor(clean.length/2);return clean.length%2?clean[m]:(clean[m-1]+clean[m])/2;}
const start=source.indexOf("const DRIFT_METRICS");const end=source.indexOf("\nconst OPERATIONS_STAGES",start);
if(start<0||end<0)throw new Error("drift functions not found");eval(source.slice(start,end));
const gameIds=[1,2,3,4,5,6,7,8];const nets=[0,2,-1,1,-2,50,2,3];
const overview={race:{gameIds},trends:{
 economics:gameIds.map((game,index)=>({game,net:nets[index],income:100+nets[index],cost:100})),
 decisionStream:gameIds.map(game=>({game,denominatorEuros:100,rejectFair:{euros:30},acceptFraud:{euros:10}})),
 estimationErrors:gameIds.map(game=>({game,values:[-.2,.1,.3]})),
},intelligence:{quality:gameIds.map(game=>({game,thresholdCoverage:.8,items:10}))},itemIndex:[]};
gameIds.forEach(game=>{const sources=game===7?["C","C","C","C"]:["A","A","B","B"];sources.forEach((source,item)=>overview.itemIndex.push({game,item:item+1,source}));});
const analysis=buildDriftAnalysis(overview,"net",5,3);
const changed=structuredClone(overview);changed.trends.economics.at(-1).net=-999;
const changedAnalysis=buildDriftAnalysis(changed,"net",5,3);
const zero=robustControlSeries([1,2,3,4,5,6].map((game,index)=>({game,value:index<5?1:2,denominatorValue:1,denominator:"one"})),5,3);
const sourceRows=buildSourceMixDrift(overview.itemIndex,gameIds,5);
const receipt=buildDriftReceipt(analysis,sourceRows,"2026-01-01T00:00:00Z");
process.stdout.write(JSON.stringify({
 strictPast:JSON.stringify(analysis.points.slice(0,7))===JSON.stringify(changedAnalysis.points.slice(0,7)),
 signal:{game:analysis.points[5].game,kind:analysis.points[5].signal,z:analysis.points[5].robustZ},
 zeroVariance:zero[5].status,
 identicalMix:sourceRows[5].score,shiftedMix:sourceRows[6].score,
 allJsdBounded:sourceRows.filter(row=>row.score!==null).every(row=>row.score>=0&&row.score<=1),
 receiptStatus:receipt.status,receiptSignals:receipt.signals.length,
}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["strictPast"])
        self.assertEqual(payload["signal"]["game"], 6)
        self.assertEqual(payload["signal"]["kind"], "favourable")
        self.assertGreater(payload["signal"]["z"], 3)
        self.assertEqual(payload["zeroVariance"], "variance-zero")
        self.assertAlmostEqual(payload["identicalMix"], 0)
        self.assertAlmostEqual(payload["shiftedMix"], 1)
        self.assertTrue(payload["allJsdBounded"])
        self.assertEqual(payload["receiptStatus"],
                         "offline-strictly-temporal-monitoring-evidence-only")
        self.assertGreaterEqual(payload["receiptSignals"], 1)

    def test_drift_receipt_and_game_links_are_claim_free_and_noncausal(self) -> None:
        body = self.javascript.split("function buildDriftReceipt", 1)[1].split(
            "async function copyDriftReceipt", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('"every baseline contains only earlier observed games;', body)
        self.assertIn('"signals are descriptive process-control flags, not causal change points', body)
        self.assertIn('"no process, charge, limit, rule, model, or submission is modified"', body)
        self.assertIn("function itemLink", self.javascript)

    def test_shared_item_link_navigates_game_item_and_game_only_ledgers(self) -> None:
        script = r'''
const fs=require("fs");const source=fs.readFileSync(process.argv[1],"utf8");
const start=source.indexOf("function itemLink");const end=source.indexOf("\nfunction cssStatus",start);
if(start<0||end<0)throw new Error("itemLink helper not found");
const calls=[];function element(tag,attrs){return {tag,attrs,listeners:{},addEventListener(type,handler){this.listeners[type]=handler;}};}
async function selectGame(game){calls.push(["game",game]);}async function selectItem(item,options){calls.push(["item",item,options.scroll]);}
function $(selector){return {scrollIntoView(options){calls.push(["scroll",selector,options.block]);}};}
eval(source.slice(start,end));
(async()=>{const item=itemLink(3,4);await item.listeners.click();const game=itemLink(5,null,"Game 5");await game.listeners.click();process.stdout.write(JSON.stringify({itemText:item.attrs.text,gameText:game.attrs.text,calls}));})().catch(error=>{process.stderr.write(error.stack);process.exit(1);});
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["itemText"], "game 3 item 4")
        self.assertEqual(payload["gameText"], "Game 5")
        self.assertEqual(payload["calls"], [
            ["game", 3], ["item", 4, True], ["game", 5], ["scroll", "#game", "start"],
        ])

    def test_rival_benchmark_pairs_games_reconciles_gap_and_bootstraps_deterministically(self) -> None:
        script = r'''
const fs=require("fs");const source=fs.readFileSync(process.argv[1],"utf8");
function clamp(value,lo,hi){return Math.min(hi,Math.max(lo,value));}
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function medianNumber(values){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const m=Math.floor(clean.length/2);return clean.length%2?clean[m]:(clean[m-1]+clean[m])/2;}
function numericQuantile(values,p){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const pos=clamp(Number(p),0,1)*(clean.length-1),lo=Math.floor(pos),hi=Math.ceil(pos);return lo===hi?clean[lo]:clean[lo]+(clean[hi]-clean[lo])*(pos-lo);}
function seededGenerator(seed){let value=Number(seed)>>>0;return()=>{value+=0x6D2B79F5;let mixed=value;mixed=Math.imul(mixed^mixed>>>15,mixed|1);mixed^=mixed+Math.imul(mixed^mixed>>>7,mixed|61);return((mixed^mixed>>>14)>>>0)/4294967296;};}
const start=source.indexOf("const RIVAL_WINDOWS");const end=source.indexOf("\nfunction emptyMarketEdge",start);if(start<0||end<0)throw new Error("rival functions not found");eval(source.slice(start,end));
const teams=["Oasis","Rival","Other"],gameIds=[1,2,3,4,5,6];const timeline=[];
for(const game of gameIds){for(const team of teams){const isOasis=team==="Oasis",isRival=team==="Rival";const income=isOasis?100:isRival?120:999;const cost=isOasis?10:isRival?20:1;const net=income-cost;timeline.push({team,game,issuedIncome:income,reviewerCost:cost,net,issuedDecisions:10,reviewedDecisions:10,acceptedByMarket:isOasis?8:7,reviewerAccepts:isOasis?5:6,officialScore:net});}}
const summaries=teams.map(team=>({team,net:timeline.filter(row=>row.team===team).reduce((s,row)=>s+row.net,0)}));
const market={teams,gameIds,timeline,summaries};const frames=new Map(gameIds.map(game=>[game,[
 {reviewer:"Oasis",wrongCost:5,hiddenFraud:2,rejectFairCost:4,acceptFraudCost:1},
 {reviewer:"Rival",wrongCost:3,hiddenFraud:1,rejectFairCost:2,acceptFraudCost:1},
]]));
const result=buildRivalBenchmark(market,frames,"Rival","all");const again=buildRivalBenchmark(market,frames,"Rival","all");
const unrelated=structuredClone(market);unrelated.timeline.filter(row=>row.team==="Other").forEach(row=>{row.net+=100000;row.issuedIncome+=100000;row.officialScore+=100000;});
const isolated=buildRivalBenchmark(unrelated,frames,"Rival","all");const receipt=buildRivalReceipt(result,"2026-01-01T00:00:00Z");
process.stdout.write(JSON.stringify({
 summary:result.summary,bootstrap:result.bootstrap,
 deterministic:JSON.stringify(result.bootstrap)===JSON.stringify(again.bootstrap),
 unrelatedStable:JSON.stringify(result.rows)===JSON.stringify(isolated.rows),
 last20:rivalGameIds(Array.from({length:30},(_,i)=>i+1),"last-20"),
 receipt:{status:receipt.status,games:receipt.denominator.pairedGames,boundaries:receipt.boundaries.length},
}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        summary = payload["summary"]
        self.assertEqual(summary["games"], 6)
        self.assertEqual((summary["incomeEdge"], summary["costEdge"],
                          summary["scoreGap"]), (-120, 60, -60))
        self.assertEqual(summary["scoreGap"],
                         summary["incomeEdge"] + summary["costEdge"])
        self.assertEqual(summary["officialGap"], -60)
        self.assertEqual(summary["reconciliationDelta"], 0)
        self.assertAlmostEqual(summary["topOneAbsoluteShare"], 1 / 6)
        self.assertAlmostEqual(summary["topFiveAbsoluteShare"], 5 / 6)
        self.assertTrue(payload["deterministic"])
        self.assertTrue(payload["unrelatedStable"])
        self.assertEqual(payload["bootstrap"]["p2_5"], -10)
        self.assertEqual(payload["bootstrap"]["p97_5"], -10)
        self.assertEqual(payload["bootstrap"]["probabilityOasisMeanAhead"], 0)
        self.assertEqual(payload["last20"], list(range(11, 31)))
        self.assertEqual(payload["receipt"], {
            "status": "offline-paired-rival-accounting-evidence-only",
            "games": 6, "boundaries": 6,
        })

    def test_rival_receipt_is_claim_free_and_explicitly_noncausal(self) -> None:
        body = self.javascript.split("function buildRivalReceipt", 1)[1].split(
            "function emptyMarketEdge", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('"every row compares both teams on the same played game;', body)
        self.assertIn('"paired bootstrap resamples whole matched games', body)
        self.assertIn("attribution is payoff accounting, not model causality", body)
        self.assertIn('"no process, charge, limit, rule, model, or submission is modified"', body)

    def test_belief_calibration_uses_lognormal_intervals_and_only_proven_bound_misses(self) -> None:
        script = r'''
const fs=require("fs");const source=fs.readFileSync(process.argv[1],"utf8");
function medianNumber(values){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const m=Math.floor(clean.length/2);return clean.length%2?clean[m]:(clean[m-1]+clean[m])/2;}
const start=source.indexOf("const BELIEF_INTERVAL_Z");const end=source.indexOf("\nconst DRIFT_METRICS",start);if(start<0||end<0)throw new Error("belief calibration functions not found");eval(source.slice(start,end));
const items=[
 {game:1,item:1,median:100,sigma:.1,tLo:90,tHi:110,source:"A"},
 {game:1,item:2,median:50,sigma:.1,tLo:100,tHi:null,source:"A"},
 {game:2,item:1,median:200,sigma:.1,tLo:100,tHi:150,source:"A"},
 {game:2,item:2,median:100,sigma:.1,tLo:80,tHi:null,source:"B"},
 {game:3,item:1,median:null,sigma:null,tLo:100,tHi:120,source:"A"},
];
const all=buildBeliefCalibration(items,{coverage:.9,window:"all",source:"all",bucket:"all"});
const onlyA=buildBeliefCalibration(items,{coverage:.9,window:"all",source:"A",bucket:"all"});
const receipt=buildCalibrationReceipt(all,"2026-01-01T00:00:00Z");
process.stdout.write(JSON.stringify({summary:all.summary,states:all.rows.map(r=>r.intervalState),curve:all.curve.map(r=>[r.coverage,r.forcedMisses,r.guaranteed]),onlyA:onlyA.summary,floorOnlyInvalid:all.rows.filter(r=>r.tHi===null&&["forced-high","guaranteed"].includes(r.intervalState)).length,receipt:{status:receipt.status,denominator:receipt.denominator,boundaries:receipt.boundaries.length}}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["total"], 4)
        self.assertEqual((payload["summary"]["forcedLow"],
                          payload["summary"]["forcedHigh"]), (1, 1))
        self.assertEqual(payload["summary"]["guaranteed"], 1)
        self.assertEqual(payload["summary"]["twoSided"], 2)
        self.assertEqual(payload["states"], ["guaranteed", "forced-low",
                                               "forced-high", "compatible"])
        self.assertEqual(payload["onlyA"]["total"], 3)
        self.assertEqual([row[0] for row in payload["curve"]], [.5, .8, .9, .95, .99])
        self.assertEqual(payload["curve"][-1][1], 2)
        self.assertEqual([row[1] for row in payload["curve"]],
                         sorted([row[1] for row in payload["curve"]], reverse=True))
        self.assertEqual([row[2] for row in payload["curve"]],
                         sorted([row[2] for row in payload["curve"]]))
        self.assertEqual(payload["floorOnlyInvalid"], 0)
        self.assertEqual(payload["receipt"], {
            "status": "offline-bounded-belief-calibration-evidence-only",
            "denominator": {
                "beliefsWithPositiveMedianSigmaAndSanctionedFloor": 4,
                "representedBeliefGames": 2,
                "twoSidedBrackets": 2, "floorOnlyBrackets": 2,
            },
            "boundaries": 6,
        })

    def test_calibration_receipt_is_claim_free_and_never_turns_bounds_into_labels(self) -> None:
        body = self.javascript.split("function buildCalibrationReceipt", 1)[1].split(
            "const DRIFT_METRICS", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn("threshold brackets are bounds", body)
        self.assertIn("overlap is compatible coverage, not proof", body)
        self.assertIn("not a temporal holdout or causal source comparison", body)
        self.assertIn('"no process, belief, charge, limit, rule, model, or submission is modified"', body)

    def test_regret_cartography_reconciles_items_games_taxonomy_and_hidden_exposure(self) -> None:
        script = r'''
const fs=require("fs");const source=fs.readFileSync(process.argv[1],"utf8");
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function medianNumber(values){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const m=Math.floor(clean.length/2);return clean.length%2?clean[m]:(clean[m-1]+clean[m])/2;}
function calibrationValueBucket(floor){const value=Number(floor);if(!Number.isFinite(value))return "unlabelled";if(value<50)return "0–50";if(value<400)return "50–400";if(value<1200)return "400–1200";return "1200+";}
const start=source.indexOf("const REGRET_WINDOWS");const end=source.indexOf("\nconst DRIFT_METRICS",start);if(start<0||end<0)throw new Error("regret cartography functions not found");eval(source.slice(start,end));
const items=[
 {game:1,item:1,a:80,b:100,tLo:90,tHi:120,status:"under",source:"A",foregoneLowerBound:100},
 {game:1,item:2,a:180,b:150,tLo:100,tHi:150,status:"over",source:"A",foregoneLowerBound:0},
 {game:2,item:1,a:100,b:100,tLo:90,tHi:110,status:"not-proven-wrong",source:"B",foregoneLowerBound:0},
 {game:2,item:2,a:50,b:50,tLo:null,tHi:null,status:"unlabelled",source:null,foregoneLowerBound:0},
];
const cells=[
 {game:1,item:1,outcome:"rejectFair",actualCost:60,provenClass:"fair",hiddenFraudEligible:false},
 {game:1,item:1,outcome:"acceptFair",actualCost:10,provenClass:"fair",hiddenFraudEligible:false},
 {game:1,item:2,outcome:"acceptFraud",actualCost:40,provenClass:"fraud",hiddenFraudEligible:false},
 {game:1,item:2,outcome:"rejectFraud",actualCost:999,provenClass:"fraud",hiddenFraudEligible:true},
 {game:2,item:1,outcome:"rejectFair",actualCost:30,provenClass:"fair",hiddenFraudEligible:false},
 {game:2,item:1,outcome:"acceptFraud",actualCost:20,provenClass:"fraud",hiddenFraudEligible:false},
 {game:99,item:1,outcome:"rejectFair",actualCost:999,provenClass:"fair",hiddenFraudEligible:false},
];
const result=buildRegretCartography(items,cells,[1,2],{window:"all",source:"all",bucket:"all",focus:"combined"});
const onlyA=buildRegretCartography(items,cells,[1,2],{window:"all",source:"A",bucket:"all",focus:"combined"});
const first=buildRegretCartography(items,cells,[1,2],{window:"first-half",source:"all",bucket:"all",focus:"combined"});
const second=buildRegretCartography(items,cells,[1,2],{window:"second-half",source:"all",bucket:"all",focus:"combined"});
const gameSum=result.games.reduce((acc,row)=>({issuer:acc.issuer+row.issuerForegoneLowerBound,reviewer:acc.reviewer+row.wrongReviewerCost,combined:acc.combined+row.combinedEvidenceLoad,items:acc.items+row.items}),{issuer:0,reviewer:0,combined:0,items:0});
const taxonomySum=result.taxonomy.reduce((acc,row)=>({combined:acc.combined+row.combinedEvidenceLoad,items:acc.items+row.items,hidden:acc.hidden+row.hiddenFraudGroups}),{combined:0,items:0,hidden:0});
const bucketSum=result.buckets.reduce((acc,row)=>({combined:acc.combined+row.combinedEvidenceLoad,items:acc.items+row.items,hidden:acc.hidden+row.hiddenFraudGroups}),{combined:0,items:0,hidden:0});
const routeSum=result.sourceBuckets.reduce((acc,row)=>({combined:acc.combined+row.combinedEvidenceLoad,items:acc.items+row.items,hidden:acc.hidden+row.hiddenFraudGroups}),{combined:0,items:0,hidden:0});
const routeA=result.sourceBuckets.find(row=>row.source==="A"&&row.bucket==="50–400");
const recurrenceA=regretRecurrenceEvidence(result.rows.filter(row=>row.source==="A"&&row.bucket==="50–400"),"combined");
const rr=(game,value)=>({game,combinedEvidenceLoad:value,issuerForegoneLowerBound:value,wrongReviewerCost:0,hiddenFraudGroups:0});
const recurrenceStates=[
 regretRecurrenceEvidence([rr(1,0),rr(1,0),rr(2,0),rr(2,0),rr(3,0),rr(3,0)],"combined").recurrence,
 regretRecurrenceEvidence([rr(1,10),rr(1,5),rr(2,3),rr(2,2)],"combined").recurrence,
 regretRecurrenceEvidence([rr(1,80),rr(1,10),rr(2,5),rr(2,2),rr(3,2),rr(3,1)],"combined").recurrence,
 regretRecurrenceEvidence([rr(1,5),rr(1,5),rr(2,5),rr(2,5),rr(3,0),rr(3,0)],"combined").recurrence,
 regretRecurrenceEvidence([rr(1,5),rr(1,5),rr(2,5),rr(2,5),rr(3,5),rr(3,5)],"combined").recurrence,
];
const receipt=buildRegretReceipt(result,"2026-01-01T00:00:00Z");
process.stdout.write(JSON.stringify({totals:result.totals,directions:result.rows.map(row=>row.reviewerDirection),gameSum,taxonomySum,bucketSum,routeSum,routeA:{items:routeA.items,games:routeA.representedGames,perItem:routeA.evidenceLoadPerItem,topGameShare:routeA.topGameShare,recurrence:recurrenceA.recurrence},recurrenceStates,onlyA:onlyA.totals,windowPartition:{items:first.totals.items+second.totals.items,combined:first.totals.combinedEvidenceLoad+second.totals.combinedEvidenceLoad},receipt:{status:receipt.status,denominator:receipt.denominator,boundaries:receipt.boundaries.length}}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["totals"]["items"], 4)
        self.assertEqual(payload["totals"]["issuerForegoneLowerBound"], 100)
        self.assertEqual(payload["totals"]["rejectFairCost"], 90)
        self.assertEqual(payload["totals"]["acceptFraudCost"], 60)
        self.assertEqual(payload["totals"]["wrongReviewerCost"], 150)
        self.assertEqual(payload["totals"]["combinedEvidenceLoad"], 250)
        self.assertEqual(payload["totals"]["hiddenFraudGroups"], 1)
        self.assertEqual(payload["totals"]["overlapItems"], 1)
        self.assertEqual(payload["directions"], ["reject-fair", "accept-fraud", "mixed", "none"])
        self.assertEqual(payload["gameSum"], {"issuer": 100, "reviewer": 150, "combined": 250, "items": 4})
        self.assertEqual(payload["taxonomySum"], {"combined": 250, "items": 4, "hidden": 1})
        self.assertEqual(payload["bucketSum"], {"combined": 250, "items": 4, "hidden": 1})
        self.assertEqual(payload["routeSum"], {"combined": 250, "items": 4, "hidden": 1})
        self.assertEqual(payload["routeA"], {"items": 2, "games": 1, "perItem": 100, "topGameShare": 1, "recurrence": "sparse denominator"})
        self.assertEqual(payload["recurrenceStates"], ["no positive focus", "sparse denominator", "game-concentrated", "limited recurrence", "repeated evidence"])
        self.assertEqual(payload["onlyA"]["items"], 2)
        self.assertEqual(payload["onlyA"]["combinedEvidenceLoad"], 200)
        self.assertEqual(payload["windowPartition"], {"items": 4, "combined": 250})
        self.assertEqual(payload["receipt"], {
            "status": "offline-two-role-bounded-observed-evidence-only",
            "denominator": {"items": 4, "reviewerCells": 6, "provenReviewerCells": 6},
            "boundaries": 7,
        })

    def test_regret_receipt_is_claim_free_noncausal_and_keeps_hidden_fraud_unpriced(self) -> None:
        body = self.javascript.split("function buildRegretReceipt", 1)[1].split(
            "const DRIFT_METRICS", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn("issuer component is a proven lower bound", body)
        self.assertIn("rejected fraudulent charge sizes remain unpriced", body)
        self.assertIn("not causal avoidable loss or a tournament counterfactual", body)
        self.assertIn('"no process, belief, charge, limit, rule, model, or submission is modified"', body)

    def test_item_peer_forensics_separates_strictly_prior_from_hindsight(self) -> None:
        script = r'''
const fs=require("fs");const source=fs.readFileSync(process.argv[1],"utf8");
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function medianNumber(values){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const m=Math.floor(clean.length/2);return clean.length%2?clean[m]:(clean[m-1]+clean[m])/2;}
const start=source.indexOf("const PEER_COHORTS");const end=source.indexOf("\nconst REGRET_WINDOWS",start);if(start<0||end<0)throw new Error("peer forensic functions not found");eval(source.slice(start,end));
const items=[
 {game:1,item:1,source:"S",tLo:500,tHi:700,a:250,b:420,median:300,sigma:.4,foregoneLowerBound:400},
 {game:2,item:1,source:"S",tLo:600,tHi:800,a:600,b:620,median:590,sigma:.3,foregoneLowerBound:0},
 {game:3,item:1,source:"S",tLo:400,tHi:550,a:300,b:350,median:320,sigma:.25,foregoneLowerBound:1600},
 {game:3,item:2,source:"S",tLo:500,tHi:null,a:600,b:520,median:540,sigma:.2,foregoneLowerBound:0},
 {game:4,item:1,source:"S",tLo:800,tHi:900,a:1600,b:1200,median:1000,sigma:.5,foregoneLowerBound:0},
 {game:2,item:2,source:"S",tLo:20,tHi:30,a:20,b:25,median:22,sigma:.2,foregoneLowerBound:0},
 {game:2,item:3,source:"T",tLo:500,tHi:700,a:500,b:500,median:500,sigma:.2,foregoneLowerBound:0},
];
const regrets=[
 {game:1,item:1,issuerForegoneLowerBound:400,wrongReviewerCost:0,combinedEvidenceLoad:400,hiddenFraudGroups:0},
 {game:2,item:1,issuerForegoneLowerBound:0,wrongReviewerCost:200,combinedEvidenceLoad:200,hiddenFraudGroups:1},
 {game:3,item:1,issuerForegoneLowerBound:1600,wrongReviewerCost:0,combinedEvidenceLoad:1600,hiddenFraudGroups:0},
 {game:3,item:2,issuerForegoneLowerBound:0,wrongReviewerCost:100,combinedEvidenceLoad:100,hiddenFraudGroups:0},
 {game:4,item:1,issuerForegoneLowerBound:0,wrongReviewerCost:10000,combinedEvidenceLoad:10000,hiddenFraudGroups:2},
];
const base=buildPeerForensics(items,regrets,3,1,{cohort:"source-bucket",metric:"combined"});
const sourceOnly=buildPeerForensics(items,regrets,3,1,{cohort:"source-only",metric:"combined"});
const degraded=buildPeerForensics(items,[],3,1,{cohort:"source-bucket",metric:"issuer",reviewerAvailable:false});
const changed=JSON.parse(JSON.stringify(regrets));changed.find(row=>row.game===4).combinedEvidenceLoad=1e9;changed.find(row=>row.game===4).wrongReviewerCost=1e9;
const changedItems=JSON.parse(JSON.stringify(items));Object.assign(changedItems.find(row=>row.game===4),{a:8000,b:6000,median:5000,sigma:2});
const mutated=buildPeerForensics(changedItems,changed,3,1,{cohort:"source-bucket",metric:"combined"});
const metric=base.metrics.find(row=>row.key==="combined");const changedMetric=mutated.metrics.find(row=>row.key==="combined");
const receipt=buildPeerReceipt(base,"2026-01-01T00:00:00Z");
process.stdout.write(JSON.stringify({counts:base.denominator,sourceOnly:sourceOnly.denominator.allPeers,degraded:{reviewerAvailable:degraded.reviewerEvidenceAvailable,issuer:degraded.metrics.find(row=>row.key==="issuer").selectedValue,reviewer:degraded.metrics.find(row=>row.key==="reviewer").selectedValue,reviewerObs:degraded.metrics.find(row=>row.key==="reviewer").prior.observations},percentiles:[metric.prior.percentile,metric.all.percentile],priorStable:JSON.stringify(metric.prior)===JSON.stringify(changedMetric.prior),allChanged:JSON.stringify(metric.all)!==JSON.stringify(changedMetric.all),priorAnalogueStable:JSON.stringify(base.priorAnalogues)===JSON.stringify(mutated.priorAnalogues),allAnalogueChanged:JSON.stringify(base.analogues)!==JSON.stringify(mutated.analogues),analogues:base.analogues.map(row=>[row.game,row.item,row.temporalSide,row.dimensions]),receipt:{status:receipt.status,denominator:receipt.denominator,boundaries:receipt.boundaries.length}}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["counts"], {"allPeers": 4, "priorPeers": 2, "sameGamePeers": 1, "futurePeers": 1})
        self.assertEqual(payload["sourceOnly"], 5)
        self.assertEqual(payload["degraded"], {"reviewerAvailable": False, "issuer": 1600, "reviewer": None, "reviewerObs": 0})
        self.assertEqual(payload["percentiles"], [1, .75])
        self.assertTrue(payload["priorStable"])
        self.assertTrue(payload["allChanged"])
        self.assertTrue(payload["priorAnalogueStable"])
        self.assertTrue(payload["allAnalogueChanged"])
        self.assertTrue(all(row[:2] != [3, 1] and row[3] >= 2 for row in payload["analogues"]))
        self.assertEqual(payload["receipt"], {
            "status": "offline-item-peer-forensics-evidence-only",
            "denominator": {"allPeers": 4, "priorPeers": 2, "sameGamePeers": 1, "futurePeers": 1},
            "boundaries": 7,
        })

    def test_peer_receipt_is_claim_free_and_never_calls_numeric_peers_semantic_matches(self) -> None:
        body = self.javascript.split("function buildPeerReceipt", 1)[1].split(
            "const REGRET_WINDOWS", 1
        )[0]
        for forbidden in ("description", "policy_text", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn("same source and sanctioned-floor regime is a retrospective numeric cohort", body)
        self.assertIn("strictly prior peers use only lower game identifiers", body)
        self.assertIn("numeric analogues are not semantic, causal, or substitutable items", body)
        self.assertIn("future and same-game peers are hindsight context only", body)
        self.assertIn('"no process, belief, charge, limit, rule, model, or submission is modified"', body)

    def test_finish_simulator_is_seeded_joint_vector_bootstrap_with_temporal_audit(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
function clamp(value,lo,hi){return Math.min(hi,Math.max(lo,value));}
function safeNumber(value,fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function medianNumber(values){const clean=values.map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!clean.length)return null;const m=Math.floor(clean.length/2);return clean.length%2?clean[m]:(clean[m-1]+clean[m])/2;}
const start = source.indexOf("function seededGenerator");
const end = source.indexOf("\nfunction raceAt", start);
if (start < 0 || end < 0) throw new Error("finish simulation functions not found");
eval(source.slice(start, end));
const names = ["Oasis", "Alpha", "Beta"];
const rounds = [
  [-10,-5,5,10,-8,12,-3,9],
  [20,-10,8,-4,6,-2,11,-5],
  [5,7,-9,4,-3,8,-6,2],
];
const series = names.map((team,index) => {
  let total=0;
  return {team,rounds:rounds[index],scores:rounds[index].map(value => total += value),total:rounds[index].reduce((a,b)=>a+b,0)};
});
const race = {gameIds:[1,2,3,4,5,6,7,8],series};
const options = {window:"last-5",runs:300,seed:417,edge:0};
const first = simulateTournamentFinish(race,options);
const second = simulateTournamentFinish(race,options);
const otherSeed = simulateTournamentFinish(race,{...options,seed:418});
const hugeEdge = simulateTournamentFinish(race,{...options,edge:100000});
const temporal = walkForwardTournament(race,{window:"all"});
const changed = JSON.parse(JSON.stringify(race));
changed.series.forEach((row,index) => {
  row.rounds[7] += 100000 * (index + 1);
  row.scores[7] = row.scores[6] + row.rounds[7];
});
const temporalChanged = walkForwardTournament(changed,{window:"all"});
process.stdout.write(JSON.stringify({
  deterministic: JSON.stringify(first) === JSON.stringify(second),
  seedChangesDraws: JSON.stringify(first.sampledVectorCounts) !== JSON.stringify(otherSeed.sampledVectorCounts),
  pathCount: first.distribution.reduce((sum,row)=>sum+row.paths,0),
  sampleCount: first.sampledVectorCounts.reduce((sum,value)=>sum+value,0),
  expectedSamples: first.runs * first.remaining,
  hugeEdgeWin: hugeEdge.winProbability,
  coneGames:[first.cone[0].game,first.cone.at(-1).game],
  firstTemporalStable: JSON.stringify(temporal.rows[0]) === JSON.stringify(temporalChanged.rows[0]),
  temporalPredictions: temporal.predictions,
  temporalUses: temporal.historicalVectorUses,
}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["deterministic"])
        self.assertTrue(payload["seedChangesDraws"])
        self.assertEqual(payload["pathCount"], 300)
        self.assertEqual(payload["sampleCount"], payload["expectedSamples"])
        self.assertEqual(payload["hugeEdgeWin"], 1)
        self.assertEqual(payload["coneGames"], [8, 100])
        self.assertTrue(payload["firstTemporalStable"])
        self.assertEqual(payload["temporalPredictions"], 2)
        self.assertGreater(payload["temporalUses"], 0)

    def test_finish_receipt_is_claim_free_reproducible_and_explicitly_non_predictive(self) -> None:
        body = self.javascript.split("async function copyForecastReceipt", 1)[1].split(
            "function robustnessSpec", 1
        )[0]
        for forbidden in ("description", "policy", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('status: "offline-descriptive-scenario-only"', body)
        self.assertIn("completeHistoricalRoundVectors", body)
        self.assertIn("seed: result.seed", body)
        self.assertIn('"resampling stress test, not a future-performance claim"', body)
        self.assertIn('"Oasis edge is a hypothetical score adjustment and is never submitted"', body)
        self.assertIn("catch (error)", body)

    def test_portfolio_evaluator_dedupes_routing_from_hindsight_scoring(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("function evaluatePortfolio");
const end = source.indexOf("\n}\n\nfunction portfolioData", start) + 2;
if (start < 0 || end < 2) throw new Error("evaluatePortfolio function not found");
eval(source.slice(start, end));
const temporalStart = source.indexOf("function portfolioTemporalRows");
const temporalEnd = source.indexOf("\n}\n\nfunction renderPortfolioTemporal", temporalStart) + 2;
if (temporalStart < 0 || temporalEnd < 2) throw new Error("portfolioTemporalRows function not found");
eval(source.slice(temporalStart, temporalEnd));
const primary = [
  {id:"a",game:1,item:1,aDelta:40,bDelta:50,source:"s1",candidateStable:true,bestPossible:1600,beforeProvenIncome:800,afterProvenIncome:1440,beforeState:"at-or-under-floor",afterState:"at-or-under-floor",hiddenCharges:9},
  {id:"a",game:1,item:2,aDelta:-50,bDelta:-10,source:"s1",candidateStable:true,bestPossible:1600,beforeProvenIncome:0,afterProvenIncome:1600,beforeState:"above-ceiling",afterState:"at-or-under-floor",hiddenCharges:3},
  {id:"a",game:1,item:3,aDelta:25,bDelta:0,source:"s2",candidateStable:false,bestPossible:1600,beforeProvenIncome:1600,afterProvenIncome:null,beforeState:"at-or-under-floor",afterState:"unprovable",hiddenCharges:4},
  {id:"a",game:1,item:4,aDelta:0,bDelta:0,source:"s1",candidateStable:true,bestPossible:null,beforeProvenIncome:null,afterProvenIncome:null,beforeState:"unlabelled",afterState:"unlabelled",hiddenCharges:0},
];
const peers = [
  {id:"b",game:1,item:1,aDelta:-5},
  {id:"b",game:1,item:2,aDelta:-5},
  {id:"b",game:1,item:3,aDelta:-5},
];
const result = evaluatePortfolio(primary, [...primary, ...peers], {gate:"no-opposition",source:"all",direction:"any"});
const consensus = evaluatePortfolio(primary, [...primary, ...peers], {gate:"consensus",source:"all",direction:"any"});
const noBRaise = evaluatePortfolio(primary, [...primary, ...peers], {gate:"no-b-raise",source:"all",direction:"any"});
process.stdout.write(JSON.stringify({result, consensusApplied:consensus.applied, noBRaise, temporal:portfolioTemporalRows(result)}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        routed = payload["result"]
        self.assertEqual((routed["before"]["items"], routed["before"]["bestPossible"]),
                         (3, 4800))
        self.assertEqual((routed["before"]["score"], routed["full"]["score"]),
                         (0.5, 3040 / 4800))
        self.assertEqual((routed["applied"], routed["fallback"], routed["safetyBlocked"]),
                         (2, 2, 2))
        self.assertEqual(routed["routed"]["score"], 4000 / 4800)
        self.assertEqual(payload["consensusApplied"], 1)
        self.assertEqual((payload["noBRaise"]["bRaisesApplied"],
                          payload["noBRaise"]["hiddenGroupsOnAppliedBRaises"]), (0, 0))
        self.assertEqual(len(payload["temporal"]), 1)
        self.assertEqual((payload["temporal"][0]["items"],
                          payload["temporal"][0]["applied"],
                          payload["temporal"][0]["delta"],
                          payload["temporal"][0]["cumulativeDelta"]), (3, 1, 1600, 1600))

    def test_forensics_copy_preserves_timing_and_payoff_boundaries(self) -> None:
        self.assertIn("Elapsed values measure distance between logged boundaries", self.html)
        self.assertIn("decision totals, not payoff", self.javascript)
        self.assertIn("Rejected fraudulent charges contribute €0 observed cost", self.html)
        self.assertIn("latestRecordedGame", self.javascript)

    def test_portfolio_handoff_receipt_is_claim_free_and_caveated(self) -> None:
        body = self.javascript.split("async function copyPortfolioReceipt", 1)[1].split(
            "function populateRuleControl", 1
        )[0]
        for forbidden in ("description", "policy", "damage", "photo", "fair_charges"):
            self.assertNotIn(forbidden, body)
        self.assertIn('status: "offline-retrospective-evidence-only"', body)
        self.assertIn('"not a temporal train/test backtest"', body)
        self.assertIn("hiddenOpposingChargeGroupsUnpriced", body)
        self.assertIn('"expensive-item routing precision at or above 0.90 not established"', body)
        self.assertIn("catch (error)", body)

    def test_portfolio_firewall_never_turns_missing_evidence_into_a_pass(self) -> None:
        body = self.javascript.split("function renderPortfolioReadiness", 1)[1].split(
            "function selectPortfolioRule", 1
        )[0]
        self.assertIn('["unresolved", "Strict temporal evaluation"', body)
        self.assertIn('["unresolved", "Expensive-item precision"', body)
        self.assertIn('["unresolved", "Deadline budget"', body)
        self.assertIn('["unresolved", "Provider failure fallback"', body)
        self.assertIn('textContent = `CLOSED ·', body)

    def test_payoff_instrument_executes_all_four_exact_branches(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("function evaluatePayoff");
const end = source.indexOf("\n}\n\nfunction payoffState", start) + 2;
if (start < 0 || end < 2) throw new Error("evaluatePayoff function not found");
eval(source.slice(start, end));
const rows = [
  evaluatePayoff(800, 700, 900, 4000),
  evaluatePayoff(800, 700, 500, 4000),
  evaluatePayoff(600, 1200, 1400, 2400),
  evaluatePayoff(600, 1200, 800, 2400),
  evaluatePayoff(800, 4000, 5000, 100),
];
process.stdout.write(JSON.stringify(rows));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        rows = json.loads(result.stdout)
        self.assertEqual(
            [(row["fair"], row["accepted"], row["cost"], row["regret"])
             for row in rows[:4]],
            [(True, True, 700, 0), (True, False, 1050, 350),
             (False, True, 1200, 1200), (False, False, 0, 0)],
        )
        self.assertEqual((rows[4]["c"], rows[4]["cost"]), (3200, 3200))

    def test_income_cost_frontier_uses_strict_two_axis_dominance(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const safeStart = source.indexOf("function safeNumber");
const safeEnd = source.indexOf("\n", safeStart);
const start = source.indexOf("function incomeCostFrontier");
const end = source.indexOf("\n}\n\nfunction renderRoundMap", start) + 2;
if (safeStart < 0 || start < 0 || end < 2) throw new Error("frontier functions missing");
eval(source.slice(safeStart, safeEnd));
eval(source.slice(start, end));
const rows = [
  {game: "a", income: 100, cost: 100},
  {game: "b", income: 200, cost: 90},
  {game: "c", income: 180, cost: 80},
  {game: "d", income: 200, cost: 90},
  {game: "e", income: 250, cost: 200},
  {game: "f", income: 50, cost: 300},
];
process.stdout.write(JSON.stringify(incomeCostFrontier(rows).map(row => row.game).sort()));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(json.loads(result.stdout), ["b", "c", "d", "e"])

    def test_replay_frame_reconstructs_only_events_visible_at_the_cursor(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("function deriveReplayFrame");
const end = source.indexOf("\n}\n\nfunction replayEventDetail", start) + 2;
if (start < 0 || end < 2) throw new Error("deriveReplayFrame function not found");
eval(source.slice(start, end));
const events = [
  {seq:1,type:"item.belief",item:1,median:100},
  {seq:2,type:"rule.fired",item:1,shadow:true},
  {seq:3,type:"item.decided",item:1,a:90,b:100},
  {seq:4,type:"item.belief",item:2,median:200},
  {seq:5,type:"submission.sent",item:null},
];
const frame = deriveReplayFrame(events, 2, [1,2]);
const final = deriveReplayFrame(events, 99, [1,2]);
process.stdout.write(JSON.stringify({frame,final}));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        payload = json.loads(result.stdout)
        frame = payload["frame"]
        self.assertEqual((frame["index"], frame["current"]["seq"],
                          frame["believedItems"], frame["decidedItems"],
                          frame["ruleEvents"], frame["shadowEvents"]),
                         (2, 3, 1, 1, 1, 1))
        item_two = next(row for row in frame["items"] if row["item"] == 2)
        self.assertIsNone(item_two["belief"])
        self.assertEqual((payload["final"]["index"], payload["final"]["believedItems"]),
                         (4, 2))

    def test_evidence_atlas_lenses_keep_their_eligible_denominators(self) -> None:
        script = r'''
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
function safeNumber(value, fallback=0){return Number.isFinite(Number(value))?Number(value):fallback;}
function clamp(value,lo,hi){return Math.min(hi,Math.max(lo,value));}
function formatNumber(value){return String(value);}
function formatCurrency(value){return String(value);}
const start = source.indexOf("function evidenceLens");
const end = source.indexOf("\n}\n\nfunction renderEvidenceAtlas", start) + 2;
if (start < 0 || end < 2) throw new Error("evidence atlas functions not found");
eval(source.slice(start, end));
const rows = [
  {field:{exact:11,lowerBound:0,hidden:5,unresolved:0},tLo:100,tHi:null,median:100,source:"s",a:50,b:60,ruleCount:0,shadowCount:0,replayCount:0,documentsAvailable:false},
  {field:{exact:16,lowerBound:0,hidden:0,unresolved:0},tLo:null,tHi:null,median:null,source:null,a:null,b:null,ruleCount:0,shadowCount:0,replayCount:0,documentsAvailable:true},
  {field:{exact:16,lowerBound:0,hidden:0,unresolved:0},tLo:100,tHi:120,median:100,source:"s",a:100,b:100,ruleCount:2,shadowCount:1,replayCount:3,documentsAvailable:true},
];
const modes = ["hidden-field","open-ceiling","missing-belief","missing-decision","missing-rule","missing-replay","missing-docs"];
const out = Object.fromEntries(modes.map(mode => {
  const values=evidenceAtlasRows(mode,rows);
  return [mode,{eligible:values.filter(row=>row.evidenceEligible).length,issues:values.filter(row=>row.evidenceEligible&&row.evidenceIssue).length}];
}));
process.stdout.write(JSON.stringify(out));
'''
        result = subprocess.run(
            ["node", "-e", script, str(VIZ / "static" / "app.js")],
            check=True, capture_output=True, text=True, timeout=5,
        )
        rows = json.loads(result.stdout)
        self.assertEqual(rows["hidden-field"], {"eligible": 3, "issues": 1})
        self.assertEqual(rows["open-ceiling"], {"eligible": 2, "issues": 1})
        self.assertEqual(rows["missing-rule"], {"eligible": 2, "issues": 1})
        self.assertEqual(rows["missing-replay"], {"eligible": 2, "issues": 1})
        for mode in ("missing-belief", "missing-decision", "missing-docs"):
            self.assertEqual(rows[mode], {"eligible": 3, "issues": 1})


if __name__ == "__main__":
    unittest.main()

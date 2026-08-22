"use client";
import { useEffect, useRef, useState } from "react";

// The Python dashboard process owns every upstream call. This UI talks only to
// it, never to the leaderboard directly -- that is what keeps "one fetch per
// 90s, shared by every open tab" true no matter how many browsers are running.
export const API = process.env.NEXT_PUBLIC_C2F_API ?? "http://127.0.0.1:8080";

export type Ev = { ts: number; round: number; case: string; seq: number; type: string; payload: any };
export type Item = {
  idx: number; desc?: string; qty?: number; unit?: string;
  median?: number; sigma?: number; source?: string;
  a?: number; b?: number; covered?: boolean; trace?: any[];
};
export type Sub = {
  tier: number; case: string; round: number; n: number; a: number; b: number;
  builtAt: number | null; sentAt?: number | null; post?: number; status?: number;
  ok?: boolean; verified?: boolean | null;
};
export type Mod = { name: string; stage?: string; state?: string; fired: number; shadow?: boolean };
export type Mark = { label: string; detail: string; ms: number | null };

export type RoundState = {
  round: number; case: string; start: number | null;
  marks: Mark[]; items: Map<number, Item>; files: string[];
  closedMs: number | null;
};

export type Live = {
  seq: number; connected: boolean; lastEventAt: number;
  current: RoundState | null;
  rounds: RoundState[];          // newest first, capped
  subs: Sub[];
  mods: Map<string, Mod>;
  alerts: { level: string; msg: string; round: number; ts: number }[];
  log: Ev[];
};

const blankRound = (round: number, cse: string, ts: number): RoundState => ({
  round, case: cse, start: ts, marks: [], items: new Map(), files: [], closedMs: null,
});

function reduce(s: Live, ev: Ev): Live {
  const p = ev.payload ?? {};
  s.log.push(ev); if (s.log.length > 400) s.log.shift();
  s.lastEventAt = Date.now();

  if (ev.type === "round.scheduled") {
    if (s.current) s.rounds = [s.current, ...s.rounds].slice(0, 40);
    s.current = blankRound(ev.round, ev.case, ev.ts);
    for (const r of p.rules ?? []) {
      const m = s.mods.get(r.name);
      s.mods.set(r.name, { name: r.name, stage: r.stage, state: r.state, fired: m?.fired ?? 0 });
    }
  }
  const R = s.current;
  const at = R?.start ? (ev.ts - R.start) * 1000 : null;
  const mark = (label: string, detail: string, ms?: number | null) =>
    R?.marks.push({ label, detail, ms: ms ?? at });

  switch (ev.type) {
    case "round.scheduled": mark("round start", `case ${ev.case} · rules frozen`, 0); break;
    case "key.requested": mark("key requested", "polling, jittered"); break;
    case "key.received": mark("key received", `case ${p.case}`, p.ms); break;
    case "case.decrypted":
      if (R) R.files = p.files ?? [];
      mark("decrypted", `${(p.files ?? []).length} files`, p.ms); break;
    case "case.parsed":
      mark("parsed", `${p.n_items} line items`);
      for (const it of p.items ?? [])
        R?.items.set(it.idx, { ...(R.items.get(it.idx) ?? {}), ...it });
      break;
    case "prior.prefetched": mark("LLM prior fetched", `${p.n} items`, p.ms); break;
    case "item.belief": {
      const it = R?.items.get(p.idx) ?? { idx: p.idx };
      R?.items.set(p.idx, { ...it, median: p.median, sigma: p.sigma, source: p.source });
      break;
    }
    case "rule.fired": {
      const name = p.rule ?? "?";
      const m = s.mods.get(name);
      s.mods.set(name, {
        name, stage: p.stage ?? m?.stage, fired: (m?.fired ?? 0) + 1,
        state: p.shadow ? "shadow" : (m?.state ?? "active"), shadow: !!p.shadow,
      });
      break;
    }
    case "item.decided": {
      const it = R?.items.get(p.idx) ?? { idx: p.idx };
      R?.items.set(p.idx, { ...it, a: p.a, b: p.b, covered: p.covered, trace: p.trace ?? [] });
      break;
    }
    case "submission.built":
      s.subs = [{
        tier: p.tier, case: ev.case, round: ev.round, n: p.n_items,
        a: p.total_a, b: p.total_b, builtAt: at,
      }, ...s.subs].slice(0, 200);
      mark(`submission #${p.tier} built`, `charge ${p.total_a}`); break;
    case "submission.sent": {
      const t = s.subs.find(x => x.tier === p.tier && x.case === ev.case);
      if (t) { t.ok = p.ok; t.post = p.ms; t.status = p.status; t.sentAt = at; }
      mark(`submission #${p.tier} sent`, `HTTP ${p.status} in ${p.ms} ms`); break;
    }
    case "submission.verified": {
      const t = s.subs.find(x => x.tier === p.tier && x.case === ev.case);
      if (t) t.verified = p.ok;
      mark(`submission #${p.tier} verified`,
        p.ok === null ? "read-back unsupported" : p.ok ? "server echo matches" : "ECHO MISMATCH");
      break;
    }
    case "round.closed":
      mark("round closed", `${p.elapsed_s}s total`);
      if (R) R.closedMs = (p.elapsed_s ?? 0) * 1000;
      break;
    case "alert":
      s.alerts = [{ level: p.level, msg: p.msg, round: ev.round, ts: ev.ts }, ...s.alerts].slice(0, 50);
      break;
  }
  return s;
}

const EMPTY: Live = {
  seq: 0, connected: false, lastEventAt: 0, current: null, rounds: [],
  subs: [], mods: new Map(), alerts: [], log: [],
};

export function useLive() {
  const ref = useRef<Live>({ ...EMPTY, mods: new Map() });
  const [, tick] = useState(0);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/events?since=${ref.current.seq}`, { cache: "no-store" });
        const d = await r.json();
        for (const ev of d.events ?? []) reduce(ref.current, ev);
        ref.current.seq = d.seq ?? ref.current.seq;
        ref.current.connected = true;
      } catch {
        ref.current.connected = false;   // the UI must never be what breaks
      }
      if (alive) tick(t => t + 1);
    };
    poll();
    const h = setInterval(poll, 1000);
    return () => { alive = false; clearInterval(h); };
  }, []);

  return ref.current;
}

export type Board = {
  standings: any[]; games: any[]; team: string | null;
  performance: any; matchup: any[];
  skew_s: number | null; server_now?: string; fetched_at: number | null;
  error: string | null; upstream_calls: number;
};

export function useBoard() {
  const [b, setB] = useState<Board | null>(null);
  const [localAt, setLocalAt] = useState(0);
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/leaderboard`, { cache: "no-store" });
        setB(await r.json());
        setLocalAt(Date.now());
      } catch { /* keep the last good board */ }
    };
    poll();
    // 30s here, but the server answers from a 90s cache -- this costs the
    // organisers nothing. Never point this at the leaderboard directly.
    const h = setInterval(poll, 30000);
    return () => clearInterval(h);
  }, []);
  return { board: b, localAt };
}

// -- money ----------------------------------------------------------------
// Two different things, never to be conflated:
//   projected  -- what our own stream says we asked for / capped at. Ours, instant.
//   confirmed  -- what the leaderboard says we actually banked. Theirs, slow, true.
export function money(live: Live, board: Board | null) {
  const settled = live.subs.filter(s => s.ok !== false);
  const best = new Map<string, Sub>();   // later tier overwrites earlier, per case
  for (const s of settled) {
    const cur = best.get(s.case);
    if (!cur || s.tier > cur.tier) best.set(s.case, s);
  }
  const rows = [...best.values()];
  const charged = rows.reduce((t, s) => t + (s.a ?? 0), 0);
  const exposure = rows.reduce((t, s) => t + (s.b ?? 0), 0);

  const p = board?.performance ?? null;
  const numeric = (o: any, ...names: string[]) => {
    if (!o) return null;
    for (const n of names) {
      const hit = Object.keys(o).find(k => k.toLowerCase().replace(/[_\s]/g, "") === n);
      if (hit != null && typeof o[hit] === "number") return o[hit] as number;
    }
    return null;
  };
  return {
    cases: rows.length,
    charged, exposure,
    confirmed: numeric(p, "balance", "total", "score", "profit", "netprofit", "money"),
    rank: numeric(p, "rank", "position", "place"),
    perf: p,
  };
}

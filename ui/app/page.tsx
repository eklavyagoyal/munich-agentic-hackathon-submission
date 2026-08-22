"use client";
import { useEffect, useState } from "react";
import { useLive, useBoard, money, type Live, type Board } from "@/lib/live";

const eur = (n: number | null | undefined, d = 2) =>
  n == null ? "—" : n.toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });

function Card({ title, hint, children, className = "" }:
  { title: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-white/10 bg-[#12161f] overflow-hidden ${className}`}>
      <header className="flex items-baseline justify-between px-4 py-2.5 border-b border-white/10">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">{title}</h2>
        {hint && <span className="text-[11px] text-slate-500">{hint}</span>}
      </header>
      {children}
    </section>
  );
}

function Pill({ tone = "dim", children }: { tone?: string; children: React.ReactNode }) {
  const t: Record<string, string> = {
    dim: "border-white/10 text-slate-400",
    ok: "border-emerald-500/40 text-emerald-400",
    err: "border-red-500/40 text-red-400",
    warn: "border-amber-500/40 text-amber-400",
    shadow: "border-violet-500/40 text-violet-400",
  };
  return <span className={`inline-block rounded-full border px-2 py-[1px] text-[10px] ${t[tone]}`}>{children}</span>;
}

function Countdown({ board, localAt }: { board: Board | null; localAt: number }) {
  const [, tick] = useState(0);
  useEffect(() => { const h = setInterval(() => tick(t => t + 1), 500); return () => clearInterval(h); }, []);
  if (!board?.server_now) return <span className="tabular-nums">—</span>;
  const next = (board.games ?? [])
    .filter(g => g.status === "scheduled" && new Date(g.start_time) >= new Date(board.server_now!))
    .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time))[0];
  if (!next) return <span className="tabular-nums">done</span>;
  const drift = (Date.now() - localAt) / 1000;
  const left = (+new Date(next.start_time) - +new Date(board.server_now)) / 1000 - drift;
  const mm = String(Math.max(0, Math.floor(left / 60))).padStart(2, "0");
  const ss = String(Math.max(0, Math.floor(left % 60))).padStart(2, "0");
  return (
    <span className={`tabular-nums ${left < 60 ? "text-amber-400" : ""}`}>
      {left < 0 ? "live" : `${mm}:${ss}`}
      <span className="ml-2 text-sm font-normal text-slate-500">#{next.id}</span>
    </span>
  );
}

export default function Page() {
  const live = useLive();
  const { board, localAt } = useBoard();
  const m = money(live, board);
  const R = live.current;
  const items = R ? [...R.items.values()].sort((a, b) => a.idx - b.idx) : [];
  const mods = [...live.mods.values()].sort((a, b) => b.fired - a.fired);
  const maxMark = Math.max(1, ...(R?.marks ?? []).map(x => x.ms ?? 0));

  return (
    <div className="min-h-screen bg-[#0a0d13] text-slate-100">
      {/* ---- the only thing that decides the game: money ---- */}
      <div className="border-b border-white/10 bg-gradient-to-b from-[#131a26] to-[#0a0d13]">
        <div className="mx-auto max-w-7xl px-6 py-8 text-center">
          <div className="mb-1 text-[11px] uppercase tracking-[0.3em] text-slate-500">
            Insurance capital · confirmed by the leaderboard
          </div>
          <div className="text-6xl font-bold tabular-nums tracking-tight">
            {m.confirmed == null
              ? <span className="text-slate-600">€ —</span>
              : <span className={m.confirmed >= 0 ? "text-emerald-400" : "text-red-400"}>
                  € {eur(m.confirmed)}
                </span>}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {m.confirmed == null
              ? "no completed round yet — the leaderboard reports nothing until we have played"
              : `rank ${m.rank ?? "—"} · this is banked money, not a projection`}
          </div>

          <div className="mt-7 grid grid-cols-2 gap-x-10 gap-y-5 sm:grid-cols-5">
            {[
              { k: "next game in", v: <Countdown board={board} localAt={localAt} /> },
              { k: "rounds played", v: <span className="tabular-nums">{live.rounds.length + (R ? 1 : 0)}</span> },
              { k: "charged (projected)", v: <span className="tabular-nums">€ {eur(m.charged, 0)}</span> },
              { k: "exposure (pay cap)", v: <span className="tabular-nums">€ {eur(m.exposure, 0)}</span> },
              { k: "clock skew", v: <span className="tabular-nums">{board?.skew_s == null ? "—" : `${board.skew_s > 0 ? "+" : ""}${board.skew_s}s`}</span> },
            ].map(s => (
              <div key={s.k}>
                <div className="text-2xl font-semibold">{s.v}</div>
                <div className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-500">{s.k}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-center gap-3 text-[11px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${live.connected ? "bg-emerald-500 animate-pulse" : "bg-slate-600"}`} />
              {live.connected ? "event stream live" : "event stream idle"}
            </span>
            <span>·</span>
            <span>{board?.upstream_calls ?? 0} leaderboard fetches total — one per 90s, shared by every tab</span>
          </div>
        </div>
      </div>

      <main className="mx-auto grid max-w-7xl gap-4 px-6 py-6 lg:grid-cols-3">
        {/* ---- opponents ---- */}
        <Card title="Standings — who is banking more than us" className="lg:col-span-2"
              hint={board?.fetched_at ? `cached ${new Date(board.fetched_at * 1000).toLocaleTimeString()}` : "not fetched"}>
          {(board?.standings?.length ?? 0) > 0 ? (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#12161f]">
                  <tr>{Object.keys(board!.standings[0]).slice(0, 7).map(c => (
                    <th key={c} className="px-3 py-2 text-left text-[10px] uppercase tracking-wider text-slate-500 font-medium">{c}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {board!.standings.slice(0, 25).map((row, i) => {
                    const mine = board!.team && Object.values(row).some(v => String(v) === board!.team);
                    return (
                      <tr key={i} className={`border-t border-white/5 ${mine ? "bg-sky-500/10" : ""}`}>
                        {Object.keys(board!.standings[0]).slice(0, 7).map(c => (
                          <td key={c} className="px-3 py-1.5 tabular-nums">
                            {typeof row[c] === "number" ? eur(row[c]) : String(row[c] ?? "—")}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="px-4 py-6 text-sm text-slate-500">
              Empty until the first game completes. The matrix endpoint returns nothing before that —
              it is not an error.
            </p>
          )}
        </Card>

        {/* ---- head to head ---- */}
        <Card title="Head to head" hint={board?.team ?? "team unknown"}>
          {(board?.matchup?.length ?? 0) > 0 ? (
            <div className="max-h-80 overflow-auto divide-y divide-white/5">
              {board!.matchup.slice(0, 20).map((r, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-2 text-sm">
                  <span className="truncate">{String(r.opponent ?? r.team ?? r.name ?? `#${i}`)}</span>
                  <span className="tabular-nums text-slate-300">
                    {typeof r.net === "number" ? eur(r.net)
                      : typeof r.balance === "number" ? eur(r.balance)
                      : Object.entries(r).filter(([, v]) => typeof v === "number").map(([k, v]) => `${k} ${eur(v as number)}`).join(" · ") || "—"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="px-4 py-6 text-sm text-slate-500">
              Needs our team name and one completed round. Start the dashboard with{" "}
              <code className="rounded bg-white/5 px-1">--team &quot;NAME&quot;</code> once we are registered.
            </p>
          )}
        </Card>

        {/* ---- round timeline ---- */}
        <Card title="Round timeline" hint={R ? `${R.case} · round ${R.round}` : "no round yet"}>
          {R?.marks.length ? (
            <div className="p-2">
              {R.marks.map((mk, i) => (
                <div key={i} className="grid grid-cols-[62px_1fr] items-center gap-3 rounded px-2 py-1.5 hover:bg-white/5">
                  <span className="text-right text-xs tabular-nums text-sky-400">
                    {mk.ms == null ? "—" : `${(mk.ms / 1000).toFixed(2)}s`}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-sm">
                      {mk.label} <span className="text-xs text-slate-500">{mk.detail}</span>
                    </div>
                    <div className="mt-1 h-[3px] rounded bg-sky-500/70"
                         style={{ width: `${Math.max(2, ((mk.ms ?? 0) / maxMark) * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="px-4 py-6 text-sm text-slate-500">Waiting for the first event.</p>}
          {R?.files.length ? (
            <div className="border-t border-white/10 px-4 py-3">
              <div className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-500">decrypted payload</div>
              <div className="flex flex-wrap gap-1.5">
                {R.files.map(f => {
                  const ext = (f.split(".").pop() ?? "").toLowerCase();
                  const kind: Record<string, string> = {
                    pdf: "pdftotext", txt: "text", png: "vision", jpg: "vision", jpeg: "vision", json: "structured",
                  };
                  return (
                    <span key={f} className="rounded border border-white/10 px-2 py-1 text-xs">
                      {f} <span className="text-slate-500">· {kind[ext] ?? "unknown"}</span>
                    </span>
                  );
                })}
              </div>
            </div>
          ) : null}
        </Card>

        {/* ---- items ---- */}
        <Card title="Line items — belief, bid, and the module that set it" className="lg:col-span-2"
              hint={items.length ? `Σ charge € ${eur(items.reduce((t, i) => t + (i.a ?? 0), 0))}` : ""}>
          {items.length ? (
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#12161f]">
                  <tr>{["#", "description", "qty", "median", "σ", "a — charge", "b — pay cap", "modules"].map(h => (
                    <th key={h} className="px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium text-slate-500">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {items.map(it => (
                    <tr key={it.idx} className="border-t border-white/5">
                      <td className="px-3 py-2 tabular-nums text-slate-500">{it.idx}</td>
                      <td className="px-3 py-2 max-w-[22rem]">
                        <div className="truncate">{it.desc ?? "—"}</div>
                        {it.covered === false && <Pill tone="err">not covered · t = 0</Pill>}
                      </td>
                      <td className="px-3 py-2 tabular-nums text-slate-400">{it.qty ?? "—"} {it.unit ?? ""}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-400">{eur(it.median)}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-400">{it.sigma?.toFixed(2) ?? "—"}</td>
                      <td className="px-3 py-2 tabular-nums font-semibold text-emerald-400">{eur(it.a)}</td>
                      <td className="px-3 py-2 tabular-nums font-semibold text-sky-400">{eur(it.b)}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {(it.trace ?? []).map((t: any, i: number) => (
                            <Pill key={i} tone={t.shadow ? "shadow" : "dim"}>{t.rule ?? t.stage}</Pill>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="px-4 py-6 text-sm text-slate-500">No case parsed yet.</p>}
        </Card>

        {/* ---- modules ---- */}
        <Card title="Modules" hint="active vs shadow">
          {mods.length ? (
            <div className="max-h-96 overflow-auto divide-y divide-white/5">
              {mods.map(md => (
                <div key={md.name} className="flex items-center justify-between px-4 py-2">
                  <span className="text-sm">{md.name}</span>
                  <span className="flex items-center gap-2">
                    <Pill>{md.stage ?? "?"}</Pill>
                    <Pill tone={md.state === "shadow" ? "shadow" : "ok"}>{md.state ?? "active"}</Pill>
                    <span className="w-8 text-right text-sm tabular-nums text-slate-400">{md.fired}</span>
                  </span>
                </div>
              ))}
            </div>
          ) : <p className="px-4 py-6 text-sm text-slate-500">No rules seen yet.</p>}
        </Card>

        {/* ---- submissions ---- */}
        <Card title="Submissions" className="lg:col-span-2" hint="later overwrites earlier — tier must never go down">
          {live.subs.length ? (
            <div className="max-h-72 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#12161f]">
                  <tr>{["tier", "case", "items", "Σ charge", "Σ pay cap", "sent at", "post", "verified"].map(h => (
                    <th key={h} className="px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium text-slate-500">{h}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {live.subs.slice(0, 30).map((s, i) => (
                    <tr key={i} className="border-t border-white/5">
                      <td className="px-3 py-1.5"><Pill tone={s.tier >= 2 ? "ok" : "dim"}>#{s.tier}</Pill></td>
                      <td className="px-3 py-1.5">{s.case}</td>
                      <td className="px-3 py-1.5 tabular-nums">{s.n}</td>
                      <td className="px-3 py-1.5 tabular-nums text-emerald-400">{eur(s.a)}</td>
                      <td className="px-3 py-1.5 tabular-nums text-sky-400">{eur(s.b)}</td>
                      <td className="px-3 py-1.5 tabular-nums">{s.sentAt != null ? `${(s.sentAt / 1000).toFixed(1)}s` : "—"}</td>
                      <td className="px-3 py-1.5 tabular-nums text-slate-400">{s.post != null ? `${s.post}ms` : "—"}</td>
                      <td className="px-3 py-1.5">
                        {s.verified === true ? <Pill tone="ok">yes</Pill>
                          : s.verified === false ? <Pill tone="err">MISMATCH</Pill>
                          : s.ok === false ? <Pill tone="err">send failed</Pill> : <Pill>—</Pill>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="px-4 py-6 text-sm text-slate-500">Nothing submitted yet.</p>}
        </Card>

        {/* ---- alerts ---- */}
        <Card title="Alerts">
          {live.alerts.length ? (
            <div className="max-h-72 overflow-auto p-3 space-y-1.5">
              {live.alerts.map((a, i) => (
                <div key={i} className={`rounded border-l-2 px-3 py-2 text-xs ${
                  a.level === "error" ? "border-red-500 bg-red-500/10" : "border-amber-500 bg-amber-500/10"}`}>
                  <span className="text-slate-500">r{a.round}</span> {a.msg}
                </div>
              ))}
            </div>
          ) : <p className="px-4 py-6 text-sm text-slate-500">Quiet.</p>}
        </Card>

        {/* ---- raw ---- */}
        <Card title="Raw event stream" className="lg:col-span-3" hint="secrets scrubbed server-side">
          <div className="max-h-64 overflow-auto px-4 py-2 font-mono text-[11px]">
            {live.log.length ? [...live.log].reverse().slice(0, 150).map((e, i) => (
              <div key={`${e.round}-${e.seq}-${i}`} className="truncate border-b border-white/5 py-0.5">
                <span className="inline-block w-10 text-slate-600">{e.seq}</span>
                <span className="inline-block w-44 text-sky-400">{e.type}</span>
                <span className="text-slate-500">{JSON.stringify(e.payload).slice(0, 200)}</span>
              </div>
            )) : <span className="text-slate-500">—</span>}
          </div>
        </Card>
      </main>
    </div>
  );
}

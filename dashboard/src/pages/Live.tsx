import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { eur, get, num } from "../api";

type LiveData = {
  alive: boolean; log_age_s: number | null;
  upcoming: { id: number; start_time: string }[];
  policy: Record<string, any>;
  rounds: any[];
  recent_errors: any[];
  log_tail: string;
  pipeline: { game: number; stages: Record<string, any>; order: string[]; finished: boolean } | null;
  anchor_pool: { n: number; games: number };
};

const STAGE_LABEL: Record<string, string> = {
  key: "Key", decrypt: "Entschlüsseln", parse: "Invoice parsen", anchors: "Anker-DB",
  estimate: "Modelle fragen", decide: "Bids setzen", submit: "Submission",
};

export default function Live() {
  const [d, setD] = useState<LiveData | null>(null);
  const [round, setRound] = useState<any | null>(null);   // full detail of pipeline game
  const [err, setErr] = useState("");
  const [clock, setClock] = useState(Date.now());
  const [sel, setSel] = useState<string>("decide");
  useEffect(() => {
    const load = () => get<LiveData>("/api/live").then((x) => {
      setD(x); setErr("");
      if (x.pipeline) {
        get<any>(`/api/rounds/${x.pipeline.game}`).then(setRound).catch(() => setRound(null));
      }
    }).catch((e) => setErr(String(e)));
    load();
    const t = setInterval(load, 2500);
    const c = setInterval(() => setClock(Date.now()), 1000);
    return () => { clearInterval(t); clearInterval(c); };
  }, []);
  if (err) return <div className="panel">API nicht erreichbar: {err}</div>;
  if (!d) return <div className="panel">lade …</div>;

  const next = d.upcoming[0];
  const secs = next ? Math.max(0, Math.round((new Date(next.start_time).getTime() - clock) / 1000)) : null;
  const pl = d.pipeline;
  const stages = pl?.stages ?? {};

  const stageState = (name: string): string => {
    const st = stages[name];
    if (!st) return "pending";
    if (st.status === "done") return "done";
    if (st.status === "start") return "running";
    return "pending";
  };

  return (
    <div className="grid">
      {/* Statuszeile */}
      <div className="cards">
        <div className="card">
          <div className="label">Runner</div>
          <div className={`value ${d.alive ? "pos" : "neg"}`}>{d.alive ? "läuft" : "TOT"}</div>
          <div className="sub">Heartbeat vor {d.log_age_s != null ? Math.round(d.log_age_s) : "?"} s</div>
        </div>
        <div className="card">
          <div className="label">{pl && !pl.finished ? "Runde läuft" : "Nächstes Spiel"}</div>
          <div className="value">{pl && !pl.finished ? `#${pl.game}` : `#${next?.id ?? "—"}`}</div>
          <div className="sub">{pl && !pl.finished ? "Pipeline aktiv" :
            secs != null ? `startet in ${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}` : ""}</div>
        </div>
        <div className="card">
          <div className="label">Anker-Datenbank</div>
          <div className="value">{num(d.anchor_pool?.n)}</div>
          <div className="sub">bewiesene Preisbänder aus {d.anchor_pool?.games} Spielen — wächst pro Runde</div>
        </div>
        <LastSubmission rounds={d.rounds} />
      </div>

      {/* Pipeline-Fluss */}
      <div className="panel">
        <h3>
          Pipeline · {pl ? (pl.finished ? `letzte Runde: Spiel #${pl.game}` : `LÄUFT GERADE: Spiel #${pl.game}`) : "noch keine Runde"}
          {pl && <span style={{ marginLeft: 10, fontWeight: 400, color: "var(--dim)", textTransform: "none", letterSpacing: 0 }}>
            — Stufe anklicken für Details</span>}
        </h3>
        <div className="flow">
          {(pl?.order ?? Object.keys(STAGE_LABEL)).map((name) => {
            const st = stages[name] ?? {};
            const state = stageState(name);
            return (
              <div key={name} className={`stage ${state} ${sel === name ? "sel" : ""}`} onClick={() => setSel(name)}>
                <div className="s-name">{STAGE_LABEL[name] ?? name}</div>
                <div className="s-main">{stageMain(name, st, round)}</div>
                <div className="s-sub">{stageSub(name, st)}</div>
              </div>
            );
          })}
        </div>
        {pl && <StageDetail name={sel} st={stages[sel] ?? {}} round={round} policy={d.policy} />}
      </div>

      <PolicyEditor policy={d.policy} />

      <div className="panel">
        <h3>Runden-Historie</h3>
        <div className="scroll" style={{ maxHeight: "30vh" }}>
          <table>
            <thead>
              <tr><th>Spiel</th><th>Zeit</th><th className="num">Items</th><th className="num">LLM</th>
                <th>Status</th><th className="num">Σ Charge</th></tr>
            </thead>
            <tbody>
              {d.rounds.filter((r) => r.game !== 0 && !r.submit?.dry_run).map((r) => (
                <tr key={r.game + r.ts}>
                  <td><Link to={`/live/${r.game}`}>#{r.game}</Link></td>
                  <td>{new Date(r.ts).toLocaleTimeString("de-DE")}</td>
                  <td className="num">{r.n_items}</td>
                  <td className="num">{r.timeline_ms?.estimate} ms</td>
                  <td>{r.submit?.ok && r.submit?.echo_ok ? <span className="badge b-green">OK + echo</span>
                    : <span className="badge b-red">Status {r.submit?.status}</span>}</td>
                  <td className="num">{eur(r.total_a)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {d.recent_errors.length > 0 && (
          <p style={{ color: "var(--red)", fontSize: 12 }}>
            Fehler: {d.recent_errors.map((e) => `#${e.game}: ${e.error}`).join(" · ")}</p>
        )}
        <details className="logbox">
          <summary>watch.log anzeigen</summary>
          <div className="docbox" style={{ maxHeight: 200 }}>{d.log_tail || "(leer)"}</div>
        </details>
      </div>
    </div>
  );
}

function stageMain(name: string, st: any, round: any): string {
  if (!st.status) return "—";
  switch (name) {
    case "key": return st.status === "done" ? `${st.ms} ms` : "hole Key …";
    case "decrypt": return st.files ? `${st.files.length} Dateien` : "…";
    case "parse": return st.n_items != null ? `${st.n_items} Items` : "…";
    case "anchors": return st.n != null ? `${st.n} Referenzen` : "…";
    case "estimate": {
      if (st.status === "start") return "Modelle laufen …";
      const m = st.models_answered ?? {};
      const okCount = Object.values(m).filter((v: any) => v > 0).length;
      return `${okCount}/${Object.keys(m).length} Modelle`;
    }
    case "decide": return st.total_a != null ? `Σa ${Math.round(st.total_a)} €` : "…";
    case "submit": {
      const r = st.result ?? {};
      if (r.dry_run) return "DRY-RUN";
      return r.ok ? `HTTP ${r.status ?? 200} ✓` : `FEHLER ${r.status ?? ""}`;
    }
  }
  return st.status;
}

function stageSub(name: string, st: any): string {
  if (!st.status) return "wartet";
  switch (name) {
    case "key": return st.archive ?? "";
    case "decrypt": return st.files ? st.files.map((f: any) => f.name).slice(0, 3).join(", ") : "";
    case "parse": return st.status === "done" ? `${st.ms} ms kumuliert` : "";
    case "anchors": return "ähnlichste gelöste Items";
    case "estimate": return st.status === "start" ? (st.models ?? []).join(", ") : `${st.ms} ms`;
    case "decide": return st.total_b != null ? `Σb ${Math.round(st.total_b)} €` : "";
    case "submit": {
      const r = st.result ?? {};
      return r.echo_ok != null ? `Echo ${r.echo_ok ? "verifiziert" : "FEHLT"} · ${r.ms} ms` : "";
    }
  }
  return "";
}

function StageDetail({ name, st, round, policy }: { name: string; st: any; round: any; policy: any }) {
  const r = round?.round;
  const box = { marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 };
  if (!st.status) return <div style={box as any}><p style={{ color: "var(--dim)" }}>Diese Stufe hat noch nicht begonnen.</p></div>;
  switch (name) {
    case "key":
      return <div style={box as any}><div className="kv">
        <span className="k">Archiv</span><span>{st.archive}</span>
        <span className="k">Dauer</span><span>{st.ms} ms (Polling ab Spielstart, 403 bis der Server freigibt)</span>
      </div></div>;
    case "decrypt":
      return <div style={box as any}>
        <table><thead><tr><th>Datei</th><th className="num">Größe</th></tr></thead><tbody>
          {(st.files ?? []).map((f: any) => (
            <tr key={f.name}><td>{f.name}</td><td className="num">{f.kb} KB</td></tr>))}
        </tbody></table>
        <p style={{ color: "var(--dim)", fontSize: 12 }}>Vollansicht der Dokumente: <Link to={`/live/${st.game ?? r?.game}`}>Runden-Detail →</Link></p>
      </div>;
    case "parse":
      return <div style={box as any}><div className="scroll" style={{ maxHeight: 260 }}>
        <table><thead><tr><th className="num">#</th><th>Beschreibung</th><th className="num">Qty</th><th>Unit</th></tr></thead>
          <tbody>{(st.items ?? []).map((it: any) => (
            <tr key={it.i}><td className="num">{it.i}</td><td style={{ whiteSpace: "normal" }}>{it.desc}</td>
              <td className="num">{it.qty}</td><td>{it.unit}</td></tr>))}</tbody></table>
      </div></div>;
    case "anchors":
      return <div style={box as any}>
        <p style={{ fontSize: 12, color: "var(--dim)", margin: "0 0 8px" }}>
          Für jedes Invoice-Item werden die ähnlichsten bereits gelösten Items (Token-Overlap + Unit-Bonus)
          aus allen früheren Spielen gezogen — mit ihren <b>bewiesenen</b> Preisgrenzen aus den echten
          Turniertransaktionen. Diese Liste geht wörtlich in den Prompt, als Kalibrier-Referenz.</p>
        <div className="scroll" style={{ maxHeight: 260 }}>
          <table><thead><tr><th>Referenz-Item</th><th className="num">Qty/Unit</th>
            <th className="num">t ≥</th><th className="num">t &lt;</th><th className="num">Ähnlichkeit</th><th className="num">aus Spiel</th></tr></thead>
            <tbody>{(st.anchors ?? []).map((a: any, i: number) => (
              <tr key={i}><td style={{ whiteSpace: "normal" }}>{a.desc}</td>
                <td className="num">{a.qty} {a.unit}</td>
                <td className="num pos">{a.t_lo ? eur(a.t_lo, 0) : "—"}</td>
                <td className="num neg">{a.t_hi != null ? eur(a.t_hi, 0) : "—"}</td>
                <td className="num">{(a.score * 100).toFixed(0)} %</td>
                <td className="num">#{a.game}</td></tr>))}</tbody></table>
        </div>
      </div>;
    case "estimate": {
      const models: string[] = r ? Object.keys(r.per_model ?? {}) : (st.models ?? []);
      return <div style={box as any}>
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          {Object.entries(st.models_answered ?? {}).map(([m, n]: any) => (
            <span key={m} className={`badge ${n ? "b-green" : "b-red"}`}>{m}: {n} Items</span>))}
          {Object.entries(st.errors ?? {}).map(([m, e]: any) => (
            <span key={m} className="badge b-red" title={e}>{m}: Fehler</span>))}
        </div>
        {r && <div className="scroll" style={{ maxHeight: 260 }}>
          <table><thead><tr><th className="num">#</th><th>Item</th>
            {models.map((m) => <th key={m} className="num">{m.replace("gpt-", "")}</th>)}
            <th className="num">Median t̂</th></tr></thead>
            <tbody>{(r.bids ?? []).map((b: any) => {
              const it = (r.items ?? []).find((x: any) => x.i === b.i) ?? {};
              return <tr key={b.i}><td className="num">{b.i}</td>
                <td style={{ whiteSpace: "normal", maxWidth: 340 }}>{it.desc}</td>
                {models.map((m) => <td key={m} className="num">{r.per_model?.[m]?.[b.i] != null ? num(r.per_model[m][b.i]) : "—"}</td>)}
                <td className="num" style={{ fontWeight: 700 }}>{num(b.t_hat)}</td></tr>;
            })}</tbody></table>
        </div>}
        {r?.prompt && <details className="logbox"><summary>kompletten Prompt anzeigen ({r.prompt.length} Zeichen)</summary>
          <div className="docbox">{r.prompt}</div></details>}
      </div>;
    }
    case "decide":
      return <div style={box as any}>
        <p style={{ fontSize: 12, color: "var(--dim)", margin: "0 0 8px" }}>
          a = {policy?.a_mult} × t̂ (Charge) · b = {policy?.b_mult} × t̂ (Akzeptanzlimit) ·
          t̂=0 → a = {policy?.zero_floor_a} € Zero-Floor, b = 0</p>
        {r && <div className="scroll" style={{ maxHeight: 260 }}>
          <table><thead><tr><th className="num">#</th><th>Item</th><th className="num">t̂</th>
            <th className="num">a (Charge)</th><th className="num">b (Limit)</th><th>Quelle</th></tr></thead>
            <tbody>{(r.bids ?? []).map((b: any) => {
              const it = (r.items ?? []).find((x: any) => x.i === b.i) ?? {};
              return <tr key={b.i}><td className="num">{b.i}</td>
                <td style={{ whiteSpace: "normal", maxWidth: 380 }}>{it.desc}</td>
                <td className="num">{num(b.t_hat)}</td>
                <td className="num pos">{eur(b.a, 2)}</td>
                <td className="num" style={{ color: "var(--blue)" }}>{eur(b.b, 2)}</td>
                <td><span className={`badge ${b.src === "fallback" ? "b-amber" : "b-gray"}`}>{b.src}</span></td></tr>;
            })}</tbody></table>
        </div>}
      </div>;
    case "submit": {
      const res = st.result ?? {};
      return <div style={box as any}><div className="kv">
        <span className="k">HTTP</span><span>{res.dry_run ? "DRY-RUN (nicht gesendet)" : res.status}</span>
        <span className="k">Echo-Verifikation</span>
        <span className={res.echo_ok ? "pos" : "neg"}>{String(res.echo_ok ?? "—")} (Server-Antwort gegen Payload geprüft)</span>
        <span className="k">Latenz</span><span>{res.ms} ms</span>
        <span className="k">Items</span><span>{st.game ?? ""} {res.n ?? (r?.bids?.length ?? "?")} Zeilen als bare JSON-Array via PUT</span>
      </div></div>;
    }
  }
  return null;
}

function LastSubmission({ rounds }: { rounds: any[] }) {
  const real = rounds.find((r) => r.game !== 0 && !r.submit?.dry_run);
  if (!real) {
    return (
      <div className="card">
        <div className="label">Letzte echte Submission</div>
        <div className="value" style={{ color: "var(--dim)" }}>noch keine</div>
        <div className="sub">wartet auf den nächsten Spielstart</div>
      </div>
    );
  }
  const ok = real.submit?.ok && real.submit?.echo_ok;
  return (
    <div className="card">
      <div className="label">Letzte echte Submission</div>
      <div className={`value ${ok ? "pos" : "neg"}`}>#{real.game} {ok ? "OK ✓" : `Status ${real.submit?.status}`}</div>
      <div className="sub">{real.n_items} Items · Σ Charge {eur(real.total_a)} · {real.submit?.ms} ms</div>
    </div>
  );
}

function PolicyEditor({ policy }: { policy: Record<string, any> }) {
  const [a, setA] = useState<string>(String(policy.a_mult));
  const [b, setB] = useState<string>(String(policy.b_mult));
  const [models, setModels] = useState<string>(String(policy.models));
  const [note, setNote] = useState<string>(String(policy.note ?? ""));
  const [saved, setSaved] = useState("");
  const dirty = useMemo(
    () => a !== String(policy.a_mult) || b !== String(policy.b_mult)
      || models !== String(policy.models) || note !== String(policy.note ?? ""),
    [a, b, models, note, policy]);

  async function save() {
    const body = { a_mult: parseFloat(a), b_mult: parseFloat(b), models, note };
    const r = await fetch("/api/policy", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setSaved(r.ok ? `gespeichert ${new Date().toLocaleTimeString("de-DE")} — gilt ab dem nächsten Spiel` : "FEHLER beim Speichern");
  }

  return (
    <div className="panel">
      <h3>Live-Policy — wird vor jedem Spiel neu gelesen, kein Neustart nötig</h3>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
        <label style={{ fontSize: 12 }}>a-Multiplikator (Issuer)<br />
          <input type="text" style={{ width: 90 }} value={a} onChange={(e) => setA(e.target.value)} /></label>
        <label style={{ fontSize: 12 }}>b-Multiplikator (Reviewer)<br />
          <input type="text" style={{ width: 90 }} value={b} onChange={(e) => setB(e.target.value)} /></label>
        <label style={{ fontSize: 12 }}>Modelle (kommagetrennt)<br />
          <input type="text" style={{ width: 360 }} value={models} onChange={(e) => setModels(e.target.value)} /></label>
        <label style={{ fontSize: 12 }}>Notiz (warum)<br />
          <input type="text" style={{ width: 240 }} value={note} onChange={(e) => setNote(e.target.value)} /></label>
        <button style={{ padding: "7px 18px", background: dirty ? "#1f6feb" : "#21262d",
          color: "#fff", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer" }}
          onClick={save} disabled={!dirty}>Übernehmen</button>
        <span style={{ fontSize: 12, color: "var(--dim)" }}>{saved}</span>
      </div>
    </div>
  );
}

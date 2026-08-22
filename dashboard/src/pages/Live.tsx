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
  now: string;
};

export default function Live() {
  const [d, setD] = useState<LiveData | null>(null);
  const [err, setErr] = useState("");
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    const load = () => get<LiveData>("/api/live").then((x) => { setD(x); setErr(""); })
      .catch((e) => setErr(String(e)));
    load();
    const t = setInterval(load, 3000);
    const c = setInterval(() => setClock(Date.now()), 1000);
    return () => { clearInterval(t); clearInterval(c); };
  }, []);
  if (err) return <div className="panel">API nicht erreichbar: {err}</div>;
  if (!d) return <div className="panel">lade …</div>;

  const next = d.upcoming[0];
  const secs = next ? Math.max(0, Math.round((new Date(next.start_time).getTime() - clock) / 1000)) : null;

  return (
    <div className="grid">
      <div className="cards">
        <div className="card">
          <div className="label">Runner</div>
          <div className={`value ${d.alive ? "pos" : "neg"}`}>{d.alive ? "LÄUFT" : "TOT"}</div>
          <div className="sub">Log vor {d.log_age_s != null ? Math.round(d.log_age_s) : "?"} s</div>
        </div>
        <div className="card">
          <div className="label">Nächstes Spiel</div>
          <div className="value">#{next?.id ?? "—"}</div>
          <div className="sub">{secs != null ? `in ${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}` : ""} · {next ? new Date(next.start_time).toLocaleTimeString("de-DE") : ""}</div>
        </div>
        <div className="card">
          <div className="label">Policy (live)</div>
          <div className="value">a×{d.policy.a_mult} · b×{d.policy.b_mult}</div>
          <div className="sub">{String(d.policy.models).split(",").length} Modelle</div>
        </div>
        <div className="card">
          <div className="label">Letzte Submission</div>
          {d.rounds[0] ? (
            <>
              <div className={`value ${d.rounds[0].submit?.ok ? "pos" : "neg"}`}>
                #{d.rounds[0].game} {d.rounds[0].submit?.dry_run ? "DRY" : d.rounds[0].submit?.ok ? "OK" : "FEHLER"}
              </div>
              <div className="sub">
                echo {String(d.rounds[0].submit?.echo_ok)} · {d.rounds[0].submit?.ms} ms · Σa {eur(d.rounds[0].total_a)}
              </div>
            </>
          ) : (<div className="value">—</div>)}
        </div>
      </div>

      <PolicyEditor policy={d.policy} />

      <div className="panel">
        <h3>Pipeline-Runden (neueste zuerst) — Klick für Prompt, Modelle, Dokumente</h3>
        <div className="scroll" style={{ maxHeight: "40vh" }}>
          <table>
            <thead>
              <tr>
                <th>Spiel</th><th>Zeit</th><th className="num">Items</th>
                <th className="num">Key</th><th className="num">Parse</th><th className="num">LLM</th><th className="num">Submit</th>
                <th>Modelle</th><th>Status</th><th className="num">Σ Charge</th>
              </tr>
            </thead>
            <tbody>
              {d.rounds.map((r) => (
                <tr key={r.game + r.ts}>
                  <td><Link to={`/live/${r.game}`}>#{r.game}</Link></td>
                  <td>{new Date(r.ts).toLocaleTimeString("de-DE")}</td>
                  <td className="num">{r.n_items}</td>
                  <td className="num">{r.timeline_ms?.key} ms</td>
                  <td className="num">{r.timeline_ms?.parse} ms</td>
                  <td className="num">{r.timeline_ms?.estimate} ms</td>
                  <td className="num">{r.timeline_ms?.submit} ms</td>
                  <td>{r.models ? Object.entries(r.models).map(([m, n]) => (
                    <span key={m} className={`badge ${n ? "b-green" : "b-red"}`} style={{ marginRight: 4 }}>
                      {String(m).replace("gpt-", "")}:{String(n)}
                    </span>)) : "—"}</td>
                  <td>
                    {r.submit?.dry_run ? <span className="badge b-amber">dry</span>
                      : r.submit?.ok && r.submit?.echo_ok ? <span className="badge b-green">OK + echo</span>
                      : r.submit?.ok ? <span className="badge b-amber">OK, echo {String(r.submit?.echo_ok)}</span>
                      : <span className="badge b-red">FEHLER {r.submit?.status}</span>}
                  </td>
                  <td className="num">{eur(r.total_a)}</td>
                </tr>
              ))}
              {!d.rounds.length && <tr><td colSpan={10}>noch keine Runde geloggt</td></tr>}
            </tbody>
          </table>
        </div>
        {d.recent_errors.length > 0 && (
          <p style={{ color: "var(--red)", fontSize: 12 }}>
            Fehler: {d.recent_errors.map((e) => `#${e.game}: ${e.error}`).join(" · ")}
          </p>
        )}
      </div>

      <div className="panel">
        <h3>watch.log (live)</h3>
        <div className="docbox" style={{ maxHeight: 220 }}>{d.log_tail || "(leer)"}</div>
      </div>
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
        <button className={dirty ? "on" : ""} style={{ padding: "7px 18px", background: dirty ? "#1f6feb" : "#21262d",
          color: "#fff", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer" }}
          onClick={save} disabled={!dirty}>Übernehmen</button>
        <span style={{ fontSize: 12, color: "var(--dim)" }}>{saved}</span>
      </div>
    </div>
  );
}

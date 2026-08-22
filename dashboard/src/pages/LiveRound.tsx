import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { eur, get } from "../api";

export default function LiveRound() {
  const { game } = useParams();
  const [d, setD] = useState<any | null>(null);
  const [err, setErr] = useState("");
  const [doc, setDoc] = useState("");
  const [showPrompt, setShowPrompt] = useState(false);
  useEffect(() => {
    get<any>(`/api/rounds/${game}`).then((x) => {
      setD(x);
      const names = Object.keys(x.docs);
      setDoc(names.find((n) => n.includes("description")) ?? names[0] ?? "");
    }).catch((e) => setErr(String(e)));
  }, [game]);
  if (err) return <div className="panel">Keine Pipeline-Runde für Spiel {game}: {err} · <Link to="/live">zurück</Link></div>;
  if (!d) return <div className="panel">lade …</div>;
  const r = d.round;
  const models: string[] = Object.keys(r.per_model ?? {});
  const itemsById: Record<number, any> = {};
  for (const it of r.items ?? []) itemsById[it.i] = it;

  const phases = r.timeline_ms ?? {};
  const phaseOrder = ["key", "decrypt", "parse", "estimate", "submit"];
  let prev = 0;
  const bars = phaseOrder.filter((p) => phases[p] != null).map((p) => {
    const dur = phases[p] - prev; prev = phases[p];
    return { name: p, dur };
  });
  const total = prev || 1;

  return (
    <div className="grid">
      <div className="panel">
        <h3>Pipeline-Runde Spiel #{r.game} · {new Date(r.ts).toLocaleString("de-DE")} · <Link to="/live">← Live</Link> · <Link to={`/games/${r.game}`}>Spielergebnis →</Link></h3>
        <div style={{ display: "flex", height: 26, borderRadius: 6, overflow: "hidden", border: "1px solid var(--border)" }}>
          {bars.map((b, i) => (
            <div key={b.name} title={`${b.name}: ${b.dur} ms`} style={{
              width: `${Math.max((100 * b.dur) / total, 2)}%`,
              background: ["#1f6feb", "#8957e5", "#d29922", "#3fb950", "#f85149"][i % 5],
              fontSize: 10, color: "#fff", padding: "6px 4px", whiteSpace: "nowrap", overflow: "hidden",
            }}>{b.name} {b.dur}ms</div>
          ))}
        </div>
        <p style={{ fontSize: 12, color: "var(--dim)" }}>
          gesamt {total} ms von 60.000 ms Budget · Policy: a×{r.policy?.a_mult} b×{r.policy?.b_mult}
          {r.policy?.note ? ` · „${r.policy.note}“` : ""} ·
          Submission: {r.submit?.dry_run ? "DRY-RUN" : `HTTP ${r.submit?.status}, echo_ok=${String(r.submit?.echo_ok)}, ${r.submit?.ms} ms`}
        </p>
        {Object.keys(r.errors ?? {}).length > 0 && (
          <p style={{ color: "var(--red)", fontSize: 12 }}>
            Modell-Fehler: {Object.entries(r.errors).map(([m, e]) => `${m}: ${e}`).join(" · ")}
          </p>
        )}
      </div>

      <div className="panel">
        <h3>Bids — jedes Item mit Modell-Votes, Median t̂ und finalem a/b</h3>
        <div className="scroll" style={{ maxHeight: "45vh" }}>
          <table>
            <thead>
              <tr>
                <th className="num">#</th><th>Beschreibung</th><th className="num">Qty</th><th>Unit</th>
                {models.map((m) => <th key={m} className="num">{m.replace("gpt-", "")}</th>)}
                <th className="num">t̂ (Median)</th><th className="num">a</th><th className="num">b</th><th>Quelle</th>
              </tr>
            </thead>
            <tbody>
              {(r.bids ?? []).map((b: any) => {
                const it = itemsById[b.i] ?? {};
                return (
                  <tr key={b.i}>
                    <td className="num">{b.i}</td>
                    <td style={{ whiteSpace: "normal", maxWidth: 380 }}>{it.desc}</td>
                    <td className="num">{it.qty}</td>
                    <td>{it.unit}</td>
                    {models.map((m) => (
                      <td key={m} className="num">{r.per_model[m]?.[b.i] != null ? eur(r.per_model[m][b.i], 0) : "—"}</td>
                    ))}
                    <td className="num" style={{ fontWeight: 700 }}>{eur(b.t_hat, 0)}</td>
                    <td className="num pos">{eur(b.a, 2)}</td>
                    <td className="num" style={{ color: "var(--blue)" }}>{eur(b.b, 2)}</td>
                    <td><span className={`badge ${b.src === "fallback" ? "b-amber" : "b-gray"}`}>{b.src}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="two">
        <div className="panel">
          <h3>
            Prompt an die Modelle{" "}
            <button style={{ marginLeft: 8, fontSize: 11, padding: "2px 8px", cursor: "pointer",
              background: "#21262d", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 5 }}
              onClick={() => setShowPrompt(!showPrompt)}>{showPrompt ? "einklappen" : "anzeigen"}</button>
          </h3>
          {showPrompt && <div className="docbox">{r.prompt || "(nicht geloggt)"}</div>}
          {!showPrompt && <p style={{ color: "var(--dim)", fontSize: 12 }}>{(r.prompt ?? "").length} Zeichen · identischer Prompt an alle {models.length} Modelle, parallel</p>}
        </div>
        <div className="panel">
          <h3>Entschlüsselte Case-Dokumente</h3>
          <div className="tabs">
            {Object.keys(d.docs).map((n) => (
              <button key={n} className={doc === n ? "on" : ""} onClick={() => setDoc(n)}>{n}</button>
            ))}
          </div>
          <div className="docbox">{d.docs[doc] ?? "(keine)"}</div>
        </div>
      </div>
    </div>
  );
}

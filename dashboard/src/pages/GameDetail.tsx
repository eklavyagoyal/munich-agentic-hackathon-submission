import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { cls, eur, get, num } from "../api";

export default function GameDetail() {
  const { id } = useParams();
  const [d, setD] = useState<any | null>(null);
  const [doc, setDoc] = useState("");
  useEffect(() => { get<any>(`/api/games/${id}`).then((x) => {
    setD(x);
    const names = Object.keys(x.docs);
    setDoc(names.find((n) => n.includes("description")) ?? names[0] ?? "");
  }); }, [id]);
  if (!d) return <div className="panel">lade …</div>;

  const chargesByItem: Record<number, any[]> = {};
  for (const c of d.charges) (chargesByItem[c.line_item] ??= []).push(c);

  return (
    <div className="grid">
      <div className="panel">
        <h3>
          Spiel #{id} · {new Date(d.game.start_time).toLocaleString("de-DE")} ·{" "}
          <Link to="/games">zurück</Link>
        </h3>
        <div className="scroll" style={{ maxHeight: "28vh" }}>
          <table>
            <thead><tr><th>Team</th><th className="num">Net in diesem Spiel</th></tr></thead>
            <tbody>
              {d.scores.map((s: any) => (
                <tr key={s.team} className={s.team === "Oasis" ? "us" : ""}>
                  <td>{s.team}</td>
                  <td className={`num ${cls(s.score)}`}>{eur(s.score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3>Line-Items: bewiesene t-Bänder vs. unsere Charge</h3>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th className="num">Item</th>
                <th className="num">t ≥ (bewiesen)</th>
                <th className="num">t &lt; (bewiesen)</th>
                <th className="num">unser a</th>
                <th>Quelle</th>
                <th>Ausgang unserer Charge</th>
                <th className="num">max. faire Charge im Feld</th>
              </tr>
            </thead>
            <tbody>
              {d.items.map((it: any) => {
                const under = it.our_a != null && it.t_lo > 0 && it.our_a < it.t_lo;
                const burned = (it.our_n_rej_zero ?? 0) > 0 && (it.our_n_rej_paid ?? 0) === 0;
                const fieldFair = Math.max(0, ...(chargesByItem[it.line_item] ?? [])
                  .filter((c: any) => c.n_rejected_paid > 0).map((c: any) => c.a ?? 0));
                return (
                  <tr key={it.line_item}>
                    <td className="num">{it.line_item}</td>
                    <td className="num pos">{it.t_lo > 0 ? eur(it.t_lo, 2) : "—"}</td>
                    <td className="num neg">{it.t_hi != null ? eur(it.t_hi, 2) : "—"}</td>
                    <td className="num">{it.our_a != null ? eur(it.our_a, 2) : "—"}</td>
                    <td><span className="badge b-gray">{it.our_a_source ?? "—"}</span></td>
                    <td>
                      {burned ? <span className="badge b-red">verbrannt (a &gt; t)</span>
                        : under ? <span className="badge b-amber">zu billig</span>
                        : it.our_a != null ? <span className="badge b-green">ok</span> : "—"}
                      {" "}
                      <span className="badge b-gray">
                        {num(it.our_n_acc)}A/{num(it.our_n_rej_paid)}P/{num(it.our_n_rej_zero)}Z
                      </span>
                    </td>
                    <td className="num">{fieldFair > 0 ? eur(fieldFair, 2) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="two">
        <div className="panel">
          <h3>Unsere Reviews (was wir akzeptiert/abgelehnt haben)</h3>
          <div className="scroll" style={{ maxHeight: "50vh" }}>
            <table>
              <thead>
                <tr><th className="num">Item</th><th>Issuer</th><th>Entscheidung</th>
                  <th className="num">geflossen</th><th className="num">Issuer-a</th></tr>
              </thead>
              <tbody>
                {d.our_reviews.map((r: any, i: number) => (
                  <tr key={i}>
                    <td className="num">{r.line_item}</td>
                    <td>{r.issuer}</td>
                    <td>
                      {r.accepted ? <span className="badge b-green">accept</span>
                        : r.amount > 0 ? <span className="badge b-red">reject + Strafe</span>
                        : <span className="badge b-gray">reject (Fraud)</span>}
                    </td>
                    <td className="num">{eur(r.accepted ? r.amount : r.amount * 1.5, 2)}</td>
                    <td className="num">{r.issuer_a != null ? eur(r.issuer_a, 2) : "?"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <h3>Case-Dokumente</h3>
          <div className="tabs">
            {Object.keys(d.docs).map((n) => (
              <button key={n} className={doc === n ? "on" : ""} onClick={() => setDoc(n)}>{n}</button>
            ))}
          </div>
          <div className="docbox">{d.docs[doc] ?? "keine entschlüsselten Dokumente"}</div>
        </div>
      </div>
    </div>
  );
}

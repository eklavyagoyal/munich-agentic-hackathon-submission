import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { eur, get } from "../api";

type Row = {
  game_id: number; line_item: number; t_lo: number; t_hi: number | null;
  our_a: number | null; a_source: string | null;
  our_rej_zero: number; our_rej_paid: number; foregone: number;
};

export default function Items() {
  const [rows, setRows] = useState<Row[]>([]);
  const [only, setOnly] = useState<"all" | "foregone" | "burned">("foregone");
  useEffect(() => { get<Row[]>("/api/items").then(setRows); }, []);

  const view = useMemo(() => {
    let v = rows;
    if (only === "foregone") v = rows.filter((r) => r.foregone > 0);
    if (only === "burned") v = rows.filter((r) => (r.our_rej_zero ?? 0) > 0 && !(r.our_rej_paid > 0));
    return v.slice(0, 500);
  }, [rows, only]);

  const totalForegone = rows.reduce((s, r) => s + (r.foregone || 0), 0);

  return (
    <div className="grid">
      <div className="panel">
        <h3>
          Item-Explorer · bewiesen liegengelassen: <span className="neg">{eur(totalForegone)}</span>
        </h3>
        <div className="tabs">
          <button className={only === "foregone" ? "on" : ""} onClick={() => setOnly("foregone")}>
            zu billig verkauft ({rows.filter((r) => r.foregone > 0).length})
          </button>
          <button className={only === "burned" ? "on" : ""} onClick={() => setOnly("burned")}>
            verbrannt / Fraud gecharged ({rows.filter((r) => (r.our_rej_zero ?? 0) > 0 && !(r.our_rej_paid > 0)).length})
          </button>
          <button className={only === "all" ? "on" : ""} onClick={() => setOnly("all")}>
            alle ({rows.length})
          </button>
        </div>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Spiel</th><th className="num">Item</th>
                <th className="num">unser a</th>
                <th className="num">t ≥</th><th className="num">t &lt;</th>
                <th className="num">entgangen (×16)</th>
                <th>Quelle</th>
              </tr>
            </thead>
            <tbody>
              {view.map((r, i) => (
                <tr key={i}>
                  <td><Link to={`/games/${r.game_id}`}>#{r.game_id}</Link></td>
                  <td className="num">{r.line_item}</td>
                  <td className="num">{r.our_a != null ? eur(r.our_a, 2) : "—"}</td>
                  <td className="num pos">{r.t_lo > 0 ? eur(r.t_lo, 2) : "—"}</td>
                  <td className="num neg">{r.t_hi != null ? eur(r.t_hi, 2) : "—"}</td>
                  <td className="num neg">{r.foregone > 0 ? eur(r.foregone) : "—"}</td>
                  <td><span className="badge b-gray">{r.a_source ?? "—"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

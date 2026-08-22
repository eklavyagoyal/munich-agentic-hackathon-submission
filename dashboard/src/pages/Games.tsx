import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { cls, eur } from "../api";
import { get } from "../api";

type Row = { id: number; start_time: string; status: string; score: number | null; cum: number; n_items: number };

export default function Games() {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => { get<Row[]>("/api/games").then(setRows); }, []);
  const mult = (iso: string) => iso >= "2026-08-23T06:00:00" ? 3 : 1;
  return (
    <div className="panel">
      <h3>Alle 100 Spiele</h3>
      <div className="scroll">
        <table>
          <thead>
            <tr><th>#</th><th>Start (lokal)</th><th>Status</th><th className="num">Items</th>
              <th className="num">Unser Net</th><th className="num">Kumuliert</th><th>Wertung</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.status === "completed" ? <Link to={`/games/${r.id}`}>#{r.id}</Link> : `#${r.id}`}</td>
                <td>{new Date(r.start_time).toLocaleString("de-DE")}</td>
                <td>
                  <span className={`badge ${r.status === "completed" ? "b-gray" : "b-blue"}`}>{r.status}</span>
                </td>
                <td className="num">{r.n_items || "—"}</td>
                <td className={`num ${cls(r.score)}`}>{r.score == null ? "—" : eur(r.score)}</td>
                <td className={`num ${cls(r.cum)}`}>{r.status === "completed" ? eur(r.cum) : "—"}</td>
                <td>{mult(r.start_time) === 3 ? <span className="badge b-amber">3×</span> : "1×"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

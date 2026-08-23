import { useEffect, useState } from "react";
import { cls, eur, num, pct } from "../api";
import { get } from "../api";

export default function Teams() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { get<any[]>("/api/teams").then(setRows); }, []);
  return (
    <div className="panel">
      <h3>Gegner-Profile — wer akzeptiert was, wer chargt wie</h3>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th className="num">Net</th>
              <th className="num">Accept-Rate als Reviewer</th>
              <th className="num">gezahlt (Accepts)</th>
              <th className="num">gezahlt (Penalties)</th>
              <th className="num">Ø Charge a</th>
              <th className="num">Items fair bewiesen</th>
              <th className="num">Items Fraud bewiesen</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.team} className={t.team === "Oasis" ? "us" : ""}>
                <td>{t.team}</td>
                <td className={`num ${cls(t.net)}`}>{eur(t.net)}</td>
                <td className="num">{pct(t.rev_accept_rate)}</td>
                <td className="num">{eur(t.rev_paid_accepted)}</td>
                <td className="num">{eur(t.rev_paid_penalties)}</td>
                <td className="num">{t.iss_avg_a != null ? eur(t.iss_avg_a, 0) : "—"}</td>
                <td className="num">{num(t.iss_fair_proven)}</td>
                <td className="num">{num(t.iss_fraud_proven)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ color: "var(--dim)", fontSize: 12 }}>
        „fair bewiesen“: Charge wurde abgelehnt und trotzdem bezahlt (a ≤ t sicher).
        „Fraud bewiesen“: mindestens ein Reviewer lehnte ab und es floss nichts (a &gt; t sicher).
      </p>
    </div>
  );
}

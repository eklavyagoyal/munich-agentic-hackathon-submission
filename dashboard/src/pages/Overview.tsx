import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { cls, eur, get, num } from "../api";

type Overview = {
  our_team: string;
  teams: any[];
  curve: { game_id: number; score: number; cum: number }[];
  completed: number;
  upcoming: { id: number; start_time: string }[];
  n_3x: number;
  mult_start: string;
  totals: Record<string, number>;
  buckets: any[];
};

export default function OverviewPage() {
  const [d, setD] = useState<Overview | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    const load = () => get<Overview>("/api/overview").then(setD).catch((e) => setErr(String(e)));
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, []);
  if (err) return <div className="panel">API nicht erreichbar: {err} — läuft <code>backend.app.server</code>?</div>;
  if (!d) return <div className="panel">lade …</div>;

  const us = d.teams.find((t) => t.team === d.our_team);
  const rank = d.teams.findIndex((t) => t.team === d.our_team) + 1;
  const next = d.upcoming[0];
  const remaining = 100 - d.completed;
  const equivalents = remaining - d.n_3x + d.n_3x * 3;
  const needed = us ? -us.net / equivalents : 0;

  return (
    <div className="grid">
      <div className="cards">
        <div className="card">
          <div className="label">Net (offiziell)</div>
          <div className={`value ${cls(us?.net)}`}>{eur(us?.net)}</div>
          <div className="sub">Platz {rank} / {d.teams.length} · {d.completed} Spiele</div>
        </div>
        <div className="card">
          <div className="label">Offene Wertung</div>
          <div className="value">{remaining} Spiele</div>
          <div className="sub">{remaining - d.n_3x}× einfach + {d.n_3x}× dreifach = {equivalents} Äquivalente</div>
        </div>
        <div className="card">
          <div className="label">Break-even braucht</div>
          <div className="value warn">{eur(needed)} / Spiel-Äq.</div>
          <div className="sub">Bestes Team macht ~{eur((d.teams[0]?.net ?? 0) / d.completed)} je Spiel</div>
        </div>
        <div className="card">
          <div className="label">Nächstes Spiel</div>
          <div className="value">#{next?.id ?? "—"}</div>
          <div className="sub">{next ? new Date(next.start_time).toLocaleTimeString("de-DE") : ""} lokal</div>
        </div>
      </div>

      <div className="cards">
        <Bucket label="Liegengelassen (a < bewiesenes t)" v={d.totals.undercharge_foregone}
          sub="Unser Charge unter t_lo — jeder Gegner hätte die Differenz gezahlt" />
        <Bucket label="Strafanteil falscher Rejections" v={d.totals.penalty_surcharge}
          sub="0,5a Anwaltskosten, vermeidbar mit höherem b" />
        <Bucket label="Bewiesenen Fraud bezahlt" v={d.totals.paid_proven_fraud}
          sub="accepted, obwohl a ≥ bewiesenes t_hi" />
        <div className="card">
          <div className="label">Verbrannte Items (Fraud gecharged)</div>
          <div className="value warn">{num(d.totals.burned_items)}</div>
          <div className="sub">a &gt; t: alle Gegner lehnten ab, 0 € verdient</div>
        </div>
      </div>

      <div className="two">
        <div className="panel">
          <h3>Kumulierter Net-Verlauf</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={d.curve}>
              <CartesianGrid stroke="#21262d" />
              <XAxis dataKey="game_id" stroke="#8b949e" fontSize={11} />
              <YAxis stroke="#8b949e" fontSize={11} tickFormatter={(v) => (v / 1000).toFixed(0) + "k"} />
              <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #2d333b" }}
                formatter={(v: number) => eur(v)} />
              <ReferenceLine y={0} stroke="#8b949e" strokeDasharray="4 4" />
              <Line dataKey="cum" stroke="#58a6ff" dot={false} strokeWidth={2} name="kumuliert" />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Net pro Spiel</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={d.curve}>
              <CartesianGrid stroke="#21262d" />
              <XAxis dataKey="game_id" stroke="#8b949e" fontSize={11} />
              <YAxis stroke="#8b949e" fontSize={11} tickFormatter={(v) => (v / 1000).toFixed(0) + "k"} />
              <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #2d333b" }}
                formatter={(v: number) => eur(v)} />
              <ReferenceLine y={0} stroke="#8b949e" />
              <Bar dataKey="score" name="net">
                {d.curve.map((c) => (
                  <Cell key={c.game_id} fill={c.score >= 0 ? "#3fb950" : "#f85149"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel">
        <h3>Standings</h3>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>#</th><th>Team</th>
                <th className="num">Net</th><th className="num">Income</th><th className="num">Costs</th>
                <th className="num">Penalties</th><th className="num">Fraud akzeptiert</th>
                <th className="num">Issuer-Acceptrate</th>
              </tr>
            </thead>
            <tbody>
              {d.teams.map((t, i) => (
                <tr key={t.team} className={t.team === d.our_team ? "us" : ""}>
                  <td>{i + 1}</td>
                  <td>{t.team}</td>
                  <td className={`num ${cls(t.net)}`}>{eur(t.net)}</td>
                  <td className="num">{eur(t.income)}</td>
                  <td className="num">{eur(t.costs)}</td>
                  <td className="num">{num(t.reviewed_penalties)}</td>
                  <td className="num">{num(t.reviewed_accepted_wrong)}</td>
                  <td className="num">{t.issued_count ? ((100 * t.issued_accepted) / t.issued_count).toFixed(0) + " %" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3>Nächste Spiele (lokal) · 3×-Phase ab {new Date(d.mult_start).toLocaleTimeString("de-DE")} Uhr</h3>
        {d.upcoming.map((g) => (
          <span key={g.id} className="badge b-blue" style={{ marginRight: 8 }}>
            #{g.id} · {new Date(g.start_time).toLocaleTimeString("de-DE")}
          </span>
        ))}
        <span style={{ marginLeft: 8 }}><Link to="/games">alle Spiele →</Link></span>
      </div>
    </div>
  );
}

function Bucket({ label, v, sub }: { label: string; v: number; sub: string }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="value neg">{eur(v)}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

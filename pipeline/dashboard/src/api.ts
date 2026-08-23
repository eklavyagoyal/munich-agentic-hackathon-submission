export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export const eur = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : v.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits }) + " €";

export const num = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : v.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const pct = (v: number | null | undefined) => (v == null ? "—" : (100 * v).toFixed(1) + " %");

export const cls = (v: number | null | undefined) => (v == null ? "" : v >= 0 ? "pos" : "neg");

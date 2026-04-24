import Link from "next/link";
import type { BuildingSummary } from "@/lib/types";

function money(v: number | null) {
  return v == null ? "—" : `$${Math.round(v).toLocaleString()}`;
}

export function BuildingsTable({ rows }: { rows: BuildingSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-navy text-paper">
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">Building</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Units</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Rent range</th>
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">Incentive</th>
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b, i) => (
            <tr
              key={b.id}
              className="reveal border-b border-rule last:border-b-0 hover:bg-[#f2eee6] transition-colors"
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <td className="px-4 py-3">
                <Link
                  href={`/buildings/${b.id}`}
                  className="font-medium text-navy hover:underline underline-offset-4"
                >
                  {b.name}
                </Link>
                <div className="text-xs text-muted mt-0.5">{b.address}</div>
              </td>
              <td className="px-4 py-3 text-right tabular">{b.total_units}</td>
              <td className="px-4 py-3 text-right tabular">
                {b.rent_min ? `${money(b.rent_min)}–${money(b.rent_max)}` : "—"}
              </td>
              <td className="px-4 py-3">
                {b.has_incentive ? (
                  <span className="inline-block px-2 py-0.5 bg-rust text-paper text-[0.7rem] uppercase tracking-[0.15em]">
                    Active
                  </span>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                {b.last_scrape_status === "success" ? (
                  <span className="text-[#2a7a3a]">Success</span>
                ) : b.last_scrape_status === "failed" ? (
                  <span
                    className="text-rust"
                    title={b.last_scrape_error || undefined}
                  >
                    Failed
                  </span>
                ) : (
                  <span className="text-muted">{b.last_scrape_status}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

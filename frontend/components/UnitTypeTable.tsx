import type { UnitTypeAggregate } from "@/lib/types";

function money(v: number | null) {
  return v == null ? "—" : `$${Math.round(v).toLocaleString()}`;
}

export function UnitTypeTable({ rows }: { rows: UnitTypeAggregate[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-navy text-paper">
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">Type</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Available</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide" title="Buildings currently listing a unit of this type">Bldgs listing</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Rent min</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Rent avg</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Rent max</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Sqft range</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.unit_type}
              className="reveal border-b border-rule last:border-b-0"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <td className="px-4 py-3 font-medium capitalize">{r.unit_type}</td>
              <td className="px-4 py-3 text-right tabular">{r.total_available}</td>
              <td className="px-4 py-3 text-right tabular">{r.buildings_count}</td>
              <td className="px-4 py-3 text-right tabular">{money(r.rent_min)}</td>
              <td className="px-4 py-3 text-right tabular">{money(r.rent_avg)}</td>
              <td className="px-4 py-3 text-right tabular">{money(r.rent_max)}</td>
              <td className="px-4 py-3 text-right tabular">
                {r.sqft_min && r.sqft_max ? `${r.sqft_min}–${r.sqft_max}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

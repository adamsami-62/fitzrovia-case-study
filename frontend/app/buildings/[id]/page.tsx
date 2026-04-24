"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import { Shell } from "@/components/Shell";
import { StatCard } from "@/components/StatCard";
import { IncentiveBlock } from "@/components/IncentiveBlock";
import { ChatBubble } from "@/components/ChatBubble";
import type { BuildingDetail, UnitOut } from "@/lib/types";

function money(v: number | null | undefined) {
  return v == null ? "—" : `$${Math.round(v).toLocaleString()}`;
}

export default function BuildingPage({ params }: { params: { id: string } }) {
  const { ready } = useAuthGuard();
  const [data, setData] = useState<BuildingDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [unitType, setUnitType] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  async function onPdf() {
    if (!data) return;
    setPdfLoading(true);
    try {
      const url = await api.buildingPdfUrl(data.id);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fitzrovia-${data.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "PDF failed");
    } finally {
      setPdfLoading(false);
    }
  }

  useEffect(() => {
    if (!ready) return;
    api.building(Number(params.id))
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Load failed"));
  }, [ready, params.id]);

  const unitTypes = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.units.map((u) => u.unit_type))).sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    if (!unitType) return data.units;
    return data.units.filter((u) => u.unit_type === unitType);
  }, [data, unitType]);

  if (!ready) return null;

  return (
    <Shell>
      <div className="mb-2 flex items-center justify-between">
        <Link
          href="/dashboard"
          className="text-sm text-muted hover:text-ink underline underline-offset-4"
        >
          ← Dashboard
        </Link>
        {data && (
          <button
            onClick={onPdf}
            disabled={pdfLoading}
            className="px-3 py-1.5 border border-navy text-navy hover:bg-navy hover:text-paper transition-colors text-xs font-medium tracking-wide"
          >
            {pdfLoading ? "Preparing…" : "Export PDF"}
          </button>
        )}
      </div>

      {err && (
        <div className="px-4 py-2.5 border-l-2 border-rust bg-rust/10 text-sm">
          {err}
        </div>
      )}

      {!data ? (
        <div className="text-muted text-sm">Loading…</div>
      ) : (
        <>
          <div className="mb-8">
            <div className="text-[0.7rem] uppercase tracking-[0.2em] text-muted mb-2">
              Building
            </div>
            <h1 className="font-display text-display-lg text-navy">{data.name}</h1>
            <div className="text-sm text-muted mt-2">
              {data.address}
              
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-10">
            <StatCard label="Available units" value={data.total_units} />
            <StatCard label="Rent min" value={money(data.rent_min)} />
            <StatCard label="Rent avg" value={money(data.rent_avg)} />
            <StatCard label="Rent max" value={money(data.rent_max)} />
          </div>

          <IncentiveBlock b={data} />

          {unitTypes.length > 1 && (
            <div className="flex flex-wrap items-center gap-2 text-xs mb-4 mt-8">
              <span className="uppercase tracking-[0.18em] text-muted">Type</span>
              <FilterChip active={unitType === null} onClick={() => setUnitType(null)}>
                All
              </FilterChip>
              {unitTypes.map((t) => (
                <FilterChip key={t} active={unitType === t} onClick={() => setUnitType(t)}>
                  {t}
                </FilterChip>
              ))}
            </div>
          )}

          <UnitsTable units={filtered} listingType={data.units[0]?.listing_type} />
        </>
      )}
      <ChatBubble />
    </Shell>
  );
}

function FilterChip({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={[
        "px-3 py-1 border transition-colors",
        active
          ? "bg-navy text-paper border-navy"
          : "bg-transparent text-ink border-rule hover:border-navy",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function UnitsTable({ units, listingType }: { units: UnitOut[]; listingType?: string }) {
  if (units.length === 0) {
    return (
      <div className="text-sm text-muted">
        No available units match this filter.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-navy text-paper">
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">
              {listingType === "floorplan_template" ? "Floorplan" : "Unit"}
            </th>
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">Type</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Rent</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Sqft</th>
            <th className="text-right px-4 py-2.5 font-medium tracking-wide">Floor</th>
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">Available</th>
            <th className="text-left px-4 py-2.5 font-medium tracking-wide">Source</th>
          </tr>
        </thead>
        <tbody>
          {units.map((u, i) => (
            <tr
              key={u.id}
              className="reveal border-b border-rule last:border-b-0"
              style={{ animationDelay: `${Math.min(i, 20) * 20}ms` }}
            >
              <td className="px-4 py-2.5 font-medium">{u.unit_identifier}</td>
              <td className="px-4 py-2.5 capitalize">{u.unit_type}</td>
              <td className="px-4 py-2.5 text-right tabular">${Math.round(u.rent).toLocaleString()}</td>
              <td className="px-4 py-2.5 text-right tabular">{u.sqft ?? "—"}</td>
              <td className="px-4 py-2.5 text-right tabular">{u.floor ?? "—"}</td>
              <td className="px-4 py-2.5">{u.available_date ?? "—"}</td>
              <td className="px-4 py-2.5">
                {u.listing_url ? (
                  <a
                    href={u.listing_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-muted hover:text-ink underline underline-offset-4"
                  >
                    Link
                  </a>
                ) : (
                  <span className="text-muted text-xs">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

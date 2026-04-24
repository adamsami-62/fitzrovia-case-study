"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import { Shell } from "@/components/Shell";
import { StatCard } from "@/components/StatCard";
import { UnitTypeTable } from "@/components/UnitTypeTable";
import { BuildingsTable } from "@/components/BuildingsTable";
import { Filters } from "@/components/Filters";
import { IncentiveBlock } from "@/components/IncentiveBlock";
import { ChatBubble } from "@/components/ChatBubble";
import type { DashboardResponse, ScrapeRunStatus } from "@/lib/types";

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-CA", {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function DashboardPage() {
  const { ready, role } = useAuthGuard();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [scraping, setScraping] = useState(false);
  const [scrapeMsg, setScrapeMsg] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Filters
  const [unitType, setUnitType] = useState<string | null>(null);

  async function load() {
    try {
      setData(await api.dashboard());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    }
  }

  useEffect(() => { if (ready) load(); }, [ready]);

  async function onScrape() {
    if (!confirm("Run a live scrape now? Takes 1 to 3 minutes. You can leave this page and come back.")) return;
    setScraping(true);
    setScrapeMsg("Starting scrape...");
    try {
      const kickoff = await api.triggerScrape();
      setScrapeMsg(`Run ${kickoff.run_id} started. Polling for progress...`);

      // Poll every 2 seconds until done. ~90 tries = 3 minutes max.
      let status: ScrapeRunStatus | null = null;
      for (let i = 0; i < 120; i++) {
        await new Promise((res) => setTimeout(res, 2000));
        try {
          status = await api.pollScrapeRun(kickoff.run_id);
        } catch (pollErr) {
          // Transient network blip during a long scrape; keep trying.
          continue;
        }
        if (status.is_complete) break;
        const elapsed = Math.round(status.elapsed_seconds);
        setScrapeMsg(
          `Scraping in progress... ${elapsed}s elapsed, ${status.buildings_succeeded}/${status.buildings_attempted} buildings done so far.`
        );
      }

      if (status && status.is_complete) {
        setScrapeMsg(
          `Run ${status.run_id} ${status.status}. ${status.buildings_succeeded}/${status.buildings_attempted} buildings, ${status.total_units_found} units, ${status.elapsed_seconds}s.`
        );
        await load();
      } else {
        setScrapeMsg("Scrape is taking longer than expected. Refresh the page in a few minutes to see results.");
      }
    } catch (e) {
      setScrapeMsg(e instanceof Error ? e.message : "Scrape failed");
    } finally {
      setScraping(false);
    }
  }

  async function onPdf() {
    setPdfLoading(true);
    try {
      const url = await api.pdfUrl();
      const a = document.createElement("a");
      a.href = url;
      a.download = `fitzrovia-comp-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
    } catch (e) {
      setScrapeMsg(e instanceof Error ? e.message : "PDF failed");
    } finally {
      setPdfLoading(false);
    }
  }

  // Apply filters to the building list + aggregates
  const allUnitTypes = useMemo(
    () => data?.by_unit_type.map((r) => r.unit_type) ?? [],
    [data]
  );
  const filteredBuildings = useMemo(() => {
    if (!data) return [];
    if (!unitType) return data.buildings;
    return data.buildings.filter((b) => unitType in b.units_by_type);
  }, [data, unitType]);

  const filteredUnitTypeRows = useMemo(() => {
    if (!data) return [];
    if (!unitType) return data.by_unit_type;
    return data.by_unit_type.filter((r) => r.unit_type === unitType);
  }, [data, unitType]);

  const incentiveBuildings = useMemo(
    () => filteredBuildings.filter((b) => b.has_incentive),
    [filteredBuildings]
  );

  if (!ready) return null;

  return (
    <Shell>
      {/* Page head */}
      <div className="flex flex-wrap items-end justify-between gap-6 mb-8">
        <div>
          <div className="text-[0.7rem] uppercase tracking-[0.2em] text-muted mb-2">
            Dashboard
          </div>
          <h1 className="font-display text-display-xl text-navy">
            Midtown <span className="italic">comp.</span>
          </h1>
          <div className="text-sm text-muted mt-2">
            Last scrape: {fmtDate(data?.last_run_finished_at ?? null)}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onPdf}
            disabled={pdfLoading || !data}
            className="px-4 py-2.5 border border-navy text-navy hover:bg-navy hover:text-paper transition-colors text-sm font-medium tracking-wide"
          >
            {pdfLoading ? "Preparing PDF…" : "Export PDF"}
          </button>
          {role === "admin" && (
            <button
              onClick={onScrape}
              disabled={scraping}
              className="px-4 py-2.5 bg-rust text-paper hover:bg-ink transition-colors text-sm font-medium tracking-wide"
            >
              {scraping ? "Scraping…" : "Scrape now"}
            </button>
          )}
        </div>
      </div>

      {scrapeMsg && (
        <div className="mb-6 px-4 py-2.5 border-l-2 border-navy bg-[#eee9de] text-sm">
          {scrapeMsg}
        </div>
      )}

      {err && (
        <div className="mb-6 px-4 py-2.5 border-l-2 border-rust bg-rust/10 text-sm">
          {err}
        </div>
      )}

      {!data ? (
        <div className="text-muted text-sm">Loading…</div>
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-6 mb-10">
            <StatCard label="Available units" value={data.total_units} />
            <StatCard label="Buildings" value={data.total_buildings} />
            <StatCard
              label="Scrapes OK"
              value={`${data.buildings_succeeded}/${data.total_buildings}`}
              sub={data.buildings_failed ? `${data.buildings_failed} failed` : undefined}
            />
            <StatCard label="With incentives" value={data.buildings_with_incentives} />
            <StatCard label="Unit categories" value={data.by_unit_type.length} />
          </div>

          {/* Filters */}
          <div className="mb-6">
            <Filters
              allUnitTypes={allUnitTypes}
              unitType={unitType}
              onUnitType={setUnitType}
            />
          </div>

          {/* By unit type */}
          <section className="mb-12">
            <h2 className="font-display text-2xl text-navy mb-3">
              Summary by unit type
            </h2>
            <UnitTypeTable rows={filteredUnitTypeRows} />
          </section>

          {/* Buildings */}
          <section className="mb-12">
            <h2 className="font-display text-2xl text-navy mb-3">
              By building
            </h2>
            <BuildingsTable rows={filteredBuildings} />
          </section>

          {/* Active incentives */}
          {incentiveBuildings.length > 0 && (
            <section>
              <h2 className="font-display text-2xl text-navy mb-3">
                Active incentives
              </h2>
              {incentiveBuildings.map((b) => (
                <div key={b.id}>
                  <div className="font-medium text-navy mt-3">{b.name}</div>
                  <IncentiveBlock b={b} />
                </div>
              ))}
            </section>
          )}
        </>
      )}
      <ChatBubble />
    </Shell>
  );
}

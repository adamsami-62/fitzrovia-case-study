import type { BuildingSummary } from "@/lib/types";

type ParsedIncentive = { promos?: any[]; _ok?: boolean } | null;

export function IncentiveBlock({ b }: { b: BuildingSummary }) {
  if (!b.has_incentive || !b.incentive_raw) return null;
  const parsed = b.incentive_parsed as ParsedIncentive;

  return (
    <div className="border-l-2 border-rust bg-[#fef7ed] px-5 py-4 my-3">
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-[0.7rem] uppercase tracking-[0.18em] text-rust font-medium">
          Active promotion
        </div>
        {b.incentive_source_url && (
          <a
            href={b.incentive_source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-muted hover:text-ink underline underline-offset-4"
          >
            Source
          </a>
        )}
      </div>
      <div className="text-sm whitespace-pre-wrap font-sans">{b.incentive_raw}</div>
      {parsed && parsed._ok && Array.isArray(parsed.promos) && parsed.promos.length > 0 && (
        <div className="mt-3 pt-3 border-t border-rust/20">
          <div className="text-[0.7rem] uppercase tracking-[0.18em] text-muted mb-2">
            Structured
          </div>
          <pre className="text-xs font-mono overflow-x-auto text-ink">
            {JSON.stringify(parsed.promos, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

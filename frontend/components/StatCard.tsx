export function StatCard({
  label, value, sub,
}: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border-l-2 border-rust pl-4 py-1">
      <div className="font-display text-3xl text-navy tabular">{value}</div>
      <div className="text-[0.7rem] uppercase tracking-[0.18em] text-muted mt-1">
        {label}
      </div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

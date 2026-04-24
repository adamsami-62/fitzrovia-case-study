"use client";

type Props = {
  allUnitTypes: string[];
  unitType: string | null;
  onUnitType: (v: string | null) => void;
};

export function Filters({ allUnitTypes, unitType, onUnitType }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="uppercase tracking-[0.18em] text-muted">Type</span>
      <Chip active={unitType === null} onClick={() => onUnitType(null)}>All</Chip>
      {allUnitTypes.map((t) => (
        <Chip key={t} active={unitType === t} onClick={() => onUnitType(t)}>
          {t}
        </Chip>
      ))}
    </div>
  );
}

function Chip({
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

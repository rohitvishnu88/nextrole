export function scoreBand(score: number): "blue" | "yellow" | "red" {
  if (score >= 70) return "blue";
  if (score >= 45) return "yellow";
  return "red";
}

const fill = { blue: "bg-blue", yellow: "bg-yellow", red: "bg-red" } as const;

export function ScoreMarker({ score, large = false }: { score: number | null; large?: boolean }) {
  if (score === null) return <span className="text-ink-muted">—</span>;
  return (
    <span className={`inline-flex items-center gap-2 font-bold ${large ? "text-4xl" : "text-sm"}`}>
      <span aria-hidden className={`${large ? "w-4 h-4" : "w-2.5 h-2.5"} shrink-0 ${fill[scoreBand(score)]}`} />
      {score}
    </span>
  );
}

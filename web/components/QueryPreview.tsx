import type { Signal } from "@/lib/types";

interface Props {
  signals: Signal[];
}

function buildQueries(signals: Signal[]): string[] {
  const active = signals.filter(s => s.active);

  const roles     = active.filter(s => s.category === "roles").map(s => s.label).slice(0, 4);
  const skills    = active.filter(s => s.category === "skills").map(s => s.label).slice(0, 3);
  const locations = active.filter(s => s.category === "location").map(s => s.label).slice(0, 2);

  if (roles.length === 0) return ["No active role signals — enable at least one role."];

  const loc    = locations.length > 0 ? locations[0] : "UK";
  const skill1 = skills[0] ?? "";
  const skill2 = skills[1] ?? "";

  const queries: string[] = [];

  if (roles[0]) queries.push(
    `site:linkedin.com/jobs/view "${roles[0]}" ${skill1} ${loc}`.trim()
  );
  if (roles[1]) queries.push(
    `site:linkedin.com/jobs/view "${roles[1]}" ${skill2} ${loc}`.trim()
  );
  if (roles[0]) queries.push(
    `site:linkedin.com/jobs/search keywords="${roles[0]}" location=${loc} f_TPR=r432000`
  );
  if (roles[2]) queries.push(
    `site:linkedin.com/jobs/view "${roles[2]}" ${skill1} ${loc} f_TPR=r432000`.trim()
  );
  if (skill1 && roles[0]) queries.push(
    `site:linkedin.com/jobs/view ${skill1} architect ${loc}`.trim()
  );

  return queries.slice(0, 5);
}

export function QueryPreview({ signals }: Props) {
  const queries     = buildQueries(signals);
  const activeCount = signals.filter(s => s.active).length;

  return (
    <div className="bg-white rounded-2xl border border-warm-border p-5 sticky top-24">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-navy text-sm">Live Query Preview</h3>
        <span className="text-xs text-muted bg-cream px-2 py-0.5 rounded-full border border-warm-border">
          {activeCount} active
        </span>
      </div>

      <p className="text-xs text-muted mb-4 leading-relaxed">
        The job search agent constructs queries like these from your active signals.
        Toggle signals to see them update.
      </p>

      <div className="space-y-2">
        {queries.map((q, i) => (
          <div key={i} className="bg-gray-950 rounded-xl px-3 py-2.5">
            <p className="text-green-400 text-xs font-mono leading-relaxed break-all">{q}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-warm-border flex gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
          High confidence
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-yellow-400 shrink-0" />
          Inferred
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-gray-300 shrink-0" />
          Default
        </span>
      </div>
    </div>
  );
}

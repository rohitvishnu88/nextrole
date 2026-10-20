import type { ChangeEntry, FabricationFlag } from "@/lib/types";
import { SectionTitle, Square, prettyLocation } from "./shared";

export function ChangesList({ changes, flags }: { changes: ChangeEntry[]; flags: FabricationFlag[] }) {
  const ordered = [...changes].sort((a, b) => Number(b.needs_confirmation) - Number(a.needs_confirmation));
  return (
    <section>
      <SectionTitle>changes</SectionTitle>
      {flags.length > 0 && (
        <div className="mb-4">
          <p className="text-sm font-bold mb-1">not in your base resume — confirm these are true</p>
          {flags.map((flag, i) => (
            <div key={i} className="flex gap-2 text-sm py-1">
              <Square colour="red" />
              <span><span className="font-bold">{flag.text}</span> <span className="text-ink-muted">· {flag.kind} · {prettyLocation(flag.location)}</span></span>
            </div>
          ))}
        </div>
      )}
      {ordered.length === 0 && <p className="text-sm text-ink-muted">No change log for this run.</p>}
      {ordered.map((change, i) => (
        <div key={i} className="flex gap-2 border-t border-rule-soft py-2.5 text-sm">
          <Square colour={change.needs_confirmation ? "red" : "ink"} />
          <div className="min-w-0 space-y-1">
            <p className="text-xs text-ink-muted">
              {change.kind} · {prettyLocation(change.location)}{change.needs_confirmation ? " · confirm this is accurate" : ""}
            </p>
            {change.before && <p className="text-ink-muted line-through">{change.before}</p>}
            <p>{change.after}</p>
            {change.reason && <p className="text-xs text-ink-muted">{change.reason}</p>}
          </div>
        </div>
      ))}
    </section>
  );
}

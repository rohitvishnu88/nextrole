"use client";
import { useUsage, formatResetDate } from "@/lib/useUsage";
import type { MeteredAction } from "@/lib/types";

const LABELS: Record<MeteredAction, string> = {
  job_search: "job searches",
  tailor: "tailored resumes",
  analyse: "job analyses",
  section_draft: "AI section drafts",
  resume_parse: "resume uploads",
  search_brief: "search briefs",
};

function money(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

export default function UsagePage() {
  const { usage } = useUsage();
  if (!usage) return <p className="text-sm text-ink-muted">loading…</p>;
  const resets = formatResetDate(usage.resets_on);

  return (
    <div className="space-y-12">
      <div>
        <h1 className="text-5xl font-bold text-ink leading-none">usage</h1>
        <p className="text-sm text-ink-muted mt-3">Allowances reset on {resets}.</p>
      </div>

      {usage.paused && (
        <p className="text-sm bg-red/10 border-l-[3px] border-red px-3 py-2">
          AI features are paused for everyone until {resets} — this month&apos;s budget has been used.
        </p>
      )}

      <section>
        <h2 className="text-xl font-bold border-b-[1.5px] border-ink pb-1">this month</h2>
        {(Object.keys(LABELS) as MeteredAction[]).map(action => {
          const a = usage.actions[action];
          const exhausted = a.limit !== null && a.used >= a.limit;
          return (
            <div key={action} className="flex items-center justify-between py-3 border-t border-rule-soft text-sm">
              <span className="flex items-center gap-2">
                <span aria-hidden className={`w-2.5 h-2.5 ${exhausted ? "bg-red" : "bg-ink"}`} />
                {LABELS[action]}
              </span>
              <span className={exhausted ? "font-bold" : ""}>
                {a.limit === null ? `${a.used} used · no limit` : `used ${a.used} of ${a.limit} · resets ${resets}`}
              </span>
            </div>
          );
        })}
      </section>

      {usage.owner && (
        <>
          <section className="border-l-[3px] border-ink px-4 py-1">
            <p className="text-4xl font-bold leading-none">{money(usage.owner.spent_usd)}</p>
            <p className="text-sm mt-1">spent of {money(usage.owner.budget_usd)} this month, everyone included</p>
          </section>

          <section>
            <h2 className="text-xl font-bold border-b-[1.5px] border-ink pb-1">by person</h2>
            {usage.owner.by_user.length === 0 && <p className="py-3 text-sm text-ink-muted">No AI usage yet this month.</p>}
            {usage.owner.by_user.map(u => (
              <div key={u.email} className="flex items-center justify-between gap-4 py-3 border-t border-rule-soft text-sm">
                <span className="truncate">{u.email}</span>
                <span className="text-ink-muted shrink-0">
                  {Object.entries(u.counts).map(([action, n]) => `${n} ${LABELS[action as MeteredAction] ?? action}`).join(" · ")}
                </span>
                <span className="font-bold shrink-0">{money(u.spent_usd)}</span>
              </div>
            ))}
          </section>

          <section>
            <h2 className="text-xl font-bold border-b-[1.5px] border-ink pb-1">by action</h2>
            {Object.entries(usage.owner.by_action).map(([action, usd]) => (
              <div key={action} className="flex items-center justify-between py-3 border-t border-rule-soft text-sm">
                <span>{LABELS[action as MeteredAction] ?? action}</span>
                <span className="font-bold">{money(usd)}</span>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}

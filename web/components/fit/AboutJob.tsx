import type { JobAnalysis } from "@/lib/types";
import { SectionTitle, Square } from "./shared";

export function LeftOff({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <SectionTitle>left off?</SectionTitle>
      <p className="text-xs text-ink-muted mb-2">If any of these are true, add them on your profile&apos;s edit page.</p>
      <ul className="space-y-1">
        {items.map((q, i) => <li key={i} className="flex gap-2 text-sm"><Square colour="ink" />{q}</li>)}
      </ul>
    </section>
  );
}

export function AboutJob({ analysis }: { analysis: JobAnalysis }) {
  return (
    <section className="space-y-3 text-sm">
      <SectionTitle>about this job</SectionTitle>
      <div>
        <p className="font-bold">what it really is</p>
        <p>{analysis.what_it_really_is}</p>
      </div>
      <div>
        <p className="font-bold">problem they&apos;re hiring to solve</p>
        <p>{analysis.problem_being_solved}</p>
      </div>
      {analysis.suspicious.length > 0 && (
        <div>
          <p className="font-bold">suspicious</p>
          <ul className="space-y-1">
            {analysis.suspicious.map((s, i) => <li key={i} className="flex gap-2"><Square colour="red" />{s}</li>)}
          </ul>
        </div>
      )}
      {analysis.search_terms.length > 0 && (
        <p><span className="font-bold">search terms:</span> {analysis.search_terms.join(", ")}</p>
      )}
    </section>
  );
}

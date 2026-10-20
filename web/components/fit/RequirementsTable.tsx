import type { Requirement } from "@/lib/types";
import { MEETS_COLOUR, SectionTitle, Square } from "./shared";

export function RequirementsTable({ requirements }: { requirements: Requirement[] }) {
  if (requirements.length === 0) return null;
  return (
    <section>
      <SectionTitle>requirements</SectionTitle>
      <div className="grid grid-cols-[1.5rem_minmax(0,1fr)_4rem_4.5rem] text-xs font-bold pb-1">
        <span>#</span><span>requirement</span><span>filter</span><span>you</span>
      </div>
      {requirements.map((req, i) => (
        <div key={i} className="border-t border-rule-soft py-2.5 text-sm">
          <div className="grid grid-cols-[1.5rem_minmax(0,1fr)_4rem_4.5rem] items-start">
            <span className="text-ink-muted">{i + 1}</span>
            <span className={req.filter_likelihood === "filler" ? "text-ink-muted" : ""}>{req.text}</span>
            <span className="text-ink-muted">{req.filter_likelihood}</span>
            <span className="flex gap-2"><Square colour={MEETS_COLOUR[req.meets]} />{req.meets}</span>
          </div>
          {(req.evidence || req.interview_answer) && (
            <details className="ml-8 mt-1">
              <summary className="cursor-pointer text-xs text-ink-muted">evidence and interview answer</summary>
              {req.evidence && <p className="mt-1 text-xs"><span className="font-bold">evidence:</span> {req.evidence}</p>}
              {req.interview_answer && <p className="mt-1 text-xs"><span className="font-bold">in interview:</span> {req.interview_answer}</p>}
            </details>
          )}
        </div>
      ))}
    </section>
  );
}

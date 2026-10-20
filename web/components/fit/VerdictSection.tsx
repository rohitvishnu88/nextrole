import type { JobAnalysis } from "@/lib/types";
import { ScoreMarker } from "@/components/ui/ScoreMarker";
import { SectionTitle, Square } from "./shared";

export function VerdictSection({ analysis }: { analysis: JobAnalysis }) {
  return (
    <section>
      <SectionTitle>verdict</SectionTitle>
      <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
        <ScoreMarker score={analysis.match_score} large />
        <div className="space-y-1">
          <p className="font-bold">{analysis.verdict}</p>
          <p className="text-sm">{analysis.verdict_reason}</p>
        </div>
      </div>
      {analysis.gaps_that_matter.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-bold mb-1">gaps that matter</p>
          <ul className="space-y-1">
            {analysis.gaps_that_matter.map((gap, i) => (
              <li key={i} className="flex gap-2 text-sm"><Square colour="red" />{gap}</li>
            ))}
          </ul>
        </div>
      )}
      {analysis.gaps_that_dont.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-bold">gaps that don&apos;t matter ({analysis.gaps_that_dont.length})</summary>
          <ul className="mt-1 space-y-1">
            {analysis.gaps_that_dont.map((gap, i) => (
              <li key={i} className="flex gap-2"><Square colour="ink" />{gap}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

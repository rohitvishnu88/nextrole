import type { AtsResult } from "@/lib/types";
import { SectionTitle, Square } from "./shared";

function Check({ ok, label }: { ok: boolean; label: string }) {
  return <li className="flex gap-2 text-sm"><Square colour={ok ? "blue" : "red"} />{label}{ok ? "" : " — not found"}</li>;
}

export function AtsView({ ats }: { ats: AtsResult }) {
  if (!ats.contact) return null;
  return (
    <section>
      <SectionTitle>ats view</SectionTitle>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <ul className="space-y-1">
          <Check ok={ats.contact.email} label="email" />
          <Check ok={ats.contact.phone} label="phone" />
          {Object.entries(ats.headings).map(([h, ok]) => <Check key={h} ok={ok} label={`${h} heading`} />)}
        </ul>
        <ul className="space-y-1">
          {ats.terms.map(t => <Check key={t.term} ok={t.present} label={t.term} />)}
        </ul>
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-sm font-bold">text an ats extracts from the pdf</summary>
        <pre className="mt-2 font-mono text-xs bg-surface border border-rule-soft p-3 whitespace-pre-wrap max-h-80 overflow-y-auto">{ats.text}</pre>
      </details>
    </section>
  );
}

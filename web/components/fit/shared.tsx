import type { Meets } from "@/lib/types";

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-xl font-bold border-b-[1.5px] border-ink pb-1 mb-3">{children}</h2>;
}

export function Square({ colour }: { colour: "blue" | "yellow" | "red" | "ink" }) {
  const fill = { blue: "bg-blue", yellow: "bg-yellow", red: "bg-red", ink: "bg-ink" }[colour];
  return <span aria-hidden className={`inline-block w-2.5 h-2.5 shrink-0 mt-1.5 ${fill}`} />;
}

export const MEETS_COLOUR: Record<Meets, "blue" | "yellow" | "red"> = { yes: "blue", partly: "yellow", no: "red" };

export function prettyLocation(location: string): string {
  const m = location.match(/^experience\[(\d+)\]\.description\[(\d+)\]$/);
  if (m) return `role ${Number(m[1]) + 1}, bullet ${Number(m[2]) + 1}`;
  const role = location.match(/^experience\[(\d+)\]$/);
  if (role) return `role ${Number(role[1]) + 1}`;
  return location;
}

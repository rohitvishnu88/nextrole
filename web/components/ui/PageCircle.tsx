const fill = { blue: "bg-blue", yellow: "bg-yellow", red: "bg-red" } as const;

// The one Bauhaus shape per page. Parent must be `relative overflow-hidden`.
export function PageCircle({ colour = "blue" }: { colour?: keyof typeof fill }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute -right-24 -top-32 w-[340px] h-[340px] rounded-full ${fill[colour]}`}
    />
  );
}

export function greeting(now: Date): "good morning" | "good afternoon" | "good evening" {
  const hour = now.getHours();
  if (hour < 12) return "good morning";
  if (hour < 18) return "good afternoon";
  return "good evening";
}

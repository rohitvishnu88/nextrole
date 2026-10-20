"use client";

interface Props {
  value: Record<string, unknown> | string;
  onChange: (next: Record<string, unknown> | string) => void;
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every(x => typeof x === "string");
}

export function EditableItemForm({ value, onChange }: Props) {
  if (typeof value === "string") {
    return (
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={4}
        className="w-full text-sm border border-rule-soft p-2 focus:outline-none focus:ring-1 focus:ring-ink"
      />
    );
  }

  return (
    <div className="space-y-2">
      {Object.entries(value).map(([key, fieldValue]) => (
        <div key={key}>
          <label className="block text-xs font-medium text-ink-muted mb-0.5">{key}</label>
          {isStringArray(fieldValue) ? (
            <textarea
              value={fieldValue.join("\n")}
              onChange={e => onChange({ ...value, [key]: e.target.value.split("\n") })}
              rows={Math.max(2, fieldValue.length)}
              className="w-full text-sm border border-rule-soft p-2 focus:outline-none focus:ring-1 focus:ring-ink"
            />
          ) : (
            <input
              value={String(fieldValue ?? "")}
              onChange={e => onChange({ ...value, [key]: e.target.value })}
              className="w-full text-sm border border-rule-soft p-2 focus:outline-none focus:ring-1 focus:ring-ink"
            />
          )}
        </div>
      ))}
    </div>
  );
}

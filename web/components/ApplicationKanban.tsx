"use client";
import { useState } from "react";
import {
  DndContext, DragEndEvent, DragOverlay, DragStartEvent,
  PointerSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Application, ApplicationStatus } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import * as api from "@/lib/api";

const COLUMNS: ApplicationStatus[] = ["saved", "applied", "interview", "offer", "rejected"];
const COL_LABELS: Record<ApplicationStatus, string> = {
  saved: "Saved", applied: "Applied", interview: "Interview", offer: "Offer", rejected: "Rejected",
};
const COL_COLOURS: Record<ApplicationStatus, string> = {
  saved:     "bg-cream border-warm-border",
  applied:   "bg-accent-light border-accent/20",
  interview: "bg-yellow-50 border-yellow-100",
  offer:     "bg-green-soft border-green-200",
  rejected:  "bg-red-50 border-red-100",
};

function KanbanCard({ app, isDragging }: { app: Application; isDragging?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: app.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="bg-white rounded-xl px-3.5 py-3 border border-warm-border shadow-sm cursor-grab active:cursor-grabbing"
    >
      <p className="text-sm font-semibold text-navy truncate">{app.company}</p>
      <p className="text-xs text-muted truncate mt-0.5">{app.job_title}</p>
      {app.applied_date && <p className="text-xs text-muted/70 mt-1.5">{app.applied_date}</p>}
    </div>
  );
}

interface Props { apps: Application[]; onRefresh: () => void; }

export function ApplicationKanban({ apps, onRefresh }: Props) {
  const [activeApp, setActiveApp] = useState<Application | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const byStatus = (status: ApplicationStatus) => apps.filter(a => a.status === status);

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveApp(null);
    if (!over) return;
    const newStatus = over.id as ApplicationStatus;
    if (!COLUMNS.includes(newStatus)) return;
    const app = apps.find(a => a.id === active.id);
    if (!app || app.status === newStatus) return;
    await api.updateApplication(app.id, { status: newStatus });
    onRefresh();
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveApp(apps.find(a => a.id === event.active.id) ?? null);
  }

  return (
    <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="flex gap-3 overflow-x-auto pb-4">
        {COLUMNS.map(col => {
          const colApps = byStatus(col);
          return (
            <div key={col} className="flex-shrink-0 w-52">
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-semibold text-muted uppercase tracking-wide">{COL_LABELS[col]}</span>
                <span className="text-xs text-muted bg-cream border border-warm-border rounded-full px-2 py-0.5">{colApps.length}</span>
              </div>
              <SortableContext id={col} items={colApps.map(a => a.id)} strategy={verticalListSortingStrategy}>
                <div className={`min-h-24 rounded-2xl border p-2 space-y-2 ${COL_COLOURS[col]}`} id={col}>
                  {colApps.map(app => (
                    <KanbanCard key={app.id} app={app} isDragging={activeApp?.id === app.id} />
                  ))}
                </div>
              </SortableContext>
            </div>
          );
        })}
      </div>
      <DragOverlay>
        {activeApp && (
          <div className="bg-white rounded-xl px-3.5 py-3 border border-accent/30 shadow-lg w-52">
            <p className="text-sm font-semibold text-navy">{activeApp.company}</p>
            <p className="text-xs text-muted mt-0.5">{activeApp.job_title}</p>
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}

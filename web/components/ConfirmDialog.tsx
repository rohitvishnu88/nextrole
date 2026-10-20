"use client";
import { createPortal } from "react-dom";

interface Props {
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

// A real in-app modal, not window.confirm() - browsers silently suppress
// confirm()/alert() after a page has shown several of them (or once the user
// checks "prevent this page from creating additional dialogs"), after which
// every future call resolves to `false` with no visible popup at all. That
// makes any confirm()-gated action look broken with zero feedback.
export function ConfirmDialog({ message, confirmLabel = "Delete", onConfirm, onCancel }: Props) {
  return createPortal(
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-5" onClick={e => e.stopPropagation()}>
        <p className="text-sm text-gray-700 mb-4">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="text-sm text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="text-sm bg-red-500 text-white rounded-lg px-3 py-1.5 hover:bg-red-600 transition-colors"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

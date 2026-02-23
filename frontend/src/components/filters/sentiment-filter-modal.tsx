"use client";

import { useState, useMemo } from "react";
import { X } from "lucide-react";

const SENTIMENTS = [
  { value: "Positive", color: "bg-green-500" },
  { value: "Neutral", color: "bg-yellow-500" },
  { value: "Negative", color: "bg-red-500" },
];

interface Props {
  open: boolean;
  selected: string[];
  onApply: (sentiments: string[]) => void;
  onClose: () => void;
}

export function SentimentFilterModal({
  open,
  selected,
  onApply,
  onClose,
}: Props) {
  const [local, setLocal] = useState<string[]>(selected);

  useMemo(() => {
    if (open) setLocal(selected);
  }, [open, selected]);

  if (!open) return null;

  const toggle = (val: string) =>
    setLocal((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val]
    );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[25vh]">
      <div className="fixed inset-0 bg-black/20" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl w-[320px]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Sentiment</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Options */}
        <div className="px-5 py-4 space-y-3">
          {SENTIMENTS.map((s) => (
            <label
              key={s.value}
              className="flex items-center gap-3 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={local.includes(s.value)}
                onChange={() => toggle(s.value)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className={`w-2.5 h-2.5 rounded-full ${s.color}`} />
              <span className="text-sm text-gray-700">{s.value}</span>
            </label>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-100 px-5 py-3 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 font-medium transition"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onApply(local);
              onClose();
            }}
            className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}

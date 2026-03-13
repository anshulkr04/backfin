"use client";

import { format, parseISO } from "date-fns";
import { Bookmark, Share2, ExternalLink } from "lucide-react";
import type { Filing } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { saveAnnouncement } from "@/lib/api";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

interface Props {
  filing: Filing;
  onCategoryFilter?: (category: string) => void;
}

export function AnnouncementDetail({ filing, onCategoryFilter }: Props) {
  const { token } = useAuth();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [note, setNote] = useState("");

  const handleSave = async () => {
    if (!token || saving) return;
    setSaving(true);
    try {
      await saveAnnouncement(token, filing.corp_id, filing.isin, "ANNOUNCEMENT", note);
      setSaved(true);
      setShowSaveModal(false);
      setNote("");
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSaving(false);
    }
  };

  let formattedDate = filing.date;
  try {
    formattedDate =
      format(parseISO(filing.date), "d MMM yyyy · HH:mm") + " IST";
  } catch {
    // use raw
  }

  const summaryContent = filing.ai_summary || filing.summary || "";

  return (
    <div className="h-full overflow-y-auto">
      {/* Breadcrumb + Actions row */}
      <div className="px-4 md:px-8 py-3 border-b border-gray-100 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <div className="text-[11px] text-gray-400 flex items-center gap-1.5 flex-wrap">
          <span className="hover:text-gray-600 cursor-pointer">Market Feed</span>
          <span>›</span>
          <span className="hover:text-gray-600 cursor-pointer">Announcements</span>
          <span>›</span>
          <span
            className={`${onCategoryFilter ? "hover:text-gray-900 cursor-pointer text-gray-600 font-medium underline decoration-dotted underline-offset-2" : "text-gray-600"}`}
            onClick={() => onCategoryFilter?.(filing.category)}
          >
            {filing.category}
          </span>
          <span>›</span>
          <span className="text-gray-900 font-medium">{filing.companyname}</span>
        </div>
        {/* Actions on the right */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => { if (!saved) setShowSaveModal(true); }}
            disabled={saving || saved}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
              saved
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            <Bookmark size={13} fill={saved ? "currentColor" : "none"} />
            {saved ? "Saved" : "Save"}
          </button>
          {filing.fileurl && (
            <a
              href={filing.fileurl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 transition"
            >
              <ExternalLink size={13} />
              <span className="hidden sm:inline">View Original Filing</span>
              <span className="sm:hidden">Original</span>
            </a>
          )}
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 transition">
            <Share2 size={13} />
            Share
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="px-4 md:px-8 py-5">
        {/* Title */}
        <h1 className="text-lg font-bold text-gray-900 leading-snug mb-2">
          {filing.headline || filing.summary}
        </h1>

        {/* Date */}
        <p className="text-xs text-gray-400 mb-4">{formattedDate}</p>

        {/* Sentiment pill — left side, plain pill no border */}
        {filing.sentiment && (
          <div className="mb-5">
            <span
              className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1 rounded-full ${
                filing.sentiment === "Positive"
                  ? "bg-green-50 text-green-700"
                  : filing.sentiment === "Negative"
                  ? "bg-red-50 text-red-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  filing.sentiment === "Positive"
                    ? "bg-green-500"
                    : filing.sentiment === "Negative"
                    ? "bg-red-500"
                    : "bg-gray-400"
                }`}
              />
              {filing.sentiment}
            </span>
          </div>
        )}

        {/* AI Summary rendered as Markdown */}
        <div className="border-t border-gray-100 pt-5">
          <article className="max-w-none text-[13px] leading-relaxed text-gray-700 text-justify markdown-content">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={{
                h1: ({ children }) => (
                  <h1 className="text-base font-bold text-gray-900 mt-4 mb-2">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-[15px] font-bold text-gray-900 mt-4 mb-2">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-[14px] font-semibold text-gray-900 mt-3 mb-1.5">{children}</h3>
                ),
                p: ({ children }) => (
                  <p className="text-[13px] text-gray-700 leading-relaxed mb-3 text-justify">{children}</p>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-gray-900">{children}</strong>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside space-y-1 mb-3 text-[13px] text-gray-700">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside space-y-1 mb-3 text-[13px] text-gray-700">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-[13px] text-gray-700 leading-relaxed">{children}</li>
                ),
                table: ({ children }) => (
                  <div className="my-3 overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-[12px] border-collapse">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-gray-50">{children}</thead>
                ),
                th: ({ children }) => (
                  <th className="text-left font-semibold text-gray-900 px-3 py-2 border-b border-gray-200 text-[12px]">{children}</th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-2 text-gray-700 border-b border-gray-100 text-[12px]">{children}</td>
                ),
                tr: ({ children }) => (
                  <tr className="hover:bg-gray-50/50">{children}</tr>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-gray-300 pl-3 my-3 text-[13px] text-gray-600 italic">{children}</blockquote>
                ),
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{children}</a>
                ),
                code: ({ children }) => (
                  <code className="text-[11px] bg-gray-100 text-gray-800 rounded px-1 py-0.5">{children}</code>
                ),
              }}
            >
              {summaryContent}
            </ReactMarkdown>
          </article>
        </div>

        {/* Investors / Related */}
        {filing.investorCorp && filing.investorCorp.length > 0 && (
          <div className="mt-6 pt-5 border-t border-gray-100 pb-6">
            <h3 className="text-xs font-semibold text-gray-900 mb-2">
              Key Investors / Stakeholders
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {filing.investorCorp.map((inv) => (
                <span
                  key={inv.investor_id}
                  className="text-[11px] bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full"
                >
                  {inv.investor_name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Save Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/20" onClick={() => { setShowSaveModal(false); setNote(""); }} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-[460px] mx-4 p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Save Item</h2>

            <div className="bg-gray-50 rounded-lg p-3 mb-4">
              <p className="text-sm font-semibold text-gray-900">{filing.companyname}</p>
              <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                {filing.headline || filing.summary}
              </p>
            </div>

            <label className="block text-sm text-gray-600 mb-1.5">
              Add an optional note
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Your notes here..."
              rows={4}
              className="w-full px-3 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-gray-400 resize-none"
            />

            <div className="flex items-center justify-end gap-3 mt-5">
              <button
                onClick={() => { setShowSaveModal(false); setNote(""); }}
                className="px-5 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-5 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Item"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

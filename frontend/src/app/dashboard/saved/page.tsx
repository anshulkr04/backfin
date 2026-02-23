"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import {
  fetchSavedAnnouncements,
  deleteSavedAnnouncement,
} from "@/lib/api";
import type { SavedItem } from "@/lib/api";
import {
  Bookmark,
  Share2,
  Download,
  StickyNote,
  Trash2,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { getCategoryClasses } from "@/lib/categories";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

type SortOrder = "latest" | "oldest" | "largest_gain" | "largest_loss";

export default function SavedPage() {
  const { token } = useAuth();
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<SavedItem | null>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>("latest");

  useEffect(() => {
    if (!token) return;
    fetchSavedAnnouncements(token)
      .then((res) => setSavedItems(res.data ?? []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  const handleUnsave = async (e: React.MouseEvent, item: SavedItem) => {
    e.stopPropagation();
    if (!token) return;
    try {
      await deleteSavedAnnouncement(token, item.id);
      setSavedItems((prev) => prev.filter((i) => i.id !== item.id));
      if (selectedItem?.id === item.id) setSelectedItem(null);
    } catch (err) {
      console.error("Failed to unsave:", err);
    }
  };

  const handleUnsaveFromDetail = async () => {
    if (!token || !selectedItem) return;
    try {
      await deleteSavedAnnouncement(token, selectedItem.id);
      setSavedItems((prev) => prev.filter((i) => i.id !== selectedItem.id));
      setSelectedItem(null);
    } catch (err) {
      console.error("Failed to unsave:", err);
    }
  };

  // Sort items
  const sortedItems = [...savedItems].sort((a, b) => {
    switch (sortOrder) {
      case "latest":
        return (b.saved_at ?? "").localeCompare(a.saved_at ?? "");
      case "oldest":
        return (a.saved_at ?? "").localeCompare(b.saved_at ?? "");
      case "largest_gain":
        return (b.percentage_change ?? -Infinity) - (a.percentage_change ?? -Infinity);
      case "largest_loss":
        return (a.percentage_change ?? Infinity) - (b.percentage_change ?? Infinity);
      default:
        return 0;
    }
  });

  function formatTime(dateStr: string) {
    try {
      return format(parseISO(dateStr), "d MMM, HH:mm") + " IST";
    } catch {
      return dateStr;
    }
  }

  function formatDate(dateStr: string) {
    try {
      return format(parseISO(dateStr), "d MMM yyyy");
    } catch {
      return dateStr;
    }
  }

  const summaryContent =
    selectedItem?.ai_summary || selectedItem?.summary || "";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bookmark size={18} className="text-orange-500" />
          <h1 className="text-lg font-bold text-gray-900">Saved Announcements</h1>
          <span className="text-xs text-gray-400 ml-2">
            {savedItems.length} item{savedItems.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel - List */}
        <div className="w-[420px] shrink-0 border-r border-gray-100 flex flex-col overflow-hidden">
          {/* Sort bar */}
          <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
            <span className="text-xs text-gray-400">Sort by:</span>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              className="text-xs font-medium text-gray-700 bg-white border border-gray-200 rounded-lg px-2 py-1.5 outline-none focus:border-gray-400"
            >
              <option value="latest">Latest Saved</option>
              <option value="oldest">Oldest Saved</option>
              <option value="largest_gain">Largest Gain</option>
              <option value="largest_loss">Largest Loss</option>
            </select>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : savedItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-sm text-gray-400">
                <Bookmark size={32} className="mb-3 text-gray-300" />
                <p>No saved announcements yet</p>
                <p className="text-xs mt-1">
                  Save announcements from the dashboard to see them here
                </p>
              </div>
            ) : (
              sortedItems.map((item, idx) => (
                <button
                  key={`${item.id}-${idx}`}
                  onClick={() => setSelectedItem(item)}
                  className={`w-full text-left px-5 py-4 border-b border-gray-100 hover:bg-gray-50/80 transition group ${
                    selectedItem?.id === item.id ? "bg-white" : ""
                  }`}
                >
                  {/* Row 1: Company name + category pill */}
                  <div className="flex items-start justify-between gap-3 mb-1">
                    <span className="text-[13px] font-bold text-gray-900 leading-snug truncate">
                      {item.companyname || `Announcement #${item.corp_id}`}
                    </span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {item.category && (
                        <span
                          className={`text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${getCategoryClasses(
                            item.category
                          )}`}
                        >
                          {item.category}
                        </span>
                      )}
                      <button
                        onClick={(e) => handleUnsave(e, item)}
                        className="p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all"
                        title="Remove from saved"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  {/* Row 2: Headline */}
                  <p className="text-[13px] text-gray-600 line-clamp-2 leading-snug mb-2">
                    {item.headline || item.summary}
                  </p>

                  {/* Row 3: Date + price change */}
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-gray-400 whitespace-nowrap">
                      {item.date ? formatTime(item.date) : ""}
                    </span>
                    {item.percentage_change !== null &&
                      item.percentage_change !== undefined && (
                        <span
                          className={`flex items-center gap-1 text-[11px] font-semibold shrink-0 ${
                            item.percentage_change >= 0
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {item.percentage_change >= 0 ? (
                            <TrendingUp size={12} />
                          ) : (
                            <TrendingDown size={12} />
                          )}
                          {item.percentage_change >= 0 ? "+" : ""}
                          {Number(item.percentage_change).toFixed(2)}%
                        </span>
                      )}
                  </div>

                  {/* Note preview */}
                  {item.note && (
                    <div className="flex items-start gap-1.5 mt-2 bg-amber-50 rounded-md px-2 py-1.5">
                      <StickyNote
                        size={11}
                        className="text-amber-500 shrink-0 mt-0.5"
                      />
                      <p className="text-[11px] text-amber-700 line-clamp-1">
                        {item.note}
                      </p>
                    </div>
                  )}
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right panel - Detail */}
        <div className="flex-1 overflow-hidden">
          {selectedItem ? (
            <div className="h-full overflow-y-auto">
              {/* Breadcrumb + Actions */}
              <div className="px-8 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="text-[11px] text-gray-400 flex items-center gap-1.5 flex-wrap">
                  <span className="hover:text-gray-600 cursor-pointer">
                    Saved
                  </span>
                  <span>›</span>
                  <span className="hover:text-gray-600 cursor-pointer">
                    Announcements
                  </span>
                  <span>›</span>
                  <span className="text-gray-600">
                    {selectedItem.category}
                  </span>
                  <span>›</span>
                  <span className="text-gray-900 font-medium">
                    {selectedItem.companyname}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-4">
                  <button
                    onClick={handleUnsaveFromDetail}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-green-200 bg-green-50 text-green-700 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition group/save"
                  >
                    <Bookmark size={13} fill="currentColor" />
                    <span className="group-hover/save:hidden">Saved</span>
                    <span className="hidden group-hover/save:inline">Unsave</span>
                  </button>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 transition">
                    <Share2 size={13} />
                    Share
                  </button>
                  {selectedItem.fileurl && (
                    <a
                      href={selectedItem.fileurl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 transition"
                    >
                      <Download size={13} />
                      Download
                    </a>
                  )}
                </div>
              </div>

              <div className="px-8 py-5">
                {/* Title */}
                <h1 className="text-lg font-bold text-gray-900 leading-snug mb-2">
                  {selectedItem.headline || selectedItem.summary}
                </h1>

                {/* Date */}
                <p className="text-xs text-gray-400 mb-4">
                  {selectedItem.date
                    ? format(parseISO(selectedItem.date), "dd MMM yyyy - HH:mm") +
                      " IST"
                    : ""}
                </p>

                {/* Saved info block */}
                <div className="border-l-4 border-amber-400 bg-amber-50/80 rounded-r-lg px-5 py-4 mb-5 space-y-1.5">
                  {selectedItem.saved_at && (
                    <p className="text-sm text-gray-700">
                      <span className="font-semibold text-gray-800">
                        Saved on:
                      </span>{" "}
                      {formatDate(selectedItem.saved_at)}
                    </p>
                  )}
                  {selectedItem.percentage_change !== null &&
                    selectedItem.percentage_change !== undefined && (
                      <p className="text-sm">
                        <span className="font-semibold text-gray-800">
                          % change since saved:
                        </span>{" "}
                        <span
                          className={`font-semibold ${
                            selectedItem.percentage_change >= 0
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {selectedItem.percentage_change >= 0 ? "+" : ""}
                          {Number(selectedItem.percentage_change).toFixed(2)}%
                        </span>
                      </p>
                    )}
                  {selectedItem.saved_price !== null &&
                    selectedItem.saved_price !== undefined &&
                    selectedItem.current_price !== null &&
                    selectedItem.current_price !== undefined && (
                      <p className="text-xs text-gray-500">
                        ₹{Number(selectedItem.saved_price).toFixed(2)} → ₹
                        {Number(selectedItem.current_price).toFixed(2)}
                      </p>
                    )}
                  {selectedItem.note && (
                    <div className="pt-1">
                      <p className="text-sm">
                        <span className="font-semibold text-gray-800">
                          Your Note:
                        </span>
                      </p>
                      <p className="text-sm text-gray-700 mt-0.5">
                        {selectedItem.note}
                      </p>
                    </div>
                  )}
                </div>

                {/* Sentiment */}
                {selectedItem.sentiment && (
                  <div className="mb-5">
                    <span
                      className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1 rounded-full ${
                        selectedItem.sentiment === "Positive"
                          ? "bg-green-50 text-green-700"
                          : selectedItem.sentiment === "Negative"
                          ? "bg-red-50 text-red-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          selectedItem.sentiment === "Positive"
                            ? "bg-green-500"
                            : selectedItem.sentiment === "Negative"
                            ? "bg-red-500"
                            : "bg-gray-400"
                        }`}
                      />
                      {selectedItem.sentiment}
                    </span>
                  </div>
                )}

                {/* AI Summary / Content */}
                <div className="border-t border-gray-100 pt-5">
                  <article className="max-w-none text-[13px] leading-relaxed text-gray-700 text-justify markdown-content">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={{
                        h1: ({ children }) => (
                          <h1 className="text-base font-bold text-gray-900 mt-4 mb-2">
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-[15px] font-bold text-gray-900 mt-4 mb-2">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-[14px] font-semibold text-gray-900 mt-3 mb-1.5">
                            {children}
                          </h3>
                        ),
                        p: ({ children }) => (
                          <p className="text-[13px] text-gray-700 leading-relaxed mb-3 text-justify">
                            {children}
                          </p>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-gray-900">
                            {children}
                          </strong>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc list-inside space-y-1 mb-3 text-[13px] text-gray-700">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-inside space-y-1 mb-3 text-[13px] text-gray-700">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => (
                          <li className="text-[13px] text-gray-700 leading-relaxed">
                            {children}
                          </li>
                        ),
                        table: ({ children }) => (
                          <div className="my-3 overflow-x-auto rounded-lg border border-gray-200">
                            <table className="w-full text-[12px] border-collapse">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-gray-50">{children}</thead>
                        ),
                        th: ({ children }) => (
                          <th className="text-left font-semibold text-gray-900 px-3 py-2 border-b border-gray-200 text-[12px]">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="px-3 py-2 text-gray-700 border-b border-gray-100 text-[12px]">
                            {children}
                          </td>
                        ),
                        tr: ({ children }) => (
                          <tr className="hover:bg-gray-50/50">{children}</tr>
                        ),
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-2 border-gray-300 pl-3 my-3 text-[13px] text-gray-600 italic">
                            {children}
                          </blockquote>
                        ),
                        a: ({ href, children }) => (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            {children}
                          </a>
                        ),
                        code: ({ children }) => (
                          <code className="text-[11px] bg-gray-100 text-gray-800 rounded px-1 py-0.5">
                            {children}
                          </code>
                        ),
                      }}
                    >
                      {summaryContent}
                    </ReactMarkdown>
                  </article>
                </div>

                {/* Investors */}
                {selectedItem.investors &&
                  selectedItem.investors.length > 0 && (
                    <div className="mt-6 pt-5 border-t border-gray-100 pb-6">
                      <h3 className="text-xs font-semibold text-gray-900 mb-2">
                        Key Investors / Stakeholders
                      </h3>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedItem.investors.map((inv) => (
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
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <Bookmark size={32} className="mb-3 text-gray-300" />
              <p className="text-sm">
                Select a saved announcement to view details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

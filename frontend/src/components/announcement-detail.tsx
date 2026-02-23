"use client";

import { format, parseISO } from "date-fns";
import { Bookmark, Download, Share2, ExternalLink } from "lucide-react";
import type { Filing } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { saveAnnouncement } from "@/lib/api";
import { useState } from "react";

interface Props {
  filing: Filing;
}

export function AnnouncementDetail({ filing }: Props) {
  const { token } = useAuth();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (!token || saving) return;
    setSaving(true);
    try {
      await saveAnnouncement(token, filing.corp_id, filing.isin);
      setSaved(true);
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

  // Parse the AI summary – it often has markdown-like structure
  const renderSummary = () => {
    if (!filing.ai_summary) {
      return (
        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
          {filing.summary}
        </p>
      );
    }

    // Split by double newline for paragraphs
    const sections = filing.ai_summary.split("\n\n");
    return (
      <div className="space-y-4">
        {sections.map((section, i) => {
          // Bold headings
          if (section.startsWith("**") && section.includes(":**")) {
            const parts = section.split(":**");
            const label = parts[0].replace(/\*\*/g, "").trim();
            const value = parts.slice(1).join(":**").replace(/\*\*/g, "").trim();
            return (
              <div key={i}>
                <span className="text-sm font-semibold text-gray-900">
                  {label}:
                </span>{" "}
                <span className="text-sm text-gray-700">{value}</span>
              </div>
            );
          }

          // Headings with ###
          if (section.startsWith("###")) {
            return (
              <h3
                key={i}
                className="text-base font-semibold text-gray-900 mt-4"
              >
                {section.replace(/^#+\s*/, "")}
              </h3>
            );
          }

          // Bullet points
          if (section.includes("\n- ") || section.startsWith("- ")) {
            const lines = section.split("\n");
            return (
              <ul key={i} className="space-y-1.5 list-disc list-inside">
                {lines.map((line, j) => {
                  const text = line.replace(/^-\s*/, "").replace(/\*\*/g, "");
                  if (!text.trim()) return null;
                  // Is this a heading before bullet points?
                  if (!line.startsWith("-") && !line.startsWith("  -")) {
                    return (
                      <h4
                        key={j}
                        className="text-sm font-semibold text-gray-900 mt-2 list-none"
                      >
                        {text}
                      </h4>
                    );
                  }
                  return (
                    <li key={j} className="text-sm text-gray-700 leading-relaxed">
                      {text}
                    </li>
                  );
                })}
              </ul>
            );
          }

          // Table-like content (Key | Value)
          if (section.includes("|")) {
            const rows = section
              .split("\n")
              .filter((r) => r.includes("|") && !r.match(/^[\s|-]+$/));
            if (rows.length > 0) {
              return (
                <table key={i} className="w-full text-sm border-collapse">
                  <tbody>
                    {rows.map((row, j) => {
                      const cells = row
                        .split("|")
                        .map((c) => c.replace(/\*\*/g, "").trim())
                        .filter(Boolean);
                      return (
                        <tr
                          key={j}
                          className={j === 0 ? "font-semibold" : ""}
                        >
                          {cells.map((cell, k) => (
                            <td
                              key={k}
                              className={`py-1.5 pr-4 ${
                                j === 0
                                  ? "text-gray-900 border-b border-gray-100"
                                  : "text-gray-700"
                              }`}
                            >
                              {cell}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              );
            }
          }

          // Plain paragraph
          return (
            <p
              key={i}
              className="text-sm text-gray-700 leading-relaxed"
              dangerouslySetInnerHTML={{
                __html: section
                  .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                  .replace(/\n/g, "<br/>"),
              }}
            />
          );
        })}
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto">
      {/* Breadcrumb */}
      <div className="px-6 py-3 border-b border-gray-100 text-xs text-gray-400 flex items-center gap-1.5">
        <span>Market Feed</span>
        <span>›</span>
        <span>Announcements</span>
        <span>›</span>
        <span className="text-gray-600">{filing.category}</span>
        <span>›</span>
        <span className="text-gray-900 font-medium">{filing.companyname}</span>
      </div>

      {/* Main content */}
      <div className="px-6 py-6 max-w-3xl">
        {/* Title */}
        <h1 className="text-xl font-bold text-gray-900 leading-snug mb-2">
          {filing.headline || filing.summary}
        </h1>

        {/* Meta */}
        <p className="text-sm text-gray-400 mb-6">{formattedDate}</p>

        {/* Actions */}
        <div className="flex items-center gap-2 mb-8">
          <button
            onClick={handleSave}
            disabled={saving || saved}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
              saved
                ? "border-green-200 bg-green-50 text-green-700"
                : "border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            <Bookmark size={14} fill={saved ? "currentColor" : "none"} />
            {saved ? "Saved" : "Save"}
          </button>
          {filing.fileurl && (
            <a
              href={filing.fileurl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 transition"
            >
              <Download size={14} />
              Download
            </a>
          )}
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 transition">
            <Share2 size={14} />
            Share
          </button>
        </div>

        {/* Sentiment badge */}
        {filing.sentiment && (
          <div className="mb-6">
            <span
              className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full ${
                filing.sentiment === "Positive"
                  ? "bg-green-50 text-green-700"
                  : filing.sentiment === "Negative"
                  ? "bg-red-50 text-red-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {filing.sentiment}
            </span>
          </div>
        )}

        {/* Body */}
        <div className="border-t border-gray-100 pt-6">{renderSummary()}</div>

        {/* Investors / Related */}
        {filing.investorCorp && filing.investorCorp.length > 0 && (
          <div className="mt-8 pt-6 border-t border-gray-100">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Key Investors / Stakeholders
            </h3>
            <div className="flex flex-wrap gap-2">
              {filing.investorCorp.map((inv) => (
                <span
                  key={inv.investor_id}
                  className="text-xs bg-gray-100 text-gray-700 px-2.5 py-1 rounded-full"
                >
                  {inv.investor_name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* PDF link */}
        {filing.fileurl && (
          <div className="mt-8 pt-6 border-t border-gray-100">
            <a
              href={filing.fileurl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-orange-600 hover:text-orange-700 font-medium"
            >
              <ExternalLink size={14} />
              View Original Document
            </a>
          </div>
        )}

        {/* Company info */}
        <div className="mt-8 pt-6 border-t border-gray-100 text-xs text-gray-400 space-y-1">
          <p>
            <span className="font-medium text-gray-500">Symbol:</span>{" "}
            {filing.symbol}
          </p>
          <p>
            <span className="font-medium text-gray-500">ISIN:</span>{" "}
            {filing.isin}
          </p>
          <p>
            <span className="font-medium text-gray-500">Security ID:</span>{" "}
            {filing.securityid}
          </p>
        </div>
      </div>
    </div>
  );
}

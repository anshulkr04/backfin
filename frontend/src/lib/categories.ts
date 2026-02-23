// ─── Category Groups & Unique Colors ───────────────
// Every category has a unique color scheme that is never reused.

export interface CategoryGroup {
  title: string;
  categories: string[];
}

export const CATEGORY_GROUPS: CategoryGroup[] = [
  {
    title: "Key Documents & Meetings",
    categories: [
      "Annual Report",
      "Investor/Analyst Meet",
      "Investor Presentation",
      "Concall Transcript",
    ],
  },
  {
    title: "Capital & Financing",
    categories: [
      "Fundraise - Rights Issue",
      "Fundraise - Preferential Issue",
      "Increase in Share Capital",
      "Fundraise - QIP",
      "DRHP",
      "Reduction in Share Capital",
      "Debt & Financing",
      "Debt Reduction",
      "Interest Rates Updates",
      "One Time Settlement (OTS)",
    ],
  },
  {
    title: "Corporate Actions",
    categories: [
      "Mergers/Acquisitions",
      "Bonus/Stock Split",
      "Divestitures",
      "Buyback",
      "Consolidation of Shares",
      "Demerger",
      "Joint Ventures",
      "Incorporation/Cessation of Subsidiary",
      "Open Offer",
    ],
  },
  {
    title: "Strategic & Business Operations",
    categories: [
      "Agreements/MoUs",
      "Expansion",
      "Operational Update",
      "New Order",
      "New Product",
      "Factory Closure",
      "Disruption of Operations",
      "PLI Scheme",
    ],
  },
  {
    title: "Financial Reporting & Ratings",
    categories: ["Financial Results", "Credit Rating"],
  },
  {
    title: "Regulatory & Legal",
    categories: [
      "Regulatory Approvals/Orders",
      "USFDA",
      "Global Pharma Regulation",
      "Litigation & Notices",
      "Insolvency and Bankruptcy",
      "Anti-dumping Duty",
      "Delisting",
      "Trading Suspension",
      "Clarifications/Confirmations",
    ],
  },
  {
    title: "Corporate Governance & Admin",
    categories: [
      "Change in KMP",
      "Name Change",
      "Demise of KMP",
      "Change in Address",
      "Change in MOA",
    ],
  },
];

export const PROCEDURAL_CATEGORY = "Procedural/Administrative";

// All categories flattened
export const ALL_CATEGORIES = CATEGORY_GROUPS.flatMap((g) => g.categories);

// ─── Unique Color Per Category ──────────────────────
// Each category maps to a unique bg + text color pair.
// The pill design stays consistent, only colors differ.
export const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  // Key Documents & Meetings
  "Annual Report":              { bg: "bg-blue-50",    text: "text-blue-700" },
  "Investor/Analyst Meet":      { bg: "bg-violet-50",  text: "text-violet-700" },
  "Investor Presentation":      { bg: "bg-indigo-50",  text: "text-indigo-700" },
  "Concall Transcript":         { bg: "bg-purple-50",  text: "text-purple-700" },

  // Capital & Financing
  "Fundraise - Rights Issue":       { bg: "bg-emerald-50",  text: "text-emerald-700" },
  "Fundraise - Preferential Issue": { bg: "bg-teal-50",     text: "text-teal-700" },
  "Increase in Share Capital":      { bg: "bg-cyan-50",     text: "text-cyan-700" },
  "Fundraise - QIP":                { bg: "bg-sky-50",      text: "text-sky-700" },
  "DRHP":                           { bg: "bg-blue-100",    text: "text-blue-800" },
  "Reduction in Share Capital":     { bg: "bg-slate-100",   text: "text-slate-700" },
  "Debt & Financing":               { bg: "bg-zinc-100",    text: "text-zinc-700" },
  "Debt Reduction":                 { bg: "bg-stone-100",   text: "text-stone-700" },
  "Interest Rates Updates":         { bg: "bg-neutral-100", text: "text-neutral-700" },
  "One Time Settlement (OTS)":      { bg: "bg-gray-200",    text: "text-gray-700" },

  // Corporate Actions
  "Mergers/Acquisitions":                { bg: "bg-rose-50",    text: "text-rose-700" },
  "Bonus/Stock Split":                   { bg: "bg-pink-50",    text: "text-pink-700" },
  "Divestitures":                        { bg: "bg-fuchsia-50", text: "text-fuchsia-700" },
  "Buyback":                             { bg: "bg-red-50",     text: "text-red-700" },
  "Consolidation of Shares":            { bg: "bg-orange-100", text: "text-orange-800" },
  "Demerger":                            { bg: "bg-amber-100",  text: "text-amber-800" },
  "Joint Ventures":                      { bg: "bg-yellow-50",  text: "text-yellow-700" },
  "Incorporation/Cessation of Subsidiary": { bg: "bg-lime-50",  text: "text-lime-700" },
  "Open Offer":                          { bg: "bg-green-50",   text: "text-green-700" },

  // Strategic & Business Operations
  "Agreements/MoUs":       { bg: "bg-teal-100",    text: "text-teal-800" },
  "Expansion":             { bg: "bg-emerald-100", text: "text-emerald-800" },
  "Operational Update":    { bg: "bg-cyan-100",    text: "text-cyan-800" },
  "New Order":             { bg: "bg-sky-100",     text: "text-sky-800" },
  "New Product":           { bg: "bg-blue-50",     text: "text-blue-600" },
  "Factory Closure":       { bg: "bg-red-100",     text: "text-red-800" },
  "Disruption of Operations": { bg: "bg-orange-50", text: "text-orange-700" },
  "PLI Scheme":            { bg: "bg-violet-100",  text: "text-violet-800" },

  // Financial Reporting & Ratings
  "Financial Results":  { bg: "bg-indigo-100", text: "text-indigo-800" },
  "Credit Rating":      { bg: "bg-amber-50",   text: "text-amber-700" },

  // Regulatory & Legal
  "Regulatory Approvals/Orders": { bg: "bg-yellow-100",  text: "text-yellow-800" },
  "USFDA":                       { bg: "bg-lime-100",    text: "text-lime-800" },
  "Global Pharma Regulation":    { bg: "bg-green-100",   text: "text-green-800" },
  "Litigation & Notices":        { bg: "bg-rose-100",    text: "text-rose-800" },
  "Insolvency and Bankruptcy":   { bg: "bg-pink-100",    text: "text-pink-800" },
  "Anti-dumping Duty":           { bg: "bg-fuchsia-100", text: "text-fuchsia-800" },
  "Delisting":                   { bg: "bg-red-100",     text: "text-red-700" },
  "Trading Suspension":          { bg: "bg-stone-200",   text: "text-stone-800" },
  "Clarifications/Confirmations": { bg: "bg-orange-50",  text: "text-orange-600" },

  // Corporate Governance & Admin
  "Change in KMP":     { bg: "bg-purple-100", text: "text-purple-800" },
  "Name Change":       { bg: "bg-indigo-50",  text: "text-indigo-600" },
  "Demise of KMP":     { bg: "bg-gray-100",   text: "text-gray-600" },
  "Change in Address": { bg: "bg-slate-50",   text: "text-slate-600" },
  "Change in MOA":     { bg: "bg-zinc-50",    text: "text-zinc-600" },

  // Procedural
  "Procedural/Administrative": { bg: "bg-gray-50", text: "text-gray-500" },
};

const DEFAULT_COLOR = { bg: "bg-gray-100", text: "text-gray-600" };

export function getCategoryColor(category: string): { bg: string; text: string } {
  return CATEGORY_COLORS[category] || DEFAULT_COLOR;
}

export function getCategoryClasses(category: string): string {
  const c = getCategoryColor(category);
  return `${c.bg} ${c.text}`;
}

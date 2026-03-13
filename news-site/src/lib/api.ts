const API_BASE = "https://api.marketwire.ai";

export interface Article {
  id: string;
  headline: string;
  slug: string;
  seo_description: string;
  body: string;
  sentiment: "Positive" | "Negative" | "Neutral" | "Mixed";
  tags: string[];
  key_figures: string;
  category: string;
  article_category: string;
  companyname: string;
  symbol: string;
  isin: string;
  sector: string;
  filing_date: string;
  published_at: string;
  source_url: string;
  view_count: number;
}

export interface CategoryCount {
  category: string;
  count: number;
}

// ── List articles with filters ──────────────────────────────────
export async function getArticles(params: {
  page?: number;
  limit?: number;
  article_category?: string;
  sentiment?: string;
  sector?: string;
  symbol?: string;
  tag?: string;
} = {}): Promise<{ articles: Article[]; page: number; limit: number; count: number }> {
  const url = new URL(`${API_BASE}/api/news/articles`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  });
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// ── Single article by slug ──────────────────────────────────────
export async function getArticleBySlug(slug: string): Promise<Article | null> {
  const res = await fetch(`${API_BASE}/api/news/articles/${encodeURIComponent(slug)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();
  return data.article ?? data;
}

// ── Latest N articles ───────────────────────────────────────────
export async function getLatestArticles(n: number = 10): Promise<Article[]> {
  const res = await fetch(`${API_BASE}/api/news/latest?n=${n}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();
  return data.articles;
}

// ── Categories with counts ──────────────────────────────────────
export async function getCategories(): Promise<CategoryCount[]> {
  const res = await fetch(`${API_BASE}/api/news/categories`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();
  return data.categories;
}

// ── Company articles ────────────────────────────────────────────
export async function getCompanyArticles(
  symbolOrIsin: string,
  page: number = 1,
  limit: number = 20
): Promise<{ articles: Article[]; company: string; page: number; limit: number; count: number }> {
  const res = await fetch(
    `${API_BASE}/api/news/company/${encodeURIComponent(symbolOrIsin)}?page=${page}&limit=${limit}`
  );
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// ── Helpers ─────────────────────────────────────────────────────
export function categoryToSlug(category: string): string {
  return category
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export function slugToCategory(slug: string): string {
  const map: Record<string, string> = {
    "earnings-and-results": "Earnings & Results",
    "mergers-and-acquisitions": "Mergers & Acquisitions",
    "fundraising-and-capital-markets": "Fundraising & Capital Markets",
    "dividends-and-corporate-actions": "Dividends & Corporate Actions",
    "leadership-changes": "Leadership Changes",
    "regulatory-and-legal": "Regulatory & Legal",
    "business-operations": "Business Operations",
    "debt-and-credit": "Debt & Credit",
    "investor-relations": "Investor Relations",
    "strategic-agreements": "Strategic Agreements",
    "market-commentary": "Market Commentary",
  };
  return map[slug] ?? slug;
}

export const CATEGORIES = [
  "Earnings & Results",
  "Mergers & Acquisitions",
  "Fundraising & Capital Markets",
  "Dividends & Corporate Actions",
  "Leadership Changes",
  "Regulatory & Legal",
  "Business Operations",
  "Debt & Credit",
  "Investor Relations",
  "Strategic Agreements",
  "Market Commentary",
] as const;

export function sentimentColor(s: string): string {
  switch (s) {
    case "Positive": return "badge-positive";
    case "Negative": return "badge-negative";
    case "Mixed": return "badge-mixed";
    default: return "badge-neutral";
  }
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(dateStr);
}

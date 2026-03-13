import rss from "@astrojs/rss";
import type { APIContext } from "astro";

const API_BASE = "https://api.marketwire.ai";

export async function GET(context: APIContext) {
  let articles: any[] = [];
  try {
    const res = await fetch(`${API_BASE}/api/news/latest?n=30`);
    if (res.ok) {
      const data = await res.json();
      articles = data.articles || [];
    }
  } catch {}

  return rss({
    title: "MarketWire News",
    description:
      "AI-powered corporate news from every NSE & BSE filing. Summarized, classified, delivered in real-time.",
    site: context.site!.toString(),
    items: articles.map((a: any) => {
      const catSlug = a.article_category
        ?.toLowerCase()
        .replace(/&/g, "and")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");
      return {
        title: a.headline,
        pubDate: new Date(a.published_at),
        description: a.seo_description || "",
        link: `/${catSlug}/${a.slug}/`,
        categories: [a.article_category].filter(Boolean),
      };
    }),
  });
}

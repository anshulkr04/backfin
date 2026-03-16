import type { Metadata } from "next";
import { Inter, DM_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";
import Script from "next/script";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "MarketWire — Real-Time NSE & BSE Corporate Filings, AI-Summarized",
  description:
    "Every NSE and BSE corporate filing — AI-summarized, classified, and delivered in real-time. Track insider trades, block deals, financial results, and 45+ categories. Stop reading 50-page PDFs.",
  keywords: [
    "NSE filings",
    "BSE filings",
    "corporate filings India",
    "stock market alerts",
    "AI stock analysis",
    "insider trades India",
    "block deals",
    "bulk deals",
    "financial results",
    "SEBI announcements",
    "MarketWire",
    "real-time market alerts",
    "Indian stock market",
    "corporate announcements",
  ],
  authors: [{ name: "MarketWire", url: "https://marketwire.app" }],
  creator: "MarketWire",
  publisher: "MarketWire",
  metadataBase: new URL("https://marketwire.app"),
  alternates: {
    canonical: "https://marketwire.app",
  },
  icons: {
    icon: "/icon.svg",
  },
  openGraph: {
    type: "website",
    locale: "en_IN",
    url: "https://marketwire.app",
    siteName: "MarketWire",
    title: "MarketWire — Real-Time NSE & BSE Corporate Filings, AI-Summarized",
    description:
      "Every NSE and BSE corporate filing — AI-summarized, classified, and delivered in real-time. Track insider trades, block deals, financial results, and 45+ categories.",
    images: [
      {
        url: "/icon.svg",
        width: 1200,
        height: 630,
        alt: "MarketWire — Real-Time Indian Stock Market Filing Alerts",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "MarketWire — Real-Time NSE & BSE Corporate Filings, AI-Summarized",
    description:
      "Every NSE and BSE corporate filing — AI-summarized, classified, and delivered in real-time. 2,400+ filings daily. 45+ categories.",
    images: ["/icon.svg"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "name": "MarketWire",
        "url": "https://marketwire.app",
        "logo": "https://marketwire.app/icon.svg",
        "description":
          "Real-time NSE and BSE corporate filing alerts — AI-summarized, classified, and delivered instantly. 2,400+ filings processed daily across 45+ categories.",
        "contactPoint": {
          "@type": "ContactPoint",
          "contactType": "customer service",
          "email": "support@marketwire.app",
        },
      },
      {
        "@type": "WebPage",
        "name": "MarketWire — Real-Time NSE & BSE Corporate Filings, AI-Summarized",
        "description":
          "Every NSE and BSE corporate filing — AI-summarized, classified, and delivered in real-time. Track insider trades, block deals, financial results, and 45+ categories.",
        "url": "https://marketwire.app",
        "dateModified": new Date().toISOString().split("T")[0],
        "inLanguage": "en-IN",
        "isPartOf": {
          "@type": "WebSite",
          "name": "MarketWire",
          "url": "https://marketwire.app",
        },
        "speakable": {
          "@type": "SpeakableSpecification",
          "cssSelector": ["h1", ".hero-description", ".faq-answer"],
        },
      },
      {
        "@type": "SoftwareApplication",
        "name": "MarketWire",
        "applicationCategory": "FinanceApplication",
        "operatingSystem": "Web",
        "url": "https://marketwire.app",
        "description":
          "AI-powered corporate filing tracker for Indian stock markets. Covers NSE, BSE, insider trades, block deals, financial results, and SEBI announcements in real-time.",
        "featureList": [
          "Real-time NSE and BSE corporate filing alerts",
          "AI-powered filing summaries",
          "Insider trade tracking",
          "Block and bulk deal monitoring",
          "Financial results analysis",
          "45+ filing category classification",
          "Telegram instant notifications",
          "Watchlist and saved filings",
        ],
        "offers": {
          "@type": "Offer",
          "price": "0",
          "priceCurrency": "INR",
          "description": "Free tier: 10 alerts/day, 2 watchlists",
        },
      },
      {
        "@type": "FAQPage",
        "mainEntity": [
          {
            "@type": "Question",
            "name": "What is MarketWire?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "MarketWire is a real-time corporate filing intelligence platform for the Indian stock market. It processes over 2,400 NSE and BSE filings daily, delivering AI-summarized insights across 45+ categories including financial results, insider trades, block deals, and SEBI announcements.",
            },
          },
          {
            "@type": "Question",
            "name": "How does MarketWire summarize corporate filings?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "MarketWire uses AI to read every BSE and NSE filing and extract three key elements: what happened (structured summary), sentiment analysis (bullish or bearish), and key numbers auto-extracted into data tables. This replaces the need to read 50-page PDF filings manually.",
            },
          },
          {
            "@type": "Question",
            "name": "What types of filings does MarketWire track?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "MarketWire tracks 45+ categories of corporate filings including: financial results, mergers and acquisitions, insider trades, block deals, bulk deals, SEBI notices, board meetings, corporate actions, investor presentations, concall transcripts, annual reports, and more — all from NSE and BSE exchanges.",
            },
          },
          {
            "@type": "Question",
            "name": "How much does MarketWire cost?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "MarketWire offers a free tier with 10 alerts per day and 2 watchlists. The Pro plan at ₹499/month provides unlimited alerts, unlimited watchlists, and access to all features.",
            },
          },
          {
            "@type": "Question",
            "name": "Can I get filing alerts on Telegram?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "Yes. MarketWire delivers instant notifications via Telegram so you receive corporate filing alerts in real-time — before the market opens. You can configure alerts for specific companies, categories, or watchlists.",
            },
          },
          {
            "@type": "Question",
            "name": "How is MarketWire different from Moneycontrol or Screener?",
            "acceptedAnswer": {
              "@type": "Answer",
              "text": "MarketWire focuses exclusively on real-time corporate filings with AI summarization. While platforms like Moneycontrol cover news broadly, MarketWire processes raw exchange filings within seconds, providing AI-generated summaries, sentiment analysis, and structured data tables — giving investors a significant time advantage.",
            },
          },
        ],
      },
    ],
  };

  return (
    <html lang="en">
      <head>
        <Script
          id="json-ld"
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
          strategy="afterInteractive"
        />
      </head>
      <body className={`${inter.variable} ${dmSans.variable} font-sans antialiased bg-white`}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}

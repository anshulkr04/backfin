"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { Logo } from "@/components/logo";
import {
  Radio,
  Zap,
  Bookmark,
  Bell,
  BarChart3,
  ArrowRight,
  ChevronRight,
  MessageCircle,
  Mail,
  Search,
  Filter,
  Check,
  Users,
  Layers,
  UserCheck,
  List,
  Building2,
  Tag,
  StickyNote,
} from "lucide-react";

/* ────────────────────────────────────────────────────
   MOCK DATA — realistic Indian market announcements
   ──────────────────────────────────────────────────── */

const MOCK_FEED = [
  { company: "Reliance Industries Ltd", headline: "Reliance Acquires 73% Stake in Karkinos Healthcare for ₹1,200 Cr", category: "Mergers/Acquisitions", catBg: "bg-rose-50", catText: "text-rose-700", time: "22 Feb, 14:32 IST", sentiment: "Positive", sentColor: "text-green-600", sentDot: "bg-green-500" },
  { company: "Tata Motors Ltd", headline: "Tata Motors Board Approves ₹7,500 Cr Investment in EV Gigafactory at Sanand", category: "Expansion", catBg: "bg-emerald-100", catText: "text-emerald-800", time: "22 Feb, 13:18 IST", sentiment: "Positive", sentColor: "text-green-600", sentDot: "bg-green-500" },
  { company: "HDFC Bank Ltd", headline: "HDFC Bank Q3 FY26 Net Profit Rises 22% YoY to ₹17,657 Cr; NIM at 3.65%", category: "Financial Results", catBg: "bg-indigo-100", catText: "text-indigo-800", time: "22 Feb, 11:45 IST", sentiment: "Positive", sentColor: "text-green-600", sentDot: "bg-green-500" },
  { company: "Infosys Ltd", headline: "Infosys Wins $2.1 Bn Digital Transformation Deal with Global Retailer", category: "New Order", catBg: "bg-sky-100", catText: "text-sky-800", time: "22 Feb, 10:22 IST", sentiment: "Positive", sentColor: "text-green-600", sentDot: "bg-green-500" },
  { company: "Adani Enterprises Ltd", headline: "SEBI Issues Show Cause Notice to Adani Group Over Related Party Transactions", category: "Litigation & Notices", catBg: "bg-rose-100", catText: "text-rose-800", time: "22 Feb, 09:50 IST", sentiment: "Negative", sentColor: "text-red-600", sentDot: "bg-red-500" },
  { company: "Wipro Ltd", headline: "Wipro Allots 44,401 Equity Shares Upon Exercise of ESOPs", category: "Increase in Share Capital", catBg: "bg-cyan-50", catText: "text-cyan-700", time: "21 Feb, 20:58 IST", sentiment: "Neutral", sentColor: "text-yellow-600", sentDot: "bg-yellow-500" },
  { company: "Sun Pharma Ltd", headline: "Sun Pharma Receives USFDA Approval for Generic Revlimid Capsules", category: "USFDA", catBg: "bg-lime-100", catText: "text-lime-800", time: "21 Feb, 18:15 IST", sentiment: "Positive", sentColor: "text-green-600", sentDot: "bg-green-500" },
];

const MOCK_INSIDER_TRADES = [
  { person: "Mukesh D. Ambani", company: "Reliance Industries", type: "Acquisition", qty: "2,50,000", value: "₹312.5 Cr", date: "22 Feb 2026" },
  { person: "Rakesh Jhunjhunwala Trust", company: "Titan Company", type: "Disposal", qty: "15,00,000", value: "₹487.5 Cr", date: "21 Feb 2026" },
  { person: "Nandan Nilekani", company: "Infosys Ltd", type: "Acquisition", qty: "5,00,000", value: "₹97.5 Cr", date: "21 Feb 2026" },
  { person: "Kumar Birla Family", company: "UltraTech Cement", type: "Pledge Created", qty: "8,20,000", value: "₹738 Cr", date: "20 Feb 2026" },
  { person: "Sanjiv Mehta", company: "Hindustan Unilever", type: "Disposal", qty: "1,25,000", value: "₹34.7 Cr", date: "20 Feb 2026" },
];

const MOCK_DEALS = [
  { company: "HDFC Bank", type: "Block Deal", buyer: "Goldman Sachs OPP", seller: "MSCI Index Fund", qty: "45,00,000", price: "₹1,780.50", value: "₹801.2 Cr", date: "22 Feb 2026" },
  { company: "Bajaj Finance", type: "Bulk Deal", buyer: "Fidelity Investments", seller: "Morgan Stanley Asia", qty: "12,50,000", price: "₹7,250.00", value: "₹906.3 Cr", date: "22 Feb 2026" },
  { company: "SBI Life Insurance", type: "Block Deal", buyer: "Vanguard EM Fund", seller: "Promoter Entity", qty: "30,00,000", price: "₹1,520.00", value: "₹456.0 Cr", date: "21 Feb 2026" },
  { company: "Tata Steel", type: "Bulk Deal", buyer: "Abu Dhabi Inv Auth", seller: "Dimensional Fund", qty: "85,00,000", price: "₹142.60", value: "₹121.2 Cr", date: "21 Feb 2026" },
];

/* ────────────────────────────────────────────────────
   PAGE
   ──────────────────────────────────────────────────── */

export default function LandingPage() {
  const { token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && token) {
      router.push("/dashboard");
    }
  }, [token, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (token) return null; // will redirect

  return (
    <div className="min-h-screen bg-white">
      {/* ───── Navbar ───── */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link href="/">
              <Logo variant="full" theme="dark" className="h-7" />
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/auth"
              className="text-sm font-medium text-gray-600 hover:text-gray-900 transition px-4 py-2"
            >
              Log in
            </Link>
            <Link
              href="/auth"
              className="text-sm font-medium text-white bg-gray-900 hover:bg-gray-800 transition px-5 py-2 rounded-lg"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* ───── Hero ───── */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-3xl mx-auto text-center mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-50 text-orange-700 text-xs font-medium mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500" />
              </span>
              Live — 2,400+ filings processed daily
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-gray-900 leading-[1.08] tracking-tight font-[family-name:var(--font-display)]">
              You&apos;re reading filings<br />
              <span className="text-orange-500">6 hours too late.</span>
            </h1>
            <p className="text-lg text-gray-500 mt-6 max-w-2xl mx-auto leading-relaxed font-[family-name:var(--font-display)]">
              MarketWire delivers every NSE and BSE corporate filing — AI-summarized, classified, and in your Telegram — before the market opens tomorrow.
            </p>
            <div className="flex items-center justify-center gap-3 mt-8">
              <Link
                href="/auth"
                className="inline-flex items-center gap-2 px-7 py-3.5 bg-orange-500 text-white font-semibold rounded-lg hover:bg-orange-600 transition text-sm"
              >
                Get Real-Time Alerts Free <ArrowRight size={16} />
              </Link>
              <a
                href="#features"
                className="inline-flex items-center gap-2 px-6 py-3 border border-gray-200 text-gray-600 font-medium rounded-lg hover:bg-gray-50 transition text-sm"
              >
                See a Live Feed →
              </a>
            </div>
            <p className="text-xs text-gray-400 mt-4">
              2,400+ filings processed daily · NSE + BSE · No PDF reading required
            </p>
          </div>

          {/* Hero Mock — Full Dashboard */}
          <div className="relative mx-auto max-w-6xl">
            <div className="absolute -inset-4 bg-gradient-to-b from-orange-50/50 via-transparent to-transparent rounded-3xl" />
            <div className="relative rounded-xl border border-gray-200 bg-white shadow-2xl shadow-gray-200/50 overflow-hidden">
              {/* Fake browser bar */}
              <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 border-b border-gray-100">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-yellow-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                </div>
                <div className="flex-1 flex justify-center">
                  <div className="px-4 py-1 bg-white rounded-md border border-gray-200 text-[11px] text-gray-400 w-64 text-center">
                    app.marketwire.ai/dashboard/market-feed
                  </div>
                </div>
              </div>

              <div className="flex h-[520px]">
                {/* Mini sidebar */}
                <div className="w-14 border-r border-gray-100 bg-white flex-col items-center py-4 gap-3 shrink-0 hidden sm:flex">
                  <div className="w-8 h-8 rounded-lg bg-gray-900 flex items-center justify-center mb-3">
                    <span className="text-white text-[10px] font-bold">MW</span>
                  </div>
                  {[Radio, Bookmark, Search, List, Users, Bell].map((Icon, i) => (
                    <div
                      key={i}
                      className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        i === 0 ? "bg-orange-50" : "hover:bg-gray-50"
                      }`}
                    >
                      <Icon size={15} className={i === 0 ? "text-orange-500" : "text-gray-400"} />
                    </div>
                  ))}
                </div>

                {/* Feed list */}
                <div className="w-[340px] border-r border-gray-100 flex flex-col overflow-hidden shrink-0 hidden md:flex">
                  <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
                    <Radio size={14} className="text-orange-500" />
                    <span className="text-sm font-bold text-gray-900">Live Market Feed</span>
                    <span className="text-[10px] text-gray-400 ml-auto">24,891</span>
                  </div>
                  <div className="flex-1 overflow-hidden">
                    {MOCK_FEED.slice(0, 5).map((item, i) => (
                      <div
                        key={i}
                        className={`px-4 py-3 border-b border-gray-50 cursor-default ${
                          i === 0 ? "bg-orange-50/40" : ""
                        } ${i > 2 ? "opacity-60" : ""}`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-0.5">
                          <span className="text-[12px] font-bold text-gray-900 truncate">{item.company}</span>
                          <span className="text-[9px] text-gray-400 shrink-0">{item.time.split(",")[1]}</span>
                        </div>
                        <p className="text-[11px] text-gray-600 line-clamp-2 leading-snug mb-1.5">{item.headline}</p>
                        <div className="flex items-center justify-between">
                          <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${item.catBg} ${item.catText}`}>
                            {item.category}
                          </span>
                          <span className={`flex items-center gap-1 text-[10px] font-medium ${item.sentColor}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${item.sentDot}`} />
                            {item.sentiment}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Detail panel */}
                <div className="flex-1 overflow-hidden flex flex-col">
                  <div className="px-5 py-2.5 border-b border-gray-100 flex items-center justify-between">
                    <div className="text-[10px] text-gray-400 flex items-center gap-1">
                      <span>Market Feed</span><span>›</span>
                      <span className="text-gray-600">Mergers/Acquisitions</span><span>›</span>
                      <span className="text-gray-900 font-medium">Reliance Industries Ltd</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] px-2 py-1 border border-green-200 bg-green-50 text-green-700 rounded font-medium flex items-center gap-1">
                        <Bookmark size={10} fill="currentColor" />Saved
                      </span>
                      <span className="text-[10px] px-2 py-1 border border-gray-200 text-gray-500 rounded font-medium">Share</span>
                    </div>
                  </div>
                  <div className="flex-1 overflow-y-auto px-5 py-4">
                    <h2 className="text-[15px] font-bold text-gray-900 leading-snug mb-1.5">
                      Reliance Acquires 73% Stake in Karkinos Healthcare for ₹1,200 Cr
                    </h2>
                    <p className="text-[10px] text-gray-400 mb-3">22 Feb 2026 · 14:32 IST</p>
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-green-50 text-green-700 mb-3">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500" />Positive
                    </span>
                    {/* Mock markdown content */}
                    <div className="border-t border-gray-100 pt-3 text-[11px] text-gray-700 space-y-2">
                      <p className="font-bold text-gray-900 text-[12px]">Acquisition Overview</p>
                      <p>Reliance Industries Limited has entered into a <strong className="text-gray-900">definitive agreement</strong> to acquire a <strong className="text-gray-900">73% controlling stake</strong> in Karkinos Healthcare Pvt. Ltd.</p>
                      <div className="border border-gray-200 rounded-lg overflow-hidden">
                        <table className="w-full text-[10px]">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="text-left px-3 py-1.5 font-semibold text-gray-900 border-b border-gray-200">Parameter</th>
                              <th className="text-left px-3 py-1.5 font-semibold text-gray-900 border-b border-gray-200">Details</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[
                              ["Acquirer", "Reliance Industries Ltd"],
                              ["Target", "Karkinos Healthcare Pvt. Ltd"],
                              ["Stake", "73%"],
                              ["Consideration", "₹1,200 Crore"],
                              ["Expected Closure", "Q1 FY27"],
                            ].map(([k, v], ri) => (
                              <tr key={ri} className="border-b border-gray-50 last:border-0">
                                <td className="px-3 py-1.5 font-medium text-gray-900">{k}</td>
                                <td className="px-3 py-1.5 text-gray-600">{v}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <p className="font-bold text-gray-900 text-[12px]">Strategic Rationale</p>
                      <ul className="list-disc list-inside space-y-0.5 text-gray-600">
                        <li>Strengthens digital healthcare ecosystem</li>
                        <li>AI-powered oncology platform complements Jio Health</li>
                        <li>Access to <strong className="text-gray-900">500+ hospital partnerships</strong></li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Social Proof Bar */}
          <div className="mt-16">
            <div className="max-w-2xl mx-auto">
              <p className="text-center text-sm text-gray-500 mb-5">
                Trusted by <span className="font-semibold text-gray-900">4,200+</span> investors and analysts across India
              </p>
              <div className="bg-gray-50 border border-gray-100 rounded-xl px-6 py-4">
                <p className="text-sm text-gray-700 italic leading-relaxed">
                  &ldquo;Caught the Adani SEBI notice 3 hours before it trended on Twitter. The Telegram alert alone is worth it.&rdquo;
                </p>
                <p className="text-xs text-gray-400 mt-2 font-medium">— Investor & Analyst, Mumbai</p>
              </div>
              <div className="flex items-center justify-center gap-8 text-gray-300 text-sm font-semibold flex-wrap mt-6">
                <span>NSE</span>
                <span className="w-1 h-1 rounded-full bg-gray-200" />
                <span>BSE</span>
                <span className="w-1 h-1 rounded-full bg-gray-200" />
                <span>5,000+ Companies</span>
                <span className="w-1 h-1 rounded-full bg-gray-200" />
                <span>45+ Categories</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ───── Feature 1: AI Summary Deep Dive ───── */}
      <section id="features" className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium mb-4">
                <Zap size={12} /> AI-Powered
              </div>
              <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-4 font-[family-name:var(--font-display)]">
                Stop reading 50-page PDFs.<br />Start acting in 30 seconds.
              </h2>
              <p className="text-gray-500 leading-relaxed mb-6">
                Our AI reads every BSE/NSE filing and delivers the only 3 things you actually need: what happened, whether it&apos;s bullish or bearish, and the key numbers in a table.
              </p>
              <ul className="space-y-3">
                {["What happened — clean, structured summary in seconds", "Bullish or bearish — instant sentiment analysis", "Key numbers — auto-extracted into data tables", "45+ categories auto-classified, zero manual work"].map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-sm text-gray-600">
                    <div className="w-5 h-5 rounded-full bg-green-50 flex items-center justify-center shrink-0">
                      <Check size={12} className="text-green-600" />
                    </div>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Mock AI summary card */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-lg shadow-gray-100/50 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="text-[11px] text-gray-400 flex items-center gap-1.5">
                  <span>Announcements</span><ChevronRight size={10} />
                  <span className="text-rose-600 font-medium">Mergers/Acquisitions</span><ChevronRight size={10} />
                  <span className="text-gray-900 font-medium">Reliance Industries</span>
                </div>
              </div>
              <div className="px-5 py-4">
                <h3 className="text-[14px] font-bold text-gray-900 mb-1">
                  Reliance Acquires 73% Stake in Karkinos Healthcare for ₹1,200 Cr
                </h3>
                <p className="text-[11px] text-gray-400 mb-3">22 Feb 2026 · 14:32 IST</p>
                <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-2.5 py-1 rounded-full bg-green-50 text-green-700 mb-4">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500" />Positive
                </span>
                <div className="border-t border-gray-100 pt-3 text-[12px] text-gray-700 space-y-2.5">
                  <p className="font-bold text-gray-900">Acquisition Overview</p>
                  <p>Reliance Industries Limited has entered into a <strong className="text-gray-900">definitive agreement</strong> to acquire a 73% controlling stake in Karkinos Healthcare.</p>
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <table className="w-full text-[11px]">
                      <thead className="bg-gray-50"><tr><th className="text-left px-3 py-2 font-semibold border-b border-gray-200">Parameter</th><th className="text-left px-3 py-2 font-semibold border-b border-gray-200">Details</th></tr></thead>
                      <tbody>
                        {[["Stake Acquired","73%"],["Consideration","₹1,200 Crore"],["Expected Closure","Q1 FY27"]].map(([k,v],i)=>(
                          <tr key={i} className="border-b border-gray-50 last:border-0"><td className="px-3 py-1.5 font-medium text-gray-900">{k}</td><td className="px-3 py-1.5">{v}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="font-bold text-gray-900">Strategic Rationale</p>
                  <ul className="list-disc list-inside text-gray-600 space-y-0.5">
                    <li>Strengthens Reliance&apos;s digital healthcare ecosystem</li>
                    <li>AI-powered oncology platform complements Jio Health Hub</li>
                    <li>Access to <strong className="text-gray-900">500+ hospital partnerships</strong></li>
                    <li>Expected to generate <strong className="text-gray-900">₹800 Cr revenue</strong> in FY27</li>
                  </ul>
                  <div className="mt-2 pt-2 border-t border-gray-100">
                    <p className="text-[10px] font-semibold text-gray-900 mb-1.5">Key Investors / Stakeholders</p>
                    <div className="flex flex-wrap gap-1.5">
                      {["Mukesh D. Ambani", "Karkinos Healthcare", "Jio Platforms"].map((n) => (
                        <span key={n} className="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{n}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ───── Feature 2: Notifications & Alerts ───── */}
      <section className="py-20 px-6 bg-gray-50/50 border-t border-b border-gray-100">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Mock notifications */}
            <div className="order-2 lg:order-1 space-y-5">
              {/* In-app — looks like the Live Market Feed with new announcements toast */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-xl shadow-gray-200/40 overflow-hidden max-w-sm">
                <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
                  <Radio size={14} className="text-orange-500" />
                  <span className="text-sm font-bold text-gray-900">Live Market Feed</span>
                  <span className="text-[10px] text-gray-400 ml-auto">24,891</span>
                </div>
                {/* New announcements toast */}
                <div className="px-4 py-2 bg-gray-900 flex items-center justify-center gap-2">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500" />
                  </span>
                  <span className="text-xs font-medium text-white">3 new announcements</span>
                  <span className="text-gray-400 text-xs">↑</span>
                </div>
                <div className="divide-y divide-gray-50">
                  {[
                    { co: "Reliance Industries Ltd", hl: "Reliance Acquires 73% Stake in Karkinos Healthcare for ₹1,200 Cr", cat: "Mergers/Acquisitions", catBg: "bg-rose-50", catText: "text-rose-700", time: " 14:32", sentiment: "Positive", sentColor: "text-green-600", sentDot: "bg-green-500", active: true },
                    { co: "Tata Motors Ltd", hl: "Tata Motors Board Approves ₹7,500 Cr Investment in EV Gigafactory at Sanand", cat: "Expansion", catBg: "bg-emerald-100", catText: "text-emerald-800", time: " 13:18", sentiment: "Positive", sentColor: "text-green-600", sentDot: "bg-green-500", active: false },
                    { co: "Adani Enterprises Ltd", hl: "SEBI Issues Show Cause Notice to Adani Group Over Related Party Transactions", cat: "Litigation & Notices", catBg: "bg-rose-100", catText: "text-rose-800", time: " 09:50", sentiment: "Negative", sentColor: "text-red-600", sentDot: "bg-red-500", active: false },
                  ].map((item, i) => (
                    <div
                      key={i}
                      className={`px-4 py-3 cursor-default ${item.active ? "bg-orange-50/40" : ""}`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-0.5">
                        <span className="text-[12px] font-bold text-gray-900 truncate">{item.co}</span>
                        <span className="text-[9px] text-gray-400 shrink-0">{item.time}</span>
                      </div>
                      <p className="text-[11px] text-gray-600 line-clamp-2 leading-snug mb-1.5">{item.hl}</p>
                      <div className="flex items-center justify-between">
                        <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${item.catBg} ${item.catText}`}>
                          {item.cat}
                        </span>
                        <span className={`flex items-center gap-1 text-[10px] font-medium ${item.sentColor}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${item.sentDot}`} />
                          {item.sentiment}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Telegram mock — realistic chat bubble */}
              <div className="bg-[#0F1621] rounded-xl overflow-hidden shadow-xl shadow-gray-200/40 max-w-sm">
                {/* Telegram header */}
                <div className="px-4 py-2.5 flex items-center gap-3 border-b border-white/5">
                  <div className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center shrink-0 overflow-hidden p-1">
                    <svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
                      <polyline points="6,20 12,20 15,12 18,26 21,16 24,22 27,14 30,20" stroke="#FFFFFF" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                    </svg>
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[13px] font-semibold text-white">MarketWire Bot</span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="#3B82F6"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" fill="#3B82F6"/></svg>
                    </div>
                    <span className="text-[10px] text-gray-400">bot · last seen just now</span>
                  </div>
                </div>
                {/* Chat area */}
                <div className="px-3 py-3 space-y-2">
                  <div className="bg-[#182533] rounded-xl rounded-tl-sm px-3.5 py-2.5 max-w-[310px] text-[12px] text-gray-200 space-y-1.5">
                    <p className="font-semibold text-white">🛒 New Announcement</p>
                    <p className="text-[11px] text-gray-400 leading-relaxed">
                      🏢 <span className="text-white font-medium">Reliance Industries Ltd</span><br />
                      📌 RELIANCE<br />
                      📂 Mergers/Acquisitions<br />
                      📅 22 Feb 2026
                    </p>
                    <p className="text-white font-medium">Reliance Acquires 73% Stake in Karkinos Healthcare for ₹1,200 Cr</p>
                    <p className="text-gray-400 leading-relaxed text-[11px]">Entered into definitive agreement to acquire 73% controlling stake. Transaction valued at ₹1,200 Crore...</p>
                    <p className="text-[11px]">💡 Sentiment: 📈 Positive</p>
                    <div className="pt-1 space-y-0.5">
                      <p className="text-[11px]">📄 <span className="text-blue-400 underline">View Document</span></p>
                      <p className="text-[11px]">🔗 <span className="text-blue-400 underline">View on MarketWire</span></p>
                    </div>
                    <p className="text-[9px] text-gray-500 text-right">9:51 AM ✓✓</p>
                  </div>
                </div>
              </div>

              {/* Email mock — realistic inbox email */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-xl shadow-gray-200/40 overflow-hidden max-w-sm">
                {/* Email header */}
                <div className="px-4 py-3 border-b border-gray-100">
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center shrink-0 overflow-hidden p-1">
                      <svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
                        <polyline points="6,20 12,20 15,12 18,26 21,16 24,22 27,14 30,20" stroke="#FFFFFF" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-[12px] font-semibold text-gray-900">MarketWire</span>
                        <span className="text-[10px] text-gray-400">6:30 PM</span>
                      </div>
                      <p className="text-[10px] text-gray-400 truncate">to me</p>
                    </div>
                  </div>
                  <p className="text-[13px] font-semibold text-gray-900">📊 Your Daily Digest — 22 Feb 2026</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">12 announcements from 3 watchlists</p>
                </div>
                {/* Email body */}
                <div className="px-4 py-3 space-y-2.5">
                  <p className="text-[11px] text-gray-600">Here&apos;s what happened with your tracked companies today:</p>
                  {[
                    { co: "Reliance Industries", hl: "Acquires 73% Stake in Karkinos Healthcare", sent: "Positive", sentColor: "text-green-600", sentBg: "bg-green-50", cat: "M&A" },
                    { co: "Tata Motors", hl: "₹7,500 Cr EV Gigafactory at Sanand", sent: "Positive", sentColor: "text-green-600", sentBg: "bg-green-50", cat: "Expansion" },
                    { co: "Adani Enterprises", hl: "SEBI Show Cause Notice — Related Party Tx", sent: "Negative", sentColor: "text-red-600", sentBg: "bg-red-50", cat: "Litigation" },
                  ].map((e, i) => (
                    <div key={i} className="border border-gray-100 rounded-lg p-2.5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-semibold text-gray-900">{e.co}</span>
                        <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${e.sentBg} ${e.sentColor}`}>{e.sent}</span>
                      </div>
                      <p className="text-[11px] text-gray-600 leading-snug">{e.hl}</p>
                      <span className="text-[9px] text-gray-400 mt-1 inline-block">{e.cat}</span>
                    </div>
                  ))}
                  <div className="pt-2 text-center">
                    <span className="text-[11px] text-orange-500 font-medium">View all 12 announcements on MarketWire →</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="order-1 lg:order-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-medium mb-4">
                <Bell size={12} /> Real-Time Alerts
              </div>
              <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-4 font-[family-name:var(--font-display)]">
                The Adani SEBI notice dropped at 9:50 AM.<br />
                <span className="text-blue-600">MarketWire pinged at 9:51 AM.</span>
              </h2>
              <p className="text-gray-500 leading-relaxed mb-4">
                The stock moved 4% by 10:15 AM. Where were you?
              </p>
              <p className="text-gray-500 leading-relaxed mb-6">
                Get instant alerts on Telegram, WhatsApp, or email — filtered to only the companies and categories you care about.
              </p>
              <ul className="space-y-3">
                {[
                  "Telegram & WhatsApp — instant, the moment a filing drops",
                  "Email digest — clean end-of-day summary",
                  "Per-watchlist alert preferences",
                  "Filter alerts by category and sentiment",
                  "In-app notification badges in real-time",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-sm text-gray-600">
                    <div className="w-5 h-5 rounded-full bg-blue-50 flex items-center justify-center shrink-0">
                      <Check size={12} className="text-blue-600" />
                    </div>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ───── Feature 3: Save & Price Track ───── */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-medium mb-4">
                <Bookmark size={12} /> Save & Track
              </div>
              <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-4 font-[family-name:var(--font-display)]">
                Did the acquisition<br />actually move the stock?
              </h2>
              <p className="text-gray-500 leading-relaxed mb-6">
                Save any filing in one click. MarketWire tracks the stock price from that exact moment — so you know if your thesis played out, and learn to trade the next one better.
              </p>
              <ul className="space-y-3">
                {[
                  "One-click save with personal notes",
                  "Automatic price tracking from the moment you save",
                  "Sort by latest, oldest, largest gain/loss",
                  "Learn what moves the market — and what doesn't",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-sm text-gray-600">
                    <div className="w-5 h-5 rounded-full bg-amber-50 flex items-center justify-center shrink-0">
                      <Check size={12} className="text-amber-600" />
                    </div>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Mock saved detail */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-lg shadow-gray-100/50 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="text-[11px] text-gray-400 flex items-center gap-1.5">
                  <span>Saved</span><ChevronRight size={10} />
                  <span>Announcements</span><ChevronRight size={10} />
                  <span className="text-gray-600">Increase in Share Capital</span><ChevronRight size={10} />
                  <span className="text-gray-900 font-medium">Wipro Ltd</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] px-2 py-1 border border-green-200 bg-green-50 text-green-700 rounded font-medium flex items-center gap-1">
                    <Bookmark size={10} fill="currentColor" />Saved
                  </span>
                </div>
              </div>
              <div className="px-5 py-4">
                <h3 className="text-[14px] font-bold text-gray-900 mb-1">
                  Wipro Allots 44,401 Equity Shares Upon Exercise of ESOPs
                </h3>
                <p className="text-[11px] text-gray-400 mb-3">06 Oct 2025 - 20:58 IST</p>

                {/* Yellow saved info block */}
                <div className="border-l-4 border-amber-400 bg-amber-50/80 rounded-r-lg px-4 py-3 mb-4 space-y-1">
                  <p className="text-[12px] text-gray-700">
                    <span className="font-semibold text-gray-800">Saved on:</span> 7 Oct 2025
                  </p>
                  <p className="text-[12px]">
                    <span className="font-semibold text-gray-800">% change since saved:</span>{" "}
                    <span className="font-semibold text-red-600">-5.61%</span>
                  </p>
                  <p className="text-[10px] text-gray-500">₹562.30 → ₹530.75</p>
                  <div className="pt-1">
                    <p className="text-[12px] font-semibold text-gray-800">Your Note:</p>
                    <p className="text-[12px] text-gray-700 mt-0.5 flex items-start gap-1.5">
                      <StickyNote size={11} className="text-amber-500 shrink-0 mt-0.5" />
                      Track ESOP dilution impact on stock price
                    </p>
                  </div>
                </div>

                <div className="border-t border-gray-100 pt-3 text-[12px] text-gray-700 space-y-2">
                  <p className="font-bold text-gray-900">Allotment of Equity Shares</p>
                  <p>This announcement informs the stock exchanges regarding the allotment of equity shares by Wipro Limited. The allotment is pursuant to the exercise of Employee Stock Option Plans (ESOPs).</p>
                  <p className="font-bold text-gray-900">Details of Allotment:</p>
                  <ul className="list-disc list-inside text-gray-600 space-y-0.5">
                    <li><strong className="text-gray-900">5,932</strong> equity shares under ADS Restricted Stock Unit Plan 2004</li>
                    <li><strong className="text-gray-900">38,469</strong> equity shares under Restricted Stock Unit Plan 2007</li>
                  </ul>
                  <p>These allotments were made on <strong className="text-gray-900">October 6, 2025</strong>.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ───── Feature 4: Insider Trades & Deals ───── */}
      <section className="py-20 px-6 bg-gray-50/50 border-t border-b border-gray-100">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium mb-4">
              <BarChart3 size={12} /> Smart Money Tracking
            </div>
            <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-3 font-[family-name:var(--font-display)]">
              Mukesh Ambani just bought ₹312 Cr of Reliance.<br />
              <span className="text-emerald-600">Did you know?</span>
            </h2>
            <p className="text-gray-500 max-w-xl mx-auto">
              Insider trades, bulk deals, and block deals — the moves promoters and FIIs make before filings hit the news cycle.
            </p>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            {/* Insider trades mock */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-lg shadow-gray-100/50 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
                <UserCheck size={16} className="text-gray-400" />
                <span className="text-sm font-bold text-gray-900">Insider Trades</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead className="bg-gray-50">
                    <tr>
                      {["Person", "Company", "Type", "Qty", "Value"].map((h) => (
                        <th key={h} className="text-left px-4 py-2 font-semibold text-gray-600 border-b border-gray-200 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_INSIDER_TRADES.map((t, i) => (
                      <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                        <td className="px-4 py-2.5 font-medium text-gray-900 whitespace-nowrap">{t.person}</td>
                        <td className="px-4 py-2.5 text-gray-600 whitespace-nowrap">{t.company}</td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${
                            t.type === "Acquisition" ? "bg-green-50 text-green-700" :
                            t.type === "Disposal" ? "bg-red-50 text-red-700" :
                            "bg-amber-50 text-amber-700"
                          }`}>{t.type}</span>
                        </td>
                        <td className="px-4 py-2.5 text-gray-600">{t.qty}</td>
                        <td className="px-4 py-2.5 font-medium text-gray-900">{t.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Bulk/Block deals mock */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-lg shadow-gray-100/50 overflow-hidden">
              <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
                <Layers size={16} className="text-gray-400" />
                <span className="text-sm font-bold text-gray-900">Bulk & Block Deals</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead className="bg-gray-50">
                    <tr>
                      {["Company", "Type", "Buyer", "Qty", "Value"].map((h) => (
                        <th key={h} className="text-left px-4 py-2 font-semibold text-gray-600 border-b border-gray-200 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_DEALS.map((d, i) => (
                      <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                        <td className="px-4 py-2.5 font-medium text-gray-900 whitespace-nowrap">{d.company}</td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${
                            d.type === "Block Deal" ? "bg-indigo-50 text-indigo-700" : "bg-sky-50 text-sky-700"
                          }`}>{d.type}</span>
                        </td>
                        <td className="px-4 py-2.5 text-gray-600 whitespace-nowrap">{d.buyer}</td>
                        <td className="px-4 py-2.5 text-gray-600">{d.qty}</td>
                        <td className="px-4 py-2.5 font-medium text-gray-900">{d.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ───── Feature 5: Watchlists ───── */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Mock watchlist */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-lg shadow-gray-100/50 overflow-hidden">
              <div className="flex h-[400px]">
                {/* Left panel */}
                <div className="w-[200px] border-r border-gray-100 flex flex-col">
                  <div className="px-4 py-3 border-b border-gray-100">
                    <p className="text-xs font-bold text-gray-900">My Watchlists</p>
                  </div>
                  <div className="flex-1">
                    {[
                      { name: "Large Cap Portfolio", count: 12, active: true },
                      { name: "Pharma Picks", count: 8, active: false },
                      { name: "IT Sector", count: 6, active: false },
                    ].map((wl, i) => (
                      <div
                        key={i}
                        className={`px-4 py-3 cursor-default flex items-center gap-2 ${wl.active ? "bg-gray-50" : ""}`}
                      >
                        <List size={13} className="text-gray-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className={`text-[11px] font-medium truncate ${wl.active ? "text-gray-900" : "text-gray-600"}`}>{wl.name}</p>
                          <p className="text-[10px] text-gray-400">{wl.count} Companies</p>
                        </div>
                        <ChevronRight size={12} className="text-gray-300 shrink-0" />
                      </div>
                    ))}
                  </div>
                  <div className="p-3 border-t border-gray-100">
                    <div className="flex items-center justify-center gap-1.5 text-[11px] text-gray-500 py-2 border border-gray-200 rounded-lg font-medium">
                      <span className="text-lg leading-none">+</span> Create New
                    </div>
                  </div>
                </div>

                {/* Right panel */}
                <div className="flex-1 flex flex-col">
                  <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                    <p className="text-sm font-bold text-gray-900">Large Cap Portfolio</p>
                    <span className="text-[10px] px-2.5 py-1 border border-gray-200 rounded-lg text-gray-500 font-medium">Edit</span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-5">
                    <div className="grid grid-cols-1 gap-4">
                      <div className="border border-gray-200 rounded-lg">
                        <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-2">
                          <Building2 size={13} className="text-gray-400" />
                          <span className="text-[11px] font-semibold text-gray-900">Tracked Companies (12)</span>
                        </div>
                        <div className="divide-y divide-gray-50">
                          {["Reliance Industries Ltd", "HDFC Bank Ltd", "Infosys Ltd", "TCS Ltd", "Bharti Airtel Ltd"].map((c) => (
                            <div key={c} className="px-4 py-2 text-[11px] text-gray-700 font-medium">{c}</div>
                          ))}
                          <div className="px-4 py-2 text-[11px] text-blue-600 font-medium">Show 7 More</div>
                        </div>
                      </div>
                      <div className="border border-gray-200 rounded-lg">
                        <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-2">
                          <Tag size={13} className="text-gray-400" />
                          <span className="text-[11px] font-semibold text-gray-900">Tracked Categories (4)</span>
                        </div>
                        <div className="p-3 flex flex-wrap gap-1.5">
                          {["Mergers/Acquisitions", "Financial Results", "Expansion", "Buyback"].map((c) => (
                            <span key={c} className="text-[10px] bg-gray-100 text-gray-700 px-2.5 py-1 rounded-full font-medium">{c}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-50 text-violet-700 text-xs font-medium mb-4">
                <List size={12} /> Watchlist Management
              </div>
              <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-4 font-[family-name:var(--font-display)]">
                You follow 8 pharma stocks<br />and hate reading about IT deals.
              </h2>
              <p className="text-gray-500 leading-relaxed mb-6">
                Build watchlists that match your portfolio — set alerts by company, category, and sentiment. MarketWire filters out the noise before it reaches you.
              </p>
              <ul className="space-y-3">
                {[
                  "Unlimited watchlists with custom names",
                  "Smart company search — type name, get results",
                  "Filter by announcement category per watchlist",
                  "Set alert channel per watchlist (Telegram / Email / None)",
                  "Only see what matters to your portfolio",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-sm text-gray-600">
                    <div className="w-5 h-5 rounded-full bg-violet-50 flex items-center justify-center shrink-0">
                      <Check size={12} className="text-violet-600" />
                    </div>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ───── Feature 6: Filters & Categories ───── */}
      <section className="py-20 px-6 bg-gray-50/50 border-t border-b border-gray-100">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-50 text-cyan-700 text-xs font-medium mb-4">
                <Filter size={12} /> Advanced Filtering
              </div>
              <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-4 font-[family-name:var(--font-display)]">
                Cut through the noise<br />in seconds
              </h2>
              <p className="text-gray-500 leading-relaxed mb-6">
                With 45+ announcement categories, multi-dimensional filtering, and sentiment analysis — find exactly the filings that matter to your investment thesis.
              </p>
              <ul className="space-y-3">
                {[
                  "45+ auto-classified announcement categories",
                  "Filter by date range, company, category, sentiment",
                  "Combine multiple filters simultaneously",
                  "Read/Unread tracking across sessions",
                  "Category-specific color coding for quick scanning",
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-sm text-gray-600">
                    <div className="w-5 h-5 rounded-full bg-cyan-50 flex items-center justify-center shrink-0">
                      <Check size={12} className="text-cyan-600" />
                    </div>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Mock filter categories */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-lg shadow-gray-100/50 overflow-hidden max-w-md mx-auto w-full">
              <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between">
                <span className="text-sm font-bold text-gray-900">Category Filter</span>
                <span className="text-[10px] text-orange-500 font-medium">8 selected</span>
              </div>
              <div className="px-5 py-3 border-b border-gray-100">
                <div className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg">
                  <Search size={14} className="text-gray-400" />
                  <span className="text-[12px] text-gray-400">Search categories...</span>
                </div>
              </div>
              <div className="px-5 py-4 max-h-[340px] overflow-y-auto space-y-4">
                {[
                  { title: "Capital & Financing", cats: [
                    { name: "Fundraise - Rights Issue", checked: true },
                    { name: "Fundraise - QIP", checked: false },
                    { name: "Increase in Share Capital", checked: true },
                    { name: "Debt Reduction", checked: false },
                  ]},
                  { title: "Corporate Actions", cats: [
                    { name: "Mergers/Acquisitions", checked: true },
                    { name: "Bonus/Stock Split", checked: true },
                    { name: "Demerger", checked: false },
                    { name: "Buyback", checked: true },
                    { name: "Open Offer", checked: false },
                  ]},
                  { title: "Strategic & Business", cats: [
                    { name: "Expansion", checked: true },
                    { name: "New Order", checked: true },
                    { name: "Agreements/MoUs", checked: false },
                    { name: "New Product", checked: true },
                  ]},
                  { title: "Financial Reporting", cats: [
                    { name: "Financial Results", checked: false },
                    { name: "Credit Rating", checked: false },
                  ]},
                ].map((group) => (
                  <div key={group.title}>
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">{group.title}</p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {group.cats.map((cat) => (
                        <div
                          key={cat.name}
                          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] ${
                            cat.checked ? "bg-orange-50 text-orange-700 font-medium" : "text-gray-600"
                          }`}
                        >
                          <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${
                            cat.checked ? "bg-orange-500 border-orange-500" : "border-gray-300"
                          }`}>
                            {cat.checked && (
                              <svg width="8" height="6" viewBox="0 0 10 8" fill="none">
                                <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            )}
                          </div>
                          {cat.name}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ───── CTA ───── */}
      <section className="py-20 px-6 bg-gray-900">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-sm text-gray-500 mb-6 italic">
            The filing dropped. The stock moved. You found out at dinner.
          </p>
          <h2 className="text-3xl font-extrabold text-white tracking-tight mb-4 font-[family-name:var(--font-display)]">
            The next Adani SEBI notice, Reliance acquisition,<br />or HDFC earnings beat is dropping today.
          </h2>
          <p className="text-gray-400 mb-8 max-w-lg mx-auto">
            Are you going to read about it tomorrow on Moneycontrol, or know about it in 60 seconds?
          </p>
          <Link
            href="/auth"
            className="inline-flex items-center gap-2 px-8 py-3.5 bg-orange-500 text-white font-semibold rounded-lg hover:bg-orange-600 transition text-sm"
          >
            Start Free — No Card Required <ArrowRight size={16} />
          </Link>
          <div className="flex items-center justify-center gap-6 mt-6 text-sm">
            <div className="text-gray-500">
              <span className="text-gray-300 font-medium">Free:</span> 10 alerts/day, 2 watchlists
            </div>
            <div className="w-px h-4 bg-gray-700" />
            <div className="text-gray-500">
              <span className="text-orange-400 font-medium">Pro:</span> Unlimited everything · ₹499/mo
            </div>
          </div>
        </div>
      </section>

      {/* ───── Footer ───── */}
      <footer className="px-6 py-8 border-t border-gray-100">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Logo variant="full" theme="dark" className="h-5" />
          </div>
          <p className="text-xs text-gray-400">
            © {new Date().getFullYear()} MarketWire. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}

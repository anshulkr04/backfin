"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { Logo } from "@/components/logo";
import {
  Radio,
  Zap,
  Bookmark,
  Bell,
  ArrowRight,
  ChevronRight,
  Eye,
  EyeOff,
  Check,
  Phone,
  Mail,
  Lock,
  User,
  TrendingUp,
  TrendingDown,
  MessageCircle,
} from "lucide-react";

/* ────────────────────────────────────────────────
   Animated feature slides for the left panel
   ──────────────────────────────────────────────── */

function LiveFeedMock() {
  const items = [
    { co: "Reliance Industries", hl: "Acquires 73% Stake in Karkinos Healthcare for ₹1,200 Cr", cat: "Mergers/Acquisitions", catBg: "bg-rose-50", catText: "text-rose-700", sent: "Positive", sentDot: "bg-green-500", sentColor: "text-green-600", time: "14:32" },
    { co: "Tata Motors Ltd", hl: "Board Approves ₹7,500 Cr EV Gigafactory at Sanand", cat: "Expansion", catBg: "bg-emerald-50", catText: "text-emerald-700", sent: "Positive", sentDot: "bg-green-500", sentColor: "text-green-600", time: "13:18" },
    { co: "HDFC Bank Ltd", hl: "Q3 FY26 Net Profit Rises 22% YoY to ₹17,657 Cr", cat: "Financial Results", catBg: "bg-indigo-50", catText: "text-indigo-700", sent: "Positive", sentDot: "bg-green-500", sentColor: "text-green-600", time: "11:45" },
    { co: "Adani Enterprises", hl: "SEBI Issues Show Cause Notice Over Related Party Transactions", cat: "Litigation", catBg: "bg-rose-50", catText: "text-rose-700", sent: "Negative", sentDot: "bg-red-500", sentColor: "text-red-600", time: "09:50" },
  ];
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden w-full max-w-sm">
      <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-2">
        <Radio size={13} className="text-orange-500" />
        <span className="text-xs font-bold text-gray-900">Live Market Feed</span>
        <span className="text-[9px] text-gray-400 ml-auto">24,891</span>
      </div>
      {items.map((item, i) => (
        <div
          key={i}
          className={`px-4 py-2.5 border-b border-gray-50 ${i === 0 ? "bg-orange-50/40" : ""} animate-fade-in`}
          style={{ animationDelay: `${i * 150}ms` }}
        >
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[11px] font-bold text-gray-900 truncate">{item.co}</span>
            <span className="text-[9px] text-gray-400">{item.time}</span>
          </div>
          <p className="text-[10px] text-gray-600 line-clamp-1 mb-1">{item.hl}</p>
          <div className="flex items-center justify-between">
            <span className={`text-[8px] font-medium px-1.5 py-0.5 rounded-full ${item.catBg} ${item.catText}`}>{item.cat}</span>
            <span className={`flex items-center gap-1 text-[9px] font-medium ${item.sentColor}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${item.sentDot}`} />
              {item.sent}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function AISummaryMock() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden w-full max-w-sm">
      <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-1.5 text-[10px] text-gray-400">
        <Zap size={11} className="text-indigo-500" />
        <span className="font-medium text-gray-900">AI Summary</span>
        <ChevronRight size={9} />
        <span className="text-rose-600">Mergers/Acquisitions</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        <h3 className="text-[12px] font-bold text-gray-900 animate-fade-in">Reliance Acquires 73% Stake in Karkinos Healthcare</h3>
        <span className="inline-flex items-center gap-1 text-[9px] font-semibold px-2 py-0.5 rounded-full bg-green-50 text-green-700 animate-fade-in" style={{animationDelay:'100ms'}}>
          <span className="w-1.5 h-1.5 rounded-full bg-green-500" />Positive
        </span>
        <div className="border border-gray-200 rounded-lg overflow-hidden animate-fade-in" style={{animationDelay:'200ms'}}>
          <table className="w-full text-[10px]">
            <thead className="bg-gray-50"><tr><th className="text-left px-3 py-1.5 font-semibold border-b border-gray-200">Parameter</th><th className="text-left px-3 py-1.5 font-semibold border-b border-gray-200">Details</th></tr></thead>
            <tbody>
              {[["Stake","73%"],["Consideration","₹1,200 Cr"],["Closure","Q1 FY27"]].map(([k,v],i)=>(
                <tr key={i} className="border-b border-gray-50 last:border-0"><td className="px-3 py-1 font-medium text-gray-900">{k}</td><td className="px-3 py-1 text-gray-600">{v}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="list-disc list-inside text-[10px] text-gray-600 space-y-0.5 animate-fade-in" style={{animationDelay:'300ms'}}>
          <li>Digital healthcare ecosystem expansion</li>
          <li>Access to <strong className="text-gray-900">500+ hospital partnerships</strong></li>
          <li>Expected <strong className="text-gray-900">₹800 Cr revenue</strong> in FY27</li>
        </ul>
      </div>
    </div>
  );
}

function NotificationMock() {
  return (
    <div className="space-y-3 w-full max-w-sm">
      {/* In-app pill */}
      <div className="bg-gray-900 text-white rounded-full px-4 py-2 inline-flex items-center gap-2 text-[11px] font-medium animate-fade-in">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500" />
        </span>
        3 new announcements
      </div>
      {/* Telegram card */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden animate-fade-in" style={{animationDelay:'200ms'}}>
        <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-blue-50 flex items-center justify-center">
            <MessageCircle size={12} className="text-blue-500" />
          </div>
          <span className="text-[11px] font-bold text-gray-900">Telegram Alert</span>
        </div>
        <div className="px-4 py-3">
          <div className="bg-[#e8f5e1] rounded-lg p-2.5 text-[10px] text-gray-800 space-y-0.5 max-w-[260px]">
            <p className="font-bold">🚨 MarketWire Alert</p>
            <p><strong>Reliance Industries</strong></p>
            <p>Acquires 73% Stake in Karkinos Healthcare</p>
            <p className="text-gray-500 mt-1">🟢 Positive · Mergers/Acquisitions</p>
          </div>
        </div>
      </div>
      {/* Email digest */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden animate-fade-in" style={{animationDelay:'400ms'}}>
        <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-purple-50 flex items-center justify-center">
            <Mail size={12} className="text-purple-500" />
          </div>
          <span className="text-[11px] font-bold text-gray-900">Daily Email Digest</span>
        </div>
        <div className="px-4 py-2.5 space-y-1">
          {[{co:"Reliance",hl:"Karkinos Healthcare",s:"🟢"},{co:"Tata Motors",hl:"EV Gigafactory",s:"🟢"},{co:"Adani",hl:"SEBI Notice",s:"🔴"}].map((e,i)=>(
            <div key={i} className="flex items-center justify-between text-[10px] py-0.5">
              <span><strong className="text-gray-900">{e.co}</strong> <span className="text-gray-500">{e.hl}</span></span>
              <span>{e.s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SaveTrackMock() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden w-full max-w-sm">
      <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-1.5 text-[10px] text-gray-400">
        <Bookmark size={11} className="text-amber-500" fill="currentColor" />
        <span className="font-medium text-gray-900">Saved</span>
        <ChevronRight size={9} />
        <span>Wipro Ltd</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        <h3 className="text-[12px] font-bold text-gray-900 animate-fade-in">Wipro Allots 44,401 Equity Shares Under ESOPs</h3>
        <div className="border-l-4 border-amber-400 bg-amber-50/80 rounded-r-lg px-3 py-2 space-y-0.5 animate-fade-in" style={{animationDelay:'150ms'}}>
          <p className="text-[10px] text-gray-700"><span className="font-semibold">Saved on:</span> 7 Oct 2025</p>
          <p className="text-[10px]">
            <span className="font-semibold text-gray-700">Change:</span>{" "}
            <span className="font-semibold text-red-600 inline-flex items-center gap-0.5"><TrendingDown size={10} />-5.61%</span>
          </p>
          <p className="text-[9px] text-gray-500">₹562.30 → ₹530.75</p>
        </div>
        <div className="flex items-start gap-1.5 animate-fade-in" style={{animationDelay:'300ms'}}>
          <div className="w-4 h-4 rounded bg-amber-100 flex items-center justify-center shrink-0 mt-0.5">
            <span className="text-[8px]">📝</span>
          </div>
          <p className="text-[10px] text-gray-600 italic">Track ESOP dilution impact on stock price</p>
        </div>
      </div>
    </div>
  );
}

const SLIDES = [
  { title: "Real-time Market Feed", subtitle: "Live filings from NSE & BSE, AI-classified and deduplicated", component: LiveFeedMock },
  { title: "AI-Powered Summaries", subtitle: "Every filing transformed into structured, actionable intelligence", component: AISummaryMock },
  { title: "Multi-Channel Alerts", subtitle: "In-app, Telegram, WhatsApp & email notifications", component: NotificationMock },
  { title: "Save & Price Track", subtitle: "Bookmark filings and track stock performance over time", component: SaveTrackMock },
];

/* ────────────────────────────────────────────────
   AUTH PAGE
   ──────────────────────────────────────────────── */

export default function AuthPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [activeSlide, setActiveSlide] = useState(0);
  const [slideDirection, setSlideDirection] = useState<"next" | "prev">("next");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { login, register, loading, error, clearError } = useAuth();
  const router = useRouter();

  // Start / restart the auto-rotate timer
  const startTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setSlideDirection("next");
      setActiveSlide((prev) => (prev + 1) % SLIDES.length);
    }, 2800);
  }, []);

  useEffect(() => {
    startTimer();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [startTimer]);

  const goToSlide = (i: number) => {
    setSlideDirection(i > activeSlide ? "next" : "prev");
    setActiveSlide(i);
    startTimer(); // reset timer on manual click
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        if (password !== confirmPassword) {
          throw new Error("Passwords do not match");
        }
        await register(email, password, phone || undefined);
      }
      router.push("/dashboard");
    } catch {
      // error is set in store
    }
  };

  return (
    <div className="min-h-screen flex bg-white">
      {/* ───── Left Panel — Feature Showcase ───── */}
      <div className="hidden lg:flex lg:w-[55%] bg-gray-950 relative overflow-hidden">
        {/* Subtle gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 via-transparent to-indigo-500/5" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-orange-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-indigo-500/5 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col items-center justify-center w-full px-12 py-8">
          {/* Logo */}
          <div className="mb-8">
            <Link href="/" className="block">
              <Logo variant="full" theme="light" className="h-8" />
            </Link>
          </div>

          {/* Feature slides */}
          <div className="w-full flex flex-col items-center">
            {/* Title / subtitle — crossfade with vertical shift */}
            <div className="mb-6 text-center relative h-[52px] w-full">
              {SLIDES.map((slide, i) => (
                <div
                  key={i}
                  className="absolute inset-0 flex flex-col items-center justify-center transition-all duration-300 ease-out"
                  style={{
                    opacity: i === activeSlide ? 1 : 0,
                    transform: i === activeSlide
                      ? "translateY(0)"
                      : slideDirection === "next"
                        ? "translateY(12px)"
                        : "translateY(-12px)",
                    pointerEvents: i === activeSlide ? "auto" : "none",
                  }}
                >
                  <h2 className="text-xl font-bold text-white tracking-tight font-[family-name:var(--font-display)]">
                    {slide.title}
                  </h2>
                  <p className="text-sm text-gray-400 mt-1.5">{slide.subtitle}</p>
                </div>
              ))}
            </div>

            {/* Card carousel — horizontal slide + scale */}
            <div className="relative w-full overflow-hidden" style={{ minHeight: 340 }}>
              {SLIDES.map((slide, i) => {
                const SlideComponent = slide.component;
                return (
                  <div
                    key={i}
                    className="absolute inset-0 flex justify-center transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
                    style={{
                      opacity: i === activeSlide ? 1 : 0,
                      transform: i === activeSlide
                        ? "translateX(0) scale(1)"
                        : i < activeSlide || (activeSlide === 0 && i === SLIDES.length - 1 && slideDirection === "next")
                          ? "translateX(-60px) scale(0.95)"
                          : "translateX(60px) scale(0.95)",
                      pointerEvents: i === activeSlide ? "auto" : "none",
                    }}
                  >
                    <SlideComponent />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Slide dots with progress fill */}
          <div className="flex items-center gap-2.5 mt-8">
            {SLIDES.map((_, i) => (
              <button
                key={i}
                onClick={() => goToSlide(i)}
                className="relative h-2 transition-all duration-300 rounded-full overflow-hidden"
                style={{ width: i === activeSlide ? 24 : 8 }}
              >
                <span
                  className={`absolute inset-0 rounded-full transition-colors duration-300 ${
                    i === activeSlide ? "bg-orange-500/30" : "bg-gray-600 hover:bg-gray-500"
                  }`}
                />
                {i === activeSlide && (
                  <span
                    className="absolute inset-0 rounded-full bg-orange-500 origin-left"
                    style={{ animation: "dot-fill 2.8s linear forwards" }}
                  />
                )}
              </button>
            ))}
          </div>

          {/* Bottom tagline */}
          <p className="text-[11px] text-gray-500 mt-8 text-center">
            Trusted by investors tracking 5,000+ companies across NSE & BSE
          </p>
        </div>
      </div>

      {/* ───── Right Panel — Auth Form ───── */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-[#FAFAFA]">
        <div className="w-full max-w-[420px]">
          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-8">
            <Link href="/" className="inline-block">
              <Logo variant="full" theme="dark" className="h-8 mx-auto" />
            </Link>
            <p className="text-sm text-gray-500 mt-1">See the move before it happens.</p>
          </div>

          {/* Header */}
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight font-[family-name:var(--font-display)]">
              {mode === "login" ? "Welcome back" : "Create your account"}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              {mode === "login"
                ? "Sign in to access your dashboard"
                : "Start tracking market-moving filings for free"}
            </p>
          </div>

          {/* Card */}
          <div className="bg-white rounded-2xl border border-gray-200 p-7 shadow-sm">
            {/* Tabs */}
            <div className="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => { setMode("login"); clearError(); }}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                  mode === "login"
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Sign In
              </button>
              <button
                onClick={() => { setMode("register"); clearError(); }}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                  mode === "register"
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Create Account
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Email address
                </label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition"
                    placeholder="you@example.com"
                  />
                </div>
              </div>

              {/* Phone — only on register */}
              {mode === "register" && (
                <div className="animate-fade-in">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Phone number <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  <div className="relative">
                    <Phone size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition"
                      placeholder="+91 98765 43210"
                    />
                  </div>
                  <p className="text-[11px] text-gray-400 mt-1">For Telegram & WhatsApp alerts</p>
                </div>
              )}

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-10 pr-11 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition"
                    placeholder="••••••••"
                    minLength={6}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Confirm Password — only on register */}
              {mode === "register" && (
                <div className="animate-fade-in">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Confirm password
                  </label>
                  <div className="relative">
                    <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      type={showPassword ? "text" : "password"}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className={`w-full pl-10 pr-11 py-2.5 rounded-lg border text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 transition ${
                        confirmPassword && confirmPassword !== password
                          ? "border-red-300 focus:border-red-500 focus:ring-red-500/20"
                          : confirmPassword && confirmPassword === password
                          ? "border-green-300 focus:border-green-500 focus:ring-green-500/20"
                          : "border-gray-300 focus:border-orange-500"
                      }`}
                      placeholder="••••••••"
                      minLength={6}
                    />
                    {confirmPassword && (
                      <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
                        {confirmPassword === password ? (
                          <Check size={16} className="text-green-500" />
                        ) : (
                          <span className="text-[10px] text-red-500 font-medium">Mismatch</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2 animate-fade-in">
                  {error}
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={loading || (mode === "register" && confirmPassword !== password)}
                className="w-full py-2.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-white text-sm font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Please wait...
                  </>
                ) : mode === "login" ? (
                  <>
                    Sign In
                    <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                  </>
                ) : (
                  <>
                    Create Account
                    <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            {mode === "register" && (
              <div className="mt-5 pt-4 border-t border-gray-100 animate-fade-in">
                <p className="text-[11px] text-gray-400 text-center">What you get with a free account:</p>
                <div className="mt-3 space-y-2">
                  {[
                    "Real-time filings from NSE & BSE",
                    "AI-powered summaries & sentiment",
                    "Unlimited watchlists & saved items",
                    "Telegram & email alerts",
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-2 text-[12px] text-gray-600">
                      <div className="w-4 h-4 rounded-full bg-green-50 flex items-center justify-center shrink-0">
                        <Check size={10} className="text-green-600" />
                      </div>
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <p className="text-center text-[11px] text-gray-400 mt-5">
            By continuing, you agree to MarketWire&apos;s Terms and Privacy Policy.
          </p>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Sidebar } from "@/components/sidebar-new";
import {
  LayoutDashboard,
  Radio,
  Bookmark,
  List,
  Search,
} from "lucide-react";
import Link from "next/link";

const BOTTOM_TABS = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard },
  { href: "/dashboard/market-feed", label: "Feed", icon: Radio },
  { href: "/dashboard/saved", label: "Saved", icon: Bookmark },
  { href: "/dashboard/watchlists", label: "Lists", icon: List },
  { href: "/dashboard/search", label: "Search", icon: Search },
];

// Pages that are part of the "Feed" tab (highlight Feed icon)
const FEED_PAGES = [
  "/dashboard/market-feed",
  "/dashboard/financial-results",
  "/dashboard/concall-transcripts",
  "/dashboard/investor-presentations",
  "/dashboard/annual-reports",
  "/dashboard/bulk-block-deals",
  "/dashboard/insider-trades",
  "/dashboard/corporate-actions",
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { token, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !token) {
      router.replace("/auth");
    }
  }, [token, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!token) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* Desktop sidebar — always visible on md+ */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Main content — on mobile leave room for bottom tabs */}
      <main className="flex-1 overflow-hidden pb-[60px] md:pb-0">
        {children}
      </main>

      {/* ── Mobile bottom tab bar ── */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-gray-200 md:hidden safe-area-bottom">
        <div className="flex items-center justify-around h-[60px]">
          {BOTTOM_TABS.map((tab) => {
            const isActive =
              tab.href === "/dashboard"
                ? pathname === "/dashboard"
                : tab.href === "/dashboard/market-feed"
                ? FEED_PAGES.includes(pathname)
                : pathname.startsWith(tab.href);

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex flex-col items-center justify-center gap-0.5 flex-1 h-full transition-colors ${
                  isActive
                    ? "text-orange-600"
                    : "text-gray-400 active:text-gray-600"
                }`}
              >
                <tab.icon size={20} strokeWidth={isActive ? 2 : 1.5} />
                <span className="text-[10px] font-medium leading-none">
                  {tab.label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}

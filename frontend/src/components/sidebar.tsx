"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { getWatchlists, createWatchlist } from "@/lib/api";
import type { Watchlist } from "@/lib/api";
import {
  LayoutDashboard,
  Bookmark,
  Radio,
  Search,
  ChevronDown,
  LogOut,
  Plus,
  Eye,
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/saved", label: "Saved", icon: Bookmark },
  { href: "/dashboard/market-feed", label: "Market Feed", icon: Radio },
  { href: "/dashboard/search", label: "Search", icon: Search },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, token, logout } = useAuth();
  const [showUser, setShowUser] = useState(false);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [wlOpen, setWlOpen] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const fetchWatchlists = useCallback(async () => {
    if (!token) return;
    try {
      const res = await getWatchlists(token);
      setWatchlists(res.watchlists ?? []);
    } catch {
      // silent
    }
  }, [token]);

  useEffect(() => {
    fetchWatchlists();
  }, [fetchWatchlists]);

  const handleCreate = async () => {
    if (!token || !newName.trim()) return;
    try {
      await createWatchlist(token, newName.trim());
      setNewName("");
      setCreating(false);
      fetchWatchlists();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <aside className="w-[200px] flex-shrink-0 border-r border-gray-200 bg-white flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-gray-100">
        <Link href="/dashboard" className="text-lg font-bold text-gray-900 tracking-tight">
          MarketWire<span className="text-orange-500">.</span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
                isActive
                  ? "bg-orange-50 text-orange-600"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              }`}
            >
              <item.icon size={16} strokeWidth={isActive ? 2 : 1.5} />
              {item.label}
            </Link>
          );
        })}

        {/* Watchlists */}
        <div className="pt-4 pb-1 px-3 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Watchlists
          </span>
          <button
            onClick={() => setCreating(true)}
            className="text-gray-400 hover:text-orange-500 transition"
          >
            <Plus size={14} />
          </button>
        </div>

        {creating && (
          <div className="px-3 py-1.5 flex items-center gap-1">
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
                if (e.key === "Escape") setCreating(false);
              }}
              placeholder="Name..."
              className="flex-1 min-w-0 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-orange-400"
            />
          </div>
        )}

        {watchlists.map((wl) => (
          <div
            key={wl._id}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-gray-600"
          >
            <Eye size={14} className="text-gray-400 shrink-0" />
            <span className="truncate text-xs">{wl.watchlistName}</span>
            <span className="ml-auto text-[10px] text-gray-400">
              {wl.isin?.length ?? 0}
            </span>
          </div>
        ))}

        {/* Filters header */}
        <div className="pt-4 pb-1 px-3">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Filters
          </span>
        </div>
        <FilterSection title="Category" />
        <FilterSection title="Sentiment" />
      </nav>

      {/* User */}
      <div className="border-t border-gray-100 p-3 relative">
        <button
          onClick={() => setShowUser(!showUser)}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg hover:bg-gray-50 transition"
        >
          <div className="w-7 h-7 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xs font-semibold">
            {user?.emailID?.[0]?.toUpperCase() || "U"}
          </div>
          <span className="text-xs text-gray-600 truncate flex-1 text-left">
            {user?.emailID || "User"}
          </span>
          <ChevronDown size={12} className="text-gray-400" />
        </button>

        {showUser && (
          <div className="absolute bottom-full left-3 right-3 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden z-50">
            <button
              onClick={() => {
                logout();
                setShowUser(false);
              }}
              className="flex items-center gap-2 w-full px-3 py-2.5 text-sm text-red-600 hover:bg-red-50 transition"
            >
              <LogOut size={14} />
              Sign Out
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

function FilterSection({ title }: { title: string }) {
  const [open, setOpen] = useState(false);
  return (
    <button
      onClick={() => setOpen(!open)}
      className="flex items-center justify-between w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg transition"
    >
      <span>{title}</span>
      <ChevronDown
        size={14}
        className={`text-gray-400 transition ${open ? "rotate-180" : ""}`}
      />
    </button>
  );
}

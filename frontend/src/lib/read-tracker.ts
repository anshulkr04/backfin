"use client";

const STORAGE_KEY = "marketwire_read_ids";

function getReadSet(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw) as string[]);
  } catch {
    return new Set();
  }
}

function persist(ids: Set<string>) {
  if (typeof window === "undefined") return;
  try {
    // Keep only last 5000 entries to prevent storage bloat
    const arr = Array.from(ids);
    const trimmed = arr.length > 5000 ? arr.slice(arr.length - 5000) : arr;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // storage full — silently fail
  }
}

export function markAsRead(corpId: string) {
  const ids = getReadSet();
  ids.add(corpId);
  persist(ids);
}

export function isRead(corpId: string): boolean {
  return getReadSet().has(corpId);
}

export function getReadIds(): Set<string> {
  return getReadSet();
}

export function clearReadHistory() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}

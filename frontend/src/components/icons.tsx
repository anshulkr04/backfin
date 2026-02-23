"use client";

/**
 * Custom section icons for MarketWire.
 * Each icon uses a 24×24 viewBox with 1.5px strokes.
 * Props mirror Lucide's API so they drop in seamlessly.
 */

interface IconProps {
  size?: number;
  className?: string;
  strokeWidth?: number;
}

const defaults = { size: 24, strokeWidth: 1.5 };

/* ── Announcements ─ megaphone with sound wave ── */
export function AnnouncementsIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8a3 3 0 0 1 0 6" />
      <path d="M5 10v2a2 2 0 0 0 2 2h1l5 4V4L8 8H7a2 2 0 0 0-2 2z" />
    </svg>
  );
}

/* ── Financial Results ─ bar chart with uptrend line ── */
export function FinancialResultsIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="14" width="4" height="6" rx="0.5" />
      <rect x="10" y="9" width="4" height="11" rx="0.5" />
      <rect x="17" y="4" width="4" height="16" rx="0.5" />
      <path d="M4 8l6-3.5 6-1" opacity="0.5" />
    </svg>
  );
}

/* ── Concall Transcripts ─ chat bubble with waveform ── */
export function ConcallIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a9 9 0 0 1-14.25 7.31L3 21l1.69-3.75A9 9 0 1 1 21 12z" />
      <line x1="8" y1="12" x2="8" y2="12.01" />
      <line x1="12" y1="10" x2="12" y2="14" />
      <line x1="16" y1="11" x2="16" y2="13" />
    </svg>
  );
}

/* ── Investor Presentations ─ projector screen ── */
export function PresentationsIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="13" rx="2" />
      <line x1="12" y1="16" x2="12" y2="20" />
      <line x1="8" y1="20" x2="16" y2="20" />
      <polyline points="8 10 11 7 14 10 17 8" />
    </svg>
  );
}

/* ── Annual Reports ─ open book ── */
export function AnnualReportsIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H12V3H6.5A2.5 2.5 0 0 0 4 5.5v14z" />
      <path d="M20 19.5A2.5 2.5 0 0 0 17.5 17H12v-14h5.5A2.5 2.5 0 0 1 20 5.5v14z" />
      <line x1="12" y1="3" x2="12" y2="17" />
    </svg>
  );
}

/* ── Bulk & Block Deals ─ stacked transaction blocks ── */
export function BulkBlockDealsIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" />
      <rect x="8" y="3" width="8" height="8" rx="1.5" />
      <line x1="12" y1="11" x2="7" y2="13" opacity="0.4" />
      <line x1="12" y1="11" x2="17" y2="13" opacity="0.4" />
    </svg>
  );
}

/* ── Insider Trades ─ person silhouette with key/lock ── */
export function InsiderTradesIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="7" r="3.5" />
      <path d="M3 21v-1a7 7 0 0 1 7-7h0" />
      <circle cx="18" cy="15" r="2" />
      <path d="M18 17v4" />
      <line x1="17" y1="19" x2="19" y2="19" />
    </svg>
  );
}

/* ── Corporate Actions ─ gear with checkmark ── */
export function CorporateActionsIcon({ size = defaults.size, className, strokeWidth = defaults.strokeWidth }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16z" />
      <path d="M12 20a8 8 0 0 0 4.9-1.7" opacity="0.3" />
      <circle cx="12" cy="12" r="3" />
      <line x1="12" y1="1" x2="12" y2="4" />
      <line x1="12" y1="20" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="6.34" y2="6.34" />
      <line x1="17.66" y1="17.66" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="4" y2="12" />
      <line x1="20" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="6.34" y2="17.66" />
      <line x1="17.66" y1="6.34" x2="19.78" y2="4.22" />
    </svg>
  );
}

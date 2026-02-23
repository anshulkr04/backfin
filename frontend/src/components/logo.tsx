"use client";

interface LogoProps {
  variant?: "full" | "short" | "icon";
  theme?: "dark" | "light";
  className?: string;
}

export function Logo({
  variant = "full",
  theme = "dark",
  className = "",
}: LogoProps) {
  const textColor = theme === "dark" ? "#111827" : "#FFFFFF";
  const accent = "#F97316";

  if (variant === "icon") {
    return (
      <svg
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        role="img"
        aria-label="MarketWire"
      >
        <rect width="36" height="36" rx="8" fill={accent} />
        <polyline
          points="6,20 12,20 15,12 18,26 21,16 24,22 27,14 30,20"
          stroke="#FFFFFF"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    );
  }

  if (variant === "short") {
    return (
      <svg
        viewBox="0 0 80 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        role="img"
        aria-label="MarketWire"
      >
        <g>
          <rect width="28" height="28" y="2" rx="6" fill={accent} />
          <polyline
            points="4,17 8,17 10,11 13,23 16,14 19,19 22,11 25,17"
            stroke="#FFFFFF"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </g>
        <text
          x="34"
          y="23"
          fontFamily="var(--font-display), 'DM Sans', system-ui, sans-serif"
          fontSize="20"
          fontWeight="700"
          letterSpacing="-0.5"
          fill={textColor}
        >
          MW
        </text>
      </svg>
    );
  }

  return (
    <svg
      viewBox="0 0 148 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="MarketWire"
    >
      <g>
        <rect width="28" height="28" y="2" rx="6" fill={accent} />
        <polyline
          points="4,17 8,17 10,11 13,23 16,14 19,19 22,11 25,17"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </g>
      <text
        x="34"
        y="23"
        fontFamily="var(--font-display), 'DM Sans', system-ui, sans-serif"
        fontSize="19"
        fontWeight="700"
        letterSpacing="-0.3"
        fill={textColor}
      >
        Market<tspan fill={accent}>Wire</tspan>
      </text>
    </svg>
  );
}
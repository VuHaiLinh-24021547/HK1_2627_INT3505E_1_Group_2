"use client";

import { useState } from "react";

interface GameAssetImgProps {
  src?: string | null;
  alt: string;
  fallbackText?: string;
  className?: string;
  title?: string;
}

/**
 * Renders a Data Dragon icon with a clean monogram fallback when offline or for empty item slots.
 */
export function GameAssetImg({ src, alt, fallbackText, className = "w-8 h-8 rounded", title }: GameAssetImgProps) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    const label = (fallbackText || alt || "?").slice(0, 3).toUpperCase();
    return (
      <div
        title={title || alt}
        className={`${className} flex items-center justify-center bg-slate-800/90 border border-slate-700/70 text-[10px] font-semibold text-slate-300 select-none shrink-0`}
      >
        {label}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      title={title || alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`${className} object-cover shrink-0 bg-slate-900`}
    />
  );
}

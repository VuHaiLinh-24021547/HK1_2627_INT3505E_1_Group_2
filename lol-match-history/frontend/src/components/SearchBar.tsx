"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { REGIONS, encodeRiotIdSlug } from "@/lib/format";

interface SearchBarProps {
  initialRegion?: string;
  initialQuery?: string;
  compact?: boolean;
}

export function SearchBar({ initialRegion = "vn2", initialQuery = "", compact = false }: SearchBarProps) {
  const router = useRouter();
  const [region, setRegion] = useState(initialRegion);
  const [query, setQuery] = useState(initialQuery);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    const hashIndex = trimmed.lastIndexOf("#");
    if (hashIndex <= 0 || hashIndex === trimmed.length - 1) {
      setError("Nhập đúng định dạng Riot ID, ví dụ: Player1#VN2");
      return;
    }
    const gameName = trimmed.slice(0, hashIndex).trim();
    const tagLine = trimmed.slice(hashIndex + 1).trim();
    if (!gameName || !tagLine) {
      setError("Tên người chơi và TagLine không được để trống.");
      return;
    }
    setError(null);
    router.push(`/players/${region}/${encodeRiotIdSlug(gameName, tagLine)}`);
  }

  return (
    <div className="w-full">
      <form
        onSubmit={handleSubmit}
        className={`flex items-stretch rounded-xl border border-slate-700/80 bg-surface-900/90 focus-within:border-cyan-400/70 focus-within:ring-2 focus-within:ring-cyan-500/20 transition ${
          compact ? "h-10 text-sm" : "h-13 shadow-xl shadow-black/40"
        }`}
      >
        <select
          aria-label="Khu vực máy chủ"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className={`bg-surface-800/80 text-slate-200 font-semibold border-r border-slate-700/70 rounded-l-xl focus:outline-none cursor-pointer ${
            compact ? "px-2.5 text-xs" : "px-3.5 text-sm"
          }`}
        >
          {REGIONS.map((r) => (
            <option key={r.code} value={r.code} className="bg-surface-900 text-slate-100">
              {r.label}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (error) setError(null);
          }}
          placeholder="Nhập Riot ID (VD: Player1#VN2)"
          className={`flex-1 bg-transparent text-slate-100 placeholder:text-slate-500 focus:outline-none ${
            compact ? "px-3 text-sm" : "px-4 py-3 text-base"
          }`}
        />

        <button
          type="submit"
          className={`flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold rounded-r-[11px] transition ${
            compact ? "px-3.5 text-xs" : "px-5 text-sm"
          }`}
        >
          <Search className={compact ? "w-3.5 h-3.5" : "w-4 h-4"} />
          {!compact && <span>Tra cứu</span>}
        </button>
      </form>
      {error && <p className="mt-1.5 text-xs text-rose-400">{error}</p>}
    </div>
  );
}

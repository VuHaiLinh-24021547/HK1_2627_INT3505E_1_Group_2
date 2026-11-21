import Link from "next/link";
import { Swords } from "lucide-react";
import { SearchBar } from "./SearchBar";

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-surface-950/85 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-4 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Swords className="w-5 h-5 text-slate-950" />
          </div>
          <div className="leading-tight">
            <div className="font-bold text-base tracking-tight text-slate-100 group-hover:text-cyan-300 transition">
              Rift<span className="text-cyan-400">Review</span>
            </div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500">LoL Match Analytics</div>
          </div>
        </Link>

        <div className="hidden sm:block w-full max-w-md">
          <SearchBar compact />
        </div>

        <nav className="flex items-center gap-3 text-xs font-medium text-slate-400 shrink-0">
          <Link
            href="/players/vn2/Player1-VN2"
            className="px-3 py-1.5 rounded-lg border border-slate-800 hover:border-cyan-500/50 hover:text-cyan-300 transition"
          >
            Demo: Player1#VN2
          </Link>
        </nav>
      </div>
    </header>
  );
}

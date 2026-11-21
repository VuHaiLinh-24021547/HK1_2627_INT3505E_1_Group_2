import Link from "next/link";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import { backendJson } from "@/lib/backend";
import { parseRiotIdSlug } from "@/lib/format";
import type { MatchListResponse, PlayerProfile, ProblemDetails, StaticCatalog } from "@/lib/types";
import { PlayerDashboard } from "@/components/PlayerDashboard";

export const dynamic = "force-dynamic";

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ region: string; riotId: string }>;
}) {
  const { region, riotId } = await params;
  const parsed = parseRiotIdSlug(riotId);
  if (!parsed) {
    return (
      <ErrorView
        title="Riot ID không hợp lệ"
        detail="Đường dẫn phải có dạng /players/{region}/{gameName}-{tagLine}, ví dụ: /players/vn2/Player1-VN2."
      />
    );
  }

  let profileRes;
  try {
    profileRes = await backendJson<PlayerProfile>(
      `regions/${encodeURIComponent(region)}/players/${encodeURIComponent(parsed.gameName)}/${encodeURIComponent(
        parsed.tagLine
      )}`
    );
  } catch (err) {
    return (
      <ErrorView
        title="Không thể kết nối Backend Flask"
        detail={
          err instanceof Error
            ? `${err.message}. Hãy chắc chắn Flask server đang chạy trên BACKEND_URL (mặc định http://127.0.0.1:5000).`
            : "Backend không phản hồi."
        }
      />
    );
  }

  if (!profileRes.ok) {
    const problem = profileRes.error as ProblemDetails | null;
    return (
      <ErrorView
        title={profileRes.status === 404 ? "Không tìm thấy người chơi" : `Lỗi tải hồ sơ (HTTP ${profileRes.status})`}
        detail={problem?.detail || "Không thể tra cứu hồ sơ người chơi này."}
      />
    );
  }

  const profile = profileRes.data;
  const [historyRes, catalogRes] = await Promise.all([
    backendJson<MatchListResponse>(`players/${encodeURIComponent(profile.puuid)}/matches?limit=10`),
    backendJson<StaticCatalog>("static-catalogs/latest?lang=vi_VN"),
  ]);

  const history: MatchListResponse = historyRes.ok
    ? historyRes.data
    : {
        data: [],
        summary: { games: 0, wins: 0, losses: 0, winRate: 0, avgKda: 0, avgCsPerMin: 0 },
        pagination: { limit: 10, nextCursor: null, hasMore: false },
      };

  const catalog = catalogRes.ok ? catalogRes.data : null;

  return <PlayerDashboard initialProfile={profile} initialHistory={history} catalog={catalog} />;
}

function ErrorView({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="mx-auto max-w-xl px-4 py-20 text-center space-y-4">
      <div className="mx-auto w-12 h-12 rounded-2xl bg-rose-500/15 border border-rose-500/40 flex items-center justify-center">
        <AlertTriangle className="w-6 h-6 text-rose-400" />
      </div>
      <h1 className="text-xl font-bold text-white">{title}</h1>
      <p className="text-sm text-slate-400">{detail}</p>
      <Link
        href="/"
        className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-900 border border-slate-700 hover:border-cyan-400 text-sm font-semibold text-cyan-300 transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Về trang tra cứu</span>
      </Link>
    </div>
  );
}

import Link from "next/link";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import { backendJson } from "@/lib/backend";
import type { MatchReviewResponse, ProblemDetails, StaticCatalog } from "@/lib/types";
import { MatchReviewView } from "@/components/MatchReviewView";

export const dynamic = "force-dynamic";

export default async function MatchReviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ matchId: string }>;
  searchParams: Promise<{ focusPuuid?: string; region?: string }>;
}) {
  const { matchId } = await params;
  const { focusPuuid, region } = await searchParams;

  const qs = new URLSearchParams();
  if (focusPuuid) qs.set("focusPuuid", focusPuuid);
  if (region) qs.set("region", region);
  const query = qs.toString() ? `?${qs.toString()}` : "";

  let reviewRes;
  try {
    reviewRes = await backendJson<MatchReviewResponse>(`matches/${encodeURIComponent(matchId)}/review${query}`);
  } catch (err) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center space-y-4">
        <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto" />
        <h1 className="text-xl font-bold text-white">Không thể kết nối Backend Flask</h1>
        <p className="text-sm text-slate-400">{err instanceof Error ? err.message : "Backend không phản hồi."}</p>
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-cyan-400 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Quay lại trang chủ
        </Link>
      </div>
    );
  }

  if (!reviewRes.ok) {
    const problem = reviewRes.error as ProblemDetails | null;
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center space-y-4">
        <AlertTriangle className="w-8 h-8 text-rose-400 mx-auto" />
        <h1 className="text-xl font-bold text-white">
          {reviewRes.status === 404 ? "Không tìm thấy trận đấu" : `Lỗi tải phân tích trận (HTTP ${reviewRes.status})`}
        </h1>
        <p className="text-sm text-slate-400">{problem?.detail || "Vui lòng thử lại sau."}</p>
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-cyan-400 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Quay lại trang chủ
        </Link>
      </div>
    );
  }

  const catalogRes = await backendJson<StaticCatalog>("static-catalogs/latest?lang=vi_VN");
  return <MatchReviewView review={reviewRes.data} catalog={catalogRes.ok ? catalogRes.data : null} />;
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Filter, Loader2, Trophy, AlertCircle, CheckCircle2 } from "lucide-react";
import type {
  MatchListItem,
  MatchListResponse,
  PlayerProfile,
  ProblemDetails,
  StaticCatalog,
  SyncJob,
} from "@/lib/types";
import { QUEUE_NAMES, tierColor } from "@/lib/format";
import { MatchCard } from "./MatchCard";
import { GameAssetImg } from "./GameAssetImg";

interface PlayerDashboardProps {
  initialProfile: PlayerProfile;
  initialHistory: MatchListResponse;
  catalog: StaticCatalog | null;
}

export function PlayerDashboard({ initialProfile, initialHistory, catalog }: PlayerDashboardProps) {
  const [profile, setProfile] = useState<PlayerProfile>(initialProfile);
  const [matches, setMatches] = useState<MatchListItem[]>(initialHistory.data);
  const [summary, setSummary] = useState(initialHistory.summary);
  const [nextCursor, setNextCursor] = useState<string | null>(initialHistory.pagination.nextCursor);
  const [hasMore, setHasMore] = useState<boolean>(initialHistory.pagination.hasMore);

  const [queueFilter, setQueueFilter] = useState<string>("");
  const [champFilter, setChampFilter] = useState<string>("");
  const [loadingList, setLoadingList] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const [cooldown, setCooldown] = useState<number>(initialProfile.cooldownRemainingSec);
  const [syncing, setSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState<{ type: "info" | "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setInterval(() => setCooldown((c) => (c > 1 ? c - 1 : 0)), 1000);
    return () => clearInterval(id);
  }, [cooldown]);

  const championOptions = useMemo(() => {
    const ids = new Set<number>();
    matches.forEach((m) => ids.add(m.player.championId));
    if (catalog) {
      Object.values(catalog.champions).forEach((c) => ids.add(c.id));
    }
    return Array.from(ids)
      .map((id) => ({ id, name: catalog?.champions[String(id)]?.name || `Champion #${id}` }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [matches, catalog]);

  async function fetchMatches({
    cursor,
    queueId,
    championId,
    append,
  }: {
    cursor?: string | null;
    queueId: string;
    championId: string;
    append: boolean;
  }) {
    const params = new URLSearchParams({ limit: "10" });
    if (cursor) params.set("cursor", cursor);
    if (queueId) params.set("queueId", queueId);
    if (championId) params.set("championId", championId);

    if (append) setLoadingMore(true);
    else setLoadingList(true);
    try {
      const resp = await fetch(`/api/lol/players/${encodeURIComponent(profile.puuid)}/matches?${params.toString()}`);
      if (!resp.ok) return;
      const body = (await resp.json()) as MatchListResponse;
      setMatches((prev) => (append ? [...prev, ...body.data] : body.data));
      setSummary(body.summary);
      setNextCursor(body.pagination.nextCursor);
      setHasMore(body.pagination.hasMore);
    } finally {
      setLoadingList(false);
      setLoadingMore(false);
    }
  }

  function applyFilters(nextQueue: string, nextChamp: string) {
    setQueueFilter(nextQueue);
    setChampFilter(nextChamp);
    fetchMatches({ queueId: nextQueue, championId: nextChamp, append: false });
  }

  async function handleSync() {
    if (syncing || cooldown > 0) return;
    setSyncing(true);
    setSyncNotice(null);
    const idempotencyKey = crypto.randomUUID();
    try {
      const resp = await fetch(`/api/lol/players/${encodeURIComponent(profile.puuid)}/sync-jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ region: profile.region, count: 20 }),
      });

      if (resp.status === 429) {
        const problem = (await resp.json()) as ProblemDetails;
        const retry = problem.retryAfterSeconds || Number(resp.headers.get("Retry-After")) || 120;
        setCooldown(retry);
        setSyncNotice({ type: "error", text: problem.detail || `Vui lòng đợi ${retry}s trước khi đồng bộ lại.` });
        return;
      }

      if (!resp.ok) {
        const problem = (await resp.json().catch(() => null)) as ProblemDetails | null;
        setSyncNotice({ type: "error", text: problem?.detail || `Đồng bộ thất bại (HTTP ${resp.status}).` });
        return;
      }

      const job = (await resp.json()) as SyncJob;
      setCooldown(120);
      setSyncNotice({
        type: "info",
        text: `Đã tạo job đồng bộ #${job.jobId.slice(0, 8)} (${job.status}). Đang cập nhật dữ liệu...`,
      });

      // Poll job status briefly
      let finalJob: SyncJob = job;
      for (let i = 0; i < 6 && (finalJob.status === "queued" || finalJob.status === "started"); i++) {
        await new Promise((r) => setTimeout(r, 700));
        const jr = await fetch(`/api/lol/sync-jobs/${encodeURIComponent(job.jobId)}`);
        if (jr.ok) finalJob = (await jr.json()) as SyncJob;
      }

      if (finalJob.status === "finished" && finalJob.result) {
        setSyncNotice({
          type: "success",
          text: `Đồng bộ hoàn tất: +${finalJob.result.newMatches} trận mới (${finalJob.result.skippedExisting} trận đã có).`,
        });
      } else if (finalJob.status === "failed") {
        setSyncNotice({
          type: "error",
          text: `Job đồng bộ gặp lỗi: ${finalJob.error?.message || "Không thể gọi Riot API"}`,
        });
      }

      // Refresh profile & match list
      const [pResp] = await Promise.all([
        fetch(
          `/api/lol/regions/${encodeURIComponent(profile.region)}/players/${encodeURIComponent(
            profile.gameName
          )}/${encodeURIComponent(profile.tagLine)}`
        ),
        fetchMatches({ queueId: queueFilter, championId: champFilter, append: false }),
      ]);
      if (pResp.ok) {
        const refreshed = (await pResp.json()) as PlayerProfile;
        setProfile(refreshed);
        if (refreshed.cooldownRemainingSec > 0) setCooldown(refreshed.cooldownRemainingSec);
      }
    } catch {
      setSyncNotice({ type: "error", text: "Không thể kết nối tới máy chủ đồng bộ." });
    } finally {
      setSyncing(false);
    }
  }

  const profileIconUrl =
    profile.profileIconId && catalog?.patch
      ? `https://ddragon.leagueoflegends.com/cdn/${catalog.patch}/img/profileicon/${profile.profileIconId}.png`
      : null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      {/* Player Profile Header */}
      <section className="rounded-2xl border border-slate-800 bg-gradient-to-br from-surface-900 via-surface-900 to-surface-800/80 p-5 sm:p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="relative">
              <GameAssetImg
                src={profileIconUrl}
                alt={profile.riotId}
                fallbackText={profile.gameName.slice(0, 2)}
                className="w-20 h-20 rounded-2xl border-2 border-cyan-500/50 shadow-lg"
              />
              {profile.summonerLevel != null && (
                <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full bg-surface-950 border border-slate-700 text-[11px] font-bold text-gold-400">
                  Lv.{profile.summonerLevel}
                </span>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                  {profile.gameName}
                  <span className="text-slate-400 font-semibold">#{profile.tagLine}</span>
                </h1>
                <span className="px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-xs font-bold uppercase text-cyan-300">
                  {profile.region}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2.5 text-xs">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border font-semibold ${tierColor(profile.soloTier)}`}>
                  <Trophy className="w-3.5 h-3.5" />
                  {profile.soloTier
                    ? `${profile.soloTier} ${profile.soloRank || ""} • ${profile.soloLp} LP`
                    : "Chưa xếp hạng Đơn/Đôi"}
                </span>
                {profile.soloTier && (
                  <span className="text-slate-400">
                    {profile.soloWins}W {profile.soloLosses}L
                    {profile.soloWinRate != null ? ` (${profile.soloWinRate}%)` : ""}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-col items-start md:items-end gap-2">
            <button
              type="button"
              onClick={handleSync}
              disabled={syncing || cooldown > 0}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-800 disabled:text-slate-400 disabled:cursor-not-allowed text-slate-950 transition shadow-lg shadow-cyan-500/15"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
              {syncing
                ? "Đang đồng bộ..."
                : cooldown > 0
                  ? `Đợi ${cooldown}s để đồng bộ lại`
                  : "Đồng bộ trận mới"}
            </button>
            <p className="text-[11px] text-slate-500">
              {profile.lastSyncedAt
                ? `Đồng bộ gần nhất: ${new Date(profile.lastSyncedAt).toLocaleString("vi-VN")}`
                : "Chưa đồng bộ từ Riot API"}
            </p>
          </div>
        </div>

        {syncNotice && (
          <div
            className={`mt-4 flex items-center gap-2 rounded-xl border px-3.5 py-2.5 text-xs ${
              syncNotice.type === "error"
                ? "border-rose-500/40 bg-rose-950/40 text-rose-200"
                : syncNotice.type === "success"
                  ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-200"
                  : "border-cyan-500/40 bg-cyan-950/40 text-cyan-200"
            }`}
          >
            {syncNotice.type === "error" ? (
              <AlertCircle className="w-4 h-4 shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            )}
            <span>{syncNotice.text}</span>
          </div>
        )}
      </section>

      {/* Summary + Filter bar */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Số trận" value={String(summary.games)} sub={`${summary.wins}W / ${summary.losses}L`} />
          <StatCard
            label="Tỷ lệ thắng"
            value={`${summary.winRate.toFixed(1)}%`}
            accent={summary.winRate >= 50 ? "text-emerald-400" : "text-rose-400"}
          />
          <StatCard label="KDA trung bình" value={summary.avgKda.toFixed(2)} accent="text-cyan-300" />
          <StatCard label="CS / phút" value={summary.avgCsPerMin.toFixed(2)} accent="text-gold-400" />
        </div>

        <div className="lg:col-span-5 rounded-xl border border-slate-800 bg-surface-900 p-3.5 flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 mr-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Bộ lọc</span>
          </div>

          <select
            aria-label="Lọc chế độ chơi"
            value={queueFilter}
            onChange={(e) => applyFilters(e.target.value, champFilter)}
            className="flex-1 min-w-[140px] rounded-lg bg-surface-800 border border-slate-700 px-2.5 py-2 text-xs text-slate-200 focus:border-cyan-400 focus:outline-none"
          >
            <option value="">Tất cả chế độ</option>
            {Object.entries(QUEUE_NAMES).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>

          <select
            aria-label="Lọc tướng"
            value={champFilter}
            onChange={(e) => applyFilters(queueFilter, e.target.value)}
            className="flex-1 min-w-[130px] rounded-lg bg-surface-800 border border-slate-700 px-2.5 py-2 text-xs text-slate-200 focus:border-cyan-400 focus:outline-none"
          >
            <option value="">Tất cả tướng</option>
            {championOptions.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Match History List */}
      <section className="space-y-3">
        {loadingList ? (
          <div className="py-12 flex items-center justify-center gap-2 text-slate-400 text-sm">
            <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
            <span>Đang tải lịch sử đấu...</span>
          </div>
        ) : matches.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-surface-900 py-14 text-center space-y-2">
            <p className="text-slate-300 font-semibold">Không có trận đấu nào khớp bộ lọc.</p>
            <p className="text-xs text-slate-500">Thử đổi bộ lọc hoặc bấm &ldquo;Đồng bộ trận mới&rdquo;.</p>
          </div>
        ) : (
          <>
            {matches.map((match) => (
              <MatchCard key={match.matchId} match={match} region={profile.region} catalog={catalog} />
            ))}

            {hasMore && nextCursor && (
              <div className="pt-2 flex justify-center">
                <button
                  type="button"
                  disabled={loadingMore}
                  onClick={() =>
                    fetchMatches({
                      cursor: nextCursor,
                      queueId: queueFilter,
                      championId: champFilter,
                      append: true,
                    })
                  }
                  className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl border border-slate-700 bg-surface-900 hover:border-cyan-500/60 hover:text-cyan-300 text-sm font-semibold text-slate-200 transition disabled:opacity-50"
                >
                  {loadingMore && <Loader2 className="w-4 h-4 animate-spin" />}
                  <span>{loadingMore ? "Đang tải..." : "Tải thêm trận đấu"}</span>
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, sub, accent = "text-white" }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-surface-900 px-3.5 py-3">
      <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{label}</div>
      <div className={`mt-1 text-xl font-extrabold ${accent}`}>{value}</div>
      {sub && <div className="text-[11px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Crown, Flame, Castle, Eye, Coins } from "lucide-react";
import type {
  EventTimelinePoint,
  MatchReviewResponse,
  ReviewParticipant,
  StaticCatalog,
  TeamSummary,
} from "@/lib/types";
import { formatDuration, formatNumber, queueLabel, encodeRiotIdSlug } from "@/lib/format";
import { GameAssetImg } from "./GameAssetImg";
import { TimelineChart } from "./TimelineChart";
import { MatchSnapshotBoard } from "./MatchSnapshotBoard";

interface MatchReviewViewProps {
  review: MatchReviewResponse;
  catalog: StaticCatalog | null;
}

export function MatchReviewView({ review, catalog }: MatchReviewViewProps) {
  const maxDamage = Math.max(1, ...review.participants.map((p) => p.damageToChamps));
  const blueTeam = review.teams.find((t) => t.teamId === 100);
  const redTeam = review.teams.find((t) => t.teamId === 200);
  const bluePlayers = review.participants.filter((p) => p.teamId === 100);
  const redPlayers = review.participants.filter((p) => p.teamId === 200);
  const focusPlayer = review.participants.find((p) => p.isFocus) || review.participants[0];
  const focusTeamId = focusPlayer?.teamId || 100;

  const timelinePoints: EventTimelinePoint[] = useMemo(() => {
    if (review.analytics?.eventTimeline && review.analytics.eventTimeline.length > 0) {
      return review.analytics.eventTimeline;
    }
    return (review.analytics?.winProbabilityFrames || []).map((f, idx) => ({
      id: `min-${idx}`,
      timestampMs: f.minute * 60_000,
      minute: f.minute,
      kind: "MINUTE",
      blueWinProb: f.blueWinProb,
      focusWinProb: f.focusWinProb,
      probDelta: 0,
      focusImpactDelta: f.focusImpactDelta,
      focusImpactCumulative: f.focusImpactCumulative,
    }));
  }, [review.analytics]);

  const initialIdx = useMemo(() => {
    if (!timelinePoints.length) return 0;
    const h0 = review.analytics?.highlights?.[0];
    if (h0) {
      const i = timelinePoints.findIndex((p) => p.id === h0.pointId);
      if (i >= 0) return i;
    }
    return Math.min(timelinePoints.length - 1, Math.floor(timelinePoints.length / 2));
  }, [timelinePoints, review.analytics]);

  const [selectedIdx, setSelectedIdx] = useState<number>(initialIdx);
  const selectedPoint = timelinePoints[Math.max(0, Math.min(timelinePoints.length - 1, selectedIdx))];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <Link
            href={
              focusPlayer?.riotId && focusPlayer.riotId.includes("#")
                ? `/players/${review.region}/${encodeRiotIdSlug(
                    focusPlayer.riotId.split("#")[0],
                    focusPlayer.riotId.split("#")[1]
                  )}`
                : "/"
            }
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-400 hover:text-cyan-300 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Quay lại lịch sử đấu</span>
          </Link>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">
            Phân tích hậu trận <span className="text-slate-400 font-mono text-lg">{review.matchId}</span>
          </h1>
          <p className="text-xs text-slate-400">
            {queueLabel(review.queueId)} &bull; Thời lượng {formatDuration(review.gameDuration)} &bull; Patch{" "}
            {review.patch} &bull; Khu vực {review.region.toUpperCase()}
          </p>
        </div>

        {/* Team Objectives Comparison */}
        {blueTeam && redTeam && (
          <div className="flex items-center gap-4 rounded-xl border border-slate-800 bg-surface-900 px-4 py-2.5 text-xs">
            <ObjectivesStrip team={blueTeam} label="Đội Xanh" color="text-sky-400" />
            <div className="h-8 w-px bg-slate-800" />
            <ObjectivesStrip team={redTeam} label="Đội Đỏ" color="text-rose-400" />
          </div>
        )}
      </div>

      {/* Win Probability + Player Impact / Timestamp Event Feed */}
      {review.timeline && (
        <TimelineChart
          frames={review.timeline.frames}
          keyEvents={review.timeline.keyEvents}
          analytics={review.analytics}
          catalog={catalog}
          focusTeamId={focusTeamId}
          focusLabel={focusPlayer?.riotId || undefined}
          selectedIdx={selectedIdx}
          onSelectIdx={setSelectedIdx}
        />
      )}

      {/* Synchronized 3-Column Snapshot: Your Team (Items/KDA/CS) | Minimap Positions | Enemy Team */}
      {review.timeline && selectedPoint && (
        <MatchSnapshotBoard
          review={review}
          catalog={catalog}
          selectedPoint={selectedPoint}
          focusTeamId={focusTeamId}
        />
      )}

      {/* Initial Win Rate (5 Lane Matchups) + 10-Player Impact Breakdown */}
      {review.analytics && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Initial Win Rate by Lane Matchup */}
          <section className="lg:col-span-5 rounded-2xl border border-slate-800 bg-surface-900 p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-white">Tỉ lệ thắng khởi đầu (Matchup)</h2>
                <p className="text-[11px] text-slate-400">Trung bình 5 kèo tướng cùng đường trước phút 0</p>
              </div>
              <div className="text-right">
                <div className="text-lg font-extrabold text-sky-400">
                  {review.analytics.initialBlueWinRate.toFixed(1)}%
                </div>
                <div className="text-[10px] text-slate-500">Đội Xanh khởi đầu</div>
              </div>
            </div>

            <div className="space-y-2">
              {review.analytics.laneMatchups.map((lane) => {
                const blueChamp = catalog?.champions[String(lane.blueChampionId)];
                const redChamp = catalog?.champions[String(lane.redChampionId)];
                return (
                  <div
                    key={lane.position}
                    className="flex items-center justify-between gap-2 rounded-xl border border-slate-800/80 bg-surface-950/60 px-3 py-2 text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <GameAssetImg
                        src={blueChamp?.imageUrl}
                        alt={blueChamp?.name || String(lane.blueChampionId)}
                        fallbackText={String(lane.blueChampionId)}
                        className="w-7 h-7 rounded-md border border-sky-500/40"
                      />
                      <span className="truncate font-semibold text-sky-200 max-w-[78px]">
                        {blueChamp?.name || `#${lane.blueChampionId}`}
                      </span>
                    </div>

                    <div className="text-center shrink-0">
                      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        {lane.position}
                      </div>
                      <div className="font-bold text-slate-200">
                        <span className={lane.blueWinRate >= 50 ? "text-sky-400" : "text-rose-400"}>
                          {lane.blueWinRate.toFixed(1)}%
                        </span>
                      </div>
                      <div className="text-[9px] text-slate-500">{lane.games} trận mẫu</div>
                    </div>

                    <div className="flex items-center gap-2 min-w-0 justify-end">
                      <span className="truncate font-semibold text-rose-200 max-w-[78px] text-right">
                        {redChamp?.name || `#${lane.redChampionId}`}
                      </span>
                      <GameAssetImg
                        src={redChamp?.imageUrl}
                        alt={redChamp?.name || String(lane.redChampionId)}
                        fallbackText={String(lane.redChampionId)}
                        className="w-7 h-7 rounded-md border border-rose-500/40"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Player Contributions (WPA%) */}
          <section className="lg:col-span-7 rounded-2xl border border-slate-800 bg-surface-900 p-5 space-y-3">
            <div>
              <h2 className="text-sm font-bold text-white">Đóng góp tỉ lệ thắng của 10 người chơi (Impact %)</h2>
              <p className="text-[11px] text-slate-400">
                Phân bổ biến thiên tỉ lệ thắng theo Giao tranh (Combat), Mục tiêu (Objective) và Đi đường/Farm (Laning)
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-[10px] uppercase text-slate-500 border-b border-slate-800">
                  <tr>
                    <th className="py-2 pr-2">Người chơi</th>
                    <th className="py-2 px-2 text-right">Giao tranh</th>
                    <th className="py-2 px-2 text-right">Mục tiêu</th>
                    <th className="py-2 px-2 text-right">Đi đường</th>
                    <th className="py-2 pl-2 text-right">Tổng Impact</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {review.analytics.playerContributions.map((c) => {
                    const champ = c.championId ? catalog?.champions[String(c.championId)] : undefined;
                    return (
                      <tr key={c.puuid} className={c.isFocus ? "bg-cyan-500/10" : ""}>
                        <td className="py-1.5 pr-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-1.5 h-5 rounded-full ${
                                c.teamId === 100 ? "bg-sky-400" : "bg-rose-400"
                              }`}
                            />
                            <GameAssetImg
                              src={champ?.imageUrl}
                              alt={champ?.name || String(c.championId ?? "")}
                              fallbackText={String(c.championId ?? "?")}
                              className="w-6 h-6 rounded"
                            />
                            <span
                              className={`truncate max-w-[130px] font-semibold ${
                                c.isFocus ? "text-cyan-300" : "text-slate-200"
                              }`}
                            >
                              {c.riotId || c.puuid.slice(0, 10)}
                            </span>
                          </div>
                        </td>
                        <td className="py-1.5 px-2 text-right font-mono text-slate-300">
                          {c.combatImpact >= 0 ? "+" : ""}
                          {c.combatImpact.toFixed(1)}%
                        </td>
                        <td className="py-1.5 px-2 text-right font-mono text-slate-300">
                          {c.objectiveImpact >= 0 ? "+" : ""}
                          {c.objectiveImpact.toFixed(1)}%
                        </td>
                        <td className="py-1.5 px-2 text-right font-mono text-slate-300">
                          {c.laningImpact >= 0 ? "+" : ""}
                          {c.laningImpact.toFixed(1)}%
                        </td>
                        <td
                          className={`py-1.5 pl-2 text-right font-mono font-bold ${
                            c.totalImpact >= 0 ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {c.totalImpact >= 0 ? "+" : ""}
                          {c.totalImpact.toFixed(2)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      {/* 10-player Full End-of-Game Scoreboard */}
      <div className="space-y-4">
        <TeamScoreboard
          title="Đội Xanh (Blue Side)"
          team={blueTeam}
          players={bluePlayers}
          region={review.region}
          maxDamage={maxDamage}
          catalog={catalog}
        />
        <TeamScoreboard
          title="Đội Đỏ (Red Side)"
          team={redTeam}
          players={redPlayers}
          region={review.region}
          maxDamage={maxDamage}
          catalog={catalog}
        />
      </div>
    </div>
  );
}

function ObjectivesStrip({ team, label, color }: { team: TeamSummary; label: string; color: string }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <span className={`font-bold ${color}`}>{label}</span>
        <span
          className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
            team.win ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"
          }`}
        >
          {team.win ? "Thắng" : "Thua"}
        </span>
      </div>
      <div className="flex items-center gap-3 text-slate-300">
        <span title="Baron" className="inline-flex items-center gap-1">
          <Crown className="w-3.5 h-3.5 text-purple-400" />
          {team.barons}
        </span>
        <span title="Rồng" className="inline-flex items-center gap-1">
          <Flame className="w-3.5 h-3.5 text-amber-400" />
          {team.dragons}
        </span>
        <span title="Trụ" className="inline-flex items-center gap-1">
          <Castle className="w-3.5 h-3.5 text-slate-400" />
          {team.towers}
        </span>
      </div>
    </div>
  );
}

function TeamScoreboard({
  title,
  team,
  players,
  region,
  maxDamage,
  catalog,
}: {
  title: string;
  team?: TeamSummary;
  players: ReviewParticipant[];
  region: string;
  maxDamage: number;
  catalog: StaticCatalog | null;
}) {
  const isBlue = team?.teamId === 100;
  return (
    <section className="rounded-2xl border border-slate-800 bg-surface-900 overflow-hidden">
      <div
        className={`px-4 py-3 border-b border-slate-800 flex items-center justify-between text-xs font-bold ${
          isBlue ? "bg-sky-950/30 text-sky-300" : "bg-rose-950/30 text-rose-300"
        }`}
      >
        <div className="flex items-center gap-2">
          <span>{title}</span>
          {team && (
            <span className={team.win ? "text-emerald-400" : "text-rose-400"}>
              ({team.win ? "CHIẾN THẮNG" : "THẤT BẠI"})
            </span>
          )}
        </div>
        {team && <span className="text-slate-400 font-medium">Tổng hạ gục: {team.kills}</span>}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-950/50 text-[11px] uppercase text-slate-500 border-b border-slate-800/80">
            <tr>
              <th className="py-2.5 px-4">Người chơi</th>
              <th className="py-2.5 px-3">KDA</th>
              <th className="py-2.5 px-3">Sát thương</th>
              <th className="py-2.5 px-3">CS</th>
              <th className="py-2.5 px-3">Vàng / Tầm nhìn</th>
              <th className="py-2.5 px-4">Trang bị</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {players.map((p) => {
              const champ = catalog?.champions[String(p.championId)];
              const keystone = p.keystoneId ? catalog?.runes[String(p.keystoneId)] : undefined;
              const dmgPct = Math.round((p.damageToChamps / maxDamage) * 100);
              const playerHref =
                p.riotId && p.riotId.includes("#")
                  ? `/players/${region}/${encodeRiotIdSlug(p.riotId.split("#")[0], p.riotId.split("#")[1])}`
                  : null;
              return (
                <tr key={p.puuid} className={p.isFocus ? "bg-cyan-500/10" : "hover:bg-surface-800/40 transition"}>
                  <td className="py-2.5 px-4">
                    <div className="flex items-center gap-2.5">
                      <GameAssetImg
                        src={champ?.imageUrl}
                        alt={champ?.name || String(p.championId)}
                        fallbackText={String(p.championId)}
                        className="w-9 h-9 rounded-lg border border-slate-700"
                      />
                      <div className="flex flex-col gap-0.5">
                        {p.spells.slice(0, 2).map((sid, i) => {
                          const sp = sid ? catalog?.spells[String(sid)] : undefined;
                          return (
                            <GameAssetImg
                              key={i}
                              src={sp?.imageUrl}
                              alt={sp?.name || ""}
                              fallbackText={sid ? `S${sid}` : "-"}
                              className="w-4 h-4 rounded-sm"
                            />
                          );
                        })}
                      </div>
                      <GameAssetImg
                        src={keystone?.imageUrl}
                        alt={keystone?.name || "Rune"}
                        fallbackText="R"
                        className="w-5 h-5 rounded-full bg-surface-950 p-0.5 border border-slate-700"
                      />
                      <div className="min-w-0">
                        {playerHref ? (
                          <Link
                            href={playerHref}
                            className={`font-semibold truncate block max-w-[140px] hover:underline ${
                              p.isFocus ? "text-cyan-300" : "text-slate-100"
                            }`}
                          >
                            {p.riotId}
                          </Link>
                        ) : (
                          <span className="font-semibold text-slate-200">{p.riotId || p.puuid.slice(0, 10)}</span>
                        )}
                        <div className="text-[10px] text-slate-500">
                          {champ?.name || `#${p.championId}`} {p.teamPosition ? `• ${p.teamPosition}` : ""}
                        </div>
                      </div>
                    </div>
                  </td>

                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <div className="font-bold text-slate-100">
                      {p.kills}/{p.deaths}/{p.assists}
                    </div>
                    <div className="text-[11px] text-cyan-300 font-semibold">{p.kda.toFixed(2)} KDA</div>
                  </td>

                  <td className="py-2.5 px-3 min-w-[125px]">
                    <div className="font-semibold text-slate-200">{p.damageToChamps.toLocaleString("vi-VN")}</div>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${isBlue ? "bg-sky-400" : "bg-rose-400"}`}
                        style={{ width: `${dmgPct}%` }}
                      />
                    </div>
                  </td>

                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <div className="font-semibold text-slate-200">{p.csTotal}</div>
                    <div className="text-[11px] text-slate-400">{p.csPerMin}/ph</div>
                  </td>

                  <td className="py-2.5 px-3 whitespace-nowrap text-slate-300">
                    <div className="inline-flex items-center gap-1 mr-2.5">
                      <Coins className="w-3 h-3 text-gold-400" />
                      {formatNumber(p.goldEarned)}
                    </div>
                    <div className="inline-flex items-center gap-1 text-slate-400">
                      <Eye className="w-3 h-3 text-cyan-400" />
                      {p.visionScore}
                    </div>
                  </td>

                  <td className="py-2.5 px-4">
                    <div className="flex items-center gap-1">
                      {p.items.slice(0, 7).map((itemId, idx) => {
                        const item = itemId ? catalog?.items[String(itemId)] : undefined;
                        if (!itemId) {
                          return (
                            <div
                              key={idx}
                              className={`w-6 h-6 bg-surface-950/70 border border-slate-800 ${
                                idx === 6 ? "rounded-full ml-0.5" : "rounded"
                              }`}
                            />
                          );
                        }
                        return (
                          <GameAssetImg
                            key={idx}
                            src={item?.imageUrl}
                            alt={item?.name || String(itemId)}
                            fallbackText={String(itemId)}
                            className={`w-6 h-6 border border-slate-700 ${
                              idx === 6 ? "rounded-full ml-0.5" : "rounded"
                            }`}
                          />
                        );
                      })}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

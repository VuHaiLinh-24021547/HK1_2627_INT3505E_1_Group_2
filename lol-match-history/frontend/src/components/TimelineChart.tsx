"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Swords, Flame, Castle, Crown, BrainCircuit, Shield } from "lucide-react";
import type {
  EventTimelinePoint,
  MatchAnalytics,
  StaticCatalog,
  TimelineFrame,
  TimelineKeyEvent,
} from "@/lib/types";
import { formatDuration, monsterLabel } from "@/lib/format";
import { GameAssetImg } from "./GameAssetImg";

interface TimelineChartProps {
  frames: TimelineFrame[];
  keyEvents: TimelineKeyEvent[];
  analytics?: MatchAnalytics | null;
  catalog: StaticCatalog | null;
  focusTeamId?: number;
  focusLabel?: string;
  selectedIdx?: number;
  onSelectIdx?: (idx: number) => void;
}

type ViewTab = "winprob" | "contribution";

function formatMMSS(timestampMs: number): string {
  const totalSec = Math.max(0, Math.floor(timestampMs / 1000));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function TimelineChart({
  frames,
  analytics,
  catalog,
  focusTeamId = 100,
  focusLabel,
  selectedIdx: controlledIdx,
  onSelectIdx,
}: TimelineChartProps) {
  const [tab, setTab] = useState<ViewTab>("winprob");
  const svgRef = useRef<SVGSVGElement | null>(null);
  const rowRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  // Build unified eventTimeline (fallback from winProbabilityFrames if backend didn't send eventTimeline)
  const points: EventTimelinePoint[] = useMemo(() => {
    if (analytics?.eventTimeline && analytics.eventTimeline.length > 0) {
      return analytics.eventTimeline;
    }
    return (analytics?.winProbabilityFrames || []).map((f, idx) => ({
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
  }, [analytics]);

  const highlights = analytics?.highlights || [];

  // Default selected point: first turning point or middle of the match
  const defaultIdx = useMemo(() => {
    if (!points.length) return 0;
    if (highlights.length > 0) {
      const i = points.findIndex((p) => p.id === highlights[0].pointId);
      if (i >= 0) return i;
    }
    return Math.min(points.length - 1, Math.floor(points.length / 2));
  }, [points, highlights]);

  const [internalIdx, setInternalIdx] = useState<number>(defaultIdx);
  const [isDragging, setIsDragging] = useState(false);

  const selectedIdx = controlledIdx !== undefined ? controlledIdx : internalIdx;
  const setSelectedIdx = (idx: number) => {
    setInternalIdx(idx);
    onSelectIdx?.(idx);
  };

  useEffect(() => {
    setInternalIdx(defaultIdx);
  }, [defaultIdx]);

  if (!frames.length || !points.length) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-surface-900 p-6 text-center text-sm text-slate-400">
        Chưa có dữ liệu timeline cho trận đấu này.
      </div>
    );
  }

  const safeIdx = Math.max(0, Math.min(points.length - 1, selectedIdx));
  const selected = points[safeIdx];

  // Geometry
  const W = 720;
  const H = 290;
  const PAD_L = 18;
  const PAD_R = 52;
  const PAD_T = 22;
  const PAD_B = 34;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const midY = PAD_T + plotH / 2;

  const maxTs = Math.max(60_000, points[points.length - 1].timestampMs);
  const xOf = (ts: number) => PAD_L + (ts / maxTs) * plotW;

  // Y mapping depends on tab (Win Probability 0..100% vs Cumulative Contribution -max..+max)
  const maxAbsContrib = Math.max(10, ...points.map((p) => Math.abs(p.focusImpactCumulative)));
  const yOf = (p: EventTimelinePoint) => {
    if (tab === "winprob") {
      return PAD_T + ((100 - p.focusWinProb) / 100) * plotH;
    }
    return midY - (p.focusImpactCumulative / maxAbsContrib) * (plotH / 2);
  };

  const coords = points.map((p) => ({ x: xOf(p.timestampMs), y: yOf(p), p }));
  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L ${coords[coords.length - 1].x.toFixed(1)} ${midY.toFixed(1)} L ${coords[0].x.toFixed(
    1
  )} ${midY.toFixed(1)} Z`;

  // X-axis ticks every 5 minutes (05:00, 10:00, 15:00, ...)
  const maxMin = Math.floor(maxTs / 60_000);
  const xTicks: number[] = [];
  for (let m = 5; m <= maxMin; m += 5) xTicks.push(m);

  // Select nearest point by SVG pointer X and auto-scroll the right timestamp list
  function selectFromClientX(clientX: number, scrollFeed: boolean) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const relX = ((clientX - rect.left) / rect.width) * W;
    const clampedX = Math.max(PAD_L, Math.min(W - PAD_R, relX));
    const targetTs = ((clampedX - PAD_L) / plotW) * maxTs;

    let best = 0;
    let bestDist = Infinity;
    for (let i = 0; i < points.length; i++) {
      const d = Math.abs(points[i].timestampMs - targetTs);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    }
    setSelectedIdx(best);
    if (scrollFeed) {
      const el = rowRefs.current[points[best].id];
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function jumpToPointId(pointId: string) {
    const idx = points.findIndex((p) => p.id === pointId);
    if (idx >= 0) {
      setSelectedIdx(idx);
      rowRefs.current[pointId]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  const selCoord = coords[safeIdx];
  const isPositivePoint =
    tab === "winprob" ? selected.focusWinProb >= 50 : selected.focusImpactCumulative >= 0;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
      {/* LEFT COLUMN: Graph + Floating Info + Turning Point Cards */}
      <div className="lg:col-span-8 rounded-2xl border border-slate-800/90 bg-[#0b101b] p-4 sm:p-5 flex flex-col justify-between gap-4">
        {/* Top bar: Floating info box + Win Probability / Your Contribution toggle */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          {/* Floating Info Box (matches Coachless top-left card) */}
          <div className="inline-flex items-center gap-3.5 rounded-xl border border-slate-700/80 bg-[#111827]/95 px-3.5 py-2.5 shadow-lg">
            <div className="space-y-0.5 text-xs">
              <div className="font-semibold text-slate-200">
                {tab === "winprob" ? (
                  <>
                    Win Probability:{" "}
                    <span className={selected.focusWinProb >= 50 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                      {selected.focusWinProb.toFixed(1)}%
                    </span>
                  </>
                ) : (
                  <>
                    Contribution:{" "}
                    <span
                      className={
                        selected.focusImpactCumulative >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"
                      }
                    >
                      {selected.focusImpactCumulative >= 0 ? "+" : ""}
                      {selected.focusImpactCumulative.toFixed(2)}%
                    </span>
                  </>
                )}
              </div>
              <div className="text-slate-400 font-mono text-[11px]">
                Time: <span className="text-slate-100 font-semibold">{formatMMSS(selected.timestampMs)}</span>
                {selected.probDelta !== 0 && (
                  <span className={`ml-2 ${selected.probDelta > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    ({selected.probDelta > 0 ? "+" : ""}
                    {selected.probDelta.toFixed(1)}%)
                  </span>
                )}
              </div>
            </div>

            {selected.kind !== "MINUTE" && (
              <div className="flex items-center gap-2 pl-2 border-l border-slate-700/70">
                <EventIcons point={selected} catalog={catalog} size="md" />
                <span
                  className={`w-1.5 h-8 rounded-full ${
                    selected.killerTeamId === focusTeamId ? "bg-emerald-400" : "bg-rose-500"
                  }`}
                />
              </div>
            )}
          </div>

          {/* Right controls: Tabs + Model badge */}
          <div className="flex flex-col items-end gap-1.5">
            <div className="inline-flex rounded-lg border border-slate-700/90 bg-[#0d1322] p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setTab("winprob")}
                className={`px-3 py-1.5 rounded-md transition ${
                  tab === "winprob"
                    ? "bg-slate-800 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Win Probability
              </button>
              <button
                type="button"
                onClick={() => setTab("contribution")}
                className={`px-3 py-1.5 rounded-md transition ${
                  tab === "contribution"
                    ? "bg-slate-800 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {focusLabel ? `${focusLabel.split("#")[0]} Contribution` : "Your Contribution"}
              </button>
            </div>
            {analytics && (
              <span className="inline-flex items-center gap-1 text-[10px] text-slate-400">
                <BrainCircuit className="w-3 h-3 text-emerald-400" />
                {analytics.modelSource === "lightgbm"
                  ? `LightGBM${analytics.modelMetrics?.rocAuc ? ` • AUC ${analytics.modelMetrics.rocAuc}` : ""}`
                  : "Heuristic fallback"}
              </span>
            )}
          </div>
        </div>

        {/* Interactive SVG Graph (click or drag anywhere) */}
        <div className="w-full overflow-x-auto">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            className="w-full min-w-[480px] h-auto select-none cursor-crosshair"
            onPointerDown={(e) => {
              setIsDragging(true);
              selectFromClientX(e.clientX, true);
            }}
            onPointerMove={(e) => {
              if (isDragging) selectFromClientX(e.clientX, true);
            }}
            onPointerUp={() => setIsDragging(false)}
            onPointerLeave={() => setIsDragging(false)}
          >
            <defs>
              <clipPath id="aboveMid">
                <rect x={PAD_L} y={PAD_T} width={plotW} height={plotH / 2} />
              </clipPath>
              <clipPath id="belowMid">
                <rect x={PAD_L} y={midY} width={plotW} height={plotH / 2} />
              </clipPath>
              <linearGradient id="emeraldArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.42" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0.02" />
              </linearGradient>
              <linearGradient id="roseArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.02" />
                <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.42" />
              </linearGradient>
            </defs>

            {/* Center 50% / 0% dashed line */}
            <line
              x1={PAD_L}
              y1={midY}
              x2={W - PAD_R}
              y2={midY}
              stroke="#475569"
              strokeDasharray="3 4"
              strokeWidth={1}
            />

            {/* Right-side Y-axis labels (100%, 50%, 0%) */}
            {(tab === "winprob"
              ? [
                  { y: PAD_T + 4, label: "100%" },
                  { y: midY + 4, label: "50%" },
                  { y: PAD_T + plotH, label: "0%" },
                ]
              : [
                  { y: PAD_T + 4, label: `+${Math.round(maxAbsContrib)}%` },
                  { y: midY + 4, label: "0%" },
                  { y: PAD_T + plotH, label: `-${Math.round(maxAbsContrib)}%` },
                ]
            ).map((t, i) => (
              <text key={i} x={W - PAD_R + 10} y={t.y} className="fill-slate-400 text-[11px] font-medium">
                {t.label}
              </text>
            ))}

            {/* Split-colored Area & Curve (Emerald above 50%, Rose below 50%) */}
            <g clipPath="url(#aboveMid)">
              <path d={areaPath} fill="url(#emeraldArea)" />
              <path d={linePath} fill="none" stroke="#34d399" strokeWidth={2} strokeLinejoin="round" />
            </g>
            <g clipPath="url(#belowMid)">
              <path d={areaPath} fill="url(#roseArea)" />
              <path d={linePath} fill="none" stroke="#fb7185" strokeWidth={2} strokeLinejoin="round" />
            </g>

            {/* Vertical crosshair line at selected timestamp */}
            <line
              x1={selCoord.x}
              y1={PAD_T - 4}
              x2={selCoord.x}
              y2={PAD_T + plotH + 6}
              stroke="#e2e8f0"
              strokeOpacity={0.75}
              strokeWidth={1.2}
            />

            {/* Turning-point markers directly on the curve */}
            {highlights.map((h) => {
              const idx = points.findIndex((p) => p.id === h.pointId);
              if (idx < 0) return null;
              const c = coords[idx];
              const good = h.probDelta >= 0;
              return (
                <g
                  key={h.pointId}
                  onClick={(e) => {
                    e.stopPropagation();
                    jumpToPointId(h.pointId);
                  }}
                  className="cursor-pointer"
                >
                  <circle
                    cx={c.x}
                    cy={c.y}
                    r={9}
                    className={
                      good
                        ? "fill-emerald-950/90 stroke-emerald-400"
                        : "fill-rose-950/90 stroke-rose-400"
                    }
                    strokeWidth={1.6}
                  />
                  <text
                    x={c.x}
                    y={c.y + 3.5}
                    textAnchor="middle"
                    className={good ? "fill-emerald-300 text-[9px] font-bold" : "fill-rose-300 text-[9px] font-bold"}
                  >
                    {h.kind === "ELITE_MONSTER_KILL" ? "★" : h.kind === "BUILDING_KILL" ? "♜" : "⚔"}
                  </text>
                </g>
              );
            })}

            {/* Selected point dot */}
            <circle
              cx={selCoord.x}
              cy={selCoord.y}
              r={5}
              className={
                isPositivePoint
                  ? "fill-emerald-400 stroke-[#0b101b]"
                  : "fill-rose-400 stroke-[#0b101b]"
              }
              strokeWidth={2}
            />

            {/* X-axis timestamps (05:00, 10:00, 15:00, ...) */}
            {xTicks.map((m) => (
              <text
                key={m}
                x={xOf(m * 60_000)}
                y={H - 8}
                textAnchor="middle"
                className="fill-slate-400 text-[11px] font-mono"
              >
                {String(m).padStart(2, "0")}:00
              </text>
            ))}
          </svg>
        </div>

        {/* Bottom 5 Turning Point Cards (clickable to jump to exact timestamp) */}
        {highlights.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {highlights.map((h) => {
              const good = h.probDelta >= 0;
              const active = selected.id === h.pointId;
              return (
                <button
                  key={h.pointId}
                  type="button"
                  onClick={() => jumpToPointId(h.pointId)}
                  className={`rounded-xl border px-3 py-2.5 text-left transition ${
                    active
                      ? good
                        ? "border-emerald-400 bg-emerald-950/40"
                        : "border-rose-400 bg-rose-950/40"
                      : "border-slate-800 bg-[#101624] hover:border-slate-600"
                  }`}
                >
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                    <span
                      className={`inline-flex items-center justify-center w-5 h-5 rounded-full border ${
                        good
                          ? "border-emerald-400/60 text-emerald-300 bg-emerald-950/60"
                          : "border-rose-400/60 text-rose-300 bg-rose-950/60"
                      }`}
                    >
                      {h.kind === "ELITE_MONSTER_KILL" ? (
                        <Crown className="w-3 h-3" />
                      ) : h.kind === "BUILDING_KILL" ? (
                        <Castle className="w-3 h-3" />
                      ) : good ? (
                        <Shield className="w-3 h-3" />
                      ) : (
                        <Swords className="w-3 h-3" />
                      )}
                    </span>
                    <span className="truncate">{h.label}</span>
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[11px]">
                    <span className={`font-bold font-mono ${good ? "text-emerald-400" : "text-rose-400"}`}>
                      {h.probDelta >= 0 ? "+" : ""}
                      {h.probDelta.toFixed(1)}%
                    </span>
                    <span className="text-slate-500 font-mono">{formatMMSS(h.timestampMs)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* RIGHT COLUMN: Synchronized Timestamp Event Feed */}
      <aside className="lg:col-span-4 rounded-2xl border border-slate-800/90 bg-[#0b101b] overflow-hidden flex flex-col max-h-[470px]">
        <div className="px-3.5 py-2.5 border-b border-slate-800/80 flex items-center justify-between text-[11px] font-semibold text-slate-400">
          <span>Timeline Events</span>
          <span className="font-mono text-slate-500">Bấm chọn mốc thời gian</span>
        </div>

        <div className="overflow-y-auto divide-y divide-slate-800/60 flex-1">
          {points.map((pt, idx) => {
            const isSel = idx === safeIdx;
            const isMinuteOnly = pt.kind === "MINUTE";
            const good = pt.killerTeamId === focusTeamId;

            return (
              <button
                key={pt.id}
                ref={(el) => {
                  rowRefs.current[pt.id] = el;
                }}
                type="button"
                onClick={() => setSelectedIdx(idx)}
                className={`w-full px-3.5 py-2.5 flex items-center justify-between gap-2 text-left transition ${
                  isSel
                    ? isMinuteOnly
                      ? "bg-slate-800/80 ring-1 ring-inset ring-cyan-400/70"
                      : good
                        ? "bg-emerald-950/40 ring-1 ring-inset ring-emerald-400/70"
                        : "bg-rose-950/40 ring-1 ring-inset ring-rose-400/70"
                    : "hover:bg-slate-900/70"
                }`}
              >
                <span
                  className={`font-mono text-xs ${
                    isSel ? "text-white font-bold" : isMinuteOnly ? "text-slate-500" : "text-slate-300 font-semibold"
                  }`}
                >
                  {formatMMSS(pt.timestampMs)}
                </span>

                {isMinuteOnly ? (
                  <span className="text-[11px] font-mono text-slate-500">
                    {pt.focusWinProb.toFixed(1)}%
                  </span>
                ) : (
                  <div className="flex items-center gap-2">
                    <EventIcons point={pt} catalog={catalog} size="sm" />
                    <span
                      className={`w-1.5 h-7 rounded-full shrink-0 ${
                        good ? "bg-emerald-400" : "bg-rose-500"
                      }`}
                    />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </aside>
    </div>
  );
}

function EventIcons({
  point,
  catalog,
  size = "sm",
}: {
  point: EventTimelinePoint;
  catalog: StaticCatalog | null;
  size?: "sm" | "md";
}) {
  const mainCls = size === "md" ? "w-8 h-8 rounded-md" : "w-7 h-7 rounded-md";
  const assistCls = size === "md" ? "w-5 h-5 rounded-sm" : "w-4 h-4 rounded-sm";

  if (point.kind === "CHAMPION_KILL") {
    const killer = point.killerChampionId ? catalog?.champions[String(point.killerChampionId)] : undefined;
    const victim = point.victimChampionId ? catalog?.champions[String(point.victimChampionId)] : undefined;
    const assists = (point.assistChampionIds || []).slice(0, 3);

    return (
      <div className="flex items-center gap-1.5">
        {assists.length > 0 && (
          <div className="flex items-center gap-0.5 opacity-85">
            {assists.map((cid, i) => {
              const ac = catalog?.champions[String(cid)];
              return (
                <GameAssetImg
                  key={i}
                  src={ac?.imageUrl}
                  alt={ac?.name || `#${cid}`}
                  fallbackText={String(cid)}
                  className={`${assistCls} border border-slate-700`}
                />
              );
            })}
          </div>
        )}
        <GameAssetImg
          src={killer?.imageUrl}
          alt={killer?.name || `#${point.killerChampionId ?? "?"}`}
          fallbackText={String(point.killerChampionId ?? "?")}
          className={`${mainCls} border border-slate-600`}
        />
        <Swords className="w-3.5 h-3.5 text-slate-400 shrink-0" />
        <GameAssetImg
          src={victim?.imageUrl}
          alt={victim?.name || `#${point.victimChampionId ?? "?"}`}
          fallbackText={String(point.victimChampionId ?? "?")}
          className={`${mainCls} border border-slate-600`}
        />
      </div>
    );
  }

  const killer = point.killerChampionId ? catalog?.champions[String(point.killerChampionId)] : undefined;
  const label =
    point.kind === "ELITE_MONSTER_KILL"
      ? monsterLabel(point.monsterType, point.monsterSubType)
      : point.buildingType === "INHIBITOR_BUILDING"
        ? "Nhà Lính"
        : "Phá Trụ";

  return (
    <div className="flex items-center gap-1.5">
      {point.killerChampionId && (
        <GameAssetImg
          src={killer?.imageUrl}
          alt={killer?.name || `#${point.killerChampionId}`}
          fallbackText={String(point.killerChampionId)}
          className={`${mainCls} border border-slate-600`}
        />
      )}
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-800/90 border border-slate-700 text-[11px] font-semibold text-slate-200">
        {point.kind === "ELITE_MONSTER_KILL" ? (
          point.monsterType === "BARON_NASHOR" ? (
            <Crown className="w-3.5 h-3.5 text-purple-300" />
          ) : (
            <Flame className="w-3.5 h-3.5 text-amber-300" />
          )
        ) : (
          <Castle className="w-3.5 h-3.5 text-slate-300" />
        )}
        <span>{label}</span>
      </span>
    </div>
  );
}

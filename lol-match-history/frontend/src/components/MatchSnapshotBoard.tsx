"use client";

import { useMemo, useState } from "react";
import { Swords, Flame, Crown, Castle, Coins } from "lucide-react";
import type {
  EventTimelinePoint,
  ItemTimelineEvent,
  KillTimelineEvent,
  MatchReviewResponse,
  ParticipantFrameSnapshot,
  ReviewParticipant,
  StaticCatalog,
  TimelineKeyEvent,
} from "@/lib/types";
import { monsterLabel } from "@/lib/format";
import { GameAssetImg } from "./GameAssetImg";

interface MatchSnapshotBoardProps {
  review: MatchReviewResponse;
  catalog: StaticCatalog | null;
  selectedPoint: EventTimelinePoint;
  focusTeamId: number;
}

const MAP_SIZE = 14870;

// Trinket item IDs in League of Legends
const TRINKET_IDS = new Set([3340, 3363, 3364, 3330, 3513]);

// Standard Summoner's Rift turret coordinates (teamId, x, y)
const SR_TURRETS: Array<{ teamId: number; x: number; y: number }> = [
  // Blue side (100)
  { teamId: 100, x: 981, y: 10441 },
  { teamId: 100, x: 1512, y: 6699 },
  { teamId: 100, x: 1169, y: 4287 },
  { teamId: 100, x: 5846, y: 6396 },
  { teamId: 100, x: 5048, y: 4812 },
  { teamId: 100, x: 3651, y: 3696 },
  { teamId: 100, x: 10504, y: 1029 },
  { teamId: 100, x: 6919, y: 1483 },
  { teamId: 100, x: 4281, y: 1253 },
  { teamId: 100, x: 1748, y: 2270 },
  { teamId: 100, x: 2177, y: 1807 },
  // Red side (200)
  { teamId: 200, x: 4318, y: 13875 },
  { teamId: 200, x: 7943, y: 13411 },
  { teamId: 200, x: 10481, y: 13650 },
  { teamId: 200, x: 8955, y: 8510 },
  { teamId: 200, x: 9767, y: 10113 },
  { teamId: 200, x: 11134, y: 11207 },
  { teamId: 200, x: 13866, y: 4505 },
  { teamId: 200, x: 13327, y: 8226 },
  { teamId: 200, x: 13624, y: 10572 },
  { teamId: 200, x: 12611, y: 13084 },
  { teamId: 200, x: 13052, y: 12612 },
];

const FALLBACK_POS: Record<string, { blue: [number, number]; red: [number, number] }> = {
  TOP: { blue: [2400, 12200], red: [3200, 12900] },
  JUNGLE: { blue: [4800, 8200], red: [9800, 6400] },
  MIDDLE: { blue: [7100, 7200], red: [7800, 7900] },
  BOTTOM: { blue: [12000, 2600], red: [12800, 3400] },
  UTILITY: { blue: [11400, 2200], red: [12200, 3800] },
};

function formatMMSS(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function toMapPct(x: number, y: number): { left: string; top: string } {
  const lx = Math.max(2, Math.min(98, (x / MAP_SIZE) * 100));
  const ty = Math.max(2, Math.min(98, (1 - y / MAP_SIZE) * 100));
  return { left: `${lx.toFixed(2)}%`, top: `${ty.toFixed(2)}%` };
}

/**
 * Reconstruct each participant's inventory (up to 6 items + 1 trinket) at timestamp `ts`.
 */
function reconstructInventories(
  itemEvents: ItemTimelineEvent[],
  ts: number
): Record<number, { items: number[]; trinket: number }> {
  const bags: Record<number, { items: number[]; trinket: number }> = {};
  const ensure = (pid: number) => {
    if (!bags[pid]) bags[pid] = { items: [], trinket: 0 };
    return bags[pid];
  };

  for (const ev of itemEvents) {
    if (ev.timestampMs > ts) break;
    const bag = ensure(ev.participantId);
    if (ev.type === "ITEM_PURCHASED" && ev.itemId) {
      if (TRINKET_IDS.has(ev.itemId)) {
        bag.trinket = ev.itemId;
      } else if (bag.items.length < 6) {
        bag.items.push(ev.itemId);
      } else {
        bag.items[5] = ev.itemId;
      }
    } else if ((ev.type === "ITEM_SOLD" || ev.type === "ITEM_DESTROYED") && ev.itemId) {
      if (TRINKET_IDS.has(ev.itemId)) {
        if (bag.trinket === ev.itemId) bag.trinket = 0;
      } else {
        const idx = bag.items.lastIndexOf(ev.itemId);
        if (idx >= 0) bag.items.splice(idx, 1);
      }
    } else if (ev.type === "ITEM_UNDO") {
      if (ev.beforeId && ev.beforeId > 0) {
        if (TRINKET_IDS.has(ev.beforeId)) {
          if (bag.trinket === ev.beforeId) bag.trinket = 0;
        } else {
          const idx = bag.items.lastIndexOf(ev.beforeId);
          if (idx >= 0) bag.items.splice(idx, 1);
        }
      }
      if (ev.afterId && ev.afterId > 0) {
        if (TRINKET_IDS.has(ev.afterId)) {
          bag.trinket = ev.afterId;
        } else if (bag.items.length < 6) {
          bag.items.push(ev.afterId);
        }
      }
    }
  }
  return bags;
}

/**
 * Interpolate participant gold, level, cs, and (x, y) position at timestamp `ts`.
 */
function interpolateParticipantStates(
  pFrames: ParticipantFrameSnapshot[],
  ts: number
): Record<number, { gold: number; level: number; cs: number; x: number | null; y: number | null }> {
  if (!pFrames.length) return {};
  let prev = pFrames[0];
  let next = pFrames[pFrames.length - 1];
  for (let i = 0; i < pFrames.length; i++) {
    if (pFrames[i].timestampMs <= ts) {
      prev = pFrames[i];
      next = pFrames[Math.min(pFrames.length - 1, i + 1)];
    } else {
      break;
    }
  }
  const span = Math.max(1, next.timestampMs - prev.timestampMs);
  const alpha = next.timestampMs === prev.timestampMs ? 0 : Math.max(0, Math.min(1, (ts - prev.timestampMs) / span));

  const out: Record<number, { gold: number; level: number; cs: number; x: number | null; y: number | null }> = {};
  for (const pidStr of Object.keys(prev.participants)) {
    const pid = Number(pidStr);
    const a = prev.participants[pidStr];
    const b = next.participants[pidStr] || a;
    const x = a.x != null && b.x != null ? Math.round(a.x + alpha * (b.x - a.x)) : a.x ?? b.x;
    const y = a.y != null && b.y != null ? Math.round(a.y + alpha * (b.y - a.y)) : a.y ?? b.y;
    out[pid] = {
      gold: Math.round(a.gold + alpha * (b.gold - a.gold)),
      level: alpha >= 0.8 ? b.level : a.level,
      cs: Math.round(a.cs + alpha * (b.cs - a.cs)),
      x,
      y,
    };
  }
  return out;
}

export function MatchSnapshotBoard({ review, catalog, selectedPoint, focusTeamId }: MatchSnapshotBoardProps) {
  const [mapImgFailed, setMapImgFailed] = useState(false);
  const ts = selectedPoint.timestampMs;
  const elapsedMin = Math.max(0.1, ts / 60_000);

  const pFrames = review.timeline?.participantFrames || [];
  const itemEvents = review.timeline?.itemEvents || [];
  const killEvents: KillTimelineEvent[] = review.timeline?.killEvents || [];
  const keyEvents: TimelineKeyEvent[] = review.timeline?.keyEvents || [];

  const snapshot = useMemo(() => {
    const states = interpolateParticipantStates(pFrames, ts);
    const inventories = reconstructInventories(itemEvents, ts);

    // KDA up to `ts` per participantId
    const kdaByPid: Record<number, { k: number; d: number; a: number }> = {};
    const ensureKda = (pid: number) => {
      if (!kdaByPid[pid]) kdaByPid[pid] = { k: 0, d: 0, a: 0 };
      return kdaByPid[pid];
    };

    // Track most recent kill position per participant within +/- 45s to refine map positions
    const recentEventPos: Record<number, { x: number; y: number; dist: number }> = {};
    for (const ev of killEvents) {
      if (ev.timestampMs <= ts) {
        if (ev.killerId) ensureKda(ev.killerId).k += 1;
        if (ev.victimId) ensureKda(ev.victimId).d += 1;
        for (const a of ev.assistingParticipantIds) ensureKda(a).a += 1;
      }
      const dist = Math.abs(ev.timestampMs - ts);
      if (ev.position && dist <= 45_000) {
        for (const pid of [ev.killerId, ev.victimId, ...ev.assistingParticipantIds]) {
          if (!pid) continue;
          if (!recentEventPos[pid] || dist < recentEventPos[pid].dist) {
            recentEventPos[pid] = { x: ev.position.x, y: ev.position.y, dist };
          }
        }
      }
    }

    // Objectives & destroyed turrets up to `ts`
    const teamObj: Record<number, { dragons: number; barons: number; heralds: number; towers: number }> = {
      100: { dragons: 0, barons: 0, heralds: 0, towers: 0 },
      200: { dragons: 0, barons: 0, heralds: 0, towers: 0 },
    };
    const destroyedPositions: Array<{ x: number; y: number; teamId: number }> = [];

    for (const ev of keyEvents) {
      if (ev.timestampMs > ts) continue;
      if (ev.type === "ELITE_MONSTER_KILL" && ev.killerTeamId && teamObj[ev.killerTeamId]) {
        if (ev.monsterType === "DRAGON") teamObj[ev.killerTeamId].dragons += 1;
        else if (ev.monsterType === "BARON_NASHOR") teamObj[ev.killerTeamId].barons += 1;
        else if (ev.monsterType === "RIFTHERALD") teamObj[ev.killerTeamId].heralds += 1;
      } else if (ev.type === "BUILDING_KILL") {
        if (ev.killerTeamId && teamObj[ev.killerTeamId] && ev.buildingType !== "INHIBITOR_BUILDING") {
          teamObj[ev.killerTeamId].towers += 1;
        }
        if (ev.position && ev.teamId) {
          destroyedPositions.push({ x: ev.position.x, y: ev.position.y, teamId: ev.teamId });
        }
      }
    }

    return { states, inventories, kdaByPid, recentEventPos, teamObj, destroyedPositions };
  }, [pFrames, itemEvents, killEvents, keyEvents, ts]);

  const yourTeamId = focusTeamId;
  const enemyTeamId = focusTeamId === 100 ? 200 : 100;
  const yourPlayers = review.participants.filter((p) => p.teamId === yourTeamId);
  const enemyPlayers = review.participants.filter((p) => p.teamId === enemyTeamId);

  const sumTeam = (players: ReviewParticipant[]) => {
    let kills = 0;
    let gold = 0;
    for (const p of players) {
      const pid = p.participantId || 0;
      kills += snapshot.kdaByPid[pid]?.k || 0;
      gold += snapshot.states[pid]?.gold || 0;
    }
    return { kills, gold };
  };

  const yourTotals = sumTeam(yourPlayers);
  const enemyTotals = sumTeam(enemyPlayers);

  const yourWinProb = selectedPoint.focusWinProb;
  const enemyWinProb = Math.max(0, Math.min(100, Number((100 - yourWinProb).toFixed(1))));

  const mapVersion = catalog?.patch || "14.23.1";
  const mapUrl = `https://ddragon.leagueoflegends.com/cdn/${mapVersion}/img/map/map11.png`;

  // Compute remaining standing turrets
  const standingTurrets = SR_TURRETS.filter(
    (t) =>
      !snapshot.destroyedPositions.some(
        (d) => d.teamId === t.teamId && Math.hypot(d.x - t.x, d.y - t.y) < 900
      )
  );

  // Resolve final map (x, y) for each of the 10 participants
  const mapMarkers = review.participants.map((p) => {
    const pid = p.participantId || 0;
    const st = snapshot.states[pid];
    const recent = snapshot.recentEventPos[pid];
    let x = st?.x ?? null;
    let y = st?.y ?? null;
    if (recent && recent.dist <= 15_000) {
      x = recent.x;
      y = recent.y;
    } else if (x == null || y == null || (x === 0 && y === 0)) {
      if (recent) {
        x = recent.x;
        y = recent.y;
      } else {
        const fb = FALLBACK_POS[(p.teamPosition || "MIDDLE").toUpperCase()] || FALLBACK_POS.MIDDLE;
        [x, y] = p.teamId === 100 ? fb.blue : fb.red;
      }
    }
    return { p, x, y };
  });

  return (
    <section className="grid grid-cols-1 xl:grid-cols-12 gap-3.5 items-start">
      {/* LEFT: Your Team */}
      <div className="xl:col-span-4 space-y-2">
        <TeamHeaderCard
          label="Your team"
          align="left"
          accent="emerald"
          kills={yourTotals.kills}
          gold={yourTotals.gold}
          obj={snapshot.teamObj[yourTeamId]}
        />
        {yourPlayers.map((p) => (
          <PlayerSnapshotRow
            key={p.puuid}
            player={p}
            catalog={catalog}
            state={snapshot.states[p.participantId || 0]}
            kda={snapshot.kdaByPid[p.participantId || 0]}
            inventory={snapshot.inventories[p.participantId || 0]}
            elapsedMin={elapsedMin}
            highlight={p.isFocus}
          />
        ))}
      </div>

      {/* CENTER: Win Prob Bar + Summoner's Rift Minimap + Selected Event */}
      <div className="xl:col-span-4 space-y-3">
        {/* Win probability split bar */}
        <div className="rounded-xl border border-slate-800/90 bg-[#0b101b] px-4 py-3 space-y-2">
          <div className="text-[11px] font-medium text-slate-400">Win probability</div>
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-emerald-400 font-mono min-w-[46px]">
              {yourWinProb.toFixed(1)}%
            </span>
            <div className="relative flex-1 h-2 rounded-full bg-rose-500 overflow-hidden">
              <div
                className="h-full bg-emerald-400 transition-all duration-200"
                style={{ width: `${yourWinProb}%` }}
              />
              <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-slate-950/80" />
            </div>
            <span className="text-sm font-bold text-rose-400 font-mono min-w-[46px] text-right">
              {enemyWinProb.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Minimap */}
        <div className="relative aspect-square w-full rounded-2xl border border-slate-800 bg-[#0d1522] overflow-hidden shadow-xl">
          {!mapImgFailed ? (
            <img
              src={mapUrl}
              alt="Summoner's Rift Minimap"
              onError={() => setMapImgFailed(true)}
              className="w-full h-full object-cover opacity-85 select-none"
            />
          ) : (
            /* Clean offline SVG Summoner's Rift schematic fallback */
            <svg viewBox="0 0 100 100" className="w-full h-full bg-[#131d2b]">
              <path d="M 8 92 L 8 8 L 92 8" fill="none" stroke="#2c3e55" strokeWidth="7" strokeLinecap="round" />
              <path d="M 8 92 L 92 92 L 92 8" fill="none" stroke="#2c3e55" strokeWidth="7" strokeLinecap="round" />
              <line x1="10" y1="90" x2="90" y2="10" stroke="#2c3e55" strokeWidth="6" />
              <line x1="12" y1="12" x2="88" y2="88" stroke="#1b4d6e" strokeWidth="8" strokeOpacity="0.65" />
              <circle cx="10" cy="90" r="10" fill="#1e3a5f" />
              <circle cx="90" cy="10" r="10" fill="#4c1d2e" />
            </svg>
          )}

          {/* Standing turrets */}
          {standingTurrets.map((t, idx) => {
            const pos = toMapPct(t.x, t.y);
            const isBlue = t.teamId === 100;
            return (
              <div
                key={idx}
                style={pos}
                title={isBlue ? "Trụ Đội Xanh" : "Trụ Đội Đỏ"}
                className={`absolute -translate-x-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border border-slate-950 ${
                  isBlue ? "bg-sky-400 shadow-[0_0_6px_#38bdf8]" : "bg-rose-500 shadow-[0_0_6px_#f43f5e]"
                }`}
              />
            );
          })}

          {/* Ping ring at the selected event's position */}
          {selectedPoint.position && (
            <div
              style={toMapPct(selectedPoint.position.x, selectedPoint.position.y)}
              className="absolute -translate-x-1/2 -translate-y-1/2 w-9 h-9 rounded-full border-2 border-amber-300 bg-amber-400/20 animate-pulse pointer-events-none"
            />
          )}

          {/* 10 Champion Position Markers */}
          {mapMarkers.map(({ p, x, y }) => {
            const champ = catalog?.champions[String(p.championId)];
            const pos = toMapPct(x, y);
            const isYours = p.teamId === yourTeamId;
            return (
              <div
                key={p.puuid}
                style={pos}
                title={`${champ?.name || `#${p.championId}`} (${p.riotId || p.teamPosition || ""})`}
                className={`absolute -translate-x-1/2 -translate-y-1/2 transition-all duration-200 ${
                  p.isFocus ? "z-20 scale-110" : "z-10"
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-full overflow-hidden border-2 shadow-md ${
                    p.isFocus
                      ? "border-cyan-300 ring-2 ring-cyan-400/50"
                      : isYours
                        ? "border-emerald-400"
                        : "border-rose-500"
                  }`}
                >
                  <GameAssetImg
                    src={champ?.imageUrl}
                    alt={champ?.name || String(p.championId)}
                    fallbackText={String(p.championId)}
                    className="w-full h-full"
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Event Footer Bar (matches `10:22 [Fizz] ⚔ [MF]` in screenshot) */}
        <div className="rounded-xl border border-slate-800/90 bg-[#0b101b] px-4 py-2.5 flex items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-3">
            <span className="font-mono font-bold text-slate-300">{formatMMSS(ts)}</span>
            {selectedPoint.kind === "CHAMPION_KILL" ? (
              <div className="flex items-center gap-1.5">
                <GameAssetImg
                  src={
                    selectedPoint.killerChampionId
                      ? catalog?.champions[String(selectedPoint.killerChampionId)]?.imageUrl
                      : undefined
                  }
                  alt="Killer"
                  fallbackText={String(selectedPoint.killerChampionId ?? "?")}
                  className="w-7 h-7 rounded-md border border-slate-600"
                />
                <Swords className="w-3.5 h-3.5 text-slate-400" />
                <GameAssetImg
                  src={
                    selectedPoint.victimChampionId
                      ? catalog?.champions[String(selectedPoint.victimChampionId)]?.imageUrl
                      : undefined
                  }
                  alt="Victim"
                  fallbackText={String(selectedPoint.victimChampionId ?? "?")}
                  className="w-7 h-7 rounded-md border border-slate-600"
                />
              </div>
            ) : selectedPoint.kind === "MINUTE" ? (
              <span className="text-slate-400">Trạng thái bản đồ tại phút {selectedPoint.minute}&apos;</span>
            ) : (
              <span className="font-semibold text-slate-200">
                {selectedPoint.kind === "ELITE_MONSTER_KILL"
                  ? monsterLabel(selectedPoint.monsterType, selectedPoint.monsterSubType)
                  : "Phá Trụ / Nhà Lính"}
              </span>
            )}
          </div>
          <span
            className={`w-1.5 h-6 rounded-full ${
              selectedPoint.kind === "MINUTE"
                ? "bg-slate-600"
                : selectedPoint.killerTeamId === yourTeamId
                  ? "bg-emerald-400"
                  : "bg-rose-500"
            }`}
          />
        </div>
      </div>

      {/* RIGHT: Enemy Team */}
      <div className="xl:col-span-4 space-y-2">
        <TeamHeaderCard
          label="Enemy team"
          align="right"
          accent="rose"
          kills={enemyTotals.kills}
          gold={enemyTotals.gold}
          obj={snapshot.teamObj[enemyTeamId]}
        />
        {enemyPlayers.map((p) => (
          <PlayerSnapshotRow
            key={p.puuid}
            player={p}
            catalog={catalog}
            state={snapshot.states[p.participantId || 0]}
            kda={snapshot.kdaByPid[p.participantId || 0]}
            inventory={snapshot.inventories[p.participantId || 0]}
            elapsedMin={elapsedMin}
            highlight={p.isFocus}
          />
        ))}
      </div>
    </section>
  );
}

function TeamHeaderCard({
  label,
  align,
  accent,
  kills,
  gold,
  obj,
}: {
  label: string;
  align: "left" | "right";
  accent: "emerald" | "rose";
  kills: number;
  gold: number;
  obj: { dragons: number; barons: number; heralds: number; towers: number };
}) {
  const isLeft = align === "left";
  const color = accent === "emerald" ? "text-emerald-400" : "text-rose-400";
  return (
    <div className="rounded-xl border border-slate-800/90 bg-[#0b101b] px-3.5 py-2.5 space-y-1.5">
      <div className={`flex items-center justify-between ${isLeft ? "" : "flex-row-reverse"}`}>
        <span className="text-xs font-bold text-slate-200">{label}</span>
        <span className={`inline-flex items-center gap-1 text-base font-extrabold font-mono ${color}`}>
          <Swords className="w-4 h-4" />
          {kills}
        </span>
      </div>
      <div className={`flex items-center justify-between text-[11px] text-slate-400 ${isLeft ? "" : "flex-row-reverse"}`}>
        <div className="flex items-center gap-2.5">
          <span title="Rồng" className="inline-flex items-center gap-1">
            <Flame className="w-3 h-3 text-amber-400" />
            {obj.dragons}
          </span>
          <span title="Baron" className="inline-flex items-center gap-1">
            <Crown className="w-3 h-3 text-purple-400" />
            {obj.barons}
          </span>
          <span title="Trụ" className="inline-flex items-center gap-1">
            <Castle className="w-3 h-3 text-slate-400" />
            {obj.towers}
          </span>
        </div>
        <span className="inline-flex items-center gap-1 font-mono font-semibold text-slate-200">
          <Coins className="w-3 h-3 text-gold-400" />
          {(gold / 1000).toFixed(1)}K
        </span>
      </div>
    </div>
  );
}

function PlayerSnapshotRow({
  player,
  catalog,
  state,
  kda,
  inventory,
  elapsedMin,
  highlight,
}: {
  player: ReviewParticipant;
  catalog: StaticCatalog | null;
  state?: { gold: number; level: number; cs: number };
  kda?: { k: number; d: number; a: number };
  inventory?: { items: number[]; trinket: number };
  elapsedMin: number;
  highlight: boolean;
}) {
  const champ = catalog?.champions[String(player.championId)];
  const keystone = player.keystoneId ? catalog?.runes[String(player.keystoneId)] : undefined;
  const subStyle = player.runes?.subStyle ? catalog?.runes[String(player.runes.subStyle)] : undefined;

  const kills = kda?.k ?? 0;
  const deaths = kda?.d ?? 0;
  const assists = kda?.a ?? 0;
  const kdaLabel = deaths === 0 ? (kills + assists > 0 ? "∞ KDA" : "KDA") : `${((kills + assists) / deaths).toFixed(2)} KDA`;
  const cs = state?.cs ?? 0;
  const csPerMin = (cs / elapsedMin).toFixed(2);
  const level = state?.level ?? 1;

  // Build 2x4 grid: top row [item0, item1, item2, trinket], bottom row [item3, item4, item5, empty]
  const invItems = inventory ? inventory.items : [];
  const trinket = inventory ? inventory.trinket : 0;
  const topSlots = [invItems[0] || 0, invItems[1] || 0, invItems[2] || 0, trinket];
  const bottomSlots = [invItems[3] || 0, invItems[4] || 0, invItems[5] || 0, 0];

  return (
    <div
      className={`rounded-xl border px-3 py-2.5 flex items-center justify-between gap-2 transition ${
        highlight
          ? "border-emerald-400/80 bg-[#0d1c22]"
          : "border-slate-800/90 bg-[#0b101b]"
      }`}
    >
      {/* Left: Champ + Level + Runes + Spells */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="relative">
          <GameAssetImg
            src={champ?.imageUrl}
            alt={champ?.name || String(player.championId)}
            fallbackText={String(player.championId)}
            className="w-11 h-11 rounded-full border border-slate-700"
          />
          <span className="absolute -bottom-0.5 -left-0.5 w-5 h-5 rounded-full bg-surface-950 border border-slate-600 flex items-center justify-center text-[10px] font-bold text-slate-200">
            {level}
          </span>
          {keystone && (
            <div className="absolute -top-0.5 -right-1.5 w-5 h-5 rounded-full bg-surface-950 border border-slate-700 p-0.5">
              <GameAssetImg src={keystone.imageUrl} alt={keystone.name} fallbackText="R" className="w-full h-full rounded-full" />
            </div>
          )}
          {subStyle && (
            <div className="absolute -bottom-0.5 -right-1.5 w-4 h-4 rounded-full bg-surface-950 border border-slate-700 p-0.5">
              <GameAssetImg src={subStyle.imageUrl} alt={subStyle.name} fallbackText="S" className="w-full h-full rounded-full" />
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1 ml-1">
          {player.spells.slice(0, 2).map((sid, i) => {
            const sp = sid ? catalog?.spells[String(sid)] : undefined;
            return (
              <GameAssetImg
                key={i}
                src={sp?.imageUrl}
                alt={sp?.name || ""}
                fallbackText={sid ? `S${sid}` : "-"}
                className="w-5 h-5 rounded border border-slate-700"
              />
            );
          })}
        </div>
      </div>

      {/* Middle: KDA + CS at timestamp */}
      <div className="min-w-0 flex-1 px-1">
        <div className="text-xs font-bold text-slate-100 font-mono">
          {kills} / {deaths} / {assists}
        </div>
        <div className="text-[11px] text-slate-400">{kdaLabel}</div>
        <div className="text-[11px] text-slate-300 truncate">
          {cs} CS <span className="text-slate-500">({csPerMin})</span>
        </div>
      </div>

      {/* Right: 2x4 Inventory Grid at timestamp */}
      <div className="grid grid-cols-4 gap-1 shrink-0">
        {[...topSlots, ...bottomSlots].map((itemId, idx) => {
          const isTrinket = idx === 3;
          const item = itemId ? catalog?.items[String(itemId)] : undefined;
          if (!itemId) {
            return (
              <div
                key={idx}
                className={`w-6 h-6 bg-[#111827] border border-slate-800/90 ${isTrinket ? "rounded-full" : "rounded"}`}
              />
            );
          }
          return (
            <GameAssetImg
              key={idx}
              src={item?.imageUrl}
              alt={item?.name || `Item #${itemId}`}
              fallbackText={String(itemId)}
              className={`w-6 h-6 border border-slate-700 ${isTrinket ? "rounded-full" : "rounded"}`}
            />
          );
        })}
      </div>
    </div>
  );
}

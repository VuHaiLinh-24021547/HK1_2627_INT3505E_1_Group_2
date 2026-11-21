"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { MatchListItem, StaticCatalog } from "@/lib/types";
import { formatDuration, formatRelativeTime, queueLabel } from "@/lib/format";
import { GameAssetImg } from "./GameAssetImg";

interface MatchCardProps {
  match: MatchListItem;
  region: string;
  catalog: StaticCatalog | null;
}

export function MatchCard({ match, region, catalog }: MatchCardProps) {
  const { player, participants } = match;
  const win = player.win;
  const champ = catalog?.champions[String(player.championId)];
  const keystone = player.keystoneId ? catalog?.runes[String(player.keystoneId)] : undefined;

  const blueTeam = participants.filter((p) => p.teamId === 100);
  const redTeam = participants.filter((p) => p.teamId === 200);

  const href = `/matches/${encodeURIComponent(match.matchId)}?focusPuuid=${encodeURIComponent(
    player.puuid
  )}&region=${encodeURIComponent(region)}`;

  return (
    <Link
      href={href}
      className={`group block rounded-xl border transition-all duration-150 ${
        win
          ? "border-emerald-500/25 bg-gradient-to-r from-emerald-950/40 via-surface-900 to-surface-900 hover:border-emerald-400/50"
          : "border-rose-500/25 bg-gradient-to-r from-rose-950/40 via-surface-900 to-surface-900 hover:border-rose-400/50"
      }`}
    >
      <div className="p-3.5 sm:p-4 flex flex-col md:flex-row md:items-center gap-3.5 justify-between">
        {/* Left: outcome + queue + duration */}
        <div className="flex items-center gap-3 min-w-[135px]">
          <div className={`w-1.5 self-stretch rounded-full ${win ? "bg-emerald-400" : "bg-rose-400"}`} />
          <div className="text-xs space-y-0.5">
            <div className={`font-bold uppercase tracking-wide ${win ? "text-emerald-400" : "text-rose-400"}`}>
              {win ? "Chiến Thắng" : "Thất Bại"}
            </div>
            <div className="text-slate-300 font-medium truncate max-w-[135px]">{queueLabel(match.queueId)}</div>
            <div className="text-slate-500">
              {formatDuration(match.gameDuration)} &bull; {formatRelativeTime(match.gameCreation)}
            </div>
            <div className="text-[10px] text-slate-500">Patch {match.patch}</div>
          </div>
        </div>

        {/* Center-left: Champion, spells, keystone, KDA, CS */}
        <div className="flex items-center gap-3.5">
          <div className="flex items-center gap-1.5">
            <div className="relative">
              <GameAssetImg
                src={champ?.imageUrl}
                alt={champ?.name || `Champ ${player.championId}`}
                fallbackText={String(player.championId)}
                className="w-12 h-12 rounded-xl border border-slate-700"
              />
              {player.teamPosition && (
                <span className="absolute -bottom-1 -right-1 px-1 py-0.2 rounded bg-surface-950 border border-slate-700 text-[9px] font-bold text-slate-300">
                  {player.teamPosition.slice(0, 3)}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1">
              {player.spells.slice(0, 2).map((spellId, idx) => {
                const spell = spellId ? catalog?.spells[String(spellId)] : undefined;
                return (
                  <GameAssetImg
                    key={idx}
                    src={spell?.imageUrl}
                    alt={spell?.name || `Spell ${spellId ?? ""}`}
                    fallbackText={spellId ? `S${spellId}` : "-"}
                    className="w-5 h-5 rounded border border-slate-700/80"
                  />
                );
              })}
            </div>
            <GameAssetImg
              src={keystone?.imageUrl}
              alt={keystone?.name || "Keystone"}
              fallbackText="R"
              className="w-7 h-7 rounded-full border border-gold-500/40 bg-surface-950 p-0.5"
            />
          </div>

          <div className="min-w-[96px]">
            <div className="text-base font-bold tracking-tight text-slate-100">
              {player.kills} <span className="text-slate-500">/</span>{" "}
              <span className="text-rose-400">{player.deaths}</span> <span className="text-slate-500">/</span>{" "}
              {player.assists}
            </div>
            <div className="text-xs font-semibold text-cyan-300">{player.kda.toFixed(2)} KDA</div>
            <div className="text-[11px] text-slate-400">
              {player.csTotal} CS ({player.csPerMin}/ph)
            </div>
          </div>
        </div>

        {/* Center-right: 6 items + trinket */}
        <div className="flex items-center gap-1">
          {player.items.slice(0, 7).map((itemId, idx) => {
            const isTrinket = idx === 6;
            const item = itemId ? catalog?.items[String(itemId)] : undefined;
            if (!itemId) {
              return (
                <div
                  key={idx}
                  className={`w-7 h-7 ${
                    isTrinket ? "rounded-full ml-1" : "rounded-md"
                  } bg-surface-950/70 border border-slate-800`}
                />
              );
            }
            return (
              <GameAssetImg
                key={idx}
                src={item?.imageUrl}
                alt={item?.name || `Item ${itemId}`}
                fallbackText={String(itemId)}
                className={`w-7 h-7 border border-slate-700/80 ${isTrinket ? "rounded-full ml-1" : "rounded-md"}`}
              />
            );
          })}
        </div>

        {/* Right: 10 participants compact list */}
        <div className="hidden lg:grid grid-cols-2 gap-x-3 gap-y-0.5 w-[210px] text-[11px]">
          {[0, 1, 2, 3, 4].map((row) => {
            const b = blueTeam[row];
            const r = redTeam[row];
            return (
              <div key={row} className="contents">
                <ParticipantMini p={b} focusPuuid={player.puuid} catalog={catalog} />
                <ParticipantMini p={r} focusPuuid={player.puuid} catalog={catalog} />
              </div>
            );
          })}
        </div>

        <div className="hidden md:flex items-center text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition">
          <ChevronRight className="w-5 h-5" />
        </div>
      </div>
    </Link>
  );
}

function ParticipantMini({
  p,
  focusPuuid,
  catalog,
}: {
  p?: MatchListItem["participants"][number];
  focusPuuid: string;
  catalog: StaticCatalog | null;
}) {
  if (!p) return <div />;
  const champ = catalog?.champions[String(p.championId)];
  const isMe = p.puuid === focusPuuid;
  const displayName = (p.riotId || "Unknown").split("#")[0];
  return (
    <div className="flex items-center gap-1 min-w-0">
      <GameAssetImg
        src={champ?.imageUrl}
        alt={champ?.name || String(p.championId)}
        fallbackText={String(p.championId)}
        className="w-4 h-4 rounded-sm"
      />
      <span className={`truncate ${isMe ? "font-bold text-cyan-300" : "text-slate-400"}`}>{displayName}</span>
    </div>
  );
}

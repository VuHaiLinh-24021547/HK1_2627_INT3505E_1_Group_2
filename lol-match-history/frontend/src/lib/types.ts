export interface ProblemDetails {
  type?: string;
  title?: string;
  status: number;
  detail: string;
  instance?: string;
  traceId?: string;
  code?: string;
  retryAfterSeconds?: number;
  errors?: Array<{ field?: string | null; code?: string; message: string }>;
}

export interface PlayerProfile {
  puuid: string;
  region: string;
  gameName: string;
  tagLine: string;
  riotId: string;
  profileIconId: number | null;
  summonerLevel: number | null;
  soloTier: string | null;
  soloRank: string | null;
  soloLp: number;
  soloWins: number;
  soloLosses: number;
  soloWinRate: number | null;
  lastSyncedAt: string | null;
  updatedAt: string | null;
  canSync: boolean;
  cooldownRemainingSec: number;
}

export interface MatchParticipantSummary {
  puuid: string;
  teamId: number;
  championId: number;
  teamPosition: string | null;
  riotId: string | null;
}

export interface MatchPlayerStats {
  puuid: string;
  riotId: string | null;
  teamId: number;
  teamPosition: string | null;
  championId: number;
  win: boolean;
  kills: number;
  deaths: number;
  assists: number;
  kda: number;
  csTotal: number;
  csPerMin: number;
  goldEarned: number;
  damageToChamps: number;
  visionScore: number;
  items: number[];
  spells: Array<number | null>;
  keystoneId: number | null;
}

export interface MatchListItem {
  matchId: string;
  queueId: number;
  gameCreation: number;
  gameDuration: number;
  patch: string;
  player: MatchPlayerStats;
  participants: MatchParticipantSummary[];
}

export interface MatchListSummary {
  games: number;
  wins: number;
  losses: number;
  winRate: number;
  avgKda: number;
  avgCsPerMin: number;
}

export interface MatchListResponse {
  data: MatchListItem[];
  summary: MatchListSummary;
  pagination: {
    limit: number;
    nextCursor: string | null;
    hasMore: boolean;
  };
}

export interface TeamSummary {
  teamId: number;
  win: boolean;
  kills: number;
  barons: number;
  dragons: number;
  heralds: number;
  voidGrubs: number;
  towers: number;
  inhibitors: number;
  bans: number[];
}

export interface ReviewParticipant extends MatchPlayerStats {
  runes?: {
    primaryStyle?: number | null;
    subStyle?: number | null;
    keystoneId?: number | null;
    perkIds?: number[];
  };
  isFocus: boolean;
  participantId: number | null;
  itemPurchases: Array<{ timestampMs: number; itemId: number }>;
}

export interface TimelineFrame {
  minute: number;
  timestampMs: number;
  blueGold: number;
  redGold: number;
  blueGoldDiff: number;
  blueXp: number;
  redXp: number;
  blueXpDiff: number;
}

export interface TimelineKeyEvent {
  timestampMs: number;
  type: "ELITE_MONSTER_KILL" | "BUILDING_KILL" | string;
  monsterType?: string;
  monsterSubType?: string;
  buildingType?: string;
  towerType?: string;
  laneType?: string;
  teamId?: number;
  killerTeamId?: number | null;
  position?: { x: number; y: number } | null;
}

export interface ParticipantFrameSnapshot {
  minute: number;
  timestampMs: number;
  participants: Record<
    string,
    {
      gold: number;
      level: number;
      cs: number;
      x: number | null;
      y: number | null;
    }
  >;
}

export interface ItemTimelineEvent {
  timestampMs: number;
  type: "ITEM_PURCHASED" | "ITEM_SOLD" | "ITEM_DESTROYED" | "ITEM_UNDO";
  participantId: number;
  itemId?: number;
  beforeId?: number;
  afterId?: number;
}

export interface KillTimelineEvent {
  timestampMs: number;
  killerId: number | null;
  victimId: number | null;
  assistingParticipantIds: number[];
  position?: { x: number; y: number } | null;
}

export interface LaneMatchup {
  position: string;
  blueChampionId: number;
  redChampionId: number;
  blueWinRate: number;
  games: number;
}

export interface WinProbabilityFrame {
  minute: number;
  blueWinProb: number;
  focusWinProb: number;
  focusImpactDelta: number;
  focusImpactCumulative: number;
}

export interface PlayerContribution {
  puuid: string;
  riotId: string | null;
  teamId: number;
  teamPosition: string | null;
  championId: number | null;
  isFocus: boolean;
  totalImpact: number;
  combatImpact: number;
  objectiveImpact: number;
  laningImpact: number;
}

export interface EventTimelinePoint {
  id: string;
  timestampMs: number;
  minute: number;
  kind: "MINUTE" | "CHAMPION_KILL" | "ELITE_MONSTER_KILL" | "BUILDING_KILL" | string;
  blueWinProb: number;
  focusWinProb: number;
  probDelta: number;
  focusImpactDelta: number;
  focusImpactCumulative: number;
  killerTeamId?: number | null;
  killerChampionId?: number | null;
  victimChampionId?: number | null;
  assistChampionIds?: number[];
  monsterType?: string;
  monsterSubType?: string;
  buildingType?: string;
  laneType?: string;
  position?: { x: number; y: number } | null;
}

export interface TimelineHighlight {
  pointId: string;
  timestampMs: number;
  kind: string;
  label: string;
  probDelta: number;
  focusWinProb: number;
  monsterType?: string;
}

export interface MatchAnalytics {
  modelSource: "lightgbm" | "heuristic";
  modelMetrics: {
    trainMatches?: number;
    valMatches?: number;
    rocAuc?: number;
    logLoss?: number;
    brierScore?: number;
    trainedAt?: string;
  } | null;
  initialBlueWinRate: number;
  laneMatchups: LaneMatchup[];
  winProbabilityFrames: WinProbabilityFrame[];
  eventTimeline?: EventTimelinePoint[];
  highlights?: TimelineHighlight[];
  playerContributions: PlayerContribution[];
}

export interface MatchReviewResponse {
  matchId: string;
  region: string;
  queueId: number;
  gameCreation: number;
  gameDuration: number;
  patch: string;
  focusPuuid: string | null;
  teams: TeamSummary[];
  participants: ReviewParticipant[];
  timeline: {
    intervalMs: number;
    frames: TimelineFrame[];
    keyEvents: TimelineKeyEvent[];
    participantFrames?: ParticipantFrameSnapshot[];
    itemEvents?: ItemTimelineEvent[];
    killEvents?: KillTimelineEvent[];
  } | null;
  analytics?: MatchAnalytics | null;
}

export interface StaticCatalog {
  patch: string;
  lang: string;
  champions: Record<string, { id: number; alias: string; name: string; title?: string; imageUrl: string }>;
  items: Record<string, { id: number; name: string; gold?: number; imageUrl: string }>;
  runes: Record<string, { id: number; name: string; type: string; styleId?: number; imageUrl: string }>;
  spells: Record<string, { id: number; alias: string; name: string; imageUrl: string }>;
}

export interface SyncJob {
  jobId: string;
  status: "queued" | "started" | "finished" | "failed";
  puuid: string;
  region: string;
  count: number;
  queueId: number | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  result: {
    requested: number;
    newMatches: number;
    skippedExisting: number;
    notFound: number;
    importedMatchIds: string[];
  } | null;
  error: { code: string; message: string } | null;
}

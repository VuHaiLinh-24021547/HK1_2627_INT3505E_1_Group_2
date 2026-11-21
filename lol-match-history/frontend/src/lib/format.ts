export const REGIONS = [
  { code: "vn2", label: "VN2", name: "Việt Nam" },
  { code: "kr", label: "KR", name: "Hàn Quốc" },
  { code: "euw1", label: "EUW", name: "Tây Âu" },
  { code: "na1", label: "NA", name: "Bắc Mỹ" },
  { code: "sg2", label: "SG2", name: "Singapore" },
  { code: "tw2", label: "TW2", name: "Đài Loan" },
  { code: "jp1", label: "JP1", name: "Nhật Bản" },
  { code: "oc1", label: "OC1", name: "Châu Đại Dương" },
] as const;

export const QUEUE_NAMES: Record<number, string> = {
  420: "Xếp Hạng Đơn/Đôi",
  440: "Xếp Hạng Linh Hoạt",
  450: "ARAM",
  400: "Thường (Chọn Ẩn/Cấm Chọn)",
  430: "Thường",
  490: "Đấu Nhanh",
  1700: "Võ Đài",
};

export const POSITION_LABELS: Record<string, string> = {
  TOP: "Đường Trên",
  JUNGLE: "Đi Rừng",
  MIDDLE: "Đường Giữa",
  BOTTOM: "Xạ Thủ",
  UTILITY: "Hỗ Trợ",
};

export function queueLabel(queueId: number): string {
  return QUEUE_NAMES[queueId] || `Queue ${queueId}`;
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatRelativeTime(timestampMs: number): string {
  const diffSec = Math.max(0, Math.floor((Date.now() - timestampMs) / 1000));
  if (diffSec < 60) return "vừa xong";
  const mins = Math.floor(diffSec / 60);
  if (mins < 60) return `${mins} phút trước`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} ngày trước`;
  return new Date(timestampMs).toLocaleDateString("vi-VN");
}

export function formatNumber(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function formatSignedGold(n: number): string {
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  const abs = Math.abs(n);
  return abs >= 1000 ? `${sign}${(abs / 1000).toFixed(1)}k` : `${sign}${abs}`;
}

export function tierColor(tier: string | null): string {
  switch ((tier || "").toUpperCase()) {
    case "CHALLENGER":
      return "text-amber-300 border-amber-400/40 bg-amber-500/10";
    case "GRANDMASTER":
      return "text-rose-300 border-rose-400/40 bg-rose-500/10";
    case "MASTER":
      return "text-purple-300 border-purple-400/40 bg-purple-500/10";
    case "DIAMOND":
      return "text-sky-300 border-sky-400/40 bg-sky-500/10";
    case "EMERALD":
      return "text-emerald-300 border-emerald-400/40 bg-emerald-500/10";
    case "PLATINUM":
      return "text-cyan-300 border-cyan-400/40 bg-cyan-500/10";
    case "GOLD":
      return "text-yellow-300 border-yellow-400/40 bg-yellow-500/10";
    default:
      return "text-slate-300 border-slate-600/50 bg-slate-800/60";
  }
}

export function encodeRiotIdSlug(gameName: string, tagLine: string): string {
  return encodeURIComponent(`${gameName}-${tagLine}`);
}

export function parseRiotIdSlug(slug: string): { gameName: string; tagLine: string } | null {
  const decoded = decodeURIComponent(slug);
  const hashIdx = decoded.lastIndexOf("#");
  if (hashIdx > 0 && hashIdx < decoded.length - 1) {
    return { gameName: decoded.slice(0, hashIdx), tagLine: decoded.slice(hashIdx + 1) };
  }
  const dashIdx = decoded.lastIndexOf("-");
  if (dashIdx > 0 && dashIdx < decoded.length - 1) {
    return { gameName: decoded.slice(0, dashIdx), tagLine: decoded.slice(dashIdx + 1) };
  }
  return null;
}

export function monsterLabel(monsterType?: string, subType?: string): string {
  if (monsterType === "BARON_NASHOR") return "Baron Nashor";
  if (monsterType === "RIFTHERALD") return "Sứ Giả Khe Nứt";
  if (monsterType === "HORDE") return "Sâu Hư Không";
  if (monsterType === "DRAGON") {
    const map: Record<string, string> = {
      FIRE_DRAGON: "Rồng Lửa",
      WATER_DRAGON: "Rồng Nước",
      EARTH_DRAGON: "Rồng Đất",
      AIR_DRAGON: "Rồng Gió",
      HEXTECH_DRAGON: "Rồng Công Nghệ",
      CHEMTECH_DRAGON: "Rồng Hóa Kỹ",
      ELDER_DRAGON: "Rồng Ngàn Tuổi",
    };
    return (subType && map[subType]) || "Rồng Nguyên Tố";
  }
  return monsterType || "Mục tiêu lớn";
}

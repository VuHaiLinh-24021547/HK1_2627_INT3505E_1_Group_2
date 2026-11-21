import Link from "next/link";
import { Activity, ShieldCheck, BarChart3, Sparkles } from "lucide-react";
import { SearchBar } from "@/components/SearchBar";

export default function HomePage() {
  return (
    <div className="relative overflow-hidden">
      {/* Subtle radial glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 w-[780px] h-[380px] rounded-full bg-cyan-500/10 blur-3xl"
      />

      <section className="relative mx-auto max-w-4xl px-4 pt-20 pb-16 text-center space-y-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Phong cách Coachless &bull; Hỗ trợ VN2, KR, EUW, NA</span>
        </div>

        <div className="space-y-4">
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Tra cứu &amp; Phân tích lịch sử đấu{" "}
            <span className="bg-gradient-to-r from-cyan-400 to-gold-400 bg-clip-text text-transparent">
              Liên Minh Huyền Thoại
            </span>
          </h1>
          <p className="mx-auto max-w-2xl text-sm sm:text-base text-slate-400">
            Xem chi tiết 10 người chơi, lọc theo tướng &amp; chế độ chơi, đồng bộ trận mới từ Riot API không dính rate
            limit và phân tích biểu đồ chênh lệch Vàng / XP từng phút.
          </p>
        </div>

        <div className="mx-auto max-w-xl">
          <SearchBar initialRegion="vn2" />
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-400">
            <span>Thử nhanh với dữ liệu mẫu:</span>
            <Link
              href="/players/vn2/Player1-VN2"
              className="px-2.5 py-1 rounded-lg bg-surface-900 border border-slate-700 hover:border-cyan-400 text-cyan-300 font-semibold transition"
            >
              Player1#VN2 (VN2)
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 pb-20 grid grid-cols-1 md:grid-cols-3 gap-4">
        <FeatureCard
          icon={<BarChart3 className="w-5 h-5 text-cyan-400" />}
          title="Biểu đồ Gold & XP Diff"
          desc="Theo dõi chênh lệch vàng và kinh nghiệm từng phút giữa Đội Xanh và Đội Đỏ kèm các mốc Baron, Rồng, Sứ Giả và phá trụ."
        />
        <FeatureCard
          icon={<Activity className="w-5 h-5 text-gold-400" />}
          title="Đồng bộ bất đồng bộ"
          desc="Chống trùng lặp trận đấu, cơ chế cooldown 120 giây và Idempotency-Key giúp làm mới dữ liệu an toàn trước giới hạn Riot API."
        />
        <FeatureCard
          icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />}
          title="Tài nguyên Data Dragon"
          desc="Tự động ánh xạ ảnh tướng, trang bị, ngọc bổ trợ và phép bổ trợ theo đúng phiên bản bản vá (vi_VN / en_US)."
        />
      </section>
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-surface-900/80 p-5 space-y-2.5">
      <div className="w-10 h-10 rounded-xl bg-surface-800 border border-slate-700/80 flex items-center justify-center">
        {icon}
      </div>
      <h2 className="text-base font-bold text-white">{title}</h2>
      <p className="text-xs leading-relaxed text-slate-400">{desc}</p>
    </div>
  );
}

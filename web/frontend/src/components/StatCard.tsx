interface StatCardProps {
  icon: string;
  value: string | number;
  label: string;
  subtitle?: string;
}

export function StatCard({ icon, value, label, subtitle }: StatCardProps) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 transition-all duration-300 hover:border-slate-700 hover:bg-slate-800/80">
      <div className="flex items-center gap-3 mb-2">
        <span className="text-2xl">{icon}</span>
        <div className="text-3xl font-bold text-white tabular-nums">
          {value}
        </div>
      </div>

      <div className="text-slate-300 font-medium text-sm mb-1">
        {label}
      </div>

      {subtitle && (
        <div className="text-slate-500 text-xs">
          {subtitle}
        </div>
      )}
    </div>
  );
}
interface StatCardProps {
  icon: string;
  value: string | number;
  label: string;
  subtitle?: string;
}

export function StatCard({ icon, value, label, subtitle }: StatCardProps) {
  return (
    <div className="bg-obsidian-surface border border-obsidian-border p-6 transition-all duration-300 hover:border-obsidian-accent/30 hover:bg-white/5">
      <div className="flex items-center gap-3 mb-2">
        <span className="text-2xl">{icon}</span>
        <div className="text-3xl font-bold text-obsidian-accent tabular-nums">
          {value}
        </div>
      </div>

      <div className="text-white/60 font-sf-mono text-sm mb-1">
        {label}
      </div>

      {subtitle && (
        <div className="text-white/40 text-xs font-sf-mono">
          {subtitle}
        </div>
      )}
    </div>
  );
}
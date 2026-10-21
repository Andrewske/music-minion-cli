import { formatKeepPct, formatLift, type InsightRow } from '../../api/insights';
import { liftBar, maxAbsLift } from './insightsView';

function LiftCell({ lift, maxAbs }: { lift: number; maxAbs: number }): JSX.Element {
  const bar = liftBar(lift, maxAbs);
  const tone = bar.side === 'up' ? 'text-obsidian-accent' : bar.side === 'down' ? 'text-red-400' : 'text-white/50';
  return (
    <div className="flex items-center justify-end gap-2">
      {/* Centered track: keeps grow right, passes grow left. */}
      <div className="relative hidden h-1.5 w-24 rounded-full bg-white/5 sm:block" aria-hidden="true">
        <span className="absolute inset-y-0 left-1/2 w-px bg-white/20" />
        {bar.side === 'up' && <span className="absolute inset-y-0 left-1/2 rounded-r-full bg-obsidian-accent" style={{ width: `${bar.widthPct / 2}%` }} />}
        {bar.side === 'down' && <span className="absolute inset-y-0 right-1/2 rounded-l-full bg-red-400/80" style={{ width: `${bar.widthPct / 2}%` }} />}
      </div>
      <span className={`w-20 text-right font-sf-mono text-xs ${tone}`}>{formatLift(lift)}</span>
    </div>
  );
}

interface InsightTableProps {
  label: string;
  rows: InsightRow[];
  selectedValue: string | null;
  onSelect: (row: InsightRow) => void;
}

/** One dimension's values: seen, keep % and lift vs the overall keep rate. */
export function InsightTable({ label, rows, selectedValue, onSelect }: InsightTableProps): JSX.Element {
  const maxAbs = maxAbsLift(rows);
  return (
    <table className="w-full text-left" aria-label={`${label} insights`}>
      <thead className="text-[11px] uppercase tracking-wide text-white/40">
        <tr>
          <th className="pb-2 pr-2 font-normal">{label}</th>
          <th className="pb-2 pr-2 text-right font-normal">Seen</th>
          <th className="pb-2 pr-2 text-right font-normal" title="A not quite counts as half a keep">Keep %</th>
          <th className="pb-2 text-right font-normal" title="Keep % minus your overall keep %">Lift</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const selected = row.value === selectedValue;
          return (
            <tr
              key={row.value}
              onClick={() => onSelect(row)}
              className={`cursor-pointer border-t border-obsidian-border ${selected ? 'bg-obsidian-accent/10' : 'hover:bg-white/5'}`}
            >
              <td className="py-1.5 pr-2">
                <button type="button" onClick={(event) => { event.stopPropagation(); onSelect(row); }} aria-pressed={selected} className={`text-left text-sm ${selected ? 'text-obsidian-accent' : 'text-white'} focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent`}>
                  {row.value}
                </button>
              </td>
              <td className="py-1.5 pr-2 text-right font-sf-mono text-xs text-white/70" title={`${row.keeps} keep · ${row.not_quites} not quite · ${row.nopes} nope`}>{row.seen}</td>
              <td className="py-1.5 pr-2 text-right font-sf-mono text-xs text-white">{formatKeepPct(row.keep_pct)}</td>
              <td className="py-1.5"><LiftCell lift={row.lift} maxAbs={maxAbs} /></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

"""Merge duplicate phantom .opus track records into their .mp3 twins.

The library DB had pre-existing duplicate rows (two track ids per file). The
opus->mp3 conversion updated one row to .mp3 and deleted the file; the twin row
still points at the now-missing .opus. Those phantom rows still carry curation
references (playlist memberships, ELO, genres, etc.), some of which the .mp3
twin lacks. This merges every phantom's references into its twin (skipping
redundant ones via UPDATE OR IGNORE), then deletes the phantom track row.

Usage:
    uv run python scripts/merge_opus_duplicates.py --dry-run
    uv run python scripts/merge_opus_duplicates.py --apply
"""

import argparse
import sys

from music_minion.core import database as db

# Every (table, column) pair whose FK references tracks.id, discovered at
# runtime — covers track_id plus comparison columns (winner_id, track_a_id,
# track_b_id) and state pointers (last_track_id, etc.).
def ref_columns(conn) -> list[tuple[str, str]]:
    tabs = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    out = []
    for t in tabs:
        if t == "tracks":
            continue
        for fk in conn.execute(f'PRAGMA foreign_key_list("{t}")').fetchall():
            # fk = (id, seq, table, from, to, on_update, on_delete, match)
            if fk[2] == "tracks" and fk[4] == "id":
                out.append((t, fk[3]))
    return out


def find_pairs(conn) -> list[tuple[int, int]]:
    """(phantom_opus_id, mp3_twin_id) for every phantom with an existing twin."""
    phantoms = conn.execute(
        "SELECT id, local_path FROM tracks WHERE lower(local_path) LIKE '%.opus'"
    ).fetchall()
    pairs = []
    for r in phantoms:
        mp3 = r["local_path"][:-5] + ".mp3"
        twin = conn.execute(
            "SELECT id FROM tracks WHERE local_path = ?", (mp3,)
        ).fetchone()
        if twin:
            pairs.append((r["id"], twin["id"]))
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with db.get_db_connection() as conn:
        cols = ref_columns(conn)
        pairs = find_pairs(conn)
        print(f"phantom->twin pairs: {len(pairs)}")
        print(f"FK columns referencing tracks.id: {len(cols)}")

        if args.dry_run:
            phantom_ids = [p for p, _ in pairs]
            qs = ",".join("?" * len(phantom_ids))
            for t, c in cols:
                n = conn.execute(
                    f'SELECT COUNT(*) FROM "{t}" WHERE "{c}" IN ({qs})',
                    phantom_ids,
                ).fetchone()[0]
                if n:
                    print(f"  {t}.{c}: {n} refs to repoint/dedupe")
            return 0

        # --apply: repoint every FK column, drop redundant leftovers, then
        # delete the phantom track rows (now unreferenced).
        moved = 0
        for phantom, twin in pairs:
            for t, c in cols:
                # Move refs the twin lacks; rows that would collide on a unique
                # constraint are skipped by OR IGNORE and deleted next.
                cur = conn.execute(
                    f'UPDATE OR IGNORE "{t}" SET "{c}" = ? WHERE "{c}" = ?',
                    (twin, phantom),
                )
                moved += cur.rowcount
                conn.execute(f'DELETE FROM "{t}" WHERE "{c}" = ?', (phantom,))
            conn.execute("DELETE FROM tracks WHERE id = ?", (phantom,))
        conn.commit()
        print(f"merged {len(pairs)} phantoms, repointed {moved} references")

        remaining = conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE lower(local_path) LIKE '%.opus'"
        ).fetchone()[0]
        print(f"opus records remaining: {remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

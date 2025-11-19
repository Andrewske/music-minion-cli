"""
Provider track import operations.

Handles importing tracks from external providers (SoundCloud, Spotify, etc.)
without deduplication - creates records with source=provider.
"""

from typing import Any, Dict, List, Tuple

from ...core import database


def batch_insert_provider_tracks(
    provider_tracks: List[Tuple[str, Dict[str, Any]]], provider: str
) -> Dict[str, int]:
    """Batch insert provider tracks without deduplication.

    Creates new track records with source=provider for all incoming tracks.
    Skips tracks that already exist (same provider_id + source).
    Uses batch operations for performance.

    Args:
        provider_tracks: List of (provider_id, metadata) from provider
        provider: Provider name ('soundcloud', 'spotify', etc.)

    Returns:
        Statistics: {'created': N, 'skipped': N, 'total': N}

    Raises:
        ValueError: If provider name is invalid
    """
    # Whitelist validation to prevent SQL injection
    VALID_PROVIDERS = {'soundcloud', 'spotify', 'youtube'}
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Invalid provider: {provider}. Must be one of: {VALID_PROVIDERS}")

    if not provider_tracks:
        return {"created": 0, "skipped": 0, "total": 0}

    # Get already-synced track IDs (check by provider_id + source)
    print(f"  Checking for duplicate {provider} tracks...")

    provider_id_col = f"{provider}_id"
    existing_ids = set()

    with database.get_db_connection() as conn:
        cursor = conn.execute(
            f"SELECT {provider_id_col} FROM tracks WHERE {provider_id_col} IS NOT NULL AND source = ?",
            (provider,),
        )
        existing_ids = {row[0] for row in cursor.fetchall()}

    if existing_ids:
        print(f"  Found {len(existing_ids)} existing {provider} tracks")

    # Filter out tracks that already exist
    to_insert = []
    skipped = 0

    for provider_id, metadata in provider_tracks:
        if provider_id in existing_ids:
            skipped += 1
            continue

        # Build insert record
        record = {
            provider_id_col: provider_id,
            "source": provider,
            f"{provider}_synced_at": None,  # Will use CURRENT_TIMESTAMP
        }

        # Add metadata fields
        record.update(metadata)

        to_insert.append(record)

    if skipped > 0:
        print(f"  Skipping {skipped} already-synced tracks")

    if not to_insert:
        print("  ✓ No new tracks to insert")
        return {"created": 0, "skipped": skipped, "total": len(provider_tracks)}

    # Batch insert (single transaction)
    print(f"  Inserting {len(to_insert)} new {provider} tracks...")

    # Build field list dynamically based on first record
    fields = list(to_insert[0].keys())
    placeholders = ", ".join([f":{field}" for field in fields])
    fields_str = ", ".join(fields)

    created = 0
    progress_interval = max(1, len(to_insert) // 100)  # Report every 1%

    with database.get_db_connection() as conn:
        try:
            # Begin explicit transaction for atomicity
            conn.execute("BEGIN TRANSACTION")

            for idx, record in enumerate(to_insert, 1):
                try:
                    conn.execute(
                        f"""
                        INSERT INTO tracks ({fields_str})
                        VALUES ({placeholders})
                        """,
                        record,
                    )
                    created += 1

                    # Progress update
                    if idx % progress_interval == 0 or idx == len(to_insert):
                        pct = (idx / len(to_insert)) * 100
                        print(f"    Progress: {idx}/{len(to_insert)} ({pct:.0f}%)")

                except Exception as e:
                    # Log error but continue with other tracks
                    print(
                        f"  Warning: Failed to insert track {record.get(provider_id_col)}: {e}"
                    )
                    continue

            # Commit all changes at once
            conn.commit()

        except Exception as e:
            # Rollback on any critical error
            conn.rollback()
            print(f"  ❌ Transaction failed, rolled back: {e}")
            raise

    print(f"  ✓ Created {created} new {provider} tracks")

    return {"created": created, "skipped": skipped, "total": len(provider_tracks)}

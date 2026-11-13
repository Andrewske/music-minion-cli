"""Follow suggestions: rank SoundCloud accounts by evidence from likes and keeps.

Pure functions only; the DB reads live in queries/follow_suggestions.py and
the nightly cache fill in follow_suggestion_caches.py.

    evidence = sum over liked/kept tracks of role_weight * recency_weight
    score    = evidence * activity_factor * size_factor

Each track credits an account once (its highest-weight role). Credited names
that resolve to an SC account merge into that account's entry; the rest stay
name-only suggestions keyed "name:<name_key>".
"""

import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
from functools import lru_cache
from typing import Any, NamedTuple

from web.backend.queries.artists import (
    _DASH_REMIX_RE,
    _FEAT_RE,
    _TITLE_REMIX_RE,
    _parse_track_credits,
    _split_credits,
)
from web.backend.soundcloud_metadata import parse_soundcloud_datetime as parse_time

ROLE_WEIGHTS: dict[str, float] = {
    "uploaded": 1.0,
    "original": 1.0,
    "remixer": 0.8,
    "feat": 0.5,
    "remixed_by_others": 0.2,
}
KEPT_WEIGHT = 0.5  # cap for tracks kept in feed/stories but never liked
ROLES = ("uploaded", "original", "remixer", "feat", "remixed_by_others", "kept")

RECENCY_FLOOR = 0.3
RECENCY_HALF_LIFE_MONTHS = 12.0
# Fallback when only the like's position is known: weight halves every
# 1,000 likes back (roughly a year of liking, a guess to tune).
RECENCY_HALF_LIFE_LIKES = 1000.0
ACTIVITY_UNKNOWN = 0.6
ACTIVITY_DORMANT = 0.1
ACTIVITY_DORMANT_DAYS = 365
ACTIVITY_SATURATION = 8  # uploads + reposts in 90 days for a full factor
SIZE_KNEE = 500_000
SIZE_AT_10M = 0.5
SIZE_MIN = 0.2
DUO_ALONE_MAX = 0.2  # a part seen alone in >= 20% of its tracks is its own name
DUO_MIN_TRACKS = 2  # a pairing seen once is a collab, not a duo name
NAME_ONLY_MIN_TRACKS = 2
LABEL_MIN_UPLOADS = 3
LABEL_OTHER_SHARE = 0.6  # share of uploads crediting someone else
TRACKS_PER_SUGGESTION = 20

LABEL_NAME_RE = re.compile(
    r"records|recordings|music\s*group|network|label|collective|\brecs\b|recs$",
    re.IGNORECASE,
)
_SLUG_SUFFIX_RE = re.compile(r"(?:music|official|musik|dj|beats|producer)+$")
_SLUG_PREFIX_RE = re.compile(r"^(?:dj|its|thisis|iam)")
_TITLE_CREDIT_RE = re.compile(r"^(.+?)\s+[-–—]\s+\S")
_IGNORED_NAME_KEYS = frozenset({"variousartists", "various", "unknown", "va"})


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class EvidenceTrack(NamedTuple):
    soundcloud_id: str
    title: str
    artist: str
    remix_artist: str | None
    liked: bool  # False: kept in feed/stories but not liked
    liked_at: str | None  # like time, or decided_at for kept-only tracks
    uploader_id: str | None
    uploader_permalink: str | None
    uploader_username: str | None
    like_order: int | None = None  # 0 = newest like in the last full fetch


class Account(NamedTuple):
    """An SC account we know by id (followed artist or cached activity)."""

    soundcloud_user_id: str
    display_name: str | None
    permalink: str | None


class Resolution(NamedTuple):
    soundcloud_user_id: str | None  # None: looked up, no match
    permalink: str | None
    display_name: str | None
    confidence: str
    source: str


class Activity(NamedTuple):
    username: str | None
    permalink: str | None
    avatar_url: str | None
    followers: int | None
    last_upload_at: str | None
    last_repost_at: str | None
    uploads_90d: int
    reposts_90d: int
    is_label: bool


class Context(NamedTuple):
    """Everything besides the tracks that scoring needs."""

    followed: tuple[Account, ...]
    resolutions: Mapping[str, Resolution]  # name_key -> resolution
    activity: Mapping[str, Activity]  # soundcloud_user_id -> activity
    dismissed: frozenset[str]  # suggestion keys
    label_overrides: Mapping[str, bool]  # suggestion key -> is_label
    now: datetime


class Hit(NamedTuple):
    """One entity credited on one track."""

    ref: str  # SC user id, or "name:<key>"
    display: str
    track: EvidenceTrack
    role: str
    weight: float


# ---------------------------------------------------------------------------
# Name keys
# ---------------------------------------------------------------------------


@lru_cache(maxsize=65536)
def name_key(name: str | None) -> str:
    """Lowercase alphanumerics only, accents folded: 'Wooli 🐘' -> 'wooli'."""
    folded = unicodedata.normalize("NFKD", name or "").casefold()
    return "".join(c for c in folded if c.isalnum() and not unicodedata.combining(c))


def slug_keys(slug: str | None) -> set[str]:
    """Key of a slug plus the variant with music/official/dj... affixes stripped."""
    key = name_key(slug)
    stripped = _SLUG_PREFIX_RE.sub("", _SLUG_SUFFIX_RE.sub("", key))
    return {k for k in (key, stripped if len(stripped) >= 3 else "") if k}


def account_keys(display_name: str | None, permalink: str | None) -> set[str]:
    """Every key a followed/known account answers to."""
    return ({name_key(display_name)} | slug_keys(permalink)) - {""}


def name_ref(key: str) -> str:
    return f"name:{key}"


_PROFILE_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.|m\.)?soundcloud\.com/([\w-]+)(?:[/?#].*)?$", re.IGNORECASE
)
_BARE_SLUG_RE = re.compile(r"^[\w-]+$")


def profile_slug(text: str) -> str | None:
    """'https://soundcloud.com/phrva/tracks' or 'phrva' -> 'phrva'; else None."""
    text = text.strip()
    match = _PROFILE_URL_RE.match(text)
    if match:
        return match.group(1)
    return text if _BARE_SLUG_RE.match(text) else None


# ---------------------------------------------------------------------------
# Credits and the duo guard
# ---------------------------------------------------------------------------


def credit_groups(track: EvidenceTrack) -> list[str]:
    """Raw credit strings that _split_credits breaks apart (duo candidates)."""
    feat = _FEAT_RE.search(track.title or "")
    remix = _TITLE_REMIX_RE.search(track.title or "") or _DASH_REMIX_RE.search(
        track.title or ""
    )
    raw = [
        track.artist,
        track.remix_artist,
        (feat.group(1) or feat.group(2)) if feat else None,
        remix.group(1) if remix else None,
    ]
    return [g.strip() for g in raw if g and len(_split_credits(g)) > 1]


def _track_name_keys(track: EvidenceTrack) -> set[str]:
    credits = _parse_track_credits(track.artist, track.title, track.remix_artist)
    return {name_key(n) for names in credits.values() for n in names} - {""}


def find_duos(tracks: Iterable[EvidenceTrack]) -> dict[str, str]:
    """Split credit strings whose parts almost never appear apart.

    Returns whole-string key -> display. 'Chase & Status' stays one name when
    'chase' and 'status' each appear without the other on < 20% of their tracks
    (and together on 2+). Comma lists are never duo names.
    """
    tracks = list(tracks)
    tracks_by_key: dict[str, set[int]] = defaultdict(set)
    for i, track in enumerate(tracks):
        for key in _track_name_keys(track):
            tracks_by_key[key].add(i)
    groups = {name_key(g): g for t in tracks for g in credit_groups(t)}
    return {
        whole: display
        for whole, display in groups.items()
        if _is_duo(display, tracks_by_key)
    }


def _is_duo(display: str, tracks_by_key: Mapping[str, set[int]]) -> bool:
    parts = {name_key(p) for p in _split_credits(display)} - {""}
    if "," in display or len(parts) < 2 or any(p not in tracks_by_key for p in parts):
        return False
    together = set.intersection(*(tracks_by_key[p] for p in parts))
    return len(together) >= DUO_MIN_TRACKS and all(
        len(tracks_by_key[p] - together) / len(tracks_by_key[p]) < DUO_ALONE_MAX
        for p in parts
    )


def _apply_duos(names: list[str], duos: Mapping[str, str]) -> list[str]:
    """Replace the parts of each known duo with the whole duo name."""
    keys = {name_key(n) for n in names}
    out = list(names)
    for display in duos.values():
        parts = {name_key(p) for p in _split_credits(display)}
        if parts <= keys:
            out = [n for n in out if name_key(n) not in parts] + [display]
            keys = (keys - parts) | {name_key(display)}
    return out


def track_name_roles(
    track: EvidenceTrack, duos: Mapping[str, str]
) -> list[tuple[str, str]]:
    """(credited name, role) pairs for one track, duo guard applied."""
    credits = _parse_track_credits(track.artist, track.title, track.remix_artist)
    own = {name_key(g): g for g in credit_groups(track)}
    duos = {k: d for k, d in own.items() if k in duos}
    remixers = _apply_duos(credits["remixers"], duos)
    remixer_keys = {name_key(r) for r in remixers}
    primary_role = "remixed_by_others" if remixers else "original"
    pairs = [(r, "remixer") for r in remixers]
    pairs += [(f, "feat") for f in _apply_duos(credits["feats"], duos)]
    pairs += [
        (p, primary_role)
        for p in _apply_duos(credits["primaries"], duos)
        if name_key(p) not in remixer_keys
    ]
    return pairs


# ---------------------------------------------------------------------------
# Hits: who gets credit for which track
# ---------------------------------------------------------------------------


def role_weight(role: str, liked: bool) -> tuple[str, float]:
    """(reported role, weight); kept-only tracks report 'kept', capped at 0.5."""
    weight = ROLE_WEIGHTS[role]
    return (role, weight) if liked else ("kept", min(weight, KEPT_WEIGHT))


def track_hits(track: EvidenceTrack, duos: Mapping[str, str]) -> list[Hit]:
    """Every credited name and the uploader account on one track."""
    hits: list[Hit] = []
    if track.uploader_id:
        role, weight = role_weight("uploaded", track.liked)
        display = track.uploader_username or ""  # permalink is the last resort
        hits.append(Hit(track.uploader_id, display, track, role, weight))
    for name, raw_role in track_name_roles(track, duos):
        key = name_key(name)
        if key and key not in _IGNORED_NAME_KEYS:
            role, weight = role_weight(raw_role, track.liked)
            hits.append(Hit(name_ref(key), name, track, role, weight))
    return hits


def resolve_ref(ref: str, resolutions: Mapping[str, Resolution]) -> str:
    """Map 'name:<key>' to its SC user id when the name resolved to one."""
    if not ref.startswith("name:"):
        return ref
    resolution = resolutions.get(ref[5:])
    return (
        resolution.soundcloud_user_id
        if resolution and resolution.soundcloud_user_id
        else ref
    )


def best_hits_by_entity(
    hits: Iterable[Hit], resolutions: Mapping[str, Resolution]
) -> dict[str, list[Hit]]:
    """Group hits by final entity; one hit per (entity, track), highest weight."""
    best: dict[tuple[str, str], Hit] = {}
    for hit in hits:
        ref = resolve_ref(hit.ref, resolutions)
        slot = (ref, hit.track.soundcloud_id)
        if slot not in best or hit.weight > best[slot].weight:
            best[slot] = hit._replace(ref=ref) if ref != hit.ref else hit
    grouped: dict[str, list[Hit]] = defaultdict(list)
    for (ref, _sc_id), hit in best.items():
        grouped[ref].append(hit)
    return dict(grouped)


def entity_origins(
    hits: Iterable[Hit], resolutions: Mapping[str, Resolution]
) -> dict[str, frozenset[str]]:
    """Final entity -> every ref that resolved into it (itself included).

    Built from all hits, before the per-track dedup, so a name that only ever
    lost to the uploader on the same track still belongs to the account."""
    origins: dict[str, set[str]] = defaultdict(set)
    for hit in hits:
        ref = resolve_ref(hit.ref, resolutions)
        origins[ref] |= {ref, hit.ref}
    return {ref: frozenset(refs) for ref, refs in origins.items()}


def collect_hits(tracks: Iterable[EvidenceTrack]) -> list[Hit]:
    """Dedupe tracks by soundcloud_id (liked beats kept), then credit them."""
    unique: dict[str, EvidenceTrack] = {}
    for track in tracks:
        if track.soundcloud_id not in unique or track.liked:
            unique[track.soundcloud_id] = track
    duos = find_duos(unique.values())
    return [hit for t in unique.values() for hit in track_hits(t, duos)]


# ---------------------------------------------------------------------------
# Name resolution (local sources)
# ---------------------------------------------------------------------------


def _exact_uploader_keys(t: EvidenceTrack) -> set[str]:
    return {name_key(t.uploader_username), name_key(t.uploader_permalink)} - {""}


def _stripped_uploader_keys(t: EvidenceTrack) -> set[str]:
    return slug_keys(t.uploader_permalink) - _exact_uploader_keys(t)


def _uploader_key_map(
    tracks: list[EvidenceTrack], keys_of: Any
) -> dict[str, Resolution]:
    """Name key -> uploader whose keys include it; most liked uploads wins."""
    counts: Counter[tuple[str, str]] = Counter(
        (k, t.uploader_id) for t in tracks if t.uploader_id for k in keys_of(t)
    )
    info = {t.uploader_id: t for t in reversed(tracks) if t.uploader_id}
    best: dict[str, Resolution] = {}
    for (key, uid), _n in counts.most_common():
        t = info[uid]
        best.setdefault(
            key,
            Resolution(
                uid, t.uploader_permalink, t.uploader_username, "high", "uploader"
            ),
        )
    return best


def uploader_resolutions(tracks: Iterable[EvidenceTrack]) -> dict[str, Resolution]:
    """Source (a): name key -> liked-track uploader whose username/permalink key
    equals it; the permalink with music/official/dj affixes stripped
    ('gawmmusic' -> 'gawm') only where no exact key claims the name."""
    tracks = list(tracks)
    return combine_resolutions(
        _uploader_key_map(tracks, _exact_uploader_keys),
        _uploader_key_map(tracks, _stripped_uploader_keys),
    )


def activity_resolutions(activity: Mapping[str, Activity]) -> dict[str, Resolution]:
    """Name key -> account, from usernames/permalinks in the activity cache."""
    found: dict[str, Resolution] = {}
    for uid, a in sorted(activity.items(), key=lambda kv: -(kv[1].followers or 0)):
        resolution = Resolution(uid, a.permalink, a.username, "high", "activity")
        keys = {name_key(a.username), name_key(a.permalink)} - {""}
        found.update({k: resolution for k in keys if k not in found})
    return found


def combine_resolutions(*sources: Mapping[str, Resolution]) -> dict[str, Resolution]:
    """Earlier sources win; a cached miss never hides a later hit."""
    combined: dict[str, Resolution] = {}
    for source in sources:
        for key, resolution in source.items():
            current = combined.get(key)
            if current is None or (
                current.soundcloud_user_id is None and resolution.soundcloud_user_id
            ):
                combined[key] = resolution
    return combined


# ---------------------------------------------------------------------------
# Factors
# ---------------------------------------------------------------------------


def recency_weight(
    liked_at: str | None, now: datetime, like_order: int | None = None
) -> float:
    """0.3 + 0.7 * decay, from the like time or else the like's position.

    Decay halves every 12 months, or every 1,000 likes back when SC gave no
    time (most likes). Neither known: the 0.3 floor.
    """
    when = parse_time(liked_at)
    if when is not None:
        age_months = max(0.0, (now - when).days / 30.44)
        decay = 0.5 ** (age_months / RECENCY_HALF_LIFE_MONTHS)
    elif like_order is not None:
        decay = 0.5 ** (max(0, like_order) / RECENCY_HALF_LIFE_LIKES)
    else:
        return RECENCY_FLOOR
    return RECENCY_FLOOR + (1 - RECENCY_FLOOR) * decay


def last_active_at(activity: Activity) -> str | None:
    times = [t for t in (activity.last_upload_at, activity.last_repost_at) if t]
    return max(times, key=_time_key) if times else None


def activity_factor(activity: Activity | None, now: datetime) -> float:
    """0.5..1.0 from posts + reposts in 90 days; 0.1 if silent for a year."""
    if activity is None:
        return ACTIVITY_UNKNOWN
    last = parse_time(last_active_at(activity))
    if last is None or (now - last).days > ACTIVITY_DORMANT_DAYS:
        return ACTIVITY_DORMANT
    recent = activity.uploads_90d + activity.reposts_90d
    return 0.5 + 0.5 * min(1.0, recent / ACTIVITY_SATURATION)


def size_factor(followers: int | None) -> float:
    """1.0 up to 500k followers, then log-scale down (0.5 at 10M, floor 0.2)."""
    if not followers or followers <= SIZE_KNEE:
        return 1.0
    slope = (1 - SIZE_AT_10M) / math.log10(10_000_000 / SIZE_KNEE)
    return max(SIZE_MIN, 1 - slope * math.log10(followers / SIZE_KNEE))


# ---------------------------------------------------------------------------
# Exclusions and labels
# ---------------------------------------------------------------------------


class Followed(NamedTuple):
    ids: frozenset[str]
    keys: frozenset[str]


def followed_index(followed: Iterable[Account]) -> Followed:
    accounts = list(followed)
    return Followed(
        ids=frozenset(a.soundcloud_user_id for a in accounts if a.soundcloud_user_id),
        keys=frozenset(
            k for a in accounts for k in account_keys(a.display_name, a.permalink)
        ),
    )


def is_followed(ref: str, keys: set[str], followed: Followed) -> bool:
    """An account (known SC id) by id only; a name-only entity by its keys.

    Names never override a distinct id: Kevin following "DirtySnatcha
    Records" must not hide the DirtySnatcha artist account."""
    if not ref.startswith("name:"):
        return ref in followed.ids
    return bool(keys & followed.keys)


def account_decisions(
    dismissed: Iterable[str],
    label_overrides: Mapping[str, bool],
    aliases: Iterable[tuple[str, str | None]],
) -> tuple[frozenset[str], dict[str, bool]]:
    """Carry every 'name:<k>' decision to each account id that k resolves to.

    `aliases` is (name_key, soundcloud_user_id) pairs, e.g. the whole
    sc_name_resolutions table, so a decision still reaches the account after
    the alias stops showing up in current evidence. Dismissals stay keyed as
    stored and gain the ids. An override on the id itself beats any alias
    override; between aliases that disagree, the first by sort order wins.
    """
    ids_by_ref: dict[str, set[str]] = defaultdict(set)
    for key, sc_id in aliases:
        if sc_id:
            ids_by_ref[name_ref(key)].add(str(sc_id))
    dismissed = frozenset(dismissed)
    dismissed_ids = {i for ref in dismissed for i in ids_by_ref.get(ref, ())}
    from_aliases = {
        sc_id: label_overrides[ref]
        for ref in sorted(label_overrides, reverse=True)
        for sc_id in ids_by_ref.get(ref, ())
    }
    return dismissed | dismissed_ids, {**from_aliases, **label_overrides}


def label_override(refs: frozenset[str], ref: str, ctx: Context) -> bool | None:
    """The entity's own override, else one set on any name merged into it
    (first by sort order when names disagree), else None."""
    if ref in ctx.label_overrides:
        return ctx.label_overrides[ref]
    named = sorted(r for r in refs if r in ctx.label_overrides)
    return ctx.label_overrides[named[0]] if named else None


def explicit_credit(artist: str | None, title: str | None) -> str | None:
    """The artist an upload names: its artist field, else an 'X - Title' prefix.

    None when the upload names nobody, which is unknown, not someone else."""
    if artist and artist.strip():
        return artist
    match = _TITLE_CREDIT_RE.match(title or "")
    return match.group(1) if match else None


def _credits_someone_else(own: set[str], artist: str | None, title: str) -> bool:
    credit = explicit_credit(artist, title)
    if credit is None:
        return False
    text = name_key(f"{credit} {title}")
    return bool(text) and not any(o in text for o in own)


def credits_others(own_keys: set[str], uploads: list[tuple[str | None, str]]) -> bool:
    """Most of an account's uploads explicitly credit another artist (label).

    `uploads` is (artist field, full title) per upload. Only an explicit
    credit naming someone else counts; an upload with no artist field and no
    'X - Title' credit counts for nobody. The account's own key anywhere in
    the credit or title makes the upload its own (a remix of someone else's
    song is still the remixer's upload)."""
    own = {k for k in own_keys if len(k) >= 3}
    if not own or len(uploads) < LABEL_MIN_UPLOADS:
        return False
    others = sum(1 for a, t in uploads if _credits_someone_else(own, a, t))
    return others / len(uploads) >= LABEL_OTHER_SHARE


def is_label(
    ref: str, refs: frozenset[str], identity: "Identity", hits: list[Hit], ctx: Context
) -> bool:
    """Override (on the account or any name merged into it) wins; else a
    label-ish name; else uploads that credit others (liked uploads here, or
    the account's recent uploads in the activity cache)."""
    override = label_override(refs, ref, ctx)
    if override is not None:
        return override
    names = (identity.display_name, identity.permalink)
    if any(n and LABEL_NAME_RE.search(n) for n in names):
        return True
    uploads = [
        (h.track.artist, f"{h.track.title} {h.track.remix_artist or ''}")
        for h in hits
        if h.track.uploader_id == ref
    ]
    if credits_others(account_keys(*names), uploads):
        return True
    activity = ctx.activity.get(ref)
    return bool(activity and activity.is_label)


# ---------------------------------------------------------------------------
# Building suggestions
# ---------------------------------------------------------------------------


def evidence_counts(hits: list[Hit]) -> dict[str, int]:
    counts = Counter(h.role for h in hits)
    return {role: counts.get(role, 0) for role in ROLES}


def _time_key(value: str | None) -> float:
    parsed = parse_time(value)
    return parsed.timestamp() if parsed else float("-inf")


def suggestion_tracks(hits: list[Hit]) -> list[dict[str, Any]]:
    """Up to 20 credited tracks, newest like first (unknown dates last)."""
    ordered = sorted(hits, key=lambda h: _time_key(h.track.liked_at), reverse=True)
    return [
        {
            "soundcloud_id": h.track.soundcloud_id,
            "title": h.track.title,
            "artist": h.track.artist,
            "role": h.role,
            "liked_at": h.track.liked_at,
        }
        for h in ordered[:TRACKS_PER_SUGGESTION]
    ]


def _most_common(values: Iterable[str | None]) -> str | None:
    counted = Counter(v for v in values if v)
    return counted.most_common(1)[0][0] if counted else None


class Identity(NamedTuple):
    display_name: str
    permalink: str | None
    avatar_url: str | None
    followers: int | None


def entity_identity(
    ref: str, hits: list[Hit], ctx: Context, resolved_by_id: Mapping[str, Resolution]
) -> Identity:
    """Display name, permalink, avatar, followers from the best source we have."""
    activity = ctx.activity.get(ref)
    resolution = resolved_by_id.get(ref)
    uploads = [h.track for h in hits if h.track.uploader_id == ref]
    display = (
        (activity.username if activity else None)
        or _most_common(t.uploader_username for t in uploads)
        or (resolution.display_name if resolution else None)
        or _most_common(h.display for h in hits)
    )
    permalink = (
        (activity.permalink if activity else None)
        or _most_common(t.uploader_permalink for t in uploads)
        or (resolution.permalink if resolution else None)
    )
    display = display or permalink or ref
    return Identity(
        display,
        permalink,
        activity.avatar_url if activity else None,
        activity.followers if activity else None,
    )


def entity_keys(
    ref: str, hits: list[Hit], identity: Identity, refs: frozenset[str]
) -> set[str]:
    """Every name key an entity answers to (for follow/dismiss matching),
    including every name that resolved into it."""
    origin_names = {r[5:] for r in refs if r.startswith("name:")}
    if ref.startswith("name:"):
        return origin_names
    names = {name_key(h.display) for h in hits} | origin_names
    return (names | account_keys(identity.display_name, identity.permalink)) - {""}


def is_excluded(
    ref: str, hits: list[Hit], keys: set[str], ctx: Context, followed: Followed
) -> bool:
    """Followed, dismissed (by id or any of its name keys), or too thin a name."""
    if is_followed(ref, keys, followed):
        return True
    if ref in ctx.dismissed or any(name_ref(k) in ctx.dismissed for k in keys):
        return True
    return ref.startswith("name:") and len(hits) < NAME_ONLY_MIN_TRACKS


def evidence_score(hits: list[Hit], now: datetime) -> float:
    return sum(
        h.weight * recency_weight(h.track.liked_at, now, h.track.like_order)
        for h in hits
    )


def build_suggestion(
    ref: str, refs: frozenset[str], hits: list[Hit], identity: Identity, ctx: Context
) -> dict[str, Any]:
    """One Suggestion in the API contract shape."""
    activity = ctx.activity.get(ref)
    evidence = evidence_score(hits, ctx.now)
    score = (
        evidence * activity_factor(activity, ctx.now) * size_factor(identity.followers)
    )
    liked = [h.track.liked_at for h in hits if h.track.liked and h.track.liked_at]
    return {
        "key": ref,
        "soundcloud_user_id": None if ref.startswith("name:") else ref,
        **identity._asdict(),
        "is_label": is_label(ref, refs, identity, hits, ctx),
        "score": round(score, 4),
        "evidence_score": round(evidence, 4),
        "evidence": evidence_counts(hits),
        "last_liked_at": max(liked, key=_time_key) if liked else None,
        "activity": _activity_out(activity),
        "tracks": suggestion_tracks(hits),
    }


def _activity_out(activity: Activity | None) -> dict[str, Any] | None:
    if activity is None:
        return None
    return {
        "uploads_90d": activity.uploads_90d,
        "reposts_90d": activity.reposts_90d,
        "last_active_at": last_active_at(activity),
    }


def rank_entities(
    tracks: Iterable[EvidenceTrack], ctx: Context
) -> list[dict[str, Any]]:
    """Every surviving entity as a Suggestion, best score first."""
    hits_all = collect_hits(tracks)
    grouped = best_hits_by_entity(hits_all, ctx.resolutions)
    origins = entity_origins(hits_all, ctx.resolutions)
    resolved_by_id = {
        r.soundcloud_user_id: r
        for r in ctx.resolutions.values()
        if r.soundcloud_user_id
    }
    followed = followed_index(ctx.followed)
    out = []
    for ref, hits in grouped.items():
        identity = entity_identity(ref, hits, ctx, resolved_by_id)
        keys = entity_keys(ref, hits, identity, origins[ref])
        if not is_excluded(ref, hits, keys, ctx, followed):
            out.append(build_suggestion(ref, origins[ref], hits, identity, ctx))
    return sorted(out, key=lambda s: (-s["score"], s["display_name"].lower()))


def split_suggestions(
    ranked: list[dict[str, Any]], max_artists: int, max_labels: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    artists = [s for s in ranked if not s["is_label"]][:max_artists]
    labels = [s for s in ranked if s["is_label"]][:max_labels]
    return artists, labels

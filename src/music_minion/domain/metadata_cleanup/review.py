"""Local web page for sorting decisions, in two modes sharing one page.

gold:  gold tags vs model     -> gold-corrections.json (applied by `eval`)
apply: current tags vs run A vs run B -> apply-decisions-<year>.json (read by `apply`)

Every decision is saved immediately so closing the tab never loses work.
"""

import json
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from loguru import logger

from music_minion.domain.metadata_cleanup import evaluate, records
from music_minion.domain.metadata_cleanup.render import expected_view

CORRECTIONS_PATH = records.WORK_DIR / "gold-corrections.json"
PAGE_PATH = Path(__file__).parent / "review.html"
_DESCRIPTION_LIMIT = 1200


@dataclass(frozen=True)
class ReviewSession:
    """What the page shows and where its decisions are saved."""

    mode: str  # "gold" | "apply"
    title: str
    rows: list[dict[str, Any]]
    decisions_path: Path
    labels: dict[str, str]


def apply_decisions_path(year: str) -> Path:
    return records.WORK_DIR / f"apply-decisions-{year}.json"


def load_corrections(path: Path = CORRECTIONS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def save_corrections(
    corrections: dict[str, Any], path: Path = CORRECTIONS_PATH
) -> None:
    """Atomic write so a crash mid-save never corrupts earlier review work."""
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(corrections, indent=1, ensure_ascii=False))
    os.replace(temp, path)


def raw_view(record: dict[str, Any], source_url: str | None) -> dict[str, Any]:
    """SoundCloud data (or raw file tags when there is none) for the page header."""
    sc = dict(record.get("soundcloud") or {})
    tags = record.get("file_tags") or {}
    description = sc.get("description") or tags.get("comment") or ""
    return {
        **sc,
        "title": sc.get("title") or tags.get("title") or record["filename"],
        "uploader": sc.get("uploader") or tags.get("artist"),
        "description": description[:_DESCRIPTION_LIMIT],
        "filename": record["filename"],
        "url": source_url,
    }


def build_gold_rows(gold_rows: list[dict], proposals: dict[str, dict]) -> list[dict]:
    """One row per gold track with a proposal; 'left' = gold tags, 'a' = model."""
    rows = []
    for gold_row in gold_rows:
        proposal = proposals.get(gold_row["id"])
        if proposal is None:
            continue
        match = evaluate.compare(gold_row["expected"], proposal)
        tags = records.read_tags(records.MUSIC_ROOT / gold_row["id"])
        rows.append({
            "id": gold_row["id"],
            "raw": raw_view(gold_row, tags.get("source_url")),
            "left": gold_row["expected"],
            "a": expected_view(proposal),
            "diff": {"title": not match["title_ignore_case"],
                     "credited_artists": not match["artists"],
                     "remixers": not match["remixers"]},
            "auto": False,
            "confidence": proposal["confidence"],
            "notes": proposal["notes"],
        })  # fmt: skip
    return rows


def _audio_path(track_id: str) -> Path | None:
    """Resolve a track id to a file, refusing anything outside the library."""
    path = (records.MUSIC_ROOT / track_id).resolve()
    root = records.MUSIC_ROOT.resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


def _byte_range(header: str | None, size: int) -> tuple[int, int]:
    """Parse 'bytes=a-b' (either side optional) so the audio element can seek."""
    if not header or not header.startswith("bytes="):
        return 0, size - 1
    first, _, last = header[6:].split(",")[0].partition("-")
    if not first:
        return max(0, size - int(last)), size - 1
    end = min(int(last), size - 1) if last else size - 1
    return int(first), end


def make_handler(session: ReviewSession) -> type[BaseHTTPRequestHandler]:
    """Handler class bound to one session (http.server requires a class)."""

    class ReviewHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE_PATH.read_bytes())
            elif url.path == "/api/data":
                self._send_json({
                    "mode": session.mode,
                    "run": session.title,
                    "labels": session.labels,
                    "rows": session.rows,
                    "corrections": load_corrections(session.decisions_path),
                })  # fmt: skip
            elif url.path == "/audio":
                self._send_audio(parse_qs(url.query).get("id", [""])[0])
            else:
                self._send(404, "text/plain", b"not found")

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/corrections":
                self._send(404, "text/plain", b"not found")
                return
            length = int(self.headers.get("Content-Length", 0))
            save_corrections(
                json.loads(self.rfile.read(length)), session.decisions_path
            )
            self._send_json({"ok": True})

        def _send_audio(self, track_id: str) -> None:
            path = _audio_path(track_id)
            if path is None:
                self._send(404, "text/plain", b"no such track")
                return
            data = path.read_bytes()
            start, end = _byte_range(self.headers.get("Range"), len(data))
            if start == 0 and end == len(data) - 1:
                self._send(200, "audio/mpeg", data)
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            self.wfile.write(data[start : end + 1])

        def _send_json(self, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self._send(200, "application/json", body)

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            logger.debug(f"review http: {format % args}")

    return ReviewHandler


def serve(session: ReviewSession, port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(session))
    logger.info(f"Review ({session.mode}) for {session.title}: http://127.0.0.1:{port}")
    logger.info(f"Decisions save to {session.decisions_path}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

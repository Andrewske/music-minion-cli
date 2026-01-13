#!/usr/bin/liquidsoap

# Personal Radio - Liquidsoap Configuration
# Streams audio to Icecast, controlled by Python scheduler via HTTP

# =============================================================================
# Logging
# =============================================================================

log.stdout := true
log.file := false
log.level := 3

# =============================================================================
# Telnet Server for Control
# =============================================================================

settings.server.telnet := true
settings.server.telnet.port := 1234
settings.server.telnet.bind_addr := "0.0.0.0"

# =============================================================================
# Environment Configuration
# =============================================================================

# Helper to get environment variable with default
def getenv(name, default) =
  result = environment.get(name)
  if result == "" then default else result end
end

icecast_host = getenv("ICECAST_HOST", "icecast")
icecast_port = int_of_string(getenv("ICECAST_PORT", "8000"))
icecast_password = getenv("ICECAST_PASSWORD", "hackme")
icecast_mount = getenv("ICECAST_MOUNT", "/stream")
scheduler_url = getenv("SCHEDULER_URL", "http://host.docker.internal:8001/api/radio/next-track")

log("Configuration loaded:")
log("  Icecast: #{icecast_host}:#{icecast_port}#{icecast_mount}")
log("  Scheduler: #{scheduler_url}")

# =============================================================================
# Dynamic Source - Request tracks from Python scheduler
# =============================================================================

# Track request counter for logging
request_count = ref(0)

def get_next_track() =
  request_count := !request_count + 1
  count = !request_count

  log("Requesting track ##{count} from scheduler...")

  # Use Liquidsoap's native HTTP client (increased timeout for remote DB)
  response = http.get(scheduler_url, timeout=30.)

  if response.status_code == 200 then
    track_path = string.trim(response)
    if track_path != "" then
      log("Received track ##{count}: #{track_path}")
      request.create(track_path)
    else
      log("Empty response for request ##{count}, will retry...")
      null()
    end
  else
    log("HTTP error #{response.status_code} for request ##{count}, will retry...")
    null()
  end
end

# Create the dynamic source with retry handling
queue = request.dynamic(
  id="radio_queue",
  retry_delay=5.,
  get_next_track
)

# =============================================================================
# Fallback Source - Silence when no tracks available
# =============================================================================

# Generate silence as ultimate fallback
silence = blank(id="silence")

# Make the queue safe with fallback to silence
radio = fallback(
  id="radio_fallback",
  track_sensitive=false,
  [queue, silence]
)

# =============================================================================
# Audio Processing
# =============================================================================

# Apply ReplayGain normalization if metadata is available
radio = amplify(
  id="replaygain",
  override="replaygain_track_gain",
  1.0,
  radio
)

# Normalize audio levels (target -6 LUFS for louder output)
radio = normalize(
  id="normalize",
  target=-6.,
  radio
)

# Additional volume boost (2x = +6dB)
radio = amplify(id="volume_boost", 2.0, radio)

# Smart crossfade between tracks (3 second duration)
radio = crossfade(
  id="crossfade",
  duration=3.,
  fade_out=2.,
  fade_in=2.,
  radio
)

# Ensure the source is always available
radio = mksafe(radio)

# =============================================================================
# Metadata Logging & Now Playing Callback
# =============================================================================

# URL for reporting track start (same base as scheduler)
track_started_url = string.replace(pattern="/next-track", (fun (_) -> "/track-started"), scheduler_url)

def log_metadata(m) =
  title = list.assoc(default="Unknown", "title", m)
  artist = list.assoc(default="Unknown", "artist", m)
  filename = list.assoc(default="", "filename", m)

  log("Now playing: #{artist} - #{title}")

  # Notify backend that this track is actually playing now
  if filename != "" then
    log("Notifying backend: #{filename}")
    thread.run(fun () -> begin
      ignore(http.post(data=filename, track_started_url, timeout=5.))
    end)
  end
end

radio.on_metadata(log_metadata)

# =============================================================================
# Output to Icecast
# =============================================================================

output.icecast(
  id="icecast_output",
  %opus(
    bitrate=128,
    vbr="constrained",
    application="audio",
    complexity=10,
    signal="music"
  ),
  host=icecast_host,
  port=icecast_port,
  password=icecast_password,
  mount=icecast_mount,
  name="Personal Radio",
  description="24/7 Personal Radio Station",
  genre="Various",
  url="http://localhost:8000",
  public=false,
  radio
)

log("Radio stream initialized - waiting for scheduler...")

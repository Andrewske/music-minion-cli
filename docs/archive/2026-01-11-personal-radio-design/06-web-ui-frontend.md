# Web UI Frontend

## Files to Modify/Create
- `web/frontend/src/pages/Radio.tsx` (new - main radio UI)
- `web/frontend/src/pages/Video.tsx` (new - YouTube video page)
- `web/frontend/src/components/radio/NowPlaying.tsx` (new)
- `web/frontend/src/components/radio/ScheduleEditor.tsx` (new)
- `web/frontend/src/components/radio/StationSelector.tsx` (new)
- `web/frontend/src/hooks/useRadioWebSocket.ts` (new)

## Implementation Details

Build React components for the radio web UI, including now-playing display, schedule editor, and YouTube video page.

### Main Radio Page (`pages/Radio.tsx`)

```tsx
import React, { useState, useEffect } from 'react';
import { NowPlaying } from '../components/radio/NowPlaying';
import { ScheduleEditor } from '../components/radio/ScheduleEditor';
import { StationSelector } from '../components/radio/StationSelector';
import { useRadioWebSocket } from '../hooks/useRadioWebSocket';

export function Radio() {
  const [selectedStation, setSelectedStation] = useState<number | null>(null);
  const nowPlaying = useRadioWebSocket();

  return (
    <div className="radio-page">
      <header>
        <h1>Personal Radio</h1>
        <StationSelector
          selectedId={selectedStation}
          onSelect={setSelectedStation}
        />
      </header>

      <main className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Now Playing Widget */}
        <section className="col-span-full">
          <NowPlaying data={nowPlaying} />
        </section>

        {/* Upcoming Queue */}
        <section>
          <h2>Up Next</h2>
          <div className="upcoming-list">
            {nowPlaying?.upcoming?.map((track, idx) => (
              <div key={track.id} className="upcoming-item">
                <span className="position">{idx + 1}.</span>
                <span className="title">{track.title}</span>
                <span className="artist">{track.artist}</span>
                <span className="duration">{formatDuration(track.duration_ms)}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Schedule Editor */}
        <section>
          <h2>Schedule</h2>
          {selectedStation && <ScheduleEditor stationId={selectedStation} />}
        </section>
      </main>

      {/* Audio Player (hidden, streams from Icecast) */}
      <audio
        src="http://mm.kevinandrews.info/stream"
        autoPlay
        controls
        style={{ position: 'fixed', bottom: 20, right: 20 }}
      />
    </div>
  );
}

function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
```

### Now Playing Component (`components/radio/NowPlaying.tsx`)

```tsx
import React from 'react';

interface NowPlayingProps {
  data: {
    track_id: number;
    title: string;
    artist: string;
    position_ms: number;
    duration_ms: number;
  } | null;
}

export function NowPlaying({ data }: NowPlayingProps) {
  if (!data) {
    return <div className="now-playing loading">Loading...</div>;
  }

  const progress = (data.position_ms / data.duration_ms) * 100;

  return (
    <div className="now-playing">
      <div className="track-info">
        <div className="track-title">{data.title}</div>
        <div className="track-artist">{data.artist}</div>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>

      <div className="time-display">
        <span>{formatTime(data.position_ms)}</span>
        <span>{formatTime(data.duration_ms)}</span>
      </div>
    </div>
  );
}

function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
```

### Schedule Editor (`components/radio/ScheduleEditor.tsx`)

```tsx
import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';

interface TimeRange {
  id: number;
  start_time: string;
  end_time: string;
  target_station: number;
  position: number;
}

export function ScheduleEditor({ stationId }: { stationId: number }) {
  const [ranges, setRanges] = useState<TimeRange[]>([]);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    loadSchedule();
  }, [stationId]);

  async function loadSchedule() {
    const data = await api.get(`/api/radio/stations/${stationId}/schedule`);
    setRanges(data);
  }

  async function addRange(range: Omit<TimeRange, 'id'>) {
    await api.post('/api/radio/schedule', range);
    loadSchedule();
  }

  async function deleteRange(id: number) {
    await api.delete(`/api/radio/schedule/${id}`);
    loadSchedule();
  }

  return (
    <div className="schedule-editor">
      {ranges.map((range) => (
        <div key={range.id} className="schedule-row">
          <span className="time-range">
            {range.start_time} - {range.end_time}
          </span>
          <span className="target">→ Station {range.target_station}</span>
          <button onClick={() => deleteRange(range.id)}>Remove</button>
        </div>
      ))}

      <button onClick={() => setIsEditing(true)}>Add Time Range</button>

      {isEditing && (
        <TimeRangeForm
          onSubmit={(range) => {
            addRange(range);
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      )}
    </div>
  );
}

function TimeRangeForm({ onSubmit, onCancel }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [targetStation, setTargetStation] = useState(0);

  return (
    <div className="time-range-form">
      <input
        type="time"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        placeholder="Start time"
      />
      <input
        type="time"
        value={end}
        onChange={(e) => setEnd(e.target.value)}
        placeholder="End time"
      />
      <input
        type="number"
        value={targetStation}
        onChange={(e) => setTargetStation(Number(e.target.value))}
        placeholder="Target station ID"
      />
      <button onClick={() => onSubmit({ start_time: start, end_time: end, target_station: targetStation })}>
        Add
      </button>
      <button onClick={onCancel}>Cancel</button>
    </div>
  );
}
```

### WebSocket Hook (`hooks/useRadioWebSocket.ts`)

```typescript
import { useEffect, useState } from 'react';

interface NowPlayingData {
  track_id: number;
  title: string;
  artist: string;
  position_ms: number;
  duration_ms: number;
  upcoming: any[];
}

export function useRadioWebSocket(): NowPlayingData | null {
  const [data, setData] = useState<NowPlayingData | null>(null);

  useEffect(() => {
    const ws = new WebSocket('ws://mm.kevinandrews.info/api/radio/live');

    ws.onmessage = (event) => {
      const nowPlaying = JSON.parse(event.data);
      setData(nowPlaying);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket closed, reconnecting in 5s...');
      setTimeout(() => {
        // Reconnect logic (could use useEffect dependency)
      }, 5000);
    };

    return () => {
      ws.close();
    };
  }, []);

  return data;
}
```

### Video Page (`pages/Video.tsx`)

```tsx
import React, { useState, useEffect } from 'react';
import YouTube from 'react-youtube';

export function Video() {
  const [nowPlaying, setNowPlaying] = useState(null);
  const [youtubeId, setYoutubeId] = useState<string | null>(null);
  const [startSeconds, setStartSeconds] = useState(0);

  useEffect(() => {
    // Poll now-playing to sync video
    const interval = setInterval(async () => {
      const response = await fetch('/api/radio/now-playing');
      const data = await response.json();
      setNowPlaying(data);

      // Extract YouTube ID if current track is YouTube
      if (data.source_type === 'youtube') {
        const match = data.source_url.match(/v=([^&]+)/);
        if (match) {
          setYoutubeId(match[1]);
          setStartSeconds(Math.floor(data.position_ms / 1000));
        }
      } else {
        setYoutubeId(null);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  if (!youtubeId) {
    return (
      <div className="video-page">
        <div className="audio-only-card">
          <h2>Audio Only</h2>
          <p>Current track: {nowPlaying?.title}</p>
          <p>Up next: {nowPlaying?.upcoming[0]?.title}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="video-page">
      <YouTube
        videoId={youtubeId}
        opts={{
          width: '100%',
          height: '720',
          playerVars: {
            autoplay: 1,
            start: startSeconds,
          },
        }}
      />
      <div className="up-next">
        Up next: {nowPlaying?.upcoming[0]?.title || 'Unknown'}
      </div>
    </div>
  );
}
```

## Acceptance Criteria

- [ ] Main radio page displays now-playing with progress bar
- [ ] Upcoming queue shows next 5 tracks
- [ ] Schedule editor allows adding/removing time ranges
- [ ] Station selector dropdown switches active station
- [ ] WebSocket updates now-playing every 5 seconds
- [ ] Audio player auto-plays Icecast stream
- [ ] Video page embeds YouTube player when YouTube content is playing
- [ ] Video page shows "Audio Only" card for non-YouTube content
- [ ] All components styled with Tailwind CSS (or project's styling system)

## Dependencies

- Requires: **05-web-ui-backend-endpoints.md** (API endpoints must exist)
- Requires: `react-youtube` package for YouTube embed

## Testing

```bash
# Install dependencies
cd web/frontend
npm install react-youtube

# Run development server
npm run dev

# Visit http://localhost:5173/radio
```

## Notes

- WebSocket reconnection logic should implement exponential backoff
- Video page load gap (~3s) is already built into schedule, so transitions feel natural
- Consider adding history page at `/radio/history` for playback history browsing

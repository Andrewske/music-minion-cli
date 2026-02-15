import { useState, useEffect, Fragment } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import type { SortingState } from '@tanstack/react-table';
import { useBuilderSession } from '../../hooks/useBuilderSession';
import { useIPCWebSocket } from '../../hooks/useIPCWebSocket';
import { builderApi } from '../../api/builder';
import type { Track, Filter } from '../../api/builder';
import { useWavesurfer } from '../../hooks/useWavesurfer';
import { usePlaylists } from '../../hooks/usePlaylists';
import { useTrackEmojis } from '../../hooks/useTrackEmojis';
import { EmojiPicker } from '../EmojiPicker';

// Obsidian Minimal Playlist Builder
// Pure black (#000) background, single amber accent, hairline borders, extreme reduction

export function ObsidianMinimalBuilder() {
  const { data: playlists } = usePlaylists();
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | null>(null);

  if (!selectedPlaylistId) {
    return (
      <div className="min-h-screen bg-black font-inter">
        <div className="max-w-lg mx-auto pt-32 px-6">
          <h1 className="text-sm font-medium text-obsidian-accent tracking-[0.2em] uppercase mb-12">
            Select Playlist
          </h1>

          <div className="space-y-px">
            {playlists?.filter(p => p.type === 'manual').map((playlist) => (
              <button
                key={playlist.id}
                onClick={() => setSelectedPlaylistId(playlist.id)}
                className="w-full group text-left"
              >
                <div className="flex items-center justify-between py-4 border-b border-obsidian-border
                  hover:border-obsidian-accent/50 transition-colors">
                  <span className="text-white/90 group-hover:text-obsidian-accent transition-colors">
                    {playlist.name}
                  </span>
                  <span className="text-white/20 text-sm font-sf-mono">
                    {playlist.track_count}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const playlist = playlists?.find(p => p.id === selectedPlaylistId);

  return (
    <ObsidianBuilderMain
      playlistId={selectedPlaylistId}
      playlistName={playlist?.name ?? 'Unknown'}
      onBack={() => setSelectedPlaylistId(null)}
    />
  );
}

interface BuilderMainProps {
  playlistId: number;
  playlistName: string;
  onBack: () => void;
}

export function ObsidianBuilderMain({ playlistId, playlistName, onBack }: BuilderMainProps) {
  const [queueTrackId, setQueueTrackId] = useState<number | null>(null);
  const [nowPlayingTrack, setNowPlayingTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [loopEnabled, setLoopEnabled] = useState(true);
  const [sorting, setSorting] = useState<SortingState>([{ id: 'artist', desc: false }]);

  const sortField = sorting[0]?.id ?? 'artist';
  const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';

  const {
    session, addTrack, skipTrack, filters, updateFilters, startSession, isAddingTrack, isSkippingTrack,
  } = useBuilderSession(playlistId);

  const PAGE_SIZE = 100;

  const { data: candidatesData, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['builder-candidates', playlistId, sortField, sortDirection],
    queryFn: ({ pageParam = 0 }) =>
      builderApi.getCandidates(playlistId, PAGE_SIZE, pageParam, sortField, sortDirection),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.hasMore ? allPages.length * PAGE_SIZE : undefined,
    enabled: !!playlistId && !!session,
  });

  const candidates = candidatesData?.pages.flatMap(p => p.candidates) ?? [];
  const queueIndex = queueTrackId ? candidates.findIndex(t => t.id === queueTrackId) : 0;

  useEffect(() => {
    if (candidates.length > 0 && (queueTrackId === null || queueIndex === -1)) {
      setQueueTrackId(candidates[0].id);
    }
  }, [candidates, queueTrackId, queueIndex]);

  const currentTrack = nowPlayingTrack ?? candidates[queueIndex] ?? null;

  useEffect(() => {
    if (playlistId) {
      builderApi.activateBuilderMode(playlistId);
      return () => { builderApi.deactivateBuilderMode(); };
    }
  }, [playlistId]);

  useEffect(() => {
    if (session && candidates.length > 0) {
      setQueueTrackId(candidates[0].id);
      setNowPlayingTrack(null);
    }
  }, [session, sortField, sortDirection]);

  useIPCWebSocket({
    onBuilderAdd: () => { if (currentTrack && !isAddingTrack && !isSkippingTrack) handleAdd(); },
    onBuilderSkip: () => { if (currentTrack && !isAddingTrack && !isSkippingTrack) handleSkip(); }
  });

  useEffect(() => { if (currentTrack) setIsPlaying(true); }, [currentTrack]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key >= '0' && e.key <= '9') {
        window.dispatchEvent(new CustomEvent('music-minion-seek-percent', { detail: parseInt(e.key) * 10 }));
      }
      if (e.key === ' ') { e.preventDefault(); setIsPlaying(prev => !prev); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleAdd = async () => {
    const trackToAdd = nowPlayingTrack ?? candidates[queueIndex];
    if (!trackToAdd || isAddingTrack || isSkippingTrack) return;
    await addTrack.mutateAsync(trackToAdd.id);
    const nextIndex = queueIndex + 1;
    if (nextIndex < candidates.length) setQueueTrackId(candidates[nextIndex].id);
    setNowPlayingTrack(null);
  };

  const handleSkip = async () => {
    const trackToSkip = nowPlayingTrack ?? candidates[queueIndex];
    if (!trackToSkip || isAddingTrack || isSkippingTrack) return;
    await skipTrack.mutateAsync(trackToSkip.id);
    const nextIndex = queueIndex + 1;
    if (nextIndex < candidates.length) setQueueTrackId(candidates[nextIndex].id);
    setNowPlayingTrack(null);
  };

  if (!session) {
    return (
      <div className="min-h-screen bg-black font-inter flex items-center justify-center">
        <div className="text-center">
          <p className="text-white/40 text-sm mb-8 font-sf-mono">{playlistName}</p>
          <button
            onClick={() => startSession.mutate(playlistId)}
            className="px-8 py-3 text-obsidian-accent border border-obsidian-accent/30
              hover:bg-obsidian-accent/10 transition-colors text-sm tracking-wider"
          >
            Begin
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black font-inter text-white">
      {/* Minimal Header */}
      <header className="border-b border-obsidian-border px-8 py-4">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <button onClick={onBack} className="text-white/40 hover:text-obsidian-accent transition-colors text-sm">
            ← Back
          </button>
          <span className="text-white/60 text-sm font-sf-mono">{playlistName}</span>
          <div className="w-12" />
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="grid grid-cols-12 gap-12">
          {/* Filters - Minimal sidebar */}
          <aside className="col-span-3">
            <ObsidianFilterPanel
              filters={filters || []}
              onUpdate={(f) => updateFilters.mutate(f)}
              isUpdating={updateFilters.isPending}
              playlistId={playlistId}
            />
          </aside>

          {/* Main */}
          <main className="col-span-9">
            {currentTrack && queueIndex < candidates.length ? (
              <div className="space-y-12">
                {/* Track Display - Ultra minimal */}
                <div className="py-8">
                  <p className="text-obsidian-accent text-sm font-sf-mono mb-2">{currentTrack.artist}</p>
                  <h2 className="text-4xl font-light text-white mb-4">{currentTrack.title}</h2>
                  {currentTrack.album && (
                    <p className="text-white/30 text-sm">{currentTrack.album}</p>
                  )}

                  {/* Metadata pills */}
                  <div className="flex gap-4 mt-6">
                    {currentTrack.bpm && (
                      <span className="text-white/40 text-xs font-sf-mono">{Math.round(currentTrack.bpm)} BPM</span>
                    )}
                    {currentTrack.key_signature && (
                      <span className="text-white/40 text-xs font-sf-mono">{currentTrack.key_signature}</span>
                    )}
                    {currentTrack.genre && (
                      <span className="text-white/40 text-xs font-sf-mono">{currentTrack.genre}</span>
                    )}
                    {currentTrack.year && (
                      <span className="text-white/40 text-xs font-sf-mono">{currentTrack.year}</span>
                    )}

                    {/* Emoji tagging */}
                    <ObsidianEmojiActions
                      track={currentTrack}
                      onUpdate={(updated) => {
                        // Always copy to nowPlayingTrack to ensure local state owns the track
                        // This prevents emoji updates from disappearing when currentTrack
                        // would otherwise pull from candidates[] on next render
                        setNowPlayingTrack(updated);
                      }}
                    />
                  </div>
                </div>

                {/* Waveform */}
                <div className="h-16 border-t border-b border-obsidian-border">
                  <ObsidianWaveform
                    track={currentTrack}
                    isPlaying={isPlaying}
                    onTogglePlayPause={() => setIsPlaying(!isPlaying)}
                    onFinish={() => {
                      if (loopEnabled) { setIsPlaying(false); setTimeout(() => setIsPlaying(true), 100); }
                      else { handleSkip(); }
                    }}
                  />
                </div>

                {/* Loop toggle */}
                <div className="flex justify-center">
                  <label className="flex items-center gap-3 text-white/30 text-sm cursor-pointer hover:text-white/50 transition-colors">
                    <input
                      type="checkbox"
                      checked={loopEnabled}
                      onChange={(e) => setLoopEnabled(e.target.checked)}
                      className="w-3 h-3 accent-obsidian-accent"
                    />
                    Loop
                  </label>
                </div>

                {/* Actions */}
                <div className="flex gap-4 justify-center">
                  <button
                    onClick={handleAdd}
                    disabled={isAddingTrack || isSkippingTrack}
                    className="px-12 py-3 border border-obsidian-accent text-obsidian-accent
                      hover:bg-obsidian-accent hover:text-black disabled:opacity-30
                      transition-all text-sm tracking-wider"
                  >
                    {isAddingTrack ? '...' : 'Add'}
                  </button>
                  <button
                    onClick={handleSkip}
                    disabled={isAddingTrack || isSkippingTrack}
                    className="px-12 py-3 border border-white/20 text-white/60
                      hover:border-white/40 hover:text-white disabled:opacity-30
                      transition-all text-sm tracking-wider"
                  >
                    {isSkippingTrack ? '...' : 'Skip'}
                  </button>
                </div>

                {/* Track Queue */}
                <ObsidianTrackQueue
                  tracks={candidates}
                  queueIndex={queueIndex}
                  nowPlayingId={nowPlayingTrack?.id ?? null}
                  onTrackClick={(t) => { if (t.id !== nowPlayingTrack?.id) setNowPlayingTrack(t); }}
                  sorting={sorting}
                  onSortingChange={setSorting}
                  onLoadMore={() => fetchNextPage()}
                  hasMore={hasNextPage ?? false}
                  isLoadingMore={isFetchingNextPage}
                />
              </div>
            ) : (
              <div className="py-20 text-center">
                <p className="text-white/40 text-sm">
                  {queueIndex >= candidates.length ? 'No more tracks' : 'Loading...'}
                </p>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

// Waveform
function ObsidianWaveform({ track, isPlaying, onTogglePlayPause, onFinish }: {
  track: Track; isPlaying: boolean; onTogglePlayPause: () => void; onFinish: () => void;
}) {
  const { containerRef, currentTime, duration, togglePlayPause } = useWavesurfer({
    trackId: track.id, isPlaying, onFinish,
  });

  const formatTime = (time: number) => {
    const m = Math.floor(time / 60);
    const s = Math.floor(time % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex items-center w-full h-full gap-4">
      <button
        onClick={onTogglePlayPause || togglePlayPause}
        className="w-8 h-8 flex items-center justify-center text-obsidian-accent
          hover:text-white transition-colors"
      >
        {isPlaying ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
          </svg>
        )}
      </button>
      <div className="flex-1 h-full relative">
        <div ref={containerRef} className="w-full h-full" />
      </div>
      <span className="text-white/30 text-xs font-sf-mono w-20 text-right">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>
    </div>
  );
}

// Filter Panel
function ObsidianFilterPanel({ filters, onUpdate, isUpdating, playlistId }: {
  filters: Filter[]; onUpdate: (f: Filter[]) => void; isUpdating: boolean; playlistId: number;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingFilter, setEditingFilter] = useState<Filter | undefined>(undefined);

  const startAdding = () => { setIsEditing(true); setEditingIndex(null); setEditingFilter(undefined); };
  const startEditing = (idx: number) => { setIsEditing(true); setEditingIndex(idx); setEditingFilter(filters[idx]); };
  const handleCancel = () => { setIsEditing(false); setEditingIndex(null); setEditingFilter(undefined); };

  const handleSave = (filter: Filter) => {
    const updated = editingIndex !== null
      ? filters.map((f, i) => i === editingIndex ? filter : f)
      : [...filters, filter];
    onUpdate(updated);
    handleCancel();
  };

  const handleDelete = (idx: number) => onUpdate(filters.filter((_, i) => i !== idx));
  const toggleConjunction = (idx: number) => {
    onUpdate(filters.map((f, i) => i === idx ? { ...f, conjunction: f.conjunction === 'AND' ? 'OR' as const : 'AND' as const } : f));
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <span className="text-obsidian-accent text-xs tracking-[0.2em] uppercase">Filters</span>
        {filters.length > 0 && (
          <button onClick={() => confirm('Clear?') && onUpdate([])} className="text-white/30 hover:text-white/60 text-xs">
            Clear
          </button>
        )}
      </div>

      <div className="space-y-2 mb-6">
        {filters.map((filter, idx) => (
          <Fragment key={`${filter.field}-${idx}`}>
            {idx > 0 && (
              <button onClick={() => toggleConjunction(idx)} disabled={isUpdating}
                className="w-full py-1 text-white/20 hover:text-white/40 text-xs transition-colors">
                {filter.conjunction}
              </button>
            )}
            <div className="group py-2 border-b border-obsidian-border hover:border-obsidian-accent/30 transition-colors">
              <div className="flex justify-between text-sm">
                <span className="text-white/60">
                  <span className="text-white/30">{filter.field}</span>
                  <span className="text-white/20 mx-2">{filter.operator}</span>
                  <span className="text-white">{filter.value}</span>
                </span>
                <div className="flex gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => startEditing(idx)} className="text-white/40 hover:text-obsidian-accent text-xs">Edit</button>
                  <button onClick={() => handleDelete(idx)} className="text-white/40 hover:text-red-400 text-xs">×</button>
                </div>
              </div>
            </div>
          </Fragment>
        ))}
      </div>

      {isEditing ? (
        <ObsidianFilterEditor initialFilter={editingFilter} playlistId={playlistId} onSave={handleSave} onCancel={handleCancel} />
      ) : (
        <button onClick={startAdding} disabled={isUpdating}
          className="w-full py-2 border border-dashed border-obsidian-border hover:border-obsidian-accent/50
            text-white/30 hover:text-obsidian-accent transition-colors text-xs">
          + Add
        </button>
      )}
    </div>
  );
}

// Filter Editor
function ObsidianFilterEditor({ initialFilter, playlistId, onSave, onCancel }: {
  initialFilter?: Filter; playlistId: number; onSave: (f: Filter) => void; onCancel: () => void;
}) {
  const [field, setField] = useState(initialFilter?.field || '');
  const [operator, setOperator] = useState(initialFilter?.operator || '');
  const [value, setValue] = useState(initialFilter?.value || '');

  const { data: candidates } = useQuery({
    queryKey: ['builder-candidates', playlistId],
    queryFn: () => builderApi.getCandidates(playlistId, 1000),
    staleTime: 5 * 60 * 1000,
  });

  const genres = candidates?.candidates ? [...new Set(candidates.candidates.map(t => t.genre).filter(Boolean))].sort() : [];
  const isNumeric = ['year', 'bpm'].includes(field);

  const inputClass = "w-full bg-black border border-obsidian-border px-3 py-2 text-white text-sm \
    focus:border-obsidian-accent/50 focus:outline-none transition-colors";

  const handleSave = () => {
    if (field && operator && value) {
      onSave({ field, operator, value, conjunction: initialFilter?.conjunction || 'AND' });
    }
  };

  return (
    <div className="space-y-4 py-4 border-t border-obsidian-border">
      <select value={field} onChange={(e) => { setField(e.target.value); setOperator(''); }} className={inputClass}>
        <option value="">Field</option>
        <option value="title">Title</option>
        <option value="artist">Artist</option>
        <option value="album">Album</option>
        <option value="genre">Genre</option>
        <option value="year">Year</option>
        <option value="bpm">BPM</option>
        <option value="key">Key</option>
      </select>

      {field && !isNumeric && (
        <select value={operator} onChange={(e) => setOperator(e.target.value)} className={inputClass}>
          <option value="">Condition</option>
          <option value="contains">contains</option>
          <option value="equals">equals</option>
          <option value="not_equals">≠</option>
          <option value="starts_with">starts with</option>
          <option value="ends_with">ends with</option>
        </select>
      )}

      {field && isNumeric && (
        <select value={operator} onChange={(e) => setOperator(e.target.value)} className={inputClass}>
          <option value="">Condition</option>
          <option value="equals">=</option>
          <option value="not_equals">≠</option>
          <option value="gt">&gt;</option>
          <option value="gte">≥</option>
          <option value="lt">&lt;</option>
          <option value="lte">≤</option>
        </select>
      )}

      {field === 'genre' && operator === 'equals' ? (
        <select value={value} onChange={(e) => setValue(e.target.value)} className={inputClass}>
          <option value="">Genre</option>
          {genres.map(g => <option key={g} value={g ?? ''}>{g}</option>)}
        </select>
      ) : field && operator && (
        <input type={isNumeric ? 'number' : 'text'} value={value} onChange={(e) => setValue(e.target.value)}
          placeholder="Value" className={inputClass} />
      )}

      <div className="flex gap-2">
        <button onClick={handleSave} disabled={!field || !operator || !value}
          className="flex-1 py-2 border border-obsidian-accent text-obsidian-accent text-xs
            hover:bg-obsidian-accent hover:text-black disabled:opacity-30 transition-all">
          {initialFilter ? 'Update' : 'Add'}
        </button>
        <button onClick={onCancel}
          className="flex-1 py-2 border border-obsidian-border text-white/40 text-xs hover:text-white transition-colors">
          Cancel
        </button>
      </div>
    </div>
  );
}

// Track Queue
export function ObsidianTrackQueue({ tracks, queueIndex, nowPlayingId, onTrackClick, sorting, onSortingChange, onLoadMore, hasMore, isLoadingMore }: {
  tracks: Track[]; queueIndex: number; nowPlayingId: number | null; onTrackClick: (t: Track) => void;
  sorting: SortingState; onSortingChange: (s: SortingState) => void;
  onLoadMore: () => void; hasMore: boolean; isLoadingMore: boolean;
}) {
  const cols = [
    { id: 'title', label: 'Title', flex: 3 },
    { id: 'artist', label: 'Artist', flex: 2 },
    { id: 'bpm', label: 'BPM', flex: 1 },
    { id: 'genre', label: 'Genre', flex: 1 },
    { id: 'year', label: 'Year', flex: 1 },
  ];

  const handleSort = (id: string) => {
    const current = sorting[0];
    onSortingChange([{ id, desc: current?.id === id ? !current.desc : false }]);
  };

  return (
    <div className="border-t border-obsidian-border">
      {/* Header */}
      <div className="flex border-b border-obsidian-border">
        {cols.map(col => (
          <button key={col.id} onClick={() => handleSort(col.id)}
            style={{ flex: col.flex }}
            className={`px-3 py-2 text-left text-xs tracking-wider uppercase transition-colors
              ${sorting[0]?.id === col.id ? 'text-obsidian-accent' : 'text-white/30 hover:text-white/60'}`}>
            {col.label}
            {sorting[0]?.id === col.id && <span className="ml-1">{sorting[0].desc ? '↓' : '↑'}</span>}
          </button>
        ))}
      </div>

      {/* Rows */}
      <div className="max-h-[35vh] overflow-y-auto">
        {tracks.map((track, idx) => {
          const isQueue = idx === queueIndex;
          const isPlaying = track.id === nowPlayingId;

          return (
            <button key={track.id} onClick={() => onTrackClick(track)}
              className={`w-full flex text-left text-sm border-b border-obsidian-border/50
                hover:bg-white/5 transition-colors
                ${isPlaying ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent' : ''}
                ${isQueue && !isPlaying ? 'bg-white/5' : ''}`}>
              <div style={{ flex: 3 }} className="px-3 py-2 truncate text-white">{track.title}</div>
              <div style={{ flex: 2 }} className="px-3 py-2 truncate text-white/50">{track.artist}</div>
              <div style={{ flex: 1 }} className="px-3 py-2 text-white/30 font-sf-mono text-xs">{track.bpm ? Math.round(track.bpm) : '-'}</div>
              <div style={{ flex: 1 }} className="px-3 py-2 truncate text-white/30">{track.genre || '-'}</div>
              <div style={{ flex: 1 }} className="px-3 py-2 text-white/30 font-sf-mono text-xs">{track.year || '-'}</div>
            </button>
          );
        })}
      </div>

      {hasMore && (
        <button onClick={onLoadMore} disabled={isLoadingMore}
          className="w-full py-2 text-white/30 hover:text-obsidian-accent text-xs transition-colors">
          {isLoadingMore ? '...' : 'More'}
        </button>
      )}
    </div>
  );
}

// Obsidian Emoji Actions
interface ObsidianEmojiActionsProps {
  track: Track;
  onUpdate: (updatedTrack: Track) => void;
}

function ObsidianEmojiActions({ track, onUpdate }: ObsidianEmojiActionsProps) {
  const [showPicker, setShowPicker] = useState(false);
  const { addEmoji, removeEmoji, isAdding, isRemoving } = useTrackEmojis(track, onUpdate);

  return (
    <div className="flex items-center gap-2">
      {track.emojis?.map((emoji, index) => (
        <button
          key={`${emoji}-${index}`}
          onClick={() => removeEmoji(emoji)}
          disabled={isRemoving}
          className="relative group text-base leading-none hover:opacity-70 disabled:opacity-30 transition-opacity"
          title="Click to remove"
        >
          <span className="block">{emoji}</span>
          <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="text-obsidian-accent text-xs font-bold">×</span>
          </span>
        </button>
      ))}
      <button
        onClick={() => setShowPicker(true)}
        disabled={isAdding}
        className="text-xs font-sf-mono text-white/40 hover:text-obsidian-accent
          disabled:opacity-30 transition-colors cursor-pointer"
      >
        {isAdding ? '...' : '+ Emoji'}
      </button>
      {showPicker && (
        <EmojiPicker
          onSelect={async (emoji: string) => {
            await addEmoji(emoji);
            setShowPicker(false);
          }}
          onClose={() => setShowPicker(false)}
        />
      )}
    </div>
  );
}

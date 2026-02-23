/**
 * SoundCloud Import Wizard.
 * Multi-step wizard for importing SoundCloud playlists by matching tracks to local library.
 *
 * Steps:
 * 1. select - Choose a SoundCloud playlist
 * 2. matching - Loading state while matching tracks
 * 3. review - Review low-confidence matches (< 0.85)
 * 4. confirm - Summary and playlist name input
 * 5. done - Success message with link to new playlist
 */

import { useReducer, useEffect, useState } from 'react';
import { Link } from '@tanstack/react-router';
import {
  getSoundCloudPlaylists,
  matchPlaylist,
  createPlaylistFromMatches,
  type SoundCloudPlaylist,
  type ScPlaylistMatch,
} from '../../api/soundcloud';
import { TrackSearchAutocomplete } from './TrackSearchAutocomplete';

// State types

type ImportStep = 'select' | 'matching' | 'review' | 'confirm' | 'done' | 'error';

interface ImportState {
  step: ImportStep;
  playlists: SoundCloudPlaylist[];
  selectedPlaylistId: string | null;
  playlistName: string;
  matches: ScPlaylistMatch[];
  createdPlaylistId: number | null;
  error: string | null;
}

type ImportAction =
  | { type: 'SET_PLAYLISTS'; playlists: SoundCloudPlaylist[] }
  | { type: 'SELECT_PLAYLIST'; id: string }
  | { type: 'START_MATCHING' }
  | { type: 'MATCHING_COMPLETE'; matches: ScPlaylistMatch[]; playlistName: string }
  | {
      type: 'FIX_MATCH';
      scTrackId: string;
      localTrackId: number;
      localTitle: string;
      localArtist: string;
    }
  | { type: 'MARK_MISSING'; scTrackId: string }
  | { type: 'UNDO_MISSING'; scTrackId: string }
  | { type: 'UPDATE_PLAYLIST_NAME'; name: string }
  | { type: 'PROCEED_TO_CONFIRM' }
  | { type: 'CREATE_SUCCESS'; playlistId: number }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'RESET' };

const initialState: ImportState = {
  step: 'select',
  playlists: [],
  selectedPlaylistId: null,
  playlistName: '',
  matches: [],
  createdPlaylistId: null,
  error: null,
};

function importReducer(state: ImportState, action: ImportAction): ImportState {
  switch (action.type) {
    case 'SET_PLAYLISTS':
      return { ...state, playlists: action.playlists };

    case 'SELECT_PLAYLIST':
      return { ...state, selectedPlaylistId: action.id };

    case 'START_MATCHING':
      return { ...state, step: 'matching', error: null };

    case 'MATCHING_COMPLETE':
      return {
        ...state,
        step: 'review',
        matches: action.matches,
        playlistName: action.playlistName,
      };

    case 'FIX_MATCH':
      return {
        ...state,
        matches: state.matches.map((m) =>
          m.sc_track_id === action.scTrackId
            ? {
                ...m,
                local_track_id: action.localTrackId,
                local_title: action.localTitle,
                local_artist: action.localArtist,
                is_approved: true,
                is_missing: false,
                isFixed: true,
              }
            : m
        ),
      };

    case 'MARK_MISSING':
      return {
        ...state,
        matches: state.matches.map((m) =>
          m.sc_track_id === action.scTrackId ? { ...m, is_missing: true, isFixed: false } : m
        ),
      };

    case 'UNDO_MISSING':
      return {
        ...state,
        matches: state.matches.map((m) =>
          m.sc_track_id === action.scTrackId ? { ...m, is_missing: false } : m
        ),
      };

    case 'UPDATE_PLAYLIST_NAME':
      return { ...state, playlistName: action.name };

    case 'PROCEED_TO_CONFIRM':
      return { ...state, step: 'confirm' };

    case 'CREATE_SUCCESS':
      return { ...state, step: 'done', createdPlaylistId: action.playlistId };

    case 'SET_ERROR':
      return { ...state, step: 'error', error: action.error };

    case 'RESET':
      return { ...initialState, playlists: state.playlists };

    default:
      return state;
  }
}

// Helper functions

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.85) return 'bg-green-500/20 text-green-400';
  if (confidence >= 0.7) return 'bg-yellow-500/20 text-yellow-400';
  return 'bg-red-500/20 text-red-400';
}

function getConfidenceBgColor(confidence: number): string {
  if (confidence >= 0.7) return 'bg-yellow-500/20';
  return 'bg-red-500/20';
}

// Subcomponents

interface SelectStepProps {
  playlists: SoundCloudPlaylist[];
  selectedPlaylistId: string | null;
  isLoading: boolean;
  onSelect: (id: string) => void;
  onStartImport: () => void;
}

function SelectStep({
  playlists,
  selectedPlaylistId,
  isLoading,
  onSelect,
  onStartImport,
}: SelectStepProps): JSX.Element {
  return (
    <div className="space-y-4">
      <p className="text-white/60">
        Select a SoundCloud playlist to import. Tracks will be matched to your local library.
      </p>

      {/* Playlist dropdown */}
      <div>
        <label htmlFor="playlist-select" className="block text-sm font-medium text-slate-300 mb-2">
          SoundCloud Playlist
        </label>
        <select
          id="playlist-select"
          value={selectedPlaylistId || ''}
          onChange={(e) => onSelect(e.target.value)}
          disabled={isLoading || playlists.length === 0}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value="">Select a playlist...</option>
          {playlists.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.track_count} tracks)
            </option>
          ))}
        </select>
      </div>

      {/* Start Import button */}
      <button
        type="button"
        onClick={onStartImport}
        disabled={!selectedPlaylistId || isLoading}
        className="w-full px-6 py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
      >
        Start Import
      </button>

      {playlists.length === 0 && !isLoading && (
        <p className="text-yellow-400 text-sm">
          No playlists found. Make sure you are authenticated with SoundCloud.
        </p>
      )}
    </div>
  );
}

function MatchingStep(): JSX.Element {
  return (
    <div className="flex flex-col items-center justify-center py-12 space-y-4">
      <svg
        className="animate-spin h-10 w-10 text-orange-500"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
      <p className="text-white text-lg">Matching tracks to your local library...</p>
      <p className="text-slate-400 text-sm">This may take a moment for large playlists.</p>
    </div>
  );
}

interface ReviewStepProps {
  matches: ScPlaylistMatch[];
  onFixMatch: (
    scTrackId: string,
    localTrackId: number,
    localTitle: string,
    localArtist: string
  ) => void;
  onMarkMissing: (scTrackId: string) => void;
  onUndoMissing: (scTrackId: string) => void;
  onContinue: () => void;
}

function ReviewStep({
  matches,
  onFixMatch,
  onMarkMissing,
  onUndoMissing,
  onContinue,
}: ReviewStepProps): JSX.Element {
  const [fixingTrackId, setFixingTrackId] = useState<string | null>(null);

  // Count stats
  const autoApproved = matches.filter((m) => m.is_approved && !m.isFixed && !m.is_missing).length;
  const manuallyFixed = matches.filter((m) => m.isFixed).length;
  const markedMissing = matches.filter((m) => m.is_missing).length;
  const needsReview = matches.filter(
    (m) => !m.is_approved && !m.is_missing && !m.isFixed
  );

  // Filter to show only matches that need review (< 0.85 confidence and not auto-approved)
  const reviewableMatches = matches.filter((m) => !m.is_approved || m.is_missing || m.isFixed);

  const handleSelectTrack = (
    scTrackId: string,
    track: { id: number; title: string; artist: string }
  ): void => {
    onFixMatch(scTrackId, track.id, track.title, track.artist);
    setFixingTrackId(null);
  };

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <div className="flex flex-wrap gap-4 p-4 bg-slate-800 border border-slate-700 rounded-lg">
        <div className="text-sm">
          <span className="text-green-400 font-medium">{autoApproved}</span>
          <span className="text-slate-400"> auto-approved</span>
        </div>
        <div className="text-sm">
          <span className="text-yellow-400 font-medium">{needsReview.length}</span>
          <span className="text-slate-400"> need review</span>
        </div>
        {manuallyFixed > 0 && (
          <div className="text-sm">
            <span className="text-blue-400 font-medium">{manuallyFixed}</span>
            <span className="text-slate-400"> manually fixed</span>
          </div>
        )}
        {markedMissing > 0 && (
          <div className="text-sm">
            <span className="text-slate-500 font-medium">{markedMissing}</span>
            <span className="text-slate-400"> missing</span>
          </div>
        )}
      </div>

      {/* Review table */}
      {reviewableMatches.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="pb-2 pr-4">SoundCloud Track</th>
                <th className="pb-2 pr-4">Local Match</th>
                <th className="pb-2 pr-4">Confidence</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reviewableMatches.map((match) => (
                <tr
                  key={match.sc_track_id}
                  className={`border-b border-slate-700/50 ${
                    match.is_missing
                      ? 'bg-slate-800/50 opacity-60'
                      : match.isFixed
                      ? 'bg-blue-500/10'
                      : getConfidenceBgColor(match.confidence)
                  }`}
                >
                  {/* SC Track */}
                  <td className={`py-3 pr-4 ${match.is_missing ? 'line-through' : ''}`}>
                    <div className="font-medium text-white truncate max-w-[200px]">
                      {match.sc_title}
                    </div>
                    <div className="text-xs text-slate-400 truncate max-w-[200px]">
                      {match.sc_artist}
                    </div>
                  </td>

                  {/* Local Match */}
                  <td className="py-3 pr-4">
                    {fixingTrackId === match.sc_track_id ? (
                      <TrackSearchAutocomplete
                        onSelect={(track) => handleSelectTrack(match.sc_track_id, track)}
                        onCancel={() => setFixingTrackId(null)}
                        initialQuery={`${match.sc_artist} ${match.sc_title}`}
                      />
                    ) : match.local_track_id ? (
                      <div>
                        <div className="text-white truncate max-w-[200px]">
                          {match.local_title}
                        </div>
                        <div className="text-xs text-slate-400 truncate max-w-[200px]">
                          {match.local_artist}
                        </div>
                      </div>
                    ) : (
                      <span className="text-slate-500 italic">No match</span>
                    )}
                  </td>

                  {/* Confidence */}
                  <td className="py-3 pr-4">
                    {!match.is_missing && (
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${getConfidenceColor(
                          match.confidence
                        )}`}
                      >
                        {Math.round(match.confidence * 100)}%
                      </span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="py-3">
                    {!match.is_missing ? (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setFixingTrackId(match.sc_track_id)}
                          className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded transition-colors"
                        >
                          Fix
                        </button>
                        <button
                          type="button"
                          onClick={() => onMarkMissing(match.sc_track_id)}
                          className="px-2 py-1 bg-slate-700 hover:bg-red-600 text-white text-xs rounded transition-colors"
                        >
                          Missing
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onUndoMissing(match.sc_track_id)}
                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-white text-xs rounded transition-colors"
                      >
                        Undo
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {reviewableMatches.length === 0 && (
        <div className="p-4 bg-green-900/20 border border-green-500/20 rounded-lg text-green-400">
          All tracks have been auto-approved with high confidence matches.
        </div>
      )}

      {/* Continue button - always enabled */}
      <button
        type="button"
        onClick={onContinue}
        className="w-full px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-lg transition-colors"
      >
        Continue
      </button>
    </div>
  );
}

interface ConfirmStepProps {
  matches: ScPlaylistMatch[];
  playlistName: string;
  isCreating: boolean;
  onNameChange: (name: string) => void;
  onCreatePlaylist: () => void;
  onBack: () => void;
}

function ConfirmStep({
  matches,
  playlistName,
  isCreating,
  onNameChange,
  onCreatePlaylist,
  onBack,
}: ConfirmStepProps): JSX.Element {
  // Calculate summary stats
  const matched = matches.filter((m) => m.local_track_id !== null && !m.is_missing).length;
  const missing = matches.filter((m) => m.is_missing).length;
  const manuallyFixed = matches.filter((m) => m.isFixed).length;
  const unreviewed = matches.filter(
    (m) => !m.is_approved && !m.is_missing && !m.isFixed && m.local_track_id !== null
  ).length;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="p-4 bg-slate-800 border border-slate-700 rounded-lg space-y-2">
        <h3 className="text-lg font-semibold text-white">Summary</h3>
        <div className="text-sm text-slate-300 space-y-1">
          <div>
            <span className="text-green-400">{matched}</span> tracks will be added
          </div>
          {missing > 0 && (
            <div>
              <span className="text-slate-500">{missing}</span> tracks marked as missing
            </div>
          )}
          {manuallyFixed > 0 && (
            <div>
              <span className="text-blue-400">{manuallyFixed}</span> manually fixed
            </div>
          )}
        </div>
      </div>

      {/* Warning for unreviewed matches */}
      {unreviewed > 0 && (
        <div className="p-4 bg-yellow-900/20 border border-yellow-500/20 rounded-lg text-yellow-400 text-sm">
          {unreviewed} low-confidence matches will be included as-is.
        </div>
      )}

      {/* Playlist name input */}
      <div>
        <label htmlFor="playlist-name" className="block text-sm font-medium text-slate-300 mb-2">
          Playlist Name
        </label>
        <input
          id="playlist-name"
          type="text"
          value={playlistName}
          onChange={(e) => onNameChange(e.target.value)}
          disabled={isCreating}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:opacity-50"
        />
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={isCreating}
          className="px-6 py-3 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onCreatePlaylist}
          disabled={!playlistName.trim() || matched === 0 || isCreating}
          className="flex-1 px-6 py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {isCreating ? (
            <>
              <svg
                className="animate-spin h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <span>Creating Playlist...</span>
            </>
          ) : (
            'Create Playlist'
          )}
        </button>
      </div>
    </div>
  );
}

interface DoneStepProps {
  playlistId: number;
  playlistName: string;
  trackCount: number;
  onImportAnother: () => void;
}

function DoneStep({
  playlistId,
  playlistName,
  trackCount,
  onImportAnother,
}: DoneStepProps): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="p-6 bg-green-900/20 border border-green-500/20 rounded-lg text-center">
        <div className="text-green-400 text-lg font-semibold mb-2">Playlist Created!</div>
        <p className="text-slate-300">
          <span className="font-medium text-white">{playlistName}</span> with {trackCount} tracks
        </p>
        <Link
          to="/playlist-builder/$playlistId"
          params={{ playlistId: String(playlistId) }}
          className="inline-block mt-4 px-6 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors"
        >
          View Playlist
        </Link>
      </div>

      <button
        type="button"
        onClick={onImportAnother}
        className="w-full px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg transition-colors"
      >
        Import Another Playlist
      </button>
    </div>
  );
}

interface ErrorStepProps {
  error: string;
  onRetry: () => void;
}

function ErrorStep({ error, onRetry }: ErrorStepProps): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="p-4 bg-red-900/20 border border-red-500/20 rounded-lg">
        <div className="text-red-400 font-medium mb-1">Import Failed</div>
        <div className="text-sm text-slate-300">{error}</div>
      </div>

      <button
        type="button"
        onClick={onRetry}
        className="w-full px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-lg transition-colors"
      >
        Try Again
      </button>
    </div>
  );
}

// Main component

export function SoundCloudImportSection(): JSX.Element {
  const [state, dispatch] = useReducer(importReducer, initialState);
  const [isLoadingPlaylists, setIsLoadingPlaylists] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // Fetch playlists on mount
  useEffect(() => {
    const fetchPlaylists = async (): Promise<void> => {
      setIsLoadingPlaylists(true);
      try {
        const playlists = await getSoundCloudPlaylists();
        dispatch({ type: 'SET_PLAYLISTS', playlists });
      } catch (err) {
        if (err instanceof Error && err.message.includes('401')) {
          dispatch({
            type: 'SET_ERROR',
            error: 'SoundCloud not authenticated. Please authenticate first.',
          });
        } else {
          dispatch({
            type: 'SET_ERROR',
            error: err instanceof Error ? err.message : 'Failed to fetch playlists',
          });
        }
      } finally {
        setIsLoadingPlaylists(false);
      }
    };

    fetchPlaylists();
  }, []);

  const handleStartMatching = async (): Promise<void> => {
    if (!state.selectedPlaylistId) return;

    dispatch({ type: 'START_MATCHING' });

    try {
      const result = await matchPlaylist(state.selectedPlaylistId);
      dispatch({
        type: 'MATCHING_COMPLETE',
        matches: result.matches,
        playlistName: result.playlist_name,
      });
    } catch (err) {
      dispatch({
        type: 'SET_ERROR',
        error: err instanceof Error ? err.message : 'Failed to match playlist',
      });
    }
  };

  const handleCreatePlaylist = async (): Promise<void> => {
    if (!state.selectedPlaylistId) return;

    setIsCreating(true);

    try {
      const result = await createPlaylistFromMatches({
        playlist_name: state.playlistName,
        sc_playlist_id: state.selectedPlaylistId,
        matches: state.matches,
      });
      dispatch({ type: 'CREATE_SUCCESS', playlistId: result.playlist_id });
    } catch (err) {
      dispatch({
        type: 'SET_ERROR',
        error: err instanceof Error ? err.message : 'Failed to create playlist',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const matchedCount = state.matches.filter(
    (m) => m.local_track_id !== null && !m.is_missing
  ).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-white">Import from SoundCloud</h2>
        <p className="text-white/60 text-sm mt-1">
          Match your SoundCloud playlists to local tracks and create local playlists.
        </p>
      </div>

      {/* Step indicator */}
      {state.step !== 'error' && (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span className={state.step === 'select' ? 'text-orange-500 font-medium' : ''}>
            Select
          </span>
          <span>{'>'}</span>
          <span className={state.step === 'matching' ? 'text-orange-500 font-medium' : ''}>
            Match
          </span>
          <span>{'>'}</span>
          <span className={state.step === 'review' ? 'text-orange-500 font-medium' : ''}>
            Review
          </span>
          <span>{'>'}</span>
          <span className={state.step === 'confirm' ? 'text-orange-500 font-medium' : ''}>
            Confirm
          </span>
          <span>{'>'}</span>
          <span className={state.step === 'done' ? 'text-orange-500 font-medium' : ''}>Done</span>
        </div>
      )}

      {/* Step content */}
      <div className="bg-obsidian-surface border border-obsidian-border p-6 rounded-lg">
        {state.step === 'select' && (
          <SelectStep
            playlists={state.playlists}
            selectedPlaylistId={state.selectedPlaylistId}
            isLoading={isLoadingPlaylists}
            onSelect={(id) => dispatch({ type: 'SELECT_PLAYLIST', id })}
            onStartImport={handleStartMatching}
          />
        )}

        {state.step === 'matching' && <MatchingStep />}

        {state.step === 'review' && (
          <ReviewStep
            matches={state.matches}
            onFixMatch={(scTrackId, localTrackId, localTitle, localArtist) =>
              dispatch({ type: 'FIX_MATCH', scTrackId, localTrackId, localTitle, localArtist })
            }
            onMarkMissing={(scTrackId) => dispatch({ type: 'MARK_MISSING', scTrackId })}
            onUndoMissing={(scTrackId) => dispatch({ type: 'UNDO_MISSING', scTrackId })}
            onContinue={() => dispatch({ type: 'PROCEED_TO_CONFIRM' })}
          />
        )}

        {state.step === 'confirm' && (
          <ConfirmStep
            matches={state.matches}
            playlistName={state.playlistName}
            isCreating={isCreating}
            onNameChange={(name) => dispatch({ type: 'UPDATE_PLAYLIST_NAME', name })}
            onCreatePlaylist={handleCreatePlaylist}
            onBack={() => dispatch({ type: 'MATCHING_COMPLETE', matches: state.matches, playlistName: state.playlistName })}
          />
        )}

        {state.step === 'done' && state.createdPlaylistId && (
          <DoneStep
            playlistId={state.createdPlaylistId}
            playlistName={state.playlistName}
            trackCount={matchedCount}
            onImportAnother={() => dispatch({ type: 'RESET' })}
          />
        )}

        {state.step === 'error' && state.error && (
          <ErrorStep error={state.error} onRetry={() => dispatch({ type: 'RESET' })} />
        )}
      </div>
    </div>
  );
}

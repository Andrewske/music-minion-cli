// Re-export from shared package
export {
  getFollowSuggestions, dismissSuggestion, setSuggestionLabel, getUntieredFollows,
  followAccount, getFollowConnections,
} from '@music-minion/shared';
export type {
  SuggestionEvidence, SuggestionActivity, SuggestionRole, SuggestionTrack, Suggestion,
  FollowSuggestionsResponse, UntieredArtist, UntieredResponse, ConnectionVia,
  FollowConnection, FollowConnectionsResponse, OkResponse, FollowAccountResponse,
} from '@music-minion/shared';

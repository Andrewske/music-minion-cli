// Re-export from shared package
export {
  getFollowSuggestions, dismissSuggestion, setSuggestionLabel, getUntieredFollows,
  followAccount, getFollowConnections, linkSuggestion,
} from '@music-minion/shared';
export type {
  SuggestionEvidence, SuggestionActivity, SuggestionRole, SuggestionTrack, Suggestion,
  FollowSuggestionsResponse, UntieredArtist, UntieredResponse, ConnectionVia,
  FollowConnection, FollowConnectionsResponse, OkResponse, FollowAccountResponse,
  LinkSuggestionResponse, FollowingCount,
} from '@music-minion/shared';

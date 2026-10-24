/**
 * PlaylistPicker — the playlist list shared by Compare and Organize.
 *
 *   [search ............ x]
 *   [Recent | A–Z | Size]      24 playlists
 *   {header}                   (e.g. Organize's Resume card)
 *   rows: name / screen-specific subtitle            >
 *
 * Each screen passes its own pre-filtered playlists, row subtitle and
 * onSelect; search and sort are local to the picker (features/playlists).
 */
import { useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import { View, Text, TextInput, Pressable, FlatList, ActivityIndicator, StyleSheet } from 'react-native';
import { ChevronRight, Search, X } from 'lucide-react-native';
import {
  PLAYLIST_SORTS,
  emptyMessage,
  selectPickerPlaylists,
} from '../features/playlists/playlistPicker';
import type { PickerPlaylist, PlaylistSort } from '../features/playlists/playlistPicker';

const ACCENT = '#7C4DFF';
const MUTED = '#9E9E9E';

export interface PlaylistPickerProps {
  /** Already narrowed to what this screen can open. */
  playlists: readonly PickerPlaylist[];
  isLoading: boolean;
  error: Error | null;
  searchPlaceholder: string;
  subtitle: (playlist: PickerPlaylist) => string;
  onSelect: (playlist: PickerPlaylist) => void;
  /** Row showing a spinner while its selection is in flight; all rows disable. */
  busyId: number | null;
  emptyText: string;
  /** testID for the first row (Maestro taps it). */
  optionTestID: string;
  /** Rendered between the sort row and the list. */
  header?: ReactNode;
}

export function PlaylistPicker(props: PlaylistPickerProps): ReactElement {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<PlaylistSort>('recent');
  const visible = useMemo(
    () => selectPickerPlaylists(props.playlists, query, sort),
    [props.playlists, query, sort],
  );

  if (props.isLoading || props.error) return <PickerStatus error={props.error} />;
  return (
    <View style={styles.root}>
      <SearchField value={query} onChange={setQuery} placeholder={props.searchPlaceholder} />
      <SortToggle value={sort} onChange={setSort} count={visible.length} />
      {props.header}
      <PlaylistList {...props} items={visible} emptyText={emptyMessage(query, props.emptyText)} />
    </View>
  );
}

interface PlaylistListProps extends PlaylistPickerProps {
  items: PickerPlaylist[];
}

function PlaylistList({ items, emptyText, optionTestID, busyId, subtitle, onSelect }: PlaylistListProps): ReactElement {
  return (
    <FlatList
      data={items}
      keyExtractor={(item) => item.id.toString()}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      contentContainerStyle={styles.listContent}
      renderItem={({ item, index }) => (
        <PlaylistRow
          testID={index === 0 ? optionTestID : undefined}
          name={item.name}
          subtitle={subtitle(item)}
          busy={busyId === item.id}
          disabled={busyId !== null}
          onPress={() => onSelect(item)}
        />
      )}
      ListEmptyComponent={<Text style={styles.empty}>{emptyText}</Text>}
    />
  );
}

function SearchField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }): ReactElement {
  return (
    <View style={styles.search}>
      <Search size={18} color={MUTED} />
      <TextInput
        testID="playlist-search"
        style={styles.searchInput}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor="#666"
        autoCorrect={false}
        returnKeyType="search"
      />
      {value ? (
        <Pressable testID="playlist-search-clear" accessibilityRole="button" accessibilityLabel="Clear search" hitSlop={8} style={styles.clear} onPress={() => onChange('')}>
          <X size={18} color={MUTED} />
        </Pressable>
      ) : null}
    </View>
  );
}

function SortToggle({ value, onChange, count }: { value: PlaylistSort; onChange: (s: PlaylistSort) => void; count: number }): ReactElement {
  return (
    <View style={styles.sortRow}>
      <View style={styles.segments} accessibilityRole="radiogroup">
        {PLAYLIST_SORTS.map(({ key, label }) => (
          <Pressable
            key={key}
            testID={`playlist-sort-${key}`}
            accessibilityRole="radio"
            accessibilityState={{ selected: value === key }}
            style={[styles.segment, value === key && styles.segmentActive]}
            onPress={() => onChange(key)}
          >
            <Text style={[styles.segmentText, value === key && styles.segmentTextActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.count}>{count === 1 ? '1 playlist' : `${count} playlists`}</Text>
    </View>
  );
}

interface PlaylistRowProps {
  testID?: string;
  name: string;
  subtitle: string;
  busy: boolean;
  disabled: boolean;
  onPress: () => void;
}

function PlaylistRow({ testID, name, subtitle, busy, disabled, onPress }: PlaylistRowProps): ReactElement {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={`${name}, ${subtitle}`}
      android_ripple={{ color: '#FFFFFF14' }}
      // Static style: NativeWind's Pressable wrapper drops function styles.
      style={styles.row}
      onPress={onPress}
      disabled={disabled}
    >
      <View style={styles.rowText}>
        <Text style={styles.rowName} numberOfLines={1}>{name}</Text>
        <Text style={styles.rowSubtitle} numberOfLines={1}>{subtitle}</Text>
      </View>
      {busy ? <ActivityIndicator size="small" color={ACCENT} /> : <ChevronRight size={20} color="#555" />}
    </Pressable>
  );
}

function PickerStatus({ error }: { error: Error | null }): ReactElement {
  if (!error) {
    return (
      <View style={styles.status}>
        <ActivityIndicator size="large" color={ACCENT} />
      </View>
    );
  }
  return (
    <View style={styles.status}>
      <Text style={styles.errorTitle}>Can&apos;t reach the server</Text>
      <Text style={styles.errorBody}>{error.message}</Text>
      <Text style={styles.errorBody}>Check that Tailscale is running.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    height: 48,
    marginHorizontal: 16,
    paddingLeft: 14,
    paddingRight: 6,
    borderRadius: 12,
    backgroundColor: '#1E1E1E',
  },
  searchInput: { flex: 1, color: '#E0E0E0', fontSize: 16, paddingVertical: 0 },
  clear: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  sortRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: 16,
    marginTop: 10,
    marginBottom: 8,
  },
  segments: { flexDirection: 'row', padding: 3, borderRadius: 10, backgroundColor: '#1A1A1A' },
  segment: { minHeight: 36, paddingHorizontal: 14, borderRadius: 8, justifyContent: 'center' },
  segmentActive: { backgroundColor: '#2D2440' },
  segmentText: { color: MUTED, fontSize: 13, fontWeight: '500' },
  segmentTextActive: { color: '#C9B8FF' },
  count: { color: '#666', fontSize: 12 },
  listContent: { paddingHorizontal: 16, paddingBottom: 32 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 64,
    paddingLeft: 16,
    paddingRight: 12,
    marginBottom: 6,
    borderRadius: 12,
    backgroundColor: '#1E1E1E',
    overflow: 'hidden',
  },
  rowText: { flex: 1, marginRight: 12 },
  rowName: { color: '#E0E0E0', fontSize: 16, fontWeight: '500' },
  rowSubtitle: { color: MUTED, fontSize: 12, marginTop: 3 },
  empty: { color: MUTED, textAlign: 'center', marginTop: 32, lineHeight: 20 },
  status: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24, gap: 6 },
  errorTitle: { color: '#CF6679', fontSize: 18, marginBottom: 4 },
  errorBody: { color: MUTED, textAlign: 'center' },
});

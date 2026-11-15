/**
 * Session switcher — bottom sheet opened from the organizer header.
 *
 *   ───
 *   Sessions
 *   [✓ Dubstep split ✎        4 buckets · 88 sorted  🗑]   ← loaded; tap to rename
 *   [  Session · Oct 20       3 buckets · 41 sorted  🗑]   ← tap to switch
 *   [  Vibes  done            2 buckets · 12 sorted  🗑]
 *   [+ New session]
 *
 * Delete asks for confirmation (it strips bucket emojis from tracks).
 * The list is only fetched while the sheet is open.
 */
import { useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Check, Pencil, Plus, Trash2 } from 'lucide-react-native';
import type { BucketSession, SessionSummary } from '@music-minion/shared';
import { useOrganizerSessionList } from '../../hooks/useOrganizerSessions';
import {
  isDoneStatus,
  renameValue,
  sessionCountsText,
  sessionLabel,
  splitSessions,
} from '../../features/organizer/sessionSwitcher';

interface SessionSwitcherSheetProps {
  visible: boolean;
  playlistId: number;
  session: BucketSession;
  isBusy: boolean;
  onClose: () => void;
  onNew: () => void;
  onSwitch: (sessionId: string) => void;
  onRename: (sessionId: string, name: string | null) => void;
  onDelete: (sessionId: string) => void;
}

export function SessionSwitcherSheet(props: SessionSwitcherSheetProps): ReactElement {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={props.visible} transparent animationType="slide" onRequestClose={props.onClose} statusBarTranslucent>
      <Pressable testID="session-sheet-backdrop" style={styles.backdrop} onPress={props.onClose} accessibilityLabel="Close sessions" />
      <View testID="session-sheet" style={[styles.sheet, { paddingBottom: 16 + insets.bottom }]}>
        <View style={styles.grabber} />
        <Text style={styles.heading}>Sessions</Text>
        {props.visible ? <SheetBody {...props} /> : null}
      </View>
    </Modal>
  );
}

function SheetBody(props: SessionSwitcherSheetProps): ReactElement {
  const { sessions, isLoading } = useOrganizerSessionList(props.playlistId, props.visible);
  const { current, others } = splitSessions(sessions, props.session.id);
  return (
    <>
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent} keyboardShouldPersistTaps="handled">
        <CurrentRow session={props.session} summary={current} disabled={props.isBusy} onRename={props.onRename} onDelete={props.onDelete} />
        {isLoading ? <ActivityIndicator style={styles.loading} color="#7C4DFF" /> : null}
        {others.map((s, index) => (
          <OtherRow key={s.id} index={index} summary={s} disabled={props.isBusy} onSwitch={props.onSwitch} onDelete={props.onDelete} />
        ))}
      </ScrollView>
      <NewSessionButton busy={props.isBusy} onPress={props.onNew} />
    </>
  );
}

/** Native confirm before discarding a session. */
function confirmDelete(label: string, onConfirm: () => void): void {
  Alert.alert(`Delete ${label}?`, 'Its buckets are dropped and bucket emojis are removed from tracks.', [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: onConfirm },
  ]);
}

interface CurrentRowProps {
  session: BucketSession;
  summary: SessionSummary | undefined;
  disabled: boolean;
  onRename: (sessionId: string, name: string | null) => void;
  onDelete: (sessionId: string) => void;
}

interface RenameDraft {
  draft: string | null;
  setDraft: (value: string) => void;
  start: () => void;
  save: () => void;
}

/** Inline rename state. Submit and the blur that follows it both call save; only the first counts. */
function useRenameDraft(session: BucketSession, onRename: (sessionId: string, name: string | null) => void): RenameDraft {
  const [draft, setDraft] = useState<string | null>(null);
  const savedRef = useRef(false);
  const start = (): void => {
    savedRef.current = false;
    setDraft(session.name ?? '');
  };
  const save = (): void => {
    if (draft === null || savedRef.current) return;
    savedRef.current = true;
    const change = renameValue(draft, session.name);
    if (change) onRename(session.id, change.name);
    setDraft(null);
  };
  return { draft, setDraft, start, save };
}

function CurrentRow({ session, summary, disabled, onRename, onDelete }: CurrentRowProps): ReactElement {
  const { draft, setDraft, start: startRename, save } = useRenameDraft(session, onRename);
  const label = sessionLabel(session);
  if (draft !== null) return <RenameRow draft={draft} placeholder={sessionLabel({ name: null, created_at: session.created_at })} onChange={setDraft} onSave={save} />;
  return (
    <View style={[styles.row, styles.rowCurrent]}>
      <Pressable testID="session-current" accessibilityRole="button" accessibilityLabel={`Rename ${label}`} disabled={disabled}
        android_ripple={{ color: '#7C4DFF40' }} style={styles.rowMain} onPress={startRename}>
        <Check size={18} color="#7C4DFF" />
        <RowText label={label} done={false} counts={summary ? sessionCountsText(summary) : null} />
        <Pencil size={14} color="#9E9E9E" />
      </Pressable>
      <TrashButton testID="session-delete-current" label={label} disabled={disabled} onConfirm={() => onDelete(session.id)} />
    </View>
  );
}

interface RenameRowProps {
  draft: string;
  placeholder: string;
  onChange: (value: string) => void;
  onSave: () => void;
}

function RenameRow({ draft, placeholder, onChange, onSave }: RenameRowProps): ReactElement {
  return (
    <View style={[styles.row, styles.rowCurrent, styles.renameRow]}>
      <TextInput testID="session-rename-input" accessibilityLabel="Session name" autoFocus value={draft}
        placeholder={placeholder} placeholderTextColor="#666" returnKeyType="done" selectTextOnFocus
        style={styles.renameInput} onChangeText={onChange} onSubmitEditing={onSave} onBlur={onSave} />
      <Pressable testID="session-rename-save" accessibilityRole="button" accessibilityLabel="Save name"
        android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 20 }} style={styles.iconButton} onPress={onSave}>
        <Check size={20} color="#7C4DFF" />
      </Pressable>
    </View>
  );
}

interface OtherRowProps {
  index: number;
  summary: SessionSummary;
  disabled: boolean;
  onSwitch: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
}

function OtherRow({ index, summary, disabled, onSwitch, onDelete }: OtherRowProps): ReactElement {
  const label = sessionLabel(summary);
  return (
    <View style={styles.row}>
      <Pressable testID={`session-option-${index}`} accessibilityRole="button" accessibilityLabel={`Open ${label}`} disabled={disabled}
        android_ripple={{ color: '#7C4DFF40' }} style={[styles.rowMain, styles.rowIndent]} onPress={() => onSwitch(summary.id)}>
        <RowText label={label} done={isDoneStatus(summary.status)} counts={sessionCountsText(summary)} />
      </Pressable>
      <TrashButton testID={`session-delete-${index}`} label={label} disabled={disabled} onConfirm={() => onDelete(summary.id)} />
    </View>
  );
}

function RowText({ label, done, counts }: { label: string; done: boolean; counts: string | null }): ReactElement {
  return (
    <View style={styles.rowText}>
      <Text style={styles.rowName} numberOfLines={1}>
        {label}
        {done ? <Text style={styles.done}>  done</Text> : null}
      </Text>
      {counts ? <Text style={styles.rowCounts}>{counts}</Text> : null}
    </View>
  );
}

interface TrashButtonProps {
  testID: string;
  label: string;
  disabled: boolean;
  onConfirm: () => void;
}

function TrashButton({ testID, label, disabled, onConfirm }: TrashButtonProps): ReactElement {
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={`Delete ${label}`} disabled={disabled}
      android_ripple={{ color: '#EF444440', borderless: true, radius: 22 }} style={styles.iconButton}
      onPress={() => confirmDelete(label, onConfirm)}>
      <Trash2 size={18} color="#9E9E9E" />
    </Pressable>
  );
}

function NewSessionButton({ busy, onPress }: { busy: boolean; onPress: () => void }): ReactElement {
  return (
    <Pressable testID="session-new-btn" accessibilityRole="button" accessibilityLabel="New session" disabled={busy}
      android_ripple={{ color: '#FFFFFF26' }} style={[styles.newButton, busy && styles.disabled]} onPress={onPress}>
      {busy ? <ActivityIndicator color="#FFFFFF" size="small" /> : <Plus size={20} color="#FFFFFF" />}
      <Text style={styles.newText}>New session</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheet: {
    backgroundColor: '#1E1E1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 8,
    maxHeight: '80%',
  },
  grabber: { alignSelf: 'center', width: 40, height: 4, borderRadius: 2, backgroundColor: '#444', marginBottom: 12 },
  heading: { color: '#E0E0E0', fontSize: 18, fontWeight: '700', marginBottom: 12 },
  list: { flexGrow: 0 },
  listContent: { gap: 8 },
  loading: { paddingVertical: 12 },
  row: { flexDirection: 'row', alignItems: 'center', minHeight: 60, borderRadius: 12, backgroundColor: '#2A2A2A', overflow: 'hidden' },
  rowCurrent: { borderWidth: 1, borderColor: '#7C4DFF80' },
  rowMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 60, paddingLeft: 14, paddingRight: 8 },
  rowIndent: { paddingLeft: 42 },
  rowText: { flex: 1 },
  rowName: { color: '#E0E0E0', fontSize: 16, fontWeight: '600' },
  done: { color: '#9E9E9E', fontSize: 12, fontWeight: '400' },
  rowCounts: { color: '#9E9E9E', fontSize: 12, marginTop: 2 },
  renameRow: { paddingLeft: 14 },
  renameInput: { flex: 1, color: '#E0E0E0', fontSize: 16, paddingVertical: 8 },
  iconButton: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
  newButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    minHeight: 52,
    marginTop: 12,
    borderRadius: 12,
    backgroundColor: '#7C4DFF',
    overflow: 'hidden',
  },
  newText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
  disabled: { opacity: 0.5 },
});

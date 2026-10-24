/**
 * One row of Feed filters under the header: `Source: All ▾` and `Rank: All ▾`
 * open option sheets; `In library` toggles in place.
 */
import { useState, type ReactElement } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Check, ChevronDown } from 'lucide-react-native';
import type { FeedRankPreset, FeedSource } from '@music-minion/shared';
import {
  RANK_OPTIONS,
  rankChipLabel,
  rankFromKey,
  rankKey,
  SOURCE_OPTIONS,
  sourceChipLabel,
  sourceFromKey,
  type FilterOption,
} from '../../features/feed/feedFormat';

const ACCENT = '#7C4DFF';

type OpenSheet = 'source' | 'rank' | null;

export interface FeedFilterRowProps {
  source: FeedSource;
  maxRank: FeedRankPreset | undefined;
  inLibrary: boolean;
  onSource: (source: FeedSource) => void;
  onMaxRank: (maxRank: FeedRankPreset | undefined) => void;
  onToggleInLibrary: () => void;
}

export function FeedFilterRow(props: FeedFilterRowProps): ReactElement {
  const [open, setOpen] = useState<OpenSheet>(null);
  return (
    <View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row} accessibilityLabel="Feed filters">
        <Chip label={sourceChipLabel(props.source)} active={props.source !== 'all'} dropdown onPress={() => setOpen('source')} testID="feed-source-chip" />
        <Chip label={rankChipLabel(props.maxRank)} active={props.maxRank !== undefined} dropdown onPress={() => setOpen('rank')} testID="feed-rank-chip" />
        <Chip label="In library" active={props.inLibrary} onPress={props.onToggleInLibrary} testID="feed-filter-library" />
      </ScrollView>
      <FilterSheets {...props} open={open} onClose={() => setOpen(null)} />
    </View>
  );
}

function FilterSheets(props: FeedFilterRowProps & { open: OpenSheet; onClose: () => void }): ReactElement {
  const { open, onClose } = props;
  return (
    <>
      <OptionSheet title="Source" visible={open === 'source'} options={SOURCE_OPTIONS} selectedKey={props.source} onClose={onClose}
        onPick={(key) => { props.onSource(sourceFromKey(key)); onClose(); }} />
      <OptionSheet title="Artist rank" visible={open === 'rank'} options={RANK_OPTIONS} selectedKey={rankKey(props.maxRank)} onClose={onClose}
        onPick={(key) => { props.onMaxRank(rankFromKey(key)); onClose(); }} />
    </>
  );
}

interface ChipProps {
  label: string;
  active: boolean;
  dropdown?: boolean;
  onPress: () => void;
  testID: string;
}

function Chip({ label, active, dropdown = false, onPress, testID }: ChipProps): ReactElement {
  const fg = active ? '#CBB8FF' : '#BDBDBD';
  return (
    <Pressable
      onPress={onPress}
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={dropdown ? `${label}; change` : `Show only tracks ${label.toLowerCase()}`}
      accessibilityState={dropdown ? undefined : { selected: active }}
      android_ripple={{ color: '#FFFFFF1F' }}
      style={[styles.chip, active && styles.chipActive]}
    >
      <Text style={[styles.chipText, { color: fg }]} numberOfLines={1}>{label}</Text>
      {dropdown ? <ChevronDown size={16} color={fg} strokeWidth={2} /> : null}
    </Pressable>
  );
}

interface OptionSheetProps {
  title: string;
  visible: boolean;
  options: readonly FilterOption[];
  selectedKey: string;
  onPick: (key: string) => void;
  onClose: () => void;
}

function OptionSheet({ title, visible, options, selectedKey, onPick, onClose }: OptionSheetProps): ReactElement {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close" testID="feed-filter-backdrop" />
      <View style={[styles.sheet, { paddingBottom: 12 + insets.bottom }]}>
        <View style={styles.grabber} />
        <Text style={styles.sheetTitle} accessibilityRole="header">{title}</Text>
        <ScrollView style={styles.list}>
          {options.map((option) => (
            <OptionRow key={option.key} option={option} selected={option.key === selectedKey} onPick={onPick} />
          ))}
        </ScrollView>
      </View>
    </Modal>
  );
}

function OptionRow({ option, selected, onPick }: { option: FilterOption; selected: boolean; onPick: (key: string) => void }): ReactElement {
  return (
    <Pressable
      onPress={() => onPick(option.key)}
      testID={option.testID}
      accessibilityRole="radio"
      accessibilityState={{ checked: selected }}
      android_ripple={{ color: '#FFFFFF14' }}
      style={styles.option}
    >
      <Text style={[styles.optionText, selected && styles.optionTextSelected]}>{option.label}</Text>
      {selected ? <Check size={20} color={ACCENT} strokeWidth={2.5} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8, paddingHorizontal: 12, paddingBottom: 10 },
  chip: {
    minHeight: 36,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingLeft: 12,
    paddingRight: 10,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#333333',
    overflow: 'hidden',
  },
  chipActive: { borderColor: '#7C4DFF99', backgroundColor: '#7C4DFF26' },
  chipText: { fontSize: 13, fontWeight: '500' },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheet: {
    backgroundColor: '#1E1E1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingTop: 8,
    maxHeight: '70%',
  },
  grabber: { alignSelf: 'center', width: 40, height: 4, borderRadius: 2, backgroundColor: '#444444', marginBottom: 8 },
  sheetTitle: { color: '#9E9E9E', fontSize: 13, fontWeight: '600', paddingHorizontal: 20, paddingVertical: 8 },
  list: { flexGrow: 0 },
  option: { minHeight: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20 },
  optionText: { color: '#E0E0E0', fontSize: 16 },
  optionTextSelected: { color: '#FFFFFF', fontWeight: '600' },
});

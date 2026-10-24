/**
 * ScreenHeader — the one header every screen uses. Fixed 56dp tall and owns
 * all top spacing below the status bar (the root layout applies the safe-area
 * inset once; screens add no top padding of their own).
 *
 *   Top-level screen:  <ScreenHeader title="Feed" right={<HeaderIconButton … />} />
 *                      → [≡] Feed ............ [action]   (≡ opens the drawer)
 *   Pushed screen:     <ScreenHeader title="Artist" onBack={router.back} />
 *                      → [←] Artist ........... [action]
 *
 * On tablet the drawer is permanent, so the ≡ button is omitted. `subtitle`
 * adds a small second line (session progress etc.) inside the same 56dp.
 */
import type { ReactElement, ReactNode } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useNavigation } from 'expo-router';
import { DrawerActions } from '@react-navigation/native';
import { ArrowLeft, Menu } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { useAdaptiveLayout } from '../hooks/useAdaptiveLayout';

export const SCREEN_HEADER_HEIGHT = 56;

export interface ScreenHeaderProps {
  title: string;
  /** Optional second line, e.g. "12/40 sorted". */
  subtitle?: string;
  /** Pushed-screen variant: shows ← and calls this. Omit on top-level screens. */
  onBack?: () => void;
  /** Accessibility label for ←. Default "Back". */
  backLabel?: string;
  /** testID for ←. Default "header-back". */
  backTestID?: string;
  /** One trailing action; use HeaderIconButton for consistency. */
  right?: ReactNode;
  titleTestID?: string;
  subtitleTestID?: string;
}

export function ScreenHeader(props: ScreenHeaderProps): ReactElement {
  const { title, subtitle, right, titleTestID, subtitleTestID } = props;
  return (
    <View style={styles.bar}>
      <Leading {...props} />
      <View style={styles.titleBlock}>
        <Text testID={titleTestID} style={styles.title} numberOfLines={1} accessibilityRole="header">
          {title}
        </Text>
        {subtitle ? (
          <Text testID={subtitleTestID} style={styles.subtitle} numberOfLines={1}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {right ? <View style={styles.right}>{right}</View> : null}
    </View>
  );
}

function Leading({ onBack, backLabel, backTestID }: ScreenHeaderProps): ReactElement | null {
  const navigation = useNavigation();
  const { isTablet } = useAdaptiveLayout();
  if (onBack) {
    return <HeaderIconButton icon={ArrowLeft} label={backLabel ?? 'Back'} onPress={onBack} testID={backTestID ?? 'header-back'} />;
  }
  if (isTablet) return <View style={styles.tabletInset} />;
  return (
    <HeaderIconButton
      icon={Menu}
      label="Open menu"
      onPress={() => navigation.dispatch(DrawerActions.openDrawer())}
      testID="nav-open"
    />
  );
}

export interface HeaderIconButtonProps {
  icon: LucideIcon;
  label: string;
  onPress: () => void;
  testID?: string;
  color?: string;
  disabled?: boolean;
}

/** 48dp round icon button sized for the header. */
export function HeaderIconButton({ icon: Icon, label, onPress, testID, color, disabled }: HeaderIconButtonProps): ReactElement {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      disabled={disabled}
      android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 22 }}
      // Static style: NativeWind's Pressable wrapper drops function styles.
      style={[styles.iconButton, disabled && styles.disabled]}
    >
      <Icon size={24} color={color ?? '#E0E0E0'} strokeWidth={2} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: SCREEN_HEADER_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 4,
    backgroundColor: '#121212',
  },
  titleBlock: {
    flex: 1,
    marginLeft: 4,
    justifyContent: 'center',
  },
  title: {
    color: '#E0E0E0',
    fontSize: 20,
    fontWeight: '600',
    letterSpacing: 0.15,
  },
  subtitle: {
    color: '#9E9E9E',
    fontSize: 12,
    marginTop: 1,
  },
  right: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disabled: {
    opacity: 0.4,
  },
  tabletInset: {
    width: 12,
  },
});

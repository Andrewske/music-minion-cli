/**
 * Adaptive layout hook — phone vs tablet breakpoint.
 * Built in Phase 1, used by every screen from day one.
 */
import { useWindowDimensions } from 'react-native';

interface AdaptiveLayout {
  isTablet: boolean;
  isPhone: boolean;
  screenWidth: number;
  screenHeight: number;
}

export const useAdaptiveLayout = (): AdaptiveLayout => {
  const { width, height } = useWindowDimensions();
  return {
    isTablet: width >= 768,
    isPhone: width < 768,
    screenWidth: width,
    screenHeight: height,
  };
};

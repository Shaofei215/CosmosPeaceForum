import { createContext } from 'react';
import type { ResolvedTheme, ThemeMode } from './theme';

export interface ThemeContextValue {
  mode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  cycleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

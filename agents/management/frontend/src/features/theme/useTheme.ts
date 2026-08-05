import { useContext } from 'react';
import { ThemeContext, type ThemeContextValue } from './ThemeContext';

/** 读取当前主题状态和循环操作。 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error('useTheme 必须在 ThemeProvider 内使用');
  }
  return context;
}

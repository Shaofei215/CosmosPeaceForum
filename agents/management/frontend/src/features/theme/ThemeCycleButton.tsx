import type { ButtonHTMLAttributes } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { cn } from '@/shared/lib/cn';
import { getNextThemeMode, type ThemeMode } from './theme';
import { useTheme } from './useTheme';

const MODE_LABELS: Record<ThemeMode, string> = {
  system: '跟随系统',
  light: '亮色',
  dark: '暗色',
};

const MODE_ICONS = {
  system: Monitor,
  light: Sun,
  dark: Moon,
} satisfies Record<ThemeMode, typeof Monitor>;

export interface ThemeCycleButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  showLabel?: boolean;
}

/** 展示当前主题模式，并在点击时按固定顺序循环。 */
export function ThemeCycleButton({
  className,
  showLabel = false,
  ...props
}: ThemeCycleButtonProps) {
  const { mode, cycleTheme } = useTheme();
  const nextMode = getNextThemeMode(mode);
  const Icon = MODE_ICONS[mode];
  const accessibleLabel = `当前主题：${MODE_LABELS[mode]}，点击切换为${MODE_LABELS[nextMode]}`;

  return (
    <button
      type="button"
      className={cn(className)}
      onClick={cycleTheme}
      title={accessibleLabel}
      aria-label={accessibleLabel}
      {...props}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      {showLabel && <span>主题：{MODE_LABELS[mode]}</span>}
    </button>
  );
}

import type { ButtonHTMLAttributes } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { copywriting } from '@/shared/config/copywriting';
import { cn } from '@/shared/lib/utils';
import { getNextThemeMode, type ThemeMode } from './theme';
import { useTheme } from './useTheme';

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
  const labels: Record<ThemeMode, string> = {
    system: copywriting('theme.system', '跟随系统'),
    light: copywriting('theme.light', '亮色'),
    dark: copywriting('theme.dark', '暗色'),
  };
  const accessibleLabel = copywriting('theme.cycle_aria', '当前主题：{current}，点击切换为{next}', {
    current: labels[mode],
    next: labels[nextMode],
  });

  return (
    <button
      type="button"
      className={cn(className)}
      onClick={cycleTheme}
      title={accessibleLabel}
      aria-label={accessibleLabel}
      {...props}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {showLabel && (
        <span>{copywriting('theme.current', '主题：{mode}', { mode: labels[mode] })}</span>
      )}
    </button>
  );
}

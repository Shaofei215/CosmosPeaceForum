import type { CSSProperties } from 'react';
import { usePublicTheme } from './hooks';

type ThemeStyle = CSSProperties & Record<string, string>;

function toRgb(color: string): [number, number, number] | null {
  const value = color.trim();
  if (value.toLowerCase() === 'transparent') {
    return [255, 255, 255];
  }

  const hex = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const raw = hex[1].length === 3 ? hex[1].replace(/./g, char => char + char) : hex[1];
    return [
      Number.parseInt(raw.slice(0, 2), 16),
      Number.parseInt(raw.slice(2, 4), 16),
      Number.parseInt(raw.slice(4, 6), 16),
    ];
  }

  const rgba = value.match(/^rgba?\(\s*(\d{1,3})[,\s]+(\d{1,3})[,\s]+(\d{1,3})/i);
  if (rgba) {
    return [
      Math.min(255, Number(rgba[1])),
      Math.min(255, Number(rgba[2])),
      Math.min(255, Number(rgba[3])),
    ];
  }

  return null;
}

function toColorWithAlpha(color: string, alpha: number, fallback: string): string {
  const rgb = toRgb(color);
  return rgb ? `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})` : fallback;
}

function toOpaqueColor(color: string): string {
  return toColorWithAlpha(color, 1, color);
}

function toGlassColor(color: string): string {
  return toColorWithAlpha(color, 0.45, 'rgba(255, 255, 255, 0.45)');
}

function getTopbarBackground(theme: ReturnType<typeof usePublicTheme>['data']) {
  if (!theme) return '#ffffff';
  if (theme.topbar_background_mode === 'gradient') {
    return `linear-gradient(${theme.topbar_gradient_direction}, ${toOpaqueColor(
      theme.topbar_gradient_from
    )}, ${toOpaqueColor(theme.topbar_gradient_to)})`;
  }
  return toOpaqueColor(theme.topbar_solid_color);
}

function getTopbarGlassBackground(theme: ReturnType<typeof usePublicTheme>['data']) {
  if (!theme) return 'rgba(255, 255, 255, 0.45)';
  if (theme.topbar_background_mode === 'gradient') {
    return `linear-gradient(${theme.topbar_gradient_direction}, ${toGlassColor(
      theme.topbar_gradient_from
    )}, ${toGlassColor(theme.topbar_gradient_to)})`;
  }
  return toGlassColor(theme.topbar_solid_color);
}

export function useThemeScopeStyle(): ThemeStyle {
  const { data: theme } = usePublicTheme();

  return {
    '--theme-accent-bg': theme?.accent_color ?? '#111827',
    '--theme-accent-fg': theme?.accent_foreground_color ?? '#ffffff',
    '--theme-subtle-bg': theme?.subtle_color ?? 'rgba(243, 244, 246, 0.82)',
    '--theme-subtle-fg': theme?.subtle_foreground_color ?? '#4b5563',
    '--theme-topbar-bg': getTopbarBackground(theme),
    '--theme-topbar-scrolled-bg': getTopbarGlassBackground(theme),
  };
}

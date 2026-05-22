export type TopbarBackgroundMode = 'solid' | 'gradient';

export interface ThemeSettings {
  id: number;
  accent_color: string;
  accent_foreground_color: string;
  subtle_color: string;
  subtle_foreground_color: string;
  topbar_background_mode: TopbarBackgroundMode;
  topbar_solid_color: string;
  topbar_gradient_from: string;
  topbar_gradient_to: string;
  topbar_gradient_direction: string;
  topbar_scrolled_background: string;
  topbar_background_image: string | null;
  topbar_decoration_top: string | null;
  topbar_decoration_bottom: string | null;
  topbar_decoration_left: string | null;
  topbar_decoration_right: string | null;
  topbar_action_active_color: string | null;
  topbar_action_active_foreground_color: string | null;
  topbar_action_inactive_color: string | null;
  topbar_action_inactive_foreground_color: string | null;
  updated_at: string;
}

export type ThemeSettingsUpdate = Omit<ThemeSettings, 'id' | 'updated_at'>;

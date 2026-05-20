import { apiClient } from '@/shared/api/client';
import type { ThemeSettings } from './types';

export const themeApi = {
  getPublicTheme: () => apiClient.get<ThemeSettings>('/theme'),
};

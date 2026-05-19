import type { AdminUser } from '@/shared/types/api';

export type AuthUser = AdminUser;

export interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
}

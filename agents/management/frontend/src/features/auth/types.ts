export interface AuthUser {
  id: number;
  username: string;
  created_at: string;
}

export interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
}

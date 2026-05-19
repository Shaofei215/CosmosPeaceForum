import { apiClient } from '@/shared/api/client';
import type { LoginRequest, LoginResponse, AdminUser } from '@/shared/types/api';

export const authApi = {
  login: (credentials: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login', credentials),

  getCurrentAdmin: () =>
    apiClient.get<AdminUser>('/auth/me'),
};

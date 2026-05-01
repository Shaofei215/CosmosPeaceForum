import { apiClient } from '@/shared/api/client';
import type { LoginRequest, LoginResponse, AdminUser, UpdateProfileRequest } from '@/shared/types/api';

export const authApi = {
  login: (credentials: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login', credentials),

  getCurrentAdmin: () =>
    apiClient.get<AdminUser>('/auth/me'),

  updateProfile: (data: UpdateProfileRequest) =>
    apiClient.put<AdminUser>('/auth/profile', data),
};

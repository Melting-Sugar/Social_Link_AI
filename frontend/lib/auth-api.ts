import { apiClient } from "./api-client";

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface MessageResponse {
  message: string;
}

export interface UserResponse {
  id: string;
  email: string;
  username: string;
  email_verified: boolean;
  created_at: string;
}

export const authApi = {
  register: (data: { email: string; username: string; password: string; password_confirm: string }) =>
    apiClient.post<TokenResponse>("/api/auth/register", data),

  login: (data: { identifier: string; password: string }) =>
    apiClient.post<TokenResponse>("/api/auth/login", data),

  logout: () => apiClient.post<MessageResponse>("/api/auth/logout"),

  forgotUsername: (email: string) =>
    apiClient.post<MessageResponse>("/api/auth/forgot-username", { email }),

  forgotPassword: (email: string) =>
    apiClient.post<MessageResponse>("/api/auth/forgot-password", { email }),

  resetPassword: (data: { token: string; new_password: string; new_password_confirm: string }) =>
    apiClient.post<MessageResponse>("/api/auth/reset-password", data),

  me: () => apiClient.get<UserResponse>("/api/users/me"),

  deleteAccount: () => apiClient.delete<MessageResponse>("/api/users/me"),
};

import { api } from './api-client';
import { AuthUser } from '../../stores/session.store';

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

export const authApi = {
  async google(idToken: string): Promise<AuthResponse> {
    const res = await api.post('/api/mobile/auth/google', { idToken });
    return res.data;
  },

  async devLogin(email?: string, name?: string): Promise<AuthResponse> {
    const res = await api.post('/api/mobile/auth/dev-login', {
      email: email || 'dev@fomo.ai',
      name: name || 'FOMO Developer',
    });
    return res.data;
  },

  async refresh(refreshToken: string): Promise<AuthResponse> {
    const res = await api.post('/api/mobile/auth/refresh', { refreshToken });
    return res.data;
  },

  async me(): Promise<AuthUser> {
    const res = await api.get('/api/mobile/auth/me');
    return res.data;
  },

  async logout(refreshToken: string): Promise<{ success: boolean }> {
    const res = await api.post('/api/mobile/auth/logout', { refreshToken });
    return res.data;
  },
};

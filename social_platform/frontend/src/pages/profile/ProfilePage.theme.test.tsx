// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@/features/theme';
import ProfilePage from './ProfilePage';

const mocks = vi.hoisted(() => ({
  currentUserId: 1,
  logout: vi.fn(),
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
}));

vi.mock('@/features/auth', () => ({
  useAuthStore: () => ({
    user: { id: mocks.currentUserId, username: `用户${mocks.currentUserId}` },
    isAuthenticated: true,
  }),
  useLogout: () => mocks.logout,
}));

vi.mock('@/features/user', () => ({
  useUser: () => ({
    data: {
      id: 1,
      username: '测试用户',
      bio: '测试签名',
      avatar_url: null,
      following_count: 2,
      followers_count: 3,
    },
    isLoading: false,
  }),
  useUpdateUser: () => ({ mutateAsync: mocks.mutateAsync, isPending: false }),
  useUploadAvatar: () => ({ mutateAsync: mocks.mutateAsync, isPending: false }),
}));

vi.mock('@/features/feed', () => ({
  useInfiniteUserFeed: () => ({
    data: { pages: [{ data: [] }] },
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
    isLoading: false,
  }),
}));

vi.mock('@/features/follow', () => ({
  useToggleFollow: () => ({ mutate: mocks.mutate, isPending: false }),
  useFollowStatus: () => ({ data: { is_following: false, is_mutual: false } }),
}));

vi.mock('@/features/report', () => ({
  useCreateReport: () => ({ mutateAsync: mocks.mutateAsync, isPending: false }),
}));

vi.mock('@/widgets/post-card', () => ({ PostCard: () => null }));

class IntersectionObserverMock implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = '';
  readonly thresholds = [];
  disconnect = vi.fn();
  observe = vi.fn();
  takeRecords = vi.fn(() => []);
  unobserve = vi.fn();
}

/** 渲染指定用户的个人主页。 */
function renderProfile(): void {
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/user/1']}>
        <Routes>
          <Route path="/user/:userId" element={<ProfilePage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );
}

beforeEach(() => {
  mocks.currentUserId = 1;
  localStorage.clear();
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      media: '(prefers-color-scheme: dark)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
  vi.stubGlobal('IntersectionObserver', IntersectionObserverMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('ProfilePage theme entry', () => {
  it('仅在本人个人主页的更多菜单展示主题循环入口，并在切换后保持菜单展开', () => {
    renderProfile();

    fireEvent.click(screen.getByRole('button', { name: '更多操作' }));
    fireEvent.click(screen.getByRole('button', { name: '当前主题：跟随系统，点击切换为亮色' }));

    expect(screen.getByText('主题：亮色')).not.toBeNull();
    expect(screen.getByRole('button', { name: '登出' })).not.toBeNull();
  });

  it('访问其他用户主页时不展示主题入口', () => {
    mocks.currentUserId = 2;
    renderProfile();

    fireEvent.click(screen.getByRole('button', { name: '更多操作' }));

    expect(screen.queryByText(/主题：/)).toBeNull();
    expect(screen.getByRole('button', { name: '举报' })).not.toBeNull();
  });
});

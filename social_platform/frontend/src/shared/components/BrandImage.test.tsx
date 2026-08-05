// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeCycleButton, ThemeProvider, THEME_STORAGE_KEY } from '@/features/theme';
import { BrandImage } from './BrandImage';

beforeEach(() => {
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
});

afterEach(() => cleanup());

describe('BrandImage', () => {
  it('暗色资源加载失败后回退同名普通图片', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    render(
      <ThemeProvider>
        <BrandImage name="banner" fallbackNames={['icon']} alt="品牌横幅" />
      </ThemeProvider>
    );

    const image = screen.getByRole('img', { name: '品牌横幅' });
    expect(image.getAttribute('src')).toBe('/banner_dark.png');
    for (let failureCount = 0; failureCount < 5; failureCount += 1) fireEvent.error(image);
    expect(image.getAttribute('src')).toBe('/banner.png');
  });

  it('实际主题变化时从普通图片切换到 dark 图片并重置候选顺序', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    render(
      <ThemeProvider>
        <BrandImage name="icon" alt="品牌图标" />
        <ThemeCycleButton />
      </ThemeProvider>
    );

    expect(screen.getByRole('img', { name: '品牌图标' }).getAttribute('src')).toBe('/icon.png');
    fireEvent.click(screen.getByRole('button', { name: '当前主题：亮色，点击切换为暗色' }));
    expect(screen.getByRole('img', { name: '品牌图标' }).getAttribute('src')).toBe(
      '/icon_dark.png'
    );
  });
});

// @vitest-environment jsdom

import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeCycleButton } from './ThemeCycleButton';
import { ThemeProvider } from './ThemeProvider';
import {
  THEME_STORAGE_KEY,
  applyTheme,
  getNextThemeMode,
  parseThemeMode,
  resolveTheme,
} from './theme';

let systemPrefersDark = false;
let mediaListeners = new Set<(event: MediaQueryListEvent) => void>();
let container: HTMLDivElement;
let root: Root;

beforeAll(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
});

afterAll(() => {
  Reflect.deleteProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT');
});

/** 安装可控制系统主题变化的 matchMedia 测试替身。 */
function installMatchMedia(): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: systemPrefersDark,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) =>
        mediaListeners.add(listener),
      removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) =>
        mediaListeners.delete(listener),
      dispatchEvent: vi.fn(),
    })),
  });
}

/** 模拟操作系统配色发生变化。 */
function setSystemTheme(prefersDark: boolean): void {
  systemPrefersDark = prefersDark;
  const event = { matches: prefersDark } as MediaQueryListEvent;
  mediaListeners.forEach(listener => listener(event));
}

/** 使用 React DOM 渲染主题按钮，避免为管理前端新增测试依赖。 */
function renderThemeButton(showLabel = false): HTMLButtonElement {
  act(() => {
    root.render(
      <ThemeProvider>
        <ThemeCycleButton showLabel={showLabel} />
      </ThemeProvider>
    );
  });
  return container.querySelector('button') as HTMLButtonElement;
}

beforeEach(() => {
  systemPrefersDark = false;
  mediaListeners = new Set();
  localStorage.clear();
  document.documentElement.classList.remove('dark');
  document.documentElement.style.colorScheme = '';
  installMatchMedia();
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe('theme helpers', () => {
  it('规范化存储值并按三态固定顺序循环', () => {
    expect(parseThemeMode(null)).toBe('system');
    expect(parseThemeMode('invalid')).toBe('system');
    expect(getNextThemeMode('system')).toBe('light');
    expect(getNextThemeMode('light')).toBe('dark');
    expect(getNextThemeMode('dark')).toBe('system');
  });

  it('仅在系统模式下使用系统偏好', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
  });

  it('应用主题时同步切换浏览器页签图标', () => {
    const favicon = document.createElement('link');
    favicon.dataset.themeFavicon = '';
    favicon.dataset.lightHref = '/icon.png';
    favicon.dataset.lightType = 'image/png';
    favicon.dataset.darkHref = '/icon_dark.webp';
    favicon.dataset.darkType = 'image/webp';
    document.head.append(favicon);

    applyTheme(document.documentElement, 'dark');
    expect(favicon.getAttribute('href')).toBe('/icon_dark.webp');
    expect(favicon.getAttribute('type')).toBe('image/webp');

    applyTheme(document.documentElement, 'light');
    expect(favicon.getAttribute('href')).toBe('/icon.png');
    expect(favicon.getAttribute('type')).toBe('image/png');
    favicon.remove();
  });
});

describe('ThemeProvider', () => {
  it('首次进入跟随系统并同步文档主题', () => {
    systemPrefersDark = true;

    renderThemeButton(true);

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe('dark');
    expect(container.textContent).toContain('主题：跟随系统');
    expect(document.querySelector('.lucide-monitor')).not.toBeNull();
  });

  it('刷新后恢复已持久化的手动主题', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');

    renderThemeButton(true);

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(container.textContent).toContain('主题：暗色');
  });

  it('循环模式、更新图标并持久化选择', () => {
    let button = renderThemeButton(true);

    expect(button.getAttribute('aria-label')).toBe('当前主题：跟随系统，点击切换为亮色');
    act(() => button.click());
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
    expect(container.textContent).toContain('主题：亮色');
    expect(document.querySelector('.lucide-sun')).not.toBeNull();

    button = container.querySelector('button') as HTMLButtonElement;
    expect(button.getAttribute('aria-label')).toBe('当前主题：亮色，点击切换为暗色');
    act(() => button.click());
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.querySelector('.lucide-moon')).not.toBeNull();

    button = container.querySelector('button') as HTMLButtonElement;
    expect(button.getAttribute('aria-label')).toBe('当前主题：暗色，点击切换为跟随系统');
    act(() => button.click());
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('system');
    expect(container.textContent).toContain('主题：跟随系统');
  });

  it('系统变化只影响跟随系统模式，并响应跨标签页更新', () => {
    const button = renderThemeButton();

    act(() => setSystemTheme(true));
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    act(() => button.click());
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    act(() => setSystemTheme(false));
    act(() => setSystemTheme(true));
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: THEME_STORAGE_KEY, newValue: 'dark' })
      );
    });
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });
});

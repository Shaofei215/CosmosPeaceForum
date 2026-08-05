export const THEME_STORAGE_KEY = 'cosmos-peace-forum-theme';
export const SYSTEM_THEME_QUERY = '(prefers-color-scheme: dark)';

export type ThemeMode = 'system' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

/** 将持久化值规范化为受支持的主题模式。 */
export function parseThemeMode(value: string | null): ThemeMode {
  return value === 'light' || value === 'dark' || value === 'system' ? value : 'system';
}

/** 按固定顺序返回下一个主题模式。 */
export function getNextThemeMode(mode: ThemeMode): ThemeMode {
  if (mode === 'system') return 'light';
  if (mode === 'light') return 'dark';
  return 'system';
}

/** 根据选定模式和系统偏好计算实际渲染主题。 */
export function resolveTheme(mode: ThemeMode, systemPrefersDark: boolean): ResolvedTheme {
  if (mode === 'system') return systemPrefersDark ? 'dark' : 'light';
  return mode;
}

/** 把实际主题同步到文档根节点和浏览器原生控件。 */
export function applyTheme(root: HTMLElement, theme: ResolvedTheme): void {
  root.classList.toggle('dark', theme === 'dark');
  root.style.colorScheme = theme;

  const favicon = root.ownerDocument.querySelector<HTMLLinkElement>('link[data-theme-favicon]');
  if (favicon === null) return;

  const href = theme === 'dark' ? favicon.dataset.darkHref : favicon.dataset.lightHref;
  const type = theme === 'dark' ? favicon.dataset.darkType : favicon.dataset.lightType;
  if (href) favicon.setAttribute('href', href);
  if (type) favicon.setAttribute('type', type);
}

/**
 * 外部跳转确认工具。
 *
 * 负责判断链接是否离开当前站点，并生成跳转确认页地址。上游由 Markdown、
 * 页脚等链接渲染组件调用，下游由外部跳转确认页解析并校验目标地址。
 */

export const EXTERNAL_REDIRECT_PATH = '/external-redirect';
const EXTERNAL_REDIRECT_PARAM = 'url';
const BARE_DOMAIN_PATTERN =
  /^(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+(?:[/:?#].*)?$/i;

/**
 * 为外部目标地址生成站内确认页地址。
 *
 * @param targetUrl 用户原本要访问的外部地址。
 * @returns 携带原始目标地址的站内确认页路径。
 */
export function buildExternalRedirectUrl(targetUrl: string): string {
  const params = new URLSearchParams({
    [EXTERNAL_REDIRECT_PARAM]: normalizeHttpHref(targetUrl) ?? targetUrl,
  });

  return `${EXTERNAL_REDIRECT_PATH}?${params.toString()}`;
}

/**
 * 将用户输入的链接规范化为可用于富文本和 Markdown 的 href。
 *
 * @param href 用户输入或 Markdown 解析出的链接。
 * @returns 裸域名自动补全 https://；其它地址去除首尾空白后原样返回。
 */
export function normalizeLinkHref(href: string): string {
  return normalizeHttpHref(href) ?? href.trim();
}

/**
 * 从查询参数中读取并校验外部跳转目标。
 *
 * @param searchParams 当前页面查询参数。
 * @returns 有效的 http/https 外部地址；无效或站内地址返回 null。
 */
export function getExternalRedirectTarget(searchParams: URLSearchParams): string | null {
  const targetUrl = searchParams.get(EXTERNAL_REDIRECT_PARAM);
  const normalizedTargetUrl = targetUrl ? normalizeHttpHref(targetUrl) : null;

  if (!normalizedTargetUrl || !isExternalHttpUrl(normalizedTargetUrl)) {
    return null;
  }

  return normalizedTargetUrl;
}

/**
 * 判断 href 是否为离开当前站点的 http/https 链接。
 *
 * @param href 待判断的链接地址。
 * @returns true 表示该地址会跳转到当前站点之外。
 */
export function isExternalHttpUrl(href: string): boolean {
  const url = parseHttpUrl(href);

  if (!url) {
    return false;
  }

  return url.origin !== getCurrentOrigin();
}

/**
 * 判断 href 是否为站内路径。
 *
 * @param href 待判断的链接地址。
 * @returns true 表示该地址可以直接交给 React Router 处理。
 */
export function isInternalHref(href: string): boolean {
  if (href.startsWith('/') || href.startsWith('#') || href.startsWith('?')) {
    return true;
  }

  const url = parseHttpUrl(href);

  return Boolean(url && url.origin === getCurrentOrigin());
}

/**
 * 把绝对站内地址转换成带查询和哈希的路径。
 *
 * @param href 站内绝对地址或相对路径。
 * @returns React Router 可用的站内路径。
 */
export function toInternalPath(href: string): string {
  if (href.startsWith('/') || href.startsWith('#') || href.startsWith('?')) {
    return href;
  }

  const url = parseHttpUrl(href);

  if (!url) {
    return href;
  }

  return `${url.pathname}${url.search}${url.hash}`;
}

/**
 * 解析并限制可跳转协议。
 *
 * @param href 用户或配置提供的链接地址。
 * @returns http/https URL 对象；解析失败或协议不允许时返回 null。
 */
function parseHttpUrl(href: string): URL | null {
  const normalizedHref = normalizeHttpHref(href);

  if (!normalizedHref) {
    return null;
  }

  try {
    const url = new URL(normalizedHref);

    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      return null;
    }

    return url;
  } catch {
    return null;
  }
}

/**
 * 将 http/https 绝对链接、协议相对链接和裸域名规范化为完整地址。
 *
 * @param href 待规范化的链接。
 * @returns 可被 URL 直接解析的 http/https 地址；非网络地址返回 null。
 */
function normalizeHttpHref(href: string): string | null {
  const trimmedHref = href.trim();

  if (!trimmedHref) {
    return null;
  }

  if (/^https?:\/\//i.test(trimmedHref)) {
    return trimmedHref;
  }

  if (trimmedHref.startsWith('//')) {
    return `${getCurrentProtocol()}${trimmedHref}`;
  }

  if (BARE_DOMAIN_PATTERN.test(trimmedHref)) {
    return `https://${trimmedHref}`;
  }

  return null;
}

/**
 * 获取当前站点 origin，供浏览器环境内的链接判断使用。
 *
 * @returns 当前页面 origin；非浏览器环境下返回本地占位 origin。
 */
function getCurrentOrigin(): string {
  if (typeof window === 'undefined') {
    return 'http://localhost';
  }

  return window.location.origin;
}

/**
 * 获取当前页面协议，用于补全协议相对链接。
 *
 * @returns 当前页面协议；非浏览器环境下默认使用 https:。
 */
function getCurrentProtocol(): string {
  if (typeof window === 'undefined') {
    return 'https:';
  }

  return window.location.protocol;
}

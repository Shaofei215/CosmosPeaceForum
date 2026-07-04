/**
 * API 错误消息标准化工具。
 *
 * FastAPI 的业务错误通常把 detail 返回为字符串，而请求参数校验错误会返回
 * 对象数组。该模块将两种响应统一为可安全渲染的字符串，避免把对象交给 React。
 */

/**
 * 将后端 detail 标准化为 React 可安全渲染的字符串。
 *
 * @param detail FastAPI 响应中的 detail 字段。
 * @param fallback detail 缺失或结构未知时使用的兜底文本。
 * @returns 供页面直接展示的错误消息。
 */
export function getApiErrorMessage(detail: unknown, fallback = '请求失败，请稍后重试'): string {
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    return '请求参数有误，请检查后重试';
  }

  return fallback;
}

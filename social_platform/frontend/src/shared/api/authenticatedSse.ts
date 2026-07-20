import { copywriting } from '@/shared/config/copywriting';

/**
 * 带 Bearer Header 的浏览器 SSE 客户端。
 *
 * 原生 EventSource 不能附带认证头，因此这里基于 fetch 解析 SSE 帧，并在首次
 * 收到 401 时轮换 access token。重连策略由调用方决定，便于区分长连接通知和
 * 一次性热榜生成任务。
 */

export interface SseMessage {
  event: string;
  data: string;
}

interface AuthenticatedSseOptions {
  url: string;
  method?: 'GET' | 'POST';
  signal: AbortSignal;
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<string | null>;
  onMessage: (message: SseMessage) => void;
}

function dispatchFrame(frame: string, onMessage: (message: SseMessage) => void): void {
  let event = 'message';
  const data: string[] = [];
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue;
    const separator = line.indexOf(':');
    const field = separator === -1 ? line : line.slice(0, separator);
    const value = separator === -1 ? '' : line.slice(separator + 1).replace(/^ /, '');
    if (field === 'event') event = value;
    if (field === 'data') data.push(value);
  }
  if (data.length > 0) onMessage({ event, data: data.join('\n') });
}

async function consumeResponse(
  response: Response,
  signal: AbortSignal,
  onMessage: (message: SseMessage) => void
): Promise<void> {
  if (!response.body) {
    throw new Error(copywriting('errors.streaming_unsupported', '浏览器不支持流式响应'));
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n');
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        dispatchFrame(buffer.slice(0, boundary), onMessage);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}

/** 建立一次认证 SSE 连接；401 时只轮换并重试一次。 */
export async function openAuthenticatedSse(options: AuthenticatedSseOptions): Promise<void> {
  let token = options.getAccessToken();
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (!token) throw new Error(copywriting('errors.session_expired', '登录已失效，请重新登录'));
    const response = await fetch(options.url, {
      method: options.method ?? 'GET',
      headers: {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
      signal: options.signal,
    });
    if (response.status === 401 && attempt === 0) {
      token = await options.refreshAccessToken();
      continue;
    }
    if (!response.ok) {
      throw new Error(
        copywriting('errors.streaming_failed', '流式请求失败（{status}）', {
          status: response.status,
        })
      );
    }
    await consumeResponse(response, options.signal, options.onMessage);
    return;
  }
}

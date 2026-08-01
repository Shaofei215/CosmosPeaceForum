import { afterEach, describe, expect, it, vi } from 'vitest';
import { openAuthenticatedSse } from './authenticatedSse';

describe('openAuthenticatedSse', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('携带认证头并解析 SSE 事件', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('event: status\ndata: {"scheduler_online":true,"agents":[]}\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const messages: Array<{ event: string; data: string }> = [];

    await openAuthenticatedSse({
      url: '/api/agents/status-stream',
      signal: new AbortController().signal,
      getAccessToken: () => 'access-secret',
      refreshAccessToken: async () => null,
      onMessage: (message) => messages.push(message),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/agents/status-stream',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer access-secret' }),
      }),
    );
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('access-secret');
    expect(messages).toEqual([
      { event: 'status', data: '{"scheduler_online":true,"agents":[]}' },
    ]);
  });

  it('收到 401 后只刷新一次并使用新 token 重试', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(new Response('event: status\ndata: {}\n\n', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const refresh = vi.fn().mockResolvedValue('fresh-token');

    await openAuthenticatedSse({
      url: '/api/agents/status-stream',
      signal: new AbortController().signal,
      getAccessToken: () => 'expired-token',
      refreshAccessToken: refresh,
      onMessage: () => undefined,
    });

    expect(refresh).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]?.headers).toMatchObject({
      Authorization: 'Bearer fresh-token',
    });
  });
});

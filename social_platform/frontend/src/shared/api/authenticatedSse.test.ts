import { afterEach, describe, expect, it, vi } from 'vitest';
import { openAuthenticatedSse } from './authenticatedSse';

describe('openAuthenticatedSse', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses the authorization header and parses event frames', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('event: notifications.changed\ndata: {"unread_count":2}\n\n', {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);
    const messages: Array<{ event: string; data: string }> = [];

    await openAuthenticatedSse({
      url: '/api/v1/notifications/events',
      signal: new AbortController().signal,
      getAccessToken: () => 'access-secret',
      refreshAccessToken: async () => null,
      onMessage: message => messages.push(message),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/notifications/events',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer access-secret' }),
      })
    );
    expect(String(fetchMock.mock.calls[0][0])).not.toContain('access-secret');
    expect(messages).toEqual([{ event: 'notifications.changed', data: '{"unread_count":2}' }]);
  });

  it('refreshes once after a 401 response', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(new Response('event: done\ndata: {}\n\n', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const refresh = vi.fn().mockResolvedValue('fresh-token');

    await openAuthenticatedSse({
      url: '/stream',
      method: 'POST',
      signal: new AbortController().signal,
      getAccessToken: () => 'expired-token',
      refreshAccessToken: refresh,
      onMessage: () => undefined,
    });

    expect(refresh).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[1][1]?.headers).toMatchObject({
      Authorization: 'Bearer fresh-token',
    });
  });
});

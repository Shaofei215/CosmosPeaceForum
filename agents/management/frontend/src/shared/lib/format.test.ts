import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatDate } from './format';

describe('formatDate', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('空值或非法日期返回空字符串', () => {
    expect(formatDate(null)).toBe('');
    expect(formatDate(undefined)).toBe('');
    expect(formatDate('not-a-date')).toBe('');
  });

  it('七天内的时间使用中文相对描述', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 20, 12, 0, 0));

    expect(formatDate(new Date(2026, 6, 20, 11, 55, 0))).toContain('分钟');
  });

  it('较早时间使用稳定的年月日与时分格式', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 20, 12, 0, 0));

    expect(formatDate(new Date(2026, 6, 1, 8, 30, 0))).toBe('2026-07-01 08:30');
  });
});

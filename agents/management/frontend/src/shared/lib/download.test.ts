// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';

import { buildAgentExportFilename, downloadBlob } from './download';

describe('downloadBlob', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('触发下载并释放对象 URL', () => {
    const createObjectUrl = vi.fn(() => 'blob:agent-export');
    const revokeObjectUrl = vi.fn();
    vi.stubGlobal('URL', {
      createObjectURL: createObjectUrl,
      revokeObjectURL: revokeObjectUrl,
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const blob = new Blob(['zip-content'], { type: 'application/zip' });

    downloadBlob(blob, 'agents_config.zip');

    expect(createObjectUrl).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:agent-export');
    expect(document.querySelector('a[download="agents_config.zip"]')).toBeNull();
  });
});

describe('buildAgentExportFilename', () => {
  it('使用本地时间生成稳定的 ZIP 文件名', () => {
    const now = new Date(2026, 7, 4, 9, 8, 7);

    expect(buildAgentExportFilename(now)).toBe('agents_config_20260804_090807.zip');
  });
});

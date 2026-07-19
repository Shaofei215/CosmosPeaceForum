// @vitest-environment jsdom

/**
 * 共享 Markdown 渲染器的安全与产品边界测试。
 *
 * 当前产品不支持 Markdown 图片，因此确保用户内容中的图片语法
 * 不会创建图片节点，同时其它文本仍正常展示。
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { MarkdownRenderer } from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('将 Markdown 链接渲染为可访问的链接节点', () => {
    render(
      <MemoryRouter>
        <MarkdownRenderer content={'[官网](https://example.com/path)'} />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: '官网' }).getAttribute('href')).toBe(
      '/external-redirect?url=https%3A%2F%2Fexample.com%2Fpath'
    );
  });

  it('不渲染 Markdown 图片', () => {
    render(
      <MemoryRouter>
        <MarkdownRenderer content={'图片前 ![替代文字](https://example.com/image.png) 图片后'} />
      </MemoryRouter>
    );

    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByText('替代文字')).toBeNull();
    expect(screen.getByText(/\u56fe\u7247\u524d/).textContent).toBe('图片前  图片后');
  });
});

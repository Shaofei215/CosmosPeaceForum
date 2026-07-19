// @vitest-environment jsdom

/**
 * 文章编辑器 HTML 转 Markdown 的单元测试。
 *
 * 重点覆盖新增的 GFM 表格序列化，确保发布时不会把可视表格
 * 降级为普通文本。
 */

import { describe, expect, it } from 'vitest';
import { Editor } from '@tiptap/core';
import { TableKit } from '@tiptap/extension-table';
import StarterKit from '@tiptap/starter-kit';
import { editorHtmlToMarkdown } from './articleMarkdown';

describe('editorHtmlToMarkdown', () => {
  it('将带表头的富文本表格转为 GFM 表格', () => {
    const html = [
      '<table>',
      '<tbody>',
      '<tr><th><p>姓名</p></th><th><p>主页</p></th></tr>',
      '<tr><td><p>小和</p></td><td><p><a href="https://example.com">example</a></p></td></tr>',
      '</tbody>',
      '</table>',
    ].join('');

    expect(editorHtmlToMarkdown(html)).toBe(
      '| 姓名 | 主页 |\n| --- | --- |\n| 小和 | [example](https://example.com) |'
    );
  });

  it('转义单元格管道字符并保留表格前后段落', () => {
    const html = [
      '<p>表格前</p>',
      '<table><tbody>',
      '<tr><td><p>列 A</p></td><td><p>列 B</p></td></tr>',
      '<tr><td><p>A | B</p></td><td><p><strong>加粗</strong></p></td></tr>',
      '</tbody></table>',
      '<p>表格后</p>',
    ].join('');

    expect(editorHtmlToMarkdown(html)).toBe(
      '表格前\n\n| 列 A | 列 B |\n| --- | --- |\n| A \\| B | **加粗** |\n\n表格后'
    );
  });

  it('保持无表格富文本的原有转换行为', () => {
    expect(editorHtmlToMarkdown('<h2>标题</h2><p>正文 <em>斜体</em></p>')).toBe(
      '## 标题\n\n正文 *斜体*'
    );
  });

  it('将同时带有斜体和粗体 mark 的文本转为三个星号语法', () => {
    expect(editorHtmlToMarkdown('<p><strong><em>斜粗体</em></strong></p>')).toBe('***斜粗体***');
  });

  it('使 TipTap 保留可编辑的结构化表格节点', () => {
    const editor = new Editor({ extensions: [StarterKit, TableKit] });

    editor.commands.insertTable({ rows: 2, cols: 2, withHeaderRow: true });

    expect(editor.getJSON().content?.[0]?.type).toBe('table');
    expect(editor.getHTML()).toContain('<table');
    expect(editorHtmlToMarkdown(editor.getHTML())).toBe('|  |  |\n| --- | --- |\n|  |  |');

    editor.destroy();
  });
});

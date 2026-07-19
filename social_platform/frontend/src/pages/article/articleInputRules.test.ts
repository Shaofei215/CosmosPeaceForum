// @vitest-environment jsdom

/**
 * 文章 Markdown 所见即所得输入规则测试。
 *
 * 测试直接经过 ProseMirror `handleTextInput` 逐字符输入最后一个闭合符，
 * 确保覆盖用户在编辑器内真实键入时的转换路径。
 */

import { Editor, type JSONContent } from '@tiptap/core';
import { TableKit } from '@tiptap/extension-table';
import StarterKit from '@tiptap/starter-kit';
import { describe, expect, it } from 'vitest';
import { MarkdownLinkExtension, MarkdownTableInputExtension } from './articleInputRules';

describe('articleInputRules', () => {
  it('在最后一个右括号输入后将 Markdown 链接替换为 link mark', () => {
    const editor = new Editor({
      extensions: [StarterKit.configure({ link: false }), MarkdownLinkExtension],
      content: '<p>[官网](https://example.com</p>',
    });

    editor.commands.setTextSelection(editor.state.doc.content.size - 1);
    typeText(editor, ')');

    const linkText = (editor.getJSON() as JSONContent).content?.[0]?.content?.[0];

    expect(linkText?.text).toBe('官网');
    expect(linkText?.marks?.[0]).toMatchObject({
      type: 'link',
      attrs: { href: 'https://example.com' },
    });

    editor.destroy();
  });

  it('在第三行最后一个管道符输入后将 GFM 文本替换为表格节点', () => {
    const editor = new Editor({
      extensions: [
        StarterKit.configure({ link: false }),
        MarkdownLinkExtension,
        TableKit,
        MarkdownTableInputExtension,
      ],
      content: ['<p>| 表头1 | 表头2 |</p>', '<p>| --- | --- |</p>', '<p>| 表格1 | 表格2 </p>'].join(
        ''
      ),
    });

    editor.commands.setTextSelection(editor.state.doc.content.size - 1);
    typeText(editor, '|');

    const document = editor.getJSON() as JSONContent;
    const table = document.content?.[0];

    expect(table?.type).toBe('table');
    expect(table?.content).toHaveLength(2);
    expect(table?.content?.[0]?.content?.map(cell => cell.type)).toEqual([
      'tableHeader',
      'tableHeader',
    ]);
    expect(table?.content?.[1]?.content?.map(cell => cell.type)).toEqual([
      'tableCell',
      'tableCell',
    ]);
    expect(table?.content?.[1]?.content?.[0]?.content?.[0]?.content?.[0]?.text).toBe('表格1');

    editor.destroy();
  });
});

/**
 * 通过编辑器的文本输入处理链逐字符写入内容。
 *
 * @param editor 接收输入的 TipTap 编辑器。
 * @param value 要模拟键入的文本。
 */
function typeText(editor: Editor, value: string): void {
  for (const character of value) {
    const { from, to } = editor.state.selection;
    let handled = false;

    editor.view.someProp('handleTextInput', handler => {
      if (!handler(editor.view, from, to, character, () => editor.state.tr.insertText(character))) {
        return false;
      }

      handled = true;
      return true;
    });

    if (!handled) {
      editor.view.dispatch(editor.state.tr.insertText(character, from, to));
    }
  }
}

// @vitest-environment jsdom

/**
 * 文章 Markdown 所见即所得输入规则测试。
 *
 * 测试直接经过 ProseMirror `handleTextInput` 逐字符输入最后一个闭合符，
 * 并覆盖粘贴规则，确保星号与下划线强调语法具有一致行为。
 */

import { Editor, type AnyExtension, type JSONContent } from '@tiptap/core';
import { TableKit } from '@tiptap/extension-table';
import StarterKit from '@tiptap/starter-kit';
import { beforeAll, describe, expect, it } from 'vitest';
import {
  MarkdownBoldMarkExtension,
  MarkdownEmphasisExtension,
  MarkdownItalicMarkExtension,
  MarkdownLinkExtension,
  MarkdownTableInputExtension,
} from './articleInputRules';

interface EmphasisSyntaxCase {
  source: string;
  expectedMarks: string[];
}

const emphasisSyntaxCases: EmphasisSyntaxCase[] = [
  { source: '*斜体*', expectedMarks: ['italic'] },
  { source: '_斜体_', expectedMarks: ['italic'] },
  { source: '**粗体**', expectedMarks: ['bold'] },
  { source: '__粗体__', expectedMarks: ['bold'] },
  { source: '***斜粗体***', expectedMarks: ['bold', 'italic'] },
  { source: '___斜粗体___', expectedMarks: ['bold', 'italic'] },
];

beforeAll(() => {
  installClipboardApiStubs();
});

describe('articleInputRules', () => {
  it.each(emphasisSyntaxCases)(
    '紧邻前文输入 $source 时转换为对应的强调 mark',
    ({ source, expectedMarks }) => {
      const editor = new Editor({
        extensions: createMarkdownEmphasisExtensions(),
        content: `<p>前文${source.slice(0, -1)}</p>`,
      });

      editor.commands.setTextSelection(editor.state.doc.content.size - 1);
      typeText(editor, source.slice(-1));

      expectEmphasisConversion(editor, expectedMarks);
      expectPlainTextContinuation(editor);
      editor.destroy();
    }
  );

  it.each(emphasisSyntaxCases)(
    '紧邻前文粘贴 $source 时转换为对应的强调 mark',
    ({ source, expectedMarks }) => {
      const editor = new Editor({
        extensions: createMarkdownEmphasisExtensions(),
      });

      editor.view.dispatch(editor.state.tr.insertText(`前文${source}`).setMeta('uiEvent', 'paste'));

      expectEmphasisConversion(editor, expectedMarks);
      expectPlainTextContinuation(editor);
      editor.destroy();
    }
  );

  it('不转换反斜线转义的强调标签', () => {
    const editor = new Editor({
      extensions: createMarkdownEmphasisExtensions(),
      content: '<p>前文\\***斜粗体**</p>',
    });

    editor.commands.setTextSelection(editor.state.doc.content.size - 1);
    typeText(editor, '*');

    const textNode = (editor.getJSON() as JSONContent).content?.[0]?.content?.[0];

    expect(textNode?.text).toBe('前文\\***斜粗体***');
    expect(textNode?.marks).toBeUndefined();
    editor.destroy();
  });

  it('Markdown 链接紧邻前文时仍转换并在完成后退出 link mark', () => {
    const editor = new Editor({
      extensions: [StarterKit.configure({ link: false }), MarkdownLinkExtension],
      content: '<p>前文[官网](https://example.com</p>',
    });

    editor.commands.setTextSelection(editor.state.doc.content.size - 1);
    typeText(editor, ')');

    const inlineContent = (editor.getJSON() as JSONContent).content?.[0]?.content;
    const linkText = inlineContent?.[1];

    expect(inlineContent?.[0]).toMatchObject({ text: '前文' });
    expect(linkText?.text).toBe('官网');
    expect(linkText?.marks?.[0]).toMatchObject({
      type: 'link',
      attrs: { href: 'https://example.com' },
    });
    expect(editor.isActive('link')).toBe(false);

    typeText(editor, '后文');

    expect((editor.getJSON() as JSONContent).content?.[0]?.content?.[2]).toMatchObject({
      text: '后文',
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
 * 断言强调源码标签已移除、前文未被污染且正文获得预期 mark。
 *
 * @param editor 已执行输入或粘贴转换的 TipTap 编辑器。
 * @param expectedMarks 强调正文应具有的 mark 名称。
 */
function expectEmphasisConversion(editor: Editor, expectedMarks: string[]): void {
  const inlineContent = (editor.getJSON() as JSONContent).content?.[0]?.content;
  const plainText = inlineContent?.[0];
  const formattedText = inlineContent?.[1];

  expect(plainText).toMatchObject({ text: '前文' });
  expect(plainText?.marks).toBeUndefined();
  expect(formattedText?.text).toMatch(/^(?:斜体|粗体|斜粗体)$/);
  expect(formattedText?.marks?.map(mark => mark.type).sort()).toEqual(expectedMarks);
}

/**
 * 断言强调转换已退出 mark，工具栏状态与后续键入都恢复为普通文本。
 *
 * @param editor 已完成 Markdown 强调转换的 TipTap 编辑器。
 */
function expectPlainTextContinuation(editor: Editor): void {
  expect(editor.isActive('bold')).toBe(false);
  expect(editor.isActive('italic')).toBe(false);

  typeText(editor, '后文');

  const trailingText = (editor.getJSON() as JSONContent).content?.[0]?.content?.[2];

  expect(trailingText).toMatchObject({ text: '后文' });
  expect(trailingText?.marks).toBeUndefined();
}

/**
 * 创建由统一强调规则接管 bold、italic 输入行为的测试扩展集合。
 *
 * @returns 包含基础节点、自定义粗斜体 mark 以及统一 Markdown 强调规则的扩展。
 */
function createMarkdownEmphasisExtensions(): AnyExtension[] {
  return [
    StarterKit.configure({ bold: false, italic: false }),
    MarkdownBoldMarkExtension,
    MarkdownItalicMarkExtension,
    MarkdownEmphasisExtension,
  ];
}

/**
 * 为 jsdom 补充 TipTap 模拟粘贴规则所需的最小剪贴板 API。
 *
 * 浏览器运行时原生提供这些对象；测试环境缺失时才安装，不覆盖已有实现。
 */
function installClipboardApiStubs(): void {
  if (typeof globalThis.DataTransfer === 'undefined') {
    Object.defineProperty(globalThis, 'DataTransfer', {
      configurable: true,
      value: class DataTransferStub {
        private readonly values = new Map<string, string>();

        getData(format: string): string {
          return this.values.get(format) ?? '';
        }

        setData(format: string, data: string): void {
          this.values.set(format, data);
        }
      },
    });
  }

  if (typeof globalThis.ClipboardEvent === 'undefined') {
    Object.defineProperty(globalThis, 'ClipboardEvent', {
      configurable: true,
      value: class ClipboardEventStub extends Event {
        readonly clipboardData: DataTransfer | null;

        constructor(type: string, init?: { clipboardData?: DataTransfer | null }) {
          super(type);
          this.clipboardData = init?.clipboardData ?? null;
        }
      },
    });
  }
}

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

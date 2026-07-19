/**
 * 文章编辑器的 Markdown 所见即所得输入规则。
 *
 * 上游由文章编辑页注册到 TipTap，下游在用户输入完整链接或
 * GFM 表格的最后一个闭合字符时，将 Markdown 源文本替换为可编辑的
 * TipTap 结构化节点。
 */

import { Extension, InputRule, type JSONContent } from '@tiptap/core';
import LinkExtension from '@tiptap/extension-link';
import { normalizeLinkHref } from '@/shared/lib/externalRedirect';

const markdownLinkPattern = /\[([^\]\n]+)\]\(([^\s()]+)\)$/;
const completedMarkdownTableRowPattern = /^\s*\|.*\|\s*$/;
const markdownTableSeparatorPattern = /^:?-{3,}:?$/;

interface TopLevelBlockSnapshot {
  position: number;
  nodeSize: number;
  typeName: string;
  text: string;
}

/**
 * 在用户输入完 `[描述](地址)` 的最后一个 `)` 时立即生成可视链接。
 *
 * 扩展保留 TipTap Link 的自动识别、粘贴和安全校验行为，只增加 Markdown
 * 闭合语法的输入规则。
 */
export const MarkdownLinkExtension = LinkExtension.extend({
  addInputRules(): InputRule[] {
    return [
      ...(this.parent?.() ?? []),
      new InputRule({
        find: markdownLinkPattern,
        handler: ({ state, range, match }) => {
          const linkText = match[1];
          const rawHref = match[2];

          if (!linkText || !rawHref) {
            return null;
          }

          const linkMark = this.type.create({ href: normalizeLinkHref(rawHref) });

          state.tr.replaceWith(range.from, range.to, state.schema.text(linkText, [linkMark]));
          state.tr.removeStoredMark(this.type);
        },
      }),
    ];
  },
});

/**
 * 在第三行 GFM 表格的最后一个 `|` 输入后生成可编辑表格。
 *
 * 规则要求连续三个顶层段落分别为表头、分隔行和首个数据行，
 * 与用户手动输入 Markdown 表格的顺序一致。
 */
export const MarkdownTableInputExtension = Extension.create({
  name: 'markdownTableInput',

  addInputRules(): InputRule[] {
    return [
      new InputRule({
        find: completedMarkdownTableRowPattern,
        handler: ({ state, match, chain }) => {
          const { $from } = state.selection;

          if ($from.depth !== 1) {
            return null;
          }

          const blocks: TopLevelBlockSnapshot[] = [];

          state.doc.forEach((node, position) => {
            blocks.push({
              position,
              nodeSize: node.nodeSize,
              typeName: node.type.name,
              text: node.textContent,
            });
          });

          const currentPosition = $from.before(1);
          const currentIndex = blocks.findIndex(block => block.position === currentPosition);

          if (currentIndex < 2) {
            return null;
          }

          const headerBlock = blocks[currentIndex - 2];
          const separatorBlock = blocks[currentIndex - 1];
          const currentBlock = blocks[currentIndex];

          if (
            headerBlock.typeName !== 'paragraph' ||
            separatorBlock.typeName !== 'paragraph' ||
            currentBlock.typeName !== 'paragraph'
          ) {
            return null;
          }

          const rows = parseCompletedMarkdownTable([
            headerBlock.text,
            separatorBlock.text,
            match[0].trim(),
          ]);

          if (!rows) {
            return null;
          }

          const tableContent = createTableContent(rows);
          const replacementEnd = currentBlock.position + currentBlock.nodeSize;

          chain()
            .deleteRange({ from: headerBlock.position, to: replacementEnd })
            .insertContentAt(headerBlock.position, tableContent)
            .run();
        },
      }),
    ];
  },
});

/**
 * 解析已完成的三行 GFM 表格。
 *
 * @param lines 依次为表头、分隔行和数据行的文本。
 * @returns 表头与数据行的单元格文本；语法或列数不合法时返回 null。
 */
function parseCompletedMarkdownTable(lines: [string, string, string]): string[][] | null {
  const headerCells = parseMarkdownTableRow(lines[0]);
  const separatorCells = parseMarkdownTableRow(lines[1]);
  const bodyCells = parseMarkdownTableRow(lines[2]);

  if (!headerCells || !separatorCells || !bodyCells) {
    return null;
  }

  const columnCount = headerCells.length;

  if (
    columnCount < 1 ||
    columnCount > 100 ||
    separatorCells.length !== columnCount ||
    bodyCells.length !== columnCount ||
    separatorCells.some(cell => !markdownTableSeparatorPattern.test(cell))
  ) {
    return null;
  }

  return [headerCells, bodyCells];
}

/**
 * 按未转义的管道字符切分一行 Markdown 表格。
 *
 * @param row 必须以 `|` 开始并以 `|` 结束的表格行。
 * @returns 去除单元格首尾空白的数组；格式不完整时返回 null。
 */
function parseMarkdownTableRow(row: string): string[] | null {
  const trimmedRow = row.trim();

  if (!trimmedRow.startsWith('|') || !trimmedRow.endsWith('|')) {
    return null;
  }

  const cells: string[] = [];
  let currentCell = '';
  let escaped = false;

  for (const character of trimmedRow.slice(1, -1)) {
    if (escaped) {
      currentCell += character;
      escaped = false;
      continue;
    }

    if (character === '\\') {
      escaped = true;
      continue;
    }

    if (character === '|') {
      cells.push(currentCell.trim());
      currentCell = '';
      continue;
    }

    currentCell += character;
  }

  if (escaped) {
    currentCell += '\\';
  }

  cells.push(currentCell.trim());
  return cells;
}

/**
 * 将表格文本转为 TipTap 可直接插入的 JSON 结构。
 *
 * @param rows 第一项为表头，其余项为普通数据行。
 * @returns 包含 table、tableRow、tableHeader 和 tableCell 节点的 TipTap 内容。
 */
function createTableContent(rows: string[][]): JSONContent {
  return {
    type: 'table',
    content: rows.map((row, rowIndex) => ({
      type: 'tableRow',
      content: row.map(cell => ({
        type: rowIndex === 0 ? 'tableHeader' : 'tableCell',
        content: [
          {
            type: 'paragraph',
            content: createInlineContent(cell),
          },
        ],
      })),
    })),
  };
}

/**
 * 把单元格中的 Markdown 链接转为 TipTap link mark，其余内容保留为文本。
 *
 * @param value 单元格文本。
 * @returns TipTap 行内内容；空单元格返回 undefined。
 */
function createInlineContent(value: string): JSONContent[] | undefined {
  if (!value) {
    return undefined;
  }

  const content: JSONContent[] = [];
  const linkPattern = /\[([^\]\n]+)\]\(([^\s()]+)\)/g;
  let currentIndex = 0;

  for (const match of value.matchAll(linkPattern)) {
    const matchIndex = match.index;
    const linkText = match[1];
    const rawHref = match[2];

    if (matchIndex > currentIndex) {
      content.push({ type: 'text', text: value.slice(currentIndex, matchIndex) });
    }

    if (linkText && rawHref) {
      content.push({
        type: 'text',
        text: linkText,
        marks: [{ type: 'link', attrs: { href: normalizeLinkHref(rawHref) } }],
      });
    }

    currentIndex = matchIndex + match[0].length;
  }

  if (currentIndex < value.length) {
    content.push({ type: 'text', text: value.slice(currentIndex) });
  }

  return content.length > 0 ? content : [{ type: 'text', text: value }];
}

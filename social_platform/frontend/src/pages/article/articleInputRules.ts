/**
 * 文章编辑器的 Markdown 所见即所得输入规则。
 *
 * 上游由文章编辑页注册到 TipTap，下游在用户输入完整的强调、链接或
 * GFM 表格的最后一个闭合字符时，将 Markdown 源文本替换为可编辑的
 * TipTap mark 或结构化节点。
 */

import {
  Extension,
  InputRule,
  PasteRule,
  type JSONContent,
  type PasteRuleMatch,
} from '@tiptap/core';
import { Bold as BoldExtension } from '@tiptap/extension-bold';
import { Italic as ItalicExtension } from '@tiptap/extension-italic';
import LinkExtension from '@tiptap/extension-link';
import { normalizeLinkHref } from '@/shared/lib/externalRedirect';

const markdownLinkPattern = /\[([^\]\n]+)\]\(([^\s()]+)\)$/;
const completedMarkdownTableRowPattern = /^\s*\|.*\|\s*$/;
const markdownTableSeparatorPattern = /^:?-{3,}:?$/;

type MarkdownEmphasisMarkName = 'bold' | 'italic';

interface MarkdownEmphasisRuleConfig {
  inputPattern: RegExp;
  pastePattern: RegExp;
  delimiterLength: number;
  markNames: readonly MarkdownEmphasisMarkName[];
}

type MarkdownInputRuleHandlerProps = Parameters<InputRule['handler']>[0];

const markdownEmphasisRules: readonly MarkdownEmphasisRuleConfig[] = [
  {
    inputPattern: /(?<![\\*])\*\*\*(?!\s)([^*\n]+?)(?<!\s)\*\*\*$/,
    pastePattern: /(?<![\\*])\*\*\*(?!\s)([^*\n]+?)(?<!\s)\*\*\*(?!\*)/g,
    delimiterLength: 3,
    markNames: ['bold', 'italic'],
  },
  {
    inputPattern: /(?<![\\_])___(?!\s)([^_\n]+?)(?<!\s)___$/,
    pastePattern: /(?<![\\_])___(?!\s)([^_\n]+?)(?<!\s)___(?!_)/g,
    delimiterLength: 3,
    markNames: ['bold', 'italic'],
  },
  {
    inputPattern: /(?<![\\*])\*\*(?!\s)([^*\n]+?)(?<!\s)\*\*$/,
    pastePattern: /(?<![\\*])\*\*(?!\s)([^*\n]+?)(?<!\s)\*\*(?!\*)/g,
    delimiterLength: 2,
    markNames: ['bold'],
  },
  {
    inputPattern: /(?<![\\_])__(?!\s)([^_\n]+?)(?<!\s)__$/,
    pastePattern: /(?<![\\_])__(?!\s)([^_\n]+?)(?<!\s)__(?!_)/g,
    delimiterLength: 2,
    markNames: ['bold'],
  },
  {
    inputPattern: /(?<![\\*])\*(?!\s)([^*\n]+?)(?<!\s)\*$/,
    pastePattern: /(?<![\\*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\*)/g,
    delimiterLength: 1,
    markNames: ['italic'],
  },
  {
    inputPattern: /(?<![\\_])_(?!\s)([^_\n]+?)(?<!\s)_$/,
    pastePattern: /(?<![\\_])_(?!\s)([^_\n]+?)(?<!\s)_(?!_)/g,
    delimiterLength: 1,
    markNames: ['italic'],
  },
];

interface TopLevelBlockSnapshot {
  position: number;
  nodeSize: number;
  typeName: string;
  text: string;
}

/**
 * 保留 TipTap 粗体 mark、命令与快捷键，但关闭其边界不一致的内置 Markdown 规则。
 *
 * 强调语法的键入与粘贴统一交给 `MarkdownEmphasisExtension` 处理。
 */
export const MarkdownBoldMarkExtension = BoldExtension.extend({
  addInputRules(): InputRule[] {
    return [];
  },

  addPasteRules(): PasteRule[] {
    return [];
  },
});

/**
 * 保留 TipTap 斜体 mark、命令与快捷键，但关闭其边界不一致的内置 Markdown 规则。
 *
 * 强调语法的键入与粘贴统一交给 `MarkdownEmphasisExtension` 处理。
 */
export const MarkdownItalicMarkExtension = ItalicExtension.extend({
  addInputRules(): InputRule[] {
    return [];
  },

  addPasteRules(): PasteRule[] {
    return [];
  },
});

/**
 * 统一处理 Markdown 星号与下划线强调语法。
 *
 * 覆盖斜体、粗体与斜粗体的六种写法，并允许开始标签紧邻普通文字或标点。
 * 较高优先级确保强调转换先于其他可能读取同一输入事务的扩展执行。
 */
export const MarkdownEmphasisExtension = Extension.create({
  name: 'markdownEmphasis',
  priority: 110,

  addInputRules(): InputRule[] {
    return markdownEmphasisRules.map(config => createMarkdownEmphasisInputRule(config));
  },

  addPasteRules(): PasteRule[] {
    return [createMarkdownEmphasisPasteRule()];
  },
});

/**
 * 为一类 Markdown 强调语法创建逐字输入规则。
 *
 * @param config 分隔符、匹配表达式及目标 mark 配置。
 * @returns 在闭合分隔符输入完成后移除源码标签并应用 mark 的 TipTap 输入规则。
 */
function createMarkdownEmphasisInputRule(config: MarkdownEmphasisRuleConfig): InputRule {
  return new InputRule({
    find: config.inputPattern,
    handler: context => applyMarkdownEmphasis(context, config),
  });
}

/**
 * 为全部 Markdown 强调语法创建统一的粘贴规则。
 *
 * @returns 将粘贴进来的 Markdown 强调源码转换为可编辑 mark 的 TipTap 粘贴规则。
 */
function createMarkdownEmphasisPasteRule(): PasteRule {
  return new PasteRule({
    find: findMarkdownEmphasisPasteMatches,
    handler: context => {
      const ruleIndex = context.match.data?.ruleIndex;

      if (typeof ruleIndex !== 'number') {
        return null;
      }

      const config = markdownEmphasisRules[ruleIndex];
      return config ? applyMarkdownEmphasis(context, config) : null;
    },
  });
}

/**
 * 一次扫描粘贴文本中的全部强调写法，避免多条粘贴插件重复处理同一事务。
 *
 * @param text 用户粘贴进编辑器的纯文本。
 * @returns 按源码位置排序的 TipTap 粘贴匹配及其规则索引。
 */
function findMarkdownEmphasisPasteMatches(text: string): PasteRuleMatch[] {
  const matches: PasteRuleMatch[] = [];

  markdownEmphasisRules.forEach((config, ruleIndex) => {
    for (const match of text.matchAll(config.pastePattern)) {
      const content = match[1];

      if (match.index === undefined || !content) {
        continue;
      }

      matches.push({
        text: match[0],
        index: match.index,
        replaceWith: content,
        data: { ruleIndex },
      });
    }
  });

  return matches.sort((first, second) => first.index - second.index);
}

/**
 * 删除 Markdown 强调分隔符，并为其中的正文应用一个或多个 TipTap mark。
 *
 * @param context 当前输入或粘贴规则的文档状态、匹配范围与捕获内容。
 * @param config 分隔符长度及要应用的 mark 名称。
 * @returns mark 不存在或捕获内容为空时返回 null，否则直接更新当前事务。
 */
function applyMarkdownEmphasis(
  context: Pick<MarkdownInputRuleHandlerProps, 'state' | 'range' | 'match'>,
  config: MarkdownEmphasisRuleConfig
): void | null {
  const { state, range, match } = context;
  const content = match[1];
  const marks = config.markNames.map(markName => state.schema.marks[markName]);

  if (!content || marks.some(mark => !mark)) {
    return null;
  }

  const contentStart = range.from + config.delimiterLength;
  const contentEnd = contentStart + content.length;
  const markEnd = range.from + content.length;

  state.tr.delete(contentEnd, range.to);
  state.tr.delete(range.from, contentStart);

  marks.forEach(mark => {
    if (!mark) return;

    state.tr.addMark(range.from, markEnd, mark.create());
  });

  state.tr.setStoredMarks([]);
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

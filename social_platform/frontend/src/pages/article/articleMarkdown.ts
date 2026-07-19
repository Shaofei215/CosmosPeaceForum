/**
 * 文章富文本与 Markdown 之间的转换工具。
 *
 * 上游由文章编辑页在内容更新和发布时调用，下游保持后端现有
 * Markdown 字符串存储契约。表格需要单独转换，因为 Turndown 默认不输出
 * GitHub Flavored Markdown 表格语法。
 */

import TurndownService from 'turndown';

const markdownConverter = new TurndownService({
  bulletListMarker: '-',
  codeBlockStyle: 'fenced',
  emDelimiter: '*',
  headingStyle: 'atx',
});

/**
 * 将 TipTap 产生的 HTML 转为平台存储的 Markdown。
 *
 * @param html 当前编辑器的 HTML 内容。
 * @returns 规范化后的 Markdown 字符串。
 */
export function editorHtmlToMarkdown(html: string): string {
  if (typeof DOMParser === 'undefined' || !html.toLowerCase().includes('<table')) {
    return normalizeMarkdown(markdownConverter.turndown(html));
  }

  const document = new DOMParser().parseFromString(html, 'text/html');
  const serializedTables = new Map<string, string>();

  document.querySelectorAll('table').forEach((table, index) => {
    const markerText = `CPFTABLEPLACEHOLDER${index}END`;
    const marker = document.createElement('p');

    marker.textContent = markerText;
    serializedTables.set(markerText, serializeMarkdownTable(table));
    table.replaceWith(marker);
  });

  let markdown = markdownConverter.turndown(document.body.innerHTML);

  serializedTables.forEach((tableMarkdown, marker) => {
    markdown = markdown.replace(marker, tableMarkdown);
  });

  return normalizeMarkdown(markdown);
}

/**
 * 将 HTML 表格序列化为 GFM 表格。
 *
 * Markdown 表格必须有表头；对于粘贴进来的无表头 HTML 表格，使用第一行
 * 作为表头，避免在发布时丢失表格结构。
 *
 * @param table 待转换的 HTML 表格。
 * @returns GFM 表格 Markdown；空表格返回空字符串。
 */
function serializeMarkdownTable(table: HTMLTableElement): string {
  const rows = Array.from(table.rows);

  if (rows.length === 0) {
    return '';
  }

  const columnCount = Math.max(...rows.map(row => row.cells.length));

  if (columnCount === 0) {
    return '';
  }

  const serializedRows = rows.map(row => {
    const cells = Array.from(row.cells, cell => serializeTableCell(cell));

    while (cells.length < columnCount) {
      cells.push('');
    }

    return `| ${cells.join(' | ')} |`;
  });
  const separator = `| ${Array.from({ length: columnCount }, () => '---').join(' | ')} |`;

  return [serializedRows[0], separator, ...serializedRows.slice(1)].join('\n');
}

/**
 * 将单元格内容转为可安全放入 GFM 表格的单行 Markdown。
 *
 * @param cell 待转换的表头或普通单元格。
 * @returns 已转义管道字符并折叠换行的单元格内容。
 */
function serializeTableCell(cell: HTMLTableCellElement): string {
  return markdownConverter
    .turndown(cell.innerHTML)
    .trim()
    .replace(/\|/g, '\\|')
    .replace(/\n+/g, '<br>');
}

/**
 * 合并转换过程产生的过多空行，并清理首尾空白。
 *
 * @param markdown 待规范化的 Markdown。
 * @returns 最多保留一个空行的 Markdown。
 */
function normalizeMarkdown(markdown: string): string {
  return markdown.replace(/\n{3,}/g, '\n\n').trim();
}

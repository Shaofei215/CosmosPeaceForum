/**
 * 用户内容校验工具。
 *
 * 页面层会禁用空内容提交按钮；API 层再次调用本工具，防止快捷键、未来新增入口
 * 或直接调用 mutation 时把纯空白正文发送到后端。校验不会裁剪正文，因为 Markdown
 * 行首空格等内容可能具有实际语义。
 */

/** 匹配不会单独产生可见内容的空白、控制字符和 Unicode 格式字符。 */
const NON_VISIBLE_CONTENT_PATTERN = /[\s\p{Cc}\p{Cf}]/gu;

/**
 * 判断正文是否至少包含一个可见字符。
 *
 * @param content 待检查的用户正文。
 * @returns 包含可见字符时返回 true；仅含空白或不可见控制字符时返回 false。
 */
export function hasVisibleContent(content: string): boolean {
  return content.replace(NON_VISIBLE_CONTENT_PATTERN, '').length > 0;
}

/**
 * 将可选正文中的纯不可见输入转换为空值，同时保留有效正文原文。
 *
 * @param content 用户输入的可选正文。
 * @returns 有可见字符时返回原文，否则返回 undefined。
 */
export function toOptionalVisibleContent(content: string | undefined): string | undefined {
  return content !== undefined && hasVisibleContent(content) ? content : undefined;
}

/**
 * 校验必填正文，并原样返回通过校验的内容。
 *
 * @param content 用户输入的正文。
 * @param label 错误消息中的内容名称。
 * @returns 未经裁剪的原正文。
 * @throws {Error} 正文为空或只包含空白字符时抛出。
 */
export function validateRequiredContent(content: string, label = '内容'): string {
  if (!hasVisibleContent(content)) {
    throw new Error(`${label}不能为空`);
  }
  return content;
}

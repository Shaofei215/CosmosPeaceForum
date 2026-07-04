/**
 * 用户资料字段校验工具。
 *
 * 用户名是登录与提及标识，沿用稳定的字符白名单；签名允许更丰富的可见文本，
 * 但拒绝控制字符和可能用于隐藏、改写显示顺序的 Unicode 格式字符。
 */

import { hasVisibleContent } from '@/shared/lib/content';

/** 用户名允许中文、英文字母、数字和下划线。 */
const USERNAME_PATTERN = /^[a-zA-Z0-9_\u4e00-\u9fa5]+$/;

/** ZWNJ 和 ZWJ 可参与正常文字塑形及组合 emoji，不作为危险格式字符处理。 */
const ALLOWED_FORMAT_CHARACTERS = new Set(['\u200c', '\u200d']);

/** 匹配 ASCII/Unicode 控制字符。 */
const CONTROL_CHARACTER_PATTERN = /\p{Cc}/u;

/** 匹配 Unicode 格式字符，例如 U+200E 和双向文本控制符。 */
const FORMAT_CHARACTER_PATTERN = /\p{Cf}/u;

/**
 * 判断用户名是否符合公开平台的稳定标识规则。
 *
 * @param username 已去除首尾空白的用户名。
 * @returns 仅包含中文、英文字母、数字和下划线时返回 true。
 */
export function isValidUsername(username: string): boolean {
  return USERNAME_PATTERN.test(username);
}

/**
 * 判断签名是否包含不允许的控制字符或 Unicode 格式字符。
 *
 * @param content 待检查的签名文本。
 * @returns 包含危险字符时返回 true，否则返回 false。
 */
export function hasDisallowedProfileCharacters(content: string): boolean {
  return Array.from(content).some(character => {
    if (CONTROL_CHARACTER_PATTERN.test(character)) return true;
    return FORMAT_CHARACTER_PATTERN.test(character) && !ALLOWED_FORMAT_CHARACTERS.has(character);
  });
}

/**
 * 判断可选签名是否可以提交。
 *
 * 空字符串用于清除签名；非空签名必须包含可见内容，且不能包含危险控制字符。
 *
 * @param content 已去除首尾空白的签名文本。
 * @returns 签名为空或符合宽松资料文本规则时返回 true。
 */
export function isValidOptionalProfileText(content: string): boolean {
  return content === '' || (hasVisibleContent(content) && !hasDisallowedProfileCharacters(content));
}

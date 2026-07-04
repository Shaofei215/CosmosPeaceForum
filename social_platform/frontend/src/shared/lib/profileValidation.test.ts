/** 用户资料字段校验的回归测试，覆盖用户名白名单与签名控制字符策略。 */

import { describe, expect, it } from 'vitest';
import {
  hasDisallowedProfileCharacters,
  isValidOptionalProfileText,
  isValidUsername,
} from './profileValidation';

describe('profileValidation', () => {
  it('用户名仅允许中英文、数字和下划线', () => {
    expect(isValidUsername('Cosmos_和平2026')).toBe(true);
    expect(isValidUsername('Cosmos-Peace')).toBe(false);
    expect(isValidUsername('宇宙✨')).toBe(false);
  });

  it('签名允许多语言、空格、标点和 emoji', () => {
    expect(isValidOptionalProfileText('Peace שלום — 🌌')).toBe(true);
    expect(isValidOptionalProfileText('家庭 👨‍👩‍👧‍👦')).toBe(true);
  });

  it('签名拒绝纯不可见内容以及混入的 U+200E', () => {
    expect(isValidOptionalProfileText('\u200e')).toBe(false);
    expect(isValidOptionalProfileText('正常签名\u200e')).toBe(false);
  });

  it('签名拒绝控制字符，但允许正常文字塑形使用的 ZWNJ 和 ZWJ', () => {
    expect(hasDisallowedProfileCharacters('签名\u0000')).toBe(true);
    expect(hasDisallowedProfileCharacters('a\u200cb\u200dc')).toBe(false);
  });

  it('允许用空字符串清除签名', () => {
    expect(isValidOptionalProfileText('')).toBe(true);
  });
});

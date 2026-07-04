import { describe, expect, it } from 'vitest';
import { hasVisibleContent, toOptionalVisibleContent, validateRequiredContent } from './content';

describe('validateRequiredContent', () => {
  it('保留正文首尾空白', () => {
    expect(validateRequiredContent('  正文内容\n')).toBe('  正文内容\n');
  });

  it('拒绝只包含空白字符的正文', () => {
    expect(() => validateRequiredContent(' \n\t', '评论')).toThrow('评论不能为空');
  });

  it('拒绝只包含 Unicode 不可见格式字符的正文', () => {
    expect(hasVisibleContent('\u200e\u200e')).toBe(false);
    expect(() => validateRequiredContent('\u200e\u200e', '正文')).toThrow('正文不能为空');
  });

  it('保留可见正文中的格式字符', () => {
    expect(validateRequiredContent('\u200e正文\u200e')).toBe('\u200e正文\u200e');
  });

  it('将仅包含不可见字符的可选正文转换为空值', () => {
    expect(toOptionalVisibleContent('\u200e')).toBeUndefined();
    expect(toOptionalVisibleContent(' 正文 ')).toBe(' 正文 ');
  });
});

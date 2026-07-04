import { describe, expect, it } from 'vitest';
import { getApiErrorMessage } from './errorMessage';

describe('getApiErrorMessage', () => {
  it('隐藏 FastAPI 参数校验错误数组中的内部实现消息', () => {
    expect(
      getApiErrorMessage([
        {
          type: 'string_too_short',
          loc: ['body', 'password'],
          msg: 'String should have at least 6 characters',
          input: '12345',
        },
      ])
    ).toBe('请求参数有误，请检查后重试');
  });

  it('保留业务接口返回的字符串错误', () => {
    expect(getApiErrorMessage('邮箱或密码错误')).toBe('邮箱或密码错误');
  });

  it('无法识别错误结构时返回兜底消息', () => {
    expect(getApiErrorMessage({ unexpected: true }, '请求异常')).toBe('请求异常');
  });
});

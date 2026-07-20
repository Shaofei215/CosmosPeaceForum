import { describe, expect, it } from 'vitest';
import copywritingConfigRaw from '../../../../copywriting.yml?raw';
import {
  interpolateCopywriting,
  parseCopywritingConfig,
  readCopywritingValue,
} from './copywriting';

const frontendSourceModules = import.meta.glob<string>('/src/**/*.{ts,tsx}', {
  eager: true,
  import: 'default',
  query: '?raw',
});

describe('copywriting config', () => {
  it('reads nested string values', () => {
    const config = parseCopywritingConfig('search:\n  empty_results: 没有找到匹配结果。\n');

    expect(readCopywritingValue(config, 'search.empty_results')).toBe('没有找到匹配结果。');
  });

  it('falls back to an empty config for invalid YAML or a non-object root', () => {
    expect(parseCopywritingConfig('search: [')).toEqual({});
    expect(parseCopywritingConfig('- one\n- two')).toEqual({});
  });

  it('ignores missing and non-string values', () => {
    const config = parseCopywritingConfig('search:\n  empty_results: 42\n');

    expect(readCopywritingValue(config, 'search.empty_results')).toBeUndefined();
    expect(readCopywritingValue(config, 'search.missing')).toBeUndefined();
  });

  it('selects one configured sentence from a string list', () => {
    const config = parseCopywritingConfig(
      'search:\n  empty_results:\n    - 没有找到匹配结果。\n    - 前不见古人，后不见来者。\n'
    );

    expect(readCopywritingValue(config, 'search.empty_results', () => 0)).toBe(
      '没有找到匹配结果。'
    );
    expect(readCopywritingValue(config, 'search.empty_results', () => 0.99)).toBe(
      '前不见古人，后不见来者。'
    );
  });

  it('rejects empty lists and lists containing non-string values', () => {
    const emptyConfig = parseCopywritingConfig('search:\n  empty_results: []\n');
    const mixedConfig = parseCopywritingConfig(
      'search:\n  empty_results:\n    - 没有找到匹配结果。\n    - 42\n'
    );

    expect(readCopywritingValue(emptyConfig, 'search.empty_results')).toBeUndefined();
    expect(readCopywritingValue(mixedConfig, 'search.empty_results')).toBeUndefined();
  });

  it('interpolates known variables and preserves unknown placeholders', () => {
    expect(
      interpolateCopywriting('{username} 的帖子，共 {count} 条，{missing}', {
        username: '星河',
        count: 3,
      })
    ).toBe('星河 的帖子，共 3 条，{missing}');
  });

  it('keeps YAML fields and frontend copywriting calls in one-to-one sync', () => {
    const configKeys = collectStringFieldPaths(parseCopywritingConfig(copywritingConfigRaw));
    const usedKeys = new Set<string>();
    const callPattern = /copywriting\(\s*'([^']+)'/g;

    for (const source of Object.values(frontendSourceModules)) {
      for (const match of source.matchAll(callPattern)) {
        usedKeys.add(match[1]);
      }
    }

    expect([...usedKeys].filter(key => !configKeys.has(key)).sort()).toEqual([]);
    expect([...configKeys].filter(key => !usedKeys.has(key)).sort()).toEqual([]);
  });
});

/**
 * 收集 YAML 配置树中所有字符串叶子字段的点分路径。
 *
 * @param value 当前配置节点。
 * @param prefix 当前节点的字段路径。
 * @returns 当前节点下所有可用文案字段路径。
 */
function collectStringFieldPaths(value: unknown, prefix = ''): Set<string> {
  const paths = new Set<string>();
  if (typeof value === 'string') {
    if (prefix) paths.add(prefix);
    return paths;
  }
  if (Array.isArray(value)) {
    if (prefix && value.length > 0 && value.every(item => typeof item === 'string')) {
      paths.add(prefix);
    }
    return paths;
  }
  if (typeof value !== 'object' || value === null) {
    return paths;
  }

  for (const [key, child] of Object.entries(value)) {
    const childPrefix = prefix ? `${prefix}.${key}` : key;
    for (const childPath of collectStringFieldPaths(child, childPrefix)) {
      paths.add(childPath);
    }
  }
  return paths;
}

/**
 * 公开平台界面文案配置。
 *
 * 该模块在前端构建时读取 ``social_platform/copywriting.yml``。业务代码调用
 * ``copywriting`` 时同时提供内置默认文案，因此配置缺项、字段类型错误或整个
 * YAML 无法解析时，页面仍能使用代码中的默认值正常展示。单项配置既可以是
 * 字符串，也可以是字符串列表；列表会在本次页面加载期间随机选择并稳定展示。
 */

import { parse } from 'yaml';
import copywritingConfigRaw from '../../../../copywriting.yml?raw';

type CopywritingVariables = Record<string, string | number>;

/** YAML 解析后的未知配置树。 */
export type CopywritingConfig = Record<string, unknown>;

const configuredCopywriting = parseCopywritingConfig(copywritingConfigRaw);
const selectedCopywriting = new Map<string, string>();

/**
 * 读取一项可配置界面文案，并替换 ``{name}`` 形式的变量。
 *
 * @param key 以点分隔的 YAML 字段路径，例如 ``search.empty_results``。
 * @param fallback 配置不可用时使用的代码默认值。
 * @param variables 可选插值变量；未提供的占位符会原样保留，便于发现配置错误。
 * @returns 配置文案或默认文案完成插值后的文本。
 */
export function copywriting(
  key: string,
  fallback: string,
  variables: CopywritingVariables = {}
): string {
  const hasSelectedValue = selectedCopywriting.has(key);
  const configured = hasSelectedValue
    ? selectedCopywriting.get(key)
    : readCopywritingValue(configuredCopywriting, key);
  if (!hasSelectedValue && configured !== undefined) {
    selectedCopywriting.set(key, configured);
  }
  return interpolateCopywriting(configured ?? fallback, variables);
}

/**
 * 解析 YAML 文案配置。
 *
 * @param raw YAML 原始文本。
 * @returns 对象形式的配置；无效、空白或非对象根节点回退为空对象。
 */
export function parseCopywritingConfig(raw: string): CopywritingConfig {
  try {
    const parsed: unknown = parse(raw);
    return isPlainObject(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

/**
 * 从配置树读取字符串或随机候选字段。
 *
 * @param config 已解析的配置树。
 * @param key 点分隔字段路径。
 * @param random 随机数生成函数，测试时可传入固定结果。
 * @returns 字符串配置或从字符串列表随机选中的一项；缺失、空列表或类型错误时返回 undefined。
 */
export function readCopywritingValue(
  config: CopywritingConfig,
  key: string,
  random: () => number = Math.random
): string | undefined {
  const segments = key.split('.').filter(Boolean);
  let current: unknown = config;

  for (const segment of segments) {
    if (!isPlainObject(current) || !(segment in current)) {
      return undefined;
    }
    current = current[segment];
  }

  if (typeof current === 'string') {
    return current;
  }
  if (!Array.isArray(current) || !current.every(value => typeof value === 'string')) {
    return undefined;
  }
  if (current.length === 0) {
    return undefined;
  }

  const sampledValue = random();
  const normalizedValue = Number.isFinite(sampledValue)
    ? Math.max(0, Math.min(0.9999999999999999, sampledValue))
    : 0;
  return current[Math.floor(normalizedValue * current.length)];
}

/**
 * 替换文案中的命名占位符。
 *
 * @param template 文案模板。
 * @param variables 插值变量。
 * @returns 完成安全字符串替换后的文案。
 */
export function interpolateCopywriting(template: string, variables: CopywritingVariables): string {
  return template.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (placeholder, name: string) => {
    const value = variables[name];
    return value === undefined ? placeholder : String(value);
  });
}

/** 判断未知值是否为可按字段读取的普通对象。 */
function isPlainObject(value: unknown): value is CopywritingConfig {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * 左侧页脚配置解析。
 *
 * 该模块在前端构建时读取 social_platform/footer.yml，并将部署实例可编辑配置
 * 合并为组件可直接消费的结构。开源项目署名不从 YAML 读取，避免被实例配置误改。
 */

import { parse } from 'yaml';
import { z } from 'zod';
import footerConfigRaw from '../../../../footer.yml?raw';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';

export interface FooterLink {
  label: string;
  href: string;
  external: boolean;
}

export interface SidebarFooterConfig {
  copyright: {
    enabled: boolean;
    text: string;
  };
  links: FooterLink[];
}

const footerLinkSchema = z.object({
  label: z.string().trim().min(1),
  href: z.string().trim().min(1),
  external: z.boolean().optional(),
});

const footerConfigSchema = z.object({
  copyright: z
    .object({
      enabled: z.boolean().optional(),
      text: z.string().optional(),
    })
    .optional(),
  links: z.array(footerLinkSchema).optional(),
});

const parsedFooterConfig = footerConfigSchema.safeParse(parseFooterYaml(footerConfigRaw));

export const SIDEBAR_FOOTER_CONFIG: SidebarFooterConfig = normalizeFooterConfig(
  parsedFooterConfig.success ? parsedFooterConfig.data : {}
);

/**
 * 解析 YAML 文本。
 *
 * @param raw YAML 原始内容。
 * @returns YAML 对象；空文件或解析失败时返回空对象。
 */
function parseFooterYaml(raw: string): unknown {
  try {
    return parse(raw) ?? {};
  } catch {
    return {};
  }
}

/**
 * 将可选配置补齐为组件使用的稳定结构。
 *
 * @param config 已通过 schema 校验的页脚配置。
 * @returns 补齐默认版权与链接外链标记后的配置。
 */
function normalizeFooterConfig(config: z.infer<typeof footerConfigSchema>): SidebarFooterConfig {
  const currentYear = new Date().getFullYear();
  const configuredCopyright = config.copyright?.text?.trim();

  return {
    copyright: {
      enabled: config.copyright?.enabled ?? true,
      text: configuredCopyright || `© ${currentYear} ${PLATFORM_DISPLAY_NAME}`,
    },
    links:
      config.links?.map(link => ({
        label: link.label,
        href: link.href,
        external: link.external ?? isExternalHref(link.href),
      })) ?? [],
  };
}

/**
 * 判断链接是否需要按外链处理。
 *
 * @param href 链接地址。
 * @returns http、https 与 mailto 链接返回 true。
 */
function isExternalHref(href: string): boolean {
  return /^(https?:|mailto:)/i.test(href);
}

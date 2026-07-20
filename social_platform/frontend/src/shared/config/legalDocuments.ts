/**
 * 公开协议文档元数据。
 *
 * 路由页与侧栏页脚共用这里的文档标题和路径，避免协议入口文案分散维护。
 */

export type LegalDocumentSlug = 'privacy-policy' | 'terms-of-service' | 'community-guidelines';

export interface LegalDocumentLink {
  slug: LegalDocumentSlug;
  title: string;
  href: string;
}

export const LEGAL_DOCUMENT_LINKS: LegalDocumentLink[] = [
  {
    slug: 'terms-of-service',
    title: copywriting('legal.terms', '服务条款'),
    href: '/legal/terms-of-service',
  },
  {
    slug: 'privacy-policy',
    title: copywriting('legal.privacy', '隐私政策'),
    href: '/legal/privacy-policy',
  },
  {
    slug: 'community-guidelines',
    title: copywriting('legal.guidelines', '社区规范'),
    href: '/legal/community-guidelines',
  },
];

/**
 * 判断路由参数是否为已登记的协议文档标识。
 *
 * @param value 待检查的路由参数。
 * @returns 参数可用于读取协议文档时返回 true。
 */
export function isLegalDocumentSlug(value: string | undefined): value is LegalDocumentSlug {
  return value !== undefined && LEGAL_DOCUMENT_LINKS.some(document => document.slug === value);
}
import { copywriting } from '@/shared/config/copywriting';

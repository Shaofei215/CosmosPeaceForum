/**
 * 协议文档展示页。
 *
 * 从平台级 Markdown 协议文档读取公开协议，并在中栏复用站内 Markdown 渲染逻辑展示。
 */

import type { ReactElement } from 'react';
import { Link, useParams } from 'react-router-dom';
import communityGuidelinesContent from '../../../../license/community-guidelines.md?raw';
import privacyPolicyContent from '../../../../license/privacy-policy.md?raw';
import termsOfServiceContent from '../../../../license/terms-of-service.md?raw';
import { MarkdownRenderer } from '@/shared/components/markdown/MarkdownRenderer';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';

type LegalDocumentSlug = 'privacy-policy' | 'terms-of-service' | 'community-guidelines';

interface LegalDocument {
  title: string;
  content: string;
}

const PLATFORM_NAME_TOKEN = '{{PLATFORM_NAME}}';

const LEGAL_DOCUMENTS: Record<LegalDocumentSlug, LegalDocument> = {
  'privacy-policy': {
    title: '隐私政策',
    content: privacyPolicyContent,
  },
  'terms-of-service': {
    title: '服务条款',
    content: termsOfServiceContent,
  },
  'community-guidelines': {
    title: '社区规范',
    content: communityGuidelinesContent,
  },
};

/**
 * 根据路由参数渲染对应协议文档。
 *
 * @returns 协议文档页面；未知文档标识时展示轻量错误状态。
 */
export default function LegalDocumentPage(): ReactElement {
  const { documentSlug } = useParams<{ documentSlug: string }>();
  const legalDocument = isLegalDocumentSlug(documentSlug)
    ? LEGAL_DOCUMENTS[documentSlug]
    : undefined;

  if (!legalDocument) {
    return (
      <section className="rounded-lg bg-white p-6 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-foreground">协议不存在</h1>
        <p className="mt-2 text-sm text-muted-foreground">请从注册页或站内链接访问有效协议。</p>
        <Link
          className="mt-4 inline-flex text-sm font-medium text-sky-600 hover:text-sky-700"
          to="/feed"
        >
          返回主页
        </Link>
      </section>
    );
  }

  const renderedContent = legalDocument.content
    .split(PLATFORM_NAME_TOKEN)
    .join(PLATFORM_DISPLAY_NAME);

  return (
    <article className="rounded-lg bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-5 border-b border-border/70 pb-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Legal</p>
        <h1 className="mt-1 text-2xl font-semibold text-foreground">{legalDocument.title}</h1>
      </div>
      <MarkdownRenderer content={renderedContent} />
    </article>
  );
}

/**
 * 判断路由参数是否为已登记的协议文档标识。
 *
 * @param value 待检查的路由参数。
 * @returns 参数可用于读取协议文档时返回 true。
 */
function isLegalDocumentSlug(value: string | undefined): value is LegalDocumentSlug {
  return value !== undefined && value in LEGAL_DOCUMENTS;
}

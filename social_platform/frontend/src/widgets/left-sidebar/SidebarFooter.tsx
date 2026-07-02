/**
 * 公开平台页脚组件。
 *
 * 供桌面左侧栏与移动端页面底部复用，展示实例可配置页脚链接、固定协议入口，
 * 以及 CosmosPeaceForum 开源项目署名。
 */

import type { ReactElement } from 'react';
import { Link } from 'react-router-dom';
import { SIDEBAR_FOOTER_CONFIG, type FooterLink } from '@/shared/config/footer';
import { LEGAL_DOCUMENT_LINKS } from '@/shared/config/legalDocuments';
import { buildExternalRedirectUrl, isExternalHttpUrl } from '@/shared/lib/externalRedirect';
import { cn } from '@/shared/lib/utils';

const COSMOS_PEACE_FORUM_REPOSITORY_URL = 'https://github.com/Shaofei215/CosmosPeaceForum';
const COSMOS_PEACE_FORUM_POWERED_BY_LOGO_PATH =
  '/src/shared/assets/cosmos-peace-forum-powered-by.png';
const COSMOS_PEACE_FORUM_POWERED_BY_LOGOS = import.meta.glob<string>(
  '/src/shared/assets/cosmos-peace-forum-powered-by.png',
  {
    eager: true,
    import: 'default',
    query: '?url',
  }
);
const COSMOS_PEACE_FORUM_POWERED_BY_LOGO_SRC =
  COSMOS_PEACE_FORUM_POWERED_BY_LOGOS[COSMOS_PEACE_FORUM_POWERED_BY_LOGO_PATH];

/**
 * 渲染公开平台通用页脚。
 *
 * @returns 可在桌面侧栏或移动端页面底部展示的页脚元素。
 */
export function SidebarFooter(): ReactElement {
  const { copyright, links } = SIDEBAR_FOOTER_CONFIG;

  return (
    <footer className="flex flex-col gap-2 text-xs text-muted-foreground">
      {copyright.enabled && <p className="leading-5">{copyright.text}</p>}

      <nav aria-label="页脚链接" className="flex flex-wrap gap-x-3 gap-y-1">
        <Link to="/agent-access" className="transition-colors hover:text-primary hover:underline">
          接入自己的 Agent
        </Link>
        {links.map(link => (
          <FooterNavLink key={`${link.label}-${link.href}`} link={link} />
        ))}
      </nav>

      <nav aria-label="协议链接" className="flex flex-wrap gap-x-3 gap-y-1">
        {LEGAL_DOCUMENT_LINKS.map(document => (
          <Link
            key={document.slug}
            to={document.href}
            className="transition-colors hover:text-primary hover:underline"
          >
            {document.title}
          </Link>
        ))}
      </nav>

      {COSMOS_PEACE_FORUM_POWERED_BY_LOGO_SRC && (
        <div className="flex flex-col gap-2">
          <p className="text-[11px] uppercase leading-none tracking-wide text-muted-foreground/80">
            Powered by
          </p>
          <Link
            to={buildExternalRedirectUrl(COSMOS_PEACE_FORUM_REPOSITORY_URL)}
            aria-label="打开 CosmosPeaceForum 开源项目仓库"
            className="inline-flex"
          >
            <img
              src={COSMOS_PEACE_FORUM_POWERED_BY_LOGO_SRC}
              alt="Powered by CosmosPeaceForum"
              className="h-auto w-40"
            />
          </Link>
        </div>
      )}
    </footer>
  );
}

/**
 * 渲染可配置的页脚链接。
 *
 * @param props.link 链接配置。
 * @returns 内链或外链元素。
 */
function FooterNavLink({ link }: { link: FooterLink }): ReactElement {
  const className = cn('transition-colors hover:text-primary hover:underline');

  if (link.external) {
    if (!isExternalHttpUrl(link.href)) {
      return (
        <a href={link.href} className={className}>
          {link.label}
        </a>
      );
    }

    return (
      <Link to={buildExternalRedirectUrl(link.href)} className={className}>
        {link.label}
      </Link>
    );
  }

  return (
    <Link to={link.href} className={className}>
      {link.label}
    </Link>
  );
}

/**
 * 外部链接跳转确认页。
 *
 * 作为用户离开公开平台前的中间页：上游由站内外链组件传入目标地址，
 * 下游在用户确认后跳转到原始外部地址。
 */

import type { ReactElement } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { BigLogo } from '@/shared/components/auth/BigLogo';
import { Button } from '@/shared/components/ui';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import { getExternalRedirectTarget } from '@/shared/lib/externalRedirect';
import { copywriting } from '@/shared/config/copywriting';

/**
 * 渲染离站确认页。
 *
 * @returns 外部链接确认页面元素。
 */
export default function ExternalRedirectPage(): ReactElement {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const targetUrl = getExternalRedirectTarget(searchParams);

  /**
   * 返回外链确认页的来源页面。
   */
  const goBack = (): void => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }

    navigate('/feed');
  };

  return (
    <main className="flex min-h-screen items-start justify-center bg-background px-4 py-10 sm:py-16">
      <section className="flex w-full max-w-2xl flex-col items-center text-center">
        <BigLogo className="mb-8 h-auto w-40 max-w-[70vw] sm:w-52" />

        <div className="w-full space-y-6">
          <div className="space-y-3">
            <h1 className="text-2xl font-semibold text-foreground sm:text-3xl">
              {copywriting('external_redirect.title', '即将离开本站')}
            </h1>
            <p className="mx-auto max-w-xl text-sm leading-7 text-muted-foreground sm:text-base">
              {copywriting(
                'external_redirect.description',
                '您即将跳转到一个外部网站。该页面不属于{platform_name}，其内容、安全性与隐私政策由目标网站自行负责，请确认地址可信后再继续访问。',
                { platform_name: PLATFORM_DISPLAY_NAME }
              )}
            </p>
          </div>

          <div className="w-full rounded-lg border border-border bg-muted/40 px-4 py-4 text-left">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              {copywriting('external_redirect.original_url', '原地址')}
            </p>
            <p className="break-all font-mono text-sm leading-6 text-foreground">
              {targetUrl ??
                copywriting('external_redirect.invalid_url', '未提供有效的外部链接地址')}
            </p>
          </div>

          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            {targetUrl ? (
              <Button
                asChild
                className="w-28 rounded-md hover:bg-primary hover:text-primary-foreground hover:shadow-md"
              >
                <a href={targetUrl} rel="noreferrer">
                  {copywriting('external_redirect.confirm', '确认跳转')}
                </a>
              </Button>
            ) : null}
            <Button type="button" variant="outline" className="w-28 rounded-md" onClick={goBack}>
              {copywriting('common.back', '返回')}
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
}

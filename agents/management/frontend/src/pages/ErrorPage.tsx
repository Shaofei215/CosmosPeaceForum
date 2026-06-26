/**
 * 管理端全屏错误状态页。
 *
 * 用于未匹配路由等全局错误状态，保持与公开平台一致的品牌错误页视觉。
 */

import { BigLogo } from '@/shared/components/auth/BigLogo';

interface ErrorPageProps {
  /** 需要突出展示的错误码。 */
  code?: string;
  /** 与错误码同宽对齐的英文错误标题。 */
  title?: string;
}

/**
 * 展示带品牌标识的管理端错误状态。
 *
 * @param props.code 页面中央的大号错误码，默认展示 404。
 * @param props.title 错误码下方的英文标题，默认展示 Not Found。
 * @returns 可直接挂载到路由 element 的错误页。
 */
export default function ErrorPage({ code = '404', title = 'Not Found' }: ErrorPageProps) {
  const titleParts = title.split(' ');
  const firstTitlePart = titleParts[0] ?? title;
  const restTitle = titleParts.slice(1).join(' ');

  return (
    <main className="auth-page">
      <BigLogo className="mt-2" />

      <section
        className="flex flex-1 items-center justify-center pb-[12vh]"
        aria-labelledby="error-page-code"
      >
        <div className="w-max text-foreground">
          <h1
            id="error-page-code"
            className="text-[clamp(7rem,24vw,15rem)] font-black leading-none"
          >
            {code}
          </h1>
          <p className="mt-3 flex w-full justify-between text-[clamp(1.5rem,5vw,3.25rem)] font-semibold uppercase leading-none tracking-normal text-muted-foreground">
            <span>{firstTitlePart}</span>
            {restTitle && <span>{restTitle}</span>}
          </p>
        </div>
      </section>
    </main>
  );
}

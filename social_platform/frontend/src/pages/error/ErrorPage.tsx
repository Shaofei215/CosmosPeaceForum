/**
 * 公开平台全屏错误状态页。
 *
 * 用于未匹配路由和路由渲染异常等全局错误状态，统一错误提示与恢复入口。
 */

import type { ReactElement } from 'react';
import { useNavigate } from 'react-router-dom';
import { BigLogo } from '@/shared/components/auth/BigLogo';
import { Button } from '@/shared/components/ui';

interface ErrorPageProps {
  /** 需要突出展示的错误码。 */
  code?: string;
  /** 错误码下方的用户友好标题。 */
  title?: string;
  /** 标题下方的恢复操作提示。 */
  description?: string;
}

/**
 * 展示带品牌标识和恢复入口的公开平台全屏错误状态。
 *
 * @param props.code 页面中央的大号错误码，默认展示 404。
 * @param props.title 错误码下方的标题，默认展示“页面不存在”。
 * @param props.description 标题下方的提示文案。
 * @returns 可直接挂载到路由 element 的错误页。
 */
export default function ErrorPage({
  code = '404',
  title = '页面不存在',
  description = '发生了一些意外，请返回上页或主页继续浏览。',
}: ErrorPageProps): ReactElement {
  const navigate = useNavigate();

  /** 返回当前错误页面之前的浏览记录；没有可返回记录时回到主页。 */
  const goBack = (): void => {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }

    navigate('/feed', { replace: true });
  };

  /** 返回公开平台主页。 */
  const goHome = (): void => {
    navigate('/feed');
  };

  return (
    <main className="flex min-h-screen flex-col items-center overflow-hidden bg-background px-4 py-4">
      <BigLogo className="mt-2" />

      <section
        className="flex flex-1 items-center justify-center pb-[12vh]"
        aria-labelledby="error-page-title"
      >
        <div className="flex max-w-xl flex-col items-center text-center">
          <p
            className="text-[clamp(7rem,24vw,15rem)] font-black leading-none text-foreground"
            aria-hidden="true"
          >
            {code}
          </p>
          <h1 id="error-page-title" className="mt-4 text-2xl font-semibold text-foreground">
            {title}
          </h1>
          <p className="mt-3 text-sm text-muted-foreground sm:text-base">{description}</p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button type="button" className="w-28 rounded-md" onClick={goBack}>
              返回上页
            </Button>
            <Button type="button" variant="outline" className="w-28 rounded-md" onClick={goHome}>
              返回主页
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
}

/**
 * 公开平台路由异常页。
 *
 * 当页面组件在 React Router 渲染阶段发生未处理异常时，由路由层复用统一错误页，
 * 避免向普通用户暴露 React Router 的默认开发者提示与内部错误信息。
 */

import type { ReactElement } from 'react';
import ErrorPage from '@/pages/error/ErrorPage';

/**
 * 展示不包含内部异常详情的公开平台路由异常状态。
 *
 * @returns 可配置为 React Router `errorElement` 的全屏错误页。
 */
export default function RouteErrorPage(): ReactElement {
  return (
    <ErrorPage
      code="500"
      title="页面暂时无法显示"
      description="发生了一些意外，请返回上页或主页继续浏览。"
    />
  );
}

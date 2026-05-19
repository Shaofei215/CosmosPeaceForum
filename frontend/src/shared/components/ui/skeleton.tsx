/**
 * 骨架屏组件
 * 基础UI组件，用于加载状态占位
 */

import { cn } from '@/shared/lib/utils';

/**
 * 骨架屏组件属性
 */
interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

/**
 * 骨架屏组件
 *
 * @example
 * <Skeleton className="h-4 w-[250px]" />
 * <Skeleton className="h-12 w-12 rounded-full" />
 */
function Skeleton({ className, ...props }: SkeletonProps) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} {...props} />;
}

export { Skeleton };
export type { SkeletonProps };

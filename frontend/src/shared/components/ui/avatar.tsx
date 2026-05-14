/**
 * 头像组件
 * 基础UI组件，用于显示用户头像
 */

import * as React from 'react';
import { getFullAvatarUrl } from '@/shared/config/api';
import { cn } from '@/shared/lib/utils';

/**
 * 头像组件属性
 */
interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 头像图片URL */
  src?: string | null;
  /** 头像替代文本 */
  alt?: string;
  /** 头像尺寸 */
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
}

/**
 * 头像尺寸映射
 */
const sizeMap = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-12 h-12 text-base',
  xl: 'w-20 h-20 text-lg',
  '2xl': 'w-24 h-24 text-xl',
};

/**
 * 获取用户名的首字母作为头像占位符
 */
function getInitials(name: string): string {
  return name.charAt(0).toUpperCase();
}

/**
 * 生成随机背景色
 */
function getRandomColor(name: string): string {
  const colors = [
    'bg-red-500',
    'bg-orange-500',
    'bg-amber-500',
    'bg-green-500',
    'bg-emerald-500',
    'bg-teal-500',
    'bg-cyan-500',
    'bg-sky-500',
    'bg-blue-500',
    'bg-indigo-500',
    'bg-violet-500',
    'bg-purple-500',
    'bg-fuchsia-500',
    'bg-pink-500',
    'bg-rose-500',
  ];
  const index = name.charCodeAt(0) % colors.length;
  return colors[index];
}

/**
 * 头像组件
 *
 * @example
 * <Avatar src="/avatar.jpg" alt="用户名" />
 * <Avatar alt="用户名" size="lg" />
 * <Avatar src="/avatar.jpg" alt="用户名" size="sm" />
 */
const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, src, alt = '', size = 'md', ...props }, ref) => {
    const [error, setError] = React.useState(false);

    const fullSrc = getFullAvatarUrl(src);

    // 如果没有图片或加载失败，显示首字母占位符
    if (!fullSrc || error) {
      return (
        <div
          ref={ref}
          className={cn(
            'relative flex shrink-0 overflow-hidden rounded-full items-center justify-center text-white font-medium',
            sizeMap[size],
            getRandomColor(alt || 'A'),
            className
          )}
          {...props}
        >
          {getInitials(alt || '用户')}
        </div>
      );
    }

    return (
      <div
        ref={ref}
        className={cn(
          'relative flex shrink-0 overflow-hidden rounded-full',
          sizeMap[size],
          className
        )}
        {...props}
      >
        <img
          src={fullSrc}
          alt={alt}
          className="aspect-square h-full w-full object-cover"
          onError={() => setError(true)}
        />
      </div>
    );
  }
);
Avatar.displayName = 'Avatar';

export { Avatar };
export type { AvatarProps };

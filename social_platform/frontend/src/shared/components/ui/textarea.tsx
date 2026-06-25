/**
 * 文本域组件
 * 基础UI组件，用于多行文本输入
 */

import * as React from 'react';
import { cn } from '@/shared/lib/utils';

/**
 * 文本域组件属性
 */
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

/**
 * 文本域组件
 *
 * @example
 * <Textarea placeholder="请输入内容" />
 * <Textarea rows={5} placeholder="多行输入" />
 * <Textarea disabled placeholder="禁用状态" />
 */
const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-y',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Textarea.displayName = 'Textarea';

export { Textarea };

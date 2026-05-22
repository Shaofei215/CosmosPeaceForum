/**
 * 按钮组件
 * 基础UI组件，支持多种变体和尺寸
 */

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { buttonVariants, type ButtonVariantProps } from './buttonVariants';
import { cn } from '@/shared/lib/utils';

/**
 * 按钮组件属性
 */
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, ButtonVariantProps {
  /** 是否作为子元素渲染 */
  asChild?: boolean;
}

/**
 * 按钮组件
 *
 * @example
 * <Button>默认按钮</Button>
 * <Button variant="destructive">删除按钮</Button>
 * <Button size="sm">小按钮</Button>
 * <Button asChild><Link to="/">链接按钮</Link></Button>
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  }
);
Button.displayName = 'Button';

export { Button };

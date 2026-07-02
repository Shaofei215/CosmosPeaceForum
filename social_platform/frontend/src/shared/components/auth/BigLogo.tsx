import { useState } from 'react';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import { cn } from '@/shared/lib/utils';

/**
 * 渲染仅供认证页桌面分栏使用的背景插画。
 *
 * @returns 由认证页布局控制尺寸与裁切范围的装饰图片。
 */
export function AuthIllustration() {
  return (
    <div className="auth-illustration" aria-hidden="true">
      <img src="/background.png" alt="" />
    </div>
  );
}

export function BigLogo({ className }: { className?: string }) {
  const [src, setSrc] = useState('/biglogo.png');

  return (
    <img
      src={src}
      alt={PLATFORM_DISPLAY_NAME}
      className={cn('auth-big-logo', className)}
      onError={() => {
        if (src !== '/logo.png') {
          setSrc('/logo.png');
        }
      }}
    />
  );
}

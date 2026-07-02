import { BrandImage } from '@/shared/components/BrandImage';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import { cn } from '@/shared/lib/utils';

/**
 * 渲染仅供认证页桌面分栏使用的背景插画。
 *
 * @returns 由认证页布局控制尺寸与裁切范围的装饰图片。
 */
export function AuthIllustration() {
  return (
    <>
      <BrandImage name="background" alt="" className="auth-mobile-background" aria-hidden="true" />
      <div className="auth-illustration" aria-hidden="true">
        <BrandImage name="background" alt="" />
      </div>
    </>
  );
}

export function BigLogo({ className }: { className?: string }) {
  return (
    <BrandImage
      name="biglogo"
      fallbackNames={['logo']}
      alt={PLATFORM_DISPLAY_NAME}
      className={cn('auth-big-logo', className)}
    />
  );
}

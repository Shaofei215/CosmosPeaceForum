import { BrandImage } from '@/shared/components/BrandImage';
import { PLATFORM_DISPLAY_NAME } from '@/shared/config/branding';
import { cn } from '@/shared/lib/cn';

/**
 * 渲染认证页分栏布局使用的背景插画。
 *
 * @returns 由认证页布局控制尺寸与裁切范围的装饰图片。
 */
export function AuthIllustration() {
  return (
    <div className="auth-illustration" aria-hidden="true">
      <BrandImage name="background" alt="" />
    </div>
  );
}

export function BigLogo({ className }: { className?: string }) {
  return (
    <BrandImage
      name="banner"
      fallbackNames={['icon']}
      alt={PLATFORM_DISPLAY_NAME}
      className={cn('auth-big-logo', className)}
    />
  );
}

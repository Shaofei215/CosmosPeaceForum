/**
 * 品牌图片组件。
 *
 * 调用方只提供 public 目录中的文件名；组件按固定格式优先级寻找实际文件，
 * 使部署方无需修改代码即可替换不同格式的品牌资源。
 */

import { useState, type ImgHTMLAttributes } from 'react';
import { useTheme } from '@/features/theme';
import { buildBrandImageCandidates } from '@/shared/lib/brandImages';

interface BrandImageProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'onError'> {
  /** public 目录中的主文件名，不含扩展名。 */
  name: string;
  /** 主文件不存在时依次尝试的备用文件名，不含扩展名。 */
  fallbackNames?: readonly string[];
}

/**
 * 渲染随主题自动切换并匹配实际扩展名的品牌图片。
 *
 * @param props 图片属性、主文件名及可选备用文件名。
 * @returns 会在加载失败时自动尝试下一候选格式的 img 元素。
 */
export function BrandImage({ name, fallbackNames = [], ...props }: BrandImageProps) {
  const { resolvedTheme } = useTheme();
  const names = [name, ...fallbackNames];
  const candidates = buildBrandImageCandidates(names, resolvedTheme);

  return (
    <FallbackImage
      key={`${resolvedTheme}\0${names.join('\0')}`}
      candidates={candidates}
      {...props}
    />
  );
}

interface FallbackImageProps extends ImgHTMLAttributes<HTMLImageElement> {
  candidates: readonly string[];
}

/** 在图片加载失败时按既定优先级尝试下一候选资源。 */
function FallbackImage({ candidates, ...props }: FallbackImageProps) {
  const [candidateIndex, setCandidateIndex] = useState(0);

  return (
    <img
      {...props}
      src={candidates[candidateIndex]}
      onError={() => {
        setCandidateIndex((current) => Math.min(current + 1, candidates.length - 1));
      }}
    />
  );
}

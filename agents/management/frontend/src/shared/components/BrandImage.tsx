/**
 * 品牌图片组件。
 *
 * 调用方只提供 public 目录中的文件名；组件按固定格式优先级寻找实际文件，
 * 使部署方无需修改代码即可替换不同格式的品牌资源。
 */

import { useEffect, useState, type ImgHTMLAttributes } from 'react';

/** 品牌图片格式优先级；PNG 置于首位以保持现有部署行为。 */
const BRAND_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif'] as const;

interface BrandImageProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'onError'> {
  /** public 目录中的主文件名，不含扩展名。 */
  name: string;
  /** 主文件不存在时依次尝试的备用文件名，不含扩展名。 */
  fallbackNames?: readonly string[];
}

/**
 * 按文件名及格式优先级生成候选 URL。
 *
 * @param names public 目录中的文件名列表，均不含扩展名。
 * @returns 按文件名、PNG/JPG/JPEG/WebP/GIF 顺序排列的 URL。
 */
function buildBrandImageCandidates(names: readonly string[]): string[] {
  return names.flatMap((name) =>
    BRAND_IMAGE_EXTENSIONS.map((extension) => `/${name}.${extension}`),
  );
}

/**
 * 渲染自动匹配实际扩展名的品牌图片。
 *
 * @param props 图片属性、主文件名及可选备用文件名。
 * @returns 会在加载失败时自动尝试下一候选格式的 img 元素。
 */
export function BrandImage({ name, fallbackNames = [], ...props }: BrandImageProps) {
  const namesKey = [name, ...fallbackNames].join('\0');
  const candidates = buildBrandImageCandidates([name, ...fallbackNames]);
  const [candidateIndex, setCandidateIndex] = useState(0);

  useEffect(() => {
    setCandidateIndex(0);
  }, [namesKey]);

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

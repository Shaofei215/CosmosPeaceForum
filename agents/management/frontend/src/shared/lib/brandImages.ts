/** 品牌图片格式优先级；PNG 置于首位以保持现有部署行为。 */
export const BRAND_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif'] as const;

export type BrandImageTheme = 'light' | 'dark';

/**
 * 按主题、文件名回退顺序及格式优先级生成品牌图片候选 URL。
 *
 * 暗色模式会先尝试每个文件名的 ``_dark`` 变体，全部不可用后再尝试同名普通图片；
 * 随后才进入下一个备用文件名，确保 ``banner`` 仍优先于 ``icon``。
 *
 * @param names public 目录中的文件名列表，均不含扩展名。
 * @param theme 当前实际渲染主题。
 * @returns 按文件名与格式优先级排列的 URL。
 */
export function buildBrandImageCandidates(
  names: readonly string[],
  theme: BrandImageTheme,
): string[] {
  return names.flatMap((name) => {
    const themedNames = theme === 'dark' ? [`${name}_dark`, name] : [name];
    return themedNames.flatMap((themedName) =>
      BRAND_IMAGE_EXTENSIONS.map((extension) => `/${themedName}.${extension}`),
    );
  });
}

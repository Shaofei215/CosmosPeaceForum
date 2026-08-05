import { describe, expect, it } from 'vitest';
import { BRAND_IMAGE_EXTENSIONS, buildBrandImageCandidates } from './brandImages';

describe('buildBrandImageCandidates', () => {
  it('亮色主题沿用文件名优先、格式次之的既有顺序', () => {
    expect(buildBrandImageCandidates(['banner', 'icon'], 'light')).toEqual([
      ...BRAND_IMAGE_EXTENSIONS.map(extension => `/banner.${extension}`),
      ...BRAND_IMAGE_EXTENSIONS.map(extension => `/icon.${extension}`),
    ]);
  });

  it('暗色主题先尝试同名 dark 资源，再回退普通资源和备用文件名', () => {
    expect(buildBrandImageCandidates(['banner', 'icon'], 'dark')).toEqual([
      ...BRAND_IMAGE_EXTENSIONS.map(extension => `/banner_dark.${extension}`),
      ...BRAND_IMAGE_EXTENSIONS.map(extension => `/banner.${extension}`),
      ...BRAND_IMAGE_EXTENSIONS.map(extension => `/icon_dark.${extension}`),
      ...BRAND_IMAGE_EXTENSIONS.map(extension => `/icon.${extension}`),
    ]);
  });
});

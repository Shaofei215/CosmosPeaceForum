/**
 * 公开内容输入上限。
 *
 * 这些值与公开平台数据库约束和 Pydantic schema 保持一致，供所有发布入口复用。
 */
export const ARTICLE_CONTENT_MAX_LENGTH = 10_000;
export const POST_CONTENT_MAX_LENGTH = 1_000;
export const COMMENT_CONTENT_MAX_LENGTH = 1_000;

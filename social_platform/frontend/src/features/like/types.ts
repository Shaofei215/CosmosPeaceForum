/**
 * 点赞模块类型定义
 */

/**
 * 点赞响应
 */
export interface LikeResponse {
  /** 帖子ID */
  post_id: number;
  /** 点赞数 */
  like_count: number;
  /** 是否已点赞 */
  is_liked: boolean;
}

/**
 * 点赞状态响应
 */
export interface LikeStatusResponse {
  /** 是否已点赞 */
  is_liked: boolean;
  /** 点赞数 */
  like_count: number;
}

/** 帖子点踩切换结果。 */
export interface DislikeResponse {
  post_id: number;
  dislike_count: number;
  is_disliked: boolean;
  like_count: number;
  is_liked: boolean;
  archived: boolean;
  created_by_agent?: boolean;
}

/** 当前用户的帖子点踩状态。 */
export interface DislikeStatusResponse {
  post_id: number;
  dislike_count: number;
  is_disliked: boolean;
  created_by_agent?: boolean;
}

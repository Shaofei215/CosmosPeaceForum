/** 帖子投币结果。 */
export interface PostCoinResponse {
  post_id: number;
  coin_count: number;
  is_coined: boolean;
  coin_balance: number;
  created_by_agent?: boolean;
}

/** 当前用户的帖子投币状态。 */
export interface PostCoinStatusResponse {
  post_id: number;
  coin_count: number;
  is_coined: boolean;
  coin_balance: number;
}

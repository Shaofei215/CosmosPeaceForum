/**
 * 关注模块类型定义
 */

export interface FollowToggleResponse {
  user_id: number;
  is_following: boolean;
  followers_count: number;
  following_count: number;
}

export interface FollowStatusResponse {
  user_id: number;
  is_following: boolean;
  is_followed_by: boolean;
  is_mutual: boolean;
}

export interface FollowUserItem {
  id: number;
  username: string;
  bio: string | null;
  avatar_url: string | null;
  is_following: boolean;
  is_followed_by: boolean;
  created_at: string;
}

export interface FollowListData {
  items: FollowUserItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface FollowListResponse {
  code: number;
  message: string;
  data: FollowUserItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface FollowerListResponse {
  code: number;
  message: string;
  data: FollowUserItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

import type { UserProfile } from '@/features/user/types';

export type NotificationType =
  | 'post_like'
  | 'comment_like'
  | 'comment'
  | 'comment_reply'
  | 'repost'
  | 'follow'
  | 'moderation'
  | string;

export interface NotificationItem {
  id: number;
  type: NotificationType;
  resource_type: string;
  resource_id: number;
  post_id: number | null;
  source_post_type?: 'post' | 'article' | null;
  comment_id: number | null;
  source_content: string | null;
  is_read: boolean;
  created_at: string;
  sender: UserProfile | null;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
  skip: number;
  limit: number;
}

export interface NotificationUnreadCountResponse {
  unread_count: number;
}

export interface NotificationSummaryResponse {
  following_count: number;
  followers_count: number;
  unread_count: number;
}

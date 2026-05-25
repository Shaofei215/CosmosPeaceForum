import type { PostFeedItem } from '@/features/feed';
import type { UserProfile } from '@/features/user';

export type SearchType = 'content' | 'user';

export interface SearchParams {
  type: SearchType;
  q: string;
  page?: number;
  page_size?: number;
}

export type ContentSearchItem = PostFeedItem;
export type UserSearchItem = UserProfile & {
  is_following?: boolean;
  is_followed_by?: boolean;
  is_mutual?: boolean;
};

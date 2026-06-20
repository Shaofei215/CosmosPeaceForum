/**
 * 话题模块类型定义。
 *
 * 话题由帖子正文中的 #话题# 标记产生，热门话题用于右栏展示和搜索跳转。
 */

export interface TopicMention {
  id: number;
  name: string;
}

export interface Topic extends TopicMention {
  post_count: number;
  heat_score: number;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

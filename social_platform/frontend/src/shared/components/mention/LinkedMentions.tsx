/**
 * 提及文本渲染组件。
 *
 * 将后端解析出的 mention_users 与正文中的 @用户名 对齐，渲染为可跳转用户主页的强调色链接。
 */
import { Fragment, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import type { TopicMention } from '@/features/topic';

export interface MentionUser {
  user_id: number;
  username: string;
}

interface LinkedMentionsProps {
  text: string;
  users?: MentionUser[];
  topics?: TopicMention[];
  className?: string;
  onMentionClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
  onTopicClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
}

const tokenPattern = /(@[a-zA-Z0-9_一-龥]+|#[a-zA-Z0-9_\-一-龥]{1,40}#)/g;

export function LinkedMentions({
  text,
  users = [],
  topics = [],
  className,
  onMentionClick,
  onTopicClick,
}: LinkedMentionsProps) {
  const userByName = new Map(users.map(user => [user.username, user]));
  const topicByName = new Map(topics.map(topic => [topic.name, topic]));
  const parts = text.split(tokenPattern);
  const linkClassName =
    className || 'font-medium text-sky-600 transition-colors hover:text-sky-700';

  return (
    <>
      {parts.map((part, index) => {
        const key = `${part}-${index}`;
        if (part.startsWith('@')) {
          const user = userByName.get(part.slice(1));
          if (!user) {
            return <Fragment key={key}>{part}</Fragment>;
          }

          return (
            <Link
              key={key}
              to={`/user/${user.user_id}`}
              className={linkClassName}
              onClick={onMentionClick}
            >
              {part}
            </Link>
          );
        }

        if (part.startsWith('#') && part.endsWith('#')) {
          const topicName = part.slice(1, -1);
          const topic = topicByName.get(topicName);
          if (!topic) {
            return <Fragment key={key}>{part}</Fragment>;
          }

          return (
            <Link
              key={key}
              to={`/search?type=topic&q=${encodeURIComponent(topic.name)}`}
              className={linkClassName}
              onClick={onTopicClick}
            >
              {part}
            </Link>
          );
        }

        return <Fragment key={key}>{part}</Fragment>;
      })}
    </>
  );
}

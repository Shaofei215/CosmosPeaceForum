/**
 * 提及文本渲染组件。
 *
 * 将后端解析出的 mention_users 与正文中的 @用户名 对齐，渲染为可跳转用户主页的强调色链接。
 */
import { Fragment, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';

export interface MentionUser {
  user_id: number;
  username: string;
}

interface LinkedMentionsProps {
  text: string;
  users?: MentionUser[];
  className?: string;
  onMentionClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
}

const mentionPattern = /(@[a-zA-Z0-9_一-龥]+)/g;

export function LinkedMentions({
  text,
  users = [],
  className,
  onMentionClick,
}: LinkedMentionsProps) {
  const userByName = new Map(users.map(user => [user.username, user]));
  const parts = text.split(mentionPattern);

  return (
    <>
      {parts.map((part, index) => {
        const key = `${part}-${index}`;
        if (!part.startsWith('@')) {
          return <Fragment key={key}>{part}</Fragment>;
        }

        const user = userByName.get(part.slice(1));
        if (!user) {
          return <Fragment key={key}>{part}</Fragment>;
        }

        return (
          <Link
            key={key}
            to={`/user/${user.user_id}`}
            className={
              className ||
              'font-medium text-[var(--theme-accent-bg)] transition-colors hover:opacity-80'
            }
            onClick={onMentionClick}
          >
            {part}
          </Link>
        );
      })}
    </>
  );
}

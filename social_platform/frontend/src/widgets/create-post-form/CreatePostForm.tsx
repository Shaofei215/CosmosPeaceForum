import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FilePenLine, Vote } from 'lucide-react';
import { useCreatePost } from '@/features/post';
import { Button, Textarea } from '@/shared/components/ui';
import { POST_CONTENT_MAX_LENGTH } from '@/shared/config/contentLimits';
import { copywriting } from '@/shared/config/copywriting';
import { hasVisibleContent } from '@/shared/lib/content';

const MIN_POLL_OPTIONS = 2;
const MAX_POLL_OPTIONS = 5;
const MAX_POLL_OPTION_LENGTH = 20;

export function CreatePostForm() {
  const [content, setContent] = useState('');
  const [isPollOpen, setIsPollOpen] = useState(false);
  const [pollOptions, setPollOptions] = useState<string[]>(['', '']);
  const { mutate: createPost, isPending } = useCreatePost();
  const normalizedPollOptions = pollOptions.map(option => option.trim());
  const canSubmitPoll =
    !isPollOpen ||
    (normalizedPollOptions.length >= MIN_POLL_OPTIONS &&
      normalizedPollOptions.every(hasVisibleContent) &&
      new Set(normalizedPollOptions).size === normalizedPollOptions.length);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!hasVisibleContent(content) || !canSubmitPoll) return;

    createPost(
      {
        content,
        ...(isPollOpen ? { poll_options: normalizedPollOptions } : {}),
      },
      {
        onSuccess: () => {
          setContent('');
          setIsPollOpen(false);
          setPollOptions(['', '']);
        },
      }
    );
  };

  const updatePollOption = (index: number, value: string) => {
    setPollOptions(currentOptions =>
      currentOptions.map((option, optionIndex) =>
        optionIndex === index ? value.slice(0, MAX_POLL_OPTION_LENGTH) : option
      )
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <Textarea
        placeholder={copywriting('post.create_placeholder', '分享你的想法...')}
        value={content}
        onChange={e => setContent(e.target.value)}
        maxLength={POST_CONTENT_MAX_LENGTH}
        rows={3}
        disabled={isPending}
        className="resize-none border-0 bg-transparent px-1 py-1.5 shadow-none focus-visible:ring-0"
      />
      {isPollOpen && (
        <div className="space-y-2">
          {pollOptions.map((option, index) => (
            <input
              key={index}
              value={option}
              onChange={event => updatePollOption(index, event.target.value)}
              maxLength={MAX_POLL_OPTION_LENGTH}
              disabled={isPending}
              placeholder={copywriting('post.poll_option', '选项 {number}', {
                number: index + 1,
              })}
              className="h-9 w-full rounded-lg border-0 bg-slate-100 px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus-visible:bg-slate-50 focus-visible:ring-2 focus-visible:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
            />
          ))}
          {pollOptions.length < MAX_POLL_OPTIONS && (
            <button
              type="button"
              onClick={() => setPollOptions(currentOptions => [...currentOptions, ''])}
              disabled={isPending}
              className="h-9 w-full rounded-lg border-0 bg-slate-100 px-3 text-left text-sm text-muted-foreground transition-colors hover:bg-slate-200 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {copywriting('post.add_poll_option', '新增选项')}
            </button>
          )}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          title={copywriting('post.poll', '投票')}
          aria-label={copywriting('post.poll', '投票')}
          onClick={() => setIsPollOpen(value => !value)}
          className={`inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:opacity-85 ${
            isPollOpen ? 'bg-zinc-950 text-white' : 'bg-zinc-100/80 text-zinc-600'
          }`}
        >
          <Vote className="h-[18px] w-[18px]" />
        </button>
        <Link
          to="/article/new"
          title={copywriting('post.write_article', '写文章')}
          aria-label={copywriting('post.write_article', '写文章')}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-zinc-100/80 text-zinc-600 transition-colors hover:opacity-85"
        >
          <FilePenLine className="h-[18px] w-[18px]" />
        </Link>
        <Button
          type="submit"
          disabled={!hasVisibleContent(content) || !canSubmitPoll || isPending}
          size="sm"
          className="px-4"
        >
          {isPending
            ? copywriting('post.publishing', '发布中...')
            : copywriting('post.publish', '发布')}
        </Button>
      </div>
    </form>
  );
}

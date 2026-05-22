import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FilePenLine } from 'lucide-react';
import { useCreatePost } from '@/features/post';
import { Button, Textarea } from '@/shared/components/ui';

export function CreatePostForm() {
  const [content, setContent] = useState('');
  const { mutate: createPost, isPending } = useCreatePost();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!content.trim()) return;

    createPost(
      { content: content.trim() },
      {
        onSuccess: () => {
          setContent('');
        },
      }
    );
  };

  return (
    <form onSubmit={handleSubmit}>
      <Textarea
        placeholder="分享你的想法..."
        value={content}
        onChange={e => setContent(e.target.value)}
        rows={3}
        disabled={isPending}
        className="resize-none border-0 bg-muted/30 shadow-none focus-visible:ring-0"
      />
      <div className="mt-3 flex justify-end gap-2">
        <Link
          to="/article/new"
          title="写文章"
          aria-label="写文章"
          className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--theme-subtle-bg)] text-[var(--theme-subtle-fg)] transition-colors hover:opacity-85"
        >
          <FilePenLine className="h-[18px] w-[18px]" />
        </Link>
        <Button type="submit" disabled={!content.trim() || isPending} size="sm" className="px-4">
          {isPending ? '发布中...' : '发布'}
        </Button>
      </div>
    </form>
  );
}

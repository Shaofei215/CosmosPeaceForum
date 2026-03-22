/**
 * 创建帖子表单组件
 */

import { useState } from 'react';
import { useCreatePost } from '@/features/post';
import { Button, Textarea } from '@/shared/components/ui';

/**
 * 创建帖子表单组件
 */
export function CreatePostForm() {
  const [content, setContent] = useState('');
  const { mutate: createPost, isPending } = useCreatePost();

  /**
   * 处理提交
   */
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
    <form onSubmit={handleSubmit} className="rounded-xl border bg-card p-4 shadow-sm">
      <Textarea
        placeholder="分享你的想法..."
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={3}
        className="resize-none border-0 focus-visible:ring-0 p-0"
        disabled={isPending}
      />
      <div className="flex justify-end mt-3 pt-3 border-t">
        <Button type="submit" disabled={!content.trim() || isPending} size="sm">
          {isPending ? '发布中...' : '发布'}
        </Button>
      </div>
    </form>
  );
}

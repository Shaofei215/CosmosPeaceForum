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
    <form onSubmit={handleSubmit}>
      <Textarea
        placeholder="分享你的想法..."
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={3}
        disabled={isPending}
        className="border-0 shadow-none bg-muted/30 focus-visible:ring-0 resize-none"
      />
      <div className="flex justify-end mt-3">
        <Button type="submit" disabled={!content.trim() || isPending} size="sm" className="px-4">
          {isPending ? '发布中...' : '发布'}
        </Button>
      </div>
    </form>
  );
}

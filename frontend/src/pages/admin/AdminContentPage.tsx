import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, Trash2 } from 'lucide-react';
import { adminApi, adminKeys, type ContentItem } from '@/features/admin';
import { Button, Card, CardContent, Input, Textarea } from '@/shared/components/ui';

export default function AdminContentPage() {
  const [keyword, setKeyword] = useState('');
  const [type, setType] = useState('');
  const [deleting, setDeleting] = useState<ContentItem | null>(null);
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: adminKeys.content(type, keyword),
    queryFn: () =>
      adminApi.content({
        skip: 0,
        limit: 100,
        type: type || undefined,
        keyword: keyword.trim() || undefined,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ item, reason }: { item: ContentItem; reason: string }) => {
      const payload = { reason: reason || undefined, notify_author: true };
      return item.type === 'comment'
        ? adminApi.deleteComment(item.id, payload)
        : adminApi.deletePost(item.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <h1 className="text-2xl font-bold">内容管理</h1>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={type}
            onChange={(event) => setType(event.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">全部内容</option>
            <option value="post">帖子/文章</option>
            <option value="comment">评论</option>
          </select>
          <div className="relative w-full sm:w-72">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索内容"
              className="pl-8"
            />
          </div>
        </div>
      </div>

      <Card className="rounded-lg">
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full min-w-[920px] text-sm">
              <thead className="border-b bg-muted/50 text-left text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">内容</th>
                  <th className="px-4 py-3 font-medium">作者</th>
                  <th className="px-4 py-3 font-medium">类型</th>
                  <th className="px-4 py-3 font-medium">互动</th>
                  <th className="px-4 py-3 font-medium">时间</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((item) => (
                  <tr key={`${item.type}-${item.id}`} className="border-b last:border-0">
                    <td className="max-w-xl px-4 py-3">
                      {item.title && <p className="mb-1 font-medium">{item.title}</p>}
                      <p className="line-clamp-2 text-muted-foreground">{item.content}</p>
                    </td>
                    <td className="px-4 py-3">@{item.author_username || item.author_id}</td>
                    <td className="px-4 py-3">{item.type === 'comment' ? '评论' : item.type}</td>
                    <td className="px-4 py-3">
                      {item.like_count} 赞
                      {item.comment_count !== null ? ` / ${item.comment_count} 评` : ''}
                    </td>
                    <td className="px-4 py-3">{new Date(item.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3">
                      <Button
                        variant="destructive"
                        size="sm"
                        className="rounded-md"
                        onClick={() => setDeleting(item)}
                      >
                        <Trash2 size={14} className="mr-1" />
                        删除
                      </Button>
                    </td>
                  </tr>
                ))}
                {(!data?.items || data.items.length === 0) && (
                  <tr>
                    <td className="px-4 py-10 text-center text-muted-foreground" colSpan={6}>
                      暂无内容
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {deleting && (
        <DeleteContentDialog
          item={deleting}
          saving={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={(reason) => deleteMutation.mutate({ item: deleting, reason })}
        />
      )}
    </div>
  );
}

function DeleteContentDialog({
  item,
  saving,
  onClose,
  onConfirm,
}: {
  item: ContentItem;
  saving: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-lg rounded-lg shadow-xl">
        <CardContent className="space-y-4 p-5">
          <div>
            <h2 className="text-lg font-semibold">删除内容</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {item.type === 'comment' ? '评论' : '帖子'} #{item.id}
            </p>
          </div>
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="删除原因，会通过通知发送给作者"
            rows={4}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="rounded-md" onClick={onClose} disabled={saving}>
              取消
            </Button>
            <Button
              variant="destructive"
              className="rounded-md"
              disabled={saving}
              onClick={() => onConfirm(reason)}
            >
              删除
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

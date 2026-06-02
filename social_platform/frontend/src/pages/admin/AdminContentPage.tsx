import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  CheckCircle,
  FileText,
  Heart,
  MessageCircle,
  Search,
  ShieldAlert,
  Trash2,
} from 'lucide-react';
import { adminApi, adminKeys, type ContentItem, type ReportedContentItem } from '@/features/admin';
import { Button, Card, CardContent, Input, Textarea } from '@/shared/components/ui';

type ContentMode = 'all' | 'reported';

function getContentKey(item: ContentItem) {
  return item.type + '-' + item.id;
}

function getReviewTargetType(item: ContentItem) {
  return item.type === 'comment' ? 'comment' : 'post';
}

function getContentPath(item: ContentItem): string | null {
  if (item.type === 'comment' && item.post_id) {
    return '/post/' + item.post_id + '?commentId=' + item.id;
  }
  if (item.type !== 'comment') {
    return '/post/' + item.id;
  }
  return null;
}

function ContentPreview({ item }: { item: ContentItem }) {
  const targetPath = getContentPath(item);
  const content = (
    <>
      {item.title && <p className="mb-1 font-medium">{item.title}</p>}
      <p className="line-clamp-2 text-muted-foreground group-hover:text-primary">{item.content}</p>
    </>
  );

  if (!targetPath) {
    return <div>{content}</div>;
  }

  return (
    <Link to={targetPath} className="group block hover:text-primary">
      {content}
    </Link>
  );
}

export default function AdminContentPage() {
  const [mode, setMode] = useState<ContentMode>('all');
  const [keyword, setKeyword] = useState('');
  const [type, setType] = useState('');
  const [deleting, setDeleting] = useState<ContentItem | null>(null);
  const [deletingReported, setDeletingReported] = useState<ReportedContentItem | null>(null);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [releasingKey, setReleasingKey] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const contentQuery = useQuery({
    queryKey: adminKeys.content(type, keyword),
    queryFn: () =>
      adminApi.content({
        skip: 0,
        limit: 100,
        type: type || undefined,
        keyword: keyword.trim() || undefined,
      }),
    enabled: mode === 'all',
  });

  const reportedQuery = useQuery({
    queryKey: adminKeys.reportedContent(type, keyword),
    queryFn: () =>
      adminApi.reportedContent({
        skip: 0,
        limit: 100,
        type: type || undefined,
        keyword: keyword.trim() || undefined,
      }),
    enabled: mode === 'reported',
  });

  const items = contentQuery.data?.items ?? [];
  const reportedItems = reportedQuery.data?.items ?? [];
  const selectedItems = items.filter(item => selectedKeys.includes(getContentKey(item)));
  const allPageSelected =
    items.length > 0 && items.every(item => selectedKeys.includes(getContentKey(item)));

  const deleteMutation = useMutation({
    mutationFn: ({ item, reason }: { item: ContentItem; reason: string }) => {
      const payload = { reason: reason || undefined, notify_author: true };
      return item.type === 'comment'
        ? adminApi.deleteComment(item.id, payload)
        : adminApi.deletePost(item.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      if (deleting) {
        setSelectedKeys(current => current.filter(key => key !== getContentKey(deleting)));
      }
      setDeleting(null);
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: async ({
      items: targetItems,
      reason,
    }: {
      items: ContentItem[];
      reason: string;
    }) => {
      const payload = { reason: reason || undefined, notify_author: true };
      const orderedItems = [...targetItems].sort((a, b) => {
        if (a.type === b.type) return 0;
        return a.type === 'comment' ? -1 : 1;
      });
      for (const item of orderedItems) {
        if (item.type === 'comment') {
          await adminApi.deleteComment(item.id, payload);
        } else {
          await adminApi.deletePost(item.id, payload);
        }
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      setBatchDeleting(false);
      setSelectedKeys([]);
    },
  });

  const releaseMutation = useMutation({
    mutationFn: (item: ReportedContentItem) =>
      adminApi.releaseReportedContent(getReviewTargetType(item), item.id),
    onMutate: item => {
      setReleasingKey(getContentKey(item));
    },
    onSettled: () => {
      setReleasingKey(null);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content', 'reports'] });
    },
  });

  const deleteReportedMutation = useMutation({
    mutationFn: ({ item, reason }: { item: ReportedContentItem; reason: string }) => {
      const payload = { reason: reason || undefined, notify_author: true };
      return adminApi.deleteReportedContent(getReviewTargetType(item), item.id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
      setDeletingReported(null);
    },
  });

  const toggleSelected = (item: ContentItem) => {
    const key = getContentKey(item);
    setSelectedKeys(current =>
      current.includes(key) ? current.filter(itemKey => itemKey !== key) : [...current, key]
    );
  };

  const toggleAllPage = () => {
    setSelectedKeys(current => {
      const pageKeys = items.map(getContentKey);
      if (items.every(item => current.includes(getContentKey(item)))) {
        return current.filter(key => !pageKeys.includes(key));
      }
      return Array.from(new Set([...current, ...pageKeys]));
    });
  };

  const switchMode = (nextMode: ContentMode) => {
    setMode(nextMode);
    setSelectedKeys([]);
  };

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold">内容管理</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant={mode === 'all' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('all')}
            >
              <FileText size={14} className="mr-1" />
              全部内容
            </Button>
            <Button
              variant={mode === 'reported' ? 'default' : 'outline'}
              size="sm"
              className="rounded-md"
              onClick={() => switchMode('reported')}
            >
              <ShieldAlert size={14} className="mr-1" />
              被举报内容审查
            </Button>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          {mode === 'all' && selectedKeys.length > 0 && (
            <Button
              variant="destructive"
              className="rounded-md"
              onClick={() => setBatchDeleting(true)}
            >
              <Trash2 size={14} className="mr-1" />
              批量删除
            </Button>
          )}
          <select
            value={type}
            onChange={event => {
              setType(event.target.value);
              setSelectedKeys([]);
            }}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">全部内容</option>
            <option value="post">帖子/文章</option>
            <option value="comment">评论</option>
          </select>
          <div className="relative w-full sm:w-72">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={keyword}
              onChange={event => {
                setKeyword(event.target.value);
                setSelectedKeys([]);
              }}
              placeholder={mode === 'reported' ? '搜索被举报内容' : '搜索内容'}
              className="pl-8"
            />
          </div>
        </div>
      </div>

      {mode === 'all' ? (
        <AllContentTable
          items={items}
          selectedKeys={selectedKeys}
          allPageSelected={allPageSelected}
          onToggleSelected={toggleSelected}
          onToggleAllPage={toggleAllPage}
          onDelete={setDeleting}
        />
      ) : (
        <ReportedContentTable
          items={reportedItems}
          releasingKey={releasingKey}
          releasePending={releaseMutation.isPending}
          onRelease={item => releaseMutation.mutate(item)}
          onDelete={setDeletingReported}
        />
      )}

      {deleting && (
        <DeleteContentDialog
          item={deleting}
          saving={deleteMutation.isPending}
          onClose={() => setDeleting(null)}
          onConfirm={reason => deleteMutation.mutate({ item: deleting, reason })}
        />
      )}
      {batchDeleting && (
        <BatchDeleteContentDialog
          items={selectedItems}
          saving={batchDeleteMutation.isPending}
          onClose={() => setBatchDeleting(false)}
          onConfirm={reason => batchDeleteMutation.mutate({ items: selectedItems, reason })}
        />
      )}
      {deletingReported && (
        <DeleteContentDialog
          item={deletingReported}
          saving={deleteReportedMutation.isPending}
          onClose={() => setDeletingReported(null)}
          onConfirm={reason => deleteReportedMutation.mutate({ item: deletingReported, reason })}
        />
      )}
    </div>
  );
}

function AllContentTable({
  items,
  selectedKeys,
  allPageSelected,
  onToggleSelected,
  onToggleAllPage,
  onDelete,
}: {
  items: ContentItem[];
  selectedKeys: string[];
  allPageSelected: boolean;
  onToggleSelected: (item: ContentItem) => void;
  onToggleAllPage: () => void;
  onDelete: (item: ContentItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="overflow-auto">
          <table className="w-full min-w-[920px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="w-10 px-4 py-3 font-medium">
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={onToggleAllPage}
                    aria-label="选择当前页内容"
                  />
                </th>
                <th className="px-4 py-3 font-medium">内容</th>
                <th className="px-4 py-3 font-medium">作者</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">互动</th>
                <th className="px-4 py-3 font-medium">时间</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={getContentKey(item)} className="border-b last:border-0">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedKeys.includes(getContentKey(item))}
                      onChange={() => onToggleSelected(item)}
                      aria-label={
                        '选择' + (item.type === 'comment' ? '评论' : '帖子') + ' ' + item.id
                      }
                    />
                  </td>
                  <td className="max-w-xl px-4 py-3">
                    <ContentPreview item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <AuthorLink item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <ContentTypeIcon item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <InteractionStats item={item} />
                  </td>
                  <td className="px-4 py-3">{new Date(item.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-center">
                    <Button
                      variant="destructive"
                      size="icon"
                      className="mx-auto rounded-md"
                      onClick={() => onDelete(item)}
                      title="删除"
                      aria-label={
                        '删除' + (item.type === 'comment' ? '评论' : '帖子') + ' ' + item.id
                      }
                    >
                      <Trash2 size={16} />
                    </Button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={7}>
                    暂无内容
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function ReportedContentTable({
  items,
  releasingKey,
  releasePending,
  onRelease,
  onDelete,
}: {
  items: ReportedContentItem[];
  releasingKey: string | null;
  releasePending: boolean;
  onRelease: (item: ReportedContentItem) => void;
  onDelete: (item: ReportedContentItem) => void;
}) {
  return (
    <Card className="rounded-lg">
      <CardContent className="p-0">
        <div className="overflow-auto">
          <table className="w-full min-w-[1080px] text-sm">
            <thead className="border-b bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">内容</th>
                <th className="px-4 py-3 font-medium">作者</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">举报人数</th>
                <th className="px-4 py-3 font-medium">举报原因</th>
                <th className="px-4 py-3 font-medium">最近举报</th>
                <th className="px-4 py-3 text-center font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={getContentKey(item)} className="border-b last:border-0">
                  <td className="max-w-md px-4 py-3">
                    <ContentPreview item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <AuthorLink item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <ContentTypeIcon item={item} />
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-md bg-muted px-2 py-1 font-medium tabular-nums">
                      {item.report_count}
                    </span>
                  </td>
                  <td className="max-w-sm px-4 py-3">
                    <div className="space-y-1.5">
                      {item.report_reasons.map(reason => (
                        <div
                          key={reason.reason}
                          className="flex items-start gap-2 rounded-md bg-muted/40 px-2 py-1.5"
                        >
                          <span className="shrink-0 rounded bg-background px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground">
                            {reason.count}
                          </span>
                          <span className="line-clamp-2 break-words text-muted-foreground">
                            {reason.reason}
                          </span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">{new Date(item.last_reported_at).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-md gap-1"
                        onClick={() => onRelease(item)}
                        disabled={releasePending && releasingKey === getContentKey(item)}
                      >
                        <CheckCircle size={14} />
                        放行
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        className="rounded-md gap-1"
                        onClick={() => onDelete(item)}
                      >
                        <Trash2 size={14} />
                        删除
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-10 text-center text-muted-foreground" colSpan={7}>
                    暂无待审举报内容
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function AuthorLink({ item }: { item: ContentItem }) {
  return (
    <Link to={'/user/' + item.author_id} className="font-medium hover:text-primary hover:underline">
      @{item.author_username || item.author_id}
    </Link>
  );
}

function ContentTypeIcon({ item }: { item: ContentItem }) {
  return (
    <span
      className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-muted text-muted-foreground"
      title={item.type === 'comment' ? '评论' : '帖子'}
      aria-label={item.type === 'comment' ? '评论' : '帖子'}
    >
      {item.type === 'comment' ? <MessageCircle size={15} /> : <FileText size={15} />}
    </span>
  );
}

function InteractionStats({ item }: { item: ContentItem }) {
  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-1 text-muted-foreground" title="点赞数">
        <Heart size={15} />
        <span className="font-medium tabular-nums text-foreground">{item.like_count}</span>
      </span>
      {item.comment_count !== null && (
        <span className="inline-flex items-center gap-1 text-muted-foreground" title="评论数">
          <MessageCircle size={15} />
          <span className="font-medium tabular-nums text-foreground">{item.comment_count}</span>
        </span>
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
            onChange={event => setReason(event.target.value)}
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

function BatchDeleteContentDialog({
  items,
  saving,
  onClose,
  onConfirm,
}: {
  items: ContentItem[];
  saving: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const commentCount = items.filter(item => item.type === 'comment').length;
  const postCount = items.length - commentCount;

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-lg rounded-lg shadow-xl">
        <CardContent className="space-y-4 p-5">
          <div>
            <h2 className="text-lg font-semibold">批量删除内容</h2>
            <p className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <FileText size={14} />
                {postCount} 帖
              </span>
              <span className="inline-flex items-center gap-1">
                <MessageCircle size={14} />
                {commentCount} 评论
              </span>
            </p>
          </div>
          <Textarea
            value={reason}
            onChange={event => setReason(event.target.value)}
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
              disabled={saving || items.length === 0}
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

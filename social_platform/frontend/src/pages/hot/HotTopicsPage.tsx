import { Link } from 'react-router-dom';
import { Flame, Search } from 'lucide-react';
import { useHotTopics } from '@/features/hot-topic';
import { Skeleton } from '@/shared/components/ui';

export default function HotTopicsPage() {
  const { data: hotTopics = [], isLoading } = useHotTopics(50);

  return (
    <div className="overflow-hidden rounded-lg bg-white shadow-sm">
      <div className="border-b border-border/50 p-4">
        <div className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-orange-500" />
          <h1 className="text-lg font-semibold">热门榜单</h1>
        </div>
      </div>

      {isLoading ? (
        <div className="divide-y divide-border/50">
          <HotTopicSkeleton />
          <HotTopicSkeleton />
          <HotTopicSkeleton />
        </div>
      ) : hotTopics.length > 0 ? (
        <div className="divide-y divide-border/50">
          {hotTopics.map((topic, index) => (
            <Link
              key={topic.id}
              to={`/search?type=content&q=${encodeURIComponent(topic.search_query)}`}
              className="flex gap-3 p-4 transition-colors hover:bg-muted/40"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-muted text-sm font-semibold text-muted-foreground">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{topic.title}</p>
                {topic.summary && (
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm text-muted-foreground">
                    {topic.summary}
                  </p>
                )}
                <p className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Search className="h-3.5 w-3.5" />
                  {topic.search_query}
                </p>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="py-12 text-center text-muted-foreground">暂无热门内容</div>
      )}
    </div>
  );
}

function HotTopicSkeleton() {
  return (
    <div className="flex gap-3 p-4">
      <Skeleton className="h-7 w-7 rounded" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  );
}

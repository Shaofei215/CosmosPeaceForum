/** 管理后台统一的服务端分页控件。 */

import type { ReactElement } from 'react';
import { Button } from '@/shared/components/ui';

export function AdminPagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}): ReactElement | null {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize && page === 0) return null;
  return (
    <div className="mt-4 flex items-center justify-between gap-3 text-sm text-muted-foreground">
      <span>
        共 {total} 条，第 {Math.min(page + 1, pageCount)} / {pageCount} 页
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="rounded-md"
          disabled={page <= 0}
          onClick={() => onPageChange(page - 1)}
        >
          上一页
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="rounded-md"
          disabled={page + 1 >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          下一页
        </Button>
      </div>
    </div>
  );
}

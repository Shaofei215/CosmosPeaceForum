import { format, formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '';

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  const diff = Date.now() - date.getTime();
  if (diff >= 0 && diff < 1000 * 60 * 60 * 24 * 7) {
    return formatDistanceToNow(date, { addSuffix: true, locale: zhCN });
  }

  return format(date, 'yyyy-MM-dd HH:mm');
}

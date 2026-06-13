import { format } from 'date-fns';
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return '';

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  const diff = Date.now() - date.getTime();
  if (diff >= 0) {
    const minute = 1000 * 60;
    const hour = minute * 60;
    const day = hour * 24;
    const timeText = format(date, 'HH:mm');

    if (diff < minute) return '刚刚';
    if (diff < hour) return `${Math.floor(diff / minute)}分钟前`;
    if (diff < day) return `${Math.floor(diff / hour)}小时前`;
    if (diff < day * 2) return `昨天 ${timeText}`;
    if (diff <= day * 3) return `${Math.floor(diff / day)}天前 ${timeText}`;
  }

  return format(date, 'yyyy-MM-dd HH:mm');
}

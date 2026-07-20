import { format } from 'date-fns';
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { copywriting } from '@/shared/config/copywriting';

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

    if (diff < minute) return copywriting('time.just_now', '刚刚');
    if (diff < hour) {
      return copywriting('time.minutes_ago', '{count}分钟前', {
        count: Math.floor(diff / minute),
      });
    }
    if (diff < day) {
      return copywriting('time.hours_ago', '{count}小时前', {
        count: Math.floor(diff / hour),
      });
    }
    if (diff < day * 2) return copywriting('time.yesterday', '昨天 {time}', { time: timeText });
    if (diff <= day * 3) {
      return copywriting('time.days_ago', '{count}天前 {time}', {
        count: Math.floor(diff / day),
        time: timeText,
      });
    }
  }

  return format(date, 'yyyy-MM-dd HH:mm');
}

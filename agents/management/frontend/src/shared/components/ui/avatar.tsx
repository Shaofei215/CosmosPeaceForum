import * as React from 'react';
import { cn } from '@/shared/lib/cn';

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string | null;
  alt?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
}

const sizeMap = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-12 h-12 text-base',
  xl: 'w-20 h-20 text-lg',
  '2xl': 'w-24 h-24 text-xl',
};

function getInitials(name: string): string {
  return name.charAt(0).toUpperCase();
}

function getRandomColor(name: string): string {
  const colors = [
    'bg-red-500', 'bg-orange-500', 'bg-amber-500', 'bg-green-500',
    'bg-emerald-500', 'bg-teal-500', 'bg-cyan-500', 'bg-sky-500',
    'bg-blue-500', 'bg-indigo-500', 'bg-violet-500', 'bg-purple-500',
    'bg-fuchsia-500', 'bg-pink-500', 'bg-rose-500',
  ];
  const index = name.charCodeAt(0) % colors.length;
  return colors[index];
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, src, alt = '', size = 'md', ...props }, ref) => {
    const [error, setError] = React.useState(false);

    if (!src || error) {
      return (
        <div
          ref={ref}
          className={cn(
            'relative flex shrink-0 overflow-hidden rounded-full items-center justify-center text-white font-medium',
            sizeMap[size],
            getRandomColor(alt || 'A'),
            className
          )}
          {...props}
        >
          {getInitials(alt || 'A')}
        </div>
      );
    }

    return (
      <div
        ref={ref}
        className={cn('relative flex shrink-0 overflow-hidden rounded-full', sizeMap[size], className)}
        {...props}
      >
        <img
          src={src}
          alt={alt}
          className="aspect-square h-full w-full object-cover"
          onError={() => setError(true)}
        />
      </div>
    );
  }
);
Avatar.displayName = 'Avatar';

export { Avatar };
export type { AvatarProps };

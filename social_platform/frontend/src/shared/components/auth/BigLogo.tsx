import { useState } from 'react';
import { cn } from '@/shared/lib/utils';

export function BigLogo({ className }: { className?: string }) {
  const [src, setSrc] = useState('/biglogo.png');

  return (
    <img
      src={src}
      alt="CosmosPeaceForum"
      className={cn('auth-big-logo', className)}
      onError={() => {
        if (src !== '/logo.png') {
          setSrc('/logo.png');
        }
      }}
    />
  );
}

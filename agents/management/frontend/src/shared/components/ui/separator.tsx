import * as React from 'react';

const Separator = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={`shrink-0 bg-border ${className ?? ''}`}
    role="separator"
    {...props}
  />
));
Separator.displayName = 'Separator';

export { Separator };

import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/shared/lib/query';

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

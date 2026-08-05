import { QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/features/theme';
import { queryClient } from '@/shared/lib/query';

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}

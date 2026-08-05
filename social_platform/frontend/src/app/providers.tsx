/**
 * 全局Provider组件
 * 组合所有必要的Provider
 */

import { QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/features/theme';
import { queryClient } from '@/shared/lib/query';

/**
 * Provider组件属性
 */
interface ProvidersProps {
  children: React.ReactNode;
}

/**
 * 全局Provider组件
 */
export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}

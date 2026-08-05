import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/features/auth';
import { coinApi } from './api';

export const usePostCoinStatus = (postId: number, enabled = true) =>
  useQuery({
    queryKey: ['posts', postId, 'coin-status'],
    queryFn: () => coinApi.getStatus(postId),
    enabled: enabled && postId > 0,
  });

/** 投币不可撤销，成功后统一刷新所有可能展示该帖子的缓存。 */
export const useGivePostCoin = () => {
  const queryClient = useQueryClient();
  const updateUser = useAuthStore(state => state.updateUser);

  return useMutation({
    mutationFn: coinApi.giveCoin,
    onSuccess: data => {
      updateUser({ coin_balance: data.coin_balance });
      queryClient.setQueryData(['posts', data.post_id, 'coin-status'], data);
      queryClient.invalidateQueries({ queryKey: ['post', data.post_id] });
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] });
    },
  });
};

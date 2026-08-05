import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { dislikeApi } from './api';

export const useDislikeStatus = (postId: number, enabled = true) =>
  useQuery({
    queryKey: ['posts', postId, 'dislike-status'],
    queryFn: () => dislikeApi.getStatus(postId),
    enabled: enabled && postId > 0,
  });

/** 点踩成功后刷新帖子详情和所有信息流状态。 */
export const useToggleDislike = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: dislikeApi.toggleDislike,
    onSuccess: data => {
      queryClient.setQueryData(['posts', data.post_id, 'dislike-status'], data);
      queryClient.invalidateQueries({ queryKey: ['post', data.post_id] });
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
};

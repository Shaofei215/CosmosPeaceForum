import type { Comment } from './types';

export const REPLIES_BATCH_SIZE = 10;

export function containsComment(comment: Comment, commentId: number): boolean {
  if (comment.id === commentId) {
    return true;
  }

  return Boolean(comment.children?.some((child) => containsComment(child, commentId)));
}

export function getInitialVisibleReplyCount(comment: Comment, focusedCommentId?: number): number {
  const totalReplies = comment.children?.length ?? 0;

  if (totalReplies === 0) {
    return 0;
  }

  if (!focusedCommentId) {
    return Math.min(REPLIES_BATCH_SIZE, totalReplies);
  }

  const focusedChildIndex = comment.children.findIndex((child) =>
    containsComment(child, focusedCommentId),
  );

  if (focusedChildIndex === -1) {
    return Math.min(REPLIES_BATCH_SIZE, totalReplies);
  }

  return Math.min(totalReplies, Math.max(REPLIES_BATCH_SIZE, focusedChildIndex + 1));
}

export function getNextVisibleReplyCount(currentVisibleCount: number, totalReplies: number): number {
  return Math.min(totalReplies, currentVisibleCount + REPLIES_BATCH_SIZE);
}

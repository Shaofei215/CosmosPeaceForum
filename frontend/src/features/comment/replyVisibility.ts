import type { Comment } from './types';

export const REPLIES_BATCH_SIZE = 5;

export function containsComment(comment: Comment, commentId: number): boolean {
  if (comment.id === commentId) {
    return true;
  }

  return Boolean(comment.children?.some((child) => containsComment(child, commentId)));
}

export function getReplyCount(comment: Comment): number {
  return comment.children.reduce(
    (total, child) => total + 1 + getReplyCount(child),
    0,
  );
}

function getReplyRenderIndex(comment: Comment, commentId: number, offset = 0): number {
  let currentIndex = offset;

  for (const child of comment.children) {
    if (child.id === commentId) {
      return currentIndex;
    }

    const descendantIndex = getReplyRenderIndex(child, commentId, currentIndex + 1);
    if (descendantIndex !== -1) {
      return descendantIndex;
    }

    currentIndex += 1 + getReplyCount(child);
  }

  return -1;
}

export function getInitialVisibleReplyCount(comment: Comment, focusedCommentId?: number): number {
  const totalReplies = getReplyCount(comment);

  if (totalReplies === 0) {
    return 0;
  }

  if (!focusedCommentId) {
    return Math.min(REPLIES_BATCH_SIZE, totalReplies);
  }

  const focusedChildIndex = getReplyRenderIndex(comment, focusedCommentId);

  if (focusedChildIndex === -1) {
    return Math.min(REPLIES_BATCH_SIZE, totalReplies);
  }

  return Math.min(totalReplies, Math.max(REPLIES_BATCH_SIZE, focusedChildIndex + 1));
}

export function getNextVisibleReplyCount(currentVisibleCount: number, totalReplies: number): number {
  return Math.min(totalReplies, currentVisibleCount + REPLIES_BATCH_SIZE);
}

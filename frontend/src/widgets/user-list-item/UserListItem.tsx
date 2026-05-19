import { Link, useNavigate } from 'react-router-dom';
import { useFollowStatus, useToggleFollow, type FollowStatusResponse } from '@/features/follow';
import { useAuthStore } from '@/features/auth';
import { Avatar, Button, Skeleton } from '@/shared/components/ui';

interface UserListItemUser {
  id: number;
  username: string;
  bio: string | null;
  avatar_url: string | null;
  is_following?: boolean;
  is_followed_by?: boolean;
}

interface UserListItemProps {
  user: UserListItemUser;
}

export function UserListItem({ user }: UserListItemProps) {
  const navigate = useNavigate();
  const { user: currentUser, isAuthenticated } = useAuthStore();
  const toggleFollow = useToggleFollow();
  const isCurrentUser = currentUser?.id === user.id;
  const hasInitialStatus =
    typeof user.is_following === 'boolean' || typeof user.is_followed_by === 'boolean';
  const initialStatus: FollowStatusResponse | undefined = hasInitialStatus
    ? {
        user_id: user.id,
        is_following: user.is_following ?? false,
        is_followed_by: user.is_followed_by ?? false,
        is_mutual: Boolean(user.is_following && user.is_followed_by),
      }
    : undefined;
  const { data: followStatus } = useFollowStatus(user.id, {
    enabled: !hasInitialStatus,
    initialData: initialStatus,
  });
  const isFollowing = followStatus?.is_following ?? false;

  const handleFollow = () => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    toggleFollow.mutate(user.id);
  };

  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <Link to={`/user/${user.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar src={user.avatar_url} alt={user.username} size="md" />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-foreground">{user.username}</div>
          {user.bio && <p className="mt-0.5 truncate text-sm text-muted-foreground">{user.bio}</p>}
        </div>
      </Link>

      {!isCurrentUser && !isFollowing && (
        <Button
          variant="outline"
          size="sm"
          onClick={handleFollow}
          disabled={toggleFollow.isPending}
          className="h-7 shrink-0 border-black bg-white px-3 text-xs text-black hover:bg-gray-100"
        >
          {toggleFollow.isPending ? (
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
          ) : (
            '关注'
          )}
        </Button>
      )}
    </div>
  );
}

export function UserListItemSkeleton() {
  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-32" />
      </div>
      <Skeleton className="h-7 w-14 rounded-full" />
    </div>
  );
}

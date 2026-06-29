# 前端核心功能实现文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 认证模块

### 登录流程

```
用户输入用户名/密码
    ↓
调用 POST /api/v1/auth/login
    ↓
验证成功后获取 access_token
    ↓
存储 token 到 Zustand + localStorage
    ↓
重定向到首页
```

### Hook 实现

```typescript
// features/auth/hooks/useLogin.ts

import { useMutation } from '@tanstack/react-query'
import { authApi } from '../api/auth'
import { useAuthStore } from '@/stores/authStore'

export function useLogin() {
  const login = useAuthStore((state) => state.login)

  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      authApi.login(username, password),
    onSuccess: (data) => {
      const { id, username } = data.data
      login({ id, username }, data.data.access_token)
    },
  })
}
```

### 持久化认证状态

```typescript
// stores/authStore.ts

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      login: (user, token) => set({ user, token, isAuthenticated: true }),
      logout: () => set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
    }
  )
)
```

---

## 信息流模块

### 获取信息流

```typescript
// features/feed/hooks/useFeed.ts

import { useInfiniteQuery } from '@tanstack/react-query'
import { feedApi } from '../api/feeds'
import { useAuthStore } from '@/stores/authStore'

export function useGlobalFeed() {
  const user = useAuthStore((state) => state.user)

  return useInfiniteQuery({
    queryKey: ['feed', 'global', user?.id],
    queryFn: ({ pageParam = 1 }) =>
      feedApi.getGlobalFeed(pageParam, 20, user?.id),
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1
      }
      return undefined
    },
    initialPageParam: 1,
  })
}
```

### 渲染信息流

```typescript
// features/feed/components/FeedList.tsx

import { useGlobalFeed } from '../hooks/useFeed'
import { PostCard } from '@/widgets/PostCard'

export function FeedList() {
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useGlobalFeed()

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-4">
      {data?.pages.flatMap((page) =>
        page.data.map((post) => <PostCard key={post.id} post={post} />)
      )}
      {hasNextPage && (
        <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
          {isFetchingNextPage ? '加载中...' : '加载更多'}
        </button>
      )}
    </div>
  )
}
```

---

## 帖子模块

### 创建帖子

```typescript
// features/post/hooks/useCreatePost.ts

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postApi } from '../api/posts'

export function useCreatePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: { title?: string; content: string }) =>
      postApi.createPost(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feed'] })
      queryClient.invalidateQueries({ queryKey: ['posts'] })
    },
  })
}
```

### 点赞功能

```typescript
// features/like/hooks/useToggleLike.ts

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postApi } from '../api/posts'

export function useTogglePostLike(postId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => postApi.toggleLike(postId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ['post', postId] })
      const previousPost = queryClient.getQueryData(['post', postId])

      queryClient.setQueryData(['post', postId], (old: any) => ({
        ...old,
        is_liked: !old.is_liked,
        like_count: old.is_liked ? old.like_count - 1 : old.like_count + 1,
      }))

      return { previousPost }
    },
    onError: (err, postId, context) => {
      queryClient.setQueryData(['post', postId], context?.previousPost)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['post', postId] })
    },
  })
}
```

---

## 评论模块

### 获取评论树

```typescript
// features/comment/hooks/useComments.ts

import { useQuery } from '@tanstack/react-query'
import { commentApi } from '../api/comments'
import { useAuthStore } from '@/stores/authStore'

export function useComments(postId: number) {
  const user = useAuthStore((state) => state.user)

  return useQuery({
    queryKey: ['comments', postId, user?.id],
    queryFn: () => commentApi.getComments(postId, user?.id),
  })
}
```

### 评论组件

```typescript
// features/comment/components/CommentTree.tsx

interface CommentItemProps {
  comment: Comment
  onReply: (parentId: number) => void
}

function CommentItem({ comment, onReply }: CommentItemProps) {
  return (
    <div className="comment-item">
      <div className="flex items-start space-x-3">
        <UserAvatar user={comment.owner} />
        <div className="flex-1">
          <div className="font-medium">{comment.owner.username}</div>
          <div className="text-gray-700">{comment.content}</div>
          <div className="flex items-center space-x-4 text-sm text-gray-500">
            <span>{formatDate(comment.created_at)}</span>
            <button onClick={() => onReply(comment.id)}>回复</button>
          </div>
        </div>
      </div>

      {comment.children && comment.children.length > 0 && (
        <div className="ml-8 mt-4 space-y-4">
          {comment.children.map((child) => (
            <CommentItem key={child.id} comment={child} onReply={onReply} />
          ))}
        </div>
      )}
    </div>
  )
}
```

---

## 用户模块

### 获取用户资料

```typescript
// features/user/hooks/useUser.ts

import { useQuery } from '@tanstack/react-query'
import { userApi } from '../api/users'

export function useUser(userId: number | string) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: () =>
      typeof userId === 'number'
        ? userApi.getUserById(userId)
        : userApi.getUserByUsername(userId),
  })
}
```

### 上传头像

```typescript
// features/user/hooks/useUploadAvatar.ts

import { useMutation } from '@tanstack/react-query'
import { userApi } from '../api/users'

export function useUploadAvatar() {
  return useMutation({
    mutationFn: (file: File) => userApi.uploadAvatar(file),
    onSuccess: (data) => {
      console.log('Avatar uploaded:', data.data.avatar_url)
    },
  })
}
```

---

## 状态管理架构

### Zustand Store 列表

| Store | 用途 |
|-------|------|
| `authStore` | 认证状态（用户信息、Token） |
| `uiStore` | UI 状态（模态框、侧边栏等） |

### Auth Store

```typescript
// stores/authStore.ts

interface User {
  id: number
  username: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (user: User, token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      login: (user, token) => set({ user, token, isAuthenticated: true }),
      logout: () => set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage',
    }
  )
)
```

---

## 路由设计

### 路由配置

```typescript
// app/router.tsx

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'profile/:userId', element: <ProfilePage /> },
      { path: 'post/:postId', element: <PostDetailPage /> },
    ],
  },
])
```

### 路由守卫

```typescript
function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
```

---

## 组件库

### 通用组件

| 组件 | 说明 |
|------|------|
| `Button` | 按钮组件 |
| `Input` | 输入框组件 |
| `Card` | 卡片组件 |
| `Modal` | 模态框组件 |
| `Avatar` | 头像组件 |
| `Spinner` | 加载动画 |

### 业务组件

| 组件 | 说明 |
|------|------|
| `PostCard` | 帖子卡片 |
| `CommentItem` | 评论项 |
| `CommentTree` | 评论树 |
| `LikeButton` | 点赞按钮 |
| `UserAvatar` | 用户头像 |

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*

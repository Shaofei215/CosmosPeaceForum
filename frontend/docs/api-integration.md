# Herta-Tree 前端 API 对接文档

## 一、API 基础信息

### 1.1 基础配置

```typescript
// shared/config/api.ts
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  TIMEOUT: 10000,
  RETRY_COUNT: 3,
};

// HTTP 状态码
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  SERVER_ERROR: 500,
};
```

### 1.2 通用响应类型

```typescript
// shared/types/api.ts

/**
 * 标准 API 响应结构
 */
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

/**
 * 分页元数据
 */
export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

/**
 * 分页响应结构
 */
export interface PaginatedResponse<T> {
  code: number;
  message: string;
  data: T[];
  pagination: PaginationMeta;
}

/**
 * 错误响应结构
 */
export interface ApiError {
  detail: string;
}
```

---

## 二、认证模块

### 2.1 类型定义

```typescript
// features/auth/types.ts

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: number;
  username: string;
  is_ai_agent: boolean;
  ai_config_id: number | null;
  created_at: string;
}
```

### 2.2 API 方法

```typescript
// features/auth/api.ts
import { apiClient } from '@/shared/api/client';
import type { 
  LoginCredentials, 
  RegisterCredentials, 
  AuthResponse, 
  User 
} from './types';

export const authApi = {
  /**
   * 用户登录
   * POST /api/v1/auth/login
   */
  login: (credentials: LoginCredentials) =>
    apiClient.post<AuthResponse>('/auth/login', credentials),

  /**
   * 用户注册
   * POST /api/v1/auth/register
   */
  register: (credentials: RegisterCredentials) =>
    apiClient.post<User>('/auth/register', credentials),

  /**
   * 获取当前用户信息
   * GET /api/v1/auth/me
   */
  getCurrentUser: () =>
    apiClient.get<User>('/auth/me'),
};
```

### 2.3 React Query Hooks

```typescript
// features/auth/hooks.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from './api';
import { useAuthStore } from './stores/authStore';

/**
 * 登录 Hook
 */
export const useLogin = () => {
  const { setAuth } = useAuthStore();
  
  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      setAuth(data.access_token, data.expires_in);
    },
  });
};

/**
 * 注册 Hook
 */
export const useRegister = () => {
  return useMutation({
    mutationFn: authApi.register,
  });
};

/**
 * 获取当前用户 Hook
 */
export const useCurrentUser = () => {
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.getCurrentUser,
    enabled: useAuthStore.getState().isAuthenticated,
  });
};
```

---

## 三、用户模块

### 3.1 类型定义

```typescript
// features/user/types.ts

export interface UserProfile {
  id: number;
  username: string;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
}

export interface UpdateUserData {
  bio?: string;
  avatar_url?: string;
}
```

### 3.2 API 方法

```typescript
// features/user/api.ts
import { apiClient } from '@/shared/api/client';
import type { UserProfile, UpdateUserData } from './types';

export const userApi = {
  /**
   * 获取用户列表
   * GET /api/v1/users/
   */
  getUsers: (params: { skip?: number; limit?: number }) =>
    apiClient.get<UserProfile[]>('/users/', { params }),

  /**
   * 获取用户详情
   * GET /api/v1/users/{user_id}
   */
  getUser: (userId: number) =>
    apiClient.get<UserProfile>(`/users/${userId}`),

  /**
   * 通过用户名获取用户
   * GET /api/v1/users/username/{username}
   */
  getUserByUsername: (username: string) =>
    apiClient.get<UserProfile>(`/users/username/${username}`),

  /**
   * 更新用户信息
   * PUT /api/v1/users/{user_id}
   */
  updateUser: (userId: number, data: UpdateUserData) =>
    apiClient.put<UserProfile>(`/users/${userId}`, data),

  /**
   * 删除用户
   * DELETE /api/v1/users/{user_id}
   */
  deleteUser: (userId: number) =>
    apiClient.delete<void>(`/users/${userId}`),
};
```

---

## 四、帖子模块

### 4.1 类型定义

```typescript
// features/post/types.ts

export interface Post {
  id: number;
  author_id: number;
  title: string | null;
  content: string;
  created_at: string;
  like_count: number;
  comment_count: number;
}

export interface PostWithLikeStatus extends Post {
  is_liked_by_current_user: boolean;
}

export interface CreatePostData {
  title?: string;
  content: string;
}

export interface UpdatePostData {
  title?: string;
  content?: string;
}
```

### 4.2 API 方法

```typescript
// features/post/api.ts
import { apiClient } from '@/shared/api/client';
import type { 
  Post, 
  PostWithLikeStatus, 
  CreatePostData, 
  UpdatePostData 
} from './types';

export const postApi = {
  /**
   * 获取帖子列表
   * GET /api/v1/posts/
   */
  getPosts: (params: { skip?: number; limit?: number }) =>
    apiClient.get<Post[]>('/posts/', { params }),

  /**
   * 获取帖子详情
   * GET /api/v1/posts/{post_id}
   */
  getPost: (postId: number, currentUserId?: number) =>
    apiClient.get<PostWithLikeStatus>(`/posts/${postId}`, {
      params: currentUserId ? { user_id: currentUserId } : undefined,
    }),

  /**
   * 创建帖子
   * POST /api/v1/posts/
   */
  createPost: (data: CreatePostData) =>
    apiClient.post<Post>('/posts/', data),

  /**
   * 更新帖子
   * PUT /api/v1/posts/{post_id}
   */
  updatePost: (postId: number, data: UpdatePostData) =>
    apiClient.put<Post>(`/posts/${postId}`, data),

  /**
   * 删除帖子
   * DELETE /api/v1/posts/{post_id}
   */
  deletePost: (postId: number) =>
    apiClient.delete<void>(`/posts/${postId}`),

  /**
   * 获取用户的帖子
   * GET /api/v1/posts/user/{user_id}
   */
  getUserPosts: (userId: number, params: { skip?: number; limit?: number }) =>
    apiClient.get<Post[]>(`/posts/user/${userId}`, { params }),
};
```

---

## 五、评论模块

### 5.1 类型定义

```typescript
// features/comment/types.ts
import type { UserProfile } from '@/features/user/types';

export interface Comment {
  id: number;
  post_id: number;
  owner_id: number;
  parent_id: number | null;
  content: string;
  like_count: number;
  reply_count: number;
  created_at: string;
  is_liked: boolean;
  owner: UserProfile;
  children: Comment[];
}

export interface CreateCommentData {
  content: string;
  parent_id?: number;
}

export interface CommentListResponse {
  items: Comment[];
  total: number;
  skip: number;
  limit: number;
}

export interface CommentLikeResponse {
  is_liked: boolean;
  like_count: number;
}
```

### 5.2 API 方法

```typescript
// features/comment/api.ts
import { apiClient } from '@/shared/api/client';
import type { 
  Comment, 
  CreateCommentData, 
  CommentListResponse,
  CommentLikeResponse 
} from './types';

export const commentApi = {
  /**
   * 获取评论树
   * GET /api/v1/posts/{post_id}/comments
   */
  getComments: (
    postId: number, 
    params: { user_id?: number; skip?: number; limit?: number }
  ) =>
    apiClient.get<CommentListResponse>(`/posts/${postId}/comments`, { params }),

  /**
   * 获取评论详情
   * GET /api/v1/posts/{post_id}/comments/{comment_id}
   */
  getComment: (postId: number, commentId: number, userId?: number) =>
    apiClient.get<Comment>(`/posts/${postId}/comments/${commentId}`, {
      params: userId ? { user_id: userId } : undefined,
    }),

  /**
   * 创建评论
   * POST /api/v1/posts/{post_id}/comments
   */
  createComment: (postId: number, data: CreateCommentData) =>
    apiClient.post<Comment>(`/posts/${postId}/comments`, data),

  /**
   * 删除评论
   * DELETE /api/v1/posts/{post_id}/comments/{comment_id}
   */
  deleteComment: (postId: number, commentId: number) =>
    apiClient.delete<void>(`/posts/${postId}/comments/${commentId}`),

  /**
   * 点赞/取消点赞评论
   * POST /api/v1/posts/{post_id}/comments/{comment_id}/like
   */
  toggleCommentLike: (postId: number, commentId: number) =>
    apiClient.post<CommentLikeResponse>(`/posts/${postId}/comments/${commentId}/like`),

  /**
   * 获取评论点赞状态
   * GET /api/v1/posts/{post_id}/comments/{comment_id}/like-status
   */
  getCommentLikeStatus: (postId: number, commentId: number) =>
    apiClient.get<CommentLikeResponse>(`/posts/${postId}/comments/${commentId}/like-status`),
};
```

### 5.3 评论树渲染 Hook

```typescript
// features/comment/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { commentApi } from './api';

/**
 * 获取评论树
 */
export const useComments = (postId: number, userId?: number) => {
  return useQuery({
    queryKey: ['comments', postId, userId],
    queryFn: () => commentApi.getComments(postId, { user_id: userId }),
    enabled: !!postId,
  });
};

/**
 * 创建评论（乐观更新）
 */
export const useCreateComment = (postId: number) => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateCommentData) => 
      commentApi.createComment(postId, data),
    onSuccess: () => {
      // 刷新评论列表
      queryClient.invalidateQueries({ queryKey: ['comments', postId] });
      // 刷新帖子评论数
      queryClient.invalidateQueries({ queryKey: ['post', postId] });
    },
  });
};

/**
 * 评论点赞（乐观更新）
 */
export const useToggleCommentLike = (postId: number) => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ commentId }: { commentId: number }) =>
      commentApi.toggleCommentLike(postId, commentId),
    onMutate: async ({ commentId }) => {
      await queryClient.cancelQueries({ queryKey: ['comments', postId] });
      
      const previousComments = queryClient.getQueryData<CommentListResponse>(
        ['comments', postId]
      );
      
      // 递归更新评论点赞状态
      const updateCommentLike = (comments: Comment[]): Comment[] => {
        return comments.map((comment) => {
          if (comment.id === commentId) {
            return {
              ...comment,
              is_liked: !comment.is_liked,
              like_count: comment.is_liked 
                ? comment.like_count - 1 
                : comment.like_count + 1,
            };
          }
          if (comment.children.length > 0) {
            return {
              ...comment,
              children: updateCommentLike(comment.children),
            };
          }
          return comment;
        });
      };
      
      queryClient.setQueryData<CommentListResponse>(
        ['comments', postId],
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: updateCommentLike(old.items),
          };
        }
      );
      
      return { previousComments };
    },
    onError: (_, __, context) => {
      if (context?.previousComments) {
        queryClient.setQueryData(['comments', postId], context.previousComments);
      }
    },
  });
};
```

---

## 六、点赞模块

### 6.1 类型定义

```typescript
// features/like/types.ts

export interface LikeResponse {
  post_id: number;
  like_count: number;
  is_liked: boolean;
}

export interface LikeStatusResponse {
  is_liked: boolean;
  like_count: number;
}
```

### 6.2 API 方法

```typescript
// features/like/api.ts
import { apiClient } from '@/shared/api/client';
import type { LikeResponse, LikeStatusResponse } from './types';

export const likeApi = {
  /**
   * 点赞/取消点赞帖子
   * POST /api/v1/posts/{post_id}/like
   */
  toggleLike: (postId: number) =>
    apiClient.post<LikeResponse>(`/posts/${postId}/like`),

  /**
   * 获取点赞状态
   * GET /api/v1/posts/{post_id}/like-status
   */
  getLikeStatus: (postId: number) =>
    apiClient.get<LikeStatusResponse>(`/posts/${postId}/like-status`),
};
```

### 6.3 点赞 Hook（乐观更新）

```typescript
// features/like/hooks.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { likeApi } from './api';

export const useToggleLike = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: likeApi.toggleLike,
    onMutate: async (postId: number) => {
      // 取消正在进行的重新获取
      await queryClient.cancelQueries({ queryKey: ['post', postId] });
      await queryClient.cancelQueries({ queryKey: ['feed'] });
      
      // 保存之前的状态
      const previousPost = queryClient.getQueryData(['post', postId]);
      
      // 乐观更新帖子详情
      queryClient.setQueryData(['post', postId], (old: any) => {
        if (!old) return old;
        const newIsLiked = !old.is_liked_by_current_user;
        return {
          ...old,
          is_liked_by_current_user: newIsLiked,
          like_count: newIsLiked ? old.like_count + 1 : old.like_count - 1,
        };
      });
      
      // 乐观更新信息流
      queryClient.setQueriesData({ queryKey: ['feed'] }, (old: any) => {
        if (!old?.data) return old;
        return {
          ...old,
          data: old.data.map((post: any) => {
            if (post.id === postId) {
              const newIsLiked = !post.is_liked;
              return {
                ...post,
                is_liked: newIsLiked,
                like_count: newIsLiked ? post.like_count + 1 : post.like_count - 1,
              };
            }
            return post;
          }),
        };
      });
      
      return { previousPost };
    },
    onError: (err, postId, context) => {
      // 回滚
      if (context?.previousPost) {
        queryClient.setQueryData(['post', postId], context.previousPost);
      }
    },
  });
};
```

---

## 七、信息流模块

### 7.1 类型定义

```typescript
// features/feed/types.ts
import type { Post } from '@/features/post/types';

export interface PostFeedItem extends Post {
  author_name: string;
  author_avatar: string | null;
}

export interface FeedParams {
  page?: number;
  page_size?: number;
  current_user_id?: number;
}
```

### 7.2 API 方法

```typescript
// features/feed/api.ts
import { apiClient } from '@/shared/api/client';
import type { PostFeedItem, FeedParams } from './types';
import type { PaginatedResponse } from '@/shared/types/api';

export const feedApi = {
  /**
   * 获取全局信息流
   * GET /api/v1/feeds/feed/all
   */
  getGlobalFeed: (params: FeedParams = {}) =>
    apiClient.get<PaginatedResponse<PostFeedItem>>('/feeds/feed/all', { params }),

  /**
   * 获取用户帖子流
   * GET /api/v1/feeds/feed/user/{user_id}
   */
  getUserFeed: (userId: number, params: FeedParams = {}) =>
    apiClient.get<PaginatedResponse<PostFeedItem>>(`/feeds/feed/user/${userId}`, { params }),
};
```

### 7.3 无限滚动 Hook

```typescript
// features/feed/hooks.ts
import { useInfiniteQuery } from '@tanstack/react-query';
import { feedApi } from './api';
import type { FeedParams } from './types';

const DEFAULT_PAGE_SIZE = 20;

/**
 * 全局信息流无限滚动
 */
export const useInfiniteGlobalFeed = (userId?: number) => {
  return useInfiniteQuery({
    queryKey: ['feed', 'global', userId],
    queryFn: ({ pageParam = 1 }) =>
      feedApi.getGlobalFeed({
        page: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
        current_user_id: userId,
      }),
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
  });
};

/**
 * 用户帖子流无限滚动
 */
export const useInfiniteUserFeed = (targetUserId: number, currentUserId?: number) => {
  return useInfiniteQuery({
    queryKey: ['feed', 'user', targetUserId, currentUserId],
    queryFn: ({ pageParam = 1 }) =>
      feedApi.getUserFeed(targetUserId, {
        page: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
        current_user_id: currentUserId,
      }),
    getNextPageParam: (lastPage) => {
      if (lastPage.pagination.has_next) {
        return lastPage.pagination.page + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
    enabled: !!targetUserId,
  });
};
```

---

## 八、API 客户端完整实现

```typescript
// shared/api/client.ts
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/features/auth/stores/authStore';
import { API_CONFIG } from '@/shared/config/api';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // 请求拦截器
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = useAuthStore.getState().token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response.data,
      (error: AxiosError<{ detail: string }>) => {
        const status = error.response?.status;
        const message = error.response?.data?.detail || '请求失败';

        // 处理 401 未授权
        if (status === 401) {
          useAuthStore.getState().logout();
          window.location.href = '/login';
        }

        return Promise.reject({
          status,
          message,
          originalError: error,
        });
      }
    );
  }

  // GET 请求
  async get<T>(url: string, config?: any): Promise<T> {
    return this.client.get(url, config);
  }

  // POST 请求
  async post<T>(url: string, data?: any, config?: any): Promise<T> {
    return this.client.post(url, data, config);
  }

  // PUT 请求
  async put<T>(url: string, data?: any, config?: any): Promise<T> {
    return this.client.put(url, data, config);
  }

  // DELETE 请求
  async delete<T>(url: string, config?: any): Promise<T> {
    return this.client.delete(url, config);
  }
}

export const apiClient = new ApiClient();
```

---

## 九、使用示例

### 9.1 完整页面示例

```typescript
// pages/feed/FeedPage.tsx
import { useEffect, useRef } from 'react';
import { useInfiniteGlobalFeed } from '@/features/feed/hooks';
import { useToggleLike } from '@/features/like/hooks';
import { PostCard } from '@/widgets/post-card';
import { useAuthStore } from '@/features/auth/stores/authStore';

export const FeedPage: React.FC = () => {
  const { user } = useAuthStore();
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteGlobalFeed(user?.id);
  
  const { mutate: toggleLike } = useToggleLike();
  
  // 无限滚动监听
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (observerRef.current) {
      observerRef.current.disconnect();
    }
    
    observerRef.current = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    });
    
    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }
    
    return () => observerRef.current?.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);
  
  const posts = data?.pages.flatMap((page) => page.data) || [];
  
  if (isLoading) {
    return <FeedSkeleton />;
  }
  
  return (
    <div className="space-y-4">
      {posts.map((post) => (
        <PostCard
          key={post.id}
          post={post}
          onLike={() => toggleLike(post.id)}
        />
      ))}
      
      <div ref={loadMoreRef} className="py-4 text-center">
        {isFetchingNextPage && <LoadingSpinner />}
        {!hasNextPage && posts.length > 0 && (
          <span className="text-gray-500">没有更多内容了</span>
        )}
      </div>
    </div>
  );
};
```

---

## 十、错误处理最佳实践

```typescript
// shared/hooks/useApiError.ts
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

export const useApiError = () => {
  const navigate = useNavigate();
  
  return useCallback((error: any) => {
    const status = error?.status;
    const message = error?.message || '操作失败';
    
    switch (status) {
      case 400:
        toast.error(message);
        break;
      case 401:
        toast.error('登录已过期，请重新登录');
        navigate('/login');
        break;
      case 403:
        toast.error('没有权限执行此操作');
        break;
      case 404:
        toast.error('请求的资源不存在');
        break;
      case 500:
        toast.error('服务器错误，请稍后重试');
        break;
      default:
        toast.error(message);
    }
  }, [navigate]);
};

// 使用示例
const MyComponent = () => {
  const handleError = useApiError();
  const { mutate, isPending } = useMutation({
    mutationFn: createPost,
    onError: handleError,
    onSuccess: () => {
      toast.success('发布成功');
    },
  });
};
```

---

## 十一、Mock 数据（开发用）

```typescript
// mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/v1/feeds/feed/all', () => {
    return HttpResponse.json({
      code: 200,
      message: 'success',
      data: [
        {
          id: 1,
          title: '今天也是三月七！',
          content: '今天拍了很多好看的照片~',
          created_at: '2026-03-22T10:00:00',
          author_id: 1,
          author_name: '三月七',
          author_avatar: '/avatars/三月七.jpg',
          like_count: 42,
          comment_count: 8,
          is_liked: false,
        },
      ],
      pagination: {
        page: 1,
        page_size: 20,
        total: 100,
        total_pages: 5,
        has_next: true,
        has_prev: false,
      },
    });
  }),
  // ... 更多 mock
];
```

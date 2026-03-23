# 前端实现文档

## 版本信息

- **时间**: 2026.3.23 8:00
- **版本**: Alpha-v1.7.4-docs: 前端文档小结
- **作者**: Herta-Tree 开发团队

---

## 功能概述

本次文档总结全面梳理了 Herta-Tree 社交平台前端实现，基于 React 19 + TypeScript + Vite 技术栈，采用 Feature-Based 架构设计，实现了完整的用户认证、信息流、帖子、评论、点赞等核心功能模块。

### 核心特性

- ✅ React 19 + TypeScript 5.4 现代化技术栈
- ✅ Feature-Based 模块化架构
- ✅ TanStack Query 服务端状态管理
- ✅ Zustand 客户端状态管理
- ✅ Tailwind CSS + Radix UI 组件库
- ✅ JWT Token 认证机制
- ✅ 乐观更新优化用户体验
- ✅ 无限滚动加载
- ✅ 完整的类型安全

---

## 技术栈

### 核心框架

| 技术 | 版本 | 用途 |
|------|------|------|
| React | ^19.0.0 | UI 框架 |
| React DOM | ^19.0.0 | DOM 渲染 |
| React Router DOM | ^7.0.0 | 路由管理 |
| TypeScript | ^5.4.0 | 类型系统 |
| Vite | ^5.0.0 | 构建工具 |

### 状态管理

| 技术 | 版本 | 用途 |
|------|------|------|
| TanStack Query | ^5.24.0 | 服务端状态管理 |
| Zustand | ^4.5.0 | 客户端状态管理 |

### UI 组件

| 技术 | 版本 | 用途 |
|------|------|------|
| Tailwind CSS | ^3.4.0 | CSS 框架 |
| Radix UI | ^1.0.5 | 无头组件库 |
| Lucide React | ^0.344.0 | 图标库 |
| Framer Motion | ^11.0.0 | 动画库 |
| class-variance-authority | ^0.7.0 | 组件变体管理 |
| tailwind-merge | ^2.2.0 | Tailwind 类名合并 |

### 工具库

| 技术 | 版本 | 用途 |
|------|------|------|
| Axios | ^1.6.7 | HTTP 客户端 |
| date-fns | ^3.3.1 | 日期处理 |
| Zod | ^3.22.4 | 数据校验 |
| React Hook Form | ^7.50.0 | 表单管理 |

---

## 项目架构

### 目录结构

```
frontend/
├── src/
│   ├── app/                    # 应用入口层
│   │   ├── main.tsx           # 应用入口
│   │   ├── router.tsx         # 路由配置
│   │   ├── providers.tsx      # 全局 Provider
│   │   └── styles/            # 全局样式
│   │
│   ├── features/              # 功能模块层 (Feature-Based)
│   │   ├── auth/              # 认证模块
│   │   ├── feed/              # 信息流模块
│   │   ├── post/              # 帖子模块
│   │   ├── comment/           # 评论模块
│   │   ├── like/              # 点赞模块
│   │   └── user/              # 用户模块
│   │
│   ├── pages/                 # 页面层
│   │   ├── auth/              # 认证页面
│   │   ├── feed/              # 信息流页面
│   │   ├── post/              # 帖子详情页面
│   │   └── profile/           # 用户资料页面
│   │
│   ├── widgets/               # 业务组件层
│   │   ├── layout/            # 布局组件
│   │   ├── post-card/         # 帖子卡片
│   │   ├── comment-list/      # 评论列表
│   │   └── create-post-form/  # 创建帖子表单
│   │
│   └── shared/                # 共享层
│       ├── api/               # API 客户端
│       ├── components/ui/     # 基础 UI 组件
│       ├── config/            # 配置文件
│       └── types/             # 全局类型
│
├── docs/                      # 文档目录
├── public/                    # 静态资源
├── index.html                 # HTML 模板
├── vite.config.ts            # Vite 配置
├── tailwind.config.js        # Tailwind 配置
├── tsconfig.json             # TypeScript 配置
└── package.json              # 依赖配置
```

### 架构分层说明

#### 1. App 层 (应用入口层)

负责应用初始化和全局配置：

- **main.tsx**: React 应用入口，挂载根组件
- **router.tsx**: 定义应用路由结构
- **providers.tsx**: 组合所有全局 Provider (QueryClientProvider 等)
- **styles/globals.css**: 全局样式和 CSS 变量

#### 2. Features 层 (功能模块层)

按业务功能划分的模块，每个模块包含：

```
features/{feature}/
├── api.ts          # API 请求
├── hooks.ts        # React Query Hooks
├── types.ts        # 类型定义
├── index.ts        # 模块导出
└── components/     # 模块专属组件 (可选)
└── stores/         # 模块状态 (可选)
```

#### 3. Pages 层 (页面层)

对应路由的页面组件，组合 widgets 和 features：

- **FeedPage**: 信息流首页
- **PostDetailPage**: 帖子详情页
- **ProfilePage**: 用户资料页
- **LoginPage/RegisterPage**: 认证页面

#### 4. Widgets 层 (业务组件层)

可复用的业务组件：

- **RootLayout/Header**: 布局组件
- **PostCard**: 帖子卡片（含评论预览、点赞、回复功能）
- **CommentList**: 评论列表（递归嵌套显示）
- **CreatePostForm**: 创建帖子表单

#### 5. Shared 层 (共享层)

全局共享的基础设施：

- **api/client.ts**: 封装 Axios，统一请求处理和错误处理
- **components/ui/**: 基础 UI 组件 (Button, Input, Avatar 等)
- **config/api.ts**: API 配置和常量
- **types/api.ts**: 全局类型定义

---

## 功能模块详解

### 1. 认证模块 (auth)

#### 文件结构

```
features/auth/
├── api.ts
├── hooks.ts
├── types.ts
├── stores/authStore.ts
├── components/AuthGuard.tsx
└── index.ts
```

#### 核心功能

- **用户登录**: `useLogin` Hook，成功后保存 Token 和用户信息
- **用户注册**: `useRegister` Hook
- **获取当前用户**: `useCurrentUser` Hook
- **登出**: `useLogout` Hook，清除状态和缓存
- **路由守卫**: `AuthGuard` 组件保护需要登录的路由

#### 状态管理

使用 Zustand + persist 中间件实现状态持久化：

```typescript
interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
}
```

#### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/auth/login` | POST | 用户登录 |
| `/auth/register` | POST | 用户注册 |
| `/auth/me` | GET | 获取当前用户 |

---

### 2. 信息流模块 (feed)

#### 文件结构

```
features/feed/
├── api.ts
├── hooks.ts
├── types.ts
└── index.ts
```

#### 核心功能

- **全局信息流**: `useInfiniteGlobalFeed` 无限滚动 Hook
- **用户帖子流**: `useInfiniteUserFeed` 用户专属帖子流

#### 数据类型

```typescript
interface PostFeedItem extends Post {
  author_name: string;
  author_avatar: string | null;
  is_liked: boolean;
}

interface FeedParams {
  page?: number;
  page_size?: number;
  current_user_id?: number;
}
```

#### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/feeds/feed/all` | GET | 全局信息流 |
| `/feeds/feed/user/{user_id}` | GET | 用户帖子流 |

---

### 3. 帖子模块 (post)

#### 文件结构

```
features/post/
├── api.ts
├── hooks.ts
├── types.ts
└── index.ts
```

#### 核心功能

- **获取帖子列表**: `usePosts`
- **获取帖子详情**: `usePost`
- **创建帖子**: `useCreatePost`
- **更新帖子**: `useUpdatePost`
- **删除帖子**: `useDeletePost`
- **获取用户帖子**: `useUserPosts`

#### 数据类型

```typescript
interface Post {
  id: number;
  author_id: number;
  title: string | null;
  content: string;
  created_at: string;
  like_count: number;
  comment_count: number;
}

interface PostWithLikeStatus extends Post {
  is_liked_by_current_user: boolean;
}
```

#### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/posts/` | GET | 获取帖子列表 |
| `/posts/{post_id}` | GET | 获取帖子详情 |
| `/posts/` | POST | 创建帖子 |
| `/posts/{post_id}` | PUT | 更新帖子 |
| `/posts/{post_id}` | DELETE | 删除帖子 |
| `/posts/user/{user_id}` | GET | 获取用户帖子 |

---

### 4. 评论模块 (comment)

#### 文件结构

```
features/comment/
├── api.ts
├── hooks.ts
├── types.ts
└── index.ts
```

#### 核心功能

- **获取评论树**: `useComments` 获取帖子的评论树结构
- **创建评论**: `useCreateComment` 支持一级评论和回复
- **删除评论**: `useDeleteComment`
- **评论点赞**: `useToggleCommentLike` 乐观更新

#### 数据类型

```typescript
interface Comment {
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
  children: Comment[];  // 嵌套回复
}

interface CommentListResponse {
  items: Comment[];
  total: number;
  skip: number;
  limit: number;
}
```

#### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/posts/{post_id}/comments` | GET | 获取评论树 |
| `/posts/{post_id}/comments` | POST | 创建评论 |
| `/posts/{post_id}/comments/{comment_id}` | DELETE | 删除评论 |
| `/posts/{post_id}/comments/{comment_id}/like` | POST | 评论点赞 |
| `/posts/{post_id}/comments/{comment_id}/like-status` | GET | 点赞状态 |

---

### 5. 点赞模块 (like)

#### 文件结构

```
features/like/
├── api.ts
├── hooks.ts
├── types.ts
└── index.ts
```

#### 核心功能

- **切换点赞**: `useToggleLike` 乐观更新帖子点赞状态
- **评论点赞**: 集成在 comment 模块

#### 乐观更新策略

```typescript
// 1. 取消正在进行的重新获取
await queryClient.cancelQueries({ queryKey: ['post', postId] });
await queryClient.cancelQueries({ queryKey: ['feed'] });

// 2. 保存之前的状态
const previousPosts = queryCache.findAll({ queryKey: ['post', postId] });

// 3. 乐观更新缓存
queryClient.setQueriesData({ queryKey: ['post', postId] }, (old) => ({
  ...old,
  is_liked_by_current_user: !old.is_liked_by_current_user,
  like_count: newIsLiked ? old.like_count + 1 : old.like_count - 1,
}));

// 4. 错误时回滚
onError: (_, postId, context) => {
  context.previousPosts.forEach(({ queryKey, data }) => {
    queryClient.setQueryData(queryKey, data);
  });
}
```

#### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/posts/{post_id}/like` | POST | 点赞/取消点赞 |
| `/posts/{post_id}/like-status` | GET | 获取点赞状态 |

---

### 6. 用户模块 (user)

#### 文件结构

```
features/user/
├── api.ts
├── hooks.ts
├── types.ts
└── index.ts
```

#### 核心功能

- **获取用户列表**: `useUsers`
- **获取用户详情**: `useUser`
- **通过用户名获取用户**: `useUserByUsername`
- **更新用户信息**: `useUpdateUser`
- **删除用户**: `useDeleteUser`

#### 数据类型

```typescript
interface UserProfile {
  id: number;
  username: string;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
}
```

#### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/users/` | GET | 获取用户列表 |
| `/users/{user_id}` | GET | 获取用户详情 |
| `/users/username/{username}` | GET | 通过用户名获取 |
| `/users/{user_id}` | PUT | 更新用户信息 |
| `/users/{user_id}` | DELETE | 删除用户 |

---

## API 客户端设计

### 封装 Axios

```typescript
class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT,
    });
    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // 请求拦截器：添加认证 Token
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // 响应拦截器：统一错误处理
    this.client.interceptors.response.use(
      (response) => response.data,
      (error) => {
        // 401 未授权处理
        if (status === 401) {
          localStorage.removeItem('token');
          window.location.href = '/login';
        }
        return Promise.reject(apiError);
      }
    );
  }
}
```

### 错误处理

```typescript
interface ApiErrorException {
  name: 'ApiErrorException';
  status: number;
  message: string;
  code?: string;
}
```

---

## 路由设计

### 路由配置

```typescript
export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <Navigate to="/feed" replace /> },

      // 公开路由
      { path: 'feed', element: <FeedPage /> },
      { path: 'post/:postId', element: <PostDetailPage /> },
      { path: 'user/:userId', element: <ProfilePage /> },

      // 认证路由
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },

      // 受保护路由
      {
        element: <AuthGuard />,
        children: [
          // 需要登录的页面
        ],
      },
    ],
  },
]);
```

### 路由说明

| 路由 | 页面 | 认证要求 |
|------|------|----------|
| `/` | 重定向到 `/feed` | 无 |
| `/feed` | 信息流首页 | 无 |
| `/post/:postId` | 帖子详情 | 无 |
| `/user/:userId` | 用户资料 | 无 |
| `/login` | 登录页 | 无 |
| `/register` | 注册页 | 无 |

---

## UI 组件设计

### 基础组件 (shared/components/ui)

| 组件 | 说明 |
|------|------|
| Button | 按钮组件，支持多种变体和尺寸 |
| Input | 输入框组件 |
| Textarea | 文本域组件 |
| Avatar | 头像组件，支持多种尺寸 |
| Card | 卡片容器组件 |
| Skeleton | 骨架屏加载组件 |

### 组件变体管理

使用 class-variance-authority (CVA) 管理组件变体：

```typescript
const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-8 px-3',
      },
    },
  }
);
```

---

## 状态管理策略

### 服务端状态 (TanStack Query)

- **数据获取**: 使用 `useQuery` 获取数据
- **数据修改**: 使用 `useMutation` 修改数据
- **无限滚动**: 使用 `useInfiniteQuery` 实现分页加载
- **缓存策略**: 根据数据类型设置不同的 staleTime

```typescript
// 缓存时间配置
export const CACHE_TIME = {
  USER: 5 * 60 * 1000,    // 5分钟
  POST: 5 * 60 * 1000,    // 5分钟
  FEED: 2 * 60 * 1000,    // 2分钟
  COMMENT: 3 * 60 * 1000, // 3分钟
};
```

### 客户端状态 (Zustand)

- **认证状态**: 用户信息、Token、登录状态
- **持久化**: 使用 persist 中间件自动同步到 localStorage

---

## 关键功能实现

### 1. 无限滚动加载

```typescript
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
```

### 2. 评论树递归渲染

```typescript
function CommentItem({ comment, depth }: CommentItemProps) {
  const isTopLevel = depth === 0;
  const hasReplies = comment.children && comment.children.length > 0;

  return (
    <div>
      {/* 评论内容 */}
      <div className="flex gap-3">
        {/* ... */}
      </div>

      {/* 递归渲染回复 */}
      {showReplies && hasReplies && (
        <div className={isTopLevel ? 'ml-12' : 'ml-0'}>
          {comment.children.map((child) => (
            <CommentItem
              key={child.id}
              comment={child}
              depth={depth + 1}
              parentOwner={{ id: comment.owner_id, username: comment.owner.username }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

### 3. 乐观更新实现

```typescript
export const useToggleLike = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: likeApi.toggleLike,
    onMutate: async (postId: number) => {
      // 取消相关查询
      await queryClient.cancelQueries({ queryKey: ['post', postId] });
      await queryClient.cancelQueries({ queryKey: ['feed'] });

      // 保存之前状态
      const previousPosts = queryCache.findAll({ queryKey: ['post', postId] });

      // 乐观更新帖子详情
      queryClient.setQueriesData({ queryKey: ['post', postId] }, (old) => ({
        ...old,
        is_liked_by_current_user: !old.is_liked_by_current_user,
        like_count: newIsLiked ? old.like_count + 1 : old.like_count - 1,
      }));

      // 乐观更新信息流
      queryClient.setQueriesData({ queryKey: ['feed'] }, (old) => ({
        ...old,
        pages: old.pages.map((page) => ({
          ...page,
          data: page.data.map((post) =>
            post.id === postId
              ? { ...post, is_liked: !post.is_liked, like_count: newCount }
              : post
          ),
        })),
      }));

      return { previousPosts };
    },
    onError: (_, postId, context) => {
      // 回滚状态
      context.previousPosts.forEach(({ queryKey, data }) => {
        queryClient.setQueryData(queryKey, data);
      });
    },
  });
};
```

---

## 构建配置

### Vite 配置

```typescript
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
});
```

### 代码分割策略

- **vendor**: React 核心库
- **ui**: Radix UI 组件
- **query**: TanStack Query

---

## 开发规范

### 代码风格

- **ESLint**: 代码质量检查
- **Prettier**: 代码格式化
- **TypeScript**: 严格类型检查
- **Husky**: Git 钩子管理
- **lint-staged**: 暂存文件检查

### 脚本命令

```bash
# 开发
pnpm dev

# 构建
pnpm build

# 代码检查
pnpm lint
pnpm lint:fix
pnpm format

# 类型检查
pnpm type-check

# 测试
pnpm test
```

---

## 后续优化建议

### 性能优化

1. **虚拟列表**: 长列表使用 react-window 或 react-virtualized
2. **图片懒加载**: 头像和帖子图片懒加载
3. **预加载**: 路由预加载和组件预加载
4. **Service Worker**: 离线缓存支持

### 功能扩展

1. **图片上传**: 支持帖子图片上传
2. **富文本编辑**: 帖子内容支持富文本
3. **实时通知**: WebSocket 实时消息推送
4. **搜索功能**: 用户和帖子搜索
5. **深色模式**: 支持主题切换

### 测试覆盖

1. **单元测试**: Jest + React Testing Library
2. **E2E 测试**: Playwright 或 Cypress
3. **视觉回归**: Storybook + Chromatic

---

## 注意事项

1. **Token 管理**: Token 存储在 localStorage，注意 XSS 防护
2. **错误处理**: 统一的错误处理和用户提示
3. **类型安全**: 所有 API 响应都有对应的 TypeScript 类型
4. **缓存策略**: 根据数据更新频率设置合适的缓存时间
5. **乐观更新**: 点赞操作使用乐观更新，失败时自动回滚

---

**文档更新时间**: 2026.3.23 8:00
**版本**: Alpha-v1.7.4-docs: 前端文档小结

# Herta-Tree 前端开发指南

## 一、开发环境准备

### 1.1 环境要求

- **Node.js**: >= 18.0.0
- **npm**: >= 9.0.0 或 **pnpm**: >= 8.0.0
- **Git**: >= 2.30.0

### 1.2 项目初始化

```bash
# 克隆项目
git clone <repository-url>
cd Herta-Tree/frontend

# 安装依赖（推荐使用 pnpm）
pnpm install

# 启动开发服务器
pnpm dev
```

### 1.3 环境变量配置

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Herta-Tree
VITE_APP_VERSION=0.1.0
```

---

## 二、项目结构详解

### 2.1 目录结构说明

```
src/
├── app/                    # 应用入口和全局配置
│   ├── main.tsx           # 应用入口文件
│   ├── router.tsx         # 路由配置
│   ├── providers.tsx      # 全局 Provider 组合
│   └── styles/            # 全局样式
│       ├── globals.css    # 全局 CSS
│       └── variables.css  # CSS 变量
│
├── features/              # 功能模块（按业务划分）
│   ├── auth/              # 认证模块
│   │   ├── api.ts         # API 请求
│   │   ├── hooks.ts       # React Query Hooks
│   │   ├── types.ts       # 类型定义
│   │   ├── stores/        # Zustand 状态管理
│   │   └── components/    # 组件
│   ├── feed/              # 信息流模块
│   ├── post/              # 帖子模块
│   ├── comment/           # 评论模块
│   ├── user/              # 用户模块
│   └── like/              # 点赞模块
│
├── pages/                 # 页面组件
│   ├── feed/
│   │   └── FeedPage.tsx
│   ├── post/
│   │   └── PostDetailPage.tsx
│   ├── profile/
│   │   └── ProfilePage.tsx
│   └── auth/
│       ├── LoginPage.tsx
│       └── RegisterPage.tsx
│
├── widgets/               # 复合组件（跨功能组合）
│   ├── header/
│   ├── sidebar/
│   ├── post-card/
│   ├── comment-tree/
│   └── layout/
│
├── shared/                # 共享资源
│   ├── api/               # API 客户端
│   │   ├── client.ts      # Axios 封装
│   │   └── error-handler.ts
│   ├── components/        # 通用组件
│   │   ├── ui/            # 基础 UI 组件
│   │   ├── common/        # 通用业务组件
│   │   └── layout/        # 布局组件
│   ├── hooks/             # 通用 Hooks
│   ├── utils/             # 工具函数
│   ├── lib/               # 第三方库封装
│   ├── types/             # 全局类型
│   └── config/            # 配置文件
│
└── mocks/                 # Mock 数据（开发用）
    ├── handlers.ts
    └── browser.ts
```

### 2.2 模块职责说明

| 目录 | 职责 | 导入规则 |
|------|------|---------|
| `app/` | 应用初始化、全局配置 | 只能导入 `shared/`, `features/` |
| `features/` | 业务功能模块 | 可导入 `shared/`, 不可导入 `pages/`, `widgets/` |
| `pages/` | 页面组装 | 可导入所有模块 |
| `widgets/` | 跨功能复合组件 | 可导入 `shared/`, `features/` |
| `shared/` | 共享资源 | 不可导入业务模块 |

---

## 三、开发规范

### 3.1 命名规范

```typescript
// 文件命名
// components/: PascalCase.tsx
PostCard.tsx
CommentTree.tsx

// hooks/: camelCase, use 前缀
useAuth.ts
useInfiniteFeed.ts

// utils/: camelCase
formatDate.ts
debounce.ts

// 类型: PascalCase
type UserProfile = { ... }
interface PostProps { ... }

// 常量: UPPER_SNAKE_CASE
const API_BASE_URL = '...'
const DEFAULT_PAGE_SIZE = 20
```

### 3.2 组件开发规范

```typescript
// ✅ 好的实践

// 1. 使用函数组件 + TypeScript
interface PostCardProps {
  post: PostFeedItem;
  onLike?: (postId: number) => void;
}

export const PostCard: React.FC<PostCardProps> = ({ post, onLike }) => {
  // 组件逻辑
  return (
    <article className="...">
      {/* JSX */}
    </article>
  );
};

// 2. 使用 default export 导出页面
export default function FeedPage() {
  return <div>...</div>;
}

// 3. 使用 named export 导出组件
export { PostCard };
export * from './types';

// ❌ 避免的做法

// 不要使用 any
function badFunction(props: any) { ... }

// 不要省略返回类型（复杂组件）
function Component(props) { ... }

// 不要混合默认导出和命名导出
export default PostCard;
export { PostCard };
```

### 3.3 Hooks 开发规范

```typescript
// ✅ 好的实践

// 1. 自定义 Hook 以 use 开头
export function useInfiniteFeed(userId?: number) {
  return useInfiniteQuery({
    queryKey: ['feed', 'global', userId],
    queryFn: fetchFeed,
  });
}

// 2. 在 Hook 内部处理错误
export function useCreatePost() {
  const queryClient = useQueryClient();
  const handleError = useApiError();
  
  return useMutation({
    mutationFn: postApi.createPost,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      toast.success('发布成功');
    },
    onError: handleError,
  });
}

// 3. 返回明确的类型
interface UseAuthReturn {
  user: User | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

export function useAuth(): UseAuthReturn {
  // ...
}
```

### 3.4 状态管理规范

```typescript
// ✅ 服务端状态 - 使用 TanStack Query
// features/post/hooks.ts
export const usePost = (postId: number) => {
  return useQuery({
    queryKey: ['post', postId],
    queryFn: () => postApi.getPost(postId),
    staleTime: 5 * 60 * 1000, // 5分钟
  });
};

// ✅ 客户端状态 - 使用 Zustand
// features/auth/stores/authStore.ts
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      login: async (credentials) => {
        const { user, token } = await authApi.login(credentials);
        set({ user, token, isAuthenticated: true });
      },
      logout: () => {
        set({ user: null, token: null, isAuthenticated: false });
      },
    }),
    { name: 'auth-storage' }
  )
);

// ❌ 避免的做法

// 不要混合服务端和客户端状态
const [posts, setPosts] = useState([]); // 服务端状态应该用 useQuery

// 不要过度使用全局状态
// 只有真正需要全局共享的状态才使用 Zustand
```

---

## 四、功能开发流程

### 4.1 添加新功能的标准流程

以添加"收藏"功能为例：

#### 步骤 1: 创建功能模块

```bash
mkdir -p src/features/favorite/{api,components,stores}
touch src/features/favorite/{api.ts,hooks.ts,types.ts,index.ts}
```

#### 步骤 2: 定义类型

```typescript
// src/features/favorite/types.ts
export interface Favorite {
  id: number;
  post_id: number;
  user_id: number;
  created_at: string;
}

export interface FavoriteListResponse {
  items: Favorite[];
  total: number;
}
```

#### 步骤 3: 实现 API 层

```typescript
// src/features/favorite/api.ts
import { apiClient } from '@/shared/api/client';
import type { Favorite, FavoriteListResponse } from './types';

export const favoriteApi = {
  getFavorites: (params: { page?: number; page_size?: number }) =>
    apiClient.get<FavoriteListResponse>('/favorites', { params }),
  
  addFavorite: (postId: number) =>
    apiClient.post<Favorite>('/favorites', { post_id: postId }),
  
  removeFavorite: (postId: number) =>
    apiClient.delete<void>(`/favorites/${postId}`),
};
```

#### 步骤 4: 实现 Hooks

```typescript
// src/features/favorite/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { favoriteApi } from './api';

export const useFavorites = (params?: { page?: number; page_size?: number }) => {
  return useQuery({
    queryKey: ['favorites', params],
    queryFn: () => favoriteApi.getFavorites(params || {}),
  });
};

export const useAddFavorite = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: favoriteApi.addFavorite,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['favorites'] });
      toast.success('收藏成功');
    },
  });
};
```

#### 步骤 5: 导出模块

```typescript
// src/features/favorite/index.ts
export * from './types';
export * from './api';
export * from './hooks';
```

#### 步骤 6: 创建页面（如果需要）

```typescript
// src/pages/favorites/FavoritesPage.tsx
import { useFavorites } from '@/features/favorite';

export default function FavoritesPage() {
  const { data, isLoading } = useFavorites();
  
  // ...
}
```

#### 步骤 7: 添加路由

```typescript
// src/app/router.tsx
{
  path: 'favorites',
  element: <AuthGuard />,
  children: [
    { index: true, element: <FavoritesPage /> },
  ],
},
```

---

## 五、样式开发规范

### 5.1 Tailwind CSS 使用规范

```tsx
// ✅ 好的实践

// 1. 使用 @apply 提取重复样式（组件级别）
// PostCard.module.css
.post-card {
  @apply rounded-lg border bg-white p-4 shadow-sm;
}

.post-card:hover {
  @apply shadow-md;
}

// 2. 使用 clsx/cn 处理条件样式
import { cn } from '@/shared/lib/utils';

<button
  className={cn(
    'rounded px-4 py-2 font-medium',
    isActive 
      ? 'bg-primary text-white' 
      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
  )}
>
  按钮
</button>

// 3. 使用 Tailwind 的响应式前缀
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

// 4. 自定义主题变量
// tailwind.config.ts
theme: {
  extend: {
    colors: {
      primary: {
        50: '#f0f9ff',
        500: '#0ea5e9',
        900: '#0c4a6e',
      },
    },
  },
}

// ❌ 避免的做法

// 不要写死像素值
<div className="w-[100px] h-[50px]">

// 不要过度使用 !important
<div className="!p-4">

// 不要混合使用多种单位
<div className="p-4 m-[10px]">
```

### 5.2 组件样式组织

```tsx
// widgets/post-card/PostCard.tsx
import styles from './PostCard.module.css';

export const PostCard: React.FC<PostCardProps> = ({ post }) => {
  return (
    <article className={styles.container}>
      <header className={styles.header}>
        {/* ... */}
      </header>
      <div className={styles.content}>
        {/* ... */}
      </div>
      <footer className={styles.footer}>
        {/* ... */}
      </footer>
    </article>
  );
};

// widgets/post-card/PostCard.module.css
.container {
  @apply rounded-lg border bg-card p-4 shadow-sm transition-shadow;
}

.container:hover {
  @apply shadow-md;
}

.header {
  @apply flex items-center gap-3 mb-3;
}

.content {
  @apply space-y-2;
}

.footer {
  @apply flex items-center gap-4 mt-4 pt-3 border-t;
}
```

---

## 六、测试规范

### 6.1 单元测试

```typescript
// features/auth/stores/authStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from './authStore';

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  });

  it('should set auth state on login', () => {
    useAuthStore.getState().setAuth('token123', 3600);
    
    expect(useAuthStore.getState().token).toBe('token123');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('should clear auth state on logout', () => {
    useAuthStore.getState().setAuth('token123', 3600);
    useAuthStore.getState().logout();
    
    expect(useAuthStore.getState().token).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
```

### 6.2 组件测试

```typescript
// widgets/post-card/PostCard.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PostCard } from './PostCard';

const mockPost = {
  id: 1,
  title: '测试帖子',
  content: '测试内容',
  author_name: '测试用户',
  like_count: 10,
  comment_count: 5,
  is_liked: false,
};

describe('PostCard', () => {
  it('should render post content', () => {
    render(<PostCard post={mockPost} />);
    
    expect(screen.getByText('测试帖子')).toBeInTheDocument();
    expect(screen.getByText('测试内容')).toBeInTheDocument();
  });

  it('should call onLike when like button clicked', () => {
    const onLike = vi.fn();
    render(<PostCard post={mockPost} onLike={onLike} />);
    
    fireEvent.click(screen.getByRole('button', { name: /点赞/i }));
    
    expect(onLike).toHaveBeenCalledWith(1);
  });
});
```

---

## 七、性能优化指南

### 7.1 列表渲染优化

```tsx
// ✅ 使用虚拟化渲染长列表
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualFeed({ posts }: { posts: Post[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  
  const virtualizer = useVirtualizer({
    count: posts.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 200,
  });

  return (
    <div ref={parentRef} className="h-[600px] overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            <PostCard post={posts[virtualItem.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 7.2 图片优化

```tsx
// ✅ 使用懒加载和占位符
<img
  src={avatarUrl}
  alt={username}
  loading="lazy"
  className="w-10 h-10 rounded-full object-cover"
  onError={(e) => {
    e.currentTarget.src = '/default-avatar.png';
  }}
/>

// ✅ 使用响应式图片
<picture>
  <source srcSet="image.webp" type="image/webp" />
  <img src="image.jpg" alt="..." />
</picture>
```

### 7.3 代码分割

```tsx
// ✅ 路由级别懒加载
const FeedPage = lazy(() => import('@/pages/feed/FeedPage'));
const PostDetailPage = lazy(() => import('@/pages/post/PostDetailPage'));

// ✅ 组件级别懒加载（大组件）
const RichTextEditor = lazy(() => import('@/shared/components/RichTextEditor'));

// 使用 Suspense 包裹
<Suspense fallback={<LoadingSpinner />}>
  <RichTextEditor />
</Suspense>
```

---

## 八、调试技巧

### 8.1 React Query DevTools

```tsx
// app/providers.tsx
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
```

### 8.2 Zustand DevTools

```ts
// features/auth/stores/authStore.ts
import { devtools } from 'zustand/middleware';

export const useAuthStore = create<AuthState>()(
  devtools(
    persist(...),
    { name: 'AuthStore' }
  )
);
```

### 8.3 日志记录

```ts
// shared/lib/logger.ts
export const logger = {
  debug: (...args: any[]) => {
    if (import.meta.env.DEV) {
      console.debug('[DEBUG]', ...args);
    }
  },
  info: (...args: any[]) => console.info('[INFO]', ...args),
  error: (...args: any[]) => console.error('[ERROR]', ...args),
};
```

---

## 九、常见问题解决

### 9.1 类型问题

```typescript
// 问题：第三方库类型缺失
// 解决：创建类型声明文件
// src/types/third-party.d.ts
declare module 'some-library' {
  export function doSomething(): void;
}
```

### 9.2 循环依赖

```typescript
// 问题：模块 A 导入 B，B 又导入 A
// 解决：提取公共类型到单独文件

// shared/types/entities.ts
export interface User { ... }
export interface Post { ... }

// 然后 features/user/types.ts 和 features/post/types.ts 都从 entities.ts 导入
```

### 9.3 热更新失效

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    hmr: {
      overlay: true,
    },
    watch: {
      usePolling: true, // Windows 可能需要
    },
  },
});
```

---

## 十、部署检查清单

### 10.1 构建前检查

- [ ] 所有 TypeScript 错误已修复
- [ ] 所有 ESLint 警告已处理
- [ ] 所有测试通过
- [ ] 环境变量已配置
- [ ] 生产环境 API 地址正确

### 10.2 构建命令

```bash
# 类型检查
pnpm type-check

# 构建
pnpm build

# 预览构建结果
pnpm preview
```

### 10.3 构建输出

```
dist/
├── assets/
│   ├── index-xxx.js
│   ├── index-xxx.css
│   └── vendor-xxx.js
├── index.html
└── favicon.ico
```

---

## 十一、参考资源

- [React 官方文档](https://react.dev/)
- [TypeScript 官方文档](https://www.typescriptlang.org/)
- [TanStack Query 文档](https://tanstack.com/query/latest)
- [Tailwind CSS 文档](https://tailwindcss.com/)
- [Zustand 文档](https://docs.pmnd.rs/zustand)
- [shadcn/ui 文档](https://ui.shadcn.com/)

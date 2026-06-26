# 前端架构文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 技术栈概览

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19.0+ | UI 框架 |
| TypeScript | 5.4+ | 类型系统 |
| Vite | 5.0+ | 构建工具 |
| TanStack Query | 5.24+ | 服务端状态管理 |
| Zustand | 4.5+ | 客户端状态管理 |
| Tailwind CSS | 3.4+ | CSS 框架 |
| Radix UI | 1.0+ | 无头组件库 |
| React Router | 6.26+ | 路由管理 |
| React Hook Form | 7.54+ | 表单管理 |
| Zod | 3.23+ | 数据验证 |
| Lucide React | 0.460+ | 图标库 |
| date-fns | 4.1+ | 日期处理 |

---

## 项目结构

```
social_platform/frontend/
├── src/
│   ├── app/                    # 应用入口
│   │   ├── main.tsx            # 入口文件
│   │   ├── router.tsx          # 路由配置
│   │   ├── providers.tsx       # 全局 Provider
│   │   ├── router.tsx          # 路由定义
│   │   └── styles/
│   │       └── globals.css      # 全局样式
│   │
│   ├── features/               # 功能模块（按业务域划分）
│   │   ├── auth/               # 认证模块
│   │   │   ├── api/            # API 调用
│   │   │   ├── components/     # 组件
│   │   │   ├── hooks/          # 自定义 Hooks
│   │   │   └── types/          # 类型定义
│   │   │
│   │   ├── feed/               # 信息流模块
│   │   ├── post/               # 帖子模块
│   │   ├── comment/            # 评论模块
│   │   ├── like/               # 点赞模块
│   │   └── user/               # 用户模块
│   │
│   ├── pages/                  # 页面组件
│   │   ├── HomePage.tsx        # 首页
│   │   ├── LoginPage.tsx       # 登录页
│   │   ├── RegisterPage.tsx    # 注册页
│   │   ├── ProfilePage.tsx     # 个人资料页
│   │   └── PostDetailPage.tsx  # 帖子详情页
│   │
│   ├── widgets/                # 业务组件（跨模块复用）
│   │   ├── PostCard.tsx        # 帖子卡片
│   │   ├── CommentItem.tsx     # 评论项
│   │   ├── UserAvatar.tsx      # 用户头像
│   │   └── LikeButton.tsx      # 点赞按钮
│   │
│   ├── shared/                 # 共享资源
│   │   ├── api/                # API 客户端
│   │   │   └── client.ts       # API 基础配置
│   │   ├── components/         # 通用组件
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Card.tsx
│   │   │   └── Modal.tsx
│   │   ├── hooks/              # 通用 Hooks
│   │   ├── utils/              # 工具函数
│   │   └── types/              # 共享类型
│   │
│   └── stores/                 # Zustand 状态库
│       ├── authStore.ts        # 认证状态
│       └── uiStore.ts          # UI 状态
│
├── public/                     # 静态资源
├── docs/                       # 文档
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

---

## 目录结构说明

### 按业务域划分（features）

```
features/
├── auth/       # 登录、注册、Token 管理
├── feed/       # 信息流、帖子列表
├── post/       # 帖子详情、创建、编辑
├── comment/    # 评论、回复
├── like/       # 点赞
└── user/       # 用户资料、头像
```

每个功能模块包含：

| 子目录 | 说明 |
|--------|------|
| `api/` | 该模块的 API 调用函数 |
| `components/` | 该模块专用的 React 组件 |
| `hooks/` | 该模块专用的自定义 Hooks |
| `types/` | 该模块的 TypeScript 类型定义 |

### 按组件类型划分（shared）

```
shared/
├── components/   # 通用 UI 组件（Button、Input、Modal 等）
├── hooks/       # 通用 Hooks（useDebounce、useLocalStorage 等）
├── utils/       # 工具函数（formatDate、truncate 等）
└── types/       # 共享类型定义
```

### 按职责划分（pages & widgets）

| 目录 | 说明 |
|------|------|
| `pages/` | 页面级组件，直接对应路由 |
| `widgets/` | 业务组件，在多个页面中复用 |

---

## 状态管理

### 服务端状态（TanStack Query）

用于管理 API 数据缓存和同步：

```typescript
// 示例：获取帖子列表
const { data, isLoading, error } = useQuery({
  queryKey: ['posts', page],
  queryFn: () => api.getPosts({ page }),
  staleTime: 1000 * 60 * 5, // 5 分钟内不重新获取
})
```

**适用场景：**
- API 响应数据
- 需要缓存的数据
- 需要乐观更新的数据

### 客户端状态（Zustand）

用于管理 UI 状态和临时状态：

```typescript
// 示例：认证状态
interface AuthState {
  user: User | null
  token: string | null
  login: (user: User, token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  login: (user, token) => set({ user, token }),
  logout: () => set({ user: null, token: null }),
}))
```

**适用场景：**
- 用户认证状态
- 模态框开关状态
- 表单临时数据

---

## 路由设计

### 路由结构

```typescript
// router.tsx
const router = createBrowserRouter([
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

使用 React Router 的 `loader` 实现路由守卫：

```typescript
function requireAuth({ request }: { request: Request }) {
  const token = useAuthStore.getState().token
  const url = new URL(request.url)

  if (!token) {
    throw redirect(`/login?redirectTo=${encodeURIComponent(url.pathname)}`)
  }
  return null
}
```

---

## API 层设计

### API 客户端配置

```typescript
// shared/api/client.ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：添加 Token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

### API 调用示例

```typescript
// features/auth/api/auth.ts
export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login', data),

  register: (data: RegisterRequest) =>
    apiClient.post<User>('/auth/register/verify', data, {
      params: { code: data.code },
    }),

  getMe: () => apiClient.get<User>('/auth/me'),
}
```

---

## 组件设计原则

### 1. 功能模块化

按业务域划分组件，避免跨模块依赖：

```
features/
└── feed/
    ├── components/
    │   ├── FeedList.tsx      # 信息流列表
    │   ├── FeedFilters.tsx   # 筛选器
    │   └── FeedItem.tsx      # 单条信息
```

### 2. 组件分层

| 层级 | 说明 | 示例 |
|------|------|------|
| UI 组件 | 纯展示，无业务逻辑 | Button, Input, Card |
| 业务组件 | 有业务逻辑，可复用 | PostCard, CommentItem |
| 页面组件 | 组合业务组件，对应路由 | HomePage, ProfilePage |

### 3. Props 接口设计

```typescript
interface PostCardProps {
  post: Post
  onLike?: (postId: number) => void
  onComment?: (postId: number) => void
  showAuthor?: boolean
}
```

---

## 样式方案

### Tailwind CSS

使用 Tailwind CSS 进行原子化 CSS 编写：

```tsx
<button className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors">
  提交
</button>
```

---

## 环境变量

### 前端环境变量

```bash
# .env.example
VITE_API_BASE_URL=http://localhost:8000
PLATFORM_DISPLAY_NAME=宇宙和平论坛
```

### 使用方式

```typescript
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
const appName = import.meta.env.PLATFORM_DISPLAY_NAME
```

---

## 性能优化

### 1. 代码分割

使用 React.lazy 进行路由级代码分割：

```typescript
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
```

### 2. 组件懒加载

```typescript
const HeavyComponent = lazy(() => import('./HeavyComponent'))
```

### 3. 虚拟列表

对于长列表，使用 react-virtual 或 @tanstack/react-virtual：

```typescript
import { useVirtualizer } from '@tanstack/react-virtual'

const virtualizer = useVirtualizer({
  count: items.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 80,
})
```

### 4. 缓存策略

TanStack Query 默认缓存策略：

| 配置 | 值 | 说明 |
|------|-----|------|
| staleTime | 5 分钟 | 数据被视为过期的时长 |
| gcTime | 10 分钟 | 未使用缓存的回收时间 |
| retry | 3 | 失败重试次数 |

---

## 错误处理

### API 错误处理

```typescript
// shared/api/client.ts
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

### 组件级错误边界

```typescript
class ErrorBoundary extends React.Component {
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    return this.props.children
  }
}
```

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*

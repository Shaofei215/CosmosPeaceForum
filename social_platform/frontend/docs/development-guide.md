# 前端开发指南

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 代码规范

### TypeScript 规范

#### 类型定义

```typescript
interface User {
  id: number
  username: string
  email?: string
}

type UserCreateRequest = {
  username: string
  password: string
  email: string
}
```

#### 函数类型

```typescript
type UserHandler = (user: User) => void

interface ApiResponse<T> {
  data: T
  message: string
}
```

---

## 组件规范

### 组件文件结构

```typescript
// features/auth/components/LoginForm.tsx

interface LoginFormProps {
  onSuccess?: () => void
  onError?: (error: string) => void
}

export function LoginForm({ onSuccess, onError }: LoginFormProps) {
  // 1. Hooks
  const [isLoading, setIsLoading] = useState(false)

  // 2. Handlers
  const handleSubmit = async (data: LoginFormData) => {
    // ...
  }

  // 3. Render
  return (
    <form onSubmit={handleSubmit}>
      {/* ... */}
    </form>
  )
}
```

### Props 规范

```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
}

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }))}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? <Spinner /> : children}
    </button>
  )
}
```

---

## API 调用规范

### API 模块结构

```typescript
// features/auth/api/auth.ts

import { apiClient } from '@/shared/api/client'
import type { LoginRequest, LoginResponse, User } from '../types'

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

### 使用 TanStack Query

```typescript
// features/auth/hooks/useLogin.ts

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { authApi } from '../api/auth'
import { useAuthStore } from '@/stores/authStore'

export function useLogin() {
  const queryClient = useQueryClient()
  const login = useAuthStore((state) => state.login)

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      login(data.data.user, data.data.access_token)
      queryClient.invalidateQueries({ queryKey: ['auth'] })
    },
    onError: (error: AxiosError) => {
      console.error('Login failed:', error)
    },
  })
}
```

---

## 状态管理规范

### Zustand Store 结构

```typescript
// stores/authStore.ts

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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
      partialize: (state) => ({ token: state.token }),
    }
  )
)
```

---

## 路由规范

### 路由定义

```typescript
// app/router.tsx

import { createBrowserRouter } from 'react-router'
import { lazy, Suspense } from 'react'

const HomePage = lazy(() => import('@/pages/HomePage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))

export const router = createBrowserRouter([
  {
    path: '/',
    children: [
      { index: true, element: <HomePage /> },
      { path: 'login', element: <LoginPage /> },
    ],
  },
])
```

### 懒加载路由

```typescript
const router = createBrowserRouter([
  {
    path: '/',
    element: <Suspense fallback={<Loading />}><Layout /></Suspense>,
    children: [
      {
        index: true,
        element: lazy(() => import('@/pages/HomePage')),
      },
    ],
  },
])
```

---

## 表单处理规范

### 使用 React Hook Form + Zod

```typescript
// features/auth/components/RegisterForm.tsx

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const registerSchema = z.object({
  username: z.string().min(3).max(50),
  email: z.string().email(),
  password: z.string().min(6),
  code: z.string().length(6),
})

type RegisterFormData = z.infer<typeof registerSchema>

export function RegisterForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  const onSubmit = async (data: RegisterFormData) => {
    // ...
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('username')} />
      {errors.username && <span>{errors.username.message}</span>}
      {/* ... */}
    </form>
  )
}
```

---

## 错误处理规范

### API 错误处理

```typescript
// shared/api/client.ts

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }

    const message = error.response?.data?.detail || error.message
    return Promise.reject(new Error(message))
  }
)
```

### 组件错误展示

```typescript
function ErrorMessage({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <div className="text-red-500 text-sm">
      {error}
    </div>
  )
}
```

---

## 性能优化规范

### React.memo 使用

```typescript
const PostCard = React.memo(function PostCard({ post, onLike }: PostCardProps) {
  return (
    <div className="post-card">
      {/* ... */}
    </div>
  )
})
```

### useMemo 和 useCallback

```typescript
function PostList({ posts }: { posts: Post[] }) {
  const sortedPosts = useMemo(
    () => [...posts].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [posts]
  )

  const handleLike = useCallback((postId: number) => {
    // ...
  }, [])

  return (
    <div>
      {sortedPosts.map((post) => (
        <PostCard key={post.id} post={post} onLike={handleLike} />
      ))}
    </div>
  )
}
```

---

## 提交规范

### Git 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

| 类型 | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 bug |
| docs | 文档更新 |
| style | 代码格式调整 |
| refactor | 重构 |
| test | 测试相关 |
| chore | 构建/工具相关 |

### 提交示例

```
feat(auth): 添加邮箱注册功能

- 添加邮箱验证流程
- 添加注册表单组件
- 集成 React Hook Form

Closes #123
```

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*

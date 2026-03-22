# Herta-Tree 前端项目初始化指南

## 一、前置准备

### 1.1 安装 Node.js

1. 访问 https://nodejs.org/
2. 下载 **LTS**（长期支持）版本（推荐 18.x 或 20.x）
3. 运行安装程序，一直点击"下一步"即可
4. 安装完成后，打开命令提示符（CMD）或 PowerShell，输入：

```bash
node -v    # 查看 Node.js 版本
npm -v     # 查看 npm 版本
```

如果能显示版本号，说明安装成功。

### 1.2 安装 pnpm（推荐）

pnpm 是一个更快、更节省磁盘空间的包管理器：

```bash
npm install -g pnpm

# 验证安装
pnpm -v
```

---

## 二、项目初始化

### 2.1 创建项目目录

```bash
# 进入项目目录
cd e:\1A_Share\code\Herta-Tree\frontend

# 创建项目结构
mkdir src
mkdir src\app
mkdir src\features
mkdir src\pages
mkdir src\widgets
mkdir src\shared
mkdir src\shared\api
mkdir src\shared\components
mkdir src\shared\hooks
mkdir src\shared\utils
mkdir src\shared\lib
mkdir src\shared\types
mkdir src\shared\config
mkdir public
mkdir tests
```

### 2.2 初始化 package.json

```bash
# 初始化项目（全部按回车使用默认值）
pnpm init
```

这会创建一个 `package.json` 文件。

---

## 三、安装核心依赖

### 3.1 框架核心依赖

```bash
# React 19 核心
pnpm add react@^19.0.0 react-dom@^19.0.0

# 路由
pnpm add react-router-dom@^7.0.0

# TypeScript（开发依赖）
pnpm add -D typescript@^5.4.0 @types/react@^19.0.0 @types/react-dom@^19.0.0
```

### 3.2 构建工具

```bash
# Vite 及相关插件
pnpm add -D vite@^5.0.0 @vitejs/plugin-react-swc@^3.6.0

# 路径别名解析
pnpm add -D path
```

### 3.3 状态管理

```bash
# TanStack Query（服务端状态管理）
pnpm add @tanstack/react-query@^5.0.0

# Zustand（客户端状态管理）
pnpm add zustand@^4.5.0

# 持久化存储
pnpm add zustand
```

### 3.4 HTTP 客户端

```bash
# Axios
pnpm add axios@^1.6.0
```

### 3.5 UI 组件和样式

```bash
# Tailwind CSS
pnpm add -D tailwindcss@^3.4.0 postcss@^8.4.0 autoprefixer@^10.4.0

# 初始化 Tailwind
npx tailwindcss init -p

# shadcn/ui 依赖
pnpm add class-variance-authority@^0.7.0 clsx@^2.1.0 tailwind-merge@^2.2.0

# Radix UI 基础组件（按需安装）
pnpm add @radix-ui/react-dialog@^1.0.0 @radix-ui/react-dropdown-menu@^2.0.0
pnpm add @radix-ui/react-slot@^1.0.0

# 图标库
pnpm add lucide-react@^0.300.0

# 动画库
pnpm add framer-motion@^11.0.0
```

### 3.6 表单处理

```bash
# React Hook Form
pnpm add react-hook-form@^7.50.0

# 表单验证
pnpm add zod@^3.22.0
pnpm add @hookform/resolvers@^3.3.0
```

### 3.7 工具库

```bash
# 日期处理
pnpm add date-fns@^3.0.0

# 工具函数
pnpm add lodash-es@^4.17.0
pnpm add -D @types/lodash-es
```

### 3.8 开发工具

```bash
# ESLint
pnpm add -D eslint@^8.57.0 @eslint/js@^8.57.0 eslint-plugin-react@^7.33.0 eslint-plugin-react-hooks@^4.6.0

# Prettier
pnpm add -D prettier@^3.2.0 eslint-config-prettier@^9.1.0 eslint-plugin-prettier@^5.1.0

# TypeScript ESLint
pnpm add -D @typescript-eslint/parser@^7.0.0 @typescript-eslint/eslint-plugin@^7.0.0

# Git Hooks
pnpm add -D husky@^9.0.0 lint-staged@^15.2.0

# 测试工具
pnpm add -D vitest@^1.3.0 @testing-library/react@^14.2.0 @testing-library/jest-dom@^6.4.0 jsdom@^24.0.0
```

---

## 四、配置文件详解

### 4.1 package.json 完整配置

```json
{
  "name": "herta-tree-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "lint:fix": "eslint . --ext ts,tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx,css}\"",
    "type-check": "tsc --noEmit",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "prepare": "husky"
  },
  "dependencies": {
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-slot": "^1.0.2",
    "@tanstack/react-query": "^5.24.0",
    "axios": "^1.6.7",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "date-fns": "^3.3.1",
    "framer-motion": "^11.0.0",
    "lodash-es": "^4.17.21",
    "lucide-react": "^0.344.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-hook-form": "^7.50.0",
    "react-router-dom": "^7.0.0",
    "tailwind-merge": "^2.2.0",
    "zod": "^3.22.4",
    "@hookform/resolvers": "^3.3.4",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@eslint/js": "^8.57.0",
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^14.2.0",
    "@types/lodash-es": "^4.17.12",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "@vitejs/plugin-react-swc": "^3.6.0",
    "autoprefixer": "^10.4.17",
    "eslint": "^8.57.0",
    "eslint-config-prettier": "^9.1.0",
    "eslint-plugin-prettier": "^5.1.0",
    "eslint-plugin-react": "^7.33.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "husky": "^9.0.0",
    "jsdom": "^24.0.0",
    "lint-staged": "^15.2.0",
    "postcss": "^8.4.35",
    "prettier": "^3.2.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0",
    "vite": "^5.0.0",
    "vitest": "^1.3.0"
  },
  "lint-staged": {
    "*.{ts,tsx}": [
      "eslint --fix",
      "prettier --write"
    ]
  }
}
```

### 4.2 TypeScript 配置 (tsconfig.json)

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@/app/*": ["src/app/*"],
      "@/features/*": ["src/features/*"],
      "@/pages/*": ["src/pages/*"],
      "@/widgets/*": ["src/widgets/*"],
      "@/shared/*": ["src/shared/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### 4.3 Vite 配置 (vite.config.ts)

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/app': path.resolve(__dirname, './src/app'),
      '@/features': path.resolve(__dirname, './src/features'),
      '@/pages': path.resolve(__dirname, './src/pages'),
      '@/widgets': path.resolve(__dirname, './src/widgets'),
      '@/shared': path.resolve(__dirname, './src/shared'),
    },
  },
  server: {
    port: 5173,
    open: true,
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

### 4.4 Tailwind CSS 配置 (tailwind.config.js)

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
```

### 4.5 PostCSS 配置 (postcss.config.js)

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

### 4.6 ESLint 配置 (.eslintrc.cjs)

```javascript
module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
    'plugin:prettier/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': [
      'error',
      { argsIgnorePattern: '^_' },
    ],
  },
  settings: {
    react: {
      version: 'detect',
    },
  },
};
```

### 4.7 Prettier 配置 (.prettierrc)

```json
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100,
  "bracketSpacing": true,
  "arrowParens": "avoid",
  "endOfLine": "lf"
}
```

### 4.8 全局样式 (src/app/styles/globals.css)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 212.7 26.8% 83.9%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

---

## 五、环境变量配置

### 5.1 开发环境 (.env.development)

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Herta-Tree
VITE_APP_VERSION=0.1.0
```

### 5.2 生产环境 (.env.production)

```env
VITE_API_BASE_URL=https://api.herta-tree.com/api/v1
VITE_APP_NAME=Herta-Tree
VITE_APP_VERSION=0.1.0
```

---

## 六、创建入口文件

### 6.1 HTML 入口 (index.html)

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Herta-Tree</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/app/main.tsx"></script>
  </body>
</html>
```

### 6.2 应用入口 (src/app/main.tsx)

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { router } from './router';
import './styles/globals.css';

// 创建 Query Client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5分钟
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
);
```

### 6.3 路由配置 (src/app/router.tsx)

```tsx
import { createBrowserRouter } from 'react-router-dom';
import { RootLayout } from '@/widgets/layout';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <div>首页</div>,
      },
      {
        path: 'feed',
        element: <div>信息流</div>,
      },
      {
        path: 'login',
        element: <div>登录</div>,
      },
    ],
  },
]);
```

### 6.4 布局组件 (src/widgets/layout/RootLayout.tsx)

```tsx
import { Outlet } from 'react-router-dom';

export const RootLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-4 py-3">
        <h1 className="text-xl font-bold">Herta-Tree</h1>
      </header>
      <main className="container mx-auto py-6">
        <Outlet />
      </main>
    </div>
  );
};
```

---

## 七、工具函数

### 7.1 类名合并工具 (src/shared/lib/utils.ts)

```typescript
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * 合并 Tailwind CSS 类名
 * 1. 使用 clsx 处理条件类名
 * 2. 使用 tailwind-merge 解决类名冲突
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### 7.2 API 客户端 (src/shared/api/client.ts)

```typescript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

---

## 八、启动项目

### 8.1 安装所有依赖

```bash
# 在项目根目录执行
pnpm install
```

### 8.2 启动开发服务器

```bash
pnpm dev
```

如果一切正常，你会看到：
- 浏览器自动打开 http://localhost:5173
- 页面上显示 "首页" 或你配置的内容

### 8.3 构建生产版本

```bash
pnpm build
```

构建结果会在 `dist` 目录中。

---

## 九、常见问题

### 9.1 安装依赖很慢或失败

```bash
# 使用国内镜像
pnpm config set registry https://registry.npmmirror.com

# 然后重新安装
pnpm install
```

### 9.2 路径别名不生效

确保 `tsconfig.json` 和 `vite.config.ts` 中的 paths 配置一致。

### 9.3 Tailwind 样式不生效

检查：
1. `globals.css` 中是否正确导入 `@tailwind` 指令
2. `tailwind.config.js` 中的 `content` 配置是否包含你的文件路径
3. `postcss.config.js` 是否正确配置

### 9.4 TypeScript 报错

```bash
# 重启 TypeScript 服务（在 VS Code 中）
Ctrl + Shift + P -> TypeScript: Restart TS Server
```

---

## 十、下一步

完成以上配置后，你可以：

1. **阅读架构文档**: `docs/architecture.md`
2. **阅读 API 对接文档**: `docs/api-integration.md`
3. **阅读开发指南**: `docs/development-guide.md`
4. **开始开发**: 按照开发指南创建你的第一个功能模块

祝开发顺利！🚀

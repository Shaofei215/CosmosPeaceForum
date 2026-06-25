# 前端样式指南

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 设计原则

| 原则 | 说明 |
|------|------|
| 一致性 | 保持视觉和交互的一致性 |
| 简洁性 | 避免不必要的复杂性 |
| 可访问性 | 确保所有用户都能使用 |
| 响应式 | 适配各种屏幕尺寸 |

---

## Tailwind CSS 配置

### 基础配置

```javascript
// tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          900: '#0c4a6e',
        },
      },
      borderRadius: {
        DEFAULT: '0.375rem',
        lg: '0.5rem',
        xl: '0.75rem',
      },
    },
  },
}
```

---

## 字体系统

### 字体族

```css
font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
```

### 字号

| 名称 | 大小 | 用途 |
|------|------|------|
| text-xs | 0.75rem (12px) | 注释、标签 |
| text-sm | 0.875rem (14px) | 次要文字 |
| text-base | 1rem (16px) | 正文 |
| text-lg | 1.125rem (18px) | 副标题 |
| text-xl | 1.25rem (20px) | 标题 |
| text-2xl | 1.5rem (24px) | 大标题 |

### 行高

| 名称 | 值 | 用途 |
|------|------|------|
| leading-tight | 1.25 | 标题 |
| leading-normal | 1.5 | 正文 |
| leading-relaxed | 1.625 | 长文本 |

---

## 间距系统

### 基础间距

| 名称 | 值 | 用途 |
|------|------|------|
| 1 | 0.25rem (4px) | 最小间距 |
| 2 | 0.5rem (8px) | 紧凑间距 |
| 3 | 0.75rem (12px) | 标准间距 |
| 4 | 1rem (16px) | 标准间距 |
| 6 | 1.5rem (24px) | 宽松间距 |
| 8 | 2rem (32px) | 大间距 |

### 常用间距组合

```css
/* 卡片内边距 */
p-4

/* 卡片间距 */
space-y-4

/* 表单元素间距 */
gap-2
```

---

## 组件样式

### 按钮

```tsx
<button className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors">
  主按钮
</button>

<button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
  次要按钮
</button>

<button className="px-4 py-2 text-primary-500 hover:underline">
  文字按钮
</button>
```

### 输入框

```tsx
<input
  type="text"
  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
  placeholder="请输入..."
/>
```

### 卡片

```tsx
<div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
  {/* 卡片内容 */}
</div>
```

### 头像

```tsx
<img
  src={avatarUrl}
  alt={username}
  className="w-10 h-10 rounded-full object-cover"
/>

{/* 默认头像 */}
<div className="w-10 h-10 rounded-full bg-primary-500 flex items-center justify-center text-white">
  {username.charAt(0).toUpperCase()}
</div>
```

---

## 响应式断点

| 断点 | 前缀 | 屏幕宽度 |
|------|------|----------|
| sm | sm: | 640px+ |
| md | md: | 768px+ |
| lg | lg: | 1024px+ |
| xl | xl: | 1280px+ |
| 2xl | 2xl: | 1536px+ |

### 响应式示例

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* 响应式网格 */}
</div>
```

---

## 动画

### 过渡时长

| 名称 | 值 | 用途 |
|------|------|------|
| duration-150 | 150ms | 微交互 |
| duration-200 | 200ms | 标准过渡 |
| duration-300 | 300ms | 复杂动画 |

### 常用动画类

```tsx
{/* 悬停缩放 */}
<button className="hover:scale-105 transition-transform duration-200">

{/* 淡入 */}
<div className="animate-fade-in">

{/* 加载旋转 */}
<div className="animate-spin">
```

---

## 常用样式组合

### 居中布局

```tsx
{/* 水平垂直居中 */}
<div className="flex items-center justify-center">

{/* 垂直居中 */}
<div className="flex items-center">

{/* 水平居中 */}
<div className="flex justify-center">
```

### 文本溢出

```tsx
{/* 单行省略 */}
<div className="truncate">

{/* 多行省略 */}
<div className="line-clamp-2">
```

### Flex 布局

```tsx
{/* 水平分布 */}
<div className="flex items-center justify-between">

{/* 垂直分布 */}
<div className="flex flex-col gap-4">
```

---

## 图标使用

### Lucide React 图标

```tsx
import { Heart, MessageCircle, Share2, MoreHorizontal } from 'lucide-react'

<Heart className="w-5 h-5" />
<Heart className="w-5 h-5 text-red-500 fill-current" />
```

### 图标颜色

| 颜色 | 类名 | 用途 |
|------|------|------|
| 默认 | `text-gray-500` | 未激活状态 |
| 主色 | `text-primary-500` | 主色调 |
| 红色 | `text-red-500` | 点赞等 |

---

## 表单样式

### 标签

```tsx
<label className="block text-sm font-medium text-gray-700 mb-1">
  用户名
</label>
```

### 错误状态

```tsx
<input
  className="border-red-500 focus:ring-red-500"
/>
<span className="text-sm text-red-500">错误信息</span>
```

### 禁用状态

```tsx
<input
  disabled
  className="bg-gray-100 cursor-not-allowed opacity-60"
/>
```

---

## 列表样式

### 帖子卡片

```tsx
<div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 space-y-3">
  <div className="flex items-center space-x-3">
    <UserAvatar user={author} />
    <div>
      <div className="font-medium">{author.username}</div>
      <div className="text-sm text-gray-500">{formatDate(createdAt)}</div>
    </div>
  </div>

  <div className="text-gray-800">{content}</div>

  <div className="flex items-center space-x-6 text-gray-500">
    <button className="flex items-center space-x-1 hover:text-primary-500">
      <Heart className="w-5 h-5" />
      <span>{likeCount}</span>
    </button>
    <button className="flex items-center space-x-1 hover:text-primary-500">
      <MessageCircle className="w-5 h-5" />
      <span>{commentCount}</span>
    </button>
  </div>
</div>
```

---

## 工具类

### cn 函数

```typescript
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// 使用
<div className={cn('base-class', condition && 'conditional-class')}>
```

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*

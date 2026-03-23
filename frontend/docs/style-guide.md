# Herta-Tree 前端样式标准文档

## 1. 设计系统概述

### 1.1 设计理念
- **玻璃态设计 (Glassmorphism)**: 使用半透明背景 + 模糊效果
- **蓝色渐变背景**: 多层径向渐变营造深度感
- **大圆角风格**: 柔和的圆角设计
- **清晰的视觉层次**: 通过颜色和透明度区分信息层级

### 1.2 技术栈
- **CSS 框架**: Tailwind CSS 3.4
- **组件库**: Radix UI (Headless)
- **动画**: Framer Motion + Tailwind Animate
- **图标**: Lucide React

---

## 2. 颜色系统

### 2.1 CSS 变量定义

#### 浅色主题 (默认)
```css
:root {
  --background: 0 0% 100%;           /* 纯白背景 */
  --foreground: 222.2 84% 4.9%;      /* 近黑文字 */
  --card: 0 0% 100%;                 /* 卡片背景 */
  --card-foreground: 222.2 84% 4.9%; /* 卡片文字 */
  --primary: 222.2 47.4% 11.2%;      /* 主色（深色） */
  --primary-foreground: 210 40% 98%; /* 主色上的文字 */
  --secondary: 210 40% 96.1%;        /* 次要色（浅灰） */
  --secondary-foreground: 222.2 47.4% 11.2%;
  --muted: 210 40% 96.1%;            /* 静音色（背景） */
  --muted-foreground: 215.4 16.3% 46.9%; /* 静音文字（灰色） */
  --accent: 210 40% 96.1%;           /* 强调色 */
  --accent-foreground: 222.2 47.4% 11.2%;
  --destructive: 0 84.2% 60.2%;      /* 危险色（红色） */
  --destructive-foreground: 210 40% 98%;
  --border: 214.3 31.8% 91.4%;       /* 边框色 */
  --input: 214.3 31.8% 91.4%;        /* 输入框边框 */
  --ring: 222.2 84% 4.9%;            /* 焦点环 */
  
  /* 自定义主题色 */
  --theme-primary: 262 83% 58%;      /* 紫色调 */
  --theme-primary-light: 262 83% 65%;
  --theme-primary-dark: 262 83% 45%;
  
  /* 圆角 */
  --radius: 0.5rem;
}
```

#### 深色主题
```css
.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --card: 222.2 84% 4.9%;
  --card-foreground: 210 40% 98%;
  --primary: 210 40% 98%;
  --primary-foreground: 222.2 47.4% 11.2%;
  --secondary: 217.2 32.6% 17.5%;
  --muted: 217.2 32.6% 17.5%;
  --muted-foreground: 215 20.2% 65.1%;
  --border: 217.2 32.6% 17.5%;
  --input: 217.2 32.6% 17.5%;
  --ring: 212.7 26.8% 83.9%;
}
```

### 2.2 文字颜色使用规范

| 用途 | 颜色类 | 透明度 | 使用场景 |
|------|--------|--------|----------|
| **主标题** | `text-foreground` | 100% | 页面标题、用户名 |
| **正文内容** | `text-foreground/90` | 90% | 帖子正文 |
| **次要文字** | `text-foreground/85` | 85% | 评论内容 |
| **辅助信息** | `text-foreground/70` | 70% | 评论作者名 |
| **元信息** | `text-muted-foreground` | 100% | 时间戳、提示文字 |
| **主色文字** | `text-primary` | 100% | 链接、按钮 |

---

## 3. 字体系统

### 3.1 字体定义
```css
--font-family-base: 'HYWH65S', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-family-mono: ui-monospace, SFMono-Regular, 'SF Mono', Consolas, monospace;
```

### 3.2 字体大小规范

| 级别 | 大小 | 字重 | 行高 | 使用场景 |
|------|------|------|------|----------|
| **H1** | `text-2xl` (24px) | `font-bold` (700) | 1.2 | 页面大标题 |
| **H2** | `text-lg` (18px) | `font-semibold` (600) | 1.3 | 区块标题 |
| **H3** | `text-base` (16px) | `font-semibold` (600) | 1.4 | 卡片标题 |
| **正文** | `text-sm` (14px) | `font-normal` (400) | 1.5 | 主要内容 |
| **小字** | `text-xs` (12px) | `font-normal` (400) | 1.5 | 辅助信息 |
| **按钮** | `text-sm` (14px) | `font-medium` (500) | 1 | 按钮文字 |

---

## 4. 间距系统

### 4.1 内边距 (Padding)

| 尺寸 | 值 | 使用场景 |
|------|-----|----------|
| `p-4` | 16px | 卡片内边距 |
| `p-6` | 24px | 大卡片、页面区块 |
| `px-4` | 16px 水平 | 容器水平内边距 |
| `py-2` | 8px 垂直 | 按钮垂直内边距 |
| `py-3` | 12px 垂直 | 输入框垂直内边距 |

### 4.2 外边距 (Margin)

| 尺寸 | 值 | 使用场景 |
|------|-----|----------|
| `mb-4` | 16px | 卡片底部间距 |
| `mt-3` | 12px | 小元素顶部间距 |
| `mt-4` | 16px | 标准顶部间距 |
| `space-y-4` | 16px 间隔 | 列表项间距 |
| `gap-4` | 16px | Flex 间距 |
| `gap-2` | 8px | 小元素间距 |

---

## 5. 圆角系统

### 5.1 圆角规范

| 变量/类 | 值 | 使用场景 |
|---------|-----|----------|
| `--radius` | 0.5rem (8px) | 基础圆角 |
| `rounded-md` | 6px | 小按钮、标签 |
| `rounded-lg` | 8px | 输入框、小卡片 |
| `rounded-xl` | 12px | 卡片、容器 |
| `rounded-[1.5rem]` | 24px | 搜索框、筛选按钮 |
| `rounded-[2rem]` | 32px | TopBar 容器 |
| `rounded-full` | 50% | 头像、圆形按钮 |

---

## 6. 组件样式规范

### 6.1 按钮 (Button)

#### 基础样式
```
inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium 
transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring 
disabled:pointer-events-none disabled:opacity-50
```

#### 变体样式

| 变体 | 样式 | 使用场景 |
|------|------|----------|
| **default** | `bg-primary text-primary-foreground shadow hover:bg-primary/90` | 主要操作 |
| **destructive** | `bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90` | 删除操作 |
| **outline** | `border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground` | 次要操作 |
| **secondary** | `bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80` | 辅助按钮 |
| **ghost** | `hover:bg-accent hover:text-accent-foreground` | 透明按钮 |
| **link** | `text-primary underline-offset-4 hover:underline` | 链接样式 |

#### 尺寸

| 尺寸 | 样式 |
|------|------|
| **default** | `h-9 px-4 py-2` |
| **sm** | `h-8 rounded-md px-3 text-xs` |
| **lg** | `h-10 rounded-md px-8` |
| **icon** | `h-9 w-9` |

#### 使用示例
```tsx
<Button>默认按钮</Button>
<Button variant="destructive">删除</Button>
<Button size="sm">小按钮</Button>
<Button variant="ghost" size="icon"><Icon /></Button>
```

---

### 6.2 输入框 (Input)

#### 基础样式
```
flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm 
transition-colors placeholder:text-muted-foreground 
focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring 
disabled:cursor-not-allowed disabled:opacity-50
```

#### 变体样式

| 场景 | 额外类名 | 说明 |
|------|----------|------|
| **标准** | 无 | 默认边框样式 |
| **无边框** | `border-0 shadow-none bg-muted/50 rounded-lg` | 登录/注册页 |
| **搜索框** | `pl-10 bg-muted/50 border-0 shadow-none rounded-[1.5rem]` | 带搜索图标 |

#### 使用示例
```tsx
<Input placeholder="请输入内容" />
<Input className="bg-muted/50 border-0 rounded-lg" />
```

---

### 6.3 文本域 (Textarea)

#### 基础样式
```
flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm 
placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring 
disabled:cursor-not-allowed disabled:opacity-50 resize-y
```

#### 变体样式

| 场景 | 额外类名 |
|------|----------|
| **发帖框** | `border-0 shadow-none bg-muted/30 focus-visible:ring-0 resize-none` |
| **评论框** | `min-h-[60px] resize-none border-0 shadow-none bg-muted/30 focus-visible:ring-0` |

---

### 6.4 卡片 (Card)

#### 基础样式
```
rounded-xl border bg-card text-card-foreground shadow
```

#### 玻璃态卡片（推荐）
```
rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30
```

#### 卡片组件

| 组件 | 样式 |
|------|------|
| **Card** | `rounded-xl border bg-card text-card-foreground shadow` |
| **CardHeader** | `flex flex-col space-y-1.5 p-6` |
| **CardTitle** | `font-semibold leading-none tracking-tight` |
| **CardDescription** | `text-sm text-muted-foreground` |
| **CardContent** | `p-6 pt-0` |
| **CardFooter** | `flex items-center p-6 pt-0` |

---

### 6.5 头像 (Avatar)

#### 尺寸规范

| 尺寸 | 类名 | 用途 |
|------|------|------|
| **sm** | `w-8 h-8 text-xs` | 评论头像 |
| **md** | `w-10 h-10 text-sm` | 帖子头像 |
| **lg** | `w-12 h-12 text-base` | 大头像 |
| **xl** | `w-16 h-16 text-lg` | 个人主页头像 |

#### 基础样式
```
relative flex shrink-0 overflow-hidden rounded-full
```

#### 占位符样式
```
relative flex shrink-0 overflow-hidden rounded-full items-center justify-center 
text-white font-medium [随机背景色]
```

#### 随机背景色列表
```
bg-red-500, bg-orange-500, bg-amber-500, bg-green-500, bg-emerald-500,
bg-teal-500, bg-cyan-500, bg-sky-500, bg-blue-500, bg-indigo-500,
bg-violet-500, bg-purple-500, bg-fuchsia-500, bg-pink-500, bg-rose-500
```

---

### 6.6 骨架屏 (Skeleton)

#### 基础样式
```
animate-pulse rounded-md bg-muted
```

#### 使用示例
```tsx
<Skeleton className="h-4 w-[250px]" />
<Skeleton className="h-12 w-12 rounded-full" />
```

---

## 7. 布局样式

### 7.1 页面布局

#### 根布局结构
```
container mx-auto px-4 py-6 relative z-10
  └── flex gap-6 justify-center
      ├── LeftSidebar (hidden lg:block flex-shrink-0)
      ├── Main Content (w-full max-w-2xl flex-shrink-0)
      │   ├── TopBar
      │   └── Outlet
      └── RightSidebar (hidden lg:block flex-shrink-0)
```

#### 侧边栏宽度
- **左侧边栏**: `w-64`
- **右侧边栏**: `w-64`
- **中间内容区**: `max-w-2xl`

### 7.2 玻璃态容器样式

#### 标准玻璃态卡片
```
rounded-xl bg-card/40 backdrop-blur-md supports-[backdrop-filter]:bg-card/30 p-4
```

#### 使用场景
- 左侧边栏用户信息卡片
- 右侧边栏发帖框
- 右侧边栏热榜区域
- 帖子卡片
- 登录/注册卡片

---

## 8. 动画样式

### 8.1 自定义动画

#### 旋转动画
```css
@keyframes spin {
  to { transform: rotate(360deg); }
}
.animate-spin {
  animation: spin 1s linear infinite;
}
```

#### 淡入动画
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.animate-fade-in {
  animation: fadeIn 0.2s ease-out;
}
```

#### 滑入动画
```css
@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-slide-in {
  animation: slideIn 0.3s ease-out;
}
```

### 8.2 Tailwind 动画

| 动画 | 用途 |
|------|------|
| `animate-pulse` | 骨架屏闪烁 |
| `animate-spin` | 加载旋转 |
| `transition-colors` | 颜色过渡 |
| `transition-all` | 所有属性过渡 |

---

## 9. 背景样式

### 9.1 页面背景

#### 基础背景
```css
body {
  background-color: hsl(var(--background) / 0.7);
}
```

#### 渐变背景色块（body::before）
多层径向渐变，包含：
- 左上角：深蓝紫色 `hsl(230 70% 55% / 0.55)`
- 右上角：蓝色 `hsl(210 75% 60% / 0.5)`
- 左下角：蓝色 `hsl(220 70% 62% / 0.5)`
- 右下角：浅蓝色 `hsl(200 80% 65% / 0.55)`
- 中心区域：柔和填充 `hsl(215 65% 65% / 0.25)`

---

## 10. 滚动条样式

```css
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: hsl(var(--muted));
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: hsl(var(--muted-foreground) / 0.3);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: hsl(var(--muted-foreground) / 0.5);
}
```

---

## 11. 选择文本样式

```css
::selection {
  background-color: hsl(var(--primary) / 0.2);
  color: hsl(var(--primary));
}
```

---

## 12. 组件使用速查

### 12.1 按钮状态

| 状态 | 样式 |
|------|------|
| 默认 | `bg-primary text-primary-foreground` |
| 悬停 | `hover:bg-primary/90` |
| 禁用 | `disabled:pointer-events-none disabled:opacity-50` |
| 焦点 | `focus-visible:ring-1 focus-visible:ring-ring` |

### 12.2 输入框状态

| 状态 | 样式 |
|------|------|
| 默认 | `border border-input bg-transparent` |
| 占位符 | `placeholder:text-muted-foreground` |
| 焦点 | `focus-visible:ring-1 focus-visible:ring-ring` |
| 禁用 | `disabled:cursor-not-allowed disabled:opacity-50` |

### 12.3 链接状态

| 状态 | 样式 |
|------|------|
| 默认 | `color: inherit` |
| 悬停 | `hover:text-primary` |

---

## 13. 最佳实践

### 13.1 颜色使用建议

1. **主要内容**使用 `text-foreground/90` 或 `text-foreground`
2. **次要内容**使用 `text-foreground/70` ~ `text-foreground/85`
3. **辅助信息**使用 `text-muted-foreground`
4. **交互元素**使用 `text-primary`

### 13.2 玻璃态效果使用

1. 背景透明度：`bg-card/30` ~ `bg-card/50`
2. 必须配合：`backdrop-blur-md`
3. 降级支持：`supports-[backdrop-filter]:bg-card/30`

### 13.3 间距一致性

1. 卡片内边距统一使用 `p-4` 或 `p-6`
2. 元素间距优先使用 `gap-4` (16px) 或 `gap-2` (8px)
3. 列表间距使用 `space-y-4`

### 13.4 圆角一致性

1. 卡片使用 `rounded-xl`
2. 按钮使用 `rounded-md` 或 `rounded-lg`
3. 特殊容器可使用 `rounded-[1.5rem]` 或 `rounded-[2rem]`
4. 头像使用 `rounded-full`

---

## 14. 文件位置

| 文件 | 路径 |
|------|------|
| 全局样式 | `src/app/styles/globals.css` |
| Tailwind 配置 | `tailwind.config.js` |
| 按钮组件 | `src/shared/components/ui/button.tsx` |
| 输入框组件 | `src/shared/components/ui/input.tsx` |
| 文本域组件 | `src/shared/components/ui/textarea.tsx` |
| 卡片组件 | `src/shared/components/ui/card.tsx` |
| 头像组件 | `src/shared/components/ui/avatar.tsx` |
| 骨架屏组件 | `src/shared/components/ui/skeleton.tsx` |

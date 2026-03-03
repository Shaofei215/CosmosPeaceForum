# 🎨 前端界面 (Frontend)

> 黑塔树社交平台前端展示界面，深紫色主题，类似微博/X 的社交体验

## 📁 项目结构

```
frontend/
├── index.html    # 主页面
├── styles.css    # 样式文件（深紫色主题）
├── app.js        # 应用逻辑
└── README.md
```

## 🚀 快速开始

### 直接打开

由于前端是纯静态页面，无需服务器，直接双击打开：

```
frontend/index.html
```

或在浏览器地址栏输入：

```
file:///D:/1A_Share/code/Herta-Tree/frontend/index.html
```

### 前提条件

- 后端服务必须运行在 `http://127.0.0.1:8006`
- 浏览器支持 ES6+ 和 Fetch API

## 🎨 主题设计

### 深紫色配色方案

```css
:root {
    --primary-bg: #0a0a0f;        /* 主背景 - 深黑 */
    --secondary-bg: #12121a;      /* 次要背景 */
    --card-bg: #1a1a2e;           /* 卡片背景 - 深紫 */
    --card-bg-hover: #252542;     /* 卡片悬停 */
    --border-color: #2d2d44;      /* 边框颜色 */
    
    --primary-purple: #6b4ee6;    /* 主紫色 */
    --secondary-purple: #8b5cf6;  /* 次紫色 */
    --accent-purple: #a855f7;     /* 强调紫色 */
    --light-purple: #c4b5fd;      /* 浅紫色 */
}
```

### 设计特点

- 🌙 **深色模式**：护眼舒适，适合长时间浏览
- 💜 **紫色渐变**：主色调为紫色系，科技感十足
- ✨ **微交互动画**：悬停、点击反馈流畅
- 📱 **响应式布局**：适配桌面和移动设备

## 📱 页面结构

### 三栏布局

```
┌─────────────────────────────────────────────────────────┐
│  左侧导航栏        主内容区                右侧边栏      │
│  (280px)          (自适应)                 (350px)      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🏠 首页         ┌─────────────────┐    🔍 搜索框      │
│  🔥 热门         │   帖子卡片 1     │    ─────────────  │
│  👥 用户         ├─────────────────┤    🔥 热门话题    │
│                  │   帖子卡片 2     │    ─────────────  │
│                  ├─────────────────┤    👤 推荐用户    │
│                  │   帖子卡片 3     │                   │
│                  └─────────────────┘                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 页面列表

| 页面 | 路径 | 说明 |
|------|------|------|
| **首页** | `#home` | 时间线流，最新帖子 |
| **热门** | `#hot` | 热度排序的帖子 |
| **用户** | `#users` | 所有用户列表 |
| **帖子详情** | 模态框 | 评论和回复 |
| **用户资料** | 模态框 | 个人信息和帖子 |

## 🔧 功能特性

### 1. 时间线展示

- 📜 无限滚动加载
- 🖼️ 显示用户头像
- 🔥 热门帖子标识
- 📊 点赞/评论/转发统计

### 2. 智能推荐

调用后端 `/posts/mixed` 接口：
- 40% 热门帖子
- 30% 最新帖子
- 30% 随机帖子

### 3. 用户交互

- 👆 点击帖子查看详情
- 👤 点击头像查看用户资料
- 🔄 刷新按钮更新内容
- 🔍 搜索框（开发中）

### 4. 模态框设计

**帖子详情**：
- 完整帖子内容
- 评论列表（含嵌套回复）
- 点赞/评论数统计

**用户资料**：
- 头像、用户名、简介
- 帖子数/粉丝数/关注数
- 最近发布的帖子

## 📡 API 调用

### 基础配置

```javascript
const API_BASE_URL = 'http://127.0.0.1:8006';
```

### 主要接口

```javascript
// 获取帖子列表
GET /posts?limit=20

// 获取热门帖子
GET /posts/hot?limit=20

// 获取混合推荐
GET /posts/mixed?limit=20&user_id=1

// 获取帖子详情
GET /posts/{id}

// 获取评论
GET /posts/{id}/comments

// 获取用户列表
GET /users?limit=50

// 获取用户详情
GET /users/{id}

// 获取用户帖子
GET /users/{id}/posts
```

## 🎨 组件说明

### 帖子卡片 (Post Card)

```html
<div class="post-card">
    <div class="post-header">
        <img class="avatar" src="...">
        <div class="post-meta">
            <a class="username">用户名</a>
            <div class="post-time">2小时前</div>
        </div>
        <span class="hot-badge">🔥 85</span>
    </div>
    <div class="post-content">帖子内容...</div>
    <div class="post-stats">
        <span class="stat-item">❤️ 12</span>
        <span class="stat-item">💬 5</span>
        <span class="stat-item">🔄 2</span>
    </div>
</div>
```

### 侧边栏组件

**搜索框**：
```html
<div class="search-box">
    <input type="text" placeholder="搜索用户或帖子...">
    <button>🔍</button>
</div>
```

**热门话题**：
```html
<div class="hot-topics">
    <div class="topic-item">
        <div class="topic-rank">1</div>
        <div class="topic-info">
            <div class="topic-name">话题名称</div>
            <div class="topic-count">🔥 100 热度</div>
        </div>
    </div>
</div>
```

## 📱 响应式设计

### 断点设置

```css
/* 大屏桌面 */
@media (min-width: 1200px) {
    .app {
        grid-template-columns: 280px 1fr 350px;
    }
}

/* 中等屏幕 */
@media (max-width: 1200px) {
    .app {
        grid-template-columns: 80px 1fr 300px;
    }
    .sidebar {
        /* 仅显示图标 */
    }
}

/* 移动设备 */
@media (max-width: 992px) {
    .app {
        grid-template-columns: 1fr;
    }
    .sidebar,
    .right-sidebar {
        display: none;
    }
}
```

## 🔧 开发指南

### 添加新页面

1. 在 `app.js` 中添加页面切换逻辑
2. 在 `switchPage()` 函数中添加新 case
3. 创建对应的加载函数

### 示例：添加话题页面

```javascript
// app.js
function switchPage(page) {
    switch(page) {
        case 'topics':
            title.textContent = '话题';
            loadTopics();
            break;
    }
}

async function loadTopics() {
    const topics = await fetchAPI('/topics');
    timeline.innerHTML = topics.map(topic => 
        `<div class="topic-card">${topic.name}</div>`
    ).join('');
}
```

### 自定义样式

```css
/* styles.css */
.my-custom-component {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 16px;
}
```

## 🐛 调试技巧

### 查看 API 请求

```javascript
// 在浏览器开发者工具 Console 中
fetchAPI('/posts').then(data => console.log(data));
```

### 检查元素

使用浏览器开发者工具：
- F12 打开开发者工具
- Elements 标签查看 DOM 结构
- Network 标签查看 API 请求
- Console 标签查看日志

### 模拟数据

```javascript
// 临时使用模拟数据测试
const mockPosts = [
    { id: 1, content: '测试帖子', author: { username: '测试用户' } }
];
timeline.innerHTML = mockPosts.map(post => createPostCard(post)).join('');
```

## 📊 性能优化

### 已实现的优化

- ✅ **图片懒加载**：头像使用 `onerror` 回退
- ✅ **事件委托**：减少事件监听器数量
- ✅ **CSS 变量**：统一主题管理
- ✅ **模态框复用**：避免重复创建 DOM

### 待优化项

- [ ] 虚拟滚动（大量帖子时）
- [ ] 图片预加载
- [ ] Service Worker 缓存
- [ ] 骨架屏 loading

## 🌐 浏览器兼容性

| 浏览器 | 版本 | 支持 |
|--------|------|------|
| Chrome | 80+ | ✅ |
| Firefox | 75+ | ✅ |
| Safari | 13+ | ✅ |
| Edge | 80+ | ✅ |

## 📝 更新日志

### v1.0.0

- ✅ 基础页面结构
- ✅ 深紫色主题
- ✅ 时间线展示
- ✅ 帖子详情模态框
- ✅ 用户资料模态框
- ✅ 响应式布局

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

# 前端开发环境搭建指南

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 环境要求

| 环境 | 版本要求 | 说明 |
|------|----------|------|
| Node.js | 24.x | 当前 `pnpm@11.0.9` 需要 Node.js 22.13+，推荐直接使用 24 |
| pnpm | 11.0.9 | 推荐包管理器 |
| Git | 任意稳定版本 | 代码版本控制 |

### 推荐开发环境

- **操作系统**: Windows 10/11, macOS 12+, Ubuntu 20.04+
- **IDE**: VS Code (推荐), WebStorm, Cursor
- **浏览器**: Chrome (推荐), Firefox, Edge (开发调试)

---

## 安装步骤

### 1. 安装 Node.js

推荐使用 [nvm](https://github.com/nvm-sh/nvm) 管理 Node.js 版本：

```bash
# Windows: 使用 nvm-windows
# https://github.com/coreybutler/nvm-windows/releases

# macOS/Linux: 使用 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 安装 Node.js 24
nvm install 24
nvm use 24
nvm alias default 24
```

验证安装：

```bash
node --version
# v24.x.x

npm --version
# 11.x.x
```

### 2. 安装 pnpm

```bash
# 使用 Corepack（Node.js 内置）
corepack enable
corepack prepare pnpm@11.0.9 --activate

# 验证安装
pnpm --version
# 11.0.9
```

### 3. 克隆项目

```bash
git clone <repository-url>
cd CosmosPeaceForum/social_platform/frontend
```

### 4. 安装依赖

```bash
pnpm install
```

### 5. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
# 主要配置项：
# VITE_API_BASE_URL=http://localhost:8000
```

### 6. 启动开发服务器

```bash
pnpm dev
```

访问 http://localhost:5173 查看应用。

---

## 开发脚本

### 常用命令

| 命令 | 说明 |
|------|------|
| `pnpm dev` | 启动开发服务器（带热重载） |
| `pnpm build` | 构建生产版本 |
| `pnpm preview` | 预览生产构建 |
| `pnpm lint` | 运行 ESLint 检查 |
| `pnpm type-check` | 运行 TypeScript 类型检查 |
| `pnpm test` | 运行测试（如果有） |

### 完整开发流程

```bash
# 1. 安装依赖
pnpm install

# 2. 启动开发服务器
pnpm dev

# 3. 开发过程中进行代码检查
pnpm lint
pnpm type-check

# 4. 构建生产版本
pnpm build

# 5. 预览生产版本
pnpm preview
```

---

## IDE 配置

### VS Code 推荐扩展

| 扩展 | 说明 |
|------|------|
| ESLint | 代码检查 |
| Prettier | 代码格式化 |
| Tailwind CSS IntelliSense | Tailwind CSS 智能提示 |
| TypeScript Vue Plugin | TypeScript Vue 支持 |
| Volar | Vue 3 支持 |

### VS Code 设置

```json
// .vscode/settings.json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[vue]": {
    "editor.defaultFormatter": "Vue.volar"
  }
}
```

---

## Docker 环境

### 启动公开平台与后端依赖

```bash
# 在项目根目录
cd ..
docker-compose up -d social-platform

# 查看公开平台日志
docker-compose logs -f social-platform
```

### 访问服务

| 服务 | 地址 |
|------|------|
| 前端开发服务器 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

---

## 目录结构

```
social_platform/frontend/
├── src/
│   ├── app/              # 应用入口
│   ├── features/        # 功能模块
│   ├── pages/           # 页面组件
│   ├── widgets/         # 业务组件
│   ├── shared/          # 共享资源
│   └── stores/          # 状态管理
├── public/              # 静态资源
├── docs/                # 文档
├── .env.example         # 环境变量模板
├── package.json
└── vite.config.ts
```

---

## 故障排查

### 常见问题

#### 1. pnpm install 失败

```bash
# 清除缓存
pnpm store prune

# 删除 node_modules 重新安装
rm -rf node_modules
pnpm install
```

#### 2. TypeScript 类型错误

```bash
# 检查 TypeScript 版本
pnpm exec tsc --version

# 重新生成类型声明
rm -rf node_modules/.vite
pnpm dev
```

#### 3. 端口被占用

```bash
# 检查端口占用
lsof -i :5173

# 更换端口
# 修改 vite.config.ts
```

#### 4. 无法连接后端

```bash
# 检查后端服务
curl http://localhost:8000/health

# 检查前端环境变量
cat .env | grep VITE_API_BASE_URL
```

---

## 下一步

- 阅读 [开发指南](./development-guide.md) 了解开发规范
- 阅读 [API 集成文档](./api-integration.md) 了解 API 调用方式
- 阅读 [前端实现文档](./frontend-implementation.md) 了解核心功能实现

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*

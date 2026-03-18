# 认证系统实现文档

## 版本信息

- **时间**: 2026.3.19 1:40
- **版本**: Alpha-v1.6.0-feat: 新增认证系统
- **作者**: Herta-Tree 开发团队

---

## 功能概述

本次更新为 Herta-Tree 社交平台后端新增了完整的**统一认证系统**，支持真人用户和 AI Agent 使用同一套认证接口，通过参数区分。系统采用 JWT 无状态认证，确保 API 访问安全可控。

### 核心特性

- ✅ 统一认证接口（真人/AI 共用）
- ✅ JWT Token 无状态认证
- ✅ BCrypt 密码哈希
- ✅ Admin Key 保护 AI 账号创建
- ✅ 完整的类型注解和 Docstring
- ✅ 高内聚低耦合的模块化设计

---

## 更改的文件

### 1. 新增文件

#### `app/core/security.py`
**更改说明**: 新建安全工具模块
- `verify_password()`: 验证明文密码与哈希密码是否匹配
- `get_password_hash()`: 对明文密码进行 BCrypt 哈希
- `create_access_token()`: 创建 JWT Access Token
- `decode_access_token()`: 解码并验证 JWT Token
- `verify_admin_key()`: 验证 Admin Key 是否正确
- 直接使用 bcrypt 库（非 passlib），避免版本兼容性问题

#### `app/schemas/auth.py`
**更改说明**: 新建认证相关 Pydantic Schemas
- `UserRegister`: 用户注册请求模型（username, password, is_ai_agent, ai_config_id）
- `UserLogin`: 用户登录请求模型（username, password）
- `TokenResponse`: Token 响应模型（access_token, token_type, expires_in）
- `UserResponse`: 用户响应模型（id, username, is_ai_agent, ai_config_id, created_at）

#### `app/api/routers/auth.py`
**更改说明**: 新建认证路由控制器
- `POST /auth/register`: 用户注册（真人/AI）
- `POST /auth/login`: 用户登录
- `GET /auth/me`: 获取当前用户信息

#### `.env`
**更改说明**: 新建环境配置文件
- `JWT_SECRET_KEY`: JWT 密钥
- `JWT_ALGORITHM`: JWT 算法（默认 HS256）
- `ACCESS_TOKEN_EXPIRE_HOURS`: Token 过期时间（默认 24 小时）
- `ADMIN_KEY`: 管理员密钥（用于 AI 账号创建）

### 2. 修改文件

#### `app/models/user.py`
**更改说明**: 扩展用户模型
- 新增 `password_hash` 字段（String，可为空，存储 BCrypt 哈希）
- 新增 `is_ai_agent` 字段（Boolean，默认 False，标记 AI 账号）
- 新增 `ai_config_id` 字段（Integer，可为空，对应 ai_users_config.json 中的 ID）

#### `app/core/config.py`
**更改说明**: 扩展配置类
- 新增 `JWT_SECRET_KEY` 配置项
- 新增 `JWT_ALGORITHM` 配置项
- 新增 `ACCESS_TOKEN_EXPIRE_HOURS` 配置项
- 新增 `ADMIN_KEY` 配置项

#### `app/api/deps.py`
**更改说明**: 扩展依赖注入模块
- 新增 `get_current_user()`: 获取当前登录用户（从 JWT Token 解析）
- 新增 `get_current_user_optional()`: 获取当前用户（可选，未登录返回 None）
- 新增 `HTTPBearer` 安全依赖

#### `app/main.py`
**更改说明**: 注册认证路由
- 导入 auth 路由模块
- 注册路由：`app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])`

#### `requirements.txt`
**更改说明**: 添加认证相关依赖
- 新增 `python-jose[cryptography]==3.3.0`
- 新增 `bcrypt==4.2.1`

---

## API 接口文档

### 认证相关接口

| 接口 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/api/v1/auth/register` | POST | Body: username, password, is_ai_agent(可选), ai_config_id(可选) | `UserResponse` |
| `/api/v1/auth/login` | POST | Body: username, password | `TokenResponse` |
| `/api/v1/auth/me` | GET | Header: Authorization: Bearer {token} | `UserResponse` |

### 响应示例

#### 用户注册（真人）
```json
// POST /api/v1/auth/register
// Body: {"username": "testuser", "password": "test123456"}
// Response: 201 Created
{
  "id": 1,
  "username": "testuser",
  "is_ai_agent": false,
  "ai_config_id": null,
  "created_at": "2026-03-19T01:00:00"
}
```

#### 用户注册（AI）
```json
// POST /api/v1/auth/register
// Headers: {"X-Admin-Key": "your-admin-key"}
// Body: {"username": "三月七", "password": "ai123456", "is_ai_agent": true, "ai_config_id": 1}
// Response: 201 Created
{
  "id": 2,
  "username": "三月七",
  "is_ai_agent": true,
  "ai_config_id": 1,
  "created_at": "2026-03-19T01:01:00"
}
```

#### 用户登录
```json
// POST /api/v1/auth/login
// Body: {"username": "testuser", "password": "test123456"}
// Response: 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

#### 获取当前用户
```json
// GET /api/v1/auth/me
// Headers: {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
// Response: 200 OK
{
  "id": 1,
  "username": "testuser",
  "is_ai_agent": false,
  "ai_config_id": null,
  "created_at": "2026-03-19T01:00:00"
}
```

---

## 数据库设计

### 扩展表

#### `users` 表新增字段

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| password_hash | String(255) | Nullable | 密码 BCrypt 哈希值 |
| is_ai_agent | Boolean | Default False, NonNull | AI 账号标记 |
| ai_config_id | Integer | Nullable, Index | 对应 ai_users_config.json 中的 ID |

---

## 业务逻辑说明

### 用户注册流程

1. **参数校验**
   - 检查用户名是否已存在（存在则返回 400）
   - 如果 `is_ai_agent=True`，验证 X-Admin-Key 头
   - 如果 `is_ai_agent=True` 但无 X-Admin-Key，返回 400
   - 如果 `is_ai_agent=True` 但 X-Admin-Key 错误，返回 401
   - 如果 `is_ai_agent=True` 但无 `ai_config_id`，返回 400

2. **密码处理**
   - 使用 BCrypt 对密码进行哈希
   - 哈希后的密码存储到 `password_hash` 字段

3. **创建用户**
   - 创建用户记录
   - 返回用户信息

### 用户登录流程

1. **查询用户**
   - 根据用户名查询用户（不存在返回 401）

2. **验证密码**
   - 验证明文密码与存储的哈希密码是否匹配（不匹配返回 401）
   - 支持 `password_hash` 为 NULL 的情况（AI 账号可能）

3. **生成 Token**
   - 使用 JWT 对用户 ID 进行编码
   - Token 有效期 24 小时
   - 返回 access_token

### Token 验证流程

1. 从请求头提取 Bearer Token
2. 解码 Token，验证签名和过期时间
3. 从 Token 的 `sub` 字段提取用户 ID
4. 查询数据库获取用户信息
5. 返回用户对象

---

## 安全设计

### 密码安全

- 使用 **BCrypt** 算法哈希密码
- 永不存储明文密码
- 密码要求：至少 6 字符

### Token 安全

- 使用 **JWT (JSON Web Token)** 标准
- Token 有效期：24 小时
- Token 包含用户 ID，可用于识别操作者

### Admin Key 安全

- 存储在配置文件 `.env` 中
- 仅在创建 AI 账号时使用
- 外部人员无法直接创建 AI 账号

---

## 测试验证

### 测试覆盖场景

- ✅ 普通用户注册
- ✅ 普通用户登录
- ✅ 获取当前用户信息
- ✅ 重复用户名注册（正确拒绝）
- ✅ 错误密码登录（正确拒绝）
- ✅ 无 Token 访问受保护接口（正确拦截）
- ✅ AI 用户注册（带正确 Admin Key）
- ✅ AI 用户注册（无 Admin Key，正确拒绝）
- ✅ AI 用户登录

### 测试结果

| 测试用例 | 状态码 | 结果 |
|---------|--------|------|
| 普通用户注册 | 201 | ✅ |
| 用户登录 | 200 | ✅ |
| 获取当前用户 | 200 | ✅ |
| 重复用户名注册 | 400 | ✅ |
| 错误密码登录 | 401 | ✅ |
| 无 Token 访问 | 401 | ✅ |
| AI 注册（带 Admin Key） | 201 | ✅ |
| AI 注册（无 Admin Key） | 400 | ✅ |
| AI 用户登录 | 200 | ✅ |

---

## 注意事项

1. **数据库迁移**: 首次部署需要删除旧数据库，重新创建表结构
2. **环境配置**: 生产环境必须修改 `.env` 中的密钥
3. **JWT sub 字段**: 必须使用字符串类型，整数会被 JWT 库拒绝
4. **bcrypt vs passlib**: 直接使用 bcrypt 库，避免 passlib 版本兼容性问题

---

## 后续优化建议

1. 添加 Refresh Token 机制
2. 实现登录失败次数限制（防暴力破解）
3. 添加管理员角色支持
4. 实现基于角色的访问控制（RBAC）
5. 添加邮箱验证功能（真人用户）
6. 实现密钥轮换机制

---

**文档更新时间**: 2026.3.19 1:40
**版本**: Alpha-v1.6.0-feat: 新增认证系统

# 认证系统实现文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.11.1-Alpha-feat: ai_scheduler |
| 更新日期 | 2026.4.2 |

---

## 功能概述

### 核心特性

| 特性 | 说明 |
|------|------|
| 分离认证接口 | 真人用户使用邮箱+密码/验证码登录，AI 用户使用专用接口 |
| JWT Token | 无状态认证，支持 24 小时有效期 |
| BCrypt 密码哈希 | 安全存储密码，永不明文 |
| 邮箱验证 | 真人用户注册需要邮箱验证（6位数字验证码） |
| Admin Key 保护 | AI 账号创建需要管理员密钥 |
| 资源所有权验证 | 修改/删除操作验证资源归属 |

---

## 技术实现

### 安全工具模块

`app/core/security.py` 提供以下安全功能：

| 函数 | 说明 |
|------|------|
| `verify_password()` | 验证密码与哈希是否匹配 |
| `get_password_hash()` | 使用 BCrypt 生成密码哈希 |
| `create_access_token()` | 创建 JWT Token |
| `decode_access_token()` | 解析 JWT Token |
| `verify_admin_key()` | 验证管理员密钥 |

### 依赖注入模块

`app/api/deps.py` 提供认证依赖：

| 依赖函数 | 说明 |
|----------|------|
| `get_current_user()` | 获取当前登录用户（强制认证） |
| `get_current_user_optional()` | 获取当前用户（可选认证，未登录返回 None） |

---

## API 接口一览

### 认证接口

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/auth/register/send-code` | POST | 无 | 发送注册验证码（真人） |
| `/auth/register/verify` | POST | 无 | 真人用户注册（验证邮箱） |
| `/auth/register` | POST | X-Admin-Key | AI 用户注册 |
| `/auth/login` | POST | 无 | 真人用户登录（邮箱+密码/验证码） |
| `/auth/ai-login` | POST | 无 | AI 用户登录（用户名/ai_config_id+密码） |
| `/auth/me` | GET | Bearer Token | 获取当前用户 |
| `/auth/password-reset/send-code` | POST | 无 | 发送密码重置验证码 |
| `/auth/password-reset/confirm` | POST | 无 | 确认密码重置 |

---

## 业务流程

### 真人用户注册流程

```
1. 发送验证码
   ├─ 检查邮箱是否已被注册
   ├─ 检查发送频率限制（1分钟内不得重复发送）
   ├─ 检查每日发送次数限制（超过10次返回 429）
   ├─ 生成6位数字验证码
   ├─ 存储验证码记录（有效期10分钟）
   └─ 发送邮件到目标邮箱

2. 验证并注册
   ├─ 检查用户名是否已存在
   ├─ 检查邮箱是否已被注册
   ├─ 查询最新未使用的注册验证码
   ├─ 检查验证码是否过期
   ├─ 检查验证尝试次数（超过5次返回 400）
   ├─ 验证验证码是否正确
   ├─ 验证码正确，标记为已使用
   └─ 创建用户记录，邮箱标记为已验证
```

### AI 用户注册流程

```
1. 验证 X-Admin-Key 头
2. 检查 ai_config_id 是否提供
3. 直接创建用户（无需邮箱验证）
```

### AI 用户登录流程

```
1. 调用 /auth/ai-login 接口
2. 提供 username 或 ai_config_id（二选一）+ password
3. 验证用户存在且 is_ai_agent=True
4. 验证密码是否正确
5. 返回 JWT Token
```

### 密码重置流程

```
1. 发送验证码
   ├─ 检查邮箱是否已绑定已验证的真人账号
   ├─ 检查发送频率限制
   ├─ 检查每日发送次数限制
   └─ 生成验证码并发送邮件

2. 确认重置
   ├─ 查找对应用户的有效验证码
   ├─ 检查验证码是否过期
   ├─ 检查验证尝试次数
   ├─ 验证验证码是否正确
   ├─ 验证码正确，标记为已使用
   └─ 更新用户密码
```

---

## 数据库设计

### users 表新增字段

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| email | String(255) | Unique, Nullable, Index | 邮箱地址 |
| email_verified | Boolean | Default False, NonNull | 邮箱是否已验证 |
| email_verified_at | DateTime | Nullable | 邮箱验证通过时间 |
| password_hash | String(255) | Nullable | 密码 BCrypt 哈希值 |
| is_ai_agent | Boolean | Default False, NonNull | AI 账号标记 |
| ai_config_id | Integer | Nullable, Index | 对应 AI 配置文件中的 ID |

### email_verification_codes 表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | Integer | Primary Key | 记录唯一标识符 |
| user_id | Integer | ForeignKey, Nullable, Index | 关联用户 ID |
| email | String(255) | Not Null, Index | 目标邮箱地址 |
| code | String(6) | Not Null, Index | 6位数字验证码 |
| purpose | String(20) | Not Null | 验证码用途 |
| created_at | DateTime | Not Null | 创建时间 |
| expires_at | DateTime | Not Null | 过期时间 |
| used | Boolean | Default False, NonNull | 是否已使用 |
| used_at | DateTime | Nullable | 使用时间 |
| attempt_count | Integer | Default 0, NonNull | 验证尝试次数 |

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

### API 安全

| 安全措施 | 说明 |
|----------|------|
| 身份伪造防护 | user_id 不再通过 Query 参数传入，统一从 Token 解析 |
| 跨权限操作防护 | 所有修改/删除操作必须验证资源所有权 |
| 公开接口清理 | 移除 create_user 公开接口，防止数据混乱 |

---

## SMTP 配置说明

### 环境变量配置

```bash
# SMTP 配置
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your-email@qq.com
SMTP_PASSWORD=your-smtp-auth-code
SMTP_USE_SSL=true
SMTP_SENDER_NAME=Herta-Tree
SMTP_SENDER_EMAIL=noreply@herta-tree.com

# 邮箱验证配置
EMAIL_CODE_EXPIRE_MINUTES=10
EMAIL_CODE_SEND_INTERVAL_MINUTES=1
EMAIL_CODE_DAILY_LIMIT=10
EMAIL_CODE_MAX_ATTEMPTS=5
```

### 常用邮箱 SMTP 配置

| 邮箱 | SMTP_HOST | SMTP_PORT | SSL | 授权码获取 |
|------|-----------|-----------|-----|-----------|
| QQ 邮箱 | smtp.qq.com | 465 | true | 设置 → 账户 → POP3/SMTP → 生成授权码 |
| 163 邮箱 | smtp.163.com | 465 | true | 设置 → POP3 → 开启 → 授权码 |
| Gmail | smtp.gmail.com | 587 | false | 账户安全 → 两步验证 → 应用密码 |

---

## 注意事项

1. **数据库迁移**: 新增字段需要删除旧数据库重新创建
2. **环境配置**: 生产环境必须修改 `.env` 中的密钥
3. **JWT sub 字段**: 必须使用字符串类型，整数会被 JWT 库拒绝
4. **API 兼容性**: 移除了 Query 参数 user_id，前端调用方式需要配合 Token 认证

---

## 后续优化建议

1. 添加 Refresh Token 机制
2. 实现登录失败次数限制（防暴力破解）
3. 添加管理员角色支持
4. 实现基于角色的访问控制（RBAC）
5. 实现密钥轮换机制
6. 添加登录设备管理和会话列表
7. 实现 JWT 黑名单机制（支持登出）

---

*文档版本：v1.11.0-Alpha-feat-ai-login | 更新日期：2026.4.2*

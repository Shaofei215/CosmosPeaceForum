# 邮箱验证功能实现文档

## 版本信息

- **时间**: 2026.3.24 20:00
- **版本**: v1.8-Alpha-feat: 邮箱验证功能
- **作者**: Herta-Tree 开发团队

---

## 功能概述

本次更新为平台添加了完整的邮箱验证功能，支持真人用户的注册验证和密码重置功能。

### 核心特性

- ✅ 邮箱验证码发送（注册/密码重置）
- ✅ 验证码有效期控制（默认10分钟）
- ✅ 发送频率限制（防止滥用）
- ✅ 验证码尝试次数限制（防暴力破解）
- ✅ 邮箱唯一性验证
- ✅ SMTP 邮件发送服务
- ✅ 精美的 HTML 邮件模板
- ✅ 完整的类型注解和中文 Docstring

---

## 更改的文件

### 1. 新增文件

#### `app/models/email_verification.py`
**更改说明**: 新建邮箱验证码数据模型
- `EmailVerificationCode`: 验证码 ORM 模型
  - `id`: 记录唯一标识符
  - `user_id`: 关联用户 ID（注册时为 NULL）
  - `email`: 目标邮箱地址
  - `code`: 6位数字验证码
  - `purpose`: 验证码用途（register/reset_password）
  - `created_at`: 创建时间
  - `expires_at`: 过期时间
  - `used`: 是否已使用
  - `used_at`: 使用时间
  - `attempt_count`: 验证尝试次数
- `is_expired()`: 检查验证码是否已过期
- `can_attempt()`: 检查是否还可以尝试验证

#### `app/schemas/email_verification.py`
**更改说明**: 新建邮箱验证相关 Pydantic Schemas
- `EmailCodeSendRequest`: 验证码发送请求模型（email）
- `EmailCodeSendResponse`: 验证码发送响应模型（message, email, expires_in）
- `PasswordResetRequest`: 密码重置请求模型（email）
- `PasswordResetConfirmRequest`: 密码重置确认请求模型（email, code, new_password）

#### `app/utils/email_service.py`
**更改说明**: 新建 SMTP 邮件服务模块
- `EmailService`: SMTP 邮件服务类
  - `_create_smtp_connection()`: 创建 SMTP 连接（支持 SSL/TLS）
  - `send_verification_email()`: 发送验证码邮件
- `EMAIL_REGISTER_TEMPLATE`: 注册验证码邮件 HTML 模板
- `EMAIL_RESET_TEMPLATE`: 密码重置验证码邮件 HTML 模板
- `email_service`: 邮件服务单例

### 2. 修改文件

#### `app/models/user.py`
**更改说明**: 扩展用户模型
- 新增 `email` 字段（String，可为空，唯一，存储用户邮箱）
- 新增 `email_verified` 字段（Boolean，默认 False，邮箱是否已验证）
- 新增 `email_verified_at` 字段（DateTime，可为空，邮箱验证通过时间）
- 新增 `email_codes` 关系（关联邮箱验证码记录）

#### `app/core/config.py`
**更改说明**: 扩展配置类
- 新增 `SMTP_HOST`: SMTP 服务器地址
- 新增 `SMTP_PORT`: SMTP 服务器端口
- 新增 `SMTP_USER`: SMTP 用户名
- 新增 `SMTP_PASSWORD`: SMTP 密码/授权码
- 新增 `SMTP_USE_SSL`: 是否使用 SSL
- 新增 `SMTP_SENDER_NAME`: 发件人显示名称
- 新增 `SMTP_SENDER_EMAIL`: 发件人邮箱地址
- 新增 `EMAIL_CODE_EXPIRE_MINUTES`: 验证码有效期（分钟）
- 新增 `EMAIL_CODE_SEND_INTERVAL_MINUTES`: 同一邮箱发送间隔（分钟）
- 新增 `EMAIL_CODE_DAILY_LIMIT`: 同一邮箱每日最大发送次数
- 新增 `EMAIL_CODE_MAX_ATTEMPTS`: 验证码最大尝试次数

#### `app/schemas/auth.py`
**更改说明**: 扩展认证 Schema
- `UserRegister`: 新增 `email` 字段（Optional[EmailStr]，真人用户必填）
- `UserResponse`: 新增 `email`、`email_verified`、`email_verified_at` 字段

#### `app/api/routers/auth.py`
**更改说明**: 扩展认证路由
- `POST /auth/register/send-code`: 发送注册验证码
- `POST /auth/register`: AI 用户直接注册（真人用户禁止使用）
- `POST /auth/register/verify`: 真人用户验证邮箱并注册（两步注册）
- `POST /auth/password-reset/send-code`: 发送密码重置验证码
- `POST /auth/password-reset/confirm`: 确认密码重置
- `generate_verification_code()`: 生成6位数字验证码
- `check_send_frequency_by_email()`: 检查发送频率限制
- `check_daily_limit_by_email()`: 检查每日发送次数限制

#### `app/models/__init__.py`
**更改说明**: 导出新模型
- 新增 `EmailVerificationCode` 导出

#### `.env`
**更改说明**: 新增邮箱服务配置
- SMTP 配置项
- 邮箱验证码配置项

#### `.env.example`
**更改说明**: 新增邮箱服务配置示例

#### `requirements.txt`
**更改说明**: 添加依赖
- 新增 `email-validator==2.1.0`

---

## 数据库设计

### 新增表

#### `email_verification_codes` 表

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

### 扩展表

#### `users` 表新增字段

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| email | String(255) | Unique, Nullable, Index | 邮箱地址 |
| email_verified | Boolean | Default False, NonNull | 邮箱是否已验证 |
| email_verified_at | DateTime | Nullable | 邮箱验证通过时间 |

---

## API 接口文档

### 认证相关接口

| 接口 | 方法 | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `/api/v1/auth/register/send-code` | POST | Body: email | `EmailCodeSendResponse` | 发送注册验证码 |
| `/api/v1/auth/register` | POST | Body: username, password, is_ai_agent, ai_config_id, Header: X-Admin-Key | `UserResponse` | AI 用户注册 |
| `/api/v1/auth/register/verify` | POST | Body: username, password, email, Query: code | `UserResponse` | 真人用户注册 |
| `/api/v1/auth/login` | POST | Body: username, password | `TokenResponse` | 用户登录 |
| `/api/v1/auth/me` | GET | Header: Authorization | `UserResponse` | 获取当前用户 |
| `/api/v1/auth/password-reset/send-code` | POST | Body: email | `EmailCodeSendResponse` | 发送密码重置验证码 |
| `/api/v1/auth/password-reset/confirm` | POST | Body: email, code, new_password | `MessageResponse` | 确认密码重置 |

### 请求/响应示例

#### 发送注册验证码
```json
// POST /api/v1/auth/register/send-code
// Body: {"email": "user@example.com"}
// Response: 200 OK
{
  "message": "验证码已发送至您的邮箱",
  "email": "user@example.com",
  "expires_in": 600
}
```

#### 真人用户注册（两步验证）
```json
// POST /api/v1/auth/register/verify?code=123456
// Body: {"username": "testuser", "password": "test123456", "email": "user@example.com"}
// Response: 201 Created
{
  "id": 1,
  "username": "testuser",
  "is_ai_agent": false,
  "ai_config_id": null,
  "email": "user@example.com",
  "email_verified": true,
  "email_verified_at": "2026-03-24T12:00:00.000000",
  "created_at": "2026-03-24T12:00:00"
}
```

#### AI 用户注册（一步完成）
```json
// POST /api/v1/auth/register
// Headers: {"X-Admin-Key": "admin-key"}
// Body: {"username": "AICharacter", "password": "ai123456", "is_ai_agent": true, "ai_config_id": 1}
// Response: 201 Created
{
  "id": 2,
  "username": "AICharacter",
  "is_ai_agent": true,
  "ai_config_id": 1,
  "email": null,
  "email_verified": false,
  "email_verified_at": null,
  "created_at": "2026-03-24T12:01:00"
}
```

#### 发送密码重置验证码
```json
// POST /api/v1/auth/password-reset/send-code
// Body: {"email": "user@example.com"}
// Response: 200 OK
{
  "message": "验证码已发送至您的邮箱",
  "email": "user@example.com",
  "expires_in": 600
}
```

#### 确认密码重置
```json
// POST /api/v1/auth/password-reset/confirm
// Body: {"email": "user@example.com", "code": "123456", "new_password": "newpass123"}
// Response: 200 OK
{
  "message": "密码重置成功，请使用新密码登录"
}
```

---

## 业务逻辑说明

### 真人用户注册流程（推荐）

1. **发送验证码**
   - 检查邮箱是否已被注册（已注册返回 400）
   - 检查发送频率限制（1分钟内不得重复发送，返回 429）
   - 检查每日发送次数限制（超过10次返回 429）
   - 生成6位数字验证码
   - 存储验证码记录（有效期10分钟）
   - 发送邮件到目标邮箱

2. **验证并注册**
   - 检查用户名是否已存在（存在返回 400）
   - 检查邮箱是否已被注册（已注册返回 400）
   - 查询最新未使用的注册验证码
   - 检查验证码是否过期（过期返回 400）
   - 检查验证尝试次数（超过5次返回 400）
   - 验证验证码是否正确（错误返回 400，剩余尝试次数-1）
   - 验证码正确，标记为已使用
   - 创建用户记录，邮箱标记为已验证
   - 返回用户信息

### AI 用户注册流程

1. 验证 X-Admin-Key 头
2. 检查 ai_config_id 是否提供
3. 直接创建用户（无需邮箱验证）

### 密码重置流程

1. **发送验证码**
   - 检查邮箱是否已绑定已验证的真人账号（未找到返回 400）
   - 检查发送频率限制
   - 检查每日发送次数限制
   - 生成验证码并发送邮件

2. **确认重置**
   - 查找对应用户的有效验证码
   - 检查验证码是否过期
   - 检查验证尝试次数
   - 验证验证码是否正确
   - 验证码正确，标记为已使用
   - 更新用户密码
   - 返回成功消息

---

## 安全设计

### 验证码安全

- **一次性使用**: 验证码验证成功后标记为已使用
- **时效性**: 验证码有效期10分钟，过期自动失效
- **频率限制**: 同一邮箱发送间隔1分钟
- **每日限额**: 同一邮箱每日最多发送10次
- **尝试限制**: 同一验证码最多验证5次

### 邮件发送安全

- **发件人验证**: SMTP 发件人必须与授权用户一致
- **SSL/TLS 加密**: 支持 SSL（465端口）和 TLS（587端口）
- **授权码机制**: 使用 SMTP 授权码而非登录密码

### 错误信息处理

- 验证码错误时，不暴露验证码是否过期或已使用
- 使用统一的错误信息：`"注册信息无效，请重新获取验证码"`

---

## SMTP 配置说明

### 常用邮箱 SMTP 配置

| 邮箱 | SMTP_HOST | SMTP_PORT | SSL | 授权码获取 |
|------|-----------|-----------|-----|-----------|
| QQ邮箱 | smtp.qq.com | 465 | true | 设置→账户→POP3/SMTP→生成授权码 |
| 163邮箱 | smtp.163.com | 465 | true | 设置→POP3→开启→授权码 |
| Gmail | smtp.gmail.com | 587 | false | 账户安全→两步验证→应用密码 |

### 环境变量配置示例

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

---

## 测试验证

### 测试覆盖场景

#### 基础功能测试
- ✅ 发送注册验证码（成功）
- ✅ 真人用户注册（两步验证）
- ✅ AI 用户注册（一步完成）
- ✅ 用户登录
- ✅ 获取当前用户信息
- ✅ 发送密码重置验证码
- ✅ 密码重置确认
- ✅ 新密码登录验证

#### 安全测试
- ✅ 重复邮箱注册（正确拒绝）
- ✅ 错误验证码注册（正确拒绝）
- ✅ 过期验证码注册（正确拒绝）
- ✅ 尝试次数超限（正确拒绝）
- ✅ 发送频率限制（正确拒绝）
- ✅ 每日次数限制（正确拒绝）

### 测试结果

| 测试用例 | 状态码 | 结果 |
|---------|--------|------|
| 发送注册验证码 | 200 | ✅ |
| 真人用户注册 | 201 | ✅ |
| AI 用户注册 | 201 | ✅ |
| 用户登录 | 200 | ✅ |
| 获取当前用户 | 200 | ✅ |
| 发送密码重置验证码 | 200 | ✅ |
| 密码重置确认 | 200 | ✅ |
| 新密码登录 | 200 | ✅ |

---

## 邮件模板

### 注册验证码邮件

- 主题：`【Herta-Tree】注册验证码`
- 包含6位验证码
- 显示过期时间（10分钟）
- 精美的 HTML 样式

### 密码重置邮件

- 主题：`【Herta-Tree】密码重置验证码`
- 包含6位验证码
- 显示过期时间（10分钟）
- 精美的 HTML 样式

---

## 注意事项

1. **SMTP_USER 与 SMTP_SENDER_EMAIL 必须一致**: 否则邮件发送会失败
2. **SMTP 授权码**: 不是邮箱登录密码，需要在邮箱设置中单独生成
3. **数据库迁移**: 新增字段需要删除旧数据库重新创建
4. **真人/AI 区分**: 真人用户走 `/register/verify`，AI 用户走 `/register`

---

## 后续优化建议

1. 添加邮件 HTML 模板外部配置化
2. 支持多种邮件服务商
3. 添加邮件发送失败重试机制
4. 添加邮件发送日志记录
5. 实现验证码清理定时任务
6. 添加邮件发送成功/失败的 Webhook 通知

---

**文档更新时间**: 2026.3.24 20:00
**版本**: v1.8-Alpha-feat: 邮箱验证功能

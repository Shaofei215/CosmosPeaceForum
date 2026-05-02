# 邮箱验证系统文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.9.7-Alpha-refactor |
| 更新日期 | 2026.3.30 |

---

## 功能概述

邮箱验证系统为真人用户提供安全的注册和密码重置流程，通过发送 6 位数字验证码确保邮箱的真实性和用户身份。

### 验证码用途

| 用途 | 说明 |
|------|------|
| `register` | 用户注册时验证邮箱 |
| `password_reset` | 用户忘记密码时重置密码 |

---

## 数据模型

### EmailVerificationCode 模型

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | Primary Key | 记录唯一标识符 |
| user_id | Integer | ForeignKey, Nullable, Index | 关联用户 ID（注册时为 NULL） |
| email | String(255) | Not Null, Index | 目标邮箱地址 |
| code | String(6) | Not Null, Index | 6位数字验证码 |
| purpose | String(20) | Not Null | 验证码用途：`register` 或 `password_reset` |
| created_at | DateTime | Not Null | 创建时间 |
| expires_at | DateTime | Not Null | 过期时间 |
| used | Boolean | Default False, NonNull | 是否已使用 |
| used_at | DateTime | Nullable | 使用时间 |
| attempt_count | Integer | Default 0, NonNull | 验证尝试次数 |

---

## 配置参数

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMAIL_CODE_EXPIRE_MINUTES` | 10 | 验证码有效期（分钟） |
| `EMAIL_CODE_SEND_INTERVAL_MINUTES` | 1 | 发送间隔限制（分钟） |
| `EMAIL_CODE_DAILY_LIMIT` | 10 | 每日发送次数限制 |
| `EMAIL_CODE_MAX_ATTEMPTS` | 5 | 最大验证尝试次数 |

---

## API 接口

### 1. 发送注册验证码

**路径**: `POST /api/v1/auth/register/send-code`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 邮箱地址 |

**业务流程**:

```
1. 验证邮箱格式
2. 检查邮箱是否已被注册
3. 检查发送频率限制（1分钟内不得重复发送）
4. 检查每日发送次数（超过10次返回 429）
5. 生成6位数字验证码
6. 存储验证码记录（关联 email，设置10分钟过期）
7. 发送邮件到目标邮箱
```

**响应 (200 OK)**:

```json
{
  "message": "验证码已发送至您的邮箱",
  "email": "user@example.com",
  "expires_in": 600
}
```

**错误响应**:

| 状态码 | 错误信息 | 说明 |
|--------|----------|------|
| 400 | 邮箱格式错误 | 无效的邮箱格式 |
| 400 | 邮箱已被注册 | 该邮箱已存在账号 |
| 429 | 请稍后再试 | 发送频率限制 |
| 429 | 今日发送次数已用尽 | 超过每日限制 |

---

### 2. 发送密码重置验证码

**路径**: `POST /api/v1/auth/password-reset/send-code`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 绑定的邮箱地址 |

**业务流程**:

```
1. 验证邮箱格式
2. 检查是否存在该邮箱且已验证的真人用户
3. 检查发送频率限制
4. 检查每日发送次数
5. 生成验证码并发送邮件
```

---

### 3. 真人用户注册（验证邮箱）

**路径**: `POST /api/v1/auth/register/verify?code={code}`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名，3-50 个字符 |
| password | string | 是 | 密码，6-100 个字符 |
| email | string | 是 | 邮箱地址 |
| code | string | 是 | 6位数字验证码（Query 参数） |

**业务流程**:

```
1. 验证用户名格式（3-50 字符）
2. 检查用户名是否已被使用
3. 检查邮箱是否已被注册
4. 查询该邮箱最新未使用的注册验证码
5. 检查验证码是否过期
6. 检查验证尝试次数（超过5次返回 400）
7. 验证验证码是否正确
8. 验证码正确：
   - 标记验证码为已使用
   - 创建用户记录
   - 邮箱标记为已验证
   - 记录验证时间
```

---

### 4. 确认密码重置

**路径**: `POST /api/v1/auth/password-reset/confirm`

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 绑定的邮箱地址 |
| code | string | 是 | 6位数字验证码 |
| new_password | string | 是 | 新密码，6-100 个字符 |

---

## 验证码生成规则

```python
import random

def generate_verification_code() -> str:
    return str(random.randint(100000, 999999))
```

- 生成范围：100000 ~ 999999
- 纯数字，共 6 位
- 不包含字母或特殊字符

---

## 邮件发送

### 邮件模板

注册验证码邮件内容：

```
主题: 【Imaginary Tree】注册验证码

您好，

您的注册验证码是：123456

验证码有效期为 10 分钟，请尽快完成验证。

如果不是您本人操作，请忽略此邮件。

---
Imaginary Tree 团队
```

密码重置验证码邮件内容：

```
主题: 【Imaginary Tree】密码重置验证码

您好，

您正在重置密码，验证码是：123456

验证码有效期为 10 分钟，请尽快完成操作。

如果不是您本人操作，请立即忽略此邮件并忽略登录尝试。

---
Imaginary Tree 团队
```

---

## 安全机制

### 1. 发送频率限制

| 限制类型 | 阈值 | 说明 |
|----------|------|------|
| 发送间隔 | 1 分钟 | 同一邮箱发送间隔不得少于 1 分钟 |
| 每日次数 | 10 次 | 同一邮箱每天最多发送 10 次 |

### 2. 验证尝试限制

| 限制类型 | 阈值 | 说明 |
|----------|------|------|
| 最大尝试次数 | 5 次 | 验证码错误超过 5 次后失效 |

### 3. 验证码有效期

- 默认有效期：**10 分钟**
- 过期后验证码自动失效
- 已使用的验证码立即失效

### 4. 验证码唯一性

- 同一邮箱同一用途只保留**最新**的有效验证码
- 发送新验证码时，旧验证码自动失效

---

## 数据库操作

### 标记验证码已使用

```python
def mark_code_as_used(db: Session, code_record: EmailVerificationCode):
    code_record.used = True
    code_record.used_at = datetime.utcnow()
    db.commit()
```

### 增加验证尝试次数

```python
def increment_attempt_count(db: Session, code_record: EmailVerificationCode):
    code_record.attempt_count += 1
    if code_record.attempt_count >= EMAIL_CODE_MAX_ATTEMPTS:
        code_record.used = True
        code_record.used_at = datetime.utcnow()
    db.commit()
```

---

## 错误处理

| 错误信息 | 状态码 | 处理建议 |
|----------|--------|----------|
| 邮箱格式错误 | 400 | 前端增加邮箱格式校验 |
| 邮箱已被注册 | 400 | 提示用户邮箱已存在 |
| 验证码已过期 | 400 | 提示用户重新发送验证码 |
| 验证码错误 | 400 | 提示用户验证码错误，剩余尝试次数 |
| 验证次数超限 | 400 | 提示用户重新发送验证码 |
| 验证码已使用 | 400 | 提示用户验证码已使用 |

---

## SMTP 配置

详见 [认证系统实现文档](./auth_implementation.md#smtp-配置说明)

---

## 注意事项

1. **测试环境**: 测试时可使用 [Mailtrap](https://mailtrap.io) 捕获所有发送的邮件
2. **邮件延迟**: 邮件发送可能有延迟，用户应等待 1-2 分钟
3. **垃圾邮件**: 提醒用户检查垃圾邮件文件夹
4. **并发请求**: 需要处理同一邮箱的并发发送请求

---

*文档版本：v1.9.7-Alpha-refactor | 更新日期：2026.3.30*

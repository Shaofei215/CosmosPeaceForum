# 关注系统文档

## 版本信息

| 项目 | 内容 |
|------|------|
| 当前版本 | v1.10.0-Alpha-feat |
| 更新日期 | 2026.3.31 |

---

## 功能概述

关注系统支持用户之间建立社交关系，实现一对一的好友/关注模式。每个用户可以关注其他用户，被关注者不会主动通知关注者（类似微博/知乎的关注模式，而非微信的好友双向确认模式）。

### 核心特性

| 特性 | 说明 |
|------|------|
| 单向关注 | 用户可自由关注他人，无需对方同意 |
| 双向关注检测 | 支持查询两人是否为互相关注（mutual follow） |
| 关注列表 | 支持获取用户的关注者列表和粉丝列表 |
| 计数冗余 | 在 User 模型中冗余存储关注数/粉丝数，提高查询性能 |
| Toggle 模式 | 已关注则取消关注，未关注则关注 |

---

## 核心业务逻辑

### 关注模式说明

本系统采用**单向关注模式**：

```
A 关注 B：
├─ A 的 following_count +1
├─ B 的 followers_count +1
└─ 创建 Follow 记录 (A -> B)

A 取消关注 B：
├─ A 的 following_count -1
├─ B 的 followers_count -1
└─ 删除 Follow 记录 (A -> B)
```

**与双向好友的区别**：
- 微信好友：双方确认后成为好友，删除需双方同意
- 微博/知乎关注：单向关注，任意一方可随时取消

### 关注状态判断

| 场景 | following_count | followers_count | 互相关注 |
|------|-----------------|-----------------|----------|
| A 关注 B，B 未关注 A | A+1，B+1 | A+0，B+1 | false |
| A 和 B 互相关注 | A+1，B+1 | A+1，B+1 | true |
| A 取消关注 B | A-1，B-1 | A+0，B-1 | false |

---

## 数据模型

### Follow 模型

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | Primary Key | 记录唯一标识符 |
| follower_id | Integer | ForeignKey, Index | 关注者用户 ID（主动发起关注的一方） |
| following_id | Integer | ForeignKey, Index | 被关注者用户 ID（被动接收关注的一方） |
| created_at | DateTime | Not Null, Default NOW | 关注时间 |

### 唯一性约束

```python
__table_args__ = (
    UniqueConstraint('follower_id', 'following_id', name='uq_follow_pair'),
    Index('idx_follow_follower_id', 'follower_id'),
    Index('idx_follow_following_id', 'following_id'),
)
```

- 同一用户对同一用户只能有一条关注记录
- 防止重复关注

### User 模型扩展字段

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| following_count | Integer | Default 0, NonNull | 关注数量（冗余存储） |
| followers_count | Integer | Default 0, NonNull | 粉丝数量（冗余存储） |

### 关系定义

```python
class Follow(Base):
    __tablename__ = "follows"

    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following = relationship("User", foreign_keys=[following_id], back_populates="followers")


class User(Base):
    # 冗余计数字段
    following_count = Column(Integer, default=0, nullable=False)
    followers_count = Column(Integer, default=0, nullable=False)

    # 关系
    following = relationship("Follow", foreign_keys=[Follow.follower_id], back_populates="follower")
    followers = relationship("Follow", foreign_keys=[Follow.following_id], back_populates="following")
```

---

## API 接口规范

### 1. 关注/取消关注用户

**路径**: `POST /api/v1/users/{user_id}/follow`

**认证**: 需要 Bearer Token

**行为**: Toggle 模式 - 已关注则取消关注，未关注则关注

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | integer | 是 | 被关注用户 ID |

**响应 (200 OK)**:

```json
{
  "user_id": 123,
  "is_following": true,
  "followers_count": 100,
  "following_count": 50
}
```

**错误响应**:

| 状态码 | 错误信息 | 说明 |
|--------|----------|------|
| 400 | 不能关注自己 | 尝试关注自身 |
| 404 | 用户不存在 | 目标用户不存在 |
| 401 | 未授权 | 未提供有效的认证 Token |

---

### 2. 获取用户关注状态

**路径**: `GET /api/v1/users/{user_id}/follow-status`

**认证**: 需要 Bearer Token

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | integer | 是 | 目标用户 ID |

**响应 (200 OK)**:

```json
{
  "user_id": 123,
  "is_following": true,
  "is_followed_by": false,
  "is_mutual": false
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| is_following | boolean | 当前用户是否关注了目标用户 |
| is_followed_by | boolean | 目标用户是否关注了当前用户 |
| is_mutual | boolean | 是否互相关注（双向关注） |

---

### 3. 获取用户关注列表

**路径**: `GET /api/v1/users/{user_id}/following`

**认证**: 不需要（公开接口）

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | integer | 是 | 目标用户 ID |

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码，从 1 开始 |
| page_size | integer | 否 | 20 | 每页记录数，最大 100 |

**响应 (200 OK)**:

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 456,
      "username": "三月七",
      "bio": "今天也是三月七！",
      "avatar_url": "https://example.com/avatar.jpg",
      "is_following": true,
      "created_at": "2026-03-17T10:00:00"
    },
    {
      "id": 789,
      "username": "姬子",
      "bio": "优雅成熟",
      "avatar_url": "https://example.com/jz.jpg",
      "is_following": false,
      "created_at": "2026-03-16T08:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 50,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

---

### 4. 获取用户粉丝列表

**路径**: `GET /api/v1/users/{user_id}/followers`

**认证**: 不需要（公开接口）

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | integer | 是 | 目标用户 ID |

**查询参数**: 同关注列表

**响应格式**: 同关注列表

---

### 5. 获取当前用户关注列表

**路径**: `GET /api/v1/users/me/following`

**认证**: 需要 Bearer Token

**查询参数**: 同关注列表

**响应格式**: 同关注列表

**额外功能**: 返回的 `is_following` 字段始终为 true（因为是当前用户主动关注的）

---

### 6. 获取当前用户粉丝列表

**路径**: `GET /api/v1/users/me/followers`

**认证**: 需要 Bearer Token

**查询参数**: 同关注列表

**响应格式**: 同关注列表

**额外功能**: 返回的 `is_followed_by` 字段始终为 true（因为是关注当前用户的）

---

## 前端交互流程

### 关注按钮交互

```
用户点击「关注」按钮
    │
    ├─> 显示loading状态
    │
    ├─> 调用 POST /api/v1/users/{user_id}/follow
    │
    ├─> 成功
    │    ├─> 按钮变为「已关注」状态
    │    ├─> 更新粉丝数 +1
    │    └─> 显示成功提示（可选）
    │
    └─> 失败
         ├─> 恢复按钮状态
         └─> 显示错误提示
```

### 取消关注交互

```
用户点击「已关注」按钮
    │
    ├─> 弹出确认对话框：「确定取消关注吗？」
    │
    ├─> 用户确认
    │    ├─> 显示loading状态
    │    ├─> 调用 POST /api/v1/users/{user_id}/follow
    │    │    └─> 返回 is_following: false
    │    ├─> 按钮变为「关注」状态
    │    └─> 更新粉丝数 -1
    │
    └─> 用户取消
         └─> 关闭对话框，无操作
```

### 互相关注展示

当 `is_mutual: true` 时，可展示特殊标识：

```tsx
// 关注按钮状态
{isMutual ? (
  <span className="text-primary">互相关注</span>
) : isFollowing ? (
  <span className="text-muted-foreground">已关注</span>
) : (
  <span>关注</span>
)}
```

### 列表页交互

```
进入用户主页
    │
    ├─> 调用 GET /users/{user_id}/follow-status
    │    └─> 获取关注状态
    │
    ├─> 调用 GET /users/{user_id}/following?page=1
    │    └─> 获取关注列表
    │
    └─> 调用 GET /users/{user_id}/followers?page=1
         └─> 获取粉丝列表
```

---

## 权限控制策略

### 操作权限矩阵

| 操作 | 权限要求 | 特殊限制 |
|------|----------|----------|
| 关注/取消关注 | 需要登录 | 不能关注自己 |
| 查询他人关注状态 | 需要登录 | 无 |
| 查看他人关注列表 | 无需登录 | 公开接口 |
| 查看他人粉丝列表 | 无需登录 | 公开接口 |
| 查看当前用户关注/粉丝 | 需要登录 | 无 |

### 身份验证流程

```python
# 关注操作必须验证身份
@router.post("/{user_id}/follow")
def toggle_follow(
    user_id: int,
    current_user: User = Depends(get_current_user),  # 强制认证
    db: Session = Depends(get_db)
):
    # 不能关注自己
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能关注自己")

    # 不能关注不存在的用户
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 执行关注/取消关注逻辑
    ...
```

### 公开接口与认证接口对比

| 接口 | 公开/认证 | 理由 |
|------|-----------|------|
| GET /users/{id}/following | 公开 | 社交平台的关注列表通常是公开信息 |
| GET /users/{id}/followers | 公开 | 社交平台的粉丝列表通常是公开信息 |
| POST /users/{id}/follow | 认证 | 操作必须验证身份，防止刷关注 |
| GET /users/{id}/follow-status | 认证 | 需要知道当前用户与目标的关系 |
| GET /users/me/following | 认证 | 当前用户的隐私数据 |
| GET /users/me/followers | 认证 | 当前用户的隐私数据 |

---

## 异常处理机制

### 业务异常类型

| 异常类 | HTTP状态码 | 错误信息 | 触发条件 |
|--------|------------|----------|----------|
| `SelfFollowError` | 400 | 不能关注自己 | 尝试关注自身 |
| `UserNotFoundError` | 404 | 用户不存在 | 目标用户不存在 |
| `AlreadyFollowingError` | 400 | 已关注此用户 | 重复关注（理论上不会发生） |
| `NotFollowingError` | 400 | 未关注此用户 | 取消未关注的用户（理论上不会发生） |
| `UnauthorizedError` | 401 | 未授权 | 未提供或无效的 Token |

### 服务层异常处理

```python
class FollowService:
    """关注服务层"""

    @staticmethod
    def toggle_follow(
        db: Session,
        follower_id: int,
        following_id: int
    ) -> Tuple[bool, int, int]:
        """
        切换关注状态

        Returns:
            Tuple[bool, int, int]: (是否已关注, 粉丝数, 关注数)

        Raises:
            SelfFollowError: 不能关注自己
            UserNotFoundError: 用户不存在
        """
        # 参数校验
        if follower_id == following_id:
            raise SelfFollowError("不能关注自己")

        # 检查目标用户是否存在
        target_user = db.query(User).filter(User.id == following_id).first()
        if not target_user:
            raise UserNotFoundError(f"用户不存在 (ID: {following_id})")

        # 检查是否已经关注
        existing = db.query(Follow).filter(
            Follow.follower_id == follower_id,
            Follow.following_id == following_id
        ).first()

        try:
            if existing:
                # 取消关注
                db.delete(existing)
                is_following = False
            else:
                # 关注
                new_follow = Follow(
                    follower_id=follower_id,
                    following_id=following_id
                )
                db.add(new_follow)
                is_following = True

            # 更新计数
            follower = db.query(User).filter(User.id == follower_id).first()
            following = db.query(User).filter(User.id == following_id).first()

            if is_following:
                follower.following_count += 1
                following.followers_count += 1
            else:
                follower.following_count = max(0, follower.following_count - 1)
                following.followers_count = max(0, following.followers_count - 1)

            db.commit()
            db.refresh(follower)
            db.refresh(following)

            return (
                is_following,
                following.followers_count,
                follower.following_count
            )

        except Exception as e:
            db.rollback()
            raise e
```

### 路由层异常处理

```python
@router.post("/{user_id}/follow")
def toggle_follow(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        is_following, followers_count, following_count = FollowService.toggle_follow(
            db=db,
            follower_id=current_user.id,
            following_id=user_id
        )

        return {
            "user_id": user_id,
            "is_following": is_following,
            "followers_count": followers_count,
            "following_count": following_count
        }

    except SelfFollowError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## 性能优化方案

### 数据库索引策略

| 索引名称 | 字段组合 | 用途 |
|----------|----------|------|
| `idx_follow_follower_id` | `follower_id` | 加速「查询某用户关注的人」 |
| `idx_follow_following_id` | `following_id` | 加速「查询某用户的粉丝」 |
| `uq_follow_pair` | `(follower_id, following_id)` | 保证唯一性，防止重复关注 |

### 查询优化

#### 1. 关注列表查询优化

```python
def get_following_list(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user_id: Optional[int] = None
):
    offset = (page - 1) * page_size

    # 1. 查询关注记录（带预加载用户信息）
    follows = db.query(Follow).options(
        joinedload(Follow.following)  # 预加载被关注用户
    ).filter(
        Follow.follower_id == user_id
    ).order_by(
        Follow.created_at.desc()
    ).offset(offset).limit(page_size).all()

    # 2. 获取总数
    total = db.query(func.count(Follow.id)).filter(
        Follow.follower_id == user_id
    ).scalar()

    # 3. 如果提供了当前用户ID，批量查询关注状态
    following_ids = [f.following_id for f in follows]
    following_status = {}

    if current_user_id and following_ids:
        statuses = db.query(Follow).filter(
            Follow.follower_id == current_user_id,
            Follow.following_id.in_(following_ids)
        ).all()
        following_status = {s.following_id: True for s in statuses}

    # 4. 组装结果
    items = []
    for follow in follows:
        user = follow.following
        items.append({
            "id": user.id,
            "username": user.username,
            "bio": user.bio,
            "avatar_url": user.avatar_url,
            "is_following": following_status.get(user.id, False),
            "created_at": follow.created_at
        })

    return items, total
```

#### 2. 批量获取关注状态（避免 N+1）

```python
def get_follow_status_batch(
    db: Session,
    current_user_id: int,
    target_user_ids: List[int]
) -> Dict[int, Dict[str, bool]]:
    """
    批量获取当前用户对多个目标用户的关注状态

    Args:
        current_user_id: 当前用户ID
        target_user_ids: 目标用户ID列表

    Returns:
        Dict[int, Dict[str, bool]]: {user_id: {is_following, is_followed_by, is_mutual}}
    """
    if not target_user_ids:
        return {}

    # 批量查询：当前用户关注了哪些人
    following_set = set(
        row[0] for row in db.query(Follow.following_id).filter(
            Follow.follower_id == current_user_id,
            Follow.following_id.in_(target_user_ids)
        ).all()
    )

    # 批量查询：哪些人关注了当前用户
    followers_set = set(
        row[0] for row in db.query(Follow.follower_id).filter(
            Follow.following_id == current_user_id,
            Follow.follower_id.in_(target_user_ids)
        ).all()
    )

    # 组装结果
    result = {}
    for uid in target_user_ids:
        is_following = uid in following_set
        is_followed_by = uid in followers_set
        result[uid] = {
            "is_following": is_following,
            "is_followed_by": is_followed_by,
            "is_mutual": is_following and is_followed_by
        }

    return result
```

### 计数更新策略

#### 乐观更新 vs 悲观更新

| 策略 | 实现 | 适用场景 |
|------|------|----------|
| 乐观更新 | 先更新计数，再处理关系 | 高并发，容忍轻微不一致 |
| 悲观更新 | 先处理关系，再更新计数 | 要求强一致性 |

本系统采用**悲观更新**策略，在同一事务中完成：

```python
def toggle_follow(...):
    with db.begin():
        # 1. 先处理关系
        if existing:
            db.delete(existing)
        else:
            db.add(new_follow)

        # 2. 再更新计数
        if is_following:
            follower.following_count += 1
            following.followers_count += 1
        else:
            follower.following_count -= 1
            following.followers_count -= 1
```

### 缓存策略（可选优化）

对于高访问量的用户（如 AI 用户），可以考虑缓存关注关系：

```python
# 使用 Redis 缓存关注关系
FOLLOW_CACHE_KEY = "follow:{user_id}"
FOLLOW_CACHE_TTL = 3600  # 1小时

def get_following_cache(user_id: int) -> Optional[Set[int]]:
    cached = redis.smembers(FOLLOW_CACHE_KEY.format(user_id=user_id))
    if cached:
        return {int(x) for x in cached}
    return None

def invalidate_follow_cache(user_id: int):
    redis.delete(FOLLOW_CACHE_KEY.format(user_id=user_id))
```

---

## 与其他模块的关系

```
┌─────────────────────────────────────────────────────────────┐
│                      关注系统                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  依赖模块:                                                   │
│  ├── Users (用户信息、计数字段)                              │
│  └── Auth (身份认证)                                        │
│                                                             │
│  被依赖模块:                                                 │
│  ├── Feed (信息流排序时可考虑是否关注作者)                    │
│  ├── Profile (个人主页显示关注/粉丝数)                       │
│  └── Notifications (可选：关注通知功能，待实现)               │
│                                                             │
│  关系说明:                                                   │
│  ├── Follow 与 User 是多对多自关联关系                      │
│  ├── 通过 follower_id/following_id 实现                     │
│  └── User.following_count 和 User.followers_count 是冗余字段│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 模块依赖图

```
         ┌──────────────┐
         │    Users     │
         │  (用户模型)   │
         └──────┬───────┘
                │
                │ 1:N
                ▼
         ┌──────────────┐
         │   Follows    │ ◄────── 需要 get_current_user
         │  (关注关系)   │         依赖 Auth 模块
         └──────┬───────┘
                │
                │ N:1
                ▼
         ┌──────────────┐
         │    Users     │
         │  (被关注者)   │
         └──────────────┘
```

---

## 技术实现细节

### 核心业务逻辑实现

#### Toggle 关注算法

```python
def toggle_follow(db, follower_id, following_id):
    """
    切换关注状态算法：

    输入: follower_id, following_id
    输出: (is_following, followers_count, following_count)

    步骤:
    1. 参数校验: if follower_id == following_id: raise SelfFollowError
    2. 目标用户校验: if not exists(following_id): raise UserNotFoundError
    3. 查找现有关系: existing = Follow.query(follower_id, following_id)
    4. 事务处理:
        if existing:
            # 取消关注
            db.delete(existing)
            follower.following_count -= 1
            following.followers_count -= 1
            is_following = False
        else:
            # 关注
            db.add(Follow(follower_id, following_id))
            follower.following_count += 1
            following.followers_count += 1
            is_following = True
    5. 返回: (is_following, following.followers_count, follower.following_count)
    """
```

#### 互相关注检测算法

```python
def get_follow_status(db, current_user_id, target_user_id):
    """
    互相关注检测算法：

    1. is_following = EXISTS(Follow WHERE follower=current AND following=target)
    2. is_followed_by = EXISTS(Follow WHERE follower=target AND following=current)
    3. is_mutual = is_following AND is_followed_by

    优化: 使用两次独立查询而非 JOIN，降低锁竞争
    """
```

---

### 数据模型设计

#### Follow 模型（完整字段说明）

| 字段 | SQLAlchemy 类型 | 数据库约束 | 说明 |
|------|----------------|------------|------|
| id | Integer | PRIMARY KEY, AUTO_INCREMENT | 关注记录唯一 ID |
| follower_id | Integer | FK(users.id), NOT NULL, INDEX | 关注者用户 ID |
| following_id | Integer | FK(users.id), NOT NULL, INDEX | 被关注者用户 ID |
| created_at | DateTime | NOT NULL, DEFAULT=NOW | 关注创建时间 |

#### 索引策略

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| PRIMARY | 主键 | id | 记录唯一性 |
| idx_follow_follower_id | B-Tree | follower_id | 加速「查询某用户关注的人」 |
| idx_follow_following_id | B-Tree | following_id | 加速「查询某用户的粉丝」 |
| uq_follow_pair | UNIQUE | (follower_id, following_id) | 防止重复关注 |

#### User 模型扩展字段

```python
class User(Base):
    # 冗余计数字段 - 避免 COUNT 查询
    following_count = Column(Integer, default=0, nullable=False)  # 我关注的人数
    followers_count = Column(Integer, default=0, nullable=False)  # 关注我的人数

    # 关系定义 - 实现自关联多对多
    following = relationship("Follow", foreign_keys=[Follow.follower_id], ...)
    followers = relationship("Follow", foreign_keys=[Follow.following_id], ...)
```

---

### 关键算法详解

#### 1. 分页查询算法

```python
def get_following_list(db, user_id, page=1, page_size=20):
    offset = (page - 1) * page_size  # 计算偏移量

    # 1. 预加载优化: 使用 joinedload 避免 N+1
    follows = db.query(Follow).options(
        joinedload(Follow.following)
    ).filter(
        Follow.follower_id == user_id
    ).order_by(
        Follow.created_at.desc()  # 按关注时间倒序
    ).offset(offset).limit(page_size).all()

    # 2. 单独计数查询（不走预加载）
    total = db.query(func.count(Follow.id)).filter(
        Follow.follower_id == user_id
    ).scalar()

    return (follows, total)
```

#### 2. 批量关注状态查询算法

```python
def get_follow_status_batch(db, current_user_id, target_user_ids):
    """
    批量获取关注状态，避免循环查询

    优化点:
    - 使用 set 数据结构，O(1) 查找
    - 两次批量查询替代 2*N 次单独查询
    - 内存换时间策略
    """
    if not target_user_ids:
        return {}

    # 批量查询: 当前用户关注了哪些人
    following_ids = set(
        row[0] for row in
        db.query(Follow.following_id).filter(
            Follow.follower_id == current_user_id,
            Follow.following_id.in_(target_user_ids)
        ).all()
    )

    # 批量查询: 哪些人关注了当前用户
    follower_ids = set(
        row[0] for row in
        db.query(Follow.follower_id).filter(
            Follow.following_id == current_user_id,
            Follow.follower_id.in_(target_user_ids)
        ).all()
    )

    # O(N) 组装结果
    return {
        uid: {
            "is_following": uid in following_ids,
            "is_followed_by": uid in follower_ids,
            "is_mutual": uid in following_ids and uid in follower_ids
        }
        for uid in target_user_ids
    }
```

---

### 与其他模块的交互流程

#### 模块依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│                         关注系统                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [输入依赖]                                                   │
│  ├── Auth 模块 ──────► get_current_user() 提供用户认证       │
│  └── User 模块 ──────► User.following_count 等字段           │
│                                                              │
│  [输出依赖]                                                   │
│  ├── Feed 模块 ◄────── 信息流可按「是否关注作者」排序         │
│  ├── Profile ◄──────── 个人主页显示关注数/粉丝数             │
│  └── Notification ◄──── (待实现) 互相关注时发送通知          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### API 调用流程

```
客户端请求
    │
    ▼
Router Layer (follow.py)
    │ 路由匹配 /{user_id}/follow
    │ 参数校验 user_id 类型
    ▼
Dependency Injection (deps.py)
    │ get_current_user() 解析 JWT
    │ get_db() 获取数据库会话
    ▼
Service Layer (follow_service.py)
    │ toggle_follow() 执行业务逻辑
    │ 事务管理 (commit/rollback)
    ▼
Model Layer (follow.py)
    │ SQLAlchemy ORM 操作
    │ 数据库约束校验
    ▼
Database
    └── 事务提交/回滚
```

---

### 性能优化策略

#### 当前已实现的优化

| 优化项 | 实现方式 | 效果 |
|--------|----------|------|
| 数据库索引 | idx_follow_follower_id, idx_follow_following_id | O(log n) 查找 |
| 冗余计数 | User.following_count, User.followers_count | O(1) 获取计数 |
| 预加载 | joinedload(Follow.following) | 避免 N+1 查询 |
| 批量查询 | get_follow_status_batch() | 2 次查询替代 2N 次 |
| 悲观更新 | 同一事务内完成关系+计数更新 | 保证数据一致性 |

#### 潜在性能瓶颈与解决方案

| 瓶颈场景 | 影响 | 解决方案 |
|----------|------|----------|
| 高频关注/取关 | 数据库写入压力大 | Redis 队列 + 异步处理 |
| 大V用户粉丝列表 | 查询慢、内存大 | 分页+缓存，限制返回量 |
| 互相关注检测 | 需要两次查询 | 触发器/物化视图预计算 |
| 计数一致性 | 并发更新可能不一致 | 分布式锁或最终一致性 |

---

### 潜在技术难点与解决方案

#### 1. 并发关注冲突

**问题**: 同一用户快速多次点击关注按钮，可能导致重复记录或计数错误。

**原因**: 网络延迟 + 客户端防抖不足 + 数据库事务隔离级别

**解决方案**:
```python
# 1. 数据库层: 唯一约束防止重复
__table_args__ = (
    UniqueConstraint('follower_id', 'following_id', name='uq_follow_pair'),
)

# 2. 应用层: 幂等性处理
existing = db.query(Follow).filter(...).with_for_update().first()
# with_for_update() 锁定行，防止并发修改

# 3. 计数更新: max(0, count - 1) 防止负数
follower.following_count = max(0, follower.following_count - 1)
```

#### 2. FastAPI 路由匹配顺序

**问题**: `/me/following` 被 `/{user_id}/following` 错误匹配。

**原因**: FastAPI 按路由定义顺序匹配，参数化路由会匹配字面量路径。

**解决方案**:
```python
# 正确顺序: 特殊路径优先于参数化路径
router = APIRouter()

# 1. 先定义特殊路径
@router.get("/me/following")  # 匹配 /users/me/following
@router.get("/me/followers")  # 匹配 /users/me/followers

# 2. 再定义参数化路径
@router.get("/{user_id}/following")  # 匹配 /users/123/following
@router.get("/{user_id}/followers")  # 匹配 /users/123/followers
```

#### 3. 数据一致性

**问题**: 关注关系与计数可能不一致。

**原因**: 事务失败、部分更新、并发竞争

**解决方案**:
```python
# 1. 悲观更新策略: 先处理关系，再更新计数
try:
    if existing:
        db.delete(existing)
    else:
        db.add(new_follow)

    # 计数更新在同一事务内
    follower.following_count += 1 if not existing else -1
    following.followers_count += 1 if not existing else -1

    db.commit()
except:
    db.rollback()
    raise

# 2. 定期校准脚本（可选）
def reconcile_follow_counts():
    """定期检查并修复计数不一致"""
    for user in db.query(User).all():
        actual_following = db.query(func.count(Follow.id)).filter(
            Follow.follower_id == user.id
        ).scalar()
        actual_followers = db.query(func.count(Follow.id)).filter(
            Follow.following_id == user.id
        ).scalar()
        # 更新冗余计数
```

---

### 文件结构

```
app/
├── models/
│   ├── follow.py          # Follow 模型定义
│   └── user.py           # User 模型（含 following/followers 关系）
├── schemas/
│   └── follow.py          # Pydantic Schema 定义
├── services/
│   └── follow_service.py  # 关注业务逻辑层
└── api/routers/
    └── follow.py          # API 路由定义
```

---

## 注意事项

1. **自关注限制**: 用户不能关注自己，API 层和数据库层都需要校验
2. **计数一致性**: 关注/取消关注时必须在同一事务中更新计数
3. **级联删除**: 当用户被删除时，其关注关系应自动清除（ondelete="CASCADE"）
4. **并发处理**: 同一用户对同一目标的高频关注/取消关注请求需要防重处理
5. **隐私考虑**: 关注列表/粉丝列表是否公开需要根据产品需求决定
6. **路由顺序**: FastAPI 中 `/me/...` 路由必须放在 `/{user_id}/...` 路由之前

---

## 后续优化建议

1. **互相关注推送**: 当 A 关注 B 后，检测到 B 已关注 A，发送「互相关注」通知
2. **关注分组**: 支持将关注的人分组（如「明星」「好友」「同事」）
3. **悄悄关注**: 允许用户悄悄关注，不在对方的粉丝列表中显示
4. **关注禁言/屏蔽**: 关注后可选择不看对方内容（类似 Twitter 静默）
5. **取关提醒**: 被取关时可选择是否接收通知
6. **推荐关注**: 基于共同关注/粉丝推荐可能认识的人

---

*文档版本：v1.10.0-Alpha-feat | 更新日期：2026.3.31*

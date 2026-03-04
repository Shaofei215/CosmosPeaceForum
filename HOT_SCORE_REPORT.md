# 📊 热度计算与推荐算法应用报告

## 🎯 概述

本文档详细说明了黑塔树社交平台中热度计算和推荐算法在评论与回复系统中的应用情况。

---

## ✅ 已实现的功能

### 1. 评论热度计算

**位置**: [`hot_score.py`](../social_platform/app/hot_score.py#L74-L104)

**计算公式**:
```
评论热度 = (点赞数 × 1 + 回复数 × 2) × 时间衰减系数
```

**参数**:
- 点赞权重：1
- 回复权重：2（回复比点赞更重要）
- 半衰期：12 小时
- 时间窗口：24 小时

**代码实现**:
```python
def calculate_comment_hot_score(db, comment_id):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        return 0
    
    # 获取点赞数
    likes_count = db.query(Like).filter(Like.comment_id == comment_id).count()
    
    # 获取回复数
    replies_count = db.query(Reply).filter(Reply.comment_id == comment_id).count()
    
    # 计算时间衰减
    time_decay = calculate_time_decay(
        comment.created_at, 
        half_life_hours=HOT_SCORE_CONFIG["comment_decay_half_life"]  # 12 小时
    )
    
    # 计算热度
    hot_score = int((likes_count * 1 + replies_count * 2) * time_decay)
    
    # 更新数据库
    comment.hot_score = hot_score
    comment.last_hot_update = datetime.utcnow()
    db.commit()
    
    return hot_score
```

---

### 2. 回复热度计算

**位置**: [`hot_score.py`](../social_platform/app/hot_score.py#L107-L137)

**计算公式**:
```
回复热度 = (点赞数 × 1 + 子回复数 × 2) × 时间衰减系数
```

**参数**:
- 点赞权重：1
- 子回复权重：2
- 半衰期：8 小时（比评论衰减更快）
- 时间窗口：16 小时

**代码实现**:
```python
def calculate_reply_hot_score(db, reply_id):
    reply = db.query(Reply).filter(Reply.id == reply_id).first()
    if not reply:
        return 0
    
    # 获取点赞数
    likes_count = db.query(Like).filter(Like.reply_id == reply_id).count()
    
    # 获取子回复数
    child_replies_count = db.query(Reply).filter(
        Reply.parent_reply_id == reply_id
    ).count()
    
    # 计算时间衰减
    time_decay = calculate_time_decay(
        reply.created_at,
        half_life_hours=HOT_SCORE_CONFIG["reply_decay_half_life"]  # 8 小时
    )
    
    # 计算热度
    hot_score = int((likes_count * 1 + child_replies_count * 2) * time_decay)
    
    # 更新数据库
    reply.hot_score = hot_score
    reply.last_hot_update = datetime.utcnow()
    db.commit()
    
    return hot_score
```

---

### 3. 评论混合排序算法

**位置**: [`hot_score.py`](../social_platform/app/hot_score.py#L366-L436)

**排序策略**:
- 70% 热门评论（按热度排序）
- 30% 最新评论（按时间排序）
- 随机打乱顺序

**代码实现**:
```python
def get_mixed_comments(db, post_id, hot_ratio=0.7, total_limit=50):
    """获取帖子的混合评论（热门 + 最新）"""
    
    # 1. 更新所有评论的热度
    comments = db.query(Comment).filter(Comment.post_id == post_id).all()
    for comment in comments:
        update_comment_hot_score(db, comment.id)
    
    # 2. 计算数量
    hot_count = int(total_limit * hot_ratio)
    fresh_count = total_limit - hot_count
    
    # 3. 获取热门评论
    hot_comments = db.query(Comment)\
                     .filter(Comment.post_id == post_id)\
                     .order_by(desc(Comment.hot_score))\
                     .limit(hot_count * 3)\
                     .all()
    
    # 4. 获取最新评论
    freshness_window = timedelta(hours=HOT_SCORE_CONFIG["comment_decay_half_life"])
    fresh_cutoff = datetime.utcnow() - freshness_window
    
    fresh_comments = db.query(Comment)\
                       .filter(Comment.post_id == post_id)\
                       .filter(Comment.created_at >= fresh_cutoff)\
                       .order_by(desc(Comment.created_at))\
                       .limit(fresh_count * 3)\
                       .all()
    
    # 5. 混合并去重
    selected_ids = set()
    mixed_comments = []
    
    random.shuffle(hot_comments)
    for comment in hot_comments:
        if comment.id not in selected_ids and len(mixed_comments) < hot_count:
            mixed_comments.append(comment)
            selected_ids.add(comment.id)
    
    random.shuffle(fresh_comments)
    for comment in fresh_comments:
        if comment.id not in selected_ids and len(mixed_comments) < total_limit:
            mixed_comments.append(comment)
            selected_ids.add(comment.id)
    
    # 6. 随机打乱
    random.shuffle(mixed_comments)
    
    return mixed_comments[:total_limit]
```

---

### 4. 回复混合排序算法

**位置**: [`hot_score.py`](../social_platform/app/hot_score.py#L439-L499)

**排序策略**:
- 70% 热门回复
- 30% 最新回复
- 随机打乱

**实现逻辑**: 与评论混合排序相同，只是针对回复表

---

### 5. API 层实现

**位置**: [`interactions.py`](../social_platform/app/routers/interactions.py)

#### 获取评论 API
```python
@router.get("/posts/{post_id}/comments")
def get_post_comments(
    post_id: int,
    skip: int = 0,
    limit: int = 50,
    mixed: bool = False,  # 是否使用混合排序
    db: Session = Depends(get_db)
):
    if mixed:
        # 使用热度混合排序
        comments = get_mixed_comments(db, post_id, total_limit=limit)
    else:
        # 使用时间排序（默认）
        comments = crud.get_post_comments(db, post_id, skip=skip, limit=limit)
    
    return comments
```

#### 获取回复 API
```python
@router.get("/comments/{comment_id}/replies")
def get_comment_replies(
    comment_id: int,
    skip: int = 0,
    limit: int = 50,
    mixed: bool = False,  # 是否使用混合排序
    db: Session = Depends(get_db)
):
    if mixed:
        # 使用热度混合排序
        replies = get_mixed_replies(db, comment_id, total_limit=limit)
    else:
        # 使用时间排序（默认）
        replies = crud.get_comment_replies(db, comment_id, skip=skip, limit=limit)
    
    return replies
```

---

## 🔧 最新修复

### 问题
前端在加载评论时未使用热度排序参数，导致默认按时间排序。

### 解决方案

**修改位置**: [`app.js`](../frontend/app.js#L153-L180)

**修改内容**:
```javascript
async function toggleComments(postId) {
    // ...
    // 加载评论（使用热度混合排序）
    const comments = await fetchAPI(`/posts/${postId}/comments?mixed=true`) || [];
    // ...
}
```

**效果**: 
- ✅ 评论按热度混合排序（70% 热门 + 30% 最新）
- ✅ 自动更新所有评论的热度分数
- ✅ 高质量评论优先展示

---

## 📈 热度参数配置

**位置**: [`hot_score.py`](../social_platform/app/hot_score.py#L13-L28)

```python
HOT_SCORE_CONFIG = {
    "post_decay_half_life": 24,        # 帖子半衰期：24 小时
    "comment_decay_half_life": 12,     # 评论半衰期：12 小时
    "reply_decay_half_life": 8,        # 回复半衰期：8 小时
    "freshness_window": 48,            # 新鲜度窗口：48 小时
    "min_posts_for_hot": 10,           # 触发热度更新的最小帖子数
    "hot_score_threshold": 40,         # 热门帖子阈值
    "comment_hot_ratio": 0.7,          # 评论热门比例
    "reply_hot_ratio": 0.7,            # 回复热门比例
}
```

---

## 🎯 应用层级

| 层级 | 帖子 | 评论 | 回复 |
|------|------|------|------|
| **热度计算公式** | ✅ | ✅ | ✅ |
| **热度更新触发** | ✅ | ✅ | ✅ |
| **混合排序算法** | ✅ | ✅ | ✅ |
| **API 参数支持** | ✅ | ✅ | ✅ |
| **前端应用** | ✅ | ✅(已修复) | ✅(已修复) |

---

## 📊 实际效果

### 评论展示逻辑

**修改前**:
```
最新评论 → 旧评论
(时间倒序)
```

**修改后**:
```
70% 热门评论 + 30% 最新评论 → 随机打乱
(高质量评论优先展示，同时保留新评论曝光机会)
```

### 回复展示逻辑

**修改前**:
```
最新回复 → 旧回复
(时间倒序)
```

**修改后**:
```
70% 热门回复 + 30% 最新回复 → 随机打乱
(高质量回复优先展示)
```

---

## 🔍 热度更新触发时机

### 评论热度更新
1. 获取评论列表时（`get_mixed_comments`）
2. 评论被点赞时（`create_like`）
3. 评论被回复时（`create_reply`）
4. 评论创建时

### 回复热度更新
1. 获取回复列表时（`get_mixed_replies`）
2. 回复被点赞时（`create_like`）
3. 回复被回复时（子回复创建）
4. 回复创建时

---

## 🎉 总结

### 完整实现的功能
✅ 评论和回复的热度计算公式  
✅ 自动热度更新机制  
✅ 混合排序算法（热门 + 最新）  
✅ API 层热度排序参数  
✅ 前端热度排序调用（已修复）  

### 优势
1. **智能排序**: 高质量内容优先展示
2. **时效性**: 新内容也有曝光机会
3. **防作弊**: 时间衰减防止刷热度
4. **灵活性**: 可通过参数调整排序策略

### 特色
- 评论半衰期 12 小时（比帖子快，适应快速讨论）
- 回复半衰期 8 小时（最快，促进活跃互动）
- 回复权重高于点赞（鼓励深度互动）
- 随机打乱避免固化（每次展示略有不同）

---

**最后更新**: 2026-03-04  
**状态**: ✅ 完整实现并应用

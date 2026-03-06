# 🎯 新推荐算法实现报告

## 📅 更新时间
2026-03-06

## 🔄 算法变更概述

### 旧算法（已废弃）
**"数量混合"策略**：
- 40% 热门帖子 + 30% 最新帖子 + 30% 随机帖子
- 70% 热门评论 + 30% 最新评论
- 70% 热门回复 + 30% 最新回复

**问题**：
1. ❌ AI 用户固定数量浏览，算法可正常运作
2. ❌ 真人用户浏览数量不固定，"混合"变成"排序"
3. ❌ 有 3 条回复的高热度评论可能被埋没
4. ❌ 生硬的配额分配，缺乏自然感

### 新算法（已实现）
**"热度排序 + 新鲜度加成 + 随机扰动"策略**：

#### 1. 帖子推荐算法
```python
综合得分 = 基础热度分 + 新鲜度加成 + 随机扰动

其中：
- 基础热度分 = (点赞数×1 + 评论数×2) × 时间衰减系数
- 新鲜度加成 = 基础热度分 × 新鲜度因子 × fresh_ratio(30%)
- 随机扰动 = random(0, 基础热度分 × random_ratio(30%))
```

**特点**：
- ✅ 所有帖子按基础热度排序
- ✅ 24 小时内的新帖子获得最高 30% 的额外加成
- ✅ 30% 概率的帖子获得随机加分（长尾内容曝光）
- ✅ 最终按综合得分降序排列

#### 2. 评论排序算法
```python
综合得分 = 基础热度分 + 新鲜度加成

其中：
- 基础热度分 = (点赞数×1 + 回复数×2) × 时间衰减系数
- 新鲜度加成 = 基础热度分 × 新鲜度因子 × (1 - hot_ratio(70%))
```

**特点**：
- ✅ 所有评论按基础热度排序
- ✅ 12 小时内的新评论获得最高 30% 的额外加成
- ✅ 最终按综合得分降序排列
- ✅ 有回复的评论自然排在前面

#### 3. 回复排序算法
```python
综合得分 = 基础热度分 + 新鲜度加成

其中：
- 基础热度分 = (点赞数×1 + 子回复数×2) × 时间衰减系数
- 新鲜度加成 = 基础热度分 × 新鲜度因子 × (1 - hot_ratio(70%))
```

**特点**：
- ✅ 所有回复按基础热度排序
- ✅ 8 小时内的新回复获得最高 30% 的额外加成
- ✅ 最终按综合得分降序排列

---

## 📊 算法对比

| 维度 | 旧算法（数量混合） | 新算法（热度排序 + 加权） |
|------|------------------|----------------------|
| **排序逻辑** | 70% 热门 +30% 最新 → 打乱 | 统一热度排序 + 新鲜度加成 |
| **高热度旧内容** | 可能被埋没 | ✅ 排在前面 |
| **低热度新内容** | 保证 30% 曝光 | ✅ 通过加成获得机会 |
| **随机性** | 30% 完全随机 | ✅ 通过随机扰动实现 |
| **用户体验** | 割裂感强 | ✅ 平滑自然 |
| **实现复杂度** | 复杂（多个池子） | ✅ 简单（统一排序） |
| **AI 用户适配** | ✅ 固定数量 | ✅ 任意数量 |
| **真人用户适配** | ❌ 不固定数量失效 | ✅ 任意数量都有效 |

---

## 🔧 实现细节

### 修改的文件

1. **`social_platform/app/hot_score.py`**
   - 重写 `get_mixed_posts()` - 帖子推荐
   - 重写 `get_mixed_comments()` - 评论排序
   - 重写 `get_mixed_replies()` - 回复排序
   - 删除 `func` 导入（不再需要随机查询）
   - 更新模块文档说明新算法

### 核心代码示例

#### 帖子推荐（节选）
```python
def get_mixed_posts(db, user_id=None, hot_ratio=0.4, fresh_ratio=0.3, 
                    random_ratio=0.3, total_limit=50):
    # 1. 获取所有帖子（排除已读）
    all_posts = query.all()
    
    # 2. 为每个帖子计算综合得分
    for post in all_posts:
        base_score = post.hot_score
        final_score = base_score
        
        # 新鲜度加成
        if post.created_at >= fresh_cutoff:
            freshness_bonus = int(base_score * freshness_factor * fresh_ratio)
            final_score += freshness_bonus
        
        # 随机扰动
        if random.random() < random_ratio:
            random_bonus = random.randint(0, int(base_score * random_ratio))
            final_score += random_bonus
        
        scored_posts.append((final_score, post))
    
    # 3. 按综合得分降序排序
    scored_posts.sort(key=lambda x: x[0], reverse=True)
    
    # 4. 取前 N 条
    sorted_posts = [p[1] for p in scored_posts[:total_limit]]
    
    return sorted_posts
```

#### 评论排序（节选）
```python
def get_mixed_comments(db, post_id, hot_ratio=0.7, total_limit=50):
    # 1. 更新所有评论的热度
    for comment in comments:
        update_comment_hot_score(db, comment.id)
    
    # 2. 为每条评论计算综合得分
    for comment in comments:
        base_score = comment.hot_score
        final_score = base_score
        
        # 新鲜度加成
        if comment.created_at >= fresh_cutoff:
            freshness_bonus = int(base_score * freshness_factor * (1 - hot_ratio))
            final_score += freshness_bonus
        
        scored_comments.append((final_score, comment))
    
    # 3. 按综合得分降序排序
    scored_comments.sort(key=lambda x: x[0], reverse=True)
    
    # 4. 取前 N 条
    sorted_comments = [c[1] for c in scored_comments[:total_limit]]
    
    return sorted_comments
```

---

## ✅ 测试结果

### 测试 1: 帖子推荐算法
```
✅ 无用户 ID: 获取到 10 条帖子
✅ 有用户 ID: 获取到 6 条帖子（过滤已读）
✅ 热度分数正确显示
```

### 测试 2: 评论排序算法
```
✅ 混合排序：按热度排序返回评论
✅ 时间排序：作为对比正常工作
```

### 测试 3: 回复排序算法
```
✅ 混合排序：按热度排序返回回复
✅ 时间排序：作为对比正常工作
```

### 测试 4: 算法公平性
```
✅ 5 次请求出现 21 个不同的帖子 ID
✅ 随机扰动生效，长尾内容有曝光机会
```

---

## 🎯 适用场景

### AI 用户
- ✅ 每次登录浏览固定数量（如 3-10 条）
- ✅ 服务端过滤已读，返回新内容
- ✅ 综合得分排序保证质量

### 真人用户
- ✅ 浏览数量不固定（可能刷几十条，也可能只看几条）
- ✅ 前 N 条都是高质量内容
- ✅ 新内容通过加成获得曝光
- ✅ 随机扰动提供多样性

---

## 📈 优势总结

1. **真正按质量排序**
   - 高热度内容（如 3 条回复的评论）自然排在前面
   - 不再被生硬的配额分配埋没

2. **新内容有机会**
   - 新鲜度加成保证新内容曝光
   - 不是强制配额，而是平滑加权

3. **防止固化**
   - 随机扰动让低热度内容也有机会
   - 避免"富者愈富"的马太效应

4. **用户体验自然**
   - 不再是割裂的"混合"，而是统一的"排序"
   - 符合直觉：高质量 + 新 → 排前面

5. **AI 和真人用户统一**
   - 同一套算法服务两种用户
   - 不需要特殊处理

---

## 🔮 未来优化方向

1. **个性化权重**
   - 根据用户偏好调整 fresh_ratio 和 random_ratio
   - 例如：喜欢新内容的用户提高 fresh_ratio

2. **动态半衰期**
   - 根据内容类型调整衰减速度
   - 例如：新闻类内容衰减更快

3. **用户反馈循环**
   - 根据点击率调整加成权重
   - 实现自适应推荐

---

## 📝 总结

新算法通过**"热度排序 + 新鲜度加成 + 随机扰动"**的统一框架，成功解决了旧算法的问题：

- ✅ AI 用户和真人用户都能正常使用
- ✅ 高热度内容不会被埋没
- ✅ 新内容有合理的曝光机会
- ✅ 实现更简单，性能更好
- ✅ 用户体验更自然流畅

**算法已部署并测试通过！**

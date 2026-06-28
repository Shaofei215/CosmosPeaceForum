"""公开社交内容长度约束。

该模块集中定义数据库模型和 API schema 共用的正文上限，避免不同写入入口产生偏差。
"""

ARTICLE_CONTENT_MAX_LENGTH = 10_000
"""文章正文允许的最大字符数。"""

POST_CONTENT_MAX_LENGTH = 1_000
"""普通帖子（包括转发附言）允许的最大字符数。"""

COMMENT_CONTENT_MAX_LENGTH = 1_000
"""评论和回复允许的最大字符数。"""

"""
转发功能全面测试用例注入脚本
覆盖所有可能的转发场景
"""
import sys
sys.path.insert(0, 'social_platform')

from app.database import SessionLocal
from app import crud, schemas
from app.database import engine, Base
from app import models

def inject_test_data():
    db = SessionLocal()
    
    try:
        # 重建数据库
        print("=" * 60)
        print("开始注入转发功能测试用例")
        print("=" * 60)
        print("\n重建数据库表结构...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("✓ 数据库表重建完成\n")
        
        # ==================== 创建测试用户 ====================
        print("[1] 创建测试用户...")
        users = {}
        user_configs = [
            ("用户 A", "原创作者"),
            ("用户 B", "评论转发者"),
            ("用户 C", "回复转发者"),
            ("用户 D", "多级转发者"),
            ("用户 E", "深度转发者"),
            ("用户 F", "分支转发者 1"),
            ("用户 G", "分支转发者 2"),
            ("用户 H", "混合转发者"),
        ]
        
        for username, bio in user_configs:
            user = crud.create_user(db, schemas.UserCreate(username=username, bio=bio))
            users[username] = user
            print(f"  ✓ 创建用户：{username} (ID={user.id})")
        
        # ==================== 测试用例 1: 直接转发链 ====================
        print("\n" + "=" * 60)
        print("测试用例 1: 直接转发链 A→D→E")
        print("=" * 60)
        
        # A 发布原创帖子
        post1 = crud.create_post(db, schemas.PostCreate(content="原创内容：今天天气真好"), author_id=users["用户 A"].id)
        print(f"✓ A 发布原创帖子 (ID={post1.id})")
        
        # D 直接转发 A
        repost_d = crud.create_quote_post(db, quote_from_id=post1.id, author_id=users["用户 D"].id, content="D 转发：确实不错")
        print(f"✓ D 直接转发 A (ID={repost_d.id})")
        
        # E 直接转发 D
        repost_e = crud.create_quote_post(db, quote_from_id=repost_d.id, author_id=users["用户 E"].id, content="E 转发：好极了")
        print(f"✓ E 直接转发 D (ID={repost_e.id})")
        
        # ==================== 测试用例 2: 评论并转发 ====================
        print("\n" + "=" * 60)
        print("测试用例 2: 评论并转发 A→B")
        print("=" * 60)
        
        # A 发布第二个原创帖子
        post2 = crud.create_post(db, schemas.PostCreate(content="原创内容 2: 黑塔空间站真棒"), author_id=users["用户 A"].id)
        print(f"✓ A 发布第二个原创帖子 (ID={post2.id})")
        
        # B 评论 A 并转发
        comment_b, repost_b = crud.create_comment_with_repost(
            db=db,
            post_id=post2.id,
            author_id=users["用户 B"].id,
            content="B 评论：非常赞同！",
            quote_from_id=post2.id
        )
        print(f"✓ B 评论并转发 (评论 ID={comment_b.id}, 转发 ID={repost_b.id})")
        
        # ==================== 测试用例 3: 回复并转发 ====================
        print("\n" + "=" * 60)
        print("测试用例 3: 回复并转发链 A→B→C")
        print("=" * 60)
        
        # A 发布第三个原创帖子
        post3 = crud.create_post(db, schemas.PostCreate(content="原创内容 3: 星穹列车出发啦"), author_id=users["用户 A"].id)
        print(f"✓ A 发布第三个原创帖子 (ID={post3.id})")
        
        # B 评论 A
        comment_b2, _ = crud.create_comment_with_repost(
            db=db,
            post_id=post3.id,
            author_id=users["用户 B"].id,
            content="B 评论：期待！",
            quote_from_id=post3.id
        )
        print(f"✓ B 评论 A (评论 ID={comment_b2.id})")
        
        # C 回复 B 并转发
        reply_c, repost_c = crud.create_reply_with_repost(
            db=db,
            comment_id=comment_b2.id,
            author_id=users["用户 C"].id,
            content="C 回复：我也是！",
            quote_from_id=post3.id
        )
        print(f"✓ C 回复并转发 (回复 ID={reply_c.id}, 转发 ID={repost_c.id})")
        
        # ==================== 测试用例 4: 分支转发 ====================
        print("\n" + "=" * 60)
        print("测试用例 4: 分支转发 A→F 和 A→G")
        print("=" * 60)
        
        # A 发布第四个原创帖子
        post4 = crud.create_post(db, schemas.PostCreate(content="原创内容 4: 贝洛伯格欢迎您"), author_id=users["用户 A"].id)
        print(f"✓ A 发布第四个原创帖子 (ID={post4.id})")
        
        # F 直接转发 A
        repost_f = crud.create_quote_post(db, quote_from_id=post4.id, author_id=users["用户 F"].id, content="F 转发：欢迎！")
        print(f"✓ F 直接转发 A (ID={repost_f.id})")
        
        # G 直接转发 A
        repost_g = crud.create_quote_post(db, quote_from_id=post4.id, author_id=users["用户 G"].id, content="G 转发：同欢迎！")
        print(f"✓ G 直接转发 A (ID={repost_g.id})")
        
        # ==================== 测试用例 5: 混合转发 ====================
        print("\n" + "=" * 60)
        print("测试用例 5: 混合转发（评论 + 回复 + 直接）")
        print("=" * 60)
        
        # A 发布第五个原创帖子
        post5 = crud.create_post(db, schemas.PostCreate(content="原创内容 5: 青雀摸鱼中"), author_id=users["用户 A"].id)
        print(f"✓ A 发布第五个原创帖子 (ID={post5.id})")
        
        # B 评论并转发
        comment_b3, repost_b3 = crud.create_comment_with_repost(
            db=db,
            post_id=post5.id,
            author_id=users["用户 B"].id,
            content="B 评论：摸鱼快乐！",
            quote_from_id=post5.id
        )
        print(f"✓ B 评论并转发 (ID={repost_b3.id})")
        
        # C 回复 B 并转发
        reply_c2, repost_c2 = crud.create_reply_with_repost(
            db=db,
            comment_id=comment_b3.id,
            author_id=users["用户 C"].id,
            content="C 回复：一起摸鱼",
            quote_from_id=post5.id
        )
        print(f"✓ C 回复并转发 (ID={repost_c2.id})")
        
        # H 直接转发 C 的转发
        repost_h = crud.create_quote_post(db, quote_from_id=repost_c2.id, author_id=users["用户 H"].id, content="H 转发：+1")
        print(f"✓ H 直接转发 C (ID={repost_h.id})")
        
        # ==================== 测试用例 6: 深度转发链 ====================
        print("\n" + "=" * 60)
        print("测试用例 6: 深度转发链 A→B→C→D→E→H")
        print("=" * 60)
        
        # A 发布第六个原创帖子
        post6 = crud.create_post(db, schemas.PostCreate(content="原创内容 6: 深链测试"), author_id=users["用户 A"].id)
        print(f"✓ A 发布第六个原创帖子 (ID={post6.id})")
        
        # B 评论并转发
        comment_b4, repost_b4 = crud.create_comment_with_repost(
            db=db,
            post_id=post6.id,
            author_id=users["用户 B"].id,
            content="B: 第一层",
            quote_from_id=post6.id
        )
        print(f"✓ B 评论并转发 (ID={repost_b4.id})")
        
        # C 回复 B 并转发
        reply_c3, repost_c3 = crud.create_reply_with_repost(
            db=db,
            comment_id=comment_b4.id,
            author_id=users["用户 C"].id,
            content="C: 第二层",
            quote_from_id=post6.id
        )
        print(f"✓ C 回复并转发 (ID={repost_c3.id})")
        
        # D 回复 C 并转发
        reply_d2, repost_d2 = crud.create_reply_with_repost(
            db=db,
            comment_id=reply_c3.id,
            author_id=users["用户 D"].id,
            content="D: 第三层",
            quote_from_id=post6.id
        )
        print(f"✓ D 回复并转发 (ID={repost_d2.id})")
        
        # E 回复 D 并转发
        reply_e2, repost_e2 = crud.create_reply_with_repost(
            db=db,
            comment_id=reply_d2.id,
            author_id=users["用户 E"].id,
            content="E: 第四层",
            quote_from_id=post6.id
        )
        print(f"✓ E 回复并转发 (ID={repost_e2.id})")
        
        # H 回复 E 并转发
        reply_h2, repost_h2 = crud.create_reply_with_repost(
            db=db,
            comment_id=reply_e2.id,
            author_id=users["用户 H"].id,
            content="H: 第五层",
            quote_from_id=post6.id
        )
        print(f"✓ H 回复并转发 (ID={repost_h2.id})")
        
        # ==================== 统计和验证 ====================
        print("\n" + "=" * 60)
        print("数据统计与验证")
        print("=" * 60)
        
        total_posts = db.query(models.Post).count()
        original_count = db.query(models.Post).filter(models.Post.post_type == 'original').count()
        quote_count = db.query(models.Post).filter(models.Post.post_type == 'quote').count()
        
        print(f"\n帖子统计:")
        print(f"  - 总帖子数：{total_posts}")
        print(f"  - 原创帖子：{original_count}")
        print(f"  - 转发帖子：{quote_count}")
        
        # 验证每个原创帖子的转发数
        print(f"\n原创帖子转发统计:")
        for i in range(1, 7):
            post = db.query(models.Post).filter(models.Post.id == i).first()
            if post:
                direct_count = db.query(models.Post).filter(models.Post.quote_from_id == post.id).count()
                total_count = crud.count_all_reposts(db, post.id)
                print(f"  - 帖子{i} (ID={post.id}): 直接转发={direct_count}, 总转发={total_count}")
        
        # 验证小卡片指向
        print(f"\n小卡片指向验证:")
        quote_posts = db.query(models.Post).filter(models.Post.post_type == 'quote').all()
        for qp in quote_posts[:10]:  # 只显示前 10 个
            print(f"  - 帖子{qp.id} ({qp.author.username}): quote_from_id={qp.quote_from_id}, original_post_id={qp.original_post_id}")
        
        print("\n" + "=" * 60)
        print("✓ 所有测试用例注入完成！")
        print("=" * 60)
        print("\n现在可以刷新前端页面查看效果！")
        
    except Exception as e:
        print(f"\n❌ 注入失败：{e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    inject_test_data()

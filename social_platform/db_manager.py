"""
数据库管理脚本
用于快速清理、重置、查看社交平台数据库
"""
import sqlite3
from pathlib import Path
import os

# 数据库文件路径 - 使用相对路径，相对于当前工作目录
# 服务器启动时在 social_platform 目录，所以数据库在 ./social_platform.db
DB_PATH = Path("./social_platform.db")


def get_connection():
    """获取数据库连接"""
    return sqlite3.connect(DB_PATH)


def show_tables():
    """显示所有表"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("\n📊 数据库表列表:")
    print("="*60)
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"  {table_name:20} - {count} 条记录")
    
    conn.close()
    print("="*60)


def show_users():
    """显示所有用户"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, bio, created_at FROM users ORDER BY id;")
    users = cursor.fetchall()
    
    print("\n👥 用户列表:")
    print("="*60)
    print(f"{'ID':<6} {'用户名':<20} {'个人简介':<30}")
    print("="*60)
    for user in users:
        user_id, username, bio, created_at = user
        bio_display = (bio[:27] + "...") if bio and len(bio) > 30 else (bio or "")
        print(f"{user_id:<6} {username:<20} {bio_display:<30}")
    
    conn.close()
    print("="*60)
    print(f"总计：{len(users)} 个用户")


def delete_user(user_id: int = None, username: str = None):
    """
    删除指定用户
    
    Args:
        user_id: 用户 ID
        username: 用户名
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if user_id:
            cursor.execute("DELETE FROM likes WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM comments WHERE author_id = ?", (user_id,))
            cursor.execute("DELETE FROM posts WHERE author_id = ?", (user_id,))
            cursor.execute("DELETE FROM follows WHERE follower_id = ? OR following_id = ?", (user_id, user_id))
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            deleted = cursor.rowcount
            conn.commit()
            print(f"✅ 已删除用户 ID: {user_id} ({deleted} 条记录)")
        
        elif username:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if user:
                user_id = user[0]
                cursor.execute("DELETE FROM likes WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM comments WHERE author_id = ?", (user_id,))
                cursor.execute("DELETE FROM posts WHERE author_id = ?", (user_id,))
                cursor.execute("DELETE FROM follows WHERE follower_id = ? OR following_id = ?", (user_id, user_id))
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                deleted = cursor.rowcount
                conn.commit()
                print(f"✅ 已删除用户 {username} (ID: {user_id}, {deleted} 条记录)")
            else:
                print(f"❌ 用户不存在：{username}")
        else:
            print("❌ 请提供 user_id 或 username")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ 删除失败：{e}")
    finally:
        conn.close()


def delete_all_users():
    """删除所有用户数据（级联删除）"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 按外键依赖顺序删除
        cursor.execute("DELETE FROM likes;")
        likes_count = cursor.rowcount
        
        cursor.execute("DELETE FROM comments;")
        comments_count = cursor.rowcount
        
        cursor.execute("DELETE FROM posts;")
        posts_count = cursor.rowcount
        
        cursor.execute("DELETE FROM follows;")
        follows_count = cursor.rowcount
        
        cursor.execute("DELETE FROM users;")
        users_count = cursor.rowcount
        
        conn.commit()
        
        print("\n✅ 已清空所有用户数据:")
        print(f"  - 删除 {users_count} 个用户")
        print(f"  - 删除 {posts_count} 个帖子")
        print(f"  - 删除 {comments_count} 条评论")
        print(f"  - 删除 {likes_count} 个点赞")
        print(f"  - 删除 {follows_count} 个关注关系")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ 清空失败：{e}")
    finally:
        conn.close()


def reset_database():
    """完全重置数据库（删除数据库文件）"""
    import shutil
    
    if DB_PATH.exists():
        # 备份数据库
        backup_path = DB_PATH.with_suffix('.db.backup')
        shutil.copy(DB_PATH, backup_path)
        print(f"💾 已备份数据库到：{backup_path}")
        
        # 删除数据库
        DB_PATH.unlink()
        print(f"✅ 已删除数据库文件：{DB_PATH}")
        print("\n⚠️  重启社交平台后端后将自动创建新数据库")
    else:
        print("⚠️  数据库文件不存在")


def clean_ai_users():
    """
    清理 AI 用户（根据配置文件中存在的用户名）
    保留其他手动创建的用户
    """
    import json
    
    config_path = Path(__file__).parent.parent / "ai_users_config.json"
    
    if not config_path.exists():
        print("❌ 配置文件不存在")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    ai_usernames = {user['username'] for user in config.get('ai_users', [])}
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, username FROM users;")
        all_users = cursor.fetchall()
        
        deleted_count = 0
        for user_id, username in all_users:
            if username in ai_usernames:
                cursor.execute("DELETE FROM likes WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM comments WHERE author_id = ?", (user_id,))
                cursor.execute("DELETE FROM posts WHERE author_id = ?", (user_id,))
                cursor.execute("DELETE FROM follows WHERE follower_id = ? OR following_id = ?", (user_id, user_id))
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                deleted_count += 1
                print(f"  删除：{username} (ID: {user_id})")
        
        conn.commit()
        print(f"\n✅ 已清理 {deleted_count} 个 AI 用户")
    
    except Exception as e:
        conn.rollback()
        print(f"❌ 清理失败：{e}")
    finally:
        conn.close()


def print_help():
    """打印帮助信息"""
    print("""
📚 数据库管理工具 - 使用帮助

用法：python db_manager.py [命令] [参数]

命令:
  show-tables     显示所有表及记录数
  show-users      显示所有用户
  delete-user ID  删除指定 ID 的用户
  delete-name 名称  删除指定用户名的用户
  delete-all      删除所有用户数据（保留表结构）
  reset           完全重置数据库（删除数据库文件）
  clean-ai        仅清理 AI 用户（根据配置文件）
  help            显示此帮助信息

示例:
  python db_manager.py show-users
  python db_manager.py delete-user 5
  python db_manager.py delete-name 三月七
  python db_manager.py clean-ai
  python db_manager.py reset

⚠️  警告：删除操作不可逆，请谨慎使用！
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "show-tables":
        show_tables()
    elif command == "show-users":
        show_users()
    elif command == "delete-user" and len(sys.argv) >= 3:
        delete_user(user_id=int(sys.argv[2]))
    elif command == "delete-name" and len(sys.argv) >= 3:
        delete_user(username=sys.argv[2])
    elif command == "delete-all":
        confirm = input("⚠️  确定要删除所有用户数据吗？(yes/no): ")
        if confirm.lower() == 'yes':
            delete_all_users()
        else:
            print("❌ 操作已取消")
    elif command == "reset":
        confirm = input("⚠️  确定要完全重置数据库吗？(yes/no): ")
        if confirm.lower() == 'yes':
            reset_database()
        else:
            print("❌ 操作已取消")
    elif command == "clean-ai":
        clean_ai_users()
    elif command == "help":
        print_help()
    else:
        print(f"❌ 未知命令：{command}")
        print_help()
        sys.exit(1)

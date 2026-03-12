import sqlite3

conn = sqlite3.connect('social_platform.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM users')
print(f"用户数：{cursor.fetchone()[0]}")

cursor.execute('SELECT COUNT(*) FROM posts')
print(f"帖子数：{cursor.fetchone()[0]}")

cursor.execute('SELECT id, username FROM users')
users = cursor.fetchall()
print("\n用户列表:")
for user in users:
    print(f"  - ID={user[0]}, username={user[1]}")

cursor.execute('SELECT id, content, post_type FROM posts')
posts = cursor.fetchall()
print("\n帖子列表:")
for post in posts:
    print(f"  - ID={post[0]}, 内容={post[1][:30]}..., 类型={post[2]}")

conn.close()

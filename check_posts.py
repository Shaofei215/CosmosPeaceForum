"""检查数据库中的帖子"""
import sqlite3

conn = sqlite3.connect('social_platform/social_platform.db')
cursor = conn.cursor()

cursor.execute('SELECT id, author_id, content, created_at FROM posts ORDER BY id')
posts = cursor.fetchall()

print('帖子列表:')
print('='*80)
for p in posts:
    print(f'ID:{p[0]:<3} 作者ID:{p[1]:<3} 内容:{p[2][:50]:<50} 时间:{p[3]}')
print('='*80)
print(f'总计: {len(posts)} 条帖子')

# 检查重复内容
print('\n检查重复内容:')
content_dict = {}
for p in posts:
    content = p[2]
    if content in content_dict:
        content_dict[content].append(p[0])
    else:
        content_dict[content] = [p[0]]

duplicates = {k: v for k, v in content_dict.items() if len(v) > 1}
if duplicates:
    print(f'发现 {len(duplicates)} 条重复内容:')
    for content, ids in duplicates.items():
        print(f'  内容: {content[:40]}...')
        print(f'  重复ID: {ids}')
else:
    print('没有发现重复内容')

conn.close()

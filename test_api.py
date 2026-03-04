import requests

# 测试获取帖子
try:
    r = requests.get('http://127.0.0.1:8006/posts')
    print(f'状态码: {r.status_code}')
    if r.status_code == 200:
        posts = r.json()
        print(f'帖子数量: {len(posts)}')
        if posts:
            print(f'第一条帖子: {posts[0]["content"][:50]}...')
    else:
        print(f'错误: {r.text}')
except Exception as e:
    print(f'请求失败: {e}')

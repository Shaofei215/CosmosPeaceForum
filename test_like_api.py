import requests

BASE_URL = 'http://127.0.0.1:8006'

print("=" * 60)
print("测试点赞功能修复")
print("=" * 60)

# 1. 获取用户列表
print("\n1. 获取用户列表...")
response = requests.get(f'{BASE_URL}/users')
users = response.json()
print(f"   用户数量：{len(users)}")
if users:
    print(f"   第一个用户：{users[0]['username']} (ID: {users[0]['id']})")

# 2. 获取帖子列表
print("\n2. 获取帖子列表...")
response = requests.get(f'{BASE_URL}/posts')
posts = response.json()
print(f"   帖子数量：{len(posts)}")
if posts:
    print(f"   第一个帖子：{posts[0]['content'][:50]}... (ID: {posts[0]['id']})")

# 3. 测试帖子点赞（这个本来就正常）
if users and posts:
    user_id = users[0]['id']
    post_id = posts[0]['id']
    
    print(f"\n3. 测试帖子点赞 (用户{user_id} -> 帖子{post_id})...")
    response = requests.post(f'{BASE_URL}/posts/{post_id}/like', params={'user_id': user_id})
    print(f"   状态码：{response.status_code}")
    if response.status_code == 201:
        print(f"   ✅ 帖子点赞成功")
    elif response.status_code == 400:
        print(f"   ℹ️  已点过赞了（这是正常的）")
    else:
        print(f"   ❌ 失败：{response.text}")

# 4. 获取帖子评论
print("\n4. 获取帖子评论...")
if posts:
    post_id = posts[0]['id']
    response = requests.get(f'{BASE_URL}/posts/{post_id}/comments')
    comments = response.json()
    print(f"   评论数量：{len(comments)}")
    
    # 5. 测试评论点赞（这是修复的功能）
    if comments and users:
        comment_id = comments[0]['id']
        user_id = users[0]['id']
        
        print(f"\n5. 测试评论点赞 (用户{user_id} -> 评论{comment_id})...")
        response = requests.post(f'{BASE_URL}/comments/{comment_id}/like', params={'user_id': user_id})
        print(f"   状态码：{response.status_code}")
        if response.status_code == 201:
            print(f"   ✅ 评论点赞成功！修复有效！")
        elif response.status_code == 400:
            print(f"   ℹ️  已点过赞了（这是正常的）")
        else:
            print(f"   ❌ 失败：{response.text}")
    
    # 6. 测试回复点赞（这也是修复的功能）
    print("\n6. 获取评论回复...")
    if comments:
        comment_id = comments[0]['id']
        response = requests.get(f'{BASE_URL}/comments/{comment_id}/replies')
        replies = response.json()
        print(f"   回复数量：{len(replies)}")
        
        if replies and users:
            reply_id = replies[0]['id']
            user_id = users[0]['id']
            
            print(f"\n7. 测试回复点赞 (用户{user_id} -> 回复{reply_id})...")
            response = requests.post(f'{BASE_URL}/replies/{reply_id}/like', params={'user_id': user_id})
            print(f"   状态码：{response.status_code}")
            if response.status_code == 201:
                print(f"   ✅ 回复点赞成功！修复有效！")
            elif response.status_code == 400:
                print(f"   ℹ️  已点过赞了（这是正常的）")
            else:
                print(f"   ❌ 失败：{response.text}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)

import requests

BASE_URL = 'http://127.0.0.1:8006'

print("=" * 60)
print("测试点赞功能修复 - 完整版")
print("=" * 60)

# 获取用户和帖子
print("\n1. 获取基础数据...")
users_response = requests.get(f'{BASE_URL}/users')
users = users_response.json()

posts_response = requests.get(f'{BASE_URL}/posts')
posts = posts_response.json()

print(f"   用户数量：{len(users)}")
print(f"   帖子数量：{len(posts)}")

if not users or not posts:
    print("❌ 缺少用户或帖子数据，无法继续测试")
    exit(1)

user_id = users[0]['id']
post_id = posts[0]['id']
print(f"   使用用户：{users[0]['username']} (ID: {user_id})")
print(f"   使用帖子：{post_id}")

# 2. 创建评论
print(f"\n2. 创建测试评论...")
comment_data = {"content": "测试评论 - 验证点赞功能修复"}
response = requests.post(
    f'{BASE_URL}/posts/{post_id}/comments',
    json=comment_data,
    params={'author_id': user_id}
)
if response.status_code in [200, 201]:
    comment = response.json()
    comment_id = comment['id']
    print(f"   ✅ 评论创建成功 (ID: {comment_id})")
else:
    print(f"   ❌ 评论创建失败：{response.text}")
    exit(1)

# 3. 创建回复
print(f"\n3. 创建测试回复...")
reply_data = {"content": "测试回复 - 验证点赞功能修复"}
response = requests.post(
    f'{BASE_URL}/comments/{comment_id}/replies',
    json=reply_data,
    params={'author_id': user_id}
)
if response.status_code in [200, 201]:
    reply = response.json()
    reply_id = reply['id']
    print(f"   ✅ 回复创建成功 (ID: {reply_id})")
else:
    print(f"   ❌ 回复创建失败：{response.text}")
    exit(1)

# 4. 测试帖子点赞
print(f"\n4. 测试帖子点赞 (用户{user_id} -> 帖子{post_id})...")
response = requests.post(f'{BASE_URL}/posts/{post_id}/like', params={'user_id': user_id})
print(f"   状态码：{response.status_code}")
if response.status_code == 201:
    print(f"   ✅ 帖子点赞成功")
elif response.status_code == 400:
    print(f"   ℹ️  已点过赞了（这是正常的）")
else:
    print(f"   ❌ 失败：{response.text}")

# 5. 测试评论点赞（修复的功能）
print(f"\n5. 测试评论点赞 (用户{user_id} -> 评论{comment_id})...")
response = requests.post(f'{BASE_URL}/comments/{comment_id}/like', params={'user_id': user_id})
print(f"   状态码：{response.status_code}")
if response.status_code == 201:
    print(f"   ✅ 评论点赞成功！修复有效！")
elif response.status_code == 400:
    print(f"   ℹ️  已点过赞了（这是正常的）")
else:
    print(f"   ❌ 失败：{response.text}")
    print(f"   ⚠️  这可能是修复未生效的迹象")

# 6. 测试回复点赞（修复的功能）
print(f"\n6. 测试回复点赞 (用户{user_id} -> 回复{reply_id})...")
response = requests.post(f'{BASE_URL}/replies/{reply_id}/like', params={'user_id': user_id})
print(f"   状态码：{response.status_code}")
if response.status_code == 201:
    print(f"   ✅ 回复点赞成功！修复有效！")
elif response.status_code == 400:
    print(f"   ℹ️  已点过赞了（这是正常的）")
else:
    print(f"   ❌ 失败：{response.text}")
    print(f"   ⚠️  这可能是修复未生效的迹象")

# 7. 测试重复点赞（应该返回 400）
print(f"\n7. 测试评论重复点赞（应该返回 400）...")
response = requests.post(f'{BASE_URL}/comments/{comment_id}/like', params={'user_id': user_id})
print(f"   状态码：{response.status_code}")
if response.status_code == 400:
    print(f"   ✅ 正确阻止了重复点赞")
    print(f"   返回消息：{response.json().get('detail', 'unknown')}")
else:
    print(f"   ❌ 未能阻止重复点赞")

print("\n" + "=" * 60)
print("测试完成！所有修复的功能都应该正常工作")
print("=" * 60)

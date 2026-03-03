"""测试API是否返回重复帖子"""
import requests

def test_mixed_posts():
    url = "http://127.0.0.1:8006/posts/mixed"
    params = {"limit": 11, "hot_ratio": 0.7}

    response = requests.get(url, params=params)
    if response.status_code == 200:
        posts = response.json()
        print(f"获取到 {len(posts)} 条帖子")
        print("="*80)

        # 检查重复ID
        ids = [p['id'] for p in posts]
        unique_ids = set(ids)

        if len(ids) != len(unique_ids):
            print(f"❌ 发现重复! 总数: {len(ids)}, 唯一ID数: {len(unique_ids)}")
            from collections import Counter
            counts = Counter(ids)
            duplicates = {k: v for k, v in counts.items() if v > 1}
            print(f"重复的ID: {duplicates}")
        else:
            print(f"✅ 没有重复! 所有 {len(ids)} 条帖子ID都是唯一的")

        print("\n帖子列表:")
        for i, post in enumerate(posts, 1):
            print(f"[{i:2}] ID:{post['id']:<3} [热度]{post.get('hot_score', 0):3d} {post['author']['username']}: {post['content'][:40]}...")
    else:
        print(f"请求失败: {response.status_code}")

if __name__ == "__main__":
    test_mixed_posts()

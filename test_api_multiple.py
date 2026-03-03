"""多次测试API是否返回重复帖子"""
import requests
from collections import Counter

def test_mixed_posts_multiple_times(times=10):
    url = "http://127.0.0.1:8006/posts/mixed"
    params = {"limit": 11, "hot_ratio": 0.7}

    all_passed = True

    for i in range(times):
        response = requests.get(url, params=params)
        if response.status_code == 200:
            posts = response.json()
            ids = [p['id'] for p in posts]
            unique_ids = set(ids)

            if len(ids) != len(unique_ids):
                print(f"❌ 第 {i+1} 次测试: 发现重复! 总数: {len(ids)}, 唯一ID数: {len(unique_ids)}")
                counts = Counter(ids)
                duplicates = {k: v for k, v in counts.items() if v > 1}
                print(f"   重复的ID: {duplicates}")
                all_passed = False
            else:
                print(f"✅ 第 {i+1} 次测试: 通过，{len(ids)} 条帖子无重复")
        else:
            print(f"❌ 第 {i+1} 次测试: 请求失败 {response.status_code}")
            all_passed = False

    print("\n" + "="*80)
    if all_passed:
        print(f"🎉 所有 {times} 次测试都通过！API 返回的帖子无重复。")
    else:
        print(f"⚠️  部分测试失败，请检查代码。")

if __name__ == "__main__":
    test_mixed_posts_multiple_times(10)

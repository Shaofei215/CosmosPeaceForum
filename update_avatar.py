"""
更新 ai_users_config.json 中的 avatar 字段
将 emoji 替换为对应的图片文件名
"""
import json
from pathlib import Path

# 头像文件名映射（将用户名映射到对应的头像文件）
AVATAR_MAPPING = {
    "三月七": "三月七.jpg",
    "星穹列车官方": "星穹列车官方.jpg",
    "黑塔空间站官方": "黑塔空间站官方.jpg",
}

# 默认头像
DEFAULT_AVATAR = "Avatar.png"

def update_avatar_in_config():
    """更新配置文件中的 avatar 字段"""
    config_path = Path("ai_users_config.json")
    
    if not config_path.exists():
        print(f"[错误] 配置文件不存在: {config_path}")
        return
    
    # 读取配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    ai_users = config.get("ai_users", [])
    
    # 更新每个用户的 avatar
    updated_count = 0
    for user in ai_users:
        username = user.get("username", "")
        old_avatar = user.get("avatar", "")
        
        # 获取新的头像文件名
        new_avatar = AVATAR_MAPPING.get(username, DEFAULT_AVATAR)
        
        # 更新 avatar 字段
        user["avatar"] = new_avatar
        updated_count += 1
        
        if username in AVATAR_MAPPING:
            print(f"[已更新] {username}: {old_avatar} -> {new_avatar}")
        else:
            print(f"[默认] {username}: {old_avatar} -> {new_avatar} (使用默认头像)")
    
    # 保存更新后的配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n[完成] 成功更新 {updated_count} 个用户的头像配置")

if __name__ == "__main__":
    update_avatar_in_config()

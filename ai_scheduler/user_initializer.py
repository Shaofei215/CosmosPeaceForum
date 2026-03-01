"""
AI 用户初始化模块
负责在社交平台后端创建 AI 用户
"""
from typing import Dict, Any, List, Tuple
from .api_client import SocialPlatformClient


class AIUserInitializer:
    """
    AI 用户初始化器
    自动在社交平台后端创建 AI 用户
    """
    
    def __init__(self, client: SocialPlatformClient):
        """
        初始化用户初始化器
        
        Args:
            client: 社交平台 API 客户端
        """
        self.client = client
    
    def initialize_users(self, ai_users: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        批量初始化 AI 用户
        
        Args:
            ai_users: AI 用户配置列表
            
        Returns:
            (成功创建的用户列表，失败的用户列表)
        """
        success_users = []
        failed_users = []
        
        print("\n" + "="*60)
        print("📝 在社交平台创建 AI 用户")
        print("="*60 + "\n")
        
        for user_config in ai_users:
            result = self.create_ai_user(user_config)
            
            if result:
                success_users.append(result)
            else:
                failed_users.append(user_config)
        
        print(f"\n✅ 成功创建：{len(success_users)} 个用户")
        if failed_users:
            print(f"⚠️  跳过/失败：{len(failed_users)} 个用户（可能已存在）")
        
        return success_users, failed_users
    
    def create_ai_user(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建单个 AI 用户
        
        Args:
            user_config: AI 用户配置
            
        Returns:
            创建的用户信息，失败则返回 None
        """
        username = user_config["username"]
        # 使用个人签名作为 bio
        bio = user_config.get("personal_signature", "")
        
        print(f"   创建用户：{username} (ID: {user_config['id']})")
        
        # 尝试创建用户
        created_user = self.client.create_user(username=username, bio=bio)
        
        if created_user:
            print(f"   ✅ 创建成功 - 平台 ID: {created_user['id']}")
            # 将原始配置与平台返回的信息合并
            return {
                **user_config,
                "platform_user_id": created_user["id"]
            }
        else:
            # 用户可能已存在，尝试获取现有用户
            existing_user = self._find_existing_user(username)
            
            if existing_user:
                print(f"   ⚠️  用户已存在 - 平台 ID: {existing_user['id']}")
                return {
                    **user_config,
                    "platform_user_id": existing_user["id"]
                }
            else:
                print(f"   ❌ 创建失败")
                return None
    
    def _find_existing_user(self, username: str) -> Dict[str, Any]:
        """
        查找已存在的用户
        
        Args:
            username: 用户名
            
        Returns:
            用户信息，不存在则返回 None
        """
        all_users = self.client.get_all_users()
        
        for user in all_users:
            if user["username"] == username:
                return user
        
        return None
    
    def setup_follow_relationships(self, ai_users: List[Dict[str, Any]]) -> int:
        """
        设置 AI 用户之间的关注关系
        
        Args:
            ai_users: 已初始化的 AI 用户列表（包含 platform_user_id）
            
        Returns:
            成功创建的关注关系数量
        """
        print("\n" + "="*60)
        print("🔗 设置 AI 用户关注关系")
        print("="*60 + "\n")
        
        success_count = 0
        
        # 创建用户 ID 映射
        user_id_map = {
            user["id"]: user["platform_user_id"] 
            for user in ai_users
        }
        
        for user in ai_users:
            follower_id = user["platform_user_id"]
            following_ids = user.get("following", [])
            
            for following_original_id in following_ids:
                # 检查被关注的用户是否也在 AI 用户列表中
                if following_original_id in user_id_map:
                    following_id = user_id_map[following_original_id]
                    
                    # 跳过自己关注自己
                    if follower_id == following_id:
                        continue
                    
                    result = self.client.follow_user(
                        follower_id=follower_id,
                        following_id=following_id
                    )
                    
                    if result:
                        success_count += 1
        
        print(f"✅ 成功创建 {success_count} 个关注关系")
        return success_count

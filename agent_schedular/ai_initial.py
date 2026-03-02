"""
AI 用户配置加载及初始化模块
从配置文件中加载 AI 用户信息，并在社交平台中创建用户
"""
import json
import requests
from typing import Dict, List, Any, Optional
from pathlib import Path


class AIUserInitializer:
    """AI 用户初始化器"""
    
    def __init__(self, config_path: str = "ai_users_config.json", 
                 api_base_url: str = "http://127.0.0.1:8000"):
        """
        初始化 AI 用户初始化器
        
        Args:
            config_path: 配置文件路径
            api_base_url: 社交平台 API 基础 URL
        """
        self.config_path = Path(config_path)
        self.api_base_url = api_base_url
        self.users_config = []
        self.initialized_users = []
        
        print("[AI 初始化] 初始化器已创建")
        print(f"[AI 初始化] 配置文件：{self.config_path}")
        print(f"[AI 初始化] API 地址：{self.api_base_url}")
    
    def load_config(self) -> bool:
        """
        加载 AI 用户配置文件
        
        Returns:
            bool: 加载是否成功
        """
        try:
            if not self.config_path.exists():
                print(f"[AI 初始化] ❌ 配置文件不存在：{self.config_path}")
                return False
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            self.users_config = config_data.get("ai_users", [])
            
            if not self.users_config:
                print("[AI 初始化] ⚠️ 配置文件中没有 AI 用户配置")
                return False
            
            print(f"[AI 初始化] ✅ 成功加载 {len(self.users_config)} 个 AI 用户配置")
            return True
            
        except json.JSONDecodeError as e:
            print(f"[AI 初始化] ❌ JSON 解析错误：{e}")
            return False
        except Exception as e:
            print(f"[AI 初始化] ❌ 加载配置失败：{e}")
            return False
    
    def create_ai_user(self, user_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        在社交平台中创建单个 AI 用户
        
        Args:
            user_config: 用户配置字典
            
        Returns:
            Optional[Dict]: 创建成功返回用户信息，失败返回 None
        """
        username = user_config.get("username")
        personal_signature = user_config.get("personal_signature", "")
        
        if not username:
            print(f"[AI 初始化] ❌ 用户配置缺少用户名")
            return None
        
        print(f"[AI 初始化] 正在创建用户：{username}")
        
        try:
            # 构造 API 请求
            url = f"{self.api_base_url}/users"
            payload = {
                "username": username,
                "bio": personal_signature
            }
            
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 201:
                # 创建成功
                created_user = response.json()
                print(f"[AI 初始化] ✅ {username} 创建成功 - 平台 ID: {created_user['id']}")
                return {**user_config, "platform_user_id": created_user["id"]}
                
            elif response.status_code == 400:
                # 用户已存在，尝试获取现有用户
                existing_user = self._find_existing_user(username)
                if existing_user:
                    print(f"[AI 初始化] ⚠️ {username} 已存在 - 平台 ID: {existing_user['id']}")
                    return {**user_config, "platform_user_id": existing_user["id"]}
                else:
                    print(f"[AI 初始化] ❌ {username} 创建失败，无法获取现有用户信息")
                    return None
            else:
                print(f"[AI 初始化] ❌ {username} 创建失败 - HTTP {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            print(f"[AI 初始化] ❌ 无法连接到社交平台 API，请确保后端已启动")
            return None
        except Exception as e:
            print(f"[AI 初始化] ❌ {username} 创建过程出错：{e}")
            return None
    
    def _find_existing_user(self, username: str) -> Optional[Dict[str, Any]]:
        """
        查找已存在的用户
        
        Args:
            username: 用户名
            
        Returns:
            Optional[Dict]: 用户信息或 None
        """
        try:
            url = f"{self.api_base_url}/users"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                users = response.json()
                for user in users:
                    if user.get("username") == username:
                        return user
        except Exception as e:
            print(f"[AI 初始化] 查找用户 {username} 失败：{e}")
        
        return None
    
    def initialize_all_users(self) -> List[Dict[str, Any]]:
        """
        初始化所有 AI 用户
        
        Returns:
            List[Dict]: 成功初始化的用户列表
        """
        print("\n[AI 初始化] 开始初始化所有 AI 用户...")
        print("=" * 60)
        
        self.initialized_users = []
        
        for user_config in self.users_config:
            result = self.create_ai_user(user_config)
            if result:
                self.initialized_users.append(result)
        
        print("=" * 60)
        print(f"[AI 初始化] 初始化完成：成功 {len(self.initialized_users)}/{len(self.users_config)}")
        
        return self.initialized_users
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        根据配置中的 ID 获取用户信息
        
        Args:
            user_id: 配置中的用户 ID
            
        Returns:
            Optional[Dict]: 用户信息或 None
        """
        for user in self.initialized_users:
            if user.get("id") == user_id:
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        根据用户名获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            Optional[Dict]: 用户信息或 None
        """
        for user in self.initialized_users:
            if user.get("username") == username:
                return user
        return None
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        获取所有已初始化的用户
        
        Returns:
            List[Dict]: 用户列表
        """
        return self.initialized_users
    
    def print_user_summary(self):
        """打印用户摘要信息"""
        print("\n[AI 初始化] 用户摘要:")
        print(f"{'ID':<6} {'用户名':<15} {'平台 ID':<10} {'签名':<30}")
        print("-" * 60)
        
        for user in self.initialized_users:
            user_id = user.get("id", "N/A")
            username = user.get("username", "N/A")
            platform_id = user.get("platform_user_id", "N/A")
            signature = user.get("personal_signature", "")[:28]
            
            print(f"{user_id:<6} {username:<15} {platform_id:<10} {signature:<30}")
    
    def initialize_initial_posts(self, posts_config_path: str = "initial_posts.json") -> int:
        """
        初始化预设帖子
        在平台冷启动时创建一些初始帖子，避免时间线为空
        
        Args:
            posts_config_path: 初始帖子配置文件路径
            
        Returns:
            int: 成功创建的帖子数量
        """
        print("\n[AI 初始化] 检查是否需要创建初始帖子...")
        
        # 先检查是否已有帖子
        try:
            url = f"{self.api_base_url}/posts"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                existing_posts = response.json()
                if existing_posts:
                    print(f"[AI 初始化] 平台已有 {len(existing_posts)} 条帖子，跳过初始帖子创建")
                    return 0
        except Exception as e:
            print(f"[AI 初始化] 检查现有帖子失败: {e}")
            return 0
        
        # 加载初始帖子配置
        posts_path = Path(posts_config_path)
        if not posts_path.exists():
            print(f"[AI 初始化] ⚠️ 初始帖子配置文件不存在：{posts_path}")
            return 0
        
        try:
            with open(posts_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            initial_posts = config_data.get("initial_posts", [])
            
            if not initial_posts:
                print("[AI 初始化] ⚠️ 配置文件中没有初始帖子")
                return 0
            
            print(f"\n[AI 初始化] 开始创建 {len(initial_posts)} 条初始帖子...")
            print("=" * 60)
            
            created_count = 0
            
            for post_data in initial_posts:
                username = post_data.get("username")
                content = post_data.get("content")
                
                if not username or not content:
                    continue
                
                # 查找用户
                user = self.get_user_by_username(username)
                if not user:
                    print(f"[AI 初始化] ⚠️ 找不到用户 {username}，跳过此帖子")
                    continue
                
                platform_user_id = user.get("platform_user_id")
                if not platform_user_id:
                    continue
                
                # 创建帖子
                try:
                    url = f"{self.api_base_url}/posts"
                    payload = {"content": content}
                    params = {"author_id": platform_user_id}
                    
                    response = requests.post(url, json=payload, params=params, timeout=5)
                    
                    if response.status_code == 201:
                        created_post = response.json()
                        print(f"[AI 初始化] ✅ {username}: {content[:40]}...")
                        created_count += 1
                    else:
                        print(f"[AI 初始化] ❌ {username} 发帖失败: HTTP {response.status_code}")
                        
                except Exception as e:
                    print(f"[AI 初始化] ❌ {username} 发帖出错: {e}")
            
            print("=" * 60)
            print(f"[AI 初始化] 初始帖子创建完成：成功 {created_count}/{len(initial_posts)}")
            
            return created_count
            
        except json.JSONDecodeError as e:
            print(f"[AI 初始化] ❌ 初始帖子 JSON 解析错误：{e}")
            return 0
        except Exception as e:
            print(f"[AI 初始化] ❌ 创建初始帖子失败：{e}")
            return 0


if __name__ == "__main__":
    # 测试代码
    print("=== AI 用户初始化器测试 ===\n")
    
    initializer = AIUserInitializer()
    
    if initializer.load_config():
        initializer.initialize_all_users()
        initializer.print_user_summary()
    else:
        print("加载配置失败")

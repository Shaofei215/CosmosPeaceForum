"""
社交平台 API 客户端
用于与社交平台后端进行交互
"""
import requests
from typing import Dict, Any, Optional, List


class SocialPlatformClient:
    """
    社交平台 API 客户端
    封装所有与社交平台的交互操作
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """
        初始化 API 客户端
        
        Args:
            base_url: 社交平台后端地址
        """
        self.base_url = base_url
        self.session = requests.Session()
    
    def check_health(self) -> bool:
        """
        检查社交平台后端是否可用
        
        Returns:
            是否可用
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def create_user(self, username: str, bio: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        创建用户
        
        Args:
            username: 用户名
            bio: 个人简介
            
        Returns:
            创建的用户信息，失败则返回 None
        """
        try:
            data = {"username": username}
            if bio:
                data["bio"] = bio
            
            response = self.session.post(f"{self.base_url}/users", json=data, timeout=10)
            
            if response.status_code == 201:
                return response.json()
            elif response.status_code == 400:
                # 用户已存在
                return None
            else:
                print(f"❌ 创建用户失败：{response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络错误：{e}")
            return None
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取用户信息
        
        Args:
            user_id: 用户 ID
            
        Returns:
            用户信息，不存在则返回 None
        """
        try:
            response = self.session.get(f"{self.base_url}/users/{user_id}", timeout=5)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                print(f"❌ 获取用户失败：{response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络错误：{e}")
            return None
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        获取所有用户列表
        
        Returns:
            用户列表
        """
        try:
            response = self.session.get(f"{self.base_url}/users", timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ 获取用户列表失败：{response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络错误：{e}")
            return []
    
    def create_post(self, author_id: int, content: str) -> Optional[Dict[str, Any]]:
        """
        创建帖子
        
        Args:
            author_id: 作者 ID
            content: 帖子内容
            
        Returns:
            创建的帖子信息，失败则返回 None
        """
        try:
            data = {"content": content}
            params = {"author_id": author_id}
            
            response = self.session.post(
                f"{self.base_url}/posts", 
                json=data, 
                params=params, 
                timeout=10
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"❌ 创建帖子失败：{response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络错误：{e}")
            return None
    
    def like_post(self, user_id: int, post_id: int) -> Optional[Dict[str, Any]]:
        """
        点赞帖子
        
        Args:
            user_id: 用户 ID
            post_id: 帖子 ID
            
        Returns:
            点赞信息，失败则返回 None
        """
        try:
            params = {"user_id": user_id}
            
            response = self.session.post(
                f"{self.base_url}/posts/{post_id}/like",
                params=params,
                timeout=10
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"❌ 点赞失败：{response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络错误：{e}")
            return None
    
    def follow_user(self, follower_id: int, following_id: int) -> Optional[Dict[str, Any]]:
        """
        关注用户
        
        Args:
            follower_id: 关注者 ID
            following_id: 被关注者 ID
            
        Returns:
            关注信息，失败则返回 None
        """
        try:
            params = {"follower_id": follower_id}
            
            response = self.session.post(
                f"{self.base_url}/users/{following_id}/follow",
                params=params,
                timeout=10
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"❌ 关注失败：{response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络错误：{e}")
            return None

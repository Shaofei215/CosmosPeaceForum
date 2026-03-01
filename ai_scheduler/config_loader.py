"""
配置加载模块
从 ai_users_config.json 加载 AI 用户配置
"""
import json
from pathlib import Path
from typing import Dict, Any, List


class ConfigLoader:
    """
    配置加载器
    负责从 JSON 文件加载 AI 用户配置
    """
    
    def __init__(self, config_path: str = "ai_users_config.json"):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
    
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: JSON 格式错误
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在：{self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config_data = json.load(f)
        
        print(f"✅ 加载配置文件：{self.config_path}")
        print(f"   AI 用户数量：{len(self.config_data.get('ai_users', []))}")
        
        return self.config_data
    
    def get_ai_users(self) -> List[Dict[str, Any]]:
        """
        获取 AI 用户列表
        
        Returns:
            AI 用户配置列表
        """
        if not self.config_data:
            self.load_config()
        
        return self.config_data.get("ai_users", [])
    
    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """
        根据 ID 获取用户配置
        
        Args:
            user_id: 用户 ID
            
        Returns:
            用户配置字典，不存在则返回 None
        """
        if not self.config_data:
            self.load_config()
        
        for user in self.config_data.get("ai_users", []):
            if user["id"] == user_id:
                return user
        
        return None
    
    def validate_user_config(self, user_config: Dict[str, Any]) -> bool:
        """
        验证用户配置是否有效
        
        Args:
            user_config: 用户配置字典
            
        Returns:
            是否有效
        """
        required_fields = ["id", "username", "monthly_logins"]
        
        for field in required_fields:
            if field not in user_config:
                print(f"❌ 用户配置缺少必要字段：{field}")
                return False
        
        # 验证月度登录次数
        if not isinstance(user_config["monthly_logins"], int) or user_config["monthly_logins"] <= 0:
            print(f"❌ 用户 {user_config['username']} 的 monthly_logins 必须为正整数")
            return False
        
        return True
    
    def get_all_valid_users(self) -> List[Dict[str, Any]]:
        """
        获取所有有效的用户配置
        
        Returns:
            有效的用户配置列表
        """
        users = self.get_ai_users()
        valid_users = []
        
        for user in users:
            if self.validate_user_config(user):
                valid_users.append(user)
        
        return valid_users

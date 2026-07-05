# 角色关系映射模块
# 从数据库读取 Agent 配置，构建关系映射表
import re
from typing import Dict, List, Set, Optional

from agents.management.backend.db_client import get_db_client


MENTION_PATTERN = re.compile(r'@([^\s@]+)')


class RelationMap:
    """
    单个角色的关系映射

    Attributes:
        user_id: 当前角色的用户 ID
        knows_ids: 该角色认识的用户 ID 集合
    """

    def __init__(self, user_id: int, knows_ids: List[int]):
        self.user_id = user_id
        self.knows_ids: Set[int] = set(knows_ids)

    def knows(self, other_user_id: int) -> bool:
        """判断该角色是否认识指定用户"""
        return other_user_id in self.knows_ids

    def add_knows(self, user_id: int) -> None:
        """添加认识的用户"""
        self.knows_ids.add(user_id)

    def remove_knows(self, user_id: int) -> None:
        """移除认识的用户"""
        self.knows_ids.discard(user_id)

    def __repr__(self) -> str:
        return f"RelationMap(user_id={self.user_id}, knows_count={len(self.knows_ids)})"


class UsernameMap:
    """
    用户名映射表

    Attributes:
        _user_id_to_username: user_id -> username
        _username_to_user_id: username -> user_id
        _username_to_name: username -> name
        _name_to_username: name -> username
    """

    def __init__(self):
        self._user_id_to_username: Dict[int, str] = {}
        self._username_to_user_id: Dict[str, int] = {}
        self._username_to_name: Dict[str, str] = {}
        self._name_to_username: Dict[str, str] = {}

    def add(self, user_id: int, username: str, name: str) -> None:
        """添加用户名映射"""
        self._user_id_to_username[user_id] = username
        self._username_to_user_id[username] = user_id
        self._username_to_name[username] = name
        self._name_to_username[name] = username

    def get_name(self, username: str) -> Optional[str]:
        """根据用户名获取角色名"""
        return self._username_to_name.get(username)

    def get_username(self, name: str) -> Optional[str]:
        """根据角色名获取用户名"""
        return self._name_to_username.get(name)

    def get_username_by_user_id(self, user_id: int) -> Optional[str]:
        """根据用户 ID 获取用户名"""
        return self._user_id_to_username.get(user_id)

    def get_user_id_by_username(self, username: str) -> Optional[int]:
        """根据用户名获取用户 ID"""
        return self._username_to_user_id.get(username)

    def get_display_name(self, username: str, user_id: int, relation_map: RelationMap) -> str:
        """获取适合当前 Agent 视角的显示名称"""
        if relation_map.knows(user_id):
            name = self.get_name(username)
            if name:
                return f"{username}（{name}）"
        return username


class RelationMappingService:
    """
    关系映射服务

    统一管理所有角色的关系映射和用户名映射。
    采用单例模式，确保全局唯一实例。
    """

    _instance: Optional['RelationMappingService'] = None

    def __new__(cls) -> 'RelationMappingService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._relation_maps: Dict[int, RelationMap] = {}
        self._username_map = UsernameMap()
        self._initialized = True

    def build_from_db(self) -> None:
        """从数据库读取 Agent 配置构建关系映射表"""
        self._relation_maps.clear()
        self._username_map = UsernameMap()

        agent_configs = get_db_client().get_agent_configs()
        agent_id_to_user_id = {
            agent['id']: agent['social_platform_user_id']
            for agent in agent_configs
            if agent.get('id') is not None and agent.get('social_platform_user_id') is not None
        }

        for agent in agent_configs:
            user_id = agent.get('social_platform_user_id')
            username = agent.get('username', '')
            name = agent.get('name', '')
            knows_ids = [
                agent_id_to_user_id[agent_id]
                for agent_id in agent.get('knows_ids', [])
                if agent_id in agent_id_to_user_id
            ]

            if user_id is None:
                continue

            self._relation_maps[user_id] = RelationMap(user_id, knows_ids)
            if username and name:
                self._username_map.add(user_id, username, name)

    def get_relation_map(self, user_id: int) -> Optional[RelationMap]:
        """获取指定用户的关系映射"""
        return self._relation_maps.get(user_id)

    def get_username_map(self) -> UsernameMap:
        """获取用户名映射表"""
        return self._username_map

    def expand_author(
        self,
        author_username: str,
        author_id: int,
        owner_id: int
    ) -> str:
        """拓展作者显示名称"""
        relation_map = self.get_relation_map(owner_id)
        if relation_map is None:
            return author_username

        return self._username_map.get_display_name(author_username, author_id, relation_map)

    def expand_content_mentions(self, content: str, owner_id: int) -> str:
        """拓展内容中的 @mention"""
        relation_map = self.get_relation_map(owner_id)
        if relation_map is None:
            return content

        knows_ids = relation_map.knows_ids
        username_map = self._username_map

        def replace_mention(match):
            username = match.group(1)
            user_id = username_map.get_user_id_by_username(username)
            if user_id is not None and user_id in knows_ids:
                display_name = username_map.get_display_name(username, user_id, relation_map)
                return f"@{display_name}"
            return match.group(0)

        return MENTION_PATTERN.sub(replace_mention, content)

    def get_all_known_users(self, owner_id: int) -> List[int]:
        """获取当前用户认识的所有用户 ID"""
        relation_map = self.get_relation_map(owner_id)
        if relation_map is None:
            return []
        return list(relation_map.knows_ids)

    def __repr__(self) -> str:
        return f"RelationMappingService(loaded_users={len(self._relation_maps)})"


def get_relation_mapping_service() -> RelationMappingService:
    """获取关系映射服务单例"""
    return RelationMappingService()


def build_relation_maps_from_db() -> RelationMappingService:
    """
    从数据库构建关系映射服务

    Returns:
        RelationMappingService: 配置好的服务实例
    """
    service = get_relation_mapping_service()
    service.build_from_db()
    return service


def rebuild_relation_maps():
    """重建关系映射"""
    service = get_relation_mapping_service()
    service.build_from_db()
    return service

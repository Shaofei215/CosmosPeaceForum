# 角色关系映射模块
# 提供 AI Agent 对其他角色的认知关系映射功能
import re
from typing import Dict, List, Set, Optional


MENTION_PATTERN = re.compile(r'@([^\s@]+)')


class RelationMap:
    """
    单个角色的关系映射

    记录该角色认识哪些其他 AI 用户，用于在数据标准化时
    将作者用户名拓展为"用户名（真名）"格式。

    Attributes:
        user_id: 当前角色的用户 ID
        knows_ids: 该角色认识的用户 ID 集合
    """

    def __init__(self, user_id: int, knows_ids: List[int]):
        self.user_id = user_id
        self.knows_ids: Set[int] = set(knows_ids)

    def knows(self, other_user_id: int) -> bool:
        """
        判断该角色是否认识指定用户

        Args:
            other_user_id: 目标用户 ID

        Returns:
            bool: 是否认识
        """
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

    提供用户 ID、用户名、角色名之间的相互查找。

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
        """
        添加用户名映射

        Args:
            user_id: 用户 ID
            username: 用户名（网名）
            name: 角色真名
        """
        self._user_id_to_username[user_id] = username
        self._username_to_user_id[username] = user_id
        self._username_to_name[username] = name
        self._name_to_username[name] = username

    def get_name(self, username: str) -> Optional[str]:
        """
        根据用户名获取角色名

        Args:
            username: 用户名

        Returns:
            Optional[str]: 角色名，不存在返回 None
        """
        return self._username_to_name.get(username)

    def get_username(self, name: str) -> Optional[str]:
        """
        根据角色名获取用户名

        Args:
            name: 角色名

        Returns:
            Optional[str]: 用户名，不存在返回 None
        """
        return self._name_to_username.get(name)

    def get_username_by_user_id(self, user_id: int) -> Optional[str]:
        """
        根据用户 ID 获取用户名

        Args:
            user_id: 用户 ID

        Returns:
            Optional[str]: 用户名，不存在返回 None
        """
        return self._user_id_to_username.get(user_id)

    def get_user_id_by_username(self, username: str) -> Optional[int]:
        """
        根据用户名获取用户 ID

        Args:
            username: 用户名

        Returns:
            Optional[int]: 用户 ID，不存在返回 None
        """
        return self._username_to_user_id.get(username)

    def get_display_name(self, username: str, user_id: int, relation_map: RelationMap) -> str:
        """
        获取适合当前 Agent 视角的显示名称

        根据关系映射决定是否显示角色真名。

        Args:
            username: 用户名
            user_id: 用户 ID
            relation_map: 当前 Agent 的关系映射

        Returns:
            str: "用户名（角色名）" 或 "用户名"
        """
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

    Attributes:
        _instance: 单例实例
        _relation_maps: 用户ID到RelationMap的映射
        _username_map: 用户名映射表
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

    def build_from_config(self, users_config: List[Dict]) -> None:
        """
        从用户配置构建关系映射表

        Args:
            users_config: 用户配置列表，每个配置包含 id, username, name, knows_ids 等字段
        """
        self._relation_maps.clear()
        self._username_map = UsernameMap()

        for user in users_config:
            user_id = user.get('id')
            username = user.get('username', '')
            name = user.get('name', '')
            knows_ids = user.get('knows_ids', [])

            if user_id is None:
                continue

            self._relation_maps[user_id] = RelationMap(user_id, knows_ids)
            if username and name:
                self._username_map.add(user_id, username, name)

    def get_relation_map(self, user_id: int) -> Optional[RelationMap]:
        """
        获取指定用户的关系映射

        Args:
            user_id: 用户 ID

        Returns:
            Optional[RelationMap]: 关系映射，不存在返回 None
        """
        return self._relation_maps.get(user_id)

    def get_username_map(self) -> UsernameMap:
        """
        获取用户名映射表

        Returns:
            UsernameMap: 用户名映射表实例
        """
        return self._username_map

    def expand_author(
        self,
        author_username: str,
        author_id: int,
        owner_id: int
    ) -> str:
        """
        拓展作者显示名称

        根据当前 Agent 的关系映射，决定是否将用户名拓展为"用户名（真名）"。

        Args:
            author_username: 作者用户名
            author_id: 作者用户 ID
            owner_id: 当前 Agent 的用户 ID

        Returns:
            str: 拓展后的显示名称
        """
        relation_map = self.get_relation_map(owner_id)
        if relation_map is None:
            return author_username

        return self._username_map.get_display_name(author_username, author_id, relation_map)

    def expand_content_mentions(self, content: str, owner_id: int) -> str:
        """
        拓展内容中的 @mention

        将内容中认识的用户 @mention 拓展为 @用户名（真名）格式。

        Args:
            content: 原始内容
            owner_id: 当前 Agent 的用户 ID

        Returns:
            str: 拓展后的内容
        """
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

    def _find_user_id_by_username(self, username: str, knows_ids: Set[int]) -> Optional[int]:
        """
        在认识的用户列表中根据用户名查找用户 ID

        Args:
            username: 用户名
            knows_ids: 认识的用户 ID 集合

        Returns:
            Optional[int]: 用户 ID，未找到返回 None
        """
        for uid in knows_ids:
            if self._username_map.get_username_by_user_id(uid) == username:
                return uid
        return None

    def get_all_known_users(self, owner_id: int) -> List[int]:
        """
        获取当前用户认识的所有用户 ID

        Args:
            owner_id: 当前用户 ID

        Returns:
            List[int]: 认识的用户 ID 列表
        """
        relation_map = self.get_relation_map(owner_id)
        if relation_map is None:
            return []
        return list(relation_map.knows_ids)

    def __repr__(self) -> str:
        return f"RelationMappingService(loaded_users={len(self._relation_maps)})"


def get_relation_mapping_service() -> RelationMappingService:
    """
    获取关系映射服务单例

    Returns:
        RelationMappingService: 关系映射服务实例
    """
    return RelationMappingService()


def build_relation_maps(users_config: List[Dict]) -> RelationMappingService:
    """
    从用户配置构建关系映射服务的便捷函数

    Args:
        users_config: 用户配置列表

    Returns:
        RelationMappingService: 配置好的服务实例
    """
    service = get_relation_mapping_service()
    service.build_from_config(users_config)
    return service

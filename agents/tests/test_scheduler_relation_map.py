import pytest
from unittest.mock import patch, MagicMock

from agents.agents_scheduler.scheduler.relation_map import (
    RelationMap,
    UsernameMap,
    RelationMappingService,
    get_relation_mapping_service,
    build_relation_maps_from_db,
    rebuild_relation_maps,
)


class TestRelationMap:
    def test_relation_map_init(self):
        rm = RelationMap(user_id=1, knows_ids=[2, 3])
        assert rm.user_id == 1
        assert len(rm.knows_ids) == 2
        assert 2 in rm.knows_ids
        assert 3 in rm.knows_ids

    def test_knows(self):
        rm = RelationMap(user_id=1, knows_ids=[2, 3])
        assert rm.knows(2) is True
        assert rm.knows(3) is True
        assert rm.knows(4) is False

    def test_add_knows(self):
        rm = RelationMap(user_id=1, knows_ids=[])
        rm.add_knows(5)
        assert rm.knows(5) is True

    def test_remove_knows(self):
        rm = RelationMap(user_id=1, knows_ids=[2, 3])
        rm.remove_knows(2)
        assert rm.knows(2) is False
        assert rm.knows(3) is True

    def test_remove_nonexistent(self):
        rm = RelationMap(user_id=1, knows_ids=[2])
        rm.remove_knows(99)
        assert rm.knows(2) is True

    def test_repr(self):
        rm = RelationMap(user_id=1, knows_ids=[2, 3, 4])
        repr_str = repr(rm)
        assert "RelationMap" in repr_str
        assert "1" in repr_str


class TestUsernameMap:
    def test_add_and_get_name(self):
        um = UsernameMap()
        um.add(1, "user1", "Alice")
        assert um.get_name("user1") == "Alice"

    def test_get_username_by_name(self):
        um = UsernameMap()
        um.add(1, "user1", "Alice")
        assert um.get_username("Alice") == "user1"

    def test_get_username_by_user_id(self):
        um = UsernameMap()
        um.add(1, "user1", "Alice")
        assert um.get_username_by_user_id(1) == "user1"

    def test_get_user_id_by_username(self):
        um = UsernameMap()
        um.add(1, "user1", "Alice")
        assert um.get_user_id_by_username("user1") == 1

    def test_get_name_not_found(self):
        um = UsernameMap()
        assert um.get_name("nonexistent") is None

    def test_get_display_name_knows(self):
        um = UsernameMap()
        um.add(1, "user1", "Alice")
        rm = RelationMap(user_id=2, knows_ids=[1])
        result = um.get_display_name("user1", 1, rm)
        assert "user1" in result
        assert "Alice" in result

    def test_get_display_name_not_knows(self):
        um = UsernameMap()
        um.add(1, "user1", "Alice")
        rm = RelationMap(user_id=2, knows_ids=[])
        result = um.get_display_name("user1", 1, rm)
        assert result == "user1"


class TestRelationMappingService:
    def test_singleton(self):
        rm1 = RelationMappingService()
        rm2 = RelationMappingService()
        assert rm1 is rm2

    def test_build_from_config(self):
        rm = RelationMappingService()
        users_config = [
            {"id": 1, "username": "user1", "name": "Alice", "knows_ids": [2]},
            {"id": 2, "username": "user2", "name": "Bob", "knows_ids": [1]},
        ]
        rm.build_from_config(users_config)
        assert rm.get_relation_map(1) is not None
        assert rm.get_relation_map(2) is not None

    def test_build_from_config_skips_none_id(self):
        rm = RelationMappingService()
        users_config = [
            {"username": "user1", "name": "Alice", "knows_ids": []},
        ]
        rm.build_from_config(users_config)
        assert len(rm._relation_maps) == 0

    def test_expand_author(self):
        rm = RelationMappingService()
        users_config = [
            {"id": 1, "username": "user1", "name": "Alice", "knows_ids": [2]},
            {"id": 2, "username": "user2", "name": "Bob", "knows_ids": [1]},
        ]
        rm.build_from_config(users_config)
        result = rm.expand_author("user2", 2, 1)
        assert "user2" in result

    def test_expand_content_mentions(self):
        rm = RelationMappingService()
        users_config = [
            {"id": 1, "username": "user1", "name": "Alice", "knows_ids": [2]},
            {"id": 2, "username": "user2", "name": "Bob", "knows_ids": []},
        ]
        rm.build_from_config(users_config)
        content = "Hello @user2, how are you?"
        result = rm.expand_content_mentions(content, 1)
        assert "@user2" in result

    def test_get_all_known_users(self):
        rm = RelationMappingService()
        users_config = [
            {"id": 1, "username": "user1", "name": "Alice", "knows_ids": [2, 3]},
        ]
        rm.build_from_config(users_config)
        known_users = rm.get_all_known_users(1)
        assert 2 in known_users
        assert 3 in known_users

    def test_get_all_known_users_not_found(self):
        rm = RelationMappingService()
        result = rm.get_all_known_users(999)
        assert result == []

    def test_repr(self):
        rm = RelationMappingService()
        rm.build_from_config([])
        repr_str = repr(rm)
        assert "RelationMappingService" in repr_str


class TestRelationMapFunctions:
    def test_get_relation_mapping_service(self):
        service = get_relation_mapping_service()
        assert isinstance(service, RelationMappingService)

    def test_rebuild_relation_maps(self):
        with patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as mock_db:
            mock_db.return_value.get_agent_configs.return_value = []
            service = rebuild_relation_maps()
            assert isinstance(service, RelationMappingService)

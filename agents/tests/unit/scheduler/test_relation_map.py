import threading

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

    def test_expand_author(self):
        rm = RelationMappingService()
        with patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as mock_db:
            mock_db.return_value.get_agent_configs.return_value = [
                {
                    "id": 1, "social_platform_user_id": 101,
                    "username": "user1", "name": "Alice", "knows_ids": [2],
                },
                {
                    "id": 2, "social_platform_user_id": 202,
                    "username": "user2", "name": "Bob", "knows_ids": [1],
                },
            ]
            rm.build_from_db()
        assert rm.expand_author("user2", 202, 101) == "user2（Bob）"

    def test_expand_content_mentions(self):
        rm = RelationMappingService()
        with patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as mock_db:
            mock_db.return_value.get_agent_configs.return_value = [
                {
                    "id": 1, "social_platform_user_id": 101,
                    "username": "user1", "name": "Alice", "knows_ids": [2],
                },
                {
                    "id": 2, "social_platform_user_id": 202,
                    "username": "user2", "name": "Bob", "knows_ids": [],
                },
            ]
            rm.build_from_db()
        assert rm.expand_content_mentions("Hello @user2", 101) == "Hello @user2（Bob）"

    def test_get_all_known_users(self):
        rm = RelationMappingService()
        with patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as mock_db:
            mock_db.return_value.get_agent_configs.return_value = [
                {
                    "id": 1, "social_platform_user_id": 101,
                    "username": "user1", "name": "Alice", "knows_ids": [2, 3],
                },
                {
                    "id": 2, "social_platform_user_id": 202,
                    "username": "user2", "name": "Bob", "knows_ids": [],
                },
                {
                    "id": 3, "social_platform_user_id": 303,
                    "username": "user3", "name": "Carol", "knows_ids": [],
                },
            ]
            rm.build_from_db()
        assert set(rm.get_all_known_users(101)) == {202, 303}

    def test_get_all_known_users_not_found(self):
        rm = RelationMappingService()
        result = rm.get_all_known_users(999)
        assert result == []

    def test_repr(self):
        rm = RelationMappingService()
        with patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as mock_db:
            mock_db.return_value.get_agent_configs.return_value = []
            rm.build_from_db()
        repr_str = repr(rm)
        assert "RelationMappingService" in repr_str

    def test_rebuild_publishes_only_complete_snapshots(self):
        """重建过程中读取方只能看到完整旧快照或完整新快照。"""
        service = RelationMappingService()
        old_configs = [
            {
                "id": 1,
                "social_platform_user_id": 101,
                "username": "owner",
                "name": "Owner",
                "knows_ids": [2],
            },
            {
                "id": 2,
                "social_platform_user_id": 202,
                "username": "friend",
                "name": "旧名字",
                "knows_ids": [],
            },
        ]
        new_configs = [
            old_configs[0],
            {**old_configs[1], "name": "新名字"},
        ]
        with patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as db:
            db.return_value.get_agent_configs.return_value = old_configs
            service.build_from_db()

        rebuild_paused = threading.Event()
        continue_rebuild = threading.Event()
        original_add = UsernameMap.add

        def blocking_add(username_map, user_id, username, name):
            if not rebuild_paused.is_set():
                rebuild_paused.set()
                continue_rebuild.wait(timeout=2)
            original_add(username_map, user_id, username, name)

        with (
            patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as db,
            patch.object(UsernameMap, "add", new=blocking_add),
        ):
            db.return_value.get_agent_configs.return_value = new_configs
            worker = threading.Thread(target=service.build_from_db)
            worker.start()
            assert rebuild_paused.wait(timeout=1)
            assert service.expand_author("friend", 202, 101) == "friend（旧名字）"
            continue_rebuild.set()
            worker.join(timeout=2)

        assert not worker.is_alive()
        assert service.expand_author("friend", 202, 101) == "friend（新名字）"


class TestRelationMapFunctions:
    def test_get_relation_mapping_service(self):
        service = get_relation_mapping_service()
        assert isinstance(service, RelationMappingService)

    def test_rebuild_relation_maps(self):
        with patch("agents.agents_scheduler.scheduler.relation_map.get_db_client") as mock_db:
            mock_db.return_value.get_agent_configs.return_value = [
                {
                    "id": 1,
                    "social_platform_user_id": 101,
                    "username": "user1",
                    "name": "Alice",
                    "knows_ids": [2],
                },
                {
                    "id": 2,
                    "social_platform_user_id": 202,
                    "username": "user2",
                    "name": "Bob",
                    "knows_ids": [1],
                },
            ]
            service = rebuild_relation_maps()
            assert isinstance(service, RelationMappingService)
            assert service.get_relation_map(101).knows(202) is True
            assert service.expand_author("user2", 202, 101) == "user2（Bob）"
            mock_db.return_value.get_agent_configs.assert_called_once_with()

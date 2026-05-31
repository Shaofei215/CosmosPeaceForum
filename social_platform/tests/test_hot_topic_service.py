import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_platform.app.db.session import Base
from social_platform.app.models import HotTopic, HotTopicGeneration, Post, User
from social_platform.app.services import hot_topic_service


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_public_hot_topics_only_returns_active_items_in_rank_order(db_session):
    db_session.add_all([
        HotTopic(title="草稿", search_query="草稿", status="draft", rank=1),
        HotTopic(title="第二", search_query="第二", status="active", rank=2),
        HotTopic(title="第一", search_query="第一", status="active", rank=1),
    ])
    db_session.commit()

    topics = hot_topic_service.list_public_hot_topics(db_session)

    assert [topic.title for topic in topics] == ["第一", "第二"]


def test_create_hot_topic_inserts_rank_and_keeps_active_ranks_unique_from_one(db_session):
    hot_topic_service.create_hot_topic(
        db_session,
        {"title": "第一", "search_query": "第一", "status": "active", "rank": 1},
    )
    hot_topic_service.create_hot_topic(
        db_session,
        {"title": "插入第一", "search_query": "插入第一", "status": "active", "rank": 1},
    )

    topics = hot_topic_service.list_public_hot_topics(db_session)

    assert [(topic.title, topic.rank) for topic in topics] == [("插入第一", 1), ("第一", 2)]


def test_settings_masks_and_preserves_secrets(db_session):
    settings = hot_topic_service.update_hot_topic_settings(
        db_session,
        {"llm_api_key": "secret", "tavily_api_key": "tavily", "publish_policy": "auto"},
    )
    masked = hot_topic_service.serialize_settings(settings)

    assert masked["llm_api_key"] == "********"
    assert masked["tavily_api_key"] == "********"
    assert masked["publish_policy"] == "auto"

    settings = hot_topic_service.update_hot_topic_settings(db_session, {"llm_api_key": "********"})
    assert settings.llm_api_key == "secret"


def test_prompt_context_contains_top_posts_current_and_history(db_session):
    user = User(username="alice", bio="研究员")
    db_session.add(user)
    db_session.commit()
    db_session.add(
        Post(author_id=user.id, title="火星实验", content="火星实验有新进展", heat_score=42)
    )
    db_session.add(HotTopic(title="当前热榜", search_query="当前", status="active", rank=1))
    db_session.add(
        HotTopicGeneration(
            status="success",
            publish_policy="auto",
            output_json='[{"title":"历史热榜","search_query":"历史"}]',
        )
    )
    db_session.commit()

    context = hot_topic_service.build_hot_topic_agent_context(db_session, history_limit=3)
    prompt = hot_topic_service.build_hot_topic_agent_prompt(context)

    assert "火星实验" in prompt
    assert "当前热榜" in prompt
    assert "历史热榜" in prompt
    assert "submit_hot_topics" in prompt


def test_auto_publish_archives_previous_agent_topics_but_keeps_manual_topic(db_session):
    manual = HotTopic(title="人工", search_query="人工", source="manual", status="active", rank=1)
    old_agent = HotTopic(title="旧 Agent", search_query="旧", source="agent", status="active", rank=1)
    generation = HotTopicGeneration(status="pending", publish_policy="auto")
    db_session.add_all([manual, old_agent, generation])
    db_session.commit()

    created = hot_topic_service.apply_generated_hot_topics(
        db_session,
        generation,
        [{"title": "新 Agent", "search_query": "新", "rank": 1}],
        "auto",
    )

    assert created[0].status == "active"
    assert db_session.query(HotTopic).filter(HotTopic.title == "人工").one().status == "active"
    assert db_session.query(HotTopic).filter(HotTopic.title == "旧 Agent").one().status == "archived"
    assert generation.status == "success"


def test_hot_topic_agent_invokes_llm_with_fresh_system_user_messages(db_session):
    settings = hot_topic_service.get_hot_topic_settings(db_session)
    settings.publish_policy = "draft"
    db_session.commit()
    seen_messages = []

    class FakeResponse:
        content = ""
        tool_calls = [
            {
                "name": "submit_hot_topics",
                "args": {
                    "topics_json": (
                        '[{"title":"新热榜","search_query":"新热榜 关键词","rank":1}]'
                    )
                },
            }
        ]

    class FakeLLM:
        def invoke(self, messages):
            seen_messages.append(messages)
            assert len(messages) == 2
            assert [message["role"] for message in messages] == ["system", "user"]
            return FakeResponse()

    generation, topics = hot_topic_service.run_hot_topic_agent(
        db_session,
        force=True,
        llm_factory=lambda _settings, _tools: FakeLLM(),
    )

    assert generation.status == "success"
    assert topics[0].title == "新热榜"
    assert topics[0].rank == 1
    assert len(seen_messages) == 1

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from social_platform.app.db.session import Base
from social_platform.app.domains.post.models import Post
from social_platform.app.domains.user.models import User
from social_platform.app.domains.hot_topic.models import HotTopic, HotTopicGeneration
from social_platform.app.domains.hot_topic import application as hot_topic_service


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
    assert "topics_json" not in prompt


def test_default_prompt_spells_out_public_output_constraints():
    prompt = hot_topic_service.DEFAULT_HOT_TOPIC_AGENT_PROMPT

    assert "不超过 150" in prompt
    assert "只能是一个搜索关键词" in prompt
    assert "不评价热度、排名、趋势" in prompt
    assert "不要解释入选原因、讨论量、排序依据或热度变化" in prompt
    assert "topics_json" not in prompt


def test_normalize_agent_topics_enforces_summary_limit_and_single_search_query():
    long_summary = "这是一段很长的摘要" * 20

    topics = hot_topic_service.normalize_agent_topics([
        {
            "title": "火星实验",
            "search_query": "火星实验，月球基地/深空探测",
            "summary": long_summary,
            "rank": 1,
        }
    ])

    assert topics == [
        {
            "title": "火星实验",
            "search_query": "火星实验",
            "summary": long_summary[:hot_topic_service.HOT_TOPIC_SUMMARY_MAX_LENGTH],
            "rank": 1,
        }
    ]


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


def test_prompt_context_allows_zero_history_limit(db_session):
    db_session.add(
        HotTopicGeneration(
            status="success",
            publish_policy="auto",
            output_json='[{"title":"历史热榜","search_query":"历史"}]',
        )
    )
    db_session.commit()

    context = hot_topic_service.build_hot_topic_agent_context(db_session, history_limit=0)

    assert context["recent_generations"] == []


def test_hot_topic_agent_tells_llm_when_final_round_is_reached(db_session):
    settings = hot_topic_service.get_hot_topic_settings(db_session)
    settings.publish_policy = "draft"
    settings.max_llm_rounds = 2
    db_session.commit()
    seen_user_prompts = []

    class FakeResponse:
        content = "[]"
        tool_calls = []

    class FakeLLM:
        def invoke(self, messages):
            seen_user_prompts.append(messages[1]["content"])
            if len(seen_user_prompts) == 1:
                return type(
                    "SearchResponse",
                    (),
                    {
                        "content": "",
                        "tool_calls": [
                            {"name": "search_platform", "args": {"query": "火星", "count": 1}},
                        ],
                    },
                )()
            return type(
                "SubmitResponse",
                (),
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "submit_hot_topics",
                            "args": {
                                "topics_json": (
                                    '[{"title":"最后一轮热榜","search_query":"最后一轮","rank":1}]'
                                )
                            },
                        }
                    ],
                },
            )()

    generation, topics = hot_topic_service.run_hot_topic_agent(
        db_session,
        force=True,
        llm_factory=lambda _settings, _tools: FakeLLM(),
    )

    assert generation.status == "success"
    assert topics[0].title == "最后一轮热榜"
    assert "最多还有 1 轮" in seen_user_prompts[0]
    assert "这是最后一轮" in seen_user_prompts[1]


def test_hot_topic_agent_retries_after_invalid_submit_json(db_session):
    settings = hot_topic_service.get_hot_topic_settings(db_session)
    settings.publish_policy = "draft"
    settings.max_llm_rounds = 2
    db_session.commit()
    seen_user_prompts = []

    class FakeLLM:
        def invoke(self, messages):
            seen_user_prompts.append(messages[1]["content"])
            if len(seen_user_prompts) == 1:
                return type(
                    "InvalidSubmitResponse",
                    (),
                    {
                        "content": "",
                        "tool_calls": [
                            {
                                "name": "submit_hot_topics",
                                "args": {
                                    "topics_json": (
                                        '[{"title":"坏 JSON","search_query":"坏"}'
                                        ' {"title":"缺逗号","search_query":"缺逗号"}]'
                                    )
                                },
                            }
                        ],
                    },
                )()
            return type(
                "ValidSubmitResponse",
                (),
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "submit_hot_topics",
                            "args": {
                                "topics_json": (
                                    '[{"title":"修正后热榜","search_query":"修正后","rank":1}]'
                                )
                            },
                        }
                    ],
                },
            )()

    generation, topics = hot_topic_service.run_hot_topic_agent(
        db_session,
        force=True,
        llm_factory=lambda _settings, _tools: FakeLLM(),
    )

    assert generation.status == "success"
    assert topics[0].title == "修正后热榜"
    assert "invalid_topics_json" in seen_user_prompts[1]


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


def test_hot_topic_agent_records_failure_when_context_building_fails(db_session, monkeypatch):
    settings = hot_topic_service.get_hot_topic_settings(db_session)
    settings.publish_policy = "draft"
    db_session.commit()

    def fail_context(_db, history_limit=hot_topic_service.DEFAULT_HISTORY_LIMIT):
        raise RuntimeError("context database failure")

    monkeypatch.setattr(hot_topic_service, "build_hot_topic_agent_context", fail_context)

    generation, topics = hot_topic_service.run_hot_topic_agent(db_session, force=True)

    assert topics == []
    assert generation.status == "failed"
    assert generation.error_message == "context database failure"
    assert generation.completed_at is not None


def test_hot_topic_agent_records_failure_when_tool_setup_fails(db_session, monkeypatch):
    settings = hot_topic_service.get_hot_topic_settings(db_session)
    settings.publish_policy = "draft"
    db_session.commit()

    def fail_tool(_db):
        raise RuntimeError("tool import failure")

    monkeypatch.setattr(hot_topic_service, "_create_search_tool", fail_tool)

    generation, topics = hot_topic_service.run_hot_topic_agent(db_session, force=True)

    assert topics == []
    assert generation.status == "failed"
    assert generation.error_message == "tool import failure"
    assert generation.input_snapshot is not None

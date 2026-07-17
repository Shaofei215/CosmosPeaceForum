"""
Scheduler 内部 HTTP 接口服务

供 management 后端调用，用于热更新通知和健康管理

端点：
- GET  /health                  - 健康检查
- POST /internal/reload/system  - 重载系统配置
- POST /internal/reload/model   - 重载模型配置
- POST /internal/reload/agent   - 重载 Agent 配置
- POST /internal/reload/all     - 重载全部配置
- POST /internal/session-injections - 添加下一次会话注入
"""

import logging
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SchedulerInternalHandler(BaseHTTPRequestHandler):
    """内部 HTTP 请求处理器"""

    scheduler_manager = None

    def log_message(self, format, *args):
        """覆盖默认日志输出"""
        logger.debug(f"[内部接口] {format % args}")

    def _send_json_response(self, status_code: int, data: dict):
        """发送 JSON 响应"""
        try:
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            import json
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError) as e:
            logger.warning(f"[内部接口] 发送响应时连接断开: {e}")
        except Exception as e:
            logger.error(f"[内部接口] 发送响应失败: {e}")

    def do_GET(self):
        """处理 GET 请求"""
        path = urlparse(self.path).path
        if path == '/health':
            self._send_json_response(200, {
                "status": "ok",
                "service": "scheduler",
            })
        elif path == '/internal/status':
            self._handle_status()
        else:
            self._send_json_response(404, {"error": "not found"})

    def do_POST(self):
        """处理 POST 请求"""
        path = urlparse(self.path).path
        if path == '/internal/reload/system':
            self._handle_reload_system()
        elif path == '/internal/reload/model':
            self._handle_reload_model()
        elif path == '/internal/reload/agent':
            self._handle_reload_agent()
        elif path == '/internal/reload/agents':
            self._handle_reload_agents()
        elif path == '/internal/reload/all':
            self._handle_reload_all()
        elif path == '/internal/session-injections':
            self._handle_session_injections()
        else:
            self._send_json_response(404, {"error": "not found"})

    def _read_json_body(self) -> dict:
        """读取 JSON 请求体。"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length <= 0:
            return {}

        import json
        return json.loads(self.rfile.read(content_length))

    def _handle_status(self):
        """返回当前 Agent 线程运行状态。"""
        if not self.scheduler_manager:
            self._send_json_response(200, {"agents": []})
            return

        self._send_json_response(200, {
            "agents": self.scheduler_manager.get_all_statuses(),
        })

    def _handle_reload_system(self):
        """重载系统配置"""
        try:
            from agents.agents_scheduler.langgraph.config import reload_session_config
            from agents.agents_scheduler.memory.config import MemoryConfig, reload_memory_config
            from agents.agents_scheduler.memory.embedding import reload_embedding_model
            from agents.agents_scheduler.memory.service import reload_memory_service
            from agents.agents_scheduler.langgraph.executor import reload_llm_registry
            from agents.agents_scheduler.scheduler.time_system import reload_time_scale

            reload_session_config()
            memory_config = MemoryConfig.from_db()
            reload_memory_service(memory_config)
            reload_memory_config(memory_config)
            reload_embedding_model(memory_config)
            reload_llm_registry()
            reload_time_scale()

            logger.info("系统配置已重载")
            self._send_json_response(200, {"message": "system config reloaded"})
        except Exception as e:
            logger.error(f"系统配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _handle_reload_model(self):
        """重载模型配置"""
        try:
            from agents.agents_scheduler.langgraph.config import reload_session_config
            from agents.agents_scheduler.langgraph.executor import reload_llm_registry

            reload_session_config()
            reload_llm_registry()

            logger.info("模型配置已重载")
            self._send_json_response(200, {"message": "model config reloaded"})
        except Exception as e:
            logger.error(f"模型配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _handle_reload_agent(self):
        """重载 Agent 配置（支持 start / stop / restart 动作）"""
        try:
            from agents.agents_scheduler.scheduler.relation_map import rebuild_relation_maps

            rebuild_relation_maps()

            body = self._read_json_body()
            if body:
                agent_id = body.get('agent_id')
                action = body.get('action', 'restart')

                if agent_id and self.scheduler_manager:
                    if action == 'start':
                        success = self.scheduler_manager.start_agent(agent_id)
                        if not success:
                            self._send_json_response(
                                404,
                                {"error": f"Agent ID={agent_id} 启动失败"}
                            )
                            return
                    elif action == 'stop':
                        success = self.scheduler_manager.stop_agent(agent_id)
                        if not success:
                            self._send_json_response(
                                404,
                                {"error": f"Agent ID={agent_id} 不存在或停止失败"}
                            )
                            return
                    else:
                        success = self.scheduler_manager.restart_agent(agent_id)
                        if not success:
                            self._send_json_response(
                                404,
                                {"error": f"Agent ID={agent_id} 不存在或重启失败"}
                            )
                            return

            logger.info("Agent 配置已重载")
            self._send_json_response(200, {"message": "agent config reloaded"})
        except Exception as e:
            logger.error(f"Agent 配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _handle_reload_agents(self):
        """批量重载 Agent 配置（支持 start / stop 动作）"""
        try:
            from agents.agents_scheduler.scheduler.relation_map import rebuild_relation_maps

            body = self._read_json_body()
            agent_ids = body.get('agent_ids') or []
            action = body.get('action', 'restart')

            if not isinstance(agent_ids, list):
                self._send_json_response(400, {"error": "agent_ids must be a list"})
                return

            rebuild_relation_maps()

            if not self.scheduler_manager:
                self._send_json_response(503, {"error": "scheduler manager unavailable"})
                return

            ids = [int(agent_id) for agent_id in agent_ids]
            if action == 'start':
                results = self.scheduler_manager.start_agents(ids)
            elif action == 'stop':
                results = self.scheduler_manager.stop_agents(ids)
            else:
                results = {agent_id: self.scheduler_manager.restart_agent(agent_id) for agent_id in ids}

            logger.info("批量 Agent 配置已重载: action=%s count=%d", action, len(ids))
            self._send_json_response(200, {
                "message": "agents config reloaded",
                "results": results,
            })
        except Exception as e:
            logger.error(f"批量 Agent 配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _handle_reload_all(self):
        """重载全部配置"""
        try:
            from agents.agents_scheduler.langgraph.config import reload_session_config
            from agents.agents_scheduler.memory.config import MemoryConfig, reload_memory_config
            from agents.agents_scheduler.memory.embedding import reload_embedding_model
            from agents.agents_scheduler.memory.service import reload_memory_service
            from agents.agents_scheduler.scheduler.relation_map import rebuild_relation_maps
            from agents.agents_scheduler.langgraph.executor import reload_llm_registry
            from agents.agents_scheduler.scheduler.time_system import reload_time_scale

            reload_session_config()
            memory_config = MemoryConfig.from_db()
            reload_memory_service(memory_config)
            reload_memory_config(memory_config)
            reload_embedding_model(memory_config)
            reload_llm_registry()
            reload_time_scale()
            rebuild_relation_maps()

            if self.scheduler_manager:
                threading.Thread(
                    target=self._restart_all_agents_in_background,
                    name="scheduler-reload-all",
                    daemon=True,
                ).start()

            logger.info("[热更新] 全部配置已重载")
            self._send_json_response(200, {"message": "all config reloaded"})
        except Exception as e:
            logger.error(f"全部配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _restart_all_agents_in_background(self) -> None:
        """
        后台重启所有 Agent 调度线程。

        reload/all 由 management 后端同步调用，HTTP 客户端有较短超时时间。
        将耗时的线程重启动作放到后台，避免调用方先断开导致 Broken pipe。
        """
        try:
            if self.scheduler_manager:
                self.scheduler_manager.restart_all()
        except Exception as e:
            logger.error("[热更新] 后台重启全部 Agent 失败: %s", e)

    def _handle_session_injections(self):
        """添加下一次登录会话使用的一次性注入。"""
        try:
            from agents.agents_scheduler.scheduler.session_injections import (
                SESSION_INJECTION_TYPE_PROMPT,
                enqueue_session_injection,
            )

            body = self._read_json_body()
            agent_ids = body.get('agent_ids') or []
            injection_type = body.get('type') or body.get('injection_type')
            content = (body.get('content') or '').strip()
            source = body.get('source') or 'internal'
            metadata = body.get('metadata') or {}

            if not isinstance(agent_ids, list) or not agent_ids:
                self._send_json_response(400, {"error": "agent_ids must be a non-empty list"})
                return
            if injection_type != SESSION_INJECTION_TYPE_PROMPT:
                self._send_json_response(400, {"error": f"unsupported injection type: {injection_type}"})
                return
            if not content:
                self._send_json_response(400, {"error": "content is required"})
                return
            if not isinstance(metadata, dict):
                self._send_json_response(400, {"error": "metadata must be an object"})
                return

            ids = [int(agent_id) for agent_id in agent_ids]
            queued = enqueue_session_injection(
                agent_ids=ids,
                injection_type=injection_type,
                content=content,
                source=source,
                metadata=metadata,
            )

            logger.info(
                "提示词注入 已加入队列: type=%s count=%d source=%s",
                injection_type,
                len(queued),
                source,
            )
            self._send_json_response(200, {
                "message": "session injections queued",
                "queued": queued,
            })
        except ValueError as e:
            self._send_json_response(400, {"error": str(e)})
        except Exception as e:
            logger.error(f"提示词注入 加入队列失败: {e}")
            self._send_json_response(500, {"error": str(e)})


class SchedulerInternalServer:
    """
    Scheduler 内部 HTTP 服务器

    运行在独立线程中，监听本地端口，
    接收 management 后端的热更新通知。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8002, scheduler_manager=None):
        self.host = host
        self.port = port
        self.scheduler_manager = scheduler_manager
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """启动内部 HTTP 服务器"""
        SchedulerInternalHandler.scheduler_manager = self.scheduler_manager

        self._server = ThreadingHTTPServer((self.host, self.port), SchedulerInternalHandler)
        self._server.daemon_threads = True

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="scheduler-internal-server",
        )
        self._thread.start()

        logger.info("调度器服务器启动在 http://%s:%d", self.host, self.port)

    def stop(self, wait: bool = True):
        """停止内部 HTTP 服务器"""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            if wait and self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)
            logger.info("调度器服务器已停止")

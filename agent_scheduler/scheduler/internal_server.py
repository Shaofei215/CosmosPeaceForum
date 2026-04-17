"""
Scheduler 内部 HTTP 接口服务

供 management 后端调用，用于热更新通知和健康管理

端点：
- GET  /health                  - 健康检查
- POST /internal/reload/system  - 重载系统配置
- POST /internal/reload/model   - 重载模型配置
- POST /internal/reload/agent   - 重载 Agent 配置
- POST /internal/reload/all     - 重载全部配置
"""

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class SchedulerInternalHandler(BaseHTTPRequestHandler):
    """内部 HTTP 请求处理器"""

    scheduler_manager = None

    def log_message(self, format, *args):
        """覆盖默认日志输出"""
        logger.debug(f"[内部接口] {format % args}")

    def _send_json_response(self, status_code: int, data: dict):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        import json
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/health':
            self._send_json_response(200, {
                "status": "ok",
                "service": "scheduler",
            })
        else:
            self._send_json_response(404, {"error": "not found"})

    def do_POST(self):
        """处理 POST 请求"""
        if self.path == '/internal/reload/system':
            self._handle_reload_system()
        elif self.path == '/internal/reload/model':
            self._handle_reload_model()
        elif self.path == '/internal/reload/agent':
            self._handle_reload_agent()
        elif self.path == '/internal/reload/all':
            self._handle_reload_all()
        else:
            self._send_json_response(404, {"error": "not found"})

    def _handle_reload_system(self):
        """重载系统配置"""
        try:
            from agent_scheduler.scheduler.config import reload_scheduler_config
            from agent_scheduler.langgraph.config import reload_session_config
            from agent_scheduler.memory.config import reload_memory_config

            reload_scheduler_config()
            reload_session_config()
            reload_memory_config()

            logger.info("[热更新] 系统配置已重载")
            self._send_json_response(200, {"message": "system config reloaded"})
        except Exception as e:
            logger.error(f"[热更新] 系统配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _handle_reload_model(self):
        """重载模型配置"""
        try:
            from agent_scheduler.langgraph.config import reload_session_config
            from agent_scheduler.langgraph.executor import reload_llm_registry

            reload_session_config()

            content_length = int(self.headers.get('Content-Length', 0))
            model_config_id = None
            if content_length > 0:
                import json
                body = json.loads(self.rfile.read(content_length))
                model_config_id = body.get('model_config_id')

            reload_llm_registry(model_config_id)

            if model_config_id is not None:
                logger.info(f"[热更新] 模型配置已重载: id={model_config_id}")
                self._send_json_response(200, {"message": f"model config {model_config_id} reloaded"})
            else:
                logger.info("[热更新] 模型配置已重载")
                self._send_json_response(200, {"message": "model config reloaded"})
        except Exception as e:
            logger.error(f"[热更新] 模型配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _handle_reload_agent(self):
        """重载 Agent 配置（重启单个 Agent 线程）"""
        try:
            from agent_scheduler.scheduler.relation_map import rebuild_relation_maps

            rebuild_relation_maps()

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                import json
                body = json.loads(self.rfile.read(content_length))
                agent_id = body.get('agent_id')
                if agent_id and self.scheduler_manager:
                    self.scheduler_manager.restart_agent(agent_id)

            logger.info("[热更新] Agent 配置已重载")
            self._send_json_response(200, {"message": "agent config reloaded"})
        except Exception as e:
            logger.error(f"[热更新] Agent 配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})

    def _handle_reload_all(self):
        """重载全部配置"""
        try:
            from agent_scheduler.scheduler.config import reload_scheduler_config
            from agent_scheduler.langgraph.config import reload_session_config
            from agent_scheduler.memory.config import reload_memory_config
            from agent_scheduler.scheduler.relation_map import rebuild_relation_maps
            from agent_scheduler.langgraph.executor import reload_llm_registry

            reload_scheduler_config()
            reload_session_config()
            reload_memory_config()
            reload_llm_registry()
            rebuild_relation_maps()

            if self.scheduler_manager:
                self.scheduler_manager.restart_all()

            logger.info("[热更新] 全部配置已重载")
            self._send_json_response(200, {"message": "all config reloaded"})
        except Exception as e:
            logger.error(f"[热更新] 全部配置重载失败: {e}")
            self._send_json_response(500, {"error": str(e)})


class SchedulerInternalServer:
    """
    Scheduler 内部 HTTP 服务器

    运行在独立线程中，监听本地端口，
    接收 management 后端的热更新通知。
    """

    def __init__(self, port: int = 8002, scheduler_manager=None):
        self.port = port
        self.scheduler_manager = scheduler_manager
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """启动内部 HTTP 服务器"""
        SchedulerInternalHandler.scheduler_manager = self.scheduler_manager

        self._server = HTTPServer(('127.0.0.1', self.port), SchedulerInternalHandler)
        self._server.daemon_threads = True

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="scheduler-internal-server",
        )
        self._thread.start()

        logger.info(f"[内部接口] 服务器启动在 http://127.0.0.1:{self.port}")

    def stop(self):
        """停止内部 HTTP 服务器"""
        if self._server:
            self._server.shutdown()
            logger.info("[内部接口] 服务器已停止")

# agent_scheduler 包初始化文件
# 标识此目录为一个独立的 Python 包，名为 agent_scheduler
#
# 此文件的作用：
# 1. 将 agent_scheduler 目录标记为一个 Python 包
# 2. 通过 pyproject.toml 的 setuptools 配置，可以被 pip install -e . 安装
# 3. 使得 from agent_scheduler.xxx 可以正常工作

__pkg_name__ = "agent_scheduler"
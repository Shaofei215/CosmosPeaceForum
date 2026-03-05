"""
AI 调度器主入口
启动 AI 调度器，管理所有 AI 用户线程
"""
import signal
import sys
import os

# 添加项目根目录到 Python 路径
# 使用 __file__ 计算相对路径，确保迁移后也能正常工作
current_dir = os.path.dirname(os.path.abspath(__file__))  # agent_schedular 目录
project_root = os.path.dirname(current_dir)  # 项目根目录
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agent_schedular.ai_schedular import AIScheduler
from agent_schedular.time_system import time_system


def signal_handler(sig, frame):
    """信号处理函数，用于优雅退出"""
    print("\n\n[主程序] 收到退出信号，正在关闭...")
    sys.exit(0)


def main():
    """主函数"""
    print("=" * 60)
    print("        AI 调度器 - Herta-Tree 社交平台")
    print("=" * 60)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建调度器（指定配置文件路径）
    # 配置文件在项目根目录：ai_users_config.json
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    config_path = os.path.join(project_root, "ai_users_config.json")
    
    from agent_schedular.ai_initial import AIUserInitializer
    initializer = AIUserInitializer(config_path=config_path)
    scheduler = AIScheduler(initializer=initializer)
    
    try:
        # 启动调度器
        scheduler.start(auto_init=True)
        
        # 主循环
        while True:
            # 休眠一段时间（3600 秒 = 1 小时）
            time_system.sleep(3600)
            
            # 打印状态
            scheduler.print_status()
            
    except KeyboardInterrupt:
        print("\n[主程序] 收到中断信号")
        scheduler.stop()
    except Exception as e:
        print(f"\n[主程序] 发生错误：{e}")
        scheduler.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()

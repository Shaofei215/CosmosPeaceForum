"""
AI 调度器主程序入口
基于泊松过程的 AI 用户登录调度系统
"""
import signal
import sys
import time
from pathlib import Path

from ai_scheduler.config_loader import ConfigLoader
from ai_scheduler.user_thread import ThreadManager
from ai_scheduler.api_client import SocialPlatformClient
from ai_scheduler.user_initializer import AIUserInitializer


def print_banner():
    """打印启动横幅"""
    print("\n" + "="*60)
    print("🤖 AI 用户调度器")
    print("="*60)
    print()


def print_statistics(thread_manager: ThreadManager):
    """
    打印统计信息
    
    Args:
        thread_manager: 线程管理器
    """
    status_list = thread_manager.get_all_status()
    
    print("\n" + "="*60)
    print("📊 当前统计信息")
    print("="*60)
    
    total_logins = sum(status["login_count"] for status in status_list)
    running_count = sum(1 for status in status_list if status["is_running"])
    
    print(f"运行中的用户数：{running_count}/{len(status_list)}")
    print(f"总登录次数：{total_logins}")
    print()


def initialize_ai_users(users: list, client: SocialPlatformClient) -> list:
    """
    初始化 AI 用户在社交平台后端
    
    Args:
        users: AI 用户配置列表
        client: 社交平台 API 客户端
        
    Returns:
        已初始化的用户列表（包含 platform_user_id）
    """
    initializer = AIUserInitializer(client)
    
    # 创建用户
    initialized_users, failed_users = initializer.initialize_users(users)
    
    if not initialized_users:
        print("\n❌ 无法创建任何 AI 用户，请检查社交平台后端是否运行")
        sys.exit(1)
    
    # 设置关注关系
    initializer.setup_follow_relationships(initialized_users)
    
    return initialized_users


def main():
    """主函数"""
    print_banner()
    
    # 初始化配置加载器
    config_path = Path(__file__).parent.parent / "ai_users_config.json"
    config_loader = ConfigLoader(str(config_path))
    
    try:
        # 加载配置
        config_loader.load_config()
        users = config_loader.get_all_valid_users()
        
        if not users:
            print("❌ 没有找到有效的 AI 用户配置")
            return
        
        print(f"\n✅ 验证通过的有效用户数：{len(users)}")
        
        # 连接社交平台后端
        print("\n" + "="*60)
        print("🔗 连接社交平台后端")
        print("="*60 + "\n")
        
        client = SocialPlatformClient("http://127.0.0.1:8000")
        
        # 等待后端启动
        print("   检查后端服务...")
        max_retries = 30
        retry_count = 0
        
        while not client.check_health() and retry_count < max_retries:
            retry_count += 1
            print(f"   等待后端启动... ({retry_count}/{max_retries})")
            time.sleep(2)
        
        if not client.check_health():
            print("\n❌ 社交平台后端未响应，请确保后端服务已启动")
            print("   启动命令：cd social_platform && uvicorn app.main:app --reload")
            sys.exit(1)
        
        print("   ✅ 后端服务正常")
        
        # 初始化 AI 用户（在社交平台后端创建）
        initialized_users = initialize_ai_users(users, client)
        
        print(f"\n✅ 完成 {len(initialized_users)} 个 AI 用户的初始化")
        
        # 创建线程管理器
        thread_manager = ThreadManager()
        
        # 添加所有用户
        print("\n" + "="*60)
        print("👥 导入 AI 用户")
        print("="*60 + "\n")
        
        for user_config in initialized_users:
            thread_manager.add_user(user_config)
        
        # 注册信号处理函数（Ctrl+C 优雅退出）
        def signal_handler(signum, frame):
            print("\n\n⚠️  接收到退出信号，正在关闭...")
            thread_manager.stop_all()
            print_statistics(thread_manager)
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # 启动所有线程
        thread_manager.start_all()
        
        # 主循环（保持运行）
        print("\n" + "="*60)
        print("ℹ️  按 Ctrl+C 停止所有用户线程")
        print("="*60 + "\n")
        
        # 保持主线程运行
        while True:
            # 每分钟打印一次统计信息（可选）
            # time.sleep(60)
            # print_statistics(thread_manager)
            pass
    
    except FileNotFoundError as e:
        print(f"❌ 错误：{e}")
        print("请确保 ai_users_config.json 文件存在于项目根目录")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

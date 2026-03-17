# 应用配置模块
# 管理应用的所有配置项
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    应用配置类
    从环境变量或.env 文件加载配置
    """
    # 项目名称
    PROJECT_NAME: str = "Herta-Tree Social Platform"
    
    # API 版本号
    VERSION: str = "0.1.0"
    
    # API v1 版本前缀
    API_V1_PREFIX: str = "/api/v1"
    
    # 数据库连接 URL，默认使用 SQLite
    DATABASE_URL: str = "sqlite:///./herta_tree.db"
    
    # 调试模式开关
    DEBUG: bool = True
    
    class Config:
        # 指定从.env 文件读取环境变量
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例
    
    使用 lru_cache 缓存配置实例，避免重复加载
    
    Returns:
        Settings 配置实例
    """
    return Settings()

# /app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )

    APP_NAME: str = "goblin-2api"
    APP_VERSION: str = "1.0.0"
    DESCRIPTION: str = "一个将 goblin.tools 转换为兼容 OpenAI 格式 API 的高性能代理。"

    API_MASTER_KEY: Optional[str] = "1"
    NGINX_PORT: int = 8088

    # 上游请求配置
    API_REQUEST_TIMEOUT: int = 120

    # 模型名称到上游 URL 的映射
    MODEL_MAPPING: Dict[str, str] = {
        "语气评判": "https://goblin.tools/api/ToneJudger/JudgeTone",
        "回应建议": "https://goblin.tools/api/ToneJudger/SuggestResponse",
    }
    DEFAULT_MODEL: str = "语气评判"

    @property
    def KNOWN_MODELS(self) -> List[str]:
        return list(self.MODEL_MAPPING.keys())

settings = Settings()

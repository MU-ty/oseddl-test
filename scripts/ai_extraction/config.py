"""
AI Agent 活动提取系统配置文件

支持两种AI方案：
1. GitHub Models (推荐 - 免费) - 需要GITHUB_TOKEN
2. OpenAI API (可选 - 付费) - 需要OPENAI_API_KEY
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """系统配置"""
    
    # ============ GitHub Models 配置 (推荐 - 免费) ============
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    """GitHub Personal Access Token - 用于GitHub Models API (推荐)"""
    
    GITHUB_MODELS_API_BASE: str = "https://models.inference.ai.azure.com/chat/completions"
    GITHUB_MODELS_DEFAULT: str = "gpt-4o"
    
    # 支持的GitHub免费模型
    GITHUB_MODELS_AVAILABLE: list = [
        "gpt-4o",                    # 推荐：最强能力，速度快
        "claude-3-5-sonnet",         # 可选：Claude能力
        "phi-4",                     # 可选：轻量级模型
        "llama-3.1-405b",           # 可选：开源大模型
    ]
    
    # ============ OpenAI 配置 (可选 - 付费) ============
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    """OpenAI API密钥 (可选 - 仅在GitHub Models不可用时使用)"""
    
    OPENAI_MODEL: str = "gpt-4-turbo-preview"  # 或 gpt-3.5-turbo
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    
    # ============ AI选择策略 ============
    # 自动选择优先级:
    # 1. 如果有GITHUB_TOKEN → 使用GitHub Models (推荐)
    # 2. 如果有OPENAI_API_KEY → 使用OpenAI (备选)
    # 3. 都没有 → 使用规则解析器 (基础)
    
    USE_GITHUB_MODELS: bool = bool(os.getenv("GITHUB_TOKEN", ""))  # 自动检测
    USE_OPENAI_FALLBACK: bool = bool(os.getenv("OPENAI_API_KEY", ""))  # 自动检测
    
    # LLM 超参数
    LLM_TEMPERATURE: float = 0.3  # 降低温度，使输出更稳定
    LLM_MAX_TOKENS: int = 2000
    
    # 项目路径
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    SCRIPTS_DIR: Path = PROJECT_ROOT / "scripts"
    EXTRACTION_DIR: Path = SCRIPTS_DIR / "ai_extraction"
    PROMPTS_DIR: Path = EXTRACTION_DIR / "prompts"
    CACHE_DIR: Path = EXTRACTION_DIR / ".cache"
    TEMP_DIR: Path = EXTRACTION_DIR / ".temp"
    
    # 网页爬取配置
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # OCR 配置
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Windows 路径，根据实际修改
    ENABLE_OCR: bool = False  # 默认关闭，需要本地安装 Tesseract
    
    # 二维码识别
    ENABLE_QR_CODE: bool = False
    
    # 文件大小限制 (MB)
    MAX_FILE_SIZE: int = 50
    MAX_IMAGE_SIZE: int = 10
    
    # 数据验证配置
    VALIDATE_LINKS: bool = False  # 链接检查可能耗时较长
    DESCRIPTION_MAX_LENGTH: int = 100
    
    # GitHub 配置
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = "hust-open-atom-club/open-source-deadlines"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = EXTRACTION_DIR / ".logs" / "extraction.log"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"
    
    def __init__(self, **data):
        super().__init__(**data)
        # 创建必要的目录
        for dir_path in [self.CACHE_DIR, self.TEMP_DIR, self.LOG_FILE.parent]:
            dir_path.mkdir(parents=True, exist_ok=True)


# 全局配置实例
settings = Settings()

# 数据文件路径
ACTIVITIES_FILE = settings.DATA_DIR / "activities.yml"
COMPETITIONS_FILE = settings.DATA_DIR / "competitions.yml"
CONFERENCES_FILE = settings.DATA_DIR / "conferences.yml"

# 数据文件别名
DATA_FILE_MAP = {
    "activity": ACTIVITIES_FILE,
    "competition": COMPETITIONS_FILE,
    "conference": CONFERENCES_FILE,
}

# 时间相关配置
IANA_TIMEZONES = [
    "Asia/Shanghai",
    "Asia/Beijing",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Asia/Singapore",
    "Asia/Hong_Kong",
    "Asia/Taipei",
    "Asia/Bangkok",
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "America/Denver",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Moscow",
    "UTC",
]

# 支持的文件格式
SUPPORTED_FORMATS = {
    "text": [".txt", ".md"],
    "web": ["http", "https"],
    "document": [".pdf"],
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
}

def print_config_info():
    """打印配置信息"""
    print("\n" + "="*60)
    print("⚙️  系统配置信息")
    print("="*60)
    
    if settings.USE_GITHUB_MODELS:
        print(f"\n✓ AI方案: GitHub Models (免费)")
        print(f"  Token: {settings.GITHUB_TOKEN[:15]}...***")
        print(f"  默认模型: {settings.GITHUB_MODELS_DEFAULT}")
        print(f"  可用模型: {', '.join(settings.GITHUB_MODELS_AVAILABLE)}")
    elif settings.USE_OPENAI_FALLBACK:
        print(f"\n⚠  AI方案: OpenAI (付费备选)")
        print(f"  API Key: {settings.OPENAI_API_KEY[:15]}...***")
        print(f"  模型: {settings.OPENAI_MODEL}")
    else:
        print(f"\n❌ AI方案: 未配置任何AI服务")
        print(f"  将使用规则解析器 (功能受限)")
    
    print(f"\n📁 项目目录: {settings.PROJECT_ROOT}")
    print(f"📊 数据目录: {settings.DATA_DIR}")
    print(f"💾 缓存目录: {settings.CACHE_DIR}")
    print(f"📝 日志文件: {settings.LOG_FILE}")
    print("="*60 + "\n")


def validate_config():
    """验证配置是否正确"""
    print("\n" + "="*60)
    print("🔍 配置验证")
    print("="*60)
    
    if settings.USE_GITHUB_MODELS:
        if not settings.GITHUB_TOKEN:
            print("❌ 已启用GitHub Models但未配置GITHUB_TOKEN")
            return False
        print("✓ GitHub Token已配置 (推荐)")
    
    if settings.USE_OPENAI_FALLBACK:
        if not settings.OPENAI_API_KEY:
            print("❌ 已启用OpenAI但未配置OPENAI_API_KEY")
            return False
        print("✓ OpenAI API Key已配置 (备选)")
    
    if not settings.USE_GITHUB_MODELS and not settings.USE_OPENAI_FALLBACK:
        print("⚠️  未配置任何AI服务，将使用规则解析器")
        print("\n建议配置:")
        print("  1. GITHUB_TOKEN (推荐 - 免费)")
        print("  2. OPENAI_API_KEY (可选 - 付费)")
        return True  # 仍然可以运行，只是功能受限
    
    print("="*60 + "\n")
    return True


if __name__ == "__main__":
    print_config_info()
    validate_config()
    print(f"\n项目根目录: {settings.PROJECT_ROOT}")
    print(f"数据目录: {settings.DATA_DIR}")
    print(f"活动数据文件: {ACTIVITIES_FILE}")
    print(f"竞赛数据文件: {COMPETITIONS_FILE}")
    print(f"会议数据文件: {CONFERENCES_FILE}")
    print(f"缓存目录: {settings.CACHE_DIR}")

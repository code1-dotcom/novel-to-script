"""
config.py — 配置管理模块
管理 API Key、模型选择、路径等全局配置项
"""

from config_bailian import BAILIAN_API_KEY, BAILIAN_BASE_URL

# 模型选择
MODEL_PRIMARY = "qwen-max"     # 主力模型，用于剧本生成和 AI 编辑
MODEL_SECONDARY = "qwen-plus"  # 辅助模型，用于角色提取

# 重试与超时配置
MAX_RETRIES = 3
TIMEOUT_SECONDS = 60

# 路径配置
NOVEL_MATERIAL_DIR = "小说素材"          # 小说素材默认文件夹
OUTPUT_DIR = "output"                    # 输出文件目录
CHARACTER_PROFILES_FILE = "character_profiles.json"  # 角色特征文档文件名
SCREENPLAY_FILE = "screenplay.yaml"      # 最终剧本文件名
CHAPTERS_DIR = "chapters"                # 各章中间产物子目录

# 生成参数
TEMPERATURE_SCRIPT = 0.7    # 剧本生成温度
TEMPERATURE_EXTRACT = 0.3   # 角色提取温度（较低，保证 JSON 格式规范）
MAX_TOKENS_SCRIPT = 4096    # 剧本生成最大 token 数
MAX_TOKENS_EXTRACT = 4096   # 角色提取最大 token 数
MAX_TOKENS_EDIT = 4096      # AI 编辑最大 token 数

# 分段处理参数
MAX_CHUNK_TOKENS = 6000     # 长文本分段处理时每段的最大 token 数
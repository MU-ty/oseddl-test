"""
AI Agent 活动提取系统 - 主入口脚本

用法:
    python main.py <url|file_path|text>
    python main.py https://summer-ospp.ac.cn
    python main.py /path/to/activity.pdf
    python main.py "活动名称是开源之夏，时间是2025年6月到9月..."
"""

import asyncio
import json
import sys
import logging
from pathlib import Path
from typing import Optional

from information_extraction import extract_information
from data_parsing import parse_activity_data
from data_validation import validate_activity_data
from result_feedback import generate_issue_comment
from config import settings

# 配置日志
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


async def main(source: str, output_format: str = "markdown"):
    """
    主处理流程
    
    Args:
        source: 信息源（URL、文件路径或纯文本）
        output_format: 输出格式 ("markdown", "json", "yaml")
    """
    
    print("=" * 60)
    print("🤖 AI 活动信息提取系统")
    print("=" * 60)
    print()
    
    # Step 1: 信息提取
    print("Step 1️⃣ : 信息提取中...")
    print("-" * 60)
    
    extraction_result = await extract_information(source)
    
    if extraction_result.error:
        print(f"❌ 提取失败: {extraction_result.error}")
        return
    
    print(f"✅ 提取成功")
    print(f"   - 提取字符数: {len(extraction_result.extracted_text)}")
    print(f"   - 图片数: {len(extraction_result.extracted_images)}")
    print(f"   - 二维码: {len(extraction_result.extracted_qr_codes)}")
    print()
    
    # Step 2: 数据解析
    print("Step 2️⃣ : 数据解析中...")
    print("-" * 60)
    
    parsed_activity = await parse_activity_data(
        extraction_result.extracted_text,
        use_llm=bool(settings.OPENAI_API_KEY),
    )
    
    print(f"✅ 解析成功")
    print(f"   - 活动名称: {parsed_activity.title}")
    print(f"   - 活动分类: {parsed_activity.category.value}")
    print(f"   - 活动标签: {', '.join(parsed_activity.tags) if parsed_activity.tags else '(无)'}")
    if parsed_activity.events:
        print(f"   - 活动ID: {parsed_activity.events[0].id}")
    print()
    
    # Step 3: 数据验证
    print("Step 3️⃣ : 数据验证中...")
    print("-" * 60)
    
    validation_result = validate_activity_data(parsed_activity)
    
    if validation_result.is_valid:
        print(f"✅ 验证通过")
    else:
        print(f"⚠️  验证警告: {len(validation_result.errors)} 个错误，{len(validation_result.warnings)} 个警告")
        for error in validation_result.errors:
            print(f"   🔴 {error.field}: {error.issue}")
        for warning in validation_result.warnings:
            print(f"   🟡 {warning.field}: {warning.issue}")
    
    print()
    
    # Step 4: 生成结果
    print("Step 4️⃣ : 生成结果中...")
    print("-" * 60)
    print()
    
    # 选择输出格式
    if output_format == "markdown":
        output = generate_issue_comment(
            extraction_result,
            parsed_activity,
            validation_result,
        )
        print(output)
    
    elif output_format == "json":
        output = {
            "extraction": extraction_result.to_dict(),
            "parsed_activity": parsed_activity.to_dict(),
            "validation": validation_result.to_dict(),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    
    elif output_format == "yaml":
        print("解析后的YAML数据:")
        print()
        print(parsed_activity.to_yaml_str())
    
    print()
    print("=" * 60)
    print("✨ 处理完成")
    print("=" * 60)


def print_usage():
    """打印使用说明"""
    
    usage = """
使用方法:
    
    python main.py <source> [--format <format>]
    
参数说明:
    
    <source>
        - URL: 活动官网或宣传文章链接 (https://...)
        - 文件路径: 本地文件路径 (.txt, .pdf, .jpg, .png 等)
        - 纯文本: 直接输入活动信息文本
    
    --format <format>  输出格式 (默认: markdown)
        - markdown: GitHub Issue 评论格式
        - json: JSON 格式
        - yaml: YAML 格式

示例:

    # 从URL提取
    python main.py https://summer-ospp.ac.cn
    
    # 从文件提取
    python main.py ./activity.pdf
    
    # 从文本提取
    python main.py "活动名称：开源之夏，时间：2025年6月-9月"
    
    # 指定输出格式
    python main.py https://example.com --format json
    
环境变量:
    
    OPENAI_API_KEY: OpenAI API密钥（可选，不配置则使用规则解析器）
    
配置文件:
    
    scripts/ai_extraction/config.py 中的 Settings 类
    
"""
    print(usage)


if __name__ == "__main__":
    
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print_usage()
        sys.exit(0)
    
    source = sys.argv[1]
    
    # 解析格式参数
    output_format = "markdown"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            output_format = sys.argv[idx + 1]
    
    # 运行主程序
    try:
        asyncio.run(main(source, output_format))
    except KeyboardInterrupt:
        print("\n⏹️  程序被中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        sys.exit(1)

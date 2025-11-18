"""
增强的工作流提取脚本 - 专为 GitHub Actions 优化
- 提取时间、地点、链接、描述等完整信息
- 更好的错误处理
- 详细的日志输出
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def extract_activity_workflow(input_data: str) -> dict:
    """
    工作流专用的提取函数
    
    Args:
        input_data: URL 或文本输入
    
    Returns:
        包含提取结果的字典
    """
    
    result = {
        "success": False,
        "error": None,
        "comment": "",
        "data": {}
    }
    
    try:
        if not input_data or not input_data.strip():
            result["error"] = "未提供有效的输入（URL或文本）"
            result["comment"] = "❌ 未提供有效的URL或文本\n\n请在命令后提供URL或活动信息，例如:\n`@bot extract https://example.com`"
            return result
        
        logger.info(f"开始提取: {input_data[:50]}...")
        
        # 导入提取模块
        try:
            from information_extraction import InformationExtractor
            from data_parsing import DataParser
            from data_validation import DataValidator
            from result_feedback import generate_issue_comment
            logger.info("✓ 所有模块导入成功")
        except ImportError as e:
            logger.error(f"模块导入失败: {e}")
            result["error"] = f"模块导入失败: {str(e)}"
            result["comment"] = f"❌ 依赖模块缺失\n\n{str(e)}"
            return result
        
        # 第 1 步：信息提取
        logger.info("第1步: 提取信息...")
        extractor = InformationExtractor(enable_ocr=False)
        
        try:
            extraction = await extractor.extract(input_data)
            logger.info(f"✓ 提取成功，文本长度: {len(extraction.extracted_text)}")
            
            if not extraction.extracted_text:
                result["error"] = "无法从输入源提取任何文本"
                result["comment"] = "❌ 提取失败\n\n无法从提供的URL或文本中提取任何内容。\n\n请确保:\n1. URL 可访问\n2. URL 指向的页面包含活动信息\n3. 或提供足够的活动文本描述"
                return result
        
        except Exception as e:
            logger.error(f"提取失败: {e}")
            result["error"] = f"提取失败: {str(e)}"
            result["comment"] = f"❌ 提取失败\n\n{str(e)}"
            return result
        
        # 第 2 步：数据解析
        logger.info("第2步: 解析数据...")
        parser = DataParser(use_github_models=True)
        
        try:
            activity = await parser.parse(extraction.extracted_text)
            logger.info(f"✓ 解析成功: {activity.title}")
        
        except Exception as e:
            logger.error(f"解析失败: {e}")
            result["error"] = f"解析失败: {str(e)}"
            result["comment"] = f"❌ 数据解析失败\n\n{str(e)}\n\n请检查提取的内容是否为有效的活动信息。"
            return result
        
        # 第 3 步：数据验证
        logger.info("第3步: 验证数据...")
        validator = DataValidator()
        
        try:
            validation = validator.validate(activity)
            logger.info(f"✓ 验证完成: {len(validation.passed)} 通过, {len(validation.warnings)} 警告")
        
        except Exception as e:
            logger.error(f"验证失败: {e}")
            # 验证失败不是致命错误，继续处理
            validation = None
        
        # 第 4 步：生成回复
        logger.info("第4步: 生成回复...")
        try:
            comment = generate_issue_comment(extraction, activity, validation)
            logger.info("✓ 回复生成成功")
        
        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            # 生成默认回复
            comment = format_default_comment(activity, extraction)
        
        # 成功！
        result["success"] = True
        result["comment"] = comment
        result["data"] = {
            "title": activity.title,
            "description": activity.description,
            "category": activity.category.value if hasattr(activity.category, 'value') else str(activity.category),
            "tags": activity.tags,
            "events": [e.to_dict() for e in activity.events] if activity.events else [],
            "source_url": input_data if input_data.startswith('http') else None,
            "source_text": extraction.extracted_text[:200] + "..." if len(extraction.extracted_text) > 200 else extraction.extracted_text
        }
        
        logger.info("✓ 完成！")
    
    except Exception as e:
        logger.exception(f"未预期的错误: {e}")
        result["error"] = str(e)
        result["comment"] = f"❌ 出现未预期的错误\n\n```\n{str(e)}\n```"
    
    return result


def format_default_comment(activity, extraction) -> str:
    """生成默认的回复评论"""
    
    comment = f"""✅ **活动信息提取成功**

📌 **活动标题:** {activity.title}

📂 **分类:** {activity.category.value if hasattr(activity.category, 'value') else activity.category}

📝 **描述:** 
{activity.description[:200] + '...' if len(activity.description) > 200 else activity.description}

🏷️ **标签:** {', '.join(activity.tags) if activity.tags else '(无)'}

⏰ **时间安排:**
"""
    
    if activity.events:
        for event in activity.events[:3]:  # 最多显示3个事件
            comment += f"\n- 年份: {event.year}\n"
            if event.date:
                comment += f"  日期: {event.date}\n"
            if event.place:
                comment += f"  地点: {event.place}\n"
            if event.timeline:
                comment += f"  {len(event.timeline)} 个时间节点\n"
    else:
        comment += "\n(未识别到具体时间)"
    
    comment += f"""

📊 **提取统计:**
- 原始文本长度: {len(extraction.extracted_text)} 字符
- 提取时间: {extraction.extraction_timestamp}
- 源类型: {extraction.source_type.value if hasattr(extraction.source_type, 'value') else extraction.source_type}

---
*由 GitHub Actions 自动提取*
"""
    
    return comment


async def main():
    """主函数"""
    
    # 从命令行参数或环境变量获取输入
    input_data = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not input_data:
        print(json.dumps({
            "success": False,
            "error": "未提供输入参数"
        }, ensure_ascii=False, indent=2))
        return
    
    # 执行提取
    result = await extract_activity_workflow(input_data)
    
    # 输出结果为 JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

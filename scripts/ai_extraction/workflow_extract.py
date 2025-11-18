import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    import logging
    import os
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # 检查环境变量
    github_token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_MODELS_TOKEN')
    if github_token:
        logger.info(f"✅ 检测到 GITHUB_TOKEN (长度: {len(github_token)})")
    else:
        logger.warning("⚠️ 未检测到 GITHUB_TOKEN，将使用纯规则提取")
    
    input_data = sys.argv[1] if len(sys.argv) > 1 else None
    result = {"success": False, "error": None, "comment": ""}
    
    try:
        if not input_data or not input_data.strip():
            result["comment"] = "❌ 未提供URL或文本"
            print(json.dumps(result, ensure_ascii=False))
            return
        
        logger.info(f"📥 输入数据: {input_data[:100]}...")
        
        from information_extraction import InformationExtractor
        from enhanced_parser import EnhancedDataParser
        from data_validation import DataValidator
        from result_feedback import generate_issue_comment
        
        # 初始化 extraction（后续会被覆盖）
        extraction = None
        extracted_text = None
        
        # 如果是 URL，尝试提取（启用 OCR）
        if input_data.startswith('http'):
            try:
                logger.info(f"🌐 开始提取URL内容: {input_data}")
                extractor = InformationExtractor(enable_ocr=True)
                extraction = await extractor.extract(input_data)
                extracted_text = extraction.extracted_text
                logger.info(f"✅ 提取到文本长度: {len(extracted_text) if extracted_text else 0}")
            except Exception as e:
                logger.error(f"⚠️ URL提取失败: {e}")
                pass
        
        # 如果提取失败或输入是文本，使用简单提取
        if not extracted_text:
            extracted_text = input_data if not input_data.startswith('http') else ""
        
        if not extracted_text or (isinstance(extracted_text, str) and len(extracted_text.strip()) < 10):
            result["comment"] = "❌ 无法提取足够的内容"
            print(json.dumps(result, ensure_ascii=False))
            return
        
        # 解析活动数据
        logger.info("🔍 开始解析活动数据...")
        parser = EnhancedDataParser()
        activity = await parser.parse(extracted_text, source_url=input_data if input_data.startswith('http') else None)
        logger.info(f"✅ 解析完成: {activity.title}")
        
        # 验证数据
        validator = DataValidator()
        validation = validator.validate(activity)
        
        # 生成回复
        if extraction:
            comment = generate_issue_comment(extraction, activity, validation)
        else:
            # 如果没有 extraction 对象，生成简单的回复
            comment = f"""✅ 活动信息提取成功

📌 **活动标题:** {activity.title}

📂 **分类:** {activity.category}

📝 **描述:** {activity.description[:200] if activity.description else '(无)'}

🏷️ **标签:** {', '.join(activity.tags) if activity.tags else '(无)'}

"""
            if activity.events:
                comment += "\n⏰ **时间安排:**\n"
                for event in activity.events[:3]:
                    if event.date:
                        comment += f"- 日期: {event.date}\n"
                    if event.place:
                        comment += f"- 地点: {event.place}\n"
        
        result["success"] = True
        result["comment"] = comment
        print(json.dumps(result, ensure_ascii=False))
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"❌ 处理失败: {e}")
        logger.error(f"详细错误:\n{error_detail}")
        
        result["error"] = str(e)
        result["comment"] = f"❌ 处理失败\n\n**错误信息:** {str(e)}\n\n请检查:\n1. 输入URL是否正确\n2. GITHUB_TOKEN是否已配置\n3. 查看Actions日志获取详细信息"
        print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    input_data = sys.argv[1] if len(sys.argv) > 1 else None
    result = {"success": False, "error": None, "comment": ""}
    
    try:
        if not input_data or not input_data.strip():
            result["comment"] = "❌ 未提供URL或文本"
            print(json.dumps(result, ensure_ascii=False))
            return
        
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
                extractor = InformationExtractor(enable_ocr=True)
                extraction = await extractor.extract(input_data)
                extracted_text = extraction.extracted_text
            except:
                pass
        
        # 如果提取失败或输入是文本，使用简单提取
        if not extracted_text:
            extracted_text = input_data if not input_data.startswith('http') else ""
        
        if not extracted_text or (isinstance(extracted_text, str) and len(extracted_text.strip()) < 10):
            result["comment"] = "❌ 无法提取足够的内容"
            print(json.dumps(result, ensure_ascii=False))
            return
        
        # 解析活动数据
        parser = EnhancedDataParser()
        activity = await parser.parse(extracted_text, source_url=input_data if input_data.startswith('http') else None)
        
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
        result["error"] = str(e)
        result["comment"] = f"❌ 错误: {str(e)}"
        print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())

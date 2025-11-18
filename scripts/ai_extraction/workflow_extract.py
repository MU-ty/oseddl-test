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
        
        extractor = InformationExtractor(enable_ocr=False)
        extraction = await extractor.extract(input_data)
        
        if not extraction.extracted_text:
            result["comment"] = "❌ 无法提取内容"
            print(json.dumps(result, ensure_ascii=False))
            return
        
        parser = EnhancedDataParser()
        activity = await parser.parse(extraction.extracted_text, source_url=input_data if input_data.startswith('http') else None)
        
        validator = DataValidator()
        validation = validator.validate(activity)
        
        comment = generate_issue_comment(extraction, activity, validation)
        
        result["success"] = True
        result["comment"] = comment
        print(json.dumps(result, ensure_ascii=False))
    
    except Exception as e:
        result["error"] = str(e)
        result["comment"] = f"❌ 错误: {str(e)}"
        print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())

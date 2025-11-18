#!/usr/bin/env python3
"""
超简化工作流提取脚本 - 只输出 JSON，不输出任何日志
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))


async def main():
    """主函数"""
    
    input_data = sys.argv[1] if len(sys.argv) > 1 else None
    
    result = {
        "success": False,
        "error": None,
        "comment": ""
    }
    
    try:
        # 检查输入
        if not input_data or not input_data.strip():
            result["error"] = "No input"
            result["comment"] = "❌ 未提供URL或文本"
            print(json.dumps(result, ensure_ascii=False))
            return
        
        # 导入模块
        from information_extraction import InformationExtractor
        from data_parsing import DataParser
        from data_validation import DataValidator
        from result_feedback import generate_issue_comment
        
        # 提取
        extractor = InformationExtractor(enable_ocr=False)
        extraction = await extractor.extract(input_data)
        
        if not extraction.extracted_text:
            result["error"] = "No text"
            result["comment"] = "❌ 无法提取内容"
            print(json.dumps(result, ensure_ascii=False))
            return
        
        # 解析
        parser = DataParser(use_github_models=True)
        activity = await parser.parse(extraction.extracted_text)
        
        # 验证
        validator = DataValidator()
        validation = validator.validate(activity)
        
        # 生成回复
        comment = generate_issue_comment(extraction, activity, validation)
        
        # 成功
        result["success"] = True
        result["comment"] = comment
        print(json.dumps(result, ensure_ascii=False))
    
    except Exception as e:
        result["error"] = str(e)
        result["comment"] = f"❌ 错误: {str(e)}"
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

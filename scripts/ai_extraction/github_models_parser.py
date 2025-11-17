"""
GitHub Models API 集成
使用GitHub免费的AI模型(Copilot)进行数据解析
不需要OpenAI API密钥
"""

import logging
import json
import re
from typing import Optional

logger = logging.getLogger(__name__)


class GitHubModelsParser:
    """
    GitHub Models 解析器
    
    使用GitHub免费的AI模型，无需额外成本
    支持的模型:
    - gpt-4o (免费额度充足)
    - claude-3-5-sonnet (免费额度)
    - phi-4
    - llama-3.1-405b
    等其他GitHub提供的模型
    """
    
    def __init__(self, github_token: str, model: str = "gpt-4o"):
        """
        初始化GitHub Models解析器
        
        Args:
            github_token: GitHub Personal Access Token (需要 repo scope)
            model: 使用的模型名称，默认gpt-4o
        """
        self.github_token = github_token
        self.model = model
        self.api_base = "https://models.inference.ai.azure.com"
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "Content-Type": "application/json",
        }
        
        if not github_token:
            logger.warning("⚠️ 未配置 GITHUB_TOKEN，无法使用GitHub Models")
        else:
            logger.info(f"✓ GitHub Models 已初始化，使用模型: {model}")
    
    async def parse(self, extracted_text: str) -> dict:
        """
        使用GitHub Models解析活动信息
        
        Args:
            extracted_text: 提取的原始文本
        
        Returns:
            dict: 解析后的活动数据
        """
        
        if not self.github_token:
            logger.error("❌ GitHub Token未配置")
            return {}
        
        try:
            import aiohttp
            
            # 构建提示词
            prompt = self._build_prompt(extracted_text)
            
            # 调用GitHub Models API
            async with aiohttp.ClientSession() as session:
                payload = {
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "model": self.model,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                }
                
                async with session.post(
                    f"{self.api_base}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=30,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        return self._parse_response(content)
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ GitHub Models API错误: {response.status} - {error_text}")
                        return {}
        
        except Exception as e:
            logger.error(f"❌ 调用GitHub Models失败: {e}")
            return {}
    
    def _build_prompt(self, extracted_text: str) -> str:
        """构建提示词"""
        
        return f"""
你是一个开源活动信息提取专家。请根据以下提取的文本，解析活动信息并返回JSON格式的数据。

## 输入文本：
{extracted_text[:3000]}

## 任务：
请从上述文本中提取以下信息，并返回有效的JSON（不包含markdown代码块）：

{{
    "title": "活动官方名称",
    "description": "一句话描述（≤100字）",
    "category": "conference/competition/activity",
    "tags": ["标签1", "标签2"],
    "events": [
        {{
            "year": 2025,
            "id": "activity-2025",
            "link": "https://example.com",
            "timezone": "Asia/Shanghai",
            "date": "2025年6月-9月",
            "place": "线上或地点",
            "timeline": [
                {{"deadline": "2025-06-04T18:00:00", "comment": "说明"}}
            ]
        }}
    ]
}}

## 重要规则：
- ID格式：小写字母、数字、连字符 (例如: oscp-2025)
- 时间格式：ISO 8601 (YYYY-MM-DDTHH:mm:ss)
- 时区：IANA标准 (如: Asia/Shanghai)
- 描述：不超过100字符
- 返回有效的JSON，不要包含任何markdown标记

现在请直接返回JSON：
"""
    
    def _parse_response(self, response_text: str) -> dict:
        """解析API响应"""
        
        try:
            # 清理响应
            response_text = response_text.strip()
            
            # 移除可能的markdown标记
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # 解析JSON
            data = json.loads(response_text)
            logger.info(f"✓ GitHub Models 解析成功: {data.get('title', 'Unknown')}")
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON解析失败: {e}")
            logger.debug(f"响应内容: {response_text[:200]}")
            return {}


# 便捷函数
async def parse_with_github_models(
    extracted_text: str,
    github_token: str,
    model: str = "gpt-4o"
) -> dict:
    """
    使用GitHub Models解析活动数据
    
    Args:
        extracted_text: 提取的原始文本
        github_token: GitHub Personal Access Token
        model: 模型名称
    
    Returns:
        dict: 解析后的活动数据
    """
    
    parser = GitHubModelsParser(github_token, model)
    return await parser.parse(extracted_text)


if __name__ == "__main__":
    print("""
    GitHub Models API 集成模块
    
    使用方法:
    1. 获取 GitHub Token: https://github.com/settings/tokens
    2. 设置环境变量: export GITHUB_TOKEN=your-token
    3. 使用代码:
    
        import asyncio
        from github_models_parser import parse_with_github_models
        
        async def main():
            result = await parse_with_github_models(
                extracted_text="活动信息...",
                github_token="ghp_...",
                model="gpt-4o"  # 或其他模型
            )
            print(result)
        
        asyncio.run(main())
    
    支持的免费模型:
    - gpt-4o (推荐)
    - claude-3-5-sonnet
    - phi-4
    - llama-3.1-405b
    
    GitHub Models 免费额度:
    - 每日请求限制: 根据模型而定
    - 无需信用卡
    - 完全免费
    
    参考文档: https://docs.github.com/en/github-models/prototyping-with-ai-models
    """)

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
                    elif response.status == 401:
                        error_text = await response.text()
                        logger.error(f"❌ GitHub Models 认证失败 (401)")
                        logger.error(f"错误详情: {error_text}")
                        logger.error(f"请检查: 1) GITHUB_TOKEN 是否已设置 2) Token 是否有效 3) Token 是否有 'models' 权限")
                        return {"error": "认证失败，请检查 GITHUB_TOKEN 配置"}
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ GitHub Models API错误: {response.status}")
                        logger.error(f"错误详情: {error_text}")
                        return {"error": f"API调用失败: {response.status}"}
        
        except Exception as e:
            logger.error(f"❌ 调用GitHub Models失败: {e}")
            return {}
    
    def _build_prompt(self, extracted_text: str) -> str:
        """构建提示词"""
        
        return f"""
你是一个专业的开源活动信息提取专家。请仔细分析以下文本，提取准确的活动信息。

## 输入文本：
{extracted_text[:3000]}

## 提取规则：

1. **活动标题** (title):
   - 提取官方完整名称（中文或英文）
   - 不要添加年份后缀除非原文中有
   - 例如: "开源之夏", "Google Summer of Code"

2. **活动描述** (description):
   - 简洁描述活动性质和目的（50-100字）
   - 重点说明活动是什么、面向谁
   - 避免营销性语言

3. **活动分类** (category):
   - conference: 会议、峰会、论坛
   - competition: 竞赛、黑客松、编程比赛
   - activity: 培训、Meetup、Workshop、社区活动

4. **标签** (tags):
   - 提取3-5个关键词
   - 包含技术栈、领域、特点
   - 例如: ["开源", "AI", "学生", "暑期"]

5. **时间信息** (events.timeline):
   - 提取所有重要时间节点
   - 时间格式: YYYY-MM-DDTHH:mm:ss
   - 如果只有日期没有时间，使用 00:00:00
   - deadline 填写精确时间，comment 填写说明（如"报名截止"、"活动开始"）

6. **地点** (place):
   - 线上活动写"线上"
   - 线下活动写城市名或具体地点
   - 混合活动写"线上+线下"

7. **ID生成** (id):
   - 格式: 活动英文简称-年份
   - 全小写，用连字符分隔
   - 例如: "ospp-2025", "gsoc-2025"

## 输出格式（纯JSON，无markdown标记）：

{{
    "title": "活动官方完整名称",
    "description": "简洁描述活动性质和目的",
    "category": "conference/competition/activity",
    "tags": ["标签1", "标签2", "标签3"],
    "events": [
        {{
            "year": 2025,
            "id": "activity-2025",
            "link": "https://活动官网",
            "timezone": "Asia/Shanghai",
            "date": "YYYY-MM-DD 或 时间范围描述",
            "place": "地点",
            "timeline": [
                {{"deadline": "2025-06-04T18:00:00", "comment": "报名截止"}},
                {{"deadline": "2025-07-01T00:00:00", "comment": "活动开始"}}
            ]
        }}
    ]
}}

请直接返回JSON，不要有任何其他文字或标记：
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

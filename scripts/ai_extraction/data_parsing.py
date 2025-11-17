"""
数据解析模块 - 使用LLM将非结构化文本转换为结构化活动数据

支持：
- 活动名称、描述提取
- 活动类别判断
- 关键时间点识别
- 地点信息提取
- 标签自动生成
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

try:
    from langchain_openai import ChatOpenAI
    from langchain.prompts import PromptTemplate
    from langchain.output_parsers import JSONOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

try:
    from github_models_parser import GitHubModelsParser
    GITHUB_MODELS_AVAILABLE = True
except ImportError:
    GITHUB_MODELS_AVAILABLE = False

from config import settings

logger = logging.getLogger(__name__)


class ActivityCategory(str, Enum):
    """活动分类"""
    CONFERENCE = "conference"  # 会议
    COMPETITION = "competition"  # 竞赛
    ACTIVITY = "activity"  # 活动


@dataclass
class TimelineEvent:
    """时间线事件"""
    deadline: str  # ISO 8601 格式
    comment: str
    
    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ActivityEvent:
    """单个年份的活动事件"""
    year: int
    id: str
    link: str
    timeline: List[TimelineEvent] = field(default_factory=list)
    timezone: str = "Asia/Shanghai"
    date: str = ""
    place: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timeline'] = [t.to_dict() for t in self.timeline]
        return data


@dataclass
class ParsedActivity:
    """解析后的活动数据"""
    title: str
    description: str
    category: ActivityCategory
    tags: List[str] = field(default_factory=list)
    events: List[ActivityEvent] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['category'] = self.category.value
        data['events'] = [e.to_dict() for e in self.events]
        return data
    
    def to_yaml_str(self) -> str:
        """转换为YAML格式字符串"""
        import yaml
        data = self.to_dict()
        return yaml.dump([data], allow_unicode=True, sort_keys=False, default_flow_style=False)


class DataParser:
    """数据解析器 - 使用LLM进行智能解析"""
    
    def __init__(self, model: str = None, use_github_models: bool = False, github_token: str = None, use_cache: bool = True):
        """
        初始化解析器
        
        Args:
            model: LLM模型名称，默认使用配置中的模型
            use_github_models: 是否使用GitHub免费模型（推荐）
            github_token: GitHub Personal Access Token（如果使用GitHub Models）
            use_cache: 是否使用缓存
        """
        self.use_github_models = use_github_models
        self.github_token = github_token or settings.GITHUB_TOKEN
        self.model = model or settings.OPENAI_MODEL
        self.use_cache = use_cache
        self.llm = None
        self.github_parser = None
        
        # 优先使用GitHub Models（免费）
        if use_github_models and self.github_token and GITHUB_MODELS_AVAILABLE:
            self.github_parser = GitHubModelsParser(self.github_token, model="gpt-4o")
            logger.info(f"✓ 使用GitHub免费模型（gpt-4o）")
        
        # 其次使用OpenAI（需要API密钥）
        elif LANGCHAIN_AVAILABLE and settings.OPENAI_API_KEY:
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            logger.info(f"✓ 使用OpenAI模型: {self.model}")
        
        else:
            logger.info("⚠️ 未配置任何LLM，将使用规则解析器")
    
    async def parse(self, extracted_text: str) -> ParsedActivity:
        """
        解析提取的文本
        
        Args:
            extracted_text: 提取的原始文本
        
        Returns:
            ParsedActivity: 解析后的活动数据
        """
        
        # 优先使用GitHub Models
        if self.github_parser:
            try:
                logger.info("使用GitHub Models解析...")
                result_dict = await self.github_parser.parse(extracted_text)
                if result_dict:
                    return self._dict_to_activity(result_dict)
            except Exception as e:
                logger.warning(f"⚠️ GitHub Models解析失败: {e}，降级到规则解析器")
        
        # 其次使用OpenAI
        if self.llm:
            try:
                logger.info("使用OpenAI LLM解析...")
                prompt = self._build_prompt(extracted_text)
                response = self.llm.invoke(prompt)
                activity = self._parse_response(response.content)
                logger.info(f"✓ 解析成功: {activity.title}")
                return activity
            
            except Exception as e:
                logger.error(f"✗ 解析失败: {e}")
                return self._create_fallback_activity(extracted_text)
        
        # 降级到规则解析器
        return self._create_fallback_activity(extracted_text)
    
    def _build_prompt(self, extracted_text: str) -> str:
        """构建LLM提示词"""
        
        # 从文本中提取可能的活动名称
        activity_hint = self._extract_activity_hint(extracted_text)
        
        prompt = f"""
你是一个开源活动信息提取专家。请根据以下提取的文本，解析活动信息并返回JSON格式的数据。

## 输入文本：
{extracted_text[:3000]}

## 任务：
请从上述文本中提取以下信息：

1. **title**: 活动官方名称（例如："开源之夏"）
2. **description**: 一句话描述活动，不超过100字
3. **category**: 活动分类，必须是以下之一：
   - "conference": 如果是学术会议、技术峰会
   - "competition": 如果是编程竞赛、创意大赛、集训营
   - "activity": 如果是线上讲座、workshop、meetup等
4. **tags**: 活动标签数组，选择3-5个最相关的标签（字符串数组）
5. **events**: 事件数组，每个事件需要以下字段：
   - year: 活动年份（数字）
   - id: 全局唯一ID，格式: {activity_hint.lower()}-yyyy（小写，字母数字和连字符）
   - link: 活动官方网址
   - timezone: IANA时区标准名称（例如："Asia/Shanghai"）
   - date: 人类可读的日期范围（例如："2025年4月30日 - 9月30日"）
   - place: 地点信息（例如："中国，上海"或"线上"）
   - timeline: 时间线事件数组，每项包含：
     * deadline: ISO 8601格式的截止时间（YYYY-MM-DDTHH:mm:ss）
     * comment: 事件说明（例如："报名开始"、"提交截止"）

## 重要规则：
- ID必须是小写字母、数字和连字符的组合
- 时间必须使用ISO 8601格式: YYYY-MM-DDTHH:mm:ss
- 时区必须是有效的IANA时区名称
- 如果文本中没有某个字段，设置为空字符串或空数组
- description字段不能超过100字
- 返回有效的JSON格式

## 响应格式：
请返回以下JSON格式（不包含markdown代码块）：
{{
    "title": "...",
    "description": "...",
    "category": "...",
    "tags": [...],
    "events": [
        {{
            "year": ...,
            "id": "...",
            "link": "...",
            "timezone": "...",
            "date": "...",
            "place": "...",
            "timeline": [
                {{"deadline": "...", "comment": "..."}}
            ]
        }}
    ]
}}

现在请直接返回JSON，不要有任何其他文本：
"""
        return prompt
    
    def _extract_activity_hint(self, text: str) -> str:
        """从文本中提取活动名称提示"""
        # 尝试在文本开头找到活动名称
        lines = text.split('\n')
        for line in lines[:10]:
            if len(line.strip()) > 2 and len(line.strip()) < 100:
                return line.strip()
        
        # 如果没找到，使用第一个大写单词
        words = text.split()
        for word in words:
            if word and word[0].isupper():
                return word
        
        return "activity"
    
    def _parse_response(self, response_text: str) -> ParsedActivity:
        """解析LLM响应"""
        
        # 清理响应文本
        response_text = response_text.strip()
        
        # 尝试提取JSON
        try:
            # 如果响应包含markdown代码块，提取JSON
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text
            
            data = json.loads(json_str)
            
            # 转换为ParsedActivity对象
            return self._dict_to_activity(data)
        
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"✗ JSON解析失败: {e}")
            logger.debug(f"响应内容: {response_text[:500]}")
            return self._create_fallback_activity(response_text)
    
    def _dict_to_activity(self, data: Dict[str, Any]) -> ParsedActivity:
        """将字典转换为ParsedActivity对象"""
        
        # 解析分类
        category_str = data.get('category', 'activity').lower()
        try:
            category = ActivityCategory(category_str)
        except ValueError:
            category = ActivityCategory.ACTIVITY
        
        # 解析事件
        events = []
        for event_data in data.get('events', []):
            try:
                timeline = [
                    TimelineEvent(
                        deadline=t['deadline'],
                        comment=t['comment']
                    )
                    for t in event_data.get('timeline', [])
                ]
                
                event = ActivityEvent(
                    year=int(event_data.get('year', 0)),
                    id=event_data.get('id', ''),
                    link=event_data.get('link', ''),
                    timezone=event_data.get('timezone', 'Asia/Shanghai'),
                    date=event_data.get('date', ''),
                    place=event_data.get('place', ''),
                    timeline=timeline,
                )
                events.append(event)
            except Exception as e:
                logger.warning(f"⚠ 事件解析失败: {e}")
                continue
        
        return ParsedActivity(
            title=data.get('title', ''),
            description=data.get('description', ''),
            category=category,
            tags=data.get('tags', []),
            events=events,
        )
    
    def _create_fallback_activity(self, text: str) -> ParsedActivity:
        """创建后备活动数据"""
        
        # 尝试从文本中提取基本信息
        title = self._extract_activity_hint(text)
        
        # 从文本中提取年份
        year_match = re.search(r'202\d', text)
        year = int(year_match.group()) if year_match else datetime.now().year
        
        # 生成ID
        id_str = f"{title.lower()}-{year}"
        id_str = re.sub(r'[^a-z0-9\-]', '-', id_str)
        id_str = re.sub(r'-+', '-', id_str).strip('-')
        
        event = ActivityEvent(
            year=year,
            id=id_str,
            link="",
            timezone="Asia/Shanghai",
            date="",
            place="",
            timeline=[],
        )
        
        return ParsedActivity(
            title=title,
            description="",
            category=ActivityCategory.ACTIVITY,
            tags=[],
            events=[event],
        )


class SimpleDataParser(DataParser):
    """简单数据解析器 - 不依赖LLM，基于规则和正则表达式"""
    
    async def parse(self, extracted_text: str) -> ParsedActivity:
        """基于规则的解析"""
        
        logger.info("使用简单解析器处理文本...")
        
        try:
            return self._parse_with_rules(extracted_text)
        except Exception as e:
            logger.error(f"✗ 解析失败: {e}")
            return self._create_fallback_activity(extracted_text)
    
    def _parse_with_rules(self, text: str) -> ParsedActivity:
        """基于规则的解析逻辑"""
        
        # 提取标题
        title = self._extract_title(text)
        
        # 提取描述
        description = self._extract_description(text)
        
        # 判断分类
        category = self._detect_category(text)
        
        # 提取标签
        tags = self._extract_tags(text, category)
        
        # 提取年份
        year = self._extract_year(text)
        
        # 提取时间线
        timeline = self._extract_timeline(text)
        
        # 提取地点
        place = self._extract_place(text)
        
        # 提取链接
        link = self._extract_link(text)
        
        # 生成ID
        id_str = self._generate_id(title, year)
        
        # 生成日期范围
        date_str = self._generate_date_range(timeline)
        
        event = ActivityEvent(
            year=year,
            id=id_str,
            link=link,
            timezone="Asia/Shanghai",
            date=date_str,
            place=place,
            timeline=timeline,
        )
        
        return ParsedActivity(
            title=title,
            description=description,
            category=category,
            tags=tags,
            events=[event],
        )
    
    def _extract_title(self, text: str) -> str:
        """提取标题"""
        lines = text.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 5 and len(line) < 100:
                return line
        return "活动"
    
    def _extract_description(self, text: str) -> str:
        """提取描述"""
        # 查找第二行或包含"描述"的行
        lines = text.split('\n')
        for line in lines:
            if '描述' in line or '简介' in line:
                # 获取该行之后的内容
                idx = lines.index(line)
                if idx + 1 < len(lines):
                    desc = lines[idx + 1].strip()
                    return desc[:100]
        
        # 如果没找到，使用文本的第二行
        if len(lines) > 1:
            return lines[1].strip()[:100]
        
        return ""
    
    def _detect_category(self, text: str) -> ActivityCategory:
        """检测活动分类"""
        text_lower = text.lower()
        
        conference_keywords = ['会议', 'conference', 'summit', 'summit', 'congress', 'forum']
        competition_keywords = ['竞赛', 'competition', 'hackathon', '黑客松', '集训', '夏令营', 'camp']
        
        for kw in conference_keywords:
            if kw in text_lower:
                return ActivityCategory.CONFERENCE
        
        for kw in competition_keywords:
            if kw in text_lower:
                return ActivityCategory.COMPETITION
        
        return ActivityCategory.ACTIVITY
    
    def _extract_tags(self, text: str, category: ActivityCategory) -> List[str]:
        """提取标签"""
        tags = []
        
        # 基于分类的默认标签
        if category == ActivityCategory.CONFERENCE:
            if '开源' in text:
                tags.append('开源')
        elif category == ActivityCategory.COMPETITION:
            if '开源' in text:
                tags.append('开源')
        
        # 查找其他关键词
        keywords = ['AI', 'Python', 'JavaScript', 'Go', 'Rust', 'Linux', '编程', '技术']
        for kw in keywords:
            if kw in text and kw not in tags:
                tags.append(kw)
        
        return tags[:5]  # 限制5个标签
    
    def _extract_year(self, text: str) -> int:
        """提取年份"""
        match = re.search(r'202\d', text)
        if match:
            return int(match.group())
        return datetime.now().year
    
    def _extract_timeline(self, text: str) -> List[TimelineEvent]:
        """提取时间线"""
        timeline = []
        
        # 查找所有日期模式
        date_pattern = r'(\d{4})[/-]?(\d{1,2})[/-]?(\d{1,2})'
        matches = re.finditer(date_pattern, text)
        
        for match in matches:
            year, month, day = match.groups()
            deadline = f"{year}-{month.zfill(2)}-{day.zfill(2)}T00:00:00"
            
            # 查找该日期附近的说明
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]
            
            comment = self._extract_comment_from_context(context)
            
            timeline.append(TimelineEvent(
                deadline=deadline,
                comment=comment,
            ))
        
        return timeline
    
    def _extract_comment_from_context(self, context: str) -> str:
        """从上下文中提取事件说明"""
        # 查找常见的关键词
        keywords = {
            '报名': '报名开始',
            '截止': '报名截止',
            '提交': '提交截止',
            '开始': '活动开始',
            '结束': '活动结束',
            '申请': '申请截止',
        }
        
        for keyword, comment in keywords.items():
            if keyword in context:
                return comment
        
        return "关键时间点"
    
    def _extract_place(self, text: str) -> str:
        """提取地点"""
        if '线上' in text or 'online' in text.lower():
            return '线上'
        
        # 查找常见城市
        cities = ['北京', '上海', '深圳', '杭州', '西安', '南京', '成都']
        for city in cities:
            if city in text:
                return f"中国，{city}"
        
        return "线上"
    
    def _extract_link(self, text: str) -> str:
        """提取链接"""
        url_pattern = r'https?://[^\s]+'
        match = re.search(url_pattern, text)
        if match:
            return match.group()
        return ""
    
    def _generate_id(self, title: str, year: int) -> str:
        """生成ID"""
        id_str = f"{title.lower()}-{year}"
        id_str = re.sub(r'[^a-z0-9\-]', '-', id_str)
        id_str = re.sub(r'-+', '-', id_str).strip('-')
        return id_str
    
    def _generate_date_range(self, timeline: List[TimelineEvent]) -> str:
        """生成日期范围"""
        if not timeline:
            return ""
        
        # 使用第一个和最后一个时间点
        first = timeline[0].deadline
        last = timeline[-1].deadline if len(timeline) > 1 else first
        
        try:
            first_date = datetime.fromisoformat(first.replace('Z', '+00:00'))
            last_date = datetime.fromisoformat(last.replace('Z', '+00:00'))
            
            if first_date == last_date:
                return first_date.strftime("%Y年%m月%d日")
            else:
                return f"{first_date.strftime('%Y年%m月%d日')} - {last_date.strftime('%m月%d日')}"
        
        except Exception:
            return ""


# 便捷函数
async def parse_activity_data(
    extracted_text: str,
    use_llm: bool = True,
) -> ParsedActivity:
    """
    快速解析活动数据
    
    Args:
        extracted_text: 提取的原始文本
        use_llm: 是否使用LLM（默认True，如果API不可用则自动降级）
    
    Returns:
        ParsedActivity: 解析后的活动数据
    """
    
    if use_llm and settings.OPENAI_API_KEY:
        parser = DataParser()
    else:
        logger.info("使用规则解析器")
        parser = SimpleDataParser()
    
    return await parser.parse(extracted_text)


if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            text = sys.argv[1]
            activity = await parse_activity_data(text)
            print(activity.to_yaml_str())
        else:
            print("用法: python data_parsing.py <text>")
    
    asyncio.run(main())

"""
增强型数据解析器 - 规则 + LLM 混合提取
优先使用正则表达式提取时间、地点、链接等结构化数据
然后使用 LLM 补充描述、标签等非结构化数据
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class TimelineEvent:
    deadline: str
    comment: str
    
    def to_dict(self) -> Dict:
        return {"deadline": self.deadline, "comment": self.comment}

@dataclass
class ActivityEvent:
    year: int
    id: str
    link: str
    timeline: List[TimelineEvent] = field(default_factory=list)
    timezone: str = "Asia/Shanghai"
    date: str = ""
    place: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "year": self.year,
            "id": self.id,
            "link": self.link,
            "timeline": [t.to_dict() for t in self.timeline],
            "timezone": self.timezone,
            "date": self.date,
            "place": self.place
        }

@dataclass
class ParsedActivity:
    title: str
    description: str
    category: str
    tags: List[str] = field(default_factory=list)
    events: List[ActivityEvent] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "events": [e.to_dict() for e in self.events]
        }

class EnhancedDataParser:
    """增强的数据解析器 - 规则 + LLM"""
    
    def __init__(self):
        self.llm = None
        try:
            from github_models_parser import GitHubModelsParser
            from config import settings
            self.llm = GitHubModelsParser(settings.GITHUB_TOKEN, model="gpt-4o")
        except:
            pass
    
    def extract_time_info(self, text: str) -> Tuple[Optional[str], List[str]]:
        """使用正则表达式提取时间信息"""
        
        # 匹配 "2025年11月11日 09:30-11:30"
        patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日[，,\s]*(\d{1,2}):(\d{2})\s*[-~]\s*(\d{1,2}):(\d{2})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})\s*(\d{1,2}):(\d{2})\s*[-~]\s*(\d{1,2}):(\d{2})',
        ]
        
        timeline = []
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) >= 8:
                    year, month, day, h1, m1, h2, m2 = match.groups()[:7]
                    date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    time_str = f"{h1.zfill(2)}:{m1.zfill(2)}-{h2.zfill(2)}:{m2.zfill(2)}"
                    
                    timeline.append(TimelineEvent(
                        deadline=f"{year}-{month.zfill(2)}-{day.zfill(2)}T{h1.zfill(2)}:{m1.zfill(2)}:00Z",
                        comment=f"事件时间: {time_str}"
                    ))
                    
                    return date_str, timeline
        
        return None, []
    
    def extract_place_info(self, text: str) -> Optional[str]:
        """使用正则表达式提取地点信息"""
        
        patterns = [
            r'地点[：:]\s*([^\n]+)',
            r'地址[：:]\s*([^\n]+)',
            r'举办地[：:]\s*([^\n]+)',
            r'举办地点[：:]\s*([^\n]+)',
            r'📍\s*([^\n]+)',
            r'Location[：:]\s*([^\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                place = match.group(1).strip()
                if place and len(place) > 2:
                    return place
        
        return None
    
    def extract_description(self, text: str) -> str:
        """提取活动描述"""
        
        # 取前 200 个字符作为描述
        lines = text.split('\n')
        description = ''
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('时间') and not line.startswith('地点'):
                description += line + ' '
                if len(description) > 200:
                    break
        
        return description[:300] if description else '活动信息'
    
    def extract_tags(self, title: str, text: str) -> List[str]:
        """自动生成标签"""
        
        tags = []
        
        # 基于标题和内容的关键词
        keywords = {
            '开源': ['开源', 'open source', 'opensource'],
            '校园': ['大学', '高校', '校园', 'university', 'campus'],
            '会议': ['会议', 'conference', 'summit'],
            '竞赛': ['竞赛', 'competition', '比赛', 'contest'],
            '讲座': ['讲座', 'talk', 'seminar'],
            '工作坊': ['工作坊', 'workshop', '研讨'],
        }
        
        combined_text = (title + ' ' + text).lower()
        
        for tag, keywords_list in keywords.items():
            for keyword in keywords_list:
                if keyword.lower() in combined_text:
                    tags.append(tag)
                    break
        
        return list(set(tags))[:5]  # 最多 5 个标签
    
    async def parse(self, extracted_text: str, source_url: str = None) -> ParsedActivity:
        """
        解析提取的文本
        """
        
        # 第 1 步：使用 LLM 获取标题和分类
        llm_result = await self._parse_with_llm(extracted_text)
        
        title = llm_result.get('title', '活动')
        description = llm_result.get('description', '')
        category = llm_result.get('category', 'activity')
        
        # 第 2 步：使用规则提取结构化信息
        date_str, timeline = self.extract_time_info(extracted_text)
        place = self.extract_place_info(extracted_text)
        tags = self.extract_tags(title, extracted_text)
        
        # 如果 LLM 没有提取描述，使用规则提取
        if not description:
            description = self.extract_description(extracted_text)
        
        # 如果 LLM 没有提取标签，使用规则提取
        if not tags:
            tags = self.extract_tags(title, extracted_text)
        
        # 构建事件
        event = ActivityEvent(
            year=datetime.now().year,
            id=self._generate_id(title),
            link=source_url or '',
            date=date_str or '',
            place=place or '',
            timeline=timeline
        )
        
        # 构建活动
        activity = ParsedActivity(
            title=title,
            description=description,
            category=category,
            tags=tags,
            events=[event]
        )
        
        return activity
    
    async def _parse_with_llm(self, text: str) -> Dict:
        """使用 LLM 解析"""
        
        if not self.llm:
            return {"title": "活动", "description": "", "category": "activity"}
        
        prompt = f"""请从以下活动文本中提取信息，返回 JSON 格式:

文本:
{text[:1000]}

请返回以下 JSON 格式 (不要其他文字):
{{
  "title": "活动标题",
  "description": "活动描述 (最多100字)",
  "category": "conference|competition|activity"
}}
"""
        
        try:
            response = await self.llm.parse(prompt)
            import json
            if isinstance(response, str):
                result = json.loads(response)
            else:
                result = response
            return result
        except:
            return {"title": "活动", "description": "", "category": "activity"}
    
    def _generate_id(self, title: str) -> str:
        """生成活动 ID"""
        import hashlib
        hash_obj = hashlib.md5(title.encode())
        return hash_obj.hexdigest()[:8]

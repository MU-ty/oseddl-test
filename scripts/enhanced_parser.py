"""
增强型数据解析器 - 规则 + LLM 混合提取
优先使用正则表达式提取时间、地点、链接等结构化数据
然后使用 LLM 补充描述、标签等非结构化数据
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

class ActivityCategory(str, Enum):
    """活动分类"""
    CONFERENCE = "conference"
    COMPETITION = "competition"
    ACTIVITY = "activity"

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
    category: Union[ActivityCategory, str]
    tags: List[str] = field(default_factory=list)
    events: List[ActivityEvent] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category.value if isinstance(self.category, ActivityCategory) else self.category,
            "tags": self.tags,
            "events": [e.to_dict() for e in self.events]
        }
    
    def to_yaml_str(self) -> str:
        """转换为YAML格式字符串"""
        try:
            import yaml
            data = self.to_dict()
            return yaml.dump([data], allow_unicode=True, sort_keys=False, default_flow_style=False)
        except:
            import json
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

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
    
    def extract_time_info(self, text: str) -> Tuple[Optional[str], List[TimelineEvent]]:
        """使用正则表达式提取时间信息，返回日期和时间线事件"""
        
        # 优先级 1: 完整时间段 "2025年11月1日（星期六）09:00-18:00" 或 "2025年11月11日 09:30-11:30"
        time_range_patterns = [
            # 格式: 2025年11月1日（星期六）09:00-18:00
            r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:[（(].*?[）)])?\s*(\d{1,2}):(\d{2})\s*[-~]\s*(\d{1,2}):(\d{2})',
            # 格式: 2025-11-01 09:00-18:00
            r'(\d{4})-(\d{1,2})-(\d{1,2})[T\s]+(\d{1,2}):(\d{2})\s*[-~]\s*(\d{1,2}):(\d{2})',
            # 格式: 2025年11月11日 09:30-11:30
            r'(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})\s*[-~]\s*(\d{1,2}):(\d{2})',
        ]
        
        timeline = []
        date_str = None
        
        for pattern in time_range_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    year, month, day, h1, m1, h2, m2 = [int(g) for g in match.groups()]
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    
                    # 添加开始时间点
                    start_time = f"{year}-{month:02d}-{day:02d}T{h1:02d}:{m1:02d}:00"
                    timeline.append(TimelineEvent(
                        deadline=start_time,
                        comment='活动开始'
                    ))
                    
                    # 添加结束时间点
                    end_time = f"{year}-{month:02d}-{day:02d}T{h2:02d}:{m2:02d}:00"
                    timeline.append(TimelineEvent(
                        deadline=end_time,
                        comment='活动结束'
                    ))
                    
                    return date_str, timeline
                except Exception as e:
                    pass
        
        # 优先级 2: ISO 8601 格式时间范围 "2025-11-01T09:00:00 - 2025-11-01T18:00:00"
        iso_range_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})T(\d{1,2}):(\d{2}):(\d{2})\s*[-~]\s*(\d{4})-(\d{1,2})-(\d{1,2})T(\d{1,2}):(\d{2}):(\d{2})'
        iso_match = re.search(iso_range_pattern, text)
        if iso_match:
            try:
                s_year, s_month, s_day, s_hour, s_min, s_sec, e_year, e_month, e_day, e_hour, e_min, e_sec = \
                    [int(g) for g in iso_match.groups()]
                
                date_str = f"{s_year}-{s_month:02d}-{s_day:02d}"
                
                timeline = [
                    TimelineEvent(
                        deadline=f"{s_year}-{s_month:02d}-{s_day:02d}T{s_hour:02d}:{s_min:02d}:{s_sec:02d}",
                        comment='活动开始'
                    ),
                    TimelineEvent(
                        deadline=f"{e_year}-{e_month:02d}-{e_day:02d}T{e_hour:02d}:{e_min:02d}:{e_sec:02d}",
                        comment='活动结束'
                    )
                ]
                return date_str, timeline
            except:
                pass
        
        # 优先级 3: 分别的开始和结束时间
        start_pattern = r'(?:开始|start)[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日[，,\s]+(\d{1,2}):(\d{2})'
        end_pattern = r'(?:结束|end)[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日[，,\s]+(\d{1,2}):(\d{2})'
        
        start_match = re.search(start_pattern, text)
        end_match = re.search(end_pattern, text)
        
        if start_match and end_match:
            try:
                s_year, s_month, s_day, s_hour, s_min = [int(g) for g in start_match.groups()]
                e_year, e_month, e_day, e_hour, e_min = [int(g) for g in end_match.groups()]
                
                date_str = f"{s_year}-{s_month:02d}-{s_day:02d}"
                
                timeline = [
                    TimelineEvent(
                        deadline=f"{s_year}-{s_month:02d}-{s_day:02d}T{s_hour:02d}:{s_min:02d}:00",
                        comment='活动开始'
                    ),
                    TimelineEvent(
                        deadline=f"{e_year}-{e_month:02d}-{e_day:02d}T{e_hour:02d}:{e_min:02d}:00",
                        comment='活动结束'
                    )
                ]
                return date_str, timeline
            except:
                pass
        
        # 优先级 4: 只有日期 "YYYY年MM月DD日"
        if not timeline:
            single_time_patterns = [
                r'(\d{4})年(\d{1,2})月(\d{1,2})日(?![0-9:])',
                r'(\d{4})-(\d{1,2})-(\d{1,2})(?![T0-9:])',
                r'time[：:]\s*(\d{4})-(\d{1,2})-(\d{1,2})',
            ]
            
            for pattern in single_time_patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        year, month, day = [int(g) for g in match.groups()[:3]]
                        date_str = f"{year}-{month:02d}-{day:02d}"
                        timeline.append(TimelineEvent(
                            deadline=f"{date_str}T00:00:00",
                            comment='关键日期'
                        ))
                        return date_str, timeline
                    except:
                        pass
        
        return date_str, timeline
    
    def extract_place_info(self, text: str) -> Optional[str]:
        """使用正则表达式提取地点信息，并清理无关信息"""
        
        patterns = [
            r'(?:地点|地址|举办地点|举办地)[：:]\s*([^\n。，；；\|]+)',
            r'(?:Location|Place)[：:]\s*([^\n。，；；\|]+)',
            r'📍\s*([^\n。，；；\|]+)',
        ]
        
        place = None
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                place = match.group(1).strip()
                break
        
        if not place:
            return None
        
        # 清理无关信息
        remove_keywords = [
            r'推荐.*?(?=\s*[，；；]|$)',  # 推荐停车位等
            r'[，；；]\s*(?:停车|地铁|公交|地铁线路|公交车|距离|附近|推荐|步行|开车|乘坐).*?(?=\s*[，；；]|$)',
            r'[，；；]\s*\d+元/小时.*?(?=\s*[，；；]|$)',
            r'[，；；]\s*\d+(?:号线|路|米).*?(?=\s*[，；；]|$)',
            r'点击报名.*?$',
            r'长按.*?$',
            r'扫描.*?$',
        ]
        
        for pattern in remove_keywords:
            place = re.sub(pattern, '', place, flags=re.IGNORECASE)
        
        place = place.strip()
        place = re.sub(r'[，；；]$', '', place)
        
        # 限制长度并验证
        if place and len(place) > 3:
            place = place[:80]
            if re.search(r'[\u4e00-\u9fa5a-zA-Z]+', place):
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
        category_str = llm_result.get('category', 'activity')
        
        # 确保 category 是有效的 Enum 值
        try:
            category = ActivityCategory(category_str)
        except (ValueError, KeyError):
            category = ActivityCategory.ACTIVITY
        
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

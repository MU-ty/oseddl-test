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
        import logging
        logger = logging.getLogger(__name__)
        
        self.llm = None
        try:
            from github_models_parser import GitHubModelsParser
            from config import settings
            
            if settings.GITHUB_TOKEN:
                self.llm = GitHubModelsParser(settings.GITHUB_TOKEN, model="gpt-4o")
                logger.info(f"✅ GitHub Models 已启用 (Token: {settings.GITHUB_TOKEN[:10]}...)")
            else:
                logger.warning("⚠️ GITHUB_TOKEN 未设置，将使用纯规则提取（无LLM）")
        except Exception as e:
            logger.error(f"❌ GitHub Models 初始化失败: {e}")
    
    def extract_time_info(self, text: str) -> Tuple[Optional[str], List[TimelineEvent]]:
        """使用正则表达式提取时间信息，返回日期和时间线事件"""
        import logging
        logger = logging.getLogger(__name__)
        
        timeline = []
        date_str = None
        
        # 优先级 1: 完整时间段 "2025年11月1日（星期六）09:00-18:00"
        time_range_patterns = [
            # 格式: 2025年11月1日（星期六）09:00-18:00 或 2025年7月18日 09:00-18:00
            r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:[（(].*?[）)])?\s*(\d{1,2}):(\d{2})\s*[-~至到]\s*(\d{1,2}):(\d{2})',
            # 格式: 2025-11-01 09:00-18:00
            r'(\d{4})-(\d{1,2})-(\d{1,2})[T\s]+(\d{1,2}):(\d{2})\s*[-~至到]\s*(\d{1,2}):(\d{2})',
        ]
        
        for pattern in time_range_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    year, month, day, h1, m1, h2, m2 = [int(g) for g in match.groups()]
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    
                    timeline.append(TimelineEvent(
                        deadline=f"{year}-{month:02d}-{day:02d}T{h1:02d}:{m1:02d}:00",
                        comment='活动开始'
                    ))
                    timeline.append(TimelineEvent(
                        deadline=f"{year}-{month:02d}-{day:02d}T{h2:02d}:{m2:02d}:00",
                        comment='活动结束'
                    ))
                    
                    logger.info(f"✓ 提取到时间段: {date_str} {h1:02d}:{m1:02d}-{h2:02d}:{m2:02d}")
                    return date_str, timeline
                except Exception as e:
                    logger.warning(f"⚠️ 时间段解析失败: {e}")
        
        # 优先级 2: ISO 8601 格式时间范围
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
        解析提取的文本 - 混合策略：规则优先 + LLM补充
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 第 1 步：使用规则提取结构化信息（更可靠）
        logger.info("📋 步骤1: 使用规则提取结构化信息...")
        date_str, timeline = self.extract_time_info(extracted_text)
        place = self.extract_place_info(extracted_text)
        
        logger.info(f"  - 日期: {date_str or '未提取到'}")
        logger.info(f"  - 地点: {place or '未提取到'}")
        logger.info(f"  - 时间线事件: {len(timeline)}个")
        
        # 第 2 步：使用 LLM 获取语义信息（标题、描述、分类）
        logger.info("🤖 步骤2: 使用LLM提取语义信息...")
        llm_result = await self._parse_with_llm(extracted_text)
        
        title = llm_result.get('title', '活动')
        description = llm_result.get('description', '')
        category_str = llm_result.get('category', 'activity')
        llm_tags = llm_result.get('tags', [])
        
        logger.info(f"  - 标题: {title}")
        logger.info(f"  - 分类: {category_str}")
        logger.info(f"  - LLM标签: {llm_tags}")
        
        # LLM可能返回更好的timeline
        if 'events' in llm_result and llm_result['events']:
            llm_timeline = llm_result['events'][0].get('timeline', [])
            if llm_timeline and len(llm_timeline) > len(timeline):
                logger.info(f"  - 使用LLM提取的时间线 ({len(llm_timeline)}个事件)")
                timeline = [TimelineEvent(
                    deadline=t['deadline'],
                    comment=t['comment']
                ) for t in llm_timeline]
        
        # 确保 category 是有效的 Enum 值
        try:
            category = ActivityCategory(category_str)
        except (ValueError, KeyError):
            category = ActivityCategory.ACTIVITY
        
        # 第 3 步：规则提取标签作为补充
        rule_tags = self.extract_tags(title, extracted_text)
        
        # 合并标签：LLM优先，规则补充
        tags = []
        if llm_tags:
            tags.extend(llm_tags)
        tags.extend([t for t in rule_tags if t not in tags])
        tags = tags[:5]  # 最多5个
        
        logger.info(f"  - 最终标签: {tags}")
        
        # 如果 LLM 没有提取描述，使用规则提取
        if not description:
            description = self.extract_description(extracted_text)
            logger.info("  - 使用规则提取的描述")
        
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
        
        logger.info(f"✅ 解析完成: {activity.title}")
        
        return activity
    
    async def _parse_with_llm(self, text: str) -> Dict:
        """使用 LLM 解析 - 直接使用github_models_parser的完整解析"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.llm:
            logger.warning("⚠️ LLM未初始化，返回默认值")
            return {"title": "活动", "description": "", "category": "activity", "tags": []}
        
        try:
            # 直接调用 GitHubModelsParser.parse()，它会返回完整的结构
            logger.info("🤖 调用GitHub Models API...")
            response = await self.llm.parse(text)
            
            if response and 'title' in response:
                logger.info(f"✅ LLM解析成功: {response.get('title', 'Unknown')}")
                return response
            elif 'error' in response:
                logger.warning(f"⚠️ LLM返回错误: {response['error']}")
                return {"title": "活动", "description": "", "category": "activity", "tags": []}
            else:
                logger.warning("⚠️ LLM返回空结果")
                return {"title": "活动", "description": "", "category": "activity", "tags": []}
        except Exception as e:
            logger.error(f"❌ LLM解析失败: {e}")
            return {"title": "活动", "description": "", "category": "activity", "tags": []}
            return {"title": "活动", "description": "", "category": "activity"}
    
    def _generate_id(self, title: str) -> str:
        """生成活动 ID"""
        import hashlib
        hash_obj = hashlib.md5(title.encode())
        return hash_obj.hexdigest()[:8]

"""
数据验证模块 - 验证解析后的活动数据的完整性和准确性

验证清单：
- ID唯一性
- 时间格式（ISO 8601）
- 时间逻辑
- 时区有效性
- 标签规范
- 描述长度
- 链接有效性（可选）
- 官网识别（进阶）
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

import yaml

from config import (
    settings, 
    ACTIVITIES_FILE, 
    COMPETITIONS_FILE, 
    CONFERENCES_FILE, 
    IANA_TIMEZONES,
    DATA_FILE_MAP,
)
from data_parsing import ParsedActivity, ActivityCategory

logger = logging.getLogger(__name__)


class ErrorLevel(str, Enum):
    """错误级别"""
    ERROR = "error"      # 致命错误，必须修复
    WARNING = "warning"  # 警告，建议修复
    INFO = "info"        # 提示信息


@dataclass
class ValidationIssue:
    """验证问题"""
    field: str
    issue: str
    level: ErrorLevel
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    suggestions: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def all_issues(self) -> List[ValidationIssue]:
        """获取所有问题"""
        return self.errors + self.warnings + self.suggestions
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'suggestion_count': len(self.suggestions),
            'errors': [e.to_dict() for e in self.errors],
            'warnings': [w.to_dict() for w in self.warnings],
            'suggestions': [s.to_dict() for s in self.suggestions],
        }


class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        """初始化验证器"""
        self.existing_data = self._load_existing_data()
        self.existing_ids = self._extract_all_ids()
        self.existing_tags = self._extract_all_tags()
    
    def validate(self, activity: ParsedActivity) -> ValidationResult:
        """
        验证活动数据
        
        Args:
            activity: 解析后的活动数据
        
        Returns:
            ValidationResult: 验证结果
        """
        
        logger.info(f"验证活动数据: {activity.title}")
        
        result = ValidationResult(is_valid=True)
        
        # 基本信息验证
        self._validate_basic_info(activity, result)
        
        # 事件验证
        for event_idx, event in enumerate(activity.events):
            self._validate_event(activity, event, event_idx, result)
        
        # 标签验证
        self._validate_tags(activity, result)
        
        # 整体验证
        self._validate_overall(activity, result)
        
        # 更新有效性
        result.is_valid = len(result.errors) == 0
        
        if result.is_valid:
            logger.info("✓ 验证通过")
        else:
            logger.warning(f"✗ 验证失败: {len(result.errors)} 个错误")
        
        return result
    
    def _validate_basic_info(self, activity: ParsedActivity, result: ValidationResult):
        """验证基本信息"""
        
        # 检查标题
        if not activity.title or len(activity.title.strip()) == 0:
            result.errors.append(ValidationIssue(
                field='title',
                issue='标题不能为空',
                level=ErrorLevel.ERROR,
            ))
        
        # 检查描述
        if not activity.description or len(activity.description.strip()) == 0:
            result.warnings.append(ValidationIssue(
                field='description',
                issue='缺少活动描述',
                level=ErrorLevel.WARNING,
                suggestion='请添加一句话描述活动',
            ))
        elif len(activity.description) > settings.DESCRIPTION_MAX_LENGTH:
            result.warnings.append(ValidationIssue(
                field='description',
                issue=f'描述过长 ({len(activity.description)} > {settings.DESCRIPTION_MAX_LENGTH})',
                level=ErrorLevel.WARNING,
                suggestion=f'请将描述缩短为 {settings.DESCRIPTION_MAX_LENGTH} 字以内',
            ))
        
        # 检查分类
        if not activity.category:
            result.errors.append(ValidationIssue(
                field='category',
                issue='活动分类不能为空',
                level=ErrorLevel.ERROR,
            ))
    
    def _validate_event(
        self, 
        activity: ParsedActivity, 
        event, 
        event_idx: int, 
        result: ValidationResult
    ):
        """验证单个事件"""
        
        field_prefix = f'events[{event_idx}]'
        
        # 检查年份
        if event.year <= 1900 or event.year > 2100:
            result.errors.append(ValidationIssue(
                field=f'{field_prefix}.year',
                issue=f'年份不合理: {event.year}',
                level=ErrorLevel.ERROR,
            ))
        
        # 检查ID
        if not event.id:
            result.errors.append(ValidationIssue(
                field=f'{field_prefix}.id',
                issue='ID不能为空',
                level=ErrorLevel.ERROR,
            ))
        else:
            self._validate_id(event.id, event_idx, result)
        
        # 检查链接
        if not event.link:
            result.warnings.append(ValidationIssue(
                field=f'{field_prefix}.link',
                issue='缺少活动链接',
                level=ErrorLevel.WARNING,
            ))
        else:
            self._validate_link(event.link, event_idx, result)
        
        # 检查时区
        if not event.timezone:
            result.errors.append(ValidationIssue(
                field=f'{field_prefix}.timezone',
                issue='时区不能为空',
                level=ErrorLevel.ERROR,
            ))
        else:
            self._validate_timezone(event.timezone, event_idx, result)
        
        # 检查时间线
        if not event.timeline:
            result.warnings.append(ValidationIssue(
                field=f'{field_prefix}.timeline',
                issue='缺少关键时间点',
                level=ErrorLevel.WARNING,
            ))
        else:
            self._validate_timeline(event.timeline, event_idx, result)
        
        # 检查地点
        if not event.place:
            result.warnings.append(ValidationIssue(
                field=f'{field_prefix}.place',
                issue='缺少地点信息',
                level=ErrorLevel.WARNING,
            ))
        
        # 检查日期范围
        if not event.date:
            result.warnings.append(ValidationIssue(
                field=f'{field_prefix}.date',
                issue='缺少人类可读的日期范围',
                level=ErrorLevel.WARNING,
            ))
    
    def _validate_id(self, id_str: str, event_idx: int, result: ValidationResult):
        """验证ID唯一性"""
        
        field = f'events[{event_idx}].id'
        
        # 检查ID格式
        if not re.match(r'^[a-z0-9\-]+$', id_str):
            result.errors.append(ValidationIssue(
                field=field,
                issue='ID格式不正确（仅允许小写字母、数字和连字符）',
                level=ErrorLevel.ERROR,
                suggestion=f'建议: {self._normalize_id(id_str)}',
            ))
            return
        
        # 检查ID唯一性
        if id_str in self.existing_ids:
            result.errors.append(ValidationIssue(
                field=field,
                issue=f'ID已存在: {id_str}',
                level=ErrorLevel.ERROR,
                suggestion='请更改ID或检查是否重复添加',
            ))
    
    def _validate_link(self, link: str, event_idx: int, result: ValidationResult):
        """验证链接"""
        
        field = f'events[{event_idx}].link'
        
        # 检查URL格式
        url_pattern = r'^https?://[^\s]+'
        if not re.match(url_pattern, link):
            result.errors.append(ValidationIssue(
                field=field,
                issue='链接格式不正确（必须以http://或https://开头）',
                level=ErrorLevel.ERROR,
            ))
            return
        
        # 可选：检查链接有效性
        if settings.VALIDATE_LINKS:
            self._check_link_accessibility(link, event_idx, result)
    
    def _check_link_accessibility(self, link: str, event_idx: int, result: ValidationResult):
        """检查链接可访问性"""
        
        field = f'events[{event_idx}].link'
        
        try:
            import requests
            response = requests.head(link, timeout=5, allow_redirects=True)
            
            if response.status_code >= 400:
                result.warnings.append(ValidationIssue(
                    field=field,
                    issue=f'链接无法访问 (HTTP {response.status_code})',
                    level=ErrorLevel.WARNING,
                ))
        
        except Exception as e:
            result.suggestions.append(ValidationIssue(
                field=field,
                issue=f'无法验证链接可访问性: {str(e)[:50]}',
                level=ErrorLevel.INFO,
            ))
    
    def _validate_timezone(self, tz: str, event_idx: int, result: ValidationResult):
        """验证时区"""
        
        field = f'events[{event_idx}].timezone'
        
        if tz not in IANA_TIMEZONES and tz != 'UTC':
            result.errors.append(ValidationIssue(
                field=field,
                issue=f'时区无效: {tz}',
                level=ErrorLevel.ERROR,
                suggestion='请使用标准IANA时区名称，如: Asia/Shanghai',
            ))
    
    def _validate_timeline(self, timeline: List, event_idx: int, result: ValidationResult):
        """验证时间线"""
        
        field_prefix = f'events[{event_idx}].timeline'
        
        previous_deadline = None
        
        for timeline_idx, event_item in enumerate(timeline):
            
            # 检查deadline格式
            if not self._is_valid_iso8601(event_item.deadline):
                result.errors.append(ValidationIssue(
                    field=f'{field_prefix}[{timeline_idx}].deadline',
                    issue=f'时间格式不正确: {event_item.deadline}',
                    level=ErrorLevel.ERROR,
                    suggestion='请使用ISO 8601格式: YYYY-MM-DDTHH:mm:ss',
                ))
                continue
            
            # 检查时间递增
            if previous_deadline:
                try:
                    curr = datetime.fromisoformat(event_item.deadline.replace('Z', '+00:00'))
                    prev = datetime.fromisoformat(previous_deadline.replace('Z', '+00:00'))
                    
                    if curr < prev:
                        result.warnings.append(ValidationIssue(
                            field=f'{field_prefix}[{timeline_idx}].deadline',
                            issue='时间顺序不正确（当前时间早于前一个时间）',
                            level=ErrorLevel.WARNING,
                        ))
                except ValueError:
                    pass
            
            previous_deadline = event_item.deadline
            
            # 检查comment
            if not event_item.comment or len(event_item.comment.strip()) == 0:
                result.warnings.append(ValidationIssue(
                    field=f'{field_prefix}[{timeline_idx}].comment',
                    issue='时间说明不能为空',
                    level=ErrorLevel.WARNING,
                ))
    
    def _validate_tags(self, activity: ParsedActivity, result: ValidationResult):
        """验证标签"""
        
        if not activity.tags:
            result.suggestions.append(ValidationIssue(
                field='tags',
                issue='未添加任何标签',
                level=ErrorLevel.INFO,
                suggestion='建议添加3-5个相关标签',
            ))
            return
        
        # 检查标签是否已存在
        for tag_idx, tag in enumerate(activity.tags):
            
            # 检查标签是否使用现有的
            similar_tags = self._find_similar_tags(tag)
            if similar_tags and tag not in self.existing_tags:
                suggestion = f"使用现有标签: {', '.join(similar_tags)}"
                result.suggestions.append(ValidationIssue(
                    field=f'tags[{tag_idx}]',
                    issue=f'标签"{tag}"与现有标签相似',
                    level=ErrorLevel.INFO,
                    suggestion=suggestion,
                ))
    
    def _validate_overall(self, activity: ParsedActivity, result: ValidationResult):
        """整体验证"""
        
        # 检查是否至少有一个事件
        if not activity.events:
            result.errors.append(ValidationIssue(
                field='events',
                issue='至少需要一个事件',
                level=ErrorLevel.ERROR,
            ))
    
    def _load_existing_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载现有数据"""
        
        data = {}
        
        for category, file_path in DATA_FILE_MAP.items():
            try:
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data[category] = yaml.safe_load(f) or []
                else:
                    data[category] = []
            except Exception as e:
                logger.warning(f"⚠ 加载数据文件失败: {file_path}: {e}")
                data[category] = []
        
        return data
    
    def _extract_all_ids(self) -> set:
        """提取所有现有的ID"""
        
        ids = set()
        
        for category, activities in self.existing_data.items():
            for activity in activities:
                events = activity.get('events', [])
                for event in events:
                    if 'id' in event:
                        ids.add(event['id'])
        
        return ids
    
    def _extract_all_tags(self) -> set:
        """提取所有现有的标签"""
        
        tags = set()
        
        for category, activities in self.existing_data.items():
            for activity in activities:
                activity_tags = activity.get('tags', [])
                tags.update(activity_tags)
        
        return tags
    
    def _find_similar_tags(self, tag: str, threshold: float = 0.6) -> List[str]:
        """查找相似的现有标签"""
        
        from difflib import SequenceMatcher
        
        similar = []
        
        for existing_tag in self.existing_tags:
            ratio = SequenceMatcher(None, tag, existing_tag).ratio()
            if ratio >= threshold and tag != existing_tag:
                similar.append(existing_tag)
        
        return similar
    
    def _is_valid_iso8601(self, date_str: str) -> bool:
        """检查是否为有效的ISO 8601格式"""
        
        try:
            datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False
    
    def _normalize_id(self, id_str: str) -> str:
        """规范化ID"""
        
        id_str = id_str.lower()
        id_str = re.sub(r'[^a-z0-9\-]', '-', id_str)
        id_str = re.sub(r'-+', '-', id_str).strip('-')
        return id_str


# 便捷函数
def validate_activity_data(activity: ParsedActivity) -> ValidationResult:
    """
    快速验证活动数据
    
    Args:
        activity: 解析后的活动数据
    
    Returns:
        ValidationResult: 验证结果
    """
    
    validator = DataValidator()
    return validator.validate(activity)


if __name__ == "__main__":
    import json
    from data_parsing import SimpleDataParser
    import asyncio
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            text = sys.argv[1]
            
            # 解析
            parser = SimpleDataParser()
            activity = await parser.parse(text)
            
            # 验证
            result = validate_activity_data(activity)
            
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("用法: python data_validation.py <text>")
    
    asyncio.run(main())

"""
结果反馈模块 - 在GitHub Issue中展示提取和验证结果

功能：
- 在Issue评论中展示提取的信息摘要
- 展示解析后的结构化数据（YAML格式）
- 展示数据验证报告
- 提供修正建议
"""

import logging
from typing import Optional
from datetime import datetime

from information_extraction import ExtractionResult
from data_parsing import ParsedActivity
from data_validation import ValidationResult, ErrorLevel

logger = logging.getLogger(__name__)


class ResultFeedback:
    """结果反馈生成器"""
    
    @staticmethod
    def generate_comment(
        extraction_result: ExtractionResult,
        parsed_activity: Optional[ParsedActivity] = None,
        validation_result: Optional[ValidationResult] = None,
    ) -> str:
        """
        生成GitHub Issue评论
        
        Args:
            extraction_result: 信息提取结果
            parsed_activity: 解析后的活动数据（可选）
            validation_result: 验证结果（可选）
        
        Returns:
            str: GitHub Issue评论内容（Markdown格式）
        """
        
        comment_parts = []
        
        # 标题
        comment_parts.append("## 🤖 AI 活动信息提取结果\n")
        
        # 提取状态
        if extraction_result.error:
            comment_parts.append(f"❌ **信息提取失败**: {extraction_result.error}\n")
            return "\n".join(comment_parts)
        
        comment_parts.append("✅ **信息提取成功**\n")
        
        # 第一部分：提取摘要
        comment_parts.append(ResultFeedback._format_extraction_summary(extraction_result))
        
        # 第二部分：解析结果
        if parsed_activity:
            comment_parts.append(ResultFeedback._format_parsed_activity(parsed_activity))
        
        # 第三部分：验证报告
        if validation_result:
            comment_parts.append(ResultFeedback._format_validation_report(validation_result))
        
        # 页脚
        comment_parts.append(ResultFeedback._format_footer())
        
        return "\n".join(comment_parts)
    
    @staticmethod
    def _format_extraction_summary(extraction_result: ExtractionResult) -> str:
        """格式化提取摘要"""
        
        parts = []
        parts.append("### 📋 信息提取摘要\n")
        
        # 信息源
        if extraction_result.source_type.value == "url":
            parts.append(f"- **信息源**: [网页链接]({extraction_result.source_url})")
        elif extraction_result.source_file:
            parts.append(f"- **信息源**: 文件 (`{extraction_result.source_file}`)")
        else:
            parts.append(f"- **信息源**: 纯文本")
        
        # 提取内容统计
        parts.append(f"- **文本字符数**: {len(extraction_result.extracted_text)}")
        parts.append(f"- **图片数量**: {len(extraction_result.extracted_images)}")
        parts.append(f"- **二维码数量**: {len(extraction_result.extracted_qr_codes)}")
        
        # 文本预览
        preview_len = min(200, len(extraction_result.extracted_text))
        preview = extraction_result.extracted_text[:preview_len].replace('\n', ' ')
        if len(extraction_result.extracted_text) > preview_len:
            preview += "..."
        
        parts.append(f"\n**文本预览**:\n```\n{preview}\n```\n")
        
        return "\n".join(parts)
    
    @staticmethod
    def _format_parsed_activity(activity: ParsedActivity) -> str:
        """格式化解析后的活动数据"""
        
        parts = []
        parts.append("### 📝 解析后的数据\n")
        
        # 基本信息
        parts.append(f"| 字段 | 值 |")
        parts.append(f"|-----|-----|")
        parts.append(f"| 活动名称 | {activity.title} |")
        parts.append(f"| 活动分类 | {activity.category.value} |")
        parts.append(f"| 活动描述 | {activity.description} |")
        parts.append(f"| 标签 | {', '.join(activity.tags) if activity.tags else '(无)'} |")
        
        if activity.events:
            event = activity.events[0]
            parts.append(f"| 活动年份 | {event.year} |")
            parts.append(f"| 活动ID | `{event.id}` |")
            parts.append(f"| 活动链接 | [{event.link}]({event.link}) |")
            parts.append(f"| 活动地点 | {event.place} |")
            parts.append(f"| 时区 | {event.timezone} |")
            parts.append(f"| 日期范围 | {event.date} |")
        
        parts.append("")
        
        # YAML格式
        parts.append("**YAML 格式**:\n")
        parts.append("```yaml")
        parts.append(activity.to_yaml_str())
        parts.append("```\n")
        
        return "\n".join(parts)
    
    @staticmethod
    def _format_validation_report(validation_result: ValidationResult) -> str:
        """格式化验证报告"""
        
        parts = []
        parts.append("### ✔️ 数据验证报告\n")
        
        # 验证状态
        if validation_result.is_valid:
            status = "✅ **验证通过**"
        else:
            status = "❌ **验证失败**"
        
        parts.append(f"{status}\n")
        
        # 问题统计
        parts.append(f"- 🔴 错误: {len(validation_result.errors)}")
        parts.append(f"- 🟡 警告: {len(validation_result.warnings)}")
        parts.append(f"- 🔵 提示: {len(validation_result.suggestions)}\n")
        
        # 详细问题
        if validation_result.errors:
            parts.append("#### 🔴 错误 (必须修复)\n")
            for issue in validation_result.errors:
                parts.append(f"- **{issue.field}**: {issue.issue}")
                if issue.suggestion:
                    parts.append(f"  > 💡 建议: {issue.suggestion}")
                parts.append("")
        
        if validation_result.warnings:
            parts.append("#### 🟡 警告 (建议修复)\n")
            for issue in validation_result.warnings:
                parts.append(f"- **{issue.field}**: {issue.issue}")
                if issue.suggestion:
                    parts.append(f"  > 💡 建议: {issue.suggestion}")
                parts.append("")
        
        if validation_result.suggestions:
            parts.append("#### 🔵 提示信息\n")
            for issue in validation_result.suggestions:
                parts.append(f"- **{issue.field}**: {issue.issue}")
                if issue.suggestion:
                    parts.append(f"  > 💡 建议: {issue.suggestion}")
                parts.append("")
        
        return "\n".join(parts)
    
    @staticmethod
    def _format_footer() -> str:
        """格式化页脚"""
        
        parts = []
        
        parts.append("---\n")
        parts.append("### 📌 下一步\n")
        
        parts.append("""
1. **检查数据准确性**: 请务必核实上述提取的信息是否准确
2. **解决问题**: 如有红色❌错误，请编辑Issue或评论中提出修正
3. **审核确认**: 数据验证通过后，可联系Maintainer进行审核
4. **等待集成**: Maintainer确认无误后，将自动创建PR并合并到数据文件

### 📚 帮助
- 关于YAML格式说明，请查看 [README.md](README.md) 中的"数据结构"部分
- 有任何问题，请在评论中提出 👇

---

*此评论由 AI Agent 自动生成于 {} UTC*
""".format(datetime.utcnow().isoformat()))
        
        return "\n".join(parts)


def generate_issue_comment(
    extraction_result: ExtractionResult,
    parsed_activity: Optional[ParsedActivity] = None,
    validation_result: Optional[ValidationResult] = None,
) -> str:
    """
    便捷函数：生成Issue评论
    
    Args:
        extraction_result: 提取结果
        parsed_activity: 解析结果（可选）
        validation_result: 验证结果（可选）
    
    Returns:
        str: Issue评论内容
    """
    
    return ResultFeedback.generate_comment(
        extraction_result,
        parsed_activity,
        validation_result,
    )


if __name__ == "__main__":
    # 示例
    from information_extraction import ExtractionResult, SourceType
    from data_parsing import ParsedActivity, ActivityCategory, ActivityEvent, TimelineEvent
    from data_validation import ValidationResult, ValidationIssue, ErrorLevel
    
    # 创建示例数据
    extraction = ExtractionResult(
        source_type=SourceType.URL,
        source_url="https://example.com/activity",
        extracted_text="这是一个示例活动的信息...",
    )
    
    activity = ParsedActivity(
        title="开源之夏",
        description="一个面向全球高校学生的暑期编程活动",
        category=ActivityCategory.COMPETITION,
        tags=["开源", "竞赛", "暑期"],
        events=[
            ActivityEvent(
                year=2025,
                id="oscp2025",
                link="https://summer-ospp.ac.cn",
                timezone="Asia/Shanghai",
                date="2025年4月30日 - 9月30日",
                place="线上",
                timeline=[
                    TimelineEvent(
                        deadline="2025-06-04T18:00:00",
                        comment="项目申请书提交",
                    ),
                ],
            )
        ],
    )
    
    validation = ValidationResult(
        is_valid=True,
        suggestions=[
            ValidationIssue(
                field="tags",
                issue="标签建议添加更多",
                level=ErrorLevel.INFO,
            )
        ],
    )
    
    # 生成评论
    comment = generate_issue_comment(extraction, activity, validation)
    print(comment)

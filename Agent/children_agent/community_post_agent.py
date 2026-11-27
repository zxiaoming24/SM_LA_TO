"""
社区发帖助手 Agent - 自动分析资源内容生成帖子草稿

核心功能：
1. 分析资源内容，识别关键知识点和问题点
2. 自动生成适合社区发布的帖子草稿（标题+内容+标签）
3. 根据内容自动判断适合的社区区域
4. 支持多种资源类型（练习题、视频、文档、思维导图等）

设计理念：
- 用户主动触发：用户在查看资源后主动点击"发帖"按钮
- 草稿生成：分析内容生成草稿，用户可以修改确认
- 智能分类：自动判断区域和标签，降低用户发帖门槛
"""

import os
import json
from typing import Dict, Any, Optional, List
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai

try:
    from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
    from Agent.community_service import CommunityService, COMMUNITY_ZONES, get_zone_by_content
except ImportError:
    from children_agent.dynamic_feature_updater import DynamicFeatureUpdater
    from community_service import CommunityService, COMMUNITY_ZONES, get_zone_by_content


class CommunityPostAgent:
    """
    社区发帖助手 Agent

    当用户在学习过程中遇到困惑，点击"发帖"按钮时，
    此 Agent 会分析当前资源内容，自动生成高质量的帖子草稿。
    """

    def __init__(self):
        self.llm = self._initialize_llm()
        self.post_generation_template = self._create_post_generation_template()
        self.feature_updater = DynamicFeatureUpdater()
        self.community_service = CommunityService()

    def _initialize_llm(self):
        try:
            return get_chat_openai(temperature=0.7, max_tokens=2000)
        except Exception as e:
            raise Exception(f"初始化 CommunityPostAgent LLM 失败: {e}")

    def _create_post_generation_template(self) -> PromptTemplate:
        template = """
你是一个社区发帖助手，负责帮助用户将学习中的困惑整理成高质量的社区帖子。

## 你的任务
分析用户提供的资源内容，找出其中可能让用户产生困惑的知识点，并生成一个适合发布到社区的帖子草稿。

## 资源内容
类型: {resource_type}
标题: {resource_title}
内容: {resource_content}

## 社区区域说明
- learning（学习区）: 学习困惑、知识点讨论、作业帮助
- life（生活区）: 日常生活分享、校园生活、闲谈
- resource（资源共享区）: 学习资料、工具推荐、资源分享
- feedback（反馈建议区）: 系统反馈、功能建议、问题报告

## 输出要求
请以 JSON 格式输出，包含以下字段：
- title: 帖子标题（简洁明了，20字以内，突出问题核心）
- content: 帖子正文内容（包含问题描述、已尝试的方法、期望的帮助）
- tags: 标签列表（3-5个相关标签）
- zone: 推荐的社区区域（learning/life/resource/feedback）
- suggested_area: 区域名称（中文）
- identified_issues: 识别出的潜在问题/困惑点列表，每一项包含：
  - issue: 问题描述（一句话概括）
  - reason: 为什么认为用户可能有这个困惑（基于资源内容分析）
  - suggestion: 发帖时建议重点描述的内容

## 生成原则
1. 标题要能清晰表达问题核心，吸引他人点击
2. 内容要结构清晰，包括：问题背景、具体疑问、已尝试的思路
3. 标签要精准，便于他人搜索
4. zone 要根据内容判断最适合的区域
5. identified_issues 要真实反映资源中的难点，不凭空编造

## 输出示例
{{
    "title": "Python循环中break语句的执行时机疑问",
    "content": "我在学习Python循环时遇到一个问题，代码如下：\\nfor i in range(5):\\n    if i == 3:\\n        break\\n    print(i)\\n\\n我理解break会退出整个循环，但实际输出是0 1 2，请问break到底在什么时候执行？",
    "tags": ["Python", "循环", "break语句", "控制流"],
    "zone": "learning",
    "suggested_area": "学习区",
    "identified_issues": [
        {{
            "issue": "break语句在循环中的执行时机不清晰",
            "reason": "资源中的示例涉及break在条件判断内执行，初学者容易混淆break和continue的区别",
            "suggestion": "在帖子中说明你对break执行顺序的理解"
        }},
        {{
            "issue": "for循环与range函数的配合使用",
            "reason": "range(5)生成0-4的数字序列，与break结合时退出条件需要明确",
            "suggestion": "描述你期望的输出是什么，实际输出是什么"
        }}
    ]
}}

请生成帖子草稿：
"""
        return PromptTemplate.from_template(template)

    def generate_post_draft(self, resource_type: str, resource_title: str,
                           resource_content: str) -> Dict[str, Any]:
        """
        分析资源内容，生成帖子草稿

        Args:
            resource_type: 资源类型（practice/video/doc/mindmap/study_plan等）
            resource_title: 资源标题
            resource_content: 资源内容

        Returns:
            包含 title, content, tags, zone, suggested_area 的字典
        """
        if not resource_content or len(resource_content.strip()) < 10:
            return {
                "title": resource_title or "Untitled",
                "content": "资源内容为空，无法生成帖子草稿",
                "tags": [],
                "zone": "learning",
                "suggested_area": "学习区",
                "error": "资源内容过短"
            }

        resource_type_display = {
            "practice": "练习题",
            "video": "视频教程",
            "doc": "文档资料",
            "mindmap": "思维导图",
            "study_plan": "学习计划",
            "test": "测试题",
            "wrong_answer": "错题",
            "resource": "学习资源",
            "other": "其他内容"
        }.get(resource_type, resource_type)

        prompt = self.post_generation_template.format(
            resource_type=resource_type_display,
            resource_title=resource_title or "无标题",
            resource_content=resource_content[:3000]
        )

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            result = json.loads(content.strip())

            result["zone"] = result.get("zone", "learning")
            if result["zone"] not in COMMUNITY_ZONES:
                result["zone"] = get_zone_by_content(resource_content, resource_title)

            result["suggested_area"] = COMMUNITY_ZONES.get(result["zone"], {}).get("name", "学习区")

            return result

        except json.JSONDecodeError as e:
            return self._generate_fallback_draft(resource_type, resource_title, resource_content)
        except Exception as e:
            return {
                "title": resource_title or "Untitled",
                "content": f"生成帖子草稿时出错: {str(e)}\n\n资源内容摘要:\n{resource_content[:500]}",
                "tags": [resource_type_display],
                "zone": get_zone_by_content(resource_content, resource_title),
                "suggested_area": COMMUNITY_ZONES.get(get_zone_by_content(resource_content, resource_title), {}).get("name", "学习区"),
                "error": str(e)
            }

    def _generate_fallback_draft(self, resource_type: str, resource_title: str,
                                  resource_content: str) -> Dict[str, Any]:
        """当 LLM 生成 JSON 失败时的降级方案"""
        content_preview = resource_content[:500]
        zone = get_zone_by_content(resource_content, resource_title)

        return {
            "title": resource_title or "关于" + resource_type + "的问题",
            "content": f"我在学习过程中遇到了以下问题：\n\n{content_preview}\n\n请问有人能帮我解答吗？",
            "tags": [resource_type, "求助"],
            "zone": zone,
            "suggested_area": COMMUNITY_ZONES.get(zone, {}).get("name", "学习区"),
            "fallback": True
        }

    def preview_post(self, user_id: str, resource_type: str, resource_title: str,
                    resource_content: str) -> Dict[str, Any]:
        """
        预览帖子草稿（不保存到数据库）

        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_title: 资源标题
            resource_content: 资源内容

        Returns:
            帖子草稿预览信息（含identified_issues）
        """
        draft = self.generate_post_draft(resource_type, resource_title, resource_content)

        return {
            "success": True,
            "draft": draft,
            "zones": COMMUNITY_ZONES,
            "preview": {
                "title": draft.get("title", ""),
                "content": draft.get("content", ""),
                "tags": draft.get("tags", []),
                "zone": draft.get("zone", "learning"),
                "zone_name": draft.get("suggested_area", "学习区"),
                "identified_issues": draft.get("identified_issues", [])
            }
        }

    def publish_post(self, user_id: str, resource_type: str, resource_title: str,
                    resource_content: str, title: Optional[str] = None,
                    content: Optional[str] = None, tags: Optional[List[str]] = None,
                    zone: Optional[str] = None) -> Dict[str, Any]:
        """
        发布帖子到社区

        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_title: 资源标题
            resource_content: 资源内容
            title: 自定义标题（可选，使用生成的草稿标题）
            content: 自定义内容（可选，使用生成的草稿内容）
            tags: 自定义标签（可选，使用生成的标签）
            zone: 自定义区域（可选，使用自动判断的区域）

        Returns:
            发布结果
        """
        draft = self.generate_post_draft(resource_type, resource_title, resource_content)

        post_title = title or draft.get("title", resource_title or "Untitled")
        post_content = content or draft.get("content", resource_content)
        post_tags = tags or draft.get("tags", [resource_type])
        post_zone = zone or draft.get("zone", "learning")

        if post_zone not in COMMUNITY_ZONES:
            post_zone = get_zone_by_content(post_content, post_title)

        try:
            result = self.community_service.create_post(
                user_id=user_id,
                title=post_title,
                content=post_content,
                tags=post_tags,
                zone=post_zone
            )

            return {
                "success": True,
                "post": result,
                "draft": draft,
                "message": f"帖子已成功发布到{COMMUNITY_ZONES.get(post_zone, {}).get('name', '学习区')}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "draft": draft,
                "message": "发帖失败，请重试"
            }

    def get_zones_info(self) -> Dict[str, Any]:
        """获取所有社区区域信息"""
        return {
            "zones": COMMUNITY_ZONES,
            "default_zone": "learning"
        }

"""
知识点智能对比Agent
负责对两个知识点进行多维度的智能对比分析
"""

import os
import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai


class KnowledgeComparisonAgent:
    """
    知识点对比Agent - 对两个知识点进行多维度智能对比
    """

    # 用户自定义知识点存储根目录
    CUSTOM_STORAGE_ROOT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "knowledge_comparison"
    )

    def __init__(self):
        """初始化知识点对比Agent"""
        self.llm = self._initialize_llm()
        self.prompt_template = self._create_comparison_prompt()
        self.visualization_prompt = self._create_visualization_prompt()

    # ==================== 用户自定义知识点管理 ====================

    def _get_user_file_path(self, user_id: str) -> str:
        """获取用户自定义知识点的文件路径"""
        user_dir = os.path.join(self.CUSTOM_STORAGE_ROOT, user_id)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, "custom_knowledge.json")

    def get_custom_knowledge(self, user_id: str) -> List[Dict[str, Any]]:
        """读取用户自定义知识点列表"""
        file_path = self._get_user_file_path(user_id)
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("custom_knowledge", [])
        except (json.JSONDecodeError, IOError):
            return []

    def add_custom_knowledge(
        self, user_id: str, name: str, category: str = "自定义"
    ) -> Dict[str, Any]:
        """添加一个自定义知识点"""
        if not name or not name.strip():
            return {"success": False, "message": "知识点名称不能为空"}

        name = name.strip()
        items = self.get_custom_knowledge(user_id)

        # 去重检查
        for item in items:
            if item.get("name") == name:
                return {"success": False, "message": f"知识点「{name}」已存在"}

        new_item = {"name": name, "category": category or "自定义"}
        items.append(new_item)

        self._save_custom_knowledge(user_id, items)
        print(f"✅ [知识点对比Agent] 用户 {user_id} 添加自定义知识点: {name}")
        return {"success": True, "data": new_item, "message": "添加成功"}

    def remove_custom_knowledge(self, user_id: str, name: str) -> Dict[str, Any]:
        """删除一个自定义知识点"""
        items = self.get_custom_knowledge(user_id)
        new_items = [item for item in items if item.get("name") != name]

        if len(new_items) == len(items):
            return {"success": False, "message": f"知识点「{name}」不存在"}

        self._save_custom_knowledge(user_id, new_items)
        print(f"✅ [知识点对比Agent] 用户 {user_id} 删除自定义知识点: {name}")
        return {"success": True, "message": "删除成功"}

    def _save_custom_knowledge(self, user_id: str, items: List[Dict[str, Any]]):
        """保存用户自定义知识点"""
        file_path = self._get_user_file_path(user_id)
        data = {
            "user_id": user_id,
            "custom_knowledge": items,
            "updated_at": __import__("datetime").datetime.now().isoformat()
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置）"""
        try:
            return get_chat_openai(temperature=0.2, max_tokens=4096)
        except Exception as e:
            raise Exception(f"初始化知识点对比Agent LLM失败: {e}")

    def _create_comparison_prompt(self) -> PromptTemplate:
        """创建知识点对比的提示词模板"""
        template = """
你是一位专业的教育内容分析师，擅长对两个相关知识点进行深度对比分析。

**任务说明：**
对「{knowledge_point_a}」和「{knowledge_point_b}」进行多维度的智能对比分析。

**要求：**
1. 从以下维度进行对比分析（如果适用）：
   - 内存分布/存储结构：数据在内存中的组织方式
   - 访问方式：随机访问、顺序访问等
   - 插入/删除操作：头部、中间、尾部的操作复杂度
   - 时间复杂度：各操作的时间复杂度分析
   - 空间开销：额外空间消耗
   - 适用场景：典型应用场景
   - 核心区别：最关键的差异点
   - 优势劣势：各自的优缺点

2. 输出必须是严格的JSON格式

3. 每个对比维度需要包含：
   - dimension: 维度名称
   - value_a: 知识点A在该维度的描述
   - value_b: 知识点B在该维度的描述

4. 还需要包含：
   - concept_a: 知识点A的核心概念（50字以内）
   - concept_b: 知识点B的核心概念（50字以内）
   - key_differences: 关键区别列表
   - summary: 总结性描述

**输出格式：**
```json
{{
  "concept_a": "知识点A核心概念",
  "concept_b": "知识点B核心概念",
  "comparisons": [
    {{
      "dimension": "内存分布",
      "value_a": "A的内存分布描述",
      "value_b": "B的内存分布描述"
    }},
    {{
      "dimension": "随机访问",
      "value_a": "A的随机访问特性",
      "value_b": "B的随机访问特性"
    }},
    {{
      "dimension": "插入/删除",
      "value_a": "A的插入删除特性",
      "value_b": "B的插入删除特性"
    }},
    {{
      "dimension": "时间复杂度",
      "value_a": "A的时间复杂度分析",
      "value_b": "B的时间复杂度分析"
    }},
    {{
      "dimension": "空间开销",
      "value_a": "A的空间开销",
      "value_b": "B的空间开销"
    }},
    {{
      "dimension": "适用场景",
      "value_a": "A的适用场景",
      "value_b": "B的适用场景"
    }}
  ],
  "key_differences": [
    "关键区别1",
    "关键区别2",
    "关键区别3"
  ],
  "summary": "总结性描述"
}}
```

**请严格按照以上JSON格式输出，不要添加任何其他内容。**

**知识点A：** {knowledge_point_a}
**知识点B：** {knowledge_point_b}
""".strip()

        return PromptTemplate.from_template(template)

    def _create_visualization_prompt(self) -> PromptTemplate:
        """创建可视化描述的提示词模板"""
        template = """
你是一位专业的数据结构可视化专家。请为「{knowledge_point}」生成一个简洁的ASCII可视化描述。

**要求：**
1. 用简单的ASCII字符展示数据结构的核心形态
2. 包含3-5个元素的示例
3. 标注关键特征（如指针、索引等）
4. 使用中文标注

**输出格式：**
返回一个包含以下内容的JSON：
- title: 可视化标题
- description: 结构描述（50字以内）
- ascii_diagram: ASCII图示（用字符串表示，保留换行符）
- highlights: 关键特征点列表

**知识点：** {knowledge_point}
""".strip()

        return PromptTemplate.from_template(template)

    async def compare_knowledge_points_async(
        self,
        knowledge_point_a: str,
        knowledge_point_b: str
    ) -> Dict[str, Any]:
        """
        异步对比两个知识点
        
        Args:
            knowledge_point_a: 知识点A名称
            knowledge_point_b: 知识点B名称
            
        Returns:
            Dict: 对比分析结果
        """
        try:
            print(f"\n🔍 [知识点对比Agent] 正在对比: {knowledge_point_a} vs {knowledge_point_b}...")

            # 并行获取两个知识点的可视化描述和对比结果
            comparison_task = self._get_comparison(knowledge_point_a, knowledge_point_b)
            viz_a_task = self._get_visualization(knowledge_point_a)
            viz_b_task = self._get_visualization(knowledge_point_b)

            comparison_result, viz_a, viz_b = await asyncio.gather(
                comparison_task, viz_a_task, viz_b_task
            )

            # 整合结果
            result = {
                "success": True,
                "knowledge_point_a": knowledge_point_a,
                "knowledge_point_b": knowledge_point_b,
                "comparison": comparison_result,
                "visualization_a": viz_a,
                "visualization_b": viz_b,
            }

            print(f"✅ 知识点对比完成: {knowledge_point_a} vs {knowledge_point_b}")
            return result

        except Exception as e:
            error_msg = f"知识点对比Agent执行失败: {e}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()

            # 失败时返回基础结构
            return {
                "success": False,
                "error": str(e),
                "knowledge_point_a": knowledge_point_a,
                "knowledge_point_b": knowledge_point_b,
                "comparison": self._get_fallback_comparison(knowledge_point_a, knowledge_point_b),
                "visualization_a": self._get_fallback_visualization(knowledge_point_a),
                "visualization_b": self._get_fallback_visualization(knowledge_point_b),
            }

    async def _get_comparison(
        self,
        knowledge_point_a: str,
        knowledge_point_b: str
    ) -> Dict[str, Any]:
        """获取对比分析结果"""
        prompt = self.prompt_template.format(
            knowledge_point_a=knowledge_point_a,
            knowledge_point_b=knowledge_point_b
        )

        response = await self.llm.ainvoke(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)

        # 清理结果并解析JSON
        result_text = self._clean_json_text(result_text)

        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            print(f"⚠️ JSON解析失败，尝试修复...")
            return self._attempt_json_fix(result_text)

    async def _get_visualization(self, knowledge_point: str) -> Dict[str, Any]:
        """获取知识点的可视化描述"""
        prompt = self.visualization_prompt.format(knowledge_point=knowledge_point)

        response = await self.llm.ainvoke(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)

        # 清理结果并解析JSON
        result_text = self._clean_json_text(result_text)

        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return self._get_fallback_visualization(knowledge_point)

    def _clean_json_text(self, text: str) -> str:
        """清理LLM返回的JSON文本"""
        # 去除markdown代码块标记
        text = re.sub(r'^```(?:json)?\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text)
        text = re.sub(r'\s*```.*', '', text)

        # 尝试提取JSON对象
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group()

        # 清理尾逗号
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        return text.strip()

    def _attempt_json_fix(self, text: str) -> Dict[str, Any]:
        """尝试修复JSON"""
        # 直接返回基础结构
        return {
            "concept_a": "待补充",
            "concept_b": "待补充",
            "comparisons": [],
            "key_differences": ["解析失败，请重试"],
            "summary": "无法完成对比分析"
        }

    def _get_fallback_comparison(
        self,
        knowledge_point_a: str,
        knowledge_point_b: str
    ) -> Dict[str, Any]:
        """获取降级版对比结果"""
        return {
            "concept_a": f"{knowledge_point_a}是一种重要的数据结构/概念",
            "concept_b": f"{knowledge_point_b}是一种相关的数据结构/概念",
            "comparisons": [
                {
                    "dimension": "核心功能",
                    "value_a": f"{knowledge_point_a}的核心功能",
                    "value_b": f"{knowledge_point_b}的核心功能"
                }
            ],
            "key_differences": [
                f"{knowledge_point_a}和{knowledge_point_b}在实现方式上存在差异",
                "两者的适用场景有所不同"
            ],
            "summary": f"{knowledge_point_a}与{knowledge_point_b}是两个相关但不同的概念"
        }

    def _get_fallback_visualization(self, knowledge_point: str) -> Dict[str, Any]:
        """获取降级版可视化"""
        return {
            "title": knowledge_point,
            "description": f"{knowledge_point}的结构示意",
            "ascii_diagram": f"[{knowledge_point}的可视化暂不可用]",
            "highlights": ["可视化生成失败"]
        }

    async def get_knowledge_list_async(
        self, course_topic: str = "", user_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取可对比的知识点列表（内置 + 用户自定义）
        
        Args:
            course_topic: 课程主题（可选，用于筛选相关知识点）
            user_id: 用户ID（可选，用于合并用户自定义知识点）
            
        Returns:
            List[Dict]: 知识点列表
        """
        # 获取内置知识点（先尝试LLM动态生成，失败则降级）
        builtin_list = self._get_builtin_knowledge_list()

        # 获取用户自定义知识点
        custom_items = []
        if user_id:
            custom_items = self.get_custom_knowledge(user_id)

        # 合并：在内置列表基础上追加"自定义"分类
        result = []
        for group in builtin_list:
            new_group = {
                "name": group.get("name", "全部知识点"),
                "category": group.get("category", ""),
                "children": list(group.get("children", []))
            }
            # 追加用户自定义分类
            if custom_items:
                new_group["children"].append({
                    "category": "自定义",
                    "items": custom_items,
                    "is_custom": True
                })
            result.append(new_group)

        return result

    def _get_builtin_knowledge_list(self) -> List[Dict[str, Any]]:
        """获取内置的知识点列表"""
        return [
            {
                "name": "全部知识点",
                "category": "",
                "children": [
                    {
                        "category": "线性结构",
                        "items": [
                            {"name": "顺序表", "category": "线性结构"},
                            {"name": "单链表", "category": "线性结构"},
                            {"name": "双向链表", "category": "线性结构"},
                            {"name": "循环链表", "category": "线性结构"},
                            {"name": "栈", "category": "线性结构"},
                            {"name": "队列", "category": "线性结构"},
                            {"name": "双端队列", "category": "线性结构"},
                        ]
                    },
                    {
                        "category": "树形结构",
                        "items": [
                            {"name": "二叉搜索树", "category": "树形结构"},
                            {"name": "AVL平衡树", "category": "树形结构"},
                            {"name": "红黑树", "category": "树形结构"},
                            {"name": "B树", "category": "树形结构"},
                            {"name": "B+树", "category": "树形结构"},
                            {"name": "堆", "category": "树形结构"},
                            {"name": "Trie树", "category": "树形结构"},
                        ]
                    },
                    {
                        "category": "图形结构",
                        "items": [
                            {"name": "图(邻接表)", "category": "图形结构"},
                            {"name": "图(邻接矩阵)", "category": "图形结构"},
                        ]
                    },
                    {
                        "category": "哈希结构",
                        "items": [
                            {"name": "哈希表", "category": "哈希结构"},
                            {"name": "布隆过滤器", "category": "哈希结构"},
                        ]
                    },
                    {
                        "category": "排序算法",
                        "items": [
                            {"name": "快速排序", "category": "排序算法"},
                            {"name": "归并排序", "category": "排序算法"},
                            {"name": "堆排序", "category": "排序算法"},
                            {"name": "冒泡排序", "category": "排序算法"},
                            {"name": "插入排序", "category": "排序算法"},
                        ]
                    },
                    {
                        "category": "查找算法",
                        "items": [
                            {"name": "二分查找", "category": "查找算法"},
                            {"name": "哈希查找", "category": "查找算法"},
                            {"name": "BFS广度优先", "category": "查找算法"},
                            {"name": "DFS深度优先", "category": "查找算法"},
                        ]
                    }
                ]
            }
        ]

    async def get_recommended_pairs_async(
        self,
        knowledge_list: List[str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        推荐值得对比的知识点组合
        
        Args:
            knowledge_list: 知识点名称列表
            limit: 返回推荐数量
            
        Returns:
            List[Dict]: 推荐的对比组合
        """
        try:
            kp_str = "、".join(knowledge_list[:30])  # 限制数量避免token过多
            
            prompt = f"""
请从以下知识点中找出最适合进行对比学习的{limit}组组合。

知识点列表：{kp_str}

要求：
1. 每组选择两个有对比价值的知识点（相似但有区别，或经常混淆）
2. 每组包含：knowledge_a、knowledge_b、reason（为什么值得对比）
3. 优先推荐在实际应用中经常需要选择的组合

输出JSON数组：
[
  {{"knowledge_a": "顺序表", "knowledge_b": "单链表", "reason": "存储结构不同，适用场景有重叠"}},
  ...
]
""".strip()

            response = await self.llm.ainvoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            
            result_text = self._clean_json_text(result_text)
            pairs = json.loads(result_text)
            
            if not isinstance(pairs, list):
                raise ValueError("返回格式错误")
            
            return pairs[:limit]

        except Exception as e:
            print(f"⚠️ 获取推荐组合失败: {e}")
            # 返回内置推荐
            return [
                {"knowledge_a": "顺序表", "knowledge_b": "单链表", "reason": "存储结构不同，适用场景有重叠"},
                {"knowledge_a": "栈", "knowledge_b": "队列", "reason": "都是线性结构，但操作受限不同"},
                {"knowledge_a": "二叉搜索树", "knowledge_b": "AVL平衡树", "reason": "BST的优化版本，理解平衡树的必要性"},
                {"knowledge_a": "B树", "knowledge_b": "B+树", "reason": "磁盘索引的两种主要实现"},
                {"knowledge_a": "哈希表", "knowledge_b": "二叉搜索树", "reason": "查找效率对比，空间换时间"},
            ]

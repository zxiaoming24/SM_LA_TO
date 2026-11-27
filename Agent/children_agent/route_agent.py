"""
路线市场助手 Agent - 智能转换学习计划为路线市场格式

核心功能：
1. 智能分析学习计划内容，自动生成路线市场信息（分类/标签/难度/简介等）
2. 将学习计划 phases 转换为路线市场标准格式
3. 生成 Mermaid 流程图语法（含知识点子图）

设计理念：
- 使用 LLM 智能分析，不依赖硬编码关键词匹配
- 支持任意领域的学习计划，不限于预定义分类
- 输出结构化 JSON，前端可直接使用
"""

import json
import re
from typing import Dict, Any, Optional, List
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai


class RouteAgent:
    """路线市场助手 Agent"""

    def __init__(self):
        self.llm = self._initialize_llm()
        self.analyze_template = self._create_analyze_template()
        self.convert_template = self._create_convert_template()
        self.flowchart_template = self._create_flowchart_template()

    def _initialize_llm(self):
        try:
            return get_chat_openai(temperature=0.3, max_tokens=3000)
        except Exception as e:
            raise Exception(f"初始化 RouteAgent LLM 失败: {e}")

    def _create_analyze_template(self) -> PromptTemplate:
        """创建智能分析学习计划的 Prompt 模板"""
        template = """
你是一个专业的学习路线分析师。请分析用户提供的学习计划，自动生成适合发布到路线市场的完整信息。

## 学习计划数据
{plan_json}

## 分析任务
请根据学习计划的标题、描述、阶段内容、知识点等信息，智能判断并生成以下字段：

1. **name**: 路线名称（简洁有力，突出核心主题）
2. **subtitle**: 副标题（概括学习路径，如"从XX到XX"）
3. **description**: 路线简介（150-200字，描述学习目标和内容体系）
4. **category**: 分类（从以下选择最匹配的：前端开发/后端开发/移动端开发/数据科学/人工智能/算法与数据结构/计算机基础/其他。如果都不匹配，根据内容自行判断一个合理的分类名称）
5. **difficulty**: 难度（easy/medium/hard，根据阶段数、知识点深度、总时长综合判断）
6. **tags**: 标签列表（5-8个核心技术/领域标签，从知识点中提取）
7. **target_audience**: 适合人群（根据难度和内容推断）
8. **estimated_duration**: 预计时长描述
9. **cover_color**: 封面颜色（根据领域选择：前端-#667eea, 后端-#f093fb, 数据-#4facfe, AI-#43e97b, 算法-#fa709a, 其他-#a18cd1）
10. **cover_icon**: 封面图标emoji（根据领域选择）

## 输出要求
严格以 JSON 格式输出，不要包含其他文字：
{{
  "name": "...",
  "subtitle": "...",
  "description": "...",
  "category": "...",
  "difficulty": "easy|medium|hard",
  "tags": ["标签1", "标签2", ...],
  "target_audience": "...",
  "estimated_duration": "...",
  "cover_color": "#xxxxxx",
  "cover_icon": "emoji"
}}

## 分析原则
- 分类判断要准确，根据核心知识点而非表面关键词
- 难度评估要合理：1-2阶段且<50h为easy，3-4阶段或50-150h为medium，5+阶段或>150h或含高级主题为hard
- 标签要从实际知识点中提取，不要臆造
- 简介要专业、有吸引力，突出学习价值
"""
        return PromptTemplate.from_template(template)

    def _create_convert_template(self) -> PromptTemplate:
        """创建学习计划转路线市场格式的 Prompt 模板"""
        template = """
你是一个学习计划格式转换专家。请将用户的学习计划转换为路线市场的标准 phases 格式。

## 原始学习计划 phases
{phases_json}

## 转换要求
将每个阶段转换为以下标准格式：
- phase: 阶段序号（从1开始）
- name: 阶段名称（简洁明了）
- weeks: 时间范围（如"第1-2周"）
- description: 阶段描述（1-2句话概括本阶段学习内容）
- knowledge_points: 知识点列表（保持原样或适当整理）
- resource_types: 推荐资源类型列表（如 ["视频", "练习题", "文档"]）
- milestone: 里程碑目标（完成什么算通过本阶段）
- estimated_hours: 预估学时（数字）
- difficulty: 本阶段难度（easy/medium/hard）

## 输出要求
严格以 JSON 数组格式输出：
[
  {{
    "phase": 1,
    "name": "...",
    "weeks": "...",
    "description": "...",
    "knowledge_points": ["知识点1", "知识点2"],
    "resource_types": ["视频", "练习题"],
    "milestone": "...",
    "estimated_hours": 20,
    "difficulty": "medium"
  }},
  ...
]

## 转换原则
- 保持原始知识点的完整性，不要遗漏
- 如果原始数据缺少某些字段，根据上下文合理推断填充
- milestone 要具体可衡量
- estimated_hours 要合理（每个阶段通常10-40小时）
"""
        return PromptTemplate.from_template(template)

    def _create_flowchart_template(self) -> PromptTemplate:
        """创建 Mermaid 流程图生成的 Prompt 模板"""
        template = """
你是一个流程图设计专家。请根据学习路线的阶段和知识点，生成 Mermaid 语法的竖向流程图。

## 路线数据
{route_json}

## 输出要求
生成 Mermaid flowchart TD（从上到下）语法的流程图，要求：
1. 开始节点 → 各阶段 → 完成节点
2. 每个阶段节点显示：阶段编号、名称、时间
3. 每个阶段下方用 subgraph 展示知识点（知识点横向排列 direction LR）
4. 阶段之间用箭头连接
5. 节点文本中不要使用双引号，用单引号或不用引号
6. 知识点名称超过15字时截断加...

## Mermaid 语法示例
graph TD
  START((开始)) --> P1
  P1["阶段1: Python基础\\n第1-2周"]
  subgraph SP1["知识点"]
    direction LR
    KP1_1["变量与类型"]
    KP1_2["控制流程"]
    KP1_3["函数定义"]
  end
  P1 --- SP1
  P1 --> P2
  P2["阶段2: 数据分析\\n第3-4周"]
  subgraph SP2["知识点"]
    direction LR
    KP2_1["Pandas基础"]
    KP2_2["数据可视化"]
  end
  P2 --- SP2
  P2 --> END((完成))

## 输出
只输出 Mermaid 代码，不要包含 ```mermaid 标记和其他文字。
"""
        return PromptTemplate.from_template(template)

    def analyze_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能分析学习计划，生成路线市场信息。

        Args:
            plan_data: 学习计划数据（含 title, description, phases 等）

        Returns:
            自动生成的路线信息字典
        """
        plan_json = json.dumps(plan_data, ensure_ascii=False, indent=2)
        prompt = self.analyze_template.format(plan_json=plan_json)

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # 提取 JSON（处理可能的 markdown 代码块包裹）
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                print(f"✅ [RouteAgent] 智能分析完成: {result.get('name', '')} -> {result.get('category', '')}")
                return result
            else:
                print(f"⚠️ [RouteAgent] LLM 返回非 JSON 格式: {content[:100]}")
                return self._fallback_analyze(plan_data)
        except json.JSONDecodeError as e:
            print(f"⚠️ [RouteAgent] JSON 解析失败: {e}")
            return self._fallback_analyze(plan_data)
        except Exception as e:
            print(f"❌ [RouteAgent] 分析失败: {e}")
            return self._fallback_analyze(plan_data)

    def convert_phases(self, phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将学习计划的 phases 转换为路线市场标准格式。

        Args:
            phases: 原始学习计划阶段列表

        Returns:
            转换后的标准 phases 列表
        """
        phases_json = json.dumps(phases, ensure_ascii=False, indent=2)
        prompt = self.convert_template.format(phases_json=phases_json)

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # 提取 JSON 数组
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                result = json.loads(json_match.group())
                print(f"✅ [RouteAgent] 阶段转换完成: {len(result)} 个阶段")
                return result
            else:
                print(f"️ [RouteAgent] 转换返回非 JSON 格式")
                return self._fallback_convert(phases)
        except json.JSONDecodeError as e:
            print(f"⚠️ [RouteAgent] 转换 JSON 解析失败: {e}")
            return self._fallback_convert(phases)
        except Exception as e:
            print(f" [RouteAgent] 转换失败: {e}")
            return self._fallback_convert(phases)

    def generate_flowchart(self, route_data: Dict[str, Any]) -> str:
        """
        生成 Mermaid 流程图语法。

        Args:
            route_data: 路线数据（含 phases）

        Returns:
            Mermaid 流程图语法字符串
        """
        route_json = json.dumps(route_data, ensure_ascii=False, indent=2)
        prompt = self.flowchart_template.format(route_json=route_json)

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            # 移除可能的 markdown 代码块标记
            content = re.sub(r'^```mermaid\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            print(f"✅ [RouteAgent] 流程图生成完成")
            return content
        except Exception as e:
            print(f"❌ [RouteAgent] 流程图生成失败: {e}")
            return self._fallback_flowchart(route_data)

    # ==================== 降级方案（LLM 不可用时） ====================

    def _fallback_analyze(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """LLM 不可用时的降级分析"""
        title = plan_data.get("title", "用户分享的学习路线")
        phases = plan_data.get("phases", [])
        total_hours = sum(p.get("estimated_hours", 0) for p in phases)

        # 简单推断难度
        if len(phases) >= 5 or total_hours >= 200:
            difficulty = "hard"
        elif len(phases) >= 3 or total_hours >= 100:
            difficulty = "medium"
        else:
            difficulty = "easy"

        # 生成副标题
        subtitle = ""
        if phases:
            first = phases[0].get("name", "")
            last = phases[-1].get("name", "")
            if first and last:
                subtitle = f"从{first}到{last}"

        # 生成简介
        all_kps = []
        for p in phases:
            all_kps.extend(p.get("knowledge_points", []))
        if all_kps:
            kp_summary = "、".join(all_kps[:6])
            if len(all_kps) > 6:
                kp_summary += f"等{len(all_kps)}个知识点"
            description = f"本路线系统覆盖{title}的核心知识体系，包含{len(phases)}个学习阶段，涵盖{kp_summary}。通过循序渐进的学习路径，帮助学习者构建完整的能力体系。"
        else:
            description = f"本路线包含{len(phases)}个学习阶段，预计{total_hours}小时。"

        return {
            "name": title,
            "subtitle": subtitle,
            "description": description,
            "category": "其他",
            "difficulty": difficulty,
            "tags": [kp for kp in all_kps[:8] if len(kp) <= 12],
            "target_audience": "有一定基础的学习者",
            "estimated_duration": plan_data.get("total_duration", f"约{total_hours}小时"),
            "cover_color": "#a18cd1",
            "cover_icon": "📚",
        }

    def _fallback_convert(self, phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """LLM 不可用时的降级转换"""
        result = []
        for idx, p in enumerate(phases, 1):
            result.append({
                "phase": idx,
                "name": p.get("name", f"阶段{idx}"),
                "weeks": p.get("weeks", ""),
                "description": p.get("description", ""),
                "knowledge_points": p.get("knowledge_points", []),
                "resource_types": p.get("resource_types", []),
                "milestone": p.get("milestone", ""),
                "estimated_hours": p.get("estimated_hours", 0),
                "difficulty": p.get("difficulty", "medium"),
            })
        return result

    def _fallback_flowchart(self, route_data: Dict[str, Any]) -> str:
        """LLM 不可用时的降级流程图"""
        phases = route_data.get("phases", [])
        lines = ["graph TD"]
        lines.append("  START((开始)) --> P1")

        for i, phase in enumerate(phases):
            num = i + 1
            name = phase.get("name", "").replace('"', "'")
            weeks = phase.get("weeks", "").replace('"', "'")
            milestone = phase.get("milestone", "").replace('"', "'")
            kps = phase.get("knowledge_points", [])

            label = f"阶段{num}: {name}\\n{weeks}"
            if milestone:
                label += f"\\n {milestone}"
            lines.append(f'  P{num}["{label}"]')

            if kps:
                lines.append(f'  subgraph SP{num}["知识点"]')
                lines.append('    direction LR')
                for j, kp in enumerate(kps):
                    kp_name = kp.replace('"', "'").replace('\n', ' ')
                    if len(kp_name) > 15:
                        kp_name = kp_name[:13] + '...'
                    lines.append(f'    KP{num}_{j+1}["{kp_name}"]')
                lines.append('  end')
                lines.append(f'  P{num} --- SP{num}')

            if i < len(phases) - 1:
                lines.append(f"  P{num} --> P{num + 1}")
            else:
                lines.append(f"  P{num} --> END((完成))")

        return "\n".join(lines)

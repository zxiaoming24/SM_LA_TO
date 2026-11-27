"""
动态特征更新子Agent - 随学随新的用户画像调整器

核心功能：
1. 根据不同任务类型动态调整特征权重比例
2. 基于学习过程中的表现实时更新用户画像
3. 支持增量式特征演化，实现个性化自适应
4. 维护特征的历史变化轨迹，支持回溯分析
5. **中央特征管理**：统一管理所有用户的最新特征，确保各子Agent获取的是最新状态

使用场景：
- 练习题生成后根据答题情况调整认知能力评分
- 视频学习后根据观看行为调整学习行为维度
- 文档阅读后根据理解程度调整学术背景维度
- 思维导图创建后根据结构化能力调整认知能力

架构设计：
- 单例模式：整个系统只有一个实例，保证特征数据的一致性
- 链式更新：Agent A更新后的特征 → 存入中央管理器 → Agent B获取最新特征
- 持久化存储：自动保存到磁盘，支持跨会话恢复
"""

import os
import json
import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai

# ChromaDB 存储（8维度特征语义检索用）
try:
    import chromadb
    from chromadb.config import Settings
    _CHROMADB_AVAILABLE = True
except ImportError:
    _CHROMADB_AVAILABLE = False


class DynamicFeatureUpdater:
    """
    动态特征更新器 - 实现随学随新的用户画像动态调整
    
    设计原则：
    1. 不同任务对应不同的调整权重策略
    2. 基于证据的渐进式更新，避免剧烈波动
    3. 保留历史轨迹，支持趋势分析
    4. 置信度驱动，高质量数据才有高影响力
    5. **中央化管理**：单例模式，统一管理所有用户特征
    """
    
    # 单例模式和线程安全
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式：确保整个系统只有一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, storage_path: str = "./user_features"):  #  进行实时更新得到数据，不可依赖内存进行
        """初始化动态特征更新器（只初始化一次）"""
        if self._initialized:
            return
        
        self.llm = self._initialize_llm()
        self.update_template = self._create_update_template()
        self.weight_strategy = self._load_weight_strategies()  #  权重策率
        
        # === 中央特征管理功能 ===
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # ★★★ Lock 目录（多进程文件锁用）★★★
        self._lock_dir = self.storage_path / ".locks"
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        
        self._cleanup_stale_locks()
        
        # 内存中的特征缓存 {user_id: features}
        self._features_cache: Dict[str, Dict[str, Any]] = {}
        
        # 特征变更历史 {user_id: [update_records]}
        self._update_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # 线程锁，保证并发安全
        self._user_locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

        # === ChromaDB 存储（8维度特征语义检索） ===
        self._chroma_client = None
        self._chroma_collection = None
        if _CHROMADB_AVAILABLE:
            self._init_chroma()

        self._initialized = True
        print("✅ DynamicFeatureUpdater 初始化完成（单例模式 + 中央特征管理）")

    def _init_chroma(self):
        """初始化 ChromaDB 客户端（存储8维度特征，支持语义检索）"""
        try:
            chroma_path = Path("./memory/user_features_db")
            chroma_path.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=str(chroma_path))
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="user_feature_profiles",
                metadata={"description": "用户8维度特征画像（支持语义检索）"}
            )
            print(f"✅ ChromaDB 特征存储已初始化: {chroma_path}")
        except Exception as e:
            print(f"⚠️ ChromaDB 初始化失败: {e}，8维度特征将仅存JSON")

    def _save_to_chroma(self, user_id: str, features: Dict[str, Any]):
        """将8维度特征存入 ChromaDB（用于语义检索）"""
        if not _CHROMADB_AVAILABLE or self._chroma_collection is None:
            return

        all_8_dims = [
            "academic_background", "learning_behavior", "goal_motivation",
            "cognitive_abilities", "emotional_state", "social_interaction",
            "time_management", "creativity_innovation"
        ]
        dim_labels = ["学术背景", "学习行为", "目标动机", "认知能力", "情绪状态", "社交互动", "时间管理", "创新创造"]

        for attempt in range(2):  # 首次尝试 + 修复后重试
            try:
                overall_score = features.get("summary_scores", {}).get("overall_score", 0)

                # 每个维度存一条记录，方便后续语义检索"哪些用户情绪状态差"
                for i, dim in enumerate(all_8_dims):
                    dim_data = features.get(dim, {})
                    score = dim_data.get("score", 0)
                    # 构建可检索的文本描述
                    fields_str = ", ".join([f"{k}={v}" for k, v in dim_data.items() if k != "score" and v])
                    text = f"用户{user_id}的{dim_labels[i]}维度：分数={score}，具体表现={fields_str}。"

                    doc_id = f"{user_id}_{dim}"
                    self._chroma_collection.upsert(
                        ids=[doc_id],
                        documents=[text],
                        metadatas=[{
                            "user_id": user_id,
                            "dimension": dim,
                            "dimension_zh": dim_labels[i],
                            "score": score,
                            "overall_score": overall_score
                        }]
                    )
                print(f"✅ [ChromaDB] 用户 {user_id} 的8维度特征已存入向量数据库")
                return  # 成功则退出
            except Exception as e:
                err_msg = str(e)
                if attempt == 0 and ("hnsw" in err_msg.lower() or "compaction" in err_msg.lower() or "segment reader" in err_msg.lower()):
                    print(f"⚠️ [ChromaDB] 索引损坏，正在尝试修复...")
                    self._repair_chroma_collection()
                else:
                    print(f"⚠️ [ChromaDB] 存储失败: {e}")
                    return

    def _repair_chroma_collection(self):
        """修复损坏的 ChromaDB collection（删除重建）"""
        try:
            collection_name = self._chroma_collection.name
            self._chroma_client.delete_collection(collection_name)
            self._chroma_collection = self._chroma_client.create_collection(
                name=collection_name,
                metadata={"description": "用户8维度特征画像（支持语义检索）"}
            )
            print(f"✅ [ChromaDB] 损坏的 collection '{collection_name}' 已重建")
        except Exception as e:
            print(f"⚠️ [ChromaDB] 修复失败: {e}，8维度特征将仅存JSON")
            self._chroma_collection = None
        
    def _compact_features_for_prompt(self, features: Dict[str, Any], compression_level: str = "auto") -> Dict[str, Any]:     #  显然要是将所有信息都添加的话导致即使在大的max_tokens也会实现json截断  所以需要将json压缩！！！！
        """
        使用JZON(结构感知压缩)精简特征数据用于Prompt
        
        JZON原理:
        - 提取Schema(z.f): 所有维度的字段名
        - 压缩实例(z.c): 只保留值数组
        - LLM通过Schema理解数据结构
        
        压缩策略(三级):
        - minimal: JZON + 仅保留score (最激进,~80 tokens)
        - balanced: JZON + 保留关键字段 (平衡,~200 tokens)  
        - detailed: JZON + 保留所有字段 (详细,~400 tokens)
        - auto: 根据特征数量自动选择
        
        Args:
            features: 完整特征数据
            compression_level: 压缩级别 (minimal/balanced/detailed/auto)
            
        Returns:
            Dict: JZON压缩后的特征数据
        """
        if not features:
            return {}
        
        # ★★★ 自动选择压缩级别 ★★★
        if compression_level == "auto":
            estimated_tokens = len(str(features)) // 4
            if estimated_tokens > 2000:
                compression_level = "minimal"
            elif estimated_tokens > 1000:
                compression_level = "balanced"
            else:
                compression_level = "detailed"
        
        dimensions = [
            "academic_background", "learning_behavior", "goal_motivation",
            "cognitive_abilities", "emotional_state", "social_interaction",
            "time_management", "creativity_innovation"
        ]
        
        # ★★★ 定义每个维度的Schema(字段顺序固定) ★★★
        schema_map = {
            "minimal": {
                "academic_background": ["score"],
                "learning_behavior": ["score"],
                "goal_motivation": ["score"],
                "cognitive_abilities": ["score"],
                "emotional_state": ["score"],
                "social_interaction": ["score"],
                "time_management": ["score"],
                "creativity_innovation": ["score"]
            },
            "balanced": {
                "academic_background": ["score", "knowledge_level", "foundation_level"],
                "learning_behavior": ["score", "learning_style", "resource_preference"],
                "goal_motivation": ["score", "motivation_strength", "short_term_goals"],
                "cognitive_abilities": ["score", "logical_thinking", "problem_solving"],
                "emotional_state": ["score", "interest_level", "confidence_level", "frustration_tolerance", "anxiety_level"],
                "social_interaction": ["score", "collaboration_tendency", "help_seeking_pattern"],
                "time_management": ["score", "learning_regularity", "time_allocation_efficiency"],
                "creativity_innovation": ["score", "divergent_thinking", "experimental_exploration"]
            },
            "detailed": {
                "academic_background": ["score", "knowledge_level", "ability_tendency", "foundation_level"],
                "learning_behavior": ["score", "learning_style", "learning_pace", "interaction_level", "resource_preference"],
                "goal_motivation": ["score", "motivation_strength", "short_term_goals", "achievement_expectation"],
                "cognitive_abilities": ["score", "logical_thinking", "creative_thinking", "problem_solving", "metacognition"],
                "emotional_state": ["score", "interest_level", "frustration_tolerance", "anxiety_level", "confidence_level"],
                "social_interaction": ["score", "collaboration_tendency", "help_seeking_pattern", "knowledge_sharing_willingness"],
                "time_management": ["score", "learning_regularity", "priority_judgment", "time_allocation_efficiency"],
                "creativity_innovation": ["score", "divergent_thinking", "cross_domain_association", "experimental_exploration", "original_expression"]
            }
        }
        
        schema = schema_map.get(compression_level, schema_map["balanced"])
        
        # ★★★ 构建JZON格式 ★★★
        jzon_data = {
            "z.f": {},  # Schema: {维度名: [字段列表]}
            "z.c": {}   # Compressed: {维度名: [值数组]}
        }
        
        for dim in dimensions:
            if dim not in features:
                continue
            
            dim_data = features[dim]
            fields = schema.get(dim, ["score"])
            
            # 提取Schema
            jzon_data["z.f"][dim] = fields
            
            # 提取值数组(按Schema顺序)
            values = []
            for field in fields:
                value = dim_data.get(field, None)
                # 字符串截断(最多40字符)
                if isinstance(value, str) and len(value) > 40:
                    value = value[:37] + "..."
                values.append(value)
            
            jzon_data["z.c"][dim] = values
        
        return jzon_data

    def build_student_profile_for_prompt(self, features: Dict[str, Any]) -> str:
        """将8维度特征构建为可直接嵌入 LLM Prompt 的可读文本

        各Agent统一调用此方法，避免重复实现 _build_student_profile_section
        """
        if not features:
            return "【学生画像】未获取到（将使用通用配置）"
        jzon = self._compact_features_for_prompt(features, compression_level="balanced")
        lines = ["【学生画像 - 请据此调整学习资源的深度与风格】"]
        schema_map = jzon.get("z.f", {})
        values_map = jzon.get("z.c", {})
        for dim, fields in schema_map.items():
            values = values_map.get(dim, [])
            for field_name, val in zip(fields, values):
                if val is not None:
                    lines.append(f"  - {field_name}: {val}")
        return "\n".join(lines) if len(lines) > 1 else "【学生画像】信息不足（将使用通用配置）"

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置）"""
        try:
            return get_chat_openai(temperature=0.2, max_tokens=4096, timeout=60)
        except Exception as e:
            raise Exception(f"初始化动态特征更新器LLM失败: {e}")
    
    def _create_update_template(self) -> PromptTemplate:
        """创建特征更新的提示词模板"""
        template = """
你是一位专业的教育心理学专家和数据分析师，负责根据学生的学习表现动态调整其个人画像特征。

**当前学生特征画像：**
{current_features}

**本次学习任务信息：**
- 任务类型：{task_type}
- 任务内容：{task_content}
- 学习表现：{performance_data}
- 完成质量：{completion_quality}
- 时间消耗：{time_spent}

**任务类型对应的调整策略：**
{adjustment_strategy}

**调整原则：**
1. **渐进式更新**：单次调整幅度不超过±15分，避免剧烈波动
2. **证据驱动**：基于具体表现数据，而非主观臆断
3. **多维度关联**：一个维度的变化可能影响相关维度
4. **衰减机制**：旧证据的影响力随时间衰减
5. **一致性检查**：确保各维度间的逻辑一致性

**需要调整的维度说明：**
- academic_background (学术背景): 知识掌握、专业能力
- learning_behavior (学习行为): 学习习惯、资源偏好、参与度
- goal_motivation (目标动机): 学习目标清晰度、动机强度
- cognitive_abilities (认知能力): 逻辑思维、创造性、问题解决
- emotional_state (情绪状态): 学习兴趣、挫折承受、焦虑水平、自信心
- social_interaction (社交互动): 协作倾向、求助行为、分享意愿、同伴影响
- time_management (时间管理): 学习规律性、优先级判断、拖延倾向、时间效率
- creativity_innovation (创新创造): 发散思维、跨界联想、实验探索、原创表达
- emotional_state (情绪状态): 学习兴趣、挫折承受、焦虑水平、自信心
- social_interaction (社交互动): 协作倾向、求助行为、分享意愿、同伴影响
- time_management (时间管理): 学习规律性、优先级判断、拖延倾向、时间效率
- creativity_innovation (创新创造): 发散思维、跨界联想、实验探索、原创表达

**输出格式（严格的JSON）：**
```json
{{
  "updated_features": {{
    "academic_background": {{
      "major_preference": "",
      "knowledge_level": "",
      "ability_tendency": "",
      "foundation_level": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }},
    "learning_behavior": {{
      "learning_style": "",
      "learning_pace": "",
      "interaction_level": "",
      "resource_preference": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }},
    "goal_motivation": {{
      "short_term_goals": "",
      "long_term_career": "",
      "motivation_strength": "",
      "achievement_expectation": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }},
    "cognitive_abilities": {{
      "logical_thinking": "",
      "creative_thinking": "",
      "problem_solving": "",
      "metacognition": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }},
    "emotional_state": {{
      "interest_level": "",
      "frustration_tolerance": "",
      "anxiety_level": "",
      "confidence_level": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }},
    "social_interaction": {{
      "collaboration_tendency": "",
      "help_seeking_pattern": "",
      "knowledge_sharing_willingness": "",
      "peer_influence": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }},
    "time_management": {{
      "learning_regularity": "",
      "priority_judgment": "",
      "procrastination_tendency": "",
      "time_allocation_efficiency": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }},
    "creativity_innovation": {{
      "divergent_thinking": "",
      "cross_domain_association": "",
      "experimental_exploration": "",
      "original_expression": "",
      "score": 0,
      "change_reason": "调整原因说明",
      "confidence": 0-100
    }}
  }},
  "dimension_changes": {{
    "academic_background_delta": 0,
    "learning_behavior_delta": 0,
    "goal_motivation_delta": 0,
    "cognitive_abilities_delta": 0,
    "emotional_state_delta": 0,
    "social_interaction_delta": 0,
    "time_management_delta": 0,
    "creativity_innovation_delta": 0
  }},
  "summary_scores": {{
    "dimension_scores": [0, 0, 0, 0, 0, 0, 0, 0],
    "overall_score": 0,
    "trend": "上升/下降/稳定"
  }},
  "update_metadata": {{
    "timestamp": "{timestamp}",
    "task_type": "{task_type}",
    "evidence_quality": "high/medium/low",
    "key_observations": ["关键观察点1", "关键观察点2"],
    "recommendations": ["后续建议1", "后续建议2"]
  }}
}}
```

**重要要求：**
- **只输出JSON，不要包含任何解释文字、注释或其他内容**
- change_reason必须具体说明调整依据
- confidence反映本次调整的可靠程度
- key_observations记录触发调整的关键行为
- recommendations给出下一步学习建议
- 确保JSON格式正确，每个字段后面都要有逗号（除了最后一个）
- 字符串值中如果包含引号，请使用\\"转义
- 数值类型不要加引号
""".strip()
        
        return PromptTemplate.from_template(template)
    
    def _load_weight_strategies(self) -> Dict[str, Dict[str, float]]:
        """
        加载不同任务类型的权重调整策略（8个维度）
        
        Returns:
            Dict: 任务类型到各维度权重的映射
        """
        return {
            # 编程练习题场景：重点评估认知能力、知识掌握、创新思维
            "practice": {
                "academic_background": 0.15,
                "learning_behavior": 0.20,
                "goal_motivation": 0.15,
                "cognitive_abilities": 0.25,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.25,
                "max_adjustment": 12,
                "description": "编程练习场景，重点评估认知能力、知识掌握、创新思维"
            },
            
            # ★★★ 理论题场景：侧重知识掌握、理解能力，不涉及创新思维（与编程题区分）★★★
            "theory": {
                "academic_background": 0.35,
                "learning_behavior": 0.20,
                "goal_motivation": 0.15,
                "cognitive_abilities": 0.30,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 10,
                "description": "理论题场景，重点评估知识掌握、学术基础、理解能力"
            },
            
            # 视频学习场景：重点关注学习行为、学术背景（不影响情绪、社交、时间、创新）
            "video_learning": {
                "academic_background": 0.25,
                "learning_behavior": 0.40,
                "goal_motivation": 0.15,
                "cognitive_abilities": 0.20,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 10,
                "description": "视频学习场景，重点观察学习习惯、资源偏好"
            },

            # ★★★ 视频回溯困惑场景：用户回看视频可能因不理解而产生困惑 ★★★
            # 重点关注学习行为（回溯频率）、认知能力（是否需额外帮助）
            # 同时影响情绪状态（焦虑/自信）和学术背景
            "video_rewind_confusion": {
                "academic_background": 0.20,
                "learning_behavior": 0.35,
                "goal_motivation": 0.10,
                "cognitive_abilities": 0.20,
                "emotional_state": 0.15,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 6,
                "description": "视频回溯困惑，用户回看视频可能表示不理解，关联认知和情绪"
            },
            
            # 文档阅读场景：重点关注学术背景、认知能力（不影响情绪、社交、时间、创新）
            "document_reading": {
                "academic_background": 0.35,
                "learning_behavior": 0.20,
                "goal_motivation": 0.15,
                "cognitive_abilities": 0.30,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 10,
                "description": "文档阅读场景，评估理解能力、知识吸收"
            },
            
            # 思维导图场景：重点关注认知能力、学术背景（不影响情绪、社交、时间、创新）
            "mindmap_creation": {
                "academic_background": 0.25,
                "learning_behavior": 0.15,
                "goal_motivation": 0.15,
                "cognitive_abilities": 0.45,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 15,
                "description": "思维导图创建，评估逻辑思维、结构化能力"
            },
            
            # 扩展阅读场景：均衡调整学术背景和认知能力（不影响情绪、社交、时间、创新）
            "extension_reading": {
                "academic_background": 0.35,
                "learning_behavior": 0.20,
                "goal_motivation": 0.20,
                "cognitive_abilities": 0.25,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 8,
                "description": "扩展阅读场景，拓展知识面"
            },
            
            # 教学指导场景：重点关注目标动机、学术背景（不影响情绪、社交、时间、创新）
            "teaching_guidance": {
                "academic_background": 0.25,
                "learning_behavior": 0.20,
                "goal_motivation": 0.35,
                "cognitive_abilities": 0.20,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 10,
                "description": "教学指导场景，明确学习目标、路径规划"
            },
            
            # ★★★ YOLO情绪检测场景：只影响情绪状态和学习行为 ★★★
            "emotion_detection": {
                "academic_background": 0.0,
                "learning_behavior": 0.30,
                "goal_motivation": 0.0,
                "cognitive_abilities": 0.0,
                "emotional_state": 0.70,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 8,
                "description": "YOLO实时情绪检测，重点更新情绪状态和间接影响学习行为"
            },
            
            # ★★★ 动画生成场景：重点关注创新创造、认知能力、学术背景（不影响情绪、社交、时间）★★★
            "animation_generation": {
                "academic_background": 0.25,
                "learning_behavior": 0.15,
                "goal_motivation": 0.15,
                "cognitive_abilities": 0.20,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.25,
                "max_adjustment": 10,
                "description": "动画生成场景，评估创新能力、可视化理解、知识表达"
            },
            
            # ★★★ 聊天对话场景：所有维度都可能受影响，重点关注情绪、目标动机、
            #    学习行为，但调整幅度小（LLM 根据对话内容分析各维度表现）★★★
            "chat_conversation": {
                "academic_background": 0.10,
                "learning_behavior": 0.15,
                "goal_motivation": 0.20,
                "cognitive_abilities": 0.10,
                "emotional_state": 0.25,
                "social_interaction": 0.10,
                "time_management": 0.05,
                "creativity_innovation": 0.05,
                "max_adjustment": 6,
                "description": "日常对话场景，LLM综合分析各维度表现"
            },
            
            # ★★★ 社区活动场景：核心影响社交互动维度，轻度影响情绪和学习行为 ★★★
            "community_activity": {
                "academic_background": 0.0,
                "learning_behavior": 0.10,
                "goal_motivation": 0.0,
                "cognitive_abilities": 0.0,
                "emotional_state": 0.15,
                "social_interaction": 0.55,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 8,
                "description": "社区活动场景，重点评估社交互动表现"
            },
            
            # ★★★ PPT生成场景：重点关注学术背景、学习行为、认知能力、创新创造 ★★★
            "ppt_generation": {
                "academic_background": 0.30,
                "learning_behavior": 0.20,
                "goal_motivation": 0.15,
                "cognitive_abilities": 0.20,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.15,
                "max_adjustment": 10,
                "description": "PPT生成场景，评估知识整合、内容组织、视觉表达能力"
            },

            # ★★★ 笔记写作场景：评估知识整理、理解深度、结构化表达能力 ★★★
            "note_writing": {
                "academic_background": 0.30,
                "learning_behavior": 0.20,
                "goal_motivation": 0.10,
                "cognitive_abilities": 0.25,
                "emotional_state": 0.05,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.10,
                "max_adjustment": 8,
                "description": "笔记写作场景，评估知识整理、理解深度、结构化表达能力"
            },

            # 默认策略：只影响前4个核心维度
            "default": {
                "academic_background": 0.30,
                "learning_behavior": 0.25,
                "goal_motivation": 0.25,
                "cognitive_abilities": 0.20,
                "emotional_state": 0.0,
                "social_interaction": 0.0,
                "time_management": 0.0,
                "creativity_innovation": 0.0,
                "max_adjustment": 10,
                "description": "默认策略，仅影响核心学习维度"
            }
        }
    
    # ==================== 中央特征管理方法 ====================
    
    def _get_user_lock(self, user_id: str) -> threading.Lock:
        """获取用户级别的线程锁"""
        with self._global_lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = threading.Lock()
            return self._user_locks[user_id]

    def _acquire_user_file_lock(self, user_id: str, timeout: float = 10.0) -> Optional[object]:
        """获取用户级别的文件锁（多进程互斥）

        Args:
            user_id: 用户ID
            timeout: 等待超时（秒）

        Returns:
            锁句柄（用完需释放），超时返回 None
        """
        import time as _time
        lock_file = self._lock_dir / f"{user_id}.lock"
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return fd
            except FileExistsError:
                _time.sleep(0.05)
        return None

    def _release_user_file_lock(self, fd: object, user_id: str):
        """释放用户级别的文件锁（正确关闭fd并删除锁文件）

        Args:
            fd: 文件锁句柄
            user_id: 用户ID，用于定位锁文件
        """
        import os as _os
        if fd is not None:
            try:
                _os.close(fd)
                lock_file = self._lock_dir / f"{user_id}.lock"
                if lock_file.exists():
                    lock_file.unlink()
            except Exception:
                pass

    def _cleanup_stale_locks(self, max_age_seconds: int = 300):
        """清理过期的锁文件（进程崩溃后残留）

        Args:
            max_age_seconds: 锁文件最大存活时间（秒），超过此时间视为过期
        """
        try:
            for lock_file in self._lock_dir.glob("*.lock"):
                if time.time() - lock_file.stat().st_mtime > max_age_seconds:
                    lock_file.unlink()
                    print(f"🗑️ [FeatureUpdater] 清理过期锁文件: {lock_file.name}")
        except Exception:
            pass

    def _read_features_atomic(self, user_id: str) -> Optional[Dict[str, Any]]:
        """在锁保护下从磁盘读取最新特征（跳过内存缓存，保证读到最新）"""
        feature_file = self.storage_path / f"{user_id}.json"
        if feature_file.exists():
            try:
                with open(feature_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                features = data.get('current_features', data.get('features', {}))
                if 'update_history' in data:
                    self._update_history[user_id] = data['update_history']
                self._features_cache[user_id] = features
                return features.copy()
            except Exception as e:
                print(f"❌ [FeatureUpdater] 原子读取失败: {e}")
                return None
        return None

    async def atomic_update_features_async(
        self,
        user_id: str,
        task_type: str,
        task_content: str,
        performance_data: Dict[str, Any],
        completion_quality: str = "medium",
        time_spent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """原子化特征更新（异步版本）"""
        thread_lock = self._get_user_lock(user_id)
        file_lock = self._acquire_user_file_lock(user_id)

        try:
            # Step 1: 快速读取特征（持锁）
            with thread_lock:
                current_features = self._read_features_atomic(user_id)
                if not current_features:
                    return {
                        "status": "error",
                        "features": {},
                        "message": f"用户 {user_id} 特征不存在，请先初始化"
                    }

            # Step 2: LLM调用（不持锁，可以自由等待）
            result = await self.update_features_async(
                current_features=current_features,
                task_type=task_type,
                task_content=task_content,
                performance_data=performance_data,
                completion_quality=completion_quality,
                time_spent=time_spent,
                user_id=user_id
            )

            return result
        finally:
            # Step 3: 释放文件锁（确保所有路径都能释放）
            if file_lock is not None:
                self._release_user_file_lock(file_lock, user_id)
    
    def get_latest_features(self, user_id: str) -> Optional[Dict[str, Any]]:      #   直接就是进行随学随新的核心代码
        """
        获取用户的最新特征（所有子Agent都通过此方法获取最新特征）
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户特征字典，如果不存在返回None
        """
        lock = self._get_user_lock(user_id)
        
        with lock:  #  锁定当前的用户
            # 先从缓存中获取
            if user_id in self._features_cache:
                print(f"📖 [FeatureUpdater] 从缓存加载用户 {user_id} 的最新特征")
                return self._features_cache[user_id].copy()
            
            # 缓存未命中，从磁盘加载
            feature_file = self.storage_path / f"{user_id}.json"
            if feature_file.exists():
                try:
                    with open(feature_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # ★★★ 兼容新旧格式：优先使用 current_features，回退到 features ★★★
                    features = data.get('current_features', data.get('features', {}))
                    
                    # ★★★ 加载历史记录（如果存在）★★★
                    if 'update_history' in data:
                        self._update_history[user_id] = data['update_history']
                    
                    self._features_cache[user_id] = features
                    print(f"📖 [FeatureUpdater] 从磁盘加载用户 {user_id} 的特征")
                    return features.copy()
                except Exception as e:
                    print(f"❌ [FeatureUpdater] 加载特征文件失败: {e}")
                    return None
            
            print(f"⚠️ [FeatureUpdater] 用户 {user_id} 的特征不存在")
            return None

    async def get_latest_features_async(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        异步获取用户的最新特征（用 asyncio.to_thread 包裹文件 IO）
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户特征字典，如果不存在返回None
        """
        return await asyncio.to_thread(self.get_latest_features, user_id)  #  实现的还是同步方法get_latest_features 只不过使用线程包裹实现间接异步

    def clear_cache(self, user_id: str):
        """清除指定用户的内存缓存，下次读取时从磁盘重新加载"""
        with self._global_lock:
            if user_id in self._features_cache:
                del self._features_cache[user_id]
                print(f"✅ [FeatureUpdater] 已清除用户 {user_id} 的内存缓存")

    def initialize_user_features(self, user_id: str, initial_features: Dict[str, Any]) -> bool:
        """
        初始化用户特征（仅在用户首次使用时调用）
        
        Args:
            user_id: 用户ID
            initial_features: 初始特征数据
            
        Returns:
            bool: 是否初始化成功
        """
        lock = self._get_user_lock(user_id)
        
        with lock:
            if user_id in self._features_cache:
                print(f"⚠️ [FeatureUpdater] 用户 {user_id} 的特征已存在，跳过初始化")
                return False
            
            # ★★★ 确保初始化时也有 summary_scores ★★★
            if 'summary_scores' not in initial_features:
                all_8_dims = [
                    "academic_background", "learning_behavior", "goal_motivation",
                    "cognitive_abilities", "emotional_state", "social_interaction",
                    "time_management", "creativity_innovation"
                ]
                dim_scores = []
                for dim in all_8_dims:
                    score = initial_features.get(dim, {}).get("score", 50)
                    dim_scores.append(max(0, min(100, int(score))))
                initial_features['summary_scores'] = {
                    "dimension_scores": dim_scores,
                    "overall_score": sum(dim_scores) // 8
                }

            self._features_cache[user_id] = initial_features.copy()
            self._save_features_to_disk(user_id, initial_features)
            self._save_to_chroma(user_id, initial_features)  # ★★★ 存入ChromaDB ★★★

            print(f"✅ [FeatureUpdater] 用户 {user_id} 的特征已初始化")
            return True
    
    def update_and_save_features(
        self,
        user_id: str,
        updated_features: Dict[str, Any],
        update_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        更新并保存用户特征（所有子Agent更新特征后都调用此方法）
        
        Args:
            user_id: 用户ID
            updated_features: 更新后的完整特征数据
            update_metadata: 更新的元数据（可选），包含更新原因、任务类型等
            
        Returns:
            bool: 是否更新成功
        """
        if not updated_features:
            print("❌ [FeatureUpdater] 更新失败：特征数据为空")
            return False
        
        lock = self._get_user_lock(user_id)
        
        with lock:
            try:
                # ★★★ 确保 summary_scores 存在（防止从磁盘加载后 dimension_scores 丢失）★★★
                if 'summary_scores' not in updated_features:
                    all_8_dims = [
                        "academic_background", "learning_behavior", "goal_motivation",
                        "cognitive_abilities", "emotional_state", "social_interaction",
                        "time_management", "creativity_innovation"
                    ]
                    dim_scores = []
                    for dim in all_8_dims:
                        score = updated_features.get(dim, {}).get("score", 50)
                        dim_scores.append(max(0, min(100, int(score))))
                    updated_features['summary_scores'] = {
                        "dimension_scores": dim_scores,
                        "overall_score": sum(dim_scores) // 8,
                        "trend": "稳定"
                    }

                # ★★★ 先从磁盘读取最新特征（防止内存缓存过期）★★★
                disk_features = self._read_features_atomic(user_id)
                old_features = disk_features or self._features_cache.get(user_id, {}).copy()
                
                # 更新缓存（关键！确保下一个Agent拿到的是最新的）
                self._features_cache[user_id] = updated_features.copy()
                
                # 记录更新历史
                update_record = {
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id,
                    "metadata": update_metadata or {},
                    "old_scores": self._extract_scores(old_features),
                    "new_scores": self._extract_scores(updated_features)
                }
                
                if user_id not in self._update_history:
                    self._update_history[user_id] = []
                self._update_history[user_id].append(update_record)
                
                # 持久化到磁盘
                self._save_features_to_disk(user_id, updated_features)
                self._save_to_chroma(user_id, updated_features)  # ★★★ 同步更新ChromaDB ★★★

                print(f"✅ [FeatureUpdater] 用户 {user_id} 的特征已更新并保存")
                if update_metadata:
                    print(f"   更新原因: {update_metadata.get('task_type', 'unknown')}")
                
                # 打印分数变化
                self._print_score_changes(old_features, updated_features)
                
                return True
                
            except Exception as e:
                print(f"❌ [FeatureUpdater] 更新特征失败: {e}")
                import traceback
                traceback.print_exc()
                return False

    async def update_and_save_features_async(
        self,
        user_id: str,
        updated_features: Dict[str, Any],
        update_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        异步更新并保存用户特征（文件 IO 在线程池执行，不阻塞事件循环）
        """
        return await asyncio.to_thread(
            self.update_and_save_features,
            user_id=user_id,
            updated_features=updated_features,
            update_metadata=update_metadata
        )

    def get_update_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取用户的特征更新历史
        
        Args:
            user_id: 用户ID
            limit: 返回的记录数量限制
            
        Returns:
            更新历史记录列表
        """
        history = self._update_history.get(user_id, [])
        return history[-limit:] if len(history) > limit else history

    def append_update_history(self, user_id: str, record: Dict[str, Any]):
        """
        追加自定义更新历史记录（供外部模块使用）

        外部模块（如 time_dimension_service）完成特征更新后，
        可通过此方法追加自定义格式的历史记录，这些记录会被
        _save_features_to_disk 持久化到特征文件中。

        Args:
            user_id: 用户ID
            record: 自定义历史记录字典
        """
        with self._global_lock:
            if user_id not in self._update_history:
                self._update_history[user_id] = []
            self._update_history[user_id].append(record)

    def _save_features_to_disk(self, user_id: str, features: Dict[str, Any]):
        """保存特征到磁盘（原子写入，防止多进程写一半崩溃导致文件损坏）"""
        feature_file = self.storage_path / f"{user_id}.json"
        tmp_file = self.storage_path / f"{user_id}.json.tmp"
        
        data_to_save = {
            "current_features": features,
            "last_updated": datetime.now().isoformat(),
            "update_count": len(self._update_history.get(user_id, [])),
            "update_history": self._update_history.get(user_id, [])
        }

        # ★★★ 保留已存在的 adopted_suggestions（如果有） ★★★
        if feature_file.exists():
            try:
                with open(feature_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if 'adopted_suggestions' in existing:
                    data_to_save['adopted_suggestions'] = existing['adopted_suggestions']
            except Exception:
                pass
        
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp_file.replace(feature_file)

    async def _save_features_to_disk_async(self, user_id: str, features: Dict[str, Any]):
        """异步保存特征到磁盘"""
        await asyncio.to_thread(self._save_features_to_disk, user_id, features)

    async def _save_to_chroma_async(self, user_id: str, features: Dict[str, Any]):
        """异步保存到 ChromaDB"""
        await asyncio.to_thread(self._save_to_chroma, user_id, features)

    def save_adopted_suggestions(self, user_id: str, suggestions: List[Dict[str, Any]]):
        """保存用户采纳的评估建议"""
        feature_file = self.storage_path / f"{user_id}.json"
        data_to_save = {}
        if feature_file.exists():
            try:
                with open(feature_file, 'r', encoding='utf-8') as f:
                    data_to_save = json.load(f)
            except Exception:
                pass
        data_to_save['adopted_suggestions'] = suggestions
        data_to_save['last_updated'] = datetime.now().isoformat()
        tmp_file = self.storage_path / f"{user_id}.json.tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp_file.replace(feature_file)
        print(f"📌 [FeatureUpdater] 已保存用户 {user_id} 的采纳建议 ({len(suggestions)} 条)")

    def get_adopted_suggestions(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户采纳的评估建议列表"""
        feature_file = self.storage_path / f"{user_id}.json"
        if feature_file.exists():
            try:
                with open(feature_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('adopted_suggestions', [])
            except Exception:
                pass
        return []
    
    async def get_adopted_suggestions_async(self, user_id: str) -> List[Dict[str, Any]]:
        """异步版本，避免阻塞事件循环"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.get_adopted_suggestions, user_id
        )
    
    def _extract_scores(self, features: Dict[str, Any]) -> Dict[str, int]:
        """提取各维度评分"""
        if not features:
            return {}
        
        scores = {}
        dimensions = ["academic_background", "learning_behavior", 
                     "goal_motivation", "cognitive_abilities"]
        
        for dim in dimensions:
            if dim in features and isinstance(features[dim], dict):
                scores[dim] = features[dim].get("score", 0)
        
        return scores
    
    def _print_score_changes(self, old_features: Dict[str, Any], new_features: Dict[str, Any]):
        """打印分数变化"""
        old_scores = self._extract_scores(old_features)
        new_scores = self._extract_scores(new_features)
        
        if not old_scores:
            print(f"   新分数: {new_scores}")
            return
        
        changes = []
        dim_names = {
            "academic_background": "学术背景",
            "learning_behavior": "学习行为",
            "goal_motivation": "目标动机",
            "cognitive_abilities": "认知能力"
        }
        
        for dim, name in dim_names.items():
            if dim in old_scores and dim in new_scores:
                delta = new_scores[dim] - old_scores[dim]
                if delta != 0:
                    sign = "+" if delta > 0 else ""
                    changes.append(f"{name}: {old_scores[dim]} → {new_scores[dim]} ({sign}{delta})")
        
        if changes:
            print(f"   分数变化:")
            for change in changes:
                print(f"     - {change}")
    
    # ==================== 原有的特征更新方法（已废弃，使用异步版本） ====================

    async def update_features_async(
        self,
        current_features: Dict[str, Any],
        task_type: str,
        task_content: str,
        performance_data: Dict[str, Any],
        completion_quality: str = "medium",
        time_spent: Optional[str] = None,
        user_id: Optional[str] = None  # 新增：用户ID
    ) -> Dict[str, Any]:
        """
        根据任务表现动态更新学生特征，并自动保存到中央管理器（异步版本）
        
        Args:
            current_features: 当前的学生特征数据
            task_type: 任务类型 (practice/video_learning/document_reading/mindmap_creation等)
            task_content: 任务具体内容描述
            performance_data: 学习表现数据（如答题正确率、观看时长等）
            completion_quality: 完成质量 (high/medium/low)
            time_spent: 时间消耗描述
            user_id: 用户ID（如果提供，会自动保存更新后的特征到中央管理器）
            
        Returns:
            Dict: 更新后的特征数据和变更信息
        """
        try:
            # 获取该任务类型的调整策略
            strategy = self.weight_strategy.get(task_type, self.weight_strategy["default"])
            
            # 构建调整策略描述
            strategy_desc = self._format_strategy_description(strategy)
            
            # 格式化性能数据
            performance_text = self._format_performance_data(performance_data)
            
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 生成提示词
            # ★★★ 精简current_features,只保留核心信息以减少Prompt长度 ★★★
            compact_features = self._compact_features_for_prompt(current_features)
            
            prompt = self.update_template.format(
                current_features=json.dumps(compact_features, ensure_ascii=False, indent=2),
                task_type=task_type,
                task_content=task_content,
                performance_data=performance_text,
                completion_quality=completion_quality,
                time_spent=time_spent or "未知",
                adjustment_strategy=strategy_desc,
                timestamp=timestamp
            )
            
            print(f"\n🔄 [动态特征更新器] 正在异步分析任务表现并调整特征...")
            print(f"   任务类型: {task_type}")
            print(f"   调整策略: {strategy['description']}")
            
            # ★★★ 调用LLM进行特征更新（异步，带重试）★★★
            max_retries = 2
            response_text = None
            for retry in range(max_retries + 1):
                try:
                    response = await self.llm.ainvoke(prompt)
                    response_text = response.content if hasattr(response, 'content') else str(response)
                    break
                except Exception as e:
                    if retry < max_retries:
                        print(f"⚠️ [动态特征更新器] LLM调用失败({retry+1}/{max_retries}): {e}，重试中...")
                        await asyncio.sleep(2)
                    else:
                        raise
            
            # 解析响应
            updated_data = self._parse_update_response(response_text)
            
            if updated_data:
                # 验证和调整更新数据的合理性
                validated_data = self._validate_and_adjust_updates(
                    current_features, 
                    updated_data, 
                    strategy
                )
                
                print(f"✅ [动态特征更新器] 异步特征更新完成")
                self._display_update_summary(current_features, validated_data)
                
                # ★★★ 关键：如果提供了user_id，自动保存到中央管理器 ★★★
                if user_id:
                    updated_feats = validated_data.get('updated_features', {})
                    # ★★★ 合并 summary_scores 到特征数据中（否则保存后 dimension_scores 会丢失）★★★
                    summary = validated_data.get('summary_scores', {})
                    if summary:
                        updated_feats['summary_scores'] = summary
                    metadata = validated_data.get('update_metadata', {})
                    metadata['task_type'] = task_type  # 确保包含任务类型
                    
                    # ★★★ 使用异步版本保存，避免 threading.Lock 阻塞事件循环 ★★★
                    await self.update_and_save_features_async(
                        user_id=user_id,
                        updated_features=updated_feats,
                        update_metadata=metadata
                    )
                    print(f"✅ [动态特征更新器] 已自动保存用户 {user_id} 的最新特征")
                
                return validated_data
            else:
                print("❌ 特征更新失败，返回原始特征")
                return {
                    "status": "error",
                    "features": current_features,
                    "message": "特征更新解析失败"
                }
                
        except Exception as e:
            print(f"❌ 动态特征更新过程出错: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "features": current_features,
                "message": f"更新异常: {str(e)}"
            }
    
    def _format_strategy_description(self, strategy: Dict[str, float]) -> str:
        """格式化调整策略描述"""
        lines = [
            f"策略说明: {strategy.get('description', 'N/A')}",
            f"最大调整幅度: ±{strategy.get('max_adjustment', 10)}分",
            "维度权重:",
        ]
        
        dimension_names = {
            "academic_background": "学术背景",
            "learning_behavior": "学习行为",
            "goal_motivation": "目标动机",
            "cognitive_abilities": "认知能力",
            "emotional_state": "情绪状态",
            "social_interaction": "社交互动",
            "time_management": "时间管理",
            "creativity_innovation": "创新创造"
        }
        
        for dim, weight in strategy.items():
            if dim in dimension_names and isinstance(weight, (int, float)):
                lines.append(f"  - {dimension_names[dim]}: {weight:.0%}")
        
        return "\n".join(lines)
    
    def _format_performance_data(self, performance_data: Dict[str, Any]) -> str:
        """格式化性能数据为文本"""
        if not performance_data:
            return "无详细性能数据"
        
        lines = []
        for key, value in performance_data.items():
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    lines.append(f"  - {sub_key}: {sub_value}")
            elif isinstance(value, list):
                lines.append(f"{key}: {', '.join(str(v) for v in value)}")
            else:
                lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
    
    def _parse_update_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的更新响应"""
        # ★★★ 空响应提前返回，避免无效解析 ★★★
        if not response or not response.strip():
            print("❌ [解析] LLM返回空响应，跳过解析")
            return None
        
        try:
            import re
            
            # ★★★ 完整打印LLM原始响应(用于调试) ★★★
            print(f"\n{'='*80}")
            print(f"📝 [DEBUG] LLM原始响应 - 完整内容")
            print(f"{'='*80}")
            print(response)
            print(f"{'='*80}")
            print(f"📝 [DEBUG] LLM原始响应长度: {len(response)} 字符")
            print(f"{'='*80}\n")
            
            # 尝试提取JSON块
            json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
            json_match = json_pattern.search(response)
            
            if json_match:
                json_str = json_match.group(1)
                print("✅ [解析] 找到JSON代码块")
            else:
                # 尝试直接匹配JSON对象
                json_only_pattern = re.compile(r'\{.*\}', re.DOTALL)
                json_match = json_only_pattern.search(response)
                if json_match:
                    json_str = json_match.group(0)
                    print("✅ [解析] 找到直接JSON对象")
                else:
                    cleaned_response = response.strip()
                    if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                        json_str = cleaned_response
                        print("✅ [解析] 响应本身就是JSON")
                    else:
                        print("❌ [解析] 未找到有效的JSON格式")
                        return None
            
            json_str = json_str.strip()
            
            # ★★★ 打印提取后的JSON字符串 ★★★
            print(f"\n{'='*80}")
            print(f"📝 [DEBUG] 提取后的JSON字符串 - 完整内容")
            print(f"{'='*80}")
            print(json_str)
            print(f"{'='*80}")
            print(f"📝 [DEBUG] JSON字符串长度: {len(json_str)} 字符")
            print(f"{'='*80}\n")
            
            # 尝试解析JSON
            try:
                data = json.loads(json_str)
                print("✅ [解析] JSON解析成功")
                return data
            except json.JSONDecodeError as e:
                print(f"❌ [解析] JSON解析失败: {e}")
                print(f"   错误位置: 第{e.lineno}行,第{e.colno}列")
                print(f"   错误字符位置: char {e.pos}")
                
                # ★★★ 打印错误附近的上下文 ★★★
                lines = json_str.split('\n')
                if e.lineno <= len(lines):
                    error_line_idx = e.lineno - 1
                    start_idx = max(0, error_line_idx - 2)
                    end_idx = min(len(lines), error_line_idx + 3)
                    
                    print(f"\n📍 [DEBUG] 错误附近内容 (第{start_idx+1}-{end_idx}行):")
                    print(f"{'-'*80}")
                    for i in range(start_idx, end_idx):
                        marker = ">>>" if i == error_line_idx else "   "
                        line_num = f"{i+1:>4}"
                        print(f"{marker} 第{line_num}行: {lines[i]}")
                        if i == error_line_idx:
                            # 标记错误位置
                            col_pos = e.colno - 1
                            if col_pos < len(lines[i]):
                                pointer = " " * (col_pos + 11) + "^"
                                print(f"      {pointer}")
                    print(f"{'-'*80}\n")
                
                return None
            
        except Exception as e:
            print(f"❌ [解析] 解析响应时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _validate_and_adjust_updates(
        self,
        original_features: Dict[str, Any],
        updated_data: Dict[str, Any],
        strategy: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        验证和调整更新数据，确保合理性
        
        Args:
            original_features: 原始特征
            updated_data: LLM生成的更新数据
            strategy: 调整策略
            
        Returns:
            Dict: 验证后的更新数据
        """
        try:
            updated_features = updated_data.get("updated_features", {})
            
            # 获取最大调整幅度
            max_adj = strategy.get("max_adjustment", 10)
            
            # 对每个维度的评分进行限制（8个维度）
            dimensions = ["academic_background", "learning_behavior", 
                         "goal_motivation", "cognitive_abilities",
                         "emotional_state", "social_interaction",
                         "time_management", "creativity_innovation"]
            
            dimension_changes = {}
            new_dimension_scores = []
            
            for dim in dimensions:
                original_score = original_features.get(dim, {}).get("score", 50)
                
                # ★★★ 关键修复：对于权重为0的维度，直接保持原样，不允许LLM修改 ★★★
                dim_weight = strategy.get(dim, 0.0)
                if dim_weight == 0.0:
                    # 权重为0的维度：情绪状态、社交互动、时间管理
                    # 强制保持原始分数不变
                    if dim in updated_features:
                        updated_features[dim]["score"] = original_score
                        updated_features[dim]["change_reason"] = f"{dim}权重为0，练题任务不影响此维度，保持原值"
                    
                    dimension_changes[f"{dim}_delta"] = 0
                    new_dimension_scores.append(original_score)
                    continue
                
                # 有权重的维度：允许LLM更新，但限制幅度
                new_score = updated_features.get(dim, {}).get("score", original_score)
                
                # 限制调整幅度
                delta = new_score - original_score
                if abs(delta) > max_adj:
                    delta = max_adj if delta > 0 else -max_adj
                    new_score = original_score + delta
                
                # 确保分数在0-100范围内
                new_score = max(0, min(100, new_score))
                
                # 更新分数
                if dim in updated_features:
                    updated_features[dim]["score"] = new_score
                
                dimension_changes[f"{dim}_delta"] = delta
                new_dimension_scores.append(new_score)
            
            # 更新变更摘要
            updated_data["dimension_changes"] = dimension_changes
            
            # 更新综合评分（8个维度）
            overall_score = sum(new_dimension_scores) // 8
            trend = self._calculate_trend(original_features, new_dimension_scores)
            
            updated_data["summary_scores"] = {
                "dimension_scores": new_dimension_scores,
                "overall_score": overall_score,
                "trend": trend
            }
            
            # 添加状态标记
            updated_data["status"] = "success"
            updated_data["original_features"] = original_features
            
            return updated_data
            
        except Exception as e:
            print(f"⚠️ 验证调整过程出错: {e}")
            return updated_data
    
    def _calculate_trend(
        self, 
        original_features: Dict[str, Any], 
        new_scores: List[int]
    ) -> str:
        """计算整体趋势（8个维度）"""
        try:
            original_scores = [
                original_features.get("academic_background", {}).get("score", 50),
                original_features.get("learning_behavior", {}).get("score", 50),
                original_features.get("goal_motivation", {}).get("score", 50),
                original_features.get("cognitive_abilities", {}).get("score", 50),
                original_features.get("emotional_state", {}).get("score", 50),
                original_features.get("social_interaction", {}).get("score", 50),
                original_features.get("time_management", {}).get("score", 50),
                original_features.get("creativity_innovation", {}).get("score", 50)
            ]
            
            original_avg = sum(original_scores) / 8
            new_avg = sum(new_scores) / 8
            
            diff = new_avg - original_avg
            
            if diff > 3:
                return "上升"
            elif diff < -3:
                return "下降"
            else:
                return "稳定"
                
        except Exception:
            return "稳定"
    
    def _display_update_summary(
        self, 
        original: Dict[str, Any], 
        updated_data: Dict[str, Any]
    ):
        """显示更新摘要"""
        changes = updated_data.get("dimension_changes", {})
        summary = updated_data.get("summary_scores", {})
        metadata = updated_data.get("update_metadata", {})
        
        print(f"\n📊 特征更新摘要:")
        print(f"   趋势: {summary.get('trend', 'N/A')}")
        print(f"   整体评分: {summary.get('overall_score', 0)}/100")
        print(f"   证据质量: {metadata.get('evidence_quality', 'N/A')}")
        
        dimension_names = {
            "academic_background_delta": "学术背景",
            "learning_behavior_delta": "学习行为",
            "goal_motivation_delta": "目标动机",
            "cognitive_abilities_delta": "认知能力",
            "emotional_state_delta": "情绪状态",
            "social_interaction_delta": "社交互动",
            "time_management_delta": "时间管理",
            "creativity_innovation_delta": "创新创造"
        }
        
        for key, name in dimension_names.items():
            delta = changes.get(key, 0)
            if delta != 0:
                sign = "+" if delta > 0 else ""
                print(f"   {name}: {sign}{delta}")
        
        observations = metadata.get("key_observations", [])
        if observations:
            print(f"   关键观察:")
            for obs in observations[:3]:
                print(f"     - {obs}")
    
    def quick_update(
        self,
        current_features: Dict[str, Any],
        task_type: str,
        score_change: int,
        affected_dimensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        快速更新模式 - 基于简单评分变化进行快速调整
        
        Args:
            current_features: 当前特征
            task_type: 任务类型
            score_change: 评分变化量 (-20 到 +20)
            affected_dimensions: 受影响的维度列表，None表示全部
            
        Returns:
            Dict: 更新后的特征
        """
        try:
            # 限制变化范围
            score_change = max(-20, min(20, score_change))
            
            # 获取策略
            strategy = self.weight_strategy.get(task_type, self.weight_strategy["default"])
            
            # 确定受影响的维度
            if affected_dimensions is None:
                affected_dimensions = ["academic_background", "learning_behavior", 
                                      "goal_motivation", "cognitive_abilities"]
            
            # 创建副本
            import copy
            updated_features = copy.deepcopy(current_features)
            
            # 按权重分配变化
            total_weight = sum(
                strategy.get(dim, 0.25) 
                for dim in affected_dimensions
            )
            
            dimension_changes = {}
            new_scores = []
            
            for dim in ["academic_background", "learning_behavior", 
                       "goal_motivation", "cognitive_abilities"]:
                original_score = updated_features.get(dim, {}).get("score", 50)
                
                if dim in affected_dimensions:
                    weight = strategy.get(dim, 0.25)
                    dim_change = int(score_change * (weight / total_weight))
                    
                    # 限制单个维度变化
                    dim_change = max(-10, min(10, dim_change))
                    new_score = original_score + dim_change
                    new_score = max(0, min(100, new_score))
                    
                    updated_features[dim]["score"] = new_score
                    dimension_changes[f"{dim}_delta"] = dim_change
                else:
                    dimension_changes[f"{dim}_delta"] = 0
                
                new_scores.append(updated_features[dim]["score"])
            
            # 更新综合评分
            overall_score = sum(new_scores) // 4
            
            result = {
                "status": "success",
                "updated_features": updated_features,
                "dimension_changes": dimension_changes,
                "summary_scores": {
                    "dimension_scores": new_scores,
                    "overall_score": overall_score,
                    "trend": "上升" if score_change > 2 else ("下降" if score_change < -2 else "稳定")
                },
                "update_metadata": {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "task_type": task_type,
                    "evidence_quality": "medium",
                    "key_observations": [f"快速更新: 评分变化{score_change:+d}"],
                    "recommendations": []
                },
                "original_features": current_features
            }
            
            print(f"⚡ [快速更新] 特征已更新，整体变化: {score_change:+d}")
            return result
            
        except Exception as e:
            print(f"❌ 快速更新失败: {e}")
            return {
                "status": "error",
                "features": current_features,
                "message": str(e)
            }
    
    def update_emotional_state_directly(
        self,
        user_id: str,
        emotional_state_update: Dict[str, Any],
        detected_emotion: Dict[str, Any],
        recommendation: str = ""
    ) -> bool:
        """
        ★★★ 专门用于YOLO情绪检测的直接更新方法（不调用LLM）★★★
        
        Args:
            user_id: 用户ID
            emotional_state_update: 情绪状态更新数据（来自EmotionStateMapper）
            detected_emotion: 检测到的情绪信息
            recommendation: 建议文本
            
        Returns:
            bool: 是否更新成功
        """
        try:
            # 1. 获取当前完整特征
            current_features = self.get_latest_features(user_id)
            
            if not current_features:
                print(f"⚠️ [FeatureUpdater] 用户 {user_id} 的特征不存在，无法更新情绪状态")
                return False
            
            # 2. 构建更新后的特征
            import copy
            updated_features = copy.deepcopy(current_features)
            updated_features['emotional_state'] = emotional_state_update
            
            # 3. 准备元数据
            confidence = detected_emotion.get('confidence', 0)
            update_metadata = {
                "task_type": "emotion_detection",
                "source": "yolo_realtime",
                "detected_emotion": detected_emotion,
                "recommendation": recommendation,
                "evidence_quality": "high" if confidence > 0.7 else "medium",
                "timestamp": datetime.now().isoformat()
            }
            
            # 4. 调用中央管理器保存
            success = self.update_and_save_features(
                user_id=user_id,
                updated_features=updated_features,
                update_metadata=update_metadata
            )
            
            if success:
                emotion_type = detected_emotion.get('type', 'unknown')
                emotion_cn = detected_emotion.get('chinese_name', '未知')
                print(f"✅ [FeatureUpdater] 用户 {user_id} 的情绪状态已更新: {emotion_type} ({emotion_cn})")
            
            return success
            
        except Exception as e:
            print(f"❌ [FeatureUpdater] 更新情绪状态失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_feature_evolution_report(
        self,
        update_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        生成特征演化报告
        
        Args:
            update_history: 历史更新记录列表
            
        Returns:
            Dict: 演化分析报告
        """
        try:
            if not update_history:
                return {"message": "无历史记录"}
            
            # 统计各维度变化趋势
            dimension_trends = {
                "academic_background": [],
                "learning_behavior": [],
                "goal_motivation": [],
                "cognitive_abilities": []
            }
            
            for record in update_history:
                scores = record.get("summary_scores", {}).get("dimension_scores", [])
                if len(scores) == 4:
                    dimension_trends["academic_background"].append(scores[0])
                    dimension_trends["learning_behavior"].append(scores[1])
                    dimension_trends["goal_motivation"].append(scores[2])
                    dimension_trends["cognitive_abilities"].append(scores[3])
            
            # 计算趋势
            trends = {}
            for dim, scores in dimension_trends.items():
                if len(scores) >= 2:
                    first_half_avg = sum(scores[:len(scores)//2]) / (len(scores)//2)
                    second_half_avg = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
                    
                    diff = second_half_avg - first_half_avg
                    if diff > 5:
                        trends[dim] = "显著上升"
                    elif diff > 2:
                        trends[dim] = "缓慢上升"
                    elif diff < -5:
                        trends[dim] = "显著下降"
                    elif diff < -2:
                        trends[dim] = "缓慢下降"
                    else:
                        trends[dim] = "基本稳定"
                else:
                    trends[dim] = "数据不足"
            
            report = {
                "total_updates": len(update_history),
                "dimension_trends": trends,
                "latest_scores": update_history[-1].get("summary_scores", {}),
                "most_impactful_tasks": self._analyze_task_impact(update_history),
                "recommendations": self._generate_evolution_recommendations(trends)
            }
            
            return report
            
        except Exception as e:
            print(f"❌ 生成演化报告失败: {e}")
            return {"error": str(e)}
    
    def _analyze_task_impact(self, update_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析不同任务类型的影响"""
        task_impacts = {}
        
        for record in update_history:
            task_type = record.get("update_metadata", {}).get("task_type", "unknown")
            changes = record.get("dimension_changes", {})
            
            if task_type not in task_impacts:
                task_impacts[task_type] = {
                    "count": 0,
                    "total_change": 0
                }
            
            task_impacts[task_type]["count"] += 1
            
            # 计算总变化量
            total_delta = sum(abs(v) for k, v in changes.items() if k.endswith("_delta"))
            task_impacts[task_type]["total_change"] += total_delta
        
        # 转换为列表并排序
        impact_list = [
            {
                "task_type": task_type,
                "update_count": data["count"],
                "avg_impact": data["total_change"] / data["count"] if data["count"] > 0 else 0
            }
            for task_type, data in task_impacts.items()
        ]
        
        impact_list.sort(key=lambda x: x["avg_impact"], reverse=True)
        return impact_list[:5]
    
    def _generate_evolution_recommendations(self, trends: Dict[str, str]) -> List[str]:
        """基于趋势生成建议"""
        recommendations = []
        
        for dim, trend in trends.items():
            dim_name_map = {
                "academic_background": "学术背景",
                "learning_behavior": "学习行为",
                "goal_motivation": "目标动机",
                "cognitive_abilities": "认知能力"
            }
            
            dim_name = dim_name_map.get(dim, dim)
            
            if "显著下降" in trend:
                recommendations.append(f"【{dim_name}】出现明显下滑，建议加强相关训练和反馈")
            elif "缓慢下降" in trend:
                recommendations.append(f"【{dim_name}】有轻微下降趋势，需关注并及时干预")
            elif "显著上升" in trend:
                recommendations.append(f"【{dim_name}】进步明显，可适当提升难度挑战更高目标")
        
        if not recommendations:
            recommendations.append("整体发展平稳，继续保持当前学习节奏")
        
        return recommendations
    
    def delete_user_features(self, user_id: str) -> bool:
        """
        删除用户的所有特征数据（包括缓存和磁盘文件）
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否成功删除
        """
        try:
            lock = self._get_user_lock(user_id)
            
            with lock:
                # 1. 从缓存中删除
                if user_id in self._features_cache:
                    del self._features_cache[user_id]
                    print(f"🗑️ [FeatureUpdater] 已从缓存删除用户 {user_id} 的特征")
                
                # 2. 从历史记录中删除
                if user_id in self._update_history:
                    del self._update_history[user_id]
                    print(f"🗑️ [FeatureUpdater] 已清除用户 {user_id} 的更新历史")
                
                # 3. 删除磁盘文件
                feature_file = self.storage_path / f"{user_id}.json"
                if feature_file.exists():
                    feature_file.unlink()
                    print(f"🗑️ [FeatureUpdater] 已删除用户 {user_id} 的特征文件")
                
                # 4. 删除用户锁
                if user_id in self._user_locks:
                    del self._user_locks[user_id]
                
                print(f"✅ [FeatureUpdater] 用户 {user_id} 的数据已完全清理")
                return True
                
        except Exception as e:
            print(f"❌ [FeatureUpdater] 删除用户 {user_id} 数据失败: {e}")
            return False

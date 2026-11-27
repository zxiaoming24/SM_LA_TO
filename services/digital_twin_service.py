"""
digital_twin_service.py - AI数字孪生（AI克隆）核心服务

功能：
1. 基于用户特征、知识掌握度、学习记录构建用户数字孪生
2. 模拟孪生用户对题目的作答行为
3. 记录用户与孪生的对比结果，用于精准诊断
4. 支持用户自行开启/关闭孪生功能

核心算法：
- 知识点掌握度：基于 SM-2 算法掌握等级归一化到 [0,1]
- 作答模拟：综合掌握度 × 能力匹配度 × 难度因子，使用 Sigmoid 概率模型
- 错误模式：基于历史错误类型分布模拟错误答案

# 存储结构（user_twin/{user_id}/twin_data.json）：
{
    "user_id": "user_001",
    "enabled": true,
    "created_at": "...",
    "last_built_at": "...",
    "last_batch_update_at": "...",         # 最近一次批次更新的时间
    "last_batch_update_index": 0,           # 批次更新处理到的记录索引
    "profile": {
        "dimension_scores": [85, 70, 90, ...],         # 8维度评分
        "overall_score": 78.5,                          # 综合分
        "knowledge_mastery": {                           # 知识点掌握度
            "Java基础": 0.85,
            "多线程": 0.45,
            ...
        },
        "ability_weights": {                             # 各维度能力权重
            "logical_thinking": 0.9,
            "memory": 0.7,
            ...
        },
        "error_patterns": {                              # 错误模式分布
            "concept_confusion": 0.35,
            "careless_mistake": 0.25,
            "incomplete_knowledge": 0.30,
            "misunderstanding": 0.10
        },
        "guess_probability": 0.15,                       # BKT P(G)
        "slip_probability": 0.10,                        # BKT P(S)
        "confidence_factor": 0.8                         # 信心因子
    },
    "comparison_history": [
        {
            "timestamp": "...",
            "question_id": "q_001",
            "knowledge_point": "Java基础",
            "user_correct": true,
            "twin_correct": false,
            "result_type": "user_right_twin_wrong",
            "difficulty": 0.6
        },
        ...
    ]
}
"""

import json
import os
import math
import re
import time
import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor


# ==================== 配置常量 ====================

# 孪生数据存储根目录
TWIN_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_twin")

# SIGMOID 温度参数（控制"对/错"边界的锐利程度）
# 值越小，边界越锐利；值越大，过渡越平滑
SIGMOID_TEMPERATURE = 4.0

# 批次更新大小：累积多少条对比记录后批量更新孪生特征
BATCH_UPDATE_SIZE = 5

# 线程池（用于异步文件IO）
_TWIN_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="digital_twin")

# 非知识点的标记模式（构建和更新时过滤）
_NON_KP_PATTERNS = {
    "fill_blank", "judge", "multiple_choice", "short_answer",
    "single_choice", "rag_knowledge", "true_false", "completion",
    "essay", "matching", "ordering", "code_completion"
}


# ==================== 内部工具函数 ====================

def _sigmoid(x: float, temperature: float = SIGMOID_TEMPERATURE) -> float:
    """Sigmoid 函数，用于计算作答正确概率"""
    return 1.0 / (1.0 + math.exp(-temperature * x))


def _calc_match_degree(user_correct: bool, twin_confidence: float) -> float:
    """计算单次对比的匹配度（连续值 0~1，而非 0%/100% 二进制）
    
    匹配度 = 1 - |用户实际得分 - 孪生信心|
    - 用户对(1.0)、孪生信心0.90 → 匹配度 0.90
    - 用户对(1.0)、孪生信心0.55 → 匹配度 0.55
    - 用户错(0.0)、孪生信心0.80 → 匹配度 0.20
    - 用户错(0.0)、孪生信心0.10 → 匹配度 0.90
    """
    user_score = 1.0 if user_correct else 0.0
    return round(1.0 - abs(user_score - twin_confidence), 3)


def _get_twin_file_path(user_id: str) -> str:
    """获取用户孪生数据文件路径"""
    user_dir = os.path.join(TWIN_DATA_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "twin_data.json")


def _load_twin_data(user_id: str) -> Optional[Dict[str, Any]]:
    """从磁盘加载孪生数据"""
    path = _get_twin_file_path(user_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_twin_data(user_id: str, data: Dict[str, Any]) -> bool:
    """原子写入孪生数据到磁盘"""
    path = _get_twin_file_path(user_id)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True
    except (IOError, OSError):
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False


# ==================== 对比结果枚举 ====================

class ComparisonResult:
    """用户 vs 孪生作答对比结果类型"""
    BOTH_CORRECT = "both_correct"            # 用户对、孪生对 → 已掌握
    BOTH_WRONG = "both_wrong"                # 用户错、孪生错 → 确实难
    USER_RIGHT_TWIN_WRONG = "user_right_twin_wrong"  # 用户对、孪生错 → 校准孪生
    USER_WRONG_TWIN_RIGHT = "user_wrong_twin_right"  # 用户错、孪生对 → 知识盲区


# ==================== 数字孪生服务 ====================

class DigitalTwinService:
    """
    数字孪生服务（单例）

    核心职责：
    1. 构建/重建用户孪生（从特征+掌握度+学习记录）
    2. 模拟孪生作答
    3. 记录对比历史
    4. 管理开启/关闭状态
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._memory_hub = None

    # ------------------------------------------------------------------
    # 依赖加载
    # ------------------------------------------------------------------

    def _get_memory_hub(self):
        """延迟加载 MemoryHub"""
        if self._memory_hub is None:
            try:
                from memory.memory_hub import MemoryHub
                self._memory_hub = MemoryHub()
            except ImportError:
                return None
        return self._memory_hub

    def _get_feature_updater(self):
        """延迟加载 DynamicFeatureUpdater"""
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            return DynamicFeatureUpdater()
        except ImportError:
            return None

    def _get_knowledge_mastery(self):
        """延迟加载 KnowledgeMasteryGraph"""
        try:
            from memory.knowledge_mastery import KnowledgeMasteryGraph
            return KnowledgeMasteryGraph()
        except ImportError:
            return None

    def _get_learning_record_db(self):
        """延迟加载 LearningRecordDB"""
        try:
            from Agent.children_agent.recommendation.learning_record_db import LearningRecordDB
            return LearningRecordDB()
        except ImportError:
            return None

    # ------------------------------------------------------------------
    # 孪生状态管理
    # ------------------------------------------------------------------

    def get_twin_status(self, user_id: str) -> Dict[str, Any]:
        """获取用户孪生状态
        
        返回:
        {
            "enabled": bool,        # 是否开启
            "exists": bool,         # 孪生数据是否存在
            "profile": {...},       # 孪生画像（如果存在）
            "has_history": bool,    # 是否有对比历史
            "comparison_count": int # 对比次数
        }
        """
        twin_data = _load_twin_data(user_id)
        if twin_data is None:
            return {
                "enabled": False,
                "exists": False,
                "profile": None,
                "has_history": False,
                "comparison_count": 0
            }
        history = twin_data.get("comparison_history", [])
        return {
            "enabled": twin_data.get("enabled", False),
            "exists": True,
            "profile": twin_data.get("profile"),
            "has_history": len(history) > 0,
            "comparison_count": len(history)
        }

    def set_twin_enabled(self, user_id: str, enabled: bool) -> Dict[str, Any]:
        """开启/关闭用户孪生"""
        twin_data = _load_twin_data(user_id)
        if twin_data is None:
            if not enabled:
                return {"success": True, "message": "孪生已关闭"}
            # 尝试自动创建
            return {"success": False, "message": "请先构建孪生再开启"}

        twin_data["enabled"] = enabled
        ok = _save_twin_data(user_id, twin_data)
        return {
            "success": ok,
            "enabled": enabled,
            "message": "孪生已开启" if enabled else "孪生已关闭"
        }

    # ------------------------------------------------------------------
    # 流式构建（用于SSE进度展示）
    # ------------------------------------------------------------------

    def build_twin_stream(self, user_id: str):
        """流式构建孪生，逐步 yield 进度事件
        
        每个事件格式: {"progress": int, "message": str, "status": str}
        status: 'building' | 'complete' | 'error'
        """
        yield {"progress": 0, "message": "开始构建数字孪生...", "status": "building", "detail": "正在初始化构建引擎"}

        try:
            # --- 步骤1: 获取特征画像 ---
            yield {"progress": 5, "message": "读取用户特征画像...", "status": "building", "detail": "正在从 DynamicFeatureUpdater 加载8维度特征数据"}
            feature_updater = self._get_feature_updater()
            features = None
            if feature_updater:
                features = feature_updater.get_latest_features(user_id)

            if features:
                yield {"progress": 15, "message": "特征画像加载完成", "status": "building", "detail":
                    "已加载特征数据：学术背景、学习行为、目标动机、认知能力、情绪状态、社交互动、时间管理、创新创造"}
            else:
                yield {"progress": 15, "message": "特征画像未找到，使用默认值", "status": "building", "detail": "未能加载用户特征数据，将使用默认参数构建孪生"}

            # --- 步骤2: 获取知识掌握度 ---
            yield {"progress": 20, "message": "读取知识点掌握度...", "status": "building", "detail": "正在从 KnowledgeMasteryGraph 查询各知识点掌握等级"}
            knowledge = self._get_knowledge_mastery()
            knowledge_mastery = {}
            kp_count = 0
            filtered_count = 0
            if knowledge:
                try:
                    all_mastery = knowledge.get_all_mastery(user_id)
                    if all_mastery:
                        for kp in all_mastery:
                            name = kp["knowledge_point"]
                            # 过滤：题型标签、内部标签、单字符、纯标点
                            if name in _NON_KP_PATTERNS:
                                filtered_count += 1
                                continue
                            if len(name.strip()) <= 1:
                                filtered_count += 1
                                continue
                            # ★★★ 过滤自动生成的无效知识点标题（与复习提醒拦截规则一致）★★★
                            if "帮我复习" in name or "rag_" in name:
                                filtered_count += 1
                                continue
                            knowledge_mastery[name] = kp.get("mastery_level", 0) / 4.0
                        kp_count = len(knowledge_mastery)
                except Exception:
                    pass

            yield {"progress": 30, "message": f"知识掌握度加载完成（共 {kp_count} 个知识点）", "status": "building",
                   "detail": f"已加载 {kp_count} 个知识点（过滤 {filtered_count} 个非知识点条目），采用 SM-2 间隔重复算法建模"}

            # --- 步骤3: 分析错误模式 ---
            yield {"progress": 35, "message": "分析历史学习记录...", "status": "building", "detail": "正在从 LearningRecordDB 读取做题记录，分析错误模式分布"}
            error_patterns = self._analyze_error_patterns(user_id)
            yield {"progress": 40, "message": "错误模式分析完成", "status": "building",
                   "detail": f"错误模式分布: {json.dumps(error_patterns, ensure_ascii=False)}"}

            # --- 步骤4: 计算BKT参数 ---
            yield {"progress": 45, "message": "计算贝叶斯知识追踪参数...", "status": "building",
                   "detail": "基于特征画像计算 BKT 猜对概率 P(G) 和 失误概率 P(S)"}
            guess_prob, slip_prob = self._estimate_bkt_params(features, knowledge_mastery)
            yield {"progress": 55, "message": f"BKT参数计算完成: P(G)={guess_prob:.3f}, P(S)={slip_prob:.3f}", "status": "building",
                   "detail": f"P(G)猜对概率={guess_prob:.3f}（能力越强越高）；P(S)失误概率={slip_prob:.3f}（粗心/焦虑越高）"}

            # --- 步骤5: 构建画像 ---
            yield {"progress": 60, "message": "提取能力维度权重...", "status": "building",
                   "detail": "从特征中提取逻辑思维、记忆力、理解力、应用能力、创造力等维度权重"}
            dimension_scores, overall_score = self._extract_dimension_scores(features)
            ability_weights = self._extract_ability_weights(features)
            yield {"progress": 70, "message": "计算信心因子...", "status": "building",
                   "detail": "基于情绪状态（自信水平、兴趣水平）综合计算作答信心因子"}
            confidence = self._estimate_confidence(features)

            yield {"progress": 80, "message": "组装孪生画像...", "status": "building",
                   "detail": f"综合评分={overall_score:.1f}分，信心因子={confidence:.3f}，共{len(ability_weights)}个能力维度"}

            if not dimension_scores and not knowledge_mastery:
                yield {"progress": 100, "message": "数据不足，无法构建孪生", "status": "error",
                       "detail": "用户特征和知识掌握度数据均缺失，请先进行学习活动"}
                return

            profile = {
                "dimension_scores": dimension_scores,
                "overall_score": overall_score,
                "knowledge_mastery": knowledge_mastery,
                "ability_weights": ability_weights,
                "error_patterns": error_patterns,
                "guess_probability": round(guess_prob, 3),
                "slip_probability": round(slip_prob, 3),
                "confidence_factor": round(confidence, 3),
                "feature_source": features is not None,
                "mastery_source": len(knowledge_mastery) > 0,
                "built_at": datetime.now().isoformat()
            }

            # --- 步骤6: 保存 ---
            yield {"progress": 85, "message": "保存孪生数据...", "status": "building",
                   "detail": f"写入磁盘: user_twin/{user_id}/twin_data.json"}

            now = datetime.now().isoformat()
            twin_data = {
                "user_id": user_id,
                "enabled": True,
                "created_at": now,
                "last_built_at": now,
                "last_batch_update_at": now,
                "last_batch_update_index": 0,
                "build_count": 1,
                "profile": profile,
                "comparison_history": []
            }
            ok = _save_twin_data(user_id, twin_data)

            if ok:
                yield {"progress": 100, "message": "孪生构建完成！", "status": "complete",
                       "detail": f"孪生已保存，共 {kp_count} 个知识点，{len(dimension_scores) if dimension_scores else 0} 个维度"}
            else:
                yield {"progress": 100, "message": "保存失败", "status": "error",
                       "detail": "写入磁盘时出错，请检查磁盘空间和权限"}

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"progress": 100, "message": f"构建异常: {str(e)}", "status": "error",
                   "detail": traceback.format_exc()}

    def rebuild_twin_stream(self, user_id: str):
        """流式重建孪生，保留历史对比数据"""
        old_data = _load_twin_data(user_id)
        old_history = old_data.get("comparison_history", []) if old_data else []

        for event in self.build_twin_stream(user_id):
            if event["status"] == "complete":
                # 重新加载已保存的数据，合并旧历史
                saved = _load_twin_data(user_id)
                if saved:
                    saved["comparison_history"] = old_history
                    saved["created_at"] = old_data["created_at"] if old_data else saved["created_at"]
                    saved["build_count"] = (old_data.get("build_count", 0) if old_data else 0) + 1
                    _save_twin_data(user_id, saved)
                    event["detail"] += f"，保留 {len(old_history)} 条对比历史记录"
            yield event

    # ------------------------------------------------------------------
    # 数据采集
    # ------------------------------------------------------------------

    def _extract_dimension_scores(self, features: Optional[Dict]) -> Tuple[List[float], float]:
        """从特征中提取8维度评分"""
        if not features:
            return [], 0.0

        summary = features.get("summary_scores", {})
        dims = summary.get("dimension_scores")
        if dims and isinstance(dims, list) and len(dims) == 8:
            return dims, summary.get("overall_score", 50.0)

        # 如果不在 summary_scores 中，尝试从 dimensions 中提取
        dims_dict = features.get("dimensions", features.get("feature_dimensions", {}))
        if dims_dict and isinstance(dims_dict, dict):
            scores = []
            for key in ["academic_background", "learning_behavior", "goal_motivation",
                        "cognitive_abilities", "emotional_state", "social_interaction",
                        "time_management", "creativity_innovation"]:
                dim = dims_dict.get(key, {})
                score = dim.get("score", 0)
                if isinstance(score, (int, float)):
                    scores.append(float(score))
                else:
                    scores.append(50.0)
            if all(s == 50.0 for s in scores):
                return [], 0.0
            return scores, sum(scores) / len(scores)

        return [], 0.0

    def _extract_ability_weights(self, features: Optional[Dict]) -> Dict[str, float]:
        """从特征中提取各能力维度权重"""
        weights = {
            "logical_thinking": 0.5,
            "memory": 0.5,
            "comprehension": 0.5,
            "application": 0.5,
            "creativity": 0.5
        }
        if not features:
            return weights

        dims = features.get("dimensions", features.get("feature_dimensions", {}))
        if not isinstance(dims, dict):
            return weights

        # 从 cognitive_abilities 提取逻辑思维、创造力
        cognitive = dims.get("cognitive_abilities", {})
        if isinstance(cognitive, dict):
            weights["logical_thinking"] = (cognitive.get("logical_thinking", 50) or 50) / 100.0
            weights["creativity"] = (cognitive.get("creative_thinking", 50) or 50) / 100.0

        # 从 academic_background 提取理解和应用能力
        academic = dims.get("academic_background", {})
        if isinstance(academic, dict):
            weights["comprehension"] = (academic.get("knowledge_level", 50) or 50) / 100.0
            weights["application"] = (academic.get("ability_tendency", 50) or 50) / 100.0
            weights["memory"] = (academic.get("foundation_level", 50) or 50) / 100.0

        return weights

    def _analyze_error_patterns(self, user_id: str) -> Dict[str, float]:
        """分析用户历史错误模式分布"""
        default_patterns = {
            "concept_confusion": 0.25,
            "careless_mistake": 0.25,
            "incomplete_knowledge": 0.25,
            "misunderstanding": 0.25,
            "calculation_error": 0.00
        }

        try:
            record_db = self._get_learning_record_db()
            if not record_db:
                return default_patterns

            # 获取最近的学习统计
            # 实际项目中可以从 LearningRecordDB 获取详细错误类型
            stats = record_db.get_user_stats(user_id) if hasattr(record_db, "get_user_stats") else None
            if stats and isinstance(stats, dict):
                wrong_dist = stats.get("wrong_type_distribution", {})
                if wrong_dist and isinstance(wrong_dist, dict):
                    total = sum(wrong_dist.values()) or 1
                    return {k: v / total for k, v in wrong_dist.items()}

            return default_patterns
        except Exception:
            return default_patterns

    def _estimate_bkt_params(self, features: Optional[Dict],
                             knowledge_mastery: Dict[str, float]) -> Tuple[float, float]:
        """估算贝叶斯知识追踪参数 P(G) 和 P(S)
        
        P(G) - 猜对概率：能力较强的用户猜对概率较高
        P(S) - 失误概率：粗心/容易焦虑的用户失误概率较高
        """
        if not features:
            return 0.15, 0.12

        dims = features.get("dimensions", features.get("feature_dimensions", {}))
        if not isinstance(dims, dict):
            return 0.15, 0.12

        emotional = dims.get("emotional_state", {})
        if isinstance(emotional, dict):
            # 焦虑程度高 → 失误概率高
            anxiety = (emotional.get("anxiety_level", 50) or 50) / 100.0
            # 自信心高 → 猜对概率高
            confidence = (emotional.get("confidence_level", 50) or 50) / 100.0
            # 细心程度（从学习行为推断）
            behavior = dims.get("learning_behavior", {})
            pace = (behavior.get("learning_pace", 50) or 50) / 100.0 if isinstance(behavior, dict) else 0.5

            slip = 0.05 + 0.20 * anxiety - 0.05 * pace
            guess = 0.05 + 0.20 * confidence
            return max(0.02, min(0.40, guess)), max(0.02, min(0.40, slip))

        return 0.15, 0.12

    def _estimate_confidence(self, features: Optional[Dict]) -> float:
        """估算用户信心因子"""
        if not features:
            return 0.7

        dims = features.get("dimensions", features.get("feature_dimensions", {}))
        if not isinstance(dims, dict):
            return 0.7

        emotional = dims.get("emotional_state", {})
        if isinstance(emotional, dict):
            confidence = (emotional.get("confidence_level", 50) or 50) / 100.0
            interest = (emotional.get("interest_level", 50) or 50) / 100.0
            return max(0.3, min(1.0, (confidence * 0.6 + interest * 0.4)))

        return 0.7

    # ------------------------------------------------------------------
    # 孪生作答模拟
    # ------------------------------------------------------------------

    def simulate_answer(self, user_id: str, question: Dict[str, Any]) -> Dict[str, Any]:
        """模拟孪生用户作答
        
        参数:
            question: {
                "question_id": str,
                "knowledge_point": str,    # 所属知识点
                "difficulty": float,        # 难度 [0, 1]
                "question_type": str,       # 题型: choice/theory/practice
                "correct_answer": Any,      # 正确答案
                "options": List (选择题时),  # 选项列表
            }
        
        返回:
        {
            "simulated_correct": bool,      # 孪生是否答对
            "confidence": float,            # 孪生作答信心 [0, 1]
            "simulated_answer": Any,        # 孪生选择的答案
            "correct_probability": float,   # 预估正确概率
            "factors": {                    # 各因子贡献
                "mastery_contribution": float,
                "ability_contribution": float,
                "difficulty_penalty": float,
                "noise": float
            }
        }
        """
        twin_data = _load_twin_data(user_id)
        if not twin_data or not twin_data.get("enabled", False):
            return {"error": "孪生未启用或不存在", "simulated_correct": None}

        profile = twin_data.get("profile", {})
        if not profile:
            return {"error": "孪生画像为空", "simulated_correct": None}

        kp = question.get("knowledge_point", "")
        difficulty = float(question.get("difficulty", 0.5))
        q_type = question.get("question_type", "choice")

        # --- 1. 知识掌握度贡献 ---
        knowledge_mastery = profile.get("knowledge_mastery", {})
        mastery = knowledge_mastery.get(kp, 0.3)  # 未知知识点默认 0.3

        # --- 2. 能力匹配度 ---
        ability_weights = profile.get("ability_weights", {})
        question_type_factors = {
            "choice": ability_weights.get("memory", 0.5),
            "theory": ability_weights.get("comprehension", 0.5),
            "practice": ability_weights.get("application", 0.5) * 0.7 +
                        ability_weights.get("logical_thinking", 0.5) * 0.3
        }
        ability_match = question_type_factors.get(q_type, 0.5)

        # --- 3. 综合正确概率 ---
        # P(correct) = sigmoid( mastery * ability_match - difficulty + bias )
        bias = profile.get("confidence_factor", 0.7) * 0.2 - 0.1
        raw_score = mastery * ability_match - difficulty + bias

        correct_prob = _sigmoid(raw_score)

        # --- 4. 加入 BKT 猜对/失误因子 ---
        guess_p = profile.get("guess_probability", 0.15)
        slip_p = profile.get("slip_probability", 0.10)
        # P(observed_correct) = P(knows) * (1 - P(S)) + P(not_knows) * P(G)
        adjusted_prob = correct_prob * (1 - slip_p) + (1 - correct_prob) * guess_p

        # --- 5. 模拟作答 ---
        simulated_correct = random.random() < adjusted_prob

        # --- 6. 模拟错误答案 ---
        simulated_answer = None
        if simulated_correct:
            simulated_answer = question.get("correct_answer")
        else:
            simulated_answer = self._simulate_wrong_answer(question, profile)

        return {
            "simulated_correct": simulated_correct,
            "confidence": round(adjusted_prob, 3),
            "simulated_answer": simulated_answer,
            "correct_probability": round(adjusted_prob, 3),
            "factors": {
                "mastery_contribution": round(mastery, 3),
                "ability_contribution": round(ability_match, 3),
                "difficulty_penalty": round(difficulty, 3),
                "bias": round(bias, 3),
                "guess_probability": guess_p,
                "slip_probability": slip_p,
                "raw_score": round(raw_score, 3)
            }
        }

    def _simulate_wrong_answer(self, question: Dict[str, Any],
                               profile: Dict[str, Any]) -> Any:
        """模拟用户错误答案"""
        q_type = question.get("question_type", "choice")
        options = question.get("options", [])

        if q_type == "choice" and options:
            error_patterns = profile.get("error_patterns", {})
            correct = question.get("correct_answer")

            # 根据错误模式权重选择错误答案
            # 如果不确定性高，倾向于选择"看起来像"的选项
            # 简单策略：排除正确答案后随机选
            wrong_options = [opt for opt in options if opt != correct]
            if wrong_options:
                return random.choice(wrong_options)

        return None

    # ------------------------------------------------------------------
    # 对比记录
    # ------------------------------------------------------------------

    async def record_comparison(self, user_id: str, question: Dict[str, Any],
                          user_correct: bool, twin_result: Dict[str, Any],
                          user_answer: Any = None) -> Dict[str, Any]:
        """异步记录一次用户 vs 孪生对比结果"""
        loop = asyncio.get_running_loop()

        def _do_record():
            twin_data = _load_twin_data(user_id)
            if not twin_data:
                return {"success": False, "message": "孪生数据未找到"}
            if not twin_data.get("enabled", False):
                return {"success": False, "message": "孪生未开启"}
            twin_correct = twin_result.get("simulated_correct")
            if twin_correct is None:
                return {"success": False, "message": "孪生未作答"}

            if user_correct and twin_correct:
                result_type = ComparisonResult.BOTH_CORRECT
            elif not user_correct and not twin_correct:
                result_type = ComparisonResult.BOTH_WRONG
            elif user_correct and not twin_correct:
                result_type = ComparisonResult.USER_RIGHT_TWIN_WRONG
            else:
                result_type = ComparisonResult.USER_WRONG_TWIN_RIGHT

            twin_confidence_val = twin_result.get("confidence", 0) or 0
            _qtype_to_atype = {"choice": "theory_answer", "theory": "theory_answer",
                               "practice": "practice_submit", "submission": "practice_submit"}
            q_type = question.get("question_type", "choice")

            record = {
                "timestamp": datetime.now().isoformat(),
                "question_id": question.get("question_id", ""),
                "knowledge_point": question.get("knowledge_point", ""),
                "difficulty": question.get("difficulty", 0.5),
                "user_correct": user_correct,
                "twin_correct": twin_correct,
                "result_type": result_type,
                "twin_confidence": twin_confidence_val,
                "twin_correct_probability": twin_result.get("correct_probability", 0),
                "match_degree": _calc_match_degree(user_correct, twin_confidence_val),
                "activity_type": _qtype_to_atype.get(q_type, "theory_answer"),
                # 做题详情
                "user_answer": user_answer,
                "twin_answer": twin_result.get("simulated_answer"),
                "correct_answer": question.get("correct_answer"),
                "question_content": question.get("content", question.get("question", "")),
                "question_options": question.get("options", []),
            }
            history = twin_data.setdefault("comparison_history", [])
            history.append(record)
            _save_twin_data(user_id, twin_data)
            return {
                "success": True, "record": record, "result_type": result_type,
                "message": self._get_comparison_message(result_type)
            }

        result = await loop.run_in_executor(_TWIN_EXECUTOR, _do_record)
        if result.get("success"):
            await self._incremental_update(user_id, _load_twin_data(user_id), result["record"])
        return result

    def _get_comparison_message(self, result_type: str) -> str:
        """根据对比结果类型生成诊断消息"""
        messages = {
            ComparisonResult.BOTH_CORRECT: "知识点掌握良好，孪生认知一致",
            ComparisonResult.BOTH_WRONG: "知识点偏难，建议重新学习基础内容",
            ComparisonResult.USER_RIGHT_TWIN_WRONG: "孪生画像需要校准，用户实际能力高于预测",
            ComparisonResult.USER_WRONG_TWIN_RIGHT: "发现知识盲区！建议重点巩固此知识点"
        }
        return messages.get(result_type, "对比完成")

    # ------------------------------------------------------------------
    # 历史查询
    # ------------------------------------------------------------------

    def get_comparison_history(self, user_id: str,
                               limit: int = 50,
                               result_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取对比历史"""
        twin_data = _load_twin_data(user_id)
        if not twin_data:
            return []

        history = twin_data.get("comparison_history", [])
        if result_type:
            history = [r for r in history if r.get("result_type") == result_type]

        # 对返回的记录做回填：旧记录没有 user_answer/twin_answer/question_content 等字段
        result = []
        for r in history[-limit:]:
            result.append(self._backfill_record(r))
        return result

    def _backfill_record(self, r: Dict) -> Dict:
        """回填旧记录的缺失字段，归一化数据"""
        # ★ 归一化 twin_confidence：统一到 0~1 范围
        raw_conf = r.get("twin_confidence", 0) or 0
        if raw_conf > 1:
            r["twin_confidence"] = round(raw_conf / 100.0, 3)
        elif raw_conf < 0:
            r["twin_confidence"] = 0
        conf = r["twin_confidence"]

        if r.get("user_answer") is None:
            atype = r.get("activity_type", "")
            uc = r.get("user_correct", False)
            if atype == "practice_submit":
                score = r.get("user_score")
                r["user_answer"] = f"得分{score}分{'（通过）' if uc else '（未通过）'}" if score is not None else ("通过" if uc else "未通过")
            elif atype == "video_watch":
                cr = r.get("user_completion_rate", 0)
                r["user_answer"] = f"完成率{int(cr*100)}%（{'理解' if uc else '未理解'}）" if cr else ("已理解" if uc else "未理解")
            else:
                r["user_answer"] = "答对" if uc else "答错"

        if r.get("twin_answer") is None:
            tc = r.get("twin_correct", False)
            conf_str = f"（孪生信心{int(conf*100)}%）" if conf else ""
            atype = r.get("activity_type", "")
            if atype == "practice_submit":
                r["twin_answer"] = f"{'通过' if tc else '未通过'}{conf_str}"
            elif atype == "video_watch":
                r["twin_answer"] = f"{'理解' if tc else '未理解'}{conf_str}"
            else:
                r["twin_answer"] = f"{'答对' if tc else '答错'}{conf_str}"

        if not r.get("question_content"):
            kp = r.get("knowledge_point", "")
            atype = r.get("activity_type", "")
            r["question_content"] = f"{kp}相关{'题' if atype == 'theory_answer' else '练习'}" if kp else f"{'题目' if atype == 'theory_answer' else '练习'}记录"

        if r.get("correct_answer") is None:
            r["correct_answer"] = ""

        # ★ 修复匹配度：旧数据可能因 confidence 未归一化计算导致负数
        md = r.get("match_degree")
        if md is not None and (md > 1 or md < -0.01):
            uc = r.get("user_correct", False)
            r["match_degree"] = _calc_match_degree(uc, conf)

        if not r.get("question_options"):
            r["question_options"] = []

        return r

    def get_comparison_stats(self, user_id: str) -> Dict[str, Any]:
        """获取对比统计摘要（含匹配度和批次更新信息）"""
        twin_data = _load_twin_data(user_id)
        if not twin_data:
            return {"exists": False}

        history = twin_data.get("comparison_history", [])
        if not history:
            return {
                "exists": True,
                "total": 0,
                "message": "暂无对比记录",
                "avg_match_degree": 0,
                "batch_update_at": twin_data.get("last_batch_update_at", ""),
                "batch_update_size": BATCH_UPDATE_SIZE,
                "pending_records": 0
            }

        total = len(history)
        both_correct = sum(1 for r in history if r["result_type"] == ComparisonResult.BOTH_CORRECT)
        both_wrong = sum(1 for r in history if r["result_type"] == ComparisonResult.BOTH_WRONG)
        user_right_twin_wrong = sum(1 for r in history if r["result_type"] == ComparisonResult.USER_RIGHT_TWIN_WRONG)
        user_wrong_twin_right = sum(1 for r in history if r["result_type"] == ComparisonResult.USER_WRONG_TWIN_RIGHT)

        # 薄弱知识点
        weak_points = set()
        for r in history:
            if r["result_type"] == ComparisonResult.USER_WRONG_TWIN_RIGHT:
                kp = r.get("knowledge_point", "")
                if kp:
                    weak_points.add(kp)

        # 匹配度统计（连续值，非二进制）
        match_degrees = [r.get("match_degree", 0.5) for r in history if r.get("match_degree") is not None]
        avg_match = round(sum(match_degrees) / len(match_degrees), 3) if match_degrees else 0

        # 批次更新信息
        batch_idx = twin_data.get("last_batch_update_index", 0)
        pending_records = total - batch_idx

        return {
            "exists": True,
            "total": total,
            "both_correct": both_correct,
            "both_correct_pct": round(both_correct / total * 100, 1) if total else 0,
            "both_wrong": both_wrong,
            "both_wrong_pct": round(both_wrong / total * 100, 1) if total else 0,
            "user_right_twin_wrong": user_right_twin_wrong,
            "user_right_twin_wrong_pct": round(user_right_twin_wrong / total * 100, 1) if total else 0,
            "user_wrong_twin_right": user_wrong_twin_right,
            "user_wrong_twin_right_pct": round(user_wrong_twin_right / total * 100, 1) if total else 0,
            "weak_knowledge_points": list(weak_points)[:10],
            "weak_point_count": len(weak_points),
            # 新增：匹配度（连续值）
            "avg_match_degree": avg_match,
            "avg_match_degree_pct": round(avg_match * 100, 1),
            "match_degree_distribution": {
                "high": round(sum(1 for m in match_degrees if m >= 0.8) / total * 100, 1) if total else 0,
                "medium": round(sum(1 for m in match_degrees if 0.4 <= m < 0.8) / total * 100, 1) if total else 0,
                "low": round(sum(1 for m in match_degrees if m < 0.4) / total * 100, 1) if total else 0,
            },
            # 新增：批次更新信息
            "batch_update_at": twin_data.get("last_batch_update_at", ""),
            "batch_update_size": BATCH_UPDATE_SIZE,
            "pending_records": pending_records,
            "pending_batch": pending_records >= BATCH_UPDATE_SIZE,
            "last_batch_adjustments": twin_data.get("last_batch_adjustments", [])
        }

    def clear_history(self, user_id: str) -> Dict[str, Any]:
        """清空对比历史"""
        twin_data = _load_twin_data(user_id)
        if not twin_data:
            return {"success": False, "message": "孪生数据未找到"}

        twin_data["comparison_history"] = []
        _save_twin_data(user_id, twin_data)
        return {"success": True, "message": "对比历史已清空"}

    # ------------------------------------------------------------------
    # 统一活动记录（供所有系统入口调用）
    # ------------------------------------------------------------------

    def record_user_activity(self, user_id: str, activity_type: str,
                              activity_data: Dict[str, Any],
                              user_outcome: Dict[str, Any]) -> Dict[str, Any]:
        """同步记录用户活动（内部通过线程池调异步方法，不阻塞事件循环）
        
        兼容接口，推荐使用 record_user_activity_async
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        async def _run():
            return await self.record_user_activity_async(user_id, activity_type, activity_data, user_outcome)

        if loop and loop.is_running():
            # 已有事件循环 → 在线程池执行协程
            import asyncio as _aio
            future = _aio.run_coroutine_threadsafe(_run(), loop)
            return future.result(timeout=30)
        else:
            # 无事件循环 → 直接运行
            return asyncio.run(_run())

    async def _record_theory_comparison(self, twin_data, profile, user_id,
                                   activity_data, user_outcome) -> Dict[str, Any]:
        """理论题对比（异步，I/O 走线程池）"""
        loop = asyncio.get_running_loop()
        user_correct = user_outcome.get("correct", False)
        knowledge_point = activity_data.get("knowledge_point", "") or ""
        difficulty = float(activity_data.get("difficulty", 0.5))
        q_type = activity_data.get("question_type", "choice")
        kp = knowledge_point or next(iter(profile.get("knowledge_mastery", {})), "")
        twin_sim = self._simulate_for_kp(profile, kp, difficulty, q_type)
        twin_correct = twin_sim["simulated_correct"]
        result_type = self._classify_comparison(user_correct, twin_correct)
        question = activity_data.get("question", {})
        record = {
            "timestamp": datetime.now().isoformat(),
            "activity_type": "theory_answer",
            "question_id": activity_data.get("question_id", ""),
            "knowledge_point": knowledge_point, "difficulty": difficulty,
            "user_correct": user_correct, "twin_correct": twin_correct,
            "result_type": result_type,
            "twin_confidence": twin_sim["confidence"],
            "twin_correct_probability": twin_sim["correct_probability"],
            "match_degree": _calc_match_degree(user_correct, twin_sim["confidence"]),
            # 做题详情
            "user_answer": user_outcome.get("user_answer"),
            "twin_answer": twin_sim.get("simulated_answer"),
            "correct_answer": question.get("correct_answer", activity_data.get("correct_answer")),
            "question_content": question.get("content", question.get("question", "")),
            "question_options": question.get("options", []),
        }
        twin_data.setdefault("comparison_history", []).append(record)
        await loop.run_in_executor(_TWIN_EXECUTOR, _save_twin_data, user_id, twin_data)
        return record

    async def _record_practice_comparison(self, twin_data, profile, user_id,
                                     activity_data, user_outcome) -> Dict[str, Any]:
        """编程题对比（异步，LLM 模拟孪生写代码，数学模型预测正误）"""
        loop = asyncio.get_running_loop()
        user_score = float(user_outcome.get("score", 0))
        user_correct = user_score >= 60
        knowledge_point = activity_data.get("knowledge_point", "") or ""
        difficulty = float(activity_data.get("difficulty", 0.5))
        kp = knowledge_point or next(iter(profile.get("knowledge_mastery", {})), "")

        # 1. 数学模型预测孪生正确性
        twin_sim = self._simulate_for_kp(profile, kp, difficulty, "practice")
        twin_correct = twin_sim["simulated_correct"]
        result_type = self._classify_comparison(user_correct, twin_correct)

        # 2. LLM 让孪生真正写代码（用于展示）
        twin_code = None
        try:
            from Agent.children_agent.twin_agent import twin_answer_practice_question
            problem_data = {
                "content": activity_data.get("question_content", ""),
                "knowledge_point": knowledge_point or kp,
                "difficulty": difficulty,
                "language": activity_data.get("language", "python"),
            }
            twin_result = await twin_answer_practice_question(profile, problem_data)
            if not twin_result.get("_fallback"):
                twin_code = twin_result.get("simulated_answer")
        except Exception:
            pass

        # 3. 构建 twin_answer：有 LLM 代码就展示代码，否则回退到通过/未通过
        if twin_code:
            _code_preview = twin_code[:200] + ("..." if len(twin_code) > 200 else "")
            twin_answer_display = _code_preview
        else:
            twin_answer_display = f"{'通过' if twin_correct else '未通过'}（孪生信心{int(twin_sim['confidence']*100)}%）"

        # 优先使用 API 传入的 user_answer（如代码预览），否则用分数推导
        _user_ans = user_outcome.get("user_answer")
        if _user_ans is None:
            _user_ans = f"得分{user_score}分{'（通过）' if user_correct else '（未通过）'}"
        _q_content = activity_data.get("question_content", activity_data.get("problem_id", ""))

        record = {
            "timestamp": datetime.now().isoformat(),
            "activity_type": "practice_submit",
            "question_id": activity_data.get("problem_id", ""),
            "knowledge_point": knowledge_point, "difficulty": difficulty,
            "user_correct": user_correct, "user_score": user_score,
            "twin_correct": twin_correct, "result_type": result_type,
            "twin_confidence": twin_sim["confidence"],
            "twin_correct_probability": twin_sim["correct_probability"],
            "match_degree": _calc_match_degree(user_correct, twin_sim["confidence"]),
            # 做题详情
            "user_answer": _user_ans,
            "twin_answer": twin_answer_display,
            "correct_answer": activity_data.get("correct_answer", "60分以上为通过"),
            "question_content": _q_content,
            "question_options": [],
        }
        twin_data.setdefault("comparison_history", []).append(record)
        await loop.run_in_executor(_TWIN_EXECUTOR, _save_twin_data, user_id, twin_data)
        return record

    async def _record_video_comparison(self, twin_data, profile, user_id,
                                  activity_data, user_outcome) -> Dict[str, Any]:
        """视频观看对比（异步，I/O 走线程池）"""
        loop = asyncio.get_running_loop()
        completion_rate = float(user_outcome.get("completion_rate", 0))
        knowledge_point = activity_data.get("knowledge_point", "") or ""
        difficulty = float(activity_data.get("difficulty", 0.3))
        kp = knowledge_point or next(iter(profile.get("knowledge_mastery", {})), "")
        twin_sim = self._simulate_for_kp(profile, kp, difficulty, "theory")
        user_understood = completion_rate >= 0.7
        _video_status = "理解" if user_understood else "未理解"
        twin_correct = twin_sim["simulated_correct"]
        _twin_video_status = "理解" if twin_correct else "未理解"
        result_type = self._classify_comparison(user_understood, twin_correct)
        record = {
            "timestamp": datetime.now().isoformat(),
            "activity_type": "video_watch",
            "question_id": activity_data.get("bvid", ""),
            "knowledge_point": knowledge_point, "difficulty": difficulty,
            "user_correct": user_understood,
            "user_completion_rate": completion_rate,
            "user_watch_duration": user_outcome.get("watch_duration", 0),
            "user_rewind_count": user_outcome.get("rewind_count", 0),
            "twin_correct": twin_correct, "result_type": result_type,
            "twin_confidence": twin_sim["confidence"],
            "twin_correct_probability": twin_sim["correct_probability"],
            "match_degree": _calc_match_degree(user_understood, twin_sim["confidence"]),
            # 做题详情
            "user_answer": f"完成率{int(completion_rate*100)}%（{_video_status}）",
            "twin_answer": f"{_twin_video_status}（孪生信心{int(twin_sim['confidence']*100)}%）",
            "correct_answer": "完成率≥70%视为已理解",
            "question_content": activity_data.get("video_title", activity_data.get("bvid", "")),
            "question_options": [],
        }
        twin_data.setdefault("comparison_history", []).append(record)
        await loop.run_in_executor(_TWIN_EXECUTOR, _save_twin_data, user_id, twin_data)
        return record

    def _simulate_for_kp(self, profile: Dict, knowledge_point: str,
                          difficulty: float, question_type: str) -> Dict[str, Any]:
        """针对单个知识点模拟孪生作答"""
        knowledge_mastery = profile.get("knowledge_mastery", {})
        mastery = knowledge_mastery.get(knowledge_point, 0.3)

        ability_weights = profile.get("ability_weights", {})
        q_type_map = {
            "choice": ability_weights.get("memory", 0.5),
            "theory": ability_weights.get("comprehension", 0.5),
            "practice": ability_weights.get("application", 0.5) * 0.7 +
                        ability_weights.get("logical_thinking", 0.5) * 0.3
        }
        ability_match = q_type_map.get(question_type, 0.5)
        bias = profile.get("confidence_factor", 0.7) * 0.2 - 0.1
        raw_score = mastery * ability_match - difficulty + bias
        correct_prob = _sigmoid(raw_score)

        guess_p = profile.get("guess_probability", 0.15)
        slip_p = profile.get("slip_probability", 0.10)
        adjusted_prob = correct_prob * (1 - slip_p) + (1 - correct_prob) * guess_p
        simulated_correct = random.random() < adjusted_prob

        # 模拟答案文本（用于前端展示）
        _answer_lookup = {
            "choice": "选项" + ("A" if simulated_correct else "B"),
            "theory": "正确理解" if simulated_correct else "理解偏差",
            "practice": "通过" if simulated_correct else "未通过",
        }
        simulated_answer = _answer_lookup.get(question_type,
                            "正确" if simulated_correct else "错误")

        return {
            "simulated_correct": simulated_correct,
            "simulated_answer": simulated_answer,
            "confidence": round(adjusted_prob, 3),
            "correct_probability": round(adjusted_prob, 3),
            "factors": {
                "mastery": round(mastery, 3),
                "ability_match": round(ability_match, 3),
                "difficulty": round(difficulty, 3),
                "bias": round(bias, 3),
                "raw_score": round(raw_score, 3)
            }
        }

    def _classify_comparison(self, user_correct: bool, twin_correct: bool) -> str:
        """判定对比结果类型"""
        if user_correct and twin_correct:
            return ComparisonResult.BOTH_CORRECT
        elif not user_correct and not twin_correct:
            return ComparisonResult.BOTH_WRONG
        elif user_correct and not twin_correct:
            return ComparisonResult.USER_RIGHT_TWIN_WRONG
        else:
            return ComparisonResult.USER_WRONG_TWIN_RIGHT

    # ------------------------------------------------------------------
    # 异步接口（用于 FastAPI）
    # ------------------------------------------------------------------

    async def get_twin_status_async(self, user_id: str) -> Dict[str, Any]:
        """异步获取孪生状态"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_TWIN_EXECUTOR, self.get_twin_status, user_id)

    async def set_twin_enabled_async(self, user_id: str, enabled: bool) -> Dict[str, Any]:
        """异步设置孪生开关"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_TWIN_EXECUTOR, self.set_twin_enabled, user_id, enabled)

    async def record_user_activity_async(self, user_id: str, activity_type: str,
                                          activity_data: Dict[str, Any],
                                          user_outcome: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """异步记录用户活动并自动与孪生对比
        
        - theory_answer: 调用 LLM TwinAgent 模拟孪生作答
        - practice_submit / video_watch: 使用数学模型模拟
        """
        # 1. 检查孪生是否存在且启用（同步，轻量）
        loop = asyncio.get_running_loop()

        def _check_twin():
            twin_data = _load_twin_data(user_id)
            if not twin_data or not twin_data.get("enabled", False):
                return None
            return twin_data

        twin_data = await loop.run_in_executor(_TWIN_EXECUTOR, _check_twin)
        if twin_data is None:
            return None

        profile = twin_data.get("profile", {})
        if not profile:
            return None

        # 2. 根据活动类型处理
        if activity_type == "theory_answer":
            result = await self._record_theory_comparison_async(
                twin_data, profile, user_id, activity_data, user_outcome
            )
        elif activity_type == "practice_submit":
            result = await self._record_practice_comparison(
                twin_data, profile, user_id, activity_data, user_outcome
            )
        elif activity_type == "video_watch":
            result = await self._record_video_comparison(
                twin_data, profile, user_id, activity_data, user_outcome
            )
        else:
            return None

        # 3. 每次对比后微调孪生掌握度
        if result:
            await self._incremental_update(user_id, twin_data, result)

        return result

    async def _record_theory_comparison_async(self, twin_data, profile, user_id,
                                               activity_data, user_outcome) -> Dict[str, Any]:
        """理论题对比（异步LLM版）"""
        user_correct = user_outcome.get("correct", False)
        knowledge_point = activity_data.get("knowledge_point", "") or ""
        difficulty = float(activity_data.get("difficulty", 0.5))
        q_type = activity_data.get("question_type", "choice")

        twin_reasoning = ""
        twin_simulated_answer = None
        # 调用 TwinAgent 让孪生真正作答
        try:
            from Agent.children_agent.twin_agent import twin_answer_theory_question
            question = activity_data.get("question", {})
            agent_input = {
                **question,
                "knowledge_point": knowledge_point,
                "question_type": q_type,
                "difficulty": difficulty,
            }
            twin_result = await twin_answer_theory_question(profile, agent_input)

            if twin_result.get("_fallback"):
                # LLM 不可用，回退到数学概率模型
                kp = knowledge_point or next(iter(profile.get("knowledge_mastery", {})), "")
                math_sim = self._simulate_for_kp(profile, kp, difficulty, q_type)
                twin_correct = math_sim["simulated_correct"]
                confidence = math_sim["confidence"]
                probability = math_sim["correct_probability"]
                twin_simulated_answer = math_sim.get("simulated_answer")
            else:
                twin_correct = twin_result.get("simulated_correct", False)
                confidence = twin_result.get("confidence", 50)
                probability = confidence / 100.0
                twin_reasoning = twin_result.get("reasoning", "")
                twin_simulated_answer = twin_result.get("simulated_answer")

        except Exception as e:
            import traceback
            traceback.print_exc()
            kp = knowledge_point or next(iter(profile.get("knowledge_mastery", {})), "")
            math_sim = self._simulate_for_kp(profile, kp, difficulty, q_type)
            twin_correct = math_sim["simulated_correct"]
            confidence = math_sim["confidence"]
            probability = math_sim["correct_probability"]
            twin_simulated_answer = math_sim.get("simulated_answer")

        # 记录对比
        result_type = self._classify_comparison(user_correct, twin_correct)
        question = activity_data.get("question", {})
        record = {
            "timestamp": datetime.now().isoformat(),
            "activity_type": "theory_answer",
            "question_id": activity_data.get("question_id", ""),
            "knowledge_point": knowledge_point, "difficulty": difficulty,
            "user_correct": user_correct, "twin_correct": twin_correct,
            "result_type": result_type,
            "twin_confidence": confidence,
            "twin_correct_probability": probability,
            "twin_reasoning": twin_reasoning,
            "match_degree": _calc_match_degree(user_correct, float(probability)),
            # 做题详情
            "user_answer": user_outcome.get("user_answer"),
            "twin_answer": twin_simulated_answer,
            "correct_answer": question.get("correct_answer", activity_data.get("correct_answer")),
            "question_content": question.get("content", question.get("question", "")),
            "question_options": question.get("options", []),
        }

        history = twin_data.setdefault("comparison_history", [])
        history.append(record)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_TWIN_EXECUTOR, _save_twin_data, user_id, twin_data)
        return record

    async def analyze_comparison(self, user_id: str, record_index: int) -> Dict[str, Any]:
        """基于用户和孪生的做题信息生成真实分析（LLM 驱动），附带可视化数据"""
        loop = asyncio.get_running_loop()

        def _load():
            twin_data = _load_twin_data(user_id)
            if not twin_data:
                return None, None
            history = twin_data.get("comparison_history", [])
            if record_index < 0 or record_index >= len(history):
                return None, None
            r = self._backfill_record(dict(history[record_index]))
            return r, twin_data.get("profile", {})

        record, profile = await loop.run_in_executor(_TWIN_EXECUTOR, _load)
        if not record:
            return {"analysis": "记录不存在", "success": False}

        kp = record.get("knowledge_point", "") or "未知知识点"
        diff = record.get("difficulty", 0.5)
        user_answer = record.get("user_answer")
        twin_answer = record.get("twin_answer")
        correct_answer = record.get("correct_answer")
        question_content = record.get("question_content", "")
        options = record.get("question_options", [])
        user_correct = record.get("user_correct", False)
        twin_correct = record.get("twin_correct", False)
        twin_confidence = record.get("twin_confidence", 0)
        twin_reasoning = record.get("twin_reasoning", "")
        rt = record.get("result_type", "")
        match_deg = record.get("match_degree", 0.5)

        # --- 构建可视化数据 ---
        km = profile.get("knowledge_mastery", {}) if profile else {}
        kp_mastery = km.get(kp, None)
        dim_scores = profile.get("dimension_scores", []) if profile else []
        overall = profile.get("overall_score", 0) if profile else 0

        result_type_labels = {
            "both_correct": "用户答对，孪生也答对",
            "both_wrong": "用户答错，孪生也答错",
            "user_right_twin_wrong": "用户答对，孪生答错",
            "user_wrong_twin_right": "用户答错，孪生答对",
        }

        # ★ 归一化 difficulty：统一到 0~1 范围
        # 题库难度可能是 1~3 分级（1简单/3困难），也可能是 0~100 的百分比
        if diff > 1:
            # 尝试自动缩放到 0~1（假设最大难度为 3 或 5）
            diff = round(diff / 3.0, 3) if diff <= 3 else round(diff / 5.0, 3) if diff <= 5 else round(diff / 100.0, 3)
        elif diff < 0:
            diff = 0
        # 如果难度是默认值 0.5，根据实际作答情况动态估算难度
        if 0.49 <= diff <= 0.51 and rt:
            difficulty_map = {
                "both_correct": 0.20,          # 双方都答对 → 简单
                "both_wrong": 0.75,             # 双方都答错 → 困难
                "user_right_twin_wrong": 0.35,  # 用户对孪生错 → 偏简单
                "user_wrong_twin_right": 0.65,  # 用户错孪生对 → 偏困难
            }
            estimated = difficulty_map.get(rt)
            if estimated is not None:
                diff = estimated

        # 视觉进度条颜色
        match_color = "#22c55e" if match_deg >= 0.7 else ("#f59e0b" if match_deg >= 0.4 else "#ef4444")
        conf_color = "#22c55e" if twin_confidence >= 0.7 else ("#f59e0b" if twin_confidence >= 0.4 else "#ef4444")
        mastery_color = "#22c55e" if kp_mastery and kp_mastery >= 0.7 else ("#f59e0b" if kp_mastery and kp_mastery >= 0.4 else "#ef4444") if kp_mastery else "#888"

        visual_data = {
            "comparison": {
                "user": {"correct": user_correct, "answer": str(user_answer or "—")},
                "twin": {"correct": twin_correct, "answer": str(twin_answer or "—"), "confidence": round(twin_confidence, 2)},
                "correct_answer": str(correct_answer or "—"),
                "result_label": result_type_labels.get(rt, rt),
            },
            "metrics": {
                "match_degree": {"value": round(match_deg, 2), "pct": int(match_deg * 100), "color": match_color},
                "twin_confidence": {"value": round(twin_confidence, 2), "pct": int(twin_confidence * 100), "color": conf_color},
                "kp_mastery": {"value": round(kp_mastery, 2) if kp_mastery else None, "pct": int(kp_mastery * 100) if kp_mastery else None, "color": mastery_color},
                "difficulty": int(diff * 100),
            },
            "knowledge_point": kp,
        }

        # --- 调用 LLM 生成分析 ---
        try:
            from utils.llm_config import get_chat_openai
            from utils.async_llm_caller import call_llm_with_retry

            llm = get_chat_openai(temperature=0.4, max_tokens=1024)

            prompt = f"""你是一位资深教育分析专家。请基于以下数字孪生对比数据，对用户的学习情况做真实、具体的分析。

## 题目信息
- 知识点：{kp}
- 难度：{int(diff * 100)}%
- 题目内容：{question_content if question_content else '（无具体题目内容）'}
- 选项：{', '.join(str(o) for o in options) if options else '（无选项）'}
- 正确答案：{correct_answer if correct_answer is not None else '（未知）'}

## 用户 vs 孪生对比
- 对比结果：{result_type_labels.get(rt, rt)}
- 用户答案：{user_answer if user_answer is not None else '（未知）'}
- 孪生答案：{twin_answer if twin_answer is not None else '（未知）'}
- 孪生信心度：{int(twin_confidence * 100) if twin_confidence else '未知'}%
{f'孪生思路：{twin_reasoning}' if twin_reasoning else ''}
- 匹配度：{int(match_deg * 100)}%

## 分析要求
请从以下角度进行分析（100-300字，中文）：
1. 用户和孪生的答案差异在哪？为什么会存在这种差异？
2. 基于正确答案，分析用户和孪生各自在理解上的长处和短板
3. 针对知识点 '{kp}'，给出具体的学习建议
4. 孪生对用户的预测准确度如何？是否需要调整孪生画像？

要求：分析必须基于实际数据，不要空洞笼统，要具体到题目本身。"""

            response = await call_llm_with_retry(
                llm=llm,
                prompt=prompt,
                max_retries=2,
                error_msg="对比分析生成失败"
            )

            if response and hasattr(response, 'content'):
                analysis_text = response.content.strip()
            elif response and isinstance(response, str):
                analysis_text = response.strip()
            else:
                analysis_text = self._build_fallback_analysis(record)

        except Exception as e:
            import traceback
            traceback.print_exc()
            analysis_text = self._build_fallback_analysis(record)

        return {
            "success": True,
            "analysis_text": analysis_text,
            "visual_data": visual_data,
            "record_index": record_index,
            "result_type": rt,
        }

    def _build_fallback_analysis(self, record: Dict) -> str:
        """LLM 不可用时的兜底分析"""
        kp = record.get("knowledge_point", "") or "未知知识点"
        user_correct = record.get("user_correct", False)
        twin_correct = record.get("twin_correct", False)
        diff = record.get("difficulty", 0.5)
        rt = record.get("result_type", "")

        lines = [f"【{kp}】难度{int(diff*100)}%"]
        lines.append(f"用户{'答对' if user_correct else '答错'} | 孪生{'答对' if twin_correct else '答错'}")

        if rt == "user_wrong_twin_right":
            lines.append("用户未能答对此题而孪生正确，说明该知识点存在盲区，建议重新学习基础概念。")
        elif rt == "user_right_twin_wrong":
            lines.append("用户答对而孪生预测错误，孪生可能低估了用户水平，建议重建孪生画像。")
        elif rt == "both_correct":
            lines.append("双方一致通过，该知识点掌握良好。")
        else:
            lines.append("双方均未答对，需要系统学习该知识点。")

        return "\n".join(lines)

    async def _incremental_update(self, user_id: str, twin_data: Dict, record: Dict):
        """每次对比后微调孪生知识掌握度（基于批次更新策略）
        
        逐条记录仅标记，累积 BATCH_UPDATE_SIZE 条后批量分析更新：
        - 分析批次内各知识点的错误模式
        - 根据批次趋势做更稳健的掌握度调整
        - 更新孪生的整体 confidence_factor
        
        批次更新完成后重置计数器。
        """
        try:
            kp = record.get("knowledge_point", "")
            if not kp:
                return

            result_type = record.get("result_type", "")
            profile = twin_data.setdefault("profile", {})
            km = profile.setdefault("knowledge_mastery", {})

            # 1. 先做一次精调（但幅度减小为 ±0.03，作为快速响应）
            current = km.get(kp, 0.3)
            if result_type == ComparisonResult.USER_RIGHT_TWIN_WRONG:
                new_val = min(1.0, current + 0.03)
                km[kp] = round(new_val, 3)
            elif result_type == ComparisonResult.USER_WRONG_TWIN_RIGHT:
                new_val = max(0.05, current - 0.03)
                km[kp] = round(new_val, 3)
            else:
                pass  # 一致不做小幅调整

            # 2. 累积批次索引，检查是否需要批量更新
            history = twin_data.get("comparison_history", [])
            batch_idx = twin_data.get("last_batch_update_index", 0)
            new_records_since_batch = len(history) - batch_idx

            if new_records_since_batch >= BATCH_UPDATE_SIZE:
                await self._run_batch_update(user_id, twin_data, history, batch_idx)
            else:
                # ★ 批次未满时也要保存 ±0.03 的精调，否则在内存中丢失
                _save_twin_data(user_id, twin_data)

        except Exception as e:
            import traceback
            traceback.print_exc()

    async def _run_batch_update(self, user_id: str, twin_data: Dict,
                                  history: List[Dict], batch_idx: int):
        """批量分析 BATCH_UPDATE_SIZE 条对比记录，更新孪生全部特征
        
        批次更新内容（4层级联）：
        1. 8维特征 dimension_scores：按 activity_type 权重映射 + 阈值调整
        2. ability_weights：从更新后的维度重算
        3. BKT 参数 (guess/slip)：从情绪维度重算
        4. error_patterns：按结果类型分布重算
        """
        # ---- 维度常量 ----
        # 8维名称（与 _extract_dimension_scores 中的 key 顺序一致）
        DIM_NAMES = ["academic_background", "learning_behavior", "goal_motivation",
                     "cognitive_abilities", "emotional_state", "social_interaction",
                     "time_management", "creativity_innovation"]

        # activity_type → [8维权重向量]（对应 DIM_NAMES 顺序）
        TYPE_DIM_WEIGHTS = {
            "theory_answer":   [0.30, 0.05, 0.05, 0.40, 0.05, 0.00, 0.05, 0.10],
            "practice_submit": [0.05, 0.35, 0.05, 0.15, 0.10, 0.00, 0.25, 0.05],
            "video_watch":     [0.50, 0.05, 0.05, 0.10, 0.05, 0.00, 0.05, 0.20],
        }
        # fallback：找不到匹配类型就用均匀分布
        FALLBACK_WEIGHTS = [0.125]*8

        try:
            batch = history[batch_idx:]
            if not batch:
                return

            profile = twin_data["profile"]

            # ==================================================================
            # Phase 0: 保持原有的知识点掌握度更新
            # ==================================================================
            km = profile.setdefault("knowledge_mastery", {})
            kp_stats = {}
            match_scores = []
            for r in batch:
                match_scores.append(r.get("match_degree", 0.5))
                kp_name = r.get("knowledge_point", "")
                if kp_name:
                    if kp_name not in kp_stats:
                        kp_stats[kp_name] = {"count": 0, "uw_tr": 0, "ur_tw": 0}
                    kp_stats[kp_name]["count"] += 1
                    if r.get("result_type") == ComparisonResult.USER_WRONG_TWIN_RIGHT:
                        kp_stats[kp_name]["uw_tr"] += 1
                    elif r.get("result_type") == ComparisonResult.USER_RIGHT_TWIN_WRONG:
                        kp_stats[kp_name]["ur_tw"] += 1

            adjustments = []
            for kp_name, stats in kp_stats.items():
                current = km.get(kp_name, 0.3)
                uw_tr_pct = stats["uw_tr"] / stats["count"] if stats["count"] else 0
                ur_tw_pct = stats["ur_tw"] / stats["count"] if stats["count"] else 0
                if uw_tr_pct > 0.6:
                    new_val = max(0.05, current - 0.15)
                    adjustments.append((kp_name, current, round(new_val, 3), "下调(盲区)", uw_tr_pct))
                elif ur_tw_pct > 0.6:
                    new_val = min(1.0, current + 0.12)
                    adjustments.append((kp_name, current, round(new_val, 3), "上调(校准)", ur_tw_pct))
                else:
                    net = ur_tw_pct - uw_tr_pct
                    if abs(net) > 0.3:
                        delta = round(net * 0.10, 3)
                        new_val = max(0.05, min(1.0, current + delta))
                        adjustments.append((kp_name, current, round(new_val, 3),
                                            f"微调({'上调' if delta>0 else '下调'})", net))
                if adjustments and adjustments[-1][0] == kp_name:
                    km[kp_name] = adjustments[-1][2]

            # ==================================================================
            # Phase 1: 更新 8 维特征 dimension_scores
            # ==================================================================
            # 按 activity_type 聚合批次信号
            type_signals = {}  # type -> {"records": [], "weights_used": []}
            for r in batch:
                atype = r.get("activity_type", "theory_answer")
                if atype not in type_signals:
                    weights = TYPE_DIM_WEIGHTS.get(atype, FALLBACK_WEIGHTS)
                    type_signals[atype] = {"records": [], "weights": weights}
                type_signals[atype]["records"].append(r)

            # 计算每个维度的净信号
            dim_net_signals = [0.0] * 8       # 净信号值
            dim_possible = [0.0] * 8          # 可能的最大信号值
            dim_avg_difficulty = [0.0] * 8    # 难度加权

            for atype, info in type_signals.items():
                recs = info["records"]
                weights = info["weights"]
                for r in recs:
                    rt = r.get("result_type", "")
                    diff = float(r.get("difficulty", 0.5))
                    for d in range(8):
                        w = weights[d]
                        if w == 0:
                            continue
                        dim_possible[d] += abs(w)
                        dim_avg_difficulty[d] += diff * abs(w)
                        if rt == ComparisonResult.USER_RIGHT_TWIN_WRONG:
                            dim_net_signals[d] += w      # 低估 → 正向
                        elif rt == ComparisonResult.USER_WRONG_TWIN_RIGHT:
                            dim_net_signals[d] -= w      # 高估 → 负向
                        # both_correct / both_wrong → 不变

            # 计算各个维度的 signal_ratio，并应用阈值决定调整幅度
            dim_scores_old = profile.get("dimension_scores", [50]*8)
            if len(dim_scores_old) != 8:
                dim_scores_old = [50]*8

            dim_scores_new = list(dim_scores_old)
            dim_detail = []  # 记录每维调整详情

            for d in range(8):
                possible = dim_possible[d]
                if possible == 0:
                    dim_detail.append((DIM_NAMES[d], dim_scores_old[d], dim_scores_old[d], "无关联", 0))
                    continue

                # 难度调节因子
                avg_diff = dim_avg_difficulty[d] / possible
                if avg_diff > 0.6:
                    diff_factor = 1.3
                elif avg_diff < 0.4:
                    diff_factor = 0.8
                else:
                    diff_factor = 1.0

                signal_ratio = dim_net_signals[d] / possible
                # 阈值判定
                if signal_ratio > 0.5:
                    delta = 4.0 * diff_factor
                    tag = "显著低估"
                elif signal_ratio > 0.3:
                    delta = 2.0 * diff_factor
                    tag = "轻度低估"
                elif signal_ratio < -0.5:
                    delta = -4.0 * diff_factor
                    tag = "显著高估"
                elif signal_ratio < -0.3:
                    delta = -2.0 * diff_factor
                    tag = "轻度高估"
                else:
                    delta = 0.0
                    tag = "无偏差"

                new_val = max(10, min(100, dim_scores_old[d] + delta))
                dim_scores_new[d] = round(new_val, 1)
                dim_detail.append((DIM_NAMES[d], dim_scores_old[d], new_val, tag, round(signal_ratio, 3)))

            profile["dimension_scores"] = dim_scores_new

            # ==================================================================
            # Phase 2: 级联更新 overall_score
            # ==================================================================
            profile["overall_score"] = round(sum(dim_scores_new) / 8, 1)

            # ==================================================================
            # Phase 3: 级联更新 ability_weights
            # ==================================================================
            # 从维度重算
            d0, d1, d2, d3, d4, d5, d6, d7 = dim_scores_new
            new_weights = {
                "logical_thinking": round((d3 * 0.4 + d7 * 0.6) / 100, 3),
                "memory":           round(d0 / 100, 3),
                "comprehension":    round((d0 * 0.3 + d3 * 0.7) / 100, 3),
                "application":      round((d1 * 0.3 + d6 * 0.7) / 100, 3),
                "creativity":       round(d7 / 100, 3),
            }
            # clamp to [0.1, 1.0]
            for k in new_weights:
                new_weights[k] = max(0.1, min(1.0, new_weights[k]))
            profile["ability_weights"] = new_weights

            # ==================================================================
            # Phase 4: 级联更新 BKT 参数
            # ==================================================================
            # 从情绪维度和认知维度估算
            emotion_score = dim_scores_new[4]  # emotional_state 0~100
            cognitive_score = dim_scores_new[3]  # cognitive_abilities 0~100
            # 高情绪（自信）→ 高 P(G)；低情绪（焦虑）→ 高 P(S)
            confidence_factor = emotion_score / 100.0
            anxiety_factor = 1.0 - emotion_score / 100.0
            profile["guess_probability"] = round(max(0.02, min(0.40, 0.05 + 0.20 * confidence_factor)), 3)
            profile["slip_probability"] = round(max(0.02, min(0.40, 0.05 + 0.20 * anxiety_factor)), 3)

            # ==================================================================
            # Phase 5: 级联更新 error_patterns
            # ==================================================================
            total_batch = len(batch)
            uw_tr_count = sum(1 for r in batch if r.get("result_type") == ComparisonResult.USER_WRONG_TWIN_RIGHT)
            ur_tw_count = sum(1 for r in batch if r.get("result_type") == ComparisonResult.USER_RIGHT_TWIN_WRONG)
            both_wrong_count = sum(1 for r in batch if r.get("result_type") == ComparisonResult.BOTH_WRONG)
            both_correct_count = sum(1 for r in batch if r.get("result_type") == ComparisonResult.BOTH_CORRECT)

            old_patterns = profile.get("error_patterns", {})
            new_patterns = {
                "concept_confusion": round(
                    (uw_tr_count / total_batch if total_batch else 0) * 0.5 +
                    old_patterns.get("concept_confusion", 0.25) * 0.5, 3
                ),
                "careless_mistake": round(
                    (ur_tw_count / total_batch if total_batch else 0) * 0.6 +
                    old_patterns.get("careless_mistake", 0.25) * 0.4, 3
                ),
                "incomplete_knowledge": round(
                    (both_wrong_count / total_batch if total_batch else 0) * 0.4 +
                    old_patterns.get("incomplete_knowledge", 0.25) * 0.6, 3
                ),
                "misunderstanding": round(
                    (both_correct_count / total_batch if total_batch else 0) * 0.3 +
                    old_patterns.get("misunderstanding", 0.25) * 0.7, 3
                ),
            }
            # 归一化到 [0, 1] 且总和 = 1
            total_w = sum(new_patterns.values()) or 1.0
            for k in new_patterns:
                new_patterns[k] = round(new_patterns[k] / total_w, 3)
            profile["error_patterns"] = new_patterns

            # ==================================================================
            # Phase 6: 更新 confidence_factor
            # ==================================================================
            avg_match = sum(match_scores) / len(match_scores) if match_scores else 0.5
            old_confidence = profile.get("confidence_factor", 0.7)
            if avg_match < 0.4:
                new_confidence = max(0.3, old_confidence - 0.05)
            elif avg_match > 0.8:
                new_confidence = min(1.0, old_confidence + 0.03)
            else:
                new_confidence = old_confidence
            profile["confidence_factor"] = round(new_confidence, 3)

            # ==================================================================
            # Phase 7: 更新批次标记
            # ==================================================================
            twin_data["last_batch_update_index"] = len(history)
            twin_data["last_batch_update_at"] = datetime.now().isoformat()
            twin_data["last_batch_adjustments"] = adjustments
            twin_data["last_batch_dim_adjustments"] = dim_detail

            _save_twin_data(user_id, twin_data)

        except Exception as e:
            import traceback
            traceback.print_exc()

    async def get_comparison_stats_async(self, user_id: str) -> Dict[str, Any]:
        """异步获取对比统计"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_TWIN_EXECUTOR, self.get_comparison_stats, user_id)

    async def get_comparison_history_async(self, user_id: str, limit: int = 50,
                                            result_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """异步获取对比历史"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _TWIN_EXECUTOR, self.get_comparison_history, user_id, limit, result_type
        )

    async def clear_history_async(self, user_id: str) -> Dict[str, Any]:
        """异步清空对比历史"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_TWIN_EXECUTOR, self.clear_history, user_id)

    async def get_writing_hints_async(self, user_id: str, knowledge_points: List[str],
                                       code_snippet: str = "") -> Dict[str, Any]:
        """异步获取孪生编程提醒（含 LLM 实时代码分析）"""
        loop = asyncio.get_running_loop()

        # 同步部分：加载孪生画像 + 静态薄弱点提醒
        def _load_hints():
            return self.get_writing_hints(user_id, knowledge_points, "")

        result = await loop.run_in_executor(_TWIN_EXECUTOR, _load_hints)

        # 异步部分：如有代码且有薄弱点，调用 LLM 做语义分析
        if code_snippet.strip() and result.get("hints"):
            weak_info = [h for h in result["hints"] if h["type"] == "weakness"]
            if weak_info:
                print(f"🔍 [孪生编码] 代码长度={len(code_snippet)}, 薄弱点={len(weak_info)}个, 调用LLM分析...")
                llm_hints = await self._detect_code_with_llm_async(
                    code_snippet, weak_info,
                    result.get("profile_summary", {}).get("error_patterns", {})
                )
                print(f"📦 [孪生编码] LLM返回 {len(llm_hints)} 条代码提示")
                result["hints"].extend(llm_hints)
            else:
                print("⏭️ [孪生编码] 无薄弱点，跳过LLM分析")


        return result

    async def _detect_code_with_llm_async(self, code: str, weak_hints: List[Dict],
                                           error_patterns: Dict[str, float]) -> List[Dict]:
        """用 LLM 分析代码，针对用户薄弱点生成提醒"""
        if not code.strip():
            return []

        # 构建薄弱点描述
        weak_desc = "\n".join(
            f"- {h['knowledge_point']}（掌握度 {h['mastery_pct']}%）" for h in weak_hints
        )
        error_desc = ""
        if error_patterns:
            top = max(error_patterns, key=error_patterns.get)
            error_desc = f"\n- 用户常见错误模式：{top}（权重 {error_patterns[top]:.0%})"

        prompt = f"""你是一位AI数字孪生编程导师，很了解这位用户的薄弱点。

## 用户的薄弱知识点
{weak_desc}{error_desc}

## 用户当前编写的代码
```python
{code}
```

## 任务
请作为资深代码审查专家，全面分析这段代码。
检查范围包括：
1. 语法错误、拼写错误
2. 逻辑bug、边界条件遗漏
3. 潜在的运行时错误（如空指针、除零、越界）
4. 特别关注与用户薄弱知识点相关的问题（但不仅限于此）

要求：
1. 每条提醒必须具体到代码行，指出问题行号和具体改进建议
2. 语气友善、有建设性
3. 优先报告严重问题（warning），其次是一般建议（info）
4. **有明确的错误或问题才输出提醒，代码无明显问题则返回空列表**
5. 最多输出 3 条提醒

## 输出格式
请严格按以下 JSON 格式输出，不要加其他内容：
[
  {{"line": <行号>, "severity": "warning/info", "tip": "问题描述及改进建议"}}
]

行号从 1 开始。
如果完全没有任何问题或建议，输出 []"""

        try:
            from utils.llm_config import get_chat_openai
            from utils.async_llm_caller import call_llm_with_retry

            llm = get_chat_openai(temperature=0.3, max_tokens=800)
            response = await call_llm_with_retry(llm=llm, prompt=prompt, max_retries=1, error_msg="代码分析失败")

            text = ""
            if response and hasattr(response, 'content'):
                text = response.content.strip()
            elif response and isinstance(response, str):
                text = response.strip()

            if not text:
                return []

            # 解析 JSON
            import json as _json
            start = text.find('[')
            end = text.rfind(']')
            if start != -1 and end > start:
                text = text[start:end + 1]
                parsed = _json.loads(text)
                if isinstance(parsed, list):
                    result = []
                    for item in parsed:
                        if isinstance(item, dict) and item.get("tip"):
                            tip = item.get("tip", "")
                            # 优先使用结构化 line 字段
                            line = item.get("line", 0)
                            if not line or line < 1:
                                # 后备：从 tip 文本中提取 "第N行" 或 "line N" 或 "L5"
                                import re as _re
                                m = _re.search(r'第\s*(\d+)\s*行|line\s*(\d+)|[Ll](\d+)', tip)
                                if m:
                                    for g in m.groups():
                                        if g:
                                            line = int(g)
                                            break
                            result.append({
                                "type": "code_pattern",
                                "severity": item.get("severity", "info"),
                                "line": line if line else 1,
                                "tip": tip,
                            })
                    return result
        except Exception:
            pass

        return []

    # ==================== 孪生编码提醒 ====================

    def get_writing_hints(self, user_id: str, knowledge_points: List[str],
                           code_snippet: str = "") -> Dict[str, Any]:
        """基于孪生画像获取编程提醒（含实时代码模式检测）

        - 静态提醒：基于薄弱知识点的编码注意事项
        - 动态检测：分析当前代码中与薄弱点相关的模式
        - 错误模式：基于历史错误类型的通用提醒
        """
        twin_data = _load_twin_data(user_id)
        if not twin_data or not twin_data.get("enabled", False):
            return {"hints": [], "user_id": user_id, "twin_enabled": False}

        profile = twin_data.get("profile", {})
        km = profile.get("knowledge_mastery", {})
        error_patterns = profile.get("error_patterns", {})
        hints = []

        # ---- 1. 静态薄弱知识点提醒 ----
        for kp in knowledge_points:
            if not kp:
                continue
            # 模糊匹配知识点
            matched_kps = [(name, val) for name, val in km.items()
                           if kp.lower() in name.lower() or name.lower() in kp.lower()]
            if not matched_kps:
                continue
            for name, mastery in matched_kps:
                if mastery is None or mastery >= 0.5:
                    continue
                hints.append({
                    "type": "weakness",
                    "knowledge_point": name,
                    "mastery_pct": int(mastery * 100),
                    "severity": "high" if mastery < 0.2 else "medium",
                    "tip": self._gen_kp_tip(name, mastery),
                    "watch_keywords": self._get_kp_keywords(name),
                })

        # ---- 2. 实时代码模式检测 ----
        if code_snippet.strip():
            weak_kps = {h["knowledge_point"]: h["mastery_pct"]
                        for h in hints if h["type"] == "weakness"}
            code_hints = self._detect_code_patterns(code_snippet, weak_kps)
            hints.extend(code_hints)

        # ---- 3. 通用错误模式提醒（取 top-1）----
        if error_patterns:
            top_pattern = max(error_patterns, key=error_patterns.get)
            top_score = error_patterns[top_pattern]
            if top_score > 0.2:
                hints.append({
                    "type": "error_pattern",
                    "pattern": top_pattern,
                    "severity": "medium",
                    "tip": self._get_error_tip(top_pattern),
                })

        return {"hints": hints, "user_id": user_id, "twin_enabled": True}

    def _gen_kp_tip(self, kp: str, mastery: float) -> str:
        """生成知识点针对性提醒"""
        kp_lower = kp.lower()
        if "循环" in kp_lower or "for" in kp_lower or "while" in kp_lower:
            return "你在「{}」掌握度仅{}%，注意：①循环边界条件 ②循环变量初始化与步进 ③避免死循环".format(kp, int(mastery * 100))
        if "递归" in kp_lower:
            return "你在「{}」掌握度仅{}%，注意：①递归终止条件(base case) ②递归深度(防栈溢出) ③返回值传递".format(kp, int(mastery * 100))
        if "数组" in kp_lower or "列表" in kp_lower or "索引" in kp_lower:
            return "你在「{}」掌握度仅{}%，注意：①索引范围(0~len-1) ②避免IndexError ③列表推导式简化代码".format(kp, int(mastery * 100))
        if "排序" in kp_lower:
            return "你在「{}」掌握度仅{}%，注意：①比较逻辑是否正确 ②稳定性考虑 ③时间复杂度".format(kp, int(mastery * 100))
        if "字符串" in kp_lower:
            return "你在「{}」掌握度仅{}%，注意：①字符串不可变性 ②切片边界 ③转义字符".format(kp, int(mastery * 100))
        return "你在「{}」掌握度仅{}%，建议编码时仔细处理相关逻辑".format(kp, int(mastery * 100))

    def _get_kp_keywords(self, kp: str) -> List[str]:
        """返回该知识点相关的代码关键词（用于前端实时监测触发）"""
        kp_lower = kp.lower()
        if "循环" in kp_lower:
            return ["for", "while", "range"]
        if "递归" in kp_lower:
            return ["def", "return"]
        if "数组" in kp_lower or "列表" in kp_lower:
            return ["[", "]", "list", "array", "索引"]
        if "条件" in kp_lower or "判断" in kp_lower:
            return ["if", "elif", "else", "switch"]
        if "排序" in kp_lower:
            return ["sort", "sorted", "冒泡", "快速"]
        return []

    def _detect_code_patterns(self, code: str, weak_kps: Dict[str, int]) -> List[Dict]:
        """实时分析代码，检测与用户薄弱点相关的潜在问题"""
        hints = []
        code_lower = code.lower()
        lines = code.splitlines()

        # 检测循环相关
        is_loop_weak = any("循环" in kp for kp in weak_kps)
        if is_loop_weak:
            # while True 无 break
            if "while true" in code_lower and "break" not in code_lower:
                hints.append({
                    "type": "code_pattern",
                    "severity": "warning",
                    "tip": "⚠️ while True 缺少 break 语句，可能导致死循环",
                })
            # 在循环内修改迭代变量
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("for ") and " in " in stripped:
                    var = stripped.split()[1]
                    for body_line in lines[lines.index(line) + 1:]:
                        if body_line.strip().startswith(var + " ") or body_line.strip().startswith(var + "="):
                            hints.append({
                                "type": "code_pattern",
                                "severity": "warning",
                                "tip": "⚠️ 不要在循环体内修改循环变量 '{}'，可能导致意外行为".format(var),
                            })
                            break
                    break

        # 检测递归相关
        is_recursion_weak = any("递归" in kp for kp in weak_kps)
        if is_recursion_weak:
            func_defs = re.findall(r'def\s+(\w+)\s*\(', code)
            for name in func_defs:
                if name in code_lower and "return" not in code_lower:
                    hints.append({
                        "type": "code_pattern",
                        "severity": "warning",
                        "tip": "⚠️ 递归函数 '{}' 需要明确的终止条件(base case)和 return 语句".format(name),
                    })
                    break

        # 检测数组越界相关
        is_array_weak = any("数组" in kp or "列表" in kp for kp in weak_kps)
        if is_array_weak and ("[" in code and "]" in code):
            # 检测 len(x)-1 模式的索引访问
            idx_patterns = re.findall(r'\[(\w+)\s*[-+]\s*\d+\]', code)
            if idx_patterns:
                for idx_var in idx_patterns:
                    if idx_var.isdigit():
                        continue
                    hints.append({
                        "type": "code_pattern",
                        "severity": "info",
                        "tip": "💡 列表索引 '{}' 注意不要越界，确保范围在 0~len(list)-1 之间".format(idx_var),
                    })

        return hints

    def _get_error_tip(self, pattern: str) -> str:
        tips = {
            "concept_confusion": "你容易混淆相似概念，建议编码时多参考官方文档确认 API 用法",
            "careless_mistake": "你容易犯粗心错误（拼写/缩进/括号），提交前建议逐行检查",
            "incomplete_knowledge": "你有部分知识盲区，遇到不确定的库函数建议先查阅资料",
            "misunderstanding": "你偶会理解错题意，建议先读题 2 遍再动手编码",
        }
        return tips.get(pattern, "你的常见错误模式是「{}」，编程时请特别留意".format(pattern))


# ==================== 全局单例 ====================

# 诊断消息生成（模块级函数，供所有记录方法共用）
_DIAGNOSIS_TEMPLATES = {
    ComparisonResult.BOTH_CORRECT: "用户和孪生都答对了，该知识点掌握一致",
    ComparisonResult.BOTH_WRONG: "用户和孪生都答错了，题目难度偏高或双方都不擅长此知识点",
    ComparisonResult.USER_RIGHT_TWIN_WRONG: "孪生答错了但对孪生知识模型来说有难度",
    ComparisonResult.USER_WRONG_TWIN_RIGHT: "孪生答对了但孪生知识模型掌握较好",
}

def _generate_diagnosis(result_type: str, knowledge_point: str, difficulty: float,
                        profile: Dict, twin_confidence: float,
                        twin_reasoning: str = "") -> str:
    """根据对比结果生成诊断说明"""
    base = _DIAGNOSIS_TEMPLATES.get(result_type, "")
    parts = [base]

    if knowledge_point:
        # 查孪生对该知识点的掌握度
        km = profile.get("knowledge_mastery", {})
        mastery_val = km.get(knowledge_point)
        if mastery_val is not None:
            pct = int(mastery_val * 100)
            if pct >= 80:
                parts.append(f"孪生掌握度较高({pct}%)")
            elif pct >= 50:
                parts.append(f"孪生掌握度一般({pct}%)")
            else:
                parts.append(f"孪生掌握度较低({pct}%)")

    if twin_reasoning:
        parts.append(f"孪生思路：{twin_reasoning}")

    return "，".join(parts)


_digital_twin_service = None

def get_digital_twin_service() -> DigitalTwinService:
    """获取数字孪生服务全局实例"""
    global _digital_twin_service
    if _digital_twin_service is None:
        _digital_twin_service = DigitalTwinService()
    return _digital_twin_service

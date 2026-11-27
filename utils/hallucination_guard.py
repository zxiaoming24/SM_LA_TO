"""
防幻觉机制模块 - Hallucination Guard

功能：
1. 事实一致性校验 - 验证LLM输出是否与参考文档一致
2. 内容安全过滤 - 检测并过滤不当、敏感内容
3. 输出格式验证 - 验证JSON等结构化输出的正确性
4. 置信度评估 - 评估LLM输出的可信度
5. 引用追踪 - 追踪回答中信息的来源

设计原则：
- 多层防御：在不同阶段进行不同维度的检查
- 可配置：支持调整校验严格程度
- 可扩展：支持添加新的校验规则
- 低延迟：避免过多的LLM调用
"""

import re
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from pathlib import Path


class ConfidenceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"


class HallucinationResult:
    """防幻觉检查结果"""
    
    def __init__(self):
        self.passed = True
        self.confidence = ConfidenceLevel.UNKNOWN
        self.safety = SafetyLevel.SAFE
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.facts_verified = 0
        self.facts_confirmed = 0
        self.references: List[Dict] = []
        self.corrected_output: Optional[str] = None
    
    @property
    def fact_accuracy(self) -> float:
        if self.facts_verified == 0:
            return 0.0
        return round(self.facts_confirmed / self.facts_verified, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "confidence": self.confidence.value,
            "safety": self.safety.value,
            "warnings": self.warnings,
            "errors": self.errors,
            "facts_verified": self.facts_verified,
            "facts_confirmed": self.facts_confirmed,
            "fact_accuracy": self.fact_accuracy,
            "references": self.references,
            "corrected_output": self.corrected_output
        }


class HallucinationGuard:
    """防幻觉守卫 - 核心防幻觉组件"""
    
    def __init__(self, strict_mode: bool = False, llm_client=None):
        """
        初始化防幻觉守卫
        
        Args:
            strict_mode: 严格模式，更严格的校验规则
            llm_client: LLM客户端，用于事实校验
        """
        self.strict_mode = strict_mode
        self.llm_client = llm_client
        
        self._sensitive_patterns = [
            r'(?:黑客|破解|入侵|攻击|病毒|木马|钓鱼|诈骗)',
            r'(?:色情|淫秽|低俗|裸体)',
            r'(?:暴力|血腥|恐怖|杀人|自杀)',
            r'(?:毒品|赌博|洗钱|走私)',
            r'(?:政治敏感|反政府|分裂|台独|藏独)',
            r'(?:歧视|仇恨|种族|性别歧视)',
            r'(?:枪支|弹药|爆炸物|管制)',
            r'(?:隐私|身份证|银行卡|密码|手机号)',
            r'(?:诈骗|传销|非法集资)',
        ]
        
        self._warning_patterns = [
            r'(?:可能|也许|大概|估计|应该)',
            r'(?:据说|听说|有人说)',
            r'(?:不确定|不太清楚|可能是)',
        ]
        
        self._max_facts_to_verify = 5
    
    def _extract_facts(self, text: str) -> List[str]:
        """
        从文本中提取事实陈述
        
        Args:
            text: LLM输出文本
            
        Returns:
            事实陈述列表
        """
        facts = []
        
        sentences = re.split(r'[。！？；\n]', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue
            
            if re.search(r'(?:是|有|包括|可以|能够|应该|必须|将会|已经)', sentence):
                facts.append(sentence)
        
        return facts[:self._max_facts_to_verify]
    
    def _find_reference(self, fact: str, context: str) -> Optional[str]:
        """
        在上下文中查找事实的引用来源
        
        Args:
            fact: 事实陈述
            context: 参考文档上下文
            
        Returns:
            引用来源片段，如果找不到返回None
        """
        fact_tokens = [t for t in fact[:30] if t.strip()]
        
        for i, paragraph in enumerate(context.split('\n\n')):
            if any(token in paragraph for token in fact_tokens):
                return paragraph[:200]
        
        return None
    
    async def _verify_fact_with_llm(self, fact: str, context: str) -> Tuple[bool, float, str]:
        """
        使用LLM验证事实一致性
        
        Args:
            fact: 待验证的事实
            context: 参考文档
            
        Returns:
            (是否一致, 置信度, 原因)
        """
        if not self.llm_client:
            return True, 0.5, "LLM客户端未配置，跳过验证"
        
        prompt = f"""请判断以下事实陈述是否与参考文档内容一致。
        
【参考文档】
{context[:2000]}

【待验证事实】
{fact}

【判断要求】
1. 如果事实与参考文档内容一致或可以合理推断，返回 YES
2. 如果事实与参考文档内容矛盾或无法从文档中找到支持，返回 NO
3. 如果不确定，返回 UNKNOWN

请直接返回 YES/NO/UNKNOWN，不要添加其他内容。"""
        
        try:
            response = await self.llm_client.ainvoke([{"role": "user", "content": prompt}])
            result = response.content.strip().upper() if hasattr(response, 'content') else str(response).strip().upper()
            
            if result == "YES":
                return True, 0.85, "事实与参考文档一致"
            elif result == "NO":
                return False, 0.9, "事实与参考文档矛盾"
            else:
                return True, 0.3, "无法确定事实准确性"
        except Exception as e:
            return True, 0.2, f"验证失败: {str(e)}"
    
    def _check_safety(self, text: str) -> Tuple[SafetyLevel, List[str]]:
        """
        内容安全检查
        
        Args:
            text: 待检查文本
            
        Returns:
            (安全等级, 违规内容列表)
        """
        violations = []
        
        for pattern in self._sensitive_patterns:
            matches = re.findall(pattern, text)
            if matches:
                violations.extend(matches)
        
        if len(violations) >= 2:
            return SafetyLevel.DANGER, violations
        elif len(violations) == 1:
            return SafetyLevel.WARNING, violations
        else:
            return SafetyLevel.SAFE, []
    
    def _check_json_format(self, text: str) -> Tuple[bool, Optional[Dict]]:
        """
        检查JSON格式是否正确
        
        Args:
            text: 待检查文本
            
        Returns:
            (是否有效, 解析后的JSON)
        """
        try:
            json_text = re.search(r'\{[\s\S]*\}', text)
            if json_text:
                data = json.loads(json_text.group())
                return True, data
            else:
                return False, None
        except json.JSONDecodeError as e:
            return False, None
    
    def _evaluate_confidence(self, text: str, facts_confirmed: int, facts_total: int) -> ConfidenceLevel:
        """
        评估置信度
        
        Args:
            text: LLM输出文本
            facts_confirmed: 已确认的事实数量
            facts_total: 总事实数量
            
        Returns:
            置信度等级
        """
        if facts_total == 0:
            warning_count = len(re.findall(r'|'.join(self._warning_patterns), text))
            if warning_count >= 3:
                return ConfidenceLevel.LOW
            elif warning_count >= 1:
                return ConfidenceLevel.MEDIUM
            else:
                return ConfidenceLevel.HIGH
        
        accuracy = facts_confirmed / facts_total
        
        if accuracy >= 0.8:
            return ConfidenceLevel.HIGH
        elif accuracy >= 0.5:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def _mask_sensitive_content(self, text: str) -> str:
        """
        脱敏处理敏感内容
        
        Args:
            text: 原始文本
            
        Returns:
            脱敏后的文本
        """
        masked = text
        
        masked = re.sub(r'\d{11}', '***-****-****', masked)
        
        masked = re.sub(r'\d{18}', '******************', masked)
        
        masked = re.sub(r'\d{4}[\s*-]?\d{4}[\s*-]?\d{4}[\s*-]?\d{4}', '****-****-****-****', masked)
        
        for pattern in self._sensitive_patterns:
            masked = re.sub(pattern, '[内容已过滤]', masked)
        
        return masked
    
    async def check(self, output: str, context: str = "", expected_format: str = "") -> HallucinationResult:
        """
        执行完整的防幻觉检查
        
        Args:
            output: LLM输出文本
            context: 参考文档上下文（用于事实校验）
            expected_format: 期望的输出格式（如 "json", "text"）
            
        Returns:
            检查结果
        """
        result = HallucinationResult()
        
        if not output:
            result.passed = False
            result.errors.append("输出为空")
            return result
        
        safety_level, violations = self._check_safety(output)
        result.safety = safety_level
        
        if safety_level == SafetyLevel.DANGER:
            result.passed = False
            result.errors.append(f"检测到危险内容: {', '.join(violations)}")
            result.corrected_output = self._mask_sensitive_content(output)
            return result
        
        if safety_level == SafetyLevel.WARNING:
            result.warnings.append(f"检测到警告内容: {', '.join(violations)}")
            result.corrected_output = self._mask_sensitive_content(output)
        
        if expected_format.lower() == "json":
            is_valid, parsed = self._check_json_format(output)
            if not is_valid:
                result.passed = False
                result.errors.append("JSON格式无效")
                return result
        
        if context:
            facts = self._extract_facts(output)
            result.facts_verified = len(facts)
            
            for fact in facts:
                reference = self._find_reference(fact, context)
                if reference:
                    is_consistent, conf_score, reason = await self._verify_fact_with_llm(fact, context)
                    
                    result.references.append({
                        "fact": fact[:50],
                        "consistent": is_consistent,
                        "confidence": conf_score,
                        "reason": reason
                    })
                    
                    if is_consistent:
                        result.facts_confirmed += 1
                    else:
                        result.warnings.append(f"事实不一致: {fact[:50]}")
        
        result.confidence = self._evaluate_confidence(output, result.facts_confirmed, result.facts_verified)
        
        if result.confidence == ConfidenceLevel.LOW and self.strict_mode:
            result.passed = False
            result.errors.append("输出置信度过低")
        
        return result
    
    async def validate_and_correct(self, output: str, context: str = "", 
                                   expected_format: str = "") -> Tuple[str, HallucinationResult]:
        """
        验证并修正输出
        
        Args:
            output: LLM输出文本
            context: 参考文档上下文
            expected_format: 期望的输出格式
            
        Returns:
            (修正后的输出, 检查结果)
        """
        result = await self.check(output, context, expected_format)
        
        if result.corrected_output:
            return result.corrected_output, result
        
        if not result.passed:
            error_summary = "; ".join(result.errors[:3])
            corrected = f"【警告】检测到以下问题：{error_summary}。请重新生成答案。"
            return corrected, result
        
        return output, result


class FactChecker:
    """事实校验器 - 独立的事实检查组件"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    async def verify_facts(self, statements: List[str], context: str) -> List[Dict[str, Any]]:
        """
        批量验证事实陈述
        
        Args:
            statements: 事实陈述列表
            context: 参考文档
            
        Returns:
            验证结果列表
        """
        results = []
        
        for statement in statements:
            is_consistent, confidence, reason = await self._verify_single_fact(statement, context)
            results.append({
                "statement": statement,
                "consistent": is_consistent,
                "confidence": confidence,
                "reason": reason
            })
        
        return results
    
    async def _verify_single_fact(self, statement: str, context: str) -> Tuple[bool, float, str]:
        """验证单个事实"""
        if not self.llm_client:
            return True, 0.5, "LLM客户端未配置"
        
        prompt = f"""请仔细对比以下事实陈述与参考文档内容。
        
【参考文档】
{context[:3000]}

【事实陈述】
{statement}

请判断：该陈述是否与参考文档一致？

回答格式：
一致/不一致/不确定
原因：简要说明理由"""
        
        try:
            response = await self.llm_client.ainvoke([{"role": "user", "content": prompt}])
            text = response.content if hasattr(response, 'content') else str(response)
            
            lines = text.split('\n')
            verdict = lines[0].strip() if lines else "不确定"
            reason = lines[1].replace("原因：", "").strip() if len(lines) > 1 else ""
            
            if verdict == "一致":
                return True, 0.85, reason
            elif verdict == "不一致":
                return False, 0.9, reason
            else:
                return True, 0.3, reason
        except Exception as e:
            return True, 0.2, f"验证失败: {str(e)}"


class ContentFilter:
    """内容过滤器 - 独立的内容安全检查组件"""
    
    def __init__(self, custom_patterns: List[str] = None):
        self._patterns = [
            (r'(?:黑客|破解|入侵|攻击|病毒|木马|钓鱼|诈骗)', '恶意行为'),
            (r'(?:色情|淫秽|低俗)', '色情内容'),
            (r'(?:暴力|血腥|恐怖|杀人|自杀)', '暴力内容'),
            (r'(?:毒品|赌博|洗钱)', '违法内容'),
            (r'(?:政治敏感|反政府|分裂)', '政治敏感'),
            (r'(?:歧视|仇恨)', '歧视内容'),
            (r'(?:枪支|弹药|爆炸物)', '危险物品'),
            (r'(?:身份证|银行卡|密码|手机号)', '隐私信息'),
        ]
        
        if custom_patterns:
            for pattern, category in custom_patterns:
                self._patterns.append((pattern, category))
    
    def filter(self, text: str) -> Tuple[str, List[Dict]]:
        """
        过滤文本中的敏感内容
        
        Args:
            text: 原始文本
            
        Returns:
            (过滤后的文本, 违规记录列表)
        """
        violations = []
        filtered_text = text
        
        for pattern, category in self._patterns:
            matches = re.findall(pattern, text)
            if matches:
                violations.append({
                    "category": category,
                    "matches": matches,
                    "count": len(matches)
                })
                filtered_text = re.sub(pattern, f'[{category}]', filtered_text)
        
        return filtered_text, violations
    
    def is_safe(self, text: str) -> bool:
        """检查文本是否安全"""
        _, violations = self.filter(text)
        return len(violations) == 0


class OutputValidator:
    """输出验证器 - 验证输出格式和完整性"""
    
    def validate_json(self, text: str, required_fields: List[str] = None) -> Tuple[bool, Optional[Dict], List[str]]:
        """
        验证JSON格式
        
        Args:
            text: 待验证文本
            required_fields: 必需字段列表
            
        Returns:
            (是否有效, 解析后的JSON, 错误列表)
        """
        errors = []
        
        try:
            json_text = re.search(r'\{[\s\S]*\}', text)
            if not json_text:
                errors.append("未找到JSON对象")
                return False, None, errors
            
            data = json.loads(json_text.group())
            
            if required_fields:
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    errors.append(f"缺少必需字段: {', '.join(missing_fields)}")
                    return False, data, errors
            
            return True, data, errors
        except json.JSONDecodeError as e:
            errors.append(f"JSON解析错误: {str(e)}")
            return False, None, errors
    
    def validate_structure(self, text: str, expected_keys: List[str]) -> Tuple[bool, List[str]]:
        """
        验证结构化输出
        
        Args:
            text: 待验证文本
            expected_keys: 期望的关键字列表
            
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        for key in expected_keys:
            if key not in text:
                errors.append(f"缺少关键字: {key}")
        
        return len(errors) == 0, errors


_hallucination_guard_instance = None


def get_hallucination_guard(strict_mode: bool = False, llm_client=None) -> HallucinationGuard:
    """获取防幻觉守卫实例（单例）"""
    global _hallucination_guard_instance
    
    if _hallucination_guard_instance is None:
        _hallucination_guard_instance = HallucinationGuard(strict_mode, llm_client)
    
    return _hallucination_guard_instance


def init_hallucination_guard(strict_mode: bool = False, llm_client=None):
    """初始化防幻觉守卫"""
    global _hallucination_guard_instance
    _hallucination_guard_instance = HallucinationGuard(strict_mode, llm_client)
    print(f"✅ 防幻觉守卫已初始化 (严格模式: {strict_mode})")
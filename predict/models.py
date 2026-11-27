"""
Pydantic 数据模型
用于API请求和响应的数据验证
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class CodeSubmissionRequest(BaseModel):
    """代码提交请求模型"""
    user_id: str = Field(..., description="用户ID", min_length=1)
    user_name: str = Field(..., description="用户姓名", min_length=1)
    problem_id: str = Field(..., description="题目ID", min_length=1)
    problem_title: Optional[str] = Field(None, description="题目标题")
    problem_data: Dict[str, Any] = Field(..., description="题目完整信息")
    code: str = Field(..., description="用户提交的代码", min_length=1)
    language: str = Field("python", description="编程语言")


class CodeSubmissionResponse(BaseModel):
    """代码提交响应模型"""
    submission_id: int = Field(..., description="提交记录ID")
    score: int = Field(..., description="得分")
    verdict: str = Field(..., description="评判结果")
    passed_tests: int = Field(..., description="通过的测试用例数")
    total_tests: int = Field(..., description="总测试用例数")
    message: str = Field("提交成功", description="响应消息")


class ComparisonRequest(BaseModel):
    """代码比较请求模型"""
    problem_data: Dict[str, Any] = Field(..., description="题目完整信息")
    submission_a_id: int = Field(..., description="用户A的提交ID")
    submission_b_id: int = Field(..., description="用户B的提交ID")


class UserInfo(BaseModel):
    """用户信息模型"""
    user_id: str = Field(..., description="用户ID")
    user_name: str = Field(..., description="用户姓名")
    score: int = Field(..., description="得分")
    verdict: str = Field(..., description="评判结果")


class AlgorithmComparison(BaseModel):
    """算法比较结果"""
    approach_a: str = Field(..., description="用户A的算法思路")
    approach_b: str = Field(..., description="用户B的算法思路")
    differences: List[str] = Field(..., description="差异点列表")
    better_approach: str = Field(..., description="更好的方案")
    reason: str = Field(..., description="判断理由")


class QualityMetric(BaseModel):
    """质量指标"""
    winner: str = Field(..., description="获胜者")
    analysis: str = Field(..., description="分析说明")


class CodeQualityComparison(BaseModel):
    """代码质量比较"""
    readability: QualityMetric = Field(..., description="可读性")
    maintainability: QualityMetric = Field(..., description="可维护性")
    conciseness: QualityMetric = Field(..., description="简洁性")


class EfficiencyComparison(BaseModel):
    """效率比较"""
    time_complexity_a: str = Field(..., description="用户A的时间复杂度")
    time_complexity_b: str = Field(..., description="用户B的时间复杂度")
    space_complexity_a: str = Field(..., description="用户A的空间复杂度")
    space_complexity_b: str = Field(..., description="用户B的空间复杂度")
    more_efficient: str = Field(..., description="更高效的方案")
    analysis: str = Field(..., description="详细分析")


class InnovationComparison(BaseModel):
    """创新性比较"""
    innovative_techniques_a: List[str] = Field(..., description="用户A的创新点")
    innovative_techniques_b: List[str] = Field(..., description="用户B的创新点")
    more_innovative: str = Field(..., description="更具创新性的方案")


class UserStrengthsWeaknesses(BaseModel):
    """用户优缺点"""
    strengths: List[str] = Field(..., description="优势列表")
    weaknesses: List[str] = Field(..., description="不足列表")


class StrengthsAndWeaknesses(BaseModel):
    """双方优缺点"""
    user_a: UserStrengthsWeaknesses = Field(..., description="用户A的优缺点")
    user_b: UserStrengthsWeaknesses = Field(..., description="用户B的优缺点")


class ImprovementSuggestions(BaseModel):
    """改进建议"""
    user_a: str = Field(..., description="给用户A的建议")
    user_b: str = Field(..., description="给用户B的建议")


class LearningRecommendations(BaseModel):
    """学习建议"""
    for_beginners: str = Field(..., description="对初学者的建议")
    key_takeaways: List[str] = Field(..., description="值得学习的要点")
    improvement_suggestions: ImprovementSuggestions = Field(..., description="改进建议")


class ComparisonResponse(BaseModel):
    """代码比较响应模型"""
    user_a: UserInfo = Field(..., description="用户A信息")
    user_b: UserInfo = Field(..., description="用户B信息")
    comparison_summary: str = Field(..., description="总体比较总结")
    algorithm_comparison: AlgorithmComparison = Field(..., description="算法比较")
    code_quality_comparison: CodeQualityComparison = Field(..., description="代码质量比较")
    efficiency_comparison: EfficiencyComparison = Field(..., description="效率比较")
    innovation_comparison: InnovationComparison = Field(..., description="创新性比较")
    strengths_and_weaknesses: StrengthsAndWeaknesses = Field(..., description="优缺点")
    learning_recommendations: LearningRecommendations = Field(..., description="学习建议")
    overall_winner: str = Field(..., description="总体获胜者")
    winner_reason: str = Field(..., description="获胜理由")
    encouragement: str = Field(..., description="鼓励话语")


class RankingItem(BaseModel):
    """排行榜项"""
    rank: int = Field(..., description="排名")
    user_id: str = Field(..., description="用户ID")
    user_name: str = Field(..., description="用户姓名")
    score: int = Field(..., description="得分")
    best_time: Optional[str] = Field(None, description="最佳提交时间")
    problem_id: str = Field(..., description="题目ID")


class RankingResponse(BaseModel):
    """排行榜响应模型"""
    problem_id: str = Field(..., description="题目ID")
    problem_title: Optional[str] = Field(None, description="题目标题")
    total_submissions: int = Field(..., description="总提交数")
    ranking: List[RankingItem] = Field(..., description="排行榜列表")


class UserSubmissionsResponse(BaseModel):
    """用户提交记录响应模型"""
    user_id: str = Field(..., description="用户ID")
    problem_id: str = Field(..., description="题目ID")
    submissions: List[Dict[str, Any]] = Field(..., description="提交记录列表")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细信息")

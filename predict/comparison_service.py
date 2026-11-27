"""
代码比较服务
调用 PracticeAgent 进行两个用户解法的深度比较分析
"""

import sys
import os
from typing import Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.children_agent.practice_agent import PracticeAgent
from services.leaderboard_service import LeaderboardService


class ComparisonService:
    """代码比较服务类"""
    
    def __init__(self):
        """初始化比较服务"""
        self.practice_agent = PracticeAgent()
        self.leaderboard_service = LeaderboardService()
    
    def compare_two_solutions(self, problem_data: Dict[str, Any], 
                              submission_a_id: int, 
                              submission_b_id: int) -> Dict[str, Any]:
        """
        比较两个用户的解题方案
        
        Args:
            problem_data: 题目完整信息
            submission_a_id: 用户A的提交ID
            submission_b_id: 用户B的提交ID
            
        Returns:
            Dict: 比较分析结果
        """
        try:
            print(f"\n🔍 [比较服务] 正在获取提交记录...")
            
            submission_a = self.leaderboard_service.get_submission_by_id(submission_a_id)
            submission_b = self.leaderboard_service.get_submission_by_id(submission_b_id)
            
            if not submission_a:
                raise ValueError(f"提交记录 {submission_a_id} 不存在")
            if not submission_b:
                raise ValueError(f"提交记录 {submission_b_id} 不存在")
            
            print(f"✅ 获取到两个提交记录:")
            print(f"   用户A: {submission_a['user_id']} (得分: {submission_a['score']})")
            print(f"   用户B: {submission_b['user_id']} (得分: {submission_b['score']})")
            
            solution_a = {
                'user_id': submission_a['user_id'],
                'code': submission_a['full_code'],
                'language': submission_a.get('language', 'python'),
                'score': submission_a['score'],
                'verdict': submission_a['verdict']
            }
            
            solution_b = {
                'user_id': submission_b['user_id'],
                'code': submission_b['full_code'],
                'language': submission_b.get('language', 'python'),
                'score': submission_b['score'],
                'verdict': submission_b['verdict']
            }
            
            print(f"\n🤖 [比较服务] 正在调用 PracticeAgent 进行比较分析...")
            comparison_result = self.practice_agent.compare_solutions(
                problem=problem_data,
                solution_a=solution_a,
                solution_b=solution_b
            )
            
            print(f"✅ 比较分析完成")
            
            return {
                'user_a': {
                    'user_id': submission_a['user_id'],
                   
                    'score': submission_a['score'],
                    'verdict': submission_a['verdict']
                },
                'user_b': {
                    'user_id': submission_b['user_id'],
                 
                    'score': submission_b['score'],
                    'verdict': submission_b['verdict']
                },
                'comparison': comparison_result
            }
            
        except ValueError as e:
            print(f"❌ 数据验证错误: {e}")
            raise
        except Exception as e:
            print(f"❌ 比较过程出错: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"比较失败: {str(e)}")
    
    def get_ranking_with_details(self, problem_id: str, 
                                  problem_title: str = None,
                                  limit: int = 50) -> Dict[str, Any]:
        """
        获取带详细信息的排行榜
        
        Args:
            problem_id: 题目ID
            problem_title: 题目标题（可选）
            limit: 返回的排名数量限制
            
        Returns:
            Dict: 排行榜数据
        """
        try:
            print(f"\n📊 [比较服务] 正在生成排行榜...")
            
            ranking = self.leaderboard_service.get_leaderboard(problem_id, limit)
            
            return {
                'problem_id': problem_id,
                'problem_title': problem_title,
                'total_submissions': ranking.get('total_submissions', 0),
                'ranking': ranking.get('top_submissions', [])
            }
            
        except Exception as e:
            print(f"❌ 生成排行榜失败: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"生成排行榜失败: {str(e)}")
    
    def get_user_submissions_detail(self, user_id: str, problem_id: str) -> Dict[str, Any]:
        """
        获取用户在某题目上的所有提交详情
        
        Args:
            user_id: 用户ID
            problem_id: 题目ID
            
        Returns:
            Dict: 用户提交记录列表
        """
        try:
            print(f"\n📋 [比较服务] 正在获取用户提交记录...")
            
            submissions = self.leaderboard_service.get_user_submissions(problem_id, user_id)
            
            print(f"✅ 获取到 {len(submissions.get('submissions', []))} 条提交记录")
            
            return submissions
            
        except Exception as e:
            print(f"❌ 获取用户提交记录失败: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"获取提交记录失败: {str(e)}")

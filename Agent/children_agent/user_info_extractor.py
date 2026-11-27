"""
用户信息抽取器 - 从自然语言对话中提取结构化用户信息（纯函数版本）
供主Agent调用
"""

import os
import json
import re
from typing import Dict, Any, Optional, List
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai


# 全局LLM实例（懒加载）
_llm_instance = None
_extraction_template = None


def _get_llm():
    """获取LLM实例（单例模式，使用统一配置）"""
    global _llm_instance
    if _llm_instance is None:
        try:
            _llm_instance = get_chat_openai(temperature=0.3, max_tokens=1500)
        except Exception as e:
            raise Exception(f"初始化LLM失败: {e}")
    return _llm_instance


def _get_extraction_template() -> PromptTemplate:
    """创建信息抽取的提示词模板（懒加载）"""
    global _extraction_template
    if _extraction_template is None:
        template = """你是一位专业的用户信息抽取专家，负责从用户的自然语言描述中提取结构化的个人信息。

**任务说明：**
分析用户的输入，提取以下信息字段。如果某个字段在用户输入中没有提到，请根据上下文合理推断，如果无法推断则标记为"未知"。

**需要提取的字段：**

1. **基本信息**
   - name (姓名): 用户的名字
   - major (专业): 用户的专业
   - grade (年级): 用户的年级（如：大一、大二、大三、大四、研一等）

2. **学习目标**
   - learning_goal (学习目标): 用户的学习目标或期望

3. **学习历史**
   - learning_history (学习历史): 用户提到的课程学习经历，包括：
     - 课程名称
     - 成绩（如果有提到）
     - 学习方式（如果有提到）

4. **学习习惯**
   - learning_habits (学习习惯): 用户的学习习惯描述

**输出格式（严格的JSON格式）：**
```json
{{
  "name": "string",
  "major": "string",
  "grade": "string",
  "learning_goal": "string",
  "learning_history": [
    {{
      "课程": "string",
      "成绩": number 或 null,
      "学习方式": "string"
    }}
  ],
  "learning_habits": "string",
  "confidence_scores": {{
    "name": 0-100,
    "major": 0-100,
    "grade": 0-100,
    "learning_goal": 0-100,
    "learning_history": 0-100,
    "learning_habits": 0-100
  }},
  "missing_fields": ["未提取到的字段列表"],
  "follow_up_questions": ["需要进一步询问的问题列表"]
}}
```

**抽取原则：**
1. 准确提取：只提取用户明确提到或可以合理推断的信息
2. 保持原意：不要改变用户表达的原意
3. 置信度评分：对每个字段的提取结果给出0-100的置信度
4. 缺失字段：列出未能提取的字段
5. 追问问题：生成需要向用户进一步确认的问题

**示例1：**
用户输入："我叫张三，是计算机专业大二的学生，我想学好编程找到好工作。之前学过数据结构，考了85分，主要是看书和做题。我每天都坚持写代码2小时。"

输出：
```json
{{
  "name": "张三",
  "major": "计算机",
  "grade": "大二",
  "learning_goal": "学好编程找到好工作",
  "learning_history": [
    {{
      "课程": "数据结构",
      "成绩": 85,
      "学习方式": "看书和做题"
    }}
  ],
  "learning_habits": "每天都坚持写代码2小时",
  "confidence_scores": {{
    "name": 95,
    "major": 90,
    "grade": 95,
    "learning_goal": 85,
    "learning_history": 90,
    "learning_habits": 90
  }},
  "missing_fields": [],
  "follow_up_questions": []
}}
```

**示例2：**
用户输入："我是李明，学计算机的，现在大二。数据结构才考了47分，唉，我就是看视频，不怎么手写代码。每天就学个20分钟吧，不太喜欢编程。"

输出：
```json
{{
  "name": "李明",
  "major": "计算机",
  "grade": "大二",
  "learning_goal": "未知",
  "learning_history": [
    {{
      "课程": "rag_knowledge",
      "成绩": 47,
      "学习方式": "只是看视频，不怎么手写代码"
    }}
  ],
  "learning_habits": "每天学习20分钟，不怎么喜欢用编程",
  "confidence_scores": {{
    "name": 95,
    "major": 90,
    "grade": 95,
    "learning_goal": 0,
    "learning_history": 90,
    "learning_habits": 85
  }},
  "missing_fields": ["learning_goal"],
  "follow_up_questions": ["你学习编程的目标是什么？是为了就业、考研还是其他原因？"]
}}
```

**重要提醒：**
- 必须输出有效的JSON格式
- 置信度要客观反映提取的可靠性
- follow_up_questions 用于引导用户提供更多缺失信息
- 如果用户提供了多个课程经历，都要提取出来
- **只输出JSON，不要输出任何其他文字**

**用户输入：**
{user_input}

**请输出JSON：**""".strip()
        
        _extraction_template = PromptTemplate.from_template(template)
    
    return _extraction_template


def extract_user_info(user_input: str, 
                     existing_info: Optional[Dict[str, Any]] = None,
                     required_fields: Optional[List[str]] = None,
                     stop_if_incomplete: bool = False) -> Dict[str, Any]:
    """
    从用户输入中提取结构化信息（主函数）
    
    Args:
        user_input: 用户的自然语言输入
        existing_info: 已有的用户信息（用于增量更新）
        required_fields: 必需字段列表，如果提供则检查完整性
        stop_if_incomplete: 如果为True且信息不完整，直接返回追问响应而不继续处理
        
    Returns:
        Dict: 提取的结构化用户信息
            - 如果 stop_if_incomplete=True 且信息不完整，返回 {"status": "need_more_info", ...}
            - 否则返回正常的提取结果
    """
    try:
        # 构建完整的用户输入（包含已有信息作为上下文）
        if existing_info:
            context_info = f"\n\n**已有的用户信息（仅供参考，以新输入为准）：**\n{json.dumps(existing_info, ensure_ascii=False, indent=2)}"
            full_input = user_input + context_info
        else:
            full_input = user_input
        
        # 获取LLM和模板
        llm = _get_llm()
        template = _get_extraction_template()
        
        # 调用LLM进行信息抽取
        prompt = template.format(user_input=full_input)
        
        print("\n🔍 [信息抽取器] 正在分析用户输入...")
        
        response = llm.invoke(prompt)
        extraction_text = response.content if hasattr(response, 'content') else str(response)
        
        # 解析JSON响应
        result = _parse_json_response(extraction_text)
        
        if result:
            print(f"✅ 信息抽取完成")
            
            # 如果有已有信息，进行合并
            if existing_info:
                result = _merge_with_existing(existing_info, result)
            
            # 显示提取结果摘要
            _display_extraction_summary(result)
            
            # 检查信息完整性（如果提供了required_fields）
            if required_fields and stop_if_incomplete:
                info_complete = is_info_complete(result, required_fields)
                
                if not info_complete:
                    # 信息不完整，生成追问响应
                    questions = get_follow_up_questions(result)
                    missing = result.get('missing_fields', [])
                    
                    print(f"\n⚠️  用户信息不完整，需要追问")
                    print(f"   缺失字段: {missing}")
                    print(f"   追问问题: {questions[:2]}")
                    
                    # 返回追问响应，停止后续处理
                    return {
                        "status": "need_more_info",
                        "message": "为了更好地帮助你，请提供以下信息：",
                        "extracted_info": result,
                        "follow_up_questions": questions,
                        "missing_fields": missing,
                        "metadata": {
                            "processing_complete": False,
                            "reason": "incomplete_information"
                        }
                    }
            
            # 添加成功状态
            result["status"] = "success"
            result["metadata"] = {
                "processing_complete": True
            }
            
            return result
        else:
            print("❌ 信息抽取失败，返回默认结构")
            default_result = _get_default_structure()
            default_result["status"] = "error"
            default_result["metadata"] = {
                "processing_complete": False,
                "reason": "extraction_failed"
            }
            return default_result
            
    except Exception as e:
        print(f"❌ 信息抽取过程出错: {e}")
        import traceback
        traceback.print_exc()
        default_result = _get_default_structure()
        default_result["status"] = "error"
        default_result["metadata"] = {
            "processing_complete": False,
            "reason": f"exception: {str(e)}"
        }
        return default_result


def _parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """解析LLM返回的JSON响应"""
    try:
        # 尝试提取JSON块
        json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
        json_match = json_pattern.search(response)
        
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接匹配JSON对象
            json_only_pattern = re.compile(r'\{.*\}', re.DOTALL)
            json_match = json_only_pattern.search(response)
            if json_match:
                json_str = json_match.group(0)
            else:
                cleaned_response = response.strip()
                if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                    json_str = cleaned_response
                else:
                    print("❌ 未找到有效的JSON格式")
                    return None

        json_str = json_str.strip()
        data = json.loads(json_str)
        return data

    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        return None
    except Exception as e:
        print(f"❌ 解析响应时发生错误: {e}")
        return None


def _merge_with_existing(existing: Dict[str, Any], 
                        extracted: Dict[str, Any]) -> Dict[str, Any]:
    """
    将新提取的信息与已有信息合并
    
    Args:
        existing: 已有的用户信息
        extracted: 新提取的用户信息
        
    Returns:
        Dict: 合并后的用户信息
    """
    merged = existing.copy()
    
    # 获取已有信息的置信度
    existing_confidence = existing.get('confidence_scores', {})
    new_confidence = extracted.get('confidence_scores', {})
    
    for field in ['name', 'major', 'grade', 'learning_goal','learning_history', 'learning_habits']:
        existing_value = existing.get(field, '未知')
        new_value = extracted.get(field, '未知')
        new_conf = new_confidence.get(field, 0)
        existing_conf = existing_confidence.get(field, 0)
        
        # 如果新值有效且（旧值无效 或 新置信度更高），则更新
        if new_value and new_value != "未知":
            # 情况1：旧值是未知的，直接采用新值
            if existing_value == "未知":
                merged[field] = new_value
                # 更新置信度，至少设为70（因为用户明确提供了）
                if 'confidence_scores' not in merged:
                    merged['confidence_scores'] = {}
                merged['confidence_scores'][field] = max(new_conf, 70)
            # 情况2：旧值已知，但新置信度明显更高，则更新
            elif new_conf > existing_conf + 20:
                merged[field] = new_value
                if 'confidence_scores' not in merged:
                    merged['confidence_scores'] = {}
                merged['confidence_scores'][field] = new_conf
    
    # 合并学习历史（追加新的课程记录）
    if 'learning_history' in extracted and extracted['learning_history']:
        if 'learning_history' not in merged:
            merged['learning_history'] = []
        
        # 添加新的课程记录（避免重复）
        existing_courses = {h.get('课程') for h in merged['learning_history'] if h.get('课程')}
        for new_course in extracted['learning_history']:
            course_name = new_course.get('课程', '')
            if course_name and course_name not in existing_courses:
                merged['learning_history'].append(new_course)
                existing_courses.add(course_name)
    
    # 更新缺失字段列表
    missing_fields = []
    for field in ['name', 'major', 'grade', 'learning_goal','learning_history', 'learning_habits']:
        value = merged.get(field, '未知')
        conf = merged.get('confidence_scores', {}).get(field, 0)
        if value == "未知" or conf < 60:
            missing_fields.append(field)
    
    merged['missing_fields'] = missing_fields
    
    # 生成新的追问问题（只针对仍然缺失的字段）
    follow_up_map = {
        'name': '请问您的姓名是？',
        'grade': '您目前是哪个年级（如大一、大二、研一等）？',
        'learning_goal': '您的学习目标是什么？',
        'learning_history': '您学过哪些相关课程？成绩和学习方式如何？',
        'learning_habits': '您平时有哪些学习习惯？'
    }
    
    merged['follow_up_questions'] = [follow_up_map[field] for field in missing_fields if field in follow_up_map]
    
    return merged


def _display_extraction_summary(result: Dict[str, Any]):
    """显示提取结果摘要"""
    print(f"\n📋 提取结果摘要:")
    print(f"   姓名: {result.get('name', '未知')}")
    print(f"   专业: {result.get('major', '未知')}")
    print(f"   年级: {result.get('grade', '未知')}")
    print(f"   学习目标: {result.get('learning_goal', '未知')}")
    print(f"   学习习惯: {result.get('learning_habits', '未知')}")
    
    history = result.get('learning_history', [])
    if history:
        print(f"   学习历史: {len(history)} 条记录")
        for h in history:
            print(f"     - {h.get('课程', '未知')}: {h.get('成绩', '未知')}分")
    
    missing = result.get('missing_fields', [])
    if missing:
        print(f"   缺失字段: {', '.join(missing)}")
    
    questions = result.get('follow_up_questions', [])
    if questions:
        print(f"   需要追问: {len(questions)} 个问题")


def _get_default_structure() -> Dict[str, Any]:
    """获取默认的用户信息结构"""
    return {
        "name": "未知",
        "major": "未知",
        "grade": "未知",
        "learning_goal": "未知",
        "learning_history": [],
        "learning_habits": "未知",
        "confidence_scores": {
            "name": 0,
            "major": 0,
            "grade": 0,
            "learning_goal": 0,
            "learning_history": 0,
            "learning_habits": 0
        },
        "missing_fields": ["name", "major", "grade", "learning_goal", "learning_history", "learning_habits"],
        "follow_up_questions": [
            "请告诉我你的姓名、专业、年级等基本信息",
            "你的学习目标是什么？",
            "你有哪些学习经历？",
            "你的学习习惯是怎样的？"
        ]
    }


def get_follow_up_questions(extraction_result: Dict[str, Any]) -> List[str]:
    """
    获取需要追问的问题列表
    
    Args:
        extraction_result: 信息抽取结果
        
    Returns:
        List[str]: 需要追问的问题列表
    """
    return extraction_result.get('follow_up_questions', [])


def is_info_complete(extraction_result: Dict[str, Any], 
                    required_fields: Optional[List[str]] = None) -> bool:
    """
    检查用户信息是否完整
    
    Args:
        extraction_result: 信息抽取结果
        required_fields: 必需的字段列表（默认为基本字段）
        
    Returns:
        bool: 信息是否完整
    """
    if required_fields is None:
        required_fields = ['name', 'major', 'grade','learning_goal','learning_history','learning_habits']
    
    missing_fields = extraction_result.get('missing_fields', [])
    confidence_scores = extraction_result.get('confidence_scores', {})
    
    # 检查必需字段是否都存在且置信度高
    for field in required_fields:
        if field in missing_fields:
            return False
        if confidence_scores.get(field, 0) < 60:
            return False
    
    return True

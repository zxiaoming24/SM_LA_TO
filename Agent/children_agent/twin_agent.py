"""
twin_agent.py - 数字孪生作答Agent（LLM驱动）

核心功能：
1. 基于用户的数字孪生画像（知识掌握度、能力维度、错误模式）
2. 让 LLM 模拟用户的知识水平和答题风格回答问题
3. 返回孪生的答案及正确性判断

使用场景：
- 理论题（选择题/判断题/填空题）：LLM真正阅读题目后作答
- 编程题：太昂贵，回退到数学概率模型
- 视频观看：回退到数学概率模型

设计理念：
- prompt 中注入孪生画像，让 LLM 角色扮演
- 知识掌握度低的知识点 → 孪生倾向于答错（模拟用户真实情况）
- 知识掌握度高的知识点 → 孪生倾向于答对
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# LLM 实例（延迟加载）
_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        try:
            from utils.llm_config import get_chat_openai
            _llm = get_chat_openai(
                temperature=0.2,          # 低温度，保持孪生风格一致
                max_tokens=512,
                model=None,               # 使用默认模型
            )
        except Exception as e:
            logger.warning(f"[TwinAgent] LLM 初始化失败: {e}")
            return None
    return _llm


async def twin_answer_theory_question(
    twin_profile: Dict[str, Any],
    question_data: Dict[str, Any]
) -> Dict[str, Any]:
    """让孪生回答一道理论题，LLM 模拟用户作答
    
    参数:
        twin_profile: 孪生画像（knowledge_mastery, dimension_scores, error_patterns 等）
        question_data: 题目数据（question, options, answer, knowledge_point, question_type, difficulty）
    
    返回:
    {
        "simulated_answer": str,         # 孪生选择的答案
        "simulated_correct": bool,       # 孪生是否答对
        "confidence": float,             # 孪生信心度
        "reasoning": str,                # 模拟的答题思路
    }
    """
    llm = _get_llm()
    if llm is None:
        # LLM 不可用，回退到概率模型
        return _fallback_math(twin_profile, question_data)

    prompt = _build_twin_prompt(twin_profile, question_data)

    try:
        from utils.async_llm_caller import call_llm_with_retry

        response = await call_llm_with_retry(
            llm=llm,
            prompt=prompt,
            max_retries=1,
            error_msg="孪生作答失败"
        )

        result = _parse_response(response, question_data)
        return result

    except Exception as e:
        logger.warning(f"[TwinAgent] LLM 调用失败，回退到数学模型: {e}")
        return _fallback_math(twin_profile, question_data)


def _build_twin_prompt(profile: Dict[str, Any], question: Dict[str, Any]) -> str:
    """构建孪生作答的 prompt"""
    km = profile.get("knowledge_mastery", {})
    # 取掌握度最高和最低的各 5 个
    sorted_kp = sorted(km.items(), key=lambda x: x[1], reverse=True)
    strong_kp = [f"{kp}({int(val*100)}%)" for kp, val in sorted_kp[:5]]
    weak_kp = [f"{kp}({int(val*100)}%)" for kp, val in sorted_kp[-5:] if val < 0.6]

    dims = profile.get("dimension_scores", [])
    dim_names = ["学术背景", "学习行为", "目标动机", "认知能力",
                  "情绪状态", "社交互动", "时间管理", "创新创造"]
    dim_text = "、".join(f"{n}={d}" for n, d in zip(dim_names, dims) if d < 60)

    errors = profile.get("error_patterns", {})
    main_errors = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:2]
    error_text = "、".join(f"{n}({int(v*100)}%)" for n, v in main_errors)

    q = question.get("question", "")
    options = question.get("options", [])
    q_type = question.get("question_type", "single_choice")
    kp_name = question.get("knowledge_point", "未知")
    difficulty = question.get("difficulty", 0.5)
    diff_label = "简单" if difficulty < 0.3 else "中等" if difficulty < 0.7 else "困难"

    system_prompt = f"""你是用户的数字孪生，你需要严格模拟用户的知识水平和答题风格。

【用户的知识掌握情况】
强项：{', '.join(strong_kp) if strong_kp else '无明显强项'}
薄弱点：{', '.join(weak_kp) if weak_kp else '无明显薄弱点'}

【用户能力短板（低于60分）】
{dim_text if dim_text else '无明显短板'}

【用户常见错误类型】
{error_text if error_text else '无明显倾向'}

【答题规则】
1. 对于知识薄弱点，你应该倾向于答错（模拟用户真实水平）
2. 对于强项知识点，你应该倾向于答对
3. 考虑用户的常见错误类型来模拟错误答案
4. 如果题目包含选项，选一个最符合用户水平的选项
5. 如果不知道，不要蒙对

请以用户的身份作答，输出格式严格如下：
答案: <你的答案>
信心度: <0-100的整数>
思路: <用一句话说明你为什么这么答>
"""

    # 构建题目部分
    if q_type in ("single_choice", "multiple_choice", "judge"):
        opts_text = "\n".join(f"  {opt}" for opt in options) if options else ""
        question_text = f"""【题目】{q}
【题型】{q_type}
【知识点】{kp_name}
【难度】{diff_label}
【选项】\n{opts_text}""" if opts_text else f"""【题目】{q}
【题型】{q_type}
【知识点】{kp_name}
【难度】{diff_label}"""
    else:
        question_text = f"""【题目】{q}
【题型】{q_type}
【知识点】{kp_name}
【难度】{diff_label}"""

    return system_prompt + "\n\n" + question_text


def _parse_response(response_text: str, question: Dict[str, Any]) -> Dict[str, Any]:
    """解析 LLM 的响应，提取答案和正确性"""
    answer = ""
    confidence = 50
    reasoning = ""
    simulated_correct = False

    if not response_text:
        return _fallback_math(question=question)

    text = str(response_text).strip()

    # ★★★ call_llm_with_retry 返回的是 AIMessage，需要取 .content ★★★
    if hasattr(response_text, "content"):
        text = response_text.content.strip()
    else:
        text = str(response_text).strip()

    # 解析各字段（兼容全角/半角冒号）
    for line in text.split("\n"):
        line = line.strip()
        # 答案
        if line.startswith("答案") and (":" in line or "：" in line):
            sep = "：" if "：" in line else ":"
            answer = line.split(sep, 1)[1].strip()
        # 信心度
        elif line.startswith("信心度") and (":" in line or "：" in line):
            sep = "：" if "：" in line else ":"
            try:
                confidence = min(100, max(0, int(line.split(sep, 1)[1].strip())))
            except ValueError:
                confidence = 50
        # 思路
        elif line.startswith("思路") and (":" in line or "：" in line):
            sep = "：" if "：" in line else ":"
            reasoning = line.split(sep, 1)[1].strip()

    # 判断是否正确
    correct_answer = question.get("answer", "")
    if correct_answer and answer:
        ans = answer.strip()
        cor = str(correct_answer).strip()
        # 取每个答案的第一个有效字符比较（A/B/C/D）
        ans_first = ans[0] if ans else ""
        cor_first = cor[0] if cor else ""
        simulated_correct = ans_first == cor_first
    else:
        # 没有正确答案或没有提取到答案，用信心度估算
        simulated_correct = confidence >= 60

    return {
        "simulated_answer": answer,
        "simulated_correct": simulated_correct,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _fallback_math(twin_profile: Optional[Dict] = None, question: Optional[Dict] = None) -> Dict[str, Any]:
    """LLM不可用时的数学回退模型"""
    return {
        "simulated_answer": None,
        "simulated_correct": None,
        "confidence": 0,
        "reasoning": "回退到数学概率模型（LLM不可用）",
        "_fallback": True,
    }


async def twin_answer_practice_question(
    twin_profile: Dict[str, Any],
    problem_data: Dict[str, Any]
) -> Dict[str, Any]:
    """让孪生写一道编程题（LLM 模拟用户水平写代码）
    
    参数:
        twin_profile: 孪生画像
        problem_data: 题目数据（content/description, correct_answer, difficulty, language, problem_id）
    
    返回:
    {
        "simulated_answer": str,         # 孪生写的代码
        "simulated_correct": bool/None,  # 孪生代码是否通过（None表示未知）
        "confidence": float,             # 孪生信心度 0-100
        "reasoning": str,                # 答题思路
    }
    """
    llm = _get_llm()
    if llm is None:
        return _fallback_math(twin_profile, problem_data)

    km = twin_profile.get("knowledge_mastery", {})
    sorted_kp = sorted(km.items(), key=lambda x: x[1], reverse=True)
    strong_kp = [f"{kp}({int(val*100)}%)" for kp, val in sorted_kp[:5]]
    weak_kp = [f"{kp}({int(val*100)}%)" for kp, val in sorted_kp[-5:] if val < 0.6]
    dims = twin_profile.get("dimension_scores", [])
    dim_names = ["学术背景", "学习行为", "目标动机", "认知能力",
                  "情绪状态", "社交互动", "时间管理", "创新创造"]

    q_content = problem_data.get("content") or problem_data.get("description") or problem_data.get("question", "")
    kp_name = problem_data.get("knowledge_point", "未知")
    diff = float(problem_data.get("difficulty", 0.5))
    diff_label = "简单" if diff < 0.3 else "中等" if diff < 0.7 else "困难"
    language = problem_data.get("language", "python")

    system_prompt = f"""你是用户的数字孪生，你需要严格模拟用户的知识水平和编程能力来解答这道编程题。

【用户的知识掌握情况】
强项：{', '.join(strong_kp) if strong_kp else '无明显强项'}
薄弱点：{', '.join(weak_kp) if weak_kp else '无明显薄弱点'}

【用户能力短板（低于60分）】
{', '.join(f'{n}={d}' for n, d in zip(dim_names, dims) if d < 60) if dims and any(d < 60 for d in dims) else '无明显短板'}

【答题规则】
1. 用 {language} 语言写代码
2. 代码质量要符合用户的水平：薄弱知识点多 → 代码可能有bug或不够优雅；强项 → 代码相对正确
3. 不要写出完美代码，要模拟用户真实水平
4. 如果用户知识掌握度低，可以写出错误代码
5. 输出完整可运行的代码

【题目】
{q_content}

【知识点】{kp_name}
【难度】{diff_label}
【语言】{language}

请以用户的身份作答，输出格式：
答案: <完整代码>
信心度: <0-100的整数>
思路: <说明你的编码思路>
"""

    try:
        from utils.async_llm_caller import call_llm_with_retry
        response = await call_llm_with_retry(
            llm=llm,
            prompt=system_prompt,
            max_retries=1,
            error_msg="孪生编程作答失败"
        )

        if not response:
            return _fallback_math(twin_profile, problem_data)

        text = str(response).strip()
        if hasattr(response, "content"):
            text = response.content.strip()

        answer = ""
        confidence = 50
        reasoning = ""

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("答案") and (":" in line or "：" in line):
                sep = "：" if "：" in line else ":"
                answer = line.split(sep, 1)[1].strip()
            elif line.startswith("信心度") and (":" in line or "：" in line):
                sep = "：" if "：" in line else ":"
                try:
                    confidence = min(100, max(0, int(line.split(sep, 1)[1].strip())))
                except ValueError:
                    confidence = 50
            elif line.startswith("思路") and (":" in line or "：" in line):
                sep = "：" if "：" in line else ":"
                reasoning = line.split(sep, 1)[1].strip()

        # 代码可能跨多行（在"答案:"之后但在"信心度:"之前的所有内容）
        if not answer:
            # 尝试提取代码块
            import re
            code_match = re.search(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
            if code_match:
                answer = code_match.group(1).strip()

        return {
            "simulated_answer": answer or "（孪生未能生成代码）",
            "simulated_correct": None,  # 代码是否正确需要评测才能知道
            "confidence": confidence,
            "reasoning": reasoning,
        }

    except Exception as e:
        logger.warning(f"[TwinAgent] 编程作答LLM调用失败: {e}")
        return _fallback_math(twin_profile, problem_data)

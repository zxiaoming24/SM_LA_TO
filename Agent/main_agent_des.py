"""
主Agent - 智能教育系统主控中心（基于LangGraph）
使用LangChain的StateGraph实现动态Agent调度和协调
"""

from typing import Dict, Any, List, TypedDict, Optional
from langgraph.graph import StateGraph, END
import asyncio
import inspect
import time
from concurrent.futures import ThreadPoolExecutor
from Agent.children_agent.feature_extractor import StudentFeatureExtractor
from Agent.children_agent.teacher_agent import TeacherAgent
from Agent.children_agent.question_refiner import QuestionRefinerAgent
from Agent.children_agent.user_info_extractor import extract_user_info, is_info_complete, get_follow_up_questions
# TODO: 集成 wx_html_create (HTML动画生成)
# from Agent.children_agent.wx_html_create import generate_animation


# ==================== DES 节点 SSE 包装 ====================

async def _des_emit_status(node: str, status: str, detail: str = ""):
    """DES 节点状态推送到 SSE 队列"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue.get()
        if queue is not None:
            await queue.put({
                "type": "node_status",
                "node": f"des_{node}",
                "status": status,
                "detail": detail,
                "timestamp": time.time()
            })
    except Exception:
        pass

async def _des_emit_thinking(node: str, content: str):
    """DES LLM 思考内容推送到 SSE 队列"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue.get()
        if queue is not None:
            await queue.put({
                "type": "thinking",
                "node": f"des_{node}",
                "content": content,
                "timestamp": time.time()
            })
    except Exception:
        pass

def _des_emit_thinking_sync(node: str, content: str):
    """同步版本的思考推送，安全地从 sync 函数中调用"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue.get()
        if queue is not None:
            # ★★★ 修复：无运行中事件循环时使用新循环，避免 RuntimeError ★★★
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(queue.put({
                    "type": "thinking",
                    "node": f"des_{node}",
                    "content": content,
                    "timestamp": time.time()
                }))
            )
    except Exception:
         pass

def _wrap_des_node(node_name: str, node_func):
    """包装 DES 节点，自动推送 node_status 事件 + 注入 SSE LLM callback"""
    async def wrapped(state) -> dict:
        await _des_emit_status(node_name, "start")
        await _des_emit_thinking(node_name, f"🚀 DES {node_name} 节点开始执行")
        # ★★★ 注入 SSE LLM callback，get_chat_openai() 自动附加到新 LLM 实例 ★★★
        handler = None
        try:
            from utils.llm_config import set_llm_callback
            from Agent.main_agent_conduct import SSEThinkingCallbackHandler
            handler = SSEThinkingCallbackHandler(f"des_{node_name}")
            set_llm_callback(handler)
        except Exception:
            pass  # callback 不可用不阻塞
        try:
            result = await node_func(state) if inspect.iscoroutinefunction(node_func) else node_func(state)
            is_error = isinstance(result, dict) and result.get("status") == "error"
            if is_error:
                await _des_emit_status(node_name, "error", str(result.get("error", "")))
            else:
                await _des_emit_status(node_name, "complete")
                await _des_emit_thinking(node_name, f"✅ DES {node_name} 节点执行完成")
            return result
        except Exception as e:
            await _des_emit_status(node_name, "error", str(e))
            await _des_emit_thinking(node_name, f"❌ DES {node_name} 异常: {str(e)}")
            raise
        finally:
            if handler is not None:
                try:
                    from utils.llm_config import set_llm_callback
                    set_llm_callback(None)
                except Exception:
                    pass
    return wrapped


# ==================== 状态定义 ====================

class AgentState(TypedDict):
    """
    Agent系统的状态定义
    在所有节点之间传递的共享状态
    """
    # 输入数据
    student_data: Dict[str, Any]  # 学生数据（结构化）
    user_query: str               # 用户问题（原始输入）
    user_id: Optional[str]        # ★★★ 用户ID（用于保存特征到JSON）★★★
    
    # 用户信息抽取结果
    extracted_user_info: Dict[str, Any]  # 从自然语言中提取的用户信息
    
    # 中间结果
    features: Dict[str, Any]      # 学生特征
    scores: Dict[str, Any]        # 评分数据
    guidance: str                 # 教师指导
    refined_outline: Dict[str, Any]  # 提炼后的大纲
    plan_options: List[Dict[str, Any]]  # 3套学习方案（新增）
    
    # 控制流
    next_agent: str               # 下一个要执行的Agent
    execution_log: List[str]      # 执行日志
    
    # 最终输出
    result: Dict[str, Any]        # 最终结果

# ==================== Agent节点函数 ====================

def create_user_info_extractor_node():
    """
    创建用户信息抽取节点（第一个执行的节点）
    从用户的自然语言输入中自动提取结构化信息
    
    Returns:
        节点函数
    """
    def user_info_extractor_node(state: AgentState) -> AgentState:
        """用户信息抽取节点的执行逻辑"""
        print("\n🔍 [节点] 用户信息抽取器执行中...")
        
        user_query = state.get("user_query", "")
        existing_info = state.get("extracted_user_info", {})
        student_data = state.get("student_data", {})  # 获取传入的学生数据
        
        # 如果有 student_data，直接使用它作为提取结果（不需要LLM再次提取）
        if student_data and not existing_info:
            print(f"💡 检测到学生数据，直接使用该数据")
            _des_emit_thinking_sync("user_info_extractor", "检测到已有学生数据，直接使用无需LLM提取")
            # 将 student_data 转换为 extract_user_info 的返回格式
            extracted_info = {
                'name': student_data.get('name', '未知'),
                'major': student_data.get('major', '未知'),
                'grade': student_data.get('grade', '未知'),
                'learning_goal': student_data.get('learning_goal', student_data.get('goal', '未知')),
                'learning_history': student_data.get('learning_history', []),
                'learning_habits': student_data.get('learning_habits', '未知'),
                'weaknesses': student_data.get('weaknesses', ''),
                'strengths': student_data.get('strengths', ''),
                'confidence_scores': {
                    'name': 95,
                    'major': 95,
                    'grade': 95,
                    'learning_goal': 85,
                    'learning_history': 90,
                    'learning_habits': 85
                },
                'missing_fields': [],
                'follow_up_questions': []
            }
            # 显示提取结果摘要
            from Agent.children_agent.user_info_extractor import _display_extraction_summary
            _display_extraction_summary(extracted_info)
        else:
            # 否则只从用户查询中提取
            extracted_info = extract_user_info(user_query, existing_info)
        
        # 检查信息是否完整
        required_fields = ['name', 'major', 'grade','learning_goal','learning_history','learning_habits']  #   执行之后过程的所需必要字段
        info_complete = is_info_complete(extracted_info, required_fields)
        
        print(f"✅ 用户信息抽取完成 - 信息完整: {info_complete}")
        
        # 更新状态
        return {
            **state,
            "extracted_user_info": extracted_info,
            "execution_log": state.get("execution_log", []) + ["user_info_extractor"]
        }
    
    return user_info_extractor_node


def create_feature_extractor_node(extractor: StudentFeatureExtractor):
    """
    创建特征提取节点
    
    Args:
        extractor: 特征提取器实例
    
    Returns:
        节点函数
    """
    async def feature_extractor_node(state: AgentState) -> AgentState:
        """特征提取节点的执行逻辑"""
        print("\n📊 [节点] 特征提取器执行中...")
        
        # 优先使用提取的用户信息，如果没有则使用 student_data
        extracted_info = state.get("extracted_user_info", {})
        student_data = state.get("student_data", {})
        user_id = state.get("user_id")  # ★★★ 获取user_id ★★★
        
        # 如果 extracted_info 中有数据，使用它；否则使用 student_data
        if extracted_info and extracted_info.get('name') != '未知':
            # 将 extracted_info 转换为 feature_extractor 需要的格式
            feature_input = {
                "姓名": extracted_info.get('name', ''),
                "专业": extracted_info.get('major', ''),
                "年级": extracted_info.get('grade', ''),
                "学习目标": extracted_info.get('learning_goal', ''),
                "学习历史": extracted_info.get('learning_history', []),
                "学习习惯": extracted_info.get('learning_habits', '')
            }
            print(f"✅ 使用提取的用户信息进行特征分析")
        else:
            feature_input = student_data
            print(f"✅ 使用原始学生数据进行特征分析")
        
        # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback（实现逐词推送）★★★
        if hasattr(extractor, '_initialize_llm'):
            extractor.llm = extractor._initialize_llm()
        
        # 执行特征提取（直接 await）
        features = await extractor.extract_features_async(feature_input)
        
        if not extractor.validate_features(features):
            print("⚠️  特征验证失败，使用默认特征")
            features = extractor._get_default_features_with_scores()
        
        # 获取评分
        scores = {
            "dimension_scores": extractor.get_dimension_scores(features),
            "overall_score": features.get('summary_scores', {}).get('overall_score', 0)
        }
        
        print(f"✅ 特征提取完成 - 总体评分: {scores['overall_score']}/100")
        
        # ★★★ 关键：将特征保存到用户特征JSON文件 ★★★
        if user_id:
            try:
                from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                updater = DynamicFeatureUpdater()
                
                # 初始化用户特征（首次注册）
                updater.initialize_user_features(user_id, features)
                
                print(f"✅ 已将特征保存到 user_features/{user_id}.json")
            except Exception as e:
                print(f"⚠️  保存特征到JSON失败: {e}")
        
        # 更新状态
        return {
            **state,
            "features": features,
            "scores": scores,
            "execution_log": state.get("execution_log", []) + ["feature_extractor"]
        }
    
    return feature_extractor_node   # 也就返回上面的信息


async def create_teacher_node_async(teacher: TeacherAgent):
    """
    创建异步教师Agent节点
    
    Args:
        teacher: 教师Agent实例
    
    Returns:
        节点函数
    """
    async def teacher_node(state: AgentState) -> AgentState:
        """教师节点的执行逻辑"""
        print("\n🎓 [节点] 教师Agent执行中...")
        
        features = state.get("features", {})
        user_query = state.get("user_query", "")
        
        # ★★★ 调用异步方法提供指导 ★★★
        guidance_result = await teacher.provide_guidance_async(
            student_features=features,
            user_query=user_query,
            user_id=state.get("user_id", "")
        )
        
        # 兼容新旧返回格式（Dict或str）
        if isinstance(guidance_result, dict):
            guidance = guidance_result.get("guidance", "")
        else:
            guidance = guidance_result
        
        print("✅ 教师指导生成完成")
        
        # 更新状态
        return {
            **state,
            "guidance": guidance,
            "execution_log": state.get("execution_log", []) + ["teacher"]
        }
    
    return teacher_node


def create_teacher_node(teacher: TeacherAgent):
    """
    创建教师Agent节点(同步版本,用于LangGraph工作流)
    
    Args:
        teacher: 教师Agent实例
    
    Returns:
        节点函数
    """
    async def teacher_node(state: AgentState) -> AgentState:
        """教师节点的执行逻辑"""
        print("\n🎓 [节点] 教师Agent执行中...")
        
        features = state.get("features", {})
        user_query = state.get("user_query", "")
        user_id = state.get("user_id", "")
        
        # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback（实现逐词推送）★★★
        teacher.llm = teacher._initialize_llm()
        
        # ★★★ 检查是否已有持久化的方案列表（首次才生成）★★★
        import os, json
        _options_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "plan_configs", f"{user_id}_options.json")
        _has_saved_options = os.path.exists(_options_path)
        loop = asyncio.get_running_loop()
        
        if not _has_saved_options:
            # 首次：生成3套方案并持久化存储
            plan_result = await teacher.generate_plan_options(
                student_features=features,
                user_query=user_query,
                user_id=user_id
            )
            plans = plan_result.get("plans", [])
            print(f"✅ 首次生成，已生成 {len(plans)} 套学习方案")
            # 持久化存储方案列表
            try:
                await loop.run_in_executor(None, lambda: (
                    os.makedirs(os.path.dirname(_options_path), exist_ok=True),
                    json.dump({"plans": plans, "user_id": user_id}, open(_options_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                ))
                print(f"✅ 方案列表已持久化到 {_options_path}")
            except Exception as e:
                print(f"⚠️ 方案列表持久化失败: {e}")
        else:
            # 非首次：从磁盘读取已有方案
            try:
                _saved = await loop.run_in_executor(None, lambda: json.load(open(_options_path, 'r', encoding='utf-8')))
                plans = _saved.get("plans", [])
                print(f"✅ 从磁盘加载已有方案列表，共 {len(plans)} 套")
            except Exception as e:
                print(f"⚠️ 读取方案列表失败，回退重新生成: {e}")
                plan_result = await teacher.generate_plan_options(
                    student_features=features,
                    user_query=user_query,
                    user_id=user_id
                )
                plans = plan_result.get("plans", [])
        
        # 生成原有的guidance作为补充说明
        guidance_result = await teacher.provide_guidance_async(
            student_features=features,
            user_query=user_query
        )
        if isinstance(guidance_result, dict):
            guidance = guidance_result.get("guidance", "")
        else:
            guidance = guidance_result
        
        print(f"✅ 教师节点完成，方案数: {len(plans)}")
        
        # 更新状态
        return {
            **state,
            "plan_options": plans,
            "guidance": guidance,
            "execution_log": state.get("execution_log", []) + ["teacher"]
        }
    
    return teacher_node


async def create_question_refiner_node_async(refiner: QuestionRefinerAgent):
    """
    创建异步问题提炼节点
    
    Args:
        refiner: 问题提炼Agent实例
    
    Returns:
        节点函数
    """
    async def question_refiner_node(state: AgentState) -> AgentState:
        """问题提炼节点的执行逻辑"""
        print("\n🔍 [节点] 问题提炼Agent执行中...")
        
        user_query = state.get("user_query", "")
        
        # ★★★ 使用异步方法提炼问题为大纲 ★★★
        refined_title = await refiner.refine_question_async(user_query)
        
        # 构建大纲结构
        refined_outline = {
            "refined_title": refined_title,
            "original_question": user_query,
            "title_length": len(refined_title),
            "outline_structure": [
                {"section": "一、概念定义", "description": f"{refined_title}的基本概念"},
                {"section": "二、核心原理", "description": f"{refined_title}的工作原理"},
                {"section": "三、实际应用", "description": f"{refined_title}的使用场景"},
                {"section": "四、常见问题", "description": f"{refined_title}的常见误区"},
                {"section": "五、总结回顾", "description": f"{refined_title}的要点总结"}
            ]
        }
        
        print(f"✅ 问题提炼完成 - 标题: {refined_outline.get('refined_title', '未命名')}")
        
        # 更新状态
        return {
            **state,
            "refined_outline": refined_outline,
            "execution_log": state.get("execution_log", []) + ["question_refiner"]
        }
    
    return question_refiner_node


def create_question_refiner_node(refiner: QuestionRefinerAgent):
    """
    创建问题提炼节点(异步版本,用于LangGraph工作流)
    
    Args:
        refiner: 问题提炼Agent实例
    
    Returns:
        异步节点函数
    """
    async def question_refiner_node(state: AgentState) -> AgentState:
        """问题提炼节点的执行逻辑（异步）"""
        print("\n🔍 [节点] 问题提炼Agent执行中...")
        
        user_query = state.get("user_query", "")
        
        # ★★★ 刷新 LLM 以绑定当前上下文的 SSE callback ★★★
        refiner.llm = refiner._initialize_llm()
        await _des_emit_thinking("question_refiner", f"正在提炼用户问题: {user_query[:50]}...")
        
        # 异步调用
        refined_outline = await refiner.generate_outline_from_question(user_query)
        
        await _des_emit_thinking("question_refiner", f"问题提炼完成: {refined_outline.get('refined_title', '')}")
        
        # 更新状态
        return {
            **state,
            "refined_outline": refined_outline,
            "execution_log": state.get("execution_log", []) + ["question_refiner"]
        }
    
    return question_refiner_node



def router_node(state: AgentState) -> AgentState:
    """
    路由决策节点 - 根据情况决定下一步走向
    
    Args:
        state: 当前状态
    
    Returns:
        更新后的状态（包含next_agent决策）
    """
    print("\n🔀 [节点] 路由决策中...")

    student_data = state.get("student_data", {})
    user_query = state.get("user_query", "")
    extracted_info = state.get("extracted_user_info", {})

    # 获取执行历史，判断当前处于哪个阶段
    execution_log = state.get("execution_log", [])

    # 检测是否是学习问题（需要提炼大纲）
    learning_keywords = [
        # 基础疑惑类
        "不会", "不懂", "不明白", "不理解", "不清楚", "不知道",

        # 学习方法类
        "怎么学", "如何学", "怎样学", "如何理解", "怎么理解", "怎样理解",
        "如何使用", "怎么用", "怎样使用", "如何实现", "怎么做",

        # 概念知识类
        "知识点", "概念", "教程", "原理", "什么是", "什么叫",
        "定义", "含义", "意思", "区别", "差异",

        # 困难困惑类
        "困惑", "难点", "难题", "困难", "问题", "疑问",
        "搞不懂", "弄不明白", "想不通", "搞不清",

        # 请求帮助类
        "请教", "帮助", "指导", "解释", "说明", "讲解",
        "详细说", "详细介绍", "具体说", "举个例子",

        # 对比分析类
        "区别", "不同", "对比", "比较", "优缺点", "哪个好",

        # 技能提升类
        "提高", "提升", "加强", "改善", "改进", "优化",
        "技巧", "方法", "策略", "建议",

        # 常见疑问词
        "什么", "为什么", "如何", "怎么", "怎样", "哪里",
        "何时", "什么时候", "哪些", "哪个"
    ]
    needs_refinement = any(keyword in user_query for keyword in learning_keywords)

    # 决策逻辑：支持串联流程
    has_student_data = bool(student_data) or bool(extracted_info)
    
    # 如果刚执行完 user_info_extractor，检查信息是否完整
    if "user_info_extractor" in execution_log and len(execution_log) == 1:
        # 第一次执行完信息抽取后
        required_fields =['name', 'major', 'grade', 'learning_goal','learning_history', 'learning_habits']  #  判断  用户输入信息是否足够进行生成属性表
        info_complete = is_info_complete(extracted_info, required_fields)
        
        # 添加详细调试信息
        confidence_scores = extracted_info.get('confidence_scores', {})
        missing_fields = extracted_info.get('missing_fields', [])
        print(f"\n🔍 信息完整性检查:")
        print(f"   required_fields: {required_fields}")
        print(f"   missing_fields: {missing_fields}")
        print(f"   confidence_scores: {confidence_scores}")
        for field in required_fields:
            conf = confidence_scores.get(field, 0)
            status = "✅" if conf >= 60 else "❌"
            print(f"     {status} {field}: {conf}")
        print(f"   info_complete: {info_complete}\n")
        
        if not info_complete:
            # 信息不完整，返回追问问题
            questions = get_follow_up_questions(extracted_info)    #   ？？？？  为什么就返回了需要继续提问的问题？？
            print(f"⚠️  用户信息不完整，需要追问")
            print(f"   缺失字段: {extracted_info.get('missing_fields', [])}")
            print(f"   追问问题: {questions[:2]}")
            
            # 直接跳到 integrator 生成追问响应
            next_agent = "integrator"
        elif needs_refinement and "question_refiner" not in execution_log:
            # 信息完整且是学习问题，先提炼问题
            next_agent = "question_refiner"
            print(f"✅ 路由决策: 信息已提取，检测到学习问题，需要提炼大纲 → {next_agent}")
        else:
            # 信息完整，继续特征提取
            next_agent = "feature_extractor"
            print(f"✅ 路由决策: 信息已提取，继续特征提取 → {next_agent}")
    
    # 如果刚执行完 question_refiner 且有学生数据，继续执行 feature_extractor
    elif "question_refiner" in execution_log and has_student_data:
        next_agent = "feature_extractor"
        print(f"✅ 路由决策: 问题已提炼，继续特征提取 → {next_agent}")
    # 如果是学习问题且还未提炼，先执行 question_refiner
    elif needs_refinement and "question_refiner" not in execution_log:
        next_agent = "question_refiner"
        print(f"✅ 路由决策: 检测到学习问题，需要提炼大纲 → {next_agent}")
    # 如果有学生数据且问题复杂，执行特征提取
    elif has_student_data:
        next_agent = "feature_extractor"
        print(f"✅ 路由决策: 需要特征提取 → {next_agent}")
    # 否则直接咨询教师
    else:
        next_agent = "teacher"
        print(f"✅ 路由决策: 快速咨询 → {next_agent}")

    return {
        **state,
        "next_agent": next_agent,
        "execution_log": execution_log + ["router"]
    }


def integrator_node(state: AgentState) -> AgentState:
    """
    结果整合节点 - 整合所有结果
    
    Args:
        state: 当前状态
    
    Returns:
        包含完整结果的状态
    """
    print("\n📦 [节点] 结果整合中...")
    
    # 检查是否已经有结果（例如 need_more_info）
    existing_result = state.get("result", {})
    if existing_result and existing_result.get("status") == "need_more_info":
        # 如果已经有追问响应，直接返回
        print("✅ 检测到追问响应，直接返回")
        return {
            **state,
            "execution_log": state.get("execution_log", []) + ["integrator"]
        }
    
    extracted_info = state.get("extracted_user_info", {})
    execution_log = state.get("execution_log", [])
    
    # 检查信息是否完整（使用完整的必需字段列表）
    required_fields = ['name', 'major', 'grade', 'learning_goal', 'learning_history', 'learning_habits']
    info_complete = is_info_complete(extracted_info, required_fields)
    
    if not info_complete:
        # 信息不完整，生成追问响应
        missing_fields = extracted_info.get('missing_fields', [])
        questions = get_follow_up_questions(extracted_info)
        
        result = {
            "status": "need_more_info",
            "message": "为了更好地帮助你，请提供以下信息：",
            "extracted_info": extracted_info,
            "follow_up_questions": questions,
            "missing_fields": missing_fields,
            "metadata": {
                "agents_used": execution_log,
                "processing_complete": False
            }
        }
        
        print(f"⚠️  信息不完整，生成追问响应")
        print(f"   缺失字段: {missing_fields}")
        print(f"   追问问题: {questions}")
        
        return {
            **state,
            "result": result,
            "execution_log": execution_log + ["integrator"]
        }
    
    # 构建最终结果（正常流程 - 信息完整）
    plan_options = state.get("plan_options", [])
    has_plan_options = bool(plan_options) and len(plan_options) >= 3
    
    result = {
        "status": "success",
        "student_data": state.get("student_data", {}),
        "extracted_user_info": extracted_info,
        "user_query": state.get("user_query", ""),
        "analysis": {
            "features": state.get("features", {}),
            "scores": state.get("scores", {})
        },
        "guidance": state.get("guidance", ""),
        "refined_outline": state.get("refined_outline", {}),
        "plan_options": plan_options if has_plan_options else None,
        "metadata": {
            "agents_used": state.get("execution_log", []),
            "processing_complete": True,
            "has_plan_options": has_plan_options
        }
    }
    
    print("✅ 结果整合完成")
    
    return {
        **state,
        "result": result,
        "execution_log": state.get("execution_log", []) + ["integrator"]
    }
# ==================== 主Agent类 ====================

class MainAgent:
    """
    主Agent - 基于LangGraph的教育系统核心控制器
    
    使用LangChain的StateGraph实现：
    - 动态路由：根据输入自动选择合适的Agent路径
    - 状态管理：在节点间传递共享状态
    - 灵活扩展：轻松添加新Agent节点
    - 可视化：清晰展示执行流程
    """

    def __init__(self):
        """初始化主Agent并构建LangGraph工作流"""
        print("🚀 正在初始化主Agent系统（LangGraph架构）...")
        
        # 初始化工具和子Agent
        self.feature_extractor = StudentFeatureExtractor()
        self.teacher_agent = TeacherAgent()
        self.question_refiner = QuestionRefinerAgent()
        
        # 构建LangGraph工作流
        self.app = self._build_workflow()
        
        print("✅ 主Agent系统初始化完成")
        print(f"   - 已编译LangGraph工作流")
    
    def _build_workflow(self):
        """
        构建LangGraph工作流
        
        流程设计：
        START → user_info_extractor (首先提取用户信息)
                 |
                 v
               router (路由决策)
                 |
                 ├─→ question_refiner → router → feature_extractor → teacher → integrator → END
                 |
                 ├─→ feature_extractor → teacher → integrator → END
                 |
                 └─→ teacher (快速路径) → integrator → END
        
        Returns:
            编译后的LangGraph应用
        """
        # 创建工作流
        workflow = StateGraph[AgentState, None, AgentState, AgentState](AgentState)  #  对应第二个参数ContextT底层默认值是None
        
        # 添加节点（使用 _wrap_des_node 包装以推送 SSE 状态）
        workflow.add_node("user_info_extractor", _wrap_des_node("user_info_extractor", create_user_info_extractor_node()))
        workflow.add_node("router", _wrap_des_node("router", router_node))
        workflow.add_node("feature_extractor", 
                         _wrap_des_node("feature_extractor", create_feature_extractor_node(self.feature_extractor)))
        workflow.add_node("teacher", 
                         _wrap_des_node("teacher", create_teacher_node(self.teacher_agent)))
        workflow.add_node("integrator", _wrap_des_node("integrator", integrator_node))
        workflow.add_node("question_refiner", 
                         _wrap_des_node("question_refiner", create_question_refiner_node(self.question_refiner)))
        
        # 设置入口点：首先执行用户信息抽取
        workflow.set_entry_point("user_info_extractor")
        
        # 从 user_info_extractor 到 router
        workflow.add_edge("user_info_extractor", "router")
        
        # 定义路由决策函数
        def route_decision(state: AgentState) -> str:
            """根据路由节点的决策动态路由"""
            next_agent = state.get("next_agent", "END")
            print(f"🚀 动态路由到: {next_agent}")
            return next_agent
        
        # 添加条件边：router根据决策路由到不同节点
        workflow.add_conditional_edges(
            "router",
            route_decision,
            {
                "feature_extractor": "feature_extractor",
                "teacher": "teacher",
                "question_refiner": "question_refiner",
                "integrator": "integrator",
                "END": END
            }
        )
        
        # 添加普通边
        workflow.add_edge("feature_extractor", "teacher")
        workflow.add_edge("question_refiner", "router")
        workflow.add_edge("teacher", "integrator")
        workflow.add_edge("integrator", END)
        
        # 编译工作流
        app = workflow.compile()
        
        print("✅ LangGraph工作流编译完成")
        print("   流程图: user_info_extractor → router → [question_refiner/feature_extractor] → teacher → integrator → END")
        
        return app

    async def process_student_consultation(
        self,
        student_data: Dict[str, Any],
        user_query: str,
        previous_extracted_info: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None  # ★★★ 新增user_id参数 ★★★
    ) -> Dict[str, Any]:
        """
        处理学生咨询请求 - 使用LangGraph执行
        
        Args:
            student_data: 学生的基本信息（可以为空，系统会自动从user_query中提取）
            user_query: 用户的具体问题或需求（自然语言）
            previous_extracted_info: 之前提取的用户信息（用于多轮对话，合并信息）
            user_id: 用户ID（用于保存特征到JSON文件）
            
        Returns:
            Dict: 包含分析结果和建议的完整响应
        """
        print("\n" + "="*60)
        print("📋 开始处理学生咨询请求（LangGraph模式）")
        print("="*60)
        
        # 初始化状态
        initial_state = AgentState(
            student_data=student_data if student_data else {},
            user_query=user_query,
            user_id=user_id,  # ★★★ 将user_id传入state ★★★
            extracted_user_info=previous_extracted_info if previous_extracted_info else {},  # 如果有之前的信息，传入作为上下文
            features={},
            scores={},
            guidance="",
            refined_outline={},
            next_agent="",
            execution_log=[],
            result={}
        )
        
        try:
            # 执行LangGraph工作流（异步）
            print("\n▶️  执行LangGraph工作流...")
            final_state = await self.app.ainvoke(initial_state)
            
            # 提取结果
            result = final_state.get("result", {})
            
            if not result:
                # 如果没有result字段，从状态中构建
                result = {
                    "status": "success",
                    "student_data": student_data,
                    "user_query": user_query,
                    "analysis": {
                        "features": final_state.get("features", {}),
                        "scores": final_state.get("scores", {})
                    },
                    "guidance": final_state.get("guidance", ""),
                    "metadata": {
                        "agents_used": final_state.get("execution_log", []),
                        "processing_complete": True
                    }
                }
            
            print("\n✅ LangGraph工作流执行完成")
            print(f"   执行节点: {final_state.get('execution_log', [])}")
            
        except Exception as e:
            print(f"❌ 处理过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            
            result = {
                "status": "error",
                "error_message": str(e),
                "student_data": student_data,
                "user_query": user_query,
                "guidance": f"抱歉，系统在分析时遇到了问题：{str(e)}。请稍后重试。"
            }
        
        print("\n" + "="*60)
        print("✨ 咨询处理完成")
        print("="*60 + "\n")
        
        return result

    def quick_consult(self, question: str) -> str:
        """
        快速咨询（不需要学生数据）
        
        Args:
            question: 教育相关问题
            
        Returns:
            str: 教师的简要建议
        """
        print(f"\n💬 [快速咨询] 问题: {question}")
        advice = self.teacher_agent.provide_quick_advice(question)
        return advice
    
    async def process_natural_language_input(self, user_input: str, 
                                      previous_extracted_info: Optional[Dict[str, Any]] = None,
                                      user_id: Optional[str] = None) -> Dict[str, Any]:  # ★★★ 新增user_id参数 ★★★
        """
        处理自然语言输入 - 异步版本
        系统会自动从用户输入中提取信息并提供建议
        
        Args:
            user_input: 用户的自然语言输入
            previous_extracted_info: 之前提取的用户信息（用于多轮对话，合并信息）
            user_id: 用户ID（用于保存特征到JSON文件）
            
        Returns:
            Dict: 处理结果
                - status: "success" 或 "need_more_info"
                - 如果 status 是 "need_more_info"，会包含 follow_up_questions
                - 如果 status 是 "success"，会包含完整的分析结果
        """
        return await self.process_student_consultation(
            student_data={},
            user_query=user_input,
            previous_extracted_info=previous_extracted_info,
            user_id=user_id  # ★★★ 传递user_id ★★★
        )
    
    async def process_natural_language_input_async(self, user_input: str, 
                                                   previous_extracted_info: Optional[Dict[str, Any]] = None,
                                                   user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        异步处理自然语言输入
        
        Args:
            user_input: 用户的自然语言输入
            previous_extracted_info: 之前提取的用户信息
            user_id: 用户ID
            
        Returns:
            Dict: 处理结果
        """
        return await self.process_natural_language_input(
            user_input,
            previous_extracted_info,
            user_id
        )


    def get_system_status(self) -> Dict[str, Any]:
        """获取系统当前状态信息"""
        return {
            "system_name": "智能教育系统主Agent（LangGraph）",
            "version": "3.1.0",
            "architecture": "LangGraph StateGraph",
            "nodes": ["user_info_extractor", "router", "feature_extractor", "teacher", "integrator", "question_refiner"],
            "capabilities": [
                "自然语言用户信息自动提取",
                "LangGraph动态路由",
                "状态管理工作流",
                "学生特征自动提取与分析",
                "个性化学习方案制定",
                "教育问题智能咨询",
                "多维度能力评估",
                "教师专业指导",
                "学习问题提炼与大纲生成",
                "可扩展Agent节点"
            ]
        }

    def display_result(self, result: Dict[str, Any]):
        """美观地展示处理结果"""
        if result["status"] != "success":
            print(f"\n❌ 处理失败: {result.get('error_message', '未知错误')}")
            return
        
        # 显示提炼的大纲（如果有）
        refined_outline = result.get('refined_outline', {})
        if refined_outline:
            print("\n" + "📝"*30)
            print("📋 学习问题大纲")
            print("📝"*30)
            print(f"\n✅ 提炼标题: {refined_outline.get('refined_title', '')}")
            print(f"   标题长度: {refined_outline.get('title_length', 0)}字")
            print(f"   原始问题: {refined_outline.get('original_question', '')}")
            print()
            print("📑 大纲结构:")
            for item in refined_outline.get('outline_structure', []):
                print(f"   {item['section']}: {item['description']}")
        
        # 显示评分（如果有）
        scores = result["analysis"].get("scores", {})
        dim_scores = scores.get("dimension_scores", [])
        overall = scores.get("overall_score", 0)
        
        if dim_scores:
            print("\n" + "🎯"*30)
            print("📊 学生特征分析报告")
            print("🎯"*30)
            
            print(f"\n【综合评分】{overall}/100")
            print("-" * 40)
            
            dimensions = ["学术背景", "学习行为", "目标动机", "认知能力"]
            for i, (dim, score) in enumerate(zip(dimensions, dim_scores)):
                bar = "█" * (score // 5) + "░" * (20 - score // 5)
                print(f"{dim:8s}: [{bar}] {score}分")


def _cancel_pending_tasks(loop):
    """取消事件循环中所有未完成的任务"""
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()



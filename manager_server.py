"""
manager_server.py - 管理端 API

提供 RESTful API 用于运行时查看和修改专注度判断、
情绪影响权重、综合评分参数、全局排行榜权重以及题库管理等配置。

挂载到 api_server.py 使用，端口保持 8000：
    from manager_server import manager_router
    app.include_router(manager_router, prefix="/admin")

=================== 全部路由清单 ====================

【权重配置】
    GET    /admin/weights                  - 查看全部权重配置
    GET    /admin/weights/schema           - 获取权重配置结构说明
    GET    /admin/weights/{category}       - 查看指定分类权重
    POST   /admin/weights/{category}       - 更新指定分类权重
    POST   /admin/weights/reset            - 重置权重为默认值

【全局排行榜权重】
    GET    /admin/global-ranking/weights   - 查看全局排行榜权重配置
    POST   /admin/global-ranking/weights   - 更新全局排行榜权重配置

【题库管理】
    GET    /admin/questions                - 题库列表（分页）
    GET    /admin/questions/stats          - 题库统计信息
    GET    /admin/questions/topics         - 获取所有知识点
    GET    /admin/questions/{qid}          - 获取题目详情
    POST   /admin/questions                - 新增题目
    PUT    /admin/questions/{qid}          - 更新题目
    DELETE /admin/questions/{qid}          - 删除题目

【视频管理】
    GET    /admin/videos                   - 视频列表（分页）
    GET    /admin/videos/{vid}             - 获取视频详情
    POST   /admin/videos                   - 新增视频
    PUT    /admin/videos/{vid}             - 更新视频
    DELETE /admin/videos/{vid}             - 删除视频
"""

import sys
import os

# 确保能导入 face_select 目录下的 weight_config_manager
_face_select_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Agent", "face_select")
if _face_select_dir not in sys.path:
    sys.path.insert(0, _face_select_dir)

import json
import asyncio

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from weight_config_manager import (
    get_weights, update_weights, reset_weights, get_weight_schema
)

# 题库管理
import sys as _sys
_qbank_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Agent", "children_agent", "recommendation")
if _qbank_path not in _sys.path:
    _sys.path.insert(0, _qbank_path)
from resource_db import ResourceDB

manager_router = APIRouter()
_qdb = ResourceDB()

# ==================== 数据模型 ====================

class WeightUpdateRequest(BaseModel):
    """权重更新请求"""
    updates: Dict[str, Any] = Field(
        ...,
        description="要更新的键值对（支持嵌套），例如: {\"immersion_weights\": {\"focus_score\": 0.5}}"
    )


class WeightResetRequest(BaseModel):
    """权重重置请求"""
    category: Optional[str] = Field(
        None,
        description=("要重置的分类名（attention_tracker / emotion_state_mapper / "
                     "attention_bridge / gaze_detector），不填则重置全部")
    )


# ==================== 题库管理数据模型 ====================

class QuestionCreateRequest(BaseModel):
    """新增题目请求"""
    topic: str = Field(..., description="主题/知识点分类")
    sub_topic: Optional[str] = Field("", description="子主题")
    difficulty: int = Field(3, description="难度 1-5", ge=1, le=5)
    knowledge_points: List[str] = Field(default_factory=list, description="知识点列表")
    title: str = Field("", description="题目标题")
    content: str = Field(..., description="题目内容/题干")
    solution: str = Field("", description="答案/解析")
    hints: List[str] = Field(default_factory=list, description="提示列表")
    options: List[str] = Field(default_factory=list, description="选项列表（选择题用）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class QuestionUpdateRequest(BaseModel):
    """更新题目请求（所有字段可选）"""
    topic: Optional[str] = Field(None, description="主题")
    sub_topic: Optional[str] = Field(None, description="子主题")
    difficulty: Optional[int] = Field(None, description="难度 1-5", ge=1, le=5)
    knowledge_points: Optional[List[str]] = Field(None, description="知识点")
    title: Optional[str] = Field(None, description="标题")
    content: Optional[str] = Field(None, description="内容")
    solution: Optional[str] = Field(None, description="答案")
    hints: Optional[List[str]] = Field(None, description="提示")
    options: Optional[List[str]] = Field(None, description="选项")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class VideoCreateRequest(BaseModel):
    """新增视频请求"""
    platform: str = Field(..., description="平台，如 bilibili / youtube")
    title: str = Field(..., description="视频标题")
    topic: str = Field(..., description="主题/知识点")
    difficulty: int = Field(3, description="难度 1-5", ge=1, le=5)
    duration_sec: int = Field(0, description="时长（秒）")
    url: str = Field("", description="视频链接")
    knowledge_points: List[str] = Field(default_factory=list, description="知识点列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class VideoUpdateRequest(BaseModel):
    """更新视频请求（所有字段可选）"""
    platform: Optional[str] = Field(None, description="平台")
    title: Optional[str] = Field(None, description="标题")
    topic: Optional[str] = Field(None, description="主题")
    difficulty: Optional[int] = Field(None, description="难度 1-5", ge=1, le=5)
    duration_sec: Optional[int] = Field(None, description="时长（秒）")
    url: Optional[str] = Field(None, description="链接")
    knowledge_points: Optional[List[str]] = Field(None, description="知识点")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ==================== API 路由 ====================
# ★★★ 注意：静态路径（/reset、/schema）必须定义在动态路径（/{category}）之前 ★★★

@manager_router.get("/weights", summary="查看全部权重配置")
async def get_all_weights():
    """获取当前所有可调权重的完整配置"""
    try:
        weights = get_weights()
        return {
            "success": True,
            "data": weights,
            "categories": list(weights.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取权重配置失败: {str(e)}")


@manager_router.get("/weights/schema", summary="获取权重配置结构说明")
async def get_weights_schema():
    """获取权重配置的完整结构说明（含分类描述和默认值）"""
    try:
        schema = get_weight_schema()
        return {
            "success": True,
            "data": schema
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取权重结构失败: {str(e)}")


@manager_router.post("/weights/reset", summary="重置权重为默认值")
async def reset_weights_endpoint(request: WeightResetRequest):
    """
    重置权重配置为系统默认值

    - 不传 category: 重置全部
    - 传 category:   重置指定分类
    """
    try:
        result = reset_weights(request.category)
        msg = "权重已全部重置为默认值"
        if request.category:
            msg = f"权重 '{request.category}' 已重置为默认值"
        return {
            "success": True,
            "message": msg,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置权重失败: {str(e)}")


@manager_router.get("/weights/{category}", summary="查看指定分类权重")
async def get_category_weights(category: str):
    """
    获取指定分类的权重配置

    可选分类:
    - attention_tracker   : 沉浸信号分权重
    - emotion_state_mapper: 情绪影响权重
    - attention_bridge    : 综合专注度评分权重
    - gaze_detector       : 瞌睡检测权重
    """
    valid_categories = ["attention_tracker", "emotion_state_mapper", "attention_bridge", "gaze_detector"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"无效的分类: '{category}'，可选: {valid_categories}"
        )

    try:
        weights = get_weights(category)
        return {
            "success": True,
            "category": category,
            "data": weights
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取权重失败: {str(e)}")


@manager_router.post("/weights/{category}", summary="更新指定分类权重")
async def update_category_weights(category: str, request: WeightUpdateRequest):
    """
    更新指定分类的权重配置

    支持嵌套更新，只需传入要修改的部分即可。
    例如更新注视专注度权重：
    ```json
    {
        "updates": {
            "immersion_weights": {
                "focus_score": 0.5,
                "distraction_penalty": 0.2
            }
        }
    }
    ```
    """
    valid_categories = ["attention_tracker", "emotion_state_mapper", "attention_bridge", "gaze_detector"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"无效的分类: '{category}'，可选: {valid_categories}"
        )

    try:
        result = update_weights(category, request.updates)
        return {
            "success": True,
            "message": f"权重 '{category}' 已更新",
            "category": category,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新权重失败: {str(e)}")


# ==================== 全局排行榜权重管理 API ====================

class GlobalRankingWeightsRequest(BaseModel):
    """全局排行榜权重更新请求"""
    coding_score: float = Field(0.30, ge=0, le=1, description="编程能力分权重")
    accuracy_score: float = Field(0.25, ge=0, le=1, description="准确率分权重")
    learning_time_score: float = Field(0.15, ge=0, le=1, description="学习时长分权重")
    problem_count_score: float = Field(0.15, ge=0, le=1, description="做题数量分权重")
    overall_feature_score: float = Field(0.15, ge=0, le=1, description="综合特征分权重")


@manager_router.get("/global-ranking/weights", summary="查看全局排行榜权重")
async def get_global_ranking_weights():
    """获取全局用户排行榜的权重配置"""
    try:
        from services.global_ranking_service import GlobalRankingService
        
        service = GlobalRankingService()
        weights = service.get_weights()
        
        return {
            "success": True,
            "data": weights,
            "description": {
                "coding_score": "编程能力分权重（所有编程题提交的平均分）",
                "accuracy_score": "准确率分权重（Accepted提交数/总提交数）",
                "learning_time_score": "学习时长分权重（基于time_management维度）",
                "problem_count_score": "做题数量分权重（非线性计算，边际递减）",
                "overall_feature_score": "综合特征分权重（8维度特征的overall_score）"
            },
            "formula": "综合分数 = w1×编程能力分 + w2×准确率分 + w3×学习时长分 + w4×做题数量分 + w5×综合特征分"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取排行榜权重失败: {str(e)}")


@manager_router.post("/global-ranking/weights", summary="更新全局排行榜权重")
async def update_global_ranking_weights(request: GlobalRankingWeightsRequest):
    """
    更新全局用户排行榜的权重配置
    
    注意: 权重总和必须为1.0
    """
    try:
        from services.global_ranking_service import GlobalRankingService
        
        weights = {
            "coding_score": request.coding_score,
            "accuracy_score": request.accuracy_score,
            "learning_time_score": request.learning_time_score,
            "problem_count_score": request.problem_count_score,
            "overall_feature_score": request.overall_feature_score
        }
        
        service = GlobalRankingService(weights=weights)
        
        return {
            "success": True,
            "message": "全局排行榜权重配置更新成功",
            "data": service.get_weights()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新排行榜权重失败: {str(e)}")


# ==================== 题库管理 API ====================

@manager_router.get("/questions", summary="题库列表（分页）")
async def list_questions(
    topic: Optional[str] = Query(None, description="主题筛选"),
    difficulty: Optional[int] = Query(None, description="难度 1-5"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100),
    order_by: str = Query("created_at DESC", description="排序")
):
    """分页获取题库列表"""
    try:
        result = _qdb.list_questions(topic, difficulty, keyword, page, page_size, order_by)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取题库列表失败: {str(e)}")


@manager_router.get("/questions/stats", summary="题库统计")
async def question_stats():
    """获取题库统计信息（总数、按主题分布、按难度分布）"""
    try:
        topics = _qdb.get_question_topics()
        total = _qdb.count_questions()
        diff_dist = {}
        for d in range(1, 6):
            diff_dist[str(d)] = _qdb.count_questions(difficulty=d)
        topic_dist = {}
        for t in topics:
            topic_dist[t] = _qdb.count_questions(topic=t)
        return {
            "success": True,
            "data": {
                "total": total,
                "topics": topics,
                "difficulty_distribution": diff_dist,
                "topic_distribution": topic_dist
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取题库统计失败: {str(e)}")


@manager_router.get("/questions/topics", summary="所有知识点")
async def question_topics():
    """获取题库中所有知识点列表"""
    try:
        topics = _qdb.get_question_topics()
        return {"success": True, "data": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识点列表失败: {str(e)}")


@manager_router.get("/questions/{qid}", summary="题目详情")
async def get_question_detail(qid: str):
    """获取单道题目的完整详情"""
    try:
        q = _qdb.get_question(qid)
        if not q:
            raise HTTPException(status_code=404, detail=f"题目不存在: {qid}")
        return {"success": True, "data": q}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取题目详情失败: {str(e)}")


@manager_router.post("/questions", summary="新增题目")
async def create_question(req: QuestionCreateRequest):
    """向题库中添加一道新题目"""
    try:
        qid = _qdb.add_question(
            topic=req.topic,
            sub_topic=req.sub_topic or "",
            difficulty=req.difficulty,
            knowledge_points=req.knowledge_points,
            content=req.content,
            solution=req.solution,
            hints=req.hints,
            metadata=req.metadata,
            title=req.title,
            options=req.options
        )
        return {"success": True, "message": "题目已创建", "data": {"id": qid}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建题目失败: {str(e)}")


@manager_router.put("/questions/{qid}", summary="更新题目")
async def update_question(qid: str, req: QuestionUpdateRequest):
    """更新指定题目的字段（仅传入的字段会被修改）"""
    try:
        kwargs = {k: v for k, v in req.model_dump(exclude_none=True).items()}
        if not kwargs:
            raise HTTPException(status_code=400, detail="未传入任何要更新的字段")
        ok = _qdb.update_question(qid, **kwargs)
        if not ok:
            raise HTTPException(status_code=404, detail=f"题目不存在: {qid}")
        updated = _qdb.get_question(qid)
        return {"success": True, "message": "题目已更新", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新题目失败: {str(e)}")


@manager_router.delete("/questions/{qid}", summary="删除题目")
async def delete_question(qid: str):
    """从题库中永久删除指定题目"""
    try:
        ok = _qdb.delete_question(qid)
        if not ok:
            raise HTTPException(status_code=404, detail=f"题目不存在: {qid}")
        return {"success": True, "message": f"题目 {qid} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除题目失败: {str(e)}")


# ==================== 理论题管理 API ====================

@manager_router.get("/theory-questions", summary="理论题列表（分页）")
async def list_theory_questions(
    topic: Optional[str] = Query(None, description="主题筛选"),
    difficulty: Optional[int] = Query(None, description="难度 1-5"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100)
):
    try:
        result = _qdb.list_questions(topic, difficulty, keyword, page, page_size,
                                     question_type='theory')
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取理论题列表失败: {str(e)}")


@manager_router.get("/theory-questions/stats", summary="理论题统计")
async def theory_question_stats():
    try:
        topics = _qdb.get_question_topics()
        total = _qdb.count_questions(question_type='theory')
        return {"success": True, "data": {"total": total, "topics": topics}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取理论题统计失败: {str(e)}")


# ==================== 编程题管理 API ====================

@manager_router.get("/practice-questions", summary="编程题列表（分页）")
async def list_practice_questions(
    topic: Optional[str] = Query(None, description="主题筛选"),
    difficulty: Optional[int] = Query(None, description="难度 1-5"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100)
):
    try:
        result = _qdb.list_questions(topic, difficulty, keyword, page, page_size,
                                     question_type='practice')
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取编程题列表失败: {str(e)}")


@manager_router.get("/practice-questions/stats", summary="编程题统计")
async def practice_question_stats():
    try:
        topics = _qdb.get_question_topics()
        total = _qdb.count_questions(question_type='practice')
        return {"success": True, "data": {"total": total, "topics": topics}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取编程题统计失败: {str(e)}")


# ==================== 视频管理 API ====================

@manager_router.get("/videos", summary="视频列表（分页）")
async def list_videos(
    topic: Optional[str] = Query(None, description="主题筛选"),
    difficulty: Optional[int] = Query(None, description="难度 1-5"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100)
):
    try:
        result = _qdb.list_videos(topic, difficulty, platform, keyword, page, page_size)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视频列表失败: {str(e)}")


@manager_router.get("/videos/stats", summary="视频统计")
async def video_stats():
    try:
        total = _qdb.count_videos()
        topics = _qdb.get_video_topics()
        return {"success": True, "data": {"total": total, "topics": topics}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视频统计失败: {str(e)}")


@manager_router.get("/videos/topics", summary="视频主题列表")
async def video_topics():
    try:
        topics = _qdb.get_video_topics()
        return {"success": True, "data": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视频主题失败: {str(e)}")


@manager_router.get("/videos/{vid}", summary="视频详情")
async def get_video_detail(vid: str):
    try:
        v = _qdb.get_video(vid)
        if not v:
            raise HTTPException(status_code=404, detail=f"视频不存在: {vid}")
        return {"success": True, "data": v}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视频详情失败: {str(e)}")


@manager_router.post("/videos", summary="新增视频")
async def create_video(req: VideoCreateRequest):
    try:
        vid = _qdb.add_video(
            platform=req.platform, title=req.title, topic=req.topic,
            difficulty=req.difficulty, duration_sec=req.duration_sec,
            url=req.url, knowledge_points=req.knowledge_points,
            metadata=req.metadata
        )
        return {"success": True, "message": "视频已创建", "data": {"id": vid}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建视频失败: {str(e)}")


@manager_router.put("/videos/{vid}", summary="更新视频")
async def update_video(vid: str, req: VideoUpdateRequest):
    try:
        kwargs = {k: v for k, v in req.model_dump(exclude_none=True).items()}
        if not kwargs:
            raise HTTPException(status_code=400, detail="未传入任何要更新的字段")
        ok = _qdb.update_video(vid, **kwargs)
        if not ok:
            raise HTTPException(status_code=404, detail=f"视频不存在: {vid}")
        updated = _qdb.get_video(vid)
        return {"success": True, "message": "视频已更新", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新视频失败: {str(e)}")


@manager_router.delete("/videos/{vid}", summary="删除视频")
async def delete_video(vid: str):
    try:
        ok = _qdb.delete_video(vid)
        if not ok:
            raise HTTPException(status_code=404, detail=f"视频不存在: {vid}")
        return {"success": True, "message": f"视频 {vid} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除视频失败: {str(e)}")


# ==================== 视频文件管理 API（OSS 存储）====================

# ★★★ 本地目录保留供旧文件向后兼容，新上传全部走 OSS ★★★
_VIDEO_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_knowledge", "video_data")
os.makedirs(_VIDEO_DATA_DIR, exist_ok=True)

_SUPPORTED_VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'}

# OSS 视频对象前缀
_OSS_VIDEO_PREFIX = "video/admin/"


@manager_router.get("/video/files", summary="视频文件列表")
async def list_video_files():
    """列出视频文件（优先从 OSS 获取，OSS 不可用时回退到本地目录）"""
    try:
        from services.oss_storage import list_files as oss_list_files, get_object_url as oss_get_url

        # 尝试从 OSS 获取
        oss_files = oss_list_files(prefix=_OSS_VIDEO_PREFIX, max_keys=200)
        if oss_files:
            files = []
            for f in oss_files:
                url = oss_get_url(f["key"], public=True) or ""
                files.append({
                    "filename": f["filename"],
                    "size": f["size"],
                    "ext": f["ext"],
                    "supported": f["ext"] in _SUPPORTED_VIDEO_EXTS,
                    "modified": f["last_modified"],
                    "url": url,
                    "source": "oss"
                })
            files.sort(key=lambda x: x["modified"], reverse=True)
            return {"success": True, "data": files, "total": len(files), "source": "oss"}
        else:
            raise Exception("OSS 返回为空，回退到本地")
    except Exception as e:
        print(f"  ⚠️ OSS 列表获取失败 ({e})，回退到本地目录")
        try:
            files = []
            for f in os.listdir(_VIDEO_DATA_DIR):
                fp = os.path.join(_VIDEO_DATA_DIR, f)
                if os.path.isfile(fp):
                    ext = os.path.splitext(f)[1].lower()
                    files.append({
                        "filename": f,
                        "size": os.path.getsize(fp),
                        "ext": ext,
                        "supported": ext in _SUPPORTED_VIDEO_EXTS,
                        "modified": os.path.getmtime(fp),
                        "url": f"/video-data/{f}",
                        "source": "local"
                    })
            files.sort(key=lambda x: x["modified"], reverse=True)
            return {"success": True, "data": files, "total": len(files), "source": "local"}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"获取视频文件列表失败: {str(e2)}")


@manager_router.post("/video/upload", summary="上传视频文件")
async def upload_video_file(file: UploadFile = File(...)):
    """上传视频文件到 OSS（支持公网访问）"""
    import tempfile

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _SUPPORTED_VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的视频格式: {ext}，支持的格式: {', '.join(_SUPPORTED_VIDEO_EXTS)}"
        )

    # 先写到临时文件
    loop = asyncio.get_running_loop()
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        content = await file.read()
        await loop.run_in_executor(None, lambda _fd=tmp_fd, _data=content: (lambda f: (f.write(_data), f.close())[0])(os.fdopen(_fd, "wb")))

        # 上传到 OSS
        from services.oss_storage import upload_file, get_public_url

        object_key = upload_file(
            local_path=tmp_path,
            user_id="admin",
            resource_type="video",
            filename=file.filename
        )

        if not object_key:
            raise HTTPException(status_code=500, detail="OSS 上传失败，请检查 OSS 配置")

        # 获取公网访问 URL
        public_url = get_public_url(object_key)

        size_str = f"{len(content)/1024/1024:.1f} MB" if len(content) > 1024*1024 else f"{len(content)/1024:.1f} KB"
        return {
            "success": True,
            "message": f"视频 {file.filename} 上传成功 ({size_str})",
            "data": {
                "filename": file.filename,
                "size": len(content),
                "object_key": object_key,
                "url": public_url
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")
    finally:
        # 清理临时文件
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@manager_router.delete("/video/files/{filename:path}", summary="删除视频文件")
async def delete_video_file(filename: str):
    """从 OSS 删除指定视频文件（同时尝试清理本地旧文件）"""
    from services.oss_storage import list_files as oss_list_files, delete_file as oss_delete_file

    # 先从 OSS 查找匹配的文件
    oss_files = oss_list_files(prefix=_OSS_VIDEO_PREFIX, max_keys=200)
    matched = [f for f in oss_files if f["filename"] == filename]

    deleted_from_oss = False
    for f in matched:
        if oss_delete_file(f["key"]):
            deleted_from_oss = True

    # 兼容清理本地旧文件
    local_path = os.path.normpath(os.path.join(_VIDEO_DATA_DIR, filename))
    deleted_from_local = False
    if local_path.startswith(os.path.normpath(_VIDEO_DATA_DIR)) and os.path.exists(local_path):
        try:
            os.remove(local_path)
            deleted_from_local = True
        except Exception:
            pass

    if not deleted_from_oss and not deleted_from_local:
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {filename}")

    msg_parts = []
    if deleted_from_oss:
        msg_parts.append("OSS")
    if deleted_from_local:
        msg_parts.append("本地")

    return {"success": True, "message": f"视频文件 {filename} 已从{'/'.join(msg_parts)}删除"}


# ==================== Agent 监控 API ====================

@manager_router.get("/agent-monitor/stats", summary="Agent 调用排行与实时状态")
async def get_agent_stats():
    """获取所有 Agent 的调用排行和实时工作状态"""
    try:
        from Agent.agent_monitor import get_agent_stats
        stats = get_agent_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Agent统计失败: {str(e)}")


@manager_router.get("/agent-monitor/history", summary="Agent 最近调用历史")
async def get_agent_history(limit: int = 50):
    """获取最近 N 条 Agent 调用历史"""
    try:
        from Agent.agent_monitor import get_agent_history
        history = get_agent_history(limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Agent历史失败: {str(e)}")


@manager_router.post("/agent-monitor/reset", summary="重置 Agent 统计数据")
async def reset_agent_stats():
    """重置所有 Agent 的调用统计数据"""
    try:
        from Agent.agent_monitor import get_monitor
        get_monitor().reset_stats()
        return {"success": True, "message": "Agent 统计数据已重置"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置失败: {str(e)}")


# ==================== 知识库管理 API ====================

import shutil
from pathlib import Path

_RAG_KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_knowledge")
os.makedirs(_RAG_KNOWLEDGE_DIR, exist_ok=True)

_SUPPORTED_KB_EXTS = {'.md', '.markdown', '.pdf', '.docx', '.doc', '.xmind'}


@manager_router.get("/knowledge/files", summary="知识库文件列表")
async def list_knowledge_files():
    """列出 rag_knowledge 目录下的所有文件"""
    try:
        files = []
        for f in os.listdir(_RAG_KNOWLEDGE_DIR):
            fp = os.path.join(_RAG_KNOWLEDGE_DIR, f)
            if os.path.isfile(fp):
                ext = os.path.splitext(f)[1].lower()
                files.append({
                    "filename": f,
                    "size": os.path.getsize(fp),
                    "ext": ext,
                    "supported": ext in _SUPPORTED_KB_EXTS,
                    "modified": os.path.getmtime(fp)
                })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "data": files, "total": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@manager_router.post("/knowledge/upload", summary="上传知识库文件")
async def upload_knowledge_file(file: UploadFile = File(...)):
    """上传文件到 rag_knowledge 目录"""
    try:
        loop = asyncio.get_running_loop()
        ext = os.path.splitext(file.filename)[1].lower()
        save_path = os.path.join(_RAG_KNOWLEDGE_DIR, file.filename)

        # 防止路径穿越
        if os.path.commonpath([os.path.abspath(save_path), os.path.abspath(_RAG_KNOWLEDGE_DIR)]) != os.path.abspath(_RAG_KNOWLEDGE_DIR):
            raise HTTPException(status_code=400, detail="非法文件名")

        content = await file.read()
        await loop.run_in_executor(None, lambda _p=save_path, _c=content: (lambda f: (f.write(_c), f.close())[0])(open(_p, "wb")))

        return {
            "success": True,
            "message": f"文件 {file.filename} 上传成功 ({(len(content))/1024:.1f} KB)",
            "data": {"filename": file.filename, "size": len(content)}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@manager_router.delete("/knowledge/files/{filename:path}", summary="删除知识库文件")
async def delete_knowledge_file(filename: str):
    """从 rag_knowledge 目录删除指定文件"""
    try:
        loop = asyncio.get_running_loop()
        # 安全校验：防止路径穿越
        safe_path = os.path.normpath(os.path.join(_RAG_KNOWLEDGE_DIR, filename))
        if not safe_path.startswith(os.path.normpath(_RAG_KNOWLEDGE_DIR)):
            raise HTTPException(status_code=400, detail="非法文件名")
        if not os.path.exists(safe_path):
            raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

        await loop.run_in_executor(None, lambda: os.remove(safe_path))
        return {"success": True, "message": f"文件 {filename} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@manager_router.post("/knowledge/sync", summary="同步知识库到向量存储")
async def sync_knowledge_to_vectorstore(
    user_id: str = Form("admin"),
    recreate: bool = Form(False)
):
    """将 rag_knowledge 目录下的文档导入 ChromaDB 向量库"""
    try:
        loop = asyncio.get_running_loop()
        from Agent.children_agent.knowledge_base_agent import KnowledgeBaseAgent
        kb = KnowledgeBaseAgent()

        if recreate:
            # 重建：删除原有 collection 后重新导入
            try:
                import chromadb
                _db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "memory", "knowledge_base_db")
                client = await loop.run_in_executor(None, lambda: chromadb.PersistentClient(path=_db_path))
                coll_name = f"kb_{user_id}"
                try:
                    await loop.run_in_executor(None, lambda: client.delete_collection(coll_name))
                except Exception:
                    pass
            except Exception:
                pass

        result = await kb.import_documents(_RAG_KNOWLEDGE_DIR, user_id)
        return {
            "success": result["status"] == "success",
            "message": result.get("message", ""),
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@manager_router.get("/knowledge/stats", summary="知识库向量库统计")
async def get_knowledge_stats(user_id: str = "admin"):
    """获取 ChromaDB 中知识库的统计信息"""
    try:
        from Agent.children_agent.knowledge_base_agent import KnowledgeBaseAgent
        kb = KnowledgeBaseAgent()
        stats = await kb.get_knowledge_stats(user_id)
        return {"success": stats["status"] == "success", "data": stats}
    except Exception as e:
        # 如果还没有向量库，返回空
        return {"success": True, "data": {"total_chunks": 0, "message": "知识库为空"}}


# ==================== 管理助手 API ====================

from pydantic import BaseModel

class HelperChatRequest(BaseModel):
    message: str = Field(..., description="管理员输入的消息")


@manager_router.post("/helper/chat", summary="管理助手对话")
async def helper_chat(request: HelperChatRequest):
    """
    与管理助手对话，支持自然语言操作管理端功能。
    返回 SSE 流式响应，包含思考过程和执行结果。
    """
    from Agent.admin_helper_agent import get_helper_agent
    from fastapi.responses import StreamingResponse

    agent = get_helper_agent()

    async def event_stream():
        try:
            async for event in agent.chat(request.message):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

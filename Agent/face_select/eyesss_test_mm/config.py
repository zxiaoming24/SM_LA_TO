"""
config.py - 综合分心检测系统配置
包含大模型API配置、检测参数、提示词等
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


# ==================== 大模型API配置 ====================
class LLMConfig:
    """大模型API配置"""
    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-v4-flash"
    
    # 通义千问 API配置（兼容 OpenAI 格式）
    QWEN_API_KEY = os.getenv("QWEN_API_KEY")
    QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL = "qwen-plus"  # 也可用 qwen-turbo
    
    # 当前使用的模型
    ACTIVE_MODEL = "deepseek"  # deepseek, moonshot, qwen
    
    # 请求配置
    REQUEST_TIMEOUT = 30.0  # 请求超时时间（秒）
    TEMPERATURE = 0.3  # 温度（越低越确定）
    MAX_TOKENS = 500  # 最大输出token数


# ==================== 视线检测配置 ====================
class GazeConfig:
    """MediaPipe 虹膜检测配置"""
    ENABLE_GAZE_DETECTION = True  # 是否启用视线检测
    
    # MediaPipe 参数
    MAX_NUM_FACES = 1  # 最大人脸数
    REFINE_LANDMARKS = True  # 启用虹膜关键点
    MIN_DETECTION_CONFIDENCE = 0.5
    MIN_TRACKING_CONFIDENCE = 0.5
    
    # 眨眼检测参数
    EAR_THRESHOLD = 0.21  # 眼睛纵横比阈值
    EAR_CONSECUTIVE_FRAMES = 3  # 连续多少帧判定为眨眼
    
    # 视线方向阈值（归一化到眼睛宽度比例）
    GAZE_X_THRESHOLD = 0.15  # 左右偏移阈值
    GAZE_Y_THRESHOLD = 0.12  # 上下偏移阈值
    
    # 注意力判定参数
    HIGH_ATTENTION_THRESHOLD = 80  # 高注意力阈值
    LOW_ATTENTION_THRESHOLD = 50  # 低注意力阈值


# ==================== 物品检测配置 ====================
class ObjectConfig:
    """YOLOv8 物品检测配置"""
    ENABLE_OBJECT_DETECTION = True  # 是否启用物品检测
    
    # 模型配置 - 使用small模型平衡速度和精度
    MODEL_PATH = "yolov8s.pt"  # 从 nano 升级到 small，mAP 提升 ~7.6%
    CONFIDENCE_THRESHOLD = 0.3  # 稍微提高阈值减少误检
    
    # 检测间隔（跳帧处理）
    DETECTION_INTERVAL = 2  # 每2帧检测一次

    # 目标追踪配置
    ENABLE_TRACKING = True  # 是否启用 ByteTrack 追踪
    TRACKER_CONFIG = "bytetrack.yaml"  # 追踪器配置（ultralytics 内置）
    
    # COCO数据集类别ID
    PHONE_CLASS_ID = 67  # 手机
    BOOK_CLASS_ID = 73  # 书
    CUP_CLASS_ID = 41  # 杯子
    BOTTLE_CLASS_ID = 39  # 瓶子
    LAPTOP_CLASS_ID = 63  # 笔记本电脑
    
    # 分心物品列表
    DISTRACTION_OBJECTS = {
        "phone": {"id": 67, "name": "手机", "severity": "high"},
        "laptop": {"id": 63, "name": "笔记本电脑", "severity": "medium"},
    }
    
    # 状态物品列表
    STATE_OBJECTS = {
        "book": {"id": 73, "name": "书", "state": "学习中"},
        "cup": {"id": 41, "name": "杯子", "state": "口渴了"},
        "bottle": {"id": 39, "name": "瓶子", "state": "口渴了"},
    }


# ==================== 综合检测配置 ====================
class DistractionConfig:
    """综合分心检测配置"""
    # 检测频率
    DETECTION_INTERVAL = 5  # 每N帧进行一次检测
    ANALYSIS_INTERVAL = 30  # 每N帧进行一次大模型分析
    
    # 时序统计窗口
    TIME_WINDOW_SECONDS = 30  # 统计最近N秒的数据
    
    # 分心判定阈值
    CONTINUOUS_DISTRACTION_FRAMES = 10  # 连续N帧检测到分心物品
    GAZE_AWAY_THRESHOLD = 0.3  # 视线偏离阈值
    
    # 大模型分析配置
    ENABLE_LLM_ANALYSIS = True  # 是否启用大模型分析
    LLM_ANALYSIS_INTERVAL = 10  # 每N秒进行一次大模型分析
    
    # ========== 行为级分心规则配置 ==========
    
    # 规则1: 玩手机 - 检测到手机 + 视线指向手机区域或低头
    PHONE_GAZE_PROXIMITY_THRESHOLD = 0.15  # 视线与手机中心的归一化距离阈值
    LOOK_DOWN_PITCH_THRESHOLD = 15  # 低头角度阈值（度），俯仰角超过此值判定为低头
    
    # 规则2: 长时间闭眼 - EAR < 阈值持续超过设定时间
    LONG_EYE_CLOSE_EAR_THRESHOLD = 0.18  # 闭眼判定阈值
    LONG_EYE_CLOSE_DURATION = 1.0  # 持续闭眼判定时长（秒）
    
    # 规则3: 视线离开主屏幕 - 注视点超出屏幕区域超过设定时间
    SCREEN_BOUNDARY_X_MIN = 0.2   # 屏幕左边界（归一化坐标）
    SCREEN_BOUNDARY_X_MAX = 0.8   # 屏幕右边界
    SCREEN_BOUNDARY_Y_MIN = 0.15  # 屏幕上边界
    SCREEN_BOUNDARY_Y_MAX = 0.85  # 屏幕下边界
    GAZE_OUT_OF_BOUNDS_DURATION = 2.0  # 视线离屏判定时长（秒）
    
    # 规则4: 头部大幅度偏转 - 头部欧拉角超出正常范围
    HEAD_YAW_THRESHOLD = 25  # 水平偏转角阈值（度），左右转头
    HEAD_PITCH_THRESHOLD = 20  # 俯仰角阈值（度），低头/仰头
    HEAD_POSE_DURATION = 1.0  # 头部偏转持续判定时长（秒）


# ==================== 嘴部/瞌睡检测配置 ====================
class MouthConfig:
    """嘴部检测和瞌睡检测配置"""
    
    # 打哈欠检测
    YAWN_MAR_THRESHOLD = 0.5  # 嘴部纵横比阈值（正常闭合0.1~0.2，张嘴>0.5）
    YAWN_CONSECUTIVE_FRAMES = 10  # 连续多少帧张嘴判定为打哈欠（约0.3秒）
    
    # 瞌睡检测
    DROWSINESS_SCORE_THRESHOLD = 0.45  # 瞌睡综合分数阈值（0~1）


# ==================== 大模型提示词 ====================
class PromptConfig:
    """大模型提示词配置"""
    
    # 分心检测系统提示词
    SYSTEM_PROMPT = """你是一个专业的学习注意力分析专家。你的任务是根据学生的实时行为数据（包括行为规则判定结果、头部姿态、嘴部状态、视线、物品检测等），综合判断其是否分心，并给出原因和建议。

规则说明：
- 规则1（玩手机）：检测到手机出现在视野中 → 直接判定为分心
- 规则2（长时间闭眼）：眼睛纵横比EAR<0.18持续超过1秒 → 判定为分心
- 规则3（视线离开屏幕）：注视点超出屏幕边界超过2秒 → 判定为分心
- 规则4（头部偏转）：头部水平偏转>25°或俯仰>20°持续超过1秒 → 判定为分心
- 规则5（打哈欠）：嘴部纵横比MAR>0.5并持续较长时间 → 判定为分心（困倦信号）
- 规则6（打瞌睡）：头部反复点头、眨眼异常、打哈欠等综合信号 → 判定为分心

请严格按照以下JSON格式输出，不要输出其他内容：
{
    "is_distracted": true/false,
    "distraction_level": "none/low/medium/high",
    "confidence": 0.0-1.0,
    "reasons": ["原因1", "原因2"],
    "suggestions": ["建议1", "建议2"],
    "attention_score": 0-100
}
"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = """请分析以下学生学习行为数据，判断是否分心：

【行为规则判定结果】
- 是否有分心行为: {behavior_distracted}
- 行为规则检测到的原因: {behavior_reasons}
- 建议: {behavior_suggestions}

【头部姿态】
- 水平偏转角(yaw): {head_yaw:.1f}°（正=右, 负=左）
- 俯仰角(pitch): {head_pitch:.1f}°（正=低头, 负=仰头）
- 翻滚角(roll): {head_roll:.1f}°

【嘴部/瞌睡状态】
- 嘴部纵横比(MAR): {mouth_mar:.3f}
- 是否打哈欠: {is_yawning}
- 哈欠总次数: {yawn_count}
- 是否瞌睡: {is_drowsy}
- 瞌睡分数: {drowsiness_score:.2f}
- 点头强度: {nodding_intensity:.2f}

【视线数据】
- 视线方向: {gaze_direction}
- 视线偏移: X={gaze_offset_x:.3f}, Y={gaze_offset_y:.3f}
- 眨眼频率: {blink_rate:.1f} 次/分钟
- 注意力等级: {attention_level}

【情绪状态】
- 情绪: {emotion}

【物品检测】
- 检测到的物品: {detected_objects}
- 分心物品: {distraction_objects}

【时序统计】
- 当前状态持续时间: {duration:.1f} 秒
- 最近30秒视线变化: {gaze_change}
- 最近30秒检测到的物品: {recent_objects}

请基于以上数据和行为规则结果进行综合分析，输出JSON格式判定结果。
"""


# ==================== 情绪分析配置 ====================
class EmotionConfig:
    """YOLO 情绪分析配置"""
    ENABLE_EMOTION_DETECTION = False  # 是否启用情绪分析（当前模型版本不兼容，默认关闭）
    
    # 模型配置（相对路径：eyesss_test_mm 上级 face_select 目录下的 best-yolo.pt）
    MODEL_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'best-yolo.pt'
    )
    CONFIDENCE_THRESHOLD = 0.5  # 检测置信度阈值
    
    # 检测间隔（跳帧处理）
    DETECTION_INTERVAL = 3  # 每3帧检测一次
    
    # 情绪类别
    CLASS_NAMES = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']
    
    # 情绪对应的状态
    EMOTION_STATE_MAP = {
        'angry': {'state': '烦躁', 'attention_impact': -20},
        'disgust': {'state': '厌恶', 'attention_impact': -15},
        'fear': {'state': '害怕', 'attention_impact': -25},
        'happy': {'state': '开心', 'attention_impact': 10},
        'neutral': {'state': '平静', 'attention_impact': 0},
        'sad': {'state': '沮丧', 'attention_impact': -15},
        'surprise': {'state': '惊讶', 'attention_impact': -10},
    }


# ==================== 区域划分配置 ====================
class RegionConfig:
    """屏幕区域划分配置（在线教育场景）"""
    
    # 区域定义
    REGIONS = {
        "video": {
            "name": "视频区",
            "x_range": (0.0, 0.35),
            "interest": 80,
            "description": "正在观看视频/PPT"
        },
        "content": {
            "name": "课程内容",
            "x_range": (0.35, 0.7),
            "interest": 90,
            "description": "正在学习课程内容"
        },
        "interaction": {
            "name": "互动区",
            "x_range": (0.7, 1.0),
            "interest": 60,
            "description": "正在互动/聊天"
        },
        "title": {
            "name": "标题栏",
            "y_range": (0.0, 0.12),
            "interest": 30,
            "description": "正在查看标题"
        },
        "control": {
            "name": "控制栏",
            "y_range": (0.85, 1.0),
            "interest": 40,
            "description": "正在操作控制栏"
        }
    }

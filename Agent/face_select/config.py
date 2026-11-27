"""配置文件
包含视频监控系统的所有可配置参数
"""

from dotenv import load_dotenv
import os

# 加载 .env 文件
load_dotenv()

# 获取环境变量
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")

from typing import Dict, Any


# 数据库配置
class DatabaseConfig:
    """数据库连接配置"""
    ENABLE_DATABASE = True  # 是否启用数据库
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_NAME = os.getenv("DB_NAME", "student_learning")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))


# API配置
class APIConfig:
    # Moonshot语言模型 API配置，这里可以换成其他语言模型或者本地部署的内容
    MOONSHOT_API_KEY = MOONSHOT_API_KEY
    MOONSHOT_API_URL = "https://api.moonshot.cn/v1/chat/completions"
    MOONSHOT_MODEL = "moonshot-v1-8k"
    
    # API请求配置
    REQUEST_TIMEOUT = 60.0 # 请求超时时间（秒）
    TEMPERATURE = 0.5 # 温度
    TOP_P = 0.01 
    TOP_K = 20
    REPETITION_PENALTY = 1.05


# 坐姿分析配置
class SittingPostureConfig:
    # 坐姿分析模块配置
    ENABLE_SITTING_POSTURE = False  # 是否启用坐姿分析
    SITTING_POSTURE_FRAMES = 10  # 每轮分析的帧数（1-10）这个是指说缓存区中抽几张图片进行分析

# 多模态分析配置
class MultiModalConfig:
    # 多模态分析模块配置
    ENABLE_MULTI_MODAL = False  # 是否启用多模态分析（默认开启）
    ENABLE_FACE_RECOGNITION = False  # 是否启用人脸识别
    MULTI_MODAL_MODEL = "qwen3-vl-flash"  # 多模态模型名称
    QWEN_API_KEY = QWEN_API_KEY
    MULTI_MODAL_QUEUE_SIZE = 10  # 队列大小（满则触发分析，实时流默认值）
    MULTI_MODAL_FRAME_INTERVAL = 60  # 多模态分析帧间隔（每 N 帧分析一次）
    MULTI_MODAL_FRAMES_PER_MINUTE = 10  # 上传视频每分钟抽取帧数
    MULTI_MODAL_REQUEST_INTERVAL_MINUTES = 2  # 上传视频每N分钟触发一次分析
    MULTI_MODAL_PROMPT = """
    你是一个专业的课堂行为分析专家，你的任务是客观、准确地描述视频中的所有行为和特征。
    请仅提供客观描述，不要做任何主观分析或判断。

    请分析以下视频并描述学生的具体学习行为特征：

    1. 面部表情识别：
    - 面部表情（专注、困惑、疲惫、兴奋等）
    - 眼神接触特征（是否盯着屏幕/书本）

    2. 肢体语言分析：
    - 坐姿（端正、趴桌子、后仰、歪斜等）
    - 手部动作（记笔记、托腮、转笔、玩手机等）
    - 头部动作（点头、摇头、低头看书、抬头听讲等）
    - 肩膀姿态（放松、紧绷、耸肩等）

    3. 环境特征：
    - 着装描述
    - 学习环境（书桌、教室背景等）
    - 光线条件

    输出格式要求：
    请按时间顺序描述观察到的行为，每种类型的行为单独成行，使用简洁的语言。
    输出示例：
    - 学生面带微笑，眼神专注于课本
    - 坐姿端正，偶尔用手势辅助记忆
    - 穿着校服，背景为整洁的书房
    """
    MULTI_MODAL_ANOMALY = """
    请根据输入的「学生学习行为描述」，按照以下要求完成任务：
1. 核心目标：以极度严苛的标准识别学生在「眼神交流」「坐姿」「手部动作」3个维度存在问题的行为表现，并严格依据对应表判断背后反映的学习状态（如走神、焦虑、不专注等）。
2. 执行规则：
   - 必做：严格对照以下预设的行为-状态对应表逐字匹配进行判断，仅分析存在问题的行为；不得遗漏任何符合对应表的问题行为。
   - 禁止：不得主观臆断未在描述中提及的行为，仅基于输入的「学生学习行为描述」原文信息分析。
3. 行为-状态对应表（需严格逐字匹配，不得放宽标准）：
   - 眼神交流：
     - 回避视线/不看屏幕 → 缺乏安全感、走神、注意力分散；
   - 坐姿：
     - 弯腰驼背 → 精神萎靡、缺乏活力、学习态度消极；
     - 抖腿 → 随意、焦虑、不耐烦，可能影响学习效率；
     - 翘二郎腿 → 显得随意、不够严肃、有防御感；
     - 身体后仰 → 可能显得懒散、疏离或过于放松；
     - 趴桌子 → 极度疲惫、厌学情绪；
   - 手部动作：
     - 双手夹在两腿之间 → 缺乏自信、紧张、寻求安全感；
     - 双手交叉放于胸前 → 防御心强、抗拒、封闭；
     - 挠头 → 着急、焦虑、思考困难；
     - 摸鼻子 → 可能紧张，或在特定情境下关联不诚实；
     - 把玩物品/转笔 → 紧张、焦虑，或心不在焉；
     - 拽衣角 → 紧张、不适应、显得不成熟；
     - 不停看表/看手机 → 制造压迫感，显得不耐烦或急于结束学习；
4. 输出要求：若存在问题行为，输出一个包含"problem_behaviors"键的JSON对象，其值为问题行为数组，每个数组元素需包含「behavior_dimension（行为维度）」「specific_behavior（具体行为）」「corresponding_state（对应状态）」「original_basis（原文依据）」四个字段；若不存在问题行为，则输出{"problem_behaviors": "无"}。
5. 输出格式示例：
{"problem_behaviors": [
  {
    "behavior_dimension": "坐姿",
    "specific_behavior": "抖腿",
    "corresponding_state": "随意、焦虑、不耐烦，可能影响学习效率",
    "original_basis": "学生在学习过程中全程有轻微抖腿的动作"
  },
  {
    "behavior_dimension": "手部动作",
    "specific_behavior": "把玩物品",
    "corresponding_state": "紧张、焦虑，或心不在焉",
    "original_basis": "学生一直把玩手中的文具"
  }
]}

    """
# 视线/专注度检测配置
class GazeConfig:
    """MediaPipe 虹膜检测与专注度分析配置"""
    ENABLE_GAZE_DETECTION = True  # 是否启用视线检测（默认关闭，兼容旧版本）
    ENABLE_ATTENTION_TRACKING = True  # 是否启用专注度追踪（写入 AttentionProfile）

    # MediaPipe 参数
    MAX_NUM_FACES = 1
    REFINE_LANDMARKS = True
    MIN_DETECTION_CONFIDENCE = 0.5
    MIN_TRACKING_CONFIDENCE = 0.5

    # 眨眼检测参数
    EAR_THRESHOLD = 0.21
    EAR_CONSECUTIVE_FRAMES = 3

    # 视线方向阈值（归一化到眼睛宽度比例）
    GAZE_X_THRESHOLD = 0.15
    GAZE_Y_THRESHOLD = 0.12

    # 注意力判定参数
    HIGH_ATTENTION_THRESHOLD = 80
    LOW_ATTENTION_THRESHOLD = 50

    # 专注度追踪帧间隔（每 N 帧记录一次 gaze 数据）
    ATTENTION_RECORD_INTERVAL = 10  # 与 EMOTION_FRAMES 保持一致，同步触发


# 嘴部检测和瞌睡检测配置
class MouthConfig:
    """嘴部检测和瞌睡检测配置（供 GazeDetector 使用）"""

    # 打哈欠检测
    YAWN_MAR_THRESHOLD = 0.5  # 嘴部纵横比阈值（正常闭合0.1~0.2，张嘴>0.5）
    YAWN_CONSECUTIVE_FRAMES = 10  # 连续多少帧张嘴判定为打哈欠（约0.3秒）

    # 瞌睡检测
    DROWSINESS_SCORE_THRESHOLD = 0.45  # 瞌睡综合分数阈值（0~1）


# 情绪分析配置
class EmotionConfig:
    # 情绪分析模块配置
    ENABLE_EMOTION = True  # 是否启用情绪分析
    EMOTION_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'best-yolo.pt')  # YOLO模型路径
    EMOTION_CONFIDENCE = 0.5  # 检测置信度阈值
    EMOTION_CLASS_NAMES = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']  # 情绪类别
    EMOTION_FRAMES = 10  # 每轮分析的帧数（1-10）这个是指说缓存区中抽几张图片进行分析

# 人脸识别配置
class FaceRecognitionConfig:
    # 人脸识别模块配置
    ENABLE_FACE_RECOGNITION = False  # 是否启用人脸识别
    FACE_RECOGNITION_FRAMES = 20  # 每轮分析的帧数
    FACE_DATABASE_PATH = "face_recognition/data/features_all.csv"  # 人脸特征数据库路径
    FACE_DETECTION_THRESHOLD = 0.4  # 人脸识别阈值（欧氏距离）

# 异常检测配置
class AnomalyDetectionConfig:
    # 异常检测模块配置
    # 坐姿异常检测配置
    SITTING_POSTURE_ANOMALIES = {
        "head": ["低头", "歪脖", "伸脖子"],  # 头部异常状态
        "hunch": ["塌腰"],  # 驼背异常状态
        "cross_leg": ["跷二郎腿"]  # 腿部异常状态
    }

    # 情绪异常检测配置
    EMOTION_ANOMALIES = ["angry", "fear", "disgust"]  # 异常情绪列表
    EMOTION_ANOMALY_CONFIDENCE_THRESHOLD = 0.55  # 情绪异常的最小置信度
    

    # 人脸识别异常检测配置
    FACE_RECOGNITION_ANOMALY_ENABLED = True  # 出现多余人脸时才出现的异常（情绪检测结果大于1），是否将未知人员视为异常
    FACE_RECOGNITION_CONFIDENCE_THRESHOLD = 0.6  # 人脸识别异常的最小置信度


def update_config(args:Dict[str, Any]) -> None:
    """使用命令行参数更新配置
    
    Args:
        args: 包含命令行参数的字典
    """

    # 更新API配置
    for key in ['qwen_api_key', 'qwen_api_url', 'qwen_model',
               'moonshot_api_key', 'moonshot_api_url', 'moonshot_model',
               'request_timeout', 'temperature', 'top_p', 'top_k',
               'repetition_penalty']:
        if key in args:
            setattr(APIConfig, key.upper(), args[key])

    # 更新坐姿分析配置
    for key in ['enable_sitting_posture', 'sitting_posture_frames']:
        if key in args:
            setattr(SittingPostureConfig, key.upper(), args[key])

    # 更新多模态分析配置
    for key in ['enable_multi_modal', 'multi_modal_model', 'qwen_api_key', 'enable_face_recognition',
                'multi_modal_frame_interval', 'multi_modal_queue_size', 'multi_modal_prompt',
                'multi_modal_frames_per_minute', 'multi_modal_request_interval_minutes']:
        if key in args:
            setattr(MultiModalConfig, key.upper(), args[key])

    # 更新视线/专注度检测配置
    for key in ['enable_gaze_detection', 'enable_attention_tracking',
                'gaze_x_threshold', 'gaze_y_threshold',
                'attention_record_interval']:
        if key in args:
            setattr(GazeConfig, key.upper(), args[key])

    # 更新情绪分析配置
    for key in ['enable_emotion', 'emotion_model_path', 'emotion_confidence', 'emotion_frames']:
        if key in args:
            setattr(EmotionConfig, key.upper(), args[key])

    # 更新人脸识别配置
    for key in ['enable_face_recognition', 'face_recognition_frames', 'face_database_path', 'face_detection_threshold']:
        if key in args:
            setattr(FaceRecognitionConfig, key.upper(), args[key])

    # 更新异常检测配置
    for key in ['emotion_anomalies', 'emotion_anomaly_confidence_threshold',
               'face_recognition_anomaly_enabled', 'face_recognition_confidence_threshold',
               'multi_modal_anomaly_enabled', 'log_anomaly_details', 'anomaly_person_tracking']:
        if key in args:
            setattr(AnomalyDetectionConfig, key.upper(), args[key])

    # 更新坐姿异常检测配置（特殊处理字典类型的配置）
    if 'sitting_posture_anomalies' in args:
        AnomalyDetectionConfig.SITTING_POSTURE_ANOMALIES.update(args['sitting_posture_anomalies'])




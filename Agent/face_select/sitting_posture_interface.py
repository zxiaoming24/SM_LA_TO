import os.path
import sys

import cv2
import mediapipe as mp
import numpy as np
from joblib import load
from PIL import Image, ImageDraw, ImageFont

from sitting_posture import CrossLeg
from sitting_posture import HunchFront
from sitting_posture import head
from logger import get_logger

import warnings
warnings.filterwarnings('ignore', category=UserWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_HEAD_PATH = os.path.join(SCRIPT_DIR, "sitting_posture", "model3", "model", "ModelHead.pkl")
MODEL_HUNCH_PATH = os.path.join(SCRIPT_DIR, "sitting_posture", "update", "rf_model_Hunch_1.joblib")
MODEL_CROSSLEG_PATH = os.path.join(SCRIPT_DIR, "sitting_posture", "update", "rf_model_CrossLeg_1.joblib")

FONT_PATH = "simsun.ttc"
DEFAULT_TEXT_COLOR = (255, 0, 0)
DEFAULT_TEXT_SIZE = 20
TEXT_POSITIONS = {
    "Head": (30, 100),
    "Hunch": (30, 120),
    "CrossLeg": (30, 140),
}

def cv2AddChineseText(img, text, position, textColor=(0, 255, 0), textSize=30):
    if (isinstance(img, np.ndarray)):  # 判断是否OpenCV图片类型
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    # 创建一个可以在给定图像上绘图的对象
    draw = ImageDraw.Draw(img)
    # 字体的格式
    fontStyle = ImageFont.truetype(FONT_PATH, textSize, encoding="utf-8")
    # 绘制文本
    draw.text(position, text, textColor, font=fontStyle)
    # 转换回OpenCV格式
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


class SittingPosturePredictor:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.drawing = mp.solutions.drawing_utils
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # 加载预训练模型
        self.modelHead = load(MODEL_HEAD_PATH)
        self.modelHunch = load(MODEL_HUNCH_PATH)
        self.modelCrossLeg = load(MODEL_CROSSLEG_PATH)
        self.logger.info("坐姿预测器初始化成功")

    def _draw_pose(self, frame, results):
        self.drawing.draw_landmarks(
            frame,
            results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.drawing.DrawingSpec(
                color=(255, 255, 0), thickness=2, circle_radius=2
            ),
            connection_drawing_spec=self.drawing.DrawingSpec(
                color=(0, 255, 255), thickness=2, circle_radius=2
            ),
        )

    def _get_centroid(self, results, frame_shape):
        if results.pose_landmarks is None:
            return None

        h, w, _ = frame_shape
        nose = results.pose_landmarks.landmark[0]
        cx, cy = int(nose.x * w), int(nose.y * h)
        return [cx, cy]

    def _predict_head(self, frame, threshold=0.8):
        pitch, yaw, roll = head.HeadInfo(frame)
        Headtest = [[pitch, yaw, roll]]
        Headprobs = self.modelHead.predict(Headtest)
        head_prob = self._safe_predict_proba(self.modelHead, Headtest, Headprobs)
        if head_prob is not None and head_prob < threshold:
            sys.stdout.flush()
            return "正常坐姿", Headprobs, head_prob
        if Headprobs == 1 or pitch < -20:
            sys.stdout.flush()
            return "低头", Headprobs, head_prob
        if Headprobs == 2:
            sys.stdout.flush()
            return "歪脖", Headprobs, head_prob
        if Headprobs == 3:
            sys.stdout.flush()
            return "伸脖子", Headprobs, head_prob
        sys.stdout.flush()
        return "正常坐姿", Headprobs, head_prob

    def _predict_hunch(self, keypoints, threshold=0.6):
        distAverage, distShoulder, distMounthToShoulder, distNoseToMounth = HunchFront.HunchInfo(
            keypoints
        )
        Hunchtest = [[distAverage, distShoulder, distMounthToShoulder, distNoseToMounth]]
        Hunchprobs = self.modelHunch.predict(Hunchtest)
        hunch_prob = self._safe_predict_proba(self.modelHunch, Hunchtest, Hunchprobs)
        if hunch_prob is not None and hunch_prob < threshold:
            sys.stdout.flush()
            return "正常坐姿", Hunchprobs, hunch_prob
        if Hunchprobs == 4:
            sys.stdout.flush()
            return "塌腰", Hunchprobs, hunch_prob
        sys.stdout.flush()
        return "正常坐姿", Hunchprobs, hunch_prob

    def _predict_cross_leg(self, keypoints, threshold=0.8):
        (
            crossDot1,
            distance1,
            crossDot2,
            distance2,
            crossDot3,
            distance3,
            distance4,
            crossDot5,
            distance5,
            distance6,
        ) = CrossLeg.CrossLegInfo(keypoints)
        CrossLegtest = [[distance1, distance2, distance3, distance4, distance5, distance6]]
        CrossLegprobs = self.modelCrossLeg.predict(CrossLegtest)
        crossleg_prob = self._safe_predict_proba(self.modelCrossLeg, CrossLegtest, CrossLegprobs)
        if crossleg_prob is not None and crossleg_prob < threshold:
            sys.stdout.flush()
            return "正常坐姿", CrossLegprobs, crossleg_prob
        if CrossLegprobs == 5 or (distance4 < 300 and distance6 < 300):
            sys.stdout.flush()
            return "跷二郎腿", CrossLegprobs, crossleg_prob
        sys.stdout.flush()
        return "正常坐姿", CrossLegprobs, crossleg_prob

    def _safe_predict_proba(self, model, X, pred_label):
        if not hasattr(model, "predict_proba"):
            return None
        try:
            probas = model.predict_proba(X)
        except Exception:
            return None
        if probas is None or len(probas) == 0:
            return None
        try:
            label = int(pred_label[0]) if hasattr(pred_label, "__len__") else int(pred_label)
            classes = getattr(model, "classes_", None)
            if classes is not None:
                class_index = int(np.where(classes == label)[0][0])
            else:
                class_index = max(0, label - 1)
            return float(probas[0][class_index])
        except Exception:
            return None

    def process_frame(self, frame, threshold=0.8):
        result = {}

        # 使用 MediaPipe 模型检测关键点
        results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if results.pose_landmarks is not None:
            keypoints = results.pose_landmarks.landmark
            self._draw_pose(frame, results)
        else:
            keypoints = None

        centroid = self._get_centroid(results, frame.shape)
        if centroid is not None:
            cv2.putText(
                frame,
                "nose",
                (centroid[0], centroid[1]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 0, 0),
                1,
            )

        textHead, Headprobs, head_prob = self._predict_head(frame, threshold)
        head_prob_text = f" ({head_prob:.2f})" if head_prob is not None else ""
        frame = cv2AddChineseText(
            frame,
            f"头部检测:{textHead}{head_prob_text}",
            TEXT_POSITIONS["Head"],
            DEFAULT_TEXT_COLOR,
            DEFAULT_TEXT_SIZE,
        )

        textHunch, Hunchprobs, hunch_prob = self._predict_hunch(keypoints, threshold)
        hunch_prob_text = f" ({hunch_prob:.2f})" if hunch_prob is not None else ""
        frame = cv2AddChineseText(
            frame,
            f"塌腰检测:{textHunch}{hunch_prob_text}",
            TEXT_POSITIONS["Hunch"],
            DEFAULT_TEXT_COLOR,
            DEFAULT_TEXT_SIZE,
        )

        textCrossLeg, CrossLegprobs, crossleg_prob = self._predict_cross_leg(keypoints, threshold)
        crossleg_prob_text = f" ({crossleg_prob:.2f})" if crossleg_prob is not None else ""
        frame = cv2AddChineseText(
            frame,
            f"翘二郎腿检测:{textCrossLeg}{crossleg_prob_text}",
            TEXT_POSITIONS["CrossLeg"],
            DEFAULT_TEXT_COLOR,
            DEFAULT_TEXT_SIZE,
        )

        result = {
            "Hunch": textHunch,
            "Head": textHead,
            "CrossLeg": textCrossLeg,
            "centroid": centroid,
            "keypoints_available": results.pose_landmarks is not None,
        }
        
        # 记录检测结果
        # self.logger.debug(
        #     f"坐姿检测结果 - 头部: {textHead}, 塌腰: {textHunch}, 翘腿: {textCrossLeg}, "
        #     f"关键点检测: {'成功' if results.pose_landmarks is not None else '失败'}"
        # )

        return frame, result


if __name__ == "__main__":

    # 用外设摄像头
    cap = cv2.VideoCapture(0)
    cv2.namedWindow('frame', cv2.WINDOW_NORMAL)
    
    _PREDICTOR = SittingPosturePredictor()
    
    while cap.isOpened():
        # 读取当前帧
        success, frame = cap.read()
        if not success:
            break
        # 显示结果
        cv2.imshow('frame', _PREDICTOR.process_frame(frame,0.6)[0])
        # 按下 'q' 键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 释放资源
    cap.release()
    cv2.destroyAllWindows()

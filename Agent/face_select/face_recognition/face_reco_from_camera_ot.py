# Copyright (C) 2018-2021 coneypo
# SPDX-License-Identifier: MIT

# Author:   coneypo
# Blog:     http://www.cnblogs.com/AdaminXie
# GitHub:   https://github.com/coneypo/Dlib_face_recognition_from_camera
# Mail:     coneypo@foxmail.com

# 利用 OT 人脸追踪, 进行人脸实时识别 / Real-time face detection and recognition via OT for multi faces
# 检测 -> 识别人脸, 新人脸出现 -> 不需要识别, 而是利用质心追踪来判断识别结果 / Do detection -> recognize face, new face -> not do re-recognition
# 人脸进行再识别需要花费大量时间, 这里用 OT 做跟踪 / Do re-recognition for multi faces will cost much time, OT will be used to instead it

import dlib
import numpy as np
import cv2
import os
import pandas as pd
import time
import logging
from typing import List, Dict, Optional, Tuple

# 获取当前脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))
# 切换到脚本所在目录
os.chdir(script_dir)

# Dlib 正向人脸检测器 / Use frontal face detector of Dlib
detector = dlib.get_frontal_face_detector()

# Dlib 人脸 landmark 特征点检测器 / Get face landmarks
predictor = dlib.shape_predictor('data/data_dlib/shape_predictor_68_face_landmarks.dat')

# Dlib Resnet 人脸识别模型, 提取 128D 的特征矢量 / Use Dlib resnet50 model to get 128D face descriptor
face_reco_model = dlib.face_recognition_model_v1("data/data_dlib/dlib_face_recognition_resnet_model_v1.dat")


class Face_Recognizer:
    def __init__(self):
        self.font = cv2.FONT_ITALIC

        # FPS
        self.frame_time = 0
        self.frame_start_time = 0
        self.fps = 0
        self.fps_show = 0
        self.start_time = time.time()

        # cnt for frame
        self.frame_cnt = 0

        # 用来存放所有录入人脸特征的数组 / Save the features of faces in the database
        self.face_features_known_list = []
        # 存储录入人脸名字 / Save the name of faces in the database
        self.face_name_known_list = []

        # 用来存储上一帧和当前帧 ROI 的质心坐标 / List to save centroid positions of ROI in frame N-1 and N
        self.last_frame_face_centroid_list = []
        self.current_frame_face_centroid_list = []

        # 用来存储上一帧和当前帧检测出目标的名字 / List to save names of objects in frame N-1 and N
        self.last_frame_face_name_list = []
        self.current_frame_face_name_list = []

        # 上一帧和当前帧中人脸数的计数器 / cnt for faces in frame N-1 and N
        self.last_frame_face_cnt = 0
        self.current_frame_face_cnt = 0

        # 用来存放进行识别时候对比的欧氏距离 / Save the e-distance for faceX when recognizing
        self.current_frame_face_X_e_distance_list = []

        # 存储当前摄像头中捕获到的所有人脸的坐标名字 / Save the positions and names of current faces captured
        self.current_frame_face_position_list = []
        # 存储当前摄像头中捕获到的人脸特征 / Save the features of people in current frame
        self.current_frame_face_feature_list = []

        # e distance between centroid of ROI in last and current frame
        self.last_current_frame_centroid_e_distance = 0

        # 控制再识别的后续帧数 / Reclassify after 'reclassify_interval' frames
        # 如果识别出 "unknown" 的脸, 将在 reclassify_interval_cnt 计数到 reclassify_interval 后, 对于人脸进行重新识别
        self.reclassify_interval_cnt = 0
        self.reclassify_interval = 10

    # 从 "features_all.csv" 读取录入人脸特征 / Get known faces from "features_all.csv"
    def get_face_database(self):
        if os.path.exists("data/features_all.csv"):
            path_features_known_csv = "data/features_all.csv"
            csv_rd = pd.read_csv(path_features_known_csv, header=None)
            for i in range(csv_rd.shape[0]):
                features_someone_arr = []
                self.face_name_known_list.append(csv_rd.iloc[i][0])
                for j in range(1, 129):
                    if csv_rd.iloc[i][j] == '':
                        features_someone_arr.append('0')
                    else:
                        features_someone_arr.append(csv_rd.iloc[i][j])
                self.face_features_known_list.append(features_someone_arr)
            logging.info("Faces in Database： %d", len(self.face_features_known_list))
            return 1
        else:
            logging.warning("'features_all.csv' not found!")
            logging.warning("Please run 'get_faces_from_camera.py' "
                            "and 'features_extraction_to_csv.py' before 'face_reco_from_camera.py'")
            return 0

    def update_fps(self):
        now = time.time()
        # 每秒刷新 fps / Refresh fps per second
        if str(self.start_time).split(".")[0] != str(now).split(".")[0]:
            self.fps_show = self.fps
        self.start_time = now
        self.frame_time = now - self.frame_start_time
        self.fps = 1.0 / self.frame_time
        self.frame_start_time = now

    @staticmethod
    # 计算两个128D向量间的欧式距离 / Compute the e-distance between two 128D features
    def return_euclidean_distance(feature_1, feature_2):
        feature_1 = np.array(feature_1)
        feature_2 = np.array(feature_2)
        dist = np.sqrt(np.sum(np.square(feature_1 - feature_2)))
        return dist

    # 使用质心追踪来识别人脸 / Use centroid tracker to link face_x in current frame with person_x in last frame
    """
    简单但有效：假设相邻帧间人脸移动距离很小
    保持身份连续性：避免每帧重新识别
    计算高效：O(n²)复杂度，适合人脸数量不多的场景
    """
    def centroid_tracker(self):
        for i in range(len(self.current_frame_face_centroid_list)):
            e_distance_current_frame_person_x_list = []
            # 对于当前帧中的人脸1, 和上一帧中的 人脸1/2/3/4/.. 进行欧氏距离计算 / For object 1 in current_frame, compute e-distance with object 1/2/3/4/... in last frame
            for j in range(len(self.last_frame_face_centroid_list)):
                self.last_current_frame_centroid_e_distance = self.return_euclidean_distance(
                    self.current_frame_face_centroid_list[i], self.last_frame_face_centroid_list[j])

                e_distance_current_frame_person_x_list.append(
                    self.last_current_frame_centroid_e_distance)

            last_frame_num = e_distance_current_frame_person_x_list.index(
                min(e_distance_current_frame_person_x_list))
            self.current_frame_face_name_list[i] = self.last_frame_face_name_list[last_frame_num]

    # 生成的 cv2 window 上面添加说明文字 / putText on cv2 window
    def draw_note(self, img_rd):
        # 添加说明 / Add some info on windows
        cv2.putText(img_rd, "Face Recognizer with OT", (20, 40), self.font, 1, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(img_rd, "Frame:  " + str(self.frame_cnt), (20, 100), self.font, 0.8, (0, 255, 0), 1,
                    cv2.LINE_AA)
        cv2.putText(img_rd, "FPS:    " + str(self.fps.__round__(2)), (20, 130), self.font, 0.8, (0, 255, 0), 1,
                    cv2.LINE_AA)
        cv2.putText(img_rd, "Faces:  " + str(self.current_frame_face_cnt), (20, 160), self.font, 0.8, (0, 255, 0), 1,
                    cv2.LINE_AA)
        cv2.putText(img_rd, "Q: Quit", (20, 450), self.font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)

        for i in range(len(self.current_frame_face_name_list)):
            img_rd = cv2.putText(img_rd, "Face_" + str(i + 1), tuple(
                [int(self.current_frame_face_centroid_list[i][0]), int(self.current_frame_face_centroid_list[i][1])]),
                                 self.font,
                                 0.8, (255, 190, 0),
                                 1,
                                 cv2.LINE_AA)

      # 处理获取的视频流, 进行人脸识别 / Face detection and recognition wit OT from input video stream
    def process(self, stream):
        # 1. 读取存放所有人脸特征的 csv / Get faces known from "features.all.csv"
        if self.get_face_database():
            while stream.isOpened():
                self.frame_cnt += 1
                logging.debug("Frame " + str(self.frame_cnt) + " starts")
                flag, img_rd = stream.read()
                kk = cv2.waitKey(1)

                # 2. 检测人脸 / Detect faces for frame X
                # dlib 要求输入为 8bit 灰度或 RGB 图像，OpenCV 返回的是 BGR，因此需要转换
                if img_rd.dtype != np.uint8:
                    img_rd = img_rd.astype(np.uint8)
                img_rgb = cv2.cvtColor(img_rd, cv2.COLOR_BGR2RGB) if len(img_rd.shape) == 3 and img_rd.shape[2] == 3 else img_rd
                faces = detector(img_rgb, 0)

                # 3. 更新人脸计数器 / Update cnt for faces in frames
                self.last_frame_face_cnt = self.current_frame_face_cnt
                self.current_frame_face_cnt = len(faces)

                # 4. 更新上一帧中的人脸列表 / Update the face name list in last frame
                self.last_frame_face_name_list = self.current_frame_face_name_list[:]

                # 5. 更新上一帧和当前帧的质心列表 / update frame centroid list
                self.last_frame_face_centroid_list = self.current_frame_face_centroid_list
                self.current_frame_face_centroid_list = []

                # 6.1 如果当前帧和上一帧人脸数没有变化 / if cnt not changes
                if (self.current_frame_face_cnt == self.last_frame_face_cnt) and (
                        self.reclassify_interval_cnt != self.reclassify_interval):
                    logging.debug("scene 1: 当前帧和上一帧相比没有发生人脸数变化 / No face cnt changes in this frame!!!")

                    self.current_frame_face_position_list = []

                    if "unknown" in self.current_frame_face_name_list:
                        logging.debug("  有未知人脸, 开始进行 reclassify_interval_cnt 计数")
                        self.reclassify_interval_cnt += 1

                    if self.current_frame_face_cnt != 0:
                        for k, d in enumerate(faces):
                            self.current_frame_face_position_list.append(tuple(
                                [faces[k].left(), int(faces[k].bottom() + (faces[k].bottom() - faces[k].top()) / 4)]))
                            self.current_frame_face_centroid_list.append(
                                [int(faces[k].left() + faces[k].right()) / 2,
                                 int(faces[k].top() + faces[k].bottom()) / 2])

                            img_rd = cv2.rectangle(img_rd,
                                                   tuple([d.left(), d.top()]),
                                                   tuple([d.right(), d.bottom()]),
                                                   (255, 255, 255), 2)

                    # 如果当前帧中有多个人脸, 使用质心追踪 / Multi-faces in current frame, use centroid-tracker to track
                    if self.current_frame_face_cnt != 1:
                        self.centroid_tracker()

                    for i in range(self.current_frame_face_cnt):
                        # 6.2 Write names under ROI
                        img_rd = cv2.putText(img_rd, "username is "+self.current_frame_face_name_list[i],
                                             self.current_frame_face_position_list[i], self.font, 0.8, (0, 255, 255), 1,
                                             cv2.LINE_AA)
                    self.draw_note(img_rd)

                # 6.2 如果当前帧和上一帧人脸数发生变化 / If cnt of faces changes, 0->1 or 1->0 or ...
                else:
                    logging.debug("scene 2: 当前帧和上一帧相比人脸数发生变化 / Faces cnt changes in this frame")
                    self.current_frame_face_position_list = []
                    self.current_frame_face_X_e_distance_list = []
                    self.current_frame_face_feature_list = []
                    self.reclassify_interval_cnt = 0

                    # 6.2.1 人脸数减少 / Face cnt decreases: 1->0, 2->1, ...
                    if self.current_frame_face_cnt == 0:
                        logging.debug("  scene 2.1 人脸消失, 当前帧中没有人脸 / No faces in this frame!!!")
                        # clear list of names and features
                        self.current_frame_face_name_list = []
                    # 6.2.2 人脸数增加 / Face cnt increase: 0->1, 0->2, ..., 1->2, ...
                    else:
                        logging.debug("  scene 2.2 出现人脸, 进行人脸识别 / Get faces in this frame and do face recognition")
                        self.current_frame_face_name_list = []
                        for i in range(len(faces)):
                            shape = predictor(img_rgb, faces[i])
                            self.current_frame_face_feature_list.append(
                                face_reco_model.compute_face_descriptor(img_rgb, shape))
                            self.current_frame_face_name_list.append("unknown")

                        # 6.2.2.1 遍历捕获到的图像中所有的人脸 / Traversal all the faces in the database
                        for k in range(len(faces)):
                            logging.debug("  For face %d in current frame:", k + 1)
                            self.current_frame_face_centroid_list.append(
                                [int(faces[k].left() + faces[k].right()) / 2,
                                 int(faces[k].top() + faces[k].bottom()) / 2])

                            self.current_frame_face_X_e_distance_list = []

                            # 6.2.2.2 每个捕获人脸的名字坐标 / Positions of faces captured
                            self.current_frame_face_position_list.append(tuple(
                                [faces[k].left(), int(faces[k].bottom() + (faces[k].bottom() - faces[k].top()) / 4)]))

                            # 6.2.2.3 对于某张人脸, 遍历所有存储的人脸特征
                            # For every faces detected, compare the faces in the database
                            for i in range(len(self.face_features_known_list)):
                                # 如果 q 数据不为空
                                if str(self.face_features_known_list[i][0]) != '0.0':
                                    e_distance_tmp = self.return_euclidean_distance(
                                        self.current_frame_face_feature_list[k],
                                        self.face_features_known_list[i])
                                    logging.debug("      with person %d, the e-distance: %f", i + 1, e_distance_tmp)
                                    self.current_frame_face_X_e_distance_list.append(e_distance_tmp)
                                else:
                                    # 空数据 person_X
                                    self.current_frame_face_X_e_distance_list.append(999999999)

                            # 6.2.2.4 寻找出最小的欧式距离匹配 / Find the one with minimum e distance
                            similar_person_num = self.current_frame_face_X_e_distance_list.index(
                                min(self.current_frame_face_X_e_distance_list))

                            if min(self.current_frame_face_X_e_distance_list) < 0.4:
                                self.current_frame_face_name_list[k] = self.face_name_known_list[similar_person_num]
                                logging.debug("  Face recognition result: %s",
                                              self.face_name_known_list[similar_person_num])
                            else:
                                logging.debug("  Face recognition result: Unknown person")

                        # 7. 生成的窗口添加说明文字 / Add note on cv2 window
                        self.draw_note(img_rd)

                        # cv2.imwrite("debug/debug_" + str(self.frame_cnt) + ".png", img_rd) # Dump current frame image if needed

                # 8. 按下 'q' 键退出 / Press 'q' to exit
                if kk == ord('q'):
                    break

                self.update_fps()
                cv2.namedWindow("camera", 1)
                cv2.imshow("camera", img_rd)

                logging.debug("Frame ends\n\n")

    def run(self):
        # cap = cv2.VideoCapture("video.mp4")  # Get video stream from video file
        cap = cv2.VideoCapture(0)              # Get video stream from camera
        self.process(cap)

        cap.release()
        cv2.destroyAllWindows()


def main():
    # logging.basicConfig(level=logging.DEBUG) # Set log level to 'logging.DEBUG' to print debug info of every frame
    logging.basicConfig(level=logging.INFO)
    Face_Recognizer_con = Face_Recognizer()
    Face_Recognizer_con.run()


if __name__ == '__main__':
    main()


# 新增：为video_processor提供简洁接口的类
class FaceRecognitionService:
    """为视频处理器提供人脸识别服务的简洁接口"""

    def __init__(self, threshold: float = 0.4):
        """
        初始化人脸识别服务

        Args:
            threshold: 人脸识别阈值（欧氏距离）
        """
        self.threshold = threshold
        self.recognizer = Face_Recognizer()
        self.is_loaded = False

    def load_face_database(self) -> bool:
        """
        加载人脸数据库

        Returns:
            bool: 是否成功加载
        """
        try:
            success = self.recognizer.get_face_database()
            self.is_loaded = success
            if success:
                logging.info(f"人脸数据库加载成功，共{len(self.recognizer.face_features_known_list)}个人脸")
            return success
        except Exception as e:
            logging.error(f"加载人脸数据库失败: {e}")
            self.is_loaded = False
            return False

    def analyze_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        分析单帧图像中的人脸

        Args:
            frame: 输入图像帧

        Returns:
            List[Dict]: 人脸识别结果列表
        """
        if not self.is_loaded:
            logging.warning("人脸数据库未加载，返回空结果")
            return []

        try:
            # 使用dlib检测人脸（dlib 期望 8bit gray 或 RGB）
            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 
            faces = detector(frame_rgb, 0)
            if not faces:
                return []

            detections = []

            for face in faces:
                # 获取人脸特征点（在 RGB 图像上）
                shape = predictor(frame_rgb, face)
                # 获取128D特征向量
                face_descriptor = face_reco_model.compute_face_descriptor(frame_rgb, shape)

                # 计算与已知人脸的距离
                min_distance = float('inf')
                best_match_index = -1

                for i, known_features in enumerate(self.recognizer.face_features_known_list):
                    if str(known_features[0]) != '0.0':
                        e_distance = self.recognizer.return_euclidean_distance(
                            face_descriptor, known_features)
                        if e_distance < min_distance:
                            min_distance = e_distance
                            best_match_index = i

                # 获取人脸框坐标
                x1, y1, x2, y2 = face.left(), face.top(), face.right(), face.bottom()

                # 判断是否为已知人脸
                if min_distance < self.threshold and best_match_index != -1:
                    name = self.recognizer.face_name_known_list[best_match_index]
                    confidence = 1.0 - min_distance  # 转换为置信度
                    is_known = True
                else:
                    name = "unknown"
                    confidence = 0.5 if min_distance == float('inf') else 1.0 - min_distance
                    is_known = False

                # 计算质心坐标
                centroid_x = (x1 + x2) / 2
                centroid_y = (y1 + y2) / 2

                detections.append({
                    'name': name,
                    'confidence': confidence,
                    'bbox': [x1, y1, x2, y2],
                    'distance': min_distance if min_distance != float('inf') else 999999,
                    'is_known': is_known,
                    'centroid': [centroid_x, centroid_y]
                })

            return detections

        except Exception as e:
            logging.error(f"人脸识别分析出错: {e}")
            return []

    def annotate_frame(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """
        在帧上绘制人脸识别结果

        Args:
            frame: 原始图像帧
            detections: 人脸识别结果

        Returns:
            np.ndarray: 标注后的图像帧
        """
        if not detections:
            return frame

        annotated_frame = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = map(int, det['bbox'])
            name = det['name']
            confidence = det['confidence']

            # 选择颜色：已知人脸用绿色，未知用红色
            color = (0, 255, 0) if det['is_known'] else (0, 0, 255)

            # 绘制矩形框
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

            # 绘制标签
            if name != "unknown" and confidence >= 0.5:
                label = f" username is {name}({confidence:.2f})"
                y_offset = y1 - 10 if y1 - 10 > 10 else y1 + 20
                cv2.putText(annotated_frame, label, (x1, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        return annotated_frame

    def is_anomaly(self, detections: List[Dict],
                   unknown_threshold: float = 0.6,
                   multiple_faces_anomaly: bool = True) -> bool:
        """
        判断人脸识别结果是否有异常

        Args:
            detections: 人脸识别结果
            unknown_threshold: 未知人脸置信度阈值
            multiple_faces_anomaly: 是否将多个人脸视为异常

        Returns:
            bool: 是否有异常
        """
        if not detections:
            return False

        # 检测是否有高置信度的未知人脸
        for det in detections:
            if not det['is_known'] and det['confidence'] > unknown_threshold:
                return True

        # 检测是否有多个人脸
        if multiple_faces_anomaly and len(detections) > 1:
            return True

        return False

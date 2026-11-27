# YOLO情绪检测 → 8维度特征更新 完整测试指南

## 📋 系统架构

```
摄像头视频流 
    ↓
WebRTC实时传输 (端口8000)
    ↓
YOLO情绪检测模型
    ↓
EmotionStateMapper (情绪状态映射器)
    ↓
8维度特征更新 (emotional_state维度)
    ↓
WebSocket推送至前端
    ↓
前端实时显示情绪状态变化
```

## 🚀 快速开始

### 1. 环境准备

确保已安装以下依赖：
```bash
conda activate your_environment
pip install ultralytics opencv-python numpy aiortc fastapi uvicorn websockets
```

### 2. 启动服务器

```bash
cd E:\PY\all_tame_channel\Agent\face-select
python main_webrtc.py --port 8080
```

**预期输出：**
```
INFO:     Uvicorn running on http://0.0.0.0:8080
INFO:     VideoWapper 情绪识别模块初始化成功
INFO:     情绪状态映射器初始化成功
INFO:     情绪分析处理间隔: 每 5 帧处理一次
```

### 3. 打开前端页面

在浏览器中打开：
```
file:///E:/PY/all_tame_channel/Agent/face-select/test_webrtc_simple.html
```

### 4. 开始分析

1. 点击"开始分析"按钮
2. 允许浏览器访问摄像头
3. 观察右侧的"情绪状态特征"面板
4. 查看日志区域的情绪检测结果

## 🧪 运行测试案例

### 测试1: 基础功能测试

```bash
cd E:\PY\all_tame_channel\Agent\face-select
python test_emotion_feature_integration.py
```

这个测试会：
- 初始化用户的8维度特征
- 模拟不同情绪的YOLO检测结果
- 展示emotional_state维度的变化
- 运行15秒的实时模拟

### 测试2: 单元测试

```bash
python test_emotion_state_mapper.py
```

测试情绪状态映射器的各个功能模块。

## 📊 数据流程详解

### YOLO检测输出格式

```json
[
  {
    "emotion": "surprise",
    "confidence": 0.705,
    "bbox": [237, 156, 370, 320],
    "centroid": [303, 238],
    "size": {"width": 133, "height": 164}
  }
]
```

### 情绪状态映射结果

```json
{
  "status": "success",
  "detected_emotion": {
    "type": "surprise",
    "chinese_name": "惊讶",
    "confidence": 0.705,
    "valence": "neutral",
    "arousal": "high"
  },
  "dimension_impact": {
    "interest_level": 0.141,
    "frustration_tolerance": -0.071,
    "anxiety_level": 0.141,
    "confidence_level": -0.071
  },
  "emotional_state_update": {
    "interest_level": "较高",
    "frustration_tolerance": "中等",
    "anxiety_level": "较低",
    "confidence_level": "较高",
    "score": 72
  },
  "recommendation": "学生对内容感到新奇，可适当增加互动元素"
}
```

### WebSocket消息格式

**后端 → 前端：**
```json
{
  "type": "feature_update",
  "user_id": "test_user",
  "updated_dimension": "emotional_state",
  "new_values": {
    "interest_level": "较高",
    "frustration_tolerance": "中等",
    "anxiety_level": "较低",
    "confidence_level": "较高",
    "score": 75
  },
  "timestamp": 1234567890.123
}
```

## 🎯 情绪到特征的映射规则

### 各情绪对子维度的影响

| 情绪 | 兴趣水平 | 挫折承受力 | 焦虑水平 | 自信心 |
|------|---------|-----------|---------|--------|
| happy | +0.3 | +0.2 | -0.4 | +0.3 |
| surprise | +0.2 | -0.1 | +0.2 | -0.1 |
| neutral | 0.0 | 0.0 | 0.0 | 0.0 |
| sad | -0.4 | -0.3 | +0.3 | -0.4 |
| angry | -0.5 | -0.5 | +0.4 | -0.3 |
| fear | -0.3 | -0.4 | +0.6 | -0.5 |
| disgust | -0.4 | -0.3 | +0.2 | -0.2 |

**注意：** 实际影响 = 基础权重 × 置信度

### 评分计算逻辑

1. 将文本描述转换为数值（极低=10, 很低=20, ..., 极高=90）
2. 应用情绪影响值
3. 限制在0-100范围内
4. 转换回最接近的文本描述
5. 综合评分由LLM根据整体表现动态调整

## 🔧 配置选项

### 修改情绪检测频率

编辑 `config.py`：
```python
class EmotionConfig:
    EMOTION_FRAMES = 5  # 每5帧检测一次（降低可减少CPU占用）
    EMOTION_CONFIDENCE = 0.5  # 最低置信度阈值
```

### 调整情绪影响权重

编辑 `emotion_state_mapper.py`：
```python
EMOTION_IMPACT_WEIGHTS = {
    'happy': {
        'interest_level': +0.3,  # 修改这些值
        'frustration_tolerance': +0.2,
        'anxiety_level': -0.4,
        'confidence_level': +0.3
    },
    # ... 其他情绪
}
```

### 启用数据库持久化

编辑 `config.py`：
```python
class DatabaseConfig:
    ENABLE_DATABASE = True  # 改为True
    DB_HOST = "localhost"
    DB_USER = "root"
    DB_PASSWORD = "your_password"
    DB_NAME = "student_learning"
```

## 📈 监控与调试

### 查看实时日志

服务器控制台会输出：
```
INFO - 情绪分析原始数据: [{"emotion": "surprise", "confidence": 0.705, ...}]
INFO - 情绪状态映射: surprise (惊讶) - 置信度: 0.71
INFO - 情绪建议: 学生对内容感到新奇，可适当增加互动元素
DEBUG - 情绪状态更新建议: {"interest_level": "较高", ...}
```

### 前端调试

打开浏览器开发者工具（F12），在Console中可以看到：
- WebSocket连接状态
- 接收到的消息
- 特征更新事件

## 🐛 常见问题

### Q1: 摄像头无法打开

**解决方案：**
1. 确保浏览器有摄像头权限
2. 检查是否有其他程序占用摄像头
3. 尝试使用Chrome或Edge浏览器

### Q2: 情绪检测不准确

**可能原因：**
1. 光线不足或过强
2. 面部角度偏离太大
3. YOLO模型需要重新训练

**改进建议：**
- 保持正面朝向摄像头
- 确保面部清晰可见
- 调整 `EMOTION_CONFIDENCE` 阈值

### Q3: 特征更新没有生效

**检查清单：**
1. 确认 `ENABLE_EMOTION = True`
2. 检查日志中是否有"情绪状态映射器初始化成功"
3. 验证WebSocket连接是否正常
4. 查看前端是否收到 `feature_update` 消息

### Q4: 端口8080被占用

**解决方案：**
```bash
# Windows查找占用端口的进程
netstat -ano | findstr :8080

# 杀死进程（替换PID为实际进程ID）
taskkill /PID <PID> /F

# 或使用其他端口
python main_webrtc.py --port 8080
```

## 📝 扩展开发

### 添加新的情绪维度

1. 在 `emotion_state_mapper.py` 中添加新维度
2. 更新 `EMOTION_IMPACT_WEIGHTS`
3. 修改 `DynamicFeatureUpdater` 的schema
4. 更新前端显示逻辑

### 集成到其他Agent

```python
from emotion_state_mapper import EmotionStateMapper

# 在任何Agent中使用
mapper = EmotionStateMapper()
result = mapper.process_emotion_detection(yolo_data, current_features)

# 获取更新建议
emotional_update = result['emotional_state_update']
```

### 自定义情绪聚合策略

```python
# 修改聚合时间窗口
aggregated = mapper.aggregate_emotions_over_time(time_window_seconds=120)

# 自定义趋势分析算法
def custom_trend_analysis(recent_emotions):
    # 你的算法
    pass
```

## 🎓 学习资源

- **YOLO情绪检测**: 参考 `camera_detection.py`
- **8维度特征系统**: 参考 `dynamic_feature_updater.py`
- **WebRTC实时通信**: 参考 `main_webrtc.py` 和 `video_deal_webrtc.py`
- **前端WebSocket**: 参考 `test_webrtc_simple.html`

## 📞 技术支持

如遇到问题，请检查：
1. 日志文件: `log/run_*.log`
2. 控制台输出
3. 浏览器开发者工具

---

**祝测试顺利！🎉**

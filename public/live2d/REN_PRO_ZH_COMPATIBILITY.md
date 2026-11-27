# Ren Pro ZH 模型兼容性说明

## ⚠️ 当前状态

**Ren Pro ZH（莲·福斯特 - PRO）** 模型目前**无法正常工作**。

---

## 🔍 问题原因

### Cubism 版本不兼容

- **Ren Pro ZH 模型版本**: Cubism 5.3
- **当前核心库版本**: Cubism Core 5.1.0
- **结果**: ❌ 加载失败，显示 "Unknown error"

### 技术细节

```
MOC3 文件版本: 06 (Cubism 5.x)
具体子版本: 5.3 (需要更新的核心库)
```

Ren Pro ZH 使用了 Cubism 5.3 的新特性：
- 透明度混合遮罩
- 离屏绘制
- 精美的半透明效果

这些特性在 Cubism Core 5.1.0 中不支持。

---

## 📊 版本对比

| 组件 | 版本 | 状态 |
|------|------|------|
| Live2D Cubism Core | 5.1.0 | ✅ 已加载 |
| PixiJS | 7.x | ✅ 正常 |
| pixi-live2d-display | 0.4.0 | ✅ 正常 |
| **Ren Pro ZH 模型** | **5.3** | ❌ **不兼容** |
| 其他模型（Mao等） | 4.x-5.0 | ✅ 正常 |

---

## ✅ 解决方案

### 方案一：等待库更新（推荐）

**pixi-live2d-display** 需要更新以支持 Cubism 5.3。

关注以下仓库的更新：
- GitHub: [guansss/pixi-live2d-display](https://github.com/guansss/pixi-live2d-display)

### 方案二：使用官方 SDK

使用 Live2D 官方的 **Cubism Web Framework**，它支持最新的 Cubism 版本。

参考：
- [Live2D Cubism Web Samples](https://github.com/Live2D/CubismWebSamples)
- [Cubism Web Framework](https://docs.live2d.com/cubism-sdk-manual/web-overview/)

### 方案三：手动更新 Core（高级）

1. 从 Live2D 官网下载最新的 Cubism Core
2. 替换项目中的 `live2dcubismcore.min.js`
3. 测试兼容性

下载地址：
```
https://www.live2d.com/download/cubism-sdk/
```

⚠️ **注意**: 即使更新了 Core，pixi-live2d-display 可能仍需要相应更新才能完全支持。

### 方案四：使用其他模型（临时）

目前可以正常使用的模型：
- ✅ **Mao** - 功能最完整
- ✅ **Ice Girl** - 最多表情（20个）
- ✅ **Huohuo** - 中文动作名
- ✅ **Asuka** - VTube Studio 格式

---

## 🔧 当前实现

我已经为 Ren Pro ZH 添加了完整的配置：

### 配置文件位置
`app.js` 中的 `MODEL_CONFIGS['ren_pro_zh']`

### 包含的资源
- **动作**: 3个（Idle × 1, TapBody × 2）
- **表情**: 5个（exp_01 ~ exp_05）
- **路径**: `./ren_pro_zh/runtime/ren.model3.json`

### 加载时的行为
1. 检测到版本不兼容
2. 显示警告对话框
3. 用户可选择是否继续尝试
4. 如果失败，显示详细的错误说明

---

## 📝 模型信息

### Ren Pro ZH（莲·福斯特 - PRO）

**来源**: Live2D 官方示例模型

**特点**:
- 展示 Cubism 5.3 新增的丰富绘制功能
- 学习透明度混合遮罩技巧
- 学习离屏绘制实现半透明效果
- 专为高性能环境设计
- 适合 PC 视频直播场景

**文件结构**:
```
ren_pro_zh/
├── ReadMe.txt
├── ren_t01.can3        # Cubism Animator 项目文件
├── ren_t01.cmo3        # Cubism Model 文件
└── runtime/            # 运行时文件
    ├── expressions/    # 5个表情
    ├── motions/        # 3个动作
    ├── ren.4096/       # 纹理
    ├── ren.cdi3.json   # 参数定义
    ├── ren.moc3        # 模型二进制
    ├── ren.model3.json # 模型配置
    └── ren.physics3.json # 物理效果
```

---

## 🎯 后续计划

当 pixi-live2d-display 或 Live2D Core 更新后：

1. ✅ 更新 `live2dcubismcore.min.js` 到最新版本
2. ✅ 测试 Ren Pro ZH 模型加载
3. ✅ 验证动作和表情功能
4. ✅ 更新文档标记为"可用"

---

## 💡 临时建议

**如果想体验完整的 Live2D 功能，建议使用以下模型：**

🥇 **首选**: Mao
- 动作最丰富（7个）
- 表情多样（8个）
- 完全兼容

🥈 **次选**: Ice Girl  
- 表情最多（20个）
- 中文命名，易于理解

🥉 **备选**: Huohuo
- 动作有趣（7个）
- 中文动作名

---

**最后更新**: 2026-04-30  
**状态**: ⏳ 等待依赖库更新

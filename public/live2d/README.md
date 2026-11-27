# Live2D 网页展示项目

## 📖 项目说明

这是一个基于 **pixi-live2d-display** 第三方库的 Live2D 模型网页展示项目，可以在浏览器中完整渲染和交互多个 Live2D Cubism 虚拟角色模型。

### ✨ 特性

- ✅ **真实渲染**：使用 PixiJS + pixi-live2d-display 实现完整的模型渲染
- ✅ **动画播放**：支持所有动作文件的播放
- ✅ **表情切换**：支持动态切换表情
- ✅ **鼠标跟踪**：模型眼神跟随鼠标移动
- ✅ **物理效果**：支持模型的物理引擎（头发、衣服摆动等）
- ✅ **6个模型**：包含 Mao、Asuka、Huohuo、Ice Girl、Haihupu、Pachan

## 🎭 包含的模型

| 模型 | 动作数量 | 表情数量 | 特色 |
|------|---------|---------|------|
| **Mao** | 7 | 8 | 完整模型，含特殊动作 |
| **Asuka** | 3 | 4 | VTube Studio 配置 |
| **Huohuo** | 7 | 6 | 丰富的中文表情 |
| **Ice Girl** | 3 | 20 | 最多表情，中文命名 |
| **Haihupu** | - | - | 基础模型 |
| **Pachan** | - | - | Pachirisu 动漫女孩 |

## 🚀 快速开始

### ⚠️ 重要提示

**必须使用本地服务器运行！** 由于浏览器的 CORS 安全策略，直接打开 HTML 文件无法加载模型资源。

### 方法一：一键启动（推荐）

#### Windows 用户
双击 [`start-server.bat`](file://d:\live2d\start-server.bat) 或 [`start-server.ps1`](file://d:\live2d\start-server.ps1)

#### macOS/Linux 用户
```bash
python3 -m http.server 8080
```

### 方法二：手动启动

#### 使用 Python
```bash
# Python 3
python -m http.server 8080

# 或 Python 2
python -m SimpleHTTPServer 8080
```

#### 使用 Node.js
```bash
# 安装 http-server（首次需要）
npm install -g http-server

# 启动服务器
http-server -p 8080
```

#### 使用 VS Code
1. 安装 "Live Server" 插件
2. 右键点击 `index.html`
3. 选择 "Open with Live Server"

### 访问应用

启动服务器后，在浏览器中访问：
```
http://localhost:8080
```

## 📁 项目结构

```
live2d/
├── index.html              # 主页面（PixiJS 版本）
├── app.js                  # 主应用脚本（使用 pixi-live2d-display）
├── live2d-viewer.js        # 简化版查看器（备用）
├── live2dcubismcore.min.js # Live2D 核心库
├── start-server.bat        # Windows 启动脚本
├── start-server.ps1        # PowerShell 启动脚本
├── README.md               # 说明文档
├── Mao/                    # Mao 模型
│   ├── mao_pro.model3.json
│   ├── mao_pro.cdi3.json
│   ├── mao_pro.physics3.json
│   ├── mao_pro.pose3.json
│   ├── expressions/        # 8个表情文件
│   └── motions/           # 7个动作文件
├── asuka/                  # Asuka 模型
├── huohuo/                 # Huohuo 模型
├── icegirl/                # Ice Girl 模型
├── haihupu/                # Haihupu 模型
└── pachan/                 # Pachan 模型
```

## 🎮 使用方法

### 基本操作

1. **切换模型**：右上角下拉菜单选择不同模型
2. **播放动作**：
   - 点击画布任意位置
   - 或点击 "🎬 随机动作" 按钮
3. **切换表情**：点击 "😊 随机表情" 按钮
4. **重置模型**：点击 "🔄 重置" 恢复初始状态
5. **自动呼吸**：点击 "💨 自动呼吸" 开关

### 鼠标交互

- **移动鼠标**：模型眼神会跟随鼠标移动
- **点击画布**：触发随机动作
- **拖拽**：可以与模型进行交互

### 键盘快捷键（可扩展）

可以自行添加键盘快捷键功能，例如：
- `Space` - 播放随机动作
- `E` - 切换随机表情
- `R` - 重置模型

## 🔧 技术实现

### 核心技术栈

- **PixiJS v7** - 高性能 2D WebGL 渲染引擎
- **pixi-live2d-display v0.4.0** - Live2D 模型渲染库
- **Live2D Cubism Core** - Live2D 核心运行时

### CDN 依赖

```html
<!-- PixiJS -->
<script src="https://cdn.jsdelivr.net/npm/pixi.js@7.x/dist/pixi.min.js"></script>

<!-- pixi-live2d-display (Cubism 4) -->
<script src="https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js"></script>

<!-- Live2D Cubism Core -->
<script src="./live2dcubismcore.min.js"></script>
```

### 主要功能实现

#### 1. 模型加载
```javascript
// 使用 pixi-live2d-display 加载模型
this.currentModel = await PIXI.live2d.Live2DModel.from(modelPath, {
    autoInteract: true,
    autoUpdate: true
});
```

#### 2. 动作播放
```javascript
// 播放指定动作组的动作
this.currentModel.motion(groupName, motionIndex);
```

#### 3. 表情切换
```javascript
// 切换表情
this.currentModel.expression(expressionName);
```

#### 4. 鼠标跟踪
```javascript
// 更新模型参数实现眼神跟踪
coreModel.setParameterValueById(paramAngleX, x * 30);
coreModel.setParameterValueById(paramAngleY, y * 30);
```

## 🌟 高级功能

### 自定义动作列表

可以修改 [`app.js`](file://d:\live2d\app.js) 中的 `playRandomMotion()` 方法来定制动作选择逻辑：

```javascript
// 只播放特定组的动作
const preferredGroups = ['Tap', 'Flick', 'Shake'];
```

### 添加音效

可以为动作添加音效：

```javascript
this.currentModel.on('motion', (group, index) => {
    // 播放对应音效
    playSound(`sounds/${group}_${index}.mp3`);
});
```

### 背景切换

可以添加背景图片切换功能：

```javascript
this.app.stage.addChildAt(backgroundSprite, 0);
```

## ⚠️ 注意事项

### 常见问题

1. **模型不显示**
   - ✅ 确保使用了本地服务器
   - ✅ 检查浏览器控制台是否有错误
   - ✅ 确认模型文件路径正确

2. **动作无法播放**
   - ✅ 检查模型是否包含动作文件
   - ✅ 查看控制台的动作组信息
   - ✅ 确认 .motion3.json 文件格式正确

3. **性能问题**
   - ✅ 降低 Canvas 分辨率
   - ✅ 减少同时渲染的模型数量
   - ✅ 关闭不必要的物理效果

### 浏览器兼容性

- ✅ Chrome / Edge（推荐）
- ✅ Firefox
- ✅ Safari
- ⚠️ 需要支持 WebGL 的现代浏览器

### CORS 问题

如果遇到跨域错误，请确保：
1. 使用本地服务器而非直接打开文件
2. 服务器允许访问 JSON 和资源文件
3. 没有浏览器扩展阻止请求

## 📚 相关资源

### 官方文档

- [PixiJS 官网](https://pixijs.com/)
- [pixi-live2d-display GitHub](https://github.com/guansss/pixi-live2d-display)
- [Live2D Cubism SDK](https://docs.live2d.com/cubism-sdk-manual/top/)

### 示例项目

- [guansss/pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) - 使用的库
- [Live2D/CubismWebSamples](https://github.com/Live2D/CubismWebSamples) - 官方示例
- [Eikanya/Live2d-model](https://github.com/Eikanya/Live2d-model) - 模型集合

### 学习资源

- [PixiJS 教程](https://pixijs.com/guides/basics/getting-started)
- [WebGL 基础](https://developer.mozilla.org/zh-CN/docs/Web/API/WebGL_API)
- [Live2D 官方教程](https://www.live2d.com/learn/)

## 🛠️ 开发建议

### 调试技巧

1. **打开浏览器控制台**（F12）查看日志和错误
2. **使用 Chrome DevTools** 的性能面板分析渲染
3. **检查 Network 标签** 确认资源加载

### 优化建议

1. **预加载资源**：在显示前预加载所有模型
2. **纹理压缩**：使用 .webp 格式减小文件大小
3. **LOD 技术**：根据距离调整模型细节
4. **缓存管理**：合理管理模型实例避免内存泄漏

### 扩展方向

- [ ] 添加更多模型
- [ ] 实现对话系统
- [ ] 添加粒子特效
- [ ] 支持移动端触摸
- [ ] 添加录音和语音识别
- [ ] 实现 AI 对话功能

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目仅供学习和研究使用。

- **代码**：MIT License
- **模型资源**：版权归各自作者所有
- **PixiJS**：MIT License
- **pixi-live2d-display**：MIT License
- **Live2D Cubism**：遵循 Live2D 开放许可协议

使用本项目时，请遵守相关法律法规和版权规定。

---

**Made with ❤️ using PixiJS & pixi-live2d-display**

# 算法可视化平台 - 使用指南

## 🎯 功能概述

这是一个完整的算法可视化平台，支持：
- ✅ 查看算法代码（JavaScript/C++/Java）
- ✅ 执行算法并生成可视化命令
- ✅ **实时动画展示** - Canvas 图形化渲染
- ✅ 播放控制（播放/暂停/重置）
- ✅ 速度调节
- ✅ 日志输出

---

## 🚀 快速开始

### 1. 访问平台
打开浏览器访问：**http://localhost:4490**

### 2. 选择算法
在左侧列表中选择：
- 🎯 冒泡排序 (Bubble Sort)
- 🎯 选择排序 (Selection Sort)

### 3. 查看代码
右侧会显示算法的详细说明和代码实现，可以切换语言查看。

### 4. 执行可视化
点击 **"🚀 执行可视化"** 按钮

### 5. 观看动画
- 点击 **"▶️ 播放"** 开始动画
- 点击 **"⏸️ 暂停"** 暂停播放
- 点击 **"🔄 重置"** 重新开始
- 拖动速度滑块调节播放速度（1x - 10x）

---

## 📊 可视化说明

### 颜色含义
- **蓝色** (#667eea) - 普通元素
- **橙色** (#f39c12) - 当前选中的元素
- **红色** (#e74c3c) - 正在修改的元素

### 图表元素
- **柱状图** - 表示数组元素的值
- **数字标签** - 显示具体数值
- **索引标记** - 底部显示数组索引

### 日志区域
绿色文本区域显示算法执行过程中的关键操作，如：
- "交换 5 和 3"
- "找到更小的值: 2"
- "原始数组: [...]"
- "排序完成: [...]"

---

## 🎮 控制功能

### 播放控制
- **播放** - 从当前帧开始自动播放
- **暂停** - 暂停在当前帧
- **重置** - 回到第一帧

### 速度控制
- 范围：1x（慢）到 10x（快）
- 默认：5x
- 可在播放过程中实时调整

### 帧计数器
显示当前进度：`当前帧 / 总帧数`

---

## 💡 技术原理

### 1. Web Worker 执行
```javascript
// 算法代码在 Web Worker 中执行
const worker = new Worker('/api/tracers/js/worker');
worker.postMessage(code);
```

### 2. 命令序列生成
算法执行时，Tracer API 会记录所有操作：
- `set` - 设置数组数据
- `select` - 选中元素
- `patch` - 修改元素值
- `log` - 记录日志

### 3. Canvas 渲染
每一帧都会：
1. 清空画布
2. 处理所有到当前帧的命令
3. 绘制柱状图
4. 应用颜色和样式

### 4. 动画播放
使用 `setInterval` 按帧播放，速度可调。

---

## 📝 添加新算法

### 目录结构
```
public/algorithms/sorting-algorithms/
  └── your-algorithm/
      ├── code.js          # JavaScript 版本（必需）
      ├── main.cpp         # C++ 版本（可选）
      ├── Code.java        # Java 版本（可选）
      └── README.md        # 说明文档（可选）
```

### 编写带可视化的代码

```javascript
// 1. 导入可视化库
const { Tracer, Array1DTracer, LogTracer } = require('algorithm-visualizer');

// 2. 创建追踪器
const tracer = new Array1DTracer();
const logger = new LogTracer();
const D = [5, 3, 8, 1, 9];
tracer.set(D);

// 3. 算法执行中添加可视化
for (let i = 0; i < D.length; i++) {
  tracer.select(i);        // 选中元素
  Tracer.delay();          // 产生一帧
  
  if (D[i] > D[i+1]) {
    logger.println(`交换 ${D[i]} 和 ${D[i+1]}`);
    // 交换...
    tracer.patch(i, D[i]); // 修改元素
    Tracer.delay();
  }
  
  tracer.deselect(i);      // 取消选中
}
```

### 关键 API
- `tracer.set(array)` - 设置数组
- `tracer.select(index)` - 选中元素（高亮）
- `tracer.patch(index, value)` - 修改元素值
- `tracer.deselect(index)` - 取消选中
- `Tracer.delay()` - 延迟（产生新帧）
- `logger.println(msg)` - 记录日志

---

## 🔧 故障排除

### 问题：点击"执行可视化"没有反应
**解决**：检查浏览器控制台是否有错误，确保 Worker 文件可访问。

### 问题：动画不流畅
**解决**：降低播放速度，或检查浏览器性能。

### 问题：Canvas 不显示
**解决**：刷新页面，确保浏览器支持 Canvas。

### 问题：命令序列为空
**解决**：检查算法代码中是否包含 `Tracer.delay()` 调用。

---

## 🎓 学习资源

### 相关文档
- [Algorithm Visualizer 官方文档](https://github.com/algorithm-visualizer)
- [Canvas API 文档](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)
- [Web Workers](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API)

### 示例代码
查看现有算法的实现：
- `public/algorithms/sorting-algorithms/bubble-sort/code.js`
- `public/algorithms/sorting-algorithms/selection-sort/code.js`

---

## 🌟 扩展建议

### 短期改进
1. 添加更多排序算法（快速排序、归并排序等）
2. 支持图结构的可视化
3. 添加步骤跳转功能
4. 导出动画为 GIF

### 长期规划
1. 支持自定义输入数据
2. 算法复杂度分析图表
3. 多语言同步执行对比
4. 在线代码编辑器

---

## 📞 技术支持

如有问题或建议，请查看：
- 浏览器开发者工具的控制台
- 服务器日志输出
- 项目文档

祝学习愉快！🎉

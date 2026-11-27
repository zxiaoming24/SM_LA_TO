# 🤖 AI 智能代码转换功能

## 概述

系统集成了通义千问 Qwen-Max 模型，可以自动将用户的纯算法代码转换为符合可视化要求的完整代码。

## 使用方式

### 1️⃣ **用户只需编写纯算法代码**

```javascript
// 用户只需要写这个
for (let i = 1; i < n; i++) {
    let key = arr[i];
    let j = i - 1;
    while (j >= 0 && arr[j] > key) {
        arr[j + 1] = arr[j];
        j--;
    }
    arr[j + 1] = key;
}
```

### 2️⃣ **系统自动转换**

点击"执行可视化"后，系统会：
1. 检测代码是否包含可视化 API
2. 如果没有，调用 LLM 进行智能转换
3. 自动添加 tracer、layout、delay 等
4. 生成完整的可视化代码并执行

### 3️⃣ **查看结果**

转换后的代码会自动执行，显示动画效果！

## 配置说明

### 环境变量

在 `.env` 文件中配置（可选，已有默认值）：

```env
QWEN_API_KEY=sk-your-api-key-here
```

### API 端点

- **转换接口**: `POST /api/visualize/transform`
- **请求体**:
  ```json
  {
    "code": "用户代码",
    "algorithmType": "auto" // 或 'sorting', 'graph', 'tree'
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "code": "转换后的完整代码",
    "detectedType": "sorting"
  }
  ```

## 支持的算法类型

- ✅ **排序算法**（一维数组）
- ✅ **二维数组/矩阵**
- ✅ **图算法**
- ✅ **树算法**

## 示例

### 输入（纯算法）
```javascript
function bubbleSort(arr) {
    const n = arr.length;
    for (let i = 0; i < n - 1; i++) {
        for (let j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                [arr[j], arr[j + 1]] = [arr[j + 1], arr[j]];
            }
        }
    }
}
```

### 输出（带可视化）
```javascript
const tracer = new Array1DTracer('冒泡排序');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const array = [5, 3, 8, 1, 9];
const N = array.length;
tracer.set(array);
logger.println('开始冒泡排序');
Tracer.delay();

for (let i = 0; i < N - 1; i++) {
    for (let j = 0; j < N - i - 1; j++) {
        tracer.select(j, 'orange');
        tracer.select(j + 1, 'orange');
        Tracer.delay();
        
        if (array[j] > array[j + 1]) {
            [array[j], array[j + 1]] = [array[j + 1], array[j]];
            
            tracer.patch(j, array[j]);
            tracer.patch(j + 1, array[j + 1]);
            Tracer.delay();
            tracer.depatch(j);
            tracer.depatch(j + 1);
        }
        
        tracer.deselect(j);
        tracer.deselect(j + 1);
    }
}

logger.println('排序完成');
const allIndices = array.map((_, idx) => idx);
tracer.select(allIndices, 'green');
Tracer.delay();
```

## 优势

✅ **零学习成本**：用户不需要了解可视化 API  
✅ **智能识别**：自动检测算法类型和数据结构  
✅ **保持逻辑**：原算法逻辑完全不变  
✅ **即时反馈**：转换过程只需几秒  

## 注意事项

- LLM 转换需要网络连接
- 首次转换可能需要 3-5 秒
- 转换结果会被缓存，相同代码不会重复调用 LLM
- 如果转换失败，系统会提示用户手动添加可视化代码

"""
算法可视化服务模块 - 纯 Python 实现
直接提供 server-master 的所有可视化功能，无需运行 Node.js 服务

功能：
1. 算法列表和详情 API（解析 algorithms 目录结构）
2. LLM 代码转换（调用通义千问 Qwen-Max 将纯算法代码转为可视化代码）
3. 静态文件服务（algorithm-visualizer UMD 库、worker.js）
4. 可视化前端页面
5. 可视化数据存储
"""

import os
import re
import uuid
import time
import threading
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse

# ==================== 路径配置 ====================

# server-master 项目根目录（位于项目根目录下）
_SERVER_MASTER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server-master')

# 算法代码目录（algorithms-master）
_ALGORITHMS_DIR = os.path.join(_SERVER_MASTER_DIR, 'public', 'algorithms', 'algorithms-master')

# ★★★ 模块级执行器单例，避免每次请求新建线程池 ★★★
_EXECUTOR = None

def _get_executor():
    global _EXECUTOR
    if _EXECUTOR is None:
        from utils.concurrent_executor import ConcurrentExecutor
        _EXECUTOR = ConcurrentExecutor(max_workers=10)
    return _EXECUTOR

# 排序算法目录（额外的自定义算法）
_SORTING_ALGORITHMS_DIR = os.path.join(_SERVER_MASTER_DIR, 'public', 'algorithms', 'sorting-algorithms')

# 前端 HTML 文件
_FRONTEND_HTML = os.path.join(_SERVER_MASTER_DIR, 'public', 'frontend-built', 'index.html')

# algorithm-visualizer UMD 库
_ALGO_VIS_LIB = os.path.join(
    _SERVER_MASTER_DIR, 'node_modules', 'algorithm-visualizer', 'dist', 'algorithm-visualizer.umd.js'
)

# Worker.js
_WORKER_JS = os.path.join(_SERVER_MASTER_DIR, 'src', 'tracers', 'js', 'worker.js')

# ==================== LLM 配置 ====================

from utils.llm_config import API_KEY as _QWEN_API_KEY, BASE_URL as _QWEN_BASE_URL, MODEL as _QWEN_MODEL

# ==================== 内存缓存 ====================

# 可视化 JSON 数据存储 {viz_id: json_content}
_viz_store: Dict[str, Any] = {}

# 算法层级缓存（避免每次请求都扫描磁盘）
_hierarchy_cache: Dict[str, Any] = {}
_hierarchy_cache_time: float = 0
_CACHE_EXPIRY = 600  # 10分钟

# ==================== 路由 ====================

router = APIRouter()


# ==================== 工具函数 ====================

def _create_key(name: str) -> str:
    """
    将名称转换为 URL-friendly 的 key
    与 Node.js hierarchy.ts 中的 createKey 逻辑完全一致:
      name.toLowerCase().trim().replace(/[^\w \-]/g, '').replace(/ /g, '-')
    """
    key = name.lower().strip()
    key = re.sub(r'[^\w \-]', '', key)
    key = re.sub(r' ', '-', key)
    return key


def _list_directories(dir_path: str) -> list:
    """列出目录中的子目录名（排除隐藏目录）"""
    if not os.path.isdir(dir_path):
        return []
    result = []
    for name in sorted(os.listdir(dir_path)):
        if name.startswith('.'):
            continue
        full_path = os.path.join(dir_path, name)
        if os.path.isdir(full_path):
            result.append(name)
    return result


def _list_files(dir_path: str) -> list:
    """列出目录中的文件名（排除隐藏文件和子目录）"""
    if not os.path.isdir(dir_path):
        return []
    result = []
    for name in sorted(os.listdir(dir_path)):
        if name.startswith('.'):
            continue
        full_path = os.path.join(dir_path, name)
        if os.path.isfile(full_path):
            result.append(name)
    return result


def _read_file_content(file_path: str) -> str:
    """安全读取文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


def _get_description(files: list) -> str:
    """
    从 README.md 提取算法描述
    与 Node.js misc.ts 中的 getDescription 逻辑一致：
    去掉第一行（标题），取第一个非空段落，去除 Markdown 标记
    """
    readme = None
    for f in files:
        if f['name'] == 'README.md':
            readme = f
            break
    if not readme or not readme.get('content'):
        return ''

    lines = readme['content'].split('\n')
    if lines:
        lines = lines[1:]  # 去掉第一行（标题）

    # 去掉开头空行
    while lines and not lines[0].strip():
        lines = lines[1:]

    # 收集描述（直到空行）
    desc_lines = []
    while lines and lines[0].strip():
        desc_lines.append(lines.pop(0))

    description = ' '.join(desc_lines)
    # 简单去除 Markdown 标记
    description = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', description)  # 链接
    description = re.sub(r'[*_`~]', '', description)                      # 粗斜体代码
    description = re.sub(r'#+\s*', '', description)                       # 标题
    return description.strip()


def _build_hierarchy() -> dict:
    """
    扫描算法目录，构建完整的层级结构
    返回格式与 Node.js Hierarchy.toJSON() 一致:
    {
      "categories": [
        {
          "key": "brute-force",
          "name": "Brute Force",
          "algorithms": [
            {
              "key": "bubble-sort",
              "name": "Bubble Sort",
              "files": [{"name": "code.js", "content": "...", "contributors": []}],
              "description": "..."
            }
          ]
        }
      ]
    }
    """
    global _hierarchy_cache, _hierarchy_cache_time

    now = time.time()
    if _hierarchy_cache and (now - _hierarchy_cache_time) < _CACHE_EXPIRY:
        return _hierarchy_cache

    categories = []

    # 1. 扫描 algorithms-master 目录（主要算法库）
    if os.path.isdir(_ALGORITHMS_DIR):
        for category_name in _list_directories(_ALGORITHMS_DIR):
            category_path = os.path.join(_ALGORITHMS_DIR, category_name)
            category_key = _create_key(category_name)
            algorithms = []

            for algo_name in _list_directories(category_path):
                algo_path = os.path.join(category_path, algo_name)
                algo_key = _create_key(algo_name)

                files = []
                for file_name in _list_files(algo_path):
                    file_path = os.path.join(algo_path, file_name)
                    files.append({
                        'name': file_name,
                        'content': _read_file_content(file_path),
                        'contributors': []
                    })

                algorithms.append({
                    'key': algo_key,
                    'name': algo_name,
                    'files': files,
                    'description': _get_description(files)
                })

            categories.append({
                'key': category_key,
                'name': category_name,
                'algorithms': algorithms
            })

    # 2. 扫描 sorting-algorithms 目录（额外的自定义排序算法）
    if os.path.isdir(_SORTING_ALGORITHMS_DIR):
        # 检查是否已有 sorting-algorithms 分类
        existing = None
        for cat in categories:
            if cat['key'] == 'sorting-algorithms':
                existing = cat
                break

        sorting_algos = []
        for algo_name in _list_directories(_SORTING_ALGORITHMS_DIR):
            algo_path = os.path.join(_SORTING_ALGORITHMS_DIR, algo_name)
            algo_key = _create_key(algo_name)

            files = []
            for file_name in _list_files(algo_path):
                file_path = os.path.join(algo_path, file_name)
                files.append({
                    'name': file_name,
                    'content': _read_file_content(file_path),
                    'contributors': []
                })

            sorting_algos.append({
                'key': algo_key,
                'name': algo_name,
                'files': files,
                'description': _get_description(files)
            })

        if existing:
            # 合并到已有分类（避免重复）
            existing_keys = {a['key'] for a in existing['algorithms']}
            for algo in sorting_algos:
                if algo['key'] not in existing_keys:
                    existing['algorithms'].append(algo)
        else:
            categories.append({
                'key': 'sorting-algorithms',
                'name': 'sorting-algorithms',
                'algorithms': sorting_algos
            })

    result = {'categories': categories}
    _hierarchy_cache = result
    _hierarchy_cache_time = now
    return result


def _find_algorithm(category_key: str, algorithm_key: str) -> Optional[dict]:
    """查找指定算法，返回格式与 Node.js Hierarchy.find() 一致"""
    hierarchy = _build_hierarchy()
    for cat in hierarchy['categories']:
        if cat['key'] == category_key:
            for algo in cat['algorithms']:
                if algo['key'] == algorithm_key:
                    return {
                        'categoryKey': category_key,
                        'categoryName': cat['name'],
                        'algorithmKey': algorithm_key,
                        'algorithmName': algo['name'],
                        'files': algo['files'],
                        'description': algo.get('description', '')
                    }
    return None


async def _transform_code_with_llm(user_code: str, algorithm_type: str = 'sorting', language: str = 'javascript', test_data: str = '') -> str:
    """
    调用通义千问 Qwen-Max 将纯算法代码转换为可视化代码
    支持多种编程语言（JavaScript, Python, Java, C++）
    优化版：增强提示词提高转换质量 + 异步调用提升并发性能
    新增：沙箱执行提取实际数据（支持 stdin 输入）
    """
    
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=_QWEN_API_KEY, base_url=_QWEN_BASE_URL)

    # 根据语言类型构建不同的提示词
    lang_prompts = {
        'javascript': {
            'code_block': 'javascript',
            'example_input': '''```javascript
function bubbleSort(arr) {
    const n = arr.length;
    for (let i = 0; i < n - 1; i++) {
        for (let j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                [arr[j], arr[j + 1]] = [arr[j + 1], arr[j]];
            }
        }
    }
    return arr;
}
```''',
            'example_output': '''```javascript
const tracer = new Array1DTracer('冒泡排序');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const array = [5, 3, 8, 1, 9, 2];
const N = array.length;
tracer.set(array);
logger.println('开始冒泡排序');
Tracer.delay();

for (let i = 0; i < N - 1; i++) {
    logger.println('第 ' + (i + 1) + ' 轮排序');
    for (let j = 0; j < N - i - 1; j++) {
        tracer.select(j, 'orange');
        tracer.select(j + 1, 'orange');
        Tracer.delay();
        
        if (array[j] > array[j + 1]) {
            logger.println('交换 ' + array[j] + ' 和 ' + array[j + 1]);
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
```'''
        },
        'python': {
            'code_block': 'python',
            'example_input': '''```python
def bubble_sort(arr):
    n = len(arr)
    for i in range(n - 1):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
```''',
            'example_output': '''```javascript
const tracer = new Array1DTracer('冒泡排序');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const array = [5, 3, 8, 1, 9, 2];
const N = array.length;
tracer.set(array);
logger.println('开始冒泡排序');
Tracer.delay();

for (let i = 0; i < N - 1; i++) {
    logger.println('第 ' + (i + 1) + ' 轮排序');
    for (let j = 0; j < N - i - 1; j++) {
        tracer.select(j, 'orange');
        tracer.select(j + 1, 'orange');
        Tracer.delay();
        
        if (array[j] > array[j + 1]) {
            logger.println('交换 ' + array[j] + ' 和 ' + array[j + 1]);
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
```'''
        },
        'java': {
            'code_block': 'java',
            'example_input': '''```java
public static void bubbleSort(int[] arr) {
    int n = arr.length;
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}
```''',
            'example_output': '''```javascript
const tracer = new Array1DTracer('冒泡排序');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const array = [5, 3, 8, 1, 9, 2];
const N = array.length;
tracer.set(array);
logger.println('开始冒泡排序');
Tracer.delay();

for (let i = 0; i < N - 1; i++) {
    logger.println('第 ' + (i + 1) + ' 轮排序');
    for (let j = 0; j < N - i - 1; j++) {
        tracer.select(j, 'orange');
        tracer.select(j + 1, 'orange');
        Tracer.delay();
        
        if (array[j] > array[j + 1]) {
            logger.println('交换 ' + array[j] + ' 和 ' + array[j + 1]);
            let temp = array[j];
            array[j] = array[j + 1];
            array[j + 1] = temp;
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
```'''
        },
        'cpp': {
            'code_block': 'cpp',
            'example_input': '''```cpp
void bubbleSort(vector<int>& arr) {
    int n = arr.size();
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                swap(arr[j], arr[j + 1]);
            }
        }
    }
}
```''',
            'example_output': '''```javascript
const tracer = new Array1DTracer('冒泡排序');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const array = [5, 3, 8, 1, 9, 2];
const N = array.length;
tracer.set(array);
logger.println('开始冒泡排序');
Tracer.delay();

for (let i = 0; i < N - 1; i++) {
    logger.println('第 ' + (i + 1) + ' 轮排序');
    for (let j = 0; j < N - i - 1; j++) {
        tracer.select(j, 'orange');
        tracer.select(j + 1, 'orange');
        Tracer.delay();
        
        if (array[j] > array[j + 1]) {
            logger.println('交换 ' + array[j] + ' 和 ' + array[j + 1]);
            let temp = array[j];
            array[j] = array[j + 1];
            array[j + 1] = temp;
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
```'''
        },
        'c': {
            'code_block': 'c',
            'example_input': '''```c
void bubbleSort(int arr[], int n) {
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}
```''',
            'example_output': '''```javascript
const tracer = new Array1DTracer('冒泡排序');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const array = [5, 3, 8, 1, 9, 2];
const N = array.length;
tracer.set(array);
logger.println('开始冒泡排序');
Tracer.delay();

for (let i = 0; i < N - 1; i++) {
    logger.println('第 ' + (i + 1) + ' 轮排序');
    for (let j = 0; j < N - i - 1; j++) {
        tracer.select(j, 'orange');
        tracer.select(j + 1, 'orange');
        Tracer.delay();
        
        if (array[j] > array[j + 1]) {
            logger.println('交换 ' + array[j] + ' 和 ' + array[j + 1]);
            let temp = array[j];
            array[j] = array[j + 1];
            array[j + 1] = temp;
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
```'''
        }
    }

    lang_info = lang_prompts.get(language, lang_prompts['javascript'])

    # 根据算法类型构建不同的 API 参考和示例
    type_specific_sections = {
        'sorting': f"""
**数组可视化 API 参考**：
```javascript
const tracer = new Array1DTracer('数组');
tracer.set([5, 3, 8, 1]);       // 设置初始数组
tracer.select(i, 'orange');      // 选中第 i 个元素（橙色高亮）
tracer.select([i,j], 'orange');  // 选中多个元素
tracer.patch(i, newVal);         // 修改第 i 个元素的值（黄色高亮）
tracer.depatch(i);               // 取消修改高亮
tracer.deselect(i);              // 取消选中高亮
Tracer.delay();                  // 必须！每次视觉变化后调用，触发一帧渲染
```

示例转换：
输入：
{lang_info['example_input']}

输出：
{lang_info['example_output']}
""",
        'search': """
**查找算法可视化 API 参考**（用 Array2DTracer 单行网格展示数据，像表格一样列出每个元素）：

★★★ 关键：查找必须用 Array2DTracer（网格/表格），不要用 Array1DTracer（柱状图）！★★★

```javascript
const tracer = new Array2DTracer('数组');   // ← 注意是 Array2DTracer
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

// 将一维数组包装成单行二维数组 [[5, 3, 8, 1, 9]]
const arr = [5, 3, 8, 1, 9];
tracer.set([arr]);   // ← 注意是 [arr]，包装成二维
Tracer.delay();

// 选中单个格子: select(row, col) — 橙色高亮
tracer.select(0, i);       // 选中第 0 行第 i 列
Tracer.delay();
tracer.deselect(0, i);     // 取消选中

// 选中范围: select(startRow, startCol, endRow, endCol)
tracer.select(0, low, 0, high);   // 选中第 0 行从 low 到 high 的范围
tracer.deselect(0, low, 0, high); // 取消选中范围

// 找到目标（绿色高亮）
tracer.select(0, foundCol);  // 找到后用 select 标记
Tracer.delay();
```

★★★ 查找可视化的核心规则：
1. **必须用 Array2DTracer** 展示网格（每个数字一个格子），不要用 Array1DTracer（柱状图）
2. **不做任何元素交换或移动**，数据始终不动
3. 用 select(0, col) / deselect(0, col) 标记当前检查的格子
4. 线性查找：从左到右逐个 select(0, i) → delay → deselect(0, i)
5. 二分查找：select(0, low, 0, high) 标记范围 → 检查 mid → 缩小范围
6. 找到目标后保持选中状态，不 deselect
7. ★★★ 直接把完整数据作为数组展示（tracer.set([完整数组])），不要猜测哪个是n、哪个是target。
   例如：数据 [5, 1, 3, 5, 7, 9, 5] → tracer.set([[5,1,3,5,7,9,5]]) → 展示全部7个格子 → 再开始查找

示例转换（线性查找）：
输入：
```python
def linear_search(arr, target):
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1
```

输出：
```javascript
const tracer = new Array2DTracer('线性查找');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const arr = [5, 3, 8, 1, 9, 5, 8];
const target = 9;
tracer.set([arr]);
logger.println('在数组中查找 ' + target);
Tracer.delay(); //src:2

for (let i = 0; i < arr.length; i++) {
    tracer.select(0, i);
    logger.println('检查 arr[' + i + '] = ' + arr[i]);
    Tracer.delay(); //src:3
    if (arr[i] === target) {
        logger.println('找到目标! 索引: ' + i);
        Tracer.delay(); //src:4
        return;
    }
    tracer.deselect(0, i);
    Tracer.delay();
}
logger.println('未找到目标 ' + target);
Tracer.delay(); //src:5
```

示例转换（二分查找）：
输入：
```python
def binary_search(arr, target):
    low, high = 0, len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
```

输出：
```javascript
const tracer = new Array2DTracer('二分查找');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const arr = [1, 3, 5, 7, 9, 11, 13, 15];
const target = 7;
tracer.set([arr]);
logger.println('在数组中查找 ' + target);
Tracer.delay(); //src:2

let low = 0, high = arr.length - 1;
while (low <= high) {
    tracer.select(0, low, 0, high);
    logger.println('搜索范围: [' + low + ', ' + high + ']');
    Tracer.delay(); //src:3
    let mid = Math.floor((low + high) / 2);
    tracer.deselect(0, low, 0, high);
    tracer.select(0, mid);
    logger.println('检查中间: arr[' + mid + '] = ' + arr[mid]);
    Tracer.delay(); //src:4
    if (arr[mid] === target) {
        logger.println('找到目标! 索引: ' + mid);
        Tracer.delay(); //src:5
        return;
    } else if (arr[mid] < target) {
        logger.println(arr[mid] + ' < ' + target + ', 搜索右半部分');
        low = mid + 1;
    } else {
        logger.println(arr[mid] + ' > ' + target + ', 搜索左半部分');
        high = mid - 1;
    }
    tracer.deselect(0, mid);
}
logger.println('未找到目标 ' + target);
Tracer.delay(); //src:7
```
""",
        'graph': """
**图可视化 API 参考**：
```javascript
const graphTracer = new GraphTracer('图');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([graphTracer, logger]));

// 用邻接矩阵设置图（必须！这是初始化图的方式）
const matrix = [
    [0, 1, 1, 0],   // 节点0连接1,2
    [1, 0, 1, 1],   // 节点1连接0,2,3
    [1, 1, 0, 0],   // 节点2连接0,1
    [0, 1, 0, 0]    // 节点3连接1
];
graphTracer.set(matrix);
Tracer.delay();

// 选中节点
graphTracer.select(nodeId);          // 选中节点（橙色）
graphTracer.deselect(nodeId);        // 取消选中

// 访问边（遍历图时高亮边）
graphTracer.visit(fromNode, toNode);  // 高亮边 from→to（橙色）
graphTracer.leave(fromNode, toNode);  // 取消高亮边

Tracer.delay();  // 必须！每次视觉变化后调用
```

★★★ 重要警告：GraphTracer 没有 patch() 和 depatch() 方法！
★★★ 只能用：set, select, deselect, visit, leave, addNode, addEdge, removeNode, removeEdge, layoutCircle, layoutTree
★★★ 绝对不要调用 graphTracer.patch() 或 graphTracer.depatch()，会报错！

示例转换：
输入：
```python
def bfs(graph, start):
    visited = set()
    queue = [start]
    visited.add(start)
    while queue:
        node = queue.pop(0)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited
```

输出：
```javascript
const graphTracer = new GraphTracer('BFS图遍历');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([graphTracer, logger]));

const adjMatrix = [
    [0, 1, 1, 0, 0],
    [1, 0, 0, 1, 0],
    [1, 0, 0, 1, 1],
    [0, 1, 1, 0, 0],
    [0, 0, 1, 0, 0]
];
graphTracer.set(adjMatrix);
logger.println('开始 BFS 遍历');
Tracer.delay();

const visited = new Set();
const queue = [0];
visited.add(0);
graphTracer.select(0);
logger.println('访问节点 0');
Tracer.delay();

while (queue.length > 0) {
    const node = queue.shift();
    logger.println('出队节点: ' + node);
    for (let neighbor = 0; neighbor < 5; neighbor++) {
        if (adjMatrix[node][neighbor] === 1 && !visited.has(neighbor)) {
            graphTracer.visit(node, neighbor);
            logger.println('访问边 ' + node + ' -> ' + neighbor);
            Tracer.delay();
            visited.add(neighbor);
            graphTracer.select(neighbor);
            logger.println('访问节点 ' + neighbor);
            Tracer.delay();
            graphTracer.leave(node, neighbor);
            queue.push(neighbor);
        }
    }
    graphTracer.deselect(node);
}
logger.println('BFS 遍历完成');
Tracer.delay();
```
""",
        'tree': """
**树可视化 API 参考**（注意：没有 TreeTracer，用 GraphTracer + layoutTree 实现树形布局）：
```javascript
// ★★★ 重要：树用 GraphTracer + layoutTree() 实现，不要用 TreeTracer ★★★
const graphTracer = new GraphTracer('二叉树');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([graphTracer, logger]));

// 用邻接矩阵表示树的父子连接（无向图，layoutTree 会自动处理方向）
// 例：节点0的子节点是1,2；节点1的子节点是3,4；节点2的子节点是5
const adjMatrix = [
    [0, 1, 1, 0, 0, 0],  // 节点0连接1,2
    [1, 0, 0, 1, 1, 0],  // 节点1连接0,3,4
    [1, 0, 0, 0, 0, 1],  // 节点2连接0,5
    [0, 1, 0, 0, 0, 0],  // 节点3连接1
    [0, 1, 0, 0, 0, 0],  // 节点4连接1
    [0, 0, 1, 0, 0, 0]   // 节点5连接2
];
graphTracer.set(adjMatrix);
graphTracer.layoutTree(0);  // ★★★ 关键！指定根节点，切换为树形布局 ★★★
Tracer.delay();

// 选中节点
graphTracer.select(nodeId);       // 选中节点（橙色高亮）
graphTracer.deselect(nodeId);     // 取消选中

// 访问边（父子之间）
graphTracer.visit(parentId, childId);  // 高亮边
graphTracer.leave(parentId, childId);  // 取消高亮

Tracer.delay();  // 必须！每次视觉变化后调用
```

★★★ 重要警告：GraphTracer 没有 patch() 和 depatch() 方法！
★★★ 只能用：set, select, deselect, visit, leave, layoutTree, addNode, addEdge
★★★ 绝对不要调用 graphTracer.patch() 或 graphTracer.depatch()，会报错！

示例转换：
输入：
```python
def inorder(node):
    if node is None:
        return
    inorder(node.left)
    print(node.val)
    inorder(node.right)
```

输出：
```javascript
const graphTracer = new GraphTracer('中序遍历');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([graphTracer, logger]));

// 二叉树邻接矩阵：0->1,2; 1->3,4; 2->5,6
const adjMatrix = [
    [0,1,1,0,0,0,0],
    [1,0,0,1,1,0,0],
    [1,0,0,0,0,1,1],
    [0,1,0,0,0,0,0],
    [0,1,0,0,0,0,0],
    [0,0,1,0,0,0,0],
    [0,0,1,0,0,0,0]
];
graphTracer.set(adjMatrix);
graphTracer.layoutTree(0);
logger.println('开始中序遍历');
Tracer.delay();

function inorder(nodeId) {
    if (nodeId < 0 || nodeId > 6) return;
    graphTracer.select(nodeId);
    logger.println('访问节点 ' + nodeId);
    Tracer.delay();

    const left = nodeId * 2 + 1;
    const right = nodeId * 2 + 2;

    if (left <= 6) {
        graphTracer.visit(nodeId, left);
        Tracer.delay();
        inorder(left);
        graphTracer.leave(nodeId, left);
    }
    logger.println('输出: 节点 ' + nodeId);
    Tracer.delay();
    if (right <= 6) {
        graphTracer.visit(nodeId, right);
        Tracer.delay();
        inorder(right);
        graphTracer.leave(nodeId, right);
    }
    graphTracer.deselect(nodeId);
}
inorder(0);
logger.println('中序遍历完成');
Tracer.delay();
```
""",
        '2d-array': """
**二维数组/矩阵可视化 API 参考**：
```javascript
const tracer = new Array2DTracer('矩阵');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

// 设置二维数组
const matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9]
];
tracer.set(matrix);
Tracer.delay();

// ★★★ 选中单元格（注意：参数是行范围+列范围，选中单个格子时 sx=ex, sy=ey）★★★
tracer.select(sx, sy, ex, ey);     // 选中行 sx~ex、列 sy~ey 的区域
tracer.select(row, col, row, col); // 选中单个单元格 (row, col)
tracer.deselect(sx, sy, ex, ey);   // 取消选中

// 选中整行或整列
tracer.selectRow(row, startCol, endCol);  // 选中整行
tracer.selectCol(col, startRow, endRow);  // 选中整列

// 修改单元格值（黄色高亮）
tracer.patch(row, col, newValue);    // 修改值
tracer.depatch(row, col);            // 取消修改高亮

Tracer.delay();  // 必须！每次视觉变化后调用
```

★★★ 重要警告：Array2DTracer 没有 selectCell() 方法！
★★★ 选中单个格子用：tracer.select(row, col, row, col)  ← 四个参数！
★★★ 完整方法列表：set, patch, depatch, select(sx,sy,ex,ey), selectRow, selectCol, deselect, deselectRow, deselectCol

示例转换：
输入：
```python
def matrix_multiply(A, B):
    n = len(A)
    C = [[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                C[i][j] += A[i][k] * B[k][j]
    return C
```

输出：
```javascript
const tracer = new Array2DTracer('矩阵乘法');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const A = [[1, 2], [3, 4]];
const B = [[5, 6], [7, 8]];
const n = 2;
const C = [[0, 0], [0, 0]];
tracer.set(C);
logger.println('开始矩阵乘法 C = A × B');
Tracer.delay();

for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
        tracer.select(i, j, i, j);  // ★★★ 四个参数！选中单个格子 ★★★
        logger.println('计算 C[' + i + '][' + j + ']');
        Tracer.delay();
        for (let k = 0; k < n; k++) {
            C[i][j] += A[i][k] * B[k][j];
        }
        tracer.patch(i, j, C[i][j]);
        logger.println('C[' + i + '][' + j + '] = ' + C[i][j]);
        Tracer.delay();
        tracer.depatch(i, j);
        tracer.deselect(i, j, i, j);  // ★★★ 四个参数！★★★
    }
}
logger.println('矩阵乘法完成');
Tracer.delay();
```
"""
    }

    # ★★★ 提取用户代码中的实际数据 ★★★
    # 优先沙箱执行（支持stdin/动态数据），失败则正则兜底，最后解析测试输入
    extracted_data = {'arrays': [], 'matrices': [], 'graphs': None, 'trees': None}
    data_source = '无'
    
    # 1. 尝试沙箱执行
    sandbox_result = _execute_in_sandbox(user_code, language, test_data)
    if sandbox_result['success'] and sandbox_result['variables']:
        for name, value in sandbox_result['variables'].items():
            if isinstance(value, list):
                if value and isinstance(value[0], list):
                    extracted_data['matrices'].append({'name': name, 'data': value})
                else:
                    extracted_data['arrays'].append({'name': name, 'data': value})
        data_source = '沙箱执行'
        print(f"✅ 沙箱执行成功，捕获变量: {list(sandbox_result['variables'].keys())}")
        
        # ★ 关键：如果有测试数据，同时解析完整原始数据 ★
        # 沙箱捕获的是用户代码解析后的变量（可能已截断，如 arr=data[1:n+1]），
        # 这里用完整的原始输入数据替换沙箱截断后的数据
        if test_data:
            parsed_raw = _parse_test_input(test_data)
            if parsed_raw and 'array' in parsed_raw:
                raw_data = parsed_raw['array']['data']
                # 如果原始数据比沙箱捕获的更长，说明沙箱截断了数据
                for i, captured_arr in enumerate(extracted_data['arrays']):
                    if len(raw_data) > len(captured_arr['data']):
                        # 用完整原始数据替换截断后的沙箱数据
                        print(f"📊 沙箱数据被截断 ({captured_arr['name']}: {len(captured_arr['data'])}个元素)，替换为完整原始数据 ({len(raw_data)}个元素)")
                        extracted_data['arrays'][i] = {'name': captured_arr['name'], 'data': raw_data}
                        break
            # 同样处理图数据：如果测试数据是邻接矩阵，用原始矩阵替换
            if parsed_raw and 'graph' in parsed_raw:
                extracted_data['graphs'] = parsed_raw['graph']
    else:
        # 2. 沙箱失败，正则兜底
        extracted_data = _extract_user_data(user_code, language)
        has_regex = bool(extracted_data['arrays'] or extracted_data['matrices'] or extracted_data['graphs'])
        
        if has_regex:
            data_source = '正则提取'
            print(f"📊 正则提取数据成功")
        elif test_data:
            # 3. 正则也没提取到，解析测试输入
            parsed = _parse_test_input(test_data)
            if parsed:
                if 'graph' in parsed:
                    extracted_data['graphs'] = parsed['graph']
                    # 自动修正算法类型为图
                    if algorithm_type == 'sorting':
                        algorithm_type = 'graph'
                        print(f"🔧 根据测试数据自动修正算法类型为: graph")
                if 'matrix' in parsed:
                    extracted_data['matrices'].append({'name': 'input_matrix', 'data': parsed['matrix']['data']})
                    if algorithm_type == 'sorting' and 'graph' not in parsed:
                        algorithm_type = '2d-array'
                        print(f"🔧 根据测试数据自动修正算法类型为: 2d-array")
                if 'array' in parsed and 'graph' not in parsed and 'matrix' not in parsed:
                    extracted_data['arrays'].append({'name': 'input_array', 'data': parsed['array']['data']})
                data_source = '测试输入解析'
                print(f"📊 从测试输入解析到数据: {list(parsed.keys())}")
            else:
                data_source = '未提取到'
        else:
            data_source = '未提取到'
        print(f"📊 数据提取结果: {data_source}")
    
    # 获取对应类型的详细参考（在 algorithm_type 可能被修正之后）
    type_section = type_specific_sections.get(algorithm_type, type_specific_sections['sorting'])
    
    user_data_text = _format_extracted_data(extracted_data)
    
    # 如果有用户提供的测试数据，也加到提示中
    if test_data and not user_data_text:
        user_data_text = f"- 用户提供的测试输入数据:\n{test_data}"
    
    print(f"📊 最终数据 (来源: {data_source}): {user_data_text if user_data_text else '(无)'}")
    
    # 构建用户数据提示段
    if user_data_text:
        data_section = f"""
★★★ 重要：以下是已经解析好的完整数据（你必须在可视化中直接使用这些数据）：
{user_data_text}

★★★ 数据使用规则（严格遵守）：
1. 直接把上面列出的数据**原封不动**作为数组使用，`tracer.set(数据)` 展示全部
2. **忽略用户代码中的 stdin/input 解析逻辑**（如 n=int(data[0]), arr=data[1:n+1] 等），
   可视化不需要模拟输入解析，直接用上面的完整数据
3. 不要猜测哪个数字是n、哪个是target，上面给什么就用什么
4. **禁止** slice()、substring、splice 等截断/截取操作
5. **禁止** 跳过任何元素
"""
    else:
        data_section = """
注意：未能从用户代码中提取到具体数据。你可以使用合理的示例数据，但数据规模应与用户代码匹配。
"""

    prompt = f"""你是一个专业的算法可视化代码转换专家。

任务：将用户提供的{language}纯算法代码转换为符合 Algorithm Visualizer 框架要求的 JavaScript 可视化代码。

用户原始代码：
```{lang_info['code_block']}
{user_code}
```
{data_section}
核心规则：
1. **必须设置布局**：Layout.setRoot(new VerticalLayout([tracer, logger]));
2. **每次视觉变化后必须调用** Tracer.delay(); 这是产生动画帧的关键！
3. **保持原算法逻辑完全不变**，只添加可视化代码
4. **无论输入什么语言，都必须返回纯 JavaScript 代码！**
5. **不要包含任何自然语言解释**，只输出代码
6. 颜色规范：select='orange'(选中), patch='yellow'(修改), 完成时 select all 'green'
7. **必须使用用户的实际数据**，不要自己编造测试数据
8. ★★★ 每个 Tracer.delay() 后面必须加注释标注它对应的原始代码行号！格式：Tracer.delay(); //src:行号
   行号是1-based（从1开始计数），对应用户原始代码中的行号。
9. ★★★ **直接使用完整数据，忽略 stdin 解析**：上面给出的数组就是最终数据，直接 `tracer.set(数组)` 展示全部元素。
   不要模拟用户代码中的 input/stdin 解析逻辑（如 n=data[0]、arr=data[1:n+1] 等），
   不要做 slice/截取操作，不要猜测哪个数字是n或target。
   例如用户的原始代码：
   第1行: def preorder(arr, index, n, result):
   第2行:     if index >= n:
   第3行:         return
   第4行:     result.append(arr[index])
   第5行:     preorder(arr, 2*index+1, n, result)
   第6行:     preorder(arr, 2*index+2, n, result)
   
   你的转换代码中每个 Tracer.delay() 必须标注对应哪行原始代码：
   result.push(arr[index]);
   tracer.select(index);
   Tracer.delay(); //src:4    ← 对应原始代码第4行 result.append(arr[index])
   
   preorder(arr, 2*index+1, n, result);  // 递归调用
   Tracer.delay(); //src:5    ← 对应原始代码第5行
   
   preorder(arr, 2*index+2, n, result);  // 递归调用  
   Tracer.delay(); //src:6    ← 对应原始代码第6行
   
   注意：递归场景中同一行会被多次执行，每次都要有对应的 Tracer.delay(); //src:同一行号

{type_section}

现在请转换上面的 {language} 代码（算法类型：{algorithm_type}）："""

    try:
        response = await client.chat.completions.create(
            model=_QWEN_MODEL,
            messages=[
                {'role': 'system', 'content': '你是一个专业的算法可视化代码转换专家，擅长将纯算法代码转换为带有可视化效果的代码。'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.3
        )

        transformed = response.choices[0].message.content
        if not transformed:
            raise Exception('LLM 返回空结果')

        # 清理代码块标记
        transformed = transformed.strip()
        for prefix in ['```javascript\n', '```javascript', '```js\n', '```js', '```']:
            if transformed.startswith(prefix):
                transformed = transformed[len(prefix):]
                break
        if transformed.endswith('```'):
            transformed = transformed[:-3]

        result = transformed.strip()
        
        # ★★★ 关键修复：彻底提取纯 JS 代码，移除所有非代码内容 ★★★
        print(f"🔍 LLM 原始返回（前500字符）:\n{result[:500]}")
        print(f"🔍 原始返回总长度: {len(result)} 字符")
        
        # 1. 优先提取代码块内容
        code_block_match = re.search(r'```(?:javascript|js)\s*\n([\s\S]*?)```', result)
        if code_block_match:
            result = code_block_match.group(1).strip()
            print(f"✅ 从 ```javascript 代码块中提取了 JS 代码")
        else:
            # 尝试通用代码块
            code_block_match = re.search(r'```\s*\n([\s\S]*?)```', result)
            if code_block_match:
                result = code_block_match.group(1).strip()
                print(f"✅ 从 ``` 代码块中提取了代码")
            else:
                print(f"⚠️ 未找到代码块标记")
        
        # 2. 移除所有自然语言段落（关键修复）
        # 检测并移除代码后面的解释文本（如 "1. **创建可视化对象**"）
        lines = result.split('\n')
        code_lines = []
        found_non_code = False
        
        for line in lines:
            stripped = line.strip()
            
            # 如果检测到自然语言标记，停止收集
            if any(marker in stripped for marker in ['**', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.']):
                if not stripped.startswith('//') and not stripped.startswith('*'):
                    found_non_code = True
                    break
            
            # 只保留代码行和注释
            if not found_non_code:
                code_lines.append(line)
        
        if found_non_code:
            result = '\n'.join(code_lines)
            print(f"✅ 移除了代码后的自然语言解释文本")
        
        # 3. 移除代码块标记
        for marker in ['```javascript', '```js', '```']:
            result = result.replace(marker, '')
        
        # 4. 移除 Python 风格的 # 注释行
        result = re.sub(r'(?m)^\s*#[^!].*$', '', result)
        
        # 5. 移除 Python 特有的语法行
        result = re.sub(r'(?m)^\s*(import |from .* import|def [a-z_]+\(|class [A-Z]|if __name__).*$', '', result)
        
        # 6. 移除空行
        result = '\n'.join(line for line in result.split('\n') if line.strip())
        
        # 7. 验证基本 JS 语法
        if not result.strip():
            raise Exception('LLM 返回的代码为空')
        
        # 8. 验证是否包含关键的可视化代码
        has_tracer = 'Array1DTracer' in result or 'Array2DTracer' in result or 'GraphTracer' in result or 'TreeTracer' in result
        if not has_tracer:
            print(f"⚠️ 警告：返回的代码中未检测到 Tracer 构造")
        else:
            print(f"✅ 检测到 Tracer 构造")
        
        # 9. 验证括号匹配
        open_braces = result.count('{')
        close_braces = result.count('}')
        if open_braces != close_braces:
            print(f"⚠️ 警告：大括号不匹配 - 开括号: {open_braces}, 闭括号: {close_braces}")
            if open_braces > close_braces:
                result += '\n' + '}' * (open_braces - close_braces)
                print(f"✅ 已自动补全 {open_braces - close_braces} 个闭合大括号")
        
        # 10. ★★★ 关键修复：替换与 Worker 全局变量冲突的变量名 ★★★
        # Worker 已经声明了 Array1DTracer, Array2DTracer, GraphTracer, TreeTracer, LogTracer 等
        # 如果 LLM 用这些名字作为变量名（如 const TreeTracer = ...），会导致重复声明错误
        conflict_names = ['Array1DTracer', 'Array2DTracer', 'GraphTracer', 'TreeTracer', 'LogTracer', 'Layout', 'Tracer', 'VerticalLayout', 'HorizontalLayout']
        replaced_name = None
        for name in conflict_names:
            # 匹配 const/let/var TreeTracer = ... 的声明
            pattern = rf'\b(const|let|var)\s+{name}\s*='
            if re.search(pattern, result):
                # 替换为 tracer（小写）
                result = re.sub(pattern, rf'\1 tracer =', result)
                replaced_name = name
                print(f"✅ 已替换冲突变量名: {name} → tracer")
                break  # 只替换第一个冲突
        
        # 11. ★★★ 修复所有残留的冲突变量名引用 ★★★
        # 如果替换了 const TreeTracer = ... → const tracer = ...
        # 还需要把代码中所有 TreeTracer.xxx 替换为 tracer.xxx
        if replaced_name:
            # 替换所有对该变量的引用（如 TreeTracer.visit → tracer.visit）
            # 但要避免替换构造函数调用 new TreeTracer() → new tracer() （这是错误的）
            # 只替换方法调用和属性访问，不替换 new 后面的构造函数名
            result = re.sub(rf'\b{replaced_name}\.(?!prototype\b)', 'tracer.', result)
            print(f"✅ 已替换所有 {replaced_name} 的引用 → tracer")
        
        # 12. ★★★ 修复不完整的 class 声明 ★★★
        # 检测是否有孤立的 constructor 方法（缺少 class 声明）
        if re.search(r'(?m)^\s+constructor\s*\(', result) and 'class TreeNode' not in result:
            # 在 constructor 前面添加 class TreeNode {
            result = re.sub(r'(?m)(^\s+constructor\s*\()', r'class TreeNode {\n\1', result)
            print(f"✅ 已修复不完整的 class 声明")
            
            # 检查是否缺少闭合的 }
            open_braces = result.count('{')
            close_braces = result.count('}')
            if open_braces > close_braces:
                result += '\n' + '}' * (open_braces - close_braces)
                print(f"✅ 已补全 class 的闭合大括号")
        
        # 13. ★★★ 修复未定义的数据结构类（MinHeap、PriorityQueue 等）★★★
        # algorithm-visualizer 库不提供这些类，需要用简单实现替代
        if 'new MinHeap()' in result or 'MinHeap' in result:
            # 在代码开头添加 MinHeap 的简单实现
            minheap_impl = """
// ★★★ MinHeap 简单实现（algorithm-visualizer 不提供此）★★★
class MinHeap {
    constructor() { this.heap = []; }
    push(item) {
        this.heap.push(item);
        this.heap.sort((a, b) => (a.dist || a) - (b.dist || b));
    }
    pop() { return this.heap.shift(); }
    isEmpty() { return this.heap.length === 0; }
}
"""
            result = minheap_impl + '\n' + result
            print(f"✅ 已添加 MinHeap 简单实现")
        
        if 'new PriorityQueue()' in result or 'PriorityQueue' in result:
            # 在代码开头添加 PriorityQueue 的简单实现
            pq_impl = """
// ★★★ PriorityQueue 简单实现 ★★★
class PriorityQueue {
    constructor() { this.queue = []; }
    push(item) {
        this.queue.push(item);
        this.queue.sort((a, b) => (a.priority || a) - (b.priority || b));
    }
    pop() { return this.queue.shift(); }
    isEmpty() { return this.queue.length === 0; }
}
"""
            result = pq_impl + '\n' + result
            print(f"✅ 已添加 PriorityQueue 简单实现")
        
        # 14. ★★★ 修复 GraphTracer 不支持的方法 ★★★
        # GraphTracer 不支持 patchEdge/visitEdge/depatchEdge 等方法
        # 需要替换为支持的方法
        method_replacements = {
            'patchEdge': 'patch',      # patchEdge(u, v) → patch(u)
            'visitEdge': 'visit',      # visitEdge(u, v) → visit(u)
            'depatchEdge': 'depatch',  # depatchEdge(u, v) → depatch(u)
            'leaveEdge': 'leave',      # leaveEdge(u, v) → leave(u)
        }
        for old_method, new_method in method_replacements.items():
            if old_method in result:
                # 替换方法名，并移除多余的参数（边相关的第二个参数）
                # 例如: graphTracer.patchEdge(u, v, weight) → graphTracer.patch(u)
                result = re.sub(
                    rf'\.{old_method}\s*\(([^,]+),\s*[^)]+\)',
                    rf'.{new_method}(\1)',
                    result
                )
                print(f"✅ 已替换不支持的方法: {old_method} → {new_method}")
        
        print(f"✅ 最终代码长度: {len(result)} 字符")
        print(f"✅ 最终代码前300字符:\n{result[:300]}")
        print(f"✅ 最终代码后200字符:\n{result[-200:]}")
        
        return result

    except Exception as e:
        raise Exception(f'代码转换失败: {str(e)}')


def _detect_algorithm_type(code: str) -> str:
    """
    检测代码类型（数组、图、树、搜索等）
    优先级：函数名 > 关键词 > 代码模式
    """
    code_lower = code.lower()
    
    # 1. 函数名检测（最强信号）
    import re
    # 匹配 def xxx / function xxx / public static xxx 中的函数名
    func_names = re.findall(r'(?:def|function|class)\s+(\w+)', code)
    func_str = ' '.join(func_names).lower()
    
    if any(kw in func_str for kw in ['graph', 'bfs', 'dfs', 'dijkstra', 'kruskal', 'prim', 'topological']):
        return 'graph'
    if any(kw in func_str for kw in ['tree', 'inorder', 'preorder', 'postorder', 'levelorder', 'bst', 'heap', 'trie']):
        return 'tree'
    if any(kw in func_str for kw in ['search', 'find', 'binary', 'bisect', 'locate']):
        return 'search'
    if any(kw in func_str for kw in ['sort', 'bubble', 'selection', 'insertion', 'merge', 'quick', 'shell', 'heap_sort']):
        return 'sorting'
    if any(kw in func_str for kw in ['matrix', 'multiply', 'transpose', 'convolve']):
        return '2d-array'
    
    # 2. 关键词检测
    graph_keywords = ['adjacency', 'graph', 'edge', 'vertex', 'vertices',
                      'bfs', 'dfs', 'dijkstra', 'kruskal', 'prim', 'topological',
                      'shortest_path', 'bellman', 'floyd', 'tarjan']
    if any(kw in code_lower for kw in graph_keywords):
        return 'graph'
    
    tree_keywords = ['tree', 'treenode', 'binarytree', 'bst', 'binary_search_tree',
                     'inorder', 'preorder', 'postorder', 'traversal',
                     'left_child', 'right_child', 'parent_node',
                     '.left', '.right', '.val', '.value',
                     'heap', 'segment_tree', 'trie', 'avl']
    if any(kw in code_lower for kw in tree_keywords):
        return 'tree'
    
    search_keywords = ['binary_search', 'linear_search', 'binarysearch',
                       'search', 'find', 'lower_bound', 'upper_bound',
                       'bisect', 'two_pointer', 'two sum', 'twosum']
    sort_keywords = ['sort', 'bubble', 'selection', 'insertion', 'merge',
                     'quick', 'heap_sort', 'shell', 'counting', 'radix',
                     'bucket', 'swap']
    is_sort = any(kw in code_lower for kw in sort_keywords)
    if not is_sort and any(kw in code_lower for kw in search_keywords):
        return 'search'
    
    # 3. 矩阵/2D数组检测
    matrix_keywords = ['matrix', '2d', 'grid', '2d_array', 'ndarray',
                       'adjacency_matrix', 'distance_matrix']
    if any(kw in code_lower for kw in matrix_keywords):
        return '2d-array'
    if ']]' in code or '[[' in code:
        return '2d-array'
    
    # 4. 代码模式检测（看变量名和数据操作）
    if any(kw in code_lower for kw in ['low', 'high', 'mid', 'left', 'right', 'target', 'key']):
        return 'search'
    
    # 5. 默认为排序（Array1DTracer 通用）
    return 'sorting'


def _extract_user_data(code: str, language: str) -> dict:
    """
    从用户代码中提取实际数据（数组、矩阵、图等）
    支持 Python, JavaScript, Java, C++, C 多种语言
    
    返回格式:
    {
        'arrays': [{'name': 'arr', 'data': [5, 3, 8, 1]}],
        'matrices': [{'name': 'matrix', 'data': [[1,2],[3,4]]}],
        'graphs': None,  # 邻接矩阵或邻接表
        'trees': None
    }
    """
    result = {
        'arrays': [],
        'matrices': [],
        'graphs': None,
        'trees': None
    }
    
    # ============ 提取一维数组 ============
    
    def _parse_array_literal(text: str) -> list:
        """从文本中解析数组字面量 [1, 2, 3]"""
        text = text.strip()
        if text.startswith('[') and text.endswith(']'):
            text = text[1:-1].strip()
        if not text:
            return []
        # 尝试解析数字
        try:
            items = []
            for item in text.split(','):
                item = item.strip()
                if item:
                    # 尝试转为数字
                    try:
                        if '.' in item:
                            items.append(float(item))
                        else:
                            items.append(int(item))
                    except ValueError:
                        items.append(item)  # 字符串
            return items
        except Exception:
            return []
    
    def _parse_brace_array(text: str) -> list:
        """从文本中解析花括号数组 {1, 2, 3}（Java/C++/C）"""
        text = text.strip()
        if text.startswith('{') and text.endswith('}'):
            text = text[1:-1].strip()
        if not text:
            return []
        try:
            items = []
            for item in text.split(','):
                item = item.strip()
                if item:
                    try:
                        if '.' in item:
                            items.append(float(item))
                        else:
                            items.append(int(item))
                    except ValueError:
                        items.append(item)
            return items
        except Exception:
            return []
    
    # --- Python 风格: arr = [1, 2, 3] ---
    # 匹配简单一维数组（不含嵌套方括号）
    py_array_pattern = re.compile(
        r'(\w+)\s*=\s*(\[(?:(?!\[).)+\])',
        re.MULTILINE
    )
    for match in py_array_pattern.finditer(code):
        name = match.group(1)
        arr_text = match.group(2)
        data = _parse_array_literal(arr_text)
        if data and len(data) >= 2:  # 至少2个元素才有意义
            result['arrays'].append({'name': name, 'data': data})
    
    # --- JavaScript 风格: const/let/var arr = [1, 2, 3] ---
    js_array_pattern = re.compile(
        r'(?:const|let|var)\s+(\w+)\s*=\s*(\[(?:(?!\[).)+\])',
        re.MULTILINE
    )
    for match in js_array_pattern.finditer(code):
        name = match.group(1)
        arr_text = match.group(2)
        data = _parse_array_literal(arr_text)
        if data and len(data) >= 2:
            # 避免重复（Python 模式已匹配过）
            if not any(a['name'] == name for a in result['arrays']):
                result['arrays'].append({'name': name, 'data': data})
    
    # --- Java/C++ 风格: int[] arr = {1, 2, 3} 或 vector<int> arr = {1, 2, 3} ---
    java_array_pattern = re.compile(
        r'(?:\w+\[\]|vector<\w+>)\s+(\w+)\s*=\s*(\{[^{}]+\})',
        re.MULTILINE
    )
    for match in java_array_pattern.finditer(code):
        name = match.group(1)
        arr_text = match.group(2)
        data = _parse_brace_array(arr_text)
        if data and len(data) >= 2:
            if not any(a['name'] == name for a in result['arrays']):
                result['arrays'].append({'name': name, 'data': data})
    
    # --- C 风格: int arr[] = {1, 2, 3} ---
    c_array_pattern = re.compile(
        r'\w+\s+(\w+)\s*\[\s*\]\s*=\s*(\{[^{}]+\})',
        re.MULTILINE
    )
    for match in c_array_pattern.finditer(code):
        name = match.group(1)
        arr_text = match.group(2)
        data = _parse_brace_array(arr_text)
        if data and len(data) >= 2:
            if not any(a['name'] == name for a in result['arrays']):
                result['arrays'].append({'name': name, 'data': data})
    
    # ============ 提取二维数组/矩阵 ============
    
    # --- Python/JS 风格: matrix = [[1,2],[3,4]] ---
    # 匹配嵌套数组（包含至少一层嵌套方括号）
    py_matrix_pattern = re.compile(
        r'(\w+)\s*=\s*(\[\s*\[.+\]\s*\])',
        re.MULTILINE | re.DOTALL
    )
    for match in py_matrix_pattern.finditer(code):
        name = match.group(1)
        matrix_text = match.group(2)
        try:
            # 简单解析：找所有内层数组
            inner_arrays = re.findall(r'\[([^\[\]]+)\]', matrix_text)
            if inner_arrays:
                matrix = []
                for inner in inner_arrays:
                    row = _parse_array_literal('[' + inner + ']')
                    if row:
                        matrix.append(row)
                if matrix and len(matrix) >= 2:
                    result['matrices'].append({'name': name, 'data': matrix})
        except Exception:
            pass
    
    # --- Java/C++ 风格: int[][] matrix = {{1,2},{3,4}} ---
    java_matrix_pattern = re.compile(
        r'(?:\w+\[\]\[\]|int\s+\w+\[\]\[\])\s+(\w+)\s*=\s*(\{\s*\{.+\}\s*\})',
        re.MULTILINE | re.DOTALL
    )
    for match in java_matrix_pattern.finditer(code):
        name = match.group(1)
        matrix_text = match.group(2)
        try:
            inner_arrays = re.findall(r'\{([^{}]+)\}', matrix_text)
            if inner_arrays:
                matrix = []
                for inner in inner_arrays:
                    row = _parse_brace_array('{' + inner + '}')
                    if row:
                        matrix.append(row)
                if matrix and len(matrix) >= 2:
                    if not any(m['name'] == name for m in result['matrices']):
                        result['matrices'].append({'name': name, 'data': matrix})
        except Exception:
            pass
    
    # ============ 提取图数据（邻接矩阵或邻接表） ============
    
    # 如果算法类型是图，且找到了矩阵，将第一个矩阵作为图数据
    if result['matrices']:
        # 检查是否像邻接矩阵（方阵，对角线为0）
        first_matrix = result['matrices'][0]
        data = first_matrix['data']
        if data and len(data) == len(data[0]):  # 方阵
            # 检查对角线是否全为0
            is_adj = all(data[i][i] == 0 for i in range(len(data)))
            if is_adj:
                result['graphs'] = {'type': 'adjacency_matrix', 'data': data}
    
    # Python 字典邻接表: graph = {0: [1, 2], 1: [0, 3]}
    py_graph_pattern = re.compile(
        r'(\w+)\s*=\s*\{(\s*\d+\s*:\s*\[.+?\]\s*(?:,\s*\d+\s*:\s*\[.+?\]\s*)*)\}',
        re.MULTILINE | re.DOTALL
    )
    for match in py_graph_pattern.finditer(code):
        name = match.group(1)
        body = match.group(2)
        try:
            # 解析邻接表
            adj_list = {}
            entries = re.findall(r'(\d+)\s*:\s*\[([^\]]*)\]', body)
            for node, neighbors in entries:
                adj_list[int(node)] = _parse_array_literal('[' + neighbors + ']')
            if adj_list:
                # 转为邻接矩阵
                max_node = max(adj_list.keys())
                for neighbors in adj_list.values():
                    for n in neighbors:
                        if isinstance(n, int):
                            max_node = max(max_node, n)
                size = max_node + 1
                adj_matrix = [[0] * size for _ in range(size)]
                for node, neighbors in adj_list.items():
                    for n in neighbors:
                        if isinstance(n, int):
                            adj_matrix[node][n] = 1
                result['graphs'] = {'type': 'adjacency_list', 'data': adj_matrix}
        except Exception:
            pass
    
    # ============ 提取树数据 ============
    # 树通常通过 class Node 或构造函数定义，比较复杂
    # 简单检测：是否有 TreeNode 类定义
    if re.search(r'class\s+(?:Tree)?Node', code, re.IGNORECASE):
        result['trees'] = {'detected': True, 'note': '用户代码中定义了树节点类'}
    
    return result


def _format_extracted_data(extracted: dict) -> str:
    """
    将提取的数据格式化为提示词中的文本
    """
    lines = []
    
    if extracted['arrays']:
        for arr in extracted['arrays'][:3]:  # 最多取前3个
            lines.append(f"- 数组 `{arr['name']}`: {arr['data']}")
    
    if extracted['matrices']:
        for mat in extracted['matrices'][:2]:
            # 格式化矩阵为可读形式
            mat_str = '[' + ', '.join(str(row) for row in mat['data']) + ']'
            lines.append(f"- 矩阵 `{mat['name']}`: {mat_str}")
    
    if extracted['graphs']:
        if extracted['graphs']['type'] == 'adjacency_matrix':
            data = extracted['graphs']['data']
            mat_str = '[' + ', '.join(str(row) for row in data) + ']'
            lines.append(f"- 图的邻接矩阵: {mat_str}")
        elif extracted['graphs']['type'] == 'adjacency_list':
            data = extracted['graphs']['data']
            mat_str = '[' + ', '.join(str(row) for row in data) + ']'
            lines.append(f"- 图的邻接矩阵（从邻接表转换）: {mat_str}")
    
    if extracted['trees']:
        lines.append(f"- 树: {extracted['trees'].get('note', '检测到树结构')}")
    
    return '\n'.join(lines)


def _detect_stdin_input(code: str, language: str) -> bool:
    """
    检测代码是否从标准输入读取数据
    如果是，需要用户提供测试数据
    """
    code_lower = code.lower()
    
    # Python: sys.stdin, input(), raw_input()
    if language in ['python', 'python3']:
        stdin_patterns = [
            r'sys\.stdin',
            r'\binput\s*\(',
            r'\braw_input\s*\(',
            r'sys\.argv',
        ]
        return any(re.search(p, code) for p in stdin_patterns)
    
    # JavaScript: readline, process.stdin, prompt
    elif language == 'javascript':
        stdin_patterns = [
            r'process\.stdin',
            r'readline\s*\(',
            r'\bprompt\s*\(',
            r'require\s*\(\s*[\'"]readline[\'"]\s*\)',
        ]
        return any(re.search(p, code) for p in stdin_patterns)
    
    # Java: Scanner, BufferedReader
    elif language == 'java':
        stdin_patterns = [
            r'\bScanner\s*\(',
            r'BufferedReader',
            r'System\.in',
            r'scanner\.next',
        ]
        return any(re.search(p, code, re.IGNORECASE) for p in stdin_patterns)
    
    # C/C++: scanf, cin, getchar
    elif language in ['c', 'cpp', 'c++']:
        stdin_patterns = [
            r'\bscanf\s*\(',
            r'\bcin\s*>>',
            r'\bgetchar\s*\(',
            r'\bfgets\s*\(',
            r'\bfread\s*\(',
        ]
        return any(re.search(p, code) for p in stdin_patterns)
    
    return False


def _inject_test_data_to_prompt(code: str, test_data: str, language: str) -> str:
    """
    将用户提供的测试数据注入到代码中
    返回修改后的代码，用测试数据替换stdin读取
    """
    if not test_data or not test_data.strip():
        return code
    
    test_data = test_data.strip()
    
    # Python: 将 sys.stdin.read() 替换为固定字符串
    if language in ['python', 'python3']:
        # 替换 sys.stdin.read()
        modified = re.sub(
            r'sys\.stdin\.read\(\)',
            f'"""{test_data}"""',
            code
        )
        # 替换 input()
        modified = re.sub(
            r'\binput\(\)',
            f'"{test_data}"',
            modified
        )
        return modified
    
    # JavaScript: 将 readline() 等替换
    elif language == 'javascript':
        modified = re.sub(
            r'readline\s*\(\s*\)',
            f'"{test_data}"',
            code
        )
        return modified
    
    # 其他语言暂时不处理，让LLM自己处理
    return code


def _execute_in_sandbox(code: str, language: str, test_data: str = '', timeout_seconds: int = 5) -> dict:
    """
    在安全沙箱中执行用户代码，捕获所有变量值
    
    返回: {
        'success': bool,
        'variables': {'arr': [1,2,3], 'matrix': [[1,2],[3,4]], ...},
        'error': str (如果失败)
    }
    """
    import signal
    from contextlib import contextmanager
    
    # 目前只支持 Python 沙箱执行
    if language not in ['python', 'python3']:
        return {'success': False, 'error': f'沙箱执行暂不支持 {language} 语言'}
    
    # 注入测试数据（如果有 stdin 读取）
    if test_data:
        code = _inject_test_data_to_prompt(code, test_data, language)
    
    # 超时控制
    @contextmanager
    def timeout_context(seconds):
        def handler(signum, frame):
            raise TimeoutError(f"代码执行超时（{seconds}秒）")
        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    
    # 执行沙箱
    sandbox_globals = {'__builtins__': __builtins__}
    sandbox_locals = {}
    
    try:
        with timeout_context(timeout_seconds):
            exec(code, sandbox_globals, sandbox_locals)
        
        # 提取数组和矩阵类型的变量
        captured = {}
        for name, value in sandbox_locals.items():
            # 跳过内置和私有变量
            if name.startswith('_'):
                continue
            
            # 一维列表
            if isinstance(value, list) and value and not isinstance(value[0], list):
                # 检查是否全是数字
                if all(isinstance(x, (int, float)) for x in value):
                    captured[name] = value
            
            # 二维列表（矩阵）
            elif isinstance(value, list) and value and isinstance(value[0], list):
                # 检查是否全是数字列表
                if all(isinstance(row, list) and all(isinstance(x, (int, float)) for x in row) for row in value):
                    captured[name] = value
        
        return {'success': True, 'variables': captured}
    
    except TimeoutError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': f'执行失败: {type(e).__name__}: {str(e)}'}


def _parse_test_input(raw_input: str) -> dict:
    """
    解析原始测试输入字符串，自动识别数据结构
    支持格式：
      - "5 3 8 1 9" → 一维数组
      - "4\n1 2 3 4\n5 6 7 8" → 第一行是n，后面是矩阵
      - "4\n0 1 1 0\n1 0 0 1\n..." → 第一行是n，后面是邻接矩阵（图）
    """
    if not raw_input or not raw_input.strip():
        return {}
    
    # 按原始行分割（保留行结构，用于判断"第一行是n"）
    raw_lines = [l.strip() for l in raw_input.strip().split('\n') if l.strip()]
    
    # 把所有数字提取出来（支持空格、换行、逗号分隔）
    tokens = re.findall(r'-?\d+\.?\d*', raw_input)
    if not tokens:
        return {}
    
    # 尝试转为整数/浮点数
    nums = []
    for t in tokens:
        try:
            if '.' in t:
                nums.append(float(t))
            else:
                nums.append(int(t))
        except ValueError:
            continue
    
    if not nums:
        return {}
    
    result = {}
    
    # 情况1：多行输入，第一行可能是 n（矩阵/图大小）
    # 只在多行输入时才尝试"第一行是n"的逻辑
    if len(raw_lines) > 1 and len(nums) >= 2:
        first_line_nums = re.findall(r'-?\d+\.?\d*', raw_lines[0])
        # 第一行只有1个数字时，才把它当n
        if len(first_line_nums) == 1:
            n = nums[0]
            remaining = nums[1:]
            
            if isinstance(n, int) and n > 0:
                # 检查是否是 n×n 方阵
                if len(remaining) == n * n:
                    matrix = []
                    for i in range(n):
                        row = remaining[i * n : (i + 1) * n]
                        matrix.append(row)
                    
                    # 判断是否是邻接矩阵（对角线全0，非负）
                    is_adj = True
                    if all(isinstance(x, (int, float)) and x >= 0 for row in matrix for x in row):
                        if all(matrix[i][i] == 0 for i in range(n)):
                            is_adj = True
                    
                    if is_adj:
                        result['graph'] = {'type': 'adjacency_matrix', 'data': matrix, 'size': n}
                    else:
                        result['matrix'] = {'data': matrix, 'size': f'{n}x{n}'}
                    return result
                
                # 检查是否是 n×m 矩阵（非方阵）
                if len(remaining) % n == 0 and len(remaining) >= n:
                    m = len(remaining) // n
                    if m > 1:
                        matrix = []
                        for i in range(n):
                            row = remaining[i * m : (i + 1) * m]
                            matrix.append(row)
                        result['matrix'] = {'data': matrix, 'size': f'{n}x{m}'}
                        return result
    
    # 情况2：纯一维数组（所有数字都是数组元素，不做任何截断）
    if len(nums) >= 1:
        result['array'] = {'data': nums}
    
    return result


def _format_parsed_input(parsed: dict) -> str:
    """将解析后的测试输入格式化为提示词文本"""
    lines = []
    if 'graph' in parsed:
        g = parsed['graph']
        mat_str = '[\n' + ',\n'.join('    ' + str(row) for row in g['data']) + '\n  ]'
        lines.append(f"- 图的邻接矩阵（{g['size']}个节点）: {mat_str}")
    if 'matrix' in parsed:
        m = parsed['matrix']
        mat_str = '[\n' + ',\n'.join('    ' + str(row) for row in m['data']) + '\n  ]'
        lines.append(f"- 矩阵（{m['size']}）: {mat_str}")
    if 'array' in parsed:
        lines.append(f"- 数组: {parsed['array']['data']}")
    return '\n'.join(lines)


# ==================== API 路由 ====================

@router.get("/viz", response_class=HTMLResponse, tags=["可视化"])
@router.get("/visualization", response_class=HTMLResponse, tags=["可视化"])
async def serve_visualization_frontend():
    """算法可视化前端页面"""
    if os.path.exists(_FRONTEND_HTML):
        with open(_FRONTEND_HTML, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<html><body><h1>可视化前端文件未找到</h1><p>请确保 server-master/public/frontend-built/index.html 存在</p></body></html>",
        status_code=404
    )


# 测试页面路径
_VIZ_TEST_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'viz_test.html')


@router.get("/viz/test", response_class=HTMLResponse, tags=["可视化"])
async def serve_viz_test():
    """算法可视化测试页面"""
    if os.path.exists(_VIZ_TEST_HTML):
        with open(_VIZ_TEST_HTML, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>测试页面未找到</h1><p>templates/viz_test.html</p>", status_code=404)


@router.get("/viz/health", tags=["可视化"])
async def viz_health():
    """可视化服务健康检查"""
    # 获取线程池状态
    try:
        executor = _get_executor()
        pool_status = executor.get_system_status()
    except Exception:
        pool_status = {"error": "无法获取线程池状态"}
    
    return {
        "status": "ok",
        "algorithms_dir_exists": os.path.isdir(_ALGORITHMS_DIR),
        "frontend_exists": os.path.exists(_FRONTEND_HTML),
        "lib_exists": os.path.exists(_ALGO_VIS_LIB),
        "worker_exists": os.path.exists(_WORKER_JS),
        "llm_cache_size": 0,
        "llm_cache_max_size": 0,
        "thread_pool": pool_status,
        "routes": [
            "GET  /viz                          - 可视化前端页面",
            "GET  /api/algorithms               - 算法列表（层级结构）",
            "GET  /api/algorithms/{cat}/{algo}   - 算法详情",
            "POST /api/visualize/transform      - LLM 代码转换",
            "GET  /api/tracers/js               - algorithm-visualizer 库",
            "GET  /api/tracers/js/worker        - Web Worker 脚本",
            "POST /api/visualizations           - 上传可视化数据",
            "GET  /api/visualizations/{id}      - 获取可视化数据",
            "POST /api/visualize/clear-cache    - 清理 LLM 缓存",
        ]
    }


# ---- 算法 API ----

@router.get("/api/algorithms", tags=["可视化"])
async def get_algorithms():
    """获取算法列表（层级结构），对应 Node.js AlgorithmsController.getHierarchy"""
    return _build_hierarchy()


@router.get("/api/algorithms/sitemap.txt", tags=["可视化"])
async def get_algorithms_sitemap():
    """算法站点地图"""
    hierarchy = _build_hierarchy()
    urls = []
    for cat in hierarchy.get('categories', []):
        for algo in cat.get('algorithms', []):
            urls.append(f"https://algorithm-visualizer.org/{cat['key']}/{algo['key']}")
    return PlainTextResponse('\n'.join(urls))


@router.get("/api/algorithms/{category_key}/{algorithm_key}", tags=["可视化"])
async def get_algorithm_detail(category_key: str, algorithm_key: str):
    """获取指定算法详情，对应 Node.js AlgorithmsController.getAlgorithm"""
    result = _find_algorithm(category_key, algorithm_key)
    if not result:
        raise HTTPException(status_code=404, detail="Algorithm not found.")
    return {"algorithm": result}


# ---- LLM 代码转换 API ----

@router.post("/api/visualize/transform", tags=["可视化"])
async def visualize_transform(request: Request):
    """
    LLM 代码转换 - 将纯算法代码转为可视化代码
    对应 Node.js VisualizeController.transformCode
    
    ★★★ 异步版本：使用并发执行器 ★★★
    通过 ConcurrentExecutor(max_workers=10) 获取 10 工作线程的线程池，
    每个用户的 LLM 转换任务在独立线程中执行，互不阻塞。
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"success": False, "error": "请求体格式错误"})

    code = body.get('code', '')
    if not code:
        return JSONResponse(status_code=400, content={"success": False, "error": "代码不能为空"})

    algorithm_type = body.get('algorithmType', 'auto')
    language = body.get('language', 'javascript')
    test_data = body.get('testData', '')  # 新增：测试数据参数

    try:
        # 自动检测算法类型
        if algorithm_type == 'auto' or not algorithm_type:
            algorithm_type = _detect_algorithm_type(code)

        print(f"🤖 开始 LLM 代码转换 (类型: {algorithm_type}, 语言: {language}, 测试数据: {test_data[:50] if test_data else '无'}...)")

        # ★★★ 使用模块级执行器单例，避免每次请求新建线程池 ★★★
        executor = _get_executor()
        
        transformed_code = await executor.execute_async(
            _transform_code_with_llm,  # async 函数
            code,
            algorithm_type,
            language,
            test_data,  # 传递测试数据
            task_id=f"viz_transform_{body.get('user_id', 'anon')}"
        )

        print("✅ 代码转换成功")

        return {"success": True, "code": transformed_code, "originalCode": code, "language": language, "detectedType": algorithm_type}

    except Exception as e:
        print(f"❌ 代码转换失败: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/api/visualize/clear-cache", tags=["可视化"])
async def clear_llm_cache():
    """清理 LLM 转换缓存（已禁用缓存功能）"""
    return {"success": True, "cleared": 0, "message": "缓存功能已禁用"}


@router.post("/api/visualize/detect-stdin", tags=["可视化"])
async def detect_stdin_mode(request: Request):
    """
    检测代码是否需要标准输入
    用于前端显示测试数据输入框
    """
    try:
        body = await request.json()
        code = body.get('code', '')
        language = body.get('language', 'python')
        
        if not code:
            return {"needsInput": False, "message": "代码为空"}
        
        needs_stdin = _detect_stdin_input(code, language)
        
        return {
            "needsInput": needs_stdin,
            "language": language,
            "message": "代码需要测试数据输入" if needs_stdin else "代码包含硬编码数据"
        }
        
    except Exception as e:
        print(f"❌ 检测 stdin 模式失败: {e}")
        return {"needsInput": False, "error": str(e)}


# ---- 静态资源 ----

@router.get("/api/tracers/js", tags=["可视化"])
async def serve_tracer_lib():
    """提供 algorithm-visualizer UMD 库文件（worker.js 通过 XHR 加载此文件）"""
    if os.path.exists(_ALGO_VIS_LIB):
        return FileResponse(
            _ALGO_VIS_LIB,
            media_type='application/javascript',
            headers={'Cache-Control': 'public, max-age=3600'}
        )
    raise HTTPException(status_code=404, detail="algorithm-visualizer library not found")


@router.get("/api/tracers/js/worker", tags=["可视化"])
async def serve_worker_js():
    """提供 Web Worker 脚本（前端通过 new Worker('/api/tracers/js/worker') 加载）"""
    if os.path.exists(_WORKER_JS):
        return FileResponse(
            _WORKER_JS,
            media_type='application/javascript',
            headers={'Content-Type': 'application/javascript', 'Cache-Control': 'no-cache'}
        )
    raise HTTPException(status_code=404, detail="Worker script not found")


# ---- 可视化数据 CRUD ----

@router.post("/api/visualizations", tags=["可视化"])
async def upload_visualization(request: Request):
    """上传并存储可视化 JSON 数据"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "请求体格式错误"})

    content = body.get('content', '')
    if not content:
        return JSONResponse(status_code=400, content={"error": "content is required"})

    viz_id = str(uuid.uuid4())
    _viz_store[viz_id] = content

    # 返回访问 URL
    return PlainTextResponse(f"/api/visualizations/{viz_id}")


@router.get("/api/visualizations/{viz_id}", tags=["可视化"])
async def get_visualization(viz_id: str):
    """获取可视化 JSON 数据（读取后自动删除）"""
    content = _viz_store.pop(viz_id, None)
    if content is None:
        raise HTTPException(status_code=404, detail="Visualization Expired")
    return JSONResponse(content=content)

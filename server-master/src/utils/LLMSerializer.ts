import OpenAI from 'openai';

export class LLMSerializer {
  private client: OpenAI;

  constructor() {
    this.client = new OpenAI({
      apiKey: process.env.QWEN_API_KEY || 'sk-4731a59edaee45c385a11c055b0d0a01',
      baseURL: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    });
  }

  /**
   * 将用户代码转换为符合可视化要求的代码
   */
  async transformCode(userCode: string, algorithmType: string = 'sorting'): Promise<string> {
    const prompt = `你是一个专业的算法可视化代码转换专家。

任务：将用户提供的纯算法代码转换为符合 Algorithm Visualizer 框架要求的可视化代码。

用户原始代码：
\`\`\`javascript
${userCode}
\`\`\`

转换要求：
1. **自动创建可视化对象**：
   - 如果代码操作一维数组，使用 Array1DTracer
   - 如果代码操作二维数组/矩阵，使用 Array2DTracer
   - 如果代码操作图结构，使用 GraphTracer
   - 添加 LogTracer 用于输出日志

2. **必须设置布局**：
   \`\`\`javascript
   Layout.setRoot(new VerticalLayout([tracer, logger]));
   \`\`\`

3. **设置初始数据**：
   \`\`\`javascript
   tracer.set(array);
   Tracer.delay();
   \`\`\`

4. **在关键步骤添加可视化**：
   - 选中元素：\`tracer.select(index, 'color')\`
   - 修改元素：\`tracer.patch(index, value)\`
   - 取消修改：\`tracer.depatch(index)\`
   - 取消选中：\`tracer.deselect(index)\`
   - **每次视觉变化后必须调用** \`Tracer.delay()\`

5. **保持原算法逻辑完全不变**，只添加可视化代码

6. **变量名可以自由命名**，但要保持一致性

7. 返回完整的、可执行的 JavaScript 代码，不要包含解释文字

示例转换：
输入：
\`\`\`javascript
for (let i = 1; i < n; i++) {
    let key = arr[i];
    let j = i - 1;
    while (j >= 0 && arr[j] > key) {
        arr[j + 1] = arr[j];
        j--;
    }
    arr[j + 1] = key;
}
\`\`\`

输出：
\`\`\`javascript
const tracer = new Array1DTracer('插入排序');
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([tracer, logger]));

const array = [5, 3, 8, 1, 9];
const N = array.length;
tracer.set(array);
logger.println('开始排序');
Tracer.delay();

for (let i = 1; i < N; i++) {
    const key = array[i];
    let j = i - 1;

    tracer.select(i, 'orange');
    Tracer.delay();
    logger.println('处理元素: ' + key);

    while (j >= 0 && array[j] > key) {
        tracer.select(j, 'red');
        Tracer.delay();

        array[j + 1] = array[j];
        tracer.patch(j + 1, array[j + 1]);
        Tracer.delay();
        tracer.depatch(j + 1);
        tracer.deselect(j);

        j--;
    }

    array[j + 1] = key;
    tracer.patch(j + 1, key);
    Tracer.delay();
    tracer.depatch(j + 1);
    tracer.deselect(i);
}

logger.println('排序完成');
const allIndices = array.map((_, idx) => idx);
tracer.select(allIndices, 'green');
Tracer.delay();
\`\`\`

**图算法示例（DFS）：**
输入：
\`\`\`javascript
function dfs(graph, startNode) {
    const visited = new Set();
    const result = [];

    function dfsHelper(node) {
        visited.add(node);
        result.push(node);

        for (const neighbor of graph[node]) {
            if (!visited.has(neighbor)) {
                dfsHelper(neighbor);
            }
        }
    }

    dfsHelper(startNode);
    return result;
}

const graph = [
    [0, 1, 1, 0],
    [1, 0, 0, 1],
    [1, 0, 0, 1],
    [0, 1, 1, 0]
];

dfs(graph, 0);
\`\`\`

输出：
\`\`\`javascript
const graphTracer = new GraphTracer().directed(false);
const logger = new LogTracer('日志');
Layout.setRoot(new VerticalLayout([graphTracer, logger]));

const graph = [
    [0, 1, 1, 0],
    [1, 0, 0, 1],
    [1, 0, 0, 1],
    [0, 1, 1, 0]
];

graphTracer.set(graph);
Tracer.delay();

function dfs(graph, startNode) {
    const visited = new Array(graph.length).fill(false);
    const result = [];

    function dfsHelper(node, prevNode) {
        visited[node] = true;
        result.push(node);

        if (prevNode !== undefined) {
            graphTracer.visit(node, prevNode);
            Tracer.delay();
        } else {
            graphTracer.visit(node);
            Tracer.delay();
        }

        for (let neighbor = 0; neighbor < graph.length; neighbor++) {
            if (graph[node][neighbor] && !visited[neighbor]) {
                dfsHelper(neighbor, node);
            }
        }
    }

    dfsHelper(startNode);
    return result;
}

dfs(graph, 0);
logger.println('DFS 遍历完成');
\`\`\`

现在请 convert the following code（算法类型：${algorithmType}）：
`;

    try {
      const response = await this.client.chat.completions.create({
        model: 'qwen-max',
        messages: [
          {
            role: 'system',
            content: '你是一个专业的算法可视化代码转换专家，擅长将纯算法代码转换为带有可视化效果的代码。',
          },
          {
            role: 'user',
            content: prompt,
          },
        ],
        temperature: 0.3, // 较低温度，保证代码准确性
      });

      const transformedCode = response.choices[0].message.content;

      if (!transformedCode) {
        throw new Error('LLM 返回空结果');
      }

      // 清理代码块标记
      let cleanedCode = transformedCode.trim();
      if (cleanedCode.startsWith('```javascript')) {
        cleanedCode = cleanedCode.replace(/^```javascript\n?/, '').replace(/\n?```$/, '');
      } else if (cleanedCode.startsWith('```js')) {
        cleanedCode = cleanedCode.replace(/^```js\n?/, '').replace(/\n?```$/, '');
      } else if (cleanedCode.startsWith('```')) {
        cleanedCode = cleanedCode.replace(/^```\n?/, '').replace(/\n?```$/, '');
      }

      console.log('✅ LLM 代码转换成功');
      return cleanedCode;
    } catch (error) {
      console.error('❌ LLM 代码转换失败:', error);
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`代码转换失败: ${errorMessage}`);
    }
  }

  /**
   * 检测代码类型（数组、图、树等）
   */
  detectAlgorithmType(code: string): string {
    if (code.includes('adjacency') || code.includes('graph') || code.includes('edge')) {
      return 'graph';
    }
    if (code.includes('tree') || code.includes('node') || code.includes('children')) {
      return 'tree';
    }
    if (code.includes('matrix') || code.includes('2d') || code.includes('grid')) {
      return '2d-array';
    }
    return 'sorting'; // 默认
  }
}

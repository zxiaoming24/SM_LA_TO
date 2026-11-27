// Worker 环境配置
if (typeof self.process === 'undefined') {
  self.process = { env: { ALGORITHM_VISUALIZER: '1' } };
}

// 捕获所有命令
let AlgorithmVisualizer = null;

// 初始化函数，由外部调用
function initialize(code) {
  // 动态加载 algorithm-visualizer 库
  if (!AlgorithmVisualizer) {
    // 通过同步 XMLHttpRequest 加载库文件
    const xhr = new XMLHttpRequest();
    xhr.open('GET', '/api/tracers/js', false); // 同步请求
    xhr.send();
    
    if (xhr.status === 200) {
      // 执行库代码
      eval(xhr.responseText);
      // 获取全局暴露的 AlgorithmVisualizer
      AlgorithmVisualizer = self.AlgorithmVisualizer || this.AlgorithmVisualizer;
    } else {
      throw new Error('Failed to load algorithm-visualizer library');
    }
  }
  
  const sandbox = code => {
    // 创建模块系统
    const module = { exports: {} };
    const exports = module.exports;
    
    const require = name => {
      if (name === 'algorithm-visualizer') {
        return AlgorithmVisualizer;
      }
      throw new Error(`Cannot find module: ${name}`);
    };
    
    // 自动注入可视化 API 到全局作用域
    // 这样用户代码可以直接使用 tracer, logger, Tracer 等，不需要 require
    let userCode = code;
    
    // 检测用户是否已经导入了库
    const hasRequire = code.includes('require(');
    const hasTracer = code.includes('new Array1DTracer') || 
                      code.includes('new Array2DTracer') || 
                      code.includes('new GraphTracer') ||
                      code.includes('new TreeTracer');
    
    console.log('Worker 环境检查:');
    console.log('- AlgorithmVisualizer 是否存在:', !!AlgorithmVisualizer);
    console.log('- AlgorithmVisualizer.Tracer 是否存在:', !!(AlgorithmVisualizer && AlgorithmVisualizer.Tracer));
    console.log('- AlgorithmVisualizer.Array1DTracer 是否存在:', !!(AlgorithmVisualizer && AlgorithmVisualizer.Array1DTracer));
    console.log('- 用户代码是否包含 require:', hasRequire);
    console.log('- 用户代码是否包含 tracer 构造:', hasTracer);
    
    // 如果用户没有导入，自动添加 API（但不创建实例）
    if (!hasRequire) {
      // 只注入 API 类，不创建默认实例
      // 让用户自己决定创建哪些 tracer
      const autoSetup = `
        // ============================================
        // 系统自动注入的可视化 API（无需手动导入）
        // ============================================
        
        // Tracer 类 - 用于可视化不同类型的数据结构
        const Tracer = AlgorithmVisualizer.Tracer;              // 基础类，提供 delay() 方法
        const Array1DTracer = AlgorithmVisualizer.Array1DTracer; // 一维数组可视化
        const Array2DTracer = AlgorithmVisualizer.Array2DTracer; // 二维数组/矩阵可视化
        const GraphTracer = AlgorithmVisualizer.GraphTracer;     // 图结构可视化
        const TreeTracer = AlgorithmVisualizer.TreeTracer;       // 树结构可视化
        const LogTracer = AlgorithmVisualizer.LogTracer;         // 日志输出
        
        // 布局类 - 用于组织多个 tracer 的显示
        const Layout = AlgorithmVisualizer.Layout;               // 布局管理器
        const VerticalLayout = AlgorithmVisualizer.VerticalLayout;   // 垂直布局
        const HorizontalLayout = AlgorithmVisualizer.HorizontalLayout; // 水平布局
        
        // 工具类
        const Randomize = AlgorithmVisualizer.Randomize;         // 生成随机数据
        
        // ============================================
        // 使用示例：
        // const tracer = new Array1DTracer('排序');
        // const logger = new LogTracer();
        // Layout.setRoot(new VerticalLayout([tracer, logger]));
        // tracer.set([5, 3, 8, 1]);
        // Tracer.delay();  // 每次视觉变化后调用
        // ============================================
      `;
      
      userCode = autoSetup + '\n' + code;
    }
    
    // 使用 Function 构造函数创建沙箱环境
    try {
      const func = new Function('require', 'module', 'exports', 'AlgorithmVisualizer', userCode);
      func(require, module, exports, AlgorithmVisualizer);
    } catch (error) {
      console.error('沙箱执行错误:', error);
      console.error('错误堆栈:', error.stack);
      throw error;
    }
  };
  
  // 初始化命令序列
  AlgorithmVisualizer.Commander.init();
  
  const lines = code.split('\n').map((line, i) => line.replace(/(\.\s*delay\s*)\(\s*\)/g, `$1(${i})`));
  const processedCode = lines.join('\n');
  
  try {
    sandbox(processedCode);
    
    // 获取命令序列
    const commands = AlgorithmVisualizer.Commander.commands || [];
    
    console.log('原始命令数量:', commands.length);
    console.log('前3个原始命令:', commands.slice(0, 3));
    
    // 检查是否生成了命令
    if (commands.length === 0) {
      console.warn('⚠️ 警告: 没有生成任何可视化命令');
      console.warn('可能的原因:');
      console.warn('1. 代码中没有调用 Tracer.delay()');
      console.warn('2. 没有创建任何 Tracer 实例');
      console.warn('3. 代码执行过程中出现错误');
    }
    
    // 转换命令格式为前端可理解的格式
    const formattedCommands = [];
    const tracerInstances = {}; // 跟踪每个 tracer 实例的类型 {tracerId: type}
    let currentTracerId = null; // 当前操作的 tracer 实例 ID
    let currentTracerType = 'array1d'; // 当前 tracer 类型，用于 select/deselect 区分维度
    
    for (const cmd of commands) {
      // 处理 algorithm-visualizer 库的命令格式
      if (cmd.method && cmd.args) {
        // 检测是否为 Tracer 构造函数调用
        if (cmd.method === 'GraphTracer' || cmd.method === 'Array1DTracer' || 
            cmd.method === 'Array2DTracer' || cmd.method === 'TreeTracer') {
          // 创建新的 tracer 实例 ID
          currentTracerId = cmd.instanceId || `tracer_${Date.now()}_${Math.random()}`;
          
          if (cmd.method === 'GraphTracer') {
            tracerInstances[currentTracerId] = 'graph';
            currentTracerType = 'graph';
          } else if (cmd.method === 'Array1DTracer') {
            tracerInstances[currentTracerId] = 'array1d';
            currentTracerType = 'array1d';
          } else if (cmd.method === 'Array2DTracer') {
            tracerInstances[currentTracerId] = 'array2d';
            currentTracerType = 'array2d';
          } else if (cmd.method === 'TreeTracer') {
            tracerInstances[currentTracerId] = 'tree';
            currentTracerType = 'tree';
          }
          continue;
        }
        
        // 检测是否切换了 tracer 实例（通过方法调用的上下文）
        // 注意：algorithm-visualizer 库中，命令会记录是哪个 tracer 调用的
        if (cmd.tracerId) {
          currentTracerId = cmd.tracerId;
        }
        
        const tracerType = tracerInstances[currentTracerId] || 'array1d';
        
        switch (cmd.method) {
          case 'set':
            if (cmd.args[0]) {
              // 根据 tracer 类型和数据格式判断
              if (tracerType === 'graph') {
                // GraphTracer 的 set 方法，将邻接矩阵转换为图结构
                const adjacencyMatrix = cmd.args[0];
                if (Array.isArray(adjacencyMatrix) && adjacencyMatrix.length > 0 && Array.isArray(adjacencyMatrix[0])) {
                  const nodes = [];
                  const edges = [];
                  
                  // 创建节点
                  for (let i = 0; i < adjacencyMatrix.length; i++) {
                    nodes.push({ id: i, label: i.toString() });
                  }
                  
                  // 创建边（只添加上三角，避免重复，处理无向图）
                  for (let i = 0; i < adjacencyMatrix.length; i++) {
                    for (let j = i + 1; j < adjacencyMatrix.length; j++) {
                      if (adjacencyMatrix[i][j] && adjacencyMatrix[i][j] !== 0) {
                        edges.push({
                          from: i,
                          to: j,
                          weight: adjacencyMatrix[i][j]
                        });
                      }
                    }
                  }
                  
                  formattedCommands.push({ 
                    type: 'set', 
                    visualizationType: 'graph',
                    nodes: nodes,
                    edges: edges
                  });
                }
              } else if (Array.isArray(cmd.args[0])) {
                // 数组类型
                if (cmd.args[0].length > 0 && Array.isArray(cmd.args[0][0])) {
                  formattedCommands.push({ type: 'set', visualizationType: 'array2d', data: cmd.args[0] });
                } else {
                  formattedCommands.push({ type: 'set', visualizationType: 'array1d', data: cmd.args[0] });
                }
              } else if (cmd.args[0].nodes && cmd.args[0].edges) {
                // 已经是图结构
                formattedCommands.push({ 
                  type: 'set',
                  visualizationType: 'graph',
                  nodes: cmd.args[0].nodes || [],
                  edges: cmd.args[0].edges || []
                });
              } else if (cmd.args[0].root) {
                // 树类型
                formattedCommands.push({ 
                  type: 'set',
                  visualizationType: 'tree',
                  root: cmd.args[0].root
                });
              }
            }
            break;
          case 'patch':
            if (cmd.args.length >= 2) {
              if (currentTracerType === 'array2d' && cmd.args.length >= 3) {
                // Array2DTracer.patch(row, col, value)
                formattedCommands.push({ type: 'patch', index: `${cmd.args[0]},${cmd.args[1]}`, value: cmd.args[2] });
              } else {
                formattedCommands.push({ type: 'patch', index: cmd.args[0], value: cmd.args[1] });
              }
            }
            break;
          case 'depatch':
            if (cmd.args.length >= 1) {
              if (currentTracerType === 'array2d' && cmd.args.length >= 2) {
                formattedCommands.push({ type: 'depatch', index: `${cmd.args[0]},${cmd.args[1]}` });
              } else {
                formattedCommands.push({ type: 'depatch', index: cmd.args[0] });
              }
            }
            break;
          case 'select':
            if (cmd.args.length >= 1) {
              if (currentTracerType === 'array2d') {
                // Array2DTracer.select 参数: (sx, sy, ex, ey) 范围选择
                // 生成 "row,col" 格式的索引，匹配 renderArray2D 的 key 格式
                const indices = [];
                if (cmd.args.length >= 4) {
                  const sx = cmd.args[0], sy = cmd.args[1], ex = cmd.args[2], ey = cmd.args[3];
                  for (let r = Math.min(sx,ex); r <= Math.max(sx,ex); r++)
                    for (let c = Math.min(sy,ey); c <= Math.max(sy,ey); c++)
                      indices.push(`${r},${c}`);
                } else if (cmd.args.length >= 2) {
                  indices.push(`${cmd.args[0]},${cmd.args[1]}`);
                } else {
                  const a = Array.isArray(cmd.args[0]) ? cmd.args[0] : [cmd.args[0]];
                  a.forEach(i => indices.push(String(i)));
                }
                formattedCommands.push({ type: 'select', indices });
              } else {
                const indices = Array.isArray(cmd.args[0]) ? cmd.args[0] : [cmd.args[0]];
                formattedCommands.push({ type: 'select', indices });
              }
            }
            break;
          case 'deselect':
            if (cmd.args.length >= 1) {
              if (currentTracerType === 'array2d') {
                const indices = [];
                if (cmd.args.length >= 4) {
                  const sx = cmd.args[0], sy = cmd.args[1], ex = cmd.args[2], ey = cmd.args[3];
                  for (let r = Math.min(sx,ex); r <= Math.max(sx,ex); r++)
                    for (let c = Math.min(sy,ey); c <= Math.max(sy,ey); c++)
                      indices.push(`${r},${c}`);
                } else if (cmd.args.length >= 2) {
                  indices.push(`${cmd.args[0]},${cmd.args[1]}`);
                } else {
                  const a = Array.isArray(cmd.args[0]) ? cmd.args[0] : [cmd.args[0]];
                  a.forEach(i => indices.push(String(i)));
                }
                formattedCommands.push({ type: 'deselect', indices });
              } else {
                const indices = Array.isArray(cmd.args[0]) ? cmd.args[0] : [cmd.args[0]];
                formattedCommands.push({ type: 'deselect', indices });
              }
            }
            break;
          case 'visit':
            // GraphTracer 的 visit 方法（访问边）
            if (cmd.args.length >= 2) {
              formattedCommands.push({ 
                type: 'select', 
                indices: [cmd.args[0], cmd.args[1]]
              });
            }
            break;
          case 'leave':
            // GraphTracer 的 leave 方法（离开边）
            if (cmd.args.length >= 2) {
              formattedCommands.push({ 
                type: 'deselect', 
                indices: [cmd.args[0], cmd.args[1]]
              });
            }
            break;
          case 'addEdge':
            // 图的添加边操作
            if (cmd.args.length >= 2) {
              formattedCommands.push({ 
                type: 'addEdge', 
                from: cmd.args[0], 
                to: cmd.args[1],
                weight: cmd.args[2] || null
              });
            }
            break;
          case 'removeEdge':
            // 图的删除边操作
            if (cmd.args.length >= 2) {
              formattedCommands.push({ 
                type: 'removeEdge', 
                from: cmd.args[0], 
                to: cmd.args[1]
              });
            }
            break;
          case 'println':
          case 'print':
            if (cmd.args.length >= 1) {
              formattedCommands.push({ type: 'log', message: String(cmd.args[0]) });
            }
            break;
          case 'delay':
            // 保留 delay 命令，提取源行号
            if (cmd.args && cmd.args.length >= 1) {
              formattedCommands.push({ 
                type: 'delay', 
                lineNumber: cmd.args[0] || 0
              });
            }
            break;
          default:
            // 其他 tracer 方法（如 chart、setRoot、directed、weighted、log 等）跳过
            break;
        }
      } else if (cmd.type) {
        // 已经是正确格式的命令
        formattedCommands.push(cmd);
      }
    }
    
    console.log('格式化后的命令数量:', formattedCommands.length);
    console.log('前3个格式化命令:', formattedCommands.slice(0, 3));
    
    postMessage(formattedCommands);
  } catch (error) {
    console.error('Worker 执行错误:', error);
    postMessage({ error: error.message });
  }
}

onmessage = e => {
  initialize(e.data);
};

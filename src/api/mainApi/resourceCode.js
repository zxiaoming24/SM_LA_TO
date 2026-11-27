//导入request对象
import request from '@/utils/request.js'
import { requestPythonAll } from '@/utils/request.js'

//根据用户id获取简单列表
export const getCodeListByUserId = (userId) => request.get(`/code/${userId}`)

//生成提交
export const submitCodeApi = (data) => request.post('/code/getId', data)

//获取生成进度
export const getCodeProgressApi = (id) => request.get(`/code/getProgress/${id}`)

//根据id查询对应的题目
export const getValueApi = (id) => request.get(`/code/getPractice/${id}`)

//根据id删除对应的阅读材料
export const deleteCodeByIdApi = (id) => request.delete(`/code/delete/${id}`)



//提交-评估
export const submitExamineApi = (data) => request.post('/code/submit/answer', data)

//获取评估进度
export const getExamineProgressApi = (id) => request.get(`/code/getSubmitResult/${id}`)

//获取本题评估历史列表
export const getExamineListApi = (practiceId, userId) => request.get(`/code/practiceAnswerList/${practiceId}/${userId}`)

//根据id删除对应的历史记录
export const deleteExamineByIdApi = (id) => request.delete(`/code/deleteAnswer/${id}`)

//根据id查询对应的历史评估页
export const getExamineValueApi = (id) => request.get(`/code/getSubmitResultById/${id}`)


//根据题目id查询排行榜
export const getCodeRankListApi = (practiceId) => request.get(`/rank/codeExamine/${practiceId}`)


//我与编程题排行榜中的成员的代码比较
export const codeCompareApi = (data) => request.post('/code/compare', data)

//=============================算法可视化==============================
export const codeVisualApi = (data) => request.post('/code/visualize/transform', data)
// 返回样例：{
//     "code": 1,
//     "msg": "成功",
//     "data": {
//         "id": 32,
//         "historyId": 233,
//         "code": "const graphTracer = new GraphTracer('BFS 图遍历');\nconst logger = new LogTracer('日志');\nLayout.setRoot(new VerticalLayout([graphTracer, logger]));\n// 示例数据：4个节点，无向图\nconst n = 4;\nconst start = 0;\nconst matrix = [\n    [0, 1, 1, 0],\n    [1, 0, 1, 1],\n    [1, 1, 0, 0],\n    [0, 1, 0, 0]\n];\ngraphTracer.set(matrix);\nlogger.println('图初始化完成');\nTracer.delay(); //src:20  (对应 scanf(\"%d\", &graph[i][j]) 的内层赋值)\n// 模拟队列与 visited 数组\nconst MAX_N = 10;\nconst visited = new Array(MAX_N).fill(false);\nconst queue = new Array(MAX_N);\nlet front = 0, rear = 0;\n// 起始节点入队并标记\nqueue[rear++] = start;\nvisited[start] = true;\ngraphTracer.select(start);\nlogger.println('起始节点 ' + start + ' 入队');\nTracer.delay(); //src:25\nTracer.delay(); //src:26\n// 模拟 first 变量（仅用于输出控制，可视化中直接用 logger）\nlet first = 1;\nwhile (front < rear) {\n    // 取出队首节点\n    let current = queue[front++];\n    graphTracer.select(current); // 确保当前节点高亮\n    if (first) {\n        logger.println('处理节点: ' + current);\n        first = 0;\n    } else {\n        logger.println('处理节点: ' + current);\n    }\n    Tracer.delay(); //src:34\n    // 遍历所有邻居\n    for (let i = 0; i < n; i++) {\n        if (matrix[current][i] === 1 && !visited[i]) {\n            // 高亮边\n            graphTracer.visit(current, i);\n            Tracer.delay(); //src:47\n            // 标记邻居已访问\n            visited[i] = true;\n            graphTracer.select(i);\n            logger.println('访问节点: ' + i);\n            Tracer.delay(); //src:48\n            // 邻居入队\n            queue[rear++] = i;\n            logger.println('节点 ' + i + ' 入队');\n            Tracer.delay(); //src:49\n            // 取消高亮边\n            graphTracer.leave(current, i);\n        }\n    }\n    // 当前节点处理完毕，取消高亮（可选，但为了清晰）\n    graphTracer.deselect(current);\n    // 此处不添加额外的 delay，因为循环结束前已有足够的 delay\n}\nlogger.println('BFS 遍历完成');\nTracer.delay(); //src:54",
//         "detectedType": "graph",
//         "originalCode": "#include <stdio.h>\n\n#define MAX_N 10\n\nint main() {\n    int n, start;\n    int graph[MAX_N][MAX_N];\n    int visited[MAX_N] = {0};\n    int queue[MAX_N];\n    int front = 0, rear = 0;\n    \n    // 读入节点数\n    scanf(\"%d\", &n);\n    // 读入起始节点\n    scanf(\"%d\", &start);\n    \n    // 读入邻接矩阵\n    for (int i = 0; i < n; i++) {\n        for (int j = 0; j < n; j++) {\n            scanf(\"%d\", &graph[i][j]);\n        }\n    }\n    \n    // 起始节点入队并标记为已访问\n    queue[rear++] = start;\n    visited[start] = 1;\n    \n    // 用于记录第一个输出，方便控制空格\n    int first = 1;\n    \n    // BFS遍历\n    while (front < rear) {\n        // 取出队首节点\n        int current = queue[front++];\n        \n        // 输出当前节点\n        if (first) {\n            printf(\"%d\", current);\n            first = 0;\n        } else {\n            printf(\" %d\", current);\n        }\n        \n        // 遍历所有邻居\n        for (int i = 0; i < n; i++) {\n            // 如果有边且未访问\n            if (graph[current][i] == 1 && !visited[i]) {\n                visited[i] = 1;\n                queue[rear++] = i;\n            }\n        }\n    }\n    \n    printf(\"\\n\");\n    return 0;\n}",
//         "language": "C"
//     }
// }

// ==============================数字孪生==============================
// 检查代码哪一行错了(代码语法检查)
// 参数:
//  data ：{"code": "...", "language": "python|javascript|java|c|cpp"}
export const checkCodeApi = (data) => requestPythonAll.post('/lint', data)
// 返回样例：{
//     "errors": [
//         {
//             "line": 50,//错误行号（只需关注这个）
//             "col": 16,//错误列号
//             "msg": "'[' was never closed",//错误信息
//             "end_col": 17//错误结束列号
//         }
//     ],
//     "language": "python"
// }

// 上报孪生提供提示
// 参数:
// - knowledgePoints: 知识点列表（逗号分隔）
// - codeSnippet: 当前已编写的代码（用于实时代码模式检测）
export const reportTwinApi = (userId, knowledgePoints, codeSnippet) => requestPythonAll.get(`/digital-twin/${userId}/hints?knowledge_points=${encodeURIComponent(knowledgePoints)}&code_snippet=${encodeURIComponent(codeSnippet)}`)
//返回样例：{
//     "hints": [
//         {
//             "type": "weakness",
//             "knowledge_point": "排序算法",
//             "mastery_pct": 0,
//             "severity": "high",
//             "tip": "你在「排序算法」掌握度仅0%，注意：①比较逻辑是否正确 ②稳定性考虑 ③时间复杂度",
//             "watch_keywords": [
//                 "sort",
//                 "sorted",
//                 "冒泡",
//                 "快速"
//             ]
//         },
//         {
//             "type": "weakness",
//             "knowledge_point": "循环结构",
//             "mastery_pct": 0,
//             "severity": "high",
//             "tip": "你在「循环结构」掌握度仅0%，注意：①循环边界条件 ②循环变量初始化与步进 ③避免死循环",
//             "watch_keywords": [
//                 "for",
//                 "while",
//                 "range"
//             ]
//         },
//         {
//             "type": "error_pattern",
//             "pattern": "concept_confusion",
//             "severity": "medium",
//             "tip": "你容易混淆相似概念，建议编码时多参考官方文档确认 API 用法"
//         },
//         {
//             "type": "code_pattern",//只注意code_pattern类型的信息
//             "severity": "warning",
//             "line": 45,
//             "tip": "列表定义不完整，缺少右括号 ']' 和后续元素，导致语法错误。请补全为 [9, 8, 7, 6, 5] 或完整数组。"
//         },
//         {
//             "type": "code_pattern",
//             "severity": "warning",
//             "line": 47,
//             "tip": "拼写错误：'pri' 应为 'print'，否则代码无法运行。"
//         },
//         {
//             "type": "code_pattern",
//             "severity": "warning",
//             "line": 56,
//             "tip": "拼写错误：'p' 应为 'print'，否则代码无法运行。"
//         }
//     ],
//     "user_id": "60",
//     "twin_enabled": true
// }

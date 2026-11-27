<script setup>
import { h, ref, onMounted, nextTick, computed, reactive, onUnmounted, watch } from 'vue' 
import { ElMessage,ElMessageBox,ElNotification, ElButton } from 'element-plus'
import * as echarts from 'echarts'
import { isSkip, removeSkip } from '@/utils/skip.js'//跳转
import { useRouter } from 'vue-router'
import { createCodeKeydownHandler } from './codeInput.js' //编码快捷键
import emitter from '@/utils/emitter'
import { getCodeListByUserId,submitCodeApi,getCodeProgressApi,
  getValueApi,deleteCodeByIdApi,submitExamineApi,getExamineProgressApi,
  getExamineListApi,deleteExamineByIdApi,
  getExamineValueApi,getCodeRankListApi,codeVisualApi,codeCompareApi,
  reportTwinApi, checkCodeApi } from '@/api/mainApi/resourceCode.js'
import { reviewCountAddOneApi } from '@/api/mainApi/layout.js'//复习次数加一
import { getUserInfoApi } from '@/api/mainApi/index.js'//根据用户id序列查询用户信息序列
import { conflictApi } from '@/api/mainApi/aiAnswer.js'//冲突提交
import { initVizModule } from './codeVisualization.js'//算法可视化模块


//全局弹窗
import { useActionPopStore } from '@/utils/actionPop.js'
const itemRef = ref([])// 循环ref 必须初始化为空数组
const popStore = useActionPopStore()
// 接收索引，获取当前 hover 的 DOM
const handleEnter = async (index, rsId, type='practice') => {
  await nextTick()
  const el = itemRef.value[index]
  if (!el) return

  const rect = el.getBoundingClientRect()
  let left = rect.left
  let top = rect.top - 60 // 元素上方60px

  // 顶部越界则改为下方展示
  if (top < 0) {
    top = rect.bottom + 10
  }

  // 每个item对应自身坐标弹出
  console.log('【hover】index：',index,'，rsId：',rsId)
  popStore.showPop(left, top, { id: index, title: `第${index+1}个条目`, rsId: rsId, rsType: type, userId: userId.value })
}


const router = useRouter()
let loginUser = null
const userId = ref(null)// 用户ID
const skipInfo = ref()//跳转信息
onMounted(async() => {
  // 获取用户名
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        userId.value = loginUser.id
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  // 获取题目列表信息
  await getList()

  // 检查 应用 中是否有要打开的编程题
  if(isSkip(4) === false){
    console.log('没有编程题需要提前打开')
  }else{
    skipInfo.value = isSkip(4)
    console.log('跳转信息:', skipInfo.value)
    try{
      await getValue(skipInfo.value.resourceId)
      await getCodeHistoryList()

    }catch(e){
      ElMessage.error('该编程题不存在，可能已经被删除了')
      console.log('打开失败')
    }
    
    removeSkip(4)//删除跳转信息
  }


  // 检查状态
  await checkList()

  
})

const codeData = ref({//外部提交数据
  userId: null,
  text: ''
})
const codeRef = ref(null)//表单验证
const btnDisvisible = ref(false)//按钮禁用是否开启
const Rules = {//表单验证规则
  text: [
    { required: true, message: '请输入主题/知识点', trigger: 'blur' },
    { min: 1, max: 30, message: '长度在 1 到 30 个字符', trigger: 'blur' }
  ]
}
const task = ref({})// 任务项
const taskProgress = ref({})// 任务项进度

const isShow = ref(false)//是否显示预览

const showCodeData = ref({//预览数据
  id: null,
  text: '',
  status: null,
  createTime: '',
  title: '',
  difficulty: '',
  description: '',
  inputFormat: '',
  outputFormat: '',
  examples: [],
  hints: [],
  knowledgePoints: [],
  sessionId: ''

  // "createTime": "2026-05-26 18:32",
  // "id": 6,
  // "text": "帮我生成一份关于循环的编程练习题",
  // "status": 2,
  // "title": "使用循环结构计算数字之和",
  // "difficulty": "简单",
  // "description": "编写一个Java程序，使用循环结构计算从1到n的所有整数的和。请确保你的程序能够处理任意正整数n。",
  // "inputFormat": "输入一个正整数n（1 ≤ n ≤ 1000）。",
  // "outputFormat": "输出从1到n的所有整数的和。",
  // "examples": [
  //     {
  //         "input": "5",
  //         "output": "15",
  //         "explanation": "1 + 2 + 3 + 4 + 5 = 15"
  //     },
  //     {
  //         "input": "10",
  //         "output": "55",
  //         "explanation": "1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10 = 55"
  //     }
  // ],
  // "hints": [
  //     "可以使用for循环来遍历从1到n的所有整数。",
  //     "在每次循环中，将当前整数加到一个累加器变量上。",
  //     "初始化累加器变量为0。",
  //     "循环结束后，输出累加器变量的值。"
  // ],
  // "knowledgePoints": [
  //     "循环结构",
  //     "数学计算"
  // ]
})
const allList = ref([// 外部所有列表
  
])// 所有列表
const showList = ref([])// 外部显示列表

const showConflictDialog = ref(false)//冲突弹窗是否开启
const conflictData = ref({
  taskId: null,
  rsType: 4,
  suggestionWarning: '',
  createTime: ''
})



// ===================题目内函数==================

const isShowLoading =  ref(false)//是否显示加载中

// ==========================左侧===========================
//收起/展开->示列/tips
const isEgShow = ref(false)//示例是否展示
const isTipsShow = ref(false)//tips是否展示

// 转换难度显示
const formatDifficulty = (difficulty) => {
  if (!difficulty) return ''
  const num = parseInt(difficulty)
  if (!isNaN(num)) {
    const map = {
      1: '简单',
      2: '中等',
      3: '困难'
    }
    return map[num] || difficulty
  }
  return difficulty
}

// markdown转html
// mode: 'format' - 处理转义字符，双换行分段（用于描述内容）
//       'simple' - 不处理转义字符，单换行分段（用于普通markdown）
const markdownToHtml = (content, mode = 'simple') => {
  if (!content) return ''
  let html = content
  
  // format模式：处理转义字符
  if (mode === 'format') {
    html = html.replace(/\\n/g, '\n')
    html = html.replace(/\\r/g, '\r')
  }
  
  // 转义HTML特殊字符
  html = html.replace(/&/g, '&amp;')
  html = html.replace(/</g, '&lt;')
  html = html.replace(/>/g, '&gt;')
  
  // markdown语法转换
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr>')
  html = html.replace(/^&gt;\s+(.*)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^######\s+(.*)$/gm, '<h6>$1</h6>')
  html = html.replace(/^#####\s+(.*)$/gm, '<h5>$1</h5>')
  html = html.replace(/^####\s+(.*)$/gm, '<h4>$1</h4>')
  html = html.replace(/^###\s+(.*)$/gm, '<h3>$1</h3>')
  html = html.replace(/^##\s+(.*)$/gm, '<h2>$1</h2>')
  html = html.replace(/^#\s+(.*)$/gm, '<h1>$1</h1>')
  html = html.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/^\d+\.\s+(.*)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul>$1</ul>')
  
  // 分段处理
  if (mode === 'format') {
    // format模式：双换行分段，段落内用<br>连接
    const paragraphs = html.split(/\n\n+/)
    const out = []
    for (const para of paragraphs) {
      const lines = para.split('\n')
      const paraLines = []
      for (const line of lines) {
        const t = line.trim()
        if (!t) continue
        paraLines.push(t)
      }
      const paraContent = paraLines.join('<br>')
      if (/^<(h[1-6]|ul|blockquote|hr)/.test(paraContent)) {
        out.push(paraContent)
      } else {
        out.push('<p>' + paraContent + '</p>')
      }
    }
    html = out.join('\n')
    html = html.replace(/<br><\/li>/g, '</li>')
    html = html.replace(/<li><br>/g, '<li>')
  } else {
    // simple模式：单换行分段，每行独立处理
    const lines = html.split('\n')
    const out = []
    for (const line of lines) {
      const t = line.trim()
      if (!t) continue
      if (/^<(h[1-6]|ul|\/ul|li|blockquote|\/blockquote|hr|img|p|code|a)/.test(t)) {
        out.push(t)
      } else {
        out.push('<p>' + t + '</p>')
      }
    }
    html = out.join('\n')
  }
  
  // 清理嵌套标签
  html = html.replace(/<p><ul>/g, '<ul>')
  html = html.replace(/<\/ul><\/p>/g, '</ul>')
  html = html.replace(/<p><li>/g, '<li>')
  html = html.replace(/<\/li><\/p>/g, '</li>')
  
  return html
}

// 处理描述内容（支持markdown、换行符、普通文本）- 兼容旧调用
const formatContent = (content) => {
  return markdownToHtml(content, 'format')
}
const btn = (option) => {
  if(option === 0){
    isEgShow.value = !isEgShow.value
  }else if(option === 1){
    isTipsShow.value = !isTipsShow.value
  }else if(option === 2){
    logStatus.value = !logStatus.value
  }
}
//提交代码分析
const submitContent = ref({//提交内容
  userId: null,
  practiceId: null,
  answer: '',
  language: 'C',
  recordId: null
})

// 生成具体的编码处理函数，传入 submitContent 引用和字段名 'answer'
const handleCodeKeydown = createCodeKeydownHandler(submitContent, 'answer')
const lineCount = ref(15) // 初始行数
const lineNumbersRef = ref(null) // 行号区域引用
// 根据内容换行符更新行数
const updateLineCount = () => {
  const lines = submitContent.value.answer.split('\n').length
  lineCount.value = Math.max(15, lines)// 至少保持 15 行高度，或者根据实际内容动态增加
}
// 同步行号区域的滚动
const syncLineNumbersScroll = (e) => {
  if (lineNumbersRef.value) {
    // 使用 transform 移动行号内容，与 textarea 滚动同步
    const scrollTop = e.target.scrollTop
    lineNumbersRef.value.style.transform = `translateY(${-scrollTop}px)`
  }
}

// ========================== 数字孪生代码检查 ==========================
const twinEnabled = ref(false)// 数字孪生是否开启
const twinWarnings = ref([])// code_pattern 类型的警告 [{line, tip}]
const twinErrors = ref([])// 语法检查错误 [{line, msg}]
let twinCheckTimer = null// 防抖定时器

// 监听孪生开关状态
emitter.on('digitalTwinToggle', (val) => {
  twinEnabled.value = val
  if (!val) {
    twinWarnings.value = []
    twinErrors.value = []
  }
})

// 代码变化时调用孪生检查（防抖 500ms）
const onTwinCodeChange = () => {
  if (!twinEnabled.value) return
  const code = submitContent.value.answer
  if (!code || !code.trim()) {
    twinWarnings.value = []
    twinErrors.value = []
    return
  }
  clearTimeout(twinCheckTimer)
  twinCheckTimer = setTimeout(() => {
    runTwinCheck(code)
  }, 500)
}

// 执行孪生检查
const runTwinCheck = async (code) => {
  // 获取当前题目的知识点（数组转逗号分隔字符串）
  const kp = showCodeData.value?.knowledgePoints || []
  const knowledgePoints = Array.isArray(kp) ? kp.join(',') : kp
  const uid = userId.value
  if (!uid) return

  // 并行调用两个接口
  try {
    const [twinRes, lintRes] = await Promise.allSettled([
      reportTwinApi(uid, knowledgePoints, code),
      checkCodeApi({ code, language: submitContent.value.language?.toLowerCase() || 'python' })
    ])

    // 处理孪生提示
    if (twinRes.status === 'fulfilled' && twinRes.value?.hints) {
      twinWarnings.value = twinRes.value.hints
        .filter(h => h.type === 'code_pattern' && h.severity === 'warning')
        .map(h => ({ line: h.line, tip: h.tip }))
    }

    // 处理语法检查
    if (lintRes.status === 'fulfilled' && lintRes.value?.errors) {
      twinErrors.value = lintRes.value.errors.map(e => ({ line: e.line, msg: e.msg }))
    }
  } catch (e) {
    console.error('孪生检查失败', e)
  }
}

// 监听代码输入
watch(() => submitContent.value.answer, () => {
  onTwinCodeChange()
})

// 获取某行的生警告
const getTwinWarning = (line) => twinWarnings.value.find(w => w.line === line) || null
// 获取某行的语法错误
const getTwinError = (line) => twinErrors.value.find(e => e.line === line) || null

onUnmounted(() => {
  emitter.off('digitalTwinToggle')
  clearTimeout(twinCheckTimer)
})
// ==========================右侧===========================
// 退出代码评估栏
const isResultShow = ref(false)//是否显示结果页
const quitResult = () => {
  isResultShow.value = false
  
  // 某个历史记录页信息
  beforeContent.value = {
    id: null,
    answer: '',
    language: '',
    score: null,
    createTime: '',
    status: null,
    verdict: '',
    passedTests: null,
    totalTests: null,
    suggestion: [],
    encouragement: '',
  }
  //排行榜信息
  rankList.value = []


  closeViz()


  // loading.value = false
  // resultCode.value = ''
  // detectedType.value = ''
  // vizVisible.value =  false
  // vizStatus.value = '等待转换...'
  // vizWorker.value = null
  // vizCanvas.value = null
  // vizLog.value =  null
  // logStatus.value = true
  

  closeLookCode()
}
//源代码展示+评估内容
const beforeContent = ref({//源代码内容+评估内容
  id: null,
  answer: '',
  language: '',
  score: null,
  createTime: '',
  status: null,
  verdict: '',
  passedTests: null,
  totalTests: null,
  suggestion: [],
  encouragement: '',
  submissionId: null

    // "id": 1,
    // "practiceId": 1,
    // "status": 2,
    // "answer": "pwd = input().strip()\nhas_letter = False\nhas_digit = False\nhas_special = False\nspecial_chars = {'@', '#', '$', '%', '^', '&', '*'}\n\nfor char in pwd:\n    if char.isalpha():\n        has_letter = True\n    elif char.isdigit():\n        has_digit = True\n    elif char in special_chars:\n        has_special = True\n\nlength = len(pwd)\nif length < 8:\n    print(\"弱\")\nelif has_letter and has_digit and has_special:\n    print(\"强\")\nelif has_letter and has_digit:\n    print(\"中\")\nelse:\n    print(\"弱\")",
    // "score": 90,
    // "suggestion": [
    //     "考虑添加一个主函数来封装整个程序流程，提高代码可读性和结构化程度。",
    //     "可以增加一些异常处理机制，比如当输入为空时给予提示。"
    // ],
    // "verdict": "Accepted",
    // "passedTests": 4,
    // "totalTests": 4,
    // "encouragement": "你的解决方案很接近完美了！继续保持这种良好的编程习惯，未来一定能在编程道路上走得更远。",
    // "createTime": "2026-05-29 19:55"
  
})

const compareVisible = ref(false)
const compareLoading = ref(false)
const compareData = ref(null)
const compareUserInfo = ref({})
const radarChartRef = ref(null)
const barChartRef = ref(null)




const resultCount = ref(15) // 初始行数
// 根据内容换行符更新行数
const updateResultCount = () => {
  const lines = beforeContent.value.answer.split('\n').length
  resultCount.value = Math.max(15, lines)// 至少保持 15 行高度，或者根据实际内容动态增加
}
// 代码分析按钮的img
const imgShow = () => { 
  const imgUrl = ref(`../../../assets/icon/${submitContent.value.language}.png`)
  try {
    return new URL(imgUrl.value, import.meta.url).href
  } catch (e) {
    console.error('图片加载失败', e)
    return '' // 或者返回一个默认图片
  }
}

// 本题历史提交记录
const showCHList = ref([
  // {//未通过
  //     "id": 7,
  //     "practiceId": 3,
  //     "createTime": "2026-05-26 18:32",
  //     "status": 2,
  //     "verdict": "Compilation Error",
  //     "score": 0
  // },
  // {//通过
  //     "id": 6,
  //     "practiceId": 3,
  //     "createTime": "2026-05-26 18:32",
  //     "status": 2,
  //     "verdict": "Accepted",
  //     "score": 96
  // },
  // //生成失败的案例
  // {
  //     "id": 3,
  //     "practiceId": 3,
  //     "createTime": "2026-05-26 18:32",
  //     "status": 3,
  //     "verdict": "",
  //     "score": null
  // },
  // //生成中的案例
  // {
  //     "id": 4,
  //     "practiceId": 3,
  //     "createTime": "2026-05-26 18:32",
  //     "status": 1,
  //     "verdict": "",
  //     "score": null
  // },

])// 显示的所有提交测评提交记录


const rankList = ref([//排行榜
  // { userId: 11, username: '张三', score: 98, avatar: 'https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png',createTime: '2026-05-26 18:32',codePreview: "pwd = input().strip()\nhas_letter = False\nhas_digit = False\nhas_special = False\nspecial_chars = {'@', '#', '$', '%', '^', '&', '*'}\n\nfor char in pwd:\n    if char.isalpha():\n        has_letter = True\n    elif char.isdigit():\n... (13 more lines)" },
]);

const isLookCode = ref(false)//查看代码对话框是否打开
const lookUserMsg = ref({//展示的信息
  userId: null,
  username: '',
  createTime: '',
  score: null,
  avatar: '',
  codePreview: ''

  // userId: 2,
  // username: "小华",
  // createTime: "2026-05-26 18:32",
  // score: 95,
  // avatar: "https://wha-whaghw.oss-cn-beijing.aliyuncs.com/e654d99a-e138-4aa6-a0b1-71f80cd39146.png",
  // codePreview: "pwd = input().strip()\nhas_letter = False\nhas_digit = False\nhas_special = False\nspecial_chars = {'@', '#', '$', '%', '^', '&', '*'}\n\nfor char in pwd:\n    if char.isalpha():\n        has_letter = True\n    elif char.isdigit():\n... (13 more lines)"
})

// 获取查看用户信息
const getLookUserMsg = (userId,index) => {
  // 对rankList遍历查找
  for (let i = 0; i < rankList.value.length; i++) {
    const item = rankList.value[i];
    if(item.userId == userId && i == index){
      lookUserMsg.value = item
      updatelookCount()//代码块行数
      isLookCode.value = true//显示查看代码对话框
      return
    }
  }
}

//关闭查看代码对话框
const closeLookCode = () => {
  isLookCode.value = false
  lookUserMsg.value = {
    userId: null,
    username: '',
    createTime: '',
    score: null,
    avatar: '',
    codePreview: ''
  }
  

}

const lookCount = ref(20) // 初始行数
// 根据内容换行符更新行数
const updatelookCount = () => {
  const lines = lookUserMsg.value.codePreview.split('\n').length
  lookCount.value = Math.max(20, lines)// 至少保持 20 行高度，或者根据实际内容动态增加
}


// ====================================外部函数===========================================
// 查看更多收起
const isOpenList = (operation) => {
  if(operation == 0){//查看更多
    showList.value = [...allList.value]
  }else if(operation == 1){ //收起
    showList.value = allList.value.slice(0,20)
  }else{
    ElMessage.error('失败')
  }
}

//退出预览
const quitShowCode = async () => {
  await getList()//获取列表
  isShow.value = false
  isEgShow.value = false//运行示例收起
  isTipsShow.value = false//提示收起
  // 编写代码区域（提交评估表单）
  submitContent.value = {
    userId: null,
    practiceId: null,
    answer: '',
    language: 'C',
  }
  // 题目内容清空
  showCodeData.value = {
    id: null,
    text: '',
    status: null,
    createTime: '',
    title: '',
    difficulty: '',
    description: '',
    inputFormat: '',
    outputFormat: '',
    examples: [],
    hints: [],
    knowledgePoints: [],
    sessionId: ''
  }

  showCHList.value = []

  //应用打开的错题重练编程题信息
  skipInfo.value = null


  quitResult()
}

//检查列表
const checkList = async() => { 
  btnDisvisible.value = true
  console.log('开始检查列表')
  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i];
    if(item.status == 1 || item.status == null){
      //轮询获取进度
      let nowNum = 0
      let maxNum = 40

      try {
        await getProgress(item.id)// 尝试查一次

        // 判断是否冲突弹窗
        if(taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null){
          console.log('有冲突弹窗')
          if (showConflictDialog.value) {
            console.log('冲突弹窗已打开，跳过')
          } else {
            conflictData.value = {
              createTime: taskProgress.value.createTime,
              suggestionWarning: taskProgress.value.suggestionWarning,
              rsType: 4,
              taskId: taskProgress.value?.id
            }
            showConflictDialog.value = true
            console.log('打开冲突弹窗')
          }
        }
        
        if(taskProgress.value == {}){//查不到返回结果
          ElMessage.error('获取生成进度失败')
        }else if(taskProgress.value.status == null){
          await deleteItem(item.id,false)
          ElMessage.error('有生成项请求生成失败，直接删除')
          await getList()
          taskProgress.value = {}
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue 
      }

      
      // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
      while (taskProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        console.log(`任务 ${item.id} 生成中... 第 ${nowNum} 次轮询`)
        
        // 异步等待 10 秒
        await new Promise(resolve => setTimeout(resolve, 10000))
        
        try {
          console.log('获取进度次数：',nowNum)
          await getProgress(item.id)
          // 判断是否冲突弹窗
          if(taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null){
            console.log('有冲突弹窗')
            if (showConflictDialog.value) {
              console.log('冲突弹窗已打开，跳过')
            } else {
              conflictData.value = {
                createTime: taskProgress.value.createTime,
                suggestionWarning: taskProgress.value.suggestionWarning,
                rsType: 4,
                taskId: taskProgress.value?.id
              }
              showConflictDialog.value = true
              console.log('打开冲突弹窗')
            }
          }
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      // 轮询结束，判断最终结果
      if (taskProgress.value.status == 2) {
        console.log(` ${item.id} 任务完成`)
        await getList()
        taskProgress.value = {}
      } else {
        console.log(` ${item.id} 未完成`)
        await getList()
        taskProgress.value = {}
      } 
    }
  }
  btnDisvisible.value = false
}

// 处理冲突弹窗选择
const handleConflictOption = async (option) => {
  try {
    const response = await conflictApi(userId.value, {
      id: conflictData.value.taskId,
      rsType: conflictData.value.rsType,
      option: option
    })
    ElMessage.success(option ? '已接受，处理中...' : '已拒绝，处理中...')
    if (response.code === 1) {
      ElMessage.success('操作完成')
    } else {
      ElMessage.error(response.msg || '操作失败')
    }
  } catch (error) {
    console.error('冲突弹窗操作失败:', error)
    ElMessage.error('网络异常，操作失败')
  } finally {
    showConflictDialog.value = false
    conflictData.value = {
      createTime: '',
      suggestionWarning: '',
      rsType: 4,
      taskId: null
    }
  }
}
// 格式化冲突消息
const formatConflictMessage = (message) => {
  if (!message) return ''
  return message.replace(/\n/g, '<br/>')
}

// 提交表单
const submit = async () => { 
  codeRef.value.validate(async(valid) => {
    if (valid) {
      codeData.value.userId = userId.value
      console.log('表单校验通过，提交中')
      btnDisvisible.value = true

      let gameInvitationSent = false
      const gameInvitationTimer = setTimeout(() => {
        if (!gameInvitationSent) {
          gameInvitationSent = true
          emitter.emit('gameInvitation')
        }
      }, 20000)

      try {
        await createTask()//创建任务获取任务项task
        if(task.value.status == 1 || task.value.status == null){
          //轮询获取进度
          let nowNum = 0
          let maxNum = 40

          try {
            await getProgress(task.value.id)// 尝试查一次
            // 判断是否冲突弹窗
            if(taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null){
              console.log('有冲突弹窗')
              if (showConflictDialog.value) {
                console.log('冲突弹窗已打开，跳过')
              } else {
                conflictData.value = {
                  createTime: taskProgress.value.createTime,
                  suggestionWarning: taskProgress.value.suggestionWarning,
                  rsType: 4,
                  taskId: taskProgress.value?.id
                }
                showConflictDialog.value = true
                console.log('打开冲突弹窗')
              }
            }
            if(taskProgress.value == {}){//查不到返回结果
              ElMessage.error('获取生成进度失败')
            }else if(taskProgress.value.status == null){
              await deleteItem(task.value.id,false)
              ElMessage.error('有生成项请求生成失败，直接删除')
              await getList()
              task.value = {}
              taskProgress.value = {}
            }
          } catch (e) {
            console.error('首次查询进度失败', e)
          }

          await getList()
          await getValue(task.value.id)

          // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
          while (taskProgress.value.status == 1 && nowNum < maxNum) {
            nowNum++
            console.log(`任务 ${task.value.id} 生成中... 第 ${nowNum} 次轮询`)

            // 异步等待 10 秒
            await new Promise(resolve => setTimeout(resolve, 10000))

            try {
              console.log('获取进度次数：',nowNum)
              await getProgress(task.value.id)
              // 判断是否冲突弹窗
              if(taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null){
                console.log('有冲突弹窗')
                if (showConflictDialog.value) {
                  console.log('冲突弹窗已打开，跳过')
                } else {
                  conflictData.value = {
                    createTime: taskProgress.value.createTime,
                    suggestionWarning: taskProgress.value.suggestionWarning,
                    rsType: 4,
                    taskId: taskProgress.value?.id
                  }
                  showConflictDialog.value = true
                  console.log('打开冲突弹窗')
                }
              }
            } catch (e) {
              console.error('轮询进度失败', e)
            }
          }

          // 轮询结束，判断最终结果
          if (taskProgress.value.status == 2) {
            console.log(` ${task.value.id} 任务完成`)
            await getList()
            await getValue(task.value.id)
            // await getCodeHistoryList(task.value.id)
            task.value = {}
            taskProgress.value = {}
          } else {
            console.log(` ${task.value.id} 未完成`)
            await getList()
            await getValue(task.value.id)
            // await getCodeHistoryList(task.value.id)
            task.value = {}
            taskProgress.value = {}
          } 
        }else if(task.value.status == 2 || task.value.status == 3){//一提交就好了
          await getList()
          await getValue(task.value.id)
          task.value = {}
          taskProgress.value = {}
        }
        btnDisvisible.value = false
        codeData.value = {userId: null,text: ''}
      } finally {
        clearTimeout(gameInvitationTimer)
      }
    }else {
      console.log('校验失败')
      return false
    }
  })
}

// ===========================外部接口=========================
// 获取列表
const getList = async () => {
  try {
    itemRef.value = []
    const result = await getCodeListByUserId(userId.value)
    if(result.code){
      allList.value = result.data
      showList.value = allList.value.slice(0,20)
    }else{
      ElMessage.error('获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
  }
}
//根据id查询题目
const getValue = async (id) => {
  try {
    isShowLoading.value = true
    const result = await getValueApi(id)
    if(result.code){
      if(result.code.data === null){
        ElMessage.error('该题不存在')
      }

      showCodeData.value = result.data
      isShow.value = true
      isShowLoading.value = false

      // 上报题目上下文给智能球
      const questionData = result.data
      if (questionData) {
        emitter.emit('contextDetail', {
          page: 'code',
          title: questionData.title || '代码练习',
          action: 'practicing',
          detail: `题目ID: ${id}, 题目: ${questionData.title || ''}, 难度: ${questionData.difficulty || ''}, 知识点: ${questionData.knowledgePoints ? questionData.knowledgePoints.join(', ') : ''}`
        })
      }


      if(isShow.value == true && showCHList.value !== []){
        await checkCodeExamine()
      }else{
        // 异步等待 10 秒
        await new Promise(resolve => setTimeout(resolve, 10000))
      }

      while(isShow.value == true){
        console.log("开始检查是否未评估完成的历史记录项")
        if(showCHList.value !== []){
          console.log("进入检查函数")
          await checkCodeExamine()
          console.log("检查完毕")
          break
        }else{
          console.log("历史记录表还未传回，等待5秒")
          // 异步等待 5 秒
          await new Promise(resolve => setTimeout(resolve, 5000))
          console.log("等待完毕")
        }
      }


    }else if(result.code === 2){
      ElMessage.error('未找到对应资源，可能已被删除')
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
}
// 根据id删除信息
const deleteItem = async (id,isTip = true) => {
  if(isTip == true){//询问是否删除
    //询问是否删除
    const confirmResult = await ElMessageBox.confirm('是否删除该题目？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }
  try {
    const result = await deleteCodeByIdApi(id)
    if(result.code){
      ElMessage.success('删除成功')
      await getList()
    }else{
      ElMessage.error('删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
  }
}

// 创建生成任务
const createTask = async () => {
  try {
    const result = await submitCodeApi(codeData.value)
    if(result.code){
      task.value = result.data
    }else{
      ElMessage.error('提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
  }
}

//查询任务状态
const getProgress = async (id) => {
  try {
    const result = await getCodeProgressApi(id)
    if(result.code){
      taskProgress.value = result.data
    }else{
      ElMessage.error('查询进度失败')
    }
  } catch (e) {
    console.error('查询进度失败', e)
  }
}



// ======================内部接口========================

// 查询该题历史记录
const getCodeHistoryList = async (id = showCodeData.value.id) => {
  try {
    const result = await getExamineListApi(id,userId.value)
    if(result.code){
      showCHList.value = result.data
      console.log(`获取 题目id：${id} 的历史记录列表成功`)
    }else{
      ElMessage.error('获取信息失败')
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
}

//根据题目id查询排行榜信息
const getCodeRankList = async (id) => { 
  try {
    const result = await getCodeRankListApi(id)
    if(result.code){
      rankList.value = result.data
    }else{
      ElMessage.error('获取信息失败')
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
}

// AI代码分析比较
const compareCode = async (item) => {
  if (!beforeContent.value.submissionId) {
    ElMessage.warning('错题重练分析')
    return
  }
  
  compareLoading.value = true
  compareData.value = null
  compareVisible.value = true
  document.body.style.overflow = 'hidden'
  
  try {
    const practiceId = beforeContent.value.practiceId
    const submissionAId = beforeContent.value.submissionId
    const submissionBId = item.submissionId
    
    const response = await codeCompareApi({
      practiceId,
      submissionAId,
      submissionBId
    })
    
    if (response.code === 1 && response.data) {
      compareData.value = response.data
      
      const userIds = []
      if (response.data[0]) userIds.push(response.data[0].user_id)
      if (response.data[1]) userIds.push(response.data[1].user_id)
      
      if (userIds.length > 0) {
        const userInfoResponse = await getUserInfoApi({ userIdList: userIds })
        if (userInfoResponse.code === 1 && userInfoResponse.data) {
          userInfoResponse.data.forEach(u => {
            compareUserInfo.value[u.userId] = u
          })
        }
      }
      
      await nextTick()
      setTimeout(() => {
        initCharts()
      }, 100)
    } else {
      ElMessage.error(response.msg || '分析失败')
      compareVisible.value = false
      document.body.style.overflow = ''
    }
  } catch (e) {
    ElMessage.error('分析失败：' + e.message)
    compareVisible.value = false
    document.body.style.overflow = ''
  } finally {
    compareLoading.value = false
  }
}

// 关闭比较弹窗
const closeCompare = () => {
  compareVisible.value = false
  document.body.style.overflow = ''
  compareData.value = null
}

// 初始化图表
const initCharts = () => {
  if (!compareData.value || compareData.value.length < 3) {
    console.warn('compareData is not ready')
    return
  }
  
  const comparison = compareData.value[2]?.data?.comparison
  if (!comparison?.chart_data) {
    console.warn('chart_data is not available')
    return
  }
  
  const chartData = comparison.chart_data
  
  const userNameA = compareUserInfo.value[compareData.value[0]?.user_id]?.username || chartData.solution_a?.name || '我'
  const userNameB = compareUserInfo.value[compareData.value[1]?.user_id]?.username || chartData.solution_b?.name || '用户'
  
  // 雷达图
  if (radarChartRef.value) {
    try {
      const radarChart = echarts.init(radarChartRef.value)
      const option = {
        tooltip: {
          trigger: 'item'
        },
        legend: {
          data: [userNameA, userNameB],
          bottom: 0
        },
        radar: {
          indicator: chartData.dimensions?.map(dim => ({ name: dim, max: 100 })) || [],
          center: ['50%', '45%'],
          radius: '55%'
        },
        series: [{
            type: 'radar',
            data: [
              {
                value: chartData.solution_a?.values || [],
                name: userNameA,
                areaStyle: { color: 'rgba(45, 125, 219, 0.3)' },
                lineStyle: { color: '#2D7DDB' },
                itemStyle: { color: '#2D7DDB' }
              },
              {
                value: chartData.solution_b?.values || [],
                name: userNameB,
                areaStyle: { color: 'rgba(78, 191, 109, 0.3)' },
                lineStyle: { color: '#4EBF6D' },
                itemStyle: { color: '#4EBF6D' }
              }
            ]
          }]
      }
      radarChart.setOption(option, true)
      window.addEventListener('resize', () => radarChart.resize())
    } catch (e) {
      console.error('Failed to init radar chart:', e)
    }
  }
  
  // 折线图
  if (barChartRef.value) {
    try {
      const lineChart = echarts.init(barChartRef.value)
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' }
        },
        legend: {
          data: [userNameA, userNameB],
          bottom: 0
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '15%',
          top: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: chartData.dimensions || []
        },
        yAxis: {
          type: 'value',
          max: 100
        },
        series: [
          {
            name: userNameA,
            type: 'line',
            data: chartData.solution_a?.values || [],
            smooth: true,
            symbol: 'circle',
            symbolSize: 8,
            lineStyle: { color: '#2D7DDB', width: 3 },
            itemStyle: { color: '#2D7DDB' },
            areaStyle: { color: 'rgba(45, 125, 219, 0.1)' }
          },
          {
            name: userNameB,
            type: 'line',
            data: chartData.solution_b?.values || [],
            smooth: true,
            symbol: 'circle',
            symbolSize: 8,
            lineStyle: { color: '#4EBF6D', width: 3 },
            itemStyle: { color: '#4EBF6D' },
            areaStyle: { color: 'rgba(78, 191, 109, 0.1)' }
          }
        ]
      }
      lineChart.setOption(option, true)
      window.addEventListener('resize', () => lineChart.resize())
    } catch (e) {
      console.error('Failed to init line chart:', e)
    }
  }
}

//根据id查询某个历史记录页信息
const getExamineMsg = async (id) => {
  try {
    const result = await getExamineValueApi(id)
    if(result.code){
      ElMessage.success('获取成功')
      beforeContent.value = result.data
      isResultShow.value = true
      await getCodeRankList(showCodeData.value.id)//获取排行榜信息
      updateResultCount()//提交评估后展示的代码块左侧数随代码行数更新
    }else{
      ElMessage.error('获取失败')
    }
  } catch (e) {
    console.error('获取失败', e)
  }
}

// 删除某个历史记录项
const delCHItem = async (id,isTip = true) => {
  if(isTip == true){
    const confirmResult = await ElMessageBox.confirm('是否删除该历史记录？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }
  try {
    const result = await deleteExamineByIdApi(id)
    if(result.code){
      ElMessage.success('删除成功')
      await getCodeHistoryList();
    }else{
      ElMessage.error('删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
  }
}

const codeTask = ref({})//提交任务状态
const cTProgress = ref({})//提交任务进度

//创建代码评估任务
const createCodeExamine = async () => {
  try {
    if (skipInfo.value?.recordId) {
      // 在submitContent.value里面追加skipInfo.recordId
      submitContent.value.recordId = skipInfo.value.recordId
    }
    const result = await submitExamineApi(submitContent.value)
    if(result.code){
      codeTask.value = result.data
    }else{
      ElMessage.error('提交分析失败')
    }
  } catch (e) {
    console.error('提交失败', e)
  }
}
// 获取代码评估进度
const getCEProgress = async (id) => {
  try {
    const result = await getExamineProgressApi(id)
    if(result.code){
      cTProgress.value = result.data

      console.log(skipInfo.value)
      // 判断是否有 question
      if (skipInfo.value.recordId && cTProgress.value?.question && cTProgress.value.score < 60 && cTProgress.value?.question.count !== 0) {
        console.log('存在 question 数据', cTProgress.value.question)
        showNotification(cTProgress.value.question)//显示通知
      } else {
        console.log('无 question 数据')
      }
      
      // 错题重练后，通过
      if(skipInfo.value.recordId && cTProgress.value.score > 60 ){
        showOkNtf()
      }
    }else{
      ElMessage.error('查询进度失败')
    }
  } catch (e) {
    console.error('查询进度失败', e)
  }
}


// ==============================内部函数=============================
// 左下角通知（错题重练）
const ok = ref({"name": {"newName": "【错题重练】帮我生成一个循环的编程题", "oldName": ["11111","2222"]}, "count": 3, "newItem": 1, "oldItem": 2})
const showNotification = (question) => {
  const { newItem = 0, name = {} } = question || {}
  const { newName = '', oldName = [] } = name

  const nameNodes = []
  for (let i = 0; i < newItem; i++) {
    nameNodes.push(
      h('div', { style: 'margin: 4px 0; color: #333; font-size: 14px;' }, newName)
    )
  }
  // 使用 Set 去重，然后遍历
  [...new Set(oldName)].forEach(item => {
    nameNodes.push(
      h('div', { style: 'margin: 4px 0; color: #666; font-size: 14px;' }, item)
    )
  })

  // 保存通知实例
  const notification1 = ElNotification({
    title: '提示',
    duration: 0,
    showClose: false,  // 👈 隐藏默认关闭按钮
    position: 'bottom-left',
    customClass: 'notify-custom',
    message: h('div', { 
      style: 'line-height: 1.7; font-size: 14px; padding: 4px 0; position: relative;' 
    }, [
      // 👇 自定义关闭按钮
      h('span', {
        style: `
          position: absolute;
          top: -30px;
          right: -8px;
          cursor: pointer;
          font-size: 18px;
          color: #909399;
          z-index: 1;
          font-family: monospace;
        `,
        onClick: () => notification1.close(),
        onMouseenter: (e) => e.target.style.color = '#409EFF',
        onMouseleave: (e) => e.target.style.color = '#909399'
      }, '✕'),
      h('p', { 
        style: 'margin: 0 0 8px 0; color: #303133; padding-right: 20px;' 
      }, '你已经提交代码评估，好几次没过咯~\n我们为你推荐几道旧题和新题，再试着练一练吧！'),
      ...nameNodes,
      h('div', { 
        style: 'margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap;' 
      }, [
        h(ElButton, {
          type: 'primary',
          size: 'small',
          onClick: async() => {
            console.log('查看编程资源列表')
            
            if(isShow.value == true){
              await getList()
              quitShowCode()
            }else{
              ElMessage.success('已在查看编程资源列表')
            }
          }
        }, '查看编程资源列表'),
        h(ElButton, {
          size: 'small',
          onClick: () => {
            console.log('返回错题本')
            notification1.close()
            router.push('/wrongQuestions')
          }
        }, '返回错题本')
      ])
    ])
  })
}
const showOkNtf = () => {
  const notification2 = ElNotification({
    title: '提示',
    duration: 0,
    showClose: false,  // 👈 隐藏默认关闭按钮
    position: 'bottom-left',
    customClass: 'notify-custom',
    message: h('div', { 
      style: 'line-height: 1.7; font-size: 14px; padding: 4px 0; position: relative;' 
    }, [
      // 👇 自定义关闭按钮
      h('span', {
        style: `
          position: absolute;
          top: -30px;
          right: -8px;
          cursor: pointer;
          font-size: 18px;
          color: #909399;
          z-index: 1;
          font-family: monospace;
        `,
        onClick: () => notification2.close(),
        onMouseenter: (e) => e.target.style.color = '#409EFF',
        onMouseleave: (e) => e.target.style.color = '#909399'
      }, '✕'),
      h('p', { 
        style: 'margin: 0 0 8px 0; color: #303133; padding-right: 20px;' 
      }, '你的重练已经通过了，返回错题本 已掌握 看看重练趋势吧！'),
      h('div', { 
        style: 'margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap;' 
      }, [
        h(ElButton, {
          size: 'small',
          onClick: () => {
            console.log('返回错题本')
            notification2.close()
            router.push('/wrongQuestions')
          }
        }, '返回错题本')
      ])
    ])
  })
}

//打开评估页
const openCodeExamine = async (id) => {
  try {
    await getExamineMsg(id)
  } catch (e) {
    console.error('打开失败', e)
  }
}

const resultScrollbarRef = ref(null)// 评价结果区滚动条引用
const rankScrollbarRef = ref(null)// 排行榜滚动条引用

// 锁定结果区滚动（可视化播放期间禁止滚动）
const _scrollBlocker = (e) => {
  const el = resultScrollbarRef.value
  if (el && el.$el?.contains(e.target)) {
    e.preventDefault()
    e.stopPropagation()
  }
}
let _lockedScrollTop = 0
const _scrollReset = () => {
  const el = resultScrollbarRef.value
  if (el && el.wrapRef && el.wrapRef.scrollTop !== _lockedScrollTop) {
    el.wrapRef.scrollTop = _lockedScrollTop
  }
}
const lockResultScroll = () => {
  const el = resultScrollbarRef.value
  if (!el) return
  // 设置 overflow 双保险
  const rootEl = el.$el
  const wrap = el.wrapRef
  if (rootEl) rootEl.style.overflow = 'hidden'
  if (wrap) {
    wrap.style.overflow = 'hidden'
    _lockedScrollTop = wrap.scrollTop
  }
  // 在 document 捕获阶段拦截所有 wheel/touchmove（仅针对 el-scrollbar 内部）
  document.addEventListener('wheel', _scrollBlocker, { passive: false, capture: true })
  document.addEventListener('touchmove', _scrollBlocker, { passive: false, capture: true })
  // 监听 scroll 事件强制回到锁定位置（防止任何绕过方式）
  if (wrap) {
    wrap.addEventListener('scroll', _scrollReset, { passive: true })
  }
}
// 解锁结果区滚动
const unlockResultScroll = () => {
  const el = resultScrollbarRef.value
  if (el) {
    const rootEl = el.$el
    const wrap = el.wrapRef
    if (rootEl) rootEl.style.overflow = ''
    if (wrap) {
      wrap.style.overflow = ''
      wrap.removeEventListener('scroll', _scrollReset)
    }
  }
  document.removeEventListener('wheel', _scrollBlocker, true)
  document.removeEventListener('touchmove', _scrollBlocker, true)
}
// 返回顶部函数
const scrollToTop = (element) => {
  if (element) {
    // 获取 el-scrollbar 内部的滚动容器 DOM 元素
    // 在 Element Plus 中，通常可以通过 wrapRef 访问
    const wrap = element.wrapRef
    
    if (wrap) {
      // 使用原生 scrollTo API 实现平滑滚动
      wrap.scrollTo({
        top: 0,
        behavior: 'smooth'
      })
    } else {
      // 兼容旧版本或 fallback：直接设置 scrollTop (瞬间跳转)
      element.setScrollTop(0)
    }
  }
}

//检查待生成项
const checkCodeExamine = async () => {
  for (let i = 0; i < showCHList.value.length; i++) {
    const item = showCHList.value[i];
    if(item.status == 1 || item.status == null){
      //轮询获取进度
      let nowNum = 0
      let maxNum = 40

      if(isShow.value == false){
        console.log("本题评估截断")
        // 清空所有内部数据
        quitShowCode()
        //退出函数
        return
      }

      try {
        await getCEProgress(item.id)// 尝试查一次
        if(cTProgress.value == {}){//查不到返回结果
          ElMessage.error('获取生成进度失败')
        }else if(cTProgress.value.status == null){
          await delCHItem(item.id,false)
          ElMessage.error('有生成项请求生成失败，直接删除')
          await getCodeHistoryList()
          cTProgress.value = {}
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue 
      }

      
      // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
      while (isShow.value == true && cTProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        console.log(`任务 ${item.id} 生成中... 第 ${nowNum} 次轮询`)
        
        // 异步等待 10 秒
        await new Promise(resolve => setTimeout(resolve, 10000))
        
        try {
          console.log('获取进度次数：',nowNum)
          await getCEProgress(item.id)
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      if(isShow.value == false){
        console.log("本题评估截断")
        // 清空所有内部数据
        quitShowCode()
        //退出函数
        return
      }


      // 轮询结束，判断最终结果
      if (cTProgress.value.status == 2) {
        console.log(` ${item.id} 任务完成`)
        await getCodeHistoryList()
        cTProgress.value = {}
      } else {
        console.log(` ${item.id} 未完成`)
        await getCodeHistoryList()
        cTProgress.value = {}
      } 
    }
  }
}

// 提交代码评估
const submitCode = async () => {
  submitContent.value.userId = userId.value
  submitContent.value.practiceId = showCodeData.value.id
  ElMessage.success("提交分析中...")
  console.log('提交中')
  // 如果该题有sessionId，说明是复习任务，提交了代码复习次数加一
  if(
    showCodeData.value?.sessionId &&
    showCodeData.value.sessionId !== '' &&
    showCodeData.value.sessionId !== 'none' &&
    showCodeData.value.sessionId !== null
  ){
    const res = await reviewCountAddOneApi(userId.value)
    if(res.code){
      console.log('今日复习次数已增加')
      ElMessage.success('今日复习次数已增加')
    }else{
      console.log('后端错误，今日复习次数增加失败')
    }
  }
  await createCodeExamine()//创建任务获取任务项
  await getExamineMsg(codeTask.value.id)
  submitContent.value = {userId: null,practiceId: null,answer: '',language: 'C',recordId: null}
  lineCount.value = 15
  if(taskProgress.value.status == 1 || taskProgress.value.status == null){
    //轮询获取进度
    let nowNum = 0
    let maxNum = 40

    if(isShow.value == false){
      console.log("本题评估截断")
      // 清空所有内部数据
      quitShowCode()
      //退出函数
      return
    }

    try {
      await getCEProgress(codeTask.value.id)// 尝试查一次
      if(cTProgress.value == {}){//查不到返回结果
        ElMessage.error('获取生成进度失败')
      }else if(cTProgress.value.status == null){
        await delCHItem(codeTask.value.id,false)
        ElMessage.error('有生成项请求生成失败，直接删除')
        await getCodeHistoryList()
        codeTask.value = {}
        cTProgress.value = {}
      }
    } catch (e) {
      console.error('首次查询进度失败', e)
    }

    if(isShow.value == false){
      console.log("本题评估截断")
      // 清空所有内部数据
      quitShowCode()
      //退出函数
      return
    }

    await getCodeHistoryList()
    await getCEProgress(codeTask.value.id)
    

    // 当状态为 1 (生成中) 且未达到最大重试次数时，持续轮询
    while (isShow.value == true && cTProgress.value.status == 1 && nowNum < maxNum) {
      nowNum++
      console.log(`任务 ${codeTask.value.id} 生成中... 第 ${nowNum} 次轮询`)

      // 异步等待 10 秒
      await new Promise(resolve => setTimeout(resolve, 10000))

      try {
        console.log('获取进度次数：',nowNum)
        await getCEProgress(codeTask.value.id)
      } catch (e) {
        console.error('轮询进度失败', e)
      }
    }

    if(isShow.value == false){
      console.log("本题评估截断")
      // 清空所有内部数据
      quitShowCode()
      //退出函数
      return
    }

    // 轮询结束，判断最终结果
    if (cTProgress.value.status == 2) {
      console.log(` ${codeTask.value.id} 任务完成`)
      await getCodeHistoryList()
      await getExamineMsg(codeTask.value.id)
      codeTask.value = {}
      cTProgress.value = {}
    } else {
      console.log(` ${codeTask.value.id} 未完成`)
      await getCodeHistoryList()
      await getExamineMsg(codeTask.value.id)
      codeTask.value = {}
      cTProgress.value = {}
    } 
  }else if(cTProgress.value.status == 2 || cTProgress.value.status == 3){//一提交就好了
    await getCodeHistoryList()
    await getExamineMsg(codeTask.value.id)
    codeTask.value = {}
    cTProgress.value = {}
  }
  

}




// =============================算法可视化（模块化管理）============================
const vizContainerRef = ref(null)
const vizModule = ref(null)
const loading = ref(false)
const detectedType = ref('')
const logStatus = ref(true)

// 初始化可视化模块（懒加载，确保 DOM 就绪）
const ensureVizModule = () => {
  if (vizContainerRef.value) {
    const callbacks = { onPlay: lockResultScroll, onComplete: unlockResultScroll }
    if (!vizModule.value) {
      vizModule.value = initVizModule(vizContainerRef.value, callbacks)
    } else {
      // DOM 可能被 v-if 销毁重建，确保 _container 引用是最新的
      const currentContainer = vizModule.value.getContainer()
      if (currentContainer !== vizContainerRef.value) {
        vizModule.value.setContainer(vizContainerRef.value)
      }
      // 更新回调
      vizModule.value.setCallbacks(callbacks)
    }
  }
  return vizModule.value
}

// 请求转换接口
const toVisualize = async () => {
  loading.value = true
  detectedType.value = ''
  const mod = ensureVizModule()
  if (!mod) { loading.value = false; return }

  // 显示持续加载提示
  const loadingMsg = ElMessage({
    message: '正在转换代码并生成可视化，请稍候...',
    type: 'info',
    duration: 0,
    showClose: false
  })

  // 清空日志
  const logEl = vizContainerRef.value?.querySelector('#vizLog')
  if (logEl) logEl.innerHTML = ''

  mod.logMsg('📡 开始请求转换接口', 'info')

  try {
    const params = {
      code: beforeContent.value.answer,
      historyId: beforeContent.value.id,
      language: beforeContent.value.language,
      algorithmType: 'auto'
    }
    const res = await codeVisualApi(params)
    if (res.code !== 1) throw new Error(res.msg || '转换失败')

    const apiData = res.data
    detectedType.value = apiData.detectedType || '未知算法'

    mod.logMsg(`✅ 接口转换成功！检测到算法类型：${detectedType.value}`, 'ok')

    // 调用模块启动 Worker + 渲染
    const result = await mod.start(apiData)
    if (!result.success) {
      throw new Error(result.error || '可视化启动失败')
    }
    loadingMsg.close()
    ElMessage.success('可视化加载完成，点击 ▶️ 开始播放')
  } catch (err) {
    loadingMsg.close()
    mod.logMsg(`❌ 失败：${err.message}`, 'err')
    ElMessage.error(`转换失败：${err.message}`)
  } finally {
    loading.value = false
  }
}

// 关闭面板
const closeViz = () => {
  const mod = vizModule.value
  if (mod) mod.close()
  detectedType.value = ''
}

// 组件销毁
onUnmounted(() => {
  const mod = vizModule.value
  if (mod) mod.destroy()
})


</script>

<template>
  <div class="container">

    <!-- 标题 -->
    <div class="title">
      <h1>编程练习 智能生成</h1>
      <p class="subtitle">输入学习主题，一键生成编程练习题</p>
    </div>

    <div class="main">
      <!-- 输入框 -->
      <div class="top">
        <div class="inputBox">
          <el-form 
            :inline="true"
            :rules="Rules" 
            ref="codeRef" 
            :model="codeData" 
            class="code-form"
            size="large"
            @keyup.enter.native="submit()"
          >
            <el-form-item class="input-field" label="主题/知识点" prop="text" style="width: 100%; max-width: 600px;">
             <el-input 
                v-model="codeData.text"
                show-word-limit 
                maxlength="30" 
                placeholder="例如：python基础"
                clearable
              />
            </el-form-item>
          
            <el-form-item class="btn-item">
              <el-button 
                type="primary" 
                class="submit-btn"
                @click="submit()"
                :disabled="btnDisvisible"
                size="large"
              >
                立即生成编程题
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <!-- 列表 -->
      <div class="bottom"> 

        <!-- 有数据显示列表滚动条 -->
        <div class="showMain" v-if="allList?.length">
          <el-scrollbar height="100%" width="100%">
            <div class="scroll-content">
              <div v-for="(item,index) in showList" 
                :key="item.id" class="scrollbar-demo-item"
                ref="itemRef"
              >

                <!-- 普通项 -->
                <div class="normal" 
                  @click="getValue(item.id),getCodeHistoryList(item.id)" 
                  v-if="item.status == 2"
                  @mouseenter="handleEnter(index,item.id)"
                  @mouseleave="popStore.delayHidePop"
                >
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.text }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime }}
                    </div>
                  </div>
                  <div class="item-right" @click.stop="deleteItem(item.id)">
                    删除
                  </div>
                </div>

                <!-- 生成项 -->
                <div class="loading"  @click="getValue(item.id)" v-else-if="item.status == 1 || item.status == null">
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.text }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime }}
                    </div>
                  </div>
                  <div class="item-right">
                    <!-- 加载动画 -->
                    <div class="loadingIcon">
                      <el-icon class="is-loading" :size="30" color="#2D7DDB"><Loading /></el-icon>
                    </div>
                    <div class="loadingText">
                      生成中
                    </div>
                  </div>
                </div>

                <!-- 失败项 -->
                <div class="failure" @click="getValue(item.id)" v-else>
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.text }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime }}
                    </div>
                  </div>
                  <div class="boxRight">
                    <div class="item-mid">
                      <div class="fail">
                        <el-icon class="shake-icon" :size="30"><CloseBold /></el-icon>
                        <div class="fail-text">生成失败</div>
                      </div>
                    </div>
                    <div class="item-right" @click.stop="deleteItem(item.id)">
                      删除
                    </div>
                  </div>
                </div>

              </div>

              <!-- 底部-查看更多 -->
              <div class="footer" v-if="allList.length > 20">
                <div @click="isOpenList(0)" class="text" v-if="allList?.length && allList.length != showList.length">查看更多</div>
                <div @click="isOpenList(1)" class="text" v-if="allList?.length && allList.length == showList.length">收起</div>
              </div>

            </div>
          </el-scrollbar>
        </div>

        <!-- 无数据时显示空 -->
        <div class="main mainNull" v-else-if="!allList || allList.length === 0">
          <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
          <div class="mainNullText">暂无生成内容</div>
        </div>

      </div>
    </div>


    <!-- 展示 -->
    <Transition name="slide-right">
      <!-- 开始编程区 -->
      <div class="showArea" v-if="isShow === true">

      <!-- 关闭 -->
      <div class="quit" @click="quitShowCode()">
        &nbsp;><br />
        关<br />
        闭<br />
        &nbsp;>
      </div>

      <!-- 加载项 -->
      <div class="codeLoading" v-if="isShowLoading === true">
        <div class="loadingIcon">
          <el-icon class="is-loading" :size="50" color="black"><Loading /></el-icon>
        </div>
        <div class="loadingText">
          加载中
        </div>
      </div>

      <!-- 生成中 -->
      <div class="codeCreating" v-if="showCodeData.status === 1">
        <div class="loadingIcon">
          <el-icon class="is-loading" :size="60"><Loading /></el-icon>
        </div>
        <div class="loadingText">
          生成中
        </div>
      </div>

      <!-- 生成失败 -->
      <div class="codeFail" v-else-if="showCodeData.status === 3">
        <div class="fail">
          <el-icon class="shake-icon" :size="50"><CloseBold /></el-icon>
          <div class="fail-text">生成失败</div>
        </div>
      </div>

      <!-- 生成成功-显示题目 -->
      <div class="codeSuccess" v-else-if="showCodeData.status === 2">

        <!-- 头部 -->
        <div class="head">
          <!-- 创建词 -->
          <div class="codeText">
            {{ showCodeData.text }}
          </div>
          <!-- 创建时间 -->
          <div class="codeTime">
            {{ showCodeData.createTime }}
          </div>
        </div>

        <!-- 左侧题目 -->
        <div class="left">
          <el-scrollbar height="795px" width="100%">
            <div class="scroll">
              <!-- 题目 -->
              <div class="codeTitle">
                <!-- 难度 -->
                <div class="codeLevel">
                  {{ formatDifficulty(showCodeData.difficulty) }}
                </div>
                <div>{{ showCodeData.title }}</div>
              </div>
            
              <!-- 内容 -->
              <div class="codeContent">
                <!-- 描述 -->
                <div class="codeDesc" v-html="formatContent(showCodeData.description)">
                </div>
                <!-- 程序需输入内容 -->
                <div class="codeInput" v-if="!(showCodeData.inputFormat === '无')" v-html="formatContent(showCodeData.inputFormat)">
                </div>
                <!-- 程序输出内容 -->
                <div class="codeOutput" v-if="!(showCodeData.outputFormat === '无')" v-html="formatContent(showCodeData.outputFormat)">
                </div>

                <!-- 知识点标签 -->
                <div class="codeTag" v-if="showCodeData.knowledgePoints.length > 0"> 
                  <div>本题知识点标签：</div>
                  <div class="tag" v-for="item in showCodeData.knowledgePoints"> 
                    {{ item }}
                  </div>
                </div>
              </div>

              <!-- 示例 -->
              <div class="codeExample" v-if="showCodeData?.examples && showCodeData?.examples.length > 0">
                <div class="egTop">
                  <div class="exampleTitle">
                    运行示例
                  </div>
                  <div class="btn" @click="btn(0)" :class="isEgShow ? 'closeShow' : 'openShow'">{{ isEgShow ? '收起' : '展开' }}</div>
                </div>
                
                <TransitionGroup name="expand-down">
                  <div 
                    v-for="(item, index) in showCodeData.examples" 
                    :key="index" 
                    v-if="isEgShow"
                    class="example-area-wrapper"
                  >
                    <div class="exampleArea">
                      <div>
                        <div class="egInput">
                          <span>输入 > </span>{{ item.input }}
                        </div>
                        <div class="egOutput">
                          <span>输出 > </span>{{ item.output }}
                        </div>
                      </div>
                      <div class="egExplanation">
                        <span>过程 > </span>{{ item.explanation }}
                      </div>
                    </div>
                  </div>
                </TransitionGroup>
              </div>

              <!-- tips -->
              <div class="codeTips" v-if="showCodeData?.hints.length > 0"> 
                <div class="tipsTop">
                  <div class="tipsTitle">
                    小提示
                  </div>
                  <div class="btn" @click="btn(1)" :class="isTipsShow ? 'closeShow' : 'openShow'">{{ isTipsShow ? '收起' : '展开' }}</div>
                </div>

                <TransitionGroup name="expand-down">
                  <div class="tipsArea" v-if="isTipsShow">
                    <div class="codeTips-item" v-for="(item, index) in showCodeData.hints" v-html="formatContent(item)">
                    </div>
                  </div>
                </TransitionGroup>
                
              </div>

              <!-- 选择语言下拉框 -->
              <div class="select-language"> 
                <select v-model="submitContent.language" class="native-select">
                  <option value="" disabled>请选择编写语言</option>
                  <option value="C">C</option>
                  <option value="C++">C++</option>
                  <option value="Java">Java</option>
                  <option value="Python">Python</option>
                  <option value="JavaScript">JavaScript</option>
                </select>
              </div>
            
              <!-- 编码输入区 (带行号) -->
              <div class="code-editor-container">
                <div class="line-numbers" ref="lineNumbersRef">
                  <div v-for="n in lineCount" :key="n" class="line-number-item">
                    <el-tooltip
                      v-if="getTwinWarning(n)"
                      placement="right"
                      effect="light"
                      :popper-style="{ maxWidth: '300px' }"
                    >
                      <template #content>
                        <div class="twin-tooltip-content">
                          <div class="twin-tooltip-title">AI数字孪生提示</div>
                          <div class="twin-tooltip-text">{{ getTwinWarning(n).tip }}</div>
                        </div>
                      </template>
                      <el-icon class="twin-warning-icon"><Warning /></el-icon>
                    </el-tooltip>
                    <el-tooltip
                      v-if="getTwinError(n)"
                      placement="right"
                      effect="light"
                      :popper-style="{ maxWidth: '300px' }"
                    >
                      <template #content>
                        <div class="twin-tooltip-content">
                          <div class="twin-tooltip-title grammar-error">代码语法错误</div>
                          <div class="twin-tooltip-text">{{ getTwinError(n).msg }}</div>
                        </div>
                      </template>
                      <el-icon class="twin-error-icon"><CircleClose /></el-icon>
                    </el-tooltip>
                    <span>{{ n }}</span>
                  </div>
                </div>
                <textarea
                  v-model="submitContent.answer"
                  @input="updateLineCount"
                  @keydown="handleCodeKeydown"
                  @scroll="syncLineNumbersScroll"
                  placeholder="// 选择编写语言后，在此处编写代码..."
                  class="code-textarea"
                  spellcheck="false"
                ></textarea>
              </div>

            </div>
          </el-scrollbar>
        </div>

        <!-- 右侧结果 -->
        <div class="right">

          <!-- 历史记录卡片 -->
          <div class="codeHistory">

            <!-- 头部标题 -->
            <div class="codeHistoryHead">
              <svg t="1779185007722" class="icon" viewBox="0 0 1024 1024" 
                version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6163" 
                width="200" height="200"><path d="M785.546573 781.547354c-35.593048 
                35.093146-76.984964 62.787737-123.275923 82.183948-47.890646 20.196055-98.780707 
                30.694005-151.470416 31.193908h-4.099199c-53.289592 
                0-104.579574-10.297989-152.770162-30.594025-46.49092-19.596173-87.882835-47.690685-123.075962-83.383714-70.286272-71.386057-108.278852-166.667448-106.679164-267.947666 
                0.799844-52.089826 11.497754-102.280023 31.893771-149.570787 19.696153-45.791056 47.590705-86.78305 82.883811-121.976177 
                72.585823-72.285882 169.466901-112.17809 272.446788-112.17809 52.389768 0 103.179848 10.198008 
                150.970514 30.194103 46.190978 19.296231 87.482913 46.990822 123.075961 82.183948 35.593048 35.193126 63.4876 76.08514 82.883812 
                121.676235 20.096075 47.090803 30.394064 97.181019 30.394064 148.770943 0 101.780121-40.19215 197.461433-113.177895 269.447374M511.400117 
                69.286467c-246.951767 0-443.413396 198.261277-447.112673 442.813513C60.488186 759.351689 259.649287 954.813513 506.701035 954.813513h4.699082c246.951767-2.499512 
                447.212654-198.161297 447.212654-442.813513 0.09998-244.452255-200.260887-442.713533-447.212654-442.713533" p-id="6164"></path>
                <path d="M736.656122 517.998828H511.200156V290.543253c0-16.596758-13.397383-29.994142-29.994142-29.994141s-29.994142 13.397383-29.994141 29.994141V547.89299c0 
                16.596758 13.397383 29.994142 29.994141 29.994141h255.350127c16.596758 0 29.994142-13.397383 29.994142-29.994141 0-16.496778-13.397383-29.894161-29.894161-29.894162" p-id="6165"></path>
              </svg>
              <div class="chTitle">本题提交分析历史</div>
            </div>

            <!-- 有数据显示滚动条 -->
            <el-scrollbar height="280px" width="100%" v-if="showCHList?.length">
              <div class="chScroll">
                <div v-for="item in showCHList" :key="item.id" class="scrollbar-demo-item">
                  
                  <!-- 普通项(通过绿色，未通过红色) -->
                  <div 
                    class="normal" 
                    :class="item.verdict === 'Accepted' ? 'pass' : (item.verdict === 'Wrong Answer' ? 'coming' : 'bad')" 
                    @click="getExamineMsg(item.id)" v-if="item.status == 2"
                  >
                    <div class="item-left">
                      <!-- 分数 -->
                      <div class="item-text">
                        <div>{{ item.score }} 分</div>
                        <div>{{ item.verdict == 'Accepted' ? '通过' : (item.verdict === 'Wrong Answer' ? '再接再厉' : '编译错误') }}</div>
                      </div>
                      <!-- 时间 -->
                      <div class="item-ct">
                        {{ item.createTime }}
                      </div>
                    </div>
                    <div class="item-right" @click.stop="delCHItem(item.id)">
                      删除
                    </div>
                  </div>

                  <!-- 分析项 -->
                  <div class="loading"  @click="getExamineMsg(item.id)" v-else-if="item.status == 1 || item.status == null">
                    <div class="item-left">
                      <div class="item-text">
                        等待返回成绩...
                      </div>
                      <div class="item-ct">
                        {{ item.createTime }}
                      </div>
                    </div>
                    <div class="item-right">
                      <!-- 加载动画 -->
                      <div class="loadingIcon">
                        <el-icon class="is-loading" :size="30" color="#2D7DDB"><Loading /></el-icon>
                      </div>
                      <div class="loadingText">
                        分析中
                      </div>
                    </div>
                  </div>

                  <!-- 分析失败项 -->
                  <div class="failure" @click="getExamineMsg(item.id)" v-else>
                    <div class="item-left">
                      <div class="item-text">
                        无成绩，系统分析失败！！
                      </div>
                      <div class="item-ct">
                        {{ item.createTime }}
                      </div>
                    </div>
                    <div class="boxRight">
                      <div class="item-mid">
                        <div class="fail">
                          <el-icon class="shake-icon" :size="30"><CloseBold /></el-icon>
                          <div class="fail-text">分析失败</div>
                        </div>
                      </div>
                      <div class="item-right" @click.stop="delCHItem(item.id)">
                        删除
                      </div>
                    </div>
                  </div>

                </div>
              </div>
            </el-scrollbar>
          
            <!-- 无数据时显示空 -->
            <div class="chNull" v-else>
              <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
              <div class="chNullText">暂无分析记录</div>
            </div>
          </div>

          <!-- 提交操作区 -->
          <div class="submit-wrapper">
            <el-button 
              type="primary" 
              class="custom-submit-btn" 
              @click="submitCode()"
              :disabled="!submitContent.answer.trim()"
              size="large"
            >
              <div class="btn-content">
                <img :src="imgShow()" alt="Lang" class="lang-icon" />
                <span class="btn-text">提交分析代码</span>
                <el-icon class="run-icon"><VideoPlay /></el-icon>
              </div>
            </el-button>
            <div class="submit-hint">
              <span>{{ submitContent.answer.trim() ? '准备就绪，点击运行' : '请在左侧编写代码' }}</span><br />
              <span>{{ submitContent.answer.trim() ? '点击提交后请耐心等待评估结果' : '提交后结果将在本侧显示' }}</span>
            </div>
          </div>

          <!-- 评价结果区 -->
          <Transition name="slide-right">
            <div class="resultArea" v-if="isResultShow">
              
              <!-- 关闭按钮 -->
              <div class="quit" @click="quitResult()">
                &nbsp;><br />
                关<br />
                闭<br />
                &nbsp;>
              </div>

              <!-- 加载状态 -->
              <div class="resultLoading" v-if="isShowLoading">
                <div class="loadingIcon">
                  <el-icon class="is-loading" :size="50" color="black"><Loading /></el-icon>
                </div>
                <div class="loadingText">
                  加载中
                </div>
              </div>

              <!-- 分析状态 -->
              <div class="resulting" v-if="beforeContent.status === 1">
                <div class="loadingIcon">
                  <el-icon class="is-loading" :size="60"><Loading /></el-icon>
                </div>
                <div class="loadingText">
                  分析中
                </div>
              </div>
            
              <!-- 分析失败 -->
              <div class="resultFail" v-else-if="beforeContent.status === 3">
                <div class="fail">
                  <el-icon class="shake-icon" :size="50"><CloseBold /></el-icon>
                  <div class="fail-text">生成失败</div>
                </div>
              </div>

              <!-- 正常状态 -->
              <div class="comment" v-else-if="beforeContent.status === 2">
                <el-scrollbar  ref="resultScrollbarRef" height="795px" width="100%">
                  <div class="scroll">


                    <!-- 原代码展示区 -->
                    <div class="beforeCode">
                      <!-- 分数 -->
                      <div class="codeScore">
                        {{ beforeContent.score }} 分
                      </div>

                      <!-- 头部 -->
                      <div class="beforeHead">
                        <!-- 代码详情 -->
                        <div class="header">
                          <span>【{{ beforeContent.createTime }}】</span>上传 <span >{{ beforeContent.language }}语言</span> 原代码：
                        </div>

                        <!-- 测评状态 -->
                        <div 
                          class="isPass" 
                          :class="beforeContent.verdict === 'Accepted' ? 'pass' : (beforeContent.verdict === 'Wrong Answer' ? 'coming' : 'bad')"
                        >
                          {{ beforeContent.verdict == 'Accepted' ? '通过' : (beforeContent.verdict === 'Wrong Answer' ? '再接再厉' : '编译错误') }}
                        </div>
                            
                      </div>

                      <!-- 代码解析 -->
                      <el-scrollbar height="370px" width="100%">
                        <div class="beforeCodeScroll">
                          

                          <!-- 代码区 -->
                          <div class="code-editor-container">
                            <div class="line-numbers">
                              <div v-for="n in resultCount" :key="n">{{ n }}</div>
                            </div>
                            <!-- @input="updateResultCount"无作用，因为不手动输入 -->
                            <textarea
                              v-model="beforeContent.answer"
                              @input="updateResultCount"
                              placeholder="// 此处为原代码展示块"
                              class="code-textarea"
                              spellcheck="false"
                              disabled
                            ></textarea>
                          </div>

                        </div>

                      </el-scrollbar> 
                    </div>

                    <!-- 其余评价 -->
                    <!-- 评价区 -->
                    <div class="codeComment">

                        <!-- 测试用例通过情况 -->
                        <div class="situation">
                          <div class="st-top">
                            <svg t="1780130645608" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6595" width="25" height="25"><path d="M870.912 231.936L638.464 112.64c14.336 15.36 23.04 35.328 23.04 57.856v682.496c0 22.528-9.216 43.008-23.04 57.856l232.96-119.808c28.16-14.848 46.08-44.032 46.08-75.776V308.224c0-32.256-17.92-61.44-46.592-76.288zM234.496 106.496h-42.496c-47.104 0-85.504 38.4-85.504 85.504v640c0 47.104 38.4 85.504 85.504 85.504h42.496c47.104 0 85.504-38.4 85.504-85.504v-640c0-47.104-38.4-85.504-85.504-85.504z m-10.24 704h-21.504c-17.92 0-32.256-14.336-32.256-32.256s14.336-32.256 32.256-32.256h21.504c17.92 0 32.256 14.336 32.256 32.256-0.512 17.92-14.848 32.256-32.256 32.256z m0-128h-21.504c-17.92 0-32.256-14.336-32.256-32.256s14.336-32.256 32.256-32.256h21.504c17.92 0 32.256 14.336 32.256 32.256-0.512 17.92-14.848 32.256-32.256 32.256z m0-128h-21.504c-17.92 0-32.256-14.336-32.256-32.256s14.336-32.256 32.256-32.256h21.504c17.92 0 32.256 14.336 32.256 32.256s-14.848 32.256-32.256 32.256zM513.536 106.496H471.04c-47.104 0-85.504 38.4-85.504 85.504v640c0 47.104 38.4 85.504 85.504 85.504h42.496c47.104 0 85.504-38.4 85.504-85.504v-640c0-47.104-38.4-85.504-85.504-85.504z m-10.752 704H481.28c-17.92 0-32.256-14.336-32.256-32.256s14.336-32.256 32.256-32.256h21.504c17.92 0 32.256 14.336 32.256 32.256s-14.336 32.256-32.256 32.256z m0-128H481.28c-17.92 0-32.256-14.336-32.256-32.256s14.336-32.256 32.256-32.256h21.504c17.92 0 32.256 14.336 32.256 32.256s-14.336 32.256-32.256 32.256z m0-128H481.28c-17.92 0-32.256-14.336-32.256-32.256s14.336-32.256 32.256-32.256h21.504c17.92 0 32.256 14.336 32.256 32.256s-14.336 32.256-32.256 32.256z" p-id="6596" fill="#0c84c3"></path></svg>
                            <div>Agent后台测试项通过情况：</div>
                          </div>
                          <div class="st-content">
                            <span>{{ beforeContent.totalTests }}</span> 项测试，共通过 <span>{{ beforeContent.passedTests }}</span> 项
                          </div>
                        </div>

                        <!-- 改进建议 -->
                        <div class="howDo">
                          <div class="hd-top">
                            <svg t="1780130559104" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6519" data-spm-anchor-id="a313x.search_index.0.i8.6c873a81RYlF4u" width="25" height="25"><path d="M512 32c212.224 0 384 174.912 384 390.4 0 162.688-98.752 306.56-245.696 364.288l-11.712 2.24H385.408l-11.712-2.24C226.752 729.024 128 585.088 128 422.4 128 206.912 299.776 32 512 32z m132.032 291.2l-5.76 0.512a32 32 0 0 0-26.24 31.488v82.176l-85.504-43.52-5.632-2.176a32 32 0 0 0-23.424 2.176l-85.44 43.52V355.2a32 32 0 0 0-64 0v134.4l0.384 5.376a32 32 0 0 0 46.08 23.168L512 458.24l117.504 59.84a32 32 0 0 0 46.528-28.544v-134.4a32 32 0 0 0-32-32z" fill="#f4ea2a" p-id="6520" data-spm-anchor-id="a313x.search_index.0.i6.6c873a81RYlF4u" class=""></path><path d="M638.656 724.928a32 32 0 0 1 31.872 34.56l-14.976 182.592c-2.304 28.096-25.6 49.92-53.76 49.92H422.208a54.144 54.144 0 0 1-53.824-49.92l-14.976-182.528a32 32 0 0 1 31.936-34.624h253.248z" fill="#d8cf2a" p-id="6521" data-spm-anchor-id="a313x.search_index.0.i5.6c873a81RYlF4u" class=""></path></svg>
                            <div>代码改进建议：</div>
                          </div>
                          <div class="hd-content" v-for="(item, index) in beforeContent.suggestion" :key="index">
                            {{ index + 1 }}、{{ item }}
                          </div>
                        </div>

                        <!-- 鼓励 -->
                        <div class="howDo encouragement">
                          <div class="hd-content" v-if="beforeContent.encouragement">
                            {{ beforeContent.encouragement }}
                          </div>
                        </div>

                    </div>

                    <!-- 算法可视化区 -->
                    <div class="visualization">
                      <!-- 按钮 -->
                      <div class="vsBtn">
                        <el-button
                          v-show="!detectedType"
                          type="primary"
                          class="custom-submit-btn"
                          @click="toVisualize()"
                          size="large"
                          :disabled="loading"
                        >
                          <div class="btn-content">
                            <span class="btn-text">{{ loading ? '转换中...' : '点击可视化预览所写代码' }}</span>
                            <el-icon class="run-icon"><VideoPlay /></el-icon>
                          </div>
                        </el-button>
                      </div>
                      <!-- 算法可视化展示区域 -->
                      <div class="vsArea" :class="logStatus ? 'openLogShow' : ''" ref="vizContainerRef" style="display:none;">
                        <!-- 加载中 -->
                        <div class="loading" v-if="loading">
                          <div class="loadingIcon">
                            <el-icon class="is-loading" :size="50" color="#DBEAFE"><Loading /></el-icon>
                          </div>
                          <div class="loadingText">生成中</div>
                        </div>

                        <!-- 可视化面板（由模块控制显示/隐藏） -->
                        <div id="vizSection" style="display:none;">
                          <div class="algorithm-visualization-section">
                            <!-- 可视化头部 -->
                            <div class="viz-header">
                              <div class="viz-header-left">
                              <svg t="1785307905754" class="icon" viewBox="0 0 1764 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1705" width="200" height="200"><path d="M756.474311 818.665244C749.078756 818.665244 741.512533 817.243022 734.230756 814.114133 617.551644 764.563911 542.060089 650.331022 542.060089 523.184356 542.060089 348.990578 683.3152 207.280356 856.940089 207.280356 1030.508089 207.280356 1171.706311 348.990578 1171.706311 523.184356 1171.706311 648.3968 1099.855644 762.345244 988.580978 813.431467 959.965867 826.5728 926.173867 814.057244 913.089422 785.499022 900.004978 756.997689 912.520533 723.205689 941.078756 710.064356 1012.076089 677.467022 1057.928533 604.137244 1057.928533 523.184356 1057.928533 411.739022 967.759644 321.058133 856.940089 321.058133 746.063644 321.058133 655.837867 411.739022 655.837867 523.184356 655.837867 604.592356 704.079644 677.694578 778.774756 709.438578 807.674311 721.726578 821.156978 755.120356 808.868978 784.019911 799.652978 805.637689 778.604089 818.665244 756.474311 818.665244" fill="#ffffff" p-id="1706"></path><path d="M857.8048 1012.775822C498.8928 1012.775822 196.073244 765.991822 47.479467 618.877156 16.873244 588.555378-0.022756 548.619378-0.022756 506.407822-0.022756 464.139378 16.873244 424.203378 47.479467 393.8816 196.073244 246.766933 498.8928-0.017067 857.8048-0.017067 1216.7168-0.017067 1519.536356 246.766933 1668.073244 393.8816 1698.679467 424.203378 1715.575467 464.139378 1715.575467 506.407822 1715.575467 548.619378 1698.679467 588.555378 1668.073244 618.877156 1640.425244 646.2976 1615.963022 670.020267 1574.434133 704.950044 1550.370133 725.1456 1514.473244 722.0736 1494.277689 698.0096 1474.082133 673.9456 1477.154133 638.048711 1501.218133 617.853156 1539.561244 585.597156 1561.349689 564.434489 1588.030578 538.038044 1596.905244 529.220267 1601.797689 518.013156 1601.797689 506.407822 1601.797689 494.802489 1596.905244 483.538489 1588.030578 474.7776 1478.405689 366.2336 1187.874133 113.760711 857.8048 113.760711 527.735467 113.760711 237.147022 366.2336 127.579022 474.7776 118.704356 483.538489 113.755022 494.802489 113.755022 506.407822 113.755022 518.013156 118.704356 529.220267 127.579022 537.981156 237.147022 646.582044 527.735467 898.998044 857.8048 898.998044 1027.618133 898.998044 1176.155022 849.5616 1339.369244 738.742044 1365.424356 720.992711 1400.809244 727.819378 1418.387911 753.8176 1436.080356 779.815822 1429.310578 815.143822 1403.312356 832.836267 1222.576356 955.602489 1049.179022 1012.775822 857.8048 1012.775822" fill="#ffffff" p-id="1707"></path></svg>
                              <h3>算法可视化预览</h3>
                              </div>
                              <div class="viz-header-actions">
                                <!-- <span class="viz-type">【{{ detectedType }}】</span> -->
                                <div class="close log" :class="logStatus ? 'closeLog' : 'openLog'" @click="btn(2)">{{ logStatus ? '关闭日志' : '开启日志' }}</div>
                                <button id="stopVizBtn" class="icon-btn" @click="vizModule?.stopWorker()" style="display:none;">⏹️</button>
                                <button class="icon-btn" @click="closeViz">✕</button>
                              </div>
                            </div>
                            <!-- 可视化内容（深色区域） -->
                            <div class="viz-body">
                              <div class="viz-status-wrap">
                                <span id="vizStatus" class="viz-status">等待转换...</span>
                              </div>
                              <!-- 左右分栏：代码面板 + 画布 -->
                              <div class="viz-content-wrap">
                                <!-- 左侧：代码执行跟踪面板 -->
                                <div id="vizCodePanel">
                                  <div class="viz-code-panel-header">
                                    📝 代码执行跟踪
                                  </div>
                                  <div id="vizCodeContent"></div>
                                </div>
                                <!-- 右侧：可视化画布 -->
                                <canvas id="vizCanvas" width="400" height="300"></canvas>
                              </div>
                              <!-- 播放控制栏 -->
                              <div id="vizControls">
                                <button id="vizPlayBtn" @click="vizModule?.play()" class="viz-btn-play">▶️ 开始</button>
                                <button id="vizPauseBtn" @click="vizModule?.pause()" class="viz-btn-pause" style="display:none;">⏸️ 暂停</button>
                                <button @click="vizModule?.reset()" class="viz-btn-reset">🔄 重置</button>
                                <select id="vizSpeedSelect" @change="vizModule?.updateSpeed($event.target.value)" class="viz-select">
                                  <option value="500">0.5x 慢速</option>
                                  <option value="180" selected>1x 正常</option>
                                  <option value="90">2x 快速</option>
                                  <option value="60">3x 极速</option>
                                </select>
                                <div class="speed-slider-wrap">
                                  <span class="speed-label">速度:</span>
                                  <input type="range" id="vizSpeed" class="speed-slider" min="20" max="500" value="180" @input="vizModule?.updateSpeedFromSlider($event.target.value)">
                                  <span id="vizSpeedLabel" class="speed-value">180ms</span>
                                </div>
                                <span id="vizFrameInfo" class="frame-info">帧: 0/0</span>
                              </div>
                              <!-- 日志区域 -->
                              <div id="vizLog" class="viz-log" v-show="logStatus"></div>
                            </div>
                          </div>
                        </div>

                      </div>
                    </div>

                    <!-- 该题排行榜 -->
                    <div class="rank">
                      <div class="rank-card">
                        <div class="rank-card-title">
                          <svg t="1779534825496" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="17006" width="32" height="32"><path d="M898.133 481.711l-184.035 12.714c-4.434 0.306-8.869 0.613-13.15 3.136l5.315-310.041c-2.297-33.26-30.743-58.028-61.785-55.884l-298.486 65.179c-31.042 2.145-55.811 30.59-53.514 63.85l17.447 123.555c-4.434 0.306-9.022-1.604-13.457-1.298l-176.537 56.754c-33.26 2.299-58.028 30.744-55.731 64.002l80.78 330.828c2.298 33.259 30.59 55.811 61.633 53.666l654.099-45.189c31.042-2.144 55.811-30.59 53.666-61.632l45.541-243.756c-2.298-33.259-30.743-58.028-61.786-55.884zM373.666 823.162l-170.73 11.795c-2.218 0.153-2.37-2.065-2.37-2.065l-80.781-330.827c-0.153-2.217 2.064-2.37 2.064-2.37l187.623-57.52c2.217-0.153 2.37 2.064 2.37 2.064l61.824 378.923z m274.944-18.994l-219.512 15.164-83.407-562.343c-0.153-2.218 2.064-2.37 2.064-2.37l300.703-65.332c2.218-0.153 2.37 2.063 2.37 2.063l-2.218 612.818z m208.425-14.399l-152.993 10.569 0.888-245.127c-0.152-2.217 2.064-2.37 2.064-2.37l192.904-13.327c2.217-0.153 2.37 2.064 2.37 2.064L856.881 787.55c2.218-0.151 2.37 2.065 0.154 2.219z" p-id="17007" fill="#2D7DDB"></path><path d="M566.113 377.896l-40.273 146.69-46.34 3.201 40.251-150.664-40.464 2.796 14.74-33.596 49.91-3.45c6.642-0.458 12.086 1.09 16.349 4.64 4.543 3.788 7.045 9.13 7.522 16.025 0.305 4.343-0.263 9.131-1.695 14.358zM301.071 609.96c3.534 15.665-1.16 32.015-14.073 49.062-10.886 14.388-24.395 25.821-40.531 34.294l59.73-13.482-3.259 27.445-91.174 20.576 1.889-26.582c11.846-8.241 23.271-19.843 34.268-34.805 13.202-17.967 18.559-32.458 16.074-43.456-2.573-11.415-8.259-16.131-17.047-14.144l-1.133 0.257c0.662 1.565 1.084 2.783 1.284 3.654 1.342 5.943 0.054 11.491-3.858 16.661-3.663 4.92-8.579 8.081-14.748 9.472-6.055 1.37-11.793 0.614-17.216-2.262-5.694-3.001-9.21-7.469-10.553-13.407-2.191-9.722 0.867-17.296 9.188-22.72 5.588-3.711 15.568-7.188 29.952-10.437 15.021-3.391 26.427-4.645 34.21-3.775 14.804 1.623 23.801 9.505 26.997 23.649zM843.891 614.556l-31.156 39.643c5.508 3.387 10.086 8.059 13.719 14.029 3.938 6.369 5.716 12.597 5.325 18.691-0.837 12.945-6.37 23.031-16.59 30.25-8.539 6.009-19.709 9.637-33.507 10.895-8.767 0.804-18.724 0.604-29.885-0.609-5.796-0.653-10.717-2.956-14.763-6.909-4.249-4.178-6.187-9.103-5.822-14.757 0.373-5.699 2.929-10.33 7.672-13.878 4.517-3.347 9.628-4.831 15.337-4.472 5.814 0.383 10.748 2.521 14.789 6.419 4.254 4.125 6.201 9.051 5.828 14.758-0.169 2.632-0.818 5.018-1.951 7.139 6.165 0.072 11.389-2.24 15.656-6.921 4.147-4.525 6.441-10.131 6.872-16.83 0.503-7.788-2.524-14.655-9.086-20.59-5.525-4.925-11.611-7.907-18.265-8.948l25.755-27.6-44.941-2.899 10.566-22.879 84.447 5.468z" p-id="17008" fill="#2D7DDB"></path></svg>
                          <span>本题成绩排行榜</span>
                          <div class="tip">*蓝色底色的为你的该题评估分数</div>
                        </div>
                        
                        <!-- 排行榜列表 -->
                        <el-scrollbar ref="rankScrollbarRef" max-height="666px" v-if="rankList.length">
                          <div class="rank-card-content"> 
                            <div 
                              v-for="(item, index) in rankList" 
                              :key="item.userId" 
                              class="rank-item"
                              :class=" item.userId === userId ? 'myRank' : ''"
                            >
                              <!-- 排名序号 -->
                              <div class="rank-medal" v-if="index < 3">
                                <div class="one" v-if="index == 0">
                                  <svg t="1779531288175" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6142" width="30" height="30"><path d="M604.813241 0l-153.688275 282.094345 283.489103 94.384552L938.160552 0H604.813241z" fill="#FFFFFF" p-id="6143"></path><path d="M600.046345 0l-148.921379 284.813241 86.528 31.426207L694.642759 0h-94.596414z" fill="#2157CC" p-id="6144"></path><path d="M648.986483 345.335172l88.187586 31.143725L938.160552 0h-96.397242l-192.794482 345.335172z" fill="#DF202A" p-id="6145"></path><path d="M419.186759 0l153.688275 282.094345-283.489103 94.384552L85.839448 0h333.347311z" fill="#FFFFFF" p-id="6146"></path><path d="M408.717241 0l148.939035 284.813241-86.528 31.426207L314.138483 0h94.596414z" fill="#2378F1" p-id="6147"></path><path d="M375.013517 345.335172l-88.187586 31.143725L85.839448 0h96.397242l192.794482 345.335172z" fill="#F5222D" p-id="6148"></path><path d="M209.125517 283.61269l184.002207 9.163034 119.913931-127.117241 119.896276 127.117241 192.264828-9.163034-9.304276 181.036138L953.37931 589.735724l-137.480827 117.971862 8.280276 189.175173-182.960552-8.139035L512 1024l-129.218207-135.256276-182.960552 8.121379 8.280276-189.157517L70.62069 589.735724l138.504827-125.086896-8.26262-181.036138h8.26262z" fill="#FFDA35" p-id="6149"></path><path d="M283.700966 572.239448c0 124.38069 104.96 225.880276 235.908413 225.880276s235.908414-100.510897 235.908414-225.880276c0-124.38069-104.96-225.880276-235.908414-225.880276s-235.908414 101.499586-235.908413 225.880276z" fill="#FABA00" p-id="6150"></path><path d="M570.120828 676.193103l-51.500138-30.27862-51.482483 30.260965a7.256276 7.256276 0 0 1-8.756966 0c-2.913103-1.942069-4.855172-5.843862-2.913103-8.77462l12.641103-61.510621-43.731862-41.012966c-2.913103-2.930759-4.855172-5.861517-2.913103-8.792275 1.942069-2.930759 4.855172-5.861517 7.768276-5.861518l59.268414-5.843862 24.293517-56.637793c1.942069-2.930759 4.855172-5.861517 7.768276-5.861517 2.930759 0 5.826207 2.930759 7.768275 5.861517l24.311173 56.637793 59.268414 5.843862c2.913103 0 5.826207 2.930759 5.826207 5.861518 1.942069 2.930759 0 7.821241-1.942069 8.792275l-43.731862 41.012966 12.641103 61.510621c0 2.930759 0 7.803586-2.913103 8.77462-3.884138 1.959724-8.756966 1.959724-11.652414 0z" fill="#FFD81F" p-id="6151"></path></svg>
                                </div>
                                <div class="two" v-else-if="index == 1">
                                  <svg t="1779531242145" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6262" width="30" height="30"><path d="M601.158621 0L450.206897 291.310345 728.275862 388.413793 926.896552 0z" fill="#FFFFFF" p-id="6263"></path><path d="M601.688276 0L450.206897 286.013793l87.710896 31.77931L697.37931 0z" fill="#2157CC" p-id="6264"></path><path d="M644.413793 356.051862L730.729931 388.413793 926.896552 0h-94.155035z" fill="#DF202A" p-id="6265"></path><path d="M405.186207 0L556.137931 291.310345 278.068966 388.413793 79.448276 0z" fill="#FFFFFF" p-id="6266"></path><path d="M404.656552 0L556.137931 286.013793 468.427034 317.793103 308.965517 0z" fill="#2378F1" p-id="6267"></path><path d="M361.931034 356.051862L275.614897 388.413793 79.448276 0h94.155034z" fill="#F5222D" p-id="6268"></path><path d="M214.121931 277.451034l180.630069 9.604414L512 158.896552l117.248 128.176551 188.557241-9.622069-7.944827 182.625104L944.551724 586.646069l-134.673655 118.554483 7.927172 190.640551-179.058758-8.015448L512 1024l-126.764138-136.174345-179.023448 8.015448 7.909517-190.640551L79.448276 586.646069l134.673655-126.569931-7.927172-182.625104z" fill="#DFE8ED" p-id="6269"></path><path d="M273.655172 582.62069c0 126.764138 102.753103 229.517241 229.517242 229.517241s229.517241-102.753103 229.517241-229.517241-102.753103-229.517241-229.517241-229.517242-229.517241 102.753103-229.517242 229.517242z" fill="#C2CBD4" p-id="6270"></path><path d="M559.457103 687.315862l-55.490206-32.909241-55.490207 32.909241a10.328276 10.328276 0 0 1-9.798621 0c-3.248552-1.641931-4.890483-6.585379-3.248552-9.886896l13.064828-65.800828-47.351173-44.438069c-3.266207-3.283862-4.890483-6.585379-3.266206-9.869241 1.641931-3.283862 4.908138-6.585379 8.156689-6.58538l63.664552-6.585379 26.112-60.875035c1.624276-3.301517 4.890483-6.585379 8.15669-6.585379s6.532414 3.283862 8.156689 6.585379l26.129655 60.875035 63.646897 6.585379c3.266207 0 6.532414 3.301517 6.532414 6.58538 1.624276 3.283862 0 8.22731-1.641931 9.886896l-47.315862 44.420414 13.047172 65.818483c0 3.283862 0 8.22731-3.266207 9.886896-1.624276 1.624276-6.532414 1.624276-9.798621 0z" fill="#DFE8ED" p-id="6271"></path></svg>
                                </div>
                                <div class="three" v-else>
                                  <svg t="1779531009068" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="22567" width="30" height="30"><path d="M601.158621 0L450.206897 291.310345 728.275862 388.413793 926.896552 0z" fill="#FFFFFF" p-id="22568"></path><path d="M601.688276 0L450.206897 286.013793l87.710896 31.77931L697.37931 0z" fill="#2157CC" p-id="22569"></path><path d="M644.413793 356.051862L730.729931 388.413793 926.896552 0h-94.155035z" fill="#DF202A" p-id="22570"></path><path d="M405.186207 0L556.137931 291.310345 278.068966 388.413793 79.448276 0z" fill="#FFFFFF" p-id="22571"></path><path d="M404.656552 0L556.137931 286.013793 468.427034 317.793103 308.965517 0z" fill="#2378F1" p-id="22572"></path><path d="M361.931034 356.051862L275.614897 388.413793 79.448276 0h94.155034z" fill="#F5222D" p-id="22573"></path><path d="M214.121931 277.451034l180.630069 9.604414L512 158.896552l117.248 128.176551 188.557241-9.622069-7.944827 182.625104L944.551724 586.646069l-134.673655 118.554483 7.927172 190.640551-179.058758-8.015448L512 1024l-126.764138-136.174345-179.023448 8.015448 7.909517-190.640551L79.448276 586.646069l134.673655-126.569931-7.927172-182.625104z" fill="#F8D197" p-id="22574"></path><path d="M273.655172 582.62069c0 126.764138 102.753103 229.517241 229.517242 229.517241s229.517241-102.753103 229.517241-229.517241-102.753103-229.517241-229.517241-229.517242-229.517241 102.753103-229.517242 229.517242z" fill="#E8A152" p-id="22575"></path><path d="M559.457103 687.315862l-55.490206-32.909241-55.490207 32.909241a10.328276 10.328276 0 0 1-9.798621 0c-3.248552-1.641931-4.890483-6.585379-3.248552-9.886896l13.064828-65.800828-47.351173-44.438069c-3.266207-3.283862-4.890483-6.585379-3.266206-9.869241 1.641931-3.283862 4.908138-6.585379 8.156689-6.58538l63.664552-6.585379 26.112-60.875035c1.624276-3.301517 4.890483-6.585379 8.15669-6.585379s6.532414 3.283862 8.156689 6.585379l26.129655 60.875035 63.646897 6.585379c3.266207 0 6.532414 3.301517 6.532414 6.58538 1.624276 3.283862 0 8.22731-1.641931 9.886896l-47.315862 44.420414 13.047172 65.818483c0 3.283862 0 8.22731-3.266207 9.886896-1.624276 1.624276-6.532414 1.624276-9.798621 0z" fill="#F8D197" p-id="22576"></path></svg>
                                </div>
                              </div>
                              <div class="rank-index" v-else>
                                {{ index + 1 }}
                              </div>
                            
                              <!-- 用户信息 -->
                              <div class="rank-info">
                                <div class="user-avatar">
                                  <!-- 如果有头像图片可以使用 img，这里用默认图标代替 -->
                                  <el-avatar :size="45" :src="item.avatar" style="border: 1px solid #eee">
                                    {{ item.username.charAt(0) }}
                                  </el-avatar>

                                  <div class="user-name">{{ item.username }}</div>
                                </div>

                                <div class="user-score">历史最高得分 
                                  <span>{{ item.score }}</span>
                                   分
                                </div>

                                <!-- <div class="user-ct">
                                  {{ item.createTime }}
                                </div> -->

                              </div>

                              <!-- AI分析比较按钮 -->
                              <div class="compareCode" @click="compareCode(item)">
                                AI分析比较
                              </div>

                              <!-- 查看按钮 -->
                              <div class="lookUserCode" @click="getLookUserMsg(item.userId,index)">
                                查看代码
                              </div>

                            </div>

                            <!-- 回到顶部 -->
                            <div class="backRankTop">
                              <div class="backTopBtn" @click="scrollToTop(rankScrollbarRef)">返回排行榜顶部</div>
                            </div>
                          </div>
                        </el-scrollbar>
                      
                        <div class="rankNull" v-else>
                          <img src="@/assets/image/emptyStatus.png" alt="暂无排名">
                          <div class="text">暂无排名</div>
                        </div>
                       
                      </div>
                    </div>

                    <!-- 回到顶部 -->
                    <div class="backTop">
                      <div class="backTopBtn" @click="scrollToTop(resultScrollbarRef)">返回评估页顶部</div>
                    </div>

                  </div>
                </el-scrollbar>

              </div>
            </div>
          </Transition>
        </div>

      </div>

      <!-- 查看他人代码对话框 -->
      <Transition name="dialog-fade">
        <div class="lookUserCodeDialog" v-if="isLookCode">

          <!-- 卡片容器 -->
          <div class="card">
            <!-- 头部信息 -->
            <div class="lookHead">
              <!-- 左侧信息 -->
              <div class="leftArea">
                <div class="user-avatar">
                  <el-avatar :size="50" :src="lookUserMsg.avatar" style="border: 1px solid #eee">
                    {{ lookUserMsg.username.charAt(0) }}
                  </el-avatar>
                </div>
                <div class="lookInfo">
                  <div class="topA">
                    <div class="user-name">{{ lookUserMsg.username }}</div>
                    <div class="user-score">得分：<span>{{ lookUserMsg.score }}</span> 分</div>
                  </div>
                  <!-- <div class="bottomA">
                    <div class="user-ct">提交分析时间：{{ lookUserMsg.createTime }}</div>
                  </div> -->
                </div>
              </div>
              <!-- 右侧关闭按钮 -->
              <div class="rightArea" @click="closeLookCode()">
                关闭
              </div>
            </div>
            <!-- 内容信息 -->
            <div class="lookCode">
              <el-scrollbar height="480px" width="100%">
                <div class="lookCodeScroll">
                  <div class="code-editor-container">
                    <div class="line-numbers">
                      <div v-for="n in lookCount" :key="n">{{ n }}</div>
                    </div>
                    <!-- @input="updateLookCount"无作用，因为不手动输入 -->
                    <textarea
                      v-model="lookUserMsg.codePreview"
                      @input="updateLookCount"
                      placeholder="// 此处为原代码展示块"
                      class="code-textarea"
                      spellcheck="false"
                      disabled
                    ></textarea>
                  </div>
                </div>
              </el-scrollbar>
            </div>
          </div>

        </div>
      </Transition>

      </div>
    </Transition>


    <!-- AI分析比较弹窗 -->
    <div v-if="compareVisible" class="compare-overlay">
      <div class="compare-modal">
        <div class="compare-header">
          <span class="compare-title">AI代码分析比较</span>
          <button class="compare-close" @click="closeCompare">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        
        <div v-if="compareLoading" class="compare-loading">
          <div class="loading-dots">
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
          </div>
          <span>AI正在分析代码，请稍候...</span>
        </div>
        
        <div v-else class="compare-body">
          <div v-if="compareData && compareData.length >= 3" class="compare-content">
            <!-- 分数对比 -->
            <div class="compare-score-section">
              <div class="compare-score-title">分数对比</div>
              <div class="score-comparison">
                <div class="score-item score-a">
                  <div class="score-avatar">
                    <el-avatar :size="50" :src="compareUserInfo[compareData[0].user_id]?.avatar">
                      {{ compareUserInfo[compareData[0].user_id]?.username?.charAt(0) || '我' }}
                    </el-avatar>
                  </div>
                  <div class="score-name">{{ compareUserInfo[compareData[0].user_id]?.username || '我' }}</div>
                  <div class="score-value">{{ compareData[0].score }}</div>
                  <div class="score-verdict" :class="compareData[0].verdict?.toLowerCase().replace(/\s+/g, '')">
                    {{ compareData[0].verdict }}
                  </div>
                </div>
                <div class="score-vs">VS</div>
                <div class="score-item score-b">
                  <div class="score-avatar">
                    <el-avatar :size="50" :src="compareUserInfo[compareData[1].user_id]?.avatar">
                      {{ compareUserInfo[compareData[1].user_id]?.username?.charAt(0) || '用户' }}
                    </el-avatar>
                  </div>
                  <div class="score-name">{{ compareUserInfo[compareData[1].user_id]?.username || '用户' }}</div>
                  <div class="score-value">{{ compareData[1].score }}</div>
                  <div class="score-verdict" :class="compareData[1].verdict?.toLowerCase().replace(/\s+/g, '')">
                    {{ compareData[1].verdict }}
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 代码对比 -->
            <div class="compare-code-section">
              <div class="compare-code-title">代码对比</div>
              <div class="code-comparison">
                <div class="code-panel code-a">
                  <div class="code-header code-header-a">
                    <span>{{ compareUserInfo[compareData[0].user_id]?.username || '我' }} 的代码</span>
                    <span class="code-lang">{{ compareData[0].language }}</span>
                  </div>
                  <pre class="code-content">{{ compareData[0].full_code }}</pre>
                </div>
                <div class="code-panel code-b">
                  <div class="code-header code-header-b">
                    <span>{{ compareUserInfo[compareData[1].user_id]?.username || '用户' }} 的代码</span>
                    <span class="code-lang">{{ compareData[1].language }}</span>
                  </div>
                  <pre class="code-content">{{ compareData[1].full_code }}</pre>
                </div>
              </div>
            </div>
            
            <!-- 图表对比 -->
            <div class="compare-chart-section">
              <div class="compare-chart-title">维度分析</div>
              <div class="chart-comparison">
                <div class="chart-panel">
                  <div class="chart-header">雷达图</div>
                  <div ref="radarChartRef" class="chart-container"></div>
                </div>
                <div class="chart-panel">
                  <div class="chart-header">折线图</div>
                  <div ref="barChartRef" class="chart-container"></div>
                </div>
              </div>
            </div>
            
            <!-- 复杂度对比 -->
            <div class="compare-complexity-section">
              <div class="compare-complexity-title">复杂度对比</div>
              <div class="complexity-grid">
                <div class="complexity-card card-a">
                  <div class="card-header">
                    <el-avatar :size="36" :src="compareUserInfo[compareData[0].user_id]?.avatar" class="card-avatar">
                      {{ compareUserInfo[compareData[0].user_id]?.username?.charAt(0) || '我' }}
                    </el-avatar>
                    <div class="card-name">{{ compareUserInfo[compareData[0].user_id]?.username || '我' }}</div>
                  </div>
                  <div class="card-body">
                    <div class="complexity-item-row">
                      <span class="complexity-type">时间复杂度</span>
                      <span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_a?.time_complexity || '-' }}</span>
                    </div>
                    <div class="complexity-item-row">
                      <span class="complexity-type">空间复杂度</span>
                      <span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_a?.space_complexity || '-' }}</span>
                    </div>
                  </div>
                </div>
                <div class="complexity-vs">
                  <!-- <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="var(--text-gray)" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                  </svg> -->
                  vs
                </div>
                <div class="complexity-card card-b">
                  <div class="card-header">
                    <el-avatar :size="36" :src="compareUserInfo[compareData[1].user_id]?.avatar" class="card-avatar">
                      {{ compareUserInfo[compareData[1].user_id]?.username?.charAt(0) || '用' }}
                    </el-avatar>
                    <div class="card-name">{{ compareUserInfo[compareData[1].user_id]?.username || '用户' }}</div>
                  </div>
                  <div class="card-body">
                    <div class="complexity-item-row">
                      <span class="complexity-type">时间复杂度</span>
                      <span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_b?.time_complexity || '-' }}</span>
                    </div>
                    <div class="complexity-item-row">
                      <span class="complexity-type">空间复杂度</span>
                      <span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_b?.space_complexity || '-' }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- AI分析报告 -->
            <div class="compare-report-section">
              <div class="compare-report-title">AI分析报告</div>
              <div class="report-content">
                <div class="report-item">
                  <div class="report-label">综合评价</div>
                  <div class="report-text" v-html="markdownToHtml(compareData[2]?.data?.comparison?.overall_evaluation || '-')"></div>
                </div>
                <div class="report-item">
                  <div class="report-label">算法思路对比</div>
                  <div class="report-text" v-html="markdownToHtml(compareData[2]?.data?.comparison?.algorithm_comparison || '-')"></div>
                </div>
                <div class="report-item">
                  <div class="report-label">算法复杂度比较</div>
                  <div class="report-text" v-html="markdownToHtml(compareData[2]?.data?.comparison?.complexity_analysis || '-')"></div>
                </div>
                <div class="report-item">
                  <div class="report-label">代码质量比较</div>
                  <div class="report-text" v-html="markdownToHtml(compareData[2]?.data?.comparison?.code_quality_comparison || '-')"></div>
                </div>
                <div class="report-item">
                  <div class="report-label">优缺点分析</div>
                  <div class="report-text" v-html="markdownToHtml(compareData[2]?.data?.comparison?.strengths_and_weaknesses || '-')"></div>
                </div>
                <div class="report-item">
                  <div class="report-label">改进建议</div>
                  <div class="report-text" v-html="markdownToHtml(compareData[2]?.data?.comparison?.suggestions_for_improvement || '-')"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>


  <!-- 冲突提示弹窗 -->
  <Transition name="fade">
    <div v-if="showConflictDialog" class="conflict-dialog-mask">
      <div class="conflict-dialog">
        <div class="conflict-dialog-header">
          <svg t="1783932506294" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1708" width="24" height="24"><path d="M512 958.016611c-245.919634 0-446.016611-200.064292-446.016611-446.016611 0-245.919634 200.095256-446.016611 446.016611-446.016611 245.952318 0 446.016611 200.064292 446.016611 446.016611S757.952318 958.016611 512 958.016611zM512 129.983389c-210.655557 0-382.016611 171.359333-382.016611 382.016611 0 210.624593 171.359333 382.016611 382.016611 382.016611 210.624593 0 382.016611-171.359333 382.016611-382.016611S722.624593 129.983389 512 129.983389z" fill="#fb722e" p-id="1709"></path><path d="M463.99957 304.00043c0 26.509985 21.490445 48.00043 48.00043 48.00043s48.00043-21.490445 48.00043-48.00043-21.490445-48.00043-48.00043-48.00043S463.99957 277.490445 463.99957 304.00043z" fill="#fb722e" p-id="1710"></path><path d="M512 768c-17.664722 0-32.00086-14.303454-32.00086-32.00086L479.99914 448c0-17.664722 14.336138-32.00086 32.00086-32.00086s32.00086 14.336138 32.00086 32.00086l0 287.99914C544.00086 753.696546 529.664722 768 512 768z" fill="#fb722e" p-id="1711"></path></svg>
          <span>温馨提示</span>
        </div>
        <div class="conflict-dialog-content" v-html="formatConflictMessage(conflictData.suggestionWarning)"></div>
        <div class="conflict-dialog-footer">
          <button class="conflict-btn conflict-btn-reject" @click="handleConflictOption(false)">
            拒绝
          </button>
          <button class="conflict-btn conflict-btn-accept" @click="handleConflictOption(true)">
            接受
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>

/* 优化 通知question 弹窗样式 */
.notify-custom {
  border-radius: 8px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1) !important;
  min-width: 380px;
  max-width: 480px;
}
.notify-custom .el-notification__content {
  padding: 8px 12px;
}

/* ================= 右侧滑入过渡动画 ================= */
/* 定义动画持续时间和缓动函数 */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

/* 进入前状态：向右偏移 100% (屏幕外) */
.slide-right-enter-from {
  transform: translateX(100%);
}

/* 进入后状态：回到原位 */
.slide-right-enter-to {
  transform: translateX(0);
}

/* 离开前状态：在原位 */
.slide-right-leave-from {
  transform: translateX(0);
}

/* 离开后状态：向右偏移 100% (屏幕外) */
.slide-right-leave-to {
  transform: translateX(100%);
}

/* ================= 向下展开过渡动画 ================= */

/* 进入/离开时的过渡属性 */
.expand-down-enter-active,
.expand-down-leave-active {
  transition: all 0.4s ease-in-out;
  overflow: hidden;
}

/* 进入前状态：高度为0，透明，向下偏移 */
.expand-down-enter-from {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}

/* 进入后状态：高度自动（通过max-height模拟），不透明，原位 */
.expand-down-enter-to {
  max-height: 500px; /* 设置一个比实际内容大的值即可 */
  opacity: 1;
  transform: translateY(0);
}

/* 离开前状态：同进入后 */
.expand-down-leave-from {
  max-height: 500px;
  opacity: 1;
  transform: translateY(0);
}

/* 离开后状态：同进入前 */
.expand-down-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateY(-10px);
}

/* 确保 wrapper 没有多余的 margin 影响动画计算 */
.example-area-wrapper {
  width: 100%;
}

/* ================= 对话框弹出动画 (淡入+缩放) ================= */

/* 进入/离开 激活状态 */
.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

/* 进入前状态：透明且缩小 */
.dialog-fade-enter-from {
  opacity: 0;
  transform: scale(0.95);
}

/* 进入后状态：完全不透明且正常大小 */
.dialog-fade-enter-to {
  opacity: 1;
  transform: scale(1);
}

/* 离开前状态：完全不透明且正常大小 */
.dialog-fade-leave-from {
  opacity: 1;
  transform: scale(1);
}

/* 离开后状态：透明且缩小 */
.dialog-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}








.container {
  width: 100%;
  height: 100%;
  background: transparent;
  overflow: hidden;
}
.title {
  text-align: center;
  margin-bottom: 20px;
}
.title h1 {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
}
.subtitle {
  font-size: 14px;
  color: var(--text-gray);
}

.main {
  /* border: 1px solid green; */
  width: 100%;
  height: 75vh;

  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 10px;
}

.top {
  width: 100%;
  /* border: 1px solid red; */
  padding: 0; 
  display: flex;
  justify-content: center;
}

.bottom {
  width: 100%;
  /* border: 1px solid blue; */
  padding: 0; 
  flex: 1;
  overflow: hidden;
}



/* 输入区域 */
.top .inputBox {
  padding: 20px 40px 0 40px;
  width: 50%; 
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: var(--shadow-normal);
  transition: all 0.5s;
}

.top .inputBox:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}


.code-form {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: flex-start;
  gap: 20px; 
}

:deep(.el-form-item__label) {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-gray);
}
.submit-btn {
  font-weight: bold;
  letter-spacing: 1px;
  transition: all 0.3s;
}
.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--primary-hv);
}
/* ================= 表单样式 ================= */
:deep(.el-button--primary){
  --el-button-bg-color: var(--primary);
  --el-button-border-color: var(--primary);

  --el-button-hover-bg-color: var(--primary-hv);
  --el-button-hover-border-color: var(--primary-hv);

  --el-button-active-color: var(--primary-act);
  --el-button-active-bg-color: var(--primary-act);
  --el-button-active-border-color: var(--primary-act);

  --el-button-disabled-bg-color: var(--primary-disa-bgc);
  --el-button-disabled-border-color: var(--primary-disa-border);
}
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}
:deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}


/* 列表区域 */
.bottom .showMain { 
  margin: 0 auto;
  /* border: 2px dotted blue; */
  width: 70%;
  height: 100%;
  flex: 1;
  min-height: 0; 
  overflow: hidden; 
}
.scroll-content {
  padding: 0 40px 30px 40px;
}
.scrollbar-demo-item {
  padding: 10px 30px;
  margin: 10px 0;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--el-fill-color-light);
  box-shadow: var(--shadow-normal);
  overflow: hidden; 
  transition: all 0.3s;
}

/* 夜间模式 - 列表项背景 */
.dark .scrollbar-demo-item {
  background: var(--bg-card);
}

/* 正常项&加载项&删除项 样式 */
.item-left {
  max-width: 1000px;
}
.normal .item-left {
  max-width: 1000px;
}
.scrollbar-demo-item>div {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.item-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-body);
  /* 溢出隐藏 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.normal .item-ct {
  font-size: 14px;
  color: var(--text-normal);
}

.scrollbar-demo-item .loading{
  animation: pulse 1.5s infinite ease-in-out; 
}

.loading .loadingIcon {
  width: 50px;
  height: 100%;
}
.loading .loadingText {
  width: 65px;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  animation: none;
}
.loading .item-right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

/* 生成项动画 */
.loadingIcon {
  width: 100px;
  height: 100px;
  margin: 0 auto;
  display: flex;
  justify-content: center;
  align-items: center;
}
.loadingText {
  color: var(--text-body);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
  animation: pulse 1.5s infinite ease-in-out; 
}
.loadingText::after {
  content: '...';
  /* steps(5, end) 计时函数：将动画分成若干个阶梯状的步骤，而不是平滑地渐变 */
  animation: dots 1.5s steps(5, end) infinite;
}
.overBox .el-icon.is-loading {
  color: var(--text-body);
  animation: rotating 2s linear infinite;
}
/* 动效 */
/* 定义旋转关键帧 */
@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
/* 定义文字闪烁呼吸关键帧 */
@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
/* 定义文字呼吸点关键帧 */
@keyframes dots {
  0%, 20% { content: '.'; }
  40% { content: '..'; }
  60%, 100% { content: '...'; }
}

/* 失败项动画 */
.fail {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--main-delete); /* 统一使用 Element 危险色 */
}
.fail .shake-icon {
  color: var(--main-delete);
  /* 添加抖动动画 */
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
  transform: translate3d(0, 0, 0);
  backface-visibility: hidden;
  perspective: 1000px;
}
.fail .fail-text {
  font-size: 14px;
  font-weight: 500;
  opacity: 0;
  animation: fade-in-up 0.5s ease-out forwards;
  animation-delay: 0.3s; /* 等图标抖完再显示文字 */
}

/* 列表处失败项文字 */
.failure .item-text{ 
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
}
.failure .item-ct{
  animation: fade-in-up 0.5s ease-out;
}
.failure .boxRight {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 60px;
}
/* 图标抖动动画 (Shake) */
@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}
/* 文字上浮渐显 (Fade In Up) */
@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.normal .item-right:hover,
.failure .item-right:hover { 
  cursor: pointer;
  text-decoration: underline;
  color: var(--main-delete);
  transition: all 0.3s;
}
/* 普通项 Hover & 加载项 Hover */
.scrollbar-demo-item:has(.normal):hover,
.scrollbar-demo-item:has(.loading):hover {
  cursor: pointer;
  box-shadow: var(--shadow-brand);
  transform: translateY(-3px);
  border-color: var(--primary);
}

/* 失败项 Hover */
.scrollbar-demo-item:has(.failure):hover {
  /* cursor: no-drop; */
  cursor: pointer;
  transform: translateY(-3px);
  border-color: var(--main-delete);
  background-color: rgba(245, 108, 108, 0.1);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.2);
}

.bottom .mainNull {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
.bottom .mainNull img {
  width: 160px;
  margin-bottom: 20px;
}
.bottom .mainNull .mainNullText {
  font-size: 16px;
  color: var(--text-gray);
}

/* 底部的底部区域 */
.bottom .footer {
  /* 居中 */
  left: 5%;
  bottom: 0;
  z-index: 1;
  width: 90%;
  height: 10%;
  flex-shrink: 0; /* 防止被压缩 */
  display: flex;
  justify-content: center;
  align-items: center;
  /* border: 2px solid green; */
  background: transparent;
}
.footer .text{
  font-size: 18px;
  color: var(--text-gray);
}
.footer .text:hover {
  text-decoration: underline;
  color: var(--primary);
  cursor: pointer;
}


/* 显示编程区 */
.showArea {
  position: absolute;
  z-index: 2;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  padding-left: 30px;
  background-color: var(--bg-page);
}
/* 退出按钮 */
.showArea .quit {
  z-index: 2;
  position: absolute;
  font-size: 20px;
  font-weight: bold;
  color: var(--main-delete);
  top: 0;
  left: 0;
  width: 30px;
  height: 100%;
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
  /* border: 1px solid black; */
  display: flex;
  justify-content: center;
  align-items: center;
}
.showArea .quit:hover {
  cursor: pointer;
}
.showArea .quit:hover {
  color: var(--main-delete-hover);
  box-shadow: 0 1px 12px var(--main-shadow);
}
/* 加载中 */
.showArea .codeLoading,
.resultArea .resultLoading {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;

  /* border: 2px solid pink; */
}

/* 生成中 */
.showArea .codeCreating,
.showArea .codeFail,
.resultArea .resulting,
.resultArea .resultFail {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: var(--primary-fade);
}
.codeCreating .loadingIcon,
.resultArea .resulting .loadingIcon {
  width: 100%;
  height: 100px;
}
.codeCreating .is-loading,
.codeCreating .loadingText,
.resulting .is-loading,
.resulting .loadingText {
  font-size: 16px;
  color: var(--primary);
}
/* 展示处失败项 */
.showArea .codeFail,
.resultArea .resultFail {
  background-color: var(--main-fail-status);
}

/* 生成成功显示区 */
.showArea .codeSuccess { 
  height: 100%;
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  transition: all 0.3s ease;
}
.codeSuccess .left,
.codeSuccess .right {
  position: relative;
  z-index: 0;
  width: 100%;
  height: 100%;
  flex: 1;
}
.codeSuccess .scroll {
  background-color: var(--bg-page);
  padding: 10px;
  padding-top: 60px;
}

.showArea .head {
  z-index: 1;
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 50px;
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.head .codeText {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
}
.head .codeTime {
  font-size: 12px;
  color: var(--text-gray);
}
.codeSuccess .codeTitle {
  /* 内部元素对齐 */
  display: flex;
  align-items: center;
  justify-content: flex-start;
}
.codeSuccess .codeTitle .codeLevel {
  font-size: 14px;
  color: var(--primary);
  border: 1px solid var(--primary);
  background-color: var(--primary-fade);
  padding: 1px 5px;
  border-radius: 3px;
}
.codeSuccess .codeTitle div:nth-child(2) {
  margin-left: 10px;
  font-size: 20px;
  font-weight: 600;
  color: var(--primary);
}

.codeSuccess .codeContent {
  margin: 10px 0;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--text-gray);
  background-color: var(--bgc-light);
}
.codeContent .codeDesc {
  font-size: 18px;
  font-weight: 500;
}
.codeContent .codeInput,
.codeContent .codeOutput {
  margin-left: 20px;
  font-size: 16px;
  color: var(--text-gray);
}
.codeContent .codeTag {
  border-top: 1px solid var(--border-color);
  width: 100%;
  margin: 5px 0;
  padding-top: 8px;
  display: flex;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 5px;
}
.codeTag div:first-child {
  font-size: 12px;
  color: var(--text-gray);
}
.codeTag .tag {
  font-size: 12px;
  border-radius: 6px;
  padding: 0 4px;
  border: 1px solid var(--highlight);
  color: var(--highlight);
}

/* 收起/展开按钮 */
.codeSuccess .btn.openShow,
.codeSuccess .btn.closeShow {
  font-size: 12px;
  color: var(--main-delete);
  border: 1px solid var(--main-delete);
  background-color: var(--main-fail-status);
  padding: 0 4px;
  border-radius: 8px;
}
.codeSuccess .btn.openShow {
  color: var(--primary-act);
  border: 1px solid var(--primary-act);
  background-color: var(--primary-fade);
}
.codeSuccess .btn:hover {
  cursor: pointer;
}

.codeSuccess .codeExample,
.codeSuccess .codeTips {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 5px;
}
.codeSuccess .codeTips{
  margin: 10px 0;
}
.codeSuccess .codeTips .codeTips-item {
  color: var(--text-gray);
}

.codeExample .egTop,
.codeTips .tipsTop { 
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}
.codeExample .exampleTitle,
.codeTips .tipsTitle { 
  font-size: 12px;
  font-weight: 500;
  color: var(--text-gray);
}

.codeExample .exampleArea,
.codeTips .tipsArea {
  width: 100%;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background-color: var(--bgc-light);
}
.codeExample .exampleArea span {
  font-weight: 600;
}
.codeExample .exampleArea>div:first-child {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 20px;
  margin-bottom: 5px;
}
.exampleArea span {
  color: var(--primary);
}

/* ======================下拉框=========================== */
.select-language {
  margin: 10px 0 10px 0;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}

.lang-label {
  font-size: 14px;
  color: var(--text-gray);
  font-weight: 700;
}

.native-select {
  /* min-width: 50px; */
  padding: 8px 30px 8px 12px;
  font-size: 13px;
  color: var(--text-gray);
  border: 1px solid var(--text-gray);
  border-radius: 4px;
  outline: none;
  cursor: pointer;
  appearance: none;
  transition: all 0.2s ease;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23cccccc' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 8px center;
  background-size: 14px;
}
.native-select:hover {
  border-color: var(--primary);
}
.native-select:focus {
  border-color: var(--primary);
}
.native-select option {
  background-color: var(--bg-card);
  color: var(--text-gray);
}



/* ====================== 编码输入区美化 (IDE 风格) ====================== */
.code-editor-container {
  position: relative;
  display: flex;
  width: 100%;
  min-height: 300px;
  border: 1px solid #3e3e42;
  border-radius: 6px;
  overflow: hidden;
  background-color: #1e1e1e;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 行号区域 */
.line-numbers {
  width: 55px;
  flex-shrink: 0;
  background-color: #1e1e1e;
  color: #858585;
  text-align: right;
  padding: 15px 8px 15px 15px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
  user-select: none;
  border-right: 1px solid #333;
  overflow: hidden;
  position: relative;
  will-change: transform;
  box-sizing: border-box;
}

.line-number-item {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  position: relative;
  height: 25.6px; /* 14px * 1.6 line-height */
  line-height: 25.6px;
}

.line-number-item span {
  flex-shrink: 0;
}

.twin-warning-icon {
  color: #f0ad4e;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
}

.twin-warning-icon:hover {
  color: #f7c948;
}

.twin-error-icon {
  color: #f56c6c;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
}

.twin-error-icon:hover {
  color: #f89898;
}

/* 孪生提示框样式 */
.twin-tooltip-content {
  padding: 4px 0;
}

.twin-tooltip-title {
  font-weight: bold;
  color: #2D7DDB;
  font-size: 14px;
  margin-bottom: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e0e0e0;
}
.grammar-error {
  color: #f56c6c;
}

.twin-tooltip-text {
  color: #333;
  font-size: 13px;
  line-height: 1.5;
}

/* 文本输入区域 */
.code-textarea {
  flex: 1;
  background-color: transparent;
  color: #d4d4d4;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  padding: 15px;
  border: none;
  resize: vertical;
  outline: none;
  white-space: pre; /* 保持空格和换行 */
  overflow-x: auto;
}
.code-textarea::placeholder {
  color: #6a6a6a;
  font-style: italic;
}

.code-editor-container:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary) inset, 0 4px 12px rgba(45, 125, 219, 0.1);
}


/* 右侧 */
/* 提交区 */
.codeSuccess .right {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  overflow-y: auto;
}
.submit-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 100px 0;
  padding: 0 180px;
  gap: 5px;
  width: 100%;
}
/* 自定义提交按钮样式 */
.custom-submit-btn {
  width: 100%;
  height: 50px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, #1a5f9e 100%); /* 渐变背景 */
  box-shadow: 0 4px 15px rgba(45, 125, 219, 0.3);
  transition: all 0.3s ease;
  border-radius: 8px;
  padding: 0;
}

.custom-submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.5);
  background: linear-gradient(135deg, var(--primary-hv) 0%, #2070b5 100%);
}

.custom-submit-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.custom-submit-btn.is-disabled,
.custom-submit-btn:disabled:hover {
  background: #333;
  box-shadow: none;
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  width: 100%;
  height: 100%;
}

.lang-icon {
  width: 35px;
  object-fit: contain;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.2));
}

.btn-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--bg-card);
  letter-spacing: 1px;
}

.run-icon {
  font-size: 18px;
  color: var(--bg-card);
}

/* 底部提示文字 */
.submit-hint {
  margin-top: 10px;
  font-size: 18px;
  color: var(--text-gray);
  text-align: center;
  transition: color 0.3s;
}
.submit-hint span:last-child {
  font-size: 14px;
  color: var(--text-gray);
}

.submit-wrapper .submit-hint:hover span {
  color: var(--primary);
}

/* 该题历史记录区域 */
.right .codeHistory {
  border: 1px solid var(--border-color);
  background-color: var(--bg-card);
  border-radius: 10px;
  box-shadow: var(--shadow-normal);
  width: 70%;
  height: 400px;
  /* border: 2px dotted green; */
  margin-top: 70px;
  padding: 20px;
  overflow: hidden;
}
.codeHistory .codeHistoryHead {
  z-index: 1;
  width: 100%;
  height: 14%;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
/* 历史记录-顶部区域 */
.codeHistoryHead .chTitle{
  font-size: 20px;
  font-weight: 700;
}
.codeHistoryHead svg {
  width: 6%;
}
.codeHistoryHead svg path {
  fill: var(--primary) !important;
  stroke: var(--primary);
}

/* 历史记录-空数据区域 */
.codeHistory .chNull {
  width: 100%;
  height: 80%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-gray);
}
.codeHistory .chNull img { 
  width: 30%;
}

.codeHistory .failure .boxRight {
  gap: 20px;
}

/* 历史记录-滚动区域 */
.codeHistory .chScroll { 
  padding: 0 10px;
}
/* 正常状态-通过测试 */
.chScroll .scrollbar-demo-item:has(.normal.pass) {
  border-color: var(--pass);
  background-color: var(--pass-bg-color);
}
.chScroll .scrollbar-demo-item:has(.normal.pass):hover { 
  border-color: var(--pass-hover);
  box-shadow: 0 2px 12px var(--pass-shadow);
}
/* 正常状态-加油 */
.chScroll .scrollbar-demo-item:has(.normal.coming) {
  border-color: var(--coming);
  background-color: var(--coming-bg-color);
}
.chScroll .scrollbar-demo-item:has(.normal.coming):hover { 
  border-color: var(--coming-hover);
  box-shadow: 0 2px 12px var(--coming-shadow);
}
/* 正常状态-编译出错 */
.chScroll .scrollbar-demo-item:has(.normal.bad) {
  border-color: var(--main-delete);
  background-color: var(--main-fail-status);
}
.chScroll .scrollbar-demo-item:has(.normal.bad):hover { 
  border-color: var(--main-delete-hover);
  box-shadow: 0 2px 12px var(--main-shadow);
}

/* 历史记录项-文字排版 */
.codeHistory .item-text {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}
.codeHistory .item-text div:first-child {
  font-weight: 700;
  font-size: 20px;
}
.codeHistory .item-text div:last-child {
  font-weight: 700;
  font-size: 14px;
  padding: 1px 6px;
}

/* pass */
.codeHistory .pass .item-text div {
  color: var(--pass);
}
.codeHistory .pass .item-text div:last-child {
  border: 1px solid var(--pass-hover);
  border-radius: 10px;
}
/* coming */
.codeHistory .coming .item-text div {
  color: var(--coming);
}
.codeHistory .coming .item-text div:last-child {
  border: 1px solid var(--coming-hover);
  border-radius: 8px;
}
/* bad */
.codeHistory .bad .item-text div {
  color: var(--main-delete);
}
.codeHistory .bad .item-text div:last-child {
  border: 1px solid var(--main-delete-hover);
  border-radius: 8px;
}


/* =======================评价结果展示区================== */
.resultArea {
  /* border: 1px solid black; */
  position: absolute;
  /* padding-top: 50px; */
  z-index: 2;
  top: 0;
  right: 0;
  width: 100%;
  height: 100%;
  padding-left: 30px;
  background-color: var(--bg-page);
  overflow: hidden;
}
.resultArea .quit {
  height: 100%;
}

/* 分析结果 */
.resultArea .comment .scroll {
  /* border: 1px solid black; */
  padding: 10px;
  padding-top: 55px;
  padding-bottom: 60px;
}

.resultArea .beforeCode {
  position: relative;
  width: 100%;
  height: 405px;
}
.beforeCode .beforeCodeScroll {
  background-color: var(--bg-page);
  padding-right: 10px;
}
/* 分数 */
.beforeCode .codeScore {
  z-index: 1;
  position: absolute;
  top: -10px;
  right: 20px;
  color: red;
  font-size: 30px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}
.beforeCode .beforeHead {
  margin-bottom: 5px;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 5px;
}

/* 头部题目状态 */
.beforeHead .isPass {
  border-radius: 3px;
  font-size: 14px;
  padding: 0 8px;
}
/* 通过 */
.beforeHead .isPass.pass{
  color: var(--pass);
  border: 1px solid var(--pass);
  background-color: var(--pass-bg-color);
}
/* 再接再厉 */
.beforeHead .isPass.coming{
  color: var(--coming);
  border: 1px solid var(--coming);
  background-color: var(--coming-bg-color);
}
/* 编译错误 */
.beforeHead .isPass.bad{
  color: var(--main-delete);
  border: 1px solid var(--main-delete);
  background-color: var(--main-fail-status);
}

.beforeHead .header {
  color: var(--text-body);
  font-size: 18px;
  font-weight: 700;
}
.beforeHead .header span {
  color: var(--primary);
  font-size: 20px;
  font-weight: 800;
}

/* 代码分析建议区域 */
.resultArea .codeComment {
  width: 100%;
  margin-top: 20px;
  padding: 10px 20px;
  border-left: 3px solid var(--primary);
  background-color: var(--primary-fade);
  border-radius: 10px;
}
.codeComment .st-top,
.codeComment .hd-top {
  /* border: 1px solid black; */
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.codeComment .st-top > div,
.codeComment .hd-top > div {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-body);
}
.codeComment .situation {
  margin-bottom: 10px;
}
.situation span {
  font-size: 20px;
  font-weight: 700;
  color: var(--primary);
}
.codeComment .st-content,
.codeComment .hd-content {
  margin-left: 5px;
}
.codeComment .encouragement {
  margin-top: 10px;
}
.encouragement .hd-content {
  color: var(--primary);
  font-weight: 600;
  font-size: 16px; 
}

/* 可视化按钮 */
.resultArea .visualization {
  margin: 20px 0;
}
.visualization .vsBtn {
  padding: 0 120px;
  margin-bottom: 20px;
}


/* 排行榜卡片优化 */
.resultArea .rank {
  padding: 0 5px;
}
.rank-card {
  width: 100%;
  height: 100%;
  min-width: 217px;
  min-height: 500px;
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  border-top: 4px solid var(--primary); /* 使用主题色 */
  background-color: var(--bg-card);
  display: flex;
  flex-direction: column;
}

.rank-card-title {
  padding: 10px 15px;
  font-size: 22px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 10px;
}

.rank-card-title .tip { 
  position: absolute;
  bottom: 5px;
  right: 40px;
  font-size: 14px;
  color: var(--text-gray);
}

.rank-card-content {
  flex: 1;
  padding: 10px 0;
  overflow-y: auto; /* 如果列表很长，允许滚动 */
  /* margin-bottom: 60px; */
}

.rank-item {
  min-width: 24px;
  min-height: 24px;
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 10px 30px;
  transition: background-color 0.3s;
  border-bottom: 1px solid var(--border-color);
}

.rank-item:hover {
  background-color: var(--bg-hover, #f5f7fa);
}
.rank-item.myRank { 
  background-color: var(--primary-light);
}
.rank-item.myRank:hover { 
  background-color: var(--primary-fade);
}
.rank-item .rank-medal { 
  padding: 0px;
  /* background-color: pink; */
}
/* 排行榜空 */
.rankNull {
  margin-top: 160px;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
}
.rankNull img {
  width: 150px;
}
.rankNull .text {
  font-size: 14px;
  color: var(--text-gray);
}

/* 排名序号样式 */
.rank-index {
  width: 20px;
  height: 20px;
  line-height: 20px;
  text-align: center;
  font-weight: bold;
  font-size: 14px;
  color: var(--primary-act);
  background-color: var(--primary-fade);
  margin-left: 5px;
  margin-right: 5px;
  border-radius: 4px;
  /* 防止压缩 */
  flex-shrink: 0; 
}


/* 用户信息区域 */
.rank-info {
  flex: 1;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 40px;
}

.rank-info .user-avatar {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 20px;
}

.user-name {
  font-size: 22px;
  color: var(--text-gray);
  font-weight: 700;
}

.user-score {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-body);
  
}
.user-score span {
  font-size: 22px;
  font-weight: 700;
  color: var(--main-delete);
}

.comment .backTop,
.comment .backRankTop {
  margin: 10px 0;
}
.backTop div,
.backRankTop div {
  text-align: center;
  width: 130px;
  height: 30px;
  color: var(--primary);
  border: 1px solid var(--primary);
  background-color: var(--primary-fade);
  border-radius: 10px;
  padding: 2px 5px;
  margin: 0 auto;
  transition: all 0.3s;
}
.backTop div:hover {
  cursor: pointer;
  color: var(--bg-card);
  background-color: var(--primary);
}

.backRankTop div {
  width: 110px;
  height: 25px;
  font-size: 12px;
  color: var(--coming);
  border: 1px solid var(--coming);
  background-color: var(--coming-bg-color);
}
.backRankTop div:hover {
  cursor: pointer;
  color: var(--bg-card);
  background-color: var(--coming);
}

/* 排行榜-AI分析比较 */
.rank-item .compareCode {
  border: 1px solid var(--primary);
  color: var(--primary);
  background-color: rgba(45, 125, 219, 0.08);
  padding: 1px 5px;
  border-radius: 10px;
  transition: all 0.3s;
  margin-right: 8px;
}
.compareCode:hover { 
  cursor: pointer;
  color: var(--bg-card);
  background-color: var(--primary);
}

/* 排行榜-查看详情 */
.rank-item .lookUserCode {
  border: 1px solid var(--pass);
  color: var(--pass);
  background-color: var(--pass-bg-color);
  padding: 1px 5px;
  border-radius: 10px;
  transition: all 0.3s;
}
.lookUserCode:hover { 
  cursor: pointer;
  color: var(--bg-card);
  background-color: var(--pass);
}


/* 查看他人代码对话框 */
.showArea .lookUserCodeDialog { 
  padding: 10px;
  z-index: 2;
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  background-color: var(--bgc-transparent); 
  backdrop-filter: blur(1px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.3s ease;
  display: flex;
  justify-content: center;
  align-items: center;

}
.lookUserCodeDialog .card { 
  padding: 20px;
  width: 900px;
  /* height: 600px; */
  max-height: 100%;
  background-color: var(--bg-card);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  border-top: 3px solid var(--primary);
  box-shadow: var(--shadow-normal);

  overflow: hidden;

}
/* 头部 */
.card .lookHead {
  padding: 5px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  border-bottom: 1px solid var(--border-color);
}
.card .lookHead .leftArea { 
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 20px;
}
.leftArea .lookInfo { 
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.leftArea .topA {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 20px;
}
.leftArea .bottomA {
  font-size: 12px;
  color: var(--text-gray);
}
.lookHead .rightArea {
  padding: 1px 10px;
  font-size: 16px;
  color: var(--main-delete);
  border: 1px solid var(--main-delete);
  background-color: var(--main-fail-status);
  border-radius: 10px;
  transition: all 0.3s;
}
.lookHead .rightArea:hover {
  cursor: pointer;
  background-color: var(--main-fail-status-hover);
}
.card .lookCode {
  border-radius: 10px;
  margin-top: 10px;
  /* border: 1px solid red; */
  max-height: 100%
}
.lookCode .lookCodeScroll {
  padding: 0 10px;
}



/* =========================算法可视化区域==================== */
.visualization .vsArea {
  background-color: var(--aside-bg-color);
  border: 1px solid var(--text-gray);
  border-radius: 10px;
  width: 100%;
  height: 520px;
  overflow: hidden;
}

.vsArea.openLogShow {
  height: 660px;
}

.vsArea {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
  gap: 10px;
}
.vsArea .loadingText {
  color: var(--primary-fade);
}

.vsArea .vsContent {
  /* border: 1px solid red; */
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: flex-start;
  padding: 10px;
}
.vsContent .vs-header { 
  margin-bottom: 10px;
  padding: 5px 10px;
  width: 100%;
  height: 40px;
  /* border: 1px solid black; */
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.vs-header h3 {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}
.vs-header h3 span {
  font-size: 20px;
  font-weight: 700;
  color: var(--primary-fade);
}
.vs-header .vsType { 
  font-size: 14px;
  color: var(--primary-fade);
}
.vsContent .vs-header-btns {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
}
.vsContent .close {
  font-size: 14px; 
  color: var(--primary-fade);
  border: 1px solid var(--primary-fade);
  padding: 1px 5px;
  border-radius: 10px;
  transition: all 0.3s;
}
.vsContent .log.openLog {
  color: var(--pass);
  border: 1px solid var(--pass);
}
.vsContent .log.closeLog {
  color: var(--coming);
  border: 1px solid var(--coming);
}

.vsContent .close:hover {
  cursor: pointer;
  color: var(--main-delete);
  border-color: var(--main-delete);
}
.vsContent .log.openLog:hover {
  color: var(--bg-card);
  background-color: var(--pass);
  border-color: var(--pass);
}
.vsContent .log.closeLog:hover {
  color: var(--bg-card);
  background-color: var(--coming);
  border-color: var(--coming);
}

/* =========================可视化面板 · 暗色主题==================== */
.algorithm-visualization-section {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.viz-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: var(--grad-primary);
  color: #fff;
}

.viz-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.viz-header-left > .icon {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
}

.viz-header-left h3 {
  margin: 0;
  font-size: 22px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}

.viz-header-actions {
  display: flex;
  align-items: center;
  gap: 35px;
}

.viz-type {
  font-size: 12px;
  opacity: 0.9;
}

.viz-header .close.log {
  cursor: pointer;
  font-size: 12px;
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-sm);
}

.viz-header .icon-btn {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
}

.viz-body {
  padding: 15px;
  background: #1e1e1e;
  color: var(--text-body);
}

.viz-status-wrap {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;
}

.viz-status {
  color: var(--text-gray);
  font-size: 13px;
}

.viz-content-wrap {
  display: flex;
  gap: 5px;
  min-height: 280px;
}

#vizCodePanel {
  display: none;
  width: 42%;
  min-width: 280px;
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: var(--radius-md);
  overflow: hidden;
  flex-shrink: 0;
}

.viz-code-panel-header {
  padding: 6px 12px;
  border-bottom: 1px solid #333;
  font-size: 12px;
  font-weight: 600;
  color: #8b949e;
  background: #2d2d2d;
}

#vizCodeContent {
  overflow-y: auto;
  max-height: 280px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 10px;
  line-height: 1.6;
  padding: 0;
}

#vizCanvas {
  flex: 1;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-page);
  min-width: 300px;
}

#vizControls {
  display: none;
  margin-top: 10px;
  padding: 10px 15px;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.viz-btn-play {
  padding: 6px 16px;
  background: var(--pass);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.viz-btn-play:hover {
  background: var(--pass-hover);
}

.viz-btn-pause {
  padding: 6px 16px;
  background: var(--coming);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.viz-btn-pause:hover {
  background: var(--coming-hover);
}

.viz-btn-reset {
  padding: 6px 16px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}
.viz-btn-reset:hover {
  background: var(--primary-hv);
}

.viz-select {
  padding: 4px 8px;
  background: var(--bg-card);
  color: var(--text-body);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
}

.speed-slider-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 180px;
}

.speed-label {
  color: var(--text-gray);
  font-size: 12px;
  white-space: nowrap;
}

.speed-slider {
  flex: 1;
  accent-color: var(--primary);
}

.speed-value {
  color: var(--text-gray);
  font-size: 12px;
  min-width: 50px;
}

.frame-info {
  color: var(--text-gray);
  font-size: 12px;
}

.viz-log {
  margin-top: 10px;
  max-height: 150px;
  overflow-y: auto;
  font-family: 'Consolas', monospace;
  font-size: 13px;
  color: #E2E8F0;
}

.log-entry {
  padding: 3px 8px;
  border-radius: 4px;
  margin: 2px 0;
  font-size: 13px;
}

.log-ok {
  background: #0a3d0a;
  color: #00ff88;
}

.log-err {
  background: #3d0a0a;
  color: #ff6666;
}

.log-info {
  background: #0a1a3d;
  color: #88aaff;
}

/* ========== AI分析比较弹窗样式 ========== */
.compare-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(6px);
}

.compare-modal {
  width: 90%;
  max-width: 1200px;
  height: 90vh;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.compare-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: linear-gradient(135deg, var(--primary) 0%, #2d7ddb 50%, #1a5bb8 100%);
  color: #fff;
  flex-shrink: 0;
}

.compare-title {
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
}

.compare-close {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  font-size: 20px;
}

.compare-close:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: rotate(90deg);
}

.compare-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 320px 40px;
  gap: 16px;
}

.loading-dots {
  display: flex;
  gap: 8px;
}

.loading-dot {
  width: 8px;
  height: 8px;
  background: var(--primary);
  border-radius: 50%;
  animation: loadingDot 1s ease-in-out infinite;
}

.loading-dot:nth-child(1) { animation-delay: 0s; }
.loading-dot:nth-child(2) { animation-delay: 0.2s; }
.loading-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes loadingDot {
  0%, 100% { transform: translateY(0); opacity: 0.5; }
  50% { transform: translateY(-12px); opacity: 1; }
}

.compare-loading span {
  font-size: 16px;
  color: var(--text-gray);
  font-weight: 500;
}

.compare-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.compare-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 分数对比 */
.compare-score-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.compare-score-title,
.compare-code-title,
.compare-chart-title,
.compare-complexity-title,
.compare-report-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 20px;
  padding-left: 12px;
  border-left: 4px solid var(--primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-comparison {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 60px;
  width: 100%;
}

.score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px;
  border-radius: 12px;
  background: var(--bgc-light);
  transition: all 0.3s ease;
  flex: 1;
  max-width: 300px;
}

.score-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.score-a {
  border: 2px solid rgba(45, 125, 219, 0.2);
}

.score-b {
  border: 2px solid rgba(78, 191, 109, 0.2);
}

.score-avatar {
  border-radius: 50%;
  padding: 3px;
}

.score-a .score-avatar {
  background: linear-gradient(135deg, rgba(45, 125, 219, 0.1), rgba(45, 125, 219, 0.3));
}

.score-b .score-avatar {
  background: linear-gradient(135deg, rgba(78, 191, 109, 0.1), rgba(78, 191, 109, 0.3));
}

.score-name {
  font-size: 15px;
  color: var(--text-title);
  font-weight: 600;
}

.score-value {
  font-size: 42px;
  font-weight: 700;
  color: var(--primary);
  text-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
}

.score-b .score-value {
  color: var(--pass);
  text-shadow: 0 2px 8px rgba(78, 191, 109, 0.3);
}

.score-verdict {
  font-size: 13px;
  padding: 6px 16px;
  border-radius: 20px;
  font-weight: 500;
  margin-top: 4px;
}

.score-verdict.accepted {
  background: var(--pass-bg-color);
  color: var(--pass);
}

.score-verdict.wronganswer {
  background: var(--coming-bg-color);
  color: var(--coming);
}

.score-verdict.compilationerror {
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.score-vs {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-gray);
  padding: 20px;
  background: #fff;
  border-radius: 50%;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

/* 代码对比 */
.compare-code-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.code-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.code-panel {
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #333;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #2d2d2d;
  border-bottom: 1px solid #333;
  font-size: 13px;
  font-weight: 500;
  color: #ccc;
}

.code-header-a {
  background: linear-gradient(90deg, rgba(45, 125, 219, 0.2), transparent);
}

.code-header-b {
  background: linear-gradient(90deg, rgba(78, 191, 109, 0.2), transparent);
}

.code-lang {
  font-size: 11px;
  color: #999;
  background: #3d3d3d;
  padding: 2px 10px;
  border-radius: 4px;
}

.code-content {
  padding: 14px;
  font-family: 'Consolas', 'Monaco', 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #e4e4e4;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.code-content::-webkit-scrollbar {
  width: 6px;
}

.code-content::-webkit-scrollbar-track {
  background: #2d2d2d;
}

.code-content::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 3px;
}

.code-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 图表对比 */
.compare-chart-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.chart-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.chart-panel {
  background: var(--bgc-light);
  border-radius: 10px;
  padding: 20px;
  border: 1px solid var(--border-color);
}

.chart-header {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-container {
  height: 280px;
}

/* 复杂度对比 */
.compare-complexity-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.complexity-grid {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 40px;
}

.complexity-card {
  flex: 1;
  max-width: 300px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
}

.complexity-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.12);
}

.card-a {
  border-left: 4px solid var(--primary);
}

.card-b {
  border-left: 4px solid var(--pass);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  background: linear-gradient(135deg, rgba(45, 125, 219, 0.05), transparent);
}

.card-b .card-header {
  background: linear-gradient(135deg, rgba(78, 191, 109, 0.05), transparent);
}

.card-avatar {
  border-radius: 50%;
}

.card-a .card-avatar {
  box-shadow: 0 0 0 3px rgba(45, 125, 219, 0.15);
}

.card-b .card-avatar {
  box-shadow: 0 0 0 3px rgba(78, 191, 109, 0.15);
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}

.card-body {
  padding: 18px;
}

.complexity-item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: var(--bgc-light);
  border-radius: 8px;
  margin-bottom: 10px;
}

.complexity-item-row:last-child {
  margin-bottom: 0;
}

.complexity-type {
  font-size: 13px;
  color: var(--text-gray);
  font-weight: 500;
}

.complexity-value {
  font-size: 15px;
  font-family: 'Consolas', monospace;
  font-weight: 700;
  color: var(--primary);
}

.card-b .complexity-value {
  color: var(--pass);
}

.complexity-vs {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, var(--primary), #2d7ddb);
  border-radius: 50%;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.4);
  flex-shrink: 0;
}

/* AI分析报告 */
.compare-report-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.report-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.report-item {
  background: linear-gradient(145deg, var(--bgc-light), #fff);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.report-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--primary);
  border-radius: 12px 0 0 12px;
}

.report-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(45, 125, 219, 0.12);
  border-color: var(--primary-light);
}

.report-item:nth-child(1)::before { background: linear-gradient(180deg, #667eea, #764ba2); }
.report-item:nth-child(2)::before { background: linear-gradient(180deg, #f093fb, #f5576c); }
.report-item:nth-child(3)::before { background: linear-gradient(180deg, #4facfe, #00f2fe); }
.report-item:nth-child(4)::before { background: linear-gradient(180deg, #43e97b, #38f9d7); }
.report-item:nth-child(5)::before { background: linear-gradient(180deg, #fa709a, #fee140); }
.report-item:nth-child(6)::before { background: linear-gradient(180deg, #a8edea, #fed6e3); }

.report-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 8px;
}

.report-label::before {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
}

.report-item:nth-child(1) .report-label::before { background: #667eea; }
.report-item:nth-child(2) .report-label::before { background: #f5576c; }
.report-item:nth-child(3) .report-label::before { background: #4facfe; }
.report-item:nth-child(4) .report-label::before { background: #43e97b; }
.report-item:nth-child(5) .report-label::before { background: #fa709a; }
.report-item:nth-child(6) .report-label::before { background: #a8edea; }

.report-text {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.7;
  padding-left: 8px;
}

.report-text :deep(p) {
  margin-bottom: 10px;
}

.report-text :deep(p:last-child) {
  margin-bottom: 0;
}

.report-text :deep(strong),
.report-text :deep(b) {
  font-weight: 600;
  color: var(--text-title);
}

.report-text :deep(em),
.report-text :deep(i) {
  font-style: italic;
}

.report-text :deep(code) {
  background: rgba(45, 125, 219, 0.08);
  color: var(--primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
}

.report-text :deep(a) {
  color: var(--primary);
  text-decoration: none;
}

.report-text :deep(a:hover) {
  text-decoration: underline;
}

.report-text :deep(h1),
.report-text :deep(h2),
.report-text :deep(h3),
.report-text :deep(h4),
.report-text :deep(h5),
.report-text :deep(h6) {
  font-weight: 600;
  margin-top: 16px;
  margin-bottom: 8px;
  color: var(--text-title);
}

.report-text :deep(h1) { font-size: 18px; }
.report-text :deep(h2) { font-size: 16px; }
.report-text :deep(h3) { font-size: 15px; }
.report-text :deep(h4),
.report-text :deep(h5),
.report-text :deep(h6) { font-size: 14px; }

.report-text :deep(ul) {
  padding-left: 24px;
  margin-bottom: 10px;
}

.report-text :deep(li) {
  margin-bottom: 4px;
  list-style-type: disc;
}

.report-text :deep(blockquote) {
  border-left: 4px solid var(--primary);
  padding-left: 12px;
  margin: 12px 0;
  color: var(--text-gray);
  background: rgba(45, 125, 219, 0.04);
  padding: 8px 12px;
  border-radius: 0 4px 4px 0;
}

.report-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 16px 0;
}


/* ===== 冲突弹窗 ===== */
.conflict-dialog-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

.conflict-dialog {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  max-width: 480px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
  animation: slideUp 0.3s ease;
}

.conflict-dialog-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.conflict-dialog-header span {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.conflict-dialog-content {
  font-size: 15px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 24px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.conflict-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.conflict-btn {
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.conflict-btn-reject {
  background: #f5f5f5;
  color: #666;
}

.conflict-btn-reject:hover {
  background: #e8e8e8;
  color: #333;
}

.conflict-btn-accept {
  background: #2D7DDB;
  color: #fff;
}

.conflict-btn-accept:hover {
  background: #1a6cd9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}

/* ============ 夜间模式适配 ============ */

/* 弹窗主体 */
.dark .compare-modal {
  background: var(--bg-card);
}

.dark .compare-body {
  background: var(--bg-card);
}

/* 分数对比区域 */
.dark .compare-score-section {
  background: var(--bg-card);
  box-shadow: var(--shadow-normal);
}

.dark .score-item {
  background: var(--bgc-light);
}

.dark .score-item:hover {
  box-shadow: var(--shadow-normal);
}

.dark .score-vs {
  background: var(--bg-hover);
  box-shadow: var(--shadow-normal);
}

/* 代码对比区域 */
.dark .compare-code-section {
  background: var(--bg-card);
  box-shadow: var(--shadow-normal);
}

/* 图表对比区域 */
.dark .compare-chart-section {
  background: var(--bg-card);
  box-shadow: var(--shadow-normal);
}

.dark .chart-panel {
  background: var(--bgc-light);
}

/* 复杂度对比区域 */
.dark .compare-complexity-section {
  background: var(--bg-card);
  box-shadow: var(--shadow-normal);
}

.dark .complexity-card {
  background: var(--bg-card);
  box-shadow: var(--shadow-normal);
}

.dark .complexity-card:hover {
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);
}

.dark .card-header {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), transparent);
}

.dark .card-b .card-header {
  background: linear-gradient(135deg, rgba(74, 222, 128, 0.1), transparent);
}

.dark .card-a .card-avatar {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.dark .card-b .card-avatar {
  box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.2);
}

.dark .complexity-item-row {
  background: var(--bgc-light);
}

/* AI分析报告区域 */
.dark .compare-report-section {
  background: var(--bg-card);
  box-shadow: var(--shadow-normal);
}

.dark .report-item {
  background: linear-gradient(145deg, var(--bgc-light), var(--bg-card));
}

.dark .report-item:hover {
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
}

.dark .report-text :deep(code) {
  background: rgba(59, 130, 246, 0.15);
}

</style>
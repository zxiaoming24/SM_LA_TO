<!-- 移动端编程练习组件 -->
<script setup>
import { ref, onMounted, nextTick, computed, reactive, onUnmounted, watch } from 'vue'
import { showToast, showConfirmDialog, showLoadingToast, showSuccessToast, showFailToast, closeToast } from 'vant'
import * as echarts from 'echarts'
import { isSkip, removeSkip } from '@/utils/skip.js'//跳转
import { useRouter } from 'vue-router'
import { createCodeKeydownHandler } from '../../main/resourceNav/codeInput.js' //编码快捷键
import emitter from '@/utils/emitter'
import { getCodeListByUserId, submitCodeApi, getCodeProgressApi,
  getValueApi, deleteCodeByIdApi, submitExamineApi, getExamineProgressApi,
  getExamineListApi, deleteExamineByIdApi,
  getExamineValueApi, getCodeRankListApi, codeVisualApi, codeCompareApi,
  reportTwinApi, checkCodeApi } from '@/api/mainApi/resourceCode.js'
import { reviewCountAddOneApi } from '@/api/mainApi/layout.js'//复习次数加一
import { getUserInfoApi } from '@/api/mainApi/index.js'//根据用户id序列查询用户信息序列
import { conflictApi } from '@/api/mainApi/aiAnswer.js'//冲突提交
import { initVizModule } from '../../main/resourceNav/codeVisualization.js'//算法可视化模块

const router = useRouter()
let loginUser = null
const userId = ref(null)// 用户ID
const skipInfo = ref()//跳转信息

onMounted(async () => {
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
  if (isSkip(4) === false) {
    console.log('没有编程题需要提前打开')
  } else {
    skipInfo.value = isSkip(4)
    console.log('跳转信息:', skipInfo.value)
    try {
      await getValue(skipInfo.value.resourceId)
      await getCodeHistoryList()
    } catch (e) {
      showFailToast('该编程题不存在，可能已经被删除了')
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
const btnDisvisible = ref(false)//按钮禁用是否开启
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
})

const allList = ref([])// 所有列表
const showList = ref([])// 外部显示列表
const isOpenList = ref(false)// 是否展开全部列表

const showConflictDialog = ref(false)//冲突弹窗是否开启
const conflictData = ref({
  taskId: null,
  rsType: 4,
  suggestionWarning: '',
  createTime: ''
})

// ===================题目内函数==================
const isShowLoading = ref(false)//是否显示加载中

// 收起/展开->示例/tips
const isEgShow = ref(false)//示例是否展示
const isTipsShow = ref(false)//tips是否展示
const logStatus = ref(true)//可视化日志是否展示

// 转换难度显示
const formatDifficulty = (difficulty) => {
  if (!difficulty) return ''
  const num = parseInt(difficulty)
  if (!isNaN(num)) {
    const map = { 1: '简单', 2: '中等', 3: '困难' }
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

  if (mode === 'format') {
    html = html.replace(/\\n/g, '\n')
    html = html.replace(/\\r/g, '\r')
  }

  html = html.replace(/&/g, '&amp;')
  html = html.replace(/</g, '&lt;')
  html = html.replace(/>/g, '&gt;')

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

  if (mode === 'format') {
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

  html = html.replace(/<p><ul>/g, '<ul>')
  html = html.replace(/<\/ul><\/p>/g, '</ul>')
  html = html.replace(/<p><li>/g, '<li>')
  html = html.replace(/<\/li><\/p>/g, '</li>')

  return html
}

const formatContent = (content) => {
  return markdownToHtml(content, 'format')
}

const btn = (option) => {
  if (option === 0) {
    isEgShow.value = !isEgShow.value
  } else if (option === 1) {
    isTipsShow.value = !isTipsShow.value
  } else if (option === 2) {
    logStatus.value = !logStatus.value
  }
}

// 提交代码分析
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
const codeTextareaRef = ref(null) // 代码编辑区引用
// 根据内容换行符更新行数
const updateLineCount = () => {
  const lines = submitContent.value.answer.split('\n').length
  lineCount.value = Math.max(15, lines)
}
// 监听代码内容变化（Enter / Tab / 自动补全等程序化修改都会更新行数）
watch(() => submitContent.value.answer, async (newVal) => {
  updateLineCount()
  await nextTick()
  // 换行（Enter）后滚动 textarea 到底部，使新行可见
  if (newVal && newVal.endsWith('\n') && codeTextareaRef.value) {
    codeTextareaRef.value.scrollTop = codeTextareaRef.value.scrollHeight
    syncLineNumbersScroll({ target: codeTextareaRef.value })
  }
}, { flush: 'post' })
// 同步行号区域的滚动
const syncLineNumbersScroll = (e) => {
  if (lineNumbersRef.value) {
    const scrollTop = e.target.scrollTop
    lineNumbersRef.value.style.transform = `translateY(${-scrollTop}px)`
  }
}
const resultLineNumbersRef = ref(null) // 结果页行号区域引用
const lookLineNumbersRef = ref(null) // 查看代码行号区域引用
// 同步结果页行号区域的滚动
const syncResultScroll = (e) => {
  if (resultLineNumbersRef.value) {
    resultLineNumbersRef.value.style.transform = `translateY(${-e.target.scrollTop}px)`
  }
}
// 同步查看代码行号区域的滚动
const syncLookScroll = (e) => {
  if (lookLineNumbersRef.value) {
    lookLineNumbersRef.value.style.transform = `translateY(${-e.target.scrollTop}px)`
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
  const kp = showCodeData.value?.knowledgePoints || []
  const knowledgePoints = Array.isArray(kp) ? kp.join(',') : kp
  const uid = userId.value
  if (!uid) return

  try {
    const [twinRes, lintRes] = await Promise.allSettled([
      reportTwinApi(uid, knowledgePoints, code),
      checkCodeApi({ code, language: submitContent.value.language?.toLowerCase() || 'python' })
    ])

    if (twinRes.status === 'fulfilled' && twinRes.value?.hints) {
      twinWarnings.value = twinRes.value.hints
        .filter(h => h.type === 'code_pattern' && h.severity === 'warning')
        .map(h => ({ line: h.line, tip: h.tip }))
    }

    if (lintRes.status === 'fulfilled' && lintRes.value?.errors) {
      twinErrors.value = lintRes.value.errors.map(e => ({ line: e.line, msg: e.msg }))
    }
  } catch (e) {
    console.error('孪生检查失败', e)
  }
}

watch(() => submitContent.value.answer, () => {
  onTwinCodeChange()
})

// 获取某行的孪生警告
const getTwinWarning = (line) => twinWarnings.value.find(w => w.line === line) || null
// 获取某行的语法错误
const getTwinError = (line) => twinErrors.value.find(e => e.line === line) || null

onUnmounted(() => {
  emitter.off('digitalTwinToggle')
  clearTimeout(twinCheckTimer)
})

// ==========================结果区===========================
// 退出代码评估栏
const isResultShow = ref(false)//是否显示结果页
const quitResult = () => {
  isResultShow.value = false
  document.body.style.overflow = ''
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
})

const compareVisible = ref(false)
const compareLoading = ref(false)
const compareData = ref(null)
const compareUserInfo = ref({})
const radarChartRef = ref(null)
const barChartRef = ref(null)

const resultCount = ref(15) // 初始行数
const updateResultCount = () => {
  const lines = beforeContent.value.answer.split('\n').length
  resultCount.value = Math.max(15, lines)
}

// 代码分析按钮的img
const imgShow = () => {
  const imgUrl = ref(`../../../assets/icon/${submitContent.value.language}.png`)
  try {
    return new URL(imgUrl.value, import.meta.url).href
  } catch (e) {
    console.error('图片加载失败', e)
    return ''
  }
}

// 本题历史提交记录
const showCHList = ref([])

const rankList = ref([])//排行榜

const isLookCode = ref(false)//查看代码对话框是否打开
const lookUserMsg = ref({//展示的信息
  userId: null,
  username: '',
  createTime: '',
  score: null,
  avatar: '',
  codePreview: ''
})

// 获取查看用户信息
const getLookUserMsg = (userId, index) => {
  for (let i = 0; i < rankList.value.length; i++) {
    const item = rankList.value[i];
    if (item.userId == userId && i == index) {
      lookUserMsg.value = item
      updatelookCount()
      isLookCode.value = true
      document.body.style.overflow = 'hidden'
      return
    }
  }
}

//关闭查看代码对话框
const closeLookCode = () => {
  isLookCode.value = false
  if (!compareVisible.value && !isResultShow.value) {
    document.body.style.overflow = ''
  }
  lookUserMsg.value = {
    userId: null,
    username: '',
    createTime: '',
    score: null,
    avatar: '',
    codePreview: ''
  }
}

const lookCount = ref(20)
const updatelookCount = () => {
  const lines = lookUserMsg.value.codePreview.split('\n').length
  lookCount.value = Math.max(20, lines)
}

// ====================================外部函数===========================================
// 退出预览
const quitShowCode = async () => {
  await getList()
  isShow.value = false
  isEgShow.value = false
  isTipsShow.value = false
  submitContent.value = {
    userId: null,
    practiceId: null,
    answer: '',
    language: 'C',
  }
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
  skipInfo.value = null
  quitResult()
}

// 返回上一页（列表或路由返回）
const goBack = () => {
  if (isResultShow.value) {
    quitResult()
  } else if (isShow.value) {
    quitShowCode()
  } else {
    router.back()
  }
}

//检查列表
const checkList = async () => {
  btnDisvisible.value = true
  console.log('开始检查列表')
  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i];
    if (item.status == 1 || item.status == null) {
      let nowNum = 0
      let maxNum = 40

      try {
        await getProgress(item.id)
        if (taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null) {
          if (!showConflictDialog.value) {
            conflictData.value = {
              createTime: taskProgress.value.createTime,
              suggestionWarning: taskProgress.value.suggestionWarning,
              rsType: 4,
              taskId: taskProgress.value?.id
            }
            showConflictDialog.value = true
            document.body.style.overflow = 'hidden'
          }
        }
        if (taskProgress.value == {}) {
          showFailToast('获取生成进度失败')
        } else if (taskProgress.value.status == null) {
          await deleteItem(item.id, false)
          showFailToast('有生成项请求生成失败，直接删除')
          await getList()
          taskProgress.value = {}
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue
      }

      while (taskProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          await getProgress(item.id)
          if (taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null) {
            if (!showConflictDialog.value) {
              conflictData.value = {
                createTime: taskProgress.value.createTime,
                suggestionWarning: taskProgress.value.suggestionWarning,
                rsType: 4,
                taskId: taskProgress.value?.id
              }
              showConflictDialog.value = true
              document.body.style.overflow = 'hidden'
            }
          }
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      if (taskProgress.value.status == 2) {
        await getList()
        taskProgress.value = {}
      } else {
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
    showToast(option ? '已接受，处理中...' : '已拒绝，处理中...')
    if (response.code === 1) {
      showSuccessToast('操作完成')
    } else {
      showFailToast(response.msg || '操作失败')
    }
  } catch (error) {
    console.error('冲突弹窗操作失败:', error)
    showFailToast('网络异常，操作失败')
  } finally {
    showConflictDialog.value = false
    document.body.style.overflow = ''
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
  if (!codeData.value.text || !codeData.value.text.trim()) {
    showToast('请输入主题/知识点')
    return
  }
  if (codeData.value.text.length > 30) {
    showToast('长度在 1 到 30 个字符')
    return
  }

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
    await createTask()
    if (task.value.status == 1 || task.value.status == null) {
      let nowNum = 0
      let maxNum = 40

      try {
        await getProgress(task.value.id)
        if (taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null) {
          if (!showConflictDialog.value) {
            conflictData.value = {
              createTime: taskProgress.value.createTime,
              suggestionWarning: taskProgress.value.suggestionWarning,
              rsType: 4,
              taskId: taskProgress.value?.id
            }
            showConflictDialog.value = true
            document.body.style.overflow = 'hidden'
          }
        }
        if (taskProgress.value == {}) {
          showFailToast('获取生成进度失败')
        } else if (taskProgress.value.status == null) {
          await deleteItem(task.value.id, false)
          showFailToast('有生成项请求生成失败，直接删除')
          await getList()
          task.value = {}
          taskProgress.value = {}
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
      }

      await getList()
      await getValue(task.value.id)

      while (taskProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          await getProgress(task.value.id)
          if (taskProgress.value?.suggestionWarning && taskProgress.value.suggestionWarning != 1 && taskProgress.value.suggestionWarning != null) {
            if (!showConflictDialog.value) {
              conflictData.value = {
                createTime: taskProgress.value.createTime,
                suggestionWarning: taskProgress.value.suggestionWarning,
                rsType: 4,
                taskId: taskProgress.value?.id
              }
              showConflictDialog.value = true
              document.body.style.overflow = 'hidden'
            }
          }
        } catch (e) {
          console.error('轮询进度失败', e)
        }
      }

      if (taskProgress.value.status == 2) {
        await getList()
        await getValue(task.value.id)
        task.value = {}
        taskProgress.value = {}
      } else {
        await getList()
        await getValue(task.value.id)
        task.value = {}
        taskProgress.value = {}
      }
    } else if (task.value.status == 2 || task.value.status == 3) {
      await getList()
      await getValue(task.value.id)
      task.value = {}
      taskProgress.value = {}
    }
    btnDisvisible.value = false
    codeData.value = { userId: null, text: '' }
  } finally {
    clearTimeout(gameInvitationTimer)
  }
}

// ===========================外部接口=========================
// 获取列表
const getList = async () => {
  try {
    const result = await getCodeListByUserId(userId.value)
    if (result.code) {
      allList.value = result.data || []
      showList.value = allList.value.slice(0, 20)
    } else {
      showFailToast('获取信息表失败')
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
    if (result.code) {
      if (result.code.data === null) {
        showFailToast('该题不存在')
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

      if (isShow.value == true && showCHList.value !== []) {
        await checkCodeExamine()
      } else {
        await new Promise(resolve => setTimeout(resolve, 10000))
      }

      while (isShow.value == true) {
        if (showCHList.value !== []) {
          await checkCodeExamine()
          break
        } else {
          await new Promise(resolve => setTimeout(resolve, 5000))
        }
      }
    } else if (result.code === 2) {
      showFailToast('未找到对应资源，可能已被删除')
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
}
// 根据id删除信息
const deleteItem = async (id, isTip = true) => {
  if (isTip == true) {
    try {
      await showConfirmDialog({ title: '提示', message: '是否删除该题目？' })
    } catch (e) {
      return
    }
  }
  try {
    const result = await deleteCodeByIdApi(id)
    if (result.code) {
      showSuccessToast('删除成功')
      await getList()
    } else {
      showFailToast('删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
    showFailToast('删除失败')
  }
}

// 创建生成任务
const createTask = async () => {
  try {
    const result = await submitCodeApi(codeData.value)
    if (result.code) {
      task.value = result.data
    } else {
      showFailToast('提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
  }
}

//查询任务状态
const getProgress = async (id) => {
  try {
    const result = await getCodeProgressApi(id)
    if (result.code) {
      taskProgress.value = result.data
    } else {
      showFailToast('查询进度失败')
    }
  } catch (e) {
    console.error('查询进度失败', e)
  }
}

// ======================内部接口========================

// 查询该题历史记录
const getCodeHistoryList = async (id = showCodeData.value.id) => {
  try {
    const result = await getExamineListApi(id, userId.value)
    if (result.code) {
      showCHList.value = result.data
      console.log(`获取 题目id：${id} 的历史记录列表成功`)
    } else {
      showFailToast('获取信息失败')
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
}

//根据题目id查询排行榜信息
const getCodeRankList = async (id) => {
  try {
    const result = await getCodeRankListApi(id)
    if (result.code) {
      rankList.value = result.data
    } else {
      showFailToast('获取信息失败')
    }
  } catch (e) {
    console.error('获取信息失败', e)
  }
}

// AI代码分析比较
const compareCode = async (item) => {
  if (!beforeContent.value.submissionId) {
    showToast('错题重练分析')
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
      showFailToast(response.msg || '分析失败')
      compareVisible.value = false
      document.body.style.overflow = ''
    }
  } catch (e) {
    showFailToast('分析失败：' + e.message)
    compareVisible.value = false
    document.body.style.overflow = ''
  } finally {
    compareLoading.value = false
  }
}

// 关闭比较弹窗
const closeCompare = () => {
  compareVisible.value = false
  if (!isLookCode.value && !isResultShow.value) {
    document.body.style.overflow = ''
  }
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
        tooltip: { trigger: 'item' },
        legend: { data: [userNameA, userNameB], bottom: 0, textStyle: { fontSize: 11 } },
        radar: {
          indicator: chartData.dimensions?.map(dim => ({ name: dim, max: 100 })) || [],
          center: ['50%', '48%'],
          radius: '52%',
          axisName: { fontSize: 10 }
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
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        legend: { data: [userNameA, userNameB], bottom: 0, textStyle: { fontSize: 11 } },
        grid: { left: '3%', right: '4%', bottom: '18%', top: '10%', containLabel: true },
        xAxis: { type: 'category', data: chartData.dimensions || [], axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', max: 100, axisLabel: { fontSize: 10 } },
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
    if (result.code) {
      showSuccessToast('获取成功')
      beforeContent.value = result.data
      isResultShow.value = true
      document.body.style.overflow = 'hidden'
      await getCodeRankList(showCodeData.value.id)
      updateResultCount()
    } else {
      showFailToast('获取失败')
    }
  } catch (e) {
    console.error('获取失败', e)
  }
}

// 删除某个历史记录项
const delCHItem = async (id, isTip = true) => {
  if (isTip == true) {
    try {
      await showConfirmDialog({ title: '提示', message: '是否删除该历史记录？' })
    } catch (e) {
      return
    }
  }
  try {
    const result = await deleteExamineByIdApi(id)
    if (result.code) {
      showSuccessToast('删除成功')
      await getCodeHistoryList();
    } else {
      showFailToast('删除失败')
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
      submitContent.value.recordId = skipInfo.value.recordId
    }
    const result = await submitExamineApi(submitContent.value)
    if (result.code) {
      codeTask.value = result.data
    } else {
      showFailToast('提交分析失败')
    }
  } catch (e) {
    console.error('提交失败', e)
  }
}
// 获取代码评估进度
const getCEProgress = async (id) => {
  try {
    const result = await getExamineProgressApi(id)
    if (result.code) {
      cTProgress.value = result.data

      console.log(skipInfo.value)
      // 判断是否有 question
      if (skipInfo.value.recordId && cTProgress.value?.question && cTProgress.value.score < 60 && cTProgress.value?.question.count !== 0) {
        console.log('存在 question 数据', cTProgress.value.question)
        showNotification(cTProgress.value.question)
      } else {
        console.log('无 question 数据')
      }

      // 错题重练后，通过
      if (skipInfo.value.recordId && cTProgress.value.score > 60) {
        showOkNtf()
      }
    } else {
      showFailToast('查询进度失败')
    }
  } catch (e) {
    console.error('查询进度失败', e)
  }
}

// ==============================内部函数=============================
// 错题重练通知（底部弹出）
const ntfVisible = ref(false)
const ntfType = ref('')// 'question' | 'ok'
const ntfData = ref({ newName: '', oldName: [], newItem: 0 })

const showNotification = (question) => {
  const { newItem = 0, name = {} } = question || {}
  const { newName = '', oldName = [] } = name
  ntfType.value = 'question'
  ntfData.value = { newName, oldName: [...new Set(oldName)], newItem }
  ntfVisible.value = true
  document.body.style.overflow = 'hidden'
}
const showOkNtf = () => {
  ntfType.value = 'ok'
  ntfData.value = { newName: '', oldName: [], newItem: 0 }
  ntfVisible.value = true
  document.body.style.overflow = 'hidden'
}
const closeNtf = () => {
  ntfVisible.value = false
  if (!compareVisible.value && !isLookCode.value && !isResultShow.value && !showConflictDialog.value) {
    document.body.style.overflow = ''
  }
}
// 通知按钮：查看编程资源列表
const ntfViewList = async () => {
  closeNtf()
  if (isShow.value == true) {
    await getList()
    quitShowCode()
  } else {
    showToast('已在查看编程资源列表')
  }
}
// 通知按钮：返回错题本
const ntfBackWrong = () => {
  closeNtf()
  router.push('/phone/wrongQuestions')
}

//打开评估页
const openCodeExamine = async (id) => {
  try {
    await getExamineMsg(id)
  } catch (e) {
    console.error('打开失败', e)
  }
}

const resultScrollbarRef = ref(null)// 评价结果区滚动容器
const rankScrollbarRef = ref(null)// 排行榜滚动容器

// 锁定结果区滚动（可视化播放期间禁止滚动）
let _lockedScrollTop = 0
const lockResultScroll = () => {
  const el = resultScrollbarRef.value
  if (el) {
    el.style.overflow = 'hidden'
    _lockedScrollTop = el.scrollTop
  }
  document.body.style.overflow = 'hidden'
}
// 解锁结果区滚动
const unlockResultScroll = () => {
  const el = resultScrollbarRef.value
  if (el) {
    el.style.overflow = 'auto'
  }
  // 恢复 body 滚动仅在结果页未关闭时
  if (isResultShow.value) {
    document.body.style.overflow = 'hidden'
  }
}
// 返回顶部函数
const scrollToTop = (element) => {
  if (element) {
    element.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

//检查待生成项
const checkCodeExamine = async () => {
  for (let i = 0; i < showCHList.value.length; i++) {
    const item = showCHList.value[i];
    if (item.status == 1 || item.status == null) {
      let nowNum = 0
      let maxNum = 40

      if (isShow.value == false) {
        console.log("本题评估截断")
        quitShowCode()
        return
      }

      try {
        await getCEProgress(item.id)
        if (cTProgress.value == {}) {
          showFailToast('获取生成进度失败')
        } else if (cTProgress.value.status == null) {
          await delCHItem(item.id, false)
          showFailToast('有生成项请求生成失败，直接删除')
          await getCodeHistoryList()
          cTProgress.value = {}
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue
      }

      while (isShow.value == true && cTProgress.value.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          await getCEProgress(item.id)
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      if (isShow.value == false) {
        console.log("本题评估截断")
        quitShowCode()
        return
      }

      if (cTProgress.value.status == 2) {
        await getCodeHistoryList()
        cTProgress.value = {}
      } else {
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
  showLoadingToast({ message: '提交分析中...', forbidClick: true, duration: 1500 })
  console.log('提交中')
  // 如果该题有sessionId，说明是复习任务，提交了代码复习次数加一
  if (
    showCodeData.value?.sessionId &&
    showCodeData.value.sessionId !== '' &&
    showCodeData.value.sessionId !== 'none' &&
    showCodeData.value.sessionId !== null
  ) {
    const res = await reviewCountAddOneApi(userId.value)
    if (res.code) {
      console.log('今日复习次数已增加')
      showSuccessToast('今日复习次数已增加')
    } else {
      console.log('后端错误，今日复习次数增加失败')
    }
  }
  await createCodeExamine()
  await getExamineMsg(codeTask.value.id)
  submitContent.value = { userId: null, practiceId: null, answer: '', language: 'C', recordId: null }
  lineCount.value = 15
  if (taskProgress.value.status == 1 || taskProgress.value.status == null) {
    let nowNum = 0
    let maxNum = 40

    if (isShow.value == false) {
      console.log("本题评估截断")
      quitShowCode()
      return
    }

    try {
      await getCEProgress(codeTask.value.id)
      if (cTProgress.value == {}) {
        showFailToast('获取生成进度失败')
      } else if (cTProgress.value.status == null) {
        await delCHItem(codeTask.value.id, false)
        showFailToast('有生成项请求生成失败，直接删除')
        await getCodeHistoryList()
        codeTask.value = {}
        cTProgress.value = {}
      }
    } catch (e) {
      console.error('首次查询进度失败', e)
    }

    if (isShow.value == false) {
      console.log("本题评估截断")
      quitShowCode()
      return
    }

    await getCodeHistoryList()
    await getCEProgress(codeTask.value.id)

    while (isShow.value == true && cTProgress.value.status == 1 && nowNum < maxNum) {
      nowNum++
      await new Promise(resolve => setTimeout(resolve, 10000))
      try {
        await getCEProgress(codeTask.value.id)
      } catch (e) {
        console.error('轮询进度失败', e)
      }
    }

    if (isShow.value == false) {
      console.log("本题评估截断")
      quitShowCode()
      return
    }

    if (cTProgress.value.status == 2) {
      await getCodeHistoryList()
      await getExamineMsg(codeTask.value.id)
      codeTask.value = {}
      cTProgress.value = {}
    } else {
      await getCodeHistoryList()
      await getExamineMsg(codeTask.value.id)
      codeTask.value = {}
      cTProgress.value = {}
    }
  } else if (cTProgress.value.status == 2 || cTProgress.value.status == 3) {
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

// 初始化可视化模块（懒加载，确保 DOM 就绪）
const ensureVizModule = () => {
  if (vizContainerRef.value) {
    const callbacks = { onPlay: lockResultScroll, onComplete: unlockResultScroll }
    if (!vizModule.value) {
      vizModule.value = initVizModule(vizContainerRef.value, callbacks)
    } else {
      const currentContainer = vizModule.value.getContainer()
      if (currentContainer !== vizContainerRef.value) {
        vizModule.value.setContainer(vizContainerRef.value)
      }
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

  showLoadingToast({ message: '正在转换代码并生成可视化，请稍候...', forbidClick: true, duration: 0 })

  const logEl = vizContainerRef.value?.querySelector('#vizLog')
  if (logEl) logEl.innerHTML = ''

  mod.logMsg('开始请求转换接口', 'info')

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

    mod.logMsg(`接口转换成功！检测到算法类型：${detectedType.value}`, 'ok')

    const result = await mod.start(apiData)
    if (!result.success) {
      throw new Error(result.error || '可视化启动失败')
    }
    closeToast()
    showSuccessToast('可视化加载完成，点击开始播放')
  } catch (err) {
    closeToast()
    mod.logMsg(`失败：${err.message}`, 'err')
    showFailToast(`转换失败：${err.message}`)
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
  <div class="phone-code">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="goBack">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">编程练习</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div v-if="!isShow" class="code-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">编程练习 智能生成</h2>
        <p class="page-desc">输入学习主题，一键生成编程练习题</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="codeData.text"
          placeholder="例如：python基础"
          maxlength="30"
          show-word-limit
          clearable
          class="code-input"
          @keydown.enter="submit"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="生成中..."
          @click="submit"
          class="submit-btn"
        >
          立即生成编程题
        </van-button>
      </div>

      <!-- 列表 -->
      <div class="list-section">
        <div v-if="allList.length > 0" class="list-wrap">
          <div
            v-for="item in (isOpenList ? allList : showList)"
            :key="item.id"
            class="list-item"
            :class="{ 'item-loading': item.status == 1 || item.status == null, 'item-fail': item.status == 3 }"
            @click="getValue(item.id); getCodeHistoryList(item.id)"
          >
            <div class="item-info">
              <div class="item-name">{{ item.text }}</div>
              <div class="item-time">{{ item.createTime }}</div>
            </div>
            <div class="item-actions">
              <van-icon v-if="item.status == 1 || item.status == null" name="loading" class="loading-icon" />
              <span v-if="item.status == 1 || item.status == null" class="status-text">生成中</span>
              <van-icon v-if="item.status == 3" name="warning-o" class="fail-icon" />
              <span v-if="item.status == 3" class="fail-status-text">生成失败</span>
              <van-icon
                v-if="item.status == 2 || item.status == 3"
                name="delete-o"
                class="delete-icon"
                @click.stop="deleteItem(item.id)"
              />
            </div>
          </div>
          <div v-if="allList.length > 20" class="expand-btn" @click="isOpenList = !isOpenList">
            {{ isOpenList ? '收起' : '查看更多' }}
          </div>
        </div>
        <div v-else class="empty-state">
          <van-empty description="暂无生成内容" />
        </div>
      </div>
    </div>

    <!-- 详情页（题目预览 + 代码编写 + 历史） -->
    <div v-if="isShow" class="code-detail-page">
      <div class="detail-nav">
        <div class="nav-side" @click="quitShowCode">
          <van-icon name="arrow-left" size="20" />
        </div>
        <div class="nav-title">{{ showCodeData.text || '编程练习' }}</div>
        <div class="nav-side" @click="quitShowCode">
          <van-icon name="cross" size="20" />
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="isShowLoading" class="status-page">
        <van-loading type="spinner" color="var(--primary)" size="48" />
        <p class="status-text">加载中...</p>
      </div>

      <!-- 生成中 -->
      <div v-else-if="showCodeData.status === 1" class="status-page">
        <van-loading type="spinner" color="var(--primary)" size="56" />
        <p class="status-text">正在生成中，请稍候...</p>
      </div>

      <!-- 生成失败 -->
      <div v-else-if="showCodeData.status === 3" class="status-page">
        <van-icon name="warning-o" size="64" color="#F56C6C" />
        <p class="status-text fail-text">生成失败</p>
      </div>

      <!-- 生成成功 - 题目内容 -->
      <div v-else-if="showCodeData.status === 2" class="detail-content">
        <!-- 创建信息 -->
        <div class="create-info">
          <div class="create-text">{{ showCodeData.text }}</div>
          <div class="create-time">{{ showCodeData.createTime }}</div>
        </div>

        <!-- 题目 -->
        <div class="code-title-box">
          <div class="code-level">{{ formatDifficulty(showCodeData.difficulty) }}</div>
          <div class="code-title">{{ showCodeData.title }}</div>
        </div>

        <!-- 内容 -->
        <div class="code-content">
          <div class="code-desc" v-html="formatContent(showCodeData.description)"></div>
          <div class="code-input-format" v-if="showCodeData.inputFormat !== '无'" v-html="formatContent(showCodeData.inputFormat)"></div>
          <div class="code-output-format" v-if="showCodeData.outputFormat !== '无'" v-html="formatContent(showCodeData.outputFormat)"></div>

          <!-- 知识点标签 -->
          <div class="code-tag" v-if="showCodeData.knowledgePoints && showCodeData.knowledgePoints.length > 0">
            <div class="tag-label">本题知识点标签：</div>
            <div class="tag-list">
              <span class="tag" v-for="(item, idx) in showCodeData.knowledgePoints" :key="idx">{{ item }}</span>
            </div>
          </div>
        </div>

        <!-- 示例 -->
        <div class="code-example" v-if="showCodeData.examples && showCodeData.examples.length > 0">
          <div class="section-top">
            <div class="section-title">运行示例</div>
            <div class="toggle-btn" @click="btn(0)">{{ isEgShow ? '收起' : '展开' }}</div>
          </div>
          <div v-if="isEgShow" class="example-list">
            <div v-for="(item, index) in showCodeData.examples" :key="index" class="example-area">
              <div class="eg-line"><span class="eg-label">输入 &gt;</span>{{ item.input }}</div>
              <div class="eg-line"><span class="eg-label">输出 &gt;</span>{{ item.output }}</div>
              <div class="eg-line"><span class="eg-label">过程 &gt;</span>{{ item.explanation }}</div>
            </div>
          </div>
        </div>

        <!-- tips -->
        <div class="code-tips" v-if="showCodeData.hints && showCodeData.hints.length > 0">
          <div class="section-top">
            <div class="section-title">小提示</div>
            <div class="toggle-btn" @click="btn(1)">{{ isTipsShow ? '收起' : '展开' }}</div>
          </div>
          <div v-if="isTipsShow" class="tips-area">
            <div class="tips-item" v-for="(item, index) in showCodeData.hints" :key="index" v-html="formatContent(item)"></div>
          </div>
        </div>

        <!-- 选择语言 -->
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
              <van-icon v-if="getTwinWarning(n)" name="warning-o" class="twin-warning-icon" @click="showToast(getTwinWarning(n).tip)" />
              <van-icon v-if="getTwinError(n)" name="close" class="twin-error-icon" @click="showToast(getTwinError(n).msg)" />
              <span class="line-num">{{ n }}</span>
            </div>
          </div>
          <textarea
            ref="codeTextareaRef"
            v-model="submitContent.answer"
            @input="updateLineCount"
            @keydown="handleCodeKeydown"
            @scroll="syncLineNumbersScroll"
            placeholder="// 选择编写语言后，在此处编写代码..."
            class="code-textarea"
            spellcheck="false"
            wrap="off"
          ></textarea>
        </div>

        <!-- 孪生提示汇总 -->
        <div v-if="twinEnabled && (twinWarnings.length > 0 || twinErrors.length > 0)" class="twin-summary">
          <div v-if="twinWarnings.length > 0" class="twin-block">
            <div class="twin-block-title">AI数字孪生提示</div>
            <div v-for="(w, i) in twinWarnings" :key="'w'+i" class="twin-line">第{{ w.line }}行：{{ w.tip }}</div>
          </div>
          <div v-if="twinErrors.length > 0" class="twin-block">
            <div class="twin-block-title error">代码语法错误</div>
            <div v-for="(e, i) in twinErrors" :key="'e'+i" class="twin-line">第{{ e.line }}行：{{ e.msg }}</div>
          </div>
        </div>

        <!-- 提交按钮 -->
        <div class="submit-wrapper">
          <van-button
            type="primary"
            block
            class="custom-submit-btn"
            @click="submitCode()"
            :disabled="!submitContent.answer.trim()"
          >
            <img :src="imgShow()" alt="Lang" class="lang-icon" v-if="submitContent.answer.trim()" />
            <span class="btn-text">{{ submitContent.answer.trim() ? '提交分析代码' : '请编写代码' }}</span>
            <!-- <van-icon name="play-circle-o" size="18" /> -->
          </van-button>
          <div class="submit-hint">
            {{ submitContent.answer.trim() ? '点击提交后请耐心等待评估结果' : '请在上方编写代码后提交' }}
          </div>
        </div>

        <!-- 本题提交分析历史 -->
        <div class="code-history">
          <div class="history-head">
            <van-icon name="clock-o" size="18" />
            <div class="history-title">本题提交分析历史</div>
          </div>

          <div v-if="showCHList && showCHList.length > 0" class="history-list">
            <div
              v-for="item in showCHList"
              :key="item.id"
              class="history-item"
              :class="item.verdict === 'Accepted' ? 'pass' : (item.verdict === 'Wrong Answer' ? 'coming' : 'bad')"
              @click="getExamineMsg(item.id)"
            >
              <div class="history-item-left">
                <div class="history-item-text" v-if="item.status == 2">
                  <div class="history-score">{{ item.score }} 分</div>
                  <div>{{ item.verdict == 'Accepted' ? '通过' : (item.verdict === 'Wrong Answer' ? '再接再厉' : '编译错误') }}</div>
                </div>
                <div class="history-item-text" v-else-if="item.status == 1 || item.status == null">
                  等待返回成绩...
                </div>
                <div class="history-item-text" v-else>
                  无成绩，系统分析失败！
                </div>
                <div class="history-item-ct">{{ item.createTime }}</div>
              </div>
              <div class="history-item-right">
                <van-icon v-if="item.status == 1 || item.status == null" name="loading" class="loading-icon" />
                <span v-if="item.status == 1 || item.status == null" class="status-text">分析中</span>
                <van-icon v-if="item.status == 3" name="warning-o" class="fail-icon" />
                <van-icon
                  v-if="item.status == 2 || item.status == 3"
                  name="delete-o"
                  class="delete-icon"
                  @click.stop="delCHItem(item.id)"
                />
              </div>
            </div>
          </div>

          <div v-else class="history-empty">
            <van-empty description="暂无分析记录" image-size="80" />
          </div>
        </div>
      </div>
    </div>

    <!-- 结果页 (全屏覆盖) -->
    <Transition name="slide-up">
      <div v-if="isResultShow" class="result-page">
        <div class="detail-nav">
          <div class="nav-side" @click="quitResult">
            <van-icon name="arrow-left" size="20" />
          </div>
          <div class="nav-title">评估结果</div>
          <div class="nav-side" @click="quitResult">
            <van-icon name="cross" size="20" />
          </div>
        </div>

        <div ref="resultScrollbarRef" class="result-scroll">
          <!-- 加载状态 -->
          <div v-if="isShowLoading" class="status-page">
            <van-loading type="spinner" color="var(--primary)" size="48" />
            <p class="status-text">加载中...</p>
          </div>

          <!-- 分析状态 -->
          <div v-else-if="beforeContent.status === 1" class="status-page">
            <van-loading type="spinner" color="var(--primary)" size="56" />
            <p class="status-text">分析中...</p>
          </div>

          <!-- 分析失败 -->
          <div v-else-if="beforeContent.status === 3" class="status-page">
            <van-icon name="warning-o" size="64" color="#F56C6C" />
            <p class="status-text fail-text">分析失败</p>
          </div>

          <!-- 正常状态 -->
          <div v-else-if="beforeContent.status === 2" class="comment">
            <!-- 分数 -->
            <div class="code-score">{{ beforeContent.score }} 分</div>

            <!-- 头部 -->
            <div class="before-head">
              <div class="header">
                <span>【{{ beforeContent.createTime }}】</span>上传<span>{{ beforeContent.language }}</span>语言原代码：
              </div>
              <div
                class="is-pass"
                :class="beforeContent.verdict === 'Accepted' ? 'pass' : (beforeContent.verdict === 'Wrong Answer' ? 'coming' : 'bad')"
              >
                {{ beforeContent.verdict == 'Accepted' ? '通过' : (beforeContent.verdict === 'Wrong Answer' ? '再接再厉' : '编译错误') }}
              </div>
            </div>

            <!-- 原代码展示 -->
            <div class="before-code">
              <div class="code-editor-container">
                <div class="line-numbers" ref="resultLineNumbersRef">
                  <div v-for="n in resultCount" :key="n" class="line-number-item"><span class="line-num">{{ n }}</span></div>
                </div>
                <textarea
                  v-model="beforeContent.answer"
                  placeholder="// 此处为原代码展示块"
                  class="code-textarea"
                  spellcheck="false"
                  disabled
                  wrap="off"
                  @scroll="syncResultScroll"
                ></textarea>
              </div>
            </div>

            <!-- 评价区 -->
            <div class="code-comment">
              <!-- 测试用例通过情况 -->
              <div class="situation">
                <div class="st-top">
                  <van-icon name="passed" size="20" color="#0c84c3" />
                  <div>Agent后台测试项通过情况：</div>
                </div>
                <div class="st-content">
                  <span class="num">{{ beforeContent.totalTests }}</span> 项测试，共通过 <span class="num">{{ beforeContent.passedTests }}</span> 项
                </div>
              </div>

              <!-- 改进建议 -->
              <div class="how-do">
                <div class="hd-top">
                  <van-icon name="bulb-o" size="20" color="#f4ea2a" />
                  <div>代码改进建议：</div>
                </div>
                <div class="hd-content" v-for="(item, index) in beforeContent.suggestion" :key="index">
                  {{ index + 1 }}、{{ item }}
                </div>
              </div>

              <!-- 鼓励 -->
              <div class="how-do encouragement" v-if="beforeContent.encouragement">
                <div class="hd-content">{{ beforeContent.encouragement }}</div>
              </div>
            </div>

            <!-- 算法可视化区 -->
            <div class="visualization">
              <div class="vs-btn">
                <van-button
                  v-show="!detectedType"
                  type="primary"
                  block
                  class="custom-submit-btn"
                  @click="toVisualize()"
                  :disabled="loading"
                >
                  <span class="btn-text">{{ loading ? '转换中...' : '点击可视化预览所写代码' }}</span>
                  <!-- <van-icon name="play-circle-o" size="18" /> -->
                </van-button>
              </div>
              <div class="vs-area" :class="logStatus ? 'open-log-show' : ''" ref="vizContainerRef" style="display:none;">
                <div class="viz-loading" v-if="loading">
                  <van-loading type="spinner" color="#DBEAFE" size="40" />
                  <div class="viz-loading-text">生成中</div>
                </div>
                <div id="vizSection" style="display:none;">
                  <div class="algorithm-viz-section">
                    <div class="viz-header">
                      <div class="viz-header-left">
                        <van-icon name="eye-o" size="18" />
                        <h3>算法可视化预览</h3>
                      </div>
                      <div class="viz-header-actions">
                        <div class="viz-log-toggle" @click="btn(2)">{{ logStatus ? '关闭日志' : '开启日志' }}</div>
                        <button id="stopVizBtn" class="icon-btn" @click="vizModule?.stopWorker()" style="display:none;">⏹️</button>
                        <button class="icon-btn" @click="closeViz">✕</button>
                      </div>
                    </div>
                    <div class="viz-body">
                      <div class="viz-status-wrap">
                        <span id="vizStatus" class="viz-status">等待转换...</span>
                      </div>
                      <div class="viz-content-wrap">
                        <div id="vizCodePanel">
                          <div class="viz-code-panel-header">代码执行跟踪</div>
                          <div id="vizCodeContent"></div>
                        </div>
                        <canvas id="vizCanvas" width="320" height="240"></canvas>
                      </div>
                      <div id="vizControls" class="viz-controls">
                        <button id="vizPlayBtn" @click="vizModule?.play()" class="viz-btn-play">▶️ 开始</button>
                        <button id="vizPauseBtn" @click="vizModule?.pause()" class="viz-btn-pause" style="display:none;">⏸️ 暂停</button>
                        <button @click="vizModule?.reset()" class="viz-btn-reset">🔄 重置</button>
                        <select id="vizSpeedSelect" @change="vizModule?.updateSpeed($event.target.value)" class="viz-select">
                          <option value="500">0.5x</option>
                          <option value="180" selected>1x</option>
                          <option value="90">2x</option>
                          <option value="60">3x</option>
                        </select>
                        <div class="speed-slider-wrap">
                          <span class="speed-label">速度:</span>
                          <input type="range" id="vizSpeed" class="speed-slider" min="20" max="500" value="180" @input="vizModule?.updateSpeedFromSlider($event.target.value)">
                          <span id="vizSpeedLabel" class="speed-value">180ms</span>
                        </div>
                        <span id="vizFrameInfo" class="frame-info">帧: 0/0</span>
                      </div>
                      <div id="vizLog" class="viz-log" v-show="logStatus"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 排行榜 -->
            <div class="rank">
              <div class="rank-card">
                <div class="rank-card-title">
                  <van-icon name="medal-o" size="22" color="#2D7DDB" />
                  <span>本题成绩排行榜</span>
                </div>
                <div class="rank-tip">*蓝色底色的为你的该题评估分数</div>

                <div v-if="rankList.length" ref="rankScrollbarRef" class="rank-list">
                  <div
                    v-for="(item, index) in rankList"
                    :key="item.userId"
                    class="rank-item"
                    :class="{ myRank: item.userId === userId }"
                  >
                    <div class="rank-medal" v-if="index < 3">
                      <div class="medal-circle" :class="'medal-' + (index + 1)">{{ index + 1 }}</div>
                    </div>
                    <div class="rank-index" v-else>{{ index + 1 }}</div>

                    <div class="rank-info">
                      <div class="user-avatar">
                        <img v-if="item.avatar" :src="item.avatar" class="avatar-img" />
                        <div v-else class="avatar-default">{{ item.username ? item.username.charAt(0) : '?' }}</div>
                        <div class="user-name">{{ item.username }}</div>
                      </div>
                      <div class="user-score">历史最高 <span>{{ item.score }}</span> 分</div>
                    </div>

                    <div class="rank-actions">
                      <div class="compare-code-btn" @click="compareCode(item)">AI分析比较</div>
                      <div class="look-code-btn" @click="getLookUserMsg(item.userId, index)">查看代码</div>
                    </div>
                  </div>
                  <div class="back-top-btn" @click="scrollToTop(rankScrollbarRef)">返回排行榜顶部</div>
                </div>

                <div v-else class="rank-empty">
                  <van-empty description="暂无排名" image-size="80" />
                </div>
              </div>
            </div>

            <!-- 返回顶部 -->
            <div class="back-top">
              <div class="back-top-btn" @click="scrollToTop(resultScrollbarRef)">返回评估页顶部</div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 查看他人代码弹窗 -->
    <Transition name="slide-up">
      <div v-if="isLookCode" class="look-code-overlay">
        <div class="look-code-card">
          <div class="look-head">
            <div class="look-left">
              <img v-if="lookUserMsg.avatar" :src="lookUserMsg.avatar" class="avatar-img" />
              <div v-else class="avatar-default">{{ lookUserMsg.username ? lookUserMsg.username.charAt(0) : '?' }}</div>
              <div class="look-info">
                <div class="user-name">{{ lookUserMsg.username }}</div>
                <div class="user-score">得分：<span>{{ lookUserMsg.score }}</span> 分</div>
              </div>
            </div>
            <div class="look-close" @click="closeLookCode">关闭</div>
          </div>
          <div class="look-code-body">
            <div class="code-editor-container">
              <div class="line-numbers" ref="lookLineNumbersRef">
                <div v-for="n in lookCount" :key="n" class="line-number-item"><span class="line-num">{{ n }}</span></div>
              </div>
              <textarea
                v-model="lookUserMsg.codePreview"
                placeholder="// 此处为原代码展示块"
                class="code-textarea"
                spellcheck="false"
                disabled
                wrap="off"
                @scroll="syncLookScroll"
              ></textarea>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- AI分析比较弹窗 -->
    <Transition name="slide-up">
      <div v-if="compareVisible" class="compare-overlay">
        <div class="compare-modal">
          <div class="compare-header">
            <span class="compare-title">AI代码分析比较</span>
            <button class="compare-close" @click="closeCompare">
              <van-icon name="cross" size="20" />
            </button>
          </div>

          <div v-if="compareLoading" class="compare-loading">
            <van-loading type="spinner" color="var(--primary)" size="40" />
            <span>AI正在分析代码，请稍候...</span>
          </div>

          <div v-else class="compare-body">
            <div v-if="compareData && compareData.length >= 3" class="compare-content">
              <!-- 分数对比 -->
              <div class="compare-section">
                <div class="compare-section-title">分数对比</div>
                <div class="score-comparison">
                  <div class="score-item score-a">
                    <div class="score-avatar">
                      <img v-if="compareUserInfo[compareData[0].user_id]?.avatar" :src="compareUserInfo[compareData[0].user_id]?.avatar" class="avatar-img" />
                      <div v-else class="avatar-default">{{ compareUserInfo[compareData[0].user_id]?.username?.charAt(0) || '我' }}</div>
                    </div>
                    <div class="score-name">{{ compareUserInfo[compareData[0].user_id]?.username || '我' }}</div>
                    <div class="score-value">{{ compareData[0].score }}</div>
                    <div class="score-verdict" :class="compareData[0].verdict?.toLowerCase().replace(/\s+/g, '')">{{ compareData[0].verdict }}</div>
                  </div>
                  <div class="score-vs">VS</div>
                  <div class="score-item score-b">
                    <div class="score-avatar">
                      <img v-if="compareUserInfo[compareData[1].user_id]?.avatar" :src="compareUserInfo[compareData[1].user_id]?.avatar" class="avatar-img" />
                      <div v-else class="avatar-default">{{ compareUserInfo[compareData[1].user_id]?.username?.charAt(0) || '用户' }}</div>
                    </div>
                    <div class="score-name">{{ compareUserInfo[compareData[1].user_id]?.username || '用户' }}</div>
                    <div class="score-value">{{ compareData[1].score }}</div>
                    <div class="score-verdict" :class="compareData[1].verdict?.toLowerCase().replace(/\s+/g, '')">{{ compareData[1].verdict }}</div>
                  </div>
                </div>
              </div>

              <!-- 代码对比 -->
              <div class="compare-section">
                <div class="compare-section-title">代码对比</div>
                <div class="code-comparison">
                  <div class="code-panel code-a">
                    <div class="code-header code-header-a">
                      <span>{{ compareUserInfo[compareData[0].user_id]?.username || '我' }}</span>
                      <span class="code-lang">{{ compareData[0].language }}</span>
                    </div>
                    <pre class="code-content compare-code">{{ compareData[0].full_code }}</pre>
                  </div>
                  <div class="code-panel code-b">
                    <div class="code-header code-header-b">
                      <span>{{ compareUserInfo[compareData[1].user_id]?.username || '用户' }}</span>
                      <span class="code-lang">{{ compareData[1].language }}</span>
                    </div>
                    <pre class="code-content compare-code">{{ compareData[1].full_code }}</pre>
                  </div>
                </div>
              </div>

              <!-- 图表对比 -->
              <div class="compare-section">
                <div class="compare-section-title">维度分析</div>
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
              <div class="compare-section">
                <div class="compare-section-title">复杂度对比</div>
                <div class="complexity-grid">
                  <div class="complexity-card card-a">
                    <div class="card-header">
                      <img v-if="compareUserInfo[compareData[0].user_id]?.avatar" :src="compareUserInfo[compareData[0].user_id]?.avatar" class="avatar-img" />
                      <div v-else class="avatar-default">{{ compareUserInfo[compareData[0].user_id]?.username?.charAt(0) || '我' }}</div>
                      <div class="card-name">{{ compareUserInfo[compareData[0].user_id]?.username || '我' }}</div>
                    </div>
                    <div class="card-body">
                      <div class="complexity-row">
                        <span class="complexity-type">时间</span>
                        <span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_a?.time_complexity || '-' }}</span>
                      </div>
                      <div class="complexity-row"><span class="complexity-type">空间</span><span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_a?.space_complexity || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="complexity-vs">vs</div>
                  <div class="complexity-card card-b">
                    <div class="card-header">
                      <img v-if="compareUserInfo[compareData[1].user_id]?.avatar" :src="compareUserInfo[compareData[1].user_id]?.avatar" class="avatar-img" />
                      <div v-else class="avatar-default">{{ compareUserInfo[compareData[1].user_id]?.username?.charAt(0) || '用' }}</div>
                      <div class="card-name">{{ compareUserInfo[compareData[1].user_id]?.username || '用户' }}</div>
                    </div>
                    <div class="card-body">
                      <div class="complexity-row"><span class="complexity-type">时间</span><span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_b?.time_complexity || '-' }}</span></div>
                      <div class="complexity-row"><span class="complexity-type">空间</span><span class="complexity-value">{{ compareData[2]?.data?.comparison?.chart_data?.solution_b?.space_complexity || '-' }}</span></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- AI分析报告 -->
              <div class="compare-section">
                <div class="compare-section-title">AI分析报告</div>
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
    </Transition>

    <!-- 冲突提示弹窗 -->
    <Transition name="fade">
      <div v-if="showConflictDialog" class="conflict-overlay">
        <div class="conflict-dialog">
          <div class="conflict-dialog-header">
            <van-icon name="warning-o" size="22" color="#fb722e" />
            <span>温馨提示</span>
          </div>
          <div class="conflict-dialog-content" v-html="formatConflictMessage(conflictData.suggestionWarning)"></div>
          <div class="conflict-dialog-footer">
            <button class="conflict-btn conflict-btn-reject" @click="handleConflictOption(false)">拒绝</button>
            <button class="conflict-btn conflict-btn-accept" @click="handleConflictOption(true)">接受</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 错题重练通知 (底部弹出) -->
    <Transition name="slide-up">
      <div v-if="ntfVisible" class="ntf-overlay" @click.self="closeNtf">
        <div class="ntf-card">
          <div class="ntf-close" @click="closeNtf">
            <van-icon name="cross" size="18" />
          </div>
          <template v-if="ntfType === 'question'">
            <p class="ntf-msg">你已经提交代码评估，好几次没过咯~<br />我们为你推荐几道旧题和新题，再试着练一练吧！</p>
            <div class="ntf-names">
              <div v-if="ntfData.newItem > 0" class="ntf-name new">{{ ntfData.newName }}</div>
              <div v-for="(name, i) in ntfData.oldName" :key="i" class="ntf-name old">{{ name }}</div>
            </div>
            <div class="ntf-actions">
              <van-button type="primary" size="small" @click="ntfViewList">查看编程资源列表</van-button>
              <van-button size="small" @click="ntfBackWrong">返回错题本</van-button>
            </div>
          </template>
          <template v-else>
            <p class="ntf-msg">你的重练已经通过了，返回错题本 已掌握 看看重练趋势吧！</p>
            <div class="ntf-actions">
              <van-button size="small" @click="ntfBackWrong">返回错题本</van-button>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.phone-code {
  min-height: 100vh;
  background: var(--bg-page, #f7f8fa);
  padding-bottom: 60px;
}

/* 顶部导航 */
.page-nav,
.detail-nav {
  display: flex;
  align-items: center;
  padding: 12px 0;
  background: var(--bg-card, #fff);
  border-bottom: 1px solid var(--border-color, #eee);
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-side {
  width: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-title {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  text-align: center;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title, #323233);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 4px;
}

/* 列表页 */
.code-list-page {
  padding: 16px;
}
.page-header {
  margin-bottom: 16px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-title, #323233);
  margin: 0 0 4px;
}
.page-desc {
  font-size: 13px;
  color: var(--text-gray, #969799);
  margin: 0;
}

/* 输入区 */
.input-section {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color, #eee);
}
.code-input {
  margin-bottom: 12px;
  border-radius: 8px;
  overflow: hidden;
}
.submit-btn {
  font-weight: 600;
}

/* 列表 */
.list-section {
  margin-top: 8px;
}
.list-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: var(--bg-card, #fff);
  border-radius: 10px;
  border: 1px solid var(--border-color, #eee);
  transition: all 0.2s;
}
.list-item:active {
  transform: scale(0.98);
}
.item-loading {
  opacity: 0.75;
}
.item-fail {
  border-color: rgba(245, 108, 108, 0.4);
}
.item-info {
  flex: 1;
  min-width: 0;
}
.item-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-body, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
}
.item-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 10px;
}
.loading-icon {
  color: var(--primary, #2D7DDB);
  animation: spin 1s linear infinite;
  font-size: 18px;
}
.status-text {
  font-size: 12px;
  color: var(--primary, #2D7DDB);
  font-weight: 500;
}
.fail-icon {
  color: #F56C6C;
  font-size: 20px;
}
.fail-status-text {
  font-size: 12px;
  color: #F56C6C;
  font-weight: 500;
}
.delete-icon {
  color: #F56C6C;
  font-size: 20px;
  padding: 4px;
}
.expand-btn {
  text-align: center;
  padding: 12px;
  font-size: 14px;
  color: var(--text-gray, #969799);
}
.empty-state {
  padding: 40px 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 详情页 */
.code-detail-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-page, #f7f8fa);
  z-index: 100;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 60px;
  box-sizing: border-box;
}

/* 状态页 */
.status-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
}
.status-page .status-text {
  margin-top: 20px;
  font-size: 16px;
  color: var(--text-gray, #969799);
}
.fail-text {
  color: #F56C6C !important;
  font-weight: 600;
}

/* 详情内容 */
.detail-content {
  padding: 16px;
}
.create-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}
.create-text {
  font-size: 14px;
  color: var(--text-body, #323233);
  font-weight: 600;
}
.create-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
}

/* 题目 */
.code-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.code-level {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: var(--primary-light, rgba(45, 125, 219, 0.1));
  color: var(--primary, #2D7DDB);
}
.code-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-title, #323233);
}

/* 内容 */
.code-content {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 14px;
  border: 1px solid var(--border-color, #eee);
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-body, #323233);
}
.code-content.compare-code {
  border-radius: 0 0 12px 12px;
}
.code-desc,
.code-input-format,
.code-output-format {
  margin-bottom: 10px;
}
.code-input-format,
.code-output-format {
  background: var(--bg-page, #f7f8fa);
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
}
.code-tag {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
}
.tag-label {
  font-size: 13px;
  color: var(--text-gray, #969799);
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  background: rgba(78, 191, 109, 0.12);
  color: var(--pass, #4EBF6D);
}

/* markdown 内容渲染 */
.code-content :deep(h1),
.code-content :deep(h2),
.code-content :deep(h3),
.code-content :deep(h4),
.code-content :deep(h5),
.code-content :deep(h6) {
  color: var(--text-title, #323233);
  margin: 10px 0 6px;
}
.code-content :deep(p) {
  margin: 6px 0;
}
.code-content :deep(code) {
  background: rgba(45, 125, 219, 0.1);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--primary, #2D7DDB);
}
.code-content :deep(a) {
  color: var(--primary, #2D7DDB);
}
.code-content :deep(ul) {
  padding-left: 20px;
  margin: 6px 0;
}
.code-content :deep(li) {
  margin: 2px 0;
}

/* 示例 / tips */
.code-example,
.code-tips {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 14px;
  border: 1px solid var(--border-color, #eee);
  margin-top: 12px;
}
.section-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.toggle-btn {
  font-size: 13px;
  color: var(--primary, #2D7DDB);
  padding: 4px 8px;
}
.example-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.example-area {
  background: var(--bg-page, #f7f8fa);
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  line-height: 1.7;
}
.eg-line {
  margin: 2px 0;
  word-break: break-all;
}
.eg-label {
  color: var(--primary, #2D7DDB);
  font-weight: 600;
  margin-right: 4px;
}
.tips-area {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-body, #323233);
}

/* 语言选择 */
.select-language {
  margin-top: 14px;
}
.native-select {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #eee);
  background: var(--bg-card, #fff);
  font-size: 14px;
  color: var(--text-body, #323233);
  appearance: none;
  background-image: linear-gradient(45deg, transparent 50%, var(--text-gray) 50%),
                    linear-gradient(135deg, var(--text-gray) 50%, transparent 50%);
  background-position: calc(100% - 16px) center, calc(100% - 11px) center;
  background-size: 5px 5px, 5px 5px;
  background-repeat: no-repeat;
}

/* 代码编辑器 */
.code-editor-container {
  display: flex;
  margin-top: 10px;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color, #eee);
  height: 280px;
}
.line-numbers {
  flex-shrink: 0;
  width: 32px;
  padding: 10px 4px 10px 6px;
  text-align: right;
  background: #252526;
  color: #858585;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 8px;
  line-height: 1.05;
  user-select: none;
  /* overflow: hidden; */
}
.line-number-item {
  position: relative;
  height: 16.1px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
}
.line-num {
  font-size: 12px;
}
.twin-warning-icon {
  color: #ffcb6b;
  font-size: 8px;
}
.twin-error-icon {
  color: #f48771;
  font-size: 8px;
}
.code-textarea {
  flex: 1;
  min-width: 0;
  padding: 10px 8px;
  border: none;
  outline: none;
  resize: none;
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 8px;
  line-height: 1.05;
  white-space: pre;
  overflow: auto;
  height: 280px;
}
.code-textarea:disabled {
  color: #c8c8c8;
  -webkit-text-fill-color: #c8c8c8;
  opacity: 1;
}

/* 孪生提示汇总 */
.twin-summary {
  margin-top: 10px;
  background: var(--bg-card, #fff);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid var(--border-color, #eee);
  font-size: 12px;
}
.twin-block {
  margin-bottom: 8px;
}
.twin-block:last-child {
  margin-bottom: 0;
}
.twin-block-title {
  font-weight: 600;
  color: #ffcb6b;
  margin-bottom: 4px;
}
.twin-block-title.error {
  color: #f48771;
}
.twin-line {
  color: var(--text-body, #323233);
  line-height: 1.6;
  padding: 2px 0;
}

/* 提交按钮 */
.submit-wrapper {
  margin-top: 16px;
}
.custom-submit-btn {
  font-weight: 600;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 10px !important;
}
.custom-submit-btn:deep(.van-button) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 10px !important;
}
.custom-submit-btn:deep(.van-button__content) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 10px !important;
  height: 100%;
  width: 100%;
}
/* 子元素显式 margin 作为 gap 的兜底，不依赖 flex gap 是否生效 */
.custom-submit-btn .lang-icon {
  width: 18px !important;
  height: 18px !important;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
  display: inline-flex !important;
  margin-right: 10px !important;
  vertical-align: middle;
}
.custom-submit-btn .btn-text {
  height: 20px !important;
  line-height: 20px !important;
  display: inline-flex !important;
  align-items: center !important;
  vertical-align: middle;
}
.custom-submit-btn :deep(.van-icon[name="play-circle-o"]) {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center;
  vertical-align: middle;
  margin-left: 0 !important;
}
.submit-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 8px;
}

/* 历史记录 */
.code-history {
  margin-top: 20px;
}
.history-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.history-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: var(--bg-card, #fff);
  border-radius: 10px;
  border: 1px solid var(--border-color, #eee);
}
.history-item:active {
  transform: scale(0.98);
}
.history-item.pass {
  border-left: 3px solid var(--pass, #4EBF6D);
}
.history-item.coming {
  border-left: 3px solid var(--coming, #ff9800);
}
.history-item.bad {
  border-left: 3px solid var(--main-delete, #F56C6C);
}
.history-item-left {
  flex: 1;
  min-width: 0;
}
.history-item-text {
  font-size: 14px;
  color: var(--text-body, #323233);
  font-weight: 600;
}
.history-score {
  font-size: 16px;
  color: var(--primary, #2D7DDB);
  font-weight: 700;
}
.history-item-ct {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
}
.history-item-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 10px;
}
.history-empty {
  padding: 20px 0;
}

/* 结果页 */
.result-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-page, #f7f8fa);
  z-index: 200;
  display: flex;
  flex-direction: column;
}
.result-scroll {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 16px 16px 76px;
}
.comment {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.code-score {
  text-align: center;
  font-size: 36px;
  font-weight: 700;
  color: var(--primary, #2D7DDB);
  padding: 10px 0;
}
.before-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card, #fff);
  border-radius: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #eee);
  font-size: 12px;
  flex-wrap: wrap;
  gap: 6px;
}
.before-head .header {
  color: var(--text-body, #323233);
}
.is-pass {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}
.is-pass.pass {
  background: rgba(78, 191, 109, 0.12);
  color: var(--pass, #4EBF6D);
}
.is-pass.coming {
  background: rgba(255, 152, 0, 0.12);
  color: var(--coming, #ff9800);
}
.is-pass.bad {
  background: rgba(245, 108, 108, 0.12);
  color: var(--main-delete, #F56C6C);
}

/* 结果页代码块 */
.before-code .code-editor-container {
  margin-top: 0;
}
.before-code .code-textarea {
  height: 280px;
}

/* 评价区 */
.code-comment {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.situation,
.how-do {
  background: var(--bg-card, #fff);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid var(--border-color, #eee);
  font-size: 13px;
}
.st-top,
.hd-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.st-content {
  color: var(--text-body, #323233);
}
.st-content .num,
.hd-content {
  color: var(--primary, #2D7DDB);
  font-weight: 600;
}
.hd-content {
  margin: 4px 0;
  color: var(--text-body, #323233);
  font-weight: 400;
  line-height: 1.6;
}
.encouragement {
  background: rgba(78, 191, 109, 0.08);
  border-color: rgba(78, 191, 109, 0.3);
}

/* 可视化 */
.visualization {
  background: var(--bg-card, #fff);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid var(--border-color, #eee);
}
.vs-btn {
  margin-bottom: 10px;
}
.vs-area {
  width: 100%;
}
.viz-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 30px 0;
  gap: 10px;
}
.viz-loading-text {
  color: var(--text-gray, #969799);
  font-size: 13px;
}
.algorithm-viz-section {
  background: #1e1e2e;
  border-radius: 8px;
  overflow: hidden;
}
.viz-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: #252526;
  color: #fff;
}
.viz-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.viz-header-left h3 {
  font-size: 13px;
  margin: 0;
  color: #fff;
}
.viz-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.viz-log-toggle {
  font-size: 11px;
  color: #9cdcfe;
  padding: 2px 6px;
  border: 1px solid #555;
  border-radius: 4px;
}
.icon-btn {
  background: transparent;
  border: none;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  padding: 2px 4px;
}
.viz-body {
  padding: 8px;
}
.viz-status-wrap {
  text-align: center;
  margin-bottom: 6px;
}
.viz-status {
  font-size: 12px;
  color: #9cdcfe;
}
.viz-content-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
#vizCodePanel {
  background: #1e1e1e;
  border-radius: 4px;
  padding: 6px;
  font-size: 11px;
  color: #d4d4d4;
  font-family: 'Consolas', monospace;
  max-height: 200px;
  overflow: auto;
}
.viz-code-panel-header {
  font-size: 11px;
  color: #9cdcfe;
  margin-bottom: 4px;
}
#vizCodeContent {
  white-space: pre;
  line-height: 1.4;
}
#vizCanvas {
  width: 100%;
  max-width: 320px;
  height: auto;
  display: block;
  margin: 0 auto;
  background: #000;
  border-radius: 4px;
}
.viz-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 8px;
  padding: 6px;
  background: #252526;
  border-radius: 4px;
}
.viz-btn-play,
.viz-btn-pause,
.viz-btn-reset {
  background: #0e639c;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 11px;
  cursor: pointer;
}
.viz-btn-reset {
  background: #555;
}
.viz-select {
  background: #3c3c3c;
  color: #fff;
  border: 1px solid #555;
  border-radius: 4px;
  padding: 3px 6px;
  font-size: 11px;
}
.speed-slider-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #ccc;
}
.speed-slider {
  width: 70px;
}
.speed-value,
.frame-info {
  font-size: 10px;
  color: #9cdcfe;
}
.viz-log {
  background: #1e1e1e;
  border-radius: 4px;
  padding: 6px;
  margin-top: 6px;
  font-size: 11px;
  font-family: 'Consolas', monospace;
  color: #d4d4d4;
  max-height: 100px;
  overflow: auto;
}

/* 排行榜 */
.rank {
  background: var(--bg-card, #fff);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid var(--border-color, #eee);
}
.rank-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.rank-tip {
  font-size: 11px;
  color: var(--text-gray, #969799);
  margin: 4px 0 10px;
}
.rank-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 500px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.rank-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: var(--bg-page, #f7f8fa);
  border-radius: 8px;
  border: 1px solid var(--border-color, #eee);
  flex-wrap: wrap;
}
.rank-item.myRank {
  background: rgba(45, 125, 219, 0.1);
  border-color: var(--primary, #2D7DDB);
}
.rank-medal {
  flex-shrink: 0;
}
.medal-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
}
.medal-1 {
  background: #f0a020;
}
.medal-2 {
  background: #b0b0b0;
}
.medal-3 {
  background: #cd7f32;
}
.rank-index {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--text-gray, #969799);
  font-weight: 600;
}
.rank-info {
  flex: 1;
  min-width: 0;
}
.user-avatar {
  display: flex;
  align-items: center;
  gap: 6px;
}
.avatar-img {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--border-color, #eee);
}
.avatar-default {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--primary, #2D7DDB);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}
.user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-body, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-score {
  font-size: 11px;
  color: var(--text-gray, #969799);
  margin-top: 2px;
}
.user-score span {
  color: var(--primary, #2D7DDB);
  font-weight: 600;
}
.rank-actions {
  display: flex;
  gap: 6px;
  width: 100%;
}
.compare-code-btn,
.look-code-btn {
  flex: 1;
  text-align: center;
  padding: 6px;
  font-size: 11px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #eee);
  color: var(--text-body, #323233);
}
.compare-code-btn {
  background: rgba(45, 125, 219, 0.08);
  color: var(--primary, #2D7DDB);
}
.look-code-btn {
  background: rgba(78, 191, 109, 0.08);
  color: var(--pass, #4EBF6D);
}
.rank-empty {
  padding: 20px 0;
}
.back-top {
  margin-top: 16px;
}
.back-top-btn {
  text-align: center;
  padding: 12px;
  font-size: 14px;
  color: var(--text-gray, #969799);
  background: var(--bg-card, #fff);
  border-radius: 10px;
  border: 1px solid var(--border-color, #eee);
}

/* 查看代码弹窗 */
.look-code-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 300;
  display: flex;
  align-items: flex-end;
  padding-bottom: 50px;
  box-sizing: border-box;
}
.look-code-card {
  width: 100%;
  background: var(--bg-card, #fff);
  border-radius: 16px 16px 0 0;
  padding: 16px;
  max-height: 85%;
  display: flex;
  flex-direction: column;
}
.look-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.look-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.look-left .avatar-img,
.look-left .avatar-default {
  width: 40px;
  height: 40px;
  font-size: 16px;
}
.look-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.look-info .user-score span {
  color: var(--primary, #2D7DDB);
  font-weight: 600;
}
.look-close {
  font-size: 14px;
  color: var(--text-gray, #969799);
  padding: 6px 10px;
}
.look-code-body {
  flex: 1;
  overflow: auto;
}
/* .look-code-body .code-textarea {
  height: 360px;
} */

/* AI比较弹窗 */
.compare-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 400;
  display: flex;
  align-items: flex-end;
  padding-bottom: 50px;
  box-sizing: border-box;
}
.compare-modal {
  width: 100%;
  height: 95%;
  background: var(--bg-page, #f7f8fa);
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.compare-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: var(--bg-card, #fff);
  border-bottom: 1px solid var(--border-color, #eee);
  flex-shrink: 0;
}
.compare-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.compare-close {
  background: transparent;
  border: none;
  color: var(--text-gray, #969799);
  cursor: pointer;
  padding: 4px;
}
.compare-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-gray, #969799);
  font-size: 14px;
}
.compare-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 16px;
}
.compare-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.compare-section {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 14px;
  border: 1px solid var(--border-color, #eee);
}
.compare-section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #323233);
  margin-bottom: 10px;
}

/* 分数对比 */
.score-comparison {
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: 8px;
}
.score-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.score-item .avatar-img,
.score-item .avatar-default {
  width: 40px;
  height: 40px;
  font-size: 16px;
}
.score-name {
  font-size: 12px;
  color: var(--text-body, #323233);
  font-weight: 600;
}
.score-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--primary, #2D7DDB);
}
.score-verdict {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(245, 108, 108, 0.12);
  color: var(--main-delete, #F56C6C);
}
.score-verdict.accepted {
  background: rgba(78, 191, 109, 0.12);
  color: var(--pass, #4EBF6D);
}
.score-vs {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-gray, #969799);
}

/* 代码对比 */
.code-comparison {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.code-panel {
  background: var(--bg-page, #f7f8fa);
  border-radius: 8px;
  overflow: hidden;
}
.code-header {
  padding: 6px 10px;
  font-size: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.code-header-a {
  background: rgba(45, 125, 219, 0.12);
  color: var(--primary, #2D7DDB);
}
.code-header-b {
  background: rgba(78, 191, 109, 0.12);
  color: var(--pass, #4EBF6D);
}
.code-lang {
  font-size: 11px;
  opacity: 0.8;
}
.code-content {
  margin: 0;
  padding: 10px;
  font-family: 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-body, #323233);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow: auto;
}

/* 图表 */
.chart-comparison {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chart-panel {
  background: var(--bg-page, #f7f8fa);
  border-radius: 8px;
  padding: 8px;
}
.chart-header {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title, #323233);
  margin-bottom: 6px;
  text-align: center;
}
.chart-container {
  width: 100%;
  height: 220px;
}

/* 复杂度 */
.complexity-grid {
  display: flex;
  align-items: center;
  gap: 8px;
}
.complexity-card {
  flex: 1;
  background: var(--bg-page, #f7f8fa);
  border-radius: 8px;
  padding: 10px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.card-header .avatar-img,
.card-header .avatar-default {
  width: 28px;
  height: 28px;
  font-size: 12px;
}
.card-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-body, #323233);
}
.card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.complexity-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}
.complexity-type {
  color: var(--text-gray, #969799);
  flex-shrink: 0;
}
.complexity-value {
  color: var(--primary, #2D7DDB);
  font-weight: 600;
  flex: 1;
  min-width: 0;
  word-break: break-all;
  text-align: right;
}
.complexity-vs {
  font-size: 12px;
  color: var(--text-gray, #969799);
  font-weight: 600;
}

/* 报告 */
.report-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.report-item {
  background: var(--bg-page, #f7f8fa);
  border-radius: 8px;
  padding: 10px;
}
.report-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title, #323233);
  margin-bottom: 4px;
}
.report-text {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-body, #323233);
}
.report-text :deep(code) {
  background: rgba(45, 125, 219, 0.1);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
  color: var(--primary, #2D7DDB);
}
.report-text :deep(strong) {
  color: var(--text-title, #323233);
}

/* 冲突弹窗 */
.conflict-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.conflict-dialog {
  width: 100%;
  max-width: 360px;
  background: var(--bg-card, #fff);
  border-radius: 12px;
  overflow: hidden;
}
.conflict-dialog-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px 16px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #323233);
  border-bottom: 1px solid var(--border-color, #eee);
}
.conflict-dialog-content {
  padding: 16px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-body, #323233);
  max-height: 300px;
  overflow-y: auto;
}
.conflict-dialog-footer {
  display: flex;
  border-top: 1px solid var(--border-color, #eee);
}
.conflict-btn {
  flex: 1;
  padding: 12px;
  border: none;
  background: transparent;
  font-size: 15px;
  cursor: pointer;
}
.conflict-btn-reject {
  color: var(--text-gray, #969799);
  border-right: 1px solid var(--border-color, #eee);
}
.conflict-btn-accept {
  color: var(--primary, #2D7DDB);
  font-weight: 600;
}

/* 错题重练通知 */
.ntf-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 600;
  display: flex;
  align-items: flex-end;
  padding-bottom: 50px;
  box-sizing: border-box;
}
.ntf-card {
  width: 100%;
  background: var(--bg-card, #fff);
  border-radius: 16px 16px 0 0;
  padding: 20px 16px calc(16px + env(safe-area-inset-bottom));
  position: relative;
}
.ntf-close {
  position: absolute;
  top: 12px;
  right: 12px;
  color: var(--text-gray, #969799);
  padding: 4px;
}
.ntf-msg {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-title, #323233);
  margin: 0 0 12px;
}
.ntf-names {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 14px;
}
.ntf-name {
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 6px;
}
.ntf-name.new {
  color: var(--primary, #2D7DDB);
  background: rgba(45, 125, 219, 0.08);
}
.ntf-name.old {
  color: var(--text-gray, #969799);
  background: var(--bg-page, #f7f8fa);
}
.ntf-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* ================= 过渡动画 ================= */
/* 向上滑入 */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.slide-up-enter-from {
  transform: translateY(100%);
}
.slide-up-leave-to {
  transform: translateY(100%);
}

/* 淡入 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

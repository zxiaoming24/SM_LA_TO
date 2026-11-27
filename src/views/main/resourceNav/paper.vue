<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isSkip, removeSkip } from '@/utils/skip.js'
import { getPaperListApi, generatePaperApi, pollPaperInfoApi, deletePaperApi, submitSingleQuestionApi } from '@/api/mainApi/resourcePaper.js'
import { useActionPopStore } from '@/utils/actionPop.js'
import emitter from '@/utils/emitter'
import { reviewCountAddOneApi } from '@/api/mainApi/layout.js'//复习次数加一

const itemRef = ref([])
const popStore = useActionPopStore()

// 接收索引，获取当前 hover 的 DOM
const handleEnter = async (index, rsId, type='question') => {
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

// ===================数据=====================
let loginUser = null
const userId = ref(null)
const skipInfo = ref()

onMounted(async() => {
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
  await getList()
  if (isSkip(7) === false) {
    console.log('没有试卷需要提前打开')
  } else {
    skipInfo.value = isSkip(7)
    console.log('跳转信息:', skipInfo.value)
    try {
      await getValue(skipInfo.value.resourceId)
    } catch(e) {
      ElMessage.error('该试卷不存在，可能已经被删除了')
      console.log('打开失败')
    }
    removeSkip(7)
  }
  await checkList()
})

const paperData = ref({
  userId: null,
  text: ''
})
const paperRef = ref(null)
const btnDisvisible = ref(false)

const Rules = {
  text: [
    { required: true, message: '请输入主题/知识点', trigger: 'blur' },
    { min: 1, max: 30, message: '长度在 1 到 30 个字符', trigger: 'blur' }
  ]
}

const task = ref({})
const taskProgress = ref({})

// ===================答题相关=====================
const isShow = ref(false)
const showPaperData = ref({
  id: null,
  paperName: '',
  status: null,
  createTime: '',
  paperInfo: null,
  multiple_choice: [],
  fill_blank: [],
  single_choice: [],
  judge: [],
  short_answer: []
})

const allQuestions = ref([])
const currentIndex = ref(0)
const userAnswers = ref({})
const questionResults = ref({})
const isAllCompleted = ref(false)
const showResult = ref(false)

const questionTypeMap = {
  'single_choice': '单选题',
  'multiple_choice': '多选题',
  'judge': '判断题',
  'fill_blank': '填空题',
  'short_answer': '简答题'
}

const currentQuestion = computed(() => {
  if (!allQuestions.value.length) return null
  return allQuestions.value[currentIndex.value] || null
})

const isCurrentAnswered = computed(() => {
  if (!currentQuestion.value) return false
  const q = currentQuestion.value
  const key = `${q.type}_${q.id}`
  const val = userAnswers.value[key]
  if (val === undefined || val === null) return false
  if (Array.isArray(val)) return val.length > 0
  return val !== ''
})

const isCurrentSubmitted = computed(() => {
  if (!currentQuestion.value) return false
  const q = currentQuestion.value
  const key = `${q.type}_${q.id}`
  return questionResults.value[key] !== undefined
})

const currentResult = computed(() => {
  if (!currentQuestion.value) return null
  const q = currentQuestion.value
  const key = `${q.type}_${q.id}`
  return questionResults.value[key] || null
})

const correctCount = computed(() => {
  let count = 0
  Object.values(questionResults.value).forEach(result => {
    if (result && result.is_correct === true) count++
  })
  return count
})

const totalQuestions = computed(() => allQuestions.value.length)

const accuracyRate = computed(() => {
  if (totalQuestions.value === 0) return 0
  return Math.round((correctCount.value / totalQuestions.value) * 100)
})

const completedCount = computed(() => Object.keys(questionResults.value).length)

const encouragementMessage = computed(() => {
  const rate = accuracyRate.value
  if (rate === 100) return '太棒了！满分通过！你是最优秀的！'
  if (rate >= 80) return '非常优秀！继续保持，你离学霸不远了！'
  if (rate >= 60) return '不错哦！再接再厉，你会越来越好！'
  if (rate >= 40) return '别灰心，多复习一下知识点，下次一定能更好！'
  return '每一次练习都是进步，加油！相信你可以的！'
})

const flattenQuestions = (data) => {
  const result = []
  const typeMap = {
    'single_choice': 'single_choice',
    'multiple_choice': 'multiple_choice',
    'judge': 'judge',
    'fill_blank': 'fill_blank',
    'short_answer': 'short_answer'
  }
  
  Object.keys(typeMap).forEach(key => {
    const list = data[key] || []
    list.forEach(item => {
      let options = []
      if (['single_choice', 'multiple_choice'].includes(key)) {
        const optionKeys = ['optionA', 'optionB', 'optionC', 'optionD', 'optionE', 'optionF']
        optionKeys.forEach(optKey => {
          if (item[optKey]) {
            let text = item[optKey]
            const match = text.match(/^[A-Z]\.\s*/)
            if (match) {
              text = text.substring(match[0].length)
            }
            options.push(text)
          }
        })
      }
      
      result.push({
        ...item,
        type: key,
        typeLabel: questionTypeMap[key],
        options: options.length > 0 ? options : (item.options || [])
      })
    })
  })
  return result
}

const getUserAnswerText = (question) => {
  const key = `${question.type}_${question.id}`
  const answer = userAnswers.value[key]
  if (answer === undefined || answer === null || answer === '') return '未作答'
  if (Array.isArray(answer)) {
    return answer.join(', ')
  }
  return String(answer)
}

const getCorrectAnswerText = (question) => {
  if (!question.answer) return '无'
  const answers = String(question.answer).split(',').map(a => a.trim())
  if (['single_choice', 'multiple_choice'].includes(question.type) && question.options && question.options.length > 0) {
    return answers.map(a => {
      const idx = a.charCodeAt(0) - 65
      if (idx >= 0 && idx < question.options.length) {
        return question.options[idx]
      }
      return a
    }).join('、')
  }
  return question.answer
}

// ===================答题函数=====================

const selectAnswer = (question, value) => {
  if (isCurrentSubmitted.value) return
  
  const key = `${question.type}_${question.id}`
  
  if (question.type === 'multiple_choice') {
    if (!userAnswers.value[key]) {
      userAnswers.value[key] = []
    }
    const arr = userAnswers.value[key]
    const index = arr.indexOf(value)
    if (index > -1) {
      arr.splice(index, 1)
    } else {
      arr.push(value)
    }
    if (arr.length === 0) {
      delete userAnswers.value[key]
    }
  } else {
    userAnswers.value[key] = value
  }
}

const isSelected = (question, value) => {
  const key = `${question.type}_${question.id}`
  const answer = userAnswers.value[key]
  if (!answer) return false
  if (Array.isArray(answer)) {
    return answer.includes(value)
  }
  return answer === value
}

const submitCurrentQuestion = async () => {
  if (!currentQuestion.value) return
  if (isCurrentSubmitted.value) {
    ElMessage.warning('本题已提交')
    return
  }
  
  const q = currentQuestion.value
  const key = `${q.type}_${q.id}`
  const userAnswer = userAnswers.value[key]
  
  if (userAnswer === undefined || userAnswer === null || userAnswer === '' || (Array.isArray(userAnswer) && userAnswer.length === 0)) {
    ElMessage.warning('请先作答')
    return
  }
  
  let submitData = {
    user_id: userId.value,
    question_type: q.type,
    question: {
      question: q.question,
      answer: q.answer
    },
    user_answer: Array.isArray(userAnswer) ? userAnswer.join(',') : String(userAnswer),
    knowledge_points: [],
    sessionId: showPaperData.value.paperInfo?.sessionId || 'none'
  }
  
  if (['single_choice', 'multiple_choice'].includes(q.type)) {
    const optionLabels = ['A', 'B', 'C', 'D', 'E', 'F']
    submitData.question.options = q.options.map((opt, idx) => {
      return optionLabels[idx] + '. ' + opt
    })
  }
  
  try {
    // 最后一题提交复习加一
    if(currentIndex.value + 1 == totalQuestions.value){
      if(showPaperData.value.paperInfo?.sessionId && (showPaperData.value.paperInfo.sessionId !== '' || showPaperData.value.paperInfo.sessionId !== 'none' || showPaperData.value.paperInfo.sessionId !== null)){
        const res = await reviewCountAddOneApi(userId.value)
        if(res.code){
          console.log('今日复习次数已增加')
          ElMessage.success('今日复习次数已增加')
        }else{
          console.log('后端错误，今日复习次数增加失败')
        }
      }
    }
    const result = await submitSingleQuestionApi(submitData)
    if (result.code === 1) {
      questionResults.value[key] = result.data
      ElMessage.success(result.data.message || '提交成功')
      checkAllCompleted()
    } else {
      ElMessage.error(result.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    ElMessage.error('提交失败，请重试')
  }
}

const checkAllCompleted = () => {
  const total = allQuestions.value.length
  const completed = Object.keys(questionResults.value).length
  if (completed >= total && total > 0) {
    isAllCompleted.value = true
    ElMessage.success('所有题目已完成！点击"查看结果"查看成绩')
  }
}

const nextQuestion = () => {
  // 检查当前题目是否已经作答
  if (!isCurrentAnswered.value) {
    ElMessage.warning('请先完成当前题目，才能进入下一题')
    return
  }
  
  // 检查当前题目是否已经提交
  if (!isCurrentSubmitted.value) {
    ElMessage.warning('请先提交当前题目，才能进入下一题')
    return
  }
  
  if (currentIndex.value < allQuestions.value.length - 1) {
    currentIndex.value++
  } else {
    if (isAllCompleted.value) {
      showResult.value = true
    } else {
      ElMessage.warning('还有题目未完成，请继续作答')
    }
  }
}

const prevQuestion = () => {
  if (currentIndex.value > 0) {
    currentIndex.value--
  }
}

const viewResult = () => {
  if (isAllCompleted.value) {
    showResult.value = true
  } else {
    ElMessage.warning('还有题目未完成')
  }
}

const quitShowHtml = () => {
  ElMessageBox.confirm('确定要关闭试卷吗？当前作答进度将不会被保存', '提示', {
    confirmButtonText: '确定关闭',
    cancelButtonText: '继续答题',
    type: 'warning'
  }).then(() => {
    isShow.value = false
    showResult.value = false
    isAllCompleted.value = false
    currentIndex.value = 0
    allQuestions.value = []
    userAnswers.value = {}
    questionResults.value = {}
    showPaperData.value = {
      id: null,
      paperName: '',
      status: null,
      createTime: '',
      paperInfo: null,
      multiple_choice: [],
      fill_blank: [],
      single_choice: [],
      judge: [],
      short_answer: []
    }
  }).catch(() => {})
}

const restartAnswer = () => {
  showResult.value = false
  currentIndex.value = 0
}

// ===================原有函数=====================

const isOpenList = (operation) => {
  if (operation == 0) {
    showList.value = [...allList.value]
  } else if (operation == 1) {
    showList.value = allList.value.slice(0, 20)
  } else {
    ElMessage.error('失败')
  }
}

const checkList = async() => {
  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i]
    if (item.status == 1 || item.status == null) {
      let nowNum = 0
      let maxNum = 40
      try {
        await getProgress(item.id)
        if (!taskProgress.value || Object.keys(taskProgress.value).length === 0) {
          ElMessage.error('获取生成进度失败')
        } else if (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == null) {
          await deleteItem(item.id, false)
          ElMessage.error('有生成项请求生成失败，直接删除')
          await getList()
          taskProgress.value = {}
        }
      } catch (e) {
        console.error('首次查询进度失败', e)
        continue
      }
      
      while (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == 1 && nowNum < maxNum) {
        nowNum++
        console.log(`任务 ${item.id} 生成中... 第 ${nowNum} 次轮询`)
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          console.log('获取进度次数：', nowNum)
          await getProgress(item.id)
        } catch (e) {
          console.error('轮询进度失败', e)
          break
        }
      }

      if (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == 2) {
        console.log(` ${item.id} 任务完成`)
        await getList()
        taskProgress.value = {}
      } else if (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == 3) {
        console.log(` ${item.id} 生成失败`)
        await getList()
        taskProgress.value = {}
      } else {
        console.log(` ${item.id} 未完成`)
        await getList()
        taskProgress.value = {}
      }
    }
  }
}

const submit = async () => {
  itemRef.value = []
  paperRef.value.validate(async(valid) => {
    if (valid) {
      paperData.value.userId = userId.value
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
        
        if (taskProgress.value.paperInfo && (taskProgress.value.paperInfo.status == 1 || taskProgress.value.paperInfo.status == null)) {
          let nowNum = 0
          let maxNum = 40

          try {
            await getProgress(task.value.id)
            if (!taskProgress.value || Object.keys(taskProgress.value).length === 0) {
              ElMessage.error('获取生成进度失败')
            } else if (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == null) {
              await deleteItem(task.value.id, false)
              ElMessage.error('生成请求失败，已删除')
              await getList()
              task.value = {}
              taskProgress.value = {}
            }
          } catch (e) {
            console.error('首次查询进度失败', e)
          }

          await getList()
          await getValue(task.value.id)
          
          while (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == 1 && nowNum < maxNum) {
            nowNum++
            console.log(`任务 ${task.value.id} 生成中... 第 ${nowNum} 次轮询`)
            await new Promise(resolve => setTimeout(resolve, 10000))
            try {
              console.log('获取进度次数：', nowNum)
              await getProgress(task.value.id)
            } catch (e) {
              console.error('轮询进度失败', e)
            }
          }

          if (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == 2) {
            console.log(` ${task.value.id} 任务完成`)
            await getList()
            await getValue(task.value.id)
            task.value = {}
            taskProgress.value = {}
          } else if (taskProgress.value.paperInfo && taskProgress.value.paperInfo.status == 3) {
            console.log(` ${task.value.id} 生成失败`)
            await getList()
            await getValue(task.value.id)
            task.value = {}
            taskProgress.value = {}
          } else {
            console.log(` ${task.value.id} 未完成`)
            await getList()
            await getValue(task.value.id)
            task.value = {}
            taskProgress.value = {}
          }
        } else if (taskProgress.value.paperInfo && (taskProgress.value.paperInfo.status == 2 || taskProgress.value.paperInfo.status == 3)) {
          await getList()
          await getValue(task.value.id)
          task.value = {}
          taskProgress.value = {}
        }
        btnDisvisible.value = false
        paperData.value = { userId: null, text: '' }
      } finally {
        clearTimeout(gameInvitationTimer)
      }
    } else {
      console.log('校验失败')
      return false
    }
  })
}

const getList = async () => {
  try {
    itemRef.value = []
    const result = await getPaperListApi(userId.value)
    if (result.code == 1) {
      allList.value = result.data || []
      allList.value.sort((a, b) => new Date(b.createTime) - new Date(a.createTime))
      showList.value = allList.value.slice(0, 20)
    } else {
      ElMessage.error(result.msg || '获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
    ElMessage.error('获取信息表失败')
  }
}

const getValue = async (id) => {
  try {
    const result = await pollPaperInfoApi(id)
    if (result.code) {
      const data = result.data
      showPaperData.value = {
        id: data.paperInfo?.id || id,
        paperName: data.paperInfo?.paperName || '',
        status: data.paperInfo?.status || null,
        createTime: data.paperInfo?.createTime || '',
        paperInfo: data.paperInfo,
        multiple_choice: data.multiple_choice || [],
        fill_blank: data.fill_blank || [],
        single_choice: data.single_choice || [],
        judge: data.judge || [],
        short_answer: data.short_answer || []
      }
      
      if (data.paperInfo?.status === 2) {
        allQuestions.value = flattenQuestions(data)
        currentIndex.value = 0
        userAnswers.value = {}
        questionResults.value = {}
        isAllCompleted.value = false
        showResult.value = false
      }
      
      isShow.value = true
    } else if(result.code === 2){
      ElMessage.error('未找到对应资源，可能已被删除')
    }
  } catch (e) {
    console.error('获取信息失败', e)
    ElMessage.error('获取信息失败')
  }
}

const deleteItem = async (id, isTip = true) => {
  if (isTip == true) {
    await ElMessageBox.confirm('是否删除该试卷？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  }
  try {
    const result = await deletePaperApi(id)
    if (result.code == 1) {
      ElMessage.success('删除成功')
      await getList()
    } else {
      ElMessage.error(result.msg || '删除失败')
    }
  } catch (e) {
    console.error('删除失败', e)
    ElMessage.error('删除失败')
  }
}

const createTask = async () => {
  try {
    const result = await generatePaperApi(paperData.value)
    if (result.code == 1) {
      task.value = result.data
      taskProgress.value = {
        paperInfo: { status: 1 }
      }
    } else {
      ElMessage.error(result.msg || '提交失败')
      btnDisvisible.value = false
    }
  } catch (e) {
    console.error('提交失败', e)
    ElMessage.error('提交失败')
    btnDisvisible.value = false
  }
}

const getProgress = async (id) => {
  try {
    const result = await pollPaperInfoApi(id)
    if (result.code == 1) {
      taskProgress.value = result.data
    } else {
      ElMessage.error(result.msg || '查询进度失败')
    }
  } catch (e) {
    console.error('查询进度失败', e)
    ElMessage.error('查询进度失败')
  }
}

// ===================数据=====================
const allList = ref([])
const showList = ref([])

const ingHtml = `<div style="max-width:800px; margin:20px auto; padding:20px; font-family:Microsoft YaHei; line-height:1.8; color:#333; background:#fff; border:1px solid #E2E8F0; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.1); min-height:297mm; display:flex; flex-direction:column; align-items:center; justify-content:center;">
  <div style="width:60px; height:60px; border:4px solid #DBEAFE; border-top-color:#2D7DDB; border-radius:50%; animation:spin 1s linear infinite; margin-bottom:20px;"></div>
  <h2 style="color:#2D7DDB; border-left:4px solid #2D7DDB; padding-left:12px; font-size:20px;">正在生成中，请稍候...</h2>
  <p style="color:#64748B; font-size:14px; margin-top:10px;">系统正在处理你的请求，请稍等片刻</p>
  <style>
    @keyframes spin { to { transform:rotate(360deg); } }
  </style>
</div>`

const failHtml = `<div style="max-width:800px; margin:20px auto; padding:20px; font-family:Microsoft YaHei; line-height:1.8; color:#333; background:#ffffff; min-height:297mm; display:flex; flex-direction:column; align-items:center; justify-content:center; border:1px solid #E2E8F0; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.08);">
  <div style="font-size:70px; color:#E53E3E; margin-bottom:24px; animation: shake 0.5s ease-in-out infinite alternate;">✕</div>
  <h2 style="color:#E53E3E; border-left:4px solid #E53E3E; padding-left:12px; font-size:22px; font-weight:bold; margin-bottom:16px;">生成失败</h2>
  <p style="color:#64748B; font-size:15px; text-align:center;">试卷生成过程中出现异常，请删除重试</p>
  <style>@keyframes shake{0%{transform:scale(1);opacity:0.8;}100%{transform:scale(1.1);opacity:1;}}</style>
</div>`
</script>

<template>
  <div class="container">
    <div class="title">
      <h1>智能试卷 智能生成</h1>
      <p class="subtitle">输入学习主题，一键生成理论题试卷</p>
    </div>

    <div class="main">
      <div class="top">
        <div class="inputBox">
          <el-form 
            :inline="true"
            :rules="Rules" 
            ref="paperRef" 
            :model="paperData" 
            class="reading-form"
            @keyup.enter.native="submit()"
          >
            <el-form-item class="input-field" label="主题/知识点" prop="text" style="width: 100%; max-width: 600px;">
             <el-input 
                v-model="paperData.text"
                show-word-limit 
                maxlength="30" 
                placeholder="例如：Java基础"
                clearable
                size="large"
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
                立即生成试卷
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="bottom">
        <div class="showMain" v-if="allList?.length">
          <el-scrollbar height="100%" width="100%">
            <div class="scroll-content">
              <div v-for="(item,index) in showList" 
                :key="item.id" @click="getValue(item.id)"  
                class="scrollbar-demo-item" 
                ref="itemRef"
              >
                <div class="normal" 
                  v-if="item.status == 2"
                  @mouseenter="handleEnter(index,item.id)"
                  @mouseleave="popStore.delayHidePop"
                >
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.paperName }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime }}
                    </div>
                  </div>
                  <div class="item-right" @click.stop="deleteItem(item.id)">
                    删除
                  </div>
                </div>

                <div class="loading" v-else-if="item.status == 1 || item.status == null">
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.paperName }}
                    </div>
                    <div class="item-ct">
                      {{ item.createTime }}
                    </div>
                  </div>
                  <div class="item-right">
                    <div class="loadingIcon">
                      <el-icon class="is-loading" :size="30" color="#2D7DDB"><Loading /></el-icon>
                    </div>
                    <div class="loadingText">
                      生成中
                    </div>
                  </div>
                </div>

                <div class="failure" v-else>
                  <div class="item-left">
                    <div class="item-text">
                      {{ item.paperName }}
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

              <div class="footer" v-if="allList.length > 20">
                <div @click="isOpenList(0)" class="text" v-if="allList?.length && allList.length != showList.length">查看更多</div>
                <div @click="isOpenList(1)" class="text" v-if="allList?.length && allList.length == showList.length">收起</div>
              </div>
            </div>
          </el-scrollbar>
        </div>

        <div class="main mainNull" v-else-if="!allList || allList.length === 0">
          <img src="@/assets/image/emptyStatus.png" alt="暂无信息">
          <div class="mainNullText">暂无生成内容</div>
        </div>
      </div>
    </div>
  </div>

  <!-- 预览页 -->
  <Transition name="fade-slide" mode="out-in">
    <div class="see" v-if="isShow == true">
      <div class="quit" @click="quitShowHtml()">
        <svg t="1779873458576" class="icon" viewBox="0 0 1025 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="5824" width="40" height="40"><path d="M1001.65696 463.424l-332.224-332.416C648.76096 110.4 624.05696 104.256 598.52096 113.792c-26.176 9.856-41.152 33.28-41.216 64.384L557.30496 328.32 492.28096 328.32 305.65696 328.384C266.48896 328.512 239.16096 355.712 239.03296 394.624c-0.128 78.4-0.128 156.736 0 235.072 0.128 37.696 27.776 65.28 65.792 65.664l252.48 0.064L557.24096 724.48c-0.128 40.768-0.256 81.408 0.576 122.112 0.256 15.936 6.528 33.28 16.256 45.184 11.904 14.656 28.224 22.72 45.952 22.72l0 0c17.536 0 35.2-8 49.728-22.464 110.848-110.72 221.568-221.504 332.288-332.352C1031.60896 530.176 1031.48096 493.248 1001.65696 463.424z" p-id="5825" fill="#ffffff"></path><path d="M387.70496 805.696 387.64096 805.696l-72.576 0.128-103.872-0.064c-52.48 0-82.624-30.144-82.624-82.688L128.56896 300.48c0-52.416 30.144-82.496 82.752-82.496l68.8-0.064 75.584 0.064 42.048-0.064c30.08 0 46.528-15.104 48.896-44.8 0.896-11.072 0.64-22.336 0.256-34.88C446.13696 106.944 428.60096 89.664 397.68896 89.6L321.33696 89.6C280.44096 89.6 239.54496 89.6 198.71296 89.856 186.16896 89.92 173.30496 91.328 160.44096 94.08 68.21696 113.728 0.88896 196.416 0.37696 290.688 0.12096 341.504 0.18496 392.384 0.24896 443.136l0.064 67.648L0.18496 581.76C0.12096 632.768-0.00704 683.712 0.44096 734.784c0.896 107.776 88.768 197.056 195.904 199.04 26.368 0.512 52.8 0.64 79.168 0.64l125.376-0.256c24.768 0 42.112-15.04 45.184-39.232 1.088-8.832 1.216-17.856 1.28-26.88l0-4.48c0.128-13.312 0.256-31.552-12.544-44.48C422.45696 806.784 404.66496 805.696 387.70496 805.696z" p-id="5826" fill="#ffffff"></path></svg>
        <div>退出</div>
      </div>
      <el-scrollbar height="100%" width="100%">
        <div class="scroll-content">
          <!-- 成功项 - 答题模式 -->
          <div class="content" v-if="showPaperData.status == 2 && !showResult"> 
            <div class="title">
              <div class="title-text">{{ showPaperData.paperName }}</div>
              <div class="title-ct">生成时间：{{ showPaperData.createTime }}</div>
            </div>
            
            <div class="progress-bar">
              <div class="progress-info">
                <span>进度：{{ completedCount }}/{{ totalQuestions }}</span>
                <span>正确：{{ correctCount }}</span>
                <span v-if="isAllCompleted" class="complete-tag">全部完成</span>
              </div>
              <el-progress :percentage="totalQuestions > 0 ? Math.round(completedCount / totalQuestions * 100) : 0" :stroke-width="8" />
            </div>

            <div class="question-nav">
              <el-button 
                size="small" 
                @click="prevQuestion" 
                :disabled="currentIndex === 0"
              >
                上一题
              </el-button>
              <span class="nav-info">第 {{ currentIndex + 1 }} / {{ totalQuestions }} 题</span>
              <el-button 
                size="small" 
                type="primary" 
                @click="nextQuestion"
                :disabled="(currentIndex === totalQuestions - 1 && !isAllCompleted) || !isCurrentAnswered || !isCurrentSubmitted"
              >
                {{ currentIndex === totalQuestions - 1 ? (isAllCompleted ? '查看结果' : '完成') : '下一题' }}
              </el-button>
            </div>

            <div class="question-container" v-if="currentQuestion">
              <div class="question-header">
                <span class="question-type">{{ currentQuestion.typeLabel }}</span>
                <span class="question-number">第 {{ currentIndex + 1 }} 题</span>
                <span class="question-status" :class="{ submitted: isCurrentSubmitted }">
                  {{ isCurrentSubmitted ? '已提交' : '待提交' }}
                </span>
              </div>
              <div class="question-text">{{ currentQuestion.question }}</div>
              
              <!-- 选择题选项 -->
              <div class="options-container" v-if="['single_choice', 'multiple_choice'].includes(currentQuestion.type)">
                <div 
                  v-for="(optText, idx) in currentQuestion.options" 
                  :key="idx"
                  class="option-item"
                  :class="{
                    selected: isSelected(currentQuestion, String.fromCharCode(65 + idx)),
                    correct: isCurrentSubmitted && currentResult && currentResult.is_correct && currentResult.correct_answer && currentResult.correct_answer.includes(String.fromCharCode(65 + idx)),
                    wrong: isCurrentSubmitted && currentResult && !currentResult.is_correct && isSelected(currentQuestion, String.fromCharCode(65 + idx)),
                    'correct-show': isCurrentSubmitted && currentResult && currentResult.correct_answer && currentResult.correct_answer.includes(String.fromCharCode(65 + idx)) && !isSelected(currentQuestion, String.fromCharCode(65 + idx))
                  }"
                  @click="!isCurrentSubmitted && selectAnswer(currentQuestion, String.fromCharCode(65 + idx))"
                >
                  <span class="option-label">{{ String.fromCharCode(65 + idx) }}.</span>
                  <span class="option-text">{{ optText }}</span>
                  <span v-if="isCurrentSubmitted && currentResult && currentResult.correct_answer && currentResult.correct_answer.includes(String.fromCharCode(65 + idx))" class="option-mark">✓</span>
                </div>
                <div v-if="currentQuestion.type === 'multiple_choice'" class="multi-hint">（多选题，可多选）</div>
              </div>

              <!-- 判断题 -->
              <div class="judge-container" v-if="currentQuestion.type === 'judge'">
                <div class="judge-options">
                  <el-button 
                    :type="isSelected(currentQuestion, '正确') ? 'success' : 'default'"
                    :plain="!isSelected(currentQuestion, '正确')"
                    @click="!isCurrentSubmitted && selectAnswer(currentQuestion, '正确')"
                    :disabled="isCurrentSubmitted"
                  >
                    正确
                  </el-button>
                  <el-button 
                    :type="isSelected(currentQuestion, '错误') ? 'danger' : 'default'"
                    :plain="!isSelected(currentQuestion, '错误')"
                    @click="!isCurrentSubmitted && selectAnswer(currentQuestion, '错误')"
                    :disabled="isCurrentSubmitted"
                  >
                    错误
                  </el-button>
                </div>
              </div>

              <!-- 填空题 -->
              <div class="fill-container" v-if="currentQuestion.type === 'fill_blank'">
                <el-input 
                  :model-value="userAnswers[`${currentQuestion.type}_${currentQuestion.id}`] || ''"
                  placeholder="请输入你的答案..."
                  :disabled="isCurrentSubmitted"
                  @update:model-value="(val) => { 
                    const key = `${currentQuestion.type}_${currentQuestion.id}`; 
                    if (val) { userAnswers[key] = val; } else { delete userAnswers[key]; } 
                  }"
                />
              </div>

              <!-- 简答题 -->
              <div class="short-container" v-if="currentQuestion.type === 'short_answer'">
                <el-input 
                  :model-value="userAnswers[`${currentQuestion.type}_${currentQuestion.id}`] || ''"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入你的答案..."
                  :disabled="isCurrentSubmitted"
                  @update:model-value="(val) => { 
                    const key = `${currentQuestion.type}_${currentQuestion.id}`; 
                    if (val) { userAnswers[key] = val; } else { delete userAnswers[key]; } 
                  }"
                />
              </div>

              <div class="result-container" v-if="isCurrentSubmitted && currentResult">
                <div class="result-box" :class="{ correct: currentResult.is_correct, wrong: !currentResult.is_correct }">
                  <div class="result-icon">{{ currentResult.is_correct ? '✓' : '✗' }}</div>
                  <div class="result-detail">
                    <div class="result-message">{{ currentResult.message || (currentResult.is_correct ? '回答正确！' : '回答错误') }}</div>
                    <div class="result-answer" v-if="!currentResult.is_correct">
                      正确答案：{{ getCorrectAnswerText(currentQuestion) }}
                    </div>
                    <div class="result-answer" v-if="!currentResult.is_correct && currentResult.user_answer">
                      你的答案：{{ getUserAnswerText(currentQuestion) }}
                    </div>
                    <div class="result-score">得分：{{ currentResult.score || 0 }} 分</div>
                  </div>
                </div>
              </div>

              <div class="submit-area" v-if="!isCurrentSubmitted">
                <el-button 
                  type="primary" 
                  size="large"
                  @click="submitCurrentQuestion"
                  :disabled="!isCurrentAnswered"
                >
                  提交答案
                </el-button>
                <span v-if="!isCurrentAnswered" class="hint-text">请先选择/填写答案</span>
              </div>
            </div>

            <!-- 底部查看结果按钮（全部完成后显示） -->
            <div class="bottom-actions" v-if="isAllCompleted">
              <el-button type="success" size="large" @click="viewResult">
                查看结果
              </el-button>
            </div>
          </div>

          <!-- 结果页 -->
          <div class="content result-page" v-if="showPaperData.status == 2 && showResult">
            <div class="title">
              <div class="title-text">{{ showPaperData.paperName }}</div>
              <div class="title-ct">生成时间：{{ showPaperData.createTime }}</div>
            </div>

            <div class="result-summary">
              <div class="result-cards">
                <div class="result-card">
                  <div class="card-label">总题数</div>
                  <div class="card-value">{{ totalQuestions }}</div>
                </div>
                <div class="result-card">
                  <div class="card-label">正确数</div>
                  <div class="card-value">{{ correctCount }}</div>
                </div>
                <div class="result-card">
                  <div class="card-label">错误数</div>
                  <div class="card-value">{{ totalQuestions - correctCount }}</div>
                </div>
              </div>

              <div class="progress-rings">
                <div class="ring-item">
                  <el-progress 
                    type="circle" 
                    :percentage="accuracyRate" 
                    :width="140"
                    :stroke-width="8"
                    :color="accuracyRate >= 80 ? '#67C23A' : accuracyRate >= 60 ? '#E6A23C' : '#F56C6C'"
                  >
                    <template #default="{ percentage }">
                      <span class="percentage-value">{{ percentage }}%</span>
                    </template>
                  </el-progress>
                  <div class="ring-label">正确率</div>
                </div>
                <div class="ring-item">
                  <el-progress 
                    type="circle" 
                    :percentage="Math.round(correctCount / totalQuestions * 100)" 
                    :width="140"
                    :stroke-width="8"
                    color="#409EFF"
                  >
                    <template #default="{ percentage }">
                      <span class="percentage-value">{{ correctCount }}/{{ totalQuestions }}</span>
                    </template>
                  </el-progress>
                  <div class="ring-label">答对题数</div>
                </div>
              </div>
            </div>

            <div class="encouragement">
              <div class="encourage-text">{{ encouragementMessage }}</div>
              <div class="wrong-note">错题已经自动移入错题本</div>
            </div>

            <div class="wrong-review" v-if="Object.keys(questionResults).some(k => questionResults[k] && !questionResults[k].is_correct)">
              <h4>错题回顾</h4>
              <div 
                v-for="(q, idx) in allQuestions.filter(q => questionResults[`${q.type}_${q.id}`] && !questionResults[`${q.type}_${q.id}`].is_correct)" 
                :key="idx"
                class="wrong-item"
              >
                <div class="wrong-question">{{ idx + 1 }}. {{ q.question }}</div>
                <div class="wrong-answer">正确答案：{{ getCorrectAnswerText(q) }}</div>
                <div class="wrong-user-answer">你的答案：{{ getUserAnswerText(q) }}</div>
              </div>
            </div>

            <div class="bottom-actions">
              <el-button @click="restartAnswer">返回答题</el-button>
              <el-button type="primary" @click="quitShowHtml">关闭试卷</el-button>
            </div>
          </div>

          <!-- 生成项 -->
          <div class="content" v-if="showPaperData.status == 1"> 
            <div class="title">
              <div class="title-text">{{ showPaperData.paperName }}</div>
              <div class="title-ct">生成时间：{{ showPaperData.createTime }}</div>
            </div>
            <div v-html="ingHtml"></div>
          </div>

          <!-- 失败项 -->
          <div class="content" v-if="showPaperData.status == 3"> 
            <div class="title">
              <div class="title-text">{{ showPaperData.paperName }}</div>
              <div class="title-ct">生成时间：{{ showPaperData.createTime }}</div>
            </div>
            <div v-html="failHtml"></div>
          </div>
        </div>
      </el-scrollbar>
    </div>
  </Transition>
</template>

<style scoped>
/* ================= 页面过渡动画 ================= */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.5s ease-in-out;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.98);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.98);
}

.container {
  width: 100%;
  height: 100%;
  background: transparent;
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
  width: 100%;
  height: 75vh;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 10px;
}
.top {
  width: 100%;
  padding: 0;
  display: flex;
  justify-content: center;
}
.bottom {
  width: 100%;
  padding: 0;
  flex: 1;
  overflow: hidden;
}

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

.reading-form {
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

.bottom .showMain {
  margin: 0 auto;
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

.bottom .item-left {
  max-width: 1000px;
}
.bottom .normal .item-left {
  max-width: 1000px;
}
.scrollbar-demo-item>div {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.bottom .item-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-body);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bottom .normal .item-ct {
  font-size: 14px;
  color: var(--text-normal);
}

.scrollbar-demo-item .loading{
  animation: pulse 1.5s infinite ease-in-out;
}
.bottom .loading .loadingIcon {
  width: 50px;
  height: 100%;
}
.bottom .loading .loadingText {
  width: 65px;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  animation: none;
}
.bottom .loading .item-right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
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
  animation: dots 1.5s steps(5, end) infinite;
}
.overBox .el-icon.is-loading {
  color: var(--text-body);
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
@keyframes dots {
  0%, 20% { content: '.'; }
  40% { content: '..'; }
  60%, 100% { content: '...'; }
}

.fail {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--main-delete);
}
.fail .shake-icon {
  color: var(--main-delete);
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
  animation-delay: 0.3s;
}

.bottom .failure .item-text {
  animation: shake 0.82s cubic-bezier(.36,.07,.19,.97) both;
}
.bottom .failure .item-ct {
  animation: fade-in-up 0.5s ease-out;
}
.bottom .failure .boxRight {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 60px;
}

@keyframes shake {
  10%, 90% { transform: translate3d(-1px, 0, 0); }
  20%, 80% { transform: translate3d(2px, 0, 0); }
  30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
  40%, 60% { transform: translate3d(4px, 0, 0); }
}
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

.bottom .normal .item-right:hover,
.bottom .failure .item-right:hover {
  cursor: pointer;
  text-decoration: underline;
  color: var(--main-delete);
  transition: all 0.3s;
}
.bottom .scrollbar-demo-item:has(.normal):hover,
.bottom .scrollbar-demo-item:has(.loading):hover {
  cursor: pointer;
  box-shadow: var(--shadow-brand);
  transform: translateY(-3px);
  border-color: var(--primary);
}
.bottom .scrollbar-demo-item:has(.failure):hover {
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

.bottom .footer {
  left: 5%;
  bottom: 0;
  z-index: 1;
  width: 90%;
  height: 10%;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background: transparent;
}
.footer .text {
  font-size: 18px;
  color: var(--text-gray);
}
.footer .text:hover {
  text-decoration: underline;
  color: var(--primary);
  cursor: pointer;
}

/* ================= 预览页样式 ================= */
.see {
  z-index: 2;
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: var(--bgc-transparent);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.3s ease;
}
.see .content {
  padding: 80px 20px;
  margin: 0 auto;
  width: 78%;
  background-color: var(--bg-page);
  border-radius: 12px;
}
.see .scroll-content {
  padding: 50px 60px 50px 60px;
}
.see .quit {
  z-index: 2;
  position: absolute;
  top: 40px;
  right: 40px;
}
.see .quit:hover {
  cursor: pointer;
}
.see .quit svg path {
  fill: var(--text-body) !important;
}
.see .quit:hover svg path {
  fill: var(--main-delete) !important;
}
.see .quit > div {
  color: var(--text-body);
}
.see .quit:hover > div {
  color: var(--main-delete);
}
.see .content .title .title-text {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
}

/* ================= 答题样式 ================= */
.progress-bar {
  margin-bottom: 20px;
  padding: 12px 20px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-gray);
}
.complete-tag {
  color: #67C23A;
  font-weight: 700;
}

.question-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}
.nav-info {
  font-size: 14px;
  color: var(--text-gray);
  font-weight: 500;
}

.question-container {
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 12px;
  border: 1px solid var(--border-color);
}
.question-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.question-type {
  padding: 2px 12px;
  background: var(--primary);
  color: #fff;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
}
.question-number {
  font-size: 14px;
  color: var(--text-gray);
}
.question-status {
  font-size: 13px;
  color: var(--text-gray);
}
.question-status.submitted {
  color: #67C23A;
}
.question-text {
  font-size: 17px;
  font-weight: 500;
  color: var(--text-title);
  margin-bottom: 16px;
  line-height: 1.6;
}

.options-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.option-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border: 2px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}
.option-item:hover:not(.correct):not(.wrong):not(.correct-show) {
  border-color: var(--primary);
  background: rgba(45, 125, 219, 0.05);
}
.option-item.selected {
  border-color: var(--primary);
  background: rgba(45, 125, 219, 0.08);
}
.option-item.correct {
  border-color: #67C23A;
  background: rgba(103, 194, 58, 0.12);
}
.option-item.wrong {
  border-color: #F56C6C;
  background: rgba(245, 108, 108, 0.12);
}
.option-item.correct-show {
  border-color: #67C23A;
  background: rgba(103, 194, 58, 0.08);
}
.option-label {
  font-weight: 600;
  margin-right: 8px;
  color: var(--text-gray);
}
.option-text {
  flex: 1;
  color: var(--text-body);
}
.option-mark {
  color: #67C23A;
  font-weight: 700;
  font-size: 18px;
}
.multi-hint {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 6px;
}

.judge-container {
  display: flex;
  justify-content: center;
  gap: 30px;
  padding: 10px 0;
}
.judge-options {
  display: flex;
  gap: 20px;
}
.judge-options .el-button {
  min-width: 120px;
  font-size: 16px;
}

.fill-container, .short-container {
  padding: 6px 0;
}
:deep(.fill-container .el-input__inner) {
  font-size: 15px;
}
:deep(.short-container .el-textarea__inner) {
  font-size: 15px;
}

.result-container {
  margin-top: 16px;
}
.result-box {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 8px;
  border: 2px solid;
}
.result-box.correct {
  border-color: #67C23A;
  background: rgba(103, 194, 58, 0.08);
}
.result-box.wrong {
  border-color: #F56C6C;
  background: rgba(245, 108, 108, 0.08);
}
.result-icon {
  font-size: 32px;
  line-height: 1;
}
.result-detail {
  flex: 1;
}
.result-message {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-title);
}
.result-answer {
  font-size: 14px;
  color: var(--text-gray);
  margin-top: 4px;
}
.result-score {
  font-size: 14px;
  color: var(--primary);
  margin-top: 4px;
  font-weight: 500;
}

.submit-area {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
}
.hint-text {
  font-size: 13px;
  color: var(--text-gray);
}

.bottom-actions {
  margin-top: 24px;
  display: flex;
  justify-content: center;
  gap: 16px;
}

/* ================= 结果页样式 ================= */
.result-page .result-summary {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
}
.result-cards {
  display: flex;
  gap: 40px;
  margin-bottom: 30px;
}
.result-card {
  text-align: center;
  padding: 12px 30px;
  background: var(--el-fill-color-light);
  border-radius: 10px;
  min-width: 80px;
}
.card-label {
  font-size: 14px;
  color: var(--text-gray);
}
.card-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-title);
  margin-top: 4px;
}

.progress-rings {
  display: flex;
  gap: 60px;
  justify-content: center;
  margin: 10px 0;
}
.ring-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.ring-label {
  margin-top: 8px;
  font-size: 14px;
  color: var(--text-gray);
}
.percentage-value {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
}

.encouragement {
  text-align: center;
  padding: 20px;
  margin: 10px 0;
  background: linear-gradient(135deg, rgba(45, 125, 219, 0.08), rgba(103, 194, 58, 0.08));
  border-radius: 12px;
  border: 1px solid var(--border-color);
}
.encourage-text {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 8px;
}
.wrong-note {
  font-size: 14px;
  color: var(--text-gray);
}

.wrong-review {
  margin-top: 20px;
  padding: 16px 20px;
  background: rgba(245, 108, 108, 0.06);
  border-radius: 10px;
  border: 1px solid rgba(245, 108, 108, 0.2);
}
.wrong-review h4 {
  color: #F56C6C;
  margin-bottom: 12px;
}
.wrong-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}
.wrong-item:last-child {
  border-bottom: none;
}
.wrong-question {
  font-weight: 500;
  color: var(--text-body);
}
.wrong-answer {
  color: #67C23A;
  font-size: 14px;
}
.wrong-user-answer {
  color: #F56C6C;
  font-size: 14px;
}

/* ================= 响应式 ================= */
@media (max-width: 768px) {
  .top .inputBox {
    width: 95%;
    padding: 16px;
  }
  .reading-form {
    flex-direction: column;
    align-items: center;
  }
  .see .content {
    width: 96%;
    padding: 40px 16px;
  }
  .see .scroll-content {
    padding: 20px;
  }
  .result-cards {
    gap: 16px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .progress-rings {
    gap: 30px;
    flex-wrap: wrap;
  }
  .question-nav {
    flex-wrap: wrap;
  }
}

/* ============ 夜间模式适配 ============ */

/* 答题区域 */
.dark .progress-bar {
  background: var(--bg-card);
}

.dark .question-container {
  background: var(--bg-card);
}

/* 选项悬停和选中状态 */
.dark .option-item:hover:not(.correct):not(.wrong):not(.correct-show) {
  background: rgba(59, 130, 246, 0.15);
}

.dark .option-item.selected {
  background: rgba(59, 130, 246, 0.2);
}

/* 结果卡片 */
.dark .result-card {
  background: var(--bg-card);
}

/* 错题回顾 */
.dark .wrong-review {
  background: rgba(245, 108, 108, 0.1);
}

</style>
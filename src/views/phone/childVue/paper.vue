<!-- 移动端试卷组件 -->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showLoadingToast, showSuccessToast, showFailToast } from 'vant'
import { getPaperListApi, generatePaperApi, pollPaperInfoApi, deletePaperApi, submitSingleQuestionApi } from '@/api/mainApi/resourcePaper.js'
import { reviewCountAddOneApi } from '@/api/mainApi/layout.js'
import { isSkip, removeSkip } from '@/utils/skip.js'

const router = useRouter()

// =================== 用户 =====================
let loginUser = null
const userId = ref(null)

onMounted(async () => {
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
  // 检查是否有跳转信息需要自动打开试卷
  const skipInfo = isSkip(7)
  if (skipInfo && skipInfo.resourceId) {
    await getValue(skipInfo.resourceId)
    removeSkip(7)
  }
  await checkList()
})

// =================== 数据 =====================
const allList = ref([])
const showList = ref([])
const paperData = ref({ userId: null, text: '' })
const btnDisvisible = ref(false)

// =================== 答题相关 =====================
const isShow = ref(false)
const showPaperData = ref({
  id: null, paperName: '', status: null, createTime: '', paperInfo: null,
  multiple_choice: [], fill_blank: [], single_choice: [], judge: [], short_answer: []
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
  const key = `${currentQuestion.value.type}_${currentQuestion.value.id}`
  return questionResults.value[key] !== undefined
})

const currentResult = computed(() => {
  if (!currentQuestion.value) return null
  const key = `${currentQuestion.value.type}_${currentQuestion.value.id}`
  return questionResults.value[key] || null
})

const correctCount = computed(() => {
  let count = 0
  Object.values(questionResults.value).forEach(r => { if (r && r.is_correct === true) count++ })
  return count
})

const totalQuestions = computed(() => allQuestions.value.length)
const accuracyRate = computed(() => totalQuestions.value === 0 ? 0 : Math.round((correctCount.value / totalQuestions.value) * 100))
const completedCount = computed(() => Object.keys(questionResults.value).length)

const encouragementMessage = computed(() => {
  const rate = accuracyRate.value
  if (rate === 100) return '太棒了！满分通过！'
  if (rate >= 80) return '非常优秀！继续保持！'
  if (rate >= 60) return '不错哦！再接再厉！'
  if (rate >= 40) return '别灰心，多复习一下！'
  return '每一次练习都是进步，加油！'
})

const flattenQuestions = (data) => {
  const result = []
  const typeMap = { 'single_choice': 'single_choice', 'multiple_choice': 'multiple_choice', 'judge': 'judge', 'fill_blank': 'fill_blank', 'short_answer': 'short_answer' }
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
            if (match) text = text.substring(match[0].length)
            options.push(text)
          }
        })
      }
      result.push({ ...item, type: key, typeLabel: questionTypeMap[key], options: options.length > 0 ? options : (item.options || []) })
    })
  })
  return result
}

const getUserAnswerText = (question) => {
  const key = `${question.type}_${question.id}`
  const answer = userAnswers.value[key]
  if (answer === undefined || answer === null || answer === '') return '未作答'
  if (Array.isArray(answer)) return answer.join(', ')
  return String(answer)
}

const getCorrectAnswerText = (question) => {
  if (!question.answer) return '无'
  const answers = String(question.answer).split(',').map(a => a.trim())
  if (['single_choice', 'multiple_choice'].includes(question.type) && question.options && question.options.length > 0) {
    return answers.map(a => {
      const idx = a.charCodeAt(0) - 65
      if (idx >= 0 && idx < question.options.length) return question.options[idx]
      return a
    }).join('、')
  }
  return question.answer
}

// =================== 答题函数 =====================
const selectAnswer = (question, value) => {
  if (isCurrentSubmitted.value) return
  const key = `${question.type}_${question.id}`
  if (question.type === 'multiple_choice') {
    if (!userAnswers.value[key]) userAnswers.value[key] = []
    const arr = userAnswers.value[key]
    const index = arr.indexOf(value)
    if (index > -1) arr.splice(index, 1)
    else arr.push(value)
    if (arr.length === 0) delete userAnswers.value[key]
  } else {
    userAnswers.value[key] = value
  }
}

const isSelected = (question, value) => {
  const key = `${question.type}_${question.id}`
  const answer = userAnswers.value[key]
  if (!answer) return false
  if (Array.isArray(answer)) return answer.includes(value)
  return answer === value
}

const submitCurrentQuestion = async () => {
  if (!currentQuestion.value) return
  if (isCurrentSubmitted.value) { showToast('本题已提交'); return }
  const q = currentQuestion.value
  const key = `${q.type}_${q.id}`
  const userAnswer = userAnswers.value[key]
  if (userAnswer === undefined || userAnswer === null || userAnswer === '' || (Array.isArray(userAnswer) && userAnswer.length === 0)) {
    showToast('请先作答'); return
  }
  let submitData = {
    user_id: userId.value, question_type: q.type,
    question: { question: q.question, answer: q.answer },
    user_answer: Array.isArray(userAnswer) ? userAnswer.join(',') : String(userAnswer),
    knowledge_points: [], sessionId: showPaperData.value.paperInfo?.sessionId || 'none'
  }
  if (['single_choice', 'multiple_choice'].includes(q.type)) {
    const optionLabels = ['A', 'B', 'C', 'D', 'E', 'F']
    submitData.question.options = q.options.map((opt, idx) => optionLabels[idx] + '. ' + opt)
  }
  try {
    if (currentIndex.value + 1 == totalQuestions.value) {
      if (showPaperData.value.paperInfo?.sessionId && (showPaperData.value.paperInfo.sessionId !== '' || showPaperData.value.paperInfo.sessionId !== 'none' || showPaperData.value.paperInfo.sessionId !== null)) {
        const res = await reviewCountAddOneApi(userId.value)
        if (res.code) showToast('今日复习次数已增加')
      }
    }
    const result = await submitSingleQuestionApi(submitData)
    if (result.code === 1) {
      questionResults.value[key] = result.data
      showSuccessToast(result.data.message || '提交成功')
      checkAllCompleted()
    } else {
      showFailToast(result.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败，请重试')
  }
}

const checkAllCompleted = () => {
  const total = allQuestions.value.length
  const completed = Object.keys(questionResults.value).length
  if (completed >= total && total > 0) {
    isAllCompleted.value = true
    showToast('所有题目已完成！')
  }
}

const nextQuestion = () => {
  if (!isCurrentAnswered.value) { showToast('请先完成当前题目'); return }
  if (!isCurrentSubmitted.value) { showToast('请先提交当前题目'); return }
  if (currentIndex.value < allQuestions.value.length - 1) {
    currentIndex.value++
  } else {
    if (isAllCompleted.value) showResult.value = true
    else showToast('还有题目未完成')
  }
}

const prevQuestion = () => { if (currentIndex.value > 0) currentIndex.value-- }

const viewResult = () => {
  if (isAllCompleted.value) showResult.value = true
  else showToast('还有题目未完成')
}

const quitShowHtml = async () => {
  try {
    await showConfirmDialog({ title: '提示', message: '确定要关闭试卷吗？当前作答进度将不会被保存' })
    isShow.value = false
    showResult.value = false
    isAllCompleted.value = false
    currentIndex.value = 0
    allQuestions.value = []
    userAnswers.value = {}
    questionResults.value = {}
    showPaperData.value = { id: null, paperName: '', status: null, createTime: '', paperInfo: null, multiple_choice: [], fill_blank: [], single_choice: [], judge: [], short_answer: [] }
  } catch (e) { /* 取消 */ }
}

const restartAnswer = () => { showResult.value = false; currentIndex.value = 0 }

// =================== 列表与生成 =====================
const getList = async () => {
  try {
    const result = await getPaperListApi(userId.value)
    if (result.code == 1) {
      allList.value = result.data || []
      allList.value.sort((a, b) => new Date(b.createTime) - new Date(a.createTime))
      showList.value = allList.value.slice(0, 20)
    } else {
      showFailToast(result.msg || '获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
    showFailToast('获取信息表失败')
  }
}

const getValue = async (id) => {
  try {
    const result = await pollPaperInfoApi(id)
    if (result.code) {
      const data = result.data
      showPaperData.value = {
        id: data.paperInfo?.id || id, paperName: data.paperInfo?.paperName || '',
        status: data.paperInfo?.status || null, createTime: data.paperInfo?.createTime || '',
        paperInfo: data.paperInfo,
        multiple_choice: data.multiple_choice || [], fill_blank: data.fill_blank || [],
        single_choice: data.single_choice || [], judge: data.judge || [], short_answer: data.short_answer || []
      }
      if (data.paperInfo?.status === 2) {
        allQuestions.value = flattenQuestions(data)
        currentIndex.value = 0; userAnswers.value = {}; questionResults.value = {}
        isAllCompleted.value = false; showResult.value = false
      }
      isShow.value = true
    } else if (result.code === 2) {
      showFailToast('未找到对应资源，可能已被删除')
    }
  } catch (e) {
    console.error('获取信息失败', e)
    showFailToast('获取信息失败')
  }
}

const deleteItem = async (id) => {
  try {
    await showConfirmDialog({ title: '提示', message: '是否删除该试卷？' })
    const result = await deletePaperApi(id)
    if (result.code == 1) { showSuccessToast('删除成功'); await getList() }
    else showFailToast(result.msg || '删除失败')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      console.error('删除失败', e)
      showFailToast('删除失败')
    }
  }
}

const submit = async () => {
  if (!paperData.value.text || !paperData.value.text.trim()) {
    showToast('请输入主题/知识点'); return
  }
  if (paperData.value.text.length > 30) {
    showToast('长度不能超过30个字符'); return
  }
  btnDisvisible.value = true
  paperData.value.userId = userId.value
  try {
    const result = await generatePaperApi(paperData.value)
    if (result.code == 1) {
      const task = result.data
      showLoadingToast({ message: '生成中...', forbidClick: true, duration: 0 })
      await getList()
      await getValue(task.id)
      let nowNum = 0; const maxNum = 40
      while (nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          const progress = await pollPaperInfoApi(task.id)
          if (progress.code == 1) {
            if (progress.data.paperInfo?.status == 2) {
              showSuccessToast('生成完成')
              await getList(); await getValue(task.id); break
            } else if (progress.data.paperInfo?.status == 3) {
              showFailToast('生成失败')
              await getList(); await getValue(task.id); break
            }
          }
        } catch (e) { console.error('轮询进度失败', e) }
      }
    } else {
      showFailToast(result.msg || '提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败')
  } finally {
    btnDisvisible.value = false
    paperData.value = { userId: null, text: '' }
    // 关闭 loading toast
    showLoadingToast({ message: '', duration: 0 })
  }
}

const checkList = async () => {
  for (let i = 0; i < allList.value.length; i++) {
    const item = allList.value[i]
    if (item.status == 1 || item.status == null) {
      let nowNum = 0; const maxNum = 40
      try {
        const progress = await pollPaperInfoApi(item.id)
        if (progress.code == 1) {
          if (progress.data.paperInfo && progress.data.paperInfo.status == null) {
            await deleteItem(item.id); await getList(); continue
          }
        }
      } catch (e) { continue }
      while (nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          const progress = await pollPaperInfoApi(item.id)
          if (progress.code == 1 && progress.data.paperInfo?.status == 2) {
            await getList(); break
          } else if (progress.code == 1 && progress.data.paperInfo?.status == 3) {
            await getList(); break
          }
        } catch (e) { break }
      }
    }
  }
}

const isOpenList = ref(false)
</script>

<template>
  <div class="phone-paper">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">智能试卷</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div v-if="!isShow" class="paper-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">智能试卷</h2>
        <p class="page-desc">输入学习主题，一键生成试卷</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="paperData.text"
          placeholder="例如：Java基础"
          maxlength="30"
          show-word-limit
          clearable
          class="paper-input"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="生成中..."
          @click="submit"
          class="submit-btn"
        >
          立即生成试卷
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
            @click="getValue(item.id)"
          >
            <div class="item-info">
              <div class="item-name">{{ item.paperName }}</div>
              <div class="item-time">{{ item.createTime }}</div>
            </div>
            <div class="item-actions">
              <van-icon v-if="item.status == 1 || item.status == null" name="loading" class="loading-icon" />
              <span v-if="item.status == 1 || item.status == null" class="status-text">生成中</span>
              <van-icon v-if="item.status == 3" name="warning-o" class="fail-icon" />
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

    <!-- 预览/答题页 -->
    <div v-if="isShow" class="paper-detail-page">
      <!-- 顶部操作栏 -->
      <div class="detail-nav">
        <van-icon name="arrow-left" size="20" @click="quitShowHtml" />
        <span class="detail-title">{{ showPaperData.paperName }}</span>
        <van-icon name="cross" size="20" @click="quitShowHtml" />
      </div>

      <!-- 生成中 -->
      <div v-if="showPaperData.status == 1" class="status-page">
        <van-loading type="spinner" color="var(--primary)" size="48" />
        <p class="status-text">正在生成中，请稍候...</p>
      </div>

      <!-- 生成失败 -->
      <div v-if="showPaperData.status == 3" class="status-page">
        <van-icon name="warning-o" size="64" color="#F56C6C" />
        <p class="status-text fail-text">生成失败</p>
      </div>

      <!-- 答题模式 -->
      <div v-if="showPaperData.status == 2 && !showResult" class="answer-page">
        <!-- 进度条 -->
        <div class="progress-section">
          <div class="progress-info">
            <span>{{ completedCount }}/{{ totalQuestions }}</span>
            <span>正确：{{ correctCount }}</span>
          </div>
          <van-progress
            :percentage="totalQuestions > 0 ? Math.round(completedCount / totalQuestions * 100) : 0"
            :show-pivot="false"
            stroke-width="6"
            color="var(--primary)"
          />
        </div>

        <!-- 题目导航 -->
        <div class="question-nav">
          <van-button size="small" :disabled="currentIndex === 0" @click="prevQuestion">上一题</van-button>
          <span class="nav-info">{{ currentIndex + 1 }} / {{ totalQuestions }}</span>
          <van-button
            size="small" type="primary"
            :disabled="(currentIndex === totalQuestions - 1 && !isAllCompleted) || !isCurrentAnswered || !isCurrentSubmitted"
            @click="nextQuestion"
          >
            {{ currentIndex === totalQuestions - 1 ? (isAllCompleted ? '查看结果' : '完成') : '下一题' }}
          </van-button>
        </div>

        <!-- 题目内容 -->
        <div v-if="currentQuestion" class="question-card">
          <div class="question-header">
            <span class="q-type">{{ currentQuestion.typeLabel }}</span>
            <span class="q-status" :class="{ submitted: isCurrentSubmitted }">
              {{ isCurrentSubmitted ? '已提交' : '待提交' }}
            </span>
          </div>
          <div class="q-text">{{ currentQuestion.question }}</div>

          <!-- 选择/多选题 -->
          <div v-if="['single_choice', 'multiple_choice'].includes(currentQuestion.type)" class="options-list">
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
              <span class="opt-label">{{ String.fromCharCode(65 + idx) }}</span>
              <span class="opt-text">{{ optText }}</span>
              <van-icon v-if="isCurrentSubmitted && currentResult && currentResult.correct_answer && currentResult.correct_answer.includes(String.fromCharCode(65 + idx))" name="success" class="opt-mark" />
            </div>
            <div v-if="currentQuestion.type === 'multiple_choice'" class="multi-hint">（多选题，可多选）</div>
          </div>

          <!-- 判断题 -->
          <div v-if="currentQuestion.type === 'judge'" class="judge-options">
            <van-button
              :type="isSelected(currentQuestion, '正确') ? 'success' : 'default'"
              @click="!isCurrentSubmitted && selectAnswer(currentQuestion, '正确')"
              :disabled="isCurrentSubmitted"
            >正确</van-button>
            <van-button
              :type="isSelected(currentQuestion, '错误') ? 'danger' : 'default'"
              @click="!isCurrentSubmitted && selectAnswer(currentQuestion, '错误')"
              :disabled="isCurrentSubmitted"
            >错误</van-button>
          </div>

          <!-- 填空题 -->
          <div v-if="currentQuestion.type === 'fill_blank'" class="fill-input">
            <van-field
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
          <div v-if="currentQuestion.type === 'short_answer'" class="short-input">
            <van-field
              :model-value="userAnswers[`${currentQuestion.type}_${currentQuestion.id}`] || ''"
              type="textarea"
              rows="4"
              placeholder="请输入你的答案..."
              :disabled="isCurrentSubmitted"
              @update:model-value="(val) => {
                const key = `${currentQuestion.type}_${currentQuestion.id}`;
                if (val) { userAnswers[key] = val; } else { delete userAnswers[key]; }
              }"
            />
          </div>

          <!-- 提交结果 -->
          <div v-if="isCurrentSubmitted && currentResult" class="result-box" :class="{ correct: currentResult.is_correct, wrong: !currentResult.is_correct }">
            <div class="result-icon">{{ currentResult.is_correct ? '✓' : '✗' }}</div>
            <div class="result-detail">
              <div class="result-msg">{{ currentResult.message || (currentResult.is_correct ? '回答正确！' : '回答错误') }}</div>
              <div v-if="!currentResult.is_correct" class="result-answer">正确答案：{{ getCorrectAnswerText(currentQuestion) }}</div>
              <div v-if="!currentResult.is_correct && currentResult.user_answer" class="result-answer">你的答案：{{ getUserAnswerText(currentQuestion) }}</div>
              <div class="result-score">得分：{{ currentResult.score || 0 }} 分</div>
            </div>
          </div>

          <!-- 提交按钮 -->
          <div v-if="!isCurrentSubmitted" class="submit-area">
            <van-button type="primary" block :disabled="!isCurrentAnswered" @click="submitCurrentQuestion">
              提交答案
            </van-button>
          </div>
        </div>

        <!-- 全部完成 -->
        <div v-if="isAllCompleted" class="bottom-actions">
          <van-button type="success" block @click="viewResult">查看结果</van-button>
        </div>
      </div>

      <!-- 结果页 -->
      <div v-if="showPaperData.status == 2 && showResult" class="result-page">
        <div class="result-summary">
          <div class="result-cards">
            <div class="r-card">
              <div class="r-label">总题数</div>
              <div class="r-value">{{ totalQuestions }}</div>
            </div>
            <div class="r-card">
              <div class="r-label">正确数</div>
              <div class="r-value">{{ correctCount }}</div>
            </div>
            <div class="r-card">
              <div class="r-label">错误数</div>
              <div class="r-value">{{ totalQuestions - correctCount }}</div>
            </div>
          </div>

          <div class="accuracy-ring">
            <van-circle
              :current-rate="accuracyRate"
              :rate="100"
              :speed="60"
              :color="accuracyRate >= 80 ? '#67C23A' : accuracyRate >= 60 ? '#E6A23C' : '#F56C6C'"
              :layer-color="'#ebedf0'"
              size="120px"
            >
              <span class="rate-text">{{ accuracyRate }}%</span>
            </van-circle>
            <div class="ring-label">正确率</div>
          </div>

          <div class="encourage-box">
            <div class="encourage-text">{{ encouragementMessage }}</div>
            <div class="wrong-note">错题已自动移入错题本</div>
          </div>

          <!-- 错题回顾 -->
          <div v-if="Object.keys(questionResults).some(k => questionResults[k] && !questionResults[k].is_correct)" class="wrong-review">
            <h4>错题回顾</h4>
            <div
              v-for="(q, idx) in allQuestions.filter(q => questionResults[`${q.type}_${q.id}`] && !questionResults[`${q.type}_${q.id}`].is_correct)"
              :key="idx"
              class="wrong-item"
            >
              <div class="wrong-q">{{ idx + 1 }}. {{ q.question }}</div>
              <div class="wrong-ans correct-ans">正确答案：{{ getCorrectAnswerText(q) }}</div>
              <div class="wrong-ans user-ans">你的答案：{{ getUserAnswerText(q) }}</div>
            </div>
          </div>

          <div class="bottom-actions">
            <van-button @click="restartAnswer">返回答题</van-button>
            <van-button type="primary" @click="quitShowHtml">关闭试卷</van-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-paper {
  min-height: 100vh;
  background: var(--bg-page, #f7f8fa);
  padding-bottom: 60px;
}

/* 顶部导航 */
.page-nav {
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
}

/* 列表页 */
.paper-list-page {
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
.paper-input {
  margin-bottom: 12px;
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
  opacity: 0.7;
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
  gap: 8px;
  flex-shrink: 0;
  margin-left: 12px;
}
.loading-icon {
  color: var(--primary, #409EFF);
  animation: spin 1s linear infinite;
}
.status-text {
  font-size: 12px;
  color: var(--primary, #409EFF);
  font-weight: 500;
}
.fail-icon {
  color: #F56C6C;
  font-size: 20px;
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

/* 预览/答题页 */
.paper-detail-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-page, #f7f8fa);
  z-index: 100;
  overflow-y: auto;
}
.detail-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-card, #fff);
  border-bottom: 1px solid var(--border-color, #eee);
  position: sticky;
  top: 0;
  z-index: 10;
}
.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title, #323233);
  flex: 1;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin: 0 8px;
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

/* 答题页 */
.answer-page {
  padding: 16px;
}
.progress-section {
  background: var(--bg-card, #fff);
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 12px;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-gray, #969799);
  margin-bottom: 8px;
}

.question-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.nav-info {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-gray, #969799);
}

/* 题目卡片 */
.question-card {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--border-color, #eee);
  margin-bottom: 12px;
}
.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.q-type {
  padding: 2px 10px;
  background: var(--primary, #409EFF);
  color: #fff;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}
.q-status {
  font-size: 12px;
  color: var(--text-gray, #969799);
}
.q-status.submitted {
  color: #67C23A;
}
.q-text {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-title, #323233);
  line-height: 1.6;
  margin-bottom: 16px;
}

/* 选项 */
.options-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.option-item {
  display: flex;
  align-items: center;
  padding: 12px 14px;
  border: 2px solid var(--border-color, #eee);
  border-radius: 10px;
  transition: all 0.2s;
}
.option-item:active:not(.correct):not(.wrong):not(.correct-show) {
  border-color: var(--primary, #409EFF);
  background: rgba(64, 158, 255, 0.05);
}
.option-item.selected {
  border-color: var(--primary, #409EFF);
  background: rgba(64, 158, 255, 0.08);
}
.option-item.correct {
  border-color: #67C23A;
  background: rgba(103, 194, 58, 0.1);
}
.option-item.wrong {
  border-color: #F56C6C;
  background: rgba(245, 108, 108, 0.1);
}
.option-item.correct-show {
  border-color: #67C23A;
  background: rgba(103, 194, 58, 0.06);
}
.opt-label {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--border-color, #eee);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-gray, #969799);
  margin-right: 10px;
  flex-shrink: 0;
}
.option-item.selected .opt-label {
  background: var(--primary, #409EFF);
  color: #fff;
}
.option-item.correct .opt-label {
  background: #67C23A;
  color: #fff;
}
.option-item.wrong .opt-label {
  background: #F56C6C;
  color: #fff;
}
.opt-text {
  flex: 1;
  font-size: 14px;
  color: var(--text-body, #323233);
}
.opt-mark {
  color: #67C23A;
  font-size: 18px;
  flex-shrink: 0;
  margin-left: 8px;
}
.multi-hint {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
}

/* 判断题 */
.judge-options {
  display: flex;
  gap: 16px;
  justify-content: center;
}
.judge-options .van-button {
  min-width: 100px;
}

/* 填空/简答 */
.fill-input, .short-input {
  margin: 8px 0;
}

/* 提交结果 */
.result-box {
  display: flex;
  gap: 12px;
  padding: 14px;
  border-radius: 10px;
  border: 2px solid;
  margin-top: 16px;
}
.result-box.correct {
  border-color: #67C23A;
  background: rgba(103, 194, 58, 0.06);
}
.result-box.wrong {
  border-color: #F56C6C;
  background: rgba(245, 108, 108, 0.06);
}
.result-icon {
  font-size: 28px;
  line-height: 1;
  flex-shrink: 0;
}
.result-detail {
  flex: 1;
}
.result-msg {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-title, #323233);
}
.result-answer {
  font-size: 13px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
}
.result-score {
  font-size: 13px;
  color: var(--primary, #409EFF);
  margin-top: 4px;
  font-weight: 500;
}

.submit-area {
  margin-top: 16px;
}

.bottom-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}
.bottom-actions .van-button {
  flex: 1;
}

/* 结果页 */
.result-page {
  padding: 16px;
}
.result-summary {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.result-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  width: 100%;
  justify-content: center;
}
.r-card {
  text-align: center;
  padding: 12px 20px;
  background: var(--bg-card, #fff);
  border-radius: 10px;
  flex: 1;
  max-width: 120px;
}
.r-label {
  font-size: 12px;
  color: var(--text-gray, #969799);
}
.r-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-title, #323233);
  margin-top: 4px;
}

.accuracy-ring {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 16px 0;
}
.rate-text {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-title, #323233);
}
.ring-label {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-gray, #969799);
}

.encourage-box {
  text-align: center;
  padding: 16px;
  margin: 16px 0;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.08), rgba(103, 194, 58, 0.08));
  border-radius: 12px;
  width: 100%;
}
.encourage-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title, #323233);
  margin-bottom: 6px;
}
.wrong-note {
  font-size: 13px;
  color: var(--text-gray, #969799);
}

/* 错题回顾 */
.wrong-review {
  width: 100%;
  margin-top: 16px;
  padding: 14px;
  background: rgba(245, 108, 108, 0.05);
  border-radius: 10px;
  border: 1px solid rgba(245, 108, 108, 0.15);
}
.wrong-review h4 {
  color: #F56C6C;
  margin: 0 0 12px;
  font-size: 15px;
}
.wrong-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color, #eee);
}
.wrong-item:last-child {
  border-bottom: none;
}
.wrong-q {
  font-weight: 500;
  font-size: 14px;
  color: var(--text-body, #323233);
}
.wrong-ans {
  font-size: 13px;
  margin-top: 4px;
}
.correct-ans {
  color: #67C23A;
}
.user-ans {
  color: #F56C6C;
}
</style>

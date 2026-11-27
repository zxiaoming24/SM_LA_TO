<script setup>
import { ref, onMounted, computed, onUnmounted, watch, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showNotify, closeToast } from 'vant'
import { saveSkip } from '@/utils/skip.js'
import emitter from '@/utils/emitter'
import { renderAnswerChart, destroyAnswerChart, highlightAttempt } from '@/views/phone/js/lineDiagram.js'
import {
  getSummaryApi, getPendingListApi, getOkListApi, deleteQuestionApi,
  getInfoApi, getAiRecommendApi, submitSingleQuestionApi,
  getFrequentlyListApi, getFrequentlyMesApi
} from '@/api/mainApi/wrongQuestions.js'
import MobileKnowledgePoints from '@/views/phone/components/MobileKnowledgePoints.vue'

const router = useRouter()
let loginUser = null
const userId = ref('')
const showTopBtn = ref(false)

// ==================== 滚动处理 ====================
const getScrollEl = () => document.querySelector('.phone-content')
const scrollHandler = () => {
  const el = getScrollEl()
  showTopBtn.value = el ? el.scrollTop > 80 : false
}
const backTop = () => {
  const el = getScrollEl()
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(async () => {
  // 初始置顶
  const el = getScrollEl()
  if (el) {
    el.scrollTop = 0
    el.addEventListener('scroll', scrollHandler)
  }

  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.username) {
        if (loginUser.isNew == false && loginUser.isBuildProfile == 0) {
          showNotify({ type: 'warning', message: '请进行画像构建~' })
          router.push('/phone/aiAnswer')
        }
        userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }

  await getSummary()
  await changeNav(1)
})

onUnmounted(() => {
  const el = getScrollEl()
  if (el) el.removeEventListener('scroll', scrollHandler)
})

// ==================== 数据 ====================
const summary = ref({})
const page = ref(1)
const pageSize = ref(10)
const totalPages = ref(1)
const qType = ref(0)
const showPopup = ref(false)
const showSituation = ref(false)
const questionList = ref([])
const okList = ref([])

const showQuestion = reactive({})

// 答题绑定
const answer = ref('')
const answerIndex = ref(null)
const multipleIndex = ref([])
const judgeAnswer = ref('')

// 分析结果
const analysisResult = ref(null)
const isSubmitting = ref(false)
const hasSubmitted = ref(false)

// 推荐材料
const recommend = ref([])
const showRecommendDetail = ref(false)
const recommendDetailData = ref(null)
const isLoadingRecommend = ref(false)

// 已掌握
const okData = ref({})
const activeIdx = ref(-1)
const curAnswer = ref('')
const curScore = ref('')
const curVerdict = ref('')

// 易错题
const frequentlyList = ref([])
const frequentlyStats = ref({})

// 推荐题目详情弹窗变量
const recommendDetailAnswerIndex = ref(null)
const recommendDetailMultipleIndex = ref([])
const recommendDetailJudgeAnswer = ref('')
const recommendDetailTextAnswer = ref('')
const recommendDetailResult = ref(null)
const recommendDetailSubmitting = ref(false)

// 题型筛选下拉选项
const qTypeOptions = [
  { text: '全部类型', value: 0 },
  { text: '编程题', value: 1 },
  { text: '单选题', value: 2 },
  { text: '多选题', value: 3 },
  { text: '判断题', value: 4 },
  { text: '填空题', value: 5 },
  { text: '简答题', value: 6 }
]

// 监听题型筛选
watch(qType, async (newValue) => {
  page.value = 1
  await getPendingList(1)
})

// ==================== 导航 ====================
const navOption = ref(0)
const activeTab = ref(1)

const onTabChange = (name) => {
  changeNav(name)
}

const changeNav = async (choose) => {
  if (navOption.value === choose) return
  switch (choose) {
    case 1:
      page.value = 1
      await getPendingList(1)
      navOption.value = 1
      break
    case 2:
      page.value = 1
      await getOkList(1)
      navOption.value = 2
      break
    case 3:
      page.value = 1
      await getFrequentlyList(1)
      await getFrequentlyStats()
      navOption.value = 3
      break
    case 4:
      navOption.value = 4
      break
    default:
      break
  }
}

// ==================== 工具函数 ====================
function formatTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${mi}:${s}`
}

const questionType = (type) => {
  switch (type) {
    case 'fill_blank': return '填空题'
    case 'programming': return '编程题'
    case 'single_choice': return '单选题'
    case 'multiple_choice': return '多选题'
    case 'judge': return '判断题'
    case 'short_answer': return '简答题'
    default: return '未知题型'
  }
}

// 题型标签颜色类
const typeClass = (type) => {
  if (type === 'programming') return 't-purple'
  if (type === 'single_choice' || type === 'multiple_choice') return 't-primary'
  if (type === 'judge') return 't-coming'
  if (type === 'fill_blank' || type === 'short_answer') return 't-pass'
  return 't-primary'
}

const extractOptionLetter = (optionText, index) => {
  if (!optionText) return String.fromCharCode(65 + index)
  const match = optionText.match(/^([A-D])\./)
  if (match) return match[1]
  if (/^[A-D]$/i.test(optionText.trim())) return optionText.trim().toUpperCase()
  return String.fromCharCode(65 + index)
}

const isProgrammingResource = (item) => {
  if (!item) return false
  if (item.sub_topic === 'programming') return true
  if (item.topic === 'programming') return true
  return false
}

const difficultyText = (diff) => {
  if (diff === 1 || diff === '简单') return '简单'
  if (diff === 2 || diff === '中等') return '中等'
  if (diff === 3 || diff === '困难') return '困难'
  return diff || '无'
}

// ==================== 翻页 ====================
const prevPage = async () => {
  if (page.value > 1) {
    page.value--
    if (navOption.value === 1) await getPendingList(page.value)
    else if (navOption.value === 2) await getOkList(page.value)
    else if (navOption.value === 3) await getFrequentlyList(page.value)
    const el = getScrollEl()
    if (el) el.scrollTop = 0
  }
}

const nextPage = async () => {
  if (page.value < totalPages.value) {
    page.value++
    if (navOption.value === 1) await getPendingList(page.value)
    else if (navOption.value === 2) await getOkList(page.value)
    else if (navOption.value === 3) await getFrequentlyList(page.value)
    const el = getScrollEl()
    if (el) el.scrollTop = 0
  }
}

// ==================== 弹窗：待巩固重练 ====================
const openPopup = async (index) => {
  const item = questionList.value[index]
  Object.assign(showQuestion, item)

  if (item) {
    emitter.emit('contextDetail', {
      page: 'wrongQuestions',
      title: '错题重练',
      action: 'reviewing',
      detail: `错题ID: ${item.record_id || item.id}, 题目: ${item.question || '未知题目'}, 知识点: ${item.knowledge_point || ''}`
    })
  }

  // 重置答题状态
  answer.value = ''
  answerIndex.value = null
  multipleIndex.value = []
  judgeAnswer.value = ''
  analysisResult.value = null
  hasSubmitted.value = false
  recommend.value = []

  showPopup.value = true
  await fetchRecommendMaterials(item.record_id)
}

// 易错题：打开重练弹窗
const openFrequentlyPopup = async (index) => {
  const item = frequentlyList.value[index]
  Object.assign(showQuestion, item)

  if (item) {
    emitter.emit('contextDetail', {
      page: 'wrongQuestions',
      title: '错题重练',
      action: 'reviewing',
      detail: `错题ID: ${item.record_id || item.id}, 题目: ${item.question_data?.title || item.question || '未知题目'}, 知识点: ${item.knowledge_point || ''}`
    })
  }

  answer.value = ''
  answerIndex.value = null
  multipleIndex.value = []
  judgeAnswer.value = ''
  analysisResult.value = null
  hasSubmitted.value = false
  recommend.value = []

  showPopup.value = true
  await fetchRecommendMaterials(item.record_id)
}

const closePopup = () => {
  showPopup.value = false
  recommend.value = []
  analysisResult.value = null
  hasSubmitted.value = false
}

// 获取推荐材料
const fetchRecommendMaterials = async (recordId) => {
  try {
    isLoadingRecommend.value = true
    showToast({ message: '正在获取推荐材料...', type: 'loading', duration: 0, forbidClick: true })
    const res = await getInfoApi(userId.value, recordId)
    closeToast()
    if (res.code === 1 && res.data.success) {
      const materials = res.data.materials || {}
      const list = materials.question || []
      recommend.value = list.filter(item => item && item.id !== undefined && item.sub_topic !== 'code_practice')

      if (!res.data.should_recommend) {
        showNotify({ type: 'warning', message: '该题错误次数较少，暂无推荐材料', position: 'bottom' })
      } else {
        showNotify({ type: 'success', message: `已为您推荐 ${recommend.value.length} 个相关题目`, position: 'bottom' })
      }
    } else {
      recommend.value = []
      showNotify({ type: 'warning', message: '暂无推荐材料', position: 'bottom' })
    }
  } catch (e) {
    console.error('获取推荐材料失败', e)
    closeToast()
    recommend.value = []
  } finally {
    isLoadingRecommend.value = false
  }
}

// 多选切换
const toggleMultiple = (index) => {
  const findIndex = multipleIndex.value.indexOf(index)
  if (findIndex > -1) multipleIndex.value.splice(findIndex, 1)
  else multipleIndex.value.push(index)
}

// 获取用户答案
const getUserAnswer = () => {
  const currentType = showQuestion.question_type
  let userAnswer = ''

  switch (currentType) {
    case 'single_choice':
      if (answerIndex.value === null || answerIndex.value === undefined) {
        showNotify({ type: 'warning', message: '请选择一个选项' })
        return null
      }
      userAnswer = extractOptionLetter(showQuestion.question_data.options[answerIndex.value], answerIndex.value)
      break
    case 'multiple_choice':
      if (!multipleIndex.value || multipleIndex.value.length === 0) {
        showNotify({ type: 'warning', message: '请至少选择一个选项' })
        return null
      }
      userAnswer = multipleIndex.value.map(idx =>
        extractOptionLetter(showQuestion.question_data.options[idx], idx)
      ).join(',')
      break
    case 'judge':
      if (!judgeAnswer.value) {
        showNotify({ type: 'warning', message: '请选择正确或错误' })
        return null
      }
      userAnswer = judgeAnswer.value
      break
    case 'fill_blank':
    case 'short_answer':
      if (!answer.value || answer.value.trim() === '') {
        showNotify({ type: 'warning', message: '请输入您的答案' })
        return null
      }
      userAnswer = answer.value.trim()
      break
    default:
      showNotify({ type: 'warning', message: '未知题型' })
      return null
  }
  return userAnswer
}

// 提交重做分析
const handleSubmitAnalysis = async () => {
  if (isSubmitting.value) return
  const userAnswer = getUserAnswer()
  if (userAnswer === null) return

  const submitData = {
    user_id: userId.value,
    question_type: showQuestion.question_type,
    question: {
      question: showQuestion.question_data.question || showQuestion.question_data.title || '',
      options: showQuestion.question_data.options || null,
      answer: showQuestion.question_data.answer || showQuestion.correct_answer || ''
    },
    user_answer: userAnswer,
    knowledge_points: (showQuestion.knowledge_points && showQuestion.knowledge_points.join) ? showQuestion.knowledge_points.join(',') : (showQuestion.knowledge_points || [])
  }

  try {
    isSubmitting.value = true
    const res = await submitSingleQuestionApi(submitData)
    if (res.code === 1) {
      analysisResult.value = res.data
      hasSubmitted.value = true
      showToast({ type: 'success', message: res.data.message || '提交成功', position: 'top' })
      await getPendingList(page.value)
      await getSummary()
      await fetchRecommendMaterials(showQuestion.record_id)
    } else {
      showToast({ type: 'fail', message: res.msg || '提交失败', position: 'top' })
    }
  } catch (e) {
    console.error('提交分析失败', e)
    showToast({ type: 'fail', message: '提交失败，请稍后重试', position: 'top' })
  } finally {
    isSubmitting.value = false
  }
}

// 重新练习
const handleResetPractice = () => {
  analysisResult.value = null
  hasSubmitted.value = false
  answer.value = ''
  answerIndex.value = null
  multipleIndex.value = []
  judgeAnswer.value = ''
  showToast({ message: '已重置，请重新作答', position: 'top' })
}

const isSubmitDisabled = computed(() => isSubmitting.value || hasSubmitted.value)
const submitBtnText = computed(() => {
  if (isSubmitting.value) return '提交中...'
  if (hasSubmitted.value) return '已提交'
  return '重做分析'
})

// 跳转编程题作答
const goAnswer = async (rsType = 4, resourceId, recordId = '') => {
  saveSkip(rsType, resourceId, recordId)
  router.push('/phone/resource/code')
}

// 推荐材料跳转
const handleRecommendJump = (item) => {
  if (!item) {
    showNotify({ type: 'warning', message: '推荐数据不存在' })
    return
  }
  const isProgramming = isProgrammingResource(item)
  if (isProgramming) {
    const problemId = item.resource_id || item.id
    goAnswer(4, problemId, showQuestion.record_id || '')
  } else {
    let subTopic = item.sub_topic || item._type || item.resource_type || 'single_choice'
    if (subTopic === 'question' || subTopic === '' || subTopic === 'theory') {
      if (item.options && item.options.length > 0) {
        if (item.answer && item.answer.length === 1 && /^[A-D]$/i.test(item.answer)) subTopic = 'single_choice'
        else if (item.answer && item.answer.includes(',')) subTopic = 'multiple_choice'
        else subTopic = 'single_choice'
      } else {
        subTopic = 'short_answer'
      }
    }
    const questionData = {
      ...item,
      question: item.content || item.title || item.metadata?.title || '',
      options: item.options || [],
      answer: item.answer || '',
      explanation: item.explanation || '',
      sub_topic: subTopic
    }
    openQuestionDetail(questionData)
    resetRecommendDetail()
  }
}

// AI生成推荐材料
const handleAiGenerate = async () => {
  if (!showQuestion.record_id) {
    showNotify({ type: 'warning', message: '记录ID不存在' })
    return
  }
  isLoadingRecommend.value = true

  let knowledgePoints = []
  if (showQuestion.knowledge_points && showQuestion.knowledge_points.length > 0) {
    knowledgePoints = showQuestion.knowledge_points
  } else if (showQuestion.question_data && showQuestion.question_data.knowledge_points) {
    knowledgePoints = showQuestion.question_data.knowledge_points
  }

  let difficulty = '中等'
  if (showQuestion.question_data && showQuestion.question_data.difficulty) {
    const diff = showQuestion.question_data.difficulty
    if (String(diff).includes('简单') || diff === '简单') difficulty = '简单'
    else if (String(diff).includes('中等') || diff === '中等') difficulty = '中等'
    else if (String(diff).includes('困难') || diff === '困难') difficulty = '困难'
  }

  const requestData = {
    user_id: userId.value,
    record_id: showQuestion.record_id,
    knowledge_points: knowledgePoints.length > 0 ? knowledgePoints : ['编程基础'],
    resource_types: ['question', 'practice'],
    difficulty
  }

  try {
    showToast({ message: 'AI正在生成推荐材料...', type: 'loading', duration: 0, forbidClick: true })
    const res = await getAiRecommendApi(requestData)
    closeToast()
    if (res.code === 1 && res.data && res.data.success) {
      showToast({ type: 'success', message: 'AI生成推荐材料成功', position: 'top' })
      await fetchRecommendMaterials(showQuestion.record_id)
    } else {
      showToast({ type: 'fail', message: res.msg || 'AI生成失败', position: 'top' })
    }
  } catch (e) {
    console.error('AI生成推荐材料失败', e)
    closeToast()
    showNotify({ type: 'warning', message: 'AI生成失败，请稍后重试', position: 'bottom' })
  } finally {
    isLoadingRecommend.value = false
  }
}

// ==================== 推荐题目详情 ====================
const openQuestionDetail = (item) => {
  recommendDetailData.value = item
  showRecommendDetail.value = true
}

const closeRecommendDetail = () => {
  showRecommendDetail.value = false
  recommendDetailData.value = null
  resetRecommendDetail()
}

const resetRecommendDetail = () => {
  recommendDetailAnswerIndex.value = null
  recommendDetailMultipleIndex.value = []
  recommendDetailJudgeAnswer.value = ''
  recommendDetailTextAnswer.value = ''
  recommendDetailResult.value = null
}

const toggleRecommendMultiple = (index) => {
  const findIndex = recommendDetailMultipleIndex.value.indexOf(index)
  if (findIndex > -1) recommendDetailMultipleIndex.value.splice(findIndex, 1)
  else recommendDetailMultipleIndex.value.push(index)
}

const submitRecommendQuestion = async () => {
  if (!recommendDetailData.value) return
  let userAnswer = ''
  const qData = recommendDetailData.value

  if (qData.sub_topic === 'single_choice') {
    if (recommendDetailAnswerIndex.value === null || recommendDetailAnswerIndex.value === undefined) {
      showNotify({ type: 'warning', message: '请选择一个选项' })
      return
    }
    userAnswer = extractOptionLetter(qData.options[recommendDetailAnswerIndex.value], recommendDetailAnswerIndex.value)
  } else if (qData.sub_topic === 'multiple_choice') {
    if (!recommendDetailMultipleIndex.value || recommendDetailMultipleIndex.value.length === 0) {
      showNotify({ type: 'warning', message: '请至少选择一个选项' })
      return
    }
    userAnswer = recommendDetailMultipleIndex.value.map(idx =>
      extractOptionLetter(qData.options[idx], idx)
    ).join(',')
  } else if (qData.sub_topic === 'judge') {
    if (!recommendDetailJudgeAnswer.value) {
      showNotify({ type: 'warning', message: '请选择正确或错误' })
      return
    }
    userAnswer = recommendDetailJudgeAnswer.value
  } else if (qData.sub_topic === 'fill_blank' || qData.sub_topic === 'short_answer') {
    if (!recommendDetailTextAnswer.value || recommendDetailTextAnswer.value.trim() === '') {
      showNotify({ type: 'warning', message: '请输入您的答案' })
      return
    }
    userAnswer = recommendDetailTextAnswer.value.trim()
  } else {
    showNotify({ type: 'warning', message: '未知题型' })
    return
  }

  const submitData = {
    user_id: userId.value,
    question_type: qData.sub_topic || 'single_choice',
    question: {
      question: qData.content || qData.title || qData.question || '',
      options: qData.options || [],
      answer: qData.answer || ''
    },
    user_answer: userAnswer,
    knowledge_points: qData.knowledge_points || []
  }

  try {
    recommendDetailSubmitting.value = true
    const res = await submitSingleQuestionApi(submitData)
    if (res.code === 1) {
      recommendDetailResult.value = res.data
      showToast({ type: 'success', message: res.data.message || '提交成功', position: 'top' })
      await getPendingList(page.value)
      await getSummary()
    } else {
      showToast({ type: 'fail', message: res.msg || '提交失败', position: 'top' })
    }
  } catch (e) {
    console.error('提交推荐题目失败', e)
    showToast({ type: 'fail', message: '提交失败，请稍后重试', position: 'top' })
  } finally {
    recommendDetailSubmitting.value = false
  }
}

// ==================== 已掌握学习趋势 ====================
const openSituation = async (index) => {
  okData.value = okList.value[index]
  const item = okList.value[index].attempts[0]
  activeIdx.value = 0
  curAnswer.value = item.user_answer
  curScore.value = item.score
  curVerdict.value = item.verdict
  showSituation.value = true
}

const onSituationOpened = () => {
  renderAnswerChart('answerChart', okData.value)
}

const onSituationClosed = () => {
  destroyAnswerChart('answerChart')
  okData.value = {}
  activeIdx.value = -1
  curAnswer.value = ''
  curScore.value = ''
  curVerdict.value = ''
}

const selectAttempt = (idx) => {
  const item = okData.value.attempts[idx]
  activeIdx.value = idx
  curAnswer.value = item.user_answer
  curScore.value = item.score
  curVerdict.value = item.verdict
  highlightAttempt('answerChart', idx)
}

// ==================== 删除 ====================
const deleteQuestion = async (recordId) => {
  try {
    await showConfirmDialog({ title: '删除错题', message: '确定要删除这道错题吗？' })
  } catch (e) {
    return
  }
  try {
    const res = await deleteQuestionApi(userId.value, recordId)
    if (res.code && res.data.success === true) {
      showToast({ type: 'success', message: '删除成功', position: 'top' })
      await getPendingList(page.value)
      await getSummary()
    } else {
      showToast({ type: 'fail', message: '删除失败', position: 'top' })
    }
  } catch (e) {
    console.error('删除失败', e)
    showToast({ type: 'fail', message: '删除失败', position: 'top' })
  }
}

// ==================== 接口 ====================
const getSummary = async () => {
  try {
    const res = await getSummaryApi(userId.value)
    if (res.code && res.data.success === true) {
      summary.value = res.data
    }
  } catch (e) {
    console.error('获取统计信息失败', e)
  }
}

const getPendingList = async (optionPage) => {
  try {
    const res = await getPendingListApi(optionPage, pageSize.value, qType.value, userId.value)
    if (res.code && res.data.success === true) {
      questionList.value = res.data.records
      page.value = res.data.page
      totalPages.value = res.data.total_pages
    } else {
      showToast({ type: 'fail', message: '查询失败', position: 'top' })
    }
  } catch (e) {
    console.error('获取待巩固列表失败', e)
  }
}

const getOkList = async (optionPage) => {
  try {
    const res = await getOkListApi(optionPage, pageSize.value, userId.value)
    if (res.code && res.data.success === true) {
      okList.value = res.data.records
      page.value = res.data.page
      totalPages.value = res.data.total_pages
    }
  } catch (e) {
    console.error('获取已掌握列表失败', e)
  }
}

const getFrequentlyList = async (optionPage) => {
  try {
    const res = await getFrequentlyListApi(optionPage, pageSize.value, userId.value)
    if (res.code && res.data.success === true) {
      frequentlyList.value = res.data.records
      page.value = res.data.page
      totalPages.value = res.data.total_pages
    } else {
      showToast({ type: 'fail', message: '获取易错题列表失败', position: 'top' })
    }
  } catch (e) {
    console.error('获取易错题列表失败', e)
  }
}

const getFrequentlyStats = async () => {
  try {
    const res = await getFrequentlyMesApi(userId.value)
    if (res.code && res.data.success === true) {
      frequentlyStats.value = res.data
    }
  } catch (e) {
    console.error('获取易错题统计失败', e)
  }
}
</script>

<template>
  <div class="phone-wrong">
    <!-- 回顶按钮 -->
    <div v-if="showTopBtn" class="back-top" @click="backTop">↑</div>

    <!-- 导航栏 -->
    <van-tabs v-model:active="activeTab" class="nav-tabs" @change="onTabChange">
      <van-tab :name="1">
        <template #title>待巩固 <span class="tab-count">{{ summary.pending || 0 }}</span></template>
      </van-tab>
      <van-tab :name="2">
        <template #title>已掌握 <span class="tab-count">{{ summary.resolved || 0 }}</span></template>
      </van-tab>
      <van-tab :name="3">
        <template #title>易错题 <span class="tab-count">{{ summary.frequently_wrong || 0 }}</span></template>
      </van-tab>
      <van-tab :name="4">
        <template #title>知识点盘问</template>
      </van-tab>
    </van-tabs>

    <!-- 题型筛选（仅待巩固） -->
    <div v-if="navOption === 1" class="filter-section">
      <van-dropdown-menu>
        <van-dropdown-item v-model="qType" :options="qTypeOptions" />
      </van-dropdown-menu>
    </div>

    <!-- 知识点盘问 -->
    <div v-if="navOption === 4" class="kp-wrap">
      <MobileKnowledgePoints :userId="userId" />
    </div>

    <!-- 待巩固列表 -->
    <div v-if="navOption === 1" class="list">
      <template v-if="questionList.length !== 0">
        <div v-for="(item, index) in questionList" :key="index" class="q-card pending-card">
          <!-- 编程题 -->
          <div v-if="item.question_type === 'programming'" class="q-body">
            <div class="q-score">{{ item.score }} 分</div>
            <div class="q-header">
              <span class="qtype t-purple">编程题</span>
              <span class="q-title">{{ item.question_data.title }}</span>
            </div>
            <div class="q-desc">{{ item.question_data.description }}</div>
            <div class="q-tags" v-if="item.question_data.knowledge_points">
              <span v-for="tag in (Array.isArray(item.question_data.knowledge_points) ? item.question_data.knowledge_points : [item.question_data.knowledge_points])" :key="tag" class="qtag">{{ tag }}</span>
            </div>
            <div class="code-block">
              <div class="code-line-num">原答案代码</div>
              <textarea class="code-area" :value="item.user_answer" spellcheck="false" disabled></textarea>
            </div>
            <div class="q-footer">
              <div class="q-meta">
                <div>创建：<span>{{ formatTime(item.created_at) }}</span></div>
                <div>重练：<span>{{ item.attempt_count }}</span> 次</div>
                <div>难度：<span>{{ item.question_data.difficulty || '无' }}</span></div>
              </div>
              <div class="q-actions">
                <div class="btn restart" @click="openPopup(index)">重新练习</div>
                <div class="btn delete" @click="deleteQuestion(item.record_id)">删除</div>
              </div>
            </div>
          </div>
          <!-- 非编程题 -->
          <div v-else class="q-body">
            <div class="q-score">{{ item.score }} 分</div>
            <div class="q-header">
              <span class="qtype" :class="typeClass(item.question_type)">{{ questionType(item.question_type) }}</span>
              <span class="q-title">{{ item.question_data.question }}</span>
            </div>
            <div class="q-options" v-if="item.question_type === 'single_choice' || item.question_type === 'multiple_choice'">
              <div v-for="(opt, oi) in item.question_data.options" :key="oi" class="opt-line">{{ opt }}</div>
            </div>
            <div class="q-tags" v-if="item.knowledge_points && item.knowledge_points.length">
              <span v-for="tag in (Array.isArray(item.knowledge_points) ? item.knowledge_points : [item.knowledge_points])" :key="tag" class="qtag">{{ tag }}</span>
            </div>
            <div class="answer-box">
              <div class="ans-row"><span class="ans-label">我的答案：</span><span class="ans-text">{{ item.user_answer || '未作答' }}</span></div>
              <div class="ans-row"><span class="ans-label">正确答案：</span><span class="ans-text">{{ item.correct_answer }}</span></div>
              <div class="ans-row" v-if="item.question_data.explanation"><span class="ans-label">题目解析：</span><span class="ans-text">{{ item.question_data.explanation }}</span></div>
            </div>
            <div class="q-footer">
              <div class="q-meta">
                <div>创建：<span>{{ formatTime(item.created_at) }}</span></div>
                <div>作答：<span>{{ item.attempt_count }}</span> 次</div>
                <div>难度：<span>{{ item.difficulty || '无' }}</span></div>
              </div>
              <div class="q-actions">
                <div class="btn restart" @click="openPopup(index)">重新练习</div>
                <div class="btn delete" @click="deleteQuestion(item.record_id)">删除</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 翻页 -->
        <div class="page-ct">
          <div class="page-btn" :class="{ disabled: page === 1 }" @click="prevPage">上一页</div>
          <div class="page-count">{{ page }}/{{ totalPages }}</div>
          <div class="page-btn" :class="{ disabled: page === totalPages }" @click="nextPage">下一页</div>
        </div>
      </template>
      <van-empty v-else description="暂无信息" />
    </div>

    <!-- 已掌握列表 -->
    <div v-if="navOption === 2" class="list">
      <template v-if="okList.length !== 0">
        <div v-for="(item, index) in okList" :key="index" class="q-card ok-card">
          <div class="q-body">
            <div class="qok"><span class="ok-icon">✓</span>已掌握</div>
            <div class="q-header">
              <span class="qtype" :class="typeClass(item.question_type)">{{ questionType(item.question_type) }}</span>
              <span class="q-title">{{ item.question_data.title || item.question_data.question }}</span>
            </div>
            <div class="q-desc" v-if="item.question_data.description || item.question_data.content">{{ item.question_data.description || item.question_data.content }}</div>
            <div class="q-options" v-if="item.question_data.options && item.question_data.options.length">
              <div v-for="(opt, oi) in item.question_data.options" :key="oi" class="opt-line">{{ opt }}</div>
            </div>
            <div class="q-options" v-if="item.question_type === 'judge'"><div class="opt-line">正确</div><div class="opt-line">错误</div></div>
            <div class="q-tags" v-if="item.question_data.knowledge_points">
              <span v-for="tag in (Array.isArray(item.question_data.knowledge_points) ? item.question_data.knowledge_points : [item.question_data.knowledge_points])" :key="tag" class="qtag">{{ tag }}</span>
            </div>
            <div class="q-footer">
              <div class="q-meta">
                <div>创建：<span>{{ formatTime(item.created_at) }}</span></div>
                <div>重练：<span>{{ item.attempt_count }}</span> 次</div>
                <div>难度：<span>{{ item.question_data.difficulty || '无' }}</span></div>
              </div>
              <div class="q-actions">
                <div class="btn trend" @click="openSituation(index)">查看得分趋势</div>
              </div>
            </div>
          </div>
        </div>

        <div class="page-ct">
          <div class="page-btn" :class="{ disabled: page === 1 }" @click="prevPage">上一页</div>
          <div class="page-count">{{ page }}/{{ totalPages }}</div>
          <div class="page-btn" :class="{ disabled: page === totalPages }" @click="nextPage">下一页</div>
        </div>
      </template>
      <van-empty v-else description="暂无信息" />
    </div>

    <!-- 易错题列表 -->
    <div v-if="navOption === 3" class="list">
      <template v-if="frequentlyList.length !== 0">
        <!-- 易错题统计 -->
        <div v-if="frequentlyStats && frequentlyStats.total" class="fw-stats-row">
          <div class="fw-stat-card"><div class="fw-stat-num">{{ frequentlyStats.total || 0 }}</div><div class="fw-stat-label">易错题总数</div></div>
          <div class="fw-stat-card"><div class="fw-stat-num">{{ frequentlyStats.threshold || 0 }}</div><div class="fw-stat-label">易错阈值</div></div>
          <div class="fw-stat-card"><div class="fw-stat-num">{{ frequentlyStats.max_attempts || 0 }}</div><div class="fw-stat-label">最多错误</div></div>
          <div class="fw-stat-card"><div class="fw-stat-num">{{ frequentlyStats.avg_attempts || 0 }}</div><div class="fw-stat-label">平均错误</div></div>
        </div>
        <div v-if="frequentlyStats.weak_knowledge_points && frequentlyStats.weak_knowledge_points.length" class="fw-kp-area">
          <span class="fw-kp-title">薄弱知识点：</span>
          <span v-for="kp in frequentlyStats.weak_knowledge_points" :key="kp.knowledge_point" class="fw-kp-tag">{{ kp.knowledge_point }}({{ kp.count }})</span>
        </div>

        <div v-for="(item, index) in frequentlyList" :key="item.record_id || index" class="q-card fw-card">
          <div class="fw-ring-wrap">
            <svg class="fw-ring" viewBox="0 0 80 80">
              <circle class="fw-ring-bg" cx="40" cy="40" r="34"></circle>
              <circle class="fw-ring-fg" cx="40" cy="40" r="34" :style="{ strokeDasharray: 213.628, strokeDashoffset: 213.628 - Math.min(item.fw_attempt_count || item.attempt_count || 0, 20) / 20 * 213.628 }"></circle>
            </svg>
            <div class="fw-ring-center">
              <span class="fw-ring-num">{{ item.fw_attempt_count || item.attempt_count || 0 }}</span>
              <span class="fw-ring-label">错误次数</span>
            </div>
          </div>
          <div class="fw-body">
            <div class="fw-header">
              <span class="fw-badge">{{ questionType(item.question_type) }}</span>
              <span class="fw-score">{{ item.score || 0 }}分</span>
              <span class="fw-frequent-badge">🔥易错题</span>
            </div>
            <div class="fw-question">{{ item.question_data.title || item.question_data.question || item.question_data.description || '无题目内容' }}</div>
            <div v-if="item.question_type !== 'programming' && item.question_data.options && item.question_data.options.length" class="fw-options">
              <div v-for="(opt, oi) in item.question_data.options" :key="oi" class="fw-option-item">{{ opt }}</div>
            </div>
            <div v-if="item.knowledge_points && item.knowledge_points.length" class="fw-kp-tags">
              <span v-for="kp in (Array.isArray(item.knowledge_points) ? item.knowledge_points : [item.knowledge_points])" :key="kp" class="fw-kp-tag">{{ kp }}</span>
            </div>
            <div class="fw-attempt-bar">
              <span class="fw-attempt-label">错误 {{ item.attempt_count || 0 }} 次</span>
              <div class="fw-bar-bg"><div class="fw-bar-fill" :style="{ width: Math.min((item.attempt_count || 0) / 20 * 100, 100) + '%' }"></div></div>
              <span class="fw-attempt-count">共 {{ (item.attempts && item.attempts.length) || 0 }} 次</span>
            </div>
            <div class="fw-footer">
              <div class="fw-time">{{ formatTime(item.created_at) }}</div>
              <div class="fw-retry-btn" @click="openFrequentlyPopup(index)">✏️ 重新练习</div>
            </div>
          </div>
        </div>

        <div class="page-ct">
          <div class="page-btn" :class="{ disabled: page === 1 }" @click="prevPage">上一页</div>
          <div class="page-count">{{ page }}/{{ totalPages }}</div>
          <div class="page-btn" :class="{ disabled: page === totalPages }" @click="nextPage">下一页</div>
        </div>
      </template>
      <van-empty v-else description="暂无信息" />
    </div>

    <!-- 弹窗1：重练 + 推荐材料 -->
    <van-popup
      v-model:show="showPopup"
      position="bottom"
      round
      closeable
      close-icon-position="top-right"
      :style="{ maxHeight: '85%' }"
      class="practice-popup"
      lock-scroll
      @closed="closePopup"
    >
      <div class="popup-header" v-if="showQuestion.question_data">错题重练</div>
      <div class="popup-scroll" v-if="showQuestion.question_data">

        <!-- 编程题：跳转按钮 -->
        <div v-if="showQuestion.question_type === 'programming'" class="programming-jump">
          <div class="jump-btn" @click="goAnswer(4, (showQuestion.question_data.id?.length ? showQuestion.question_data.id : showQuestion.question_data.problem_id), showQuestion.record_id)">
            跳转编程题页重练 &gt;
          </div>
        </div>
        <!-- 非编程题答题区 -->
        <template v-else>
          <div class="practice-header">
            <span class="qtype" :class="typeClass(showQuestion.question_type)">{{ questionType(showQuestion.question_type) }}</span>
            <div class="practice-q">{{ showQuestion.question_data.question }}</div>
          </div>

          <!-- 单选题 -->
          <div v-if="showQuestion.question_type === 'single_choice'" class="options">
            <div v-for="(option, index) in showQuestion.question_data.options" :key="index" class="option-card" :class="{ 'selected': answerIndex === index }" @click="!hasSubmitted && (answerIndex = index)">
              <div class="opt-letter">{{ String.fromCharCode(65 + index) }}</div>
              <div class="opt-text">{{ option }}</div>
            </div>
          </div>

          <!-- 多选题 -->
          <div v-if="showQuestion.question_type === 'multiple_choice'" class="options">
            <div v-for="(option, index) in showQuestion.question_data.options" :key="index" class="option-card" :class="{ 'selected': multipleIndex.includes(index) }" @click="!hasSubmitted && toggleMultiple(index)">
              <div class="opt-letter">{{ String.fromCharCode(65 + index) }}</div>
              <div class="opt-text">{{ option }}</div>
            </div>
            <div v-if="multipleIndex.length > 0" class="tip-text">已选择 {{ multipleIndex.length }} 项</div>
          </div>

          <!-- 判断题 -->
          <div v-if="showQuestion.question_type === 'judge'" class="options judge">
            <div class="option-card" :class="{ 'selected': judgeAnswer === '正确' }" @click="!hasSubmitted && (judgeAnswer = '正确')">
              <div class="opt-letter">√</div><div class="opt-text">正确</div>
            </div>
            <div class="option-card" :class="{ 'selected': judgeAnswer === '错误' }" @click="!hasSubmitted && (judgeAnswer = '错误')">
              <div class="opt-letter">×</div><div class="opt-text">错误</div>
            </div>
          </div>

          <!-- 填空/简答 -->
          <div v-if="showQuestion.question_type === 'fill_blank' || showQuestion.question_type === 'short_answer'" class="textarea-wrap">
            <textarea rows="4" placeholder="请输入您的答案..." class="answer-textarea" v-model="answer" :disabled="hasSubmitted"></textarea>
          </div>

          <!-- 分析结果 -->
          <div v-if="analysisResult" class="analysis-result">
            <div class="result-header">
              <span class="result-icon" :class="analysisResult.is_correct ? 'correct' : 'wrong'">{{ analysisResult.is_correct ? '✓' : '✗' }}</span>
              <span class="result-text">{{ analysisResult.is_correct ? '回答正确！' : '回答错误' }}</span>
              <span class="result-score">得分：{{ analysisResult.score || 0 }} 分</span>
            </div>
            <div class="result-body" v-if="analysisResult.message"><p>{{ analysisResult.message }}</p></div>
            <div class="result-body" v-if="analysisResult.correct_answer"><p><strong>正确答案：</strong>{{ analysisResult.correct_answer }}</p></div>
            <div class="result-body" v-if="analysisResult.user_answer"><p><strong>你的答案：</strong>{{ analysisResult.user_answer }}</p></div>
          </div>

          <!-- 提交 / 重新练习 -->
          <div v-if="!hasSubmitted" class="submit-btn" :class="{ disabled: isSubmitDisabled }" @click="handleSubmitAnalysis">{{ submitBtnText }}</div>
          <div v-else class="submit-btn reset-btn" @click="handleResetPractice">重新练习</div>
        </template>

        <!-- 推荐材料 -->
        <div class="recommend-section">
          <div class="section-title">💡 推荐材料</div>
          <template v-if="recommend && recommend.length">
            <div v-for="(item, idx) in recommend" :key="idx" class="recommend-item">
              <div class="ri-title">【{{ questionType(item.sub_topic) || questionType(item.topic) || '通用' }}】 {{ item.title || '推荐补救题目' }}</div>
              <div class="ri-label">难度：{{ difficultyText(item.difficulty) }} | 知识点：{{ Array.isArray(item.knowledge_points) ? item.knowledge_points.join('、') : (item.knowledge_points || '无') }}</div>
              <div class="ri-btn" @click="handleRecommendJump(item)">
                {{ isProgrammingResource(item) ? '【编程题】跳转作答' : '【理论题】查看题目' }}
              </div>
            </div>
          </template>
          <div v-else class="recommend-empty">
            <van-loading v-if="isLoadingRecommend" type="spinner" size="24px" color="var(--text-gray)" />
            <div class="empty-text">{{ isLoadingRecommend ? '加载中...' : '暂无推荐材料' }}</div>
          </div>
          <div class="ai-btn" :class="{ loading: isLoadingRecommend }" @click="handleAiGenerate">
            {{ isLoadingRecommend ? 'AI生成中...' : (recommend.length ? 'AI生成更多推荐资料' : 'AI生成推荐材料') }}
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 弹窗2：学习趋势 -->
    <van-popup
      v-model:show="showSituation"
      position="bottom"
      round
      closeable
      close-icon-position="top-right"
      :style="{ maxHeight: '85%' }"
      class="situation-popup"
      lock-scroll
      @opened="onSituationOpened"
      @closed="onSituationClosed"
    >
      <div class="popup-header" v-if="okData.question_data">得分趋势</div>
      <div class="popup-scroll" v-if="okData.question_data">
        <div id="answerChart" class="chart-box"></div>

        <div class="q-base">
          <h3 class="q-base-title">{{ okData.question_data.title || okData.question_data.question }}</h3>
          <div class="q-base-meta">
            <span class="meta-tag">{{ okData.question_data.difficulty || okData.question_type }}</span>
            <span>知识点：{{ (() => { const p = okData.question_data.knowledge_points || okData.knowledge_points; return Array.isArray(p) ? p.join('、') : (p || '无'); })() }}</span>
          </div>
          <div class="q-base-stat">
            <span>作答次数：{{ okData.attempt_count }} 次</span>
            <span>最终得分：{{ okData.mastered_score }} 分</span>
          </div>
        </div>

        <div class="divider"></div>

        <div class="attempt-list">
          <div v-for="(item, idx) in okData.attempts" :key="idx" class="attempt-item" :class="{ active: activeIdx === idx }" @click="selectAttempt(idx)">
            <span>第{{ item.attempt_number }}次</span>
            <span class="score" :class="item.verdict === 'Accepted' ? 'ok' : 'err'">{{ item.score }}分</span>
          </div>
        </div>

        <div class="answer-panel" v-if="curAnswer">
          <div class="panel-head">
            <span>本次作答</span>
            <span class="mini-score" :class="curVerdict === 'Accepted' ? 'ok' : 'err'">{{ curScore }}分 · {{ curVerdict }}</span>
          </div>
          <pre class="answer-code">{{ curAnswer }}</pre>
        </div>
      </div>
    </van-popup>

    <!-- 弹窗3：推荐题目详情 -->
    <van-popup
      v-model:show="showRecommendDetail"
      position="bottom"
      round
      closeable
      close-icon-position="top-right"
      :style="{ maxHeight: '85%' }"
      class="detail-popup"
      lock-scroll
      @closed="closeRecommendDetail"
    >
      <div class="popup-header" v-if="recommendDetailData">
        {{ recommendDetailData.sub_topic === 'single_choice' ? '单选题' : recommendDetailData.sub_topic === 'multiple_choice' ? '多选题' : recommendDetailData.sub_topic === 'judge' ? '判断题' : recommendDetailData.sub_topic === 'fill_blank' ? '填空题' : recommendDetailData.sub_topic === 'short_answer' ? '简答题' : '理论题' }}
      </div>
      <div class="popup-scroll" v-if="recommendDetailData">
        <div class="detail-q">{{ recommendDetailData.question || recommendDetailData.content || recommendDetailData.title }}</div>

        <!-- 单选 -->
        <div v-if="recommendDetailData.options && recommendDetailData.options.length > 0 && recommendDetailData.sub_topic === 'single_choice'" class="options">
          <div v-for="(option, index) in recommendDetailData.options" :key="index" class="option-card" :class="{ 'selected': recommendDetailAnswerIndex === index }" @click="!recommendDetailResult && (recommendDetailAnswerIndex = index)">
            <div class="opt-letter">{{ String.fromCharCode(65 + index) }}</div>
            <div class="opt-text">{{ option }}</div>
          </div>
        </div>

        <!-- 多选 -->
        <div v-if="recommendDetailData.options && recommendDetailData.options.length > 0 && recommendDetailData.sub_topic === 'multiple_choice'" class="options">
          <div v-for="(option, index) in recommendDetailData.options" :key="index" class="option-card" :class="{ 'selected': recommendDetailMultipleIndex.includes(index) }" @click="!recommendDetailResult && toggleRecommendMultiple(index)">
            <div class="opt-letter">{{ String.fromCharCode(65 + index) }}</div>
            <div class="opt-text">{{ option }}</div>
          </div>
          <div v-if="recommendDetailMultipleIndex.length > 0" class="tip-text">已选择 {{ recommendDetailMultipleIndex.length }} 项</div>
        </div>

        <!-- 判断 -->
        <div v-if="recommendDetailData.sub_topic === 'judge'" class="options judge">
          <div class="option-card" :class="{ 'selected': recommendDetailJudgeAnswer === '正确' }" @click="!recommendDetailResult && (recommendDetailJudgeAnswer = '正确')">
            <div class="opt-letter">√</div><div class="opt-text">正确</div>
          </div>
          <div class="option-card" :class="{ 'selected': recommendDetailJudgeAnswer === '错误' }" @click="!recommendDetailResult && (recommendDetailJudgeAnswer = '错误')">
            <div class="opt-letter">×</div><div class="opt-text">错误</div>
          </div>
        </div>

        <!-- 填空/简答 -->
        <div v-if="recommendDetailData.sub_topic === 'fill_blank' || recommendDetailData.sub_topic === 'short_answer'" class="textarea-wrap">
          <textarea rows="4" placeholder="请输入您的答案..." class="answer-textarea" v-model="recommendDetailTextAnswer" :disabled="!!recommendDetailResult"></textarea>
        </div>

        <!-- 分析结果 -->
        <div v-if="recommendDetailResult" class="analysis-result">
          <div class="result-header">
            <span class="result-icon" :class="recommendDetailResult.is_correct ? 'correct' : 'wrong'">{{ recommendDetailResult.is_correct ? '✓' : '✗' }}</span>
            <span class="result-text">{{ recommendDetailResult.is_correct ? '回答正确！' : '回答错误' }}</span>
            <span class="result-score">得分：{{ recommendDetailResult.score || 0 }} 分</span>
          </div>
          <div class="result-body" v-if="recommendDetailResult.message"><p>{{ recommendDetailResult.message }}</p></div>
          <div class="result-body" v-if="recommendDetailResult.correct_answer"><p><strong>正确答案：</strong>{{ recommendDetailResult.correct_answer }}</p></div>
          <div class="result-body" v-if="recommendDetailResult.user_answer"><p><strong>你的答案：</strong>{{ recommendDetailResult.user_answer }}</p></div>
        </div>

        <div v-if="!recommendDetailResult" class="submit-btn" :class="{ disabled: recommendDetailSubmitting }" @click="submitRecommendQuestion">
          {{ recommendDetailSubmitting ? '提交中...' : '提交答案' }}
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.phone-wrong {
  padding-bottom: 60px;
  background: var(--bg-page);
  min-height: 100%;
}

/* 回顶按钮 */
.back-top {
  position: fixed;
  right: 16px;
  bottom: 70px;
  width: 44px;
  height: 44px;
  background: var(--primary);
  color: #fff;
  border-radius: 50%;
  text-align: center;
  line-height: 42px;
  font-size: 22px;
  z-index: 100;
  box-shadow: var(--shadow-brand);
}

/* 导航 tabs */
.nav-tabs {
  background: var(--bg-card);
  position: sticky;
  top: 0;
  z-index: 100;
}

:deep(.nav-tabs .van-tab) {
  font-size: 14px;
  color: var(--text-body);
  padding: 0 6px;
  flex: 1;
}

:deep(.nav-tabs .van-tab__text) {
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 16px;
  padding: 0 5px;
  margin-left: 3px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  text-align: center;
  border-radius: 8px;
  background: var(--bg-hover);
  color: var(--text-gray);
  white-space: nowrap;
  flex-shrink: 0;
}

:deep(.nav-tabs .van-tab--active) {
  color: var(--primary);
  font-weight: 600;
}

:deep(.nav-tabs .van-tab--active) .tab-count {
  background: var(--grad-primary);
  color: #fff;
}

:deep(.nav-tabs .van-tabs__nav) {
  background: var(--bg-card);
}

:deep(.nav-tabs .van-tabs__line) {
  background: var(--primary);
  width: 20px;
  height: 3px;
  border-radius: 2px;
}

/* 筛选 */
.filter-section {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}
:deep(.filter-section .van-dropdown-menu__bar) {
  background: var(--bg-card);
  box-shadow: none;
  height: 40px;
}

/* 知识点盘问 */
.kp-wrap {
  padding: 4px 0;
}

/* 列表 */
.list {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 题目卡片 */
.q-card {
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  padding: 14px;
  position: relative;
  overflow: hidden;
}
.q-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
}
.pending-card::before { background: linear-gradient(90deg, transparent, var(--coming), transparent); }
.ok-card::before { background: linear-gradient(90deg, transparent, var(--pass), transparent); }
.fw-card::before { background: linear-gradient(90deg, transparent, var(--main-delete), transparent); }

.q-body { display: flex; flex-direction: column; gap: 6px; }

.q-score {
  position: absolute;
  top: 12px;
  right: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-gray);
}

.qok {
  font-size: 13px;
  font-weight: 600;
  color: var(--pass);
  display: flex;
  align-items: center;
  gap: 4px;
}
.ok-icon {
  display: inline-flex;
  width: 18px; height: 18px;
  align-items: center; justify-content: center;
  background: var(--pass);
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
}

.q-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.qtype {
  flex-shrink: 0;
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 12px;
  border: 1px solid;
  font-weight: 600;
}
.t-purple { color: var(--purple); border-color: var(--purple); background: var(--purple-bg); }
.t-primary { color: var(--primary); border-color: var(--primary); background: var(--primary-light); }
.t-coming { color: var(--coming); border-color: var(--coming); background: var(--coming-bg-color); }
.t-pass { color: var(--pass); border-color: var(--pass); background: var(--pass-bg-color); }

.q-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  line-height: 1.4;
  flex: 1;
  min-width: 0;
  max-width: 240px;
}
.q-desc {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.5;
}
.q-options { display: flex; flex-direction: column; gap: 2px; }
.opt-line {
  font-size: 13px;
  color: var(--text-body);
  padding: 3px 8px;
  background: var(--bg-hover);
  border-radius: 6px;
}
.q-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 4px 0;
}
.qtag {
  font-size: 11px;
  padding: 2px 8px;
  border: 1px solid var(--pass);
  color: var(--pass);
  border-radius: 10px;
}

/* 代码块 */
.code-block {
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  margin: 4px 0;
}
.code-line-num {
  padding: 6px 10px;
  font-size: 11px;
  color: #858585;
  background: #252526;
  border-bottom: 1px solid #333;
}
.code-area {
  width: 100%;
  min-height: 120px;
  padding: 10px;
  background: transparent;
  color: #d4d4d4;
  border: none;
  outline: none;
  resize: vertical;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre;
  overflow-x: auto;
}

/* 答案区 */
.answer-box {
  background: var(--bg-hover);
  border-radius: 8px;
  padding: 8px 10px;
  margin: 4px 0;
}
.ans-row {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-body);
}
.ans-label { font-weight: 600; color: var(--text-title); }

/* 底部 */
.q-footer {
  border-top: 1px solid var(--border-color);
  padding-top: 8px;
  margin-top: 4px;
}
.q-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 8px;
}
.q-meta span { color: var(--text-title); font-weight: 600; }
.q-actions {
  display: flex;
  gap: 8px;
}
.btn {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  font-size: 13px;
  border-radius: 8px;
  border: 1px solid;
  font-weight: 500;
  transition: all 0.2s;
}
.pending-card .btn.restart { color: var(--coming); border-color: var(--coming); }
.pending-card .btn.restart:active { background: var(--coming); color: #fff; }
.pending-card .btn.delete { color: var(--main-delete); border-color: var(--main-delete); }
.pending-card .btn.delete:active { background: var(--main-delete); color: #fff; }
.ok-card .btn.trend { color: var(--pass); border-color: var(--pass); }
.ok-card .btn.trend:active { background: var(--pass); color: #fff; }

/* 翻页 */
.page-ct {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 8px 0 4px;
}
.page-btn {
  padding: 6px 14px;
  font-size: 13px;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  color: var(--primary);
  background: var(--bg-card);
}
.page-btn.disabled { color: var(--text-gray); }
.page-count {
  padding: 6px 12px;
  font-size: 13px;
  background: var(--bg-hover);
  border-radius: 18px;
  color: var(--text-body);
}

/* ============ 易错题卡片 ============ */
.fw-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.fw-stat-card {
  background: var(--main-fail-status);
  border: 1px solid var(--main-delete);
  border-radius: 10px;
  padding: 10px 4px;
  text-align: center;
}
.fw-stat-num {
  font-size: 18px;
  font-weight: 700;
  color: var(--main-delete-hover);
}
.fw-stat-label {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 2px;
}
.fw-kp-area {
  padding: 8px 10px;
  background: var(--bg-hover);
  border-radius: 8px;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
.fw-kp-title { font-weight: 600; color: var(--main-delete-hover); margin-right: 4px; }
.fw-kp-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.fw-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.fw-ring-wrap {
  flex-shrink: 0;
  position: relative;
  width: 64px;
  height: 64px;
}
.fw-ring {
  display: block;
  width: 64px;
  height: 64px;
  transform: rotate(-90deg);
}
.fw-ring-bg { fill: none; stroke: var(--border-color); stroke-width: 6; }
.fw-ring-fg { fill: none; stroke: var(--main-delete); stroke-width: 6; stroke-linecap: round; transition: stroke-dashoffset 0.6s ease; }
.fw-ring-center {
  position: absolute;
  top: 0; left: 0;
  width: 64px; height: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.fw-ring-num { font-size: 16px; font-weight: 800; color: var(--main-delete-hover); line-height: 1; }
.fw-ring-label { font-size: 8px; color: var(--text-gray); margin-top: 1px; }

.fw-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.fw-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fw-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; background: var(--main-fail-status); color: var(--main-delete); }
.fw-score { font-size: 13px; font-weight: 700; color: var(--text-gray); }
.fw-frequent-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--main-delete), var(--main-delete-hover));
  color: #fff;
  margin-left: auto;
}
.fw-question {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-title);
  font-weight: 600;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.fw-options { display: flex; flex-direction: column; gap: 3px; }
.fw-option-item { padding: 3px 8px; background: var(--bg-hover); border-radius: 6px; font-size: 12px; color: var(--text-body); }
.fw-kp-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.fw-attempt-bar { display: flex; align-items: center; gap: 8px; }
.fw-attempt-label { font-size: 11px; color: var(--text-gray); white-space: nowrap; }
.fw-bar-bg { flex: 1; height: 5px; background: var(--border-color); border-radius: 3px; overflow: hidden; }
.fw-bar-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--main-delete), var(--main-delete-hover)); }
.fw-attempt-count { font-size: 11px; color: var(--text-gray); white-space: nowrap; }
.fw-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 8px; }
.fw-time { font-size: 11px; color: var(--text-gray); }
.fw-retry-btn {
  padding: 6px 14px;
  border-radius: 8px;
  background: var(--main-delete);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
}
.fw-retry-btn:active { background: var(--main-delete-hover); }

/* ============ 弹窗通用 ============ */
:deep(.van-popup) {
  background: var(--bg-card);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding-bottom: 50px;
}
:deep(.van-popup .van-popup__close) {
  background: var(--bg-card);
  z-index: 10;
}
:deep(.van-popup .van-popup__close-icon) {
  color: var(--text-gray);
}
.popup-header {
  flex-shrink: 0;
  padding: 14px 16px 12px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-card);
  z-index: 2;
}
.popup-scroll {
  flex: 1;
  padding: 14px 16px 20px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  box-sizing: border-box;
  background: var(--bg-card);
  min-height: 0;
}

/* 编程题跳转 */
.programming-jump {
  padding: 24px 0;
  display: flex;
  justify-content: center;
}
.jump-btn {
  padding: 12px 20px;
  background: var(--grad-primary);
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  text-align: center;
  box-shadow: var(--shadow-brand);
  width: 100%;
  max-width: 320px;
}

/* 答题区 */
.practice-header {
  margin-bottom: 12px;
}
.practice-q {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  line-height: 1.6;
  margin-top: 8px;
  word-break: break-word;
  overflow-wrap: break-word;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}
.options.judge { flex-direction: row; gap: 12px; }
.options.judge .option-card { flex: 1; }
.option-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 12px;
  background: var(--bg-card);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  transition: all 0.2s;
  cursor: pointer;
  touch-action: manipulation;
}
.option-card.selected {
  border-color: var(--primary);
  background: var(--primary-light);
}
.opt-letter {
  width: 26px; height: 26px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-gray);
}
.option-card.selected .opt-letter {
  background: var(--primary);
  color: #fff;
}
.opt-text {
  flex: 1;
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: break-word;
}
.option-card.selected .opt-text { color: var(--text-title); font-weight: 500; }
.tip-text {
  font-size: 12px;
  color: var(--primary);
  text-align: center;
  padding: 4px 0;
}

.textarea-wrap { margin-bottom: 12px; }
.answer-textarea {
  width: 100%;
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-body);
  background: var(--bg-card);
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  outline: none;
  resize: none;
  box-sizing: border-box;
  font-family: inherit;
  -webkit-appearance: none;
  appearance: none;
}
.answer-textarea:focus { border-color: var(--primary); }

/* 分析结果 */
.analysis-result {
  margin: 12px 0;
  padding: 12px;
  border-radius: 10px;
  background: var(--bg-hover);
  border: 1px solid var(--border-color);
}
.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.result-icon {
  display: inline-flex;
  width: 26px; height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
.result-icon.correct { background: var(--pass); }
.result-icon.wrong { background: var(--main-delete); }
.result-text { font-size: 14px; font-weight: 600; color: var(--text-title); }
.result-score { margin-left: auto; font-size: 12px; color: var(--text-gray); }
.result-body {
  padding: 6px 0;
  font-size: 13px;
  color: var(--text-body);
  border-top: 1px solid var(--border-color);
  line-height: 1.6;
  word-break: break-word;
}
.result-body strong { color: var(--text-title); }

/* 提交按钮 */
.submit-btn {
  width: 100%;
  padding: 13px 0;
  background: var(--grad-primary);
  color: #fff;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  text-align: center;
  box-shadow: var(--shadow-brand);
  margin: 8px 0;
  touch-action: manipulation;
}
.submit-btn.disabled { opacity: 0.6; }
.submit-btn.reset-btn {
  background: var(--pass);
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

/* 推荐材料 */
.recommend-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-color);
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 10px;
}
.recommend-item {
  padding: 12px;
  background: var(--bg-hover);
  border-radius: 10px;
  margin-bottom: 10px;
  border: 1px solid var(--border-color);
}
.ri-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 4px;
  line-height: 1.5;
  word-break: break-word;
}
.ri-label {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 8px;
  line-height: 1.4;
  word-break: break-word;
}
.ri-btn {
  display: block;
  width: 100%;
  padding: 8px 12px;
  background: var(--primary);
  color: #fff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  text-align: center;
  touch-action: manipulation;
}
.ri-btn:active { background: var(--primary-hv); }
.recommend-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 0;
}
.empty-text {
  font-size: 13px;
  color: var(--text-gray);
}
.ai-btn {
  margin-top: 12px;
  padding: 12px 0;
  text-align: center;
  background: var(--grad-primary);
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow-brand);
  touch-action: manipulation;
}
.ai-btn.loading { background: var(--text-gray); opacity: 0.7; }

/* ============ 学习趋势弹窗 ============ */
.chart-box {
  width: 100%;
  height: 220px;
  margin-bottom: 12px;
  background: var(--bg-card);
  border-radius: 10px;
}
.q-base {
  padding: 10px 0;
}
.q-base-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 6px;
  line-height: 1.5;
  word-break: break-word;
}
.q-base-meta {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 6px;
  line-height: 1.5;
  word-break: break-word;
}
.meta-tag {
  display: inline-block;
  padding: 1px 6px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: 4px;
  font-size: 11px;
  margin-right: 6px;
}
.q-base-stat {
  font-size: 12px;
  color: var(--text-gray);
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px;
}
.divider {
  height: 1px;
  background: var(--border-color);
  margin-bottom: 10px;
}
.attempt-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}
.attempt-item {
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  touch-action: manipulation;
}
.attempt-item.active {
  background: var(--primary-fade);
  border-color: var(--primary);
}
.score.err, .mini-score.err { color: var(--main-delete); }
.score.ok, .mini-score.ok { color: var(--pass); }
.answer-panel {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}
.panel-head {
  padding: 8px 12px;
  background: var(--bg-hover);
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: 4px;
}
.answer-code {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  white-space: pre;
  overflow-x: auto;
  max-height: 240px;
  overflow-y: auto;
  font-family: Consolas, Monaco, monospace;
  -webkit-overflow-scrolling: touch;
}

/* 推荐题目详情 */
.detail-q {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  line-height: 1.5;
  margin-bottom: 12px;
}

/* 空状态 */
:deep(.van-empty) {
  padding: 40px 0;
}
:deep(.van-empty__description) {
  color: var(--text-gray);
  font-size: 13px;
}
</style>

<!-- 移动端智学路径 -->
<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { showToast, showConfirmDialog, showNotify, showLoadingToast, closeToast } from 'vant'
import { saveSkip, isSkip, removeSkip } from '@/utils/skip.js'
import { useRouter } from 'vue-router'
import {
  isCreateApi, startPlanApi, getProgressApi, createRsApi, phaseProgressApi,
  getPathPlanListApi, delPathPlanApi, getPlanDetailApi, checkStatusApi, getCheckMsgApi,
  isOpenExamApi, getExamQuestionsApi, submitExamAnswersApi, rejectCheckMsgApi,
  getVersionTreeApi, changeVersionApi, reCreatePlanApi,
  phaseApplyApi, ackNotificationApi, getPhaseNotificationApi,
  aiShareApi, shareToMarketApi
} from '@/api/mainApi/pathPlan.js'
import MobileTreeChart from '@/views/phone/components/MobileTreeChart.vue'
import MobilePathPlanMarket from '@/views/phone/components/MobilePathPlanMarket.vue'
import emitter from '@/utils/emitter.js'
import { conflictApi } from '@/api/mainApi/aiAnswer.js'

const router = useRouter()

// ===================================================================
// 数据定义
// ===================================================================
const generating = ref(false)
const generatingResources = ref({})
const userId = ref(null)
const planList = ref([])
const selectedPlanId = ref(null)
const isViewingDetail = ref(false)
const showMarket = ref(false)
const planText = ref('')

const currentUserId = computed(() => {
  const user = JSON.parse(localStorage.getItem('loginUser') || '{}')
  return user.id || user.user_id || ''
})

const hasPlan = computed(() => planList.value && planList.value.length > 0)

const selectedPlan = computed(() => {
  if (!planList.value || !selectedPlanId.value) return null
  return planList.value.find(p => p.plan_id === selectedPlanId.value) || null
})

const planData = ref({ plan: null, phases: [] })
const phases = computed(() => planData.value?.phases || [])

const totalProgress = ref({
  title: '', total_duration: '', total_phases: 0, completed_phases: 0,
  progress: '0/0', current_phase: null
})

const currentPhaseIndex = ref(-1)
const phaseProgressMap = ref({})
const kpCompletedMap = ref({})
const kpResourcesMap = ref({})
const kpGeneratedMap = ref({})

// 续期
const continuationInfo = ref(null)
const hasContinuationPending = ref(false)
const hasContinuationPlan = ref(false)
const continuationPlan = ref(null)
const hasCheckedContinuation = ref(false)
const continuationGenerating = ref(false)

// 版本树
const versionTree = ref({
  versions: [], active_version_plan_id: '', active_version: 0,
  has_tree: false, root_plan_id: ''
})
const versionTreeLoading = ref(false)
const reCreatingPhase = ref({})
const versionTreeExpanded = ref(true)

// 考试
const examDialogVisible = ref(false)
const examData = ref(null)
const currentExamPhaseIndex = ref(-1)
const examSubmitting = ref(false)
const examResults = ref(null)
const examShowResults = ref(false)
const examLoading = ref(false)
const examAlreadyCompleted = ref(false)
const examStartingLoading = ref({})
const examAnswers = ref({})
const lineCountMap = ref({})
const currentQuestionIndex = ref(0)
const allExamQuestions = ref([])
const exampleExpandedMap = ref({})
const hintExpandedMap = ref({})
const isAllSubmitted = ref(false)
const examCompletedMap = ref({})
const examResultMap = ref({})

// 冲突弹窗
const showConflictDialog = ref(false)
const conflictData = ref({
  message: '', weak_points_info: [], text: '', rsType: -1, taskId: ''
})

// 分享
const shareDialogVisible = ref(false)
const shareLoading = ref(false)
const shareSubmitting = ref(false)
const shareTagInput = ref('')
const shareForm = ref({
  name: '', subtitle: '', description: '', category: '',
  difficulty: 'beginner', tags: [], target_audience: '',
  cover_color: '#667eea', cover_icon: '📚'
})

// 评估报告
const generatingAssessment = ref(false)
const assessmentReport = ref(null)
const showAssessmentReport = ref(false)
const updatingNextPhase = ref(false)

// 滚动
const showTopBtn = ref(false)
const getScrollEl = () => document.querySelector('.phone-content')
const scrollHandler = () => {
  const el = getScrollEl()
  showTopBtn.value = el ? el.scrollTop > 80 : false
}
const backTop = () => {
  const el = getScrollEl()
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' })
}

// ===================================================================
// 计算属性
// ===================================================================
const allPhasesCompleted = computed(() => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  return phasesList.every(p => p.status === '已完成')
})

const completionPercent = computed(() => {
  const total = Number(totalProgress.value.total_phases) || 1
  const done = Number(totalProgress.value.completed_phases) || 0
  return Math.round((done / total) * 100)
})

const currentExamQuestion = computed(() => {
  if (!allExamQuestions.value.length) return null
  return allExamQuestions.value[currentQuestionIndex.value] || null
})

const isCurrentAnswered = computed(() => {
  const q = currentExamQuestion.value
  if (!q) return false
  if (isAllSubmitted.value) return true
  const key = q.type + '_' + q.index
  const val = examAnswers.value[key]
  if (val === undefined || val === null) return false
  if (Array.isArray(val)) return val.length > 0
  return val !== ''
})

const allQuestionsAnswered = computed(() => {
  if (allExamQuestions.value.length === 0) return false
  if (isAllSubmitted.value) return true
  return allExamQuestions.value.every(q => {
    const key = q.type + '_' + q.index
    const val = examAnswers.value[key]
    if (val === undefined || val === null) return false
    if (Array.isArray(val)) return val.length > 0
    return val !== ''
  })
})

const completedCount = computed(() => {
  if (isAllSubmitted.value) return allExamQuestions.value.length
  let count = 0
  allExamQuestions.value.forEach(q => {
    const key = q.type + '_' + q.index
    const val = examAnswers.value[key]
    if (val !== undefined && val !== null && val !== '' && !(Array.isArray(val) && val.length === 0)) {
      count++
    }
  })
  return count
})

const totalExamQuestions = computed(() => allExamQuestions.value.length)

// ===================================================================
// 工具方法
// ===================================================================
const getUserId = () => {
  const userStr = localStorage.getItem('loginUser')
  if (!userStr) return false
  try {
    const loginUser = JSON.parse(userStr)
    if (loginUser?.id) {
      if (loginUser.isNew == false && loginUser.isBuildProfile == 0) {
        showToast({ type: 'warning', message: '请进行画像构建~', position: 'middle' })
        router.push('/phone/aiAnswer')
      }
      userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      return true
    }
  } catch (err) {
    console.error('解析登录用户失败', err)
  }
  return false
}

const difficultyType = (difficulty) => {
  if (!difficulty) return ''
  if (difficulty === '简单') return 'var(--pass)'
  if (difficulty === '中等') return 'var(--coming)'
  if (difficulty === '困难') return 'var(--main-delete)'
  return ''
}

const phaseStatusColor = (status) => {
  if (status === '已完成') return 'var(--pass)'
  if (status === '进行中') return 'var(--primary)'
  return 'var(--text-gray)'
}

const getKpKey = (phaseIndex, knowledgePoint) => `${phaseIndex}_${knowledgePoint}`

const resourceTypeName = (type) => {
  const map = { 0: 'PPT课件', 1: '思维导图', 2: '讲解文档', 3: '拓展阅读', 4: '编程题', 5: '视频教程', 6: '动画演示', 7: '试卷', 8: '学习计划' }
  return map[type] || `未知类型(${type})`
}

const getResourceIcon = (type) => {
  const map = { 0: 'description', 1: 'cluster-o', 2: 'description', 3: 'notes-o', 4: 'edit', 5: 'video-o', 6: 'flower-o', 7: 'orders-o', 8: 'guide-o' }
  return map[type] || 'description'
}

const getResourceColor = (type) => {
  const map = { 0: '#FF6B6B', 1: '#4ECDC4', 2: '#45B7D1', 3: '#96CEB4', 4: '#FFEAA7', 5: '#DDA0DD', 6: '#FF9FF3', 7: '#54A0FF', 8: '#5F27CD' }
  return map[type] || '#95A5A6'
}

const isPhaseUnlocked = (phaseIndex) => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  if (phaseIndex === 0) return true
  const prev = phasesList[phaseIndex - 1]
  if (prev?.status !== '已完成') return false
  const prevExamInfo = extractExamInfoFromPhase(prev)
  return prevExamInfo.passed
}

const isPhaseCompleted = (phaseIndex) => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  return phasesList[phaseIndex]?.status === '已完成'
}

const isKpCompleted = (phaseIndex, kpName) => {
  const map = kpCompletedMap.value[phaseIndex] || {}
  return !!map[kpName]
}

const isKpGenerated = (phaseIndex, knowledgePoint) => {
  const key = getKpKey(phaseIndex, knowledgePoint)
  return !!kpGeneratedMap.value[key]
}

const getKpResources = (phaseIndex, knowledgePoint) => {
  const key = getKpKey(phaseIndex, knowledgePoint)
  return kpResourcesMap.value[key] || []
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${mi}`
}

const isPhaseFullyCompleted = (phaseIndex) => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  const phase = phasesList[phaseIndex]
  if (!phase) return false
  if (phase.status !== '已完成') return false
  const kpMap = kpCompletedMap.value[phaseIndex] || {}
  const kpList = phase.knowledge_points || []
  if (kpList.length === 0) return false
  return kpList.every(kp => kpMap[kp] === true)
}

const getQuestionTypeName = (type) => {
  const map = { 'single_choice': '单选题', 'multiple_choice': '多选题', 'judge': '判断题', 'essay': '简答题', 'fill_blank': '填空题', 'programming': '编程题' }
  return map[type] || type || '未知'
}

const extractExamInfoFromPhase = (phase) => {
  if (!phase) return { completed: false, passed: false, results: null, examData: null, score: 0, total: 0, hasExamData: false, examCompleted: false }
  const notification = phase._notification || {}
  const examData = notification.exam_data || phase.exam_data || null
  const hasExamData = !!examData && (examData.programming_questions?.length > 0 || examData.theory_questions?.length > 0)
  const examCompleted = notification.exam_completed === true || phase.exam_completed === true
  const examScore = notification.exam_score || phase.exam_score || phase._exam_completed_info?.score || 0
  const examTotal = phase._exam_completed_info?.total || examData?.total_score || 0
  let passed = false
  if (examCompleted && examTotal > 0) {
    passed = examScore >= examTotal * 0.6
  }
  const results = notification.exam_results || phase.exam_results || phase._exam_completed_info?.results || null
  return { completed: examCompleted, passed, results, examData, score: examScore, total: examTotal, hasExamData, examCompleted }
}

// ===================================================================
// API 请求
// ===================================================================
const fetchPlanList = async () => {
  if (!userId.value) return
  showLoadingToast({ message: '数据加载中...', forbidClick: true, duration: 0 })
  try {
    const res = await getPathPlanListApi(userId.value)
    closeToast()
    if (res.code === 1 && res.data?.success) {
      const plans = res.data.plans || []
      planList.value = plans.sort((a, b) => {
        const dateA = a.created_at || a.updated_at || new Date(0)
        const dateB = b.created_at || b.updated_at || new Date(0)
        return new Date(dateB) - new Date(dateA)
      })
      if (planList.value.length > 0) {
        const activePlan = planList.value.find(p => p.is_active === true)
        if (activePlan) {
          selectedPlanId.value = activePlan.plan_id
          await viewPlanDetail(activePlan.plan_id)
        } else {
          selectedPlanId.value = planList.value[0].plan_id
          await viewPlanDetail(planList.value[0].plan_id)
        }
      }
    } else {
      showToast({ type: 'fail', message: res.msg || '获取计划列表失败', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    console.error('获取计划列表异常', err)
    showToast({ type: 'fail', message: '获取计划列表失败', position: 'middle' })
  }
}

const viewPlanDetail = async (planId, versionData = null) => {
  if (!userId.value || !planId) return
  if (!versionData) {
    showLoadingToast({ message: '数据加载中...', forbidClick: true, duration: 0 })
  }
  selectedPlanId.value = planId
  isViewingDetail.value = true
  try {
    await fetchVersionTree(planId)
    if (versionData && versionData.plan) {
      planData.value = { plan: versionData.plan, phases: versionData.plan.phases || [] }
      initKpStates()
      await fetchCurrentProgress(planId)
      await fetchAllPhasesProgress(planId)
      await checkContinuationStatus()
      extractAllPhaseExamStatus()
    } else {
      const actualPlanId = versionTree.value.active_version_plan_id || planId
      selectedPlanId.value = actualPlanId
      const res = await getPlanDetailApi(userId.value, actualPlanId)
      if (!versionData) closeToast()
      if (res.code === 1 && res.data?.success) {
        planData.value = { plan: res.data.plan, phases: res.data.plan.phases || [] }
        initKpStates()
        await fetchCurrentProgress(actualPlanId)
        await fetchAllPhasesProgress(actualPlanId)
        await checkContinuationStatus()
        extractAllPhaseExamStatus()
      } else {
        showToast({ type: 'fail', message: res.msg || '获取计划详情失败', position: 'middle' })
        isViewingDetail.value = false
      }
    }
    // 滚动到顶部
    const el = getScrollEl()
    if (el) el.scrollTop = 0
  } catch (err) {
    if (!versionData) closeToast()
    console.error('获取计划详情异常', err)
    showToast({ type: 'fail', message: '获取计划详情失败', position: 'middle' })
    isViewingDetail.value = false
  }
}

const extractAllPhaseExamStatus = () => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return
  phasesList.forEach((phase, idx) => {
    const info = extractExamInfoFromPhase(phase)
    examCompletedMap.value[idx] = info
    if (info.completed) {
      examResultMap.value[idx] = { results: info.results, examData: info.examData, score: info.score, total: info.total }
    }
  })
}

const initKpStates = () => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return
  kpResourcesMap.value = {}
  kpGeneratedMap.value = {}
  phasesList.forEach((phase, idx) => {
    const kpList = phase.knowledge_points || []
    kpList.forEach(kp => {
      const key = getKpKey(idx, kp)
      kpResourcesMap.value[key] = []
      kpGeneratedMap.value[key] = false
    })
  })
}

const fetchCurrentProgress = async (planId) => {
  if (!userId.value || !planId) return
  try {
    const res = await getProgressApi(userId.value, planId)
    if (res.code === 1 && res.data?.success) {
      totalProgress.value = {
        title: res.data.summary.title || '',
        total_duration: res.data.summary.total_duration || '',
        total_phases: Number(res.data.summary.total_phases) || 0,
        completed_phases: Number(res.data.summary.completed_phases) || 0,
        progress: res.data.summary.progress || '0/0',
        current_phase: res.data.summary.current_phase
      }
      if (res.data.summary.current_phase) {
        currentPhaseIndex.value = res.data.summary.current_phase._index ??
          res.data.summary.current_phase.phase - 1
      }
    }
  } catch (err) {
    console.error('获取总进度失败', err)
  }
}

const fetchAllPhasesProgress = async (planId) => {
  if (!userId.value || !planId) return
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return
  for (let i = 0; i < phasesList.length; i++) {
    await fetchPhaseProgress(i, planId)
  }
}

const fetchPhaseProgress = async (phaseIndex, planId) => {
  if (!userId.value || !planId) return
  try {
    const res = await phaseProgressApi(userId.value, phaseIndex, planId)
    if (res.code === 1 && res.data?.success) {
      const phaseDetail = res.data.phase_detail || res.data
      const total = phaseDetail.total_knowledge_points || 0
      const done = phaseDetail.completed_kps || 0
      const percent = total === 0 ? 0 : Math.round((done / total) * 100)
      phaseProgressMap.value[phaseIndex] = percent
      const kpMap = {}
      if (phaseDetail.knowledge_point_details && phaseDetail.knowledge_point_details.length > 0) {
        phaseDetail.knowledge_point_details.forEach(item => {
          kpMap[item.name] = item.completed
        })
      }
      kpCompletedMap.value[phaseIndex] = kpMap
      const phasesList = planData.value.phases
      if (phasesList && phasesList[phaseIndex]) {
        phasesList[phaseIndex].status = phaseDetail.status
      }
    } else {
      phaseProgressMap.value[phaseIndex] = 0
      kpCompletedMap.value[phaseIndex] = {}
    }
  } catch (err) {
    console.error(`阶段${phaseIndex}进度请求异常`, err)
    phaseProgressMap.value[phaseIndex] = 0
  }
}

const generatePlan = async () => {
  const text = planText.value.trim()
  if (!text) return showToast({ type: 'warning', message: '请输入学习主题', position: 'middle' })
  if (!userId.value) return showToast({ type: 'fail', message: '请先登录', position: 'middle' })
  generating.value = true
  showLoadingToast({ message: '生成学习路径中...', forbidClick: true, duration: 0 })
  try {
    const res = await startPlanApi({ userId: userId.value, text: planText.value, enableTTS: false })
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '学习路径生成成功！', position: 'middle' })
      planText.value = ''
      await fetchPlanList()
    } else if (res.code === 1 && !res.data?.success && res.data?.weak_points_detected) {
      conflictData.value = {
        message: res.data.message || '检测到薄弱环节，是否针对这些问题制定学习计划？',
        weak_points_info: res.data.weak_points_info || [],
        text: planText.value, rsType: 8, taskId: ''
      }
      showConflictDialog.value = true
    } else {
      showToast({ type: 'fail', message: res.msg || '生成失败，请重试', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    console.error('生成计划异常', err)
    showToast({ type: 'fail', message: '网络异常，生成失败', position: 'middle' })
  } finally {
    generating.value = false
  }
}

const handleConflictOption = async (option) => {
  showLoadingToast({ message: '处理中...', forbidClick: true, duration: 0 })
  try {
    const response = await conflictApi(userId.value, {
      id: 'pp_' + conflictData.value.text,
      rsType: conflictData.value.rsType, option: option
    })
    if (response.code === 1) {
      showToast({ type: 'success', message: option ? '已接受，正在生成学习计划...' : '已拒绝，正在生成您的学习计划...', position: 'middle' })
      const res = await startPlanApi({ userId: userId.value, text: conflictData.value.text, enableTTS: false })
      closeToast()
      if (res.code === 1 && res.data?.success) {
        showToast({ type: 'success', message: '学习路径生成成功！', position: 'middle' })
        planText.value = ''
        await fetchPlanList()
      } else {
        showToast({ type: 'fail', message: res.msg || '生成失败，请重试', position: 'middle' })
      }
    } else {
      closeToast()
      showToast({ type: 'fail', message: response.msg || '操作失败', position: 'middle' })
    }
  } catch (error) {
    closeToast()
    console.error('冲突弹窗操作失败:', error)
    showToast({ type: 'fail', message: '网络异常，操作失败', position: 'middle' })
  } finally {
    showConflictDialog.value = false
  }
}

const generateKpResources = async (phaseIndex, knowledgePoint) => {
  if (!userId.value || !selectedPlanId.value) return
  if (!isPhaseUnlocked(phaseIndex)) return showToast({ message: '请先解锁当前阶段', position: 'middle' })
  const key = getKpKey(phaseIndex, knowledgePoint)
  if (isKpGenerated(phaseIndex, knowledgePoint)) {
    return showToast({ message: '该知识点的资源已生成', position: 'middle' })
  }
  if (!generatingResources.value[key]) generatingResources.value[key] = {}
  generatingResources.value[key]['all'] = true
  showLoadingToast({ message: `生成「${knowledgePoint}」资源中...`, forbidClick: true, duration: 0 })
  try {
    const res = await createRsApi(userId.value, phaseIndex, knowledgePoint)
    closeToast()
    if (res.code === 1 && res.data && res.data.points && Array.isArray(res.data.points) && res.data.points.length > 0) {
      kpGeneratedMap.value[key] = true
      kpResourcesMap.value[key] = res.data.points
      showToast({ type: 'success', message: `知识点「${knowledgePoint}」资源生成成功！共 ${res.data.points.length} 个资源`, position: 'middle' })
      await fetchPhaseProgress(phaseIndex, selectedPlanId.value)
    } else {
      showToast({ type: 'warning', message: '资源生成成功，但未返回资源数据', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    console.error('生成知识点资源异常', err)
    showToast({ type: 'fail', message: `知识点「${knowledgePoint}」资源生成失败`, position: 'middle' })
  } finally {
    if (generatingResources.value[key]) generatingResources.value[key]['all'] = false
  }
}

const goResourceDetail = (phaseIndex, resourceType, resourceId) => {
  saveSkip(resourceType, resourceId)
  showNotify({ type: 'success', message: `跳转到 ${resourceTypeName(resourceType)}` })
  const routeMap = {
    0: '/phone/resource/ppt', 1: '/phone/resource/mindmap', 2: '/phone/resource/word',
    3: '/phone/resource/reading', 4: '/phone/resource/code', 5: '/phone/resource/video',
    6: '/phone/resource/anima', 7: '/phone/resource/paper', 8: '/phone/pathPlan'
  }
  const path = routeMap[resourceType]
  if (path) router.push(path)
}

const handleDeletePlan = async (planId) => {
  if (!userId.value) return
  try {
    await showConfirmDialog({
      title: '删除确认',
      message: '确定要删除该学习计划吗？此操作不可恢复！'
    })
    showLoadingToast({ message: '删除中...', forbidClick: true, duration: 0 })
    const res = await delPathPlanApi(userId.value, planId)
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '计划已删除', position: 'middle' })
      planList.value = planList.value.filter(p => p.plan_id !== planId)
      if (selectedPlanId.value === planId) {
        if (planList.value.length > 0) {
          selectedPlanId.value = planList.value[0].plan_id
          await viewPlanDetail(selectedPlanId.value)
        } else {
          selectedPlanId.value = null
          isViewingDetail.value = false
          planData.value = { plan: null, phases: [] }
        }
      }
    } else {
      showToast({ type: 'fail', message: res.msg || '删除失败', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    if (err !== 'cancel') {
      console.error('删除计划异常', err)
      showToast({ type: 'fail', message: '删除失败，请重试', position: 'middle' })
    }
  }
}

const refreshCurrentPlan = async () => {
  if (selectedPlanId.value) await viewPlanDetail(selectedPlanId.value)
}

const silentRefreshPlan = async () => {
  if (!userId.value || !selectedPlanId.value) return
  try {
    const res = await getPlanDetailApi(userId.value, selectedPlanId.value)
    if (res.code === 1 && res.data?.success) {
      planData.value = { plan: res.data.plan, phases: res.data.plan.phases || [] }
      initKpStates()
      extractAllPhaseExamStatus()
    }
  } catch (e) { /* 静默失败 */ }
}

const backToList = () => {
  isViewingDetail.value = false
  selectedPlanId.value = null
  planData.value = { plan: null, phases: [] }
  phaseProgressMap.value = {}
  kpCompletedMap.value = {}
  kpResourcesMap.value = {}
  kpGeneratedMap.value = {}
  generatingResources.value = {}
}

// ===================================================================
// 分享
// ===================================================================
const openShareDialog = async () => {
  if (!selectedPlanId.value || !planData.value?.plan) {
    return showToast({ type: 'warning', message: '请先选择一个学习计划', position: 'middle' })
  }
  shareDialogVisible.value = true
  shareLoading.value = true
  shareForm.value = {
    name: '', subtitle: '', description: '', category: '',
    difficulty: 'beginner', tags: [], target_audience: '',
    cover_color: '#667eea', cover_icon: '📚'
  }
  try {
    const res = await aiShareApi({ plan_data: planData.value.plan })
    if (res.code === 1 && res.data?.success && res.data.route_info) {
      const info = res.data.route_info
      shareForm.value = {
        name: info.name || '', subtitle: info.subtitle || '',
        description: info.description || '', category: info.category || '',
        difficulty: info.difficulty || 'beginner', tags: info.tags || [],
        target_audience: info.target_audience || '',
        cover_color: info.cover_color || '#667eea', cover_icon: info.cover_icon || '📚'
      }
    } else {
      showToast({ type: 'fail', message: res.msg || 'AI分析失败', position: 'middle' })
      shareDialogVisible.value = false
    }
  } catch (e) {
    console.error('AI分析学习计划异常', e)
    showToast({ type: 'fail', message: 'AI分析失败', position: 'middle' })
    shareDialogVisible.value = false
  } finally {
    shareLoading.value = false
  }
}

const closeShareDialog = () => {
  shareDialogVisible.value = false
  shareLoading.value = false
  shareSubmitting.value = false
}

const addShareTag = () => {
  const tag = shareTagInput.value.trim()
  if (tag && !shareForm.value.tags.includes(tag)) {
    shareForm.value.tags.push(tag)
  }
  shareTagInput.value = ''
}

const removeShareTag = (idx) => {
  shareForm.value.tags.splice(idx, 1)
}

const submitShare = async () => {
  if (!shareForm.value.name.trim()) return showToast({ type: 'warning', message: '请输入路线名称', position: 'middle' })
  if (!shareForm.value.category) return showToast({ type: 'warning', message: '请选择分类', position: 'middle' })
  shareSubmitting.value = true
  showLoadingToast({ message: '发布中...', forbidClick: true, duration: 0 })
  try {
    const res = await shareToMarketApi({
      user_id: userId.value,
      plan_data: planData.value.plan,
      route_info: {
        name: shareForm.value.name, subtitle: shareForm.value.subtitle,
        description: shareForm.value.description, category: shareForm.value.category,
        difficulty: shareForm.value.difficulty, tags: shareForm.value.tags,
        target_audience: shareForm.value.target_audience,
        cover_color: shareForm.value.cover_color, cover_icon: shareForm.value.cover_icon
      }
    })
    closeToast()
    if (res.code === 1 && res.data) {
      if (res.data.success) {
        showToast({ type: 'success', message: `分享成功！路线：${res.data.route_name || shareForm.value.name}`, position: 'middle' })
        closeShareDialog()
      } else {
        showToast({ type: 'warning', message: res.data.error || '分享失败', position: 'middle' })
      }
    } else {
      showToast({ type: 'fail', message: res.msg || '分享失败', position: 'middle' })
    }
  } catch (e) {
    closeToast()
    console.error('分享到路线市场异常', e)
    showToast({ type: 'fail', message: '提交失败', position: 'middle' })
  } finally {
    shareSubmitting.value = false
  }
}

// ===================================================================
// 续期
// ===================================================================
const checkContinuationStatus = async () => {
  if (!userId.value) return
  try {
    const res = await checkStatusApi(userId.value, selectedPlanId.value)
    if (res.code === 1 && res.data?.success) {
      hasContinuationPending.value = res.data.continuation_pending || false
      hasContinuationPlan.value = res.data.has_continuation_plan || false
      continuationPlan.value = res.data.continuation_plan || null
      hasCheckedContinuation.value = true
      if (!hasContinuationPending.value && !hasContinuationPlan.value && allPhasesCompleted.value) {
        showNotify({ type: 'success', message: '该学习计划已完成，再接再厉哦~' })
      }
    }
  } catch (err) {
    console.error('检查续期状态异常', err)
  }
}

const fetchVersionTree = async (planId) => {
  if (!userId.value || !planId) return
  versionTreeLoading.value = true
  try {
    const res = await getVersionTreeApi(userId.value, planId)
    if (res.code === 1 && res.data) {
      versionTree.value = {
        versions: res.data.versions || [],
        active_version_plan_id: res.data.active_version_plan_id || '',
        active_version: res.data.active_version || 0,
        has_tree: res.data.has_tree || false,
        root_plan_id: res.data.root_plan_id || ''
      }
    }
  } catch (err) {
    console.error('获取版本树异常', err)
  } finally {
    versionTreeLoading.value = false
  }
}

const handleReCreatePhase = async (phaseIndex) => {
  if (!userId.value || !selectedPlanId.value) return
  if (reCreatingPhase.value[phaseIndex]) return
  try {
    await showConfirmDialog({
      title: '重新生成阶段',
      message: '确认重新生成该阶段？该阶段的学习进度将被重置。'
    })
    reCreatingPhase.value[phaseIndex] = true
    showLoadingToast({ message: '重新生成中...', forbidClick: true, duration: 0 })
    const res = await reCreatePlanApi(userId.value, { phase_index: phaseIndex, plan_id: selectedPlanId.value })
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '阶段重新生成成功', position: 'middle' })
      await viewPlanDetail(selectedPlanId.value)
    } else {
      showToast({ type: 'fail', message: res.data.message || '阶段重新生成失败', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    if (err !== 'cancel') {
      console.error('重新生成阶段异常', err)
      showToast({ type: 'fail', message: '操作失败，请重试', position: 'middle' })
    }
  } finally {
    reCreatingPhase.value[phaseIndex] = false
  }
}

const handleReceiveContinuation = async () => {
  if (!userId.value) return
  if (continuationGenerating.value) return
  try {
    await showConfirmDialog({
      title: '接收续期建议',
      message: '确认接收续期建议？系统将为您生成全新的续期学习计划。'
    })
    continuationGenerating.value = true
    showLoadingToast({ message: '正在生成续期计划...', forbidClick: true, duration: 0 })
    const res = await getCheckMsgApi(userId.value, selectedPlanId.value)
    closeToast()
    if (res.code === 1 && res.data?.success) {
      const planTitle = res.data.message || '新学习计划'
      showToast({ type: 'success', message: `续期计划「${planTitle}」已生成`, position: 'middle' })
      await fetchPlanList()
      hasContinuationPending.value = false
      hasContinuationPlan.value = true
    } else {
      showToast({ type: 'fail', message: '生成续期计划失败', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    if (err !== 'cancel') {
      console.error('接收续期建议异常', err)
      showToast({ type: 'fail', message: '操作失败，请重试', position: 'middle' })
    }
  } finally {
    continuationGenerating.value = false
  }
}

const handleRejectContinuation = async () => {
  if (!userId.value) return
  try {
    await showConfirmDialog({
      title: '拒绝续期建议',
      message: '确认拒绝续期建议？该学习计划将永不生成续期计划。'
    })
    showLoadingToast({ message: '处理中...', forbidClick: true, duration: 0 })
    const res = await rejectCheckMsgApi(userId.value, selectedPlanId.value)
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '已拒绝续期建议', position: 'middle' })
      hasContinuationPending.value = false
      hasContinuationPlan.value = false
      await checkContinuationStatus()
    } else {
      showToast({ type: 'fail', message: '操作失败', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    if (err !== 'cancel') {
      console.error('拒绝续期建议异常', err)
      showToast({ type: 'fail', message: '操作失败，请重试', position: 'middle' })
    }
  }
}

// ===================================================================
// 考试
// ===================================================================
const viewExamAssessment = async (phaseIndex) => {
  const phase = phases.value[phaseIndex]
  if (!phase) return
  const info = extractExamInfoFromPhase(phase)
  if (!info.completed || !info.results) {
    return showToast({ type: 'warning', message: '未找到考试结果', position: 'middle' })
  }
  currentExamPhaseIndex.value = phaseIndex
  examResults.value = {
    score: info.score || 0,
    total: info.total || info.results.length || 0,
    passed: info.passed,
    results: info.results,
    message: info.passed ? `恭喜通过！得分 ${info.score || 0}/${info.total || info.results.length || 0}` : `考试未通过，得分 ${info.score || 0}/${info.total || info.results.length || 0}`
  }
  examShowResults.value = true
  isAllSubmitted.value = true
  examDialogVisible.value = true
}

const updateNextPhasePlan = async () => {
  if (!userId.value || !selectedPlanId.value) return
  updatingNextPhase.value = true
  showLoadingToast({ message: '正在规划下一阶段...', forbidClick: true, duration: 0 })
  try {
    const applyRes = await phaseApplyApi(userId.value, currentExamPhaseIndex.value)
    if (applyRes.success !== true) {
      closeToast()
      showToast({ type: 'fail', message: '接受评估失败，请重试', position: 'middle' })
      return
    }
    await ackNotificationApi(userId.value, currentExamPhaseIndex.value)
    const currentPlanId = selectedPlanId.value
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000))
      try {
        const vtRes = await getVersionTreeApi(userId.value, currentPlanId)
        if (vtRes.code === 1 && vtRes.data?.has_tree && vtRes.data?.versions) {
          const activeId = vtRes.data.active_version_plan_id
          if (activeId && activeId !== currentPlanId) {
            try { await ackNotificationApi(userId.value, currentExamPhaseIndex.value) } catch (e) { console.warn(e) }
            closeExamDialog()
            await viewPlanDetail(activeId)
            closeToast()
            showNotify({ type: 'success', message: '已成功进入下一阶段学习计划！' })
            return
          }
        }
      } catch (e) { console.warn(e) }
    }
    closeToast()
    await refreshCurrentPlan()
    showToast({ type: 'warning', message: '等待超时，请手动刷新查看', position: 'middle' })
  } catch (err) {
    closeToast()
    console.error('[评估] 更新下一阶段计划失败', err)
    showToast({ type: 'fail', message: '更新下一阶段计划失败', position: 'middle' })
  } finally {
    updatingNextPhase.value = false
  }
}

const generateAssessmentReport = async () => {
  if (!userId.value || !selectedPlanId.value || currentExamPhaseIndex.value < 0) return
  generatingAssessment.value = true
  showLoadingToast({ message: '正在生成评估报告...', forbidClick: true, duration: 0 })
  const phase = phases.value[currentExamPhaseIndex.value]
  if (phase?.phase_assessment) {
    assessmentReport.value = {
      assessment_ready: true,
      assessment: phase.phase_assessment,
      phase_index: currentExamPhaseIndex.value,
      phase_name: phase.name || `阶段${currentExamPhaseIndex.value + 1}`
    }
    showAssessmentReport.value = true
    generatingAssessment.value = false
    closeToast()
    return
  }
  try {
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 1000))
      await silentRefreshPlan()
      const p = phases.value[currentExamPhaseIndex.value]
      if (p?.phase_assessment) {
        assessmentReport.value = {
          assessment_ready: true,
          assessment: p.phase_assessment,
          phase_index: currentExamPhaseIndex.value,
          phase_name: p.name || `阶段${currentExamPhaseIndex.value + 1}`
        }
        showAssessmentReport.value = true
        closeToast()
        return
      }
      try {
        const res = await getPhaseNotificationApi(userId.value)
        if (res.success && res.notification && res.notification.assessment_ready) {
          assessmentReport.value = res.notification
          showAssessmentReport.value = true
          closeToast()
          return
        }
      } catch (e) { console.warn(e) }
    }
    closeToast()
    showToast({ type: 'warning', message: '评估报告生成较慢，请稍后刷新查看', position: 'middle' })
  } catch (err) {
    closeToast()
    console.error('[评估] 生成评估报告失败', err)
    showToast({ type: 'fail', message: '生成评估报告失败', position: 'middle' })
  } finally {
    generatingAssessment.value = false
  }
}

const startPhaseExam = async (phaseIndex) => {
  if (!userId.value || !selectedPlanId.value) return
  const phase = phases.value[phaseIndex]
  const info = extractExamInfoFromPhase(phase)
  if (info.passed) {
    viewExamAssessment(phaseIndex)
    return
  }
  examStartingLoading.value[phaseIndex] = true
  examAlreadyCompleted.value = false
  examShowResults.value = false
  examResults.value = null
  currentQuestionIndex.value = 0
  allExamQuestions.value = []
  examAnswers.value = {}
  lineCountMap.value = {}
  exampleExpandedMap.value = {}
  hintExpandedMap.value = {}
  isAllSubmitted.value = false
  if (info.hasExamData) {
    examDialogVisible.value = true
    examData.value = info.examData
    currentExamPhaseIndex.value = phaseIndex
    allExamQuestions.value = flattenExamQuestions(examData.value)
    currentQuestionIndex.value = 0
    allExamQuestions.value.forEach((q, idx) => {
      const key = q.type + '_' + idx
      if (q.type === 'programming') {
        examAnswers.value[key] = ''
        lineCountMap.value[key] = 10
        exampleExpandedMap.value[key] = false
        hintExpandedMap.value[key] = false
      } else if (q.type === 'multiple_choice') {
        examAnswers.value[key] = []
      } else {
        examAnswers.value[key] = ''
      }
    })
    examStartingLoading.value[phaseIndex] = false
    return
  }
  showLoadingToast({ message: '正在准备考试...', forbidClick: true, duration: 0 })
  try {
    const res = await isOpenExamApi(userId.value, phaseIndex, selectedPlanId.value)
    closeToast()
    if (res.code === 1 && res.data?.success) {
      if (res.data.take_exam) {
        await fetchExamQuestions(phaseIndex)
      } else {
        showToast({ message: '已跳过考试，正在进入下一阶段', position: 'middle' })
        await refreshCurrentPlan()
      }
    } else {
      showToast({ type: 'fail', message: '操作失败', position: 'middle' })
    }
  } catch (err) {
    closeToast()
    console.error('开始考试异常', err)
    showToast({ type: 'fail', message: '获取考试数据失败', position: 'middle' })
  } finally {
    examStartingLoading.value[phaseIndex] = false
  }
}

const fetchExamQuestions = async (phaseIndex) => {
  if (!userId.value) return
  examLoading.value = true
  examDialogVisible.value = true
  try {
    const res = await getExamQuestionsApi(userId.value, phaseIndex)
    if (res.code === 1 && res.data?.success === false && res.data?.reason === '考试已完成') {
      examAlreadyCompleted.value = true
      examLoading.value = false
      await refreshCurrentPlan()
      return
    }
    if (res.code === 1 && res.data?.success) {
      examData.value = res.data.exam_data
      currentExamPhaseIndex.value = phaseIndex
      allExamQuestions.value = flattenExamQuestions(examData.value)
      currentQuestionIndex.value = 0
      allExamQuestions.value.forEach((q, idx) => {
        const key = q.type + '_' + idx
        if (q.type === 'programming') {
          examAnswers.value[key] = ''
          lineCountMap.value[key] = 10
          exampleExpandedMap.value[key] = false
          hintExpandedMap.value[key] = false
        } else if (q.type === 'multiple_choice') {
          examAnswers.value[key] = []
        } else {
          examAnswers.value[key] = ''
        }
      })
      examShowResults.value = false
      examResults.value = null
      examAlreadyCompleted.value = false
      isAllSubmitted.value = false
    } else {
      showToast({ type: 'fail', message: res.msg || '获取考题失败', position: 'middle' })
      examDialogVisible.value = false
    }
  } catch (err) {
    console.error('获取考题异常', err)
    showToast({ type: 'fail', message: '获取考题失败', position: 'middle' })
    examDialogVisible.value = false
  } finally {
    examLoading.value = false
  }
}

const flattenExamQuestions = (data) => {
  const result = []
  let index = 0
  if (data.programming_questions && data.programming_questions.length > 0) {
    data.programming_questions.forEach((q, i) => {
      result.push({ ...q, type: 'programming', typeLabel: '编程题', index: index++, originalIndex: i, category: 'programming' })
    })
  }
  if (data.theory_questions && data.theory_questions.length > 0) {
    data.theory_questions.forEach((q, i) => {
      result.push({ ...q, type: q.type || 'single_choice', typeLabel: getQuestionTypeName(q.type || 'single_choice'), index: index++, originalIndex: i, category: 'theory' })
    })
  }
  return result
}

const selectExamAnswer = (question, value) => {
  if (isAllSubmitted.value) return
  const key = question.type + '_' + question.index
  if (question.type === 'multiple_choice') {
    if (!examAnswers.value[key]) examAnswers.value[key] = []
    const arr = examAnswers.value[key]
    const idx = arr.indexOf(value)
    if (idx > -1) arr.splice(idx, 1)
    else arr.push(value)
    if (arr.length === 0) examAnswers.value[key] = []
  } else {
    examAnswers.value[key] = value
  }
}

const isExamOptionSelected = (question, value) => {
  const key = question.type + '_' + question.index
  const answer = examAnswers.value[key]
  if (!answer) return false
  if (Array.isArray(answer)) return answer.includes(value)
  return answer === value
}

const updateLineCount = (question) => {
  const key = question.type + '_' + question.index
  const value = examAnswers.value[key] || ''
  const lines = value.split('\n').length
  lineCountMap.value[key] = Math.max(10, lines)
}

const toggleExampleExpand = (question) => {
  const key = question.type + '_' + question.index
  exampleExpandedMap.value[key] = !exampleExpandedMap.value[key]
}

const toggleHintExpand = (question) => {
  const key = question.type + '_' + question.index
  hintExpandedMap.value[key] = !hintExpandedMap.value[key]
}

const submitAllExamAnswers = async () => {
  if (!userId.value) return
  if (!allQuestionsAnswered.value) return showToast({ type: 'warning', message: '还有题目未作答', position: 'middle' })
  if (isAllSubmitted.value) return showToast({ message: '已提交，请查看结果', position: 'middle' })
  const programmingAnswers = []
  const theoryAnswers = []
  allExamQuestions.value.forEach(q => {
    const key = q.type + '_' + q.index
    const answer = examAnswers.value[key] || ''
    if (q.category === 'programming') programmingAnswers.push(String(answer))
    else theoryAnswers.push(String(answer))
  })
  examSubmitting.value = true
  showLoadingToast({ message: '提交中...', forbidClick: true, duration: 0 })
  try {
    const res = await submitExamAnswersApi(userId.value, currentExamPhaseIndex.value, { programm: programmingAnswers, theory: theoryAnswers })
    closeToast()
    if (res.code === 1 && res.data?.success) {
      isAllSubmitted.value = true
      examResults.value = res.data
      examShowResults.value = true
      showNotify({ type: res.data.passed ? 'success' : 'warning', message: `得分：${res.data.score}/${res.data.total}` })
      await refreshCurrentPlan()
    } else {
      if (res.data?.reason === '考试已完成') {
        isAllSubmitted.value = true
        await refreshCurrentPlan()
        const phase = phases.value[currentExamPhaseIndex.value]
        const info = extractExamInfoFromPhase(phase)
        if (info.results) {
          examResults.value = {
            score: info.score || 0, total: info.total || info.results.length || 0,
            passed: info.passed, results: info.results,
            message: info.passed ? `恭喜通过！得分 ${info.score || 0}/${info.total || info.results.length || 0}` : `考试未通过，得分 ${info.score || 0}/${info.total || info.results.length || 0}`
          }
          examShowResults.value = true
        } else {
          closeExamDialog()
        }
      } else {
        showToast({ type: 'fail', message: res.msg || '提交答案失败', position: 'middle' })
      }
    }
  } catch (err) {
    closeToast()
    console.error('提交考试异常', err)
    showToast({ type: 'fail', message: '提交失败', position: 'middle' })
  } finally {
    examSubmitting.value = false
  }
}

const nextExamQuestion = () => {
  if (currentQuestionIndex.value < allExamQuestions.value.length - 1) currentQuestionIndex.value++
}
const prevExamQuestion = () => {
  if (currentQuestionIndex.value > 0) currentQuestionIndex.value--
}

const closeExamDialog = () => {
  examDialogVisible.value = false
  examData.value = null
  examResults.value = null
  examShowResults.value = false
  currentExamPhaseIndex.value = -1
  examAlreadyCompleted.value = false
  examLoading.value = false
  currentQuestionIndex.value = 0
  allExamQuestions.value = []
  examAnswers.value = {}
  lineCountMap.value = {}
  exampleExpandedMap.value = {}
  hintExpandedMap.value = {}
  isAllSubmitted.value = false
  assessmentReport.value = null
  showAssessmentReport.value = false
  generatingAssessment.value = false
}

// ===================================================================
// 生命周期
// ===================================================================
const skipInfo = ref({})

onMounted(async () => {
  const el = getScrollEl()
  if (el) {
    el.scrollTop = 0
    el.addEventListener('scroll', scrollHandler)
  }
  if (!getUserId()) {
    showToast({ type: 'fail', message: '未检测到登录信息', position: 'middle' })
    return
  }
  await fetchPlanList()
  if (isSkip(8) === false) {
    console.log('没有学习计划需要提前打开')
  } else {
    skipInfo.value = isSkip(8)
    showToast({ type: 'success', message: '为你显示的是当前学习计划', position: 'middle' })
    removeSkip(8)
  }
  emitter.on('versionChanged', async (data) => {
    if (typeof data === 'object' && data.planId) {
      await viewPlanDetail(data.planId, data.data)
    } else {
      await viewPlanDetail(data)
    }
  })
})

onUnmounted(() => {
  emitter.off('versionChanged')
  const el = getScrollEl()
  if (el) el.removeEventListener('scroll', scrollHandler)
})

watch(planList, (newList) => {
  if (!newList || newList.length === 0) {
    isViewingDetail.value = false
    planData.value = { plan: null, phases: [] }
  }
}, { deep: true })
</script>

<template>
  <div class="pp-container">
    <!-- 顶部导航 -->
    <div class="mobile-header">
      <div class="header-back" @click="isViewingDetail ? backToList() : $router.back()">
        <van-icon name="arrow-left" size="20" color="var(--text-title)" />
        <span v-if="isViewingDetail" class="back-text">返回列表</span>
      </div>
      <span class="header-title">智学路径</span>
      <div class="market-btn" @click="showMarket = true">
        <van-icon name="shop-o" size="16" color="#fff" />
        <span>市场</span>
      </div>
    </div>

    <!-- 状态一：无学习计划 -->
    <div v-if="!planList || planList.length === 0" class="no-plan-wrapper">
      <div class="no-plan-card">
        <div class="no-plan-icon">
          <van-icon name="guide-o" size="60" color="var(--primary)" />
        </div>
        <h3>暂无专属学习路径</h3>
        <p>输入你想要学习的内容，AI将为你生成定制化学习计划</p>
        <van-field
          v-model="planText"
          placeholder="例如：从零入门大模型微调开发"
          maxlength="60"
          class="plan-input"
          @keyup.enter="generatePlan"
        />
        <van-button
          type="primary"
          block
          round
          :loading="generating"
          @click="generatePlan"
          class="plan-btn"
        >一键生成路径</van-button>
      </div>
    </div>

    <!-- 状态二：计划列表 -->
    <div v-else-if="planList && planList.length > 0 && !isViewingDetail" class="plan-list-wrapper">
      <!-- 创建新计划 -->
      <div class="create-plan-section">
        <div class="create-plan-label">
          <van-icon name="add-o" size="14" color="var(--primary)" />
          <span>创建新计划</span>
        </div>
        <van-field
          v-model="planText"
          placeholder="输入学习主题..."
          maxlength="60"
          class="create-plan-input"
          @keyup.enter="generatePlan"
        />
        <van-button type="primary" round :loading="generating" @click="generatePlan">点击生成</van-button>
      </div>

      <!-- 计划列表标题 -->
      <div class="plan-list-header">
        <span class="list-title">我的学习计划</span>
        <span class="list-count">共 {{ planList.length }} 个</span>
      </div>

      <!-- 计划卡片 -->
      <div class="plan-list">
        <div
          v-for="plan in planList"
          :key="plan.plan_id"
          class="plan-card"
          @click="viewPlanDetail(plan.plan_id)"
        >
          <div class="plan-card-top">
            <h3 class="plan-title">{{ plan.title }}</h3>
            <!-- <van-tag :type="plan.is_active ? 'primary' : 'default'" plain size="medium">
              {{ plan.is_active ? '激活中' : '已归档' }}
            </van-tag> -->
          </div>
          <div class="plan-card-bottom">
            <div class="plan-meta">
              <span class="meta-item">
                <van-icon name="clock-o" size="12" />
                {{ plan.total_duration || '未设置' }}
              </span>
              <span class="meta-item">
                <van-icon name="calendar-o" size="12" />
                {{ formatDate(plan.created_at) }}
              </span>
            </div>
            <div class="plan-card-footer">
              <van-button type="primary" plain size="small" @click.stop="viewPlanDetail(plan.plan_id)">查看详情</van-button>
              <van-button type="danger" plain size="small" @click.stop="handleDeletePlan(plan.plan_id)">删除</van-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 状态三：计划详情 -->
    <div v-else-if="isViewingDetail && planData && planData.plan" class="has-plan-wrapper">
      <!-- 工具栏 -->
      <div class="detail-toolbar">
        <!-- <van-button plain size="small" icon="arrow-left" @click="backToList">列表</van-button> -->
        <van-button type="primary" plain size="small" icon="replay" @click="refreshCurrentPlan">刷新</van-button>
        <van-button type="primary" size="small" icon="share-o" @click="openShareDialog">分享到学习路线市场</van-button>
        <van-button type="danger" plain size="small" icon="delete-o" @click="handleDeletePlan(selectedPlanId)" :disabled="!selectedPlanId">删除</van-button>
      </div>

      <!-- 总览卡片 -->
      <div class="plan-overview">
        <div class="overview-info">
          <h2>{{ planData.plan?.title || '未命名计划' }}</h2>
          <p class="description" v-if="planData.plan?.description">{{ planData.plan.description }}</p>
          <div class="info-tags">
            <span class="info-tag primary">{{ planData.plan?.total_duration || '未知' }}</span>
            <span class="info-tag" :style="{ color: difficultyType(planData.plan?.difficulty) }">
              {{ planData.plan?.difficulty || '未知' }}
            </span>
            <span class="info-tag">{{ totalProgress.progress || '0/0' }} 阶段</span>
          </div>
        </div>
        <div class="overview-progress">
          <van-circle :percentage="completionPercent" :size="80" :stroke-width="60" color="var(--primary)" layer-color="var(--bg-hover)">
            <template #default>
              <div class="circle-text">
                <span class="circle-num">{{ completionPercent }}%</span>
                <span class="circle-label">完成</span>
              </div>
            </template>
          </van-circle>
        </div>
      </div>

      <!-- 版本树 -->
      <div class="version-tree-section" v-if="versionTree.has_tree && versionTree.versions.length > 0">
        <div class="version-tree-header" @click="versionTreeExpanded = !versionTreeExpanded">
          <div class="vt-title">
            <van-icon name="points" size="16" color="var(--primary)" />
            <span>版本树</span>
            <van-tag plain type="primary" size="medium">v{{ versionTree.active_version }}</van-tag>
          </div>
          <van-icon :name="versionTreeExpanded ? 'arrow-up' : 'arrow-down'" size="14" color="var(--text-gray)" />
        </div>
        <div class="version-tree-content" v-show="versionTreeExpanded">
          <div class="version-tree-loading" v-if="versionTreeLoading">
            <van-loading type="spinner" size="24px" color="var(--primary)">加载中...</van-loading>
          </div>
          <MobileTreeChart
            v-if="!versionTreeLoading"
            :key="versionTree.active_version_plan_id"
            :versions="versionTree.versions"
            :active-plan-id="versionTree.active_version_plan_id"
            :active-version="versionTree.active_version"
            :user-id="userId"
          />
        </div>
      </div>

      <!-- 阶段时间线 -->
      <div class="phases-timeline" v-if="phases && phases.length > 0">
        <div
          v-for="(phase, idx) in phases"
          :key="idx"
          class="phase-item"
          :class="{
            'phase-locked': !isPhaseUnlocked(idx),
            'phase-active': isPhaseUnlocked(idx) && currentPhaseIndex === idx && !isPhaseCompleted(idx),
            'phase-completed': isPhaseCompleted(idx)
          }"
        >
          <!-- 时间线标记 -->
          <div class="timeline-marker">
            <div class="marker-dot">
              <van-icon v-if="isPhaseCompleted(idx)" name="success" size="14" color="#fff" />
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <div class="timeline-line" v-if="idx < phases.length - 1"></div>
          </div>

          <!-- 阶段卡片 -->
          <div class="phase-card">
            <div class="card-header">
              <div class="phase-name">
                {{ phase.name || '未命名阶段' }}
                <van-tag v-if="isPhaseUnlocked(idx)" :color="phaseStatusColor(phase.status)" plain size="medium">
                  {{ phase.status || '未知' }}
                </van-tag>
                <van-tag v-else type="default" plain size="medium">
                  <van-icon name="lock" size="10" /> 未解锁
                </van-tag>
              </div>
              <van-button
                v-if="isPhaseUnlocked(idx)"
                size="mini"
                type="warning"
                plain
                :loading="reCreatingPhase[idx] || false"
                @click="handleReCreatePhase(idx)"
              >重置</van-button>
            </div>

            <!-- 锁定提示 -->
            <div class="phase-lock-tip" v-if="!isPhaseUnlocked(idx)">
              <van-icon name="lock" size="12" />
              <span>通过「{{ idx > 0 ? phases[idx - 1]?.name || '上一阶段' : '上一阶段' }}」考试后解锁</span>
            </div>

            <div class="phase-meta" v-if="isPhaseUnlocked(idx)">
              <span v-if="phase.weeks">{{ phase.weeks }}</span>
              <span v-if="phase.estimated_hours">预计 {{ phase.estimated_hours }}h</span>
            </div>

            <div class="card-desc" v-if="phase.description">{{ phase.description }}</div>

            <div class="card-milestone" v-if="phase.milestone">
              <van-icon name="flag-o" size="12" color="var(--coming)" />
              <span>{{ phase.milestone }}</span>
            </div>

            <div class="card-progress" v-if="isPhaseUnlocked(idx) && phaseProgressMap[idx] !== undefined">
              <van-progress :percentage="phaseProgressMap[idx] || 0" stroke-width="4" :show-pivot="false" color="var(--primary)" />
              <span class="progress-text">{{ phaseProgressMap[idx] || 0 }}%</span>
            </div>

            <!-- 知识点列表 -->
            <div class="kp-list" v-if="phase.knowledge_points && phase.knowledge_points.length > 0">
              <div
                v-for="(kp, kIdx) in phase.knowledge_points"
                :key="kIdx"
                class="kp-item"
                :class="{ 'kp-completed': isKpCompleted(idx, kp) }"
              >
                <div class="kp-row">
                  <div class="kp-info">
                    <span class="kp-badge">{{ kIdx + 1 }}</span>
                    <span class="kp-name">{{ kp }}</span>
                    <van-tag v-if="isKpCompleted(idx, kp)" type="success" plain size="mini">已完成</van-tag>
                  </div>
                  <div class="kp-actions">
                    <div v-if="!isPhaseUnlocked(idx)" class="kp-locked">
                      <van-icon name="lock" size="12" />
                    </div>
                    <van-tag v-else-if="isKpGenerated(idx, kp)" type="success" size="mini">已生成</van-tag>
                    <van-button
                      v-else
                      type="primary"
                      size="mini"
                      :loading="generatingResources[getKpKey(idx, kp)]?.['all'] || false"
                      @click="generateKpResources(idx, kp)"
                    >生成资源</van-button>
                  </div>
                </div>

                <!-- 资源列表 -->
                <div class="kp-resources" v-if="isKpGenerated(idx, kp) && getKpResources(idx, kp).length > 0">
                  <div
                    v-for="(resource, rIdx) in getKpResources(idx, kp)"
                    :key="rIdx"
                    class="kp-resource"
                    @click="goResourceDetail(idx, resource[0], resource[1])"
                  >
                    <div class="resource-info">
                      <van-icon :name="getResourceIcon(resource[0])" size="14" :color="getResourceColor(resource[0])" />
                      <span class="resource-type">{{ resourceTypeName(resource[0]) }}</span>
                      <span class="resource-id">ID:{{ resource[1] }}</span>
                    </div>
                    <van-icon name="arrow" size="12" color="var(--text-gray)" />
                  </div>
                </div>
              </div>
            </div>

            <!-- 考试按钮 -->
            <div class="phase-exam" v-if="isPhaseFullyCompleted(idx)">
              <template v-if="examCompletedMap[idx]?.passed">
                <van-button type="primary" size="small" @click="viewExamAssessment(idx)">查看评估报告</van-button>
                <span class="exam-tip passed">考试已通过</span>
              </template>
              <template v-else-if="examCompletedMap[idx]?.examCompleted">
                <van-button type="danger" size="small" :loading="examStartingLoading[idx] || false" @click="startPhaseExam(idx)">
                  {{ examStartingLoading[idx] ? '准备中...' : '再次考试' }}
                </van-button>
                <span class="exam-tip failed">未通过，点击重考</span>
              </template>
              <template v-else>
                <van-button type="warning" size="small" :loading="examStartingLoading[idx] || false" @click="startPhaseExam(idx)">
                  {{ examStartingLoading[idx] ? '准备中...' : '开始考试' }}
                </van-button>
              </template>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="no-phases-tip">
        <van-empty description="暂无阶段数据" />
      </div>

      <!-- 续期 -->
      <div class="continuation-section" v-if="allPhasesCompleted">
        <div class="continuation-card">
          <div class="continuation-header">
            <van-icon name="flag-o" size="16" color="var(--coming)" />
            <span>生成续期学习计划</span>
          </div>
          <p class="continuation-desc">当前学习计划已全部完成！您可以生成续期学习计划，继续深入学习。</p>
          <div class="continuation-actions">
            <van-button
              type="primary"
              size="small"
              :disabled="hasContinuationPlan || !hasContinuationPending || continuationGenerating"
              :loading="continuationGenerating"
              @click="handleReceiveContinuation"
            >{{ continuationGenerating ? '生成中...' : '立即生成' }}</van-button>
            <van-button
              type="danger"
              size="small"
              plain
              :disabled="hasContinuationPlan || !hasContinuationPending || continuationGenerating"
              @click="handleRejectContinuation"
            >永不生成</van-button>
            <span v-if="hasContinuationPlan || !hasContinuationPending" class="continuation-tip">您已经选择过了</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 回到顶部 -->
    <div class="back-top" v-if="showTopBtn" @click="backTop">
      <van-icon name="back-top" size="20" color="var(--primary)" />
    </div>

    <!-- 分享弹窗 -->
    <van-popup
      v-model:show="shareDialogVisible"
      position="bottom"
      :style="{ height: '85%' }"
      round
      closeable
      close-icon-position="top-right"
    >
      <div class="share-popup">
        <h3 class="share-title">分享到学习路线市场</h3>
        <div v-if="shareLoading" class="share-loading">
          <van-loading type="spinner" size="32px" color="var(--primary)">AI 正在智能分析你的学习计划</van-loading>
        </div>
        <div v-else class="share-form">
          <van-field v-model="shareForm.name" label="路线名称" placeholder="路线名称" required />
          <van-field v-model="shareForm.subtitle" label="一句话介绍" placeholder="用一句话概括" />
          <van-field v-model="shareForm.description" label="路线简介" type="textarea" placeholder="描述路线的核心内容" rows="3" autosize />
          <van-field v-model="shareForm.category" label="分类" placeholder="如：前端开发" required />
          <div class="share-field">
            <span class="share-label">难度</span>
            <div class="diff-btns">
              <span class="diff-btn" :class="{ active: shareForm.difficulty === 'beginner' }" @click="shareForm.difficulty = 'beginner'">入门</span>
              <span class="diff-btn" :class="{ active: shareForm.difficulty === 'medium' }" @click="shareForm.difficulty = 'medium'">进阶</span>
              <span class="diff-btn" :class="{ active: shareForm.difficulty === 'advanced' }" @click="shareForm.difficulty = 'advanced'">高级</span>
            </div>
          </div>
          <div class="share-field">
            <span class="share-label">标签</span>
            <div class="share-tags">
              <span v-for="(tag, idx) in shareForm.tags" :key="idx" class="share-tag">
                {{ tag }}
                <span class="tag-remove" @click="removeShareTag(idx)">&times;</span>
              </span>
              <input
                v-if="shareForm.tags.length < 8"
                v-model="shareTagInput"
                placeholder="回车添加"
                class="tag-input"
                @keydown.enter.prevent="addShareTag"
              />
            </div>
          </div>
          <van-field v-model="shareForm.target_audience" label="适合人群" placeholder="如：零基础" />
          <div class="share-footer">
            <van-button plain @click="closeShareDialog">取消</van-button>
            <van-button type="primary" :loading="shareSubmitting" @click="submitShare">发布到路线市场</van-button>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 考试弹窗 -->
    <van-popup
      v-model:show="examDialogVisible"
      position="bottom"
      :style="{ height: '90%' }"
      round
      :close-on-click-overlay="false"
    >
      <div class="exam-popup">
        <div class="exam-header">
          <h3>{{ examShowResults ? '考试评估' : '阶段考试' }}</h3>
          <van-icon name="cross" size="20" color="var(--text-gray)" @click="closeExamDialog" />
        </div>

        <!-- 加载状态 -->
        <div v-if="examLoading" class="exam-loading">
          <van-loading type="spinner" size="36px" color="var(--primary)">正在生成考题，请稍候...</van-loading>
        </div>

        <!-- 考试已完成 -->
        <div v-else-if="examAlreadyCompleted" class="exam-completed">
          <van-icon name="passed" size="48" color="var(--coming)" />
          <h3>该阶段考试已完成</h3>
          <p>您已经完成了该阶段的考试，无需重复作答。</p>
          <van-button type="primary" @click="closeExamDialog">我知道了</van-button>
        </div>

        <!-- 答题模式 -->
        <template v-else-if="examData && !examShowResults">
          <div class="exam-progress-bar">
            <div class="progress-info">
              <span>进度：{{ completedCount }}/{{ totalExamQuestions }}</span>
              <span v-if="allQuestionsAnswered" class="complete-tag">全部已答</span>
              <span v-else class="incomplete-tag">还有 {{ totalExamQuestions - completedCount }} 题未答</span>
            </div>
            <van-progress :percentage="totalExamQuestions > 0 ? Math.round(completedCount / totalExamQuestions * 100) : 0" stroke-width="6" color="var(--primary)" />
          </div>

          <div class="exam-nav">
            <van-button size="small" plain @click="prevExamQuestion" :disabled="currentQuestionIndex === 0">上一题</van-button>
            <span class="nav-info">{{ currentQuestionIndex + 1 }} / {{ totalExamQuestions }}</span>
            <van-button size="small" type="primary" @click="nextExamQuestion" :disabled="currentQuestionIndex === totalExamQuestions - 1">下一题</van-button>
          </div>

          <div class="exam-question" v-if="currentExamQuestion">
            <div class="question-header">
              <span class="question-type">{{ currentExamQuestion.typeLabel }}</span>
              <span class="question-status" :class="{ answered: isCurrentAnswered, submitted: isAllSubmitted }">
                {{ isAllSubmitted ? '已提交' : (isCurrentAnswered ? '已作答' : '待作答') }}
              </span>
            </div>
            <div class="question-text">{{ currentExamQuestion.question || currentExamQuestion.description }}</div>

            <!-- 选择题 -->
            <div class="options-container" v-if="['single_choice', 'multiple_choice'].includes(currentExamQuestion.type)">
              <div
                v-for="(optText, optIdx) in currentExamQuestion.options"
                :key="optIdx"
                class="option-item"
                :class="{ selected: isExamOptionSelected(currentExamQuestion, String.fromCharCode(65 + optIdx)) }"
                @click="!isAllSubmitted && selectExamAnswer(currentExamQuestion, String.fromCharCode(65 + optIdx))"
              >
                <span class="option-letter">{{ String.fromCharCode(65 + optIdx) }}</span>
                <span class="option-text">{{ optText }}</span>
              </div>
              <div v-if="currentExamQuestion.type === 'multiple_choice'" class="multi-hint">（多选题，可多选）</div>
            </div>

            <!-- 判断题 -->
            <div class="judge-container" v-if="currentExamQuestion.type === 'judge'">
              <div class="judge-options">
                <van-button
                  :type="isExamOptionSelected(currentExamQuestion, '正确') ? 'success' : 'default'"
                  :plain="!isExamOptionSelected(currentExamQuestion, '正确')"
                  @click="!isAllSubmitted && selectExamAnswer(currentExamQuestion, '正确')"
                  :disabled="isAllSubmitted"
                >正确</van-button>
                <van-button
                  :type="isExamOptionSelected(currentExamQuestion, '错误') ? 'danger' : 'default'"
                  :plain="!isExamOptionSelected(currentExamQuestion, '错误')"
                  @click="!isAllSubmitted && selectExamAnswer(currentExamQuestion, '错误')"
                  :disabled="isAllSubmitted"
                >错误</van-button>
              </div>
            </div>

            <!-- 填空题 -->
            <div class="fill-container" v-if="currentExamQuestion.type === 'fill_blank'">
              <van-field
                :model-value="examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index] || ''"
                placeholder="请输入你的答案..."
                :disabled="isAllSubmitted"
                @update:model-value="(val) => { if (!isAllSubmitted) { examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index] = val || ''; } }"
              />
            </div>

            <!-- 简答题 -->
            <div class="short-container" v-if="currentExamQuestion.type === 'essay'">
              <van-field
                :model-value="examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index] || ''"
                type="textarea"
                rows="3"
                autosize
                placeholder="请输入你的答案..."
                :disabled="isAllSubmitted"
                @update:model-value="(val) => { if (!isAllSubmitted) { examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index] = val || ''; } }"
              />
            </div>

            <!-- 编程题 -->
            <div class="programming-container" v-if="currentExamQuestion.type === 'programming'">
              <div class="programming-info" v-if="currentExamQuestion.input_format || currentExamQuestion.output_format">
                <div v-if="currentExamQuestion.input_format" class="info-item">
                  <strong>输入：</strong>{{ currentExamQuestion.input_format }}
                </div>
                <div v-if="currentExamQuestion.output_format" class="info-item">
                  <strong>输出：</strong>{{ currentExamQuestion.output_format }}
                </div>
              </div>

              <div class="programming-examples" v-if="currentExamQuestion.examples && currentExamQuestion.examples.length > 0">
                <div class="section-toggle" @click="!isAllSubmitted && toggleExampleExpand(currentExamQuestion)">
                  <span>示例</span>
                  <van-icon :name="exampleExpandedMap[currentExamQuestion.type + '_' + currentExamQuestion.index] ? 'arrow-up' : 'arrow-down'" size="12" />
                </div>
                <div v-show="exampleExpandedMap[currentExamQuestion.type + '_' + currentExamQuestion.index]" class="section-content">
                  <div v-for="(ex, exIdx) in currentExamQuestion.examples" :key="exIdx" class="example-item">
                    <div><strong>输入{{ exIdx + 1 }}：</strong></div>
                    <pre>{{ ex.input }}</pre>
                    <div><strong>输出{{ exIdx + 1 }}：</strong></div>
                    <pre>{{ ex.output }}</pre>
                  </div>
                </div>
              </div>

              <div class="code-editor">
                <textarea
                  v-model="examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index]"
                  @input="updateLineCount(currentExamQuestion)"
                  placeholder="// 在此编写代码..."
                  class="code-textarea"
                  spellcheck="false"
                  :disabled="isAllSubmitted"
                ></textarea>
              </div>
            </div>
          </div>

          <div class="exam-footer">
            <van-button
              type="primary"
              @click="submitAllExamAnswers"
              :loading="examSubmitting"
              :disabled="!allQuestionsAnswered || examSubmitting"
            >{{ examSubmitting ? '提交中...' : '提交全部答案' }}</van-button>
          </div>
        </template>

        <!-- 考试结果 -->
        <div class="exam-result" v-if="examShowResults && examResults && !showAssessmentReport">
          <div class="result-summary">
            <div class="result-cards">
              <div class="result-card">
                <div class="card-label">总分</div>
                <div class="card-value">{{ examResults.total || totalExamQuestions }}</div>
              </div>
              <div class="result-card">
                <div class="card-label">得分</div>
                <div class="card-value">{{ examResults.score || 0 }}</div>
              </div>
              <div class="result-card">
                <div class="card-label">结果</div>
                <div class="card-value" :class="{ passed: examResults.passed, failed: !examResults.passed }">
                  {{ examResults.passed ? '通过' : '未通过' }}
                </div>
              </div>
            </div>
            <div class="encouragement">
              <div class="encourage-text">{{ examResults.message || '考试完成！' }}</div>
              <div class="wrong-note">错题已自动移入错题本</div>
            </div>
          </div>

          <!-- 错题回顾 -->
          <div class="wrong-review" v-if="examResults.results && examResults.results.some(r => !r.correct)">
            <h4>错题回顾</h4>
            <div
              v-for="(result, idx) in examResults.results.filter(r => !r.correct)"
              :key="idx"
              class="wrong-item"
            >
              <div class="wrong-question">{{ idx + 1 }}. {{ result.question || '题目' }}</div>
              <div class="wrong-answer">正确：{{ result.correct_answer || '-' }}</div>
              <div class="wrong-user-answer">你的：{{ result.user_answer || '未作答' }}</div>
            </div>
          </div>

          <div class="result-footer">
            <van-button @click="closeExamDialog" :disabled="generatingAssessment">关闭</van-button>
            <van-button
              v-if="examResults.passed"
              type="warning"
              @click="generateAssessmentReport"
              :loading="generatingAssessment"
            >{{ generatingAssessment ? '生成中...' : '生成评估报告' }}</van-button>
          </div>
        </div>

        <!-- 评估报告 -->
        <div class="assessment-report" v-if="examShowResults && showAssessmentReport && assessmentReport && assessmentReport.assessment">
          <div class="assessment-header">
            <h3>阶段评估报告</h3>
            <van-tag :type="assessmentReport.assessment.readiness?.ready ? 'success' : 'danger'" size="medium">
              {{ assessmentReport.assessment.phase_summary?.status || (assessmentReport.assessment.readiness?.ready ? '通过' : '未通过') }}
            </van-tag>
          </div>

          <div class="assessment-body">
            <!-- 阶段概览 -->
            <div class="assessment-section" v-if="assessmentReport.assessment.phase_summary">
              <h4>阶段概览</h4>
              <div class="summary-info">
                <span>综合得分：<strong>{{ assessmentReport.assessment.phase_summary.score }}分</strong></span>
                <van-tag size="mini" :type="assessmentReport.assessment.readiness?.ready ? 'success' : 'warning'">
                  {{ assessmentReport.assessment.phase_summary.status }}
                </van-tag>
              </div>
              <p class="summary-text">{{ assessmentReport.assessment.phase_summary.summary }}</p>
            </div>

            <!-- 知识点分析 -->
            <div class="assessment-section" v-if="assessmentReport.assessment.knowledge_point_analysis?.length">
              <h4>知识点掌握分析</h4>
              <div
                v-for="(kp, idx) in assessmentReport.assessment.knowledge_point_analysis"
                :key="idx"
                class="kp-analysis"
              >
                <div class="kp-analysis-header">
                  <span class="kp-analysis-name">{{ kp.name }}</span>
                  <van-tag size="mini" :type="kp.mastery === '薄弱' ? 'danger' : kp.mastery === '良好' ? 'success' : 'warning'">
                    {{ kp.mastery }}
                  </van-tag>
                </div>
                <van-progress :percentage="kp.score" stroke-width="4" :color="kp.score >= 60 ? 'var(--pass)' : kp.score >= 40 ? 'var(--coming)' : 'var(--main-delete)'" />
                <p class="kp-comment">{{ kp.comment }}</p>
              </div>
            </div>

            <!-- 薄弱点 -->
            <div class="assessment-section" v-if="assessmentReport.assessment.weak_points?.length">
              <h4>薄弱点分析</h4>
              <div v-for="(wp, idx) in assessmentReport.assessment.weak_points" :key="idx" class="weak-point-item">
                <div class="weak-point-title">
                  <van-icon name="warning-o" size="12" color="var(--main-delete)" />
                  {{ wp.point }}
                </div>
                <p class="weak-impact"><strong>影响：</strong>{{ wp.impact_on_next_phase }}</p>
              </div>
            </div>

            <!-- 准备度 -->
            <div class="assessment-section" v-if="assessmentReport.assessment.readiness">
              <h4>准备度评估（{{ assessmentReport.assessment.readiness.score }}分）</h4>
              <van-tag :type="assessmentReport.assessment.readiness.ready ? 'success' : 'danger'" size="large">
                {{ assessmentReport.assessment.readiness.ready ? '已准备好进入下一阶段' : '暂不建议进入下一阶段' }}
              </van-tag>
              <div class="readiness-gaps" v-if="assessmentReport.assessment.readiness.gaps?.length">
                <p><strong>待填补差距：</strong></p>
                <ul>
                  <li v-for="(gap, idx) in assessmentReport.assessment.readiness.gaps" :key="idx">{{ gap }}</li>
                </ul>
              </div>
              <div class="readiness-suggestions" v-if="assessmentReport.assessment.readiness.suggestions?.length">
                <p><strong>改进建议：</strong></p>
                <ul>
                  <li v-for="(sug, idx) in assessmentReport.assessment.readiness.suggestions" :key="idx">{{ sug }}</li>
                </ul>
              </div>
            </div>
          </div>

          <div class="assessment-footer">
            <van-button
              type="primary"
              @click="updateNextPhasePlan"
              :loading="updatingNextPhase"
              v-if="currentExamPhaseIndex < phases.length - 1"
            >{{ updatingNextPhase ? '规划中...' : '更新下一阶段计划' }}</van-button>
            <van-button @click="closeExamDialog">关闭</van-button>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- 冲突弹窗 -->
    <van-popup
      v-model:show="showConflictDialog"
      position="center"
      round
      :close-on-click-overlay="false"
      :style="{ width: '85%' }"
    >
      <div class="conflict-dialog">
        <div class="conflict-header">
          <van-icon name="info-o" size="20" color="var(--highlight)" />
          <span>学习计划建议</span>
        </div>
        <div class="conflict-content">
          <div class="conflict-message">{{ conflictData.message }}</div>
          <div v-if="conflictData.weak_points_info.length > 0" class="weak-points-list">
            <div v-for="(point, index) in conflictData.weak_points_info" :key="index" class="weak-point">
              <div class="point-header">
                <span class="point-priority">{{ point.priority }}</span>
                <span class="point-title">{{ point.point }}</span>
              </div>
              <div class="point-performance">{{ point.performance }}</div>
            </div>
          </div>
        </div>
        <div class="conflict-footer">
          <van-button plain type="danger" size="small" @click="handleConflictOption(false)">拒绝</van-button>
          <van-button type="primary" size="small" @click="handleConflictOption(true)">接受</van-button>
        </div>
      </div>
    </van-popup>

    <!-- 学习路线市场 -->
    <MobilePathPlanMarket
      v-if="showMarket"
      :userId="currentUserId"
      @close="showMarket = false"
      @adopted="fetchPlanList"
    />
  </div>
</template>

<style scoped>
.pp-container {
  min-height: 100vh;
  background: var(--bg-page);
  padding-bottom: 60px;
}

/* 顶部导航 */
.mobile-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-back {
  display: flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: background 0.2s;
}

.header-back:active {
  background: var(--bg-hover, rgba(0,0,0,0.05));
}

.back-text {
  font-size: 14px;
  color: var(--text-title);
  font-weight: 500;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

.market-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: var(--primary);
  color: #fff;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.market-btn:active {
  opacity: 0.8;
}

/* 状态一：无计划 */
.no-plan-wrapper {
  padding: 40px 24px;
  display: flex;
  justify-content: center;
}

.no-plan-card {
  text-align: center;
  width: 100%;
  max-width: 360px;
}

.no-plan-icon {
  margin-bottom: 16px;
}

.no-plan-card h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 8px;
}

.no-plan-card p {
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 20px;
  line-height: 1.5;
}

.plan-input {
  margin-bottom: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.plan-btn {
  margin-top: 4px;
}

/* 状态二：计划列表 */
.plan-list-wrapper {
  padding: 16px;
}

.create-plan-section {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 12px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.create-plan-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  width: 100%;
  margin-bottom: 4px;
}

.create-plan-input {
  flex: 1;
  min-width: 120px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.plan-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 0 4px;
}

.list-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}

.list-count {
  font-size: 12px;
  color: var(--text-gray);
}

.plan-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plan-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 14px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
}

.plan-card:active {
  transform: scale(0.98);
}

.plan-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.plan-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  flex: 1;
  margin-right: 8px;
}

.plan-card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
}

.plan-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: var(--text-gray);
  white-space: nowrap;
}

.plan-card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* 状态三：详情 */
.has-plan-wrapper {
  padding: 12px 16px;
}

.detail-toolbar {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.plan-overview {
  display: flex;
  gap: 12px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
}

.overview-info {
  flex: 1;
  min-width: 0;
}

.overview-info h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 6px;
}

.description {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 8px;
  line-height: 1.5;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.info-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.info-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-hover);
  color: var(--text-body);
}

.info-tag.primary {
  background: var(--primary-light);
  color: var(--primary);
}

.overview-progress {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.circle-text {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.circle-num {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
  display: block;
}

.circle-label {
  font-size: 9px;
  color: var(--text-gray);
}

/* 版本树 */
.version-tree-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.version-tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
}

.vt-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
}

.version-tree-content {
  padding: 0 4px 8px;
}

.version-tree-loading {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

/* 阶段时间线 */
.phases-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.phase-item {
  display: flex;
  gap: 10px;
  position: relative;
  min-width: 0;
}

.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  padding-top: 4px;
}

.marker-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  z-index: 2;
}

.phase-completed .marker-dot {
  background: var(--pass);
}

.phase-locked .marker-dot {
  background: var(--text-gray);
}

.timeline-line {
  width: 2px;
  flex: 1;
  background: var(--border-color);
  margin-top: 4px;
  min-height: 20px;
}

.phase-card {
  flex: 1;
  min-width: 0;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 12px 14px;
  margin-bottom: 12px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.phase-locked .phase-card {
  opacity: 0.7;
}

.card-header {
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.phase-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  flex-wrap: wrap;
  min-width: 0;
  overflow: hidden;
}

.phase-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.card-desc {
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.5;
  margin-bottom: 6px;
}

.card-milestone {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--coming);
  margin-bottom: 6px;
}

.card-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-progress .van-progress {
  flex: 1;
}

.progress-text {
  font-size: 11px;
  color: var(--text-gray);
  white-space: nowrap;
}

/* 知识点 */
.kp-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kp-item {
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 8px 10px;
}

.kp-item.kp-completed {
  background: var(--pass-bg-color);
}

.kp-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.kp-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.kp-badge {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.kp-name {
  font-size: 12px;
  color: var(--text-title);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kp-actions {
  flex-shrink: 0;
}

.kp-locked {
  color: var(--text-gray);
}

.kp-resources {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kp-resource {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.kp-resource:active {
  background: var(--bg-hover);
}

.resource-info {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.resource-type {
  font-size: 11px;
  color: var(--text-body);
  font-weight: 500;
}

.resource-id {
  font-size: 10px;
  color: var(--text-gray);
}

/* 考试 */
.phase-exam {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
  flex-wrap: wrap;
}

.exam-tip {
  font-size: 11px;
}

.exam-tip.passed {
  color: var(--pass);
}

.exam-tip.failed {
  color: var(--main-delete);
}

.phase-lock-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-gray);
  margin: 6px 0;
  padding: 6px 10px;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
}

.no-phases-tip {
  padding: 40px 0;
}

/* 续期 */
.continuation-section {
  margin-top: 16px;
}

.continuation-card {
  background: var(--coming-bg-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--coming);
}

.continuation-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 8px;
}

.continuation-desc {
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.5;
  margin-bottom: 12px;
}

.continuation-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.continuation-tip {
  font-size: 11px;
  color: var(--pass);
}

/* 回到顶部 */
.back-top {
  position: fixed;
  right: 16px;
  bottom: 80px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-color);
  z-index: 50;
}

/* 分享弹窗 */
.share-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow-y: auto;
}

.share-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  text-align: center;
  margin-bottom: 16px;
}

.share-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px 0;
}

.share-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.share-field {
  padding: 8px 0;
}

.share-label {
  display: block;
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 8px;
}

.diff-btns {
  display: flex;
  gap: 8px;
}

.diff-btn {
  flex: 1;
  text-align: center;
  padding: 6px;
  font-size: 12px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  color: var(--text-body);
  border: 1px solid var(--border-color);
}

.diff-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.share-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 8px;
  background: var(--bg-input);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.share-tag {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--primary-light);
  color: var(--primary);
}

.tag-remove {
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
}

.tag-input {
  flex: 1;
  min-width: 80px;
  border: none;
  outline: none;
  font-size: 12px;
  background: transparent;
}

.share-footer {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.share-footer .van-button {
  flex: 1;
}

/* 考试弹窗 */
.exam-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.exam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.exam-header h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
}

.exam-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
}

.exam-completed {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 12px;
  text-align: center;
}

.exam-completed h3 {
  font-size: 16px;
  color: var(--text-title);
}

.exam-completed p {
  font-size: 13px;
  color: var(--text-gray);
}

.exam-progress-bar {
  padding: 12px 16px;
  flex-shrink: 0;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--text-body);
}

.complete-tag {
  color: var(--pass);
  font-weight: 600;
}

.incomplete-tag {
  color: var(--coming);
}

.exam-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px 8px;
  flex-shrink: 0;
}

.nav-info {
  font-size: 13px;
  color: var(--text-gray);
}

.exam-question {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 16px;
  -webkit-overflow-scrolling: touch;
}

.question-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.question-type {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 600;
}

.question-status {
  font-size: 11px;
  color: var(--text-gray);
}

.question-status.answered {
  color: var(--pass);
}

.question-status.submitted {
  color: var(--primary);
}

.question-text {
  font-size: 14px;
  color: var(--text-title);
  line-height: 1.6;
  margin-bottom: 16px;
  font-weight: 500;
}

.options-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.5;
}

.option-item.selected {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary);
}

.option-letter {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.option-item.selected .option-letter {
  background: var(--primary);
  color: #fff;
}

.multi-hint {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 4px;
}

.judge-container {
  display: flex;
  gap: 12px;
}

.judge-options {
  display: flex;
  gap: 12px;
  flex: 1;
}

.judge-options .van-button {
  flex: 1;
}

.fill-container, .short-container {
  margin-top: 4px;
}

.programming-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.programming-info {
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  font-size: 11px;
  color: var(--text-body);
}

.info-item {
  margin-bottom: 2px;
}

.section-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-body);
  font-weight: 500;
}

.section-content {
  padding: 8px 10px;
}

.example-item {
  font-size: 11px;
  color: var(--text-body);
  margin-bottom: 8px;
}

.example-item pre {
  background: var(--canvas-bg);
  color: var(--canvas-hint-text);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  overflow-x: auto;
  margin: 4px 0;
}

.code-editor {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.code-textarea {
  width: 100%;
  min-height: 200px;
  padding: 10px;
  border: none;
  outline: none;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  background: var(--bg-input);
  color: var(--text-title);
  resize: vertical;
}

.exam-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.exam-footer .van-button {
  width: 100%;
}

/* 考试结果 */
.exam-result {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  -webkit-overflow-scrolling: touch;
}

.result-cards {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.result-card {
  flex: 1;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 12px 8px;
  text-align: center;
  border: 1px solid var(--border-color);
}

.card-label {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 4px;
}

.card-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title);
}

.card-value.passed {
  color: var(--pass);
}

.card-value.failed {
  color: var(--main-delete);
}

.encouragement {
  text-align: center;
  margin-bottom: 16px;
}

.encourage-text {
  font-size: 14px;
  color: var(--text-title);
  font-weight: 600;
  margin-bottom: 4px;
}

.wrong-note {
  font-size: 11px;
  color: var(--text-gray);
}

.wrong-review h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 8px;
}

.wrong-item {
  background: var(--main-fail-status);
  border-radius: var(--radius-md);
  padding: 10px;
  margin-bottom: 8px;
}

.wrong-question {
  font-size: 12px;
  color: var(--text-title);
  margin-bottom: 4px;
}

.wrong-answer {
  font-size: 11px;
  color: var(--pass);
  margin-bottom: 2px;
}

.wrong-user-answer {
  font-size: 11px;
  color: var(--main-delete);
}

.result-footer {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.result-footer .van-button {
  flex: 1;
}

/* 评估报告 */
.assessment-report {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.assessment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.assessment-header h3 {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-title);
}

.assessment-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  -webkit-overflow-scrolling: touch;
}

.assessment-section {
  margin-bottom: 16px;
}

.assessment-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 8px;
}

.summary-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-body);
  margin-bottom: 6px;
}

.summary-text {
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.5;
}

.kp-analysis {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 10px;
  margin-bottom: 8px;
  border: 1px solid var(--border-color);
}

.kp-analysis-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.kp-analysis-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-title);
}

.kp-comment {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 4px;
  line-height: 1.4;
}

.weak-point-item {
  background: var(--main-fail-status);
  border-radius: var(--radius-md);
  padding: 10px;
  margin-bottom: 8px;
}

.weak-point-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-title);
  font-weight: 600;
  margin-bottom: 4px;
}

.weak-impact {
  font-size: 11px;
  color: var(--text-body);
  line-height: 1.4;
}

.readiness-gaps, .readiness-suggestions {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-body);
}

.readiness-gaps ul, .readiness-suggestions ul {
  padding-left: 20px;
  margin-top: 4px;
}

.readiness-gaps li, .readiness-suggestions li {
  font-size: 11px;
  color: var(--text-body);
  margin-bottom: 2px;
}

.assessment-footer {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.assessment-footer .van-button {
  flex: 1;
}

/* 冲突弹窗 */
.conflict-dialog {
  padding: 20px;
}

.conflict-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 12px;
}

.conflict-content {
  margin-bottom: 16px;
}

.conflict-message {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.5;
  margin-bottom: 12px;
}

.weak-points-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.weak-point {
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 8px 10px;
}

.point-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.point-priority {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--main-delete);
  color: #fff;
  font-weight: 600;
}

.point-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-title);
}

.point-performance {
  font-size: 11px;
  color: var(--text-gray);
}

.conflict-footer {
  display: flex;
  gap: 12px;
}

.conflict-footer .van-button {
  flex: 1;
}
</style>

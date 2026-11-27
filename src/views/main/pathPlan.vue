<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox, ElNotification, ElLoading } from 'element-plus'
import { saveSkip, isSkip, removeSkip } from '@/utils/skip.js'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import {
  isCreateApi, startPlanApi, getProgressApi, createRsApi, phaseProgressApi,
  getPathPlanListApi, delPathPlanApi, getPlanDetailApi, checkStatusApi, getCheckMsgApi,
  isOpenExamApi, getExamQuestionsApi, submitExamAnswersApi, rejectCheckMsgApi,
  getVersionTreeApi,changeVersionApi,reCreatePlanApi,
  phaseApplyApi, ackNotificationApi, getPhaseNotificationApi,
  aiShareApi, shareToMarketApi
} from '@/api/mainApi/pathPlan.js'
import TreeChart from '@/components/treeChart.vue'
import PathPlanMarket from '@/components/pathPlanMarket.vue'
import emitter from '@/utils/emitter.js'
import { conflictApi } from '@/api/mainApi/aiAnswer.js'//冲突选择接口

// 导入代码编辑器快捷键处理
import { createCodeKeydownHandler } from '@/views/main/resourceNav/codeInput.js'

const router = useRouter()

// ===================================================================
// 一、数据定义区
// ===================================================================

/** 生成学习计划的加载状态 */
const generating = ref(false)

/** 一键生成资源的加载状态（按阶段索引+知识点记录） */
const generatingResources = ref({})

/** 当前登录用户ID */
const userId = ref(null)

/** 主题状态 */
const themeStore = useThemeStore()

/** 获取加载遮罩背景色 */
const getLoadingBg = () => {
  return themeStore.isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.9)'
}

/** 冲突弹窗相关 */
const showConflictDialog = ref(false)
const conflictData = ref({
  message: '',
  weak_points_info: [],
  text: '',
  rsType: -1,
  taskId: ''
})

/** 学习计划列表 - 初始化为空数组 */
const planList = ref([])

/** 当前选中的计划ID */
const selectedPlanId = ref(null)

/** 是否正在查看计划详情 */
const isViewingDetail = ref(false)

/** 是否显示学习路线市场 */
const showMarket = ref(false)

/** 当前用户ID */
const currentUserId = computed(() => {
  const user = JSON.parse(localStorage.getItem('loginUser') || '{}')
  return user.id || user.user_id || ''
})

/** 是否已拥有学习计划（至少有一个计划） */
const hasPlan = computed(() => {
  return planList.value && planList.value.length > 0
})

/** 当前选中的计划数据（从列表中获取） */
const selectedPlan = computed(() => {
  if (!planList.value || !selectedPlanId.value) return null
  return planList.value.find(p => p.plan_id === selectedPlanId.value) || null
})

/** 
 * 学习计划主体数据（详情）
 * plan: 计划概要信息（标题、描述、总时长等）
 * phases: 阶段列表（每个阶段包含名称、知识点、资源类型等）
 */
const planData = ref({
  plan: null,
  phases: []
})

/** 计算属性：阶段列表的便捷引用 */
const phases = computed(() => {
  return planData.value?.phases || []
})

/**
 * 全局进度总览数据
 */
const totalProgress = ref({
  title: '',
  total_duration: '',
  total_phases: 0,
  completed_phases: 0,
  progress: '0/0',
  current_phase: null
})

/** 当前正在进行的阶段索引（从0开始） */
const currentPhaseIndex = ref(-1)

/** 用户输入的学习主题/提示词 */
const planText = ref('')

/**
 * 各阶段进度百分比映射
 */
const phaseProgressMap = ref({})

/**
 * 各阶段知识点完成状态映射
 */
const kpCompletedMap = ref({})

/**
 * 各阶段各知识点的资源数据
 * key: 阶段索引_知识点名称, value: [ [资源类型, 资源id], ... ]
 */
const kpResourcesMap = ref({})

/**
 * 各阶段各知识点是否已生成资源
 * key: 阶段索引_知识点名称, value: boolean
 */
const kpGeneratedMap = ref({})

// ===================================================================
// 续期计划相关数据
// ===================================================================

/** 续期计划相关 */
const continuationInfo = ref(null)
const hasContinuationPending = ref(false)
const hasContinuationPlan = ref(false)
const continuationPlan = ref(null)

/** 是否已检查续期状态 */
const hasCheckedContinuation = ref(false)

/** 续期计划生成加载状态 */
const continuationGenerating = ref(false)

// ===================================================================
// 版本树相关数据
// ===================================================================

const versionTree = ref({
  versions: [],
  active_version_plan_id: '',
  active_version: 0,
  has_tree: false,
  root_plan_id: ''
})

const versionTreeLoading = ref(false)

const reCreatingPhase = ref({})

const versionTreeExpanded = ref(true)

// ===================================================================
// 考试相关数据
// ===================================================================

/** 考试弹窗 */
const examDialogVisible = ref(false)
const examData = ref(null)
const currentExamPhaseIndex = ref(-1)
const examSubmitting = ref(false)
const examResults = ref(null)
const examShowResults = ref(false)

/** 获取考题的加载状态 */
const examLoading = ref(false)

/** 考试已完成状态（弹窗内使用） */
const examAlreadyCompleted = ref(false)

/** 考试开始按钮的加载状态（每个阶段独立） */
const examStartingLoading = ref({})

/** 考试答案 - 按索引存储 */
const examAnswers = ref({})

/** 编程题行数 */
const lineCountMap = ref({})

/** 当前题目索引 */
const currentQuestionIndex = ref(0)

/** 所有题目列表（展平） */
const allExamQuestions = ref([])

/** 编程题示例展开状态 */
const exampleExpandedMap = ref({})

/** 编程题提示展开状态 */
const hintExpandedMap = ref({})

/** 是否已提交全部答案 */
const isAllSubmitted = ref(false)

/** 各阶段考试完成状态（从数据中读取） */
const examCompletedMap = ref({})

/** 各阶段考试结果数据 */
const examResultMap = ref({})

// ===================================================================
// 分享到学习路线市场相关数据
// ===================================================================

const shareDialogVisible = ref(false)
const shareLoading = ref(false)
const shareSubmitting = ref(false)
const shareTagInput = ref('')
const shareForm = ref({
  name: '',
  subtitle: '',
  description: '',
  category: '',
  difficulty: 'beginner',
  tags: [],
  target_audience: '',
  cover_color: '#667eea',
  cover_icon: '📚'
})

// ===================================================================
// 计算属性
// ===================================================================

/** 是否所有阶段已完成（用于控制续期按钮） */
const allPhasesCompleted = computed(() => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  return phasesList.every(p => p.status === '已完成')
})

/** 计算整体完成百分比 */
const completionPercent = computed(() => {
  const total = Number(totalProgress.value.total_phases) || 1
  const done = Number(totalProgress.value.completed_phases) || 0
  return Math.round((done / total) * 100)
})

/** 当前题目 */
const currentExamQuestion = computed(() => {
  if (!allExamQuestions.value.length) return null
  return allExamQuestions.value[currentQuestionIndex.value] || null
})

/** 当前题目是否已作答 */
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

/** 所有题目是否都已作答 */
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

/** 已完成题数 */
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

/** 总题数 */
const totalExamQuestions = computed(() => {
  return allExamQuestions.value.length
})

// ===================================================================
// 二、工具辅助方法区
// ===================================================================

/**
 * 从 localStorage 读取当前登录用户ID
 */
const getUserId = () => {
  const userStr = localStorage.getItem('loginUser')
  if (!userStr) return false
  try {
    const loginUser = JSON.parse(userStr)

    if (loginUser?.id) {
      // 判断登录用户类型
      if(loginUser.isNew == false && loginUser.isBuildProfile == 0){
        ElMessage.warning('请进行画像构建~')
        router.push('/aiAnswer')
      }
      userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      return true
    }
  } catch (err) {
    console.error('解析登录用户失败', err)
  }
  return false
}

/**
 * 根据难度等级返回对应的 Element Plus 标签类型
 */
const difficultyType = (difficulty) => {
  if (!difficulty) return 'info'
  if (difficulty === '简单') return 'success'
  if (difficulty === '中等') return 'warning'
  if (difficulty === '困难') return 'danger'
  return 'info'
}

/**
 * 根据阶段状态返回对应的标签类型
 */
const phaseStatusType = (status) => {
  if (status === '已完成') return 'success'
  if (status === '进行中') return 'primary'
  return 'info'
}

/**
 * 生成知识点资源的唯一key
 */
const getKpKey = (phaseIndex, knowledgePoint) => {
  return `${phaseIndex}_${knowledgePoint}`
}

/**
 * 将资源类型代码转换为中文名称
 */
const resourceTypeName = (type) => {
  const map = {
    0: 'PPT课件',
    1: '思维导图',
    2: '讲解文档',
    3: '拓展阅读',
    4: '编程题',
    5: '视频教程',
    6: '动画演示',
    7: '试卷',
    8: '学习计划'
  }
  return map[type] || `未知类型(${type})`
}

/**
 * 根据资源类型返回对应的图标组件
 */
const getResourceIcon = (type) => {
  const map = {
    0: 'Document',
    1: 'Connection',
    2: 'Document',
    3: 'Tickets',
    4: 'EditPen',
    5: 'VideoCamera',
    6: 'Film',
    7: 'Reading',
    8: 'Guide'
  }
  return map[type] || 'Document'
}

/**
 * 根据资源类型返回对应的颜色
 */
const getResourceColor = (type) => {
  const map = {
    0: '#FF6B6B',
    1: '#4ECDC4',
    2: '#45B7D1',
    3: '#96CEB4',
    4: '#FFEAA7',
    5: '#DDA0DD',
    6: '#FF9FF3',
    7: '#54A0FF',
    8: '#5F27CD'
  }
  return map[type] || '#95A5A6'
}

/**
 * 根据资源类型返回对应的标签类型
 */
const getResourceTagType = (type) => {
  const map = {
    0: 'danger',
    1: 'success',
    2: 'primary',
    3: 'warning',
    4: 'warning',
    5: 'danger',
    6: 'info',
    7: 'primary',
    8: 'success'
  }
  return map[type] || 'info'
}

/**
 * 判断某个阶段是否已解锁
 */
const isPhaseUnlocked = (phaseIndex) => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  if (phaseIndex === 0) return true
  const prev = phasesList[phaseIndex - 1]
  if (prev?.status !== '已完成') return false
  const prevExamInfo = extractExamInfoFromPhase(prev)
  return prevExamInfo.passed
}

/**
 * 判断某个阶段是否已全部完成
 */
const isPhaseCompleted = (phaseIndex) => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  return phasesList[phaseIndex]?.status === '已完成'
}

/**
 * 判断某个知识点是否已完成
 */
const isKpCompleted = (phaseIndex, kpName) => {
  const map = kpCompletedMap.value[phaseIndex] || {}
  return !!map[kpName]
}

/**
 * 判断某个知识点的资源是否已生成
 */
const isKpGenerated = (phaseIndex, knowledgePoint) => {
  const key = getKpKey(phaseIndex, knowledgePoint)
  return !!kpGeneratedMap.value[key]
}

/**
 * 获取某个知识点的资源列表
 */
const getKpResources = (phaseIndex, knowledgePoint) => {
  const key = getKpKey(phaseIndex, knowledgePoint)
  return kpResourcesMap.value[key] || []
}

/**
 * 获取阶段的知识点列表
 */
const getKnowledgePoints = (phaseIndex) => {
  const phase = phases.value[phaseIndex]
  if (!phase) return []
  return phase.knowledge_points || []
}

/** 格式化日期 */
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * 判断阶段是否已完成（所有知识点完成 + 状态为已完成）
 */
const isPhaseFullyCompleted = (phaseIndex) => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return false
  const phase = phasesList[phaseIndex]
  if (!phase) return false
  
  // 阶段状态为"已完成"
  if (phase.status !== '已完成') return false
  
  const kpMap = kpCompletedMap.value[phaseIndex] || {}
  const kpList = phase.knowledge_points || []
  if (kpList.length === 0) return false
  
  return kpList.every(kp => kpMap[kp] === true)
}

/**
 * 获取题目类型名称
 */
const getQuestionTypeName = (type) => {
  const map = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'judge': '判断题',
    'essay': '简答题',
    'fill_blank': '填空题',
    'programming': '编程题'
  }
  return map[type] || type || '未知'
}

/**
 * 获取分析标签
 */
const getAnalysisLabel = (key) => {
  const map = {
    'correctness': '正确性',
    'logic': '逻辑',
    'code_quality': '代码质量',
    'efficiency': '效率'
  }
  return map[key] || key
}

/**
 * 从阶段数据中提取考试完成状态和结果
 */
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
  
  return {
    completed: examCompleted,
    passed,
    results,
    examData,
    score: examScore,
    total: examTotal,
    hasExamData,
    examCompleted
  }
}

// ===================================================================
// 三、API 请求方法区
// ===================================================================

// ===================================================================
// 三、API 请求方法区 - 修改 fetchPlanList
// ===================================================================

/**
 * 1. 获取学习计划列表
 */
const fetchPlanList = async () => {
  if (!userId.value) return
  let loadingInstance = ElLoading.service({
    fullscreen: true,
    text: '数据加载中...',
    background: getLoadingBg()
  })
  try {
    const res = await getPathPlanListApi(userId.value)
    if (res.code === 1 && res.data?.success) {
      // 倒序排序：按创建时间从新到旧
      const plans = res.data.plans || []
      planList.value = plans.sort((a, b) => {
        // 如果 created_at 不存在，用 updated_at 或当前时间作为备选
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
      ElMessage.warning(res.msg || '获取计划列表失败')
    }
  } catch (err) {
    console.error('获取计划列表异常', err)
    ElMessage.error('获取计划列表失败，请重试')
  } finally {
    loadingInstance.close()
  }
}

/**
 * 2. 查看计划详情
 */
const viewPlanDetail = async (planId, versionData = null) => {
  if (!userId.value || !planId) return
  
  let loadingInstance = null
  if (!versionData) {
    loadingInstance = ElLoading.service({
      fullscreen: true,
      text: '数据加载中...',
      background: getLoadingBg()
    })
  }
  
  selectedPlanId.value = planId
  isViewingDetail.value = true
  
  try {
    // 先获取版本树，确定当前活跃版本
    await fetchVersionTree(planId)
    
    if (versionData && versionData.plan) {
      planData.value = {
        plan: versionData.plan,
        phases: versionData.plan.phases || []
      }
      // 初始化资源状态
      initKpStates()
      // 拉取进度数据 - 使用传入的planId（切换的目标版本）
      await fetchCurrentProgress(planId)
      await fetchAllPhasesProgress(planId)
      
      // 检查续期状态
      await checkContinuationStatus()
      
      // 提取各阶段的考试完成状态
      extractAllPhaseExamStatus()
    } else {
      // 获取当前活跃版本的计划ID（可能与传入的planId不同）
      const actualPlanId = versionTree.value.active_version_plan_id || planId
      
      // 更新选中的计划ID为当前活跃版本
      selectedPlanId.value = actualPlanId
      
      const res = await getPlanDetailApi(userId.value, actualPlanId)
      if (res.code === 1 && res.data?.success) {
        planData.value = {
          plan: res.data.plan,
          phases: res.data.plan.phases || []
        }
        // 初始化资源状态
        initKpStates()
        // 拉取进度数据
        await fetchCurrentProgress(actualPlanId)
        await fetchAllPhasesProgress(actualPlanId)
        
        // 检查续期状态
        await checkContinuationStatus()
        
        // 提取各阶段的考试完成状态
        extractAllPhaseExamStatus()
      } else {
        ElMessage.error(res.msg || '获取计划详情失败')
        isViewingDetail.value = false
      }
    }
  } catch (err) {
    console.error('获取计划详情异常', err)
    ElMessage.error('获取计划详情失败，请重试')
    isViewingDetail.value = false
  } finally {
    if (loadingInstance) loadingInstance.close()
  }
}

/**
 * 提取所有阶段的考试完成状态
 */
const extractAllPhaseExamStatus = () => {
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return
  
  phasesList.forEach((phase, idx) => {
    const info = extractExamInfoFromPhase(phase)
    examCompletedMap.value[idx] = info
    if (info.completed) {
      examResultMap.value[idx] = {
        results: info.results,
        examData: info.examData,
        score: info.score,
        total: info.total
      }
    }
  })
}

/**
 * 初始化知识点资源状态
 */
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

/**
 * 3. 获取全局总进度 / 当前所处阶段
 */
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

/**
 * 4. 批量拉取所有阶段的进度
 */
const fetchAllPhasesProgress = async (planId) => {
  if (!userId.value || !planId) return
  const phasesList = phases.value
  if (!phasesList || phasesList.length === 0) return
  
  for (let i = 0; i < phasesList.length; i++) {
    await fetchPhaseProgress(i, planId)
  }
}

/**
 * 5. 拉取单个阶段的完成详情
 */
const fetchPhaseProgress = async (phaseIndex, planId) => {
  if (!userId.value || !planId) return
  try {
    const res = await phaseProgressApi(userId.value, phaseIndex, planId)

    // 调用java
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

    // 直接调用py
    // if (res.success) {
    //   const total = res.total_knowledge_points || 0
    //   const done = res.completed_kps || 0
    //   const percent = total === 0 ? 0 : Math.round((done / total) * 100)
    //   phaseProgressMap.value[phaseIndex] = percent

    //   const kpMap = {}
    //   if (res.knowledge_point_details && res.knowledge_point_details.length > 0) {
    //     res.knowledge_point_details.forEach(item => {
    //       kpMap[item.name] = item.completed
    //     })
    //   }
    //   kpCompletedMap.value[phaseIndex] = kpMap

    //   const phasesList = planData.value.phases
    //   if (phasesList && phasesList[phaseIndex]) {
    //     phasesList[phaseIndex].status = res.status
    //   }
    // } else {
    //   phaseProgressMap.value[phaseIndex] = 0
    //   kpCompletedMap.value[phaseIndex] = {}
    // }
  } catch (err) {
    console.error(`阶段${phaseIndex}进度请求异常`, err)
    phaseProgressMap.value[phaseIndex] = 0
  }
}

/**
 * 6. AI 生成全新学习路径
 */
const generatePlan = async () => {
  const text = planText.value.trim()
  if (!text) return ElMessage.warning('请输入学习主题')
  if (!userId.value) return ElMessage.error('请先登录')

  generating.value = true
  try {
    const res = await startPlanApi({
      userId: userId.value,
      text: planText.value,
      enableTTS: false
    })
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('学习路径生成成功！')
      planText.value = ''
      await fetchPlanList()
    } else if (res.code === 1 && !res.data?.success && res.data?.weak_points_detected) {
      conflictData.value = {
        message: res.data.message || '检测到薄弱环节，是否针对这些问题制定学习计划？',
        weak_points_info: res.data.weak_points_info || [],
        text: planText.value,
        rsType: 8,
        taskId: ''
      }
      showConflictDialog.value = true
    } else {
      ElMessage.error(res.msg || '生成失败，请重试')
    }
  } catch (err) {
    console.error('生成计划异常', err)
    ElMessage.error('网络异常，生成失败')
  } finally {
    generating.value = false
  }
}

// 处理冲突弹窗选择
const handleConflictOption = async (option) => {
  try {
    const response = await conflictApi(userId.value, {
      id: 'pp_'+conflictData.value.text,
      rsType: conflictData.value.rsType,
      option: option
    })
    if (response.code === 1) {
      ElMessage.success(option ? '已接受，正在生成学习计划...' : '已拒绝，正在生成您的学习计划...')
      if (option) {
        const res = await startPlanApi({
          userId: userId.value,
          text: conflictData.value.text,
          enableTTS: false
        })
        if (res.code === 1 && res.data?.success) {
          ElMessage.success('学习路径生成成功！')
          planText.value = ''
          await fetchPlanList()
        } else {
          ElMessage.error(res.msg || '生成失败，请重试')
        }
      } else {
        const res = await startPlanApi({
          userId: userId.value,
          text: conflictData.value.text,
          enableTTS: false
        })
        if (res.code === 1 && res.data?.success) {
          ElMessage.success('学习路径生成成功！')
          planText.value = ''
          await fetchPlanList()
        } else {
          ElMessage.error(res.msg || '生成失败，请重试')
        }
      }
    } else {
      ElMessage.error(response.msg || '操作失败')
    }
  } catch (error) {
    console.error('冲突弹窗操作失败:', error)
    ElMessage.error('网络异常，操作失败')
  } finally {
    showConflictDialog.value = false
  }
}

/**
 * 7. 一键生成知识点资源
 */
const generateKpResources = async (phaseIndex, knowledgePoint) => {
  if (!userId.value || !selectedPlanId.value) return
  if (!isPhaseUnlocked(phaseIndex)) return ElMessage.info('请先解锁当前阶段')
  
  const key = getKpKey(phaseIndex, knowledgePoint)
  if (isKpGenerated(phaseIndex, knowledgePoint)) {
    return ElMessage.info('该知识点的资源已生成')
  }

  // 设置加载状态
  if (!generatingResources.value[key]) {
    generatingResources.value[key] = {}
  }
  generatingResources.value[key]['all'] = true

  try {
    const res = await createRsApi(userId.value, phaseIndex, knowledgePoint)
    
    if (res.code === 1 && res.data && res.data.points && Array.isArray(res.data.points) && res.data.points.length > 0) {
      kpGeneratedMap.value[key] = true
      kpResourcesMap.value[key] = res.data.points
      
      ElMessage.success(`知识点「${knowledgePoint}」资源生成/查找成功！共生成/查找 ${res.data.points.length} 个资源`)
      
      // 刷新本阶段进度
      await fetchPhaseProgress(phaseIndex, selectedPlanId.value)
    } else {
      ElMessage.warning('资源生成成功，但未返回资源数据')
    }
  } catch (err) {
    console.error('生成知识点资源异常', err)
    ElMessage.error(`知识点「${knowledgePoint}」资源生成失败，请稍后重试`)
  } finally {
    if (generatingResources.value[key]) {
      generatingResources.value[key]['all'] = false
    }
  }
}

/**
 * 8. 跳转到资源详情
 */
const goResourceDetail = (phaseIndex, resourceType, resourceId) => {
  console.log('跳转到资源详情', { phaseIndex, resourceType, resourceTypeName: resourceTypeName(resourceType), resourceId })
  saveSkip(resourceType, resourceId)
  ElNotification({
    title: '操作提示',
    message: `跳转到 ${resourceTypeName(resourceType)} 详情，资源ID: ${resourceId}`,
    type: 'success',
    position: 'bottom-left',
    duration: 3000,
    showClose: true,
  })
  switch(resourceType){
    case 0:
      router.push('/ppt')
      break
    case 1:
      router.push('/mindMap')
      break
    case 2:
      router.push('/word')
      break
    case 3:
      router.push('/reading')
      break
    case 4:
      router.push('/code')
      break
    case 5:
      router.push('/video')
      break
    case 6:
      router.push('/anima')
      break
    case 7:
      router.push('/paper')
      break
    case 8:
      router.push('/pathPlan')
      break
    default:
      console.log('不存在该资源，无法跳转')
  }
}

/**
 * 9. 删除学习计划
 */
const handleDeletePlan = async (planId) => {
  if (!userId.value) return
  try {
    await ElMessageBox.confirm('确定要删除该学习计划吗？此操作不可恢复！', '删除确认', {
      type: 'warning'
    })
    const res = await delPathPlanApi(userId.value, planId)
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('计划已删除')
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
      ElMessage.error(res.msg || '删除失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('删除计划异常', err)
      ElMessage.error('删除失败，请重试')
    }
  }
}

/**
 * 10. 刷新当前计划详情
 */
const refreshCurrentPlan = async () => {
  if (selectedPlanId.value) {
    await viewPlanDetail(selectedPlanId.value)
  }
}

/**
 * 静默刷新计划数据（无 loading 弹窗，用于后台轮询）
 */
const silentRefreshPlan = async () => {
  if (!userId.value || !selectedPlanId.value) return
  try {
    const res = await getPlanDetailApi(userId.value, selectedPlanId.value)
    if (res.code === 1 && res.data?.success) {
      planData.value = {
        plan: res.data.plan,
        phases: res.data.plan.phases || []
      }
      initKpStates()
      extractAllPhaseExamStatus()
    }
  } catch (e) {
    // 静默失败
  }
}

/**
 * 11. 返回列表
 */
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
// 分享到学习路线市场方法
// ===================================================================

/** 打开分享对话框 */
const openShareDialog = async () => {
  if (!selectedPlanId.value || !planData.value?.plan) {
    ElMessage.warning('请先选择一个学习计划')
    return
  }
  shareDialogVisible.value = true
  shareLoading.value = true
  shareForm.value = {
    name: '',
    subtitle: '',
    description: '',
    category: '',
    difficulty: 'beginner',
    tags: [],
    target_audience: '',
    cover_color: '#667eea',
    cover_icon: '📚'
  }
  try {
    const res = await aiShareApi({ plan_data: planData.value.plan })
    if (res.code === 1 && res.data?.success && res.data.route_info) {
      const info = res.data.route_info
      shareForm.value = {
        name: info.name || '',
        subtitle: info.subtitle || '',
        description: info.description || '',
        category: info.category || '',
        difficulty: info.difficulty || 'beginner',
        tags: info.tags || [],
        target_audience: info.target_audience || '',
        cover_color: info.cover_color || '#667eea',
        cover_icon: info.cover_icon || '📚'
      }
    } else {
      ElMessage.error(res.msg || 'AI分析失败，请稍后重试')
      shareDialogVisible.value = false
    }
  } catch (e) {
    console.error('AI分析学习计划异常', e)
    ElMessage.error('AI分析失败: ' + (e.message || '未知错误'))
    shareDialogVisible.value = false
  } finally {
    shareLoading.value = false
  }
}

/** 关闭分享对话框 */
const closeShareDialog = () => {
  shareDialogVisible.value = false
  shareLoading.value = false
  shareSubmitting.value = false
}

/** 添加标签 */
const addShareTag = () => {
  const tag = shareTagInput.value.trim()
  if (tag && !shareForm.value.tags.includes(tag)) {
    shareForm.value.tags.push(tag)
  }
  shareTagInput.value = ''
}

/** 移除标签 */
const removeShareTag = (idx) => {
  shareForm.value.tags.splice(idx, 1)
}

/** 提交分享到路线市场 */
const submitShare = async () => {
  if (!shareForm.value.name.trim()) {
    ElMessage.warning('请输入路线名称')
    return
  }
  if (!shareForm.value.category) {
    ElMessage.warning('请选择分类')
    return
  }
  shareSubmitting.value = true
  try {
    const res = await shareToMarketApi({
      user_id: userId.value,
      plan_data: planData.value.plan,
      route_info: {
        name: shareForm.value.name,
        subtitle: shareForm.value.subtitle,
        description: shareForm.value.description,
        category: shareForm.value.category,
        difficulty: shareForm.value.difficulty,
        tags: shareForm.value.tags,
        target_audience: shareForm.value.target_audience,
        cover_color: shareForm.value.cover_color,
        cover_icon: shareForm.value.cover_icon
      }
    })
    if (res.code === 1 && res.data) {
      if (res.data.success) {
        ElMessage.success(`分享成功！路线：${res.data.route_name || shareForm.value.name}`)
        closeShareDialog()
      } else {
        ElMessage.warning(res.data.error || '分享失败')
      }
    } else {
      ElMessage.error(res.msg || '分享失败')
    }
  } catch (e) {
    console.error('分享到路线市场异常', e)
    ElMessage.error('提交失败: ' + (e.message || '网络错误'))
  } finally {
    shareSubmitting.value = false
  }
}

// ===================================================================
// 续期计划方法
// ===================================================================

/**
 * 检查续期状态
 */
const checkContinuationStatus = async () => {
  if (!userId.value) return
  try {
    const res = await checkStatusApi(userId.value, selectedPlanId.value)
    if (res.code === 1 && res.data?.success) {
      hasContinuationPending.value = res.data.continuation_pending || false
      hasContinuationPlan.value = res.data.has_continuation_plan || false
      continuationPlan.value = res.data.continuation_plan || null
      hasCheckedContinuation.value = true

      // 如果有续期计划，显示通知
      if (!hasContinuationPending.value && !hasContinuationPlan.value && allPhasesCompleted.value) {
        ElNotification({
          title: '该学习计划已完成',
          message: '再接再厉哦~',
          type: 'success',
          position: 'bottom-left',
          duration: 5000,
          showClose: true,
        })
      }
    }
  } catch (err) {
    console.error('检查续期状态异常', err)
  }
}

/**
 * 获取版本树
 */
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

/**
 * （旧）切换版本
 */
// const handleChangeVersion = async (planId) => {
//   if (!userId.value || !planId) return
//   let loadingInstance = null
//   try {
//     await ElMessageBox.confirm(
//       '确认切换到该版本？当前学习进度将被保存。',
//       '切换版本',
//       {
//         confirmButtonText: '确认切换',
//         cancelButtonText: '取消',
//         type: 'warning'
//       }
//     )
    
//     loadingInstance = ElLoading.service({
//       fullscreen: true,
//       text: '切换版本中...',
//       background: 'rgba(255, 255, 255, 0.9)'
//     })
    
//     const res = await changeVersionApi(userId.value, planId)
//     if (res.code === 1) {
//       ElMessage.success('版本切换成功')
//       await viewPlanDetail(planId)
//     } else {
//       ElMessage.error(res.msg || '版本切换失败')
//     }
//   } catch (err) {
//     if (err !== 'cancel') {
//       console.error('切换版本异常', err)
//       ElMessage.error('操作失败，请重试')
//     }
//   } finally {
//     if (loadingInstance) loadingInstance.close()
//   }
// }

/**
 * 重新生成某阶段计划
 */
const handleReCreatePhase = async (phaseIndex) => {
  if (!userId.value || !selectedPlanId.value) return
  if (reCreatingPhase.value[phaseIndex]) return
  
  try {
    await ElMessageBox.confirm(
      '确认重新生成该阶段？该阶段的学习进度将被重置。',
      '重新生成阶段',
      {
        confirmButtonText: '确认重新生成',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    reCreatingPhase.value[phaseIndex] = true
    
    const res = await reCreatePlanApi(userId.value, {
      phase_index: phaseIndex,
      plan_id: selectedPlanId.value
    })
    
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('阶段重新生成成功')
      await viewPlanDetail(selectedPlanId.value)
    } else {
      ElMessage.error(res.data.message || '阶段重新生成失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('重新生成阶段异常', err)
      ElMessage.error('操作失败，请重试')
    }
  } finally {
    reCreatingPhase.value[phaseIndex] = false
  }
}

/**
 * （旧）获取版本树的树形结构
 */
// const buildVersionTree = () => {
//   const versions = versionTree.value.versions || []
//   const treeMap = {}
  
//   versions.forEach(v => {
//     treeMap[v.plan_id] = {
//       ...v,
//       children: []
//     }
//   })
  
//   const rootNodes = []
//   versions.forEach(v => {
//     if (v.parent_plan_id && treeMap[v.parent_plan_id]) {
//       treeMap[v.parent_plan_id].children.push(treeMap[v.plan_id])
//     } else {
//       rootNodes.push(treeMap[v.plan_id])
//     }
//   })
  
//   return rootNodes
// }

/**
 * 获取触发类型样式
 */
const getTriggerTypeClass = (type) => {
  const typeMap = {
    'initial': 'trigger-initial',
    'phase_completed': 'trigger-completed',
    'phase_regenerated': 'trigger-regenerated'
  }
  return typeMap[type] || 'trigger-other'
}

/**
 * 获取触发类型标签
 */
const getTriggerTypeLabel = (type) => {
  const typeMap = {
    'initial': '原始计划',
    'phase_completed': '阶段完成',
    'phase_regenerated': '阶段重置'
  }
  return typeMap[type] || type
}

/**
 * 扁平化版本树
 */
const flattenVersionTree = (node, level = 0) => {
  const result = [{ ...node, level }]
  if (node.children && node.children.length > 0) {
    node.children.forEach(child => {
      result.push(...flattenVersionTree(child, level + 1))
    })
  }
  return result
}

/**
 * 格式化版本日期
 */
const formatVersionDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

/**
 * （旧）计算版本树SVG布局（参照 study_plan.html 的版本树样式）
 */
// const versionTreeLayout = computed(() => {
//   const versions = versionTree.value.versions || []
//   if (versions.length === 0) return { nodes: [], connections: [], width: 0, height: 0 }

//   const childrenMap = {}
//   let root = null

//   versions.forEach(v => {
//     const parentId = v.parent_plan_id
//     if (!parentId) {
//       root = v
//     } else {
//       if (!childrenMap[parentId]) childrenMap[parentId] = []
//       childrenMap[parentId].push(v)
//     }
//   })

//   const nodeWidth = 85
//   const nodeHeight = 34
//   const levelGap = 95
//   const phaseHeight = 28
//   const siblingGap = 70
//   const phaseRadius = 6

//   const nodePositions = {}

//   function calculatePositions(node, level, startX) {
//     const children = childrenMap[node.plan_id] || []
//     const phaseCount = node.phase_count || 1
//     const totalHeight = nodeHeight + phaseCount * phaseHeight + 22

//     if (children.length === 0) {
//       nodePositions[node.plan_id] = { x: startX, y: level * levelGap, totalHeight }
//       return { width: nodeWidth, midX: startX + nodeWidth / 2, totalHeight }
//     }

//     let totalChildWidth = 0
//     const childResults = []
//     let currentX = startX

//     children.forEach((child, idx) => {
//       const result = calculatePositions(child, level + 1, currentX)
//       childResults.push(result)
//       currentX += result.width + (idx < children.length - 1 ? siblingGap : 0)
//       totalChildWidth += result.width
//     })

//     if (children.length > 1) {
//       totalChildWidth += (children.length - 1) * siblingGap
//     }

//     const midX = startX + totalChildWidth / 2
//     const nodeX = midX - nodeWidth / 2

//     nodePositions[node.plan_id] = {
//       x: nodeX,
//       y: level * levelGap,
//       totalHeight,
//       childMids: childResults.map(r => r.midX)
//     }

//     return { width: Math.max(totalChildWidth, nodeWidth), midX, totalHeight }
//   }

//   if (root) {
//     calculatePositions(root, 0, 50)
//   } else {
//     versions.forEach((v, idx) => {
//       nodePositions[v.plan_id] = { x: 50 + idx * (nodeWidth + siblingGap), y: 0, totalHeight: nodeHeight + 22 }
//     })
//   }

//   let maxX = 50, maxY = 50
//   Object.values(nodePositions).forEach(pos => {
//     maxX = Math.max(maxX, pos.x + nodeWidth)
//     maxY = Math.max(maxY, pos.y + pos.totalHeight + 35)
//   })

//   // 构建连接线
//   const connections = []
//   function drawConnections(node) {
//     const children = childrenMap[node.plan_id] || []
//     const parentPos = nodePositions[node.plan_id]
//     if (!parentPos) return
//     const parentMidX = parentPos.x + nodeWidth / 2

//     const forkPhaseIdx = Math.min(node.completed_phase_count || 0, (node.phase_count || 1) - 1)
//     const forkY = parentPos.y + nodeHeight + forkPhaseIdx * phaseHeight + phaseHeight / 2

//     children.forEach((child, idx) => {
//       const childPos = nodePositions[child.plan_id]
//       if (!childPos) return
//       const childMidX = childPos.x + nodeWidth / 2
//       const childTopY = childPos.y

//       if (children.length === 1) {
//         connections.push({
//           d: `M ${parentMidX} ${forkY} L ${parentMidX} ${childTopY}`,
//           label: '',
//           labelX: 0,
//           labelY: 0
//         })
//       } else {
//         const midY = (forkY + childTopY) / 2
//         connections.push({
//           d: `M ${parentMidX} ${forkY} L ${parentMidX} ${midY} L ${childMidX} ${midY} L ${childMidX} ${childTopY}`,
//           label: idx === 0 ? '是' : '否',
//           labelX: (parentMidX + childMidX) / 2,
//           labelY: midY - 8
//         })
//       }

//       drawConnections(child)
//     })
//   }

//   if (root) drawConnections(root)

//   // 构建节点数据
//   const nodes = versions.map(node => {
//     const pos = nodePositions[node.plan_id]
//     if (!pos) return null
//     const isActive = node.is_active
//     const hasChildren = childrenMap[node.plan_id] && childrenMap[node.plan_id].length > 0

//     const fillColor = hasChildren ? (isActive ? '#6c5ce7' : '#00b894') : '#fdcb6e'
//     const strokeColor = hasChildren ? (isActive ? '#a29bfe' : '#00cec9') : '#f39c12'

//     const phases = []
//     for (let i = 0; i < (node.phase_count || 1); i++) {
//       const phaseY = pos.y + nodeHeight + i * phaseHeight + phaseHeight / 2
//       const isCompleted = i < (node.completed_phase_count || 0)
//       phases.push({
//         cx: pos.x + nodeWidth / 2,
//         cy: phaseY,
//         r: phaseRadius,
//         fill: isCompleted ? '#00b894' : '#e0e0e0',
//         stroke: isCompleted ? '#00cec9' : '#ccc',
//         number: i + 1,
//         isCompleted,
//         textColor: isCompleted ? '#fff' : '#888'
//       })
//     }

//     return {
//       planId: node.plan_id,
//       x: pos.x,
//       y: pos.y,
//       width: nodeWidth,
//       height: nodeHeight,
//       fillColor,
//       strokeColor,
//       versionNumber: node.version_number,
//       isActive,
//       triggerText: node.trigger_description || (node.version_number === 1 ? '原始方案' : ''),
//       triggerY: pos.y + pos.totalHeight + 2,
//       phases
//     }
//   }).filter(Boolean)

//   return {
//     nodes,
//     connections,
//     width: maxX + 50,
//     height: maxY + 50
//   }
// })

/**
 * 接收续期建议 - 立即生成续期计划
 */
const handleReceiveContinuation = async () => {
  if (!userId.value) return
  if (continuationGenerating.value) return // 防止重复点击
  
  try {
    await ElMessageBox.confirm(
      '确认接收续期建议？系统将为您生成全新的续期学习计划。',
      '接收续期建议',
      {
        confirmButtonText: '立即生成',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    
    // 设置加载状态
    continuationGenerating.value = true
    
    ElNotification({
      title: '正在生成续期计划',
      message: '系统正在为您生成全新的续期学习计划，请耐心等待...',
      type: 'info',
      position: 'bottom-left',
      duration: 5000,
      showClose: true,
    })
    
    const res = await getCheckMsgApi(userId.value, selectedPlanId.value)
    if (res.code === 1 && res.data?.success) {
      const planTitle = res.data.message || '新学习计划'
      ElNotification({
        title: '续期计划生成成功！',
        message: `续期计划「${planTitle}」已生成，请查看计划列表。`,
        type: 'success',
        position: 'bottom-left',
        duration: 10000,
        showClose: true,
      })
      
      // 刷新计划列表和详情
      await fetchPlanList()
      hasContinuationPending.value = false
      hasContinuationPlan.value = true
    } else {
      ElMessage.error('生成续期计划失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('接收续期建议异常', err)
      ElMessage.error('操作失败，请重试')
    }
  } finally {
    // 无论成功还是失败，都清除加载状态
    continuationGenerating.value = false
  }
}

/**
 * 拒绝续期建议 - 永不生成
 */
const handleRejectContinuation = async () => {
  if (!userId.value) return
  try {
    await ElMessageBox.confirm(
      '确认拒绝续期建议？该学习计划将永不生成续期计划。',
      '拒绝续期建议',
      {
        confirmButtonText: '确认拒绝',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    // 使用 rejectCheckMsgApi 拒绝续期
    const res = await rejectCheckMsgApi(userId.value, selectedPlanId.value)
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('已拒绝续期建议，该学习计划将永不生成续期计划')
      hasContinuationPending.value = false
      hasContinuationPlan.value = false
      // 刷新状态
      await checkContinuationStatus()
    } else {
      ElMessage.error('操作失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('拒绝续期建议异常', err)
      ElMessage.error('操作失败，请重试')
    }
  }
}

// ===================================================================
// 考试相关方法
// ===================================================================

/**
 * 查看考试评估（显示结果统计）
 */
const viewExamAssessment = async (phaseIndex) => {
  const phase = phases.value[phaseIndex]
  if (!phase) return
  
  const info = extractExamInfoFromPhase(phase)
  if (!info.completed || !info.results) {
    ElMessage.warning('未找到考试结果')
    return
  }
  
  // 记录当前考试的阶段索引
  currentExamPhaseIndex.value = phaseIndex
  
  // 构建 examResults 格式
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
  // 阻止背景页面滚动
  document.body.style.overflow = 'hidden'
}

// 更新下一阶段计划的加载状态
const updatingNextPhase = ref(false)

/**
 * 更新下一阶段计划（考试通过后触发）
 */
const updateNextPhasePlan = async () => {
  if (!userId.value || !selectedPlanId.value) return
  
  updatingNextPhase.value = true
  
  try {
    // 1. 调用接受评估接口，触发下一阶段计划生成
    const applyRes = await phaseApplyApi(userId.value, currentExamPhaseIndex.value)
    console.log('[评估] phaseApply 返回:', applyRes)
    
    if (applyRes.success !== true) {
      ElMessage.error('接受评估失败，请重试')
      return
    }
    
    // 2. 确认通知
    await ackNotificationApi(userId.value, currentExamPhaseIndex.value)
    
    // 3. 轮询版本树，等待新版本出现（最多等待30秒）
    const currentPlanId = selectedPlanId.value
    ElMessage.info('正在为你规划下一阶段学习内容...')
    
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000))
      
      try {
        const vtRes = await getVersionTreeApi(userId.value, currentPlanId)
        
        if (vtRes.code === 1 && vtRes.data?.has_tree && vtRes.data?.versions) {
          const activeId = vtRes.data.active_version_plan_id
          
          if (activeId && activeId !== currentPlanId) {
            // 新版本已生成，对新版本也执行 ack
            try {
              await ackNotificationApi(userId.value, currentExamPhaseIndex.value)
            } catch (e) {
              console.warn('[评估] ack新版本失败:', e)
            }
            
            // 关闭弹窗
            closeExamDialog()
            
            // 跳转到新版本
            await viewPlanDetail(activeId)
            
            ElNotification({
              title: '计划已更新',
              message: '已成功进入下一阶段学习计划！',
              type: 'success',
              position: 'bottom-left',
              duration: 4000,
              showClose: true,
            })
            
            return
          }
        }
      } catch (e) {
        console.warn('[评估] 版本树查询失败:', e)
      }
    }
    
    // 超时，刷新当前计划
    await refreshCurrentPlan()
    ElMessage.warning('等待超时，请手动刷新查看')
    
  } catch (err) {
    console.error('[评估] 更新下一阶段计划失败:', err)
    ElMessage.error('更新下一阶段计划失败，请重试')
  } finally {
    updatingNextPhase.value = false
  }
}

// 评估报告相关状态
const generatingAssessment = ref(false)
const assessmentReport = ref(null)
const showAssessmentReport = ref(false)

/**
 * 生成并展示评估报告
 */
const generateAssessmentReport = async () => {
  if (!userId.value || !selectedPlanId.value || currentExamPhaseIndex.value < 0) return
  
  generatingAssessment.value = true
  ElMessage.info('正在生成评估报告...')
  
  // ★★★ 优先从已加载的阶段数据中直接提取 phase_assessment ★★★
  const phase = phases.value[currentExamPhaseIndex.value]
  if (phase?.phase_assessment) {
    assessmentReport.value = {
      assessment_ready: true,
      assessment: phase.phase_assessment,
      phase_index: currentExamPhaseIndex.value,
      phase_name: phase.name || `阶段${currentExamPhaseIndex.value + 1}`,
    }
    showAssessmentReport.value = true
    generatingAssessment.value = false
    ElNotification({
      title: '评估报告已就绪',
      message: '请查看评估报告详情',
      type: 'success',
      position: 'bottom-left',
      duration: 3000,
      showClose: true,
    })
    return
  }
  
  try {
    // 轮询等待评估报告生成完成（最多60秒）
    const maxWait = 60
    for (let i = 0; i < maxWait; i++) {
      await new Promise(r => setTimeout(r, 1000))
      
      // ★★★ 每次轮询静默刷新计划数据，获取最新的 phase_assessment ★★★
      await silentRefreshPlan()
      const p = phases.value[currentExamPhaseIndex.value]
      if (p?.phase_assessment) {
        assessmentReport.value = {
          assessment_ready: true,
          assessment: p.phase_assessment,
          phase_index: currentExamPhaseIndex.value,
          phase_name: p.name || `阶段${currentExamPhaseIndex.value + 1}`,
        }
        showAssessmentReport.value = true
        ElNotification({ title: '评估报告已生成', message: '请查看评估报告详情', type: 'success', position: 'bottom-left', duration: 3000, showClose: true })
        return
      }
      
      try {
        const res = await getPhaseNotificationApi(userId.value)
        
        if (res.success && res.notification && res.notification.assessment_ready) {
          assessmentReport.value = res.notification
          showAssessmentReport.value = true
          
          ElNotification({
            title: '评估报告已生成',
            message: '请查看评估报告详情',
            type: 'success',
            position: 'bottom-left',
            duration: 3000,
            showClose: true,
          })
          
          return
        }
      } catch (e) {
        console.warn('[评估] 轮询通知失败:', e)
      }
    }
    
    // 超时
    ElMessage.warning('评估报告生成较慢，请稍后刷新页面查看')
    
  } catch (err) {
    console.error('[评估] 生成评估报告失败:', err)
    ElMessage.error('生成评估报告失败，请重试')
  } finally {
    generatingAssessment.value = false
  }
}

/**
 * 开始阶段考试
 */
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
    document.body.style.overflow = 'hidden'
    
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
    
    if (info.examCompleted && !info.passed) {
      examShowResults.value = false
      examResults.value = null
      examAlreadyCompleted.value = false
      isAllSubmitted.value = false
      
      ElNotification({
        title: '考题已就绪',
        message: '这是第' + (info.completedCount || 1) + '次考试，请认真作答',
        type: 'success',
        position: 'bottom-left',
        duration: 3000,
        showClose: true,
      })
    } else {
      examShowResults.value = false
      examResults.value = null
      examAlreadyCompleted.value = false
      isAllSubmitted.value = false
      
      ElNotification({
        title: '考题已就绪',
        message: '请认真作答，完成所有题目后点击提交',
        type: 'success',
        position: 'bottom-left',
        duration: 3000,
        showClose: true,
      })
    }
    
    examStartingLoading.value[phaseIndex] = false
    return
  }
  
  ElNotification({
    title: '正在准备考试',
    message: '系统正在生成考题，请耐心等待...',
    type: 'info',
    position: 'bottom-left',
    duration: 3000,
    showClose: true,
  })
  
  try {
    const res = await isOpenExamApi(userId.value, phaseIndex, selectedPlanId.value)
    if (res.code === 1 && res.data?.success) {
      if (res.data.take_exam) {
        await fetchExamQuestions(phaseIndex)
      } else {
        ElMessage.info('已跳过考试，正在进入下一阶段')
        await refreshCurrentPlan()
      }
    } else {
      ElMessage.error('操作失败')
    }
  } catch (err) {
    console.error('开始考试异常', err)
    ElMessage.error('获取考试数据失败')
  } finally {
    examStartingLoading.value[phaseIndex] = false
  }
}

/**
 * 获取考题数据
 */
const fetchExamQuestions = async (phaseIndex) => {
  if (!userId.value) return
  
  // 显示加载状态
  examLoading.value = true
  examDialogVisible.value = true
  // 阻止背景页面滚动
  document.body.style.overflow = 'hidden'
  
  try {
    const res = await getExamQuestionsApi(userId.value, phaseIndex)
    
    // 检查是否考试已完成
    if (res.code === 1 && res.data?.success === false && res.data?.reason === '考试已完成') {
      examAlreadyCompleted.value = true
      examLoading.value = false
      // 刷新计划详情以更新状态
      await refreshCurrentPlan()
      ElNotification({
        title: '考试已完成',
        message: '该阶段考试已完成，无需重复作答。',
        type: 'warning',
        position: 'bottom-left',
        duration: 5000,
        showClose: true,
      })
      return
    }
    
    if (res.code === 1 && res.data?.success) {
      examData.value = res.data.exam_data
      currentExamPhaseIndex.value = phaseIndex
      
      // 展平所有题目
      allExamQuestions.value = flattenExamQuestions(examData.value)
      currentQuestionIndex.value = 0
      
      // 初始化答案
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
      
      ElNotification({
        title: '考题已就绪',
        message: '请认真作答，完成所有题目后点击提交',
        type: 'success',
        position: 'bottom-left',
        duration: 3000,
        showClose: true,
      })
    } else {
      ElMessage.error(res.msg || '获取考题失败')
      examDialogVisible.value = false
      // 恢复背景页面滚动
      document.body.style.overflow = ''
    }
  } catch (err) {
    console.error('获取考题异常', err)
    ElMessage.error('获取考题失败，请重试')
    examDialogVisible.value = false
    // 恢复背景页面滚动
    document.body.style.overflow = ''
  } finally {
    examLoading.value = false
  }
}

/**
 * 展平考试题目
 */
const flattenExamQuestions = (data) => {
  const result = []
  let index = 0
  
  // 编程题
  if (data.programming_questions && data.programming_questions.length > 0) {
    data.programming_questions.forEach((q, i) => {
      result.push({
        ...q,
        type: 'programming',
        typeLabel: '编程题',
        index: index++,
        originalIndex: i,
        category: 'programming'
      })
    })
  }
  
  // 理论题
  if (data.theory_questions && data.theory_questions.length > 0) {
    data.theory_questions.forEach((q, i) => {
      result.push({
        ...q,
        type: q.type || 'single_choice',
        typeLabel: getQuestionTypeName(q.type || 'single_choice'),
        index: index++,
        originalIndex: i,
        category: 'theory'
      })
    })
  }
  
  return result
}

/**
 * 选择答案（选择题/判断题）
 */
const selectExamAnswer = (question, value) => {
  if (isAllSubmitted.value) return
  
  const key = question.type + '_' + question.index
  
  if (question.type === 'multiple_choice') {
    if (!examAnswers.value[key]) {
      examAnswers.value[key] = []
    }
    const arr = examAnswers.value[key]
    const index = arr.indexOf(value)
    if (index > -1) {
      arr.splice(index, 1)
    } else {
      arr.push(value)
    }
    if (arr.length === 0) {
      examAnswers.value[key] = []
    }
  } else {
    examAnswers.value[key] = value
  }
}

/**
 * 检查选项是否被选中
 */
const isExamOptionSelected = (question, value) => {
  const key = question.type + '_' + question.index
  const answer = examAnswers.value[key]
  if (!answer) return false
  if (Array.isArray(answer)) {
    return answer.includes(value)
  }
  return answer === value
}

/**
 * 更新编程题行数
 */
const updateLineCount = (question) => {
  const key = question.type + '_' + question.index
  const value = examAnswers.value[key] || ''
  const lines = value.split('\n').length
  lineCountMap.value[key] = Math.max(10, lines)
}

/**
 * 处理代码编辑器键盘事件
 */
const handleCodeKeydown = (e, question) => {
  if (isAllSubmitted.value) return
  
  const key = question.type + '_' + question.index
  const textarea = e.target
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const value = examAnswers.value[key] || ''
  
  // 定义成对符号
  const pairs = {
    '(': ')',
    '[': ']',
    '{': '}',
    '"': '"',
    "'": "'"
  }
  
  // 辅助函数：更新值并设置光标
  const updateValue = (newValue, newCursorPos) => {
    examAnswers.value[key] = newValue
    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = newCursorPos
      updateLineCount(question)
    })
  }
  
  // 1. Tab 键：插入 4 个空格
  if (e.key === 'Tab') {
    e.preventDefault()
    const spaces = '    '
    const newValue = value.substring(0, start) + spaces + value.substring(end)
    updateValue(newValue, start + 4)
    return
  }
  
  // 2. Enter 键：智能换行与缩进
  if (e.key === 'Enter') {
    e.preventDefault()
    
    const lastNewLineIndex = value.lastIndexOf('\n', start - 1)
    const currentLineStart = lastNewLineIndex + 1
    const currentLineContent = value.substring(currentLineStart, start)
    
    const indentMatch = currentLineContent.match(/^\s*/)
    const baseIndent = indentMatch ? indentMatch[0] : ''
    
    const textAfterCursor = value.substring(end)
    const nextNonWhitespaceChar = textAfterCursor.match(/\S/)?.[0]
    
    const trimmedLineEnd = currentLineContent.trimEnd()
    const lastChar = trimmedLineEnd.charAt(trimmedLineEnd.length - 1)
    
    let newIndent = baseIndent
    
    // 场景 A: 当前行以 { 结尾，且光标后紧跟 }
    if (lastChar === '{' && nextNonWhitespaceChar === '}') {
      const closeCharIndex = value.indexOf('}', end)
      if (closeCharIndex !== -1) {
        const before = value.substring(0, start)
        const middleIndent = baseIndent + '    '
        const afterIndent = baseIndent
        const closeLine = '\n' + afterIndent + '}'
        const rest = value.substring(closeCharIndex + 1)
        const newValue = before + '\n' + middleIndent + '\n' + afterIndent + '}' + rest
        const newCursorPos = before.length + 1 + middleIndent.length
        updateValue(newValue, newCursorPos)
        return
      }
    }
    
    // 场景 B: 当前行以 { 结尾
    if (lastChar === '{') {
      newIndent = baseIndent + '    '
    }
    
    // 场景 C: 普通回车
    const insertion = '\n' + newIndent
    const newValue = value.substring(0, start) + insertion + value.substring(end)
    updateValue(newValue, start + insertion.length)
    return
  }
  
  // 3. 自动补全成对符号
  if (pairs[e.key]) {
    e.preventDefault()
    const openChar = e.key
    const closeChar = pairs[e.key]
    
    if (start !== end) {
      const selectedText = value.substring(start, end)
      const newValue = value.substring(0, start) + openChar + selectedText + closeChar + value.substring(end)
      updateValue(newValue, start + 1 + selectedText.length + 1)
    } else {
      const newValue = value.substring(0, start) + openChar + closeChar + value.substring(end)
      updateValue(newValue, start + 1)
    }
    return
  }
  
  // 4. Backspace: 智能删除
  if (e.key === 'Backspace') {
    if (start === end && start > 0) {
      const charBefore = value.charAt(start - 1)
      const charAfter = value.charAt(start)
      
      // 智能删除成对符号
      if (pairs[charBefore] === charAfter) {
        e.preventDefault()
        const newValue = value.substring(0, start - 1) + value.substring(start + 1)
        updateValue(newValue, start - 1)
        return
      }
      
      // 智能删除缩进
      if (charBefore === ' ') {
        const lastNewLineIndex = value.lastIndexOf('\n', start - 1)
        const currentLineStart = lastNewLineIndex + 1
        const currentLineContentBeforeCursor = value.substring(currentLineStart, start)
        
        if (/^\s*$/.test(currentLineContentBeforeCursor)) {
          e.preventDefault()
          const indentUnit = 4
          const spacesToDelete = Math.min(indentUnit, currentLineContentBeforeCursor.length)
          const deleteStartPos = start - spacesToDelete
          const newValue = value.substring(0, deleteStartPos) + value.substring(start)
          updateValue(newValue, deleteStartPos)
          return
        }
      }
    }
  }
}

/**
 * 切换示例展开状态
 */
const toggleExampleExpand = (question) => {
  const key = question.type + '_' + question.index
  exampleExpandedMap.value[key] = !exampleExpandedMap.value[key]
}

/**
 * 切换提示展开状态
 */
const toggleHintExpand = (question) => {
  const key = question.type + '_' + question.index
  hintExpandedMap.value[key] = !hintExpandedMap.value[key]
}

/**
 * 提交所有答案
 */
const submitAllExamAnswers = async () => {
  if (!userId.value) return
  if (!allQuestionsAnswered.value) {
    ElMessage.warning('还有题目未作答，请完成所有题目')
    return
  }
  if (isAllSubmitted.value) {
    ElMessage.warning('已提交，请查看结果')
    return
  }
  
  // 构建提交数据
  const programmingAnswers = []
  const theoryAnswers = []
  
  allExamQuestions.value.forEach(q => {
    const key = q.type + '_' + q.index
    const answer = examAnswers.value[key] || ''
    
    if (q.category === 'programming') {
      programmingAnswers.push(String(answer))
    } else {
      theoryAnswers.push(String(answer))
    }
  })
  
  const submitData = {
    programm: programmingAnswers,
    theory: theoryAnswers
  }
  
  examSubmitting.value = true
  
  try {
    const res = await submitExamAnswersApi(userId.value, currentExamPhaseIndex.value, submitData)
    
    if (res.code === 1 && res.data?.success) {
      // 标记已提交
      isAllSubmitted.value = true
      examResults.value = res.data
      examShowResults.value = true
      
      const passed = res.data.passed
      const score = res.data.score
      const total = res.data.total
      
      if (passed) {
        ElNotification({
          title: '考试通过！',
          message: `得分：${score}/${total}，恭喜通过考试！`,
          type: 'success',
          position: 'bottom-left',
          duration: 6000,
          showClose: true,
        })
      } else {
        ElNotification({
          title: '考试未通过',
          message: `得分：${score}/${total}，请继续努力！`,
          type: 'warning',
          position: 'bottom-left',
          duration: 6000,
          showClose: true,
        })
      }
      // 刷新进度以更新考试状态
      await refreshCurrentPlan()
    } else {
      // 检查是否是考试已完成
      if (res.data?.reason === '考试已完成') {
        isAllSubmitted.value = true
        
        await refreshCurrentPlan()
        
        const phase = phases.value[currentExamPhaseIndex.value]
        const info = extractExamInfoFromPhase(phase)
        
        if (info.results) {
          examResults.value = {
            score: info.score || 0,
            total: info.total || info.results.length || 0,
            passed: info.passed,
            results: info.results,
            message: info.passed ? `恭喜通过！得分 ${info.score || 0}/${info.total || info.results.length || 0}` : `考试未通过，得分 ${info.score || 0}/${info.total || info.results.length || 0}`
          }
          examShowResults.value = true
          
          ElNotification({
            title: '考试评估',
            message: info.passed ? '恭喜通过考试！' : '考试未通过，请继续努力！',
            type: info.passed ? 'success' : 'warning',
            position: 'bottom-left',
            duration: 5000,
            showClose: true,
          })
        } else {
          ElNotification({
            title: '考试已完成',
            message: '该阶段考试已完成，无需重复提交。',
            type: 'warning',
            position: 'bottom-left',
            duration: 5000,
            showClose: true,
          })
          closeExamDialog()
        }
      } else {
        ElMessage.error(res.msg || '提交答案失败')
      }
    }
  } catch (err) {
    console.error('提交考试异常', err)
    ElMessage.error('提交失败，请重试')
  } finally {
    examSubmitting.value = false
  }
}

/**
 * 下一题
 */
const nextExamQuestion = () => {
  if (currentQuestionIndex.value < allExamQuestions.value.length - 1) {
    currentQuestionIndex.value++
  }
}

/**
 * 上一题
 */
const prevExamQuestion = () => {
  if (currentQuestionIndex.value > 0) {
    currentQuestionIndex.value--
  }
}

/**
 * 关闭考试弹窗
 */
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
  // 重置评估报告状态
  assessmentReport.value = null
  showAssessmentReport.value = false
  generatingAssessment.value = false
  // 恢复背景页面滚动
  document.body.style.overflow = ''
}

// ===================================================================
// 四、生命周期与监听区
// ===================================================================

const skipInfo = ref({})

onMounted(async () => {
  if (!getUserId()) {
    ElMessage.error('未检测到登录信息，请登录后使用')
    return
  }
  await fetchPlanList()

  // 检查应用中是否有要打开的学习计划
  if (isSkip(8) === false) {
    console.log('没有学习计划需要提前打开')
  } else {
    skipInfo.value = isSkip(8)
    console.log('跳转信息:', skipInfo.value)
    ElMessage.success('为你显示的是当前学习计划，若计划不对，请返回计划列表查看')
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
})

/**
 * 监听计划列表变化
 */
watch(planList, (newList) => {
  if (!newList || newList.length === 0) {
    isViewingDetail.value = false
    planData.value = { plan: null, phases: [] }
  }
}, { deep: true })

/**
 * 监听分享对话框打开状态，锁定/解锁页面滚动
 */
watch(shareDialogVisible, (visible) => {
  if (visible) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})
</script>

<template>
  <div class="learning-path-container">
    <!-- ============================================================ -->
    <!-- 页面头部 -->
    <!-- ============================================================ -->
    <div class="path-header">
      <div class="header-left">
        <h1>智学路径</h1>
        <p class="subtitle">阶段化学习路线，循序渐进掌握完整知识体系</p>
        <button class="market-entry-btn" @click="showMarket = true">
          🛒 学习路线市场
        </button>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 主体内容 -->
    <!-- ============================================================ -->
    <div class="path-content">

      <!-- ========================================================== -->
      <!-- 状态一：无学习计划 - 展示创建表单 -->
      <!-- ========================================================== -->
      <div v-if="!planList || planList.length === 0" class="no-plan-wrapper">
        <div class="no-plan-card">
          <div class="no-plan-icon">
            <svg t="1781679088278" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="9032" width="150" height="150"><path d="M865.206857 691.565714c-55.881143 0-107.739429 35.913143-123.757714 87.771429H318.464c-63.853714 0-115.785143-51.858286-115.785143-115.712 0-63.853714 51.931429-111.689143 115.785143-111.689143H709.485714c107.739429 0 195.510857-87.771429 195.510857-195.584 0-107.739429-87.771429-195.510857-195.510857-195.510857H286.500571c-15.945143-51.931429-63.853714-87.771429-123.684571-87.771429C94.939429 72.996571 35.108571 132.827429 35.108571 200.630857c0 67.876571 59.830857 127.707429 127.707429 127.707429 55.881143 0 107.739429-35.84 123.684571-87.771429h419.108572c63.780571 0 115.712 51.931429 115.712 115.712 0 63.853714-47.908571 115.712-111.762286 115.712H318.464A195.876571 195.876571 0 0 0 122.88 667.648c0 107.739429 87.771429 195.510857 195.584 195.510857h419.035429c15.945143 51.931429 63.853714 87.771429 123.684571 87.771429 71.826286 0 127.707429-59.830857 127.707429-127.634286 0-67.876571-55.881143-131.657143-123.684572-131.657143zM162.816 252.562286c-23.990857 0-47.908571-23.917714-47.908571-51.858286 0-27.940571 23.917714-47.908571 47.908571-47.908571 23.917714 0 47.908571 23.990857 47.908571 47.908571 0 23.990857-19.968 51.931429-47.908571 51.931429z m702.390857 618.642285a48.493714 48.493714 0 0 1-47.908571-47.908571c0-23.990857 23.917714-47.908571 47.908571-47.908571 23.917714 0 47.908571 23.917714 47.908572 47.908571 0 23.917714-23.990857 47.908571-47.908572 47.908571z" fill="#2D7DDB" p-id="9033"></path></svg>
          </div>
          <h3>暂无专属学习路径</h3>
          <p>输入你想要学习的内容，AI将为你生成定制化学习计划</p>
          <div class="input-area">
            <el-input
              v-model="planText"
              placeholder="例如：从零入门大模型微调开发"
              maxlength="60"
              show-word-limit
              size="large"
              class="plan-input"
              @keyup.enter="generatePlan"
            />
            <el-button type="primary" size="large" @click="generatePlan" :loading="generating">
              一键生成路径
            </el-button>
          </div>
        </div>
      </div>

      <!-- ========================================================== -->
      <!-- 状态二：有计划 - 展示计划列表 -->
      <!-- ========================================================== -->
      <div v-else-if="planList && planList.length > 0 && !isViewingDetail" class="plan-list-wrapper">
        <div class="create-plan-section">
          <div class="create-plan-inner">
            <div class="create-plan-label">
              <el-icon><Plus /></el-icon>
              <span>创建新计划</span>
            </div>
            <div class="create-plan-form">
              <el-input
                v-model="planText"
                placeholder="输入学习主题，如：从零入门大模型微调开发"
                maxlength="60"
                show-word-limit
                class="create-plan-input"
                @keyup.enter="generatePlan"
                size="large"
              />
              <el-button size="large" type="primary" @click="generatePlan" :loading="generating">
                生成
              </el-button>
            </div>
          </div>
        </div>

        <div class="plan-list-header">
          <span class="list-title">我的学习计划</span>
          <span class="list-count">共 {{ planList.length }} 个计划</span>
        </div>

        <div class="plan-grid">
          <div 
            v-for="plan in planList" 
            :key="plan.plan_id"
            class="plan-card-item"
            @click="viewPlanDetail(plan.plan_id)"
          >
            <div class="plan-card-content">
              <div class="plan-card-top">
                <h3 class="plan-title">{{ plan.title }}</h3>
              </div>
              <div class="plan-meta">
                <span class="meta-item">
                  <el-icon><Clock /></el-icon>
                  {{ plan.total_duration || '未设置' }}
                </span>
                <span class="meta-item">
                  <el-icon><Calendar /></el-icon>
                  创建于 {{ formatDate(plan.created_at) }}
                </span>
              </div>
              <div class="plan-card-footer">
                <el-button type="primary" plain size="small" @click.stop="viewPlanDetail(plan.plan_id)">
                  查看详情
                </el-button>
                <el-button type="danger" plain size="small" @click.stop="handleDeletePlan(plan.plan_id)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ========================================================== -->
      <!-- 状态三：查看计划详情 -->
      <!-- ========================================================== -->
      <div v-else-if="isViewingDetail && planData && planData.plan" class="has-plan-wrapper">
        <div class="detail-toolbar">
          <el-button @click="backToList">
            <el-icon><ArrowLeft /></el-icon>
            返回列表
          </el-button>
          <el-button type="primary" plain @click="refreshCurrentPlan">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" @click="openShareDialog">
            <el-icon><Share /></el-icon>&nbsp;
            分享到学习路线市场
          </el-button>
          <el-button type="danger" plain @click="handleDeletePlan(selectedPlanId)" :disabled="!selectedPlanId">
            <el-icon><Delete /></el-icon>
            删除计划
          </el-button>
        </div>

        

        <!-- ======================================================== -->
        <!-- 顶部总览卡片 -->
        <!-- ======================================================== -->
        <div class="plan-overview">
          <div class="overview-left">
            <h2>{{ planData.plan?.title || '未命名计划' }}</h2>
            <p class="description">{{ planData.plan?.description || '' }}</p>
            <div class="info-tags">
              <el-tag>{{ planData.plan?.total_duration || '未知' }}</el-tag>
              <el-tag :type="difficultyType(planData.plan?.difficulty)">
                {{ planData.plan?.difficulty || '未知' }}
              </el-tag>
              <el-tag type="info">{{ totalProgress.progress || '0/0' }} 阶段</el-tag>
              <el-tag :type="selectedPlan?.is_active ? 'success' : 'info'">
                {{ selectedPlan?.is_active ? '激活中' : '已归档' }}
              </el-tag>
            </div>
          </div>
          <div class="overview-right">
            <div class="progress-circle">
              <el-progress type="circle" :percentage="completionPercent" :width="100" stroke-width="10" />
              <span class="progress-label">整体完成进度</span>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 版本树 -->
        <!-- ======================================================== -->
        <div class="version-tree-section" v-if="versionTree.has_tree && versionTree.versions.length > 0">
          <div class="version-tree-header" @click="versionTreeExpanded = !versionTreeExpanded">
            <div class="version-tree-title">
              <el-icon><GitBranch /></el-icon>
              <span>版本树</span>
              <span class="vt-sub">当前版本</span>
              <el-tag size="small" type="info">v{{ versionTree.active_version }}</el-tag>
            </div>
            <el-icon :class="{ 'rotated': versionTreeExpanded }"><ArrowDown /></el-icon>
          </div>
          
          <Transition name="slide-fade">
            <div class="version-tree-content" v-show="versionTreeExpanded">
              <div class="version-tree-loading" v-if="versionTreeLoading">
                <el-icon class="is-loading" :size="30"></el-icon>
                <span>加载版本树中...</span>
              </div>
              <Transition name="tree-fade">
                <TreeChart 
                  v-if="!versionTreeLoading"
                  :key="versionTree.active_version_plan_id"
                  :versions="versionTree.versions"
                  :active-plan-id="versionTree.active_version_plan_id"
                  :active-version="versionTree.active_version"
                  :user-id="userId"
                />
              </Transition>
            </div>
          </Transition>
        </div>

        <!-- ======================================================== -->
        <!-- 阶段时间线列表 -->
        <!-- ======================================================== -->
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
            <!-- ====================================================== -->
            <!-- 时间线左侧：圆点 + 连接线 -->
            <!-- ====================================================== -->
            <div class="timeline-marker">
              <div class="marker-dot">
                <el-icon v-if="isPhaseCompleted(idx)"><Check /></el-icon>
                <span v-else>{{ idx + 1 }}</span>
              </div>
              <div class="timeline-line" v-if="idx < phases.length - 1"></div>
            </div>

            <!-- ====================================================== -->
            <!-- 阶段卡片 -->
            <!-- ====================================================== -->
            <div class="phase-card">
              <div class="card-header">
                <div class="phase-name">
                  {{ phase.name || '未命名阶段' }}
                  <el-tag 
                    v-if="isPhaseUnlocked(idx)"
                    :type="phaseStatusType(phase.status)" 
                    size="small" 
                    effect="plain"
                  >
                    {{ phase.status || '未知' }}
                  </el-tag>
                  <el-tag 
                    v-else
                    type="info" 
                    size="small" 
                    effect="plain"
                  >
                    <el-icon><Lock /></el-icon>
                    未解锁
                  </el-tag>
                </div>
                <div class="phase-actions">
                  <div class="phase-meta">
                    <span>{{ phase.weeks || '' }}</span>
                    <span>预计 {{ phase.estimated_hours || 0 }} 小时</span>
                  </div>
                  <el-button 
                    v-if="isPhaseUnlocked(idx)"
                    size="small" 
                    type="warning" 
                    plain
                    :loading="reCreatingPhase[idx] || false"
                    :disabled="reCreatingPhase[idx]"
                    @click="handleReCreatePhase(idx)"
                  >
                    <el-icon><Refresh /></el-icon>
                    重置阶段
                  </el-button>
                </div>
              </div>

              <div class="card-desc">{{ phase.description || '' }}</div>

              <div class="card-milestone" v-if="phase.milestone">
                <el-icon><Flag /></el-icon>
                <span>{{ phase.milestone }}</span>
              </div>

              <div class="card-progress" v-if="isPhaseUnlocked(idx) && phaseProgressMap[idx] !== undefined">
                <el-progress :percentage="phaseProgressMap[idx] || 0" stroke-width="6" :show-text="false" />
                <span class="progress-text">{{ phaseProgressMap[idx] || 0 }}%</span>
              </div>
              <div class="card-progress" v-else-if="!isPhaseUnlocked(idx)">
                <el-progress :percentage="0" stroke-width="6" :show-text="false" />
                <span class="progress-text" style="color: var(--text-gray);">未解锁</span>
              </div>

              <!-- ==================================================== -->
              <!-- 知识点列表 - 每个知识点独立显示，左右布局 -->
              <!-- ==================================================== -->
              <div class="phase-knowledge-list" v-if="phase.knowledge_points && phase.knowledge_points.length > 0">
                <div 
                  v-for="(kp, kIdx) in phase.knowledge_points" 
                  :key="kIdx"
                  class="knowledge-item"
                  :class="{ 'kp-completed': isKpCompleted(idx, kp) }"
                >
                  <!-- 知识点行：左侧是知识点名称和状态，右侧是生成按钮 -->
                  <div class="knowledge-row">
                    <!-- 左侧：知识点信息 -->
                    <div class="knowledge-info">
                      <span class="kp-badge">{{ kIdx + 1 }}</span>
                      <span class="kp-name">{{ kp }}</span>
                      <el-tag v-if="isKpCompleted(idx, kp)" size="small" type="success" effect="plain">
                        <el-icon><Check /></el-icon>
                        已完成
                      </el-tag>
                    </div>
                    
                    <!-- 右侧：操作按钮 -->
                    <div class="knowledge-actions">
                      <!-- 未解锁时显示锁定图标 -->
                      <div v-if="!isPhaseUnlocked(idx)" class="kp-locked-icon">
                        <el-icon><Lock /></el-icon>
                        <span>未解锁</span>
                      </div>
                      <!-- 已生成时显示"已生成"标签 -->
                      <el-tag v-else-if="isKpGenerated(idx, kp)" size="small" type="success">
                        <el-icon><Check /></el-icon>
                        已生成
                      </el-tag>
                      <!-- 生成按钮 -->
                      <el-button 
                        v-else
                        type="primary" 
                        size="small"
                        :loading="generatingResources[getKpKey(idx, kp)]?.['all'] || false"
                        :disabled="generatingResources[getKpKey(idx, kp)]?.['all']"
                        @click="generateKpResources(idx, kp)"
                      >
                        <el-icon><MagicStick /></el-icon>
                        <span v-if="generatingResources[getKpKey(idx, kp)]?.['all']">生成中...</span>
                        <span v-else>生成资源 / 查看资源</span>
                      </el-button>
                    </div>
                  </div>

                  <!-- 资源列表 - 在知识点行下方显示 -->
                  <div class="kp-resources" v-if="isKpGenerated(idx, kp) && getKpResources(idx, kp).length > 0">
                    <div class="kp-resource-items">
                      <div 
                        v-for="(resource, rIdx) in getKpResources(idx, kp)" 
                        :key="rIdx"
                        class="kp-resource-item"
                      >
                        <div class="kp-resource-info">
                          <el-icon :style="{ color: getResourceColor(resource[0]) }">
                            <component :is="getResourceIcon(resource[0])" />
                          </el-icon>
                          <el-tag :type="getResourceTagType(resource[0])" size="small" effect="plain">
                            {{ resourceTypeName(resource[0]) }}
                          </el-tag>
                          <span class="kp-resource-id">ID: {{ resource[1] }}</span>
                        </div>
                        <el-button 
                          type="primary" 
                          size="small"
                          plain
                          @click="goResourceDetail(idx, resource[0], resource[1])"
                        >
                          <el-icon><Right /></el-icon>
                          查看
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- ==================================================== -->
              <!-- 阶段底部 - 考试按钮 -->
              <!-- ==================================================== -->
              <div class="phase-exam-section" v-if="isPhaseFullyCompleted(idx)">
                <template v-if="examCompletedMap[idx]?.passed">
                  <el-button 
                    type="primary" 
                    size="default"
                    @click="viewExamAssessment(idx)"
                  >
                    <el-icon><EditPen /></el-icon>
                    查看评估报告
                  </el-button>
                  <span class="exam-completed-tip">
                    <el-icon><Check /></el-icon>
                    考试已通过
                  </span>
                </template>
                <template v-else-if="examCompletedMap[idx]?.examCompleted">
                  <el-button 
                    type="danger" 
                    size="default"
                    @click="startPhaseExam(idx)"
                    :loading="examStartingLoading[idx] || false"
                    :disabled="examStartingLoading[idx] || examSubmitting"
                  >
                    <el-icon><EditPen /></el-icon>
                    {{ examStartingLoading[idx] ? '准备考题中...' : '再次考试' }}
                  </el-button>
                  <span class="exam-loading-tip">
                    <el-icon><InfoFilled /></el-icon>
                    考试未通过，点击重新答题
                  </span>
                </template>
                <template v-else>
                  <el-button 
                    type="warning" 
                    size="default"
                    @click="startPhaseExam(idx)"
                    :loading="examStartingLoading[idx] || false"
                    :disabled="examStartingLoading[idx] || examSubmitting"
                  >
                    <el-icon><EditPen /></el-icon>
                    {{ examStartingLoading[idx] ? '准备考题中...' : '开始考试' }}
                  </el-button>
                  <span v-if="examStartingLoading[idx]" class="exam-loading-tip">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    正在生成考题，请耐心等待...
                  </span>
                </template>
              </div>
            </div>

            <!-- ====================================================== -->
            <!-- 锁定提示 -->
            <!-- ====================================================== -->
            <div class="phase-lock-tip" v-if="!isPhaseUnlocked(idx)">
              <el-icon><Lock /></el-icon>
              <span>通过「{{ idx > 0 ? phases[idx - 1]?.name || '上一阶段' : '上一阶段' }}」考试后自动解锁</span>
            </div>
          </div>
        </div>
        <div v-else class="no-phases-tip">
          <el-empty description="暂无阶段数据" />
        </div>

        <!-- ======================================================== -->
        <!-- 续期学习计划区域 - 放在底部 -->
        <!-- ======================================================== -->
        <div class="continuation-section" v-if="allPhasesCompleted">
          <div class="continuation-card">
            <div class="continuation-header">
              <el-icon><Flag /></el-icon>
              <span>生成续期学习计划</span>
            </div>
            <div class="continuation-body">
              <p class="continuation-desc">
                当前学习计划已全部完成！您可以生成续期学习计划，继续深入学习相关知识。
              </p>
              <div class="continuation-actions">
                <el-button 
                  type="primary" 
                  size="large"
                  :disabled="hasContinuationPlan || !hasContinuationPending || continuationGenerating"
                  :loading="continuationGenerating"
                  @click="handleReceiveContinuation"
                >
                  <el-icon v-if="!continuationGenerating"><MagicStick /></el-icon>
                  {{ continuationGenerating ? '正在生成续期计划，请耐心等待...' : '立即生成（接收续期建议）' }}
                </el-button>
                <el-button 
                  type="danger" 
                  size="large"
                  plain
                  :disabled="hasContinuationPlan || !hasContinuationPending || continuationGenerating"
                  @click="handleRejectContinuation"
                >
                  永不生成（拒绝续期建议）
                </el-button>
                <span v-if="hasContinuationPlan || !hasContinuationPending" class="continuation-tip">
                  <el-icon><Check /></el-icon>
                  您已经选择过了
                </span>
              </div>
            </div>
          </div>
        </div>


      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 分享到学习路线市场弹窗 -->
    <!-- ============================================================ -->
    <div v-if="shareDialogVisible" class="share-dialog-overlay">
      <div class="share-dialog">
        <div class="share-dialog-header">
          <div class="share-header-left">
            <span class="share-header-icon">🚀</span>
            <div>
              <h3>分享到学习路线市场</h3>
              <p class="share-header-desc">AI 已为你整理好路线信息，可自由编辑后发布</p>
            </div>
          </div>
          <button class="share-dialog-close" @click="closeShareDialog">&times;</button>
        </div>
        <div class="share-dialog-body">
          <!-- 加载态 -->
          <div v-if="shareLoading" class="share-loading">
            <div class="share-spinner-ring"></div>
            <p class="share-loading-text">AI 正在智能分析你的学习计划</p>
            <p class="share-loading-hint">即将为你生成路线名称、简介和标签...</p>
          </div>
          <!-- 表单 -->
          <div v-else class="share-form">
            <!-- 基本信息区 -->
            <div class="share-section">
              <div class="share-section-title">基本信息</div>
              <div class="share-form-item">
                <label>路线名称 <span class="required">*</span></label>
                <input v-model="shareForm.name" placeholder="例如：3个月Python从入门到实战" class="share-input" maxlength="50" />
                <span class="share-char-count">{{ (shareForm.name || '').length }}/50</span>
              </div>
              <div class="share-form-item">
                <label>一句话介绍</label>
                <input v-model="shareForm.subtitle" placeholder="用一句话概括这条路线的亮点" class="share-input" maxlength="30" />
              </div>
              <div class="share-form-item">
                <label>路线简介</label>
                <textarea v-model="shareForm.description" placeholder="描述路线的核心内容、学习方式和预期收获..." rows="6" class="share-textarea"></textarea>
              </div>
            </div>
            <!-- 分类与难度 -->
            <div class="share-section">
              <div class="share-section-title">分类与难度</div>
              <div class="share-form-row">
                <div class="share-form-item">
                  <label>分类 <span class="required">*</span></label>
                  <select v-model="shareForm.category" class="share-select">
                    <option value="">请选择分类</option>
                    <option value="前端开发">前端开发</option>
                    <option value="后端开发">后端开发</option>
                    <option value="移动开发">移动开发</option>
                    <option value="数据科学">数据科学</option>
                    <option value="人工智能">人工智能</option>
                    <option value="算法">算法</option>
                    <option value="计算机基础">计算机基础</option>
                    <option value="其他">其他</option>
                  </select>
                </div>
                <div class="share-form-item">
                  <label>难度等级</label>
                  <div class="share-difficulty-group">
                    <button 
                      type="button" 
                      class="share-diff-btn" 
                      :class="{ active: shareForm.difficulty === 'beginner' }"
                      @click="shareForm.difficulty = 'beginner'"
                    >入门</button>
                    <button 
                      type="button" 
                      class="share-diff-btn" 
                      :class="{ active: shareForm.difficulty === 'medium' }"
                      @click="shareForm.difficulty = 'medium'"
                    >进阶</button>
                    <button 
                      type="button" 
                      class="share-diff-btn" 
                      :class="{ active: shareForm.difficulty === 'advanced' }"
                      @click="shareForm.difficulty = 'advanced'"
                    >高级</button>
                  </div>
                </div>
              </div>
            </div>
            <!-- 标签与人群 -->
            <div class="share-section">
              <div class="share-section-title">标签与受众</div>
              <div class="share-form-item">
                <label>标签 <span class="share-hint">（回车添加，最多 8 个）</span></label>
                <div class="share-tags">
                  <span v-for="(tag, idx) in shareForm.tags" :key="idx" class="share-tag">
                    {{ tag }}
                    <span class="share-tag-remove" @click="removeShareTag(idx)">&times;</span>
                  </span>
                  <input 
                    v-if="shareForm.tags.length < 8"
                    v-model="shareTagInput" 
                    placeholder="输入标签后回车" 
                    class="share-tag-input" 
                    @keydown.enter.prevent="addShareTag" 
                  />
                </div>
              </div>
              <div class="share-form-item">
                <label>适合人群</label>
                <input v-model="shareForm.target_audience" placeholder="例如：零基础、转行人员、在校学生..." class="share-input" />
              </div>
            </div>
          </div>
        </div>
        <div class="share-dialog-footer" v-if="!shareLoading">
          <button class="share-btn-cancel" @click="closeShareDialog">取消</button>
          <button class="share-btn-submit" @click="submitShare" :disabled="shareSubmitting">
            <span v-if="shareSubmitting" class="share-btn-spinner"></span>
            {{ shareSubmitting ? '发布中...' : '发布到路线市场' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 考试弹窗 -->
    <!-- ============================================================ -->
    <div v-if="examDialogVisible" class="exam-dialog-overlay">
      <div class="exam-dialog">
        <div class="exam-dialog-header">
          <h3>{{ examShowResults ? '考试评估' : '阶段考试' }}</h3>
          <div class="header-actions">
            <!-- 提交按钮：未提交时显示 -->
            <template v-if="!isAllSubmitted && !examShowResults">
              <el-button 
                type="primary" 
                size="default"
                @click="submitAllExamAnswers"
                :loading="examSubmitting"
                :disabled="!allQuestionsAnswered || examSubmitting"
              >
                {{ examSubmitting ? '提交中...' : '提交全部答案' }}
              </el-button>
            </template>
            <template v-else-if="isAllSubmitted && !examShowResults">
              <el-tag type="success" size="large" effect="dark">
                <el-icon><Check /></el-icon>
                已提交
              </el-tag>
            </template>
            <button class="exam-dialog-close" @click="closeExamDialog">×</button>
          </div>
        </div>
        
        <!-- 加载状态 -->
        <div v-if="examLoading" class="exam-dialog-body exam-loading">
          <div class="loading-container">
            <el-icon class="is-loading" :size="48"><Loading /></el-icon>
            <p>正在生成考题，请稍候...</p>
            <p class="loading-tip">考题生成可能需要一些时间，请耐心等待</p>
          </div>
        </div>
        
        <!-- 考试已完成提示 -->
        <div v-else-if="examAlreadyCompleted" class="exam-dialog-body exam-completed">
          <div class="completed-container">
            <el-icon :size="64" color="#E6A23C"><CircleCheck /></el-icon>
            <h3>该阶段考试已完成</h3>
            <p>您已经完成了该阶段的考试，无需重复作答。</p>
            <el-button type="primary" @click="closeExamDialog">我知道了</el-button>
          </div>
        </div>

        <!-- 答题模式 -->
        <template v-else-if="examData && !examShowResults">
          <div class="exam-dialog-body">
            <!-- 进度条 -->
            <div class="exam-progress-bar">
              <div class="progress-info">
                <span>进度：{{ completedCount }}/{{ totalExamQuestions }}</span>
                <span v-if="allQuestionsAnswered" class="complete-tag">全部已答</span>
                <span v-else class="incomplete-tag">还有 {{ totalExamQuestions - completedCount }} 题未答</span>
                <span v-if="isAllSubmitted" class="submitted-tag">已提交</span>
              </div>
              <el-progress :percentage="totalExamQuestions > 0 ? Math.round(completedCount / totalExamQuestions * 100) : 0" :stroke-width="8" />
            </div>

            <!-- 导航按钮 -->
            <div class="exam-question-nav">
              <el-button 
                size="small" 
                @click="prevExamQuestion" 
                :disabled="currentQuestionIndex === 0"
              >
                上一题
              </el-button>
              <span class="nav-info">第 {{ currentQuestionIndex + 1 }} / {{ totalExamQuestions }} 题</span>
              <el-button 
                size="small" 
                type="primary" 
                @click="nextExamQuestion"
                :disabled="currentQuestionIndex === totalExamQuestions - 1"
              >
                下一题
              </el-button>
            </div>

            <!-- 当前题目 -->
            <div class="exam-question-container" v-if="currentExamQuestion">
              <div class="question-header">
                <span class="question-type">{{ currentExamQuestion.typeLabel }}</span>
                <span class="question-number">第 {{ currentQuestionIndex + 1 }} 题</span>
                <span class="question-status" :class="{ answered: isCurrentAnswered, submitted: isAllSubmitted }">
                  {{ isAllSubmitted ? '已提交' : (isCurrentAnswered ? '已作答' : '待作答') }}
                </span>
                <span v-if="currentExamQuestion.difficulty" class="question-difficulty-tag">
                  {{ currentExamQuestion.difficulty }}
                </span>
              </div>
              
              <div class="question-text">{{ currentExamQuestion.question || currentExamQuestion.description }}</div>
              
              <!-- ======================================== -->
              <!-- 选择题选项 -->
              <!-- ======================================== -->
              <div class="options-container" v-if="['single_choice', 'multiple_choice'].includes(currentExamQuestion.type)">
                <div 
                  v-for="(optText, optIdx) in currentExamQuestion.options" 
                  :key="optIdx"
                  class="option-item"
                  :class="{
                    selected: isExamOptionSelected(currentExamQuestion, String.fromCharCode(65 + optIdx))
                  }"
                  @click="!isAllSubmitted && selectExamAnswer(currentExamQuestion, String.fromCharCode(65 + optIdx))"
                  :style="{ cursor: isAllSubmitted ? 'not-allowed' : 'pointer', opacity: isAllSubmitted ? 0.7 : 1 }"
                >
                  <!-- <span class="option-label">{{ String.fromCharCode(65 + optIdx) }}.</span> -->
                  <span class="option-text">{{ optText }}</span>
                </div>
                <div v-if="currentExamQuestion.type === 'multiple_choice'" class="multi-hint">（多选题，可多选）</div>
              </div>

              <!-- ======================================== -->
              <!-- 判断题 -->
              <!-- ======================================== -->
              <div class="judge-container" v-if="currentExamQuestion.type === 'judge'">
                <div class="judge-options">
                  <el-button 
                    :type="isExamOptionSelected(currentExamQuestion, '正确') ? 'success' : 'default'"
                    :plain="!isExamOptionSelected(currentExamQuestion, '正确')"
                    @click="!isAllSubmitted && selectExamAnswer(currentExamQuestion, '正确')"
                    :disabled="isAllSubmitted"
                  >
                    正确
                  </el-button>
                  <el-button 
                    :type="isExamOptionSelected(currentExamQuestion, '错误') ? 'danger' : 'default'"
                    :plain="!isExamOptionSelected(currentExamQuestion, '错误')"
                    @click="!isAllSubmitted && selectExamAnswer(currentExamQuestion, '错误')"
                    :disabled="isAllSubmitted"
                  >
                    错误
                  </el-button>
                </div>
              </div>

              <!-- ======================================== -->
              <!-- 填空题 -->
              <!-- ======================================== -->
              <div class="fill-container" v-if="currentExamQuestion.type === 'fill_blank'">
                <el-input 
                  :model-value="examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index] || ''"
                  placeholder="请输入你的答案..."
                  :disabled="isAllSubmitted"
                  @update:model-value="(val) => { 
                    if (!isAllSubmitted) {
                      const key = currentExamQuestion.type + '_' + currentExamQuestion.index; 
                      examAnswers[key] = val || ''; 
                    }
                  }"
                />
              </div>

              <!-- ======================================== -->
              <!-- 简答题 -->
              <!-- ======================================== -->
              <div class="short-container" v-if="currentExamQuestion.type === 'essay'">
                <el-input 
                  :model-value="examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index] || ''"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入你的答案..."
                  :disabled="isAllSubmitted"
                  @update:model-value="(val) => { 
                    if (!isAllSubmitted) {
                      const key = currentExamQuestion.type + '_' + currentExamQuestion.index; 
                      examAnswers[key] = val || ''; 
                    }
                  }"
                />
              </div>

              <!-- ======================================== -->
              <!-- 编程题（示例和提示默认折叠） -->
              <!-- ======================================== -->
              <div class="programming-container" v-if="currentExamQuestion.type === 'programming'">
                <!-- 题目信息 -->
                <div class="programming-info">
                  <div v-if="currentExamQuestion.input_format" class="info-item">
                    <strong>输入格式：</strong>{{ currentExamQuestion.input_format }}
                  </div>
                  <div v-if="currentExamQuestion.output_format" class="info-item">
                    <strong>输出格式：</strong>{{ currentExamQuestion.output_format }}
                  </div>
                  <div v-if="currentExamQuestion.time_limit" class="info-item">
                    <strong>时间限制：</strong>{{ currentExamQuestion.time_limit }}
                  </div>
                  <div v-if="currentExamQuestion.memory_limit" class="info-item">
                    <strong>内存限制：</strong>{{ currentExamQuestion.memory_limit }}
                  </div>
                </div>

                <!-- 示例（默认折叠） -->
                <div class="programming-examples" v-if="currentExamQuestion.examples && currentExamQuestion.examples.length > 0">
                  <div class="section-header" @click="!isAllSubmitted && toggleExampleExpand(currentExamQuestion)">
                    <span class="section-title">示例</span>
                    <el-icon class="expand-icon" :class="{ expanded: exampleExpandedMap[currentExamQuestion.type + '_' + currentExamQuestion.index] }">
                      <ArrowDown />
                    </el-icon>
                  </div>
                  <div v-show="exampleExpandedMap[currentExamQuestion.type + '_' + currentExamQuestion.index]" class="section-content">
                    <div v-for="(ex, exIdx) in currentExamQuestion.examples" :key="exIdx" class="example-item">
                      <div><strong>示例 {{ exIdx + 1 }} 输入：</strong></div>
                      <pre>{{ ex.input }}</pre>
                      <div><strong>示例 {{ exIdx + 1 }} 输出：</strong></div>
                      <pre>{{ ex.output }}</pre>
                      <div v-if="ex.explanation" class="example-explanation">
                        <strong>说明：</strong>{{ ex.explanation }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 提示（默认折叠） -->
                <div class="programming-hints" v-if="currentExamQuestion.hints && currentExamQuestion.hints.length > 0">
                  <div class="section-header" @click="!isAllSubmitted && toggleHintExpand(currentExamQuestion)">
                    <span class="section-title">提示</span>
                    <el-icon class="expand-icon" :class="{ expanded: hintExpandedMap[currentExamQuestion.type + '_' + currentExamQuestion.index] }">
                      <ArrowDown />
                    </el-icon>
                  </div>
                  <div v-show="hintExpandedMap[currentExamQuestion.type + '_' + currentExamQuestion.index]" class="section-content">
                    <ul>
                      <li v-for="(hint, hIdx) in currentExamQuestion.hints" :key="hIdx">{{ hint }}</li>
                    </ul>
                  </div>
                </div>

                <!-- 代码编辑器 -->
                <div class="code-editor-container" :style="{ opacity: isAllSubmitted ? 0.7 : 1 }">
                  <div class="line-numbers">
                    <div v-for="n in (lineCountMap[currentExamQuestion.type + '_' + currentExamQuestion.index] || 10)" :key="n">{{ n }}</div>
                  </div>
                  <textarea
                    v-model="examAnswers[currentExamQuestion.type + '_' + currentExamQuestion.index]"
                    @input="updateLineCount(currentExamQuestion)"
                    @keydown="handleCodeKeydown($event, currentExamQuestion)"
                    placeholder="// 在此编写代码..."
                    class="code-textarea"
                    spellcheck="false"
                    :disabled="isAllSubmitted"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- ======================================== -->
        <!-- 考试评估结果页 -->
        <!-- ======================================== -->
        <div class="exam-dialog-body result-page" v-if="examShowResults && examResults && !showAssessmentReport">
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

            <div class="progress-rings">
              <div class="ring-item">
                <el-progress 
                  type="circle" 
                  :percentage="examResults.total > 0 ? Math.round((examResults.score || 0) / examResults.total * 100) : 0" 
                  :width="140"
                  :stroke-width="8"
                  :color="(examResults.score || 0) / examResults.total >= 0.6 ? '#67C23A' : '#F56C6C'"
                >
                  <template #default="{ percentage }">
                    <span class="percentage-value">{{ percentage }}%</span>
                  </template>
                </el-progress>
                <div class="ring-label">得分率</div>
              </div>
              <div class="ring-item">
                <el-progress 
                  type="circle" 
                  :percentage="100" 
                  :width="140"
                  :stroke-width="8"
                  color="#409EFF"
                >
                  <template #default>
                    <span class="percentage-value">{{ examResults.score || 0 }}/{{ examResults.total || totalExamQuestions }}</span>
                  </template>
                </el-progress>
                <div class="ring-label">总分</div>
              </div>
            </div>
          </div>

          <div class="encouragement">
            <div class="encourage-text">{{ examResults.message || '考试完成！' }}</div>
            <div class="wrong-note">错题已经自动移入错题本</div>
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
              <div class="wrong-answer">正确答案：{{ result.correct_answer || '-' }}</div>
              <div class="wrong-user-answer">你的答案：{{ result.user_answer || '未作答' }}</div>
            </div>
          </div>
          
          <div class="bottom-actions">
            <el-button @click="closeExamDialog" :disabled="generatingAssessment">关闭</el-button>
            <el-button 
              v-if="examResults.passed" 
              type="warning"
              @click="generateAssessmentReport"
              :loading="generatingAssessment"
            >
              {{ generatingAssessment ? '正在生成评估报告...' : '生成评估报告' }}
            </el-button>
          </div>
        </div>

        <!-- ======================================== -->
        <!-- 阶段评估报告页（替换考试结果） -->
        <!-- ======================================== -->
        <div class="exam-dialog-body assessment-page" v-if="examShowResults && showAssessmentReport && assessmentReport && assessmentReport.assessment">
          <div class="assessment-report">
            <!-- 头部：阶段概览 -->
            <div class="assessment-header">
              <h3>阶段评估报告 - {{ assessmentReport.phase_name || '' }}</h3>
              <el-tag :type="assessmentReport.assessment.readiness?.ready ? 'success' : 'danger'">
                {{ assessmentReport.assessment.phase_summary?.status || (assessmentReport.assessment.readiness?.ready ? '通过' : '未通过') }}
              </el-tag>
            </div>
            
            <!-- 阶段概览 -->
            <div class="assessment-summary" v-if="assessmentReport.assessment.phase_summary">
              <h4>阶段概览</h4>
              <div class="summary-info">
                <div class="summary-item">
                  <span class="summary-label">综合得分：</span>
                  <span class="summary-value score">{{ assessmentReport.assessment.phase_summary.score }}分</span>
                </div>
                <div class="summary-item">
                  <span class="summary-label">评估状态：</span>
                  <el-tag size="small" :type="assessmentReport.assessment.readiness?.ready ? 'success' : 'warning'">
                    {{ assessmentReport.assessment.phase_summary.status }}
                  </el-tag>
                </div>
              </div>
              <p class="summary-text">{{ assessmentReport.assessment.phase_summary.summary }}</p>
              <div class="time-efficiency" v-if="assessmentReport.assessment.phase_summary.time_efficiency">
                <span>计划学时：{{ assessmentReport.assessment.phase_summary.time_efficiency.planned_hours }}h</span>
                <span>实际学时：{{ assessmentReport.assessment.phase_summary.time_efficiency.actual_hours }}h</span>
                <span class="efficiency-eval">{{ assessmentReport.assessment.phase_summary.time_efficiency.evaluation }}</span>
              </div>
            </div>
            
            <!-- 知识点分析 -->
            <div class="assessment-knowledge" v-if="assessmentReport.assessment.knowledge_point_analysis?.length">
              <h4>知识点掌握分析</h4>
              <div class="knowledge-list">
                <div 
                  v-for="(kp, idx) in assessmentReport.assessment.knowledge_point_analysis" 
                  :key="idx"
                  class="knowledge-item"
                  :class="{ weak: kp.mastery === '薄弱' }"
                >
                  <div class="kp-header">
                    <span class="kp-name">{{ kp.name }}</span>
                    <div class="kp-mastery">
                      <el-progress 
                        :percentage="kp.score" 
                        :stroke-width="8"
                        :color="kp.score >= 60 ? '#67C23A' : kp.score >= 40 ? '#E6A23C' : '#F56C6C'"
                        style="width: 120px"
                      />
                      <el-tag size="small" :type="kp.mastery === '薄弱' ? 'danger' : kp.mastery === '良好' ? 'success' : 'warning'">
                        {{ kp.mastery }}
                      </el-tag>
                    </div>
                  </div>
                  
                  <p class="kp-comment">{{ kp.comment }}</p>
                </div>
              </div>
            </div>
            
            <!-- 薄弱点分析 -->
            <div class="assessment-weak" v-if="assessmentReport.assessment.weak_points?.length">
              <h4>薄弱点分析</h4>
              <div 
                v-for="(wp, idx) in assessmentReport.assessment.weak_points" 
                :key="idx"
                class="weak-item"
              >
                <div class="weak-point">
                  <el-icon color="#F56C6C"><WarningFilled /></el-icon>
                  {{ wp.point }}
                </div>
                <div class="weak-impact">
                  <strong>对下一阶段的影响：</strong>{{ wp.impact_on_next_phase }}
                </div>
              </div>
            </div>
            
            <!-- 改进分析 -->
            <div class="assessment-improvement" v-if="assessmentReport.assessment.improvement_analysis">
              <h4>改进分析</h4>
              <p v-if="assessmentReport.assessment.improvement_analysis.compared_to_previous">
                <strong>与上阶段对比：</strong>{{ assessmentReport.assessment.improvement_analysis.compared_to_previous }}
              </p>
              <p v-if="assessmentReport.assessment.improvement_analysis.details">
                <strong>详细分析：</strong>{{ assessmentReport.assessment.improvement_analysis.details }}
              </p>
            </div>
            
            <!-- 准备度评估 -->
            <div class="assessment-readiness" v-if="assessmentReport.assessment.readiness">
              <h4>准备度评估（{{ assessmentReport.assessment.readiness.score }}分）</h4>
              <div class="readiness-status">
                <el-tag :type="assessmentReport.assessment.readiness.ready ? 'success' : 'danger'" size="large">
                  {{ assessmentReport.assessment.readiness.ready ? '已准备好进入下一阶段' : '暂不建议进入下一阶段' }}
                </el-tag>
              </div>
              <div class="readiness-gaps" v-if="assessmentReport.assessment.readiness.gaps?.length">
                <p><strong>待填补的差距：</strong></p>
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
            
            <!-- 调整建议 -->
            <div class="assessment-adjustments" v-if="assessmentReport.assessment.adjustments">
              <h4>调整建议</h4>
              <div v-if="assessmentReport.assessment.adjustments.needs_remedy">
                <p class="remedy-label"><el-icon color="#F56C6C"><WarningFilled /></el-icon> 需要回炉巩固</p>
                <ul v-if="assessmentReport.assessment.adjustments.remedy_suggestions?.length" class="remedy-list">
                  <li v-for="(item, idx) in assessmentReport.assessment.adjustments.remedy_suggestions" :key="idx">{{ item }}</li>
                </ul>
              </div>
              <div v-if="assessmentReport.assessment.adjustments.difficulty_adjustment" class="difficulty-adj">
                <strong>难度调整：</strong>
                <el-tag :type="assessmentReport.assessment.adjustments.difficulty_adjustment.action === '调低' ? 'warning' : 'info'">
                  {{ assessmentReport.assessment.adjustments.difficulty_adjustment.action }}
                </el-tag>
                <span class="adj-reason">{{ assessmentReport.assessment.adjustments.difficulty_adjustment.reason }}</span>
              </div>
            </div>
            
            <!-- 下一步行动 -->
            <div class="assessment-actions">
              <el-button
                type="primary"
                @click="updateNextPhasePlan"
                :loading="updatingNextPhase"
                v-if="currentExamPhaseIndex < phases.length - 1"
              >
                {{ updatingNextPhase ? '正在规划下一阶段...' : '更新下一阶段计划' }}
              </el-button>
              <el-button @click="closeExamDialog">关闭</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <Transition name="fade">
    <div v-if="showConflictDialog" class="conflict-dialog-mask">
      <div class="conflict-dialog">
        <div class="conflict-dialog-header">
          <svg t="1783932506294" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1708" width="24" height="24"><path d="M512 958.016611c-245.919634 0-446.016611-200.064292-446.016611-446.016611 0-245.919634 200.095256-446.016611 446.016611-446.016611 245.952318 0 446.016611 200.064292 446.016611 446.016611S757.952318 958.016611 512 958.016611zM512 129.983389c-210.655557 0-382.016611 171.359333-382.016611 382.016611 0 210.624593 171.359333 382.016611 382.016611 382.016611 210.624593 0 382.016611-171.359333 382.016611-382.016611S722.624593 129.983389 512 129.983389z" fill="#fb722e" p-id="1709"></path><path d="M463.99957 304.00043c0 26.509985 21.490445 48.00043 48.00043 48.00043s48.00043-21.490445 48.00043-48.00043-21.490445-48.00043-48.00043-48.00043S463.99957 277.490445 463.99957 304.00043z" fill="#fb722e" p-id="1710"></path><path d="M512 768c-17.664722 0-32.00086-14.303454-32.00086-32.00086L479.99914 448c0-17.664722 14.336138-32.00086 32.00086-32.00086s32.00086 14.336138 32.00086 32.00086l0 287.99914C544.00086 753.696546 529.664722 768 512 768z" fill="#fb722e" p-id="1711"></path></svg>
          <span>学习计划建议</span>
        </div>
        <div class="conflict-dialog-content">
          <div class="conflict-message">{{ conflictData.message }}</div>
          <div v-if="conflictData.weak_points_info.length > 0" class="weak-points-list">
            <div v-for="(point, index) in conflictData.weak_points_info" :key="index" class="weak-point-item">
              <div class="point-header">
                <span class="point-priority" :class="'priority-' + point.priority">{{ point.priority }}</span>
                <span class="point-title">{{ point.point }}</span>
              </div>
              <div class="point-performance">{{ point.performance }}</div>
              <div class="point-reason">{{ point.possible_reason }}</div>
            </div>
          </div>
        </div>
        <div class="conflict-dialog-footer">
          <button class="conflict-btn conflict-btn-reject" @click="handleConflictOption(false)">
            拒绝 - 生成我所输入的主题
          </button>
          <button class="conflict-btn conflict-btn-accept" @click="handleConflictOption(true)">
            接受 - 生成上述学习计划
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- 学习路线市场 -->
  <PathPlanMarket 
    v-if="showMarket" 
    :userId="currentUserId" 
    @close="showMarket = false"
    @adopted="fetchPlanList"
  />
</template>



<style scoped>
/* =====================================================================
   样式说明：使用 CSS 变量（定义在 base.css 中）
   ===================================================================== */

/* -------------------- 加载遮罩 z-index -------------------- */
.path-content {
  position: relative;
}
.path-content :deep(.el-loading-mask) {
  z-index: 2 !important;
}

/* -------------------- 页面外层容器 -------------------- */
.learning-path-container {
  width: 100%;
  min-width: 1384px;
  min-height: 85vh;
  background: transparent;
  padding: 20px;
}

/* -------------------- 头部标题区域 -------------------- */
.path-header {
  text-align: center;
  margin-bottom: 20px;
}
.header-left h1 {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  font-family: "抖音美好体", "三极行楷简体-粗", sans-serif;
  color: var(--text-title);
}
.header-left .subtitle {
  font-size: 14px;
  color: var(--text-gray);
}

/* -------------------- 详情页顶部操作栏 -------------------- */
.detail-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 20px;
  padding: 0 4px;
}

/* -------------------- 空状态 / 创建表单 -------------------- */
.no-plan-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 500px;
}
.no-plan-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 48px 40px;
  text-align: center;
  box-shadow: var(--shadow-normal);
  max-width: 550px;
  width: 100%;
}
.no-plan-icon {
  font-size: 64px;
  margin-bottom: 20px;
}
.no-plan-card h3 {
  font-size: 24px;
  margin-bottom: 12px;
  color: var(--text-title);
}
.no-plan-card p {
  color: var(--text-gray);
  margin-bottom: 28px;
}
.input-area {
  display: flex;
  gap: 12px;
}
.plan-input {
  flex: 1;
}

/* -------------------- 创建计划区域（列表上方） -------------------- */
.create-plan-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 16px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
  border: 1px dashed var(--primary);
}
.create-plan-inner {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.create-plan-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--primary);
  font-weight: 500;
  white-space: nowrap;
}
.create-plan-label .el-icon {
  font-size: 18px;
}
.create-plan-form {
  display: flex;
  flex: 1;
  gap: 12px;
  min-width: 280px;
}
.create-plan-input {
  flex: 1;
}

/* -------------------- 计划列表 -------------------- */
.plan-list-wrapper {
  max-width: 1200px;
  margin: 0 auto;
}
.plan-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 0 4px;
}
.list-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-title);
}
.list-count {
  margin-left: 10px;
  font-size: 14px;
  color: var(--text-gray);
}

/* 学习路线市场入口按钮 */
.market-entry-btn {
  margin-top: 20px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: var(--grad-primary);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s;
  box-shadow: var(--shadow-brand);
}

.market-entry-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(45, 125, 219, 0.4);
}

.market-entry-btn:active {
  transform: translateY(0);
}

.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.plan-card-item {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: var(--shadow-normal);
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid var(--border-color);
}
.plan-card-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-brand);
  border-color: var(--primary);
}
.plan-card-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.plan-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
}
.plan-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title);
  margin: 0;
  line-height: 1.4;
  flex: 1;
}
.plan-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--text-gray);
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.plan-card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

/* -------------------- 已有计划详情 -------------------- */
.has-plan-wrapper {
  max-width: 1200px;
  margin: 0 auto;
  animation: fadeIn 0.4s ease-out;
}

/* -------------------- 顶部概览渐变卡片 -------------------- */
.plan-overview {
  background: var(--grad-primary);
  border-radius: var(--radius-lg);
  padding: 28px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #ffffff;
  margin-bottom: 32px;
  box-shadow: var(--shadow-brand);
}
.overview-left h2 {
  font-size: 24px;
  margin-bottom: 12px;
  font-weight: 600;
}
.overview-left .description {
  opacity: 0.9;
  font-size: 14px;
  margin-bottom: 16px;
  max-width: 500px;
  line-height: 1.5;
}
.info-tags {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.info-tags .el-tag {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
}
.progress-circle {
  position: relative;
  text-align: center;
}
.progress-label {
  display: block;
  font-size: 12px;
  margin-top: 8px;
  opacity: 0.9;
}

/* -------------------- 版本树 -------------------- */
.version-tree-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  margin-bottom: 32px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}
.version-tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  cursor: pointer;
  background: var(--bgc-light);
  transition: background 0.2s;
}
.version-tree-header:hover {
  background: var(--bgc-mid);
}
.version-tree-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: var(--text-title);
}
.version-tree-title .el-icon {
  color: var(--primary);
}
.version-tree-header .el-icon {
  transition: transform 0.3s;
}
.version-tree-header .el-icon.rotated {
  transform: rotate(180deg);
}
.version-tree-content {
  padding: 16px 20px;
}
.version-tree-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-gray);
}
.version-tree-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.version-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: var(--radius-md);
  background: var(--bg-page);
  transition: all 0.2s;
}
.version-item:hover {
  background: var(--bgc-light);
}
.version-item.active {
  background: var(--primary-fade);
  border: 1px solid var(--primary);
}
.version-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 20px;
  flex-shrink: 0;
}
.version-line {
  width: 2px;
  height: 100%;
  background: var(--border-color);
  position: absolute;
  top: 0;
  left: 9px;
}
.version-item:last-child .version-line {
  display: none;
}
.version-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--border-color);
  flex-shrink: 0;
  z-index: 1;
  margin-top: 2px;
}
.version-item.active .version-dot {
  background: var(--primary);
}
.version-item.trigger-initial .version-dot {
  background: var(--pass);
}
.version-item.trigger-completed .version-dot {
  background: var(--primary);
}
.version-item.trigger-regenerated .version-dot {
  background: var(--coming);
}
.version-info {
  flex: 1;
  min-width: 0;
}
.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.version-number {
  font-weight: 600;
  color: var(--text-title);
}
.version-id {
  font-size: 12px;
  color: var(--text-gray);
  font-family: monospace;
}
.version-item.active .active-tag {
  background: var(--pass);
  border-color: var(--pass);
  color: white;
}
.version-desc {
  font-size: 13px;
  color: var(--text-body);
  margin-bottom: 4px;
}
.version-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-gray);
}
.version-actions {
  margin-top: 8px;
}
.version-actions .el-button {
  padding: 4px 12px;
}
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  max-height: 0;
}
.slide-fade-enter-to,
.slide-fade-leave-from {
  opacity: 1;
  max-height: 500px;
}

.tree-fade-enter-active,
.tree-fade-leave-active {
  transition: all 0.3s ease;
}

.tree-fade-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.tree-fade-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* -------------------- 时间线容器 -------------------- */
.phases-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.phase-item {
  display: flex;
  margin-bottom: 20px;
  position: relative;
}

/* -------------------- 时间线圆点竖线 -------------------- */
.timeline-marker {
  width: 60px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.marker-dot {
  width: 36px;
  height: 36px;
  background: var(--bg-card);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
  box-shadow: var(--shadow-normal);
  z-index: 2;
  transition: all 0.3s ease;
}
.phase-active .marker-dot {
  background: var(--primary);
  color: white;
  box-shadow: 0 0 0 4px var(--primary-fade);
}
.phase-completed .marker-dot {
  background: var(--pass);
  color: white;
}
.phase-locked .marker-dot {
  background: var(--bgc-mid);
  color: var(--text-gray);
}
.timeline-line {
  width: 2px;
  flex: 1;
  background: var(--border-color);
  margin-top: 4px;
  min-height: 40px;
}

/* -------------------- 阶段卡片通用样式 -------------------- */
.phase-card {
  flex: 1;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 12px;
  transition: all 0.3s ease;
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-color);
}
.phase-card:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-brand);
  border-color: var(--primary);
}
.phase-item.phase-active .phase-card {
  border-left: 4px solid var(--primary);
}
.phase-item.phase-completed .phase-card {
  border-left: 4px solid var(--pass);
}
.phase-item.phase-locked .phase-card {
  opacity: 0.7;
  filter: grayscale(0.1);
}

/* -------------------- 卡片头部 -------------------- */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.phase-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title);
  display: flex;
  align-items: center;
  gap: 8px;
}
.phase-meta {
  font-size: 13px;
  color: var(--text-gray);
  display: flex;
  gap: 16px;
}
.phase-actions {
  display: flex;
  gap: 8px;
}

/* -------------------- 卡片内容 -------------------- */
.card-desc {
  color: var(--text-body);
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 12px;
}
.card-milestone {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--primary);
  background: var(--primary-light);
  padding: 6px 12px;
  border-radius: 999px;
  width: fit-content;
  margin-bottom: 12px;
}
.card-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}
.card-progress .el-progress {
  flex: 1;
}
.progress-text {
  font-size: 12px;
  color: var(--text-gray);
  min-width: 40px;
}

/* -------------------- 知识点列表 -------------------- */
.phase-knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

/* 知识点行 - 左右布局 */
.knowledge-item {
  background: var(--bgc-light);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
}
.knowledge-item:hover {
  border-color: var(--primary-light);
}
.knowledge-item.kp-completed {
  border-color: var(--pass);
  background: var(--pass-bg-color);
}

.knowledge-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

/* 左侧：知识点信息 */
.knowledge-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.kp-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: var(--primary);
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.knowledge-item.kp-completed .kp-badge {
  background: var(--pass);
}
.kp-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title);
}
.knowledge-info .el-tag {
  flex-shrink: 0;
}

/* 右侧：操作按钮 */
.knowledge-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.kp-locked-icon {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-gray);
}
.knowledge-actions .el-button {
  height: 32px;
}

/* 资源列表 - 在知识点行下方 */
.kp-resources {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-color);
}
.kp-resource-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kp-resource-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
  border: 1px solid transparent;
}
.kp-resource-item:hover {
  background: var(--primary-fade);
  border-color: var(--primary-light);
}
.kp-resource-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.kp-resource-info .el-icon {
  font-size: 16px;
}
.kp-resource-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-body);
}
.kp-resource-id {
  font-size: 11px;
  color: var(--text-gray);
  background: var(--bgc-mid);
  padding: 1px 6px;
  border-radius: 999px;
}
.kp-resource-item .el-button {
  flex-shrink: 0;
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

/* -------------------- 阶段考试按钮 -------------------- */
.phase-exam-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.phase-exam-section .exam-btn-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}
.phase-exam-section .el-button {
  min-width: 160px;
}
.exam-loading-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--primary);
  animation: pulse 1.5s ease-in-out infinite;
}
.exam-loading-tip .el-icon {
  font-size: 16px;
}
.exam-completed-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--success);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* -------------------- 锁定提示 -------------------- */
.phase-lock-tip {
  position: absolute;
  left: 60px;
  bottom: -8px;
  font-size: 12px;
  color: var(--text-gray);
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-normal);
}

/* -------------------- 空状态提示 -------------------- */
.no-phases-tip {
  padding: 40px 0;
}

/* =====================================================================
   续期计划样式
   ===================================================================== */
.continuation-section {
  margin-top: 40px;
  padding-top: 30px;
  border-top: 2px dashed var(--border-color);
}
.continuation-card {
  background-color: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 28px 32px;
  color: var(--text-gray);
  box-shadow: var(--shadow-brand);
}
.continuation-header {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
}
.continuation-header .el-icon {
  font-size: 28px;
}
.continuation-desc {
  width: 530px;
  font-size: 15px;
  opacity: 0.9;
  margin: 0 auto;
  margin-bottom: 20px;
}
.continuation-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.continuation-actions .el-button {
  border: 2px solid rgba(255,255,255,0.3);
  background: rgba(255,255,255,0.15);
  color: #fff;
}
.continuation-actions .el-button:hover:not(.is-disabled) {
  background: rgba(255,255,255,0.25);
}
.continuation-actions .el-button.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.continuation-actions .el-button.el-button--danger {
  color: var(--text-gray);
  border-color: var(--text-gray);
}
.continuation-actions .el-button.el-button--danger:hover {
  color: var(--main-delete);
  border-color: var(--main-delete);
}
.continuation-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.15);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 14px;
}

/* 夜间模式 - 续期按钮 */
.dark .continuation-actions .el-button {
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}
.dark .continuation-actions .el-button:hover:not(.is-disabled) {
  background: rgba(59, 130, 246, 0.25);
}
.dark .continuation-tip {
  background: rgba(59, 130, 246, 0.15);
}

/* =====================================================================
   考试弹窗样式
   ===================================================================== */
.exam-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.3s ease-out;
}

.exam-dialog {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 95%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  animation: slideUp 0.3s ease-out;
}

.exam-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.exam-dialog-header h3 {
  margin: 0;
  font-size: 20px;
  color: var(--text-title);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.exam-dialog-close {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: var(--text-gray);
  padding: 0 8px;
  line-height: 1;
  transition: color 0.2s;
}
.exam-dialog-close:hover {
  color: var(--danger);
}

.exam-dialog-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

/* 加载状态 */
.exam-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}
.loading-container {
  text-align: center;
}
.loading-container .el-icon {
  color: var(--primary);
  margin-bottom: 16px;
}
.loading-container p {
  font-size: 16px;
  color: var(--text-body);
  margin: 8px 0;
}
.loading-tip {
  font-size: 13px;
  color: var(--text-gray) !important;
}

/* 考试已完成 */
.exam-completed {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}
.completed-container {
  text-align: center;
}
.completed-container .el-icon {
  margin-bottom: 16px;
}
.completed-container h3 {
  font-size: 20px;
  color: var(--text-title);
  margin: 12px 0;
}
.completed-container p {
  font-size: 14px;
  color: var(--text-gray);
  margin-bottom: 20px;
}

/* 考试进度条 */
.exam-progress-bar {
  margin-bottom: 16px;
  padding: 10px 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 14px;
  color: var(--text-gray);
}
.complete-tag {
  color: var(--success);
  font-weight: 700;
}
.incomplete-tag {
  color: var(--warning);
  font-weight: 700;
}
.submitted-tag {
  color: var(--primary);
  font-weight: 700;
}

/* 导航按钮 */
.exam-question-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  margin-bottom: 16px;
}
.nav-info {
  font-size: 14px;
  color: var(--text-gray);
  font-weight: 500;
}

/* 题目容器 */
.exam-question-container {
  padding: 16px 20px;
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
.question-status.answered {
  color: var(--success);
}
.question-status.submitted {
  color: var(--primary);
}
.question-difficulty-tag {
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 4px;
  background: var(--warning);
  color: #fff;
}
.question-text {
  font-size: 17px;
  font-weight: 500;
  color: var(--text-title);
  margin-bottom: 16px;
  line-height: 1.6;
}

/* 选择题 */
.options-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.option-item {
  display: flex;
  align-items: center;
  padding: 8px 14px;
  border: 2px solid var(--border-color);
  border-radius: 8px;
  transition: all 0.3s;
}
.option-item:hover:not(.selected):not(.show-correct):not(.show-wrong) {
  border-color: var(--primary);
  background: rgba(45, 125, 219, 0.05);
}
.option-item.selected {
  border-color: var(--primary);
  background: rgba(45, 125, 219, 0.08);
}
.option-item.show-correct {
  border-color: var(--success);
  background: rgba(103, 194, 58, 0.12);
}
.option-item.show-wrong {
  border-color: var(--danger);
  background: rgba(245, 108, 108, 0.12);
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
  font-weight: 700;
  font-size: 18px;
}
.option-mark.correct-mark {
  color: var(--success);
}
.option-mark.wrong-mark {
  color: var(--danger);
}
.multi-hint {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 6px;
}

/* 判断题 */
.judge-container {
  display: flex;
  justify-content: center;
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

/* 填空题/简答题 */
.fill-container, .short-container {
  padding: 6px 0;
}
:deep(.fill-container .el-input__inner) {
  font-size: 15px;
}
:deep(.short-container .el-textarea__inner) {
  font-size: 15px;
}

/* ================= 编程题样式 ================= */
.programming-container {
  margin-top: 12px;
}
.programming-info {
  padding: 10px 14px;
  background: var(--bgc-light);
  border-radius: 6px;
  margin-bottom: 10px;
}
.programming-info .info-item {
  font-size: 14px;
  color: var(--text-body);
  margin: 3px 0;
}

/* 可折叠区域 */
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 0;
  user-select: none;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 6px;
}
.section-header:hover {
  color: var(--primary);
}
.section-title {
  font-weight: 600;
  color: var(--text-title);
  font-size: 14px;
}
.expand-icon {
  transition: transform 0.3s ease;
  font-size: 16px;
}
.expand-icon.expanded {
  transform: rotate(180deg);
}
.section-content {
  padding: 8px 0;
}

.programming-examples {
  margin: 10px 0;
}
.example-item {
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  margin-bottom: 6px;
  border: 1px solid var(--border-color);
}
.example-item pre {
  background: var(--bgc-dark);
  color: var(--text-light);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  margin: 4px 0;
  font-size: 13px;
  overflow-x: auto;
}
.example-explanation {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-gray);
}
.programming-hints {
  margin: 10px 0;
}
.programming-hints ul {
  margin: 4px 0;
  padding-left: 20px;
  color: var(--text-gray);
}
.programming-hints ul li {
  font-size: 13px;
  margin: 2px 0;
}

/* 代码编辑器 */
.code-editor-container {
  position: relative;
  display: flex;
  width: 100%;
  min-height: 180px;
  border: 1px solid #3e3e42;
  border-radius: 6px;
  overflow: hidden;
  background-color: #1e1e1e;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  margin-top: 10px;
  transition: opacity 0.3s;
}
.line-numbers {
  width: 40px;
  background-color: #1e1e1e;
  color: #858585;
  text-align: right;
  padding: 10px 8px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.6;
  user-select: none;
  border-right: 1px solid #333;
  overflow: hidden;
}
.code-textarea {
  flex: 1;
  background-color: transparent;
  color: #d4d4d4;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  padding: 10px 14px;
  border: none;
  resize: vertical;
  outline: none;
  white-space: pre;
  overflow-x: auto;
  min-height: 180px;
}
.code-textarea::placeholder {
  color: #6a6a6a;
  font-style: italic;
}
.code-editor-container:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary) inset, 0 4px 12px rgba(45, 125, 219, 0.1);
}
.code-textarea:disabled {
  cursor: not-allowed;
}

/* ======================================== */
/* 结果容器 */
/* ======================================== */
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
  border-color: var(--success);
  background: rgba(103, 194, 58, 0.08);
}
.result-box.wrong {
  border-color: var(--danger);
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
.result-verdict {
  font-size: 14px;
  color: var(--primary);
  margin-top: 4px;
  font-weight: 500;
}
.result-analysis {
  margin-top: 6px;
  padding: 8px 12px;
  background: var(--bgc-light);
  border-radius: 4px;
  font-size: 13px;
  color: var(--text-body);
}
.result-score {
  font-size: 14px;
  color: var(--primary);
  margin-top: 4px;
  font-weight: 500;
}

/* ======================================== */
/* 结果页样式 */
/* ======================================== */
.result-page .result-summary {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 0;
}
.result-cards {
  display: flex;
  gap: 30px;
  margin-bottom: 20px;
}
.result-card {
  text-align: center;
  padding: 10px 24px;
  background: var(--el-fill-color-light);
  border-radius: 10px;
  min-width: 70px;
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
.card-value.passed {
  color: var(--success);
}
.card-value.failed {
  color: var(--danger);
}
.progress-rings {
  display: flex;
  gap: 50px;
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
  color: var(--text-title, #303133);
}
.encouragement {
  text-align: center;
  padding: 16px 20px;
  margin: 10px 0;
  background: linear-gradient(135deg, rgba(45, 125, 219, 0.08), rgba(103, 194, 58, 0.08));
  border-radius: 12px;
  border: 1px solid var(--border-color);
}
.encourage-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 6px;
}
.wrong-note {
  font-size: 14px;
  color: var(--text-gray);
}
.wrong-review {
  margin-top: 14px;
  padding: 14px 18px;
  background: rgba(245, 108, 108, 0.06);
  border-radius: 10px;
  border: 1px solid rgba(245, 108, 108, 0.2);
}
.wrong-review h4 {
  color: var(--danger);
  margin-bottom: 10px;
}
.wrong-item {
  padding: 8px 0;
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
  color: var(--success);
  font-size: 14px;
}
.wrong-user-answer {
  color: var(--danger);
  font-size: 14px;
}

.bottom-actions {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  gap: 16px;
}

/* 评估报告样式 */
.assessment-report {
  margin-top: 16px;
  padding: 20px;
  background: var(--bg-card);
  border-radius: 12px;
  max-height: 600px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
}

.assessment-report h4 {
  margin: 0 0 12px;
  font-size: 16px;
  color: var(--primary);
  padding-bottom: 8px;
  border-bottom: 2px solid rgba(45, 125, 219, 0.15);
}

.assessment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--border-color);
}

.assessment-header h3 {
  margin: 0;
  font-size: 20px;
  color: var(--text-title);
  font-weight: 600;
}

/* 阶段概览 */
.assessment-summary {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-normal);
}

.summary-info {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 12px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-label {
  font-weight: 500;
  color: var(--text-gray);
}

.summary-value.score {
  font-size: 20px;
  font-weight: 700;
  color: var(--primary);
}

.summary-text {
  line-height: 1.8;
  color: var(--text-body);
  margin: 12px 0;
  padding: 12px;
  background: var(--bgc-light);
  border-radius: 6px;
}

.time-efficiency {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: var(--text-gray);
  padding-top: 10px;
  border-top: 1px dashed var(--border-color);
}

.efficiency-eval {
  color: var(--warning);
  font-weight: 500;
}

/* 知识点分析 */
.assessment-knowledge {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-normal);
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.knowledge-item {
  padding: 12px;
  border-radius: 6px;
  background: var(--bgc-light);
  border: 1px solid var(--border-color);
  transition: all 0.2s;
}

.knowledge-item.weak {
  background: rgba(245, 108, 108, 0.1);
  border-color: rgba(245, 108, 108, 0.3);
}

.knowledge-item:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.kp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.kp-name {
  font-weight: 500;
  color: var(--text-title);
}

.kp-mastery {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 6px;
}

.kp-comment {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.6;
  margin: 6px 0 0;
}

/* 薄弱点分析 */
.assessment-weak {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-normal);
}

.weak-item {
  padding: 12px;
  margin-bottom: 10px;
  background: rgba(230, 162, 60, 0.08);
  border-radius: 6px;
  border-left: 3px solid var(--warning);
}

.weak-item:last-child {
  margin-bottom: 0;
}

.weak-point {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: var(--text-title);
  font-weight: 500;
  margin-bottom: 8px;
}

.weak-point .el-icon {
  margin-top: 3px;
}

.weak-impact {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.6;
  padding-left: 24px;
}

/* 改进分析 */
.assessment-improvement {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-normal);
}

.assessment-improvement p {
  margin: 8px 0;
  line-height: 1.7;
  color: var(--text-body);
}

/* 准备度评估 */
.assessment-readiness {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-normal);
}

.assessment-readiness .readiness-status {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}


.readiness-gaps,
.readiness-suggestions {
  margin-top: 14px;
  padding: 12px;
  background: var(--bgc-light);
  border-radius: 6px;
}

.readiness-gaps ul,
.readiness-suggestions ul {
  margin: 8px 0 0;
  padding-left: 20px;
}

.readiness-gaps li,
.readiness-suggestions li {
  margin: 6px 0;
  line-height: 1.6;
  color: var(--text-body);
}

/* 调整建议 */
.assessment-adjustments {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-normal);
}

.remedy-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--danger);
  font-weight: 600;
  margin-bottom: 10px;
}

.remedy-list {
  margin: 0;
  padding-left: 24px;
}

.remedy-list li {
  margin: 6px 0;
  line-height: 1.6;
  color: var(--text-body);
}

.difficulty-adj {
  margin-top: 14px;
  padding: 12px;
  background: var(--bgc-light);
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.adj-reason {
  font-size: 13px;
  color: var(--text-gray);
  flex: 1;
  min-width: 200px;
}

.assessment-actions {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: center;
}

/* 动画 */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

:deep(.el-progress__text) {
  color: var(--bg-card);
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
  background: var(--bg-card);
  border-radius: 12px;
  padding: 24px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
  animation: slideUp 0.3s ease;
}

.conflict-dialog-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.conflict-dialog-header span {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title);
}

.conflict-dialog-content {
  margin-bottom: 24px;
}

.conflict-message {
  font-size: 15px;
  color: var(--text-body);
  line-height: 1.6;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bgc-light);
  border-radius: 8px;
  border-left: 4px solid var(--warning);
}

.weak-points-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.weak-point-item {
  padding: 16px;
  background: var(--bgc-light);
  border-radius: 10px;
  border: 1px solid var(--border-color);
}

.point-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.point-priority {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.priority-高 {
  background: rgba(245, 108, 108, 0.1);
  color: var(--danger);
}

.priority-中 {
  background: rgba(230, 162, 60, 0.1);
  color: var(--warning);
}

.priority-低 {
  background: rgba(103, 194, 58, 0.1);
  color: var(--success);
}

.point-title {
  font-weight: 600;
  color: var(--text-title);
  font-size: 14px;
}

.point-performance {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.6;
  margin-bottom: 6px;
}

.point-reason {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.6;
  padding-left: 12px;
  border-left: 2px solid var(--border-color);
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
  background: var(--bgc-light);
  color: var(--text-gray);
}

.conflict-btn-reject:hover {
  background: var(--bgc-mid);
  color: var(--text-title);
}

.conflict-btn-accept {
  background: var(--primary);
  color: #fff;
}

.conflict-btn-accept:hover {
  background: var(--primary);
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}

/* ===== 夜间模式适配 ===== */
.dark .assessment-header {
  border-bottom-color: var(--border-color);
}

.dark .summary-label,
.dark .summary-text,
.dark .time-efficiency,
.dark .kp-comment,
.dark .weak-impact,
.dark .readiness-gaps li,
.dark .readiness-suggestions li,
.dark .adj-reason {
  color: var(--text-gray);
}

.dark .summary-text,
.dark .readiness-gaps,
.dark .readiness-suggestions,
.dark .difficulty-adj {
  background: var(--bgc-light);
}

.dark .knowledge-item {
  background: var(--bgc-light);
  border-color: var(--border-color);
}

.dark .knowledge-item.weak {
  background: rgba(245, 108, 108, 0.1);
  border-color: rgba(245, 108, 108, 0.3);
}

.dark .weak-item {
  background: rgba(230, 162, 60, 0.1);
  border-left-color: #f59e0b;
}

.dark .assessment-improvement p {
  color: var(--text-body);
}

.dark .point-reason {
  border-left-color: var(--border-color);
}

/* ============================================================ */
/* 分享到学习路线市场弹窗样式 */
/* ============================================================ */
.share-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.25s ease-out;
}

.share-dialog {
  background: var(--bg-card);
  border-radius: 16px;
  width: 92%;
  max-width: 640px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255,255,255,0.05);
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}

/* Header */
.share-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.share-header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.share-header-icon {
  font-size: 28px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 2px;
}

.share-dialog-header h3 {
  margin: 0 0 4px;
  font-size: 17px;
  font-weight: 700;
  color: var(--text-title);
}

.share-header-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-gray);
}

.share-dialog-close {
  background: none;
  border: none;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 22px;
  cursor: pointer;
  color: var(--text-gray);
  transition: all 0.15s;
  flex-shrink: 0;
}

.share-dialog-close:hover {
  background: var(--bg-hover);
  color: var(--text-title);
}

/* Body */
.share-dialog-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

/* Loading */
.share-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 56px 0 48px;
  gap: 12px;
}

.share-spinner-ring {
  width: 44px;
  height: 44px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.share-loading-text {
  margin: 4px 0 0;
  color: var(--text-title);
  font-size: 15px;
  font-weight: 600;
}

.share-loading-hint {
  margin: 0;
  color: var(--text-gray);
  font-size: 13px;
}

/* Form sections */
.share-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.share-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.share-section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--primary-light, rgba(99, 102, 241, 0.15));
}

.share-form-row {
  display: flex;
  gap: 16px;
}

.share-form-row .share-form-item {
  flex: 1;
}

.share-form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}

.share-form-item label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-body);
}

.required {
  color: #ef4444;
}

.share-hint {
  font-weight: 400;
  color: var(--text-gray);
  font-size: 12px;
}

.share-char-count {
  position: absolute;
  right: 10px;
  top: 28px;
  font-size: 11px;
  color: var(--text-gray);
  pointer-events: none;
}

/* Inputs */
.share-input,
.share-textarea,
.share-select {
  width: 100%;
  padding: 10px 12px;
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-input);
  color: var(--text-body);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.share-input:focus,
.share-textarea:focus,
.share-select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.share-input::placeholder,
.share-textarea::placeholder {
  color: var(--text-gray);
  opacity: 0.7;
}

.share-textarea {
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
}

.share-select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%239ca3af' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}

.share-select option {
  background: var(--bg-card);
  color: var(--text-body);
}

/* Difficulty buttons */
.share-difficulty-group {
  display: flex;
  gap: 0;
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.share-diff-btn {
  flex: 1;
  padding: 9px 0;
  border: none;
  background: var(--bg-input);
  color: var(--text-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border-right: 1px solid var(--border-color);
}

.share-diff-btn:last-child {
  border-right: none;
}

.share-diff-btn:hover {
  background: var(--bg-hover);
}

.share-diff-btn.active {
  background: var(--primary);
  color: #fff;
  font-weight: 600;
}

/* Tags */
.share-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 8px 10px;
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-input);
  min-height: 42px;
  transition: border-color 0.2s, box-shadow 0.2s;
  cursor: text;
}

.share-tags:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.share-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px 3px 10px;
  background: var(--primary-light, rgba(99, 102, 241, 0.12));
  color: var(--primary);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  animation: fadeIn 0.15s ease-out;
}

.share-tag-remove {
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  opacity: 0.6;
  transition: opacity 0.15s;
  padding: 0 2px;
}

.share-tag-remove:hover {
  opacity: 1;
}

.share-tag-input {
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-body);
  font-size: 13px;
  flex: 1;
  min-width: 100px;
  padding: 2px 0;
}

/* Footer */
.share-dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
  background: var(--bg-card);
}

.share-btn-cancel {
  padding: 9px 20px;
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  background: transparent;
  color: var(--text-body);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.share-btn-cancel:hover {
  background: var(--bg-hover);
  border-color: var(--text-gray);
}

.share-btn-submit {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 24px;
  border: none;
  border-radius: 10px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
}

.share-btn-submit:hover:not(:disabled) {
  background: var(--primary-hv);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
  transform: translateY(-1px);
}

.share-btn-submit:active:not(:disabled) {
  transform: translateY(0);
}

.share-btn-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.share-btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

/* Dark mode */
.dark .share-dialog {
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.06);
}

.dark .share-tag {
  background: rgba(99, 102, 241, 0.2);
}

.dark .share-diff-btn {
  background: var(--bg-input);
}

.dark .share-diff-btn.active {
  background: var(--primary);
}

.dark .share-btn-submit {
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
}

.dark .share-btn-submit:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}
</style>
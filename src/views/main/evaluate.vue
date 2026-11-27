<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'
import {
  Check, Close, Refresh, Plus, Delete, ArrowLeft,
  Warning, CircleCheck, CircleClose, TrendCharts,
  Document, Reading, Clock, Calendar, DataAnalysis,
  User, Medal, Aim, List, Tickets, Minus
} from '@element-plus/icons-vue'
import emitter from '@/utils/emitter'
import {
  getReportApi,
  createReportApi,
  takeSugApi,
  sugListApi,
  noSugApi,
  reCreateDimApi
} from '@/api/mainApi/evaluate.js'

const router = useRouter()

// ===================================================================
// 一、数据定义区
// ===================================================================

/** 加载状态 */
const loading = ref(false)
const generating = ref(false)
const regenerating = ref(false)

/** 是否禁用滚动 */
const disableScroll = computed(() => loading.value || generating.value || regenerating.value)

/** 动画数字 */
const animatedScore = ref(0)
const animatedDimScores = ref([])
const animatedDashboardValues = reactive({
  score: 0,
  dimensions: 0,
  weakPoints: 0,
  knowledgePriority: 0,
  planReasonable: false
})

/** 用户ID */
const userId = ref(null)

/** 评估报告数据 */
const reportData = ref(null)

/** 已采纳的建议列表 */
const adoptedSuggestions = ref([])

/** ECharts 实例 */
const radarChartRef = ref(null)
let radarChartInstance = null

/** 主题状态 */
const themeStore = useThemeStore()

/** 采纳权重配置 */
const weightOptions = [
  { value: 0.25, label: '较不符合' },
  { value: 0.50, label: '部分符合' },
  { value: 0.75, label: '比较符合' },
  { value: 0.95, label: '非常符合' }
]

/** 当前选中的权重 */
const selectedWeight = ref(0.75)

/** 是否显示采纳面板 */
const showAdoptPanel = ref(false)

/** 当前要采纳的建议 */
const currentSuggestion = ref(null)

/** 建议类型映射 */
const suggestionTypeMap = {
  'knowledge_priority': '知识点优先级',
  'pace_advice': '学习节奏',
  'resource_adjustment': '资源调整',
  'difficulty_adjustment': '难度调整',
  'plan_optimization': '计划优化'
}

/** 评估状态映射 */
const statusMap = {
  '优秀': 'success',
  '良好': 'primary',
  '一般': 'warning',
  '需要干预': 'danger',
  '快速进步': 'success',
  '稳步提升': 'success',
  '遇到瓶颈': 'warning',
  'S': 'success',
  'A': 'success',
  'B': 'warning',
  'C': 'danger',
  'D': 'danger'
}

/** 排序后的薄弱点（按优先级） */
const sortedWeakPoints = computed(() => {
  if (!reportData.value?.weak_points) return []
  const order = { '高': 0, '中': 1, '低': 2 }
  return [...reportData.value.weak_points].sort(
    (a, b) => (order[a.priority] || 99) - (order[b.priority] || 99)
  )
})

// ===================================================================
// 二、工具方法区
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
 * 格式化日期
 */
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
 * 获取状态标签类型
 */
const getStatusType = (status) => {
  return statusMap[status] || 'info'
}

/**
 * 获取建议类型名称
 */
const getSuggestionTypeName = (type) => {
  return suggestionTypeMap[type] || type
}

/**
 * 获取分数对应的颜色
 */
const getScoreColor = (score) => {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  if (score >= 40) return '#F56C6C'
  return '#F56C6C'
}

/**
 * 数字滚动动画
 * 支持两种调用方式：
 * 1. animateNumber(ref, start, end) - 更新 ref
 * 2. animateNumber(obj, key, end) - 更新响应式对象的属性
 */
const animateNumber = (target, startOrKey, end, duration = 800) => {
  let targetRef = target
  let start = startOrKey
  let finalEnd = end
  
  if (typeof startOrKey === 'string') {
    const key = startOrKey
    start = target[key] || 0
    targetRef = {
      get value() { return target[key] },
      set value(v) { target[key] = v }
    }
  }
  
  const startTime = performance.now()
  const diff = finalEnd - start
  
  const update = (currentTime) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeOut = 1 - Math.pow(1 - progress, 3)
    targetRef.value = Math.round(start + diff * easeOut)
    
    if (progress < 1) {
      requestAnimationFrame(update)
    }
  }
  
  requestAnimationFrame(update)
}

/**
 * 更新动画数据
 */
const updateAnimations = () => {
  if (!reportData.value) return
  
  const score = reportData.value.overall_score !== undefined 
    ? reportData.value.overall_score 
    : (reportData.value.overall?.score || 0)
  
  animateNumber(animatedScore, animatedScore.value, score)
  
  const dims = reportData.value.dimensions || []
  const newDimScores = dims.map((d, i) => ({
    index: i,
    value: d.score || 0,
    animatedValue: ref(animatedDimScores.value[i]?.animatedValue?.value || animatedDimScores.value[i]?.animatedValue || 0)
  }))
  
  animatedDimScores.value = newDimScores
  newDimScores.forEach((d) => {
    animateNumber(d.animatedValue, d.animatedValue.value, d.value)
  })
  
  animateNumber(animatedDashboardValues, 'score', score)
  animateNumber(animatedDashboardValues, 'dimensions', dims.length)
  animateNumber(animatedDashboardValues, 'weakPoints', reportData.value.weak_points?.length || 0)
  animateNumber(animatedDashboardValues, 'knowledgePriority', (reportData.value.adjustments?.knowledge_priority || []).length)
  animatedDashboardValues.planReasonable = reportData.value.plan_optimization?.needs_adjustment
}

/**
 * 获取分数对应的等级
 */
const getScoreLevel = (score) => {
  if (score >= 80) return '优秀'
  if (score >= 60) return '良好'
  if (score >= 40) return '一般'
  return '需要改进'
}

/**
 * 获取趋势样式类
 */
const getTrendClass = (trend) => {
  if (trend === '上升') return 'trend-up'
  if (trend === '下降') return 'trend-down'
  return 'trend-stable'
}

/**
 * 检查某个知识点是否已被采纳
 */
const isKnowledgeAdopted = (knowledge) => {
  return adoptedSuggestions.value.some(
    sug => sug.type === 'knowledge_priority' && sug.content === knowledge
  )
}

// ===================================================================
// 三、API 请求方法区
// ===================================================================

/**
 * 1. 获取评估报告
 */
const fetchReport = async () => {
  if (!userId.value) return
  loading.value = true
  try {
    const res = await getReportApi(userId.value)
    if (res.code === 1 && res.data?.success) {
      reportData.value = res.data.assessment
      
      // 上报评估报告上下文给智能球
      const report = res.data.assessment
      if (report) {
        emitter.emit('contextDetail', {
          page: 'evaluate',
          title: '学习评估',
          action: 'viewing',
          detail: `报告ID: ${report.assessment_id || ''}, 状态: ${report.overall?.status || ''}, 分数: ${report.overall?.score || 0}`
        })
      }
      
      await nextTick()
      updateAnimations()
    } else {
      ElMessage.warning('暂无评估报告')
      reportData.value = null
    }
  } catch (err) {
    console.error('获取评估报告异常', err)
    ElMessage.error('获取评估报告失败')
  } finally {
    loading.value = false
  }
}

/**
 * 2. 生成新的评估报告
 */
const generateReport = async () => {
  if (!userId.value) return
  try {
    await ElMessageBox.confirm('生成新的评估报告将覆盖当前报告，确认继续？', '确认生成', {
      type: 'warning'
    })
    generating.value = true
    const res = await createReportApi(userId.value)
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('评估报告生成成功！')
      reportData.value = res.data.assessment
      
      // 上报新评估报告上下文给智能球
      const report = res.data.assessment
      if (report) {
        emitter.emit('contextDetail', {
          page: 'evaluate',
          title: '学习评估',
          action: 'evaluating',
          detail: `报告ID: ${report.assessment_id || ''}, 状态: ${report.overall?.status || ''}, 分数: ${report.overall?.score || 0}`
        })
      }
      
      await fetchAdoptedSuggestions()
      setTimeout(() => {
        renderCharts()
      }, 300)
    } else {
      ElMessage.error('生成报告失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('生成报告异常', err)
      ElMessage.error('生成报告失败，请重试')
    }
  } finally {
    generating.value = false
  }
}

/**
 * 3. 获取已采纳的建议
 */
const fetchAdoptedSuggestions = async () => {
  if (!userId.value) return
  try {
    const res = await sugListApi(userId.value)
    if (res.code === 1 && res.data?.success) {
      adoptedSuggestions.value = res.data.adopted_suggestions || []
    }
  } catch (err) {
    console.error('获取已采纳建议异常', err)
  }
}

/**
 * 4. 打开采纳面板
 */
const openAdoptPanel = (suggestion) => {
  currentSuggestion.value = suggestion
  selectedWeight.value = 0.75
  showAdoptPanel.value = true
}

/**
 * 5. 关闭采纳面板
 */
const closeAdoptPanel = () => {
  showAdoptPanel.value = false
  currentSuggestion.value = null
}

/**
 * 6. 确认采纳建议
 */
const confirmAdoptSuggestion = async () => {
  if (!userId.value || !currentSuggestion.value) return
  
  const suggestion = currentSuggestion.value
  const suggestionType = suggestion.suggestionType || suggestion.type
  
  try {
    const res = await takeSugApi(userId.value, {
      suggestionType: suggestionType,
      content: suggestion.content || suggestion.point,
      weight: selectedWeight.value
    })
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('建议采纳成功！')
      closeAdoptPanel()
      await fetchAdoptedSuggestions()
      await fetchReport()
    } else {
      ElMessage.error('采纳失败')
    }
  } catch (err) {
    console.error('采纳建议异常', err)
    ElMessage.error('采纳失败，请重试')
  }
}

/**
 * 7. 撤销采纳的建议
 */
const handleRevokeSuggestion = async (suggestion) => {
  try {
    await ElMessageBox.confirm('确定要撤销该建议吗？', '确认撤销', {
      type: 'warning'
    })
    const res = await noSugApi(userId.value, {
      suggestionType: suggestion.type,
      content: suggestion.content
    })
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('已撤销建议')
      await fetchAdoptedSuggestions()
      await fetchReport()
    } else {
      ElMessage.error('撤销失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('撤销建议异常', err)
      ElMessage.error('撤销失败，请重试')
    }
  }
}

/**
 * 8. 刷新数据
 */
const refreshData = async () => {
  await fetchReport()
  await fetchAdoptedSuggestions()
}

/**
 * 9. 重评指定部分
 */
const reRegeneratePart = async (partType, index) => {
  if (!userId.value || !reportData.value) return
  if (regenerating.value) return
  
  const confirmMsg = {
    'dimension': `确定要重新评估第 ${index + 1} 个维度「${reportData.value.dimensions[index]?.name || ''}」吗？`,
    'weak_point': `确定要重新识别第 ${index + 1} 个薄弱点「${reportData.value.weak_points[index]?.point || ''}」吗？`,
    'overall': '确定要重新评估总体等级吗？'
  }
  
  try {
    await ElMessageBox.confirm(confirmMsg[partType] || '确定要重新生成这部分吗？', '确认重评', {
      type: 'warning'
    })
    
    regenerating.value = true
    ElMessage.info('正在重新评估中，请稍候...')
    
    const res = await reCreateDimApi(userId.value, {
      assessment_id: reportData.value.assessment_id,
      part_type: partType,
      part_index: index
    })
    
    if (res.code === 1 && res.data?.success && res.data.assessment) {
      ElMessage.success(`已重新生成${getPartTypeName(partType)}`)
      reportData.value = res.data.assessment
      await nextTick()
      renderCharts()
      updateAnimations()
    } else {
      ElMessage.error('重新生成失败: ' + (res.data?.message || '未知错误'))
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('重评失败', err)
      ElMessage.error('重评失败，请重试')
    }
  } finally {
    regenerating.value = false
  }
}

/**
 * 获取重评部分名称
 */
const getPartTypeName = (type) => {
  const names = {
    'dimension': '维度评估',
    'weak_point': '薄弱点',
    'suggestion': '建议',
    'overall': '总体评估'
  }
  return names[type] || type
}

/**
 * 10. 渲染图表
 */
const renderCharts = () => {
  if (!reportData.value || !radarChartRef.value) return
  
  const dims = reportData.value.dimensions || []
  if (!dims.length) return
  
  if (radarChartInstance) {
    radarChartInstance.dispose()
  }
  
  radarChartInstance = echarts.init(radarChartRef.value)
  
  const labels = dims.map(d => d.name || '')
  const scores = dims.map(d => d.score || 0)
  
  const overallScore = reportData.value.overall_score !== undefined ? reportData.value.overall_score : (reportData.value.overall?.score || 0)
  const scoreColor = getScoreColor(overallScore)
  
  const getAreaColor = (color) => {
    if (color.startsWith('#')) {
      const r = parseInt(color.slice(1, 3), 16)
      const g = parseInt(color.slice(3, 5), 16)
      const b = parseInt(color.slice(5, 7), 16)
      return `rgba(${r}, ${g}, ${b}, 0.2)`
    }
    return 'rgba(45, 125, 219, 0.2)'
  }

  // 根据主题设置颜色
  const isDark = themeStore.isDark
  const textColor = isDark ? '#e2e8f0' : '#64748B'
  const axisColor = isDark ? '#475569' : '#E2E8F0'
  const splitLineColor = isDark ? '#475569' : '#E2E8F0'
  const splitAreaColors = isDark ? ['#1e293b', '#334155'] : ['#EFF6FF', '#F8FAFC']
  const tooltipBg = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
  
  radarChartInstance.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: labels.map(name => ({ name, max: 100 })),
      radius: '65%',
      axisName: {
        color: textColor,
        fontSize: 12
      },
      splitArea: {
        areaStyle: {
          color: splitAreaColors
        }
      },
      splitLine: {
        lineStyle: {
          color: splitLineColor
        }
      },
      axisLine: {
        lineStyle: {
          color: axisColor
        }
      }
    },
    series: [{
      type: 'radar',
      data: [{
        value: scores,
        name: '当前得分',
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: {
          color: scoreColor,
          width: 2
        },
        areaStyle: {
          color: getAreaColor(scoreColor)
        },
        itemStyle: {
          color: scoreColor
        }
      }]
    }],
    tooltip: {
      trigger: 'item',
      backgroundColor: tooltipBg,
      textStyle: {
        color: textColor
      },
      formatter: (params) => {
        const data = params.data
        return `<div style="padding:8px;">
          <div style="font-weight:600;margin-bottom:8px;">当前得分</div>
          ${labels.map((name, idx) => `
            <div>${name}: <strong>${data.value[idx]}</strong></div>
          `).join('')}
        </div>`
      }
    }
  })
}

/**
 * 11. 图表 resize
 */
const handleResize = () => {
  if (radarChartInstance) {
    radarChartInstance.resize()
  }
}

// ===================================================================
// 四、生命周期
// ===================================================================

onMounted(async () => {
  if (!getUserId()) {
    ElMessage.error('未检测到登录信息，请登录后使用')
    return
  }
  await refreshData()
  setTimeout(() => {
    renderCharts()
  }, 300)
  window.addEventListener('resize', handleResize)
})

watch(disableScroll, (newVal) => {
  if (newVal) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

// 监听主题变化，重新渲染图表
watch(() => themeStore.isDark, () => {
  nextTick(() => {
    renderCharts()
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (radarChartInstance) {
    radarChartInstance.dispose()
    radarChartInstance = null
  }
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="evaluate-container">
    <!-- ============================================================ -->
    <!-- 加载遮罩层 -->
    <!-- ============================================================ -->
    <div v-if="loading || generating || regenerating" class="loading-overlay">
      <div class="loading-content">
        <div class="loading-spinner"></div>
        <div class="loading-text">
          <span v-if="loading">正在加载评估数据</span>
          <span v-else-if="generating">正在生成评估报告</span>
          <span v-else-if="regenerating">正在重新评估</span>
          <span class="loading-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </span>
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 页面头部 - 标题居中 -->
    <!-- ============================================================ -->
    <div class="page-header">
      <h1>智评优化</h1>
      <p class="subtitle">全面分析学习效果，智能推荐优化建议</p>
      <!-- 只有有报告时才显示按钮 -->
      <div class="header-actions" v-if="reportData">
        <el-button type="primary" @click="generateReport" :loading="generating">
          <el-icon><Refresh /></el-icon>
          生成新报告
        </el-button>
        <el-button plain @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 主体内容 -->
    <!-- ============================================================ -->
    <div class="page-content" v-loading="loading" element-loading-text="加载中...">

      <!-- ========================================================== -->
      <!-- 无报告状态 -->
      <!-- ========================================================== -->
      <div v-if="!reportData" class="empty-state">
        <div class="empty-card">
          <div class="empty-icon">
            <el-icon :size="100" color="var(--pass)"><Medal /></el-icon>
          </div>
          <h3>暂无评估报告</h3>
          <p>点击「生成新报告」按钮，AI将为你生成学习效果评估</p>
          <el-button type="primary" size="large" @click="generateReport" :loading="generating">
            <el-icon><Refresh /></el-icon>
            生成评估报告
          </el-button>
        </div>
      </div>

      <!-- ========================================================== -->
      <!-- 有报告状态 -->
      <!-- ========================================================== -->
      <div v-else class="report-wrapper">
        <!-- ======================================================== -->
        <!-- 报告头部 - 整体概况 -->
        <!-- ======================================================== -->
        <div class="report-header">
          <div class="report-header-left">
            <div class="report-id">
              <span class="label">报告编号：</span>
              <span class="value">{{ reportData.assessment_id || '-' }}</span>
            </div>
            <div class="report-time">
              <span class="label">生成时间：</span>
              <span class="value">{{ formatDate(reportData.generated_at) }}</span>
            </div>
          </div>
          <div class="report-header-right">
            <el-tag :type="getStatusType(reportData.overall?.status)" size="large">
              {{ reportData.overall?.status || '未知' }}
            </el-tag>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 整体评分卡片 -->
        <!-- ======================================================== -->
        <div class="overview-card">
          <div class="overview-left">
            <div class="score-circle">
              <div class="score-number animate-number">{{ animatedScore }}</div>
              <div class="score-label">综合评分</div>
            </div>
            <div class="overview-info">
              <div class="overview-status-row">
                <h2>{{ reportData.overall_level || reportData.overall?.status || '未知' }}</h2>
                <el-button 
                  type="text" 
                  size="small" 
                  class="regen-btn-overview"
                  @click="reRegeneratePart('overall', null)"
                  title="重新评估总体等级"
                  :disabled="regenerating"
                >
                  <el-icon><Refresh /></el-icon>
                  重评
                </el-button>
              </div>
              <p class="summary">{{ reportData.overall_summary || reportData.overall?.summary || '' }}</p>
            </div>
          </div>
          <div class="overview-right">
            <div class="status-tag">
              <el-tag :type="getStatusType(reportData.overall_level || reportData.overall?.status)" size="large">
                {{ reportData.overall_level || reportData.overall?.status || '未知' }}
              </el-tag>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 评估数据可视化 -->
        <!-- ======================================================== -->
        <div class="visualization-section">
          <h3 class="section-title">
            <el-icon><DataAnalysis /></el-icon>
            评估数据可视化
          </h3>

          <!-- 学习状态仪表盘 -->
          <div class="dashboard-grid">
            <div class="dashboard-item animate-item">
              <div class="di-value" :style="{ color: getScoreColor(animatedDashboardValues.score) }">
                {{ animatedDashboardValues.score }}
              </div>
              <div class="di-label">综合评分</div>
            </div>
            <div class="dashboard-item animate-item">
              <div class="di-value" :style="{ color: 'var(--primary)' }">
                {{ animatedDashboardValues.dimensions }}
              </div>
              <div class="di-label">评估维度</div>
            </div>
            <div class="dashboard-item animate-item">
              <div class="di-value" :style="{ color: 'var(--main-delete)' }">
                {{ animatedDashboardValues.weakPoints }}
              </div>
              <div class="di-label">薄弱环节</div>
            </div>
            <div class="dashboard-item animate-item">
              <div class="di-value" :style="{ color: 'var(--coming)' }">
                {{ animatedDashboardValues.knowledgePriority }}
              </div>
              <div class="di-label">优先知识点</div>
            </div>
            <div class="dashboard-item animate-item">
              <div class="di-value" :style="{ color: animatedDashboardValues.planReasonable ? 'var(--main-delete)' : 'var(--pass)' }">
                <el-icon v-if="animatedDashboardValues.planReasonable"><Warning /></el-icon>
                <el-icon v-else><CircleCheck /></el-icon>
              </div>
              <div class="di-label">计划合理性</div>
            </div>
          </div>

          <!-- 雷达图 + 进度条 -->
          <div class="viz-container">
            <div class="viz-card">
              <div class="viz-title">能力雷达图</div>
              <div ref="radarChartRef" class="viz-chart"></div>
            </div>
            <div class="viz-card">
              <div class="viz-title">各维度得分</div>
              <div class="progress-bars">
                <div 
                  v-for="(dim, index) in reportData.dimensions" 
                  :key="index"
                  class="progress-bar-wrapper"
                >
                  <div class="progress-bar-label">
                    <span class="pb-name">{{ dim.name }}</span>
                    <span class="pb-score" :style="{ color: getScoreColor(dim.score) }">
                      {{ dim.score || 0 }} 分
                    </span>
                  </div>
                  <div class="progress-bar-track">
                    <div 
                      class="progress-bar-fill" 
                      :style="{ 
                        width: (dim.score || 0) + '%', 
                        background: getScoreColor(dim.score) 
                      }"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 薄弱点热力图 -->
          <div class="viz-card viz-card-full">
            <div class="viz-title">薄弱点优先级热力图</div>
            <div class="heatmap-container">
              <div 
                v-for="(point, index) in sortedWeakPoints" 
                :key="index"
                class="heatmap-item"
                :class="'priority-' + (point.priority || '中').toLowerCase()"
              >
                <span class="hm-point">{{ point.point }}</span>
                <div 
                  class="hm-bar" 
                  :class="'priority-' + (point.priority || '中').toLowerCase()"
                ></div>
                <span class="hm-priority">{{ point.priority || '中' }}优先级</span>
              </div>
              <div v-if="!reportData.weak_points?.length" class="empty-weak">
                暂无薄弱点
              </div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 维度评分网格 -->
        <!-- ======================================================== -->
        <div class="dimensions-section">
          <h3 class="section-title">
            <el-icon><DataAnalysis /></el-icon>
            各维度评估
          </h3>
          <div class="dimensions-grid">
            <div 
              v-for="(dim, index) in reportData.dimensions" 
              :key="index"
              class="dimension-card"
            >
              <div class="dimension-header">
                <span class="dimension-name">{{ dim.name }}</span>
                <div class="dimension-actions">
                  <span class="dimension-trend" :class="getTrendClass(dim.trend)">
                    {{ dim.trend || '稳定' }}
                    <el-icon v-if="dim.trend === '上升'"><TrendCharts /></el-icon>
                    <el-icon v-else-if="dim.trend === '下降'"><TrendCharts /></el-icon>
                    <el-icon v-else><Minus /></el-icon>
                  </span>
                  <el-button 
                    type="text" 
                    size="small" 
                    class="regen-btn"
                    @click="reRegeneratePart('dimension', index)"
                    title="重新评估此维度"
                    :disabled="regenerating"
                  >
                    <el-icon><Refresh /></el-icon>
                    重评
                  </el-button>
                </div>
              </div>
              <div class="dimension-score">
                <el-progress 
                  :percentage="animatedDimScores[index]?.animatedValue?.value || Math.round(dim.score)" 
                  :color="getScoreColor(dim.score)"
                  stroke-width="10"
                />
              </div>
              <div class="dimension-analysis">{{ dim.analysis || '' }}</div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 薄弱点分析 -->
        <!-- ======================================================== -->
        <div class="weak-points-section">
          <h3 class="section-title">
            <el-icon><Warning /></el-icon>
            薄弱点分析
          </h3>
          <div class="weak-points-list">
            <div 
              v-for="(point, index) in reportData.weak_points" 
              :key="index"
              class="weak-point-card"
              :class="'priority-' + (point.priority || '中').toLowerCase()"
            >
              <div class="weak-header">
                <span class="weak-point">{{ point.point }}</span>
                <div class="weak-actions">
                  <el-tag 
                    :type="point.priority === '高' ? 'danger' : point.priority === '中' ? 'warning' : 'info'"
                    size="small"
                  >
                    {{ point.priority || '中' }}优先级
                  </el-tag>
                  <el-button 
                    type="text" 
                    size="small" 
                    class="regen-btn"
                    @click="reRegeneratePart('weak_point', index)"
                    title="重新识别此薄弱点"
                    :disabled="regenerating"
                  >
                    <el-icon><Refresh /></el-icon>
                    重评
                  </el-button>
                </div>
              </div>
              <div class="weak-content">
                <div class="weak-performance">
                  <span class="label">表现：</span>
                  <span>{{ point.performance || '' }}</span>
                </div>
                <div class="weak-reason">
                  <span class="label">可能原因：</span>
                  <span>{{ point.possible_reason || '' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 学习调整建议（横向排版） -->
        <!-- ======================================================== -->
        <div class="adjustments-section">
          <h3 class="section-title">
            <el-icon><List /></el-icon>
            学习调整建议
          </h3>
          <div class="adjustments-grid">
            <!-- 资源调整 -->
            <div class="adjustment-card" v-if="reportData.adjustments?.resource_adjustment">
              <div class="adjustment-title">资源调整</div>
              <div class="adjustment-content">
                <div class="adjust-item">
                  <span class="adjust-label">增加：</span>
                  <div class="adjust-tags">
                    <el-tag 
                      v-for="(item, idx) in reportData.adjustments.resource_adjustment.increase" 
                      :key="idx"
                      size="small"
                      type="success"
                    >
                      {{ item }}
                    </el-tag>
                  </div>
                </div>
                <div class="adjust-item">
                  <span class="adjust-label">减少：</span>
                  <div class="adjust-tags">
                    <el-tag 
                      v-for="(item, idx) in reportData.adjustments.resource_adjustment.decrease" 
                      :key="idx"
                      size="small"
                      type="danger"
                    >
                      {{ item }}
                    </el-tag>
                  </div>
                </div>
                <div class="adjust-reason">
                  <span class="label">原因：</span>
                  <span>{{ reportData.adjustments.resource_adjustment.reason }}</span>
                </div>
              </div>
              <div class="adjust-actions">
                <el-button 
                  type="primary" 
                  size="small"
                  plain
                  @click="openAdoptPanel({
                    suggestionType: 'resource_adjustment',
                    content: JSON.stringify(reportData.adjustments.resource_adjustment?.reason || reportData.adjustments.resource_adjustment)
                  })"
                >
                  <el-icon><Plus /></el-icon>
                  采纳
                </el-button>
              </div>
            </div>

            <!-- 难度调整 -->
            <div class="adjustment-card" v-if="reportData.adjustments?.difficulty_adjustment">
              <div class="adjustment-title">难度调整</div>
              <div class="adjustment-content">
                <div class="adjust-item">
                  <span class="adjust-label">操作：</span>
                  <el-tag :type="reportData.adjustments.difficulty_adjustment.action === '调低' ? 'warning' : 'primary'">
                    {{ reportData.adjustments.difficulty_adjustment.action }}
                  </el-tag>
                </div>
                <div class="adjust-reason">
                  <span class="label">原因：</span>
                  <span>{{ reportData.adjustments.difficulty_adjustment.reason }}</span>
                </div>
              </div>
              <div class="adjust-actions">
                <el-button 
                  type="primary" 
                  size="small"
                  plain
                  @click="openAdoptPanel({
                    suggestionType: 'difficulty_adjustment',
                    content: reportData.adjustments.difficulty_adjustment.action + '：' + reportData.adjustments.difficulty_adjustment.reason
                  })"
                >
                  <el-icon><Plus /></el-icon>
                  采纳
                </el-button>
              </div>
            </div>

            <!-- 知识点优先级 - 每个知识点单独采纳 -->
            <div class="adjustment-card" v-if="reportData.adjustments?.knowledge_priority && reportData.adjustments.knowledge_priority.length > 0">
              <div class="adjustment-title">知识点优先级</div>
              <div class="adjustment-content">
                <div class="knowledge-priority-list">
                  <div 
                    v-for="(item, idx) in reportData.adjustments.knowledge_priority" 
                    :key="idx"
                    class="knowledge-priority-item"
                    :class="{ 'adopted': isKnowledgeAdopted(item) }"
                  >
                    <span class="knowledge-priority-name">
                      <span class="kp-index">{{ idx + 1 }}</span>
                      {{ item }}
                    </span>
                    <div class="knowledge-priority-actions">
                      <el-tag v-if="isKnowledgeAdopted(item)" size="small" type="success">
                        <el-icon><Check /></el-icon>
                        已采纳
                      </el-tag>
                      <el-button 
                        v-else
                        type="primary" 
                        size="small"
                        plain
                        @click="openAdoptPanel({
                          suggestionType: 'knowledge_priority',
                          content: item,
                          point: item
                        })"
                      >
                        <el-icon><Plus /></el-icon>
                        采纳
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 学习节奏 -->
            <div class="adjustment-card" v-if="reportData.adjustments?.pace_advice">
              <div class="adjustment-title">学习节奏</div>
              <div class="adjustment-content">
                <div class="adjust-item">
                  <span class="adjust-label">建议：</span>
                  <span>{{ reportData.adjustments.pace_advice }}</span>
                </div>
              </div>
              <div class="adjust-actions">
                <el-button 
                  type="primary" 
                  size="small"
                  plain
                  @click="openAdoptPanel({
                    suggestionType: 'pace_advice',
                    content: reportData.adjustments.pace_advice
                  })"
                >
                  <el-icon><Plus /></el-icon>
                  采纳
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 计划优化 -->
        <!-- ======================================================== -->
        <div class="plan-optimization-section" v-if="reportData.plan_optimization">
          <h3 class="section-title">
            <el-icon><Aim /></el-icon>
            计划优化建议
          </h3>
          <div class="plan-optimization-card">
            <div class="optimization-status">
              <span class="label">是否需要调整：</span>
              <el-tag :type="reportData.plan_optimization.needs_adjustment ? 'warning' : 'success'">
                {{ reportData.plan_optimization.needs_adjustment ? '需要调整' : '无需调整' }}
              </el-tag>
            </div>
            <div class="optimization-suggestions" v-if="reportData.plan_optimization.suggestions">
              <div class="suggestion-item" v-for="(sug, idx) in reportData.plan_optimization.suggestions" :key="idx">
                <span class="suggestion-num">{{ idx + 1 }}.</span>
                <span>{{ sug }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ======================================================== -->
        <!-- 已采纳建议 -->
        <!-- ======================================================== -->
        <div class="adopted-section" v-if="adoptedSuggestions.length > 0">
          <h3 class="section-title">
            <el-icon><CircleCheck /></el-icon>
            已采纳建议（{{ adoptedSuggestions.length }}条）
          </h3>
          <div class="adopted-list">
            <div 
              v-for="(sug, index) in adoptedSuggestions" 
              :key="index"
              class="adopted-item"
            >
              <div class="adopted-info">
                <el-tag size="small" :type="sug.type === 'pace_advice' ? 'warning' : 'primary'">
                  {{ getSuggestionTypeName(sug.type) }}
                </el-tag>
                <span class="adopted-content">{{ sug.content }}</span>
                <el-tag size="small" type="info">
                  权重：{{ (sug.weight * 100).toFixed(0) }}%
                </el-tag>
              </div>
              <el-button 
                type="danger" 
                size="small"
                plain
                @click="handleRevokeSuggestion(sug)"
              >
                <el-icon><Close /></el-icon>
                撤销
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 采纳建议面板（内联，不使用el-dialog） -->
    <!-- ============================================================ -->
    <div v-if="showAdoptPanel" class="adopt-panel-overlay" @click.self="closeAdoptPanel">
      <div class="adopt-panel">
        <div class="adopt-panel-header">
          <span class="adopt-panel-title">采纳建议</span>
          <el-button type="text" @click="closeAdoptPanel">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
        <div class="adopt-panel-body">
          <div class="adopt-suggestion-preview">
            <p class="adopt-label">建议内容：</p>
            <p class="adopt-content">{{ currentSuggestion?.content || currentSuggestion?.point || '' }}</p>
          </div>
          <div class="adopt-weight-section">
            <p class="adopt-label">请选择符合程度：</p>
            <div class="weight-options">
              <el-button 
                v-for="option in weightOptions" 
                :key="option.value"
                :type="selectedWeight === option.value ? 'primary' : 'default'"
                @click="selectedWeight = option.value"
                class="weight-btn"
              >
                {{ (option.value * 100).toFixed(0) }}% - {{ option.label }}
              </el-button>
            </div>
          </div>
        </div>
        <div class="adopt-panel-footer">
          <el-button @click="closeAdoptPanel">取消</el-button>
          <el-button type="primary" @click="confirmAdoptSuggestion">确认采纳</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =====================================================================
   样式说明：使用 CSS 变量（定义在 base.css 中）
   ===================================================================== */

.evaluate-container {
  width: 100%;
  min-width: 1384px;
  min-height: 85vh;
  background: transparent;
  padding: 20px;
}

/* -------------------- 页面头部 - 标题居中 -------------------- */
.page-header {
  text-align: center;
  margin-bottom: 20px;
}
.page-header h1 {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  font-family: "抖音美好体", "三极行楷简体-粗", sans-serif;
  color: var(--text-title);
}
.page-header .subtitle {
  font-size: 14px;
  color: var(--text-gray);
  margin-bottom: 16px;
}
.header-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}
.header-actions .el-button {
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
}
.header-actions .el-button--primary {
  background: var(--grad-primary);
  border-color: var(--primary);
}
.header-actions .el-button--primary:hover {
  background: var(--primary-hv);
  border-color: var(--primary-hv);
}
.header-actions .el-button--plain {
  border-color: var(--border-color);
  color: var(--text-body);
}
.header-actions .el-button--plain:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}

/* -------------------- 加载遮罩 z-index -------------------- */
.page-content {
  position: relative;
  min-width: 1384px;
}
.page-content :deep(.el-loading-mask) {
  z-index: 2 !important;
}

/* -------------------- 加载遮罩层 -------------------- */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(4px);
  z-index: 2;
  display: flex;
  justify-content: center;
  align-items: center;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 16px;
  color: var(--text-title);
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots .dot {
  width: 8px;
  height: 8px;
  background: var(--primary);
  border-radius: 50%;
  animation: dotBounce 1.4s infinite ease-in-out both;
}

.loading-dots .dot:nth-child(1) { animation-delay: -0.32s; }
.loading-dots .dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes dotBounce {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* -------------------- 空状态 -------------------- */
.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 500px;
}
.empty-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 48px 40px;
  text-align: center;
  box-shadow: var(--shadow-normal);
  max-width: 500px;
  width: 100%;
}
.empty-icon {
  margin-bottom: 20px;
  display: flex;
  justify-content: center;
}
.empty-card h3 {
  font-size: 24px;
  margin-bottom: 12px;
  color: var(--text-title);
}
.empty-card p {
  color: var(--text-gray);
  margin-bottom: 28px;
}

/* -------------------- 报告包装器 -------------------- */
.report-wrapper {
  max-width: 1200px;
  margin: 0 auto;
  animation: fadeIn 0.4s ease-out;
}

/* -------------------- 报告头部 -------------------- */
.report-header {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  box-shadow: var(--shadow-normal);
}
.report-header-left {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.report-header-left .label {
  color: var(--text-gray);
  font-size: 13px;
}
.report-header-left .value {
  color: var(--text-title);
  font-size: 13px;
  font-weight: 500;
}

/* -------------------- 整体评分卡片 -------------------- */
.overview-card {
  background: var(--grad-primary);
  border-radius: var(--radius-lg);
  padding: 28px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #ffffff;
  margin-bottom: 24px;
  box-shadow: var(--shadow-brand);
}
.overview-left {
  display: flex;
  align-items: center;
  gap: 24px;
}
.score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.score-number {
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
}
.score-label {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 4px;
}
.overview-info h2 {
  font-size: 22px;
  font-weight: 600;
  margin-bottom: 8px;
}
.overview-info .summary {
  opacity: 0.9;
  font-size: 14px;
  max-width: 800px;
  line-height: 1.6;
}

/* -------------------- 维度评分网格 -------------------- */
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 16px;
}
.section-title .el-icon {
  font-size: 20px;
  color: var(--primary);
}

.dimensions-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}
.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.dimension-card {
  background: var(--bgc-light);
  border-radius: var(--radius-md);
  padding: 16px 20px;
}
.dimension-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.dimension-name {
  font-size: 20px;
  font-weight: 500;
  color: var(--text-title);
}
.dimension-actions{
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}
.dimension-trend {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 2px;
}
.dimension-trend {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-page);
  font-weight: 500;
}
.dimension-trend.trend-up {
  color: var(--pass);
  background: var(--pass-bg-color);
}
.dimension-trend.trend-down {
  color: var(--main-delete);
  background: var(--main-fail-status);
}
.dimension-trend.trend-stable {
  color: var(--text-gray);
  background: var(--bgc-light);
}
.dimension-score {
  margin-bottom: 10px;
}
.dimension-analysis {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.5;
}

/* -------------------- 薄弱点分析 -------------------- */
.weak-points-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}
.weak-points-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.weak-point-card {
  border-radius: var(--radius-md);
  padding: 16px 20px;
  border-left: 4px solid var(--info);
  background: var(--bgc-light);
}
.weak-point-card.priority-high {
  border-left-color: var(--danger);
}
.weak-point-card.priority-middle {
  border-left-color: var(--warning);
}
.weak-point-card.priority-low {
  border-left-color: var(--info);
}
.weak-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}
.weak-point {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
}
.weak-actions{
  display: flex;
  align-items: center;
  gap: 8px;
}
.weak-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--text-body);
}
.weak-content .label {
  color: var(--text-gray);
  font-weight: 500;
}

/* -------------------- 学习调整建议（横向排版） -------------------- */
.adjustments-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}
.adjustments-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.adjustment-card {
  background: var(--bgc-light);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}
.adjustment-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}
.adjustment-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-body);
  flex: 1;
}
.adjust-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}
.adjust-label {
  color: var(--text-gray);
  font-weight: 500;
  flex-shrink: 0;
}
.adjust-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.adjust-reason {
  font-size: 13px;
  color: var(--text-gray);
}
.adjust-reason .label {
  color: var(--text-gray);
  font-weight: 500;
}
.adjust-actions {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
}
.adjust-actions .el-button {
  min-width: 80px;
  justify-content: center;
}

/* -------------------- 知识点优先级 - 每个单独采纳 -------------------- */
.knowledge-priority-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.knowledge-priority-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
}
.knowledge-priority-item:hover {
  border-color: var(--primary-light);
}
.knowledge-priority-item.adopted {
  border-color: var(--pass);
  background: var(--pass-bg-color);
}
.knowledge-priority-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-body);
}
.kp-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--primary);
  color: white;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.knowledge-priority-item.adopted .kp-index {
  background: var(--pass);
}
.knowledge-priority-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.knowledge-priority-actions .el-button {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

/* -------------------- 计划优化 -------------------- */
.plan-optimization-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}
.plan-optimization-card {
  background: var(--bgc-light);
  border-radius: var(--radius-md);
  padding: 16px 20px;
}
.optimization-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.optimization-status .label {
  font-size: 13px;
  color: var(--text-gray);
}
.optimization-suggestions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.suggestion-item {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.6;
}
.suggestion-num {
  color: var(--primary);
  font-weight: 600;
  margin-right: 4px;
}

/* -------------------- 已采纳建议 -------------------- */
.adopted-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}
.adopted-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.adopted-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--pass-bg-color);
  border-radius: var(--radius-md);
  border: 1px solid var(--pass);
  gap: 12px;
  flex-wrap: wrap;
}
.adopted-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  flex: 1;
}
.adopted-content {
  font-size: 13px;
  color: var(--text-body);
}

/* -------------------- 采纳面板（内联，不使用el-dialog） -------------------- */
.adopt-panel-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease-out;
}
.adopt-panel {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 520px;
  max-width: 92vw;
  max-height: 80vh;
  box-shadow: var(--shadow-heavy);
  display: flex;
  flex-direction: column;
}
.adopt-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
}
.adopt-panel-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title);
}
.adopt-panel-header .el-button {
  font-size: 20px;
  color: var(--text-gray);
  padding: 0;
}
.adopt-panel-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}
.adopt-suggestion-preview {
  margin-bottom: 20px;
}
.adopt-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title);
  margin-bottom: 6px;
}
.adopt-content {
  font-size: 14px;
  color: var(--text-body);
  background: var(--bgc-light);
  padding: 12px 16px;
  border-radius: var(--radius-md);
  line-height: 1.6;
  word-break: break-all;
}
.weight-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 8px;
}
.weight-btn {
  width: 100%;
  height: 44px;
  font-size: 13px;
  margin: 0 !important;
}
.weight-btn :deep(.el-button__text) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}
.adopt-panel-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
}

/* -------------------- 评估数据可视化 -------------------- */
.visualization-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}

/* 仪表盘 */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.dashboard-item {
  text-align: center;
  padding: 16px;
  border-radius: var(--radius-md);
  background: var(--bgc-light);
}
.dashboard-item .di-value {
  font-size: 28px;
  font-weight: 700;
}
.dashboard-item .di-label {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 4px;
}

/* 可视化容器 */
.viz-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.viz-card {
  padding: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: var(--bgc-light);
}
.viz-card-full {
  grid-column: 1 / -1;
}
.viz-card .viz-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 12px;
}
.viz-card .viz-chart {
  width: 100%;
  height: 220px;
}

/* 进度条 */
.progress-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.progress-bar-wrapper {
  margin-bottom: 0;
}
.progress-bar-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin-bottom: 4px;
}
.progress-bar-label .pb-name {
  color: var(--text-body);
}
.progress-bar-label .pb-score {
  font-weight: 600;
}
.progress-bar-track {
  height: 8px;
  background: var(--bg-page);
  border-radius: 4px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.8s ease;
}

/* 薄弱点热力图 */
.heatmap-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.heatmap-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
}
.heatmap-item.priority-high {
  background: var(--main-fail-status);
}
.heatmap-item.priority-middle,
.heatmap-item.priority-zhong {
  background: var(--pass-bg-color);
}
.heatmap-item.priority-low,
.heatmap-item.priority-di {
  background: var(--coming-bg-color);
}
.heatmap-item .hm-point {
  flex: 1;
  font-size: 13px;
  color: var(--text-body);
}
.heatmap-item.priority-high .hm-point {
  color: var(--main-delete);
}
.heatmap-item.priority-middle .hm-point,
.heatmap-item.priority-zhong .hm-point {
  color: var(--pass);
}
.heatmap-item.priority-low .hm-point,
.heatmap-item.priority-di .hm-point {
  color: var(--coming);
}
.heatmap-item .hm-bar {
  flex: 2;
  height: 20px;
  border-radius: 4px;
  min-width: 60px;
  transition: all 0.8s ease-out;
}
.heatmap-item.priority-high .hm-bar {
  background: var(--main-delete);
  width: 90%;
  opacity: 0.7;
}
.heatmap-item.priority-middle .hm-bar,
.heatmap-item.priority-zhong .hm-bar {
  background: var(--pass);
  width: 60%;
  opacity: 0.7;
}
.heatmap-item.priority-low .hm-bar,
.heatmap-item.priority-di .hm-bar {
  background: var(--coming);
  width: 30%;
  opacity: 0.7;
}
.heatmap-item .hm-priority {
  font-size: 11px;
  white-space: nowrap;
}
.heatmap-item.priority-high .hm-priority {
  color: var(--main-delete);
}
.heatmap-item.priority-middle .hm-priority,
.heatmap-item.priority-zhong .hm-priority {
  color: var(--pass);
}
.heatmap-item.priority-low .hm-priority,
.heatmap-item.priority-di .hm-priority {
  color: var(--coming);
}
.empty-weak {
  color: var(--text-gray);
  font-size: 13px;
  text-align: center;
  padding: 12px;
}

/* 重评按钮 */
.regen-btn {
  color: var(--primary);
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid var(--primary-light);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  transition: all 0.2s ease;
  cursor: pointer;
}
.regen-btn:hover {
  color: #fff;
  background: var(--primary);
  border-color: var(--primary);
}
.regen-btn:disabled {
  color: var(--text-gray);
  border-color: var(--border-color);
  background: var(--bgc-light);
  cursor: not-allowed;
  opacity: 0.6;
}
.regen-btn-overview {
  color: rgba(255, 255, 255, 0.9);
  padding: 6px 14px;
  font-size: 13px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: var(--radius-sm);
  margin-left: 12px;
  background: rgba(255, 255, 255, 0.1);
  transition: all 0.2s ease;
  cursor: pointer;
}
.regen-btn-overview:hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.5);
}
.regen-btn-overview:disabled {
  color: rgba(255, 255, 255, 0.4);
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  cursor: not-allowed;
  opacity: 0.6;
}

/* 整体状态行 */
.overview-status-row {
  display: flex;
}

/* -------------------- 数据变化动画 -------------------- */
.animate-number {
  transition: color 0.5s ease;
}

.animate-item {
  animation: scaleIn 0.5s ease-out;
}

@keyframes scaleIn {
  0% {
    transform: scale(0.9);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.dimension-card {
  transition: all 0.3s ease;
}

.dimension-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-normal);
}

.weak-point-card {
  transition: all 0.3s ease;
}

.weak-point-card:hover {
  transform: translateX(4px);
}

/* -------------------- 动画 -------------------- */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* -------------------- 响应式适配 -------------------- */
/* @media (max-width: 768px) {
  .evaluate-container {
    min-width: unset;
  }
  .report-header {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }
  .report-header-left {
    flex-direction: column;
    gap: 4px;
  }
  .overview-card {
    flex-direction: column;
    text-align: center;
    gap: 16px;
  }
  .overview-left {
    flex-direction: column;
  }
  .overview-info .summary {
    max-width: 100%;
  }
  .overview-status-row {
    justify-content: center;
  }
  .dimensions-grid {
    grid-template-columns: 1fr;
  }
  .adjustments-grid {
    grid-template-columns: 1fr;
  }
  .adopted-item {
    flex-direction: column;
    align-items: stretch;
  }
  .weight-options {
    grid-template-columns: 1fr 1fr;
  }
  .adopt-panel {
    width: 95vw;
  }
  .adjust-actions {
    justify-content: center;
  }
  .adjust-actions .el-button {
    width: 100%;
  }
  .knowledge-priority-item {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  .knowledge-priority-actions {
    justify-content: flex-end;
  }
  .viz-container {
    grid-template-columns: 1fr;
  }
  .dashboard-grid {
    grid-template-columns: repeat(2, 1fr);
  }
} */

/* ============ 夜间模式适配 ============ */

/* Element Plus v-loading 遮罩层 */
.dark .page-content :deep(.el-loading-mask) {
  background: rgba(15, 23, 42, 0.9) !important;
}

.dark .page-content :deep(.el-loading-text) {
  color: var(--text-body) !important;
}

/* 自定义加载遮罩层 */
.dark .loading-overlay {
  background: rgba(15, 23, 42, 0.9);
}

.dark .loading-text {
  color: var(--text-body);
}

</style>
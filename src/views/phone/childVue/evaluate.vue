<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  showToast, showSuccessToast, showFailToast,
  showConfirmDialog, showLoadingToast
} from 'vant'
import * as echarts from 'echarts'
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
// 数据定义
// ===================================================================

const loading = ref(false)
const generating = ref(false)
const regenerating = ref(false)
const userId = ref(null)
const reportData = ref(null)
const adoptedSuggestions = ref([])

const animatedScore = ref(0)
const animatedDimScores = ref([])
const animatedDashboardValues = reactive({
  score: 0,
  dimensions: 0,
  weakPoints: 0,
  knowledgePriority: 0
})

const radarChartRef = ref(null)
let radarChartInstance = null

const weightOptions = [
  { value: 0.25, label: '较不符合' },
  { value: 0.50, label: '部分符合' },
  { value: 0.75, label: '比较符合' },
  { value: 0.95, label: '非常符合' }
]
const selectedWeight = ref(0.75)
const showAdoptPanel = ref(false)
const currentSuggestion = ref(null)

const suggestionTypeMap = {
  'knowledge_priority': '知识点优先级',
  'pace_advice': '学习节奏',
  'resource_adjustment': '资源调整',
  'difficulty_adjustment': '难度调整',
  'plan_optimization': '计划优化'
}

const statusMap = {
  '优秀': 'success', '良好': 'primary', '一般': 'warning', '需要干预': 'danger',
  '快速进步': 'success', '稳步提升': 'success', '遇到瓶颈': 'warning',
  'S': 'success', 'A': 'success', 'B': 'warning', 'C': 'danger', 'D': 'danger'
}

const sortedWeakPoints = computed(() => {
  if (!reportData.value?.weak_points) return []
  const order = { '高': 0, '中': 1, '低': 2 }
  return [...reportData.value.weak_points].sort(
    (a, b) => (order[a.priority] || 99) - (order[b.priority] || 99)
  )
})

// ===================================================================
// 工具方法
// ===================================================================

const getUserId = () => {
  const userStr = localStorage.getItem('loginUser')
  if (!userStr) return false
  try {
    const loginUser = JSON.parse(userStr)
    if (loginUser?.id) {
      userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
      return true
    }
  } catch (err) {
    console.error('解析登录用户失败', err)
  }
  return false
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

const getScoreColor = (score) => {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
}

const getScoreLevel = (score) => {
  if (score >= 80) return '优秀'
  if (score >= 60) return '良好'
  if (score >= 40) return '一般'
  return '需要改进'
}

const getTrendClass = (trend) => {
  if (trend === '上升') return 'trend-up'
  if (trend === '下降') return 'trend-down'
  return 'trend-stable'
}

const getSuggestionTypeName = (type) => suggestionTypeMap[type] || type

const getStatusType = (status) => statusMap[status] || 'primary'

const isKnowledgeAdopted = (knowledge) => {
  return adoptedSuggestions.value.some(
    sug => sug.type === 'knowledge_priority' && sug.content === knowledge
  )
}

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
    if (progress < 1) requestAnimationFrame(update)
  }
  requestAnimationFrame(update)
}

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
}

// ===================================================================
// API 请求
// ===================================================================

const fetchReport = async () => {
  if (!userId.value) return
  loading.value = true
  try {
    const res = await getReportApi(userId.value)
    if (res.code === 1 && res.data?.success) {
      reportData.value = res.data.assessment
      await nextTick()
      updateAnimations()
    } else {
      reportData.value = null
    }
  } catch (err) {
    console.error('获取评估报告异常', err)
    showFailToast('获取评估报告失败')
  } finally {
    loading.value = false
  }
}

const generateReport = async () => {
  if (!userId.value) return
  try {
    await showConfirmDialog({
      title: '确认生成',
      message: '生成新的评估报告将覆盖当前报告，确认继续？'
    })
    generating.value = true
    showLoadingToast({ message: '正在生成...', forbidClick: true, duration: 0 })
    const res = await createReportApi(userId.value)
    if (res.code === 1 && res.data?.success) {
      showSuccessToast('评估报告生成成功！')
      reportData.value = res.data.assessment
      await fetchAdoptedSuggestions()
      setTimeout(() => renderCharts(), 300)
    } else {
      showFailToast('生成报告失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('生成报告异常', err)
      showFailToast('生成报告失败')
    }
  } finally {
    generating.value = false
  }
}

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

const openAdoptPanel = (suggestion) => {
  currentSuggestion.value = suggestion
  selectedWeight.value = 0.75
  showAdoptPanel.value = true
}

const closeAdoptPanel = () => {
  showAdoptPanel.value = false
  currentSuggestion.value = null
}

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
      showSuccessToast('建议采纳成功！')
      closeAdoptPanel()
      await fetchAdoptedSuggestions()
      await fetchReport()
    } else {
      showFailToast('采纳失败')
    }
  } catch (err) {
    console.error('采纳建议异常', err)
    showFailToast('采纳失败')
  }
}

const handleRevokeSuggestion = async (suggestion) => {
  try {
    await showConfirmDialog({
      title: '确认撤销',
      message: '确定要撤销该建议吗？'
    })
    const res = await noSugApi(userId.value, {
      suggestionType: suggestion.type,
      content: suggestion.content
    })
    if (res.code === 1 && res.data?.success) {
      showSuccessToast('已撤销建议')
      await fetchAdoptedSuggestions()
      await fetchReport()
    } else {
      showFailToast('撤销失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      showFailToast('撤销失败')
    }
  }
}

const refreshData = async () => {
  showLoadingToast({ message: '刷新中...', forbidClick: true, duration: 0 })
  await fetchReport()
  await fetchAdoptedSuggestions()
  showToast('刷新完成')
}

const reRegeneratePart = async (partType, index) => {
  if (!userId.value || !reportData.value || regenerating.value) return
  const partNames = { dimension: '维度评估', weak_point: '薄弱点', overall: '总体评估' }
  try {
    await showConfirmDialog({
      title: '确认重评',
      message: `确定要重新评估「${partNames[partType] || partType}」吗？`
    })
    regenerating.value = true
    showLoadingToast({ message: '正在重新评估...', forbidClick: true, duration: 0 })
    const res = await reCreateDimApi(userId.value, {
      assessment_id: reportData.value.assessment_id,
      part_type: partType,
      part_index: index
    })
    if (res.code === 1 && res.data?.success && res.data.assessment) {
      showSuccessToast('重新评估成功')
      reportData.value = res.data.assessment
      await nextTick()
      renderCharts()
      updateAnimations()
    } else {
      showFailToast('重新生成失败')
    }
  } catch (err) {
    if (err !== 'cancel') showFailToast('重评失败')
  } finally {
    regenerating.value = false
  }
}

// ===================================================================
// 图表
// ===================================================================

const renderCharts = () => {
  if (!reportData.value || !radarChartRef.value) return
  const dims = reportData.value.dimensions || []
  if (!dims.length) return
  if (radarChartInstance) radarChartInstance.dispose()
  radarChartInstance = echarts.init(radarChartRef.value)
  const labels = dims.map(d => d.name || '')
  const scores = dims.map(d => d.score || 0)
  const overallScore = reportData.value.overall_score !== undefined
    ? reportData.value.overall_score
    : (reportData.value.overall?.score || 0)
  const scoreColor = getScoreColor(overallScore)
  const r = parseInt(scoreColor.slice(1, 3), 16)
  const g = parseInt(scoreColor.slice(3, 5), 16)
  const b = parseInt(scoreColor.slice(5, 7), 16)
  radarChartInstance.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: labels.map(name => ({ name, max: 100 })),
      radius: '60%',
      axisName: { color: '#64748B', fontSize: 11 },
      splitArea: { areaStyle: { color: ['#EFF6FF', '#F8FAFC'] } },
      splitLine: { lineStyle: { color: '#E2E8F0' } },
      axisLine: { lineStyle: { color: '#E2E8F0' } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: scores,
        name: '当前得分',
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: scoreColor, width: 2 },
        areaStyle: { color: `rgba(${r}, ${g}, ${b}, 0.2)` },
        itemStyle: { color: scoreColor }
      }]
    }],
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const data = params.data
        return `<div style="padding:6px;font-size:12px;">
          <div style="font-weight:600;margin-bottom:4px;">当前得分</div>
          ${labels.map((name, idx) => `<div>${name}: <strong>${data.value[idx]}</strong></div>`).join('')}
        </div>`
      }
    }
  })
}

const handleResize = () => {
  if (radarChartInstance) radarChartInstance.resize()
}

// ===================================================================
// 导航
// ===================================================================

const handleBack = () => {
  router.back()
}

// ===================================================================
// 生命周期
// ===================================================================

onMounted(async () => {
  if (!getUserId()) {
    showFailToast('未检测到登录信息')
    return
  }
  await fetchReport()
  await fetchAdoptedSuggestions()
  setTimeout(() => renderCharts(), 300)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (radarChartInstance) {
    radarChartInstance.dispose()
    radarChartInstance = null
  }
})
</script>

<template>
  <div class="phone-evaluate">
    <!-- 顶部导航 -->
    <div class="page-header-bar">
      <van-icon name="arrow-left" size="20" @click="handleBack" />
      <span class="header-title">智评优化</span>
      <div class="header-right" v-if="reportData">
        <van-icon name="replay" size="18" @click="generateReport" />
      </div>
    </div>

    <!-- 加载遮罩 -->
    <div v-if="loading || generating || regenerating" class="loading-overlay">
      <van-loading type="spinner" size="36" color="var(--primary)" />
      <span class="loading-text">
        {{ loading ? '正在加载...' : generating ? '正在生成报告...' : '正在重新评估...' }}
      </span>
    </div>

    <!-- 主内容 -->
    <div class="page-content">
      <!-- 无报告 -->
      <div v-if="!reportData && !loading" class="empty-state">
        <van-icon name="medal-o" size="64" color="var(--primary)" />
        <h3>暂无评估报告</h3>
        <p>点击下方按钮，AI将为你生成学习效果评估</p>
        <van-button type="primary" round @click="generateReport" :loading="generating">
          生成评估报告
        </van-button>
      </div>

      <!-- 有报告 -->
      <div v-else-if="reportData" class="report-wrapper">
        <!-- 报告编号 & 时间 -->
        <div class="report-meta">
          <div class="meta-row">
            <span class="meta-label">报告编号</span>
            <span class="meta-value">{{ reportData.assessment_id || '-' }}</span>
          </div>
          <div class="meta-row">
            <span class="meta-label">生成时间</span>
            <span class="meta-value">{{ formatDate(reportData.generated_at) }}</span>
          </div>
          <div class="meta-status" :class="'status-' + (getStatusType(reportData.overall?.status))">
            {{ reportData.overall?.status || '未知' }}
          </div>
        </div>

        <!-- 综合评分卡片 -->
        <div class="score-card">
          <div class="score-circle">
            <div class="score-number">{{ animatedScore }}</div>
            <div class="score-label">综合评分</div>
          </div>
          <div class="score-info">
            <div class="score-level-row">
              <h2>{{ reportData.overall_level || reportData.overall?.status || '未知' }}</h2>
              <div class="regen-btn-white" @click="reRegeneratePart('overall', null)">
                重评
              </div>
            </div>
            <p class="score-summary">{{ reportData.overall_summary || reportData.overall?.summary || '' }}</p>
          </div>
        </div>

        <!-- 数据仪表盘 -->
        <div class="dashboard-grid">
          <div class="dash-item">
            <div class="dash-value" :style="{ color: getScoreColor(animatedDashboardValues.score) }">
              {{ animatedDashboardValues.score }}
            </div>
            <div class="dash-label">综合评分</div>
          </div>
          <div class="dash-item">
            <div class="dash-value" style="color: var(--primary)">{{ animatedDashboardValues.dimensions }}</div>
            <div class="dash-label">评估维度</div>
          </div>
          <div class="dash-item">
            <div class="dash-value" style="color: #F56C6C">{{ animatedDashboardValues.weakPoints }}</div>
            <div class="dash-label">薄弱环节</div>
          </div>
          <div class="dash-item">
            <div class="dash-value" style="color: #E6A23C">{{ animatedDashboardValues.knowledgePriority }}</div>
            <div class="dash-label">优先知识点</div>
          </div>
        </div>

        <!-- 雷达图 -->
        <div class="section-card">
          <div class="section-title">能力雷达图</div>
          <div ref="radarChartRef" class="radar-chart"></div>
        </div>

        <!-- 各维度得分 -->
        <div class="section-card">
          <div class="section-title">各维度得分</div>
          <div class="dim-bars">
            <div v-for="(dim, index) in reportData.dimensions" :key="index" class="dim-bar-item">
              <div class="dim-bar-label">
                <span>{{ dim.name }}</span>
                <span :style="{ color: getScoreColor(dim.score) }">{{ dim.score || 0 }}分</span>
              </div>
              <div class="dim-bar-track">
                <div class="dim-bar-fill" :style="{ width: (dim.score || 0) + '%', background: getScoreColor(dim.score) }"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 各维度评估 -->
        <div class="section-card">
          <div class="section-title">各维度评估</div>
          <div class="dim-cards">
            <div v-for="(dim, index) in reportData.dimensions" :key="index" class="dim-eval-card">
              <div class="dim-eval-header">
                <span class="dim-eval-name">{{ dim.name }}</span>
                <span class="dim-trend" :class="getTrendClass(dim.trend)">{{ dim.trend || '稳定' }}</span>
              </div>
              <div class="dim-eval-analysis">{{ dim.analysis || '' }}</div>
              <div class="btn-right">
                <van-button size="mini" plain round class="regen-btn" @click="reRegeneratePart('dimension', index)" :disabled="regenerating">
                  重新评估
                </van-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 薄弱点分析 -->
        <div class="section-card">
          <div class="section-title">薄弱点分析</div>
          <div class="weak-list">
            <div
              v-for="(point, index) in reportData.weak_points"
              :key="index"
              class="weak-card"
              :class="'priority-' + (point.priority || '中').toLowerCase()"
            >
              <div class="weak-header">
                <span class="weak-point">{{ point.point }}</span>
                <van-tag :type="point.priority === '高' ? 'danger' : point.priority === '中' ? 'warning' : 'primary'" size="medium">
                  {{ point.priority || '中' }}优先级
                </van-tag>
              </div>
              <div class="weak-detail">
                <div><span class="weak-label">表现：</span>{{ point.performance || '' }}</div>
                <div><span class="weak-label">原因：</span>{{ point.possible_reason || '' }}</div>
              </div>
              <div class="btn-right">
                <van-button size="mini" plain round class="regen-btn" @click="reRegeneratePart('weak_point', index)" :disabled="regenerating">
                  重新评估
                </van-button>
              </div>
            </div>
            <div v-if="!reportData.weak_points?.length" class="empty-text">暂无薄弱点</div>
          </div>
        </div>

        <!-- 薄弱点优先级热力图 -->
        <div class="section-card" v-if="sortedWeakPoints.length">
          <div class="section-title">薄弱点优先级</div>
          <div class="heatmap-list">
            <div
              v-for="(point, index) in sortedWeakPoints"
              :key="index"
              class="heatmap-item"
              :class="'priority-' + (point.priority || '中').toLowerCase()"
            >
              <span class="hm-name">{{ point.point }}</span>
              <div class="hm-bar" :class="'priority-' + (point.priority || '中').toLowerCase()"></div>
              <span class="hm-priority">{{ point.priority || '中' }}</span>
            </div>
          </div>
        </div>

        <!-- 学习调整建议 -->
        <div class="section-card">
          <div class="section-title">学习调整建议</div>

          <!-- 资源调整 -->
          <div v-if="reportData.adjustments?.resource_adjustment" class="adjust-card">
            <div class="adjust-title">资源调整</div>
            <div class="adjust-body">
              <div class="adjust-row" v-if="reportData.adjustments.resource_adjustment.increase?.length">
                <span class="adjust-label">增加：</span>
                <div class="tag-wrap">
                  <van-tag type="success" v-for="(item, idx) in reportData.adjustments.resource_adjustment.increase" :key="idx">{{ item }}</van-tag>
                </div>
              </div>
              <div class="adjust-row" v-if="reportData.adjustments.resource_adjustment.decrease?.length">
                <span class="adjust-label">减少：</span>
                <div class="tag-wrap">
                  <van-tag type="danger" v-for="(item, idx) in reportData.adjustments.resource_adjustment.decrease" :key="idx">{{ item }}</van-tag>
                </div>
              </div>
              <div class="adjust-reason" v-if="reportData.adjustments.resource_adjustment.reason">
                <span class="adjust-label">原因：</span>{{ reportData.adjustments.resource_adjustment.reason }}
              </div>
            </div>
            <van-button size="small" type="primary" plain round block @click="openAdoptPanel({
              suggestionType: 'resource_adjustment',
              content: JSON.stringify(reportData.adjustments.resource_adjustment?.reason || reportData.adjustments.resource_adjustment)
            })">采纳建议</van-button>
          </div>

          <!-- 难度调整 -->
          <div v-if="reportData.adjustments?.difficulty_adjustment" class="adjust-card">
            <div class="adjust-title">难度调整</div>
            <div class="adjust-body">
              <div class="adjust-row">
                <span class="adjust-label">操作：</span>
                <van-tag :type="reportData.adjustments.difficulty_adjustment.action === '调低' ? 'warning' : 'primary'">
                  {{ reportData.adjustments.difficulty_adjustment.action }}
                </van-tag>
              </div>
              <div class="adjust-reason" v-if="reportData.adjustments.difficulty_adjustment.reason">
                <span class="adjust-label">原因：</span>{{ reportData.adjustments.difficulty_adjustment.reason }}
              </div>
            </div>
            <van-button size="small" type="primary" plain round block @click="openAdoptPanel({
              suggestionType: 'difficulty_adjustment',
              content: reportData.adjustments.difficulty_adjustment.action + '：' + reportData.adjustments.difficulty_adjustment.reason
            })">采纳建议</van-button>
          </div>

          <!-- 知识点优先级 -->
          <div v-if="reportData.adjustments?.knowledge_priority?.length" class="adjust-card">
            <div class="adjust-title">知识点优先级</div>
            <div class="adjust-body">
              <div
                v-for="(item, idx) in reportData.adjustments.knowledge_priority"
                :key="idx"
                class="kp-item"
                :class="{ adopted: isKnowledgeAdopted(item) }"
              >
                <div class="kp-info">
                  <span class="kp-index">{{ idx + 1 }}</span>
                  <span>{{ item }}</span>
                </div>
                <div class="kp-actions">
                  <van-tag v-if="isKnowledgeAdopted(item)" type="success" size="medium">已采纳</van-tag>
                  <van-button v-else size="mini" type="primary" plain round @click="openAdoptPanel({
                    suggestionType: 'knowledge_priority', content: item, point: item
                  })">采纳</van-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 学习节奏 -->
          <div v-if="reportData.adjustments?.pace_advice" class="adjust-card">
            <div class="adjust-title">学习节奏</div>
            <div class="adjust-body">
              <div class="adjust-reason">{{ reportData.adjustments.pace_advice }}</div>
            </div>
            <van-button size="small" type="primary" plain round block @click="openAdoptPanel({
              suggestionType: 'pace_advice', content: reportData.adjustments.pace_advice
            })">采纳建议</van-button>
          </div>
        </div>

        <!-- 计划优化 -->
        <div class="section-card" v-if="reportData.plan_optimization">
          <div class="section-title">计划优化建议</div>
          <div class="plan-card">
            <div class="plan-status">
              <span>是否需要调整：</span>
              <van-tag :type="reportData.plan_optimization.needs_adjustment ? 'warning' : 'success'">
                {{ reportData.plan_optimization.needs_adjustment ? '需要调整' : '无需调整' }}
              </van-tag>
            </div>
            <div class="plan-suggestions" v-if="reportData.plan_optimization.suggestions">
              <div v-for="(sug, idx) in reportData.plan_optimization.suggestions" :key="idx" class="plan-sug-item">
                <span class="sug-num">{{ idx + 1 }}.</span>
                <span>{{ sug }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 已采纳建议 -->
        <div class="section-card" v-if="adoptedSuggestions.length > 0">
          <div class="section-title">已采纳建议（{{ adoptedSuggestions.length }}条）</div>
          <div class="adopted-list">
            <div v-for="(sug, index) in adoptedSuggestions" :key="index" class="adopted-item">
              <div class="adopted-info">
                <van-tag size="medium" :type="sug.type === 'pace_advice' ? 'warning' : 'primary'">
                  {{ getSuggestionTypeName(sug.type) }}
                </van-tag>
                <span class="adopted-content">{{ sug.content }}</span>
                <van-tag size="medium" plain>权重 {{ (sug.weight * 100).toFixed(0) }}%</van-tag>
              </div>
              <van-button size="small" type="danger" plain round @click="handleRevokeSuggestion(sug)">撤销</van-button>
            </div>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="bottom-actions">
          <van-button type="primary" round block @click="generateReport" :loading="generating">
            生成新报告
          </van-button>
          <van-button plain round block @click="refreshData" style="margin-top: 10px">
            刷新数据
          </van-button>
        </div>
      </div>
    </div>

    <!-- 采纳建议弹窗 -->
    <van-popup v-model:show="showAdoptPanel" position="bottom" round :style="{ maxHeight: '60vh' }">
      <div class="adopt-panel">
        <div class="adopt-panel-header">
          <span class="adopt-panel-title">采纳建议</span>
          <van-icon name="cross" size="20" @click="closeAdoptPanel" />
        </div>
        <div class="adopt-panel-body">
          <div class="adopt-preview">
            <div class="adopt-label">建议内容：</div>
            <div class="adopt-content">{{ currentSuggestion?.content || currentSuggestion?.point || '' }}</div>
          </div>
          <div class="adopt-weight">
            <div class="adopt-label">请选择符合程度：</div>
            <div class="weight-options">
              <van-button
                v-for="option in weightOptions"
                :key="option.value"
                :type="selectedWeight === option.value ? 'primary' : 'default'"
                size="small"
                round
                @click="selectedWeight = option.value"
                class="weight-btn"
              >
                {{ (option.value * 100).toFixed(0) }}% {{ option.label }}
              </van-button>
            </div>
          </div>
        </div>
        <div class="adopt-panel-footer">
          <van-button plain round @click="closeAdoptPanel">取消</van-button>
          <van-button type="primary" round @click="confirmAdoptSuggestion">确认采纳</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.phone-evaluate {
  min-height: 100vh;
  background: var(--bg-page);
  padding-bottom: 60px;
}

/* 顶部导航 */
.page-header-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  padding: 0 16px;
  z-index: 100;
  border-bottom: 1px solid var(--border-color);
}
.page-header-bar .header-title {
  flex: 1;
  text-align: center;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title);
}
.page-header-bar .header-right {
  width: 40px;
  display: flex;
  justify-content: flex-end;
}

/* 加载遮罩 */
.loading-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 200;
}
.loading-text {
  color: #fff;
  font-size: 14px;
}

/* 主内容 */
.page-content {
  padding-top: 56px;
  padding-left: 14px;
  padding-right: 14px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  gap: 12px;
  text-align: center;
}
.empty-state h3 {
  font-size: 18px;
  color: var(--text-title);
  margin: 0;
}
.empty-state p {
  font-size: 13px;
  color: var(--text-gray);
  margin: 0;
}

/* 报告元信息 */
.report-meta {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 14px 16px;
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  border: 1px solid var(--border-color);
}
.meta-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
.meta-label {
  font-size: 12px;
  color: var(--text-gray);
}
.meta-value {
  font-size: 12px;
  color: var(--text-title);
  font-weight: 500;
}
.meta-status {
  margin-left: auto;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}
.status-success { background: rgba(103, 194, 58, 0.1); color: #67C23A; }
.status-primary { background: rgba(64, 158, 255, 0.1); color: #409EFF; }
.status-warning { background: rgba(230, 162, 60, 0.1); color: #E6A23C; }
.status-danger { background: rgba(245, 108, 108, 0.1); color: #F56C6C; }

/* 综合评分卡片 */
.score-card {
  background: linear-gradient(135deg, var(--primary), var(--primary-hv));
  border-radius: 16px;
  padding: 24px 20px;
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 20px;
  color: #fff;
}
.score-circle {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.score-number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}
.score-label {
  font-size: 11px;
  opacity: 0.8;
  margin-top: 2px;
}
.score-info {
  flex: 1;
  min-width: 0;
}
.score-level-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.score-level-row h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}
.score-level-row .regen-btn-white {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.4);
  color: #fff;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.score-level-row .regen-btn-white:active {
  background: rgba(255, 255, 255, 0.35);
}
.score-summary {
  font-size: 13px;
  opacity: 0.9;
  line-height: 1.5;
  margin: 0;
}

/* 仪表盘 */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 14px;
}
.dash-item {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 14px 8px;
  text-align: center;
  border: 1px solid var(--border-color);
}
.dash-value {
  font-size: 22px;
  font-weight: 700;
}
.dash-label {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 4px;
}

/* 通用 section 卡片 */
.section-card {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  margin-top: 14px;
  border: 1px solid var(--border-color);
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid var(--primary);
}

/* 雷达图 */
.radar-chart {
  width: 100%;
  height: 220px;
}

/* 维度进度条 */
.dim-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dim-bar-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dim-bar-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-body);
}
.dim-bar-label span:last-child {
  font-weight: 600;
}
.dim-bar-track {
  height: 8px;
  background: var(--bg-page);
  border-radius: 4px;
  overflow: hidden;
}
.dim-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.8s ease;
}

/* 维度评估卡片 */
.dim-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dim-eval-card {
  background: var(--bg-page);
  border-radius: 10px;
  padding: 12px 14px;
}
.dim-eval-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.dim-eval-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-title);
}
.dim-trend {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 8px;
  font-weight: 500;
}
.dim-trend.trend-up { color: #67C23A; background: rgba(103, 194, 58, 0.1); }
.dim-trend.trend-down { color: #F56C6C; background: rgba(245, 108, 108, 0.1); }
.dim-trend.trend-stable { color: var(--text-gray); background: var(--bg-card); }
.dim-eval-analysis {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.5;
  margin-bottom: 8px;
}
.regen-btn {
  color: var(--primary);
  border-color: var(--primary-light);
  font-size: 12px;
}
.btn-right {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

/* 薄弱点 */
.weak-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.weak-card {
  border-radius: 10px;
  padding: 12px 14px;
  border-left: 4px solid #409EFF;
  background: var(--bg-page);
}
.weak-card.priority-high { border-left-color: #F56C6C; }
.weak-card.priority-middle,
.weak-card.priority-zhong { border-left-color: #E6A23C; }
.weak-card.priority-low,
.weak-card.priority-di { border-left-color: #409EFF; }
.weak-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: nowrap;
  gap: 8px;
}
.weak-header .van-tag {
  flex-shrink: 0;
  white-space: nowrap;
}
.weak-point {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
}
.weak-detail {
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.6;
  margin-bottom: 8px;
}
.weak-label {
  color: var(--text-gray);
  font-weight: 500;
}
.empty-text {
  text-align: center;
  color: var(--text-gray);
  font-size: 13px;
  padding: 16px 0;
}

/* 热力图 */
.heatmap-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.heatmap-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
}
.heatmap-item.priority-high { background: rgba(245, 108, 108, 0.08); }
.heatmap-item.priority-middle,
.heatmap-item.priority-zhong { background: rgba(230, 162, 60, 0.08); }
.heatmap-item.priority-low,
.heatmap-item.priority-di { background: rgba(230, 162, 60, 0.05); }
.hm-name {
  flex: 3;
  font-size: 12px;
  color: var(--text-body);
}
.hm-bar {
  flex: 2;
  height: 16px;
  border-radius: 4px;
  min-width: 40px;
}
.hm-bar.priority-high { background: rgba(245, 108, 108, 0.6); width: 90%; }
.hm-bar.priority-middle,
.hm-bar.priority-zhong { background: rgba(230, 162, 60, 0.6); width: 60%; }
.hm-bar.priority-low,
.hm-bar.priority-di { background: rgba(64, 158, 255, 0.5); width: 30%; }
.hm-priority {
  font-size: 11px;
  white-space: nowrap;
}

/* 调整建议 */
.adjust-card {
  background: var(--bg-page);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 10px;
}
.adjust-card:last-child { margin-bottom: 0; }
.adjust-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}
.adjust-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-body);
  margin-bottom: 10px;
}
.adjust-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}
.adjust-label {
  color: var(--text-gray);
  font-weight: 500;
  flex-shrink: 0;
}
.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.adjust-reason {
  font-size: 12px;
  color: var(--text-gray);
}

/* 知识点优先级 */
.kp-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  margin-bottom: 6px;
  gap: 8px;
}
.kp-item:last-child { margin-bottom: 0; }
.kp-item.adopted {
  border-color: #67C23A;
  background: rgba(103, 194, 58, 0.05);
}
.kp-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-body);
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.kp-info span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kp-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--primary);
  color: #fff;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.kp-item.adopted .kp-index { background: #67C23A; }
.kp-actions {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
.kp-actions :deep(.van-button) {
  width: 50px !important;
  min-width: 50px !important;
  max-width: 50px !important;
  white-space: nowrap !important;
  word-break: keep-all !important;
  overflow: visible !important;
}
.kp-actions :deep(.van-button__content) {
  white-space: nowrap !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
}
.kp-actions :deep(.van-tag) {
  white-space: nowrap !important;
}

/* 计划优化 */
.plan-card {
  background: var(--bg-page);
  border-radius: 10px;
  padding: 14px;
}
.plan-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-body);
  margin-bottom: 10px;
}
.plan-suggestions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.plan-sug-item {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.6;
}
.sug-num {
  color: var(--primary);
  font-weight: 600;
  margin-right: 4px;
}

/* 已采纳 */
.adopted-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.adopted-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: rgba(103, 194, 58, 0.05);
  border-radius: 10px;
  border: 1px solid rgba(103, 194, 58, 0.3);
  gap: 8px;
}
.adopted-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  flex: 1;
}
.adopted-content {
  font-size: 12px;
  color: var(--text-body);
}

/* 底部操作 */
.bottom-actions {
  margin-top: 20px;
  padding-bottom: 20px;
}

/* 采纳面板 */
.adopt-panel {
  padding: 0;
}
.adopt-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}
.adopt-panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}
.adopt-panel-body {
  padding: 16px 20px;
}
.adopt-preview {
  margin-bottom: 16px;
}
.adopt-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-title);
  margin-bottom: 6px;
}
.adopt-content {
  font-size: 13px;
  color: var(--text-body);
  background: var(--bg-page);
  padding: 10px 14px;
  border-radius: 8px;
  line-height: 1.6;
  word-break: break-all;
}
.adopt-weight {
  margin-bottom: 8px;
}
.weight-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
}
.weight-btn {
  font-size: 12px;
}
.adopt-panel-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid var(--border-color);
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}
</style>

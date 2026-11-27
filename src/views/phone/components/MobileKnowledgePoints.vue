<script setup>
import { ref, onMounted, nextTick, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { getKnowledgePointsApi, startInterrogationApi, submitAnswerApi } from '@/api/mainApi/knowledgePoints.js'
import emptyStatusImg from '@/assets/image/emptyStatus.png'

const props = defineProps({
  userId: { type: String, default: '' }
})

// ==================== 状态 ====================
const currentView = ref('list') // 'list' | 'quiz' | 'result'
const allKps = ref([])
const activeStatus = ref('all')
const loading = ref(false)

// 盘问状态
const sessionId = ref(null)
const knowledgePoint = ref('')
const currentRound = ref(0)
const totalRounds = ref(3)
const answerText = ref('')
const isSubmitting = ref(false)

// 翻页状态
const currentStep = ref(0)
const steps = ref([])

// 结果数据
const resultData = ref(null)
const resultKp = ref('')

// 图表实例
let barChart = null
let radarChart = null

// ==================== 知识点列表 ====================
const loadKnowledgePoints = async () => {
  if (!props.userId) return
  loading.value = true
  try {
    const res = await getKnowledgePointsApi(props.userId)
    if (res && res.success) {
      allKps.value = res.knowledge_points || []
    } else {
      allKps.value = []
    }
  } catch (e) {
    console.error('加载知识点失败', e)
    allKps.value = []
  } finally {
    loading.value = false
  }
}

const statusCounts = () => {
  const counts = { all: allKps.value.length }
  for (const kp of allKps.value) {
    const s = kp.status || 'unpracticed'
    counts[s] = (counts[s] || 0) + 1
  }
  return counts
}

const filteredKps = () => {
  if (activeStatus.value === 'all') return allKps.value
  return allKps.value.filter(kp => (kp.status || 'unpracticed') === activeStatus.value)
}

const switchTab = (status) => {
  activeStatus.value = status
}

const getFillClass = (score) => {
  if (score < 30) return 'fill-low'
  if (score < 60) return 'fill-mid'
  return 'fill-high'
}

const getScoreColor = (score) => {
  if (score < 40) return 'var(--main-delete)'
  if (score < 70) return 'var(--coming)'
  return 'var(--pass)'
}

const getTagInfo = (kp) => {
  if (kp.has_unresolved) return { label: '待巩固', cls: 'tag-unresolved' }
  if (kp.wrong_count === 0) return { label: '未练习', cls: 'tag-new' }
  return { label: '已巩固', cls: 'tag-resolved' }
}

const getInterrogationColor = (score) => {
  if (score >= 75) return 'var(--pass)'
  if (score >= 50) return 'var(--coming)'
  return 'var(--main-delete)'
}

// ==================== 开始盘问 ====================
const startQuiz = async (kpName) => {
  knowledgePoint.value = kpName
  currentRound.value = 0
  answerText.value = ''
  sessionId.value = null
  currentStep.value = 0
  steps.value = []

  currentView.value = 'quiz'

  steps.value = [{ type: 'loading', html: '', text: '正在生成第1轮场景题...' }]

  try {
    const res = await startInterrogationApi({
      user_id: props.userId,
      knowledge_point: kpName
    })
    if (!res || !res.success) {
      steps.value = [{ type: 'error', html: '', text: res?.detail || '启动失败' }]
      return
    }

    sessionId.value = res.session_id
    totalRounds.value = res.total_rounds || 3
    renderQuestion(res)
  } catch (e) {
    steps.value = [{ type: 'error', html: '', text: '网络错误: ' + e.message }]
  }
}

const renderQuestion = (data) => {
  currentRound.value = data.round_number || 1
  isSubmitting.value = false

  let scenarioHtml = ''
  if (data.scenario) {
    scenarioHtml = `<div class="scenario-box"><div class="scenario-label">场景描述</div><div>${escapeHtml(data.scenario)}</div></div>`
  }

  let hintHtml = ''
  if (data.hint) {
    hintHtml = `<div class="hint-box"><span class="hint-label">思考提示:</span> ${escapeHtml(data.hint)}</div>`
  }

  let imageHtml = ''
  if (data.image_url) {
    imageHtml = `<div class="q-image-wrap"><img src="${escapeHtml(data.image_url)}" class="q-image" alt="配图" onerror="this.style.display='none'"></div>`
  }

  steps.value = [{
    type: 'question',
    html: `${scenarioHtml}<div class="question-text">${escapeHtml(data.question || '')}</div>${imageHtml}${hintHtml}`
  }]
  currentStep.value = 0
}

// ==================== 提交回答 ====================
const submitAnswer = async () => {
  const text = answerText.value.trim()
  if (!text || isSubmitting.value) return
  if (!sessionId.value) return

  isSubmitting.value = true
  answerText.value = ''

  try {
    const res = await submitAnswerApi({
      session_id: sessionId.value,
      answer: text
    })

    if (!res || !res.success) {
      steps.value.push({ type: 'error', html: '', text: res?.detail || '提交失败' })
      currentStep.value = steps.value.length - 1
      isSubmitting.value = false
      return
    }

    if (res.is_final) {
      resultData.value = res
      resultKp.value = knowledgePoint.value
      setTimeout(() => showResult(res), 800)
    } else {
      renderEvaluationAndNext(res)
    }
  } catch (e) {
    steps.value.push({ type: 'error', html: '', text: '网络错误: ' + e.message })
    currentStep.value = steps.value.length - 1
  }
  isSubmitting.value = false
}

const renderEvaluationAndNext = (data) => {
  const ev = data.evaluation || {}
  const score = ev.score || 0

  let strengthsHtml = ''
  if (ev.strengths && ev.strengths.length) {
    strengthsHtml = `<div class="ev-strengths">亮点: ${ev.strengths.join('、')}</div>`
  }
  let weaknessesHtml = ''
  if (ev.weaknesses && ev.weaknesses.length) {
    weaknessesHtml = `<div class="ev-weaknesses">待加强: ${ev.weaknesses.join('、')}</div>`
  }

  const verdictText = ev.verdict === 'correct' ? '回答正确' : ev.verdict === 'partially_correct' ? '部分正确' : '需要加强'
  const verdictIcon = ev.verdict === 'correct' ? '✓' : ev.verdict === 'partially_correct' ? '~' : '✗'

  const scoreClass = score >= 70 ? 'score-good' : score >= 40 ? 'score-ok' : 'score-bad'

  steps.value.push({
    type: 'evaluation',
    html: `<div class="evaluation-card">
      <div class="ev-score-circle ${scoreClass}">
        <div class="ev-score-number">${score}</div>
        <div class="ev-score-unit">分</div>
      </div>
      <div class="ev-verdict-badge ${scoreClass}">${verdictIcon} ${verdictText}</div>
      <div class="ev-divider"></div>
      <div class="ev-feedback">${escapeHtml(ev.feedback || '')}</div>
      ${strengthsHtml}${weaknessesHtml}
    </div>`
  })

  currentRound.value = data.round_number || 1

  let nextContent = ''

  if (data.next_scenario) {
    nextContent += `<div class="scenario-box"><div class="scenario-label">场景描述</div><div>${escapeHtml(data.next_scenario)}</div></div>`
  }

  nextContent += `<div class="question-text">${escapeHtml(data.next_question || '')}</div>`

  if (data.next_image_url) {
    nextContent += `<div class="q-image-wrap"><img src="${escapeHtml(data.next_image_url)}" class="q-image" alt="配图" onerror="this.style.display='none'"></div>`
  }

  if (data.next_hint) {
    nextContent += `<div class="hint-box"><span class="hint-label">思考提示:</span> ${escapeHtml(data.next_hint)}</div>`
  }

  steps.value.push({
    type: 'nextQuestion',
    html: `<div class="next-question-header">
      <span class="next-question-icon">→</span>
      <span>第 ${currentRound.value} 轮</span>
    </div>
    <div class="next-question-content">
      ${nextContent}
    </div>`
  })

  currentStep.value = steps.value.length - 2
}

const nextStep = () => {
  if (currentStep.value < steps.value.length - 1) {
    currentStep.value++
    if (steps.value[currentStep.value]?.type === 'nextQuestion') {
      isSubmitting.value = false
    }
  }
}

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

const currentStepContent = () => {
  if (steps.value.length === 0) return null
  return steps.value[currentStep.value] || null
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submitAnswer()
  }
}

// ==================== 结果展示 ====================
const showResult = (data) => {
  currentView.value = 'result'
  nextTick(() => {
    renderCharts(data)
  })
}

const renderCharts = (data) => {
  const vd = data.visualization_data || {}
  const barData = vd.bar_data || {}
  const radarData = vd.radar_data || {}

  const barEl = document.getElementById('kpBarChart')
  const radarEl = document.getElementById('kpRadarChart')

  if (barEl) {
    barChart = echarts.init(barEl)
    const categories = barData.categories || ['综合掌握度']
    const expected = barData.expected || [0]
    const actual = barData.actual || [0]

    barChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['预期掌握度', '实际掌握度'], bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 40, right: 15, top: 15, bottom: 35 },
      xAxis: { type: 'category', data: categories, axisLabel: { fontSize: 11, fontWeight: 500 } },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 10, formatter: '{value}分' }, splitLine: { lineStyle: { type: 'dashed' } } },
      series: [
        { name: '预期掌握度', type: 'bar', data: expected, barWidth: '30%', itemStyle: { borderRadius: [4, 4, 0, 0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#93c5fd' }, { offset: 1, color: '#60a5fa' }] } } },
        { name: '实际掌握度', type: 'bar', data: actual, barWidth: '30%', itemStyle: { borderRadius: [4, 4, 0, 0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#a78bfa' }, { offset: 1, color: '#7c3aed' }] } } }
      ]
    })
  }

  if (radarEl) {
    radarChart = echarts.init(radarEl)
    const indicators = radarData.indicators || []
    const expectedArr = radarData.expected || []
    const actualArr = radarData.actual || []

    radarChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { data: ['预期掌握度', '实际掌握度'], bottom: 0, textStyle: { fontSize: 11 } },
      radar: {
        indicator: indicators, shape: 'polygon', splitNumber: 4,
        axisName: { fontSize: 11 },
        splitArea: { areaStyle: { color: ['rgba(102,126,234,0.02)', 'rgba(102,126,234,0.04)', 'rgba(102,126,234,0.06)', 'rgba(102,126,234,0.08)'] } },
        splitLine: { lineStyle: { color: 'rgba(0,0,0,0.1)' } },
        axisLine: { lineStyle: { color: 'rgba(0,0,0,0.15)' } }
      },
      series: [{
        name: '盘问评估', type: 'radar',
        data: [
          { value: expectedArr, name: '预期掌握度', areaStyle: { color: 'rgba(96,165,250,0.2)' }, lineStyle: { color: '#60a5fa', width: 2 }, itemStyle: { color: '#60a5fa' } },
          { value: actualArr, name: '实际掌握度', areaStyle: { color: 'rgba(124,58,237,0.2)' }, lineStyle: { color: '#7c3aed', width: 2 }, itemStyle: { color: '#7c3aed' } }
        ]
      }]
    })
  }

  window.addEventListener('resize', handleResize)
}

const handleResize = () => {
  barChart?.resize()
  radarChart?.resize()
}

const backToList = () => {
  currentView.value = 'list'
  destroyCharts()
  loadKnowledgePoints()
}

const destroyCharts = () => {
  window.removeEventListener('resize', handleResize)
  barChart?.dispose()
  radarChart?.dispose()
  barChart = null
  radarChart = null
}

const getResultVerdictClass = (verdict) => {
  if (verdict === 'mastered') return 'verdict-mastered'
  if (verdict === 'basically_mastered') return 'verdict-basic'
  return 'verdict-not'
}

const getDimColor = (score) => {
  if (score >= 75) return 'var(--pass)'
  if (score >= 50) return 'var(--coming)'
  return 'var(--main-delete)'
}

const escapeHtml = (text) => {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

const scrollToBottom = () => {
  nextTick(() => {
    const chatArea = document.querySelector('.quiz-answer-area')
    if (chatArea) chatArea.scrollTop = chatArea.scrollHeight
  })
}

onMounted(() => {
  loadKnowledgePoints()
})

onUnmounted(() => {
  destroyCharts()
})

watch(steps, () => scrollToBottom(), { deep: true })
</script>

<template>
  <div class="mkp-root">

    <!-- ===== 视图1: 知识点列表 ===== -->
    <div v-if="currentView === 'list'" class="mkp-list-view">
      <div class="mkp-subtitle">基于错题知识点提取，点击进入盘问以评估实际掌握程度</div>

      <!-- 状态标签（横向滚动） -->
      <div class="mkp-tabs">
        <div class="mkp-tab-btn" :class="{ active: activeStatus === 'all' }" @click="switchTab('all')">
          <van-icon name="apps-o" />全部 <span class="tab-cnt">({{ statusCounts().all }})</span>
        </div>
        <div class="mkp-tab-btn" :class="{ active: activeStatus === 'struggling' }" @click="switchTab('struggling')">
          <van-icon name="warning-o" />需巩固 <span class="tab-cnt">({{ statusCounts().struggling || 0 }})</span>
        </div>
        <div class="mkp-tab-btn" :class="{ active: activeStatus === 'unpracticed' }" @click="switchTab('unpracticed')">
          <van-icon name="edit" />待盘问 <span class="tab-cnt">({{ statusCounts().unpracticed || 0 }})</span>
        </div>
        <div class="mkp-tab-btn" :class="{ active: activeStatus === 'new' }" @click="switchTab('new')">
          <van-icon name="star-o" />新知识点 <span class="tab-cnt">({{ statusCounts().new || 0 }})</span>
        </div>
        <div class="mkp-tab-btn" :class="{ active: activeStatus === 'mastered' }" @click="switchTab('mastered')">
          <van-icon name="success" />已掌握 <span class="tab-cnt">({{ statusCounts().mastered || 0 }})</span>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="mkp-loading">
        <van-loading size="20px" />
        <span>加载知识点列表...</span>
      </div>

      <!-- 空状态 -->
      <div v-else-if="allKps.length === 0" class="mkp-empty">
        <img :src="emptyStatusImg" class="mkp-empty-img" alt="暂无数据" />
        <div class="mkp-empty-text">暂无知识点数据，请先做一些错题</div>
      </div>

      <!-- 知识点卡片列表 -->
      <div v-else class="mkp-list">
        <div
          v-for="kp in filteredKps()"
          :key="kp.knowledge_point"
          class="mkp-card"
          @click="startQuiz(kp.knowledge_point)"
        >
          <!-- 顶部: 名称 + 标签 -->
          <div class="mkp-card-header">
            <div class="mkp-card-name">{{ kp.knowledge_point }}</div>
            <span class="mkp-tag" :class="getTagInfo(kp).cls">{{ getTagInfo(kp).label }}</span>
          </div>

          <!-- 统计信息行 -->
          <div class="mkp-card-stats">
            <div class="stat-item">
              <van-icon name="edit" class="stat-icon" />
              <span class="stat-label">错题</span>
              <span class="stat-value">{{ kp.wrong_count }}次</span>
            </div>
            <div class="stat-item">
              <van-icon name="chart-trending-o" class="stat-icon" />
              <span class="stat-label">最高连续错</span>
              <span class="stat-value">{{ kp.max_attempt }}次</span>
            </div>
          </div>

          <!-- 掌握度进度条 -->
          <div class="mastery-section">
            <div class="mastery-header">
              <span class="mastery-title">预期掌握度</span>
              <span class="mastery-score" :style="{ color: getScoreColor(kp.expected_mastery_score) }">
                {{ kp.expected_mastery_score }}%
              </span>
            </div>
            <div class="mastery-bar">
              <div :class="['mastery-fill', getFillClass(kp.expected_mastery_score)]"
                   :style="{ width: kp.expected_mastery_score + '%' }"></div>
            </div>
          </div>

          <!-- 盘问结果 -->
          <div class="ir-result">
            <van-icon name="passed" class="ir-icon" />
            <span class="ir-label">盘问结果</span>
            <span class="ir-badge" v-if="kp.interrogation"
                  :style="{
                    color: getInterrogationColor(kp.interrogation.overall_score),
                    background: getInterrogationColor(kp.interrogation.overall_score) + '15'
                  }">
              {{ kp.interrogation.verdict_label }} {{ kp.interrogation.overall_score }}分
            </span>
            <span class="ir-badge ir-badge-none" v-else>
              暂无
            </span>
          </div>
        </div>

        <!-- 筛选后无数据 -->
        <div v-if="filteredKps().length === 0" class="mkp-empty">
          <img :src="emptyStatusImg" class="mkp-empty-img" alt="暂无数据" />
          <div class="mkp-empty-text">该分类下暂无知识点</div>
        </div>
      </div>
    </div>

    <!-- ===== 视图2: 盘问 ===== -->
    <div v-if="currentView === 'quiz'" class="mkp-quiz-view">
      <!-- 顶部信息栏 -->
      <div class="quiz-header">
        <div class="quiz-back-btn" @click="backToList">
          <van-icon name="arrow-left" />
        </div>
        <div class="quiz-kp-title">{{ knowledgePoint }}</div>
        <div class="quiz-round-info">{{ currentRound }}/{{ totalRounds }}轮</div>
      </div>

      <!-- 题目区域 -->
      <div class="quiz-question-panel">
        <div class="panel-title">
          <van-icon name="question-o" class="panel-icon" />
          <span v-if="currentStepContent()?.type === 'question'">当前题目</span>
          <span v-else-if="currentStepContent()?.type === 'evaluation'">评估结果</span>
          <span v-else-if="currentStepContent()?.type === 'nextQuestion'">下一题</span>
          <span v-else>题目</span>
          <span class="step-indicator">{{ currentStep + 1 }}/{{ steps.length }}页</span>
        </div>
        <div class="question-content">
          <!-- 加载中 -->
          <div v-if="currentStepContent()?.type === 'loading'" class="mkp-loading">
            <van-loading size="20px" />
            <span>{{ currentStepContent()?.text }}</span>
          </div>
          <!-- 错误 -->
          <div v-else-if="currentStepContent()?.type === 'error'" class="error-block">
            {{ currentStepContent()?.text }}
          </div>
          <!-- 题目/评估/下一题 -->
          <div v-else-if="currentStepContent()?.html" v-html="currentStepContent().html" class="question-block"></div>

          <!-- 评估遮罩 -->
          <div v-if="isSubmitting" class="eval-overlay">
            <div class="eval-overlay-content">
              <van-loading size="24px" color="#fff" />
              <span>评估中...</span>
            </div>
          </div>
        </div>
        <!-- 翻页按钮 -->
        <div class="step-nav">
          <div class="prev-step-btn" :class="{ disabled: currentStep === 0 }" @click="prevStep">
            <van-icon name="arrow-left" />上一步
          </div>
          <div class="next-step-btn" :class="{ disabled: currentStep >= steps.length - 1 }" @click="nextStep">
            下一步<van-icon name="arrow" />
          </div>
        </div>
      </div>

      <!-- 作答区域 -->
      <div class="quiz-answer-panel">
        <div class="panel-title">
          <van-icon name="edit" class="panel-icon" />
          我的回答
        </div>
        <div class="answer-content">
          <textarea
            v-model="answerText"
            rows="5"
            placeholder="输入你的回答..."
            :disabled="isSubmitting"
            @keydown="handleKeydown"
            class="answer-input"
          ></textarea>
          <div
            class="send-btn"
            :class="{ disabled: isSubmitting || !answerText.trim() }"
            @click="submitAnswer"
          >
            <van-icon name="guide-o" />
            提交回答
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 视图3: 结果 ===== -->
    <div v-if="currentView === 'result' && resultData" class="mkp-result-view">
      <div class="result-header-card">
        <div :class="['verdict-badge', getResultVerdictClass(resultData.result?.verdict)]">
          {{ resultData.result?.verdict_label || '未知' }}
        </div>
        <div class="overall-score">
          {{ resultData.result?.overall_score || 0 }}<span class="score-unit">分</span>
        </div>
        <div class="result-summary">{{ resultData.result?.summary || '' }}</div>
      </div>

      <!-- 图表 -->
      <div class="chart-card">
        <div class="chart-title"><van-icon name="bar-chart-o" />预期 vs 实际掌握度</div>
        <div class="chart-container" id="kpBarChart"></div>
      </div>
      <div class="chart-card">
        <div class="chart-title"><van-icon name="aim" />多维度掌握分析</div>
        <div class="chart-container" id="kpRadarChart"></div>
      </div>

      <!-- 三维度评分 -->
      <div class="dimension-summary" v-if="resultData.result?.dimensions">
        <div class="dim-title"><van-icon name="balance-o" />三维度评分</div>
        <div class="dim-grid">
          <div class="dim-item">
            <div class="dim-name">概念理解</div>
            <div class="dim-score" :style="{ color: getDimColor(resultData.result.dimensions.concept_understanding || 0) }">
              {{ resultData.result.dimensions.concept_understanding || 0 }}
            </div>
            <div class="dim-bar">
              <div class="dim-fill" :style="{ width: (resultData.result.dimensions.concept_understanding || 0) + '%', background: getDimColor(resultData.result.dimensions.concept_understanding || 0) }"></div>
            </div>
          </div>
          <div class="dim-item">
            <div class="dim-name">应用能力</div>
            <div class="dim-score" :style="{ color: getDimColor(resultData.result.dimensions.application_ability || 0) }">
              {{ resultData.result.dimensions.application_ability || 0 }}
            </div>
            <div class="dim-bar">
              <div class="dim-fill" :style="{ width: (resultData.result.dimensions.application_ability || 0) + '%', background: getDimColor(resultData.result.dimensions.application_ability || 0) }"></div>
            </div>
          </div>
          <div class="dim-item">
            <div class="dim-name">思考深度</div>
            <div class="dim-score" :style="{ color: getDimColor(resultData.result.dimensions.depth_of_thinking || 0) }">
              {{ resultData.result.dimensions.depth_of_thinking || 0 }}
            </div>
            <div class="dim-bar">
              <div class="dim-fill" :style="{ width: (resultData.result.dimensions.depth_of_thinking || 0) + '%', background: getDimColor(resultData.result.dimensions.depth_of_thinking || 0) }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 提升建议 -->
      <div class="suggestions" v-if="resultData.result?.improvement_suggestions?.length">
        <div class="dim-title"><van-icon name="notes-o" />提升建议</div>
        <ul>
          <li v-for="(s, i) in resultData.result.improvement_suggestions" :key="i">
            {{ s }}
          </li>
        </ul>
      </div>

      <div class="result-actions">
        <div class="back-list-btn" @click="backToList">
          <van-icon name="arrow-left" />返回列表
        </div>
        <div class="retry-btn" @click="startQuiz(resultKp)">
          <van-icon name="replay" />重新盘问
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.mkp-root {
  width: 100%;
  min-height: 300px;
  padding: 0 16px;
  padding-bottom: 60px;
}

/* ===== 列表视图 ===== */
.mkp-list-view {
  padding: 0;
}

.mkp-subtitle {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 4px;
  line-height: 1.5;
}

/* 标签页 - 横向滚动 */
.mkp-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  padding-bottom: 2px;
}
.mkp-tabs::-webkit-scrollbar {
  display: none;
}

.mkp-tab-btn {
  padding: 5px 12px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--bg-card);
  color: var(--text-body);
  font-size: 12px;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
  transition: all 0.2s;
}

.mkp-tab-btn.active {
  background: var(--grad-primary);
  color: #fff;
  border-color: transparent;
}

.tab-cnt {
  font-size: 10px;
  opacity: 0.8;
  margin-left: 2px;
}

/* 加载 & 空状态 */
.mkp-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30px;
  gap: 8px;
  color: var(--text-gray);
  font-size: 13px;
}

.mkp-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 250px;
  color: var(--text-gray);
}

.mkp-empty-img {
  width: 120px;
  height: auto;
  margin-bottom: 12px;
  opacity: 0.8;
}

.mkp-empty-text {
  font-size: 13px;
}

/* 卡片列表 - 单列 */
.mkp-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mkp-card {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mkp-card:active {
  transform: scale(0.98);
  border-color: var(--primary);
}

/* 卡片头部 */
.mkp-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.mkp-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  line-height: 1.4;
  flex: 1;
}

.mkp-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

.tag-unresolved {
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.tag-resolved {
  background: var(--pass-bg-color);
  color: var(--pass);
}

.tag-new {
  background: var(--primary-fade);
  color: var(--primary);
}

/* 统计信息 */
.mkp-card-stats {
  display: flex;
  gap: 16px;
  padding: 8px 0;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.stat-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.stat-icon {
  font-size: 14px;
  color: var(--primary);
}

.stat-value {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-title);
}

.stat-label {
  font-size: 11px;
  color: var(--text-gray);
}

/* 掌握度进度条 */
.mastery-section {
  padding: 2px 0;
}

.mastery-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.mastery-title {
  font-size: 12px;
  color: var(--text-gray);
}

.mastery-score {
  font-size: 14px;
  font-weight: 600;
}

.mastery-bar {
  height: 6px;
  background: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.mastery-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.fill-low {
  background: linear-gradient(90deg, var(--main-delete), var(--coming));
}

.fill-mid {
  background: linear-gradient(90deg, var(--coming), var(--warning));
}

.fill-high {
  background: linear-gradient(90deg, var(--pass), var(--success));
}

/* 盘问结果 */
.ir-result {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--bg-hover);
  border-radius: 6px;
  font-size: 12px;
}

.ir-icon {
  font-size: 14px;
  color: var(--pass);
}

.ir-label {
  color: var(--text-gray);
  font-size: 11px;
}

.ir-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 12px;
  margin-left: auto;
}

.ir-badge-none {
  background: var(--bg-hover);
  color: var(--text-gray);
}

/* ===== 盘问视图 ===== */
.mkp-quiz-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quiz-header {
  background: var(--bg-card);
  border-radius: 10px;
  margin-top: 9px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--border-color);
}

.quiz-back-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-body);
  font-size: 14px;
  flex-shrink: 0;
}

.quiz-kp-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quiz-round-info {
  font-size: 12px;
  color: var(--text-gray);
  background: var(--bg-hover);
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}

/* 题目面板 */
.quiz-question-panel,
.quiz-answer-panel {
  background: var(--bg-card);
  border-radius: 10px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-title {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  display: flex;
  align-items: center;
  gap: 5px;
}

.panel-icon {
  font-size: 15px;
  color: var(--primary);
}

.step-indicator {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-gray);
  background: var(--bg-hover);
  padding: 1px 6px;
  border-radius: 8px;
}

/* 翻页按钮 */
.step-nav {
  padding: 8px 12px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.prev-step-btn,
.next-step-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
}

.prev-step-btn {
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-body);
}

.next-step-btn {
  background: var(--grad-primary);
  color: #fff;
}

.prev-step-btn.disabled,
.next-step-btn.disabled {
  opacity: 0.4;
  pointer-events: none;
}

/* 错误提示 */
.error-block {
  color: var(--main-delete);
  font-size: 13px;
  padding: 10px;
  background: var(--main-fail-status);
  border-radius: 6px;
}

.question-content,
.answer-content {
  padding: 12px;
  flex: 1;
  overflow-y: auto;
  position: relative;
  -webkit-overflow-scrolling: touch;
}

.question-content::-webkit-scrollbar,
.answer-content::-webkit-scrollbar {
  width: 3px;
}

.question-content::-webkit-scrollbar-thumb,
.answer-content::-webkit-scrollbar-thumb {
  background: var(--text-gray);
  border-radius: 2px;
}

.question-block {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-body);
  margin-bottom: 8px;
}

/* 评估遮罩 */
.eval-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.eval-overlay-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
}

/* 场景框 - v-html 穿透样式 */
.question-content :deep(.scenario-box) {
  background: var(--primary-light);
  border-left: 3px solid var(--primary);
  border-radius: 6px;
  padding: 8px 10px;
  margin: 6px 0;
  font-size: 12px;
  color: var(--text-body);
}

.question-content :deep(.scenario-label) {
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 3px;
  font-size: 12px;
}

.question-content :deep(.question-text) {
  font-size: 14px;
  font-weight: 500;
  margin: 6px 0;
  color: var(--text-title);
}

.question-content :deep(.q-image-wrap) {
  margin: 8px 0;
  text-align: center;
}

.question-content :deep(.q-image) {
  max-width: 100%;
  max-height: 200px;
  width: auto;
  height: auto;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  object-fit: contain;
}

.question-content :deep(.hint-box) {
  background: var(--coming-bg-color);
  border-radius: 6px;
  padding: 8px 10px;
  margin: 6px 0;
  font-size: 12px;
  color: var(--coming);
  border: 1px solid var(--coming-shadow);
}

.question-content :deep(.hint-label) {
  font-weight: 600;
}

/* 评估卡片 */
.question-content :deep(.evaluation-card) {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 16px;
  margin: 8px 0;
  border: 2px solid var(--border-color);
}

.question-content :deep(.ev-score-circle) {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: 0 auto 10px;
}

.question-content :deep(.ev-score-circle.score-good) {
  background: linear-gradient(135deg, var(--pass-bg-color), var(--pass-shadow));
  border: 3px solid var(--pass);
}

.question-content :deep(.ev-score-circle.score-ok) {
  background: linear-gradient(135deg, var(--coming-bg-color), var(--coming-shadow));
  border: 3px solid var(--coming);
}

.question-content :deep(.ev-score-circle.score-bad) {
  background: linear-gradient(135deg, var(--main-fail-status), var(--main-fail-status-hover));
  border: 3px solid var(--main-delete);
}

.question-content :deep(.ev-score-number) {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
  color: var(--text-gray);
}

.question-content :deep(.ev-score-unit) {
  font-size: 11px;
  margin-top: 1px;
  color: var(--text-gray);
}

.question-content :deep(.ev-verdict-badge) {
  display: block;
  width: fit-content;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
  margin: 0 auto 10px;
  text-align: center;
}

.question-content :deep(.ev-verdict-badge.score-good) {
  background: var(--pass-bg-color);
  color: var(--pass);
}

.question-content :deep(.ev-verdict-badge.score-ok) {
  background: var(--coming-bg-color);
  color: var(--coming);
}

.question-content :deep(.ev-verdict-badge.score-bad) {
  background: var(--main-fail-status);
  color: var(--main-delete);
}

.question-content :deep(.ev-divider) {
  height: 1px;
  background: var(--border-color);
  margin: 10px 0;
}

.question-content :deep(.ev-feedback) {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-body);
  margin-bottom: 8px;
}

.question-content :deep(.ev-strengths) {
  background: var(--pass-bg-color);
  border-left: 3px solid var(--pass);
  border-radius: 6px;
  padding: 8px 10px;
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--pass);
}

.question-content :deep(.ev-weaknesses) {
  background: var(--main-fail-status);
  border-left: 3px solid var(--main-delete);
  border-radius: 6px;
  padding: 8px 10px;
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--main-delete);
}

/* 下一题 */
.question-content :deep(.next-question-header) {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
}

.question-content :deep(.next-question-icon) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.question-content :deep(.next-question-content) {
  padding-left: 2px;
}

/* 作答输入框 */
.answer-input {
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  background: var(--bg-input);
  color: var(--text-body);
  margin-bottom: 10px;
}

.answer-input:focus {
  border-color: var(--primary);
}

.send-btn {
  width: 100%;
  padding: 10px;
  border-radius: 8px;
  background: var(--grad-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: opacity 0.2s;
}

.send-btn.disabled {
  opacity: 0.4;
  pointer-events: none;
}

.send-btn:active {
  opacity: 0.8;
}

/* ===== 结果视图 ===== */
.mkp-result-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-header-card {
  text-align: center;
  padding: 20px 14px;
  background: var(--bg-card);
  border-radius: 10px;
  border: 1px solid var(--border-color);
}

.verdict-badge {
  display: inline-flex;
  align-items: center;
  padding: 5px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.verdict-mastered {
  background: linear-gradient(135deg, var(--pass-bg-color), var(--pass-shadow));
  color: var(--pass);
}

.verdict-basic {
  background: linear-gradient(135deg, var(--coming-bg-color), var(--coming-shadow));
  color: var(--coming);
}

.verdict-not {
  background: linear-gradient(135deg, var(--main-fail-status), var(--main-fail-status-hover));
  color: var(--main-delete);
}

.overall-score {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-title);
  margin: 4px 0;
}

.score-unit {
  font-size: 14px;
  color: var(--text-gray);
}

.result-summary {
  font-size: 13px;
  color: var(--text-gray);
  line-height: 1.5;
}

/* 图表 */
.chart-card {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid var(--border-color);
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.chart-container {
  width: 100%;
  height: 220px;
}

/* 三维度评分 */
.dimension-summary {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid var(--border-color);
}

.dim-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--text-title);
  display: flex;
  align-items: center;
  gap: 5px;
}

.dim-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.dim-item {
  text-align: center;
  padding: 10px 6px;
  background: var(--bg-hover);
  border-radius: 8px;
}

.dim-name {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 3px;
}

.dim-score {
  font-size: 22px;
  font-weight: 700;
}

.dim-bar {
  height: 3px;
  background: var(--border-color);
  border-radius: 2px;
  margin-top: 5px;
  overflow: hidden;
}

.dim-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s;
}

/* 提升建议 */
.suggestions {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid var(--border-color);
}

.suggestions ul {
  list-style: none;
}

.suggestions li {
  padding: 8px 10px;
  margin-bottom: 6px;
  background: var(--bg-hover);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-body);
  border-left: 3px solid var(--primary);
  line-height: 1.5;
}

/* 操作按钮 */
.result-actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.result-actions > div {
  flex: 1;
  padding: 10px;
  border-radius: 8px;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: all 0.2s;
}

.back-list-btn {
  background: var(--bg-hover);
  color: var(--text-body);
  border: 1px solid var(--border-color);
}

.retry-btn {
  background: var(--grad-primary);
  color: #fff;
}

.back-list-btn:active,
.retry-btn:active {
  opacity: 0.8;
}
</style>

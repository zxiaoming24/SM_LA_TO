<template>
  <div v-if="visible" class="dt-page">
    <!-- Tab 栏 -->
    <div class="dt-tab-bar">
      <div
        class="dt-tab"
        :class="{ active: activeTab === 'overview' }"
        @click="switchTab('overview')"
      >
        <el-icon><Monitor /></el-icon>
        总览
      </div>
      <div
        class="dt-tab"
        :class="{ active: activeTab === 'profile' }"
        @click="switchTab('profile')"
      >
        <el-icon><DataAnalysis /></el-icon>
        孪生画像
      </div>
      <div
        class="dt-tab"
        :class="{ active: activeTab === 'history' }"
        @click="switchTab('history')"
      >
        <el-icon><List /></el-icon>
        对比历史
      </div>
      <div class="dt-tab-close" @click="emit('close')">
        <el-icon><CircleClose /></el-icon>
      </div>
    </div>

    <!-- 构建进度弹窗 -->
    <div v-if="buildOverlayVisible" class="dt-build-overlay">
      <div class="dt-build-modal">
        <h2>
          <el-icon :size="20"><Monitor /></el-icon>
          正在构建数字孪生
        </h2>
        <div class="dt-build-subtitle">正在从多个数据源采集你的特征数据...</div>

        <div class="dt-progress-wrap">
          <div class="dt-progress-bar-bg">
            <div class="dt-progress-bar-fill" :style="{ width: buildProgress + '%' }"></div>
          </div>
          <div class="dt-progress-text">
            <span>{{ buildProgressLabel }}</span>
            <span>{{ buildStepLabel }}</span>
          </div>
        </div>

        <div class="dt-build-status-panel">
          <div
            v-for="(line, idx) in buildStatusLines"
            :key="idx"
            class="dt-status-line"
            :class="{ completed: line.dotClass === 'done', errored: line.dotClass === 'error' }"
          >
            <div class="dt-status-dot" :class="line.dotClass"></div>
            <div class="dt-status-msg">
              {{ line.message }}
              <div v-if="line.detail" class="dt-status-detail">{{ line.detail }}</div>
            </div>
            <div class="dt-status-pct">{{ line.pct }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="dt-container">
      <!-- ==================== TAB: 总览 ==================== -->
      <div v-show="activeTab === 'overview'" class="dt-tab-content">
        <!-- 状态横幅 -->
        <div class="dt-status-banner" :class="twinStatusClass">
          <el-icon class="dt-status-icon" :size="28">
            <Monitor v-if="twinData?.status?.exists" />
            <CircleClose v-else />
          </el-icon>
          <div class="dt-status-text">
            <h3>{{ statusTitle }}</h3>
            <p>{{ statusDesc }}</p>
          </div>
          <button
            class="dt-btn dt-btn-primary"
            :disabled="isBuilding"
            @click="buildTwin"
          >
            {{ isBuilding ? '构建中...' : (twinData?.status?.exists ? (twinData.status.enabled ? '重建孪生' : '构建孪生') : '构建孪生') }}
          </button>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="dt-loading">
          <div class="dt-spinner"></div>
          <p>正在加载...</p>
        </div>

        <!-- 无数据 -->
        <div v-else-if="!twinData" class="dt-empty">
          <el-icon :size="64" color="var(--text-gray)"><Monitor /></el-icon>
          <p>暂无数据</p>
        </div>

        <!-- 统计卡片 -->
        <div v-else-if="twinData?.stats?.exists" class="dt-stats-grid">
          <div class="dt-stat-card">
            <div class="dt-stat-num" style="color: var(--primary)">{{ twinData.stats.total || 0 }}</div>
            <div class="dt-stat-label">总对比次数</div>
          </div>
          <div class="dt-stat-card">
            <div class="dt-stat-num" style="color: var(--pass)">{{ twinData.stats.both_correct || 0 }}</div>
            <div class="dt-stat-label">你对他对</div>
          </div>
          <div class="dt-stat-card">
            <div class="dt-stat-num" style="color: var(--purple)">{{ twinData.stats.user_wrong_twin_right || 0 }}</div>
            <div class="dt-stat-label">你错他对 <span class="dt-stat-hint" style="color: var(--purple)">盲区</span></div>
          </div>
          <div class="dt-stat-card">
            <div class="dt-stat-num" style="color: var(--coming)">{{ twinData.stats.user_right_twin_wrong || 0 }}</div>
            <div class="dt-stat-label">你对他错 <span class="dt-stat-hint" style="color: var(--coming)">需校准</span></div>
          </div>
          <div class="dt-stat-card">
            <div class="dt-stat-num" style="color: var(--main-delete)">{{ twinData.stats.both_wrong || 0 }}</div>
            <div class="dt-stat-label">你错他错 <span class="dt-stat-hint" style="color: var(--main-delete)">偏难</span></div>
          </div>
          <div
            v-if="twinData.stats.pending_records !== undefined && twinData.stats.batch_update_size !== undefined"
            class="dt-stat-card"
          >
            <div class="dt-stat-num" style="font-size: 22px; color: var(--purple)">
              {{ twinData.stats.pending_records }}/{{ twinData.stats.batch_update_size }}
            </div>
            <div class="dt-stat-label">
              {{ twinData.stats.pending_batch ? '待更新 批次已满' : `待批次更新（${twinData.stats.batch_update_size}条触发）` }}
            </div>
          </div>
        </div>

        <!-- 趋势图 -->
        <div v-if="!loading && twinData?.status?.exists" class="dt-section-card">
          <div class="dt-card-header">
            <h2><el-icon><TrendCharts /></el-icon> 学习趋势对比</h2>
            <span class="dt-subtitle">用户 vs 孪生 正确率变化</span>
          </div>
          <div ref="trendChartRef" class="dt-chart-container" style="height: 280px;"></div>
        </div>

        <!-- 诊断提示 -->
        <div v-if="!loading && diagnosisBoxes.length" class="dt-diagnosis-list">
          <div
            v-for="(box, idx) in diagnosisBoxes"
            :key="idx"
            class="dt-diagnosis-box"
            :class="box.type"
          >
            <el-icon :size="16" style="flex-shrink: 0; margin-right: 6px;">
              <WarningFilled v-if="box.type === 'warning'" />
              <InfoFilled v-else-if="box.type === 'info'" />
              <SuccessFilled v-else />
            </el-icon>
            <span v-html="box.html"></span>
          </div>
        </div>

        <!-- 薄弱知识点 -->
        <div
          v-if="!loading && twinData?.stats?.weak_knowledge_points?.length"
          class="dt-section-card"
        >
          <div class="dt-card-header">
            <h2><el-icon><Warning /></el-icon> 薄弱知识点</h2>
            <span class="dt-subtitle">你错他对的知识点</span>
          </div>
          <div class="dt-tag-list">
            <span
              v-for="kp in twinData.stats.weak_knowledge_points"
              :key="kp"
              class="dt-tag dt-tag-danger"
            >{{ kp }}</span>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="!loading && !twinData" class="dt-empty-state">
          <img src="@/assets/image/emptyStatus.png" alt="empty" class="dt-empty-img" />
          <p>加载孪生数据后查看总览</p>
        </div>
      </div>

      <!-- ==================== TAB: 孪生画像 ==================== -->
      <div v-show="activeTab === 'profile'" class="dt-tab-content">
        <!-- 雷达图 -->
        <div class="dt-section-card">
          <div class="dt-card-header">
            <h2><el-icon><DataAnalysis /></el-icon> 八维能力雷达</h2>
            <span class="dt-subtitle">基于特征提取器的8维度评分</span>
          </div>
          <div ref="radarChartRef" class="dt-chart-container" style="height: 360px;"></div>
        </div>

        <!-- 知识点掌握度 -->
        <div class="dt-section-card">
          <div class="dt-card-header">
            <h2><el-icon><Collection /></el-icon> 知识点掌握度</h2>
            <span class="dt-subtitle">共 {{ masteryEntries.length }} 个知识点</span>
          </div>
          <div v-if="masteryEntries.length" class="dt-kp-grid">
            <div v-for="[kp, val] in masteryEntries" :key="kp" class="dt-kp-item">
              <span class="dt-kp-name" :title="kp">{{ kp }}</span>
              <div class="dt-kp-bar">
                <div
                  class="dt-kp-fill"
                  :style="{ width: Math.round(val * 100) + '%', background: masteryColor(val) }"
                ></div>
              </div>
              <span class="dt-kp-val" :style="{ color: masteryColor(val) }">{{ Math.round(val * 100) }}%</span>
            </div>
          </div>
          <div v-else class="dt-empty-state" style="padding: 24px;">
            <p>暂无掌握度数据</p>
          </div>
        </div>

        <!-- 孪生参数 -->
        <div class="dt-section-card">
          <div class="dt-card-header">
            <h2><el-icon><Setting /></el-icon> 孪生参数</h2>
          </div>
          <div v-if="twinProfile" class="dt-params-grid">
            <div class="dt-param-item">
              <span class="dt-param-label">综合评分</span>
              <span class="dt-param-value">{{ twinProfile.overall_score ?? '--' }}</span>
            </div>
            <div class="dt-param-item">
              <span class="dt-param-label">猜对概率 P(G)</span>
              <span class="dt-param-value">{{ twinProfile.guess_probability ?? '--' }}</span>
            </div>
            <div class="dt-param-item">
              <span class="dt-param-label">失误概率 P(S)</span>
              <span class="dt-param-value">{{ twinProfile.slip_probability ?? '--' }}</span>
            </div>
            <div class="dt-param-item">
              <span class="dt-param-label">信心因子</span>
              <span class="dt-param-value">{{ twinProfile.confidence_factor ?? '--' }}</span>
            </div>
            <div class="dt-param-item">
              <span class="dt-param-label">特征来源</span>
              <span class="dt-param-value">
                <el-icon v-if="twinProfile.feature_source" color="var(--pass)"><CircleCheckFilled /></el-icon>
                <el-icon v-else color="var(--main-delete)"><CircleCloseFilled /></el-icon>
                {{ twinProfile.feature_source ? '已加载' : '未加载' }}
              </span>
            </div>
            <div class="dt-param-item">
              <span class="dt-param-label">掌握度来源</span>
              <span class="dt-param-value">
                <el-icon v-if="twinProfile.mastery_source" color="var(--pass)"><CircleCheckFilled /></el-icon>
                <el-icon v-else color="var(--main-delete)"><CircleCloseFilled /></el-icon>
                {{ twinProfile.mastery_source ? '已加载' : '未加载' }}
              </span>
            </div>
          </div>
          <div v-if="twinProfile?.error_patterns && Object.keys(twinProfile.error_patterns).length" class="dt-error-patterns">
            <strong>错误模式分布:</strong>
            <span>{{ JSON.stringify(twinProfile.error_patterns) }}</span>
          </div>
          <div v-if="!twinProfile" class="dt-empty-state" style="padding: 24px;">
            <p>生未构建</p>
          </div>
        </div>
      </div>

      <!-- ==================== TAB: 对比历史 ==================== -->
      <div v-show="activeTab === 'history'" class="dt-tab-content">
        <div class="dt-section-card">
          <div class="dt-card-header">
            <h2><el-icon><List /></el-icon> 对比历史</h2>
            <div class="dt-history-actions">
              <el-select v-model="historyFilter" placeholder="全部类型" size="small" @change="loadHistory" style="width: 160px;">
                <el-option label="全部类型" value="" />
                <el-option label="你对他对" value="both_correct" />
                <el-option label="你错他错" value="both_wrong" />
                <el-option label="你对他错" value="user_right_twin_wrong" />
                <el-option label="你错他对" value="user_wrong_twin_right" />
              </el-select>
              <button class="dt-btn dt-btn-danger dt-btn-sm" @click="clearHistory">清空历史</button>
            </div>
          </div>

          <div v-if="historyLoading" class="dt-loading">
            <div class="dt-spinner"></div>
            <p>正在加载...</p>
          </div>

          <div v-else-if="historyList.length" class="dt-history-list">
            <div
              v-for="(r, displayIdx) in reversedHistory"
              :key="r.timestamp + '-' + displayIdx"
              class="dt-history-entry"
            >
              <!-- 头行 -->
              <div class="dt-history-header">
                <el-icon :size="20" :color="resultInfo(r.result_type).color">
                  <component :is="resultInfo(r.result_type).icon"></component>
                </el-icon>
                <div class="dt-history-header-info">
                  <div class="dt-history-header-label">{{ resultInfo(r.result_type).label }}</div>
                  <div class="dt-history-header-meta">
                    {{ r.knowledge_point || '--' }} · {{ formatTime(r.timestamp) }}
                  </div>
                </div>
                <div class="dt-history-confidence">
                  <div class="dt-confidence-label">孪生信心</div>
                  <div class="dt-confidence-value" :style="{ color: resultInfo(r.result_type).color }">
                    {{ r.twin_confidence ? Math.round(r.twin_confidence * 100) + '%' : '--' }}
                  </div>
                </div>
              </div>

              <!-- 答案卡片 -->
              <div class="dt-answer-cards">
                <div v-if="r.question_content" class="dt-question-block">
                  <strong>题目：</strong>
                  <span v-if="r.question_content.length > 120">
                    <span v-if="!isQuestionExpanded(getOrigIdx(displayIdx))">
                      {{ r.question_content.slice(0, 120) }}...
                      <a href="javascript:void(0)" class="dt-toggle-link" @click.stop="toggleQuestion(getOrigIdx(displayIdx))">展开</a>
                    </span>
                    <span v-else>
                      {{ r.question_content }}
                      <a href="javascript:void(0)" class="dt-toggle-link" @click.stop="toggleQuestion(getOrigIdx(displayIdx))">收起</a>
                    </span>
                  </span>
                  <span v-else>{{ r.question_content }}</span>
                </div>
                <div v-if="r.question_options?.length" class="dt-options-block">
                  <div
                    v-for="(opt, oi) in r.question_options"
                    :key="oi"
                    class="dt-option-item"
                  >
                    <span class="dt-option-letter">{{ String.fromCharCode(65 + oi) }}.</span>
                    <span>{{ opt }}</span>
                  </div>
                </div>
                <div class="dt-answer-item dt-answer-user">
                  <strong>你的答案：</strong>
                  <span>{{ r.user_answer ?? '--' }}</span>
                </div>
                <div class="dt-answer-item dt-answer-twin">
                  <strong>孪生答案：</strong>
                  <span>{{ r.twin_answer ?? '--' }}</span>
                </div>
                <div v-if="r.correct_answer" class="dt-answer-item dt-answer-correct">
                  <strong>正确答案：</strong>
                  <span>{{ r.correct_answer }}</span>
                </div>
              </div>

              <!-- 分析 -->
              <div class="dt-analysis-row">
                <button
                  class="dt-btn dt-btn-primary dt-btn-sm"
                  :disabled="analyzingOrigIdx === getOrigIdx(displayIdx)"
                  @click="analyzeRecord(getOrigIdx(displayIdx), r)"
                >
                  {{ analyzingOrigIdx === getOrigIdx(displayIdx) ? '分析中...' : (analysisResults[getOrigIdx(displayIdx)]?.visible ? '收起分析' : '分析') }}
                </button>
              </div>

              <div
                v-if="analysisResults[getOrigIdx(displayIdx)]?.visible"
                class="dt-analysis-panel"
              >
                <div v-if="analysisResults[getOrigIdx(displayIdx)]?.loading" class="dt-loading-sm">
                  <div class="dt-spinner-sm"></div>
                  <span>正在生成分析...</span>
                </div>
                <template v-else-if="analysisResults[getOrigIdx(displayIdx)]?.data">
                  <!-- 答案对比 -->
                  <div v-if="analysisResults[getOrigIdx(displayIdx)].data.visual_data" class="dt-visual-comparison">
                    <div
                      class="dt-visual-card"
                      :class="analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.user.correct ? 'dt-vc-correct' : 'dt-vc-wrong'"
                    >
                      <div class="dt-vc-label">你的答案</div>
                      <div class="dt-vc-answer">{{ analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.user.answer }}</div>
                      <div class="dt-vc-status">
                        {{ analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.user.correct ? '正确' : '错误' }}
                      </div>
                    </div>
                    <div
                      class="dt-visual-card"
                      :class="analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.twin.correct ? 'dt-vc-correct' : 'dt-vc-wrong-twin'"
                    >
                      <div class="dt-vc-label">孪生答案</div>
                      <div class="dt-vc-answer">{{ analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.twin.answer }}</div>
                      <div class="dt-vc-status">
                        {{ analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.twin.correct ? '正确' : '错误' }}
                      </div>
                    </div>
                    <div
                      v-if="analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.correct_answer && analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.correct_answer !== '—'"
                      class="dt-visual-card dt-vc-correct-answer"
                    >
                      <div class="dt-vc-label">正确答案</div>
                      <div class="dt-vc-answer">{{ analysisResults[getOrigIdx(displayIdx)].data.visual_data.comparison.correct_answer }}</div>
                    </div>
                  </div>

                  <!-- 指标进度条 -->
                  <div v-if="analysisResults[getOrigIdx(displayIdx)].data.visual_data?.metrics" class="dt-metrics-bars">
                    <div
                      v-for="(bar, bi) in metricBars(analysisResults[getOrigIdx(displayIdx)].data.visual_data.metrics, analysisResults[getOrigIdx(displayIdx)].data.visual_data.knowledge_point)"
                      :key="bi"
                      class="dt-metric-row"
                    >
                      <span class="dt-metric-label">{{ bar.label }}</span>
                      <div class="dt-metric-bar-bg">
                        <div
                          class="dt-metric-bar-fill"
                          :style="{ width: bar.pct + '%', background: bar.color }"
                        ></div>
                      </div>
                      <span class="dt-metric-pct" :style="{ color: bar.color }">{{ bar.pct }}%</span>
                    </div>
                  </div>

                  <!-- 分析文字 -->
                  <div class="dt-analysis-text" v-html="analysisResults[getOrigIdx(displayIdx)].data.analysis_text"></div>
                </template>
                <div v-else-if="analysisResults[getOrigIdx(displayIdx)]?.error" class="dt-analysis-error">
                  {{ analysisResults[getOrigIdx(displayIdx)].error }}
                </div>
              </div>
            </div>
          </div>

          <div v-else class="dt-empty-state" style="padding: 40px;">
            <img src="@/assets/image/emptyStatus.png" alt="empty" class="dt-empty-img" />
            <p>暂无对比记录</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

import {
  getDigitalTwinApi,
  toggleDigitalTwinApi,
  buildDigitalTwinStream,
  getComparisonApi,
  analyzeRecordApi,
  clearHistoryApi
} from '@/api/mainApi/digitalTwins'

const props = defineProps({
  visible: { type: Boolean, default: false },
  userId: { type: String, default: '' }
})

const emit = defineEmits(['close'])

// ==================== Tab ====================
const tabs = [
  { key: 'overview', label: '总览' },
  { key: 'profile', label: '孪生画像' },
  { key: 'history', label: '对比历史' }
]
const activeTab = ref('overview')

function switchTab(key) {
  activeTab.value = key
  nextTick(() => {
    if (key === 'profile') initRadarChart()
    if (key === 'overview') initTrendChart()
  })
}

// ==================== 数据 ====================
const twinData = ref(null)
const loading = ref(false)
const isBuilding = ref(false)
const historyList = ref([])
const historyLoading = ref(false)
const historyFilter = ref('')
const analyzingOrigIdx = ref(-1)
const analysisResults = ref({})
const expandedQuestions = ref(new Set())

// 构建进度弹窗状态
const buildOverlayVisible = ref(false)
const buildProgress = ref(0)
const buildProgressLabel = ref('0%')
const buildStepLabel = ref('初始化...')
const buildStatusLines = ref([])

let radarChartInstance = null
let trendChartInstance = null

// ==================== 计算属性 ====================
const twinStatusClass = computed(() => {
  if (!twinData.value) return 'dt-status-inactive'
  return twinData.value.status.exists ? 'dt-status-active' : 'dt-status-inactive'
})

const statusTitle = computed(() => {
  if (!twinData.value) return '尚未构建孪生'
  return twinData.value.status.exists ? '孪生已构建' : '尚未构建孪生'
})

const statusDesc = computed(() => {
  if (!twinData.value) return '输入用户ID后点击"加载"，然后构建你的数字孪生'
  if (twinData.value.status.exists) {
    const profile = twinData.value.status.profile || {}
    const builtAt = profile.built_at ? profile.built_at.replace('T', ' ').substring(0, 19) : '未知'
    return `构建时间: ${builtAt} | 综合评分: ${profile.overall_score || '--'}`
  }
  return '点击"构建孪生"按钮，系统将基于你的特征和知识掌握度创建数字分身'
})

const twinProfile = computed(() => twinData.value?.status?.profile || null)

const DIMENSION_NAMES = ['学术背景', '学习行为', '目标动机', '认知能力', '情绪状态', '社交互动', '时间管理', '创新创造']

const masteryEntries = computed(() => {
  const mastery = twinProfile.value?.knowledge_mastery
  if (!mastery) return []
  const nonKp = new Set([
    'fill_blank', 'judge', 'multiple_choice', 'short_answer',
    'single_choice', 'rag_knowledge', 'true_false', 'completion',
    'essay', 'matching', 'ordering', 'code_completion'
  ])
  return Object.entries(mastery)
    .filter(([kp]) => {
      if (nonKp.has(kp)) return false
      if (kp.trim().length <= 1) return false
      if (kp.includes('帮我复习') || kp.includes('rag_')) return false
      return true
    })
    .sort((a, b) => a[0].localeCompare(b[0]))
})

function masteryColor(val) {
  const pct = Math.round(val * 100)
  if (pct >= 80) return 'var(--pass)'
  if (pct >= 60) return 'var(--primary)'
  if (pct >= 40) return 'var(--coming)'
  return 'var(--main-delete)'
}

const reversedHistory = computed(() => [...historyList.value].reverse())

const diagnosisBoxes = computed(() => {
  const stats = twinData.value?.stats
  if (!stats || !stats.exists || !stats.total) return []
  const boxes = []
  if (stats.user_wrong_twin_right > stats.total * 0.3) {
    boxes.push({
      type: 'warning',
      html: `检测到较多"你错他对"的情况（<strong>${stats.user_wrong_twin_right_pct}%</strong>），表明存在明显的知识盲区，建议重点关注薄弱知识点。`
    })
  }
  if (stats.user_right_twin_wrong > stats.total * 0.3) {
    boxes.push({
      type: 'info',
      html: `检测到较多"你对他错"的情况（<strong>${stats.user_right_twin_wrong_pct}%</strong>），孪生画像可能需要校准。`
    })
  }
  if (stats.pending_batch) {
    boxes.push({
      type: 'warning',
      html: `<strong>孪生特征待更新:</strong> 已累积 ${stats.pending_records} 条新对比记录（触发阈值 ${stats.batch_update_size} 条），系统将在下次对比时自动执行批量特征更新。`
    })
  } else if (stats.batch_update_at) {
    const batchTime = stats.batch_update_at.replace('T', ' ').substring(0, 16)
    boxes.push({
      type: 'info',
      html: `<strong>孪生特征已更新:</strong> 上次批次更新于 ${batchTime}，累积 ${stats.pending_records} 条待处理记录（${stats.batch_update_size}条触发批量更新）。`
    })
  }
  return boxes
})

// ==================== 结果类型映射 ====================
const resultTypeMap = {
  both_correct: { icon: 'CircleCheckFilled', label: '你对他对，掌握一致', color: 'var(--pass)' },
  both_wrong: { icon: 'CircleCloseFilled', label: '你错他错，题目偏难', color: 'var(--main-delete)' },
  user_right_twin_wrong: { icon: 'RefreshRight', label: '你对他错，生需校准', color: 'var(--coming)' },
  user_wrong_twin_right: { icon: 'Warning', label: '你错他对，发现知识盲区', color: 'var(--primary)' }
}

function resultInfo(type) {
  return resultTypeMap[type] || { icon: 'QuestionFilled', label: type, color: 'var(--text-gray)' }
}

// ==================== 指标条 ====================
function metricBars(metrics, kp) {
  const bars = []
  if (metrics.match_degree?.pct !== undefined && metrics.match_degree?.pct !== null) {
    bars.push({ label: '匹配度', pct: metrics.match_degree.pct, color: metrics.match_degree.color || 'var(--primary)' })
  }
  if (metrics.twin_confidence?.pct !== undefined && metrics.twin_confidence?.pct !== null) {
    bars.push({ label: '孪生信心', pct: metrics.twin_confidence.pct, color: metrics.twin_confidence.color || 'var(--coming)' })
  }
  if (metrics.kp_mastery?.pct !== undefined && metrics.kp_mastery?.pct !== null) {
    bars.push({ label: (kp || '知识点') + ' 掌握度', pct: metrics.kp_mastery.pct, color: metrics.kp_mastery.color || 'var(--primary)' })
  }
  if (metrics.difficulty !== undefined && metrics.difficulty !== null) {
    const d = metrics.difficulty
    bars.push({ label: '题目难度', pct: d, color: d >= 70 ? 'var(--main-delete)' : d >= 40 ? 'var(--coming)' : 'var(--pass)' })
  }
  return bars
}

// ==================== 时间格式化 ====================
function formatTime(ts) {
  if (!ts) return '--'
  return ts.replace('T', ' ').substring(0, 16)
}

// 获取原始索引（reversed 后的 displayIdx -> 原始数组索引）
function getOrigIdx(displayIdx) {
  return historyList.value.length - 1 - displayIdx
}

// 展开/收起题目
function toggleQuestion(origIdx) {
  if (expandedQuestions.value.has(origIdx)) {
    expandedQuestions.value.delete(origIdx)
  } else {
    expandedQuestions.value.add(origIdx)
  }
  expandedQuestions.value = new Set(expandedQuestions.value)
}

function isQuestionExpanded(origIdx) {
  return expandedQuestions.value.has(origIdx)
}

// ==================== 数据加载 ====================
async function loadTwin() {
  if (!props.userId) return
  loading.value = true
  twinData.value = null
  try {
    const data = await getDigitalTwinApi(props.userId)
    if (!data.success) throw new Error(data.detail || '加载失败')
    twinData.value = data
    nextTick(() => {
      initTrendChart()
    })
  } catch (e) {
    console.error('加载孪生数据失败:', e)
    ElMessage.error('加载失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// ==================== 孪生开关 ====================
async function toggleTwin(enabled) {
  if (!props.userId) return
  try {
    await toggleDigitalTwinApi(props.userId, enabled)
    if (enabled) loadTwin()
  } catch (e) {
    console.error('切换孪生失败:', e)
  }
}

// ==================== 构建孪生 ====================
function showBuildOverlay() {
  buildOverlayVisible.value = true
  buildProgress.value = 0
  buildProgressLabel.value = '0%'
  buildStepLabel.value = '初始化...'
  buildStatusLines.value = []
}

function hideBuildOverlay() {
  buildOverlayVisible.value = false
}

function addBuildStatusLine(dotClass, message, detail, pct) {
  buildStatusLines.value.push({
    dotClass,
    message,
    detail,
    pct
  })
}

async function buildTwin() {
  if (!props.userId || isBuilding.value) return
  isBuilding.value = true

  showBuildOverlay()

  try {
    const resp = await buildDigitalTwinStream(props.userId)
    if (!resp.ok) throw new Error('HTTP ' + resp.status)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))

          // 更新进度条
          const pct = event.progress || 0
          buildProgress.value = pct
          buildProgressLabel.value = pct + '%'
          buildStepLabel.value = event.message || ''

          // 添加状态行
          const dotClass = event.status === 'complete' ? 'done'
                         : event.status === 'error' ? 'error'
                         : 'running'
          addBuildStatusLine(dotClass, event.message, event.detail || '', pct + '%')

          // 构建完成
          if (event.status === 'complete') {
            buildStepLabel.value = '完成！'
            setTimeout(() => {
              hideBuildOverlay()
              loadTwin()
            }, 1500)
            return
          }

          // 构建出错
          if (event.status === 'error') {
            buildStepLabel.value = '构建出错'
            setTimeout(() => {
              hideBuildOverlay()
              ElMessage.error('构建失败: ' + (event.message || '未知错误'))
            }, 2000)
            return
          }
        } catch (e) {
          console.warn('SSE parse error:', e)
        }
      }
    }
  } catch (e) {
    hideBuildOverlay()
    ElMessage.error('构建失败: ' + e.message)
  } finally {
    isBuilding.value = false
  }
}

// ==================== 对比历史 ====================
async function loadHistory() {
  if (!props.userId) return
  historyLoading.value = true
  try {
    const params = { limit: 50 }
    if (historyFilter.value) params.result_type = historyFilter.value
    const data = await getComparisonApi(props.userId, params)
    if (!data.success) throw new Error('加载失败')
    historyList.value = data.history || []
  } catch (e) {
    console.error('加载历史失败:', e)
    historyList.value = []
  } finally {
    historyLoading.value = false
  }
}

async function clearHistory() {
  if (!props.userId) return
  if (!confirm('确定清空所有对比历史？')) return
  try {
    await clearHistoryApi(props.userId)
    historyList.value = []
    await loadTwin()
  } catch (e) {
    console.error('清空历史失败:', e)
  }
}

// ==================== 分析记录 ====================
async function analyzeRecord(origIdx, record) {
  const key = origIdx
  if (analysisResults.value[key]?.visible) {
    analysisResults.value[key].visible = false
    return
  }

  analyzingOrigIdx.value = origIdx
  analysisResults.value[key] = { visible: true, loading: true, data: null, error: null }

  try {
    const data = await analyzeRecordApi(props.userId, origIdx)
    if (data.success) {
      analysisResults.value[key] = { visible: true, loading: false, data, error: null }
    } else {
      analysisResults.value[key] = { visible: true, loading: false, data: null, error: '分析失败: ' + (data.analysis || '未知错误') }
    }
  } catch (e) {
    analysisResults.value[key] = { visible: true, loading: false, data: null, error: '请求失败: ' + e.message }
  } finally {
    analyzingOrigIdx.value = -1
  }
}

// ==================== ECharts ====================
const radarChartRef = ref(null)
const trendChartRef = ref(null)

function getChartTheme() {
  // 数字孪生页面始终是深色背景，所以始终使用浅色文字
  return {
    textColor: '#E2E8F0',
    axisColor: '#475569',
    splitColor: '#334155',
    bgColor: '#1E293B',
    tooltipBg: 'rgba(30,41,59,0.95)',
    tooltipBorder: '#334155',
    tooltipText: '#E2E8F0',
    primary: '#3B82F6',
    coming: '#FB923C',
  }
}

function initRadarChart() {
  if (!radarChartRef.value) return
  const profile = twinProfile.value
  if (!profile?.dimension_scores || profile.dimension_scores.length !== 8) return

  if (!radarChartInstance) {
    radarChartInstance = echarts.init(radarChartRef.value)
  }

  const theme = getChartTheme()

  radarChartInstance.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: theme.tooltipBg,
      borderColor: theme.tooltipBorder,
      textStyle: { color: theme.tooltipText, fontSize: 12 }
    },
    legend: {
      data: [{ name: '你', icon: 'roundRect' }],
      bottom: 0,
      textStyle: { fontSize: 12, color: 'rgba(255,255,255,0.8)' },
      itemStyle: { color: 'rgba(255,255,255,0.8)' }
    },
    radar: {
      indicator: DIMENSION_NAMES.map(name => ({ name, max: 100 })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: 'rgba(255,255,255,0.7)', fontSize: 11 },
      splitArea: {
        areaStyle: {
          color: ['rgba(255,255,255,0.03)', 'rgba(255,255,255,0.06)']
        }
      },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.15)' } }
    },
    series: [{
      type: 'radar',
      name: '你',
      data: [{
        value: profile.dimension_scores,
        areaStyle: { color: 'rgba(255,255,255,0.12)' },
        lineStyle: { color: 'rgba(255,255,255,0.8)', width: 2 },
        itemStyle: { color: '#fff' }
      }]
    }]
  }, true)
}

function initTrendChart() {
  if (!trendChartRef.value) return
  if (!twinData.value?.status?.exists) return

  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChartRef.value)
  }

  getComparisonApi(props.userId, { limit: 200 }).then(data => {
    const history = data.history || []
    if (history.length < 2) {
      // 数据不足，显示空状态
      trendChartInstance.clear()
      trendChartInstance.setOption({
        graphic: {
          elements: [{
            type: 'text',
            left: 'center',
            top: 'middle',
            style: {
              text: '暂无足够数据，继续学习后将自动生成对比曲线',
              fontSize: 14,
              fill: getChartTheme().textColor
            }
          }]
        }
      })
      return
    }

    const labels = history.map((_, i) => '#' + (i + 1))
    const correctRate = (arr, idx) => {
      const slice = arr.slice(0, idx + 1)
      return Math.round(slice.filter(Boolean).length / slice.length * 100)
    }
    const userData = history.map((_, i) => correctRate(history.map(r => r.user_correct), i))
    const twinData2 = history.map((_, i) => correctRate(history.map(r => r.twin_correct), i))

    const theme = getChartTheme()

    trendChartInstance.setOption({
      tooltip: {
        trigger: 'axis',
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: theme.tooltipText, fontSize: 12 }
      },
      legend: {
        data: ['用户', '孪生'],
        bottom: 0,
        itemWidth: 20,
        itemHeight: 3,
        textStyle: { fontSize: 12, color: theme.textColor }
      },
      grid: { left: '4%', right: '5%', top: '10%', bottom: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: theme.axisColor } },
        axisTick: { show: false },
        axisLabel: { fontSize: 11, color: theme.textColor, interval: 'auto' }
      },
      yAxis: {
        type: 'value',
        min: 0, max: 100, interval: 25,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: theme.splitColor, type: 'dashed' } },
        axisLabel: { formatter: '{value}%', fontSize: 11, color: theme.textColor }
      },
      series: [
        {
          name: '用户',
          type: 'line',
          data: userData,
          smooth: 0.4,
          symbol: 'circle',
          symbolSize: 6,
          showSymbol: false,
          emphasis: { focus: 'series', itemStyle: { borderWidth: 2, borderColor: theme.bgColor } },
          lineStyle: { width: 2.5, color: 'var(--primary)', shadowColor: 'rgba(45,125,219,0.3)', shadowBlur: 8, shadowOffsetY: 3 },
          itemStyle: { color: 'var(--primary)' },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(45,125,219,0.25)' },
                { offset: 1, color: 'rgba(45,125,219,0.02)' }
              ]
            }
          }
        },
        {
          name: '孪生',
          type: 'line',
          data: twinData2,
          smooth: 0.4,
          symbol: 'circle',
          symbolSize: 6,
          showSymbol: false,
          emphasis: { focus: 'series', itemStyle: { borderWidth: 2, borderColor: theme.bgColor } },
          lineStyle: { width: 2.5, color: 'var(--coming)', shadowColor: 'rgba(230,162,60,0.3)', shadowBlur: 8, shadowOffsetY: 3 },
          itemStyle: { color: 'var(--coming)' },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(230,162,60,0.2)' },
                { offset: 1, color: 'rgba(230,162,60,0.02)' }
              ]
            }
          }
        }
      ]
    }, true)
  }).catch(() => {})
}

// ==================== 窗口 resize ====================
function handleResize() {
  radarChartInstance?.resize()
  trendChartInstance?.resize()
}

// ==================== 生命周期 ====================
watch(() => props.userId, (val) => {
  if (val) loadTwin()
}, { immediate: true })

watch(activeTab, (val) => {
  nextTick(() => {
    if (val === 'profile') initRadarChart()
    if (val === 'overview') initTrendChart()
    if (val === 'history' && !historyList.value.length) loadHistory()
  })
})

watch(() => props.visible, (val) => {
  if (val) {
    // 打开时重置到初始状态
    activeTab.value = 'overview'
    loadTwin()
    nextTick(() => {
      initTrendChart()
      trendChartInstance?.resize()
    })
  } else {
    // 关闭时清理所有状态
    radarChartInstance?.dispose()
    trendChartInstance?.dispose()
    radarChartInstance = null
    trendChartInstance = null
    activeTab.value = 'overview'
    twinData.value = null
    historyList.value = []
    analysisResults.value = {}
    expandedQuestions.value = new Set()
  }
}, { immediate: true })

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
/* ==================== 页面布局 ==================== */
.dt-page {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e293b 100%);
  z-index: 1000;
  overflow: hidden;
}

/* ==================== Tab 栏 ==================== */
.dt-tab-bar {
  display: flex;
  background: rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 10;
  flex-shrink: 0;
}

.dt-tab {
  padding: 14px 24px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255,255,255,0.6);
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
  user-select: none;
}

.dt-tab:hover {
  color: #fff;
}

.dt-tab.active {
  color: #fff;
  border-bottom-color: var(--primary);
  font-weight: 600;
}

.dt-tab-close {
  margin-left: auto;
  padding: 14px 16px;
  cursor: pointer;
  color: rgba(255,255,255,0.6);
  transition: all 0.2s;
  display: flex;
  align-items: center;
}

.dt-tab-close:hover {
  color: #fff;
  background: rgba(255,255,255,0.12);
}

/* ==================== 容器 ==================== */
.dt-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px 260px;
  margin: 0 auto;
  width: 100%;
}

/* ==================== 状态横幅 ==================== */
.dt-status-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.dt-status-active {
  background: rgba(74, 222, 128, 0.1);
  border: 1px solid rgba(74, 222, 128, 0.3);
}

.dt-status-inactive {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
}

.dt-status-icon {
  color: rgba(255,255,255,0.6);
}

.dt-status-active .dt-status-icon {
  color: var(--pass);
}

.dt-status-text {
  flex: 1;
}

.dt-status-text h3 {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 2px;
}

.dt-status-text p {
  font-size: 13px;
  color: rgba(255,255,255,0.6);
}

/* ==================== 按钮 ==================== */
.dt-btn {
  padding: 8px 18px;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  white-space: nowrap;
}

.dt-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dt-btn-primary {
  background: var(--primary);
  color: #fff;
}

.dt-btn-primary:hover:not(:disabled) {
  background: var(--primary-hv);
}

.dt-btn-danger {
  background: var(--main-delete);
  color: #fff;
}

.dt-btn-danger:hover:not(:disabled) {
  background: var(--main-delete-hover);
}

.dt-btn-sm {
  padding: 5px 12px;
  font-size: 12px;
}

/* ==================== 统计卡片 ==================== */
.dt-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.dt-stat-card {
  background: rgba(255,255,255,0.05);
  border-radius: var(--radius-lg);
  padding: 16px;
  text-align: center;
  border: 1px solid rgba(255,255,255,0.08);
}

.dt-stat-num {
  font-size: 28px;
  font-weight: 700;
}

.dt-stat-label {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  margin-top: 4px;
}

.dt-stat-hint {
  font-size: 11px;
  font-weight: 600;
}

/* ==================== 区段卡片 ==================== */
.dt-section-card {
  background: rgba(255,255,255,0.05);
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid rgba(255,255,255,0.08);
  margin-bottom: 16px;
}

.dt-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.dt-card-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dt-subtitle {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  font-weight: 400;
}

/* ==================== 图表 ==================== */
.dt-chart-container {
  width: 100%;
}

/* ==================== 诊断提示 ==================== */
.dt-diagnosis-list {
  margin-bottom: 16px;
}

.dt-diagnosis-box {
  display: flex;
  align-items: flex-start;
  padding: 14px 18px;
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 1.5;
  color: rgba(255,255,255,0.8);
}

.dt-diagnosis-box.warning {
  background: rgba(251, 146, 60, 0.1);
  border-left: 4px solid var(--coming);
}

.dt-diagnosis-box.info {
  background: rgba(59, 130, 246, 0.1);
  border-left: 4px solid var(--primary);
}

.dt-diagnosis-box.success {
  background: rgba(74, 222, 128, 0.1);
  border-left: 4px solid var(--pass);
}

/* ==================== 标签 ==================== */
.dt-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dt-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
}

.dt-tag-danger {
  background: rgba(245, 108, 108, 0.15);
  color: var(--main-delete);
}

/* ==================== 知识点掌握度 ==================== */
.dt-kp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.dt-kp-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.05);
}

.dt-kp-name {
  font-size: 13px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(255,255,255,0.8);
}

.dt-kp-bar {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  overflow: hidden;
}

.dt-kp-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s;
}

.dt-kp-val {
  font-size: 12px;
  font-weight: 600;
  width: 34px;
  text-align: right;
}

/* ==================== 生参数 ==================== */
.dt-params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.dt-param-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255,255,255,0.05);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.dt-param-label {
  color: rgba(255,255,255,0.6);
}

.dt-param-value {
  font-weight: 600;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 4px;
}

.dt-error-patterns {
  margin-top: 12px;
  padding: 10px;
  background: rgba(255,255,255,0.05);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  line-height: 1.6;
}

/* ==================== 对比历史 ==================== */
.dt-history-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.dt-history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dt-history-entry {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: rgba(255,255,255,0.03);
}

.dt-history-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.05);
}

.dt-history-header-info {
  flex: 1;
  min-width: 0;
}

.dt-history-header-label {
  font-weight: 500;
  color: #fff;
  font-size: 13px;
}

.dt-history-header-meta {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  margin-top: 2px;
}

.dt-history-confidence {
  text-align: right;
  flex-shrink: 0;
}

.dt-confidence-label {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
}

.dt-confidence-value {
  font-size: 14px;
  font-weight: 600;
}

/* 答案卡片 */
.dt-answer-cards {
  padding: 8px 12px 4px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dt-question-block {
  width: 100%;
  padding: 6px 10px;
  background: rgba(255,255,255,0.05);
  border-radius: var(--radius-md);
  color: rgba(255,255,255,0.8);
  font-size: 13px;
  line-height: 1.5;
}

.dt-toggle-link {
  color: var(--primary);
  font-size: 11px;
  cursor: pointer;
  text-decoration: none;
  margin-left: 4px;
}

.dt-toggle-link:hover {
  text-decoration: underline;
}

.dt-options-block {
  width: 100%;
  padding: 4px 10px;
}

.dt-option-item {
  font-size: 12px;
  color: rgba(255,255,255,0.8);
  padding: 2px 0;
  display: flex;
  gap: 4px;
}

.dt-option-letter {
  display: inline-block;
  width: 20px;
  font-weight: 600;
  color: var(--primary);
  flex-shrink: 0;
}

.dt-answer-item {
  flex: 1;
  min-width: 120px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  font-size: 12px;
}

.dt-answer-user {
  background: rgba(74, 222, 128, 0.1);
}

.dt-answer-user strong {
  color: var(--pass);
}

.dt-answer-twin {
  background: rgba(251, 146, 60, 0.1);
}

.dt-answer-twin strong {
  color: var(--coming);
}

.dt-answer-correct {
  background: rgba(59, 130, 246, 0.1);
}

.dt-answer-correct strong {
  color: var(--primary);
}

.dt-answer-item span {
  color: rgba(255,255,255,0.8);
}

/* 分析 */
.dt-analysis-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 15px 20px;
}

.dt-analysis-panel {
  margin: 0 12px 12px;
  padding: 12px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255,255,255,0.8);
}

.dt-loading-sm {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  padding: 16px;
  color: rgba(255,255,255,0.6);
}

.dt-spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.1);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: dt-spin 0.8s linear infinite;
}

/* 可视化对比 */
.dt-visual-comparison {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.dt-visual-card {
  flex: 1;
  min-width: 100px;
  padding: 10px;
  border-radius: var(--radius-md);
  text-align: center;
}

.dt-vc-correct {
  background: rgba(74, 222, 128, 0.1);
}

.dt-vc-wrong {
  background: rgba(245, 108, 108, 0.1);
}

.dt-vc-wrong-twin {
  background: rgba(251, 146, 60, 0.1);
}

.dt-vc-correct-answer {
  background: rgba(59, 130, 246, 0.1);
}

.dt-vc-label {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 4px;
}

.dt-vc-answer {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
}

.dt-vc-status {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  margin-top: 4px;
}

.dt-vc-correct .dt-vc-answer { color: var(--pass); }
.dt-vc-wrong .dt-vc-answer { color: var(--main-delete); }
.dt-vc-wrong-twin .dt-vc-answer { color: var(--coming); }
.dt-vc-correct-answer .dt-vc-answer { color: var(--primary); }

/* 指标条 */
.dt-metrics-bars {
  margin-bottom: 10px;
}

.dt-metric-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.dt-metric-label {
  width: 80px;
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  text-align: right;
  flex-shrink: 0;
}

.dt-metric-bar-bg {
  flex: 1;
  height: 10px;
  border-radius: 5px;
  background: rgba(255,255,255,0.1);
  overflow: hidden;
}

.dt-metric-bar-fill {
  height: 100%;
  border-radius: 5px;
  transition: width 0.4s;
}

.dt-metric-pct {
  width: 34px;
  font-size: 11px;
  font-weight: 600;
  text-align: right;
  flex-shrink: 0;
}

/* 分析文字 */
.dt-analysis-text {
  background: rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255,255,255,0.8);
}

.dt-analysis-error {
  color: var(--main-delete);
  font-size: 12px;
}

/* ==================== 加载 & 空状态 ==================== */
.dt-loading {
  text-align: center;
  padding: 40px;
  color: rgba(255,255,255,0.6);
  font-size: 14px;
}

.dt-spinner {
  display: inline-block;
  width: 24px;
  height: 24px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: dt-spin 0.8s linear infinite;
  margin-bottom: 8px;
}

.dt-empty {
  text-align: center;
  padding: 80px 20px;
  color: rgba(255,255,255,0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.dt-empty p {
  font-size: 14px;
  margin: 0;
}

@keyframes dt-spin {
  to { transform: rotate(360deg); }
}

.dt-empty-state {
  text-align: center;
  padding: 40px 20px;
  color: rgba(255,255,255,0.6);
}

.dt-empty-img {
  width: 180px;
  height: auto;
  opacity: 0.8;
  margin-bottom: 12px;
}

.dt-empty-state p {
  font-size: 14px;
}

/* ==================== 构建进度弹窗 ==================== */
.dt-build-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dt-build-modal {
  background: #1e293b;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  padding: 32px;
  width: 620px;
  max-width: 92vw;
  max-height: 80vh;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  color: rgba(255,255,255,0.8);
}

.dt-build-modal h2 {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dt-build-subtitle {
  font-size: 13px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 20px;
}

.dt-progress-wrap {
  margin-bottom: 20px;
}

.dt-progress-bar-bg {
  height: 6px;
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
  overflow: hidden;
}

.dt-progress-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--grad-primary);
  transition: width 0.4s ease;
}

.dt-progress-text {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.6);
}

.dt-build-status-panel {
  background: rgba(255,255,255,0.05);
  border-radius: 10px;
  padding: 16px;
  max-height: 280px;
  overflow-y: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.dt-build-status-panel::-webkit-scrollbar {
  width: 4px;
}

.dt-build-status-panel::-webkit-scrollbar-track {
  background: transparent;
}

.dt-build-status-panel::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.2);
  border-radius: 2px;
}

.dt-status-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  animation: dt-statusFadeIn 0.3s ease forwards;
}

.dt-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.dt-status-dot.waiting {
  background: rgba(255,255,255,0.3);
}

.dt-status-dot.running {
  background: var(--primary);
  box-shadow: 0 0 8px var(--primary);
  animation: dt-dotPulse 1s ease-in-out infinite;
}

.dt-status-dot.done {
  background: var(--pass);
}

.dt-status-dot.error {
  background: var(--main-delete);
}

.dt-status-msg {
  flex: 1;
  color: rgba(255,255,255,0.8);
}

.dt-status-detail {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  margin-top: 2px;
}

.dt-status-pct {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  white-space: nowrap;
}

.dt-status-line.completed .dt-status-msg {
  color: var(--pass);
}

.dt-status-line.errored .dt-status-msg {
  color: var(--main-delete);
}

@keyframes dt-statusFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes dt-dotPulse {
  0%, 100% { box-shadow: 0 0 8px var(--primary); }
  50% { box-shadow: 0 0 16px var(--primary), 0 0 24px var(--primary); }
}

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
  .dt-tab-bar {
    padding: 0 12px;
    overflow-x: auto;
  }

  .dt-tab {
    padding: 12px 16px;
    font-size: 13px;
    white-space: nowrap;
  }

  .dt-container {
    padding: 16px 12px;
  }

  .dt-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .dt-kp-grid {
    grid-template-columns: 1fr;
  }

  .dt-params-grid {
    grid-template-columns: 1fr;
  }

  .dt-visual-comparison {
    flex-direction: column;
  }

  .dt-build-modal {
    padding: 20px;
    width: 100%;
    max-height: 90vh;
    border-radius: 12px;
  }

  .dt-build-status-panel {
    max-height: 200px;
  }
}
</style>

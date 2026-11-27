<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAllWeights, getCategoryWeights, updateCategoryWeights, resetWeights } from '@/api/backstage/adOpSetting.js'

const activeTab = ref('overview')
const loading = ref(false)
const statusMessage = ref('')
const statusType = ref('')

const route = useRoute()

const overviewData = ref(null)
const attentionData = ref(null)
const emotionData = ref(null)
const bridgeData = ref(null)
const gazeData = ref(null)

const catLabels = {
  attention_tracker: { label: '注意力追踪', desc: '沉浸信号分权重', icon: 'eye' },
  emotion_state_mapper: { label: '情绪映射', desc: '情绪影响权重', icon: 'heart' },
  attention_bridge: { label: '综合评分', desc: '综合专注度评分权重', icon: 'star' },
  gaze_detector: { label: '瞌睡检测', desc: '瞌睡检测权重', icon: 'moon' }
}

const immersionLabels = { 
  focus_score: '注视专注度', 
  distraction_penalty: '分心负分', 
  head_stability: '头部稳定性', 
  duration_score: '时长分' 
}

const emotionLabels = { 
  happy: '开心', 
  neutral: '中性', 
  surprise: '惊讶', 
  sad: '悲伤', 
  angry: '愤怒', 
  fear: '恐惧', 
  disgust: '厌恶' 
}

const dimLabels = { 
  interest_level: '兴趣', 
  frustration_tolerance: '挫折容忍', 
  anxiety_level: '焦虑', 
  confidence_level: '自信' 
}

const drowsinessLabels = { 
  head_down: '低头时间', 
  recent_yawn: '打哈欠', 
  abnormal_blink: '异常眨眼' 
}

const scoreDeltaLabels = { interest: '兴趣', frustration: '挫折', anxiety: '焦虑', confidence: '自信' }
const baselineLabels = { interest: '兴趣', frustration: '挫折', anxiety: '焦虑', confidence: '自信' }

const showStatus = (type, msg) => {
  statusType.value = type
  statusMessage.value = msg
}

const clearStatus = () => {
  statusMessage.value = ''
}

const loadOverview = async () => {
  loading.value = true
  clearStatus()
  try {
    const response = await getAllWeights()
    if (response.success) {
      overviewData.value = response.data
      showStatus('success', '加载成功')
    } else {
      throw new Error(response.detail || '加载失败')
    }
  } catch (e) {
    showStatus('error', e.message)
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

const convertNumbers = (obj) => {
  if (typeof obj === 'number') return obj
  if (typeof obj === 'string') {
    const num = parseFloat(obj)
    return isNaN(num) ? obj : num
  }
  if (Array.isArray(obj)) return obj.map(convertNumbers)
  if (typeof obj === 'object' && obj !== null) {
    const result = {}
    for (const key in obj) {
      result[key] = convertNumbers(obj[key])
    }
    return result
  }
  return obj
}

const loadCategory = async (category) => {
  loading.value = true
  clearStatus()
  try {
    const response = await getCategoryWeights(category)
    if (response.success) {
      const data = convertNumbers(response.data)
      if (category === 'attention_tracker') attentionData.value = data
      if (category === 'emotion_state_mapper') emotionData.value = data
      if (category === 'attention_bridge') bridgeData.value = data
      if (category === 'gaze_detector') gazeData.value = data
      showStatus('success', '加载成功')
    } else {
      throw new Error(response.detail || '加载失败')
    }
  } catch (e) {
    showStatus('error', e.message)
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

const switchTab = (tab) => {
  activeTab.value = tab
  if (tab !== 'overview') {
    const catMap = {
      attention: 'attention_tracker',
      emotion: 'emotion_state_mapper',
      bridge: 'attention_bridge',
      gaze: 'gaze_detector'
    }
    const cat = catMap[tab]
    if (cat) {
      if (tab === 'attention' && !attentionData.value) loadCategory(cat)
      if (tab === 'emotion' && !emotionData.value) loadCategory(cat)
      if (tab === 'bridge' && !bridgeData.value) loadCategory(cat)
      if (tab === 'gaze' && !gazeData.value) loadCategory(cat)
    }
  }
}

const buildUpdates = (formEl) => {
  const inputs = formEl.querySelectorAll('[data-path]')
  const updates = {}
  inputs.forEach(inp => {
    const path = inp.dataset.path.split('.')
    let val = inp.value
    if (inp.type === 'number') {
      val = inp.step && inp.step.includes('.') ? parseFloat(val) : parseInt(val, 10)
    }
    let cur = updates
    for (let i = 0; i < path.length - 1; i++) {
      if (!cur[path[i]]) cur[path[i]] = {}
      cur = cur[path[i]]
    }
    cur[path[path.length - 1]] = val
  })
  return updates
}

const saveCategory = async (category) => {
  const formId = {
    attention_tracker: 'attnForm',
    emotion_state_mapper: 'emoForm',
    attention_bridge: 'bridgeForm',
    gaze_detector: 'gazeForm'
  }[category]
  
  const formEl = document.getElementById(formId)
  if (!formEl) return
  
  const updates = buildUpdates(formEl)
  if (Object.keys(updates).length === 0) {
    ElMessage.warning('没有修改内容')
    return
  }
  
  if (category === 'gaze_detector') {
    const weights = updates.drowsiness_weights || {}
    const keys = Object.keys(weights)
    if (keys.length > 0) {
      const currentWeights = { ...gazeData.value.drowsiness_weights, ...weights }
      const total = Object.values(currentWeights).reduce((sum, v) => sum + parseFloat(v), 0)
      if (Math.abs(total - 1) > 0.001) {
        ElMessage.error(`瞌睡检测权重总和必须为1.0，当前总和为${total.toFixed(2)}`)
        return
      }
    }
  }
  
  try {
    const response = await updateCategoryWeights(category, updates)
    if (response.success) {
      ElMessage.success(response.message || '保存成功')
      showStatus('success', '保存成功')
      loadCategory(category)
    } else {
      throw new Error(response.detail || '保存失败')
    }
  } catch (e) {
    showStatus('error', e.message)
    ElMessage.error(e.message)
  }
}

const handleSliderChange = (e) => {
  const slider = e.target
  const original = parseFloat(slider.dataset.original)
  const current = parseFloat(slider.value)
  const min = parseFloat(slider.min) || 0
  const max = parseFloat(slider.max) || 100
  const label = slider.nextElementSibling
  
  const percentage = ((current - min) / (max - min)) * 100
  slider.style.setProperty('--slider-fill', `${percentage}%`)
  
  if (label && label.classList.contains('value-label')) {
    if (current !== original) {
      label.textContent = `调整为：${current}`
      label.classList.add('modified')
    } else {
      label.textContent = `当前值：${current}`
      label.classList.remove('modified')
    }
  }
}

const handleDimensionBoundsChange = (e) => {
  const card = e.target.closest('.param-card')
  const minInput = card.querySelector('input[data-path="dimension_bounds.min"]')
  const maxInput = card.querySelector('input[data-path="dimension_bounds.max"]')
  const label = card.querySelector('.value-label')
  
  if (minInput && maxInput && label) {
    const originalMin = parseFloat(minInput.dataset.original)
    const originalMax = parseFloat(maxInput.dataset.original)
    const currentMin = parseFloat(minInput.value)
    const currentMax = parseFloat(maxInput.value)
    
    if (currentMin !== originalMin || currentMax !== originalMax) {
      label.textContent = `调整为：[${currentMin}, ${currentMax}]`
      label.classList.add('modified')
    } else {
      label.textContent = `当前值：[${currentMin}, ${currentMax}]`
      label.classList.remove('modified')
    }
  }
}

const weightSum = computed(() => {
  if (!gazeData.value?.drowsiness_weights) return 0
  const weights = Object.values(gazeData.value.drowsiness_weights)
  return weights.reduce((sum, v) => sum + parseFloat(v), 0)
})



const handleReset = async () => {
  try {
    const response = await resetWeights()
    if (response.success) {
      ElMessage.success(response.message)
      loadOverview()
      attentionData.value = null
      emotionData.value = null
      bridgeData.value = null
      gazeData.value = null
    }
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const processToolParams = async () => {
  const tool = route.query.tool
  if (!tool) {
    await loadOverview()
    return
  }

  let args = null
  try {
    args = route.query.args ? JSON.parse(route.query.args) : null
  } catch (e) {
    args = null
  }

  switch (tool) {
    case 'get_weight_config': {
      const cat = args?.category || args?.Category || ''
      const catMap = {
        attention_tracker: 'attention',
        emotion_state_mapper: 'emotion',
        attention_bridge: 'bridge',
        gaze_detector: 'gaze'
      }
      const tab = catMap[cat]
      if (tab) {
        activeTab.value = tab
        await loadCategory(cat)
      } else {
        await loadOverview()
      }
      break
    }
    case 'update_weight': {
      const cat = args?.category || ''
      const catMap = {
        attention_tracker: 'attention',
        emotion_state_mapper: 'emotion',
        attention_bridge: 'bridge',
        gaze_detector: 'gaze'
      }
      const tab = catMap[cat]
      if (tab) {
        activeTab.value = tab
        await loadCategory(cat)
      } else {
        await loadOverview()
      }
      break
    }
    case 'reset_weights': {
      await handleReset()
      break
    }
    default:
      await loadOverview()
      break
  }
}

onMounted(() => {
  processToolParams()
})

watch(() => route.query, () => {
  processToolParams()
}, { deep: true })
</script>

<template>
  <div class="container">
    <div class="tab-bar">
      <div 
        v-for="tab in [{key:'overview',label:'总览',icon:'grid'},{key:'attention',label:'注意力追踪',icon:'eye'},{key:'emotion',label:'情绪映射',icon:'heart'},{key:'bridge',label:'综合评分',icon:'star'},{key:'gaze',label:'瞌睡检测',icon:'moon'}]"
        :key="tab.key"
        :class="['tab', {active: activeTab === tab.key}]"
        @click="switchTab(tab.key)"
      >
        <svg v-if="tab.icon === 'grid'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        <svg v-else-if="tab.icon === 'eye'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
        <svg v-else-if="tab.icon === 'heart'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        <svg v-else-if="tab.icon === 'star'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        <svg v-else-if="tab.icon === 'moon'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
        {{ tab.label }}
      </div>
    </div>

    <div class="content">
      <div class="status-bar" :class="statusType" v-if="statusMessage">{{ statusMessage }}</div>

      <!-- 总览 -->
      <div v-if="activeTab === 'overview'" class="tab-content">
        <div class="card">
          <div class="toolbar">
            <button class="btn btn-primary" @click="loadOverview">刷新</button>
            <!-- <button class="btn btn-danger" @click="handleReset">重置为默认值</button> -->
          </div>
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="overviewData" class="ov-grid">
            <div 
              v-for="(info, key) in catLabels" 
              :key="key"
              class="ov-card"
              @click="switchTab({attention_tracker:'attention',emotion_state_mapper:'emotion',attention_bridge:'bridge',gaze_detector:'gaze'}[key])"
            >
              <div class="ov-icon">
                <svg v-if="info.icon === 'eye'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else-if="info.icon === 'heart'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                <svg v-else-if="info.icon === 'star'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                <svg v-else-if="info.icon === 'moon'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
              </div>
              <div class="ov-name">{{ info.label }}</div>
              <div class="ov-desc">{{ info.desc }}</div>
              <div class="ov-fields">
                <span>共 {{ Object.keys(overviewData[key] || {}).length }} 个字段</span>
              </div>
            </div>
          </div>
          <div v-else class="empty">点击刷新加载配置概览</div>
        </div>
      </div>

      <!-- 注意力追踪 -->
      <div v-if="activeTab === 'attention'" class="tab-content">
        <div class="card" id="attnForm">
          <!-- <div class="alert-card">修改将立即生效并持久化到磁盘。</div> -->
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="attentionData">
            <div class="grid-2">
              <div v-if="attentionData.immersion_weights" class="form-section">
                <div class="form-section-title">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
                  沉浸信号分权重（应总和为 1.0）
                </div>
                <div v-for="(v, k) in attentionData.immersion_weights" :key="k" class="param-card">
                  <span class="param-label">{{ immersionLabels[k] || k }}</span>
                  <input type="range" step="0.01" min="0" max="1" :value="v" :data-path="`immersion_weights.${k}`" :data-original="v" :style="{ '--slider-fill': `${v * 100}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ v }}</span>
                </div>
              </div>
              <div class="form-section">
                <div class="form-section-title">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="4.93" x2="9.17" y1="4.93" y2="9.17"/><line x1="14.83" x2="19.07" y1="14.83" y2="19.07"/><line x1="14.83" x2="19.07" y1="4.93" y2="9.17"/><line x1="14.83" x2="14.83" y1="4.93" y2="9.17"/></svg>
                  其他参数
                </div>
                <div v-for="f in [{key:'distraction_additional_penalty',label:'额外分心扣分系数',step:0.01,min:0,max:1},{key:'meaningful_distraction_threshold',label:'有意义分心阈值（帧）',step:1,min:0,max:1000},{key:'max_deviation_for_focus',label:'专注归一化阈值',step:0.01,min:0,max:1},{key:'duration_seconds_for_full_score',label:'满分所需时长（秒）',step:1,min:0,max:3600}]" :key="f.key" class="param-card">
                  <span class="param-label">{{ f.label }}</span>
                  <input type="range" :step="f.step" :min="f.min" :max="f.max" :value="attentionData[f.key]" :data-path="f.key" :data-original="attentionData[f.key]" :style="{ '--slider-fill': `${((attentionData[f.key] - f.min) / (f.max - f.min)) * 100}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ attentionData[f.key] }}</span>
                </div>
              </div>
            </div>
            <div class="btn-center"><button class="btn btn-success" @click="saveCategory('attention_tracker')">保存修改</button></div>
          </div>
        </div>
      </div>

      <!-- 情绪映射 -->
      <div v-if="activeTab === 'emotion'" class="tab-content">
        <div class="card" id="emoForm">
          <!-- <div class="alert-card">修改将立即生效并持久化到磁盘。</div> -->
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="emotionData">
            <div v-if="emotionData.emotion_impact_weights" class="form-section">
              <div class="form-section-title">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                情绪影响权重
              </div>
              <div class="emo-grid">
                <div v-for="(weights, emo) in emotionData.emotion_impact_weights" :key="emo" class="emo-card">
                  <div class="emo-name">{{ emotionLabels[emo] || emo }}</div>
                  <div v-for="(val, dim) in weights" :key="dim" class="param-card">
                    <span class="param-label">{{ dimLabels[dim] || dim }}</span>
                    <input type="range" step="0.1" min="-1" max="1" :value="val" :data-path="`emotion_impact_weights.${emo}.${dim}`" :data-original="val" :style="{ '--slider-fill': `${((val + 1) / 2) * 100}%` }" class="param-slider" @input="handleSliderChange">
                    <span class="value-label">当前值：{{ val }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="grid-2">
              <div v-if="emotionData.impact_multiplier !== undefined" class="form-section">
                <div class="form-section-title">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="4.93" x2="9.17" y1="4.93" y2="9.17"/><line x1="14.83" x2="19.07" y1="14.83" y2="19.07"/><line x1="14.83" x2="19.07" y1="4.93" y2="9.17"/><line x1="14.83" x2="14.83" y1="4.93" y2="9.17"/></svg>
                  全局参数
                </div>
                <div class="param-card">
                  <span class="param-label">情绪影响倍数</span>
                  <input type="range" step="1" min="0" max="100" :value="emotionData.impact_multiplier" data-path="impact_multiplier" :data-original="emotionData.impact_multiplier" :style="{ '--slider-fill': `${emotionData.impact_multiplier}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ emotionData.impact_multiplier }}</span>
                </div>
                <div v-if="emotionData.dimension_bounds" class="param-card">
                  <span class="param-label">子维度范围</span>
                  <span class="hint">最小值</span>
                  <input type="number" step="1" :value="emotionData.dimension_bounds.min" data-path="dimension_bounds.min" :data-original="emotionData.dimension_bounds.min" class="param-input-narrow" @input="handleDimensionBoundsChange">
                  <span class="hint">最大值</span>
                  <input type="number" step="1" :value="emotionData.dimension_bounds.max" data-path="dimension_bounds.max" :data-original="emotionData.dimension_bounds.max" class="param-input-narrow" @input="handleDimensionBoundsChange">
                  <span class="value-label">当前值：[{{ emotionData.dimension_bounds.min }}, {{ emotionData.dimension_bounds.max }}]</span>
                </div>
              </div>
              <div v-if="emotionData.score_delta_weights" class="form-section">
                <div class="form-section-title">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                  评分变化量权重
                </div>
                <div v-for="(v, k) in emotionData.score_delta_weights" :key="k" class="param-card">
                  <span class="param-label">{{ scoreDeltaLabels[k] || k }}</span>
                  <input type="range" step="0.1" min="0" max="1" :value="v" :data-path="`score_delta_weights.${k}`" :data-original="v" :style="{ '--slider-fill': `${v * 100}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ v }}</span>
                </div>
              </div>
            </div>
            <div v-if="emotionData.emotion_baseline" class="form-section">
              <div class="form-section-title">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>
                情绪基准值
              </div>
              <div class="emo-grid">
                <div v-for="(vals, emo) in emotionData.emotion_baseline" :key="emo" class="emo-card">
                  <div class="emo-name">{{ emotionLabels[emo] || emo }}</div>
                  <div v-for="(v, k) in vals" :key="k" class="param-card">
                    <span class="param-label">{{ baselineLabels[k] || k }}</span>
                    <input type="range" step="1" min="-100" max="100" :value="v" :data-path="`emotion_baseline.${emo}.${k}`" :data-original="v" :style="{ '--slider-fill': `${((v + 100) / 200) * 100}%` }" class="param-slider" @input="handleSliderChange">
                    <span class="value-label">当前值：{{ v }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="btn-center"><button class="btn btn-success" @click="saveCategory('emotion_state_mapper')">保存修改</button></div>
          </div>
        </div>
      </div>

      <!-- 综合评分 -->
      <div v-if="activeTab === 'bridge'" class="tab-content">
        <div class="card" id="bridgeForm">
          <!-- <div class="alert-card">修改将立即生效并持久化到磁盘。</div> -->
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="bridgeData">
            <div class="form-section">
              <div class="form-section-title">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                评分参数
              </div>
              <div class="grid-2">
                <div v-for="f in [{key:'composite_score_max',label:'综合评分最大值',step:1,min:0,max:1000},{key:'base_score',label:'基础分',step:1,min:0,max:100},{key:'immersion_max_contribution',label:'沉浸信号最大贡献',step:1,min:0,max:100},{key:'distraction_max_contribution',label:'分心最大贡献',step:1,min:0,max:100},{key:'valence_positive_bonus',label:'积极情绪加分',step:1,min:0,max:100}]" :key="f.key" class="param-card">
                  <span class="param-label">{{ f.label }}</span>
                  <input type="range" :step="f.step" :min="f.min" :max="f.max" :value="bridgeData[f.key]" :data-path="f.key" :data-original="bridgeData[f.key]" :style="{ '--slider-fill': `${((bridgeData[f.key] - f.min) / (f.max - f.min)) * 100}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ bridgeData[f.key] }}</span>
                </div>
                <div v-for="f in [{key:'valence_negative_penalty',label:'消极情绪减分',step:1,min:-100,max:100},{key:'confidence_min_multiplier',label:'置信度最小乘数',step:0.1,min:0,max:1},{key:'confidence_max_multiplier_factor',label:'置信度最大乘数因子',step:0.1,min:0,max:1},{key:'valence_positive_ratio',label:'积极判定阈值倍数',step:0.1,min:0,max:10},{key:'valence_negative_ratio',label:'消极判定阈值倍数',step:0.1,min:0,max:10}]" :key="f.key" class="param-card">
                  <span class="param-label">{{ f.label }}</span>
                  <input type="range" :step="f.step" :min="f.min" :max="f.max" :value="bridgeData[f.key]" :data-path="f.key" :data-original="bridgeData[f.key]" :style="{ '--slider-fill': `${((bridgeData[f.key] - f.min) / (f.max - f.min)) * 100}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ bridgeData[f.key] }}</span>
                </div>
              </div>
            </div>
            <div v-if="bridgeData.score_levels" class="form-section">
              <div class="form-section-title">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="3" x2="21" y2="21"/><path d="M18 3v18a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V3"/></svg>
                评分等级
              </div>
              <div class="level-list">
                <div v-for="lv in bridgeData.score_levels" :key="lv.threshold" class="level-tag">
                  <span class="th">≥{{ lv.threshold }}</span> {{ lv.label }}
                </div>
              </div>
              <div class="level-note">评分等级为只读展示，可通过 JSON 编辑器修改</div>
            </div>
            <div class="btn-center"><button class="btn btn-success" @click="saveCategory('attention_bridge')">保存修改</button></div>
          </div>
        </div>
      </div>

      <!-- 瞌睡检测 -->
      <div v-if="activeTab === 'gaze'" class="tab-content">
        <div class="card" id="gazeForm">
          <!-- <div class="alert-card">修改将立即生效并持久化到磁盘。</div> -->
          <div v-if="loading" class="loading">加载中...</div>
          <div v-else-if="gazeData">
            <div class="grid-2">
              <div v-if="gazeData.drowsiness_weights" class="form-section">
                <div class="form-section-title">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
                  瞌睡检测权重（应总和为 1.0）
                </div>
                <div class="weight-summary">
                  <span>当前总和：</span>
                  <span :class="{ 'weight-sum-valid': weightSum === 1, 'weight-sum-invalid': weightSum !== 1 }">{{ weightSum.toFixed(2) }}</span>
                  <span v-if="weightSum !== 1" class="weight-hint">（需调整为 1.0）</span>
                </div>
                <div v-for="(v, k) in gazeData.drowsiness_weights" :key="k" class="param-card">
                  <span class="param-label">{{ drowsinessLabels[k] || k }}</span>
                  <input type="range" step="0.1" min="0" max="1" :value="v" :data-path="`drowsiness_weights.${k}`" :data-original="v" :style="{ '--slider-fill': `${v * 100}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ v }}</span>
                </div>
              </div>
              <div class="form-section">
                <div class="form-section-title">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="4.93" x2="9.17" y1="4.93" y2="9.17"/><line x1="14.83" x2="19.07" y1="14.83" y2="19.07"/><line x1="14.83" x2="19.07" y1="4.93" y2="9.17"/><line x1="14.83" x2="14.83" y1="4.93" y2="9.17"/></svg>
                  检测参数
                </div>
                <div v-for="f in [{key:'head_down_angle_threshold',label:'低头判定角度（度）',step:1,min:0,max:180},{key:'yawn_cooldown_seconds',label:'哈欠冷却时间（秒）',step:1,min:0,max:600},{key:'blink_rate_low_threshold',label:'眨眼频率下限（次/分钟）',step:1,min:0,max:100},{key:'blink_rate_high_threshold',label:'眨眼频率上限（次/分钟）',step:1,min:0,max:200},{key:'drowsiness_score_threshold',label:'瞌睡判定阈值',step:0.01,min:0,max:1}]" :key="f.key" class="param-card">
                  <span class="param-label">{{ f.label }}</span>
                  <input type="range" :step="f.step" :min="f.min" :max="f.max" :value="gazeData[f.key]" :data-path="f.key" :data-original="gazeData[f.key]" :style="{ '--slider-fill': `${((gazeData[f.key] - f.min) / (f.max - f.min)) * 100}%` }" class="param-slider" @input="handleSliderChange">
                  <span class="value-label">当前值：{{ gazeData[f.key] }}</span>
                </div>
              </div>
            </div>
            <div class="btn-center"><button class="btn btn-success" @click="saveCategory('gaze_detector')">保存修改</button></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  min-height: 85vh;
  background: var(--bg-page);
  /* border: 1px solid black; */
}

.tab-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 12px 28px;
  gap: 8px;
  background: var(--bg-page);
}

.tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 28px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-gray);
  transition: all 0.3s ease;
  border-radius: 20px;
  border: 1px solid transparent;
}

.tab:hover {
  color: var(--primary);
  background: var(--primary-light);
  border-color: var(--primary-fade);
}

.tab.active {
  color: #fff;
  background: var(--primary);
  font-weight: 600;
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
}

.content {
  padding: 20px 32px;
}

.status-bar {
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}

.status-bar.success {
  background: var(--pass-bg-color);
  color: var(--pass);
  border: 1px solid var(--pass-shadow);
}

.status-bar.error {
  background: var(--main-fail-status);
  color: var(--main-delete);
  border: 1px solid var(--main-shadow);
}

.status-bar.info {
  background: rgba(45, 125, 219, 0.1);
  color: var(--primary);
  border: 1px solid var(--primary-fade);
}

.card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 24px 28px;
  margin-bottom: 20px;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.btn {
  padding: 9px 20px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--primary);
  color: #fff;
}

.btn-primary:hover {
  background: var(--primary-hv);
}

.btn-success {
  background: var(--pass);
  color: #fff;
}

.btn-success:hover {
  background: var(--pass-hover);
}

.btn-danger {
  background: var(--main-delete);
  color: #fff;
}

.btn-danger:hover {
  background: var(--main-delete-hover);
}

.alert-card {
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 14px;
  color: #b45309;
  margin-bottom: 16px;
}

.loading {
  text-align: center;
  padding: 50px;
  color: var(--text-gray);
  font-size: 16px;
}

.empty {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-gray);
  font-size: 15px;
}

.btn-center {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.weight-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 16px;
  background: var(--bgc-light);
  border-radius: 8px;
  font-size: 15px;
}

.weight-sum-valid {
  color: var(--pass);
  font-weight: 700;
}

.weight-sum-invalid {
  color: var(--danger);
  font-weight: 700;
}

.weight-hint {
  color: var(--danger);
  font-size: 13px;
}

.ov-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.ov-card {
  background: var(--bgc-light);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  padding: 28px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  text-align: center;
}

.ov-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.ov-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.12);
  transform: translateY(-2px);
}

.ov-name {
  font-weight: 600;
  font-size: 18px;
  color: var(--primary);
}

.ov-desc {
  font-size: 15px;
  color: var(--text-gray);
}

.ov-fields {
  font-size: 14px;
  color: var(--text-gray);
}

.form-section {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
  border: 1px solid var(--border-color);
}

.form-section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 16px;
  padding-left: 12px;
  border-left: 4px solid var(--primary);
  display: flex;
  align-items: center;
  gap: 10px;
}

.param-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: #fff;
  border-radius: 10px;
  margin-bottom: 10px;
  transition: all 0.25s ease;
  border: 1px solid var(--border-color);
  gap: 15px;
}

.param-card:hover {
  background: rgba(45, 125, 219, 0.03);
  border-color: var(--primary-fade);
  transform: translateX(4px);
}

.param-label {
  font-size: 14px;
  color: var(--text-body);
  font-weight: 500;
  min-width: 150px;
  flex-shrink: 0;
}

.param-slider {
  flex: 1;
  height: 8px;
  -webkit-appearance: none;
  appearance: none;
  background: linear-gradient(to right, var(--primary) var(--slider-fill, 50%), var(--border-color) var(--slider-fill, 50%));
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}

.param-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  background: #fff;
  border: 3px solid var(--primary);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
  transition: all 0.2s;
  margin-top: -6px;
}

.param-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.4);
}

.param-slider::-webkit-slider-runnable-track {
  height: 8px;
  border-radius: 4px;
}

.param-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  background: #fff;
  border: 3px solid var(--primary);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.3);
}

.param-slider::-moz-range-track {
  height: 8px;
  border-radius: 4px;
}

.value-label {
  font-size: 13px;
  color: var(--primary);
  background: var(--primary-light);
  padding: 6px 14px;
  border-radius: 20px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 100px;
  text-align: center;
}

.value-label.modified {
  color: #fff;
  background: var(--pass);
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
}

.param-input-narrow {
  width: 70px;
  padding: 6px 10px;
  border: 2px solid var(--border-color);
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  outline: none;
  text-align: center;
  transition: all 0.2s;
}

.param-input-narrow:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(45, 125, 219, 0.08);
}

.hint {
  font-size: 12px;
  color: var(--text-gray);
}

.sub-group {
  padding: 0;
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.emo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.emo-card {
  background: linear-gradient(145deg, #fafafa 0%, #fff 100%);
  border-radius: 14px;
  padding: 18px;
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.emo-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.1);
  transform: translateY(-2px);
}

.emo-card .emo-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--primary-light);
  text-align: center;
}

.emo-card .param-card {
  background: #fff;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 8px;
}

.emo-card .param-card:hover {
  transform: none;
  background: rgba(45, 125, 219, 0.03);
}

.emo-card .param-label {
  min-width: 90px;
  font-size: 13px;
}

.score-delta-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.level-list {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.level-tag {
  background: linear-gradient(135deg, var(--primary-light) 0%, rgba(45, 125, 219, 0.08) 100%);
  border: 1px solid var(--primary-fade);
  border-radius: 20px;
  padding: 6px 16px;
  font-size: 13px;
  color: var(--text-body);
  transition: all 0.2s;
}

.level-tag:hover {
  background: var(--primary-light);
  transform: translateY(-1px);
}

.level-tag .th {
  color: var(--primary);
  font-weight: 600;
}

.level-note {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 12px;
}
</style>
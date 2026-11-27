<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getRankingWeightsApi, updateRankingWeightsApi } from '@/api/backstage/adRank.js'

const route = useRoute()
const loading = ref(false)
const rankingData = ref(null)
const weightDescriptions = ref({})
const formula = ref('')

const weightLabels = {
  coding_score: '编程能力分',
  accuracy_score: '准确率分',
  learning_time_score: '学习时长分',
  problem_count_score: '做题数量分',
  overall_feature_score: '综合特征分'
}

// 加载排行榜权重
const loadRankingWeights = async () => {
  loading.value = true
  try {
    const response = await getRankingWeightsApi()
    if (response.success) {
      rankingData.value = response.data
      weightDescriptions.value = response.description || {}
      formula.value = response.formula || ''
    } else {
      throw new Error(response.detail || '加载失败')
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

// 计算权重总和
const weightSum = computed(() => {
  if (!rankingData.value) return 0
  const weights = Object.values(rankingData.value)
  return weights.reduce((sum, v) => sum + parseFloat(v), 0)
})

// 处理滑块变化
const handleSliderChange = (e) => {
  const slider = e.target
  const original = parseFloat(slider.dataset.original)
  const current = parseFloat(slider.value)
  const key = slider.dataset.path
  const label = slider.nextElementSibling
  
  // 更新数据
  if (rankingData.value && key) {
    rankingData.value[key] = current
  }
  
  // 更新滑块样式
  const percentage = current * 100
  slider.style.setProperty('--slider-fill', `${percentage}%`)
  
  // 更新标签
  if (label && label.classList.contains('value-label')) {
    if (current !== original) {
      label.textContent = `调整为：${(current * 100).toFixed(0)}%`
      label.classList.add('modified')
    } else {
      label.textContent = `当前值：${(current * 100).toFixed(0)}%`
      label.classList.remove('modified')
    }
  }
}

// 保存权重
const saveRankingWeights = async () => {
  if (!rankingData.value) return
  
  // 验证权重总和
  if (Math.abs(weightSum.value - 1.0) > 0.01) {
    ElMessage.error(`权重总和必须为 1.0，当前总和为 ${weightSum.value.toFixed(2)}`)
    return
  }
  
  try {
    const response = await updateRankingWeightsApi(rankingData.value)
    if (response.success) {
      ElMessage.success(response.message || '保存成功')
      loadRankingWeights()
    } else {
      throw new Error(response.detail || '保存失败')
    }
  } catch (e) {
    ElMessage.error(e.message)
  }
}

// 处理工具参数
const processToolParams = async () => {
  const tool = route.query.tool
  
  await loadRankingWeights()
  
  if (!tool) return
  
  switch (tool) {
    case 'get_global_ranking_weights':
      // 权重已在 loadRankingWeights 中加载
      break
    case 'update_global_ranking_weights':
      // 权重已加载，用户可以直接编辑
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
    <div class="content">
      <div class="card">
        <div class="alert-card">修改将立即生效，重新计算排行榜。权重总和必须为 1.0。</div>
        
        <div class="toolbar">
          <button class="btn btn-primary" @click="loadRankingWeights">刷新</button>
          <span class="update-time" v-if="rankingData">上次更新: {{ new Date().toLocaleTimeString('zh-CN', { hour12: false }) }}</span>
          <span class="weight-total" v-if="rankingData">
            权重总和: 
            <span :class="{ 'weight-sum-valid': weightSum === 1, 'weight-sum-invalid': weightSum !== 1 }">
              {{ weightSum.toFixed(2) }}
            </span>
          </span>
        </div>
        
        <div v-if="loading" class="loading">加载中...</div>
        
        <div v-else-if="rankingData">
          <div class="form-section">
            <div class="form-section-title">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
              </svg>
              排行榜权重配置
            </div>
            
            <div class="formula-info" v-if="formula">
              {{ formula }}
            </div>
            
            <div class="weight-summary">
              <span>当前总和：</span>
              <span :class="{ 'weight-sum-valid': weightSum === 1, 'weight-sum-invalid': weightSum !== 1 }">
                {{ weightSum.toFixed(2) }}
              </span>
              <span v-if="weightSum !== 1" class="weight-hint">（需调整为 1.0）</span>
            </div>
            
            <div v-for="(value, key) in rankingData" :key="key" class="param-card">
              <span class="param-label">{{ weightLabels[key] || key }}</span>
              <input 
                type="range" 
                step="0.01" 
                min="0" 
                max="1" 
                :value="value" 
                :data-path="key" 
                :data-original="value" 
                :style="{ '--slider-fill': `${value * 100}%` }" 
                class="param-slider" 
                @input="handleSliderChange"
              >
              <span class="value-label">当前值：{{ (value * 100).toFixed(0) }}%</span>
              <span class="weight-desc" v-if="weightDescriptions[key]">{{ weightDescriptions[key] }}</span>
            </div>
          </div>
          
          <div class="btn-center">
            <button class="btn btn-success" @click="saveRankingWeights">保存修改</button>
          </div>
        </div>
        
        <div v-else class="empty">点击刷新加载权重配置</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  min-height: 85vh;
  background: var(--bg-page);
}

.content {
  padding: 20px 32px;
}

.card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 24px 28px;
  margin-bottom: 20px;
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

.toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.update-time {
  font-size: 13px;
  color: var(--text-gray);
}

.weight-total {
  font-size: 14px;
  color: var(--text-body);
  font-weight: 500;
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

.formula-info {
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 16px;
  padding: 10px 14px;
  background: var(--bgc-light);
  border-radius: 8px;
}

.weight-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
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
  color: var(--main-delete);
  font-weight: 700;
}

.weight-hint {
  color: var(--main-delete);
  font-size: 13px;
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

.weight-desc {
  font-size: 12px;
  color: var(--text-gray);
  margin-left: 8px;
  flex-shrink: 0;
}

.btn-center {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>

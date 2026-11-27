<!-- aiAnswer页面-构建画像成功以后的方案选择对话框 -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { changePlanApi, getPlanApi } from '@/api/mainApi/aiAnswer.js'
import { ElMessage } from 'element-plus'

const props = defineProps({
  plans: {
    type: Array,
    default: () => []
  },
  userId: {
    type: String,
    default: ''
  },
  isViewMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['select', 'close'])

const currentPlanId = ref('')
const planList = ref([])

const difficultyColor = computed(() => ({
  'easy': { bg: 'rgba(34, 197, 94, 0.15)', text: '#22c55e' },
  'medium': { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b' },
  'hard': { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444' }
}))

const currentPlanName = computed(() => {
  if (!currentPlanId.value) return '未选择'
  const plan = planList.value.find(p => p.plan_id === currentPlanId.value)
  return plan ? plan.name : '未选择'
})

onMounted(async () => {
  if (props.isViewMode && props.userId) {
    try {
      const response = await getPlanApi(props.userId)
      if (response.code === 1 && response.data) {
        currentPlanId.value = response.data.planId || response.data.plan_id || ''
        planList.value = response.data.plans || []
      }
    } catch (e) {
      console.error('获取方案失败:', e)
      ElMessage.error('获取方案失败')
    }
  } else {
    planList.value = props.plans
  }
})

const handleSelect = async (plan) => {
  if (!props.userId) {
    ElMessage.warning('用户ID为空')
    return
  }
  
  try {
    const response = await changePlanApi({
      user_id: props.userId,
      plan_id: plan.plan_id,
      plan_name: plan.name
    })
    
    if (response.code === 1) {
      ElMessage.success('选择方案成功')
      currentPlanId.value = plan.plan_id
      emit('select', plan)
    } else {
      ElMessage.error(response.msg || '选择方案失败')
    }
  } catch (e) {
    console.error('选择方案失败:', e)
    ElMessage.error('选择方案失败')
  }
}

const handleClose = () => {
  emit('close')
}
</script>

<template>
  <div class="plan-selector">
    <div class="plan-header">
      <span class="plan-title">学习方案推荐</span>
      <span class="plan-subtitle">{{ isViewMode ? '查看或切换学习方案' : '选择适合你的学习路径' }}</span>
    </div>
    
    <div v-if="isViewMode" class="current-plan">
      <span class="current-label">当前方案：</span>
      <span class="current-value">{{ currentPlanName }}</span>
    </div>
    
    <div class="plan-grid">
      <div 
        v-for="plan in planList" 
        :key="plan.plan_id" 
        :class="['plan-card', { 'plan-card-selected': plan.plan_id === currentPlanId }]"
      >
        <div class="plan-card-header">
          <div class="plan-id" :style="{ background: difficultyColor[plan.difficulty]?.bg || '#f1f5f9', color: difficultyColor[plan.difficulty]?.text || '#64748b' }">
            {{ plan.plan_id }}
          </div>
          <div class="plan-name">{{ plan.name }}</div>
          <div class="plan-subtitle">{{ plan.subtitle }}</div>
          <div v-if="plan.plan_id === currentPlanId" class="plan-selected-badge">✓ 已选择</div>
        </div>
        
        <div class="plan-description">{{ plan.description }}</div>
        
        <div class="plan-tags">
          <span 
            v-for="tag in plan.style_tags" 
            :key="tag" 
            class="plan-tag"
          >
            {{ tag }}
          </span>
        </div>
        
        <div class="plan-detail">
          <div class="detail-row">
            <span class="detail-label">难度</span>
            <span class="detail-value" :style="{ color: difficultyColor[plan.difficulty]?.text || '#64748b' }">
              {{ plan.difficulty === 'easy' ? '简单' : plan.difficulty === 'medium' ? '中等' : '困难' }}
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">重点</span>
            <span class="detail-value">{{ plan.focus }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">预计时长</span>
            <span class="detail-value">{{ plan.estimated_effort }}</span>
          </div>
        </div>
        
        <div class="plan-info">
          {{ plan.detail }}
        </div>
        
        <button 
          class="plan-select-btn" 
          @click="handleSelect(plan)"
          :disabled="plan.plan_id === currentPlanId"
        >
          {{ plan.plan_id === currentPlanId ? '已选择' : '选择该方案' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plan-selector {
  background: #fff;
  border-radius: 12px;
  /* padding: 10px; */
  /* box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); */
}

.plan-header {
  margin-bottom: 20px;
  text-align: center;
}

.plan-title {
  display: block;
  font-size: 22px;
  font-weight: 600;
  color: #1f2a3f;
  margin-bottom: 4px;
}

.plan-subtitle {
  font-size: 13px;
  color: #94a3b8;
}

.plan-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.plan-card {
  background: #f8fafc;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e2e8f0;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.plan-card:hover {
  border-color: #2D7DDB;
  box-shadow: 0 4px 16px rgba(45, 125, 219, 0.12);
  transform: translateY(-2px);
}

.plan-card-header {
  margin-bottom: 12px;
}

.plan-id {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 8px;
}

.plan-name {
  font-size: 16px;
  font-weight: 600;
  color: #1f2a3f;
  margin-bottom: 2px;
}

.plan-subtitle {
  font-size: 13px;
  color: #64748b;
}

.plan-description {
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
  margin-bottom: 12px;
}

.plan-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.plan-tag {
  padding: 3px 8px;
  background: rgba(45, 125, 219, 0.1);
  color: #2D7DDB;
  font-size: 11px;
  border-radius: 4px;
}

.plan-detail {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f1f5f9;
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-label {
  font-size: 12px;
  color: #94a3b8;
}

.detail-value {
  font-size: 12px;
  font-weight: 500;
  color: #334155;
}

.plan-info {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(44, 62, 107, 0.03);
  border-radius: 6px;
}

.plan-select-btn {
  width: 100%;
  padding: 10px;
  background: linear-gradient(135deg, #2D7DDB, #5094E4);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  margin-top: auto;
}

.plan-select-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.4);
}

.plan-select-btn:active {
  transform: translateY(0);
}

.plan-select-btn:disabled {
  background: #e2e8f0;
  color: #94a3b8;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.current-plan {
  text-align: center;
  margin-bottom: 16px;
  padding: 12px;
  background: rgba(45, 125, 219, 0.08);
  border-radius: 8px;
}

.current-label {
  font-size: 13px;
  color: #64748b;
}

.current-value {
  font-size: 14px;
  font-weight: 600;
  color: #2D7DDB;
  margin-left: 4px;
}

.plan-card-selected {
  border-color: #2D7DDB;
  box-shadow: 0 0 0 2px rgba(45, 125, 219, 0.1);
}

.plan-selected-badge {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  margin-top: 6px;
}

/* ============ 夜间模式适配 ============ */

.dark .plan-selector {
  background: var(--bg-card);
  /* box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2); */
}

.dark .plan-title {
  color: var(--text-title);
}

.dark .plan-subtitle {
  color: var(--text-gray);
}

.dark .plan-card {
  background: var(--bg-page);
  border-color: var(--border-color);
}

.dark .plan-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.2);
}

.dark .plan-name {
  color: var(--text-title);
}

.dark .plan-description {
  color: var(--text-body);
}

.dark .plan-tag {
  background: rgba(59, 130, 246, 0.15);
  color: var(--primary);
}

.dark .plan-detail {
  background: var(--bg-card);
}

.dark .detail-row {
  border-bottom-color: var(--border-color);
}

.dark .detail-label {
  color: var(--text-gray);
}

.dark .detail-value {
  color: var(--text-body);
}

.dark .plan-info {
  background: rgba(59, 130, 246, 0.05);
  color: var(--text-gray);
}

.dark .plan-select-btn:disabled {
  background: rgba(71, 85, 105, 0.3);
  color: var(--text-gray);
}

.dark .current-plan {
  background: rgba(59, 130, 246, 0.1);
}

.dark .current-label {
  color: var(--text-gray);
}

.dark .current-value {
  color: var(--primary);
}

.dark .plan-card-selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

</style>
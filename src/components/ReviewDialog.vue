<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElLoading } from 'element-plus'
import { reviewRemindApi, getSessionIdApi, reviewRemindSevenDaysApi, reviewRemindTotalApi } from '@/api/mainApi/layout.js'//接口
import { saveSkip } from '@/utils/skip.js'//跳转
import emptyStatus from '@/assets/image/emptyStatus.png'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  userId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['update:visible'])

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const reminder = ref(null)
const reminderData = ref({
  today_due_count: 0,
  seven_days_count: 0,
  total_count: 0
})
const activeTab = ref('due')
const currentData = ref(null)


watch(() => props.visible, (newVal) => {
  if (newVal) {
    activeTab.value = 'due'
    document.body.style.overflow = 'hidden'
    fetchReviewReminder()
  } else {
    document.body.style.overflow = ''
  }
}, { immediate: true })

const fetchReviewReminder = async () => {
  if (!props.userId) {
    ElMessage.warning('用户ID不存在')
    return
  }
  
  loading.value = true
  try {
    const [res1, res2, res3] = await Promise.all([
      reviewRemindApi(props.userId),
      reviewRemindSevenDaysApi(props.userId),
      reviewRemindTotalApi(props.userId)
    ])
    
    if (res1.code === 1 && res1.data && res1.data.reminder) {
      reminder.value = res1.data.reminder
      reminderData.value.today_due_count = res1.data.reminder.today_due_count || 0
    }
    
    if (res2.code === 1 && res2.data) {
      reminderData.value.seven_days_count = res2.data.count || 0
    }
    
    if (res3.code === 1 && res3.data) {
      reminderData.value.total_count = res3.data.count || 0
    }
    
    await fetchTabData('due')
  } catch (error) {
    console.error('获取复习提醒失败:', error)
    ElMessage.error('获取复习提醒失败，请稍后重试')
    reminder.value = null
  } finally {
    loading.value = false
  }
}

const switchTab = async (tab) => {
  if (activeTab.value === tab) return
  activeTab.value = tab
  await fetchTabData(tab)
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const fetchTabData = async (tab) => {
  loading.value = true
  try {
    let res
    switch (tab) {
      case 'due':
        res = await reviewRemindApi(props.userId)
        if (res.code === 1 && res.data && res.data.reminder) {
          reminder.value = res.data.reminder
          currentData.value = res.data.reminder
        }
        break
      case 'sevenDays':
        res = await reviewRemindSevenDaysApi(props.userId)
        if (res.code === 1 && res.data) {
          currentData.value = res.data
        }
        break
      case 'total':
        res = await reviewRemindTotalApi(props.userId)
        if (res.code === 1 && res.data) {
          currentData.value = res.data
        }
        break
    }
  } catch (error) {
    console.error('获取数据失败:', error)
    ElMessage.error('获取数据失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 生成编程题
const handleGeneratePractice = (topic) => {
  const message = `帮我生成用于复习的关于${topic}的编程题`
  getSessionId(topic).then(sessionId => {
    if (sessionId) {
      navigateToAiAnswer(message, sessionId)
    } else {
      ElMessage.warning('无法获取会话ID，无法生成复习题')
    }
  })
}
// 生成理论题
const handleGenerateTheory = (topic) => {
  const message = `帮我生成用于复习的关于${topic}的理论题`
  getSessionId(topic).then(sessionId => {
    if (sessionId) {
      navigateToAiAnswer(message, sessionId)
    } else {
      ElMessage.warning('无法获取会话ID，无法生成复习题')
    }
  })
}

//获取复习会话ID
const getSessionId = async (topic) => { 
  try {
    const res = await getSessionIdApi(
      {
        user_id: props.userId,
        knowledge_point: topic,
        total_questions: 5
      }
    )
    if (res.success && res.session_id) {
      return res.session_id
    } else {
      ElMessage.warning('获取会话ID失败')
      return null
    }
  } catch (error) {
    console.error('获取会话ID失败:', error)
    ElMessage.error('获取会话ID失败，请稍后重试')
  }

}

const navigateToAiAnswer = (message, sessionId) => {
  console.log('保存复习信息：（message，sessionId）:', message, sessionId)
  // 关闭对话框
  emit('update:visible', false)
  


  // 跳转，保存信息
  saveSkip(10, '', '', sessionId, message)

  // 如果当前已在目标页面，显示加载状态后刷新；否则跳转
  if (route.path === '/aiAnswer') {
    console.log('【复习】处于aiAnswer，刷新页面')
    // 显示全屏加载遮罩
    const loadingInstance = ElLoading.service({
      fullscreen: true,
      text: '正在加载资源...',
      background: 'rgba(255, 255, 255, 0.9)'
    })
    // 短暂延迟后刷新，确保加载状态可见
    setTimeout(() => {
      window.location.reload()
    }, 200)
  } else {
    console.log('【复习】不处于aiAnswer，跳转页面')
    router.push('/aiAnswer')
  }
}

const handleClose = () => {
  emit('update:visible', false)
}
</script>

<template>
  <div v-if="visible" class="review-overlay">
    <div class="review-dialog">
      <div class="dialog-header">
        <span class="dialog-title">复习提醒</span>
        <span class="dialog-close" @click="handleClose">×</span>
      </div>
      
      <div class="dialog-body">
        <div v-if="loading" class="loading-wrapper">
          <div class="loading-spinner"></div>
          <span>加载中...</span>
        </div>
        
        <div v-else-if="!reminder" class="empty-wrapper">
          <div class="empty-icon">
            <svg t="1782116572531" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1714" width="100" height="100"><path d="M439.9 359.2l-99.7-156.3h-81.4c-66.5 0-120.5 53.9-120.5 120.5v294.9h751.4V359.2H439.9z" fill="#2867CE" p-id="1715"></path><path d="M769.3 871.6H258.7c-92.9 0-168.5-75.6-168.5-168.5V323.3c0-92.9 75.6-168.5 168.5-168.5h81.4c16.4 0 31.7 8.4 40.5 22.2l85.5 134.1h423.5c26.6 0 48.1 21.5 48.1 48.1v343.9c0.1 92.9-75.5 168.5-168.4 168.5zM258.7 250.9c-39.9 0-72.4 32.5-72.4 72.4v379.8c0 39.9 32.5 72.4 72.4 72.4h510.5c39.9 0 72.4-32.5 72.4-72.4V407.3H439.9c-16.4 0-31.7-8.4-40.5-22.2L313.9 251h-55.2z" fill="#BDD2EF" p-id="1716"></path><path d="M840.2 272.7h-314l-69.6-109.2h383.6z" fill="#2867CE" p-id="1717"></path></svg>
          </div>
          <p>暂无复习内容</p>
          <span class="empty-tip">继续学习，积累更多知识点吧</span>
        </div>
        
        <div v-else class="review-content">
          <div class="tabs-bar">
          <div 
            class="tab-item" 
            :class="{ active: activeTab === 'due' }"
            @click="switchTab('due')"
          >
            <span class="tab-value">{{ reminderData.today_due_count || 0 }}</span>
            <span class="tab-label">待复习</span>
          </div>
          <div class="tab-divider"></div>
          <div 
            class="tab-item" 
            :class="{ active: activeTab === 'sevenDays' }"
            @click="switchTab('sevenDays')"
          >
            <span class="tab-value">{{ reminderData.seven_days_count || 0 }}</span>
            <span class="tab-label">近7天复习</span>
          </div>
          <div class="tab-divider"></div>
          <div 
            class="tab-item" 
            :class="{ active: activeTab === 'total' }"
            @click="switchTab('total')"
          >
            <span class="tab-value">{{ reminderData.total_count || 0 }}</span>
            <span class="tab-label">总计</span>
          </div>
        </div>
          
          <div v-if="activeTab === 'due' && reminder.message" class="reminder-message">
            {{ reminder.message }}
          </div>
          
          <div v-if="activeTab === 'due' && (!currentData?.grouped_due || Object.keys(currentData.grouped_due).length === 0)" class="empty-state">
            <img :src="emptyStatus" alt="空状态" class="empty-img" />
            <p>暂无待复习内容</p>
            <span class="empty-tip">继续学习，积累更多知识点吧</span>
          </div>
          
          <div v-else-if="activeTab === 'due'" class="grouped-list">
            <div 
              v-for="(items, groupName) in (currentData?.grouped_due || {})" 
              :key="groupName"
              class="group-item"
            >
              <div class="group-header">
                <span class="group-tag">{{ groupName }}</span>
                <span class="group-count">{{ items.length }} 项</span>
              </div>
              <div class="item-list">
                <div 
                  v-for="item in items" 
                  :key="item.topic"
                  class="review-item"
                  :class="{ 'low-mastery': item.mastery_points === 0 }"
                >
                  <div class="item-info">
                    <span class="item-title">{{ item.title }}</span>
                    <span class="mastery-label" :class="{ 'green': item.mastery_points > 0 }">
                      {{ item.mastery_label }}
                    </span>
                    <div class="mastery-bar">
                      <div 
                        class="mastery-fill" 
                        :style="{ width: (item.mastery_points * 100) + '%' }"
                      ></div>
                    </div>
                    <span class="mastery-points">掌握度: {{ item.mastery_points }}</span>
                  </div>
                  <div class="item-actions">
                    <button 
                      class="btn-practice"
                      @click="handleGeneratePractice(item.topic)"
                    >
                      生成复习编程题
                    </button>
                    <button 
                      class="btn-theory"
                      @click="handleGenerateTheory(item.topic)"
                    >
                      生成复习试卷理论题
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else-if="activeTab === 'sevenDays' && (!currentData?.sessions || currentData.sessions.length === 0)" class="empty-state">
            <img :src="emptyStatus" alt="空状态" class="empty-img" />
            <p>暂无近7天复习记录</p>
            <span class="empty-tip">继续学习，积累更多知识点吧</span>
          </div>
          
          <div v-else-if="activeTab === 'sevenDays'" class="sessions-list">
            <div 
              v-for="session in (currentData?.sessions || [])" 
              :key="session.session_id"
              class="session-item"
            >
              <div class="session-icon">
                <svg t="1783932506294" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1708" width="32" height="32"><path d="M512 958.016611c-245.919634 0-446.016611-200.064292-446.016611-446.016611 0-245.919634 200.095256-446.016611 446.016611-446.016611 245.952318 0 446.016611 200.064292 446.016611 446.016611S757.952318 958.016611 512 958.016611zM512 129.983389c-210.655557 0-382.016611 171.359333-382.016611 382.016611 0 210.624593 171.359333 382.016611 382.016611 382.016611 210.624593 0 382.016611-171.359333 382.016611-382.016611S722.624593 129.983389 512 129.983389z" fill="#2D7DDB" p-id="1709"></path><path d="M463.99957 304.00043c0 26.509985 21.490445 48.00043 48.00043 48.00043s48.00043-21.490445 48.00043-48.00043-21.490445-48.00043-48.00043-48.00043S463.99957 277.490445 463.99957 304.00043z" fill="#2D7DDB" p-id="1710"></path><path d="M512 768c-17.664722 0-32.00086-14.303454-32.00086-32.00086L479.99914 448c0-17.664722 14.336138-32.00086 32.00086-32.00086s32.00086 14.336138 32.00086 32.00086l0 287.99914C544.00086 753.696546 529.664722 768 512 768z" fill="#2D7DDB" p-id="1711"></path></svg>
              </div>
              <div class="session-info">
                <span class="session-topic">{{ session.knowledge_point }}</span>
                <div class="session-stats">
                  <span class="stat-item">答题数: {{ session.answered_count }}</span>
                  <span class="stat-item">正确数: {{ session.correct_count }}</span>
                  <span class="stat-item">正确率: {{ session.answered_count > 0 ? Math.round(session.correct_count / session.answered_count * 100) : 0 }}%</span>
                </div>
                <span class="session-time">完成时间: {{ formatTime(session.completed_at) }}</span>
              </div>
            </div>
          </div>
          
          <div v-else-if="activeTab === 'total' && (!currentData?.items || currentData.items.length === 0)" class="empty-state">
            <img :src="emptyStatus" alt="空状态" class="empty-img" />
            <p>暂无学习记录</p>
            <span class="empty-tip">继续学习，积累更多知识点吧</span>
          </div>
          
          <div v-else-if="activeTab === 'total'" class="total-list">
            <div 
              v-for="item in (currentData?.items || [])" 
              :key="item.id"
              class="total-item"
            >
              <div class="total-info">
                <div class="total-header">
                  <span class="total-topic">{{ item.knowledge_point }}</span>
                  <span class="total-label" :class="{ 'green': item.mastery_points > 0 }">
                    {{ item.mastery_label }}
                  </span>
                </div>
                <div class="total-bar">
                  <div 
                    class="total-fill" 
                    :style="{ width: (item.mastery_points * 100) + '%' }"
                  ></div>
                </div>
                <div class="total-stats">
                  <span class="stat-item">练习次数: {{ item.total_practiced }}</span>
                  <span class="stat-item">正确次数: {{ item.total_correct }}</span>
                  <span class="stat-item">掌握度: {{ item.mastery_points }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="dialog-footer">
        <button class="btn-close" @click="handleClose">关闭</button>
      </div>
    </div>
  </div>
</template>



<style scoped>
.review-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 20;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.review-dialog {
  width: 820px;
  min-height: 80vh;
  max-height: 80vh;
  background: var(--bg-card, #ffffff);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  justify-content: space-between;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    transform: translateY(30px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 16px 24px;
  border-bottom: 1px solid var(--border-color, #e8ecf1);
  flex-shrink: 0;
}

.dialog-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-title, #1a1a2e);
}

.dialog-close {
  font-size: 28px;
  line-height: 1;
  color: var(--text-secondary, #8c8c8c);
  cursor: pointer;
  transition: all 0.2s;
  width: 36px;
  height: 36px;
  padding-bottom: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.dialog-close:hover {
  background: var(--bg-hover, #f5f5f5);
  color: var(--text-body, #333);
}

.dialog-body {
  padding: 16px 24px;
  flex: 1;
  overflow-y: auto;
  min-height: 50vh;
  max-height: 60vh;
}

.dialog-body::-webkit-scrollbar {
  width: 6px;
}

.dialog-body::-webkit-scrollbar-track {
  background: transparent;
}

.dialog-body::-webkit-scrollbar-thumb {
  background: var(--border-color, #d0d5dd);
  border-radius: 3px;
}

.loading-wrapper {
  margin-top: 150px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-secondary, #8c8c8c);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-color, #e8ecf1);
  border-top-color: var(--primary, #409eff);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-wrapper {
  margin-top: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.empty-icon {
  font-size: 56px;
}

.empty-state {
  margin-top: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.empty-img {
  width: 180px;
  opacity: 0.8;
}

.empty-state p {
  font-size: 16px;
  color: var(--text-body, #333);
  margin: 0;
}

.empty-state .empty-tip {
  font-size: 14px;
  color: var(--text-gray, #64748B);
}

.empty-wrapper p {
  font-size: 16px;
  color: var(--text-body, #333);
  margin: 8px 0 0 0;
}

.empty-tip {
  font-size: 14px;
  color: var(--text-secondary, #8c8c8c);
}

.tabs-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 20px;
  background: var(--bg-page, #f5f7fa);
  border-radius: 12px;
  margin-bottom: 16px;
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 12px 24px;
  border-radius: 8px;
  transition: all 0.2s;
}

.tab-item:hover {
  background: rgba(45, 125, 219, 0.1);
}

.tab-item.active {
  background: var(--primary, #2D7DDB);
}

.tab-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary, #2D7DDB);
  transition: all 0.2s;
}

.tab-item.active .tab-value {
  color: #fff;
}

.tab-label {
  font-size: 14px;
  color: var(--text-gray, #64748B);
  transition: all 0.2s;
}

.tab-item.active .tab-label {
  color: rgba(255, 255, 255, 0.85);
}

.tab-divider {
  width: 1px;
  height: 40px;
  background: var(--border-color, #e8ecf1);
}

.reminder-message {
  padding: 12px 16px;
  background: var(--coming-bg-color, #fcf4e8);
  border-radius: 8px;
  color: var(--coming, #E6A23C);
  font-size: 14px;
  margin-bottom: 20px;
}

.grouped-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.group-item {
  background: var(--bg-page, #f5f7fa);
  border-radius: 12px;
  overflow: hidden;
}

.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--primary-light, #EFF6FF);
}

.group-tag {
  font-size: 15px;
  font-weight: 600;
  color: var(--primary, #2D7DDB);
}

.group-count {
  font-size: 13px;
  color: var(--text-gray, #64748B);
}

.item-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.review-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: var(--bg-card, #ffffff);
  border-radius: 10px;
  border: 1px solid var(--border-color, #e8ecf1);
  transition: all 0.2s;
}

.review-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.review-item.low-mastery {
  opacity: 0.7;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.item-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-body, #333);
}

.mastery-label {
  font-size: 12px;
  color: var(--text-gray, #64748B);
  padding: 2px 8px;
  background: #f4f4f5;
  border-radius: 4px;
  display: inline-block;
  width: fit-content;
}

.mastery-label.green {
  color: var(--pass, #67C23A);
  background: var(--pass-bg-color, #effbe8);
}

.mastery-bar {
  width: 200px;
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
}

.mastery-fill {
  height: 100%;
  background: var(--primary, #2D7DDB);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.mastery-points {
  font-size: 12px;
  color: var(--text-gray, #64748B);
}

.item-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  margin-left: 16px;
}

.btn-practice,
.btn-theory {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-weight: 500;
  white-space: nowrap;
}

.btn-practice {
  background: var(--primary-light, #EFF6FF);
  color: var(--primary, #2D7DDB);
}

.btn-practice:hover {
  background: var(--primary-fade, #DBEAFE);
}

.btn-theory {
  background: var(--pass-bg-color, #effbe8);
  color: var(--pass, #67C23A);
}

.btn-theory:hover {
  background: var(--pass-shadow, #c7e3c7);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 12px 24px 20px 24px;
  border-top: 1px solid var(--border-color, #e8ecf1);
  flex-shrink: 0;
}

.btn-close {
  padding: 8px 28px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #d0d5dd);
  background: transparent;
  color: var(--text-body, #333);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-close:hover {
  background: var(--bg-hover, #f5f5f5);
  border-color: var(--text-secondary, #8c8c8c);
}

.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 16px;
  background: var(--bg-card, #ffffff);
  border-radius: 12px;
  border: 1px solid var(--border-color, #e8ecf1);
  transition: all 0.2s;
}

.session-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.session-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-light, #EFF6FF);
  border-radius: 12px;
  margin-right: 16px;
}

.session-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.session-topic {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #1a1a2e);
}

.session-stats {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.stat-item {
  font-size: 13px;
  color: var(--text-gray, #64748B);
}

.session-time {
  font-size: 12px;
  color: var(--text-gray, #64748B);
}

.total-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.total-item {
  padding: 16px;
  background: var(--bg-card, #ffffff);
  border-radius: 12px;
  border: 1px solid var(--border-color, #e8ecf1);
  transition: all 0.2s;
}

.total-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.total-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.total-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.total-topic {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #1a1a2e);
  flex: 1;
  margin-right: 12px;
}

.total-label {
  font-size: 12px;
  color: var(--text-gray, #64748B);
  padding: 3px 10px;
  background: #f4f4f5;
  border-radius: 4px;
  flex-shrink: 0;
}

.total-label.green {
  color: var(--pass, #67C23A);
  background: var(--pass-bg-color, #effbe8);
}

.total-bar {
  width: 100%;
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
}

.total-fill {
  height: 100%;
  background: var(--primary, #2D7DDB);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.total-stats {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}
</style>
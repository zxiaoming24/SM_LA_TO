<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showLoadingToast, closeToast } from 'vant'
import { reviewRemindApi, reviewRemindSevenDaysApi, reviewRemindTotalApi, getSessionIdApi, markEvaluateReportNotifyAsReadApi, getEvaluateReportNotifyApi } from '@/api/mainApi/layout.js'
import { colearningNoticeApi } from '@/api/mainApi/partners.js'
import { saveSkip } from '@/utils/skip.js'

const router = useRouter()

const userId = ref('')
const loading = ref(false)

// ==================== 复习提醒 ====================
const reminder = ref(null)
const reminderData = ref({
  today_due_count: 0,
  seven_days_count: 0,
  total_count: 0
})
const reviewTab = ref('due')
const reviewCurrentData = ref(null)

// ==================== 共学通知 ====================
const notifications = ref([])

// ==================== 评估报告通知 ====================
const evaluateNotifications = ref([])
const evaluateUnreadCount = ref(0)

// ==================== Tab 切换 ====================
const activeMainTab = ref('review')

const switchMainTab = (tab) => {
  activeMainTab.value = tab
}

// ==================== 复习提醒功能 ====================
const fetchReviewReminder = async () => {
  if (!userId.value) return
  loading.value = true
  try {
    const [res1, res2, res3] = await Promise.all([
      reviewRemindApi(userId.value),
      reviewRemindSevenDaysApi(userId.value),
      reviewRemindTotalApi(userId.value)
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
    await fetchReviewTabData('due')
  } catch (e) {
    console.error('获取复习提醒失败:', e)
    reminder.value = null
  } finally {
    loading.value = false
  }
}

const switchReviewTab = async (tab) => {
  if (reviewTab.value === tab) return
  reviewTab.value = tab
  await fetchReviewTabData(tab)
}

const fetchReviewTabData = async (tab) => {
  loading.value = true
  try {
    let res
    switch (tab) {
      case 'due':
        res = await reviewRemindApi(userId.value)
        if (res.code === 1 && res.data && res.data.reminder) {
          reminder.value = res.data.reminder
          reviewCurrentData.value = res.data.reminder
        }
        break
      case 'sevenDays':
        res = await reviewRemindSevenDaysApi(userId.value)
        if (res.code === 1 && res.data) {
          reviewCurrentData.value = res.data
        }
        break
      case 'total':
        res = await reviewRemindTotalApi(userId.value)
        if (res.code === 1 && res.data) {
          reviewCurrentData.value = res.data
        }
        break
    }
  } catch (e) {
    console.error('获取数据失败:', e)
  } finally {
    loading.value = false
  }
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

const handleGeneratePractice = async (topic) => {
  try {
    showLoadingToast({ message: '正在生成...', forbidClick: true })
    const res = await getSessionIdApi({
      user_id: userId.value,
      knowledge_point: topic,
      total_questions: 5
    })
    closeToast()
    if (res.success && res.session_id) {
      navigateToAiAnswer(`帮我生成用于复习的关于${topic}的编程题`, res.session_id)
    } else {
      showToast('获取会话ID失败')
    }
  } catch (e) {
    closeToast()
    showToast('生成失败，请稍后重试')
  }
}

const handleGenerateTheory = async (topic) => {
  try {
    showLoadingToast({ message: '正在生成...', forbidClick: true })
    const res = await getSessionIdApi({
      user_id: userId.value,
      knowledge_point: topic,
      total_questions: 5
    })
    closeToast()
    if (res.success && res.session_id) {
      navigateToAiAnswer(`帮我生成用于复习的关于${topic}的理论题`, res.session_id)
    } else {
      showToast('获取会话ID失败')
    }
  } catch (e) {
    closeToast()
    showToast('生成失败，请稍后重试')
  }
}

const navigateToAiAnswer = (message, sessionId) => {
  saveSkip(10, '', '', sessionId, message)
  router.push('/phone/chat')
}

// ==================== 共学通知 ====================
const fetchNotifications = async () => {
  if (!userId.value) return
  try {
    const res = await colearningNoticeApi(userId.value)
    if (res.code === 1 && res.data) {
      notifications.value = res.data.accepted || []
    }
  } catch (e) {
    console.error('获取共学通知失败:', e)
  }
}

const goToStudy = () => {
  router.push({ path: '/phone/partners', query: { tab: 'tg-study' } })
}

const goToPairProgramming = () => {
  router.push({ path: '/phone/partners', query: { tab: 'tg-study' } })
}

// ==================== 评估报告通知 ====================
const fetchEvaluateNotifications = async () => {
  if (!userId.value) return
  try {
    const res = await getEvaluateReportNotifyApi(userId.value)
    if (res.code === 1 && res.data) {
      evaluateNotifications.value = res.data.notifications || []
      evaluateUnreadCount.value = res.data.unread_count || 0
    }
  } catch (e) {
    console.error('获取评估报告通知失败:', e)
  }
}

const goToEvaluate = (assessmentId) => {
  if (assessmentId) {
    markEvaluateRead(assessmentId)
  }
  router.push('/phone/evaluate')
}

const markEvaluateRead = async (assessmentId) => {
  try {
    await markEvaluateReportNotifyAsReadApi(userId.value, { assessment_id: assessmentId })
    evaluateNotifications.value.forEach(item => {
      if (item.assessment_id === assessmentId) {
        item.read = true
      }
    })
    evaluateUnreadCount.value = evaluateNotifications.value.filter(n => !n.read).length
  } catch (e) {
    console.error('标记已读失败:', e)
  }
}

// ==================== 资源类型映射 ====================
const getResourceTypeLabel = (type) => {
  const map = {
    'doc': '讲解文档', 'document': '讲解文档',
    'practice': '编程题', 'mindmap': '思维导图',
    'extension': '拓展阅读', 'video': '视频',
    'animation': '动画', 'ppt': 'PPT', 'question': '试卷'
  }
  return map[type] || type || '未知'
}

const getTagClass = (type) => {
  const classMap = {
    'doc': 'tag-primary', 'extension': 'tag-success',
    'practice': 'tag-warning', 'video': 'tag-danger',
    'default': 'tag-info', 'mindmap': 'tag-default'
  }
  return classMap[type] || 'tag-default'
}

// ==================== 轮询 ====================
let reviewPollingTimer = null
let notifyPollingTimer = null
const isPollingActive = ref(true)

const startPolling = () => {
  isPollingActive.value = true
  pollReviewCount()
  pollNotificationCount()
}

const stopPolling = () => {
  isPollingActive.value = false
  if (reviewPollingTimer) { clearTimeout(reviewPollingTimer); reviewPollingTimer = null }
  if (notifyPollingTimer) { clearTimeout(notifyPollingTimer); notifyPollingTimer = null }
}

const pollReviewCount = async () => {
  if (!isPollingActive.value || !userId.value) return
  try {
    const res = await reviewRemindApi(userId.value)
    if (res.code === 1 && res.data && res.data.reminder) {
      reminderData.value.today_due_count = res.data.reminder.today_due_count || 0
    }
  } catch (e) {}
  if (isPollingActive.value) {
    reviewPollingTimer = setTimeout(pollReviewCount, 30000)
  }
}

const pollNotificationCount = async () => {
  if (!isPollingActive.value || !userId.value) return
  try {
    const [colearnRes, evalRes] = await Promise.all([
      colearningNoticeApi(userId.value),
      getEvaluateReportNotifyApi(userId.value)
    ])
    if (colearnRes.code === 1 && colearnRes.data) {
      notifications.value = colearnRes.data.accepted || []
    }
    if (evalRes.code === 1 && evalRes.data) {
      evaluateNotifications.value = evalRes.data.notifications || []
      evaluateUnreadCount.value = evalRes.data.unread_count || 0
    }
  } catch (e) {}
  if (isPollingActive.value) {
    notifyPollingTimer = setTimeout(pollNotificationCount, 30000)
  }
}

// ==================== 初始化 ====================
onMounted(async () => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      userId.value = typeof user.id === 'string' ? user.id : String(user.id)
    } catch (e) {}
  }
  if (userId.value) {
    fetchReviewReminder()
    fetchNotifications()
    fetchEvaluateNotifications()
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="notification-page">
    <!-- 顶部导航 -->
    <div class="page-header">
      <van-icon name="arrow-left" size="20" color="var(--text-title)" @click="$router.back()" />
      <span class="page-title">消息通知</span>
      <span class="header-count" v-if="reminderData.today_due_count + evaluateUnreadCount + notifications.length > 0">
        {{ reminderData.today_due_count + evaluateUnreadCount + notifications.length }}
      </span>
    </div>

    <!-- 主 Tab 切换 -->
    <div class="main-tabs">
      <div
        class="main-tab"
        :class="{ active: activeMainTab === 'review' }"
        @click="switchMainTab('review')"
      >
        📚 复习提醒
        <span v-if="reminderData.today_due_count > 0" class="tab-badge">{{ reminderData.today_due_count }}</span>
      </div>
      <div
        class="main-tab"
        :class="{ active: activeMainTab === 'notification' }"
        @click="switchMainTab('notification')"
      >
        🔔 消息通知
        <span v-if="evaluateUnreadCount + notifications.length > 0" class="tab-badge">{{ evaluateUnreadCount + notifications.length }}</span>
      </div>
    </div>

    <!-- 复习提醒 -->
    <div v-if="activeMainTab === 'review'" class="tab-content">
      <div v-if="loading" class="loading-wrapper">
        <van-loading type="spinner" size="24px" color="var(--primary)">加载中...</van-loading>
      </div>

      <div v-else-if="!reminder" class="empty-wrapper">
        <van-icon name="books-o" size="64" color="var(--border-color)" />
        <p>暂无复习内容</p>
        <span>继续学习，积累更多知识点吧</span>
      </div>

      <div v-else class="review-content">
        <!-- 子 Tab -->
        <div class="sub-tabs">
          <div
            class="sub-tab"
            :class="{ active: reviewTab === 'due' }"
            @click="switchReviewTab('due')"
          >
            <span class="sub-tab-value">{{ reminderData.today_due_count || 0 }}</span>
            <span class="sub-tab-label">待复习</span>
          </div>
          <div class="tab-divider"></div>
          <div
            class="sub-tab"
            :class="{ active: reviewTab === 'sevenDays' }"
            @click="switchReviewTab('sevenDays')"
          >
            <span class="sub-tab-value">{{ reminderData.seven_days_count || 0 }}</span>
            <span class="sub-tab-label">近7天</span>
          </div>
          <div class="tab-divider"></div>
          <div
            class="sub-tab"
            :class="{ active: reviewTab === 'total' }"
            @click="switchReviewTab('total')"
          >
            <span class="sub-tab-value">{{ reminderData.total_count || 0 }}</span>
            <span class="sub-tab-label">总计</span>
          </div>
        </div>

        <!-- 复习提示消息 -->
        <div v-if="reviewTab === 'due' && reminder.message" class="reminder-message">
          {{ reminder.message }}
        </div>

        <!-- 待复习列表 -->
        <div v-if="reviewTab === 'due'">
          <div v-if="!reviewCurrentData?.grouped_due || Object.keys(reviewCurrentData.grouped_due).length === 0" class="empty-section">
            <van-icon name="clock-o" size="40" color="var(--border-color)" />
            <p>暂无待复习内容</p>
          </div>
          <div v-else class="grouped-list">
            <div
              v-for="(items, groupName) in reviewCurrentData.grouped_due"
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
                      <div class="mastery-fill" :style="{ width: (item.mastery_points * 100) + '%' }"></div>
                    </div>
                    <span class="mastery-points">掌握度: {{ item.mastery_points }}</span>
                  </div>
                  <div class="item-actions">
                    <van-button size="small" type="primary" plain @click="handleGeneratePractice(item.topic)">生成编程题复习</van-button>
                    <van-button size="small" type="warning" plain @click="handleGenerateTheory(item.topic)">生成理论题试卷复习</van-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 近7天记录 -->
        <div v-else-if="reviewTab === 'sevenDays'">
          <div v-if="!reviewCurrentData?.sessions || reviewCurrentData.sessions.length === 0" class="empty-section">
            <van-icon name="clock-o" size="40" color="var(--border-color)" />
            <p>暂无近7天复习记录</p>
          </div>
          <div v-else class="sessions-list">
            <div
              v-for="session in reviewCurrentData.sessions"
              :key="session.session_id"
              class="session-item"
            >
              <div class="session-icon">📝</div>
              <div class="session-info">
                <span class="session-title">{{ session.topic || '复习内容' }}</span>
                <span class="session-time">{{ formatTime(session.created_at) }}</span>
                <span class="session-duration">时长: {{ session.duration || 0 }}分钟</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 总计 -->
        <div v-else-if="reviewTab === 'total'">
          <div v-if="!reviewCurrentData?.sessions || reviewCurrentData.sessions.length === 0" class="empty-section">
            <van-icon name="orders-o" size="40" color="var(--border-color)" />
            <p>暂无复习记录</p>
          </div>
          <div v-else class="sessions-list">
            <div
              v-for="session in reviewCurrentData.sessions"
              :key="session.session_id"
              class="session-item"
            >
              <div class="session-icon">📝</div>
              <div class="session-info">
                <span class="session-title">{{ session.topic || '复习内容' }}</span>
                <span class="session-time">{{ formatTime(session.created_at) }}</span>
                <span class="session-duration">时长: {{ session.duration || 0 }}分钟</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 消息通知 -->
    <div v-else class="tab-content">
      <!-- 空状态 -->
      <div v-if="notifications.length === 0 && evaluateNotifications.length === 0" class="empty-wrapper">
        <van-icon name="chat-o" size="64" color="var(--border-color)" />
        <p>暂无通知</p>
        <span>暂无消息通知</span>
      </div>

      <!-- 共学通知 -->
      <div v-if="notifications.length > 0" class="notification-section">
        <h4 class="section-title">共学通知</h4>
        <div class="collect-list">
          <div
            v-for="item in notifications"
            :key="item.id"
            class="collect-item"
          >
            <div class="collect-info">
              <span class="resource-tag" :class="getTagClass(item.resource_type)">
                {{ getResourceTypeLabel(item.resource_type) }}
              </span>
              <span class="resource-tag" :class="item.mode === 'pair' ? 'mode-pair' : 'mode-separate'">
                {{ item.mode === 'pair' ? '结对编程' : '独立学习' }}
              </span>
              <span class="collect-time">{{ formatTime(item.responded_at || item.created_at) }}</span>
            </div>
            <div class="collect-title-row">
              <span class="collect-title">{{ item.title || '未命名资源' }}</span>
              <div class="collect-actions">
                <van-button
                  v-if="item.status === 'accepted' && item.mode === 'separate'"
                  size="small"
                  type="primary"
                  @click="goToStudy"
                >去学习</van-button>
                <van-button
                  v-if="item.status === 'accepted' && item.mode === 'pair'"
                  size="small"
                  type="primary"
                  @click="goToPairProgramming"
                >去结对编程</van-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 评估报告通知 -->
      <div v-if="evaluateNotifications.length > 0" class="notification-section">
        <h4 class="section-title">评估报告通知</h4>
        <div class="collect-list">
          <div
            v-for="item in evaluateNotifications"
            :key="item.assessment_id"
            class="collect-item evaluate-item"
          >
            <div class="collect-info">
              <span class="resource-tag tag-evaluate">评估报告</span>
              <span class="resource-tag" :class="item.read ? 'tag-read' : 'tag-unread'">
                {{ item.read ? '已读' : '未读' }}
              </span>
              <span class="collect-title">{{ item.title }}</span>
              <span class="collect-time">{{ formatTime(item.timestamp) }}</span>
            </div>
            <div class="collect-content">{{ item.content }}</div>
            <div class="evaluate-btn">
              <van-button
                v-if="!item.read"
                size="small"
                plain
                @click="markEvaluateRead(item.assessment_id)"
              >标记已读</van-button>
              <van-button
                size="small"
                type="primary"
                @click="goToEvaluate(item.assessment_id)"
              >查看报告</van-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notification-page {
  min-height: 100vh;
  background: var(--bg-page);
  padding-bottom: 60px;
}

/* 顶部导航 */
.page-header {
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

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

.header-count {
  font-size: 12px;
  background: var(--primary);
  color: #fff;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

/* 主 Tab */
.main-tabs {
  display: flex;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.main-tab {
  flex: 1;
  padding: 12px 8px;
  text-align: center;
  font-size: 14px;
  color: var(--text-gray);
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.main-tab.active {
  color: var(--primary);
  font-weight: 600;
}

.main-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 20%;
  right: 20%;
  height: 3px;
  background: var(--primary);
  border-radius: 2px;
}

.tab-badge {
  font-size: 10px;
  background: var(--main-delete);
  color: #fff;
  padding: 0 5px;
  border-radius: 8px;
  min-width: 16px;
  height: 14px;
  line-height: 14px;
  display: inline-block;
  text-align: center;
  font-weight: 600;
}

/* Tab 内容 */
.tab-content {
  padding: 12px;
}

.loading-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 60px 0;
}

.empty-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 8px;
  color: var(--text-gray);
}

.empty-wrapper p {
  font-size: 15px;
  color: var(--text-body);
  margin-top: 12px;
}

.empty-wrapper span {
  font-size: 13px;
  color: var(--text-gray);
}

.empty-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
  gap: 8px;
  color: var(--text-gray);
}

.empty-section p {
  font-size: 14px;
  color: var(--text-body);
}

/* 复习 - 子 Tab */
.sub-tabs {
  display: flex;
  align-items: center;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 4px;
  margin-bottom: 12px;
  border: 1px solid var(--border-color);
}

.sub-tab {
  flex: 1;
  text-align: center;
  padding: 8px 4px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sub-tab.active {
  background: var(--primary);
  color: #fff;
}

.sub-tab-value {
  font-size: 16px;
  font-weight: 700;
}

.sub-tab-label {
  font-size: 11px;
}

.tab-divider {
  width: 1px;
  height: 24px;
  background: var(--border-color);
}

.reminder-message {
  padding: 10px 12px;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: var(--radius-md);
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.5;
}

/* 分组列表 */
.grouped-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-item {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 12px;
  border: 1px solid var(--border-color);
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.group-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  padding: 2px 8px;
  border-radius: 4px;
  white-space: normal;
  word-break: break-all;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  line-clamp: 1;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  max-width: 80%;
}

.group-count {
  font-size: 12px;
  color: var(--text-gray);
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.review-item {
  background: var(--bg-page);
  border-radius: var(--radius-md);
  padding: 10px;
  border: 1px solid var(--border-color);
}

.review-item.low-mastery {
  border-color: var(--main-delete);
  background: rgba(245, 108, 108, 0.05);
}

.item-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
}

.mastery-label {
  font-size: 12px;
  color: var(--main-delete);
}

.mastery-label.green {
  color: var(--pass);
}

.mastery-bar {
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.mastery-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s;
}

.mastery-points {
  font-size: 11px;
  color: var(--text-gray);
}

.item-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* 会话列表 */
.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item {
  display: flex;
  gap: 10px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  border: 1px solid var(--border-color);
}

.session-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
}

.session-time {
  font-size: 11px;
  color: var(--text-gray);
}

.session-duration {
  font-size: 11px;
  color: var(--text-gray);
}

/* 通知区域 */
.notification-section {
  margin-bottom: 16px;
}

.notification-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid var(--primary);
}

.collect-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.collect-item {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  border: 1px solid var(--border-color);
}

.collect-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.resource-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.mode-separate {
  background: #e8f3ff;
  color: #3370ff;
}

.mode-pair {
  background: #f0e8ff;
  color: #7b4cff;
}

.tag-primary { background: #ecf5ff; color: #409eff; }
.tag-success { background: #f0f9eb; color: #67c23a; }
.tag-warning { background: #fdf6ec; color: #e6a23c; }
.tag-danger { background: #fef0f0; color: #f56c6c; }
.tag-info { background: #f4f4f5; color: #909399; }
.tag-default { background: #f4f4f5; color: #909399; }

.collect-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.collect-title {
  font-size: 13px;
  color: var(--text-body);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.collect-time {
  font-size: 11px;
  color: var(--text-gray);
  flex-shrink: 0;
}

.collect-actions {
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

.evaluate-item {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.collect-content {
  font-size: 12px;
  color: var(--text-gray);
  line-height: 1.5;
  padding: 4px 0;
}

.evaluate-btn {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
}

.tag-evaluate {
  background: #fef0f0;
  color: #f56c6c;
}

.tag-read {
  background: #f4f4f5;
  color: #909399;
}

.tag-unread {
  background: #ecf5ff;
  color: #409eff;
}
</style>

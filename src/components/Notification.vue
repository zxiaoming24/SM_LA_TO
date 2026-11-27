<!-- layout 消息通知：弹窗组件 -->

<!-- components/Notification.vue -->
<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  notifications: {
    type: Array,
    default: () => []
  },
  evaluateNotifications: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:visible', 'close', 'markEvaluateRead'])

const router = useRouter()
const dialogVisible = ref(false)
const scrollContainer = ref(null)

// 资源类型映射
const getResourceTypeLabel = (type) => {
  const map = {
    'doc': '讲解文档',
    'document': '讲解文档',
    'practice': '编程题',
    'mindmap': '思维导图',
    'extension': '拓展阅读',
    'video': '视频',
    'animation': '动画',
    'ppt': 'PPT',
    'question': '试卷'
  }
  return map[type] || type || '未知'
}

// 资源类型样式映射
const getTagClass = (type) => {
  const classMap = {
    'doc': 'tag-primary',
    'extension': 'tag-success',
    'practice': 'tag-warning',
    'video': 'tag-danger',
    'default': 'tag-info',
    'mindmap': 'tag-default'
  }
  return classMap[type] || 'tag-default'
}

// 监听visible变化
watch(() => props.visible, (newVal) => {
  dialogVisible.value = newVal
  if (newVal) {
    document.body.style.overflow = 'hidden'
    nextTick(() => {
      if (scrollContainer.value) {
        scrollContainer.value.scrollTop = 0
      }
    })
  } else {
    document.body.style.overflow = ''
  }
}, { immediate: true })

// 监听dialogVisible变化，同步到父组件
watch(dialogVisible, (newVal) => {
  if (!newVal) {
    document.body.style.overflow = ''
    emit('update:visible', false)
    emit('close')
  }
})

// 关闭弹窗（仅通过×按钮）
const closeDialog = () => {
  dialogVisible.value = false
}

// 处理遮罩点击（不关闭）
const handleMaskClick = (e) => {
  if (e.target === e.currentTarget) {
    return
  }
}

// 去学习
const goToStudy = () => {
  dialogVisible.value = false
  document.body.style.overflow = ''
  router.push({ path: '/partners', query: { tab: 'tg-study' } })
}

// 去结对编程
const goToPairProgramming = () => {
  dialogVisible.value = false
  document.body.style.overflow = ''
  router.push({ path: '/partners', query: { tab: 'tg-study' } })
}

// 去评估报告
const goToEvaluate = (assessmentId) => {
  dialogVisible.value = false
  document.body.style.overflow = ''
  emit('markEvaluateRead', assessmentId)
  router.push('/evaluate')
}

// 标记评估报告通知为已读
const markEvaluateRead = (assessmentId) => {
  emit('markEvaluateRead', assessmentId)
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

// 组件卸载时恢复滚动
onUnmounted(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <div v-if="dialogVisible" class="collect-overlay">
    <div class="collect-dialog">
      <div class="dialog-header">
        <span class="dialog-title">消息通知</span>
        <span class="dialog-close" @click="closeDialog">×</span>
      </div>
      
      <div class="dialog-body" ref="scrollContainer">
        <div v-if="notifications.length === 0 && evaluateNotifications.length === 0" class="empty-wrapper">
          <div class="empty-icon">
            <svg t="1782116572531" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1714" width="100" height="100"><path d="M439.9 359.2l-99.7-156.3h-81.4c-66.5 0-120.5 53.9-120.5 120.5v294.9h751.4V359.2H439.9z" fill="#2867CE" p-id="1715"></path><path d="M769.3 871.6H258.7c-92.9 0-168.5-75.6-168.5-168.5V323.3c0-92.9 75.6-168.5 168.5-168.5h81.4c16.4 0 31.7 8.4 40.5 22.2l85.5 134.1h423.5c26.6 0 48.1 21.5 48.1 48.1v343.9c0.1 92.9-75.5 168.5-168.4 168.5zM258.7 250.9c-39.9 0-72.4 32.5-72.4 72.4v379.8c0 39.9 32.5 72.4 72.4 72.4h510.5c39.9 0 72.4-32.5 72.4-72.4V407.3H439.9c-16.4 0-31.7-8.4-40.5-22.2L313.9 251h-55.2z" fill="#BDD2EF" p-id="1716"></path><path d="M840.2 272.7h-314l-69.6-109.2h383.6z" fill="#2867CE" p-id="1717"></path></svg>
          </div>
          <p>暂无通知</p>
          <span class="empty-tip">暂无消息通知</span>
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
                <span class="collect-title" :title="item.title || '未命名资源'">
                  {{ item.title || '未命名资源' }}
                </span>
                <span class="collect-time">{{ formatTime(item.responded_at || item.created_at) }}</span>
              </div>
              <div class="collect-actions">
                <button 
                  v-if="item.status === 'accepted' && item.mode === 'separate'"
                  class="btn-view"
                  @click="goToStudy"
                >
                  去学习
                </button>
                <button 
                  v-if="item.status === 'accepted' && item.mode === 'pair'"
                  class="btn-view"
                  @click="goToPairProgramming"
                >
                  去结对编程
                </button>
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
                <span class="collect-title" :title="item.title">{{ item.title }}</span>
                <span class="collect-time">{{ formatTime(item.timestamp) }}</span>
              </div>
              <div class="collect-content">{{ item.content }}</div>
              <div class="evaluate-btn">
                <button 
                  v-if="!item.read"
                  class="btn-mark-read"
                  @click="markEvaluateRead(item.assessment_id)"
                >
                  标记已读
                </button>
                <button 
                  class="btn-view"
                  @click="goToEvaluate(item.assessment_id)"
                >
                  查看报告
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="dialog-footer">
        <span class="collect-count">共 {{ notifications.length + evaluateNotifications.length }} 条通知</span>
        <button class="btn-close" @click="closeDialog">关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.collect-overlay {
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
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.collect-dialog {
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
  min-height: 65vh;
  max-height: 65vh;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
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

.dialog-body::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary, #8c8c8c);
}

.empty-wrapper {
  margin-top: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 8px;
}

.empty-icon {
  font-size: 56px;
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

.collect-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.collect-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: var(--bg-page, #f5f7fa);
  border-radius: 10px;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.collect-item:hover {
  background: var(--bg-card, #ffffff);
  border-color: var(--border-color, #e8ecf1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.collect-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.resource-tag {
  display: inline-block;
  padding: 2px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

.mode-separate {
  background: #e8f3ff;
  color: #3370ff;
}

.mode-pair {
  background: #f0e8ff;
  color: #7b4cff;
}

.tag-primary {
  background: #ecf5ff;
  color: #409eff;
}

.tag-success {
  background: #f0f9eb;
  color: #67c23a;
}

.tag-warning {
  background: #fdf6ec;
  color: #e6a23c;
}

.tag-danger {
  background: #fef0f0;
  color: #f56c6c;
}

.tag-info {
  background: #f4f4f5;
  color: #909399;
}

.tag-default {
  background: #f4f4f5;
  color: #909399;
}

.collect-title {
  font-size: 15px;
  color: var(--text-body, #333);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.collect-time {
  font-size: 13px;
  color: var(--text-secondary, #8c8c8c);
  white-space: nowrap;
  flex-shrink: 0;
}

.collect-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  margin-left: 12px;
}

.evaluate-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.btn-view {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-weight: 500;
  white-space: nowrap;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  height: 32px;
  background: var(--primary, #409eff);
  color: #fff;
}

.btn-view:hover {
  background: #66b1ff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.btn-view:active {
  transform: translateY(0);
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px 20px 24px;
  border-top: 1px solid var(--border-color, #e8ecf1);
  flex-shrink: 0;
}

.collect-count {
  font-size: 14px;
  color: var(--text-secondary, #8c8c8c);
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

/* -------------------- 评估报告通知样式 -------------------- */
.notification-section {
  margin-bottom: 24px;
}
.notification-section:last-child {
  margin-bottom: 0;
}

.notification-section .section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title, #1a1a2e);
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid var(--primary, #409eff);
}

.evaluate-item {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.evaluate-item .collect-info {
  width: 100%;
}

.collect-content {
  font-size: 13px;
  color: var(--text-secondary, #8c8c8c);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  padding-left: 0;
  margin-top: 4px;
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

.btn-mark-read {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid var(--border-color, #d0d5dd);
  background: transparent;
  color: var(--text-body, #333);
  font-weight: 500;
  white-space: nowrap;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  height: 32px;
}

.btn-mark-read:hover {
  background: var(--primary-light, #ecf5ff);
  border-color: var(--primary, #409eff);
  color: var(--primary, #409eff);
}

</style>
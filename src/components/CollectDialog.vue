<!-- layout 创建 收藏 弹窗组件（自定义弹窗） -->
<!-- @/components/CollectDialog.vue -->
<template>
  <!-- 遮罩层 -->
  <div v-if="visible" class="collect-overlay">
    <!-- 弹窗内容 -->
    <div class="collect-dialog">
      <!-- 标题栏 -->
      <div class="dialog-header">
        <span class="dialog-title">我的收藏</span>
        <span class="dialog-close" @click="handleClose">×</span>
      </div>
      
      <!-- 内容区域 -->
      <div class="dialog-body">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-wrapper">
          <div class="loading-spinner"></div>
          <span>加载中...</span>
        </div>
        
        <!-- 空状态 -->
        <div v-else-if="collectList.length === 0" class="empty-wrapper">
          <div class="empty-icon">
            <svg t="1782116572531" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="1714" width="100" height="100"><path d="M439.9 359.2l-99.7-156.3h-81.4c-66.5 0-120.5 53.9-120.5 120.5v294.9h751.4V359.2H439.9z" fill="#2867CE" p-id="1715"></path><path d="M769.3 871.6H258.7c-92.9 0-168.5-75.6-168.5-168.5V323.3c0-92.9 75.6-168.5 168.5-168.5h81.4c16.4 0 31.7 8.4 40.5 22.2l85.5 134.1h423.5c26.6 0 48.1 21.5 48.1 48.1v343.9c0.1 92.9-75.5 168.5-168.4 168.5zM258.7 250.9c-39.9 0-72.4 32.5-72.4 72.4v379.8c0 39.9 32.5 72.4 72.4 72.4h510.5c39.9 0 72.4-32.5 72.4-72.4V407.3H439.9c-16.4 0-31.7-8.4-40.5-22.2L313.9 251h-55.2z" fill="#BDD2EF" p-id="1716"></path><path d="M840.2 272.7h-314l-69.6-109.2h383.6z" fill="#2867CE" p-id="1717"></path></svg>
          </div>
          <p>暂无收藏内容</p>
          <span class="empty-tip">快去收藏你感兴趣的资源吧</span>
        </div>
        
        <!-- 收藏列表 -->
        <div v-else class="collect-list">
          <div 
            v-for="item in collectList" 
            :key="item.resource_id"
            class="collect-item"
          >
            <div class="collect-info">
              <!-- 资源类型标签 -->
              <span class="resource-tag" :class="getTagClass(item.resource_type)">
                {{ getResourceTypeLabel(item.resource_type) }}
              </span>
              
              <!-- 标题 -->
              <span class="collect-title" :title="item.title || '未命名资源'">
                {{ item.title || '未命名资源' }}
              </span>
              
              <!-- 创建时间 -->
              <span class="collect-time">{{ formatTime(item.created_at) }}</span>
            </div>
            
            <div class="collect-actions">
              <!-- 查看按钮 -->
              <button 
                class="btn-view"
                @click="handleView(item)"
              >
                查看
              </button>
              
              <!-- 取消收藏按钮 -->
              <button 
                class="btn-cancel"
                :disabled="cancelLoadingMap[item.resource_id]"
                @click="handleCancelCollect(item)"
              >
                <span v-if="cancelLoadingMap[item.resource_id]" class="btn-loading"></span>
                <span v-else>取消收藏</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 底部 -->
      <div class="dialog-footer">
        <span class="collect-count">共 {{ collectList.length }} 个收藏</span>
        <button class="btn-close" @click="handleClose">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElLoading } from 'element-plus'
import { collectListApi, collectCancelApi } from '@/api/mainApi/layout.js'
import { saveSkip } from '@/utils/skip.js'

// Props
// defineProps父传子，子接受用（只读）
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

// Emits
// defineEmits：子组件通过这个修改或调用父组件的变量或函数
// update:visible对应父组件的v-model:visible/:visible，一定要写成update:visible
// refresh对应父组件的refresh
const emit = defineEmits(['update:visible', 'refresh'])

const router = useRouter()
const route = useRoute()

// 响应式数据
const loading = ref(false)
const collectList = ref([])
const cancelLoadingMap = ref({})

// 资源类型映射
const resourceTypeMap = {
  'ppt': 'PPT',
  'question': '试卷',
  'doc': '讲解文档',
  'extension': '拓展阅读',
  'practice': '编程题',
  'video': '视频',
  'mindmap': '思维导图',
  'default': '其他'
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

// 获取资源类型标签
const getResourceTypeLabel = (type) => {
  return resourceTypeMap[type] || resourceTypeMap['default']
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

// 监听visible变化
watch(() => props.visible, (newVal) => {
  if (newVal) {
    document.body.style.overflow = 'hidden'
    fetchCollectList()
  } else {
    document.body.style.overflow = ''
  }
}, { immediate: true })

// 获取收藏列表
const fetchCollectList = async () => {
  if (!props.userId) {
    ElMessage.warning('用户ID不存在')
    return
  }
  
  loading.value = true
  try {
    const res = await collectListApi(props.userId)
    if (res.code === 1 && res.data && res.data.favorites) {
      collectList.value = res.data.favorites
    } else {
      collectList.value = []
      if (res.msg) {
        ElMessage.warning(res.msg)
      }
    }
  } catch (error) {
    console.error('获取收藏列表失败:', error)
    ElMessage.error('获取收藏列表失败，请稍后重试')
    collectList.value = []
  } finally {
    loading.value = false
  }
}

// 资源类型到 rsType 的映射
const resourceTypeToRsType = {
  'ppt': 0,
  'mindmap': 1,
  'doc': 2,
  'extension': 3,
  'practice': 4,
  'video': 5,
  'animation': 6,
  'question': 7
}

// 路由路径映射
const resourceTypeToRoute = {
  'ppt': '/ppt',
  'mindmap': '/mindMap',
  'doc': '/word',
  'extension': '/reading',
  'practice': '/code',
  'video': '/video',
  'animation': '/anima',
  'question': '/paper'
}

// 查看资源（跳转函数）
const handleView = (item) => {
  const rsType = resourceTypeToRsType[item.resource_type]
  const routePath = resourceTypeToRoute[item.resource_type]
  
  if (rsType === undefined || routePath === undefined) {
    ElMessage.warning(`未知资源类型: ${item.resource_type}`)
    return
  }
  
  // 保存跳转信息
  saveSkip(rsType, item.resource_id)
  
  // 关闭弹窗
  emit('update:visible', false)
  
  // 如果当前已在目标页面，显示加载状态后刷新；否则跳转
  if (route.path === routePath) {
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
    router.push(routePath)
  }
  
  console.log('查看资源:', item.resource_type, item.resource_id, 'rsType:', rsType)
}

// 取消收藏
const handleCancelCollect = async (item) => {
  const resourceId = item.resource_id
  
  // 设置加载状态
  cancelLoadingMap.value[resourceId] = true
  
  try {
    const data = {
      user_id: props.userId,
      resource_id: resourceId,
      resource_type: item.resource_type
    }
    const res = await collectCancelApi(data)
    
    if (res.code === 1) {
      ElMessage.success(res.data?.message || '取消收藏成功')
      
      // ===== 修改：重新调用获取收藏列表接口 =====
      await fetchCollectList()
      
      // 通知父组件刷新
      emit('refresh')
    } else {
      ElMessage.warning(res.data?.message || res.msg || '取消收藏失败')
    }
  } catch (error) {
    console.error('取消收藏失败:', error)
    ElMessage.error('取消收藏失败，请稍后重试')
  } finally {
    delete cancelLoadingMap.value[resourceId]
  }
}

// 关闭弹窗
const handleClose = () => {
  emit('update:visible', false)// 更新visible
}
</script>

<style scoped>
/* ===== 遮罩层 ===== */
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

/* ===== 弹窗主体 ===== */
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

/* ===== 标题栏 ===== */
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

/* ===== 内容区域 ===== */
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

/* 滚动条样式 */
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

/* ===== 加载状态 ===== */
.loading-wrapper {
  margin-top: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
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
  to {
    transform: rotate(360deg);
  }
}

/* ===== 空状态 ===== */
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

/* ===== 收藏列表 ===== */
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

/* 资源类型标签 */
.resource-tag {
  display: inline-block;
  padding: 2px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
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

/* 标题 */
.collect-title {
  font-size: 15px;
  color: var(--text-body, #333);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 时间 */
.collect-time {
  font-size: 13px;
  color: var(--text-secondary, #8c8c8c);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ===== 操作按钮 ===== */
.collect-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  margin-left: 12px;
}

.btn-view,
.btn-cancel {
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
}

.btn-view {
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

.btn-cancel {
  background: #fef0f0;
  color: #f56c6c;
}

.btn-cancel:hover:not(:disabled) {
  background: #fde2e2;
  transform: translateY(-1px);
}

.btn-cancel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-cancel:active:not(:disabled) {
  transform: translateY(0);
}

/* 按钮加载动画 */
.btn-loading {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #f56c6c;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ===== 底部 ===== */
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
</style>
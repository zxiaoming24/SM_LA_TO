<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import { collectListApi, collectCancelApi } from '@/api/mainApi/layout.js'
import { saveSkip } from '@/utils/skip.js'

const router = useRouter()

const userId = ref('')
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

const getResourceTypeLabel = (type) => {
  return resourceTypeMap[type] || resourceTypeMap['default']
}

const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hours}:${minutes}`
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

// 移动端路由映射
const resourceTypeToRoute = {
  'ppt': '/phone/resource/ppt',
  'mindmap': '/phone/resource/mindmap',
  'doc': '/phone/resource/word',
  'extension': '/phone/resource/reading',
  'practice': '/phone/resource/code',
  'video': '/phone/resource/video',
  'animation': '/phone/resource/anima',
  'question': '/phone/resource/paper'
}

// 获取收藏列表
const fetchCollectList = async () => {
  if (!userId.value) return
  loading.value = true
  try {
    const res = await collectListApi(userId.value)
    if (res.code === 1 && res.data && res.data.favorites) {
      collectList.value = res.data.favorites
    } else {
      collectList.value = []
    }
  } catch (e) {
    console.error('获取收藏列表失败:', e)
    collectList.value = []
  } finally {
    loading.value = false
  }
}

// 查看资源
const handleView = (item) => {
  const rsType = resourceTypeToRsType[item.resource_type]
  const routePath = resourceTypeToRoute[item.resource_type]

  if (rsType === undefined || routePath === undefined) {
    showToast(`未知资源类型: ${item.resource_type}`)
    return
  }

  saveSkip(rsType, item.resource_id)
  router.push(routePath)
}

// 取消收藏
const handleCancelCollect = (item) => {
  showConfirmDialog({
    title: '取消收藏',
    message: `确定要取消收藏"${item.title || '未命名资源'}"吗？`
  }).then(async () => {
    const resourceId = item.resource_id
    cancelLoadingMap.value[resourceId] = true
    try {
      const data = {
        user_id: userId.value,
        resource_id: resourceId,
        resource_type: item.resource_type
      }
      const res = await collectCancelApi(data)
      if (res.code === 1) {
        showSuccessToast(res.data?.message || '取消收藏成功')
        await fetchCollectList()
      } else {
        showToast(res.data?.message || res.msg || '取消收藏失败')
      }
    } catch (e) {
      console.error('取消收藏失败:', e)
      showToast('取消收藏失败，请稍后重试')
    } finally {
      delete cancelLoadingMap.value[resourceId]
    }
  }).catch(() => {})
}

onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      userId.value = typeof user.id === 'string' ? user.id : String(user.id)
    } catch (e) {}
  }
  if (userId.value) {
    fetchCollectList()
  }
})
</script>

<template>
  <div class="collection-page">
    <!-- 顶部导航 -->
    <div class="page-header">
      <van-icon name="arrow-left" size="20" color="var(--text-title)" @click="$router.back()" />
      <span class="page-title">我的收藏</span>
      <span class="header-count" v-if="collectList.length > 0">{{ collectList.length }}</span>
    </div>

    <!-- 内容区域 -->
    <div class="content-body">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-wrapper">
        <van-loading type="spinner" size="24px" color="var(--primary)">加载中...</van-loading>
      </div>

      <!-- 空状态 -->
      <div v-else-if="collectList.length === 0" class="empty-wrapper">
        <van-icon name="star-o" size="64" color="var(--border-color)" />
        <p>暂无收藏内容</p>
        <span>快去收藏你感兴趣的资源吧</span>
      </div>

      <!-- 收藏列表 -->
      <div v-else class="collect-list">
        <div
          v-for="item in collectList"
          :key="item.resource_id"
          class="collect-item"
        >
          <div class="collect-top">
            <span class="resource-tag" :class="getTagClass(item.resource_type)">
              {{ getResourceTypeLabel(item.resource_type) }}
            </span>
            <span class="collect-time">{{ formatTime(item.created_at) }}</span>
          </div>
          <div class="collect-title-row">
            <span class="collect-title">{{ item.title || '未命名资源' }}</span>
            <div class="collect-actions">
              <van-button
                size="small"
                type="primary"
                @click="handleView(item)"
              >查看</van-button>
              <van-button
                size="small"
                type="danger"
                plain
                :loading="cancelLoadingMap[item.resource_id]"
                @click="handleCancelCollect(item)"
              >取消收藏</van-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.collection-page {
  min-height: 100vh;
  background: var(--bg-page);
  padding-bottom: 60px;
}

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

.content-body {
  padding: 12px;
}

.loading-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 80px 0;
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

.collect-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.resource-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.tag-primary { background: #ecf5ff; color: #409eff; }
.tag-success { background: #f0f9eb; color: #67c23a; }
.tag-warning { background: #fdf6ec; color: #e6a23c; }
.tag-danger { background: #fef0f0; color: #f56c6c; }
.tag-info { background: #f4f4f5; color: #909399; }
.tag-default { background: #f4f4f5; color: #909399; }

.collect-time {
  font-size: 11px;
  color: var(--text-gray);
  flex-shrink: 0;
}

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

.collect-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
</style>

<!-- 移动端学习路线市场组件 -->
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { showToast, showConfirmDialog, showLoadingToast, closeToast } from 'vant'
import {
  categoriesApi, getRouteListApi, getRouteDetailApi, adoptRouteApi,
  deleteRouteApi, evaluateRouteApi, updateRouteApi, getAdoptedRoutesApi
} from '@/api/mainApi/pathPlanMarket.js'
import { getUserInfoApi } from '@/api/mainApi/index.js'

const props = defineProps({
  userId: { type: String, required: true }
})

const emit = defineEmits(['close', 'adopted'])

// ========== State ==========
const categories = ref([])
const routeList = ref([])
const listLoading = ref(false)
const currentCategory = ref('')
const currentSort = ref('hot')
const searchText = ref('')
let searchTimer = null

// Detail
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentRoute = ref(null)

// User info map for reviews
const userInfoMap = ref({})

// Review
const reviewRating = ref(5)
const reviewComment = ref('')

// Edit
const editVisible = ref(false)
const editForm = ref({
  name: '', subtitle: '', description: '', category: '',
  difficulty: 'medium', tagsStr: '', target_audience: '',
  estimated_duration: '', prerequisites: ''
})

// Maps
const diffLabelMap = { easy: '入门', medium: '进阶', hard: '高级', beginner: '入门', advanced: '高级' }
const diffColorMap = { easy: 'var(--pass)', medium: 'var(--coming)', hard: 'var(--main-delete)', beginner: 'var(--pass)', advanced: 'var(--main-delete)' }

// Computed
const isOwner = computed(() => {
  return String(currentRoute.value?.creator?.id) === String(props.userId)
})

const sortedReviews = computed(() => {
  const reviews = currentRoute.value?.reviews || []
  return [...reviews].sort((a, b) => {
    const timeA = new Date(a.created_at || 0).getTime()
    const timeB = new Date(b.created_at || 0).getTime()
    return timeB - timeA
  })
})

// ========== Lifecycle ==========
onMounted(() => {
  loadCategories()
  loadRoutes()
  document.body.style.overflow = 'hidden'
})

onUnmounted(() => {
  document.body.style.overflow = ''
})

// ========== Categories ==========
const loadCategories = async () => {
  try {
    const res = await categoriesApi()
    if (res.code === 1 && res.data?.success && res.data.categories) {
      categories.value = res.data.categories
    }
  } catch (e) {
    console.warn('加载分类失败:', e)
  }
}

const setCategory = (cat) => {
  currentCategory.value = cat
  loadRoutes()
}

const setSort = (sort) => {
  currentSort.value = sort
  loadRoutes()
}

const debounceSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadRoutes, 300)
}

// ========== Routes ==========
const adoptedRouteIds = ref(new Set())

const loadAdoptedRoutes = async () => {
  try {
    const res = await getAdoptedRoutesApi(String(props.userId))
    if (res.code === 1 && res.data?.success && res.data.adoptions) {
      adoptedRouteIds.value = new Set(res.data.adoptions.map(a => a.route_id))
    }
  } catch (e) {
    console.error('加载已采纳路线失败:', e)
  }
}

const loadRoutes = async () => {
  listLoading.value = true
  try {
    await loadAdoptedRoutes()
    const res = await getRouteListApi(String(props.userId), currentSort.value === 'mine' ? 'hot' : currentSort.value, searchText.value || null)
    if (res.code === 1 && res.data?.success) {
      let routes = res.data.routes || []
      routes.forEach(r => {
        r.adopted_by_user = adoptedRouteIds.value.has(r.route_id)
      })
      if (currentSort.value === 'mine') {
        routes = routes.filter(r => String(r.creator?.id) === String(props.userId))
      } else if (currentCategory.value) {
        routes = routes.filter(r => r.category === currentCategory.value)
      }
      routeList.value = routes
    }
  } catch (e) {
    console.error('加载路线失败:', e)
    showToast({ type: 'fail', message: '加载路线失败' })
  } finally {
    listLoading.value = false
  }
}

// ========== Detail ==========
const openDetail = async (routeId) => {
  detailVisible.value = true
  detailLoading.value = true
  currentRoute.value = null

  try {
    const res = await getRouteDetailApi(routeId)
    if (res.code === 1 && res.data?.success && res.data.route) {
      const route = res.data.route
      route.adopted_by_user = adoptedRouteIds.value.has(route.route_id)
      currentRoute.value = route
      await loadReviewUserInfo(route.reviews)
    } else {
      showToast({ type: 'fail', message: '加载详情失败' })
    }
  } catch (e) {
    console.error('加载详情失败:', e)
    showToast({ type: 'fail', message: '加载详情失败' })
  } finally {
    detailLoading.value = false
  }
}

const closeDetail = () => {
  detailVisible.value = false
  currentRoute.value = null
  reviewComment.value = ''
  reviewRating.value = 5
}

// Load user info for reviews
const loadReviewUserInfo = async (reviews) => {
  if (!reviews?.length) return
  const userIds = [...new Set(reviews.map(r => String(r.user_id)).filter(Boolean))]
  if (!userIds.length) return
  try {
    const res = await getUserInfoApi({ userIdList: userIds })
    if (res.code === 1 && res.data) {
      const map = {}
      res.data.forEach(u => { map[u.userId] = u })
      userInfoMap.value = { ...userInfoMap.value, ...map }
    }
  } catch (e) {
    console.error('加载用户信息失败:', e)
  }
}

// Format review time
const formatReviewTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  if (days < 30) return `${Math.floor(days / 7)}周前`
  if (days < 365) return `${Math.floor(days / 30)}个月前`
  return `${Math.floor(days / 365)}年前`
}

// ========== Adopt ==========
const quickAdopt = async (routeId) => {
  await doAdopt(routeId, false)
}

const adoptRoute = async (personalize) => {
  if (!currentRoute.value) return
  await doAdopt(currentRoute.value.route_id, personalize)
}

const doAdopt = async (routeId, personalize) => {
  showLoadingToast({ message: '采纳中...', forbidClick: true, duration: 0 })
  try {
    const res = await adoptRouteApi(routeId, { user_id: String(props.userId), personalized: personalize })
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: `已成功采纳：${res.data.plan_name || '学习计划'}` })
      closeDetail()
      emit('adopted')
      emit('close')
    } else {
      showToast({ type: 'fail', message: res.data?.error || '采纳失败' })
    }
  } catch (e) {
    closeToast()
    showToast({ type: 'fail', message: '采纳失败: ' + (e.message || '网络错误') })
  }
}

// ========== Review ==========
const submitReview = async () => {
  if (!currentRoute.value || !reviewComment.value.trim()) {
    showToast('请填写评价内容')
    return
  }
  try {
    const res = await evaluateRouteApi(currentRoute.value.route_id, {
      user_id: String(props.userId),
      rating: reviewRating.value,
      comment: reviewComment.value.trim()
    })
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '评价提交成功' })
      reviewComment.value = ''
      reviewRating.value = 5
      openDetail(currentRoute.value.route_id)
    } else {
      showToast({ type: 'fail', message: '评价提交失败' })
    }
  } catch (e) {
    showToast({ type: 'fail', message: '评价提交失败' })
  }
}

// ========== Edit ==========
const openEditModal = () => {
  if (!currentRoute.value) return
  const r = currentRoute.value
  editForm.value = {
    name: r.name || '',
    subtitle: r.subtitle || '',
    description: r.description || '',
    category: r.category || '',
    difficulty: r.difficulty || 'medium',
    tagsStr: (r.tags || []).join(', '),
    target_audience: r.target_audience || '',
    estimated_duration: r.estimated_duration || '',
    prerequisites: r.prerequisites || ''
  }
  editVisible.value = true
}

const closeEditModal = () => {
  editVisible.value = false
}

const saveRoute = async () => {
  if (!currentRoute.value || !editForm.value.name.trim()) {
    showToast('路线名称不能为空')
    return
  }
  const tags = editForm.value.tagsStr
    ? editForm.value.tagsStr.split(/[,，]/).map(t => t.trim()).filter(t => t)
    : []

  showLoadingToast({ message: '保存中...', forbidClick: true, duration: 0 })
  try {
    const res = await updateRouteApi(currentRoute.value.route_id, {
      user_id: String(props.userId),
      name: editForm.value.name.trim(),
      subtitle: editForm.value.subtitle.trim(),
      description: editForm.value.description.trim(),
      category: editForm.value.category,
      difficulty: editForm.value.difficulty,
      tags,
      target_audience: editForm.value.target_audience.trim(),
      estimated_duration: editForm.value.estimated_duration.trim(),
      prerequisites: editForm.value.prerequisites.trim()
    })
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '路线已更新' })
      closeEditModal()
      closeDetail()
      loadRoutes()
    } else {
      showToast({ type: 'fail', message: '保存失败' })
    }
  } catch (e) {
    closeToast()
    showToast({ type: 'fail', message: '保存失败: ' + (e.message || '网络错误') })
  }
}

// ========== Delete ==========
const handleDeleteRoute = async () => {
  if (!currentRoute.value) return
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要删除此路线吗？删除后不可恢复！'
    })
    showLoadingToast({ message: '删除中...', forbidClick: true, duration: 0 })
    const res = await deleteRouteApi(currentRoute.value.route_id, props.userId)
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '路线已删除' })
      closeDetail()
      loadRoutes()
    } else {
      showToast({ type: 'fail', message: res.data?.error || '删除失败' })
    }
  } catch (e) {
    closeToast()
    if (e !== 'cancel') {
      showToast({ type: 'fail', message: '删除失败' })
    }
  }
}

const getDiffLabel = (diff) => diffLabelMap[diff] || '进阶'
const getDiffColor = (diff) => diffColorMap[diff] || 'var(--coming)'

const avatarColors = ['#667eea', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#fee140', '#30cfd0', '#a8edea']
const avatarColor = (userId) => {
  if (!userId) return avatarColors[0]
  let hash = 0
  for (let i = 0; i < String(userId).length; i++) {
    hash = String(userId).charCodeAt(i) + ((hash << 5) - hash)
  }
  return avatarColors[Math.abs(hash) % avatarColors.length]
}

// Check if a route is owned by current user
const isOwnerForRoute = (route) => {
  return String(route?.creator?.id) === String(props.userId)
}

// Edit from list - set currentRoute and open edit modal
const openEditModalForRoute = (route) => {
  currentRoute.value = route
  openEditModal()
}

// Delete from list
const handleDeleteRouteById = async (routeId) => {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要删除此路线吗？删除后不可恢复！'
    })
    showLoadingToast({ message: '删除中...', forbidClick: true, duration: 0 })
    const res = await deleteRouteApi(routeId, props.userId)
    closeToast()
    if (res.code === 1 && res.data?.success) {
      showToast({ type: 'success', message: '路线已删除' })
      loadRoutes()
    } else {
      showToast({ type: 'fail', message: res.data?.error || '删除失败' })
    }
  } catch (e) {
    closeToast()
    if (e !== 'cancel') {
      showToast({ type: 'fail', message: '删除失败' })
    }
  }
}
</script>

<template>
  <div class="mobile-market-wrapper">
    <!-- Header -->
    <div class="market-header">
      <div class="header-left">
        <van-icon name="shop-o" size="22" color="var(--primary)" />
        <div>
          <h2>学习路线市场</h2>
          <p>精选学习路线，一键采纳</p>
        </div>
      </div>
      <van-icon name="cross" size="20" color="var(--text-gray)" @click="$emit('close')" />
    </div>

    <!-- Search -->
    <div class="search-bar">
      <van-search
        v-model="searchText"
        placeholder="搜索路线名称、关键词..."
        shape="round"
        @update:model-value="debounceSearch"
      />
    </div>

    <!-- Sort -->
    <div class="sort-bar">
      <span class="sort-btn" :class="{ active: currentSort === 'hot' }" @click="setSort('hot')">最热</span>
      <span class="sort-btn" :class="{ active: currentSort === 'rating' }" @click="setSort('rating')">评分</span>
      <span class="sort-btn" :class="{ active: currentSort === 'new' }" @click="setSort('new')">最新</span>
      <span class="sort-btn" :class="{ active: currentSort === 'mine' }" @click="setSort('mine')">我的分享</span>
    </div>

    <!-- Category Tags -->
    <div class="category-bar">
      <span class="cat-tag" :class="{ active: currentCategory === '' }" @click="setCategory('')">全部</span>
      <span
        v-for="cat in categories"
        :key="cat"
        class="cat-tag"
        :class="{ active: currentCategory === cat }"
        @click="setCategory(cat)"
      >{{ cat }}</span>
    </div>

    <!-- Content -->
    <div class="market-content">
      <div v-if="listLoading" class="loading-state">
        <van-loading type="spinner" size="32px" color="var(--primary)">加载中...</van-loading>
      </div>

      <div v-else-if="routeList.length === 0" class="empty-state">
        <van-empty :description="currentSort === 'mine' ? '暂无分享的路线' : '暂无学习路线'" />
      </div>

      <div v-else class="route-list">
        <div
          v-for="route in routeList"
          :key="route.route_id"
          class="route-card"
        >
          <div class="route-card-header" :style="{ background: route.cover_color || 'var(--grad-primary)' }">
            <span class="route-icon">{{ route.cover_icon || '📚' }}</span>
            <div class="header-badges">
              <span class="route-difficulty" :style="{ color: getDiffColor(route.difficulty) }">
                {{ getDiffLabel(route.difficulty) }}
              </span>
              <span v-if="route.category" class="route-category">{{ route.category }}</span>
              <span v-if="isOwnerForRoute(route)" class="my-badge">我的分享</span>
              <span v-else-if="route.adopted_by_user" class="adopted-badge">已采纳</span>
            </div>
          </div>
          <div class="route-card-body" @click="openDetail(route.route_id)">
            <h3 class="route-name">{{ route.name }}</h3>
            <p class="route-subtitle" v-if="route.subtitle">{{ route.subtitle }}</p>
            <div class="route-meta">
              <span class="meta-item">
                <van-icon name="fire-o" size="12" />
                {{ route.stats?.adoptions || 0 }}采纳
              </span>
              <span class="meta-item">
                <van-icon name="star-o" size="12" />
                {{ route.stats?.rating?.toFixed(1) || '0.0' }}
              </span>
              <span class="meta-item" v-if="route.estimated_duration">
                <van-icon name="clock-o" size="12" />
                {{ route.estimated_duration }}
              </span>
            </div>
            <div class="route-tags" v-if="route.tags && route.tags.length > 0">
              <span v-for="(tag, idx) in route.tags.slice(0, 3)" :key="idx" class="route-tag">{{ tag }}</span>
            </div>
          </div>
          <div class="route-card-actions">
            <template v-if="isOwnerForRoute(route)">
              <van-button type="primary" plain size="small" @click.stop="openEditModalForRoute(route)">
                <van-icon name="edit" /> 编辑
              </van-button>
              <van-button type="danger" plain size="small" @click.stop="handleDeleteRouteById(route.route_id)">
                <van-icon name="delete-o" /> 删除
              </van-button>
            </template>
            <template v-else>
              <van-button
                :type="route.adopted_by_user ? 'success' : 'primary'"
                :plain="!route.adopted_by_user"
                size="small"
                :disabled="route.adopted_by_user"
                @click.stop="quickAdopt(route.route_id)"
              >
                <template v-if="route.adopted_by_user">✓ 已采纳</template>
                <template v-else><van-icon name="aim" /> 采纳该路线</template>
              </van-button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Popup -->
    <van-popup
      v-model:show="detailVisible"
      position="bottom"
      :style="{ height: '95%' }"
      round
      closeable
      close-icon-position="top-right"
      @closed="closeDetail"
    >
      <div class="detail-popup">
        <div v-if="detailLoading" class="detail-loading">
          <van-loading type="spinner" size="36px" color="var(--primary)">加载中...</van-loading>
        </div>

        <template v-else-if="currentRoute">
          <div class="detail-header" :style="{ background: currentRoute.cover_color || 'var(--grad-primary)' }">
            <span class="detail-icon">{{ currentRoute.cover_icon || '📚' }}</span>
            <h2>{{ currentRoute.name }}</h2>
            <p v-if="currentRoute.subtitle">{{ currentRoute.subtitle }}</p>
          </div>

          <div class="detail-body">
            <!-- Info -->
            <div class="detail-info">
              <div class="info-row">
                <span class="info-label">分类</span>
                <span class="info-value">{{ currentRoute.category || '未分类' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">难度</span>
                <span class="info-value" :style="{ color: getDiffColor(currentRoute.difficulty) }">
                  {{ getDiffLabel(currentRoute.difficulty) }}
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">采纳数</span>
                <span class="info-value">{{ currentRoute.stats?.adoptions || 0 }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">评分</span>
                <span class="info-value">{{ currentRoute.stats?.rating?.toFixed(1) || '0.0' }}</span>
              </div>
              <div class="info-row" v-if="currentRoute.estimated_duration">
                <span class="info-label">预计时长</span>
                <span class="info-value">{{ currentRoute.estimated_duration }}</span>
              </div>
              <div class="info-row" v-if="currentRoute.target_audience">
                <span class="info-label">适合人群</span>
                <span class="info-value">{{ currentRoute.target_audience }}</span>
              </div>
            </div>

            <!-- Description -->
            <div class="detail-section" v-if="currentRoute.description">
              <h4>路线简介</h4>
              <p class="detail-text">{{ currentRoute.description }}</p>
            </div>

            <!-- Tags -->
            <div class="detail-section" v-if="currentRoute.tags && currentRoute.tags.length > 0">
              <h4>标签</h4>
              <div class="detail-tags">
                <span v-for="(tag, idx) in currentRoute.tags" :key="idx" class="detail-tag">{{ tag }}</span>
              </div>
            </div>

            <!-- Phases -->
            <div class="detail-section" v-if="currentRoute.phases && currentRoute.phases.length > 0">
              <h4>学习阶段 ({{ currentRoute.phases.length }})</h4>
              <div class="phase-list">
                <div v-for="(phase, idx) in currentRoute.phases" :key="idx" class="phase-item">
                  <div class="phase-num">{{ idx + 1 }}</div>
                  <div class="phase-content">
                    <div class="phase-name">{{ phase.name }}</div>
                    <div class="phase-weeks" v-if="phase.weeks">{{ phase.weeks }}</div>
                    <div class="phase-milestone" v-if="phase.milestone">里程碑：{{ phase.milestone }}</div>
                    <div class="phase-kps" v-if="phase.knowledge_points && phase.knowledge_points.length > 0">
                      <span v-for="(kp, kIdx) in phase.knowledge_points" :key="kIdx" class="kp-tag">{{ kp }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Route Flowchart -->
            <div class="detail-section" v-if="currentRoute.phases && currentRoute.phases.length > 0">
              <h4>📋 路线流程图</h4>
              <div class="route-flow">
                <div v-for="(phase, idx) in currentRoute.phases" :key="idx" class="flow-node">
                  <div class="flow-connector" v-if="idx > 0"></div>
                  <div class="flow-node-circle" :class="`node-${idx}`">
                    <span>{{ idx + 1 }}</span>
                  </div>
                  <div class="flow-node-content">
                    <div class="flow-node-title">{{ phase.name }}</div>
                    <div class="flow-node-sub" v-if="phase.weeks">{{ phase.weeks }}</div>
                    <div class="flow-node-milestone" v-if="phase.milestone">🏁 {{ phase.milestone }}</div>
                    <div class="flow-node-kps" v-if="phase.knowledge_points && phase.knowledge_points.length > 0">
                      <span v-for="(kp, kIdx) in phase.knowledge_points.slice(0, 3)" :key="kIdx" class="flow-kp">{{ kp }}</span>
                      <span v-if="phase.knowledge_points.length > 3" class="flow-kp-more">+{{ phase.knowledge_points.length - 3 }}</span>
                    </div>
                  </div>
                </div>
                <!-- <div class="flow-end-node">完成 ✓</div> -->
              </div>
            </div>

            <!-- Creator -->
            <!-- <div class="detail-section" v-if="currentRoute.creator">
              <h4>发布者</h4>
              <div class="creator-info">
                <van-icon name="user-o" size="16" />
                <span>{{ currentRoute.creator.username || currentRoute.creator.nickname || '匿名用户' }}</span>
              </div>
            </div> -->

            <!-- Reviews -->
            <div class="detail-section" v-if="sortedReviews && sortedReviews.length > 0">
              <h4>评价 ({{ sortedReviews.length }})</h4>
              <div class="review-list">
                <div v-for="(review, idx) in sortedReviews" :key="idx" class="review-item">
                  <div class="review-header">
                    <div class="review-user-info">
                      <div class="review-avatar" :style="{ background: avatarColor(review.user_id) }">
                        <van-image
                          v-if="userInfoMap[review.user_id]?.avatar"
                          :src="userInfoMap[review.user_id].avatar"
                          round
                          width="32"
                          height="32"
                          fit="cover"
                        />
                        <span v-else class="avatar-fallback">{{ (userInfoMap[review.user_id]?.username || userInfoMap[review.user_id]?.nickname || 'U').charAt(0).toUpperCase() }}</span>
                      </div>
                      <div class="review-user-meta">
                        <span class="review-user">{{ userInfoMap[review.user_id]?.username || userInfoMap[review.user_id]?.nickname || '匿名用户' }}</span>
                        <span class="review-time">{{ formatReviewTime(review.created_at) }}</span>
                      </div>
                    </div>
                    <div class="review-rating">
                      <van-rate v-model="review.rating" readonly size="18" color="#ffd21e" />
                    </div>
                  </div>
                  <p class="review-comment">{{ review.comment }}</p>
                </div>
              </div>
            </div>

            <!-- Add Review -->
            <div class="detail-section">
              <h4>发表评价</h4>
              <div class="review-form">
                <van-rate v-model="reviewRating" size="20" color="#ffd21e" />
                <van-field
                  v-model="reviewComment"
                  type="textarea"
                  placeholder="写下你的评价..."
                  rows="2"
                  autosize
                  class="review-input"
                />
                <van-button size="small" type="primary" @click="submitReview">提交评价</van-button>
              </div>
            </div>
          </div>

          <!-- Footer Actions -->
          <div class="detail-footer">
            <van-button v-if="isOwner" plain type="primary" size="small" @click="openEditModal">编辑</van-button>
            <van-button v-if="isOwner" plain type="danger" size="small" @click="handleDeleteRoute">删除</van-button>
            <van-button
              v-if="!currentRoute.adopted_by_user"
              type="primary"
              size="small"
              @click="adoptRoute(false)"
            >采纳路线</van-button>
            <van-button
              v-else
              type="success"
              size="small"
              plain
              disabled
            >已采纳</van-button>
          </div>
        </template>
      </div>
    </van-popup>

    <!-- Edit Popup -->
    <van-popup
      v-model:show="editVisible"
      position="bottom"
      :style="{ height: '80%' }"
      round
      closeable
      close-icon-position="top-right"
    >
      <div class="edit-popup">
        <h3>编辑路线</h3>
        <div class="edit-form">
          <van-field v-model="editForm.name" label="名称" placeholder="路线名称" />
          <van-field v-model="editForm.subtitle" label="副标题" placeholder="一句话介绍" />
          <van-field
            v-model="editForm.description"
            label="简介"
            type="textarea"
            placeholder="路线简介"
            rows="3"
            autosize
          />
          <van-field v-model="editForm.category" label="分类" placeholder="如：前端开发" />
          <van-field v-model="editForm.tagsStr" label="标签" placeholder="逗号分隔" />
          <van-field v-model="editForm.target_audience" label="适合人群" placeholder="如：零基础" />
          <van-field v-model="editForm.estimated_duration" label="预计时长" placeholder="如：3个月" />
          <van-field v-model="editForm.prerequisites" label="前置要求" placeholder="如：无" />
          <div class="edit-difficulty">
            <span class="edit-label">难度</span>
            <div class="diff-btns">
              <span class="diff-btn" :class="{ active: editForm.difficulty === 'beginner' || editForm.difficulty === 'easy' }" @click="editForm.difficulty = 'beginner'">入门</span>
              <span class="diff-btn" :class="{ active: editForm.difficulty === 'medium' }" @click="editForm.difficulty = 'medium'">进阶</span>
              <span class="diff-btn" :class="{ active: editForm.difficulty === 'advanced' || editForm.difficulty === 'hard' }" @click="editForm.difficulty = 'advanced'">高级</span>
            </div>
          </div>
        </div>
        <div class="edit-footer">
          <van-button plain @click="closeEditModal">取消</van-button>
          <van-button type="primary" @click="saveRoute">保存</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.mobile-market-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-page);
  z-index: 1000;
  display: flex;
  flex-direction: column;
}

.market-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-left h2 {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-title);
}

.header-left p {
  font-size: 11px;
  color: var(--text-gray);
}

.search-bar {
  flex-shrink: 0;
}

.sort-bar {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  padding: 0 16px 8px;
  flex-shrink: 0;
}

.sort-btn {
  padding: 4px 14px;
  font-size: 12px;
  border-radius: 20px;
  background: var(--bg-card);
  color: var(--text-gray);
  border: 1px solid var(--border-color);
}

.sort-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.category-bar {
  display: flex;
  gap: 8px;
  padding: 0 16px 8px;
  overflow-x: auto;
  flex-shrink: 0;
  -webkit-overflow-scrolling: touch;
}

.category-bar::-webkit-scrollbar {
  display: none;
}

.cat-tag {
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 20px;
  background: var(--bg-card);
  color: var(--text-gray);
  border: 1px solid var(--border-color);
  white-space: nowrap;
  flex-shrink: 0;
}

.cat-tag.active {
  background: var(--primary-light);
  color: var(--primary);
  border-color: var(--primary);
}

.market-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px 80px;
  -webkit-overflow-scrolling: touch;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.route-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.route-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-color);
}

.route-card:active {
  transform: scale(0.98);
}

.route-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
}

.route-icon {
  font-size: 22px;
  flex-shrink: 0;
}

.header-badges {
  display: flex;
  align-items: center;
  gap: 6px;
}

.route-difficulty {
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.9);
  padding: 2px 10px;
  border-radius: 10px;
}

.route-category {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 8px;
}

.route-card-body {
  padding: 12px 14px;
  text-align: center;
}

.route-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 4px;
  text-align: center;
}

.route-subtitle {
  font-size: 10px;
  color: var(--text-gray);
  margin-bottom: 8px;
  text-align: center;
}

.route-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-bottom: 6px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: var(--text-gray);
}

.meta-item.adopted {
  color: var(--pass);
}

.route-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px;
}

.route-tag {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 8px;
  background: var(--primary-light);
  color: var(--primary);
}

.my-badge {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--pass);
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.adopted-badge {
  font-size: 10px;
  background: var(--pass);
  color: #fff;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.route-card-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-page);
}

/* Detail Popup */
.detail-popup {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding-bottom: 50px;
}

.detail-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.detail-header {
  padding: 12px 14px;
  text-align: center;
  color: #fff;
  flex-shrink: 0;
}

.detail-icon {
  font-size: 24px;
  display: block;
  margin-bottom: 4px;
}

.detail-header h2 {
  font-size: 15px;
  font-weight: 700;
}

.detail-header p {
  font-size: 11px;
  opacity: 0.9;
  margin-top: 2px;
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  -webkit-overflow-scrolling: touch;
}

.detail-info {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 12px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color);
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.info-label {
  color: var(--text-gray);
}

.info-value {
  color: var(--text-title);
  font-weight: 500;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section h4 {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 10px;
  padding-left: 10px;
  border-left: 3px solid var(--primary);
  line-height: 1.3;
}

/* Route Flowchart */
.route-flow {
  position: relative;
  padding: 4px 0;
}

.flow-node {
  position: relative;
  display: flex;
  gap: 10px;
  padding-bottom: 12px;
}

.flow-connector {
  position: absolute;
  left: 13px;
  top: -2px;
  width: 2px;
  height: 14px;
  background: linear-gradient(to bottom, var(--primary-light, #667eea), var(--primary, #667eea));
}

.flow-node-circle {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  position: relative;
  z-index: 2;
}

.flow-node-circle.node-0 {
  background: #10b981;
}

.flow-node-circle.node-1 {
  background: #667eea;
}

.flow-node-circle.node-2 {
  background: #f59e0b;
}

.flow-node-circle.node-3 {
  background: #ef4444;
}

.flow-node-circle.node-4 {
  background: #8b5cf6;
}

.flow-node-circle.node-5,
.flow-node-circle.node-6 {
  background: #667eea;
}

.flow-node-content {
  flex: 1;
  min-width: 0;
  padding: 4px 8px 8px 8px;
  background: var(--bg-card, #f8f9ff);
  border-radius: 8px;
  border: 1px solid var(--border-light, #e8ecff);
}

.flow-node-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 2px;
}

.flow-node-sub {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 2px;
}

.flow-node-milestone {
  font-size: 11px;
  color: #f59e0b;
  margin-bottom: 3px;
}

.flow-node-kps {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.flow-kp {
  font-size: 10px;
  padding: 1px 6px;
  background: var(--primary-light, #e8ecff);
  color: var(--primary, #667eea);
  border-radius: 4px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flow-kp-more {
  font-size: 10px;
  color: var(--text-gray);
}

.flow-end-node {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border-radius: 8px;
  margin-top: 4px;
}

.detail-text {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.6;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-tag {
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 10px;
  background: var(--primary-light);
  color: var(--primary);
}

.phase-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.phase-item {
  display: flex;
  gap: 10px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 10px;
  border: 1px solid var(--border-color);
}

.phase-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.phase-content {
  flex: 1;
}

.phase-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
}

.phase-weeks {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 2px;
}

.phase-milestone {
  font-size: 11px;
  color: var(--coming);
  margin-top: 2px;
}

.phase-kps {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.kp-tag {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 8px;
  background: var(--bg-hover);
  color: var(--text-body);
}

.creator-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-body);
}

.review-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.review-item {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 10px;
  border: 1px solid var(--border-color);
}

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.review-user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.avatar-fallback {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.review-user-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.review-user {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-title);
}

.review-time {
  font-size: 10px;
  color: var(--text-gray);
}

.review-rating {
  flex-shrink: 0;
}

.review-comment {
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.5;
}

.review-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-input {
  background: var(--bg-input);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.detail-footer {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
  flex-shrink: 0;
  justify-content: flex-end;
}

/* Edit Popup */
.edit-popup {
  padding-bottom: 50px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.edit-popup h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  text-align: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.edit-form {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.edit-difficulty {
  margin-top: 12px;
}

.edit-label {
  display: block;
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 8px;
}

.diff-btns {
  display: flex;
  gap: 8px;
}

.diff-btn {
  flex: 1;
  text-align: center;
  padding: 8px;
  font-size: 13px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  color: var(--text-body);
  border: 1px solid var(--border-color);
}

.diff-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.edit-footer {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
}

.edit-footer .van-button {
  flex: 1;
}
</style>

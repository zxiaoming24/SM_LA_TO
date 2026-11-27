<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useThemeStore } from '@/stores/theme'
import {
  categoriesApi, getRouteListApi, getRouteDetailApi, adoptRouteApi,
  deleteRouteApi, evaluateRouteApi, updateRouteApi, getAdoptedRoutesApi
} from '@/api/mainApi/pathPlanMarket.js'
import { getUserInfoApi } from '@/api/mainApi/index.js'

const props = defineProps({
  userId: { type: String, required: true }
})

const emit = defineEmits(['close', 'adopted'])

const themeStore = useThemeStore()

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

// Sorted reviews (newest first)
const sortedReviews = computed(() => {
  const reviews = currentRoute.value?.reviews || []
  return [...reviews].sort((a, b) => {
    const timeA = new Date(a.created_at || 0).getTime()
    const timeB = new Date(b.created_at || 0).getTime()
    return timeB - timeA
  })
})

// Flowchart iframe
const flowchartSrcdoc = computed(() => {
  if (!currentRoute.value) return ''
  const syntax = generateMermaidSyntax(currentRoute.value)
  return buildFlowchartHtml(syntax)
})

// Generate Mermaid syntax from route phases
const generateMermaidSyntax = (route) => {
  const phases = route.phases || []
  if (phases.length === 0) return 'graph TD\n  A[暂无阶段]'

  const lines = ['graph TD']
  lines.push('  START((开始)) --> P1')

  for (let i = 0; i < phases.length; i++) {
    const phase = phases[i]
    const phaseNum = i + 1
    const name = (phase.name || '').replace(/"/g, "'")
    const weeks = (phase.weeks || '').replace(/"/g, "'")
    const milestone = (phase.milestone || '').replace(/"/g, "'")
    const kps = phase.knowledge_points || []

    let phaseLabel = `阶段${phaseNum}: ${name}\\n${weeks}`
    if (milestone) phaseLabel += `\\n🏁 ${milestone}`
    lines.push(`  P${phaseNum}["${phaseLabel}"]`)

    if (kps.length > 0) {
      lines.push(`  subgraph SP${phaseNum}["知识点"]`)
      lines.push('    direction LR')
      for (let j = 0; j < kps.length; j++) {
        let kpName = (kps[j] || '').replace(/"/g, "'").replace(/\n/g, ' ')
        if (kpName.length > 20) kpName = kpName.substring(0, 18) + '...'
        lines.push(`    KP${phaseNum}_${j + 1}["${kpName}"]`)
      }
      lines.push('  end')
      lines.push(`  P${phaseNum} --- SP${phaseNum}`)
    }

    if (i < phases.length - 1) {
      lines.push(`  P${phaseNum} --> P${phaseNum + 1}`)
    } else {
      lines.push(`  P${phaseNum} --> END((完成))`)
    }
  }

  return lines.join('\n')
}

// Build complete HTML for iframe
const buildFlowchartHtml = (mermaidSyntax) => {
  const isDark = themeStore.isDark
  const bgColor = isDark ? '#1E293B' : '#fff'
  const textColor = isDark ? '#E2E8F0' : '#1a1a2e'
  const primaryColor = isDark ? '#334155' : '#e8ecff'
  const borderColor = isDark ? '#3B82F6' : '#667eea'
  const lineColor = isDark ? '#3B82F6' : '#667eea'
  const clusterBkg = isDark ? '#1E293B' : '#f8f9ff'
  const titleColor = isDark ? '#60A5FA' : '#667eea'
  const btnBg = isDark ? '#334155' : '#fff'
  const btnText = isDark ? '#E2E8F0' : '#333'
  const btnHoverBg = isDark ? '#3B82F6' : '#667eea'
  const sectionBg = isDark ? '#0F172A' : '#f8f9ff'
  const sectionBorder = isDark ? '#334155' : '#e8ecff'

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: ${sectionBg};
  padding: 16px;
  color: ${textColor};
}
.flowchart-wrap { 
  background: ${sectionBg};
  border-radius: 14px; 
  padding: 16px; 
  border: 1px solid ${sectionBorder};
}
.flowchart-controls { 
  display: flex; 
  gap: 8px; 
  margin-bottom: 12px; 
  justify-content: center; 
  flex-wrap: wrap; 
}
.flowchart-controls button { 
  padding: 6px 14px; 
  border: 1px solid ${borderColor}; 
  border-radius: 8px;
  background: ${btnBg}; 
  color: ${btnText}; 
  font-size: 13px; 
  cursor: pointer;
  transition: all 0.2s; 
}
.flowchart-controls button:hover { 
  background: ${btnHoverBg}; 
  color: #fff; 
  border-color: ${btnHoverBg};
}
.flowchart-zoom-wrap { 
  overflow: auto; 
  max-height: 600px; 
  scrollbar-width: none; /* 新增：隐藏 Firefox 滚动条 */
  -ms-overflow-style: none; /* 新增：隐藏 IE/Edge 滚动条 */
}
.flowchart-zoom-wrap::-webkit-scrollbar {
  display: none; /* 新增：隐藏 Chrome/Safari 滚动条 */
}
.flowchart-container { 
  background: ${bgColor};
  border-radius: 12px; 
  padding: 20px; 
  overflow-x: auto;
  min-height: 200px; 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  transition: transform 0.2s;
}
.flowchart-container svg { 
  max-width: 100%; 
  height: auto; 
}

/* 全屏样式 */
.flowchart-wrap:fullscreen {
  width: 100vw;
  height: 100vh;
  padding: 20px;
  display: flex;
  flex-direction: column;
  background: ${sectionBg};
}

.flowchart-wrap:fullscreen .flowchart-zoom-wrap {
  flex: 1;
  max-height: none;
  overflow: auto;
}

.flowchart-wrap:fullscreen .flowchart-container {
  height: 100%;
  min-height: 0;
}
</style>
</head>
<body>
<div class="flowchart-wrap">
  <div class="flowchart-controls">
    <button onclick="zoomOut()">🔍- 缩小</button>
    <button onclick="zoomIn()">🔍+ 放大</button>
    <button onclick="zoomReset()">🔄 重置</button>
    <button id="fullscreenBtn" onclick="toggleFullscreen()">⛶ 全屏</button>
  </div>
  <div class="flowchart-zoom-wrap" id="zoomWrap">
    <div class="flowchart-container" id="flowchartContainer">
      <pre class="mermaid">${mermaidSyntax}</pre>
    </div>
  </div>
</div>
<script src="/mermaid.min.js"><\/script>
<script>
mermaid.initialize({
  startOnLoad: true,
  theme: '${isDark ? 'dark' : 'base'}',
  themeVariables: {
    primaryColor: '${primaryColor}',
    primaryTextColor: '${textColor}',
    primaryBorderColor: '${borderColor}',
    lineColor: '${lineColor}',
    secondaryColor: '${isDark ? '#1E293B' : '#f0f2f5'}',
    tertiaryColor: '${bgColor}',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontSize: '13px',
    clusterBkg: '${clusterBkg}',
    clusterBorder: '${borderColor}',
    titleColor: '${titleColor}',
  },
  flowchart: { htmlLabels: true, curve: 'basis', padding: 15, nodeSpacing: 30, rankSpacing: 50 },
});

let currentScale = 1;
function zoomIn() { currentScale = Math.min(currentScale + 0.2, 3); applyZoom(); }
function zoomOut() { currentScale = Math.max(currentScale - 0.2, 0.3); applyZoom(); }
function zoomReset() { currentScale = 1; applyZoom(); }
function applyZoom() {
  const container = document.getElementById('flowchartContainer');
  container.style.transform = 'scale(' + currentScale + ')';
  container.style.transformOrigin = 'top center';
}
function toggleFullscreen() {
  const wrap = document.querySelector('.flowchart-wrap');
  if (!document.fullscreenElement) {
    wrap.requestFullscreen().catch(err => {});
  } else {
    document.exitFullscreen();
  }
}
function updateFullscreenBtn() {
  const btn = document.getElementById('fullscreenBtn');
  if (btn) {
    btn.textContent = document.fullscreenElement ? '⛶ 缩小' : '⛶ 全屏';
  }
}
document.addEventListener('fullscreenchange', updateFullscreenBtn);
<\/script>
</body>
</html>`
}

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
const diffColorMap = { easy: '#10b981', medium: '#f59e0b', hard: '#ef4444', beginner: '#10b981', advanced: '#ef4444' }

// Computed
const isOwner = computed(() => {
  return String(currentRoute.value?.creator?.id) === String(props.userId)
})

const detailHeaderStyle = computed(() => {
  const color = currentRoute.value?.cover_color || '#667eea'
  return { background: color }
})

// ========== Lifecycle ==========
onMounted(() => {
  loadCategories()
  loadRoutes()
  loadAdoptedRoutes()
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
const loadRoutes = async () => {
  listLoading.value = true
  try {
    // 先加载已采纳路线
    await loadAdoptedRoutes()
    
    const res = await getRouteListApi(String(props.userId), currentSort.value, searchText.value || null)
    if (res.code === 1 && res.data?.success) {
      let routes = res.data.routes || []
      
      // 用已采纳列表标记
      routes.forEach(r => {
        r.adopted_by_user = adoptedRouteIds.value.has(r.route_id)
      })
      
      // Filter by category if set
      if (currentCategory.value) {
        routes = routes.filter(r => r.category === currentCategory.value)
      }
      routeList.value = routes
    }
  } catch (e) {
    console.error('加载路线失败:', e)
    ElMessage.error('加载路线失败')
  } finally {
    listLoading.value = false
  }
}

// 加载已采纳路线，用于详情面板判断
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

// ========== Detail ==========
const openDetail = async (routeId) => {
  detailVisible.value = true
  detailLoading.value = true
  currentRoute.value = null

  try {
    const res = await getRouteDetailApi(routeId)
    if (res.code === 1 && res.data?.success && res.data.route) {
      const route = res.data.route
      // 从已采纳列表中判断是否已采纳
      route.adopted_by_user = adoptedRouteIds.value.has(route.route_id)
      currentRoute.value = route
      // 加载评价用户信息
      await loadReviewUserInfo(route.reviews)
    } else {
      ElMessage.error('加载详情失败')
    }
  } catch (e) {
    console.error('加载详情失败:', e)
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

const closeDetail = () => {
  detailVisible.value = false
  currentRoute.value = null
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
  try {
    const res = await adoptRouteApi(routeId, { user_id: String(props.userId), personalized: personalize })
    if (res.code === 1 && res.data?.success) {
      ElMessage.success(`已成功采纳：${res.data.plan_name || '学习计划'}`)
      closeDetail()
      emit('adopted')
      emit('close')
    } else {
      ElMessage.error(res.data?.error || '采纳失败')
    }
  } catch (e) {
    ElMessage.error('采纳失败: ' + (e.message || '网络错误'))
  }
}

// ========== Review ==========
const submitReview = async () => {
  if (!currentRoute.value || !reviewComment.value.trim()) {
    ElMessage.warning('请填写评价内容')
    return
  }
  try {
    const res = await evaluateRouteApi(currentRoute.value.route_id, {
      user_id: String(props.userId),
      rating: reviewRating.value,
      comment: reviewComment.value.trim()
    })
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('评价提交成功')
      reviewComment.value = ''
      reviewRating.value = 5
      // Refresh detail
      openDetail(currentRoute.value.route_id)
    } else {
      ElMessage.error('评价提交失败')
    }
  } catch (e) {
    ElMessage.error('评价提交失败')
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
    ElMessage.warning('路线名称不能为空')
    return
  }
  const tags = editForm.value.tagsStr
    ? editForm.value.tagsStr.split(/[,，]/).map(t => t.trim()).filter(t => t)
    : []
  
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
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('路线已更新')
      closeEditModal()
      closeDetail()
      loadRoutes()
    } else {
      ElMessage.error('保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || '网络错误'))
  }
}

// ========== Delete ==========
const handleDeleteRoute = async () => {
  if (!currentRoute.value) return
  try {
    await ElMessageBox.confirm('确定要删除此路线吗？删除后不可恢复！', '确认删除', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res = await deleteRouteApi(currentRoute.value.route_id, props.userId)
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('路线已删除')
      closeDetail()
      loadRoutes()
    } else {
      ElMessage.error(res.data?.error || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 从列表卡片直接编辑
const openEditModalForRoute = (route) => {
  currentRoute.value = route
  openEditModal()
}

// 从列表卡片直接删除
const handleDeleteRouteById = async (routeId) => {
  try {
    await ElMessageBox.confirm('确定要删除此路线吗？删除后不可恢复！', '确认删除', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res = await deleteRouteApi(routeId, props.userId)
    if (res.code === 1 && res.data?.success) {
      ElMessage.success('路线已删除')
      loadRoutes()
    } else {
      ElMessage.error(res.data?.error || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}
</script>

<template>
  <div class="market-wrapper">
    <!-- Header -->
    <div class="market-header">
      <div class="header-top">
        <div class="header-left">
          <el-icon class="header-icon"><ShoppingCart /></el-icon>
          <div>
            <h1>学习路线市场</h1>
            <p>精选学习路线，一键采纳为你的个性化学习计划</p>
          </div>
        </div>
        <button class="market-close-btn" @click="$emit('close')">&times;</button>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="search-box">
        <input v-model="searchText" type="text" placeholder="搜索路线名称、关键词..." @input="debounceSearch" />
        <el-icon class="search-icon"><Search /></el-icon>
      </div>
      <div class="sort-group">
        <button class="sort-btn" :class="{ active: currentSort === 'hot' }" @click="setSort('hot')"><el-icon><TrendCharts /></el-icon> 最热</button>
        <button class="sort-btn" :class="{ active: currentSort === 'rating' }" @click="setSort('rating')"><el-icon><StarFilled /></el-icon> 评分</button>
        <button class="sort-btn" :class="{ active: currentSort === 'new' }" @click="setSort('new')"><el-icon><Filter /></el-icon> 最新</button>
      </div>
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
    <div class="content">
      <!-- Loading -->
      <div v-if="listLoading" class="loading-state">
        <div class="spinner"></div>
        <p>加载中...</p>
      </div>
      <!-- Empty -->
      <div v-else-if="routeList.length === 0" class="empty-state">
        <el-icon class="empty-icon"><Document /></el-icon>
        <p>暂无匹配的路线</p>
      </div>
      <!-- Route Grid -->
      <div v-else class="route-grid">
        <div 
          v-for="route in routeList" 
          :key="route.route_id" 
          class="route-card"
          @click="openDetail(route.route_id)"
        >
          <div class="card-cover" :style="{ background: route.cover_color || '#667eea' }">
            <span class="cover-icon">{{ route.cover_icon || '📚' }}</span>
            <span class="cover-badge" :style="{ color: diffColorMap[route.difficulty] || '#666' }">
              {{ diffLabelMap[route.difficulty] || route.difficulty }}
            </span>
            <span v-if="String(route.creator?.id) === String(userId)" class="my-badge"><el-icon><User /></el-icon> 我的发布</span>
            <span v-else-if="route.adopted_by_user" class="adopted-badge">✓ 已采纳</span>
          </div>
          <div class="card-body">
            <div class="card-title">{{ route.name }}</div>
            <div class="card-subtitle">{{ route.subtitle }}</div>
            <div class="card-desc">{{ route.description }}</div>
            <div class="card-meta">
              <span class="meta-item"><el-icon><StarFilled /></el-icon> {{ route.stats?.rating || 0 }}</span>
              <span class="meta-item"><el-icon><UserFilled /></el-icon> {{ route.stats?.adoptions || 0 }}人采纳</span>
              <span class="meta-item"><el-icon><Calendar /></el-icon> {{ route.estimated_duration }}</span>
            </div>
            <div class="card-tags">
              <span v-for="tag in (route.tags || []).slice(0, 4)" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </div>
          <div class="card-footer">
            <button class="detail-btn" @click.stop="openDetail(route.route_id)">查看详情</button>
            <div class="card-footer-actions">
              <template v-if="String(route.creator?.id) === String(userId)">
                <button class="edit-btn" @click.stop="openEditModalForRoute(route)"><el-icon><Edit /></el-icon> 编辑</button>
                <button class="delete-btn" @click.stop="handleDeleteRouteById(route.route_id)"><el-icon><Delete /></el-icon> 删除</button>
              </template>
              <template v-else>
                <button 
                  class="adopt-btn" 
                  :class="{ adopted: route.adopted_by_user }"
                  :disabled="route.adopted_by_user"
                  @click.stop="quickAdopt(route.route_id)"
                >
                  <template v-if="route.adopted_by_user">✓ 已采纳</template>
                  <template v-else><el-icon><Aim /></el-icon> 直接采纳</template>
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Overlay -->
    <div v-if="detailVisible" class="detail-overlay">
      <div class="detail-panel">
        <!-- ========== 上部：头部 ========== -->
        <div class="detail-top" :style="detailHeaderStyle">
          <button class="close-btn" @click="closeDetail">&times;</button>
          <div v-if="detailLoading" class="detail-loading">
            <div class="spinner"></div>
          </div>
          <template v-else-if="currentRoute">
            <div class="top-left">
              <div class="detail-icon">{{ currentRoute.cover_icon || '📚' }}</div>
              <div class="top-info">
                <h2>{{ currentRoute.name }}</h2>
                <div class="detail-subtitle">{{ currentRoute.subtitle }}</div>
                <div class="detail-meta-inline">
                  <span class="meta-chip">{{ diffLabelMap[currentRoute.difficulty] || currentRoute.difficulty }}</span>
                  <span class="meta-chip"><el-icon><Calendar /></el-icon> {{ currentRoute.estimated_duration }}</span>
                  <span class="meta-chip"><el-icon><Timer /></el-icon> {{ currentRoute.estimated_hours || 0 }}h</span>
                  <span class="meta-chip"><el-icon><StarFilled /></el-icon> {{ currentRoute.stats?.rating || 0 }}</span>
                  <span class="meta-chip"><el-icon><UserFilled /></el-icon> {{ currentRoute.stats?.adoptions || 0 }}人采纳</span>
                </div>
              </div>
            </div>
            <div class="top-actions">
              <template v-if="isOwner">
                <button class="action-btn-sm edit" @click="openEditModal"><el-icon><Edit /></el-icon> 编辑</button>
                <button class="action-btn-sm delete" @click="handleDeleteRoute"><el-icon><Delete /></el-icon> 删除</button>
              </template>
              <template v-else>
                <button class="action-btn-sm direct" :disabled="currentRoute.adopted_by_user" @click="adoptRoute(false)"><el-icon><Aim /></el-icon> 直接使用</button>
                <button class="action-btn-sm ai" :disabled="currentRoute.adopted_by_user" @click="adoptRoute(true)"><el-icon><Monitor /></el-icon> AI个性化</button>
                <span v-if="currentRoute.adopted_by_user" class="adopted-tag">✓ 已采纳</span>
              </template>
            </div>
          </template>
        </div>

        <!-- ========== 下部：三栏内容 ========== -->
        <div v-if="currentRoute" class="detail-content">
          <!-- 左栏：路线简介、前置要求、学习阶段 -->
          <div class="detail-col col-left">
            <div class="detail-section">
              <h3><el-icon><Document /></el-icon> 路线简介</h3>
              <p class="section-text">{{ currentRoute.description }}</p>
            </div>

            <div v-if="currentRoute.prerequisites" class="detail-section">
              <h3><el-icon><Compass /></el-icon> 前置要求</h3>
              <p class="section-text muted">{{ currentRoute.prerequisites }}</p>
            </div>

            <div class="detail-section">
              <h3><el-icon><Collection /></el-icon> 学习阶段 ({{ (currentRoute.phases || []).length }}个)</h3>
              <div 
                v-for="(phase, idx) in (currentRoute.phases || [])" 
                :key="idx" 
                class="phase-card"
              >
                <div class="phase-title">阶段{{ phase.phase || idx + 1 }}：{{ phase.name }}</div>
                <div class="phase-weeks"><el-icon><Clock /></el-icon> {{ phase.weeks }} | 预估 {{ phase.estimated_hours || 0 }}小时</div>
                <div class="phase-desc">{{ phase.description }}</div>
                <div v-if="phase.knowledge_points?.length" class="phase-kps">
                  <span v-for="kp in phase.knowledge_points" :key="kp" class="kp">{{ kp }}</span>
                </div>
                <div v-if="phase.milestone" class="phase-milestone"><el-icon><Flag /></el-icon> 里程碑：{{ phase.milestone }}</div>
              </div>
            </div>
          </div>

          <!-- 中栏：路线流程图 -->
          <div class="detail-col col-middle">
            <div class="flowchart-section">
              <h3><el-icon><MapLocation /></el-icon> 路线流程图</h3>
              <iframe 
                v-if="flowchartSrcdoc"
                :srcdoc="flowchartSrcdoc"
                class="flowchart-iframe"
                frameborder="0"
              ></iframe>
            </div>
          </div>

          <!-- 右栏：用户评价、发表评价 -->
          <div class="detail-col col-right">

            <div class="detail-section">
              <h3><el-icon><EditPen /></el-icon> 发表评价</h3>
              <div class="review-form">
                <div class="star-rating">
                  <el-icon
                    v-for="n in 5"
                    :key="n"
                    class="star"
                    :class="{ active: n <= reviewRating }"
                    @click="reviewRating = n"
                  ><StarFilled /></el-icon>
                </div>
                <textarea v-model="reviewComment" rows="4" placeholder="分享你的学习体验..."></textarea>
                <button class="submit-review-btn" @click="submitReview">提交评价</button>
              </div>
            </div>
            
            <div v-if="currentRoute.reviews?.length" class="detail-section">
              <h3><el-icon><ChatDotRound /></el-icon> 用户评价 ({{ currentRoute.reviews.length }})</h3>
              <div v-for="(review, idx) in sortedReviews" :key="idx" class="review-item">
                <div class="review-header">
                  <div class="review-user-info">
                    <el-avatar :size="35" :src="userInfoMap[review.user_id]?.avatar || ''">
                      {{ userInfoMap[review.user_id]?.username?.charAt(0) || 'User' }}
                    </el-avatar>
                    <div class="review-user-meta">
                      <span class="review-user">{{ userInfoMap[review.user_id]?.username || review.user_id }}</span>
                      <span class="review-time">{{ formatReviewTime(review.created_at) }}</span>
                    </div>
                  </div>
                  <span class="review-stars">
                    <el-icon v-for="n in (review.rating || 0)" :key="n"><StarFilled /></el-icon>
                  </span>
                </div>
                <div class="review-text">{{ review.comment }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <div v-if="editVisible" class="share-dialog-overlay">
      <div class="share-dialog">
        <div class="share-dialog-header">
          <div class="share-header-left">
            <span class="share-header-icon">✏️</span>
            <div>
              <h3>编辑学习路线</h3>
              <p class="share-header-desc">修改路线信息后保存发布</p>
            </div>
          </div>
          <button class="share-dialog-close" @click="closeEditModal">&times;</button>
        </div>
        <div class="share-dialog-body">
          <div class="share-form">
            <!-- 基本信息区 -->
            <div class="share-section">
              <div class="share-section-title">基本信息</div>
              <div class="share-form-item">
                <label>路线名称 <span class="required">*</span></label>
                <input v-model="editForm.name" type="text" placeholder="例如：3个月Python从入门到实战" class="share-input" maxlength="50" />
                <span class="share-char-count">{{ (editForm.name || '').length }}/50</span>
              </div>
              <div class="share-form-item">
                <label>一句话介绍</label>
                <input v-model="editForm.subtitle" type="text" placeholder="用一句话概括这条路线的亮点" class="share-input" maxlength="30" />
              </div>
              <div class="share-form-item">
                <label>路线简介</label>
                <textarea v-model="editForm.description" placeholder="描述路线的核心内容、学习方式和预期收获..." rows="6" class="share-textarea"></textarea>
              </div>
            </div>
            <!-- 分类与难度 -->
            <div class="share-section">
              <div class="share-section-title">分类与难度</div>
              <div class="share-form-row">
                <div class="share-form-item">
                  <label>分类 <span class="required">*</span></label>
                  <select v-model="editForm.category" class="share-select">
                    <option value="">请选择分类</option>
                    <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
                    <option value="其他">其他</option>
                  </select>
                </div>
                <div class="share-form-item">
                  <label>难度等级</label>
                  <div class="share-difficulty-group">
                    <button type="button" class="share-diff-btn" :class="{ active: editForm.difficulty === 'easy' }" @click="editForm.difficulty = 'easy'">入门</button>
                    <button type="button" class="share-diff-btn" :class="{ active: editForm.difficulty === 'medium' }" @click="editForm.difficulty = 'medium'">进阶</button>
                    <button type="button" class="share-diff-btn" :class="{ active: editForm.difficulty === 'hard' }" @click="editForm.difficulty = 'hard'">高级</button>
                  </div>
                </div>
              </div>
            </div>
            <!-- 标签与人群 -->
            <div class="share-section">
              <div class="share-section-title">其他信息</div>
              <div class="share-form-item">
                <label>标签 <span class="share-hint">（逗号分隔）</span></label>
                <input v-model="editForm.tagsStr" type="text" placeholder="如：Python, 数据分析, Pandas" class="share-input" />
              </div>
              <div class="share-form-item">
                <label>适合人群</label>
                <input v-model="editForm.target_audience" type="text" placeholder="例如：零基础、转行人员、在校学生..." class="share-input" />
              </div>
              <div class="share-form-row">
                <div class="share-form-item">
                  <label>预计时长</label>
                  <input v-model="editForm.estimated_duration" type="text" placeholder="如：3个月" class="share-input" />
                </div>
                <div class="share-form-item">
                  <label>前置要求</label>
                  <input v-model="editForm.prerequisites" type="text" placeholder="如：Python基础" class="share-input" />
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="share-dialog-footer">
          <button class="share-btn-cancel" @click="closeEditModal">取消</button>
          <button class="share-btn-submit" @click="saveRoute">保存修改</button>
        </div>
      </div>
    </div>
  </div>
</template>



<style scoped>
.market-wrapper {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 1314px;
  animation: wrapperFadeIn 0.3s ease;
}

@keyframes wrapperFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.market-header {
  background: var(--primary);
  color: #fff;
  padding: 20px 28px 16px;
  flex-shrink: 0;
  animation: headerFadeIn 0.4s ease;
}

@keyframes headerFadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.header-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.header-icon {
  font-size: 28px;
  color: #fff;
  animation: headerIconPulse 2s ease-in-out infinite;
}

@keyframes headerIconPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.market-header h1 {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 4px;
}

.market-header p {
  font-size: 13px;
  opacity: 0.85;
  margin: 0;
}

.market-close-btn {
  background: rgba(255,255,255,0.2);
  border: none;
  color: #fff;
  font-size: 24px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.market-close-btn:hover {
  background: rgba(255,255,255,0.35);
  transform: rotate(90deg);
}

.filter-bar {
  background: var(--bg-card);
  padding: 14px 28px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
  animation: filterBarFadeIn 0.3s ease;
}

@keyframes filterBarFadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.search-box {
  flex: 1;
  min-width: 200px;
  position: relative;
}

.search-box input {
  width: 100%;
  padding: 10px 14px 10px 38px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  outline: none;
  background: var(--bg-input);
  color: var(--text-body);
  box-sizing: border-box;
  transition: border-color 0.2s ease;
}

.search-box input:focus {
  border-color: var(--primary);
}

.search-box input:focus ~ .search-icon {
  color: var(--primary);
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 16px;
  color: var(--text-gray);
  transition: color 0.2s ease;
}

.sort-group {
  display: flex;
  gap: 4px;
}

.sort-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  font-size: 13px;
  cursor: pointer;
  color: var(--text-body);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s ease;
}

.sort-btn .el-icon {
  font-size: 20px;
  transition: transform 0.2s ease;
}

.sort-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.sort-btn:hover .el-icon {
  transform: scale(1.1);
}

.sort-btn:active {
  transform: scale(0.96);
}

.sort-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.category-bar {
  padding: 10px 28px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
  animation: filterBarFadeIn 0.3s ease 0.1s both;
}

.cat-tag {
  padding: 6px 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
  background: var(--bg-hover);
  color: var(--text-body);
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.cat-tag:hover {
  background: var(--primary-light);
  color: var(--primary);
  transform: translateY(-1px);
}

.cat-tag:active {
  transform: translateY(0);
}

.cat-tag.active {
  background: var(--primary);
  color: #fff;
}

.content {
  padding: 20px 28px;
  overflow-y: auto;
  flex: 1;
  animation: contentFadeIn 0.4s ease 0.2s both;
}

@keyframes contentFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.loading-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-gray);
  animation: loadingFadeIn 0.3s ease;
}

@keyframes loadingFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.loading-state.small {
  padding: 30px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-gray);
  animation: emptyFadeIn 0.4s ease;
}

@keyframes emptyFadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  color: var(--text-gray);
  animation: emptyIconFloat 2s ease-in-out infinite;
}

@keyframes emptyIconFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

.route-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  animation: gridFadeIn 0.4s ease;
}

@keyframes gridFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.route-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-color);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  animation: cardFadeIn 0.4s ease both;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.route-card:nth-child(1) { animation-delay: 0.05s; }
.route-card:nth-child(2) { animation-delay: 0.1s; }
.route-card:nth-child(3) { animation-delay: 0.15s; }
.route-card:nth-child(4) { animation-delay: 0.2s; }
.route-card:nth-child(5) { animation-delay: 0.25s; }
.route-card:nth-child(6) { animation-delay: 0.3s; }
.route-card:nth-child(7) { animation-delay: 0.35s; }
.route-card:nth-child(8) { animation-delay: 0.4s; }

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.route-card:hover {
  border-color: var(--primary);
  box-shadow: 0 4px 12px var(--shadow-color);
  transform: translateY(-2px);
}

.route-card:hover .card-cover {
  filter: brightness(1.05);
}

.route-card:hover .card-title {
  color: var(--primary);
}

.card-cover {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: filter 0.3s ease;
}

.cover-icon {
  font-size: 42px;
  transition: transform 0.3s ease;
}

.route-card:hover .cover-icon {
  transform: scale(1.1);
}

.cover-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  background: var(--bg-card);
  color: var(--text-title);
  border: 1px solid var(--border-color);
  animation: badgeFadeIn 0.3s ease;
}

.adopted-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  background: var(--pass);
  color: #fff;
  animation: badgeFadeIn 0.3s ease;
}

.my-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  background: var(--primary);
  color: #fff;
  animation: badgeFadeIn 0.3s ease;
}

@keyframes badgeFadeIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.edit-btn, .delete-btn {
  padding: 6px 12px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
  transition: all 0.2s ease;
}

.edit-btn:active, .delete-btn:active {
  transform: scale(0.94);
}

.edit-btn {
  background: var(--warning);
}

.edit-btn:hover {
  background: var(--warning-hover);
}

.delete-btn {
  background: var(--main-delete);
}

.delete-btn:hover {
  background: var(--main-delete-hover);
}

.card-body {
  padding: 14px 16px;
  flex: 1;
  transition: padding 0.2s ease;
}

.route-card:hover .card-body {
  padding: 16px 16px 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--text-title);
  transition: color 0.2s ease;
}

.card-subtitle {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 8px;
  transition: color 0.2s ease;
}

.card-desc {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.5;
  margin-bottom: 10px;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.2s ease;
}

.route-card:hover .card-subtitle {
  color: var(--text-body);
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-gray);
  flex-wrap: wrap;
  transition: color 0.2s ease;
}

.route-card:hover .card-meta {
  color: var(--primary);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.meta-item .el-icon {
  font-size: 15px;
  transition: transform 0.2s ease;
}

.route-card:hover .meta-item .el-icon {
  transform: scale(1.1);
}

.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
  animation: tagsFadeIn 0.3s ease;
}

@keyframes tagsFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.card-tags .tag {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  background: var(--primary-light);
  color: var(--primary);
  transition: background 0.2s ease, transform 0.2s ease;
}

.card-tags .tag:hover {
  background: var(--primary-fade);
  transform: translateY(-1px);
}

.card-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-hover);
  transition: background 0.2s ease;
}

.route-card:hover .card-footer {
  background: var(--primary-light);
}

.card-footer-actions {
  display: flex;
  gap: 8px;
}

.detail-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-body);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.detail-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.detail-btn:active {
  transform: scale(0.96);
}

.adopt-btn {
  padding: 8px 20px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.adopt-btn:hover {
  background: var(--primary-hv);
}

.adopt-btn:active {
  transform: scale(0.96);
}

.adopt-btn.adopted {
  opacity: 0.6;
  cursor: not-allowed;
  background: var(--text-gray);
}

.detail-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;
  background: var(--bg-page);
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  min-width: 1314px;
  animation: detailFadeIn 0.3s ease;
}

@keyframes detailFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.detail-panel {
  background: var(--bg-page);
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: detailSlideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes detailSlideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.detail-top {
  padding: 20px 28px;
  padding-right: 80px;
  color: #fff;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-shrink: 0;
  animation: detailTopSlide 0.4s ease;
}

@keyframes detailTopSlide {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.detail-top .close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(255,255,255,0.25);
  border: none;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.detail-top .close-btn:hover {
  background: rgba(255,255,255,0.4);
  transform: rotate(90deg);
}

.detail-loading {
  padding: 30px;
  text-align: center;
  animation: loadingFadeIn 0.3s ease;
}

.top-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  animation: topLeftFadeIn 0.4s ease 0.1s both;
}

@keyframes topLeftFadeIn {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.detail-icon {
  font-size: 42px;
  animation: iconBounce 0.5s ease;
}

@keyframes iconBounce {
  0% { transform: scale(0.8); opacity: 0; }
  50% { transform: scale(1.1); }
  100% { transform: scale(1); opacity: 1; }
}

.top-info h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
  animation: titleFadeIn 0.4s ease 0.15s both;
}

@keyframes titleFadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.detail-subtitle {
  font-size: 14px;
  opacity: 0.85;
  margin-bottom: 8px;
  animation: titleFadeIn 0.4s ease 0.2s both;
}

.detail-meta-inline {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  animation: titleFadeIn 0.4s ease 0.25s both;
}

.meta-chip {
  padding: 4px 10px;
  background: rgba(255,255,255,0.2);
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.meta-chip .el-icon {
  font-size: 12px;
}

.top-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
  align-items: center;
  animation: actionsFadeIn 0.4s ease 0.2s both;
}

@keyframes actionsFadeIn {
  from {
    opacity: 0;
    transform: translateX(10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.action-btn-sm {
  padding: 10px 18px;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.action-btn-sm:active:not(:disabled) {
  transform: scale(0.96);
}

.action-btn-sm.direct {
  background: var(--pass);
}

.action-btn-sm.direct:hover:not(:disabled) {
  background: var(--pass-hover);
}

.action-btn-sm.ai {
  background: rgba(255,255,255,0.25);
  border: 1px solid rgba(255,255,255,0.3);
}

.action-btn-sm.ai:hover:not(:disabled) {
  background: rgba(255,255,255,0.35);
}

.action-btn-sm.edit {
  background: var(--warning);
}

.action-btn-sm.edit:hover {
  background: var(--warning-hover);
}

.action-btn-sm.delete {
  background: var(--main-delete);
}

.action-btn-sm.delete:hover {
  background: var(--main-delete-hover);
}

.action-btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.adopted-tag {
  padding: 8px 16px;
  background: rgba(255,255,255,0.25);
  border-radius: var(--radius-md);
  color: #fff;
  font-weight: 600;
  font-size: 13px;
  margin-left: 8px;
  animation: adoptedPulse 0.5s ease;
}

@keyframes adoptedPulse {
  0% { transform: scale(0.9); opacity: 0; }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); opacity: 1; }
}

.adopted-notice-inline {
  padding: 8px 16px;
  background: rgba(255,255,255,0.25);
  border-radius: var(--radius-md);
  animation: adoptedPulse 0.5s ease;
}

.adopted-notice-inline span {
  color: #fff;
  font-weight: 600;
  font-size: 13px;
}

.detail-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
  background: var(--bg-card);
  animation: detailContentFadeIn 0.4s ease 0.2s both;
}

@keyframes detailContentFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.detail-col {
  padding: 20px;
  overflow-y: auto;
  animation: colFadeIn 0.4s ease;
}

@keyframes colFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.col-left {
  flex: 0 0 520px;
  border-right: 1px solid var(--border-color);
  animation-delay: 0.1s;
  animation-fill-mode: both;
}

.col-middle {
  flex: 1;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  background: var(--bg-page);
  animation-delay: 0.2s;
  animation-fill-mode: both;
}

.col-right {
  flex: 0 0 400px;
  animation-delay: 0.3s;
  animation-fill-mode: both;
}

.detail-section {
  margin-bottom: 24px;
  animation: detailSectionFadeIn 0.3s ease;
}

@keyframes detailSectionFadeIn {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.detail-section h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
  animation: sectionFadeIn 0.3s ease;
  transition: border-color 0.2s ease;
}

.detail-section h3:hover {
  border-bottom-color: var(--primary);
}

@keyframes sectionFadeIn {
  from {
    opacity: 0;
    transform: translateX(-4px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.section-text {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.8;
  animation: textFadeIn 0.3s ease;
}

@keyframes textFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.section-text.muted {
  color: var(--text-gray);
}

.flowchart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-bottom: 0;
  height: 100%;
  overflow: hidden;
  animation: flowchartFadeIn 0.4s ease;
}

@keyframes flowchartFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.flowchart-section h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  animation: sectionFadeIn 0.3s ease;
}

.col-middle .flowchart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-bottom: 0;
}

.flowchart-iframe {
  flex: 1;
  width: 100%;
  min-height: 400px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  animation: iframeFadeIn 0.4s ease;
  transition: border-color 0.2s ease;
}

.flowchart-iframe:hover {
  border-color: var(--primary);
}

@keyframes iframeFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.phase-card {
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 12px;
  border-left: 4px solid var(--primary);
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
  animation: phaseFadeIn 0.3s ease both;
}

.phase-card:nth-child(1) { animation-delay: 0.05s; }
.phase-card:nth-child(2) { animation-delay: 0.1s; }
.phase-card:nth-child(3) { animation-delay: 0.15s; }
.phase-card:nth-child(4) { animation-delay: 0.2s; }
.phase-card:nth-child(5) { animation-delay: 0.25s; }

@keyframes phaseFadeIn {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.phase-card:hover {
  border-left-color: var(--primary-hv);
  background: var(--bg-card);
  transform: translateX(4px);
}

.phase-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 4px;
  transition: color 0.2s ease;
}

.phase-card:hover .phase-title {
  color: var(--primary);
}

.phase-weeks {
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 8px;
  transition: color 0.2s ease;
}

.phase-card:hover .phase-weeks {
  color: var(--text-body);
}

.phase-desc {
  font-size: 13px;
  color: var(--text-body);
  margin-bottom: 10px;
  line-height: 1.5;
}

.phase-kps {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  animation: kpsFadeIn 0.3s ease;
}

@keyframes kpsFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.phase-kps .kp {
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  background: var(--primary-light);
  color: var(--primary);
  transition: background 0.2s ease, transform 0.2s ease;
}

.phase-kps .kp:hover {
  background: var(--primary-fade);
  transform: translateY(-1px);
}

.phase-milestone {
  font-size: 12px;
  color: var(--pass);
  margin-bottom: 10px;
  padding: 6px 10px;
  background: var(--pass-bg-color);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--pass);
  transition: border-color 0.2s ease, transform 0.2s ease;
  animation: milestoneFadeIn 0.3s ease;
}

@keyframes milestoneFadeIn {
  from {
    opacity: 0;
    transform: translateX(-5px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.phase-card:hover .phase-milestone {
  border-left-color: var(--pass-hover);
  transform: translateX(2px);
}

.review-item {
  padding: 12px;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  margin-bottom: 8px;
  border: 1px solid var(--border-color);
  animation: reviewFadeIn 0.3s ease both;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.review-item:nth-child(1) { animation-delay: 0.05s; }
.review-item:nth-child(2) { animation-delay: 0.1s; }
.review-item:nth-child(3) { animation-delay: 0.15s; }
.review-item:nth-child(4) { animation-delay: 0.2s; }
.review-item:nth-child(5) { animation-delay: 0.25s; }

@keyframes reviewFadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.review-item:hover {
  border-color: var(--primary);
  transform: translateX(4px);
}

.review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.review-user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-user-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
}

.review-user {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  transition: color 0.2s ease;
}

.review-time {
  font-size: 11px;
  color: var(--text-gray);
}

.review-item:hover .review-user {
  color: var(--primary);
}

.review-stars {
  color: var(--warning);
  font-size: 13px;
  display: inline-flex;
  gap: 2px;
  transition: transform 0.2s ease;
}

.review-item:hover .review-stars {
  transform: scale(1.05);
}

.review-stars .el-icon {
  font-size: 13px;
}

.review-text {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.5;
  transition: color 0.2s ease;
}

.review-item:hover .review-text {
  color: var(--text-title);
}

.review-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  animation: reviewFormFadeIn 0.3s ease;
}

@keyframes reviewFormFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.star-rating {
  display: flex;
  gap: 4px;
  animation: starRatingFadeIn 0.3s ease;
}

@keyframes starRatingFadeIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.star-rating .star {
  cursor: pointer;
  font-size: 20px;
  opacity: 0.4;
  color: var(--warning);
  transition: all 0.15s ease;
}

.star-rating .star:hover {
  opacity: 0.7;
  transform: scale(1.15);
}

.star-rating .star.active {
  opacity: 1;
}

.star-rating .star:active {
  transform: scale(0.9);
}

.review-form textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  resize: vertical;
  background: var(--bg-input);
  color: var(--text-body);
  font-size: 13px;
  box-sizing: border-box;
  transition: border-color 0.2s ease;
}

.review-form textarea:focus {
  border-color: var(--primary);
  outline: none;
}

.submit-review-btn {
  padding: 8px 20px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  align-self: flex-end;
  transition: all 0.2s ease;
}

.submit-review-btn:hover {
  background: var(--primary-hv);
}

.submit-review-btn:active {
  transform: scale(0.96);
}

/* Share Dialog Styles */
.share-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.25s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.share-dialog {
  background: var(--bg-card);
  border-radius: 16px;
  width: 92%;
  max-width: 640px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255,255,255,0.05);
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.share-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.share-header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.share-header-icon {
  font-size: 28px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 2px;
}

.share-dialog-header h3 {
  margin: 0 0 4px;
  font-size: 17px;
  font-weight: 700;
  color: var(--text-title);
}

.share-header-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-gray);
}

.share-dialog-close {
  background: none;
  border: none;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 22px;
  cursor: pointer;
  color: var(--text-gray);
  transition: all 0.15s;
  flex-shrink: 0;
}

.share-dialog-close:hover {
  background: var(--bg-hover);
  color: var(--text-title);
}

.share-dialog-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.share-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.share-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.share-section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--primary-light);
}

.share-form-row {
  display: flex;
  gap: 16px;
}

.share-form-row .share-form-item {
  flex: 1;
}

.share-form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}

.share-form-item label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-body);
}

.required {
  color: #ef4444;
}

.share-hint {
  font-weight: 400;
  color: var(--text-gray);
  font-size: 12px;
}

.share-char-count {
  position: absolute;
  right: 10px;
  top: 28px;
  font-size: 11px;
  color: var(--text-gray);
  pointer-events: none;
}

.share-input,
.share-textarea,
.share-select {
  width: 100%;
  padding: 10px 12px;
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-input);
  color: var(--text-body);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.share-input:focus,
.share-textarea:focus,
.share-select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(45, 125, 219, 0.1);
}

.share-input::placeholder,
.share-textarea::placeholder {
  color: var(--text-gray);
  opacity: 0.7;
}

.share-textarea {
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
}

.share-select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%239ca3af' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}

.share-select option {
  background: var(--bg-card);
  color: var(--text-body);
}

.share-difficulty-group {
  display: flex;
  gap: 0;
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.share-diff-btn {
  flex: 1;
  padding: 9px 0;
  border: none;
  background: var(--bg-input);
  color: var(--text-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border-right: 1px solid var(--border-color);
}

.share-diff-btn:last-child {
  border-right: none;
}

.share-diff-btn:hover {
  background: var(--bg-hover);
}

.share-diff-btn.active {
  background: var(--primary);
  color: #fff;
  font-weight: 600;
}

.share-dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
  background: var(--bg-card);
}

.share-btn-cancel {
  padding: 9px 20px;
  border: 1.5px solid var(--border-color);
  border-radius: 10px;
  background: transparent;
  color: var(--text-body);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.share-btn-cancel:hover {
  background: var(--bg-hover);
  border-color: var(--text-gray);
}

.share-btn-submit {
  padding: 9px 24px;
  border: none;
  border-radius: 10px;
  background: var(--primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.share-btn-submit:hover:not(:disabled) {
  background: var(--primary-hv);
  transform: translateY(-1px);
}

.share-btn-submit:active:not(:disabled) {
  transform: translateY(0);
}

.share-btn-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.dark .share-dialog {
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.06);
}

.dark .share-btn-submit {
  box-shadow: 0 2px 8px rgba(45, 125, 219, 0.15);
}

.dark .share-btn-submit:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.25);
}

.detail-col::-webkit-scrollbar,
.content::-webkit-scrollbar {
  width: 8px;
}

.detail-col::-webkit-scrollbar-track,
.content::-webkit-scrollbar-track {
  background: var(--bg-hover);
}

.detail-col::-webkit-scrollbar-thumb,
.content::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}

.detail-col::-webkit-scrollbar-thumb:hover,
.content::-webkit-scrollbar-thumb:hover {
  background: var(--text-gray);
}
</style>

<!-- 移动端知识点智能对比组件 -->
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { showToast, showConfirmDialog } from 'vant'

// 兼容 ElMessage / ElMessageBox → vant
const ElMessage = {
  success: (msg) => showToast({ type: 'success', message: msg, position: 'middle', duration: 2000 }),
  error: (msg) => showToast({ type: 'fail', message: msg, position: 'middle', duration: 3000 }),
  info: (msg) => showToast({ message: msg, position: 'middle', duration: 2000 }),
  warning: (msg) => showToast({ message: msg, position: 'middle', duration: 2000 })
}
const ElMessageBox = {
  confirm: (message, title) => showConfirmDialog({ title: title || '提示', message })
}
import { useRouter } from 'vue-router'
import {
  getKnowledgeListApi,
  addCustomKnowledgeApi,
  removeCustomKnowledgeApi,
  getRecommendationsApi,
  compareKnowledgeApi
} from '@/api/mainApi/resourceKnowledgeComparison.js'

// =================== 用户信息 ===================
const userId = ref('')
const router = useRouter()
const goBack = () => router.back()

// =================== 视图切换 ===================
const currentView = ref('select') // 'select' | 'result'

const switchView = (view) => {
  currentView.value = view
}

// =================== 数据 ===================
const selectedA = ref(null)
const selectedB = ref(null)
const allKnowledge = ref([])
const recommendations = ref([])
const draggedName = ref(null)
const dragOverSlot = ref(null) // 'a' | 'b' | null

// 搜索
const searchQuery = ref('')

// 自定义添加
const customName = ref('')
const customCategory = ref('自定义')

// 加载 & 对比结果
const loading = ref(false)
const compareLoading = ref(false)
const comparisonResult = ref(null)

// =================== 触摸拖拽（移动端） ===================
// touchDrag: { name, startX, startY, x, y, started }
const touchDrag = ref(null)
const touchDragOverSlot = ref(null)
const justDragged = ref(false)

// =================== 计算属性 ===================
const selectedCount = computed(() => (selectedA.value ? 1 : 0) + (selectedB.value ? 1 : 0))

const canCompare = computed(() => !!(selectedA.value && selectedB.value))

const knowledgeRoot = computed(() => allKnowledge.value[0] || null)

const filteredGroups = computed(() => {
  const root = knowledgeRoot.value
  if (!root || !root.children) return []
  const query = searchQuery.value.toLowerCase().trim()
  if (!query) return root.children
  return root.children
    .map(group => ({
      ...group,
      items: group.items.filter(
        item =>
          item.name.toLowerCase().includes(query) ||
          item.category.toLowerCase().includes(query)
      )
    }))
    .filter(group => group.items.length > 0)
})

// 对比结果拆解
const resultComparison = computed(() => comparisonResult.value?.comparison || {})
const resultVizA = computed(() => comparisonResult.value?.visualization_a || {})
const resultVizB = computed(() => comparisonResult.value?.visualization_b || {})

// =================== 内置知识点（兜底） ===================
function getBuiltinKnowledge() {
  return [
    {
      name: '全部知识点',
      category: '',
      children: [
        {
          category: '线性结构',
          items: [
            { name: '顺序表', category: '线性结构' },
            { name: '单链表', category: '线性结构' },
            { name: '双向链表', category: '线性结构' },
            { name: '循环链表', category: '线性结构' },
            { name: '栈', category: '线性结构' },
            { name: '队列', category: '线性结构' },
            { name: '双端队列', category: '线性结构' }
          ]
        },
        {
          category: '树形结构',
          items: [
            { name: '二叉搜索树', category: '树形结构' },
            { name: 'AVL平衡树', category: '树形结构' },
            { name: '红黑树', category: '树形结构' },
            { name: 'B树', category: '树形结构' },
            { name: 'B+树', category: '树形结构' },
            { name: '堆', category: '树形结构' },
            { name: 'Trie树', category: '树形结构' }
          ]
        },
        {
          category: '图形结构',
          items: [
            { name: '图(邻接表)', category: '图形结构' },
            { name: '图(邻接矩阵)', category: '图形结构' }
          ]
        },
        {
          category: '哈希结构',
          items: [
            { name: '哈希表', category: '哈希结构' },
            { name: '布隆过滤器', category: '哈希结构' }
          ]
        },
        {
          category: '排序算法',
          items: [
            { name: '快速排序', category: '排序算法' },
            { name: '归并排序', category: '排序算法' },
            { name: '堆排序', category: '排序算法' },
            { name: '冒泡排序', category: '排序算法' },
            { name: '插入排序', category: '排序算法' }
          ]
        },
        {
          category: '查找算法',
          items: [
            { name: '二分查找', category: '查找算法' },
            { name: '哈希查找', category: '查找算法' },
            { name: 'BFS广度优先', category: '查找算法' },
            { name: 'DFS深度优先', category: '查找算法' }
          ]
        }
      ]
    }
  ]
}

// =================== 加载知识点列表 ===================
async function loadKnowledgeList() {
  try {
    const data = await getKnowledgeListApi(userId.value)
    if (data && data.success && data.data) {
      allKnowledge.value = data.data
    } else {
      allKnowledge.value = getBuiltinKnowledge()
    }
  } catch (e) {
    console.error('加载知识点列表失败:', e)
    allKnowledge.value = getBuiltinKnowledge()
  }
  loadRecommendations()
}

// =================== 加载推荐 ===================
async function loadRecommendations() {
  try {
    const data = await getRecommendationsApi()
    if (data && data.success && data.data && data.data.length > 0) {
      recommendations.value = data.data
    } else {
      recommendations.value = []
    }
  } catch (e) {
    recommendations.value = [
      { knowledge_a: '顺序表', knowledge_b: '单链表', reason: '存储结构不同，适用场景有重叠' },
      { knowledge_a: '栈', knowledge_b: '队列', reason: '都是线性结构，但操作受限不同' },
      { knowledge_a: '二叉搜索树', knowledge_b: 'AVL平衡树', reason: 'BST的优化版本，理解平衡树的必要性' },
      { knowledge_a: 'B树', knowledge_b: 'B+树', reason: '磁盘索引的两种主要实现' },
      { knowledge_a: '哈希表', knowledge_b: '二叉搜索树', reason: '查找效率对比，空间换时间' }
    ]
  }
}

// =================== 拖拽（桌面） ===================
function onDragStart(event, name) {
  draggedName.value = name
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.setData('text/plain', name)
}

function onDragEnd() {
  draggedName.value = null
}

function onDragOver(slot) {
  dragOverSlot.value = slot
}

function onDragLeave(slot) {
  if (dragOverSlot.value === slot) {
    dragOverSlot.value = null
  }
}

function onDrop(slot) {
  const name = draggedName.value || (touchDrag.value && touchDrag.value.started ? touchDrag.value.name : null)
  dragOverSlot.value = null
  if (!name) return

  // 如果拖入的名称已在另一个槽，则交换
  if (slot === 'a' && selectedB.value === name) {
    selectedB.value = selectedA.value
    selectedA.value = name
  } else if (slot === 'b' && selectedA.value === name) {
    selectedA.value = selectedB.value
    selectedB.value = name
  } else {
    if (slot === 'a') selectedA.value = name
    else selectedB.value = name
  }
}

// =================== 触摸拖拽（移动端） ===================
function onTouchStart(event, name) {
  if (event.touches.length !== 1) return
  const touch = event.touches[0]
  touchDrag.value = {
    name,
    startX: touch.clientX,
    startY: touch.clientY,
    x: touch.clientX,
    y: touch.clientY,
    started: false
  }
  document.addEventListener('touchmove', onTouchMove, { passive: false })
  document.addEventListener('touchend', onTouchEnd)
  document.addEventListener('touchcancel', onTouchEnd)
}

function onTouchMove(event) {
  const d = touchDrag.value
  if (!d || event.touches.length !== 1) return
  const touch = event.touches[0]
  d.x = touch.clientX
  d.y = touch.clientY

  // 超过阈值才开始拖拽，避免误触阻断点击
  if (!d.started) {
    const dx = touch.clientX - d.startX
    const dy = touch.clientY - d.startY
    if (Math.sqrt(dx * dx + dy * dy) < 8) return
    d.started = true
  }

  event.preventDefault()

  // 探测手指下方是否为投放槽
  const el = document.elementFromPoint(touch.clientX, touch.clientY)
  let slot = null
  if (el) {
    const slotEl = el.closest('.kc-drop-slot')
    if (slotEl && slotEl.dataset && slotEl.dataset.slot) {
      slot = slotEl.dataset.slot
    }
  }
  touchDragOverSlot.value = slot
}

function onTouchEnd() {
  const d = touchDrag.value
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
  document.removeEventListener('touchcancel', onTouchEnd)

  if (d && d.started) {
    if (touchDragOverSlot.value) {
      draggedName.value = d.name
      onDrop(touchDragOverSlot.value)
      draggedName.value = null
    }
    justDragged.value = true
    setTimeout(() => { justDragged.value = false }, 350)
  }
  touchDrag.value = null
  touchDragOverSlot.value = null
}

// =================== 点击选择 ===================
function selectKnowledge(name) {
  if (justDragged.value) return
  // 已选则取消
  if (selectedA.value === name) {
    selectedA.value = null
    return
  }
  if (selectedB.value === name) {
    selectedB.value = null
    return
  }
  // 已选满2个，A←B，B←新
  if (selectedA.value && selectedB.value) {
    selectedA.value = selectedB.value
    selectedB.value = name
  } else if (!selectedA.value) {
    selectedA.value = name
  } else if (!selectedB.value) {
    selectedB.value = name
  }
}

function clearSlot(slot) {
  if (justDragged.value) return
  if (slot === 'a') selectedA.value = null
  else selectedB.value = null
}

// =================== 推荐组合点击 ===================
function applyRecommendation(rec) {
  selectedA.value = rec.knowledge_a
  selectedB.value = rec.knowledge_b
  showToast(`已选择：${rec.knowledge_a} VS ${rec.knowledge_b}`)
  const el = document.querySelector('.phone-content')
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' })
}

// =================== 自定义知识点 ===================
async function addCustomKnowledge() {
  const name = customName.value.trim()
  if (!name) {
    ElMessage.error('请输入知识点名称')
    return
  }
  try {
    const data = await addCustomKnowledgeApi({
      user_id: userId.value,
      name: name,
      category: customCategory.value
    })
    if (data && data.success) {
      ElMessage.success(`已添加「${name}」`)
      customName.value = ''
      await loadKnowledgeList()
    } else {
      ElMessage.error((data && data.message) || '添加失败')
    }
  } catch (e) {
    ElMessage.error('添加失败: ' + e.message)
  }
}

async function removeCustomKnowledge(name) {
  try {
    await ElMessageBox.confirm(`确定删除自定义知识点「${name}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    const data = await removeCustomKnowledgeApi({
      user_id: userId.value,
      name: name
    })
    if (data && data.success) {
      ElMessage.info(`已删除「${name}」`)
      if (selectedA.value === name) selectedA.value = null
      if (selectedB.value === name) selectedB.value = null
      await loadKnowledgeList()
    } else {
      ElMessage.error((data && data.message) || '删除失败')
    }
  } catch (e) {
    ElMessage.error('删除失败: ' + e.message)
  }
}

// =================== 开始对比 ===================
async function startComparison() {
  if (!selectedA.value || !selectedB.value) {
    ElMessage.error('请选择两个知识点')
    return
  }
  loading.value = true
  compareLoading.value = true
  try {
    const data = await compareKnowledgeApi({
      knowledge_point_a: selectedA.value,
      knowledge_point_b: selectedB.value
    })
    if (data && data.success) {
      comparisonResult.value = data.data
      switchView('result')
      ElMessage.success('对比分析完成！')
    } else {
      ElMessage.error((data && data.error) || '对比分析失败')
    }
  } catch (e) {
    ElMessage.error(`对比分析失败: ${e.message}`)
    console.error(e)
  } finally {
    loading.value = false
    compareLoading.value = false
  }
}

// =================== userId 变更 ===================
function onUserIdChange() {
  const v = userId.value.trim()
  userId.value = v || 'user_001'
  loadKnowledgeList()
}

// =================== 初始化 ===================
onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.id) {
        userId.value = loginUser.id
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  loadKnowledgeList()
})

onBeforeUnmount(() => {
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
  document.removeEventListener('touchcancel', onTouchEnd)
})
</script>

<template>
  <div class="kc-container">
    <!-- 装饰光斑（缩小版，无光点动画以提升移动端性能） -->
    <div class="kc-blob"></div>

    <!-- 顶部导航栏 -->
    <div class="mobile-header">
      <div class="header-left" @click="goBack">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="header-title">知识点智能对比</div>
      <div class="header-right">
        <van-icon
          v-if="currentView === 'result'"
          name="replay"
          size="20"
          @click="switchView('select')"
        />
      </div>
    </div>

    <div class="kc-content">
      <!-- 视图切换 -->
      <div class="kc-view-toggle">
        <button :class="{ active: currentView === 'select' }" @click="switchView('select')">
          <el-icon><Reading /></el-icon> 选择
        </button>
        <button :class="{ active: currentView === 'result' }" @click="switchView('result')">
          <el-icon><TrendCharts /></el-icon> 结果
        </button>
      </div>

      <!-- ── 选择视图 ── -->
      <div v-show="currentView === 'select'" class="kc-panel">
        <div class="kc-knowledge-selector">
          <div class="kc-selector-header">
            <div class="kc-selector-title">选择两个知识点进行对比</div>
            <div class="kc-selected-info">
              已选: <span class="kc-selected-highlight">{{ selectedCount }}</span> / 2
            </div>
          </div>

          <!-- 拖拽区域（垂直堆叠） -->
          <div class="kc-drop-zone-container">
            <div
              class="kc-drop-slot"
              data-slot="a"
              :class="{
                'filled-a': selectedA,
                'drag-over-a': dragOverSlot === 'a' || touchDragOverSlot === 'a'
              }"
              @dragover.prevent="onDragOver('a')"
              @dragleave="onDragLeave('a')"
              @drop.prevent="onDrop('a')"
              @click="clearSlot('a')"
            >
              <div class="kc-slot-badge">A</div>
              <div class="kc-slot-label">知识点 A</div>
              <div class="kc-slot-value" :class="{ 'kc-slot-placeholder': !selectedA }">
                {{ selectedA || '拖拽或点击选择' }}
              </div>
              <div class="kc-slot-hint">长按拖到此处 / 点击清除</div>
              <button
                v-if="selectedA"
                class="kc-clear-btn"
                @click.stop="clearSlot('a')"
              >×</button>
            </div>

            <div class="kc-compare-arrow">VS</div>

            <div
              class="kc-drop-slot"
              data-slot="b"
              :class="{
                'filled-b': selectedB,
                'drag-over-b': dragOverSlot === 'b' || touchDragOverSlot === 'b'
              }"
              @dragover.prevent="onDragOver('b')"
              @dragleave="onDragLeave('b')"
              @drop.prevent="onDrop('b')"
              @click="clearSlot('b')"
            >
              <div class="kc-slot-badge">B</div>
              <div class="kc-slot-label">知识点 B</div>
              <div class="kc-slot-value" :class="{ 'kc-slot-placeholder': !selectedB }">
                {{ selectedB || '拖拽或点击选择' }}
              </div>
              <div class="kc-slot-hint">长按拖到此处 / 点击清除</div>
              <button
                v-if="selectedB"
                class="kc-clear-btn"
                @click.stop="clearSlot('b')"
              >×</button>
            </div>
          </div>

          <button
            class="kc-compare-btn"
            :class="{ loading: compareLoading }"
            :disabled="!canCompare || compareLoading"
            @click="startComparison"
          >
            <el-icon><Search /></el-icon> 开始对比分析
          </button>

          <!-- 添加自定义知识点 -->
          <div class="kc-add-custom-bar">
            <input
              v-model="customName"
              type="text"
              placeholder="输入自定义知识点名称..."
              @keyup.enter="addCustomKnowledge"
            />
            <div class="kc-add-row">
              <select v-model="customCategory">
                <option value="自定义">自定义</option>
                <option value="线性结构">线性结构</option>
                <option value="树形结构">树形结构</option>
                <option value="图形结构">图形结构</option>
                <option value="哈希结构">哈希结构</option>
                <option value="排序算法">排序算法</option>
                <option value="查找算法">查找算法</option>
                <option value="其他">其他</option>
              </select>
              <button @click="addCustomKnowledge"><el-icon><Plus /></el-icon> 添加</button>
            </div>
          </div>

          <!-- 搜索 -->
          <div class="kc-search-box">
            <el-icon class="kc-search-icon"><Search /></el-icon>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索知识点..."
            />
          </div>

          <!-- 知识图谱（2 列） -->
          <div class="kc-knowledge-container">
            <div
              v-for="(group, gi) in filteredGroups"
              :key="gi"
              class="kc-category-group"
            >
              <div class="kc-category-title">
                {{ group.category }}
                <span v-if="group.is_custom" class="kc-custom-badge">用户自定义</span>
              </div>
              <div class="kc-knowledge-graph">
                <div
                  v-for="(item, ii) in group.items"
                  :key="ii"
                  class="kc-knowledge-node"
                  :class="{
                    custom: group.is_custom,
                    'selected-a': selectedA === item.name,
                    'selected-b': selectedB === item.name
                  }"
                  draggable="true"
                  @dragstart="onDragStart($event, item.name)"
                  @dragend="onDragEnd"
                  @touchstart="onTouchStart($event, item.name)"
                  @click="selectKnowledge(item.name)"
                >
                  <div class="kc-node-drag-icon">⋮⋮</div>
                  <button
                    v-if="group.is_custom"
                    class="kc-node-del"
                    title="删除"
                    @click.stop="removeCustomKnowledge(item.name)"
                  >×</button>
                  <div class="kc-node-name">{{ item.name }}</div>
                  <div class="kc-node-cat">{{ item.category }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 推荐 -->
          <div v-if="recommendations.length > 0" class="kc-recommendations">
            <div class="kc-rec-title"><van-icon name="star-o" /> 推荐对比组合</div>
            <div class="kc-rec-list">
              <div
                v-for="(rec, ri) in recommendations"
                :key="ri"
                class="kc-rec-item"
                @click="applyRecommendation(rec)"
              >
                <div class="kc-rec-pair">
                  {{ rec.knowledge_a }} <span class="kc-vs-inline">VS</span> {{ rec.knowledge_b }}
                </div>
                <div class="kc-rec-reason">{{ rec.reason || '' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 结果视图 ── -->
      <div v-show="currentView === 'result'" class="kc-panel">
        <div v-if="comparisonResult" class="kc-comparison-result">
          <!-- 返回按钮 + 标题 -->
          <button class="kc-back-btn" @click="switchView('select')">
            <el-icon><ArrowLeft /></el-icon> 返回重新选择
          </button>

          <div class="kc-result-header">
            <div class="kc-result-title">
              <span class="kp-a">{{ comparisonResult.knowledge_point_a }}</span>
              <span class="kc-vs">VS</span>
              <span class="kp-b">{{ comparisonResult.knowledge_point_b }}</span>
            </div>
            <div class="kc-result-subtitle">{{ resultComparison.summary || '' }}</div>
          </div>

          <!-- 可视化（单列） -->
          <div class="kc-visualization-section">
            <div class="kc-viz-card">
              <div class="kc-viz-card-header">
                <div class="kc-viz-badge a">A</div>
                <div class="kc-viz-title">{{ comparisonResult.knowledge_point_a }}</div>
              </div>
              <div class="kc-viz-desc">
                {{ resultVizA.description || resultComparison.concept_a || '' }}
              </div>
              <pre class="kc-viz-diagram">{{ resultVizA.ascii_diagram || '暂无可视化' }}</pre>
              <div class="kc-viz-highlights">
                <span
                  v-for="(h, hi) in (resultVizA.highlights || [])"
                  :key="hi"
                  class="kc-highlight-tag"
                >{{ h }}</span>
              </div>
            </div>

            <div class="kc-viz-card">
              <div class="kc-viz-card-header">
                <div class="kc-viz-badge b">B</div>
                <div class="kc-viz-title">{{ comparisonResult.knowledge_point_b }}</div>
              </div>
              <div class="kc-viz-desc">
                {{ resultVizB.description || resultComparison.concept_b || '' }}
              </div>
              <pre class="kc-viz-diagram">{{ resultVizB.ascii_diagram || '暂无可视化' }}</pre>
              <div class="kc-viz-highlights">
                <span
                  v-for="(h, hi) in (resultVizB.highlights || [])"
                  :key="hi"
                  class="kc-highlight-tag"
                >{{ h }}</span>
              </div>
            </div>
          </div>

          <!-- 对比表格（横向滚动） -->
          <div class="kc-comparison-table-section">
            <div class="kc-section-title"><el-icon><TrendCharts /></el-icon> 多维度对比分析</div>
            <div class="kc-table-scroll">
              <table class="kc-comparison-table">
                <thead>
                  <tr>
                    <th>对比维度</th>
                    <th class="kp-a">{{ comparisonResult.knowledge_point_a }}</th>
                    <th class="kp-b">{{ comparisonResult.knowledge_point_b }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(c, ci) in (resultComparison.comparisons || [])"
                    :key="ci"
                  >
                    <td class="kc-dimension">{{ c.dimension }}</td>
                    <td>{{ c.value_a }}</td>
                    <td>{{ c.value_b }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 关键区别 -->
          <div
            v-if="resultComparison.key_differences && resultComparison.key_differences.length > 0"
            class="kc-key-differences"
          >
            <div class="kc-section-title"><el-icon><Key /></el-icon> 关键区别</div>
            <div class="kc-differences-list">
              <div
                v-for="(diff, di) in resultComparison.key_differences"
                :key="di"
                class="kc-difference-item"
              >
                <div class="kc-difference-icon">{{ di + 1 }}</div>
                <div class="kc-difference-text">{{ diff }}</div>
              </div>
            </div>
          </div>

          <!-- 总结 -->
          <div v-if="resultComparison.summary" class="kc-summary-section">
            <div class="kc-section-title kc-section-title-sm"><el-icon><Document /></el-icon> 总结</div>
            <div class="kc-summary-text">{{ resultComparison.summary }}</div>
          </div>
        </div>

        <!-- 无结果占位 -->
        <div v-else class="kc-empty-result">
          <p>暂无对比结果，请先选择知识点进行对比分析</p>
          <button class="kc-back-btn" @click="switchView('select')">
            <el-icon><ArrowLeft /></el-icon> 去选择知识点
          </button>
        </div>
      </div>
    </div>

    <!-- 触摸拖拽跟随浮层 -->
    <div
      v-if="touchDrag && touchDrag.started"
      class="kc-touch-clone"
      :style="{ left: touchDrag.x + 'px', top: touchDrag.y + 'px' }"
    >
      {{ touchDrag.name }}
    </div>

    <!-- 加载遮罩 -->
    <div v-if="loading" class="kc-loading-overlay">
      <div class="kc-loading-card">
        <div class="kc-loading-spinner"></div>
        <div class="kc-loading-text">正在分析知识点...</div>
        <div class="kc-loading-sub">AI 正在进行多维度对比</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ===== 顶部导航栏 ===== */
.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.2s;
  color: var(--text-title);
}

.header-left:active,
.header-right:active {
  background: var(--bg-hover);
}

.header-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title);
  letter-spacing: 0.5px;
}

.kc-container {
  position: relative;
  min-height: 100vh;
  background: transparent;
  overflow: hidden;
}

/* 装饰光斑（缩小版） */
.kc-blob {
  position: fixed;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.1;
  z-index: 0;
  pointer-events: none;
  background: var(--primary);
  top: -60px;
  left: -60px;
  animation: kc-float-bg 20s ease-in-out infinite;
}

@keyframes kc-float-bg {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(20px, 30px) scale(1.1); }
}

.kc-content {
  position: relative;
  z-index: 2;
  width: 100%;
  margin: 0 auto;
  padding: 60px 12px 40px;
}

/* Header */
.title {
  text-align: center;
  margin-bottom: 16px;
}
.title h1 {
  margin-top: 6px;
  font-size: 20px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.header-icon {
  font-size: 22px;
  color: var(--primary);
}
.subtitle {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 4px;
}

/* 视图切换 */
.kc-view-toggle {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 16px;
}

.kc-view-toggle button {
  flex: 1;
  min-height: 44px;
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-gray);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.kc-view-toggle button:active {
  background: var(--bg-hover);
  color: var(--text-title);
}

.kc-view-toggle button.active {
  background: var(--grad-primary);
  color: var(--btn-text);
  border-color: transparent;
  box-shadow: var(--shadow-brand);
}

/* 面板 */
.kc-panel {
  animation: kc-fade-in 0.4s ease;
}

@keyframes kc-fade-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 选择器卡片 */
.kc-knowledge-selector {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  box-shadow: var(--shadow-normal);
}

.kc-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.kc-selector-title {
  color: var(--text-title);
  font-size: 16px;
  font-weight: 600;
}

.kc-selected-info {
  color: var(--text-gray);
  font-size: 13px;
}

.kc-selected-highlight {
  color: var(--purple-text);
  font-weight: 600;
}

/* 拖拽区域（垂直堆叠） */
.kc-drop-zone-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: stretch;
  margin-bottom: 16px;
}

.kc-drop-slot {
  min-height: 96px;
  padding: 16px 14px;
  border-radius: var(--radius-md);
  border: 2px dashed var(--border-color);
  background: var(--bgc-transparent);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  position: relative;
}

.kc-drop-slot:active {
  border-color: var(--text-gray);
  background: var(--bg-hover);
}

.kc-drop-slot.drag-over-a {
  border-color: var(--pass);
  background: var(--pass-bg-color);
  transform: scale(1.02);
}

.kc-drop-slot.drag-over-b {
  border-color: var(--coming);
  background: var(--coming-bg-color);
  transform: scale(1.02);
}

.kc-drop-slot.filled-a {
  border-style: solid;
  border-color: var(--pass);
  background: var(--pass-bg-color);
}

.kc-drop-slot.filled-b {
  border-style: solid;
  border-color: var(--coming);
  background: var(--coming-bg-color);
}

.kc-slot-label {
  font-size: 11px;
  color: var(--text-gray);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.kc-slot-badge {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 6px;
  background: var(--bgc-mid);
  color: var(--text-gray);
}

.kc-drop-slot.filled-a .kc-slot-badge {
  background: var(--pass);
  color: var(--btn-text);
}

.kc-drop-slot.filled-b .kc-slot-badge {
  background: var(--coming);
  color: var(--btn-text);
}

.kc-slot-value {
  font-size: 16px;
  color: var(--text-title);
  font-weight: 600;
  word-break: break-all;
}

.kc-slot-placeholder {
  font-size: 13px;
  color: var(--text-gray);
  font-weight: normal;
}

.kc-slot-hint {
  font-size: 11px;
  color: var(--text-gray);
  opacity: 0.7;
  margin-top: 4px;
}

.kc-clear-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bgc-mid);
  border: none;
  color: var(--text-title);
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.kc-clear-btn:active {
  background: var(--main-delete);
  color: var(--btn-text);
}

.kc-compare-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: var(--purple-text);
  font-weight: 700;
  min-height: 28px;
  animation: kc-bounce 2s infinite;
}

@keyframes kc-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

/* 对比按钮 */
.kc-compare-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: 48px;
  padding: 14px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--grad-primary);
  color: var(--btn-text);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 4px;
}

.kc-compare-btn:active:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-brand);
}

.kc-compare-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.kc-compare-btn.loading {
  opacity: 0.8;
  cursor: wait;
}

/* 添加自定义 */
.kc-add-custom-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 20px;
  margin-bottom: 16px;
}

.kc-add-custom-bar input {
  width: 100%;
  min-height: 44px;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  color: var(--text-title);
  font-size: 14px;
  outline: none;
  transition: all 0.3s;
}

.kc-add-custom-bar input::placeholder {
  color: var(--text-gray);
  opacity: 0.6;
}

.kc-add-custom-bar input:focus {
  border-color: var(--primary);
}

.kc-add-row {
  display: flex;
  gap: 10px;
}

.kc-add-row select {
  flex: 1;
  min-height: 44px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  color: var(--text-title);
  font-size: 14px;
  outline: none;
  cursor: pointer;
}

.kc-add-row select option {
  background: var(--bg-card);
  color: var(--text-title);
}

.kc-add-row button {
  min-height: 44px;
  padding: 10px 18px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--pass);
  color: var(--btn-text);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}

.kc-add-row button:active {
  background: var(--pass-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--pass-shadow);
}

/* 搜索 */
.kc-search-box {
  position: relative;
  margin-bottom: 16px;
}

.kc-search-box input {
  width: 100%;
  min-height: 44px;
  padding: 10px 14px 10px 40px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  color: var(--text-title);
  font-size: 14px;
  outline: none;
  transition: all 0.3s;
}

.kc-search-box input::placeholder {
  color: var(--text-gray);
  opacity: 0.6;
}

.kc-search-box input:focus {
  border-color: var(--primary);
}

.kc-search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-gray);
  font-size: 16px;
  z-index: 1;
}

/* 知识图谱（2 列） */
.kc-knowledge-graph {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-top: 10px;
}

.kc-knowledge-node {
  padding: 12px 10px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  border: 1px solid var(--border-color);
  cursor: grab;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: center;
  position: relative;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  touch-action: pan-y;
  min-height: 60px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.kc-knowledge-node:active {
  cursor: grabbing;
  transform: scale(0.97);
}

.kc-knowledge-node.selected-a {
  border-color: var(--pass);
  background: var(--pass-bg-color);
  box-shadow: 0 4px 16px var(--pass-shadow);
}

.kc-knowledge-node.selected-b {
  border-color: var(--coming);
  background: var(--coming-bg-color);
  box-shadow: 0 4px 16px var(--coming-shadow);
}

.kc-node-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title);
  position: relative;
  z-index: 1;
  word-break: break-all;
}

.kc-node-cat {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 2px;
  position: relative;
  z-index: 1;
}

.kc-node-drag-icon {
  position: absolute;
  top: 4px;
  right: 4px;
  font-size: 10px;
  color: var(--text-gray);
  opacity: 0.4;
  z-index: 1;
}

.kc-node-del {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--main-fail-status);
  border: none;
  color: var(--main-delete);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.kc-node-del:active {
  background: var(--main-fail-status-hover);
}

/* 分类组 */
.kc-category-group {
  margin-top: 18px;
}

.kc-category-title {
  color: var(--text-gray);
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
  padding-left: 6px;
  border-left: 3px solid var(--primary);
}

.kc-custom-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  background: var(--pass-bg-color);
  color: var(--pass);
  margin-left: 6px;
}

/* 推荐 */
.kc-recommendations {
  margin-top: 24px;
  padding: 16px;
  background: var(--bgc-transparent);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.kc-rec-title {
  color: var(--text-body);
  font-size: 14px;
  margin-bottom: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.kc-rec-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kc-rec-item {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s;
  min-height: 44px;
}

.kc-rec-item:active {
  background: var(--primary-light);
  border-color: var(--primary);
  transform: translateX(2px);
}

.kc-rec-pair {
  font-size: 14px;
  color: var(--text-title);
  font-weight: 500;
  word-break: break-all;
}

.kc-rec-pair .kc-vs-inline {
  color: var(--purple-text);
  margin: 0 4px;
  font-weight: 600;
}

.kc-vs {
  color: var(--text-gray);
  margin: 0 8px;
  font-weight: 400;
}

.kc-rec-reason {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 4px;
}

/* 结果视图 */
.kc-comparison-result {
  animation: kc-fade-in 0.5s ease;
}

.kc-result-header {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 18px 16px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-normal);
}

.kc-result-title {
  text-align: center;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 4px;
  word-break: break-all;
  line-height: 1.4;
}

.kc-result-title .kp-a {
  color: var(--pass);
}

.kc-result-title .kp-b {
  color: var(--coming);
}

.kc-result-subtitle {
  text-align: center;
  color: var(--text-gray);
  font-size: 13px;
  margin-top: 4px;
}

.kc-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 8px 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  border-radius: var(--radius-md);
  color: var(--text-gray);
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 14px;
  transition: all 0.2s;
}

.kc-back-btn:active {
  border-color: var(--primary);
  color: var(--primary);
}

.kc-empty-result {
  text-align: center;
  padding: 40px 16px;
  color: var(--text-gray);
}

.kc-empty-result p {
  margin-bottom: 16px;
  font-size: 14px;
}

/* 可视化区域（单列） */
.kc-visualization-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 16px;
}

.kc-viz-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-normal);
}

.kc-viz-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-color);
}

.kc-viz-badge {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--btn-text);
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.kc-viz-badge.a {
  background: var(--pass);
}

.kc-viz-badge.b {
  background: var(--coming);
}

.kc-viz-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title);
  word-break: break-all;
}

.kc-viz-desc {
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 10px;
  line-height: 1.6;
}

.kc-viz-diagram {
  background: var(--bg-hover);
  color: var(--text-body);
  padding: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-x: auto;
  margin-bottom: 10px;
}

.kc-viz-highlights {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.kc-highlight-tag {
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: var(--primary-light);
  color: var(--primary);
}

/* 对比表格（横向滚动） */
.kc-comparison-table-section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-normal);
  margin-bottom: 16px;
}

.kc-section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.kc-section-title-sm {
  margin-bottom: 10px;
  font-size: 15px;
}

.kc-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: var(--radius-md);
}

.kc-comparison-table {
  width: 100%;
  min-width: 460px;
  border-collapse: collapse;
  overflow: hidden;
  border-radius: var(--radius-md);
  box-shadow: 0 2px 12px var(--shadow-color);
}

.kc-comparison-table thead {
  background: var(--grad-primary);
  color: var(--btn-text);
}

.kc-comparison-table th {
  padding: 12px 14px;
  text-align: left;
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}

.kc-comparison-table th:first-child {
  width: 26%;
}

.kc-comparison-table th.kp-a {
  background: var(--pass);
}

.kc-comparison-table th.kp-b {
  background: var(--coming);
}

.kc-comparison-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-body);
  line-height: 1.6;
  vertical-align: top;
  word-break: break-word;
}

.kc-comparison-table td.kc-dimension {
  font-weight: 600;
  color: var(--text-title);
  background: var(--bg-hover);
  white-space: nowrap;
}

.kc-comparison-table tbody tr:last-child td {
  border-bottom: none;
}

/* 关键区别（单列） */
.kc-key-differences {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-normal);
  margin-bottom: 16px;
}

.kc-differences-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kc-difference-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  background: var(--primary-light);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary);
}

.kc-difference-icon {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  background: var(--primary);
  color: var(--btn-text);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.kc-difference-text {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.6;
}

/* 总结 */
.kc-summary-section {
  background: var(--primary-light);
  border: 1px solid var(--primary-fade);
  border-radius: var(--radius-md);
  padding: 16px;
}

.kc-summary-text {
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.8;
}

/* 触摸拖拽跟随浮层 */
.kc-touch-clone {
  position: fixed;
  z-index: 9999;
  pointer-events: none;
  transform: translate(-50%, -130%);
  padding: 8px 14px;
  border-radius: var(--radius-md);
  background: var(--grad-primary);
  color: var(--btn-text);
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow-brand);
  max-width: 60vw;
  word-break: break-all;
  white-space: nowrap;
}

/* 加载遮罩 */
.kc-loading-overlay {
  position: fixed;
  inset: 0;
  background: var(--bgc-dark);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.kc-loading-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 32px 28px;
  text-align: center;
  box-shadow: var(--shadow-normal);
  width: 100%;
  max-width: 280px;
}

.kc-loading-spinner {
  width: 44px;
  height: 44px;
  border: 4px solid var(--primary-fade);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: kc-spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

@keyframes kc-spin {
  to { transform: rotate(360deg); }
}

.kc-loading-text {
  font-size: 15px;
  color: var(--text-title);
  font-weight: 500;
}

.kc-loading-sub {
  font-size: 12px;
  color: var(--text-gray);
  margin-top: 6px;
}
</style>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getKnowledgeListApi,
  addCustomKnowledgeApi,
  removeCustomKnowledgeApi,
  getRecommendationsApi,
  compareKnowledgeApi
} from '@/api/mainApi/resourceKnowledgeComparison.js'

// =================== 用户信息 ===================
const userId = ref('')

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

// 装饰光点
const sparkles = ref(
  Array.from({ length: 20 }, () => ({
    left: Math.random() * 100 + '%',
    top: Math.random() * 100 + '%',
    size: 1 + Math.random() * 2 + 'px',
    duration: 8 + Math.random() * 12 + 's',
    delay: Math.random() * 10 + 's',
    opacity: 0.2 + Math.random() * 0.3
  }))
)

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

// =================== 拖拽 ===================
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
  const name = draggedName.value
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

// =================== 点击选择 ===================
function selectKnowledge(name) {
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
  if (slot === 'a') selectedA.value = null
  else selectedB.value = null
}

// =================== 推荐组合点击 ===================
function applyRecommendation(rec) {
  selectedA.value = rec.knowledge_a
  selectedB.value = rec.knowledge_b
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
</script>

<template>
  <div class="kc-container">
    <!-- 装饰光斑 -->
    <div class="kc-blob"></div>
    <div
      v-for="(sp, i) in sparkles"
      :key="i"
      class="kc-sparkle"
      :style="{
        left: sp.left,
        top: sp.top,
        width: sp.size,
        height: sp.size,
        animationDuration: sp.duration,
        animationDelay: sp.delay,
        opacity: sp.opacity
      }"
    ></div>

    <div class="kc-content">
      <!-- Header -->
      <div class="title">
        <h1><el-icon class="header-icon"><Reading /></el-icon> 知识点智能对比</h1>
        <p class="subtitle">拖拽知识点到中央区域，或点击选择，一键对比差异</p>
      </div>

      <!-- 视图切换 -->
      <div class="kc-view-toggle">
        <button :class="{ active: currentView === 'select' }" @click="switchView('select')">
          <el-icon><Reading /></el-icon> 知识点选择
        </button>
        <button :class="{ active: currentView === 'result' }" @click="switchView('result')">
          <el-icon><TrendCharts /></el-icon> 对比结果
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

          <!-- 拖拽区域 -->
          <div class="kc-drop-zone-container">
            <div
              class="kc-drop-slot"
              :class="{
                'filled-a': selectedA,
                'drag-over-a': dragOverSlot === 'a'
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
              <div class="kc-slot-hint">将知识点拖到此处</div>
              <button
                v-if="selectedA"
                class="kc-clear-btn"
                @click.stop="clearSlot('a')"
              >×</button>
            </div>

            <div class="kc-compare-arrow">VS</div>

            <div
              class="kc-drop-slot"
              :class="{
                'filled-b': selectedB,
                'drag-over-b': dragOverSlot === 'b'
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
              <div class="kc-slot-hint">将知识点拖到此处</div>
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

          <!-- 搜索 -->
          <div class="kc-search-box">
            <el-icon class="kc-search-icon"><Search /></el-icon>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索知识点..."
            />
          </div>

          <!-- 知识图谱 -->
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
            <div class="kc-rec-title"><el-icon><Bulb /></el-icon> 推荐对比组合</div>
            <div class="kc-rec-list">
              <div
                v-for="(rec, ri) in recommendations"
                :key="ri"
                class="kc-rec-item"
                @click="applyRecommendation(rec)"
              >
                <div class="kc-rec-pair">
                  {{ rec.knowledge_a }} <span class="kc-vs">VS</span> {{ rec.knowledge_b }}
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
            <el-icon><ArrowLeft /></el-icon> 返回重新选择知识点
          </button>

          <div class="kc-result-header">
            <div class="kc-result-title">
              <span class="kp-a">{{ comparisonResult.knowledge_point_a }}</span>
              <span class="kc-vs">VS</span>
              <span class="kp-b">{{ comparisonResult.knowledge_point_b }}</span>
            </div>
            <div class="kc-result-subtitle">{{ resultComparison.summary || '' }}</div>
          </div>

          <!-- 可视化 -->
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

          <!-- 对比表格 -->
          <div class="kc-comparison-table-section">
            <div class="kc-section-title"><el-icon><TrendCharts /></el-icon> 多维度对比分析</div>
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
            <div class="kc-section-title" style="margin-bottom: 10px;"><el-icon><Document /></el-icon> 总结</div>
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
.kc-container {
  position: relative;
  min-height: 100vh;
  background: transparent;
  overflow: hidden;
}

/* 装饰光斑 */
.kc-blob {
  position: fixed;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.12;
  z-index: 0;
  pointer-events: none;
  background: var(--primary);
  top: -100px;
  left: -100px;
  animation: kc-float-bg 20s ease-in-out infinite;
}

@keyframes kc-float-bg {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(40px, 60px) scale(1.1); }
}

.kc-sparkle {
  position: fixed;
  pointer-events: none;
  z-index: 0;
  border-radius: 50%;
  background: var(--bgc-mid);
  animation: kc-sparkle-float linear infinite;
}

@keyframes kc-sparkle-float {
  0% { transform: translateY(0) scale(0); opacity: 0; }
  20% { opacity: 1; }
  80% { opacity: 1; }
  100% { transform: translateY(-100vh) scale(1); opacity: 0; }
}

.kc-content {
  position: relative;
  z-index: 2;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px;
}

/* Header */
.title {
  text-align: center;
  margin-bottom: 20px;
}
.title h1 {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
  color: var(--text-title);
  /* icon与文字对齐 */
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.subtitle {
  font-size: 14px;
  color: var(--text-gray);
}

/* 用户ID */
.kc-user-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.kc-user-bar label {
  color: var(--text-gray);
  font-size: 13px;
}

.kc-user-bar input {
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: 8px;
  color: var(--text-title);
  font-size: 13px;
  width: 160px;
  outline: none;
  transition: border-color 0.3s;
}

.kc-user-bar input:focus {
  border-color: var(--primary);
}

/* 视图切换 */
.kc-view-toggle {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 20px;
}

.kc-view-toggle button {
  padding: 10px 24px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-gray);
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.kc-view-toggle button:hover {
  background: var(--bg-hover);
  color: var(--text-title);
}

.kc-view-toggle button.active {
  background: var(--grad-primary);
  color: #fff;
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
  border-radius: 20px;
  padding: 28px;
  box-shadow: var(--shadow-normal);
}

.kc-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.kc-selector-title {
  color: var(--text-title);
  font-size: 18px;
  font-weight: 600;
}

.kc-selected-info {
  color: var(--text-gray);
  font-size: 14px;
}

.kc-selected-highlight {
  color: var(--purple-text);
  font-weight: 600;
}

/* 拖拽区域 */
.kc-drop-zone-container {
  display: flex;
  gap: 16px;
  align-items: stretch;
  margin-bottom: 24px;
}

.kc-drop-slot {
  flex: 1;
  min-height: 120px;
  padding: 20px;
  border-radius: 14px;
  border: 2px dashed var(--border-color);
  background: var(--bgc-transparent);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  position: relative;
}

.kc-drop-slot:hover {
  border-color: var(--text-gray);
  background: var(--bg-hover);
}

.kc-drop-slot.drag-over-a {
  border-color: var(--pass);
  background: var(--pass-bg-color);
  transform: scale(1.03);
}

.kc-drop-slot.drag-over-b {
  border-color: var(--coming);
  background: var(--coming-bg-color);
  transform: scale(1.03);
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
  font-size: 12px;
  color: var(--text-gray);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.kc-slot-badge {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 8px;
  background: var(--bgc-mid);
  color: var(--text-gray);
}

.kc-drop-slot.filled-a .kc-slot-badge {
  background: var(--pass);
  color: #fff;
}

.kc-drop-slot.filled-b .kc-slot-badge {
  background: var(--coming);
  color: #fff;
}

.kc-slot-value {
  font-size: 18px;
  color: var(--text-title);
  font-weight: 600;
}

.kc-slot-placeholder {
  font-size: 14px;
  color: var(--text-gray);
  font-weight: normal;
}

.kc-slot-hint {
  font-size: 11px;
  color: var(--text-gray);
  opacity: 0.7;
  margin-top: 6px;
}

.kc-clear-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--bgc-mid);
  border: none;
  color: var(--text-title);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.kc-clear-btn:hover {
  background: var(--main-delete);
  color: #fff;
}

.kc-compare-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: var(--purple-text);
  font-weight: 700;
  min-width: 50px;
  animation: kc-bounce 2s infinite;
}

@keyframes kc-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

/* 对比按钮 */
.kc-compare-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 16px;
  border: none;
  border-radius: 12px;
  background: var(--grad-primary);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 8px;
}

.kc-compare-btn:hover:not(:disabled) {
  transform: translateY(-2px);
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
  gap: 10px;
  margin-top: 28px;
  margin-bottom: 20px;
  align-items: center;
}

.kc-add-custom-bar input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: 10px;
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

.kc-add-custom-bar select {
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: 10px;
  color: var(--text-title);
  font-size: 14px;
  outline: none;
  cursor: pointer;
}

.kc-add-custom-bar select option {
  background: var(--bg-card);
  color: var(--text-title);
}

.kc-add-custom-bar button {
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  background: var(--pass);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 6px;
}

.kc-add-custom-bar button:hover {
  background: var(--pass-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--pass-shadow);
}

/* 搜索 */
.kc-search-box {
  position: relative;
  margin-bottom: 20px;
}

.kc-search-box input {
  width: 100%;
  padding: 12px 16px 12px 44px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: 10px;
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
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-gray);
  font-size: 16px;
  z-index: 1;
}

/* 知识图谱 */
.kc-knowledge-graph {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
  margin-top: 12px;
}

.kc-knowledge-node {
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--bg-hover);
  border: 1px solid var(--border-color);
  cursor: grab;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: center;
  position: relative;
  overflow: hidden;
  user-select: none;
}

.kc-knowledge-node:active {
  cursor: grabbing;
}

.kc-knowledge-node:hover {
  transform: translateY(-4px);
  border-color: var(--primary);
  box-shadow: var(--shadow-brand);
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
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  position: relative;
  z-index: 1;
}

.kc-node-cat {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 4px;
  position: relative;
  z-index: 1;
}

.kc-node-drag-icon {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 10px;
  color: var(--text-gray);
  opacity: 0.4;
  z-index: 1;
}

.kc-node-del {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--main-fail-status);
  border: none;
  color: var(--main-delete);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.kc-node-del:hover {
  background: var(--main-fail-status-hover);
}

/* 分类组 */
.kc-category-group {
  margin-top: 24px;
}

.kc-category-title {
  color: var(--text-gray);
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  padding-left: 4px;
  border-left: 3px solid var(--primary);
}

.kc-custom-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  background: var(--pass-bg-color);
  color: var(--pass);
  margin-left: 8px;
}

/* 推荐 */
.kc-recommendations {
  margin-top: 32px;
  padding: 20px;
  background: var(--bgc-transparent);
  border-radius: 16px;
  border: 1px solid var(--border-color);
}

.kc-rec-title {
  color: var(--text-body);
  font-size: 14px;
  margin-bottom: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.kc-rec-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.kc-rec-item {
  padding: 12px 16px;
  border-radius: 10px;
  background: var(--bg-hover);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.25s;
}

.kc-rec-item:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  transform: translateX(3px);
}

.kc-rec-pair {
  font-size: 14px;
  color: var(--text-title);
  font-weight: 500;
}

.kc-rec-pair .kc-vs {
  color: var(--purple-text);
  margin: 0 6px;
}

.kc-vs {
  color: var(--text-gray);
  margin: 0 12px;
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
  border-radius: 20px;
  padding: 24px 32px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-normal);
}

.kc-result-title {
  text-align: center;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 4px;
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
  font-size: 14px;
}

.kc-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  border-radius: 8px;
  color: var(--text-gray);
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 16px;
  transition: all 0.25s;
}

.kc-back-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.kc-empty-result {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-gray);
}

.kc-empty-result p {
  margin-bottom: 16px;
  font-size: 15px;
}

/* 可视化区域 */
.kc-visualization-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.kc-viz-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 20px;
  box-shadow: var(--shadow-normal);
}

.kc-viz-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.kc-viz-badge {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 14px;
}

.kc-viz-badge.a {
  background: var(--pass);
}

.kc-viz-badge.b {
  background: var(--coming);
}

.kc-viz-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

.kc-viz-desc {
  font-size: 13px;
  color: var(--text-gray);
  margin-bottom: 12px;
  line-height: 1.6;
}

.kc-viz-diagram {
  background: var(--bg-page);
  color: var(--text-body);
  padding: 16px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-x: auto;
  margin-bottom: 12px;
}

.kc-viz-highlights {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.kc-highlight-tag {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  background: var(--primary-light);
  color: var(--primary);
}

/* 对比表格 */
.kc-comparison-table-section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 28px;
  box-shadow: var(--shadow-normal);
  margin-bottom: 24px;
}

.kc-section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.kc-comparison-table {
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  border-radius: 12px;
  box-shadow: 0 2px 12px var(--shadow-color);
}

.kc-comparison-table thead {
  background: var(--grad-primary);
  color: #fff;
}

.kc-comparison-table th {
  padding: 14px 20px;
  text-align: left;
  font-weight: 600;
  font-size: 14px;
}

.kc-comparison-table th:first-child {
  width: 25%;
}

.kc-comparison-table th.kp-a {
  background: var(--pass);
}

.kc-comparison-table th.kp-b {
  background: var(--coming);
}

.kc-comparison-table td {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  color: var(--text-body);
  line-height: 1.6;
}

.kc-comparison-table td.kc-dimension {
  font-weight: 600;
  color: var(--text-title);
  background: var(--bg-hover);
}

.kc-comparison-table tbody tr:hover {
  background: var(--bg-hover);
}

.kc-comparison-table tbody tr:last-child td {
  border-bottom: none;
}

/* 关键区别 */
.kc-key-differences {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 28px;
  box-shadow: var(--shadow-normal);
  margin-bottom: 24px;
}

.kc-differences-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.kc-difference-item {
  display: flex;
  gap: 12px;
  padding: 14px;
  background: var(--primary-light);
  border-radius: 10px;
  border-left: 3px solid var(--primary);
}

.kc-difference-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  background: var(--primary);
  color: #fff;
  border-radius: 6px;
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
  border-radius: 16px;
  padding: 20px 24px;
}

.kc-summary-text {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.8;
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
  z-index: 3;
}

.kc-loading-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 40px 48px;
  text-align: center;
  box-shadow: var(--shadow-normal);
}

.kc-loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--primary-fade);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: kc-spin 0.8s linear infinite;
  margin: 0 auto 20px;
}

@keyframes kc-spin {
  to { transform: rotate(360deg); }
}

.kc-loading-text {
  font-size: 16px;
  color: var(--text-title);
  font-weight: 500;
}

.kc-loading-sub {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 6px;
}

/* 响应式 */
@media (max-width: 768px) {
  .kc-visualization-section {
    grid-template-columns: 1fr;
  }

  .kc-drop-zone-container {
    flex-direction: column;
  }

  .kc-compare-arrow {
    transform: rotate(90deg);
  }

  .kc-comparison-table th,
  .kc-comparison-table td {
    padding: 10px 12px;
    font-size: 12px;
  }

  .kc-knowledge-graph {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  }

  .kc-add-custom-bar {
    flex-wrap: wrap;
  }

  .kc-add-custom-bar input {
    flex: 1 1 100%;
  }
}
</style>

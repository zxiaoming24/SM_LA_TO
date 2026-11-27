<!-- 知识图谱 -->
<template>
  <Teleport to="body">
    <div v-if="visible" class="km-overlay">
      <div class="km-modal">
        <!-- 生成学习计划加载遮罩 -->
        <div v-if="isGeneratingPlan" class="km-plan-overlay">
          <div class="km-plan-loading-card">
            <div class="km-ml-spinner"></div>
            <div class="km-ml-text">正在生成学习计划...</div>
            <div class="km-ml-sub">AI 正在分析知识点并制定学习路径</div>
          </div>
        </div>
        <!-- 生成学习计划结果弹窗 -->
        <div v-if="planResult.show" class="km-plan-result-overlay" @click="closePlanResult">
          <div class="km-plan-result-card" :class="planResult.type" @click.stop>
            <div class="km-plan-result-icon">{{ planResult.type === 'success' ? '✓' : '✕' }}</div>
            <div class="km-plan-result-msg">{{ planResult.message }}</div>
            <button class="km-plan-result-btn" @click="closePlanResult">确定</button>
          </div>
        </div>
        <!-- 删除确认弹窗 -->
        <div v-if="deleteConfirm.show" class="km-delete-confirm-overlay" @click="cancelDelete">
          <div class="km-delete-confirm-card" @click.stop>
            <div class="km-delete-confirm-icon">⚠</div>
            <div class="km-delete-confirm-title">删除确认</div>
            <div class="km-delete-confirm-msg">确定删除这个知识图谱吗？</div>
            <div class="km-delete-confirm-btns">
              <button class="km-delete-cancel-btn" @click="cancelDelete">取消</button>
              <button class="km-delete-confirm-btn" @click="confirmDelete">确定</button>
            </div>
          </div>
        </div>
        <!-- 顶部 -->
        <div class="km-header">
          <div class="km-title">
            <span><svg t="1784965730799" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6943" id="mx_n_1784965730800" width="25" height="25"><path d="M870.4 711.111111c-28.444444 0-56.888889 8.533333-79.644444 22.755556l-162.133334-156.444445c25.6-34.133333 42.666667-76.8 42.666667-122.311111 0-42.666667-14.222222-82.488889-36.977778-113.777778l93.866667-99.555555c17.066667 8.533333 36.977778 17.066667 56.888889 17.066666 62.577778 0 113.777778-51.2 113.777777-113.777777s-51.2-113.777778-113.777777-113.777778-113.777778 51.2-113.777778 113.777778c0 22.755556 5.688889 39.822222 17.066667 56.888889l-93.866667 99.555555c-31.288889-28.444444-73.955556-45.511111-122.311111-45.511111-48.355556 0-93.866667 17.066667-130.844445 48.355556L258.844444 227.555556c8.533333-17.066667 14.222222-36.977778 14.222223-56.888889 0-62.577778-51.2-113.777778-113.777778-113.777778s-113.777778 51.2-113.777778 113.777778 51.2 113.777778 113.777778 113.777777c22.755556 0 42.666667-5.688889 59.733333-17.066666l88.177778 79.644444c-22.755556 31.288889-34.133333 68.266667-34.133333 108.088889 0 51.2 19.911111 96.711111 51.2 130.844445l-59.733334 62.577777c-22.755556-14.222222-48.355556-22.755556-76.8-22.755555-79.644444 0-142.222222 62.577778-142.222222 142.222222s62.577778 142.222222 142.222222 142.222222 142.222222-62.577778 142.222223-142.222222c0-28.444444-8.533333-56.888889-25.6-79.644444l59.733333-65.422223c31.288889 19.911111 68.266667 31.288889 105.244444 31.288889 42.666667 0 82.488889-14.222222 113.777778-36.977778l164.977778 156.444445c-11.377778 22.755556-19.911111 51.2-19.911111 79.644444 0 79.644444 62.577778 142.222222 142.222222 142.222223s142.222222-62.577778 142.222222-142.222223-62.577778-142.222222-142.222222-142.222222z m-85.333333-625.777778c31.288889 0 56.888889 25.6 56.888889 56.888889s-25.6 56.888889-56.888889 56.888889-56.888889-25.6-56.888889-56.888889 25.6-56.888889 56.888889-56.888889z m-682.666667 85.333334c0-31.288889 25.6-56.888889 56.888889-56.888889s56.888889 25.6 56.888889 56.888889-25.6 56.888889-56.888889 56.888889-56.888889-25.6-56.888889-56.888889z m85.333333 682.666666c-48.355556 0-85.333333-36.977778-85.333333-85.333333s36.977778-85.333333 85.333333-85.333333c14.222222 0 25.6 2.844444 36.977778 8.533333l39.822222 36.977778c5.688889 11.377778 8.533333 25.6 8.533334 39.822222 0 48.355556-36.977778 85.333333-85.333334 85.333333z m284.444445-256c-79.644444 0-142.222222-62.577778-142.222222-142.222222s62.577778-142.222222 142.222222-142.222222 142.222222 62.577778 142.222222 142.222222-62.577778 142.222222-142.222222 142.222222z m398.222222 341.333334c-48.355556 0-85.333333-36.977778-85.333333-85.333334s36.977778-85.333333 85.333333-85.333333 85.333333 36.977778 85.333333 85.333333-36.977778 85.333333-85.333333 85.333334z" p-id="6944" fill="#ffffff"></path></svg> 知识图谱</span>
            <span class="km-subtitle">上传文档，AI自动提取知识点与关系</span>
          </div>
          <button class="km-close-btn" @click="close">×</button>
        </div>

        <!-- 主体 -->
        <div class="km-main">
          <!-- 左侧面板 -->
          <div class="km-left">
            <div class="km-upload-area">
              <div class="km-upload-zone" :class="{ dragover: isDragover, uploading: isUploading }"
                   @click="triggerFileInput" @dragover.prevent="isDragover = true"
                   @dragleave="isDragover = false" @drop.prevent="handleDrop">
                <div class="km-upload-icon"><svg t="1784966235838" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="6626" width="45" height="45"><path d="M752 80H272c-70.4 0-128 57.6-128 128v608c0 70.4 57.6 128 128 128h353.6c33.6 0 65.6-12.8 91.2-36.8l126.4-126.4c24-24 36.8-56 36.8-91.2V208c0-70.4-57.6-128-128-128zM208 816V208c0-35.2 28.8-64 64-64h480c35.2 0 64 28.8 64 64v464h-96c-70.4 0-128 57.6-128 128v80H272c-35.2 0-64-28.8-64-64z m462.4 44.8c-4.8 4.8-9.6 8-14.4 11.2V800c0-35.2 28.8-64 64-64h75.2l-124.8 124.8z" fill="#ffffff" p-id="6627"></path><path d="M368 352h288c17.6 0 32-14.4 32-32s-14.4-32-32-32H368c-17.6 0-32 14.4-32 32s14.4 32 32 32zM496 608h-128c-17.6 0-32 14.4-32 32s14.4 32 32 32h128c17.6 0 32-14.4 32-32s-14.4-32-32-32zM368 512h288c17.6 0 32-14.4 32-32s-14.4-32-32-32H368c-17.6 0-32 14.4-32 32s14.4 32 32 32z" fill="#ffffff" p-id="6628"></path></svg></div>
                <div class="km-upload-text">点击或拖拽文档到此处</div>
                <div class="km-upload-hint">支持 PDF / Word / Markdown / TXT / XMind</div>
              </div>
              <div v-if="isUploading" class="km-upload-progress">
                <div class="km-progress-bar"><div class="km-progress-fill" :style="{ width: uploadProgress + '%' }"></div></div>
                <div class="km-progress-text">{{ uploadProgressText }}</div>
              </div>
              <input ref="fileInputRef" type="file" accept=".pdf,.md,.doc,.docx,.txt,.xmind" style="display:none" @change="handleFileSelect" />
            </div>

            <div class="km-graph-list">
              <div class="km-list-title">📚 已生成的图谱</div>
              <!-- 合并栏 -->
              <div v-if="graphs.length >= 2" class="km-merge-bar">
                <span class="km-merge-count">已选 {{ selectedMergeIds.size }} 个</span>
                <button class="km-merge-btn" :disabled="selectedMergeIds.size < 2" :class="{ loading: isMerging }" @click="doMerge">
                  <span v-if="isMerging" class="km-btn-spinner"></span>
                  {{ isMerging ? '合并中...' : '🔄 合并选中' }}
                </button>
              </div>
              <!-- 空提示 -->
              <div v-if="graphs.length === 0" class="km-empty-hint">暂无图谱，请上传文档生成</div>
              <!-- 图谱列表 -->
              <div v-for="g in graphs" :key="g.graph_id" class="km-graph-item" :class="{ active: g.graph_id === currentGraphId }">
                <input type="checkbox" class="km-item-check" :checked="selectedMergeIds.has(g.graph_id)" @change="toggleMergeSelect(g.graph_id, $event)" />
                <div class="km-item-body" @click="selectGraph(g.graph_id)">
                  <div class="km-item-title">{{ g.title || g.source_file }}</div>
                  <div class="km-item-meta">
                    <span>📄 {{ g.source_file }}</span>
                    <span>🔗 {{ g.node_count }}节点 / {{ g.edge_count }}边</span>
                    <span class="km-item-del" @click.stop="deleteGraph(g.graph_id)" title="删除">&times;</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 右侧图谱面板 -->
          <div class="km-graph-panel">
            <!-- 合并加载遮罩 -->
            <div v-if="isMerging" class="km-merge-overlay">
              <div class="km-merge-loading-card">
                <div class="km-ml-spinner"></div>
                <div class="km-ml-text">正在合并图谱...</div>
                <div class="km-ml-sub">LLM 正在分析知识点并进行智能融合</div>
              </div>
            </div>
            <!-- 空状态 -->
            <div v-if="!currentGraphId && !isLoadingGraph" class="km-graph-empty-state">
              <div class="km-big-icon">🧠</div>
              <div class="km-text">选择一个图谱或上传文档</div>
              <div class="km-sub">AI将从文档中自动提取知识点与关系</div>
            </div>
            <!-- 加载中 -->
            <div v-if="isLoadingGraph" class="km-canvas-loading">
              <div class="km-spinner"></div>
              <div class="km-loading-text">加载图谱数据...</div>
            </div>
            <!-- 图谱容器 -->
            <div ref="graphCanvasRef" class="km-graph-canvas"></div>
            <!-- 节点详情面板 -->
            <div v-if="detailVisible" class="km-detail-panel">
              <!-- <button class="km-detail-close" @click="closeDetail">×</button> -->
              <div class="km-node-name">{{ detailNode.name || '' }}</div>
              <div class="km-node-cat" :class="getCatClass(detailNode.category)">{{ detailNode.category || '未分类' }}</div>
              <div class="km-mastery-badge" :class="`km-mastery-${detailNode.mastery_level || 0}`">
                <span class="km-mastery-dot" :class="`km-mastery-dot-${detailNode.mastery_level || 0}`"></span>
                {{ getMasteryLabel(detailNode.mastery_level) }} (Lv.{{ detailNode.mastery_level || 0 }})
              </div>
              <div class="km-node-desc">{{ detailNode.description || '暂无描述' }}</div>
              <div v-if="detailRels.length > 0" class="km-node-rels">
                <div class="km-rel-title">🔗 关联知识点</div>
                <div v-for="(r, i) in detailRels" :key="i" class="km-rel-item">{{ r.arrow }} {{ r.relation }} → {{ r.otherName }}</div>
              </div>
              <button class="km-btn-plan" :disabled="detailNode._extra" @click="generateStudyPlan">
                {{ detailNode._extra ? '🗺 该知识点不在当前文档中' : '🗺 生成学习计划' }}
              </button>
            </div>
            <!-- 布局切换 -->
            <div class="km-layout-toggle" @click="toggleLayout" title="切换布局模式">
              <span class="km-toggle-icon">{{ isHierarchical ? '⊞' : '⊟' }}</span>
              <span class="km-toggle-label">{{ isHierarchical ? '层级' : '自由' }}</span>
            </div>
            <!-- 掌握度图例 -->
            <div class="km-mastery-legend">
              <div class="km-legend-title">掌握度</div>
              <div class="km-legend-item"><span class="km-legend-dot" style="background:#ccc"></span>未接触</div>
              <div class="km-legend-item"><span class="km-legend-dot" style="background:#4caf50"></span>已了解</div>
              <div class="km-legend-item"><span class="km-legend-dot" style="background:#2196f3"></span>已理解</div>
              <div class="km-legend-item"><span class="km-legend-dot" style="background:#ff9800"></span>已应用</div>
              <div class="km-legend-item"><span class="km-legend-dot" style="background:#f44336"></span>已掌握</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Network, DataSet } from 'vis-network/standalone'
import {
  listGraphsApi,
  uploadGraphApi,
  getEnrichedGraphApi,
  deleteGraphApi,
  mergeGraphsApi,
  generateStudyPlanApi
} from '@/api/mainApi/KnowledgeMap.js'

// ==================== Props ====================
const props = defineProps({
  visible: { type: Boolean, default: false },
  userId: { type: String, required: true }
})

const emit = defineEmits(['close'])

// ==================== State ====================
const fileInputRef = ref(null)
const graphCanvasRef = ref(null)

const graphs = ref([])
const currentGraphId = ref(null)
const selectedMergeIds = ref(new Set())

const isDragover = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const uploadProgressText = ref('')
const isLoadingGraph = ref(false)
const isMerging = ref(false)
const isGeneratingPlan = ref(false)
const planResult = ref({ show: false, type: '', message: '' })
const deleteConfirm = ref({ show: false, graphId: '' })

const detailVisible = ref(false)
const detailNode = ref({})
const detailRels = ref([])

const isHierarchical = ref(true)

let network = null
let nodesDataSet = null
let edgesDataSet = null
let allNodes = []
let allEdges = []

// ==================== Watch ====================
watch(() => props.visible, (val) => {
  if (val) {
    document.body.style.overflow = 'hidden'
    loadGraphs()
  } else {
    document.body.style.overflow = ''
    clearGraph()
  }
})

// ==================== Methods ====================
function close() {
  emit('close')
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileSelect(e) {
  if (e.target.files.length) uploadFile(e.target.files[0])
}

function handleDrop(e) {
  isDragover.value = false
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0])
}

async function uploadFile(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  const supported = ['.pdf', '.md', '.doc', '.docx', '.txt', '.xmind']
  if (!supported.includes(ext)) {
    ElMessage.error('不支持的文件格式')
    return
  }

  isUploading.value = true
  uploadProgress.value = 0
  uploadProgressText.value = '正在上传...'

  const formData = new FormData()
  formData.append('file', file)

  try {
    // 模拟进度
    const pi = setInterval(() => {
      uploadProgress.value = Math.min(uploadProgress.value + 5, 60)
    }, 200)

    await uploadGraphApi(props.userId, formData)
    clearInterval(pi)
    uploadProgress.value = 100
    uploadProgressText.value = '✅ 生成完成！'
    ElMessage.success('知识图谱生成成功！')

    await loadGraphs()
    if (graphs.value.length > 0) {
      selectGraph(graphs.value[0].graph_id)
    }

    setTimeout(() => {
      isUploading.value = false
      uploadProgress.value = 0
    }, 1500)
  } catch (e) {
    isUploading.value = false
    uploadProgress.value = 0
    ElMessage.error(e.message || '生成失败')
  }
}

async function loadGraphs() {
  try {
    const res = await listGraphsApi(props.userId)
    graphs.value = res.success ? res.data : []
    // 清理已不存在的选中项
    const currentIds = new Set(graphs.value.map(g => g.graph_id))
    for (const id of selectedMergeIds.value) {
      if (!currentIds.has(id)) selectedMergeIds.value.delete(id)
    }
  } catch (e) {
    ElMessage.error('加载图谱列表失败')
  }
}

function toggleMergeSelect(graphId, event) {
  if (event.target.checked) {
    selectedMergeIds.value.add(graphId)
  } else {
    selectedMergeIds.value.delete(graphId)
  }
  // 触发响应式更新
  selectedMergeIds.value = new Set(selectedMergeIds.value)
}

async function doMerge() {
  const ids = [...selectedMergeIds.value]
  if (ids.length < 2) {
    ElMessage.error('请至少选择2个图谱')
    return
  }

  isMerging.value = true
  try {
    const res = await mergeGraphsApi(props.userId, ids)
    ElMessage.success('合并成功！')
    selectedMergeIds.value = new Set()
    await loadGraphs()
    if (res.data && res.data.graph_id) {
      selectGraph(res.data.graph_id)
    }
  } catch (e) {
    ElMessage.error('合并失败: ' + (e.message || '未知错误'))
  } finally {
    isMerging.value = false
  }
}

function deleteGraph(graphId) {
  deleteConfirm.value = { show: true, graphId }
}

async function confirmDelete() {
  const graphId = deleteConfirm.value.graphId
  deleteConfirm.value = { show: false, graphId: '' }
  try {
    await deleteGraphApi(props.userId, graphId)
    ElMessage.info('已删除')
    if (currentGraphId.value === graphId) {
      currentGraphId.value = null
      clearGraph()
    }
    await loadGraphs()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

function cancelDelete() {
  deleteConfirm.value = { show: false, graphId: '' }
}

async function selectGraph(graphId) {
  currentGraphId.value = graphId
  isLoadingGraph.value = true

  try {
    const res = await getEnrichedGraphApi(props.userId, graphId)
    if (!res.success || !res.data) throw new Error('加载失败')
    isLoadingGraph.value = false
    await nextTick()
    renderGraph(res.data)
  } catch (e) {
    ElMessage.error('加载图谱数据失败')
    isLoadingGraph.value = false
  }
}

function renderGraph(graphData) {
  const nodes = graphData.nodes || []
  const edges = graphData.edges || []
  allNodes = nodes
  allEdges = edges

  if (nodes.length === 0) {
    clearGraph()
    return
  }

  const masteryColors = {
    0: { bg: 'rgba(255,255,255,0.08)', border: 'rgba(255,255,255,0.2)', text: 'rgba(255,255,255,0.75)', glow: 'rgba(255,255,255,0)' },
    1: { bg: 'rgba(46,204,113,0.15)', border: '#2ecc71', text: '#2ecc71', glow: 'rgba(46,204,113,0.3)' },
    2: { bg: 'rgba(52,152,219,0.15)', border: '#3498db', text: '#3498db', glow: 'rgba(52,152,219,0.3)' },
    3: { bg: 'rgba(243,156,18,0.15)', border: '#f39c12', text: '#f39c12', glow: 'rgba(243,156,18,0.3)' },
    4: { bg: 'rgba(231,76,60,0.15)', border: '#e74c3c', text: '#e74c3c', glow: 'rgba(231,76,60,0.3)' },
  }

  const visNodes = nodes.map(n => {
    const level = n.mastery_level !== undefined ? n.mastery_level : 0
    const mc = masteryColors[level] || masteryColors[0]
    const isExtra = n._extra
    const baseSize = nodes.length > 30 ? 18 : nodes.length > 15 ? 22 : 26
    const size = isExtra ? baseSize * 0.6 : baseSize

    return {
      id: n.id,
      label: n.name,
      title: `${n.name}\n${n.category || '未分类'} · ${n.mastery_label || '未接触'}\n${n.description || ''}`,
      color: {
        background: mc.bg,
        border: mc.border,
        highlight: { background: 'rgba(102,126,234,0.2)', border: '#667eea' },
      },
      font: {
        color: mc.text,
        size: nodes.length > 20 ? 11 : 13,
        face: 'Microsoft YaHei, PingFang SC, sans-serif',
        strokeWidth: nodes.length > 20 ? 0 : 2,
        strokeColor: 'rgba(15,12,41,0.6)',
        bold: true,
      },
      borderWidth: isExtra ? 1 : 2.5,
      borderWidthSelected: 4,
      size: size,
      shape: 'box',
      widthConstraint: { maximum: nodes.length > 20 ? 100 : 140 },
      shadow: {
        enabled: true,
        color: mc.glow || 'rgba(255,255,255,0.05)',
        size: 12, x: 0, y: 0,
      },
      opacity: isExtra ? 0.5 : 1.0,
    }
  })

  const relColors = {
    '前置依赖': '#e74c3c', '包含': '#3498db', '关联': '#2ecc71',
    '举例': '#f39c12', '对比': '#9b59b6',
  }

  const visEdges = edges.map(e => {
    const relColor = relColors[e.relation] || 'rgba(255,255,255,0.25)'
    return {
      from: e.source, to: e.target,
      label: e.relation || '',
      color: { color: relColor, highlight: '#667eea', hover: '#667eea', opacity: 0.8 },
      font: {
        size: 11, color: relColor, strokeWidth: 3,
        strokeColor: 'rgba(15,12,41,0.8)', face: 'Microsoft YaHei', align: 'middle',
      },
      width: 2.5, selectionWidth: 4, hoverWidth: 3,
      smooth: { type: 'curvedCW', roundness: 0.12 },
      arrows: { to: { enabled: true, scaleFactor: 1, type: 'arrow' } },
      shadow: { enabled: true, color: 'rgba(255,255,255,0.05)', size: 6, x: 0, y: 0 },
    }
  })

  nodesDataSet = new DataSet(visNodes)
  edgesDataSet = new DataSet(visEdges)

  const options = {
    nodes: {
      borderWidth: 2.5, borderWidthSelected: 4,
      shadow: { enabled: true, size: 12 },
      shapeProperties: { borderRadius: 8 },
    },
    edges: { shadow: { enabled: true, size: 6 } },
    layout: {
      hierarchical: {
        enabled: true, direction: 'LR', sortMethod: 'directed',
        nodeSpacing: 200, levelSeparation: 320, treeSpacing: 220,
        blockShifting: true, edgeMinimization: true, parentCentralization: true,
      },
    },
    physics: { enabled: false },
    interaction: {
      hover: true, tooltipDelay: 150, navigationButtons: false,
      keyboard: true, dragNodes: true, zoomView: true,
    },
  }

  if (network) network.destroy()
  network = new Network(graphCanvasRef.value, { nodes: nodesDataSet, edges: edgesDataSet }, options)

  network.on('click', params => {
    if (params.nodes.length === 1) {
      showNodeDetail(params.nodes[0])
    } else {
      closeDetail()
    }
  })

  setTimeout(() => network.fit({ animation: true }), 300)
}

function showNodeDetail(nodeId) {
  const node = allNodes.find(n => n.id === nodeId)
  if (!node) return
  detailNode.value = node

  const rels = allEdges.filter(e => e.source === nodeId || e.target === nodeId)
  detailRels.value = rels.map(r => {
    const otherId = r.source === nodeId ? r.target : r.source
    const otherNode = allNodes.find(n => n.id === otherId)
    return {
      arrow: r.source === nodeId ? '→' : '←',
      relation: r.relation || '关联',
      otherName: otherNode ? otherNode.name : otherId
    }
  })

  detailVisible.value = true
}

function closeDetail() {
  detailVisible.value = false
  detailNode.value = {}
  detailRels.value = []
}

function clearGraph() {
  if (network) { network.destroy(); network = null }
  nodesDataSet = null
  edgesDataSet = null
  allNodes = []
  allEdges = []
  closeDetail()
}

function toggleLayout() {
  if (!network || !nodesDataSet || !edgesDataSet) return
  isHierarchical.value = !isHierarchical.value

  if (isHierarchical.value) {
    network.setOptions({
      layout: {
        hierarchical: {
          enabled: true, direction: 'LR', sortMethod: 'directed',
          nodeSpacing: 180, levelSeparation: 280, treeSpacing: 200,
          blockShifting: true, edgeMinimization: true, parentCentralization: true,
        },
      },
      physics: { enabled: false },
    })
  } else {
    network.setOptions({
      layout: { hierarchical: { enabled: false } },
      physics: {
        enabled: true, solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -40, centralGravity: 0.005,
          springLength: 200, springConstant: 0.04, damping: 0.5,
        },
        stabilization: { iterations: 150 },
      },
    })
  }
  ElMessage.info(isHierarchical.value ? '已切换为层级排列' : '已切换为自由力导向')
}

async function generateStudyPlan() {
  const node = detailNode.value
  if (!node || !node.name) return

  const kpName = node.name
  const desc = node.description ? `（${node.description}）` : ''
  const cat = node.category ? `[${node.category}]` : ''
  const relHint = detailRels.value.length > 0
    ? `，关联知识点: ${detailRels.value.slice(0, 3).map(r => r.otherName).join('、')}`
    : ''

  isGeneratingPlan.value = true

  try {
    const res = await generateStudyPlanApi(props.userId, {
      user_input: `系统地学习「${kpName}」${cat}${desc}${relHint}`,
      enable_tts: false,
      ignore_weak_points: true,
      focus_weak_points: false,
    })
    let msg = `「${kpName}」学习计划已生成！`
    if (res.weak_points_detected) {
      msg += ' 已检测到薄弱点，学习计划已针对性调整'
    }
    planResult.value = { show: true, type: 'success', message: msg }
  } catch (e) {
    planResult.value = { show: true, type: 'error', message: '生成计划失败: ' + (e.message || '未知错误') }
  } finally {
    isGeneratingPlan.value = false
  }
}

function closePlanResult() {
  planResult.value = { show: false, type: '', message: '' }
}

function getCatClass(cat) {
  const cats = ['概念', '原理', '方法', '工具', '应用']
  return cats.includes(cat) ? `km-cat-${cat}` : 'km-cat-default'
}

function getMasteryLabel(level) {
  const labels = { 0: '未接触', 1: '已了解', 2: '已理解', 3: '已应用', 4: '已掌握' }
  return labels[level] || '未知'
}

function escHtml(s) {
  if (!s) return ''
  const d = document.createElement('div')
  d.textContent = s
  return d.innerHTML
}

onBeforeUnmount(() => {
  if (network) network.destroy()
})
</script>

<style scoped>
.km-overlay {
  position: fixed; inset: 0; z-index: 20000;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}

.km-modal {
  width: 100vw; height: 100vh;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e293b 100%);
  border-radius: 0; overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: none;
}

/* Header */
.km-header {
  padding: 14px 28px; flex-shrink: 0;
  background: rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  display: flex; align-items: center; justify-content: space-between;
  color: #fff;
}
.km-title {
  font-size: 20px; font-weight: 700;
  display: flex; align-items: center; gap: 10px;
}
.km-title .icon {
  vertical-align: middle;
  flex-shrink: 0;
}
.km-title span:not(.km-subtitle) {
  background: linear-gradient(135deg, #fff, #f093fb);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  display: flex; align-items: center; gap: 8px;
}
.km-subtitle { font-size: 12px; -webkit-text-fill-color: rgba(255,255,255,0.5); }
.km-close-btn {
  background: rgba(255,255,255,0.06); border: none; font-size: 20px;
  cursor: pointer; color: rgba(255,255,255,0.5); padding: 4px 10px;
  border-radius: 8px; transition: all 0.2s;
}
.km-close-btn:hover { background: rgba(255,255,255,0.12); color: #fff; }

/* Main */
.km-main { flex: 1; display: flex; overflow: hidden; }

/* Left panel */
.km-left {
  width: 300px; min-width: 300px;
  background: rgba(255,255,255,0.05);
  border-right: 1px solid rgba(255,255,255,0.06);
  display: flex; flex-direction: column; overflow: hidden;
}

.km-upload-area { padding: 18px 16px 14px; border-bottom: 1px solid rgba(255,255,255,0.06); }
.km-upload-zone {
  border: 2px dashed rgba(255,255,255,0.15);
  border-radius: 14px; padding: 22px 16px 18px;
  text-align: center; cursor: pointer;
  transition: all 0.35s; position: relative; overflow: hidden;
}
.km-upload-zone:hover, .km-upload-zone.dragover {
  border-color: var(--primary); transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(45,125,219,0.15);
}
.km-upload-zone.uploading { pointer-events: none; opacity: 0.5; }
.km-upload-icon { font-size: 34px; margin-bottom: 6px; display: block; }
.km-upload-text { font-size: 13px; color: rgba(255,255,255,0.7); }
.km-upload-hint { font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 4px; }

.km-upload-progress { margin-top: 14px; }
.km-progress-bar { height: 4px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
.km-progress-fill {
  height: 100%; background: var(--grad-primary);
  border-radius: 4px; transition: width 0.4s;
}
.km-progress-text { font-size: 12px; color: rgba(255,255,255,0.5); margin-top: 6px; text-align: center; }

.km-graph-list { flex: 1; overflow-y: auto; padding: 12px 14px; }
.km-list-title {
  font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.4);
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;
}

.km-merge-bar {
  display: flex; align-items: center; gap: 8px; padding: 8px 0 10px;
  border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 8px;
}
.km-merge-count { font-size: 12px; color: rgba(255,255,255,0.4); flex: 1; }
.km-merge-btn {
  padding: 6px 14px; border: none; border-radius: 8px; font-size: 12px;
  font-weight: 600; cursor: pointer;
  background: var(--primary);
  color: #fff; transition: all 0.25s;
}
.km-merge-btn:hover { background: var(--primary-hv); }
.km-merge-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.km-merge-btn.loading { opacity: 0.7; cursor: wait; }
.km-btn-spinner {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid rgba(255,255,255,0.2);
  border-top-color: #fff; border-radius: 50%;
  animation: km-spin 0.6s linear infinite;
  vertical-align: middle; margin-right: 4px;
}

.km-empty-hint { text-align: center; padding: 40px 16px; color: rgba(255,255,255,0.25); font-size: 13px; }

.km-graph-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 12px; border-radius: 14px; cursor: default; margin-bottom: 8px;
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05);
  transition: all 0.25s;
}
.km-graph-item:hover { background: rgba(255,255,255,0.07); border-color: rgba(102,126,234,0.2); transform: translateX(3px); }
.km-graph-item.active { background: rgba(102,126,234,0.1); border-color: rgba(102,126,234,0.35); }
.km-item-check { width: 15px; height: 15px; cursor: pointer; accent-color: #667eea; flex-shrink: 0; margin-top: 2px; }
.km-item-body { flex: 1; min-width: 0; cursor: pointer; overflow: hidden; }
.km-item-title {
  font-size: 14px; font-weight: 500; color: rgba(255,255,255,0.85);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 4px;
}
.km-item-meta {
  font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 4px;
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
.km-item-meta span {
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 100%;
}
.km-item-del {
  margin-left: auto; color: rgba(255,255,255,0.2); cursor: pointer;
  font-size: 14px; padding: 2px 6px; border-radius: 6px; transition: all 0.2s;
}
.km-item-del:hover { color: #ff6b6b; background: rgba(255,107,107,0.12); }

/* Right panel */
.km-graph-panel {
  flex: 1; position: relative;
  background: radial-gradient(ellipse at 30% 50%, rgba(102,126,234,0.04) 0%, transparent 60%),
              radial-gradient(ellipse at 70% 50%, rgba(118,75,162,0.04) 0%, transparent 60%);
}
.km-graph-canvas { width: 100%; height: 100%; }

.km-graph-empty-state {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  text-align: center; color: rgba(255,255,255,0.3);
}
.km-big-icon { font-size: 72px; margin-bottom: 14px; display: block; animation: km-float 4s ease-in-out infinite; }
@keyframes km-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
.km-text { font-size: 16px; font-weight: 500; }
.km-sub { font-size: 12px; margin-top: 6px; opacity: 0.6; }

.km-canvas-loading {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  z-index: 5; text-align: center;
}
.km-spinner {
  width: 36px; height: 36px; border: 3px solid rgba(255,255,255,0.08);
  border-top-color: #667eea; border-radius: 50%;
  animation: km-spin 0.8s linear infinite; margin: 0 auto 10px;
}
@keyframes km-spin { to { transform: rotate(360deg); } }
.km-loading-text { font-size: 13px; color: rgba(255,255,255,0.4); }

/* Detail panel */
.km-detail-panel {
  position: absolute; right: 20px; top: 20px; width: 280px;
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px; box-shadow: 0 8px 40px rgba(0,0,0,0.3);
  padding: 18px; z-index: 10;
  animation: km-slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes km-slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.km-detail-close {
  float: right; background: rgba(255,255,255,0.06); border: none; font-size: 16px;
  cursor: pointer; color: rgba(255,255,255,0.5); padding: 4px 8px;
  border-radius: 8px; transition: all 0.2s;
}
.km-detail-close:hover { background: rgba(255,255,255,0.12); color: #fff; }
.km-node-name { font-size: 17px; font-weight: 700; color: #fff; margin-bottom: 6px; }
.km-node-cat {
  display: inline-block; padding: 2px 12px; border-radius: 10px;
  font-size: 11px; font-weight: 500; margin-bottom: 8px;
}
.km-cat-概念 { background: rgba(33,150,243,0.15); color: #64b5f6; }
.km-cat-原理 { background: rgba(244,67,54,0.15); color: #ef9a9a; }
.km-cat-方法 { background: rgba(76,175,80,0.15); color: #81c784; }
.km-cat-工具 { background: rgba(255,152,0,0.15); color: #ffb74d; }
.km-cat-应用 { background: rgba(156,39,176,0.15); color: #ce93d8; }
.km-cat-default { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.5); }

.km-mastery-badge {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px;
  border-radius: 12px; font-size: 12px; font-weight: 500; margin: 6px 0 10px;
}
.km-mastery-0 { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.4); }
.km-mastery-1 { background: rgba(76,175,80,0.15); color: #81c784; }
.km-mastery-2 { background: rgba(33,150,243,0.15); color: #64b5f6; }
.km-mastery-3 { background: rgba(255,152,0,0.15); color: #ffb74d; }
.km-mastery-4 { background: rgba(244,67,54,0.15); color: #ef9a9a; }
.km-mastery-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }
.km-mastery-dot-0 { background: rgba(255,255,255,0.3); }
.km-mastery-dot-1 { background: #81c784; }
.km-mastery-dot-2 { background: #64b5f6; }
.km-mastery-dot-3 { background: #ffb74d; }
.km-mastery-dot-4 { background: #ef9a9a; }

.km-node-desc { font-size: 13px; color: rgba(255,255,255,0.6); line-height: 1.6; }
.km-node-rels { margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.06); }
.km-rel-title { font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.4); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
.km-rel-item { font-size: 12px; color: rgba(102,126,234,0.8); padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
.km-rel-item:last-child { border: none; }

.km-btn-plan {
  display: block; width: 100%; padding: 10px; border: none; border-radius: 10px;
  font-size: 13px; font-weight: 600; cursor: pointer; margin-top: 14px;
  background: var(--primary);
  color: #fff; box-shadow: var(--shadow-brand);
  transition: all 0.25s;
}
.km-btn-plan:hover { background: var(--primary-hv); transform: translateY(-2px); }
.km-btn-plan:disabled { opacity: 0.4; cursor: not-allowed; transform: none !important; box-shadow: none !important; }

/* Layout toggle */
.km-layout-toggle {
  position: absolute; left: 16px; bottom: 16px; z-index: 10;
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 10px; padding: 8px 14px; cursor: pointer;
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: rgba(255,255,255,0.6);
  transition: all 0.25s; user-select: none;
}
.km-layout-toggle:hover { border-color: #667eea; color: #fff; box-shadow: 0 4px 16px rgba(102,126,234,0.15); }
.km-toggle-icon { font-size: 16px; }

/* Mastery legend */
.km-mastery-legend {
  position: absolute; right: 16px; bottom: 16px; z-index: 10;
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; padding: 10px 14px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  font-size: 12px; color: rgba(255,255,255,0.5); line-height: 1.8;
}
.km-legend-title { font-weight: 600; color: rgba(255,255,255,0.4); margin-bottom: 2px; font-size: 11px; }
.km-legend-item { display: flex; align-items: center; gap: 6px; }
.km-legend-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }

/* Merge overlay */
.km-merge-overlay {
  position: absolute; inset: 0; z-index: 50;
  background: rgba(15,12,41,0.6); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
}
.km-merge-loading-card {
  background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px; padding: 32px 48px; text-align: center;
  backdrop-filter: blur(16px);
}
.km-ml-spinner {
  width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.08);
  border-top-color: #667eea; border-radius: 50%;
  animation: km-spin 0.8s linear infinite; margin: 0 auto 16px;
}
.km-ml-text { font-size: 15px; color: rgba(255,255,255,0.8); font-weight: 500; }
.km-ml-sub { font-size: 12px; color: rgba(255,255,255,0.4); margin-top: 6px; }

/* 生成学习计划加载遮罩 */
.km-plan-overlay {
  position: absolute; inset: 0; z-index: 60;
  background: rgba(15,12,41,0.7); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
}
.km-plan-loading-card {
  background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px; padding: 32px 48px; text-align: center;
  backdrop-filter: blur(16px);
}

/* 生成学习计划结果弹窗 */
.km-plan-result-overlay {
  position: absolute; inset: 0; z-index: 70;
  background: rgba(15,12,41,0.7); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
}
.km-plan-result-card {
  background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15);
  border-radius: 16px; padding: 32px 48px; text-align: center;
  backdrop-filter: blur(16px); min-width: 300px;
}
.km-plan-result-card.success { border-color: rgba(46,204,113,0.4); }
.km-plan-result-card.error { border-color: rgba(231,76,60,0.4); }
.km-plan-result-icon {
  width: 56px; height: 56px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 28px; font-weight: bold; margin: 0 auto 16px;
}
.km-plan-result-card.success .km-plan-result-icon {
  background: rgba(46,204,113,0.2); color: #2ecc71;
}
.km-plan-result-card.error .km-plan-result-icon {
  background: rgba(231,76,60,0.2); color: #e74c3c;
}
.km-plan-result-msg {
  font-size: 15px; color: rgba(255,255,255,0.9); margin-bottom: 20px;
  line-height: 1.6;
}
.km-plan-result-btn {
  background: var(--primary);
  color: #fff; border: none; border-radius: 8px;
  padding: 10px 32px; font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.km-plan-result-btn:hover {
  background: var(--primary-hv);
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}

/* 删除确认弹窗 */
.km-delete-confirm-overlay {
  position: absolute; inset: 0; z-index: 80;
  background: rgba(15,12,41,0.7); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
}
.km-delete-confirm-card {
  background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15);
  border-radius: 16px; padding: 32px 48px; text-align: center;
  backdrop-filter: blur(16px); min-width: 320px;
}
.km-delete-confirm-icon {
  font-size: 48px; color: #f39c12; margin-bottom: 16px;
}
.km-delete-confirm-title {
  font-size: 18px; font-weight: 600; color: rgba(255,255,255,0.95);
  margin-bottom: 12px;
}
.km-delete-confirm-msg {
  font-size: 14px; color: rgba(255,255,255,0.7); margin-bottom: 24px;
}
.km-delete-confirm-btns {
  display: flex; gap: 12px; justify-content: center;
}
.km-delete-cancel-btn {
  background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.8);
  border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;
  padding: 10px 24px; font-size: 14px; cursor: pointer;
  transition: all 0.2s;
}
.km-delete-cancel-btn:hover {
  background: rgba(255,255,255,0.15);
}
.km-delete-confirm-btn {
  background: linear-gradient(135deg, #e74c3c, #c0392b);
  color: #fff; border: none; border-radius: 8px;
  padding: 10px 24px; font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.km-delete-confirm-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(231,76,60,0.3);
}

/* Scrollbar */
.km-graph-list::-webkit-scrollbar { width: 4px; }
.km-graph-list::-webkit-scrollbar-track { background: transparent; }
.km-graph-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
.km-graph-list::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
</style>

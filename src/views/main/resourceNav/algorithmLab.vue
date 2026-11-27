<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getStructuresApi,
  getInitialStateApi,
  getOperationsApi,
  executeOperationApi,
  executeCustomOperationApi,
  addCustomStructureApi,
  deleteCustomStructureApi
} from '@/api/mainApi/resourceAlgorithmLab.js'

// =================== 用户 ===================
const userId = ref('user_001')

// =================== 数据结构选择 ===================
const structures = ref([])
const currentStructureKey = ref('')
const currentStructureName = ref('')
const currentStructureIsCustom = ref(false)

// =================== 操作 ===================
const operations = ref([])
const currentOperation = ref('')
const paramInput = ref('')

// =================== 画布状态 ===================
const nodes = ref([])
const edges = ref([])
const pointers = ref({})
const selectedNodeId = ref(null)

// =================== 操作历史 & 播放 ===================
const operationHistory = ref([])
const allSteps = ref([])
const currentStepIndex = ref(-1)
const isPlaying = ref(false)
let playTimer = null

// =================== 拖拽 ===================
const draggingId = ref(null)
const dragOffset = reactive({ x: 0, y: 0 })

// =================== 播放模式 ===================
const isPlayback = ref(false)
const highlightedNodes = ref([])
const playbackNodes = ref([])
const playbackEdges = ref([])
const playbackPointers = ref({})
let pulseAnim = null

// =================== 播放速度 ===================
const speed = ref(1200)

// =================== UI 状态 ===================
const activeTab = ref('code')
const loading = ref(false)
const canvasEmpty = ref(true)
const canvasHintVisible = ref(false)

// =================== 自定义数据结构对话框 ===================
const showAddStructDialog = ref(false)
const newStructName = ref('')
const newStructDesc = ref('')
const newStructCategory = ref('自定义')
const addStructLoading = ref(false)

// =================== 自定义操作 ===================
const customOpInput = ref('')
const customOpLoading = ref(false)

// =================== Canvas ===================
const canvasRef = ref(null)
const canvasWrapperRef = ref(null)
let ctx = null
let resizeObserver = null

// =================== 主题色（适配亮/暗模式） ===================
const isDark = ref(document.documentElement.classList.contains('dark'))

function getCanvasColors() {
  const dark = isDark.value
  return {
    canvasBg: dark ? 'rgba(15, 23, 42, 0.8)' : 'rgba(15, 12, 41, 0.8)',
    gridLine: dark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.04)',
    edgeDefault: dark ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.4)',
    edgeHighlight: 'rgba(240,147,251,0.9)',
    nodeGradStart: '#667eea',
    nodeGradEnd: '#764ba2',
    nodeHighlightStart: '#f093fb',
    nodeHighlightEnd: '#f5576c',
    nodeBorder: 'rgba(255,255,255,0.6)',
    nodeBorderHighlight: 'rgba(255,255,255,1)',
    nodeText: '#fff',
    nodeIdText: dark ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.4)',
    pointerBg: 'rgba(240,147,251,0.9)',
    pointerText: '#fff',
    pointerLine: 'rgba(240,147,251,0.6)',
    selectionRing: '#f093fb',
    glowNormal: 'rgba(102,126,234,0.4)',
    glowHighlight: 'rgba(240,147,251,0.6)',
  }
}

// =================== 计算属性 ===================
const hasStructure = computed(() => !!currentStructureKey.value)
const hasOperation = computed(() => !!currentOperation.value)
const canExecute = computed(() => hasStructure.value && hasOperation.value)
const totalSteps = computed(() => allSteps.value.length)
const currentStepDisplay = computed(() => {
  if (currentStepIndex.value < 0) return `步骤: 0 / ${totalSteps.value}`
  return `步骤: ${currentStepIndex.value + 1} / ${totalSteps.value}`
})
const historyCount = computed(() => operationHistory.value.length)
const noArbitraryDelete = computed(() =>
  ['stack', 'queue'].includes(currentStructureKey.value)
)
const canRemoveNode = computed(() => !!selectedNodeId.value && !noArbitraryDelete.value)
const executeBtnText = computed(() => {
  if (hasOperation.value) {
    const op = operations.value.find(o => o.key === currentOperation.value)
    return op ? op.name : currentOperation.value
  }
  if (hasStructure.value) return '请选择操作'
  return '请选择数据结构'
})

const currentOpParams = computed(() => {
  const op = operations.value.find(o => o.key === currentOperation.value)
  return op?.params || []
})

// =================== 内置数据结构（兜底） ===================
function getBuiltinStructures() {
  return [
    { key: 'singly_linked_list', name: '单链表', category: '线性结构' },
    { key: 'doubly_linked_list', name: '双向链表', category: '线性结构' },
    { key: 'stack', name: '栈', category: '线性结构' },
    { key: 'queue', name: '队列', category: '线性结构' },
    { key: 'binary_search_tree', name: '二叉搜索树', category: '树形结构' },
    { key: 'heap', name: '堆', category: '树形结构' },
    { key: 'hash_table', name: '哈希表', category: '哈希结构' },
  ]
}

function getDefaultOperations() {
  return [
    { key: 'insert', name: '插入', params: ['value'] },
    { key: 'delete', name: '删除', params: ['value'] },
    { key: 'traverse', name: '遍历', params: [] },
  ]
}

// =================== 加载数据结构列表 ===================
async function loadStructures() {
  try {
    const data = await getStructuresApi(userId.value)
    if (data && data.success && data.data) {
      structures.value = data.data
    } else {
      structures.value = getBuiltinStructures()
    }
  } catch (e) {
    structures.value = getBuiltinStructures()
  }
}

// =================== 选择数据结构 ===================
async function selectStructure(s) {
  currentStructureKey.value = s.key
  currentStructureName.value = s.name
  currentStructureIsCustom.value = !!s.is_custom
  selectedNodeId.value = null
  operationHistory.value = []
  allSteps.value = []
  currentStepIndex.value = -1
  exitPlayback()

  canvasEmpty.value = false
  canvasHintVisible.value = true

  await loadOperations(s.key)

  try {
    const data = await getInitialStateApi(s.key, 5, userId.value)
    if (data && data.success) {
      nodes.value = data.data.nodes || []
      edges.value = data.data.edges || []
      pointers.value = data.data.pointers || {}
      drawCanvas()
    } else {
      throw new Error(data?.error || '加载失败')
    }
  } catch (e) {
    initFallbackState(s.key)
    drawCanvas()
  }

  resetCodePanel()
  updateHistory()
}

// =================== 加载操作列表 ===================
async function loadOperations(structureKey) {
  try {
    const data = await getOperationsApi(structureKey, userId.value)
    if (data && data.success && data.data) {
      operations.value = data.data
    } else {
      operations.value = getDefaultOperations()
    }
  } catch (e) {
    operations.value = getDefaultOperations()
  }
}

// =================== 选择操作 ===================
function selectOperation(op) {
  currentOperation.value = op.key
}

// =================== 初始化兜底状态 ===================
function initFallbackState(structureKey) {
  const nodeList = []
  const count = 5

  if (structureKey === 'singly_linked_list' || structureKey === 'doubly_linked_list') {
    for (let i = 0; i < count; i++) {
      nodeList.push({
        id: `node_${i}`,
        value: Math.floor(Math.random() * 90) + 10,
        position_x: 100 + i * 110,
        position_y: 180,
        next: i < count - 1 ? `node_${i + 1}` : null
      })
    }
    edges.value = nodeList.slice(0, -1).map((n, i) => ({ from: n.id, to: nodeList[i + 1].id }))
    pointers.value = { head: 'node_0' }
  } else if (structureKey === 'stack') {
    for (let i = 0; i < count; i++) {
      nodeList.push({
        id: `node_${i}`,
        value: Math.floor(Math.random() * 90) + 10,
        position_x: 200,
        position_y: 300 - i * 45
      })
    }
    pointers.value = { top: `node_${count - 1}` }
  } else if (structureKey === 'queue') {
    for (let i = 0; i < count; i++) {
      nodeList.push({
        id: `node_${i}`,
        value: Math.floor(Math.random() * 90) + 10,
        position_x: 80 + i * 100,
        position_y: 180
      })
    }
    pointers.value = { front: 'node_0', rear: `node_${count - 1}` }
  } else if (structureKey === 'binary_search_tree') {
    const sortedVals = [15, 35, 50, 70, 85]
    buildBST(sortedVals, 0, 300, 80, nodeList, [])
    pointers.value = { root: nodeList[0]?.id }
  }

  nodes.value = nodeList
}

function buildBST(arr, depth, x, y, nodeList, edgeList) {
  if (!arr.length) return null
  const mid = Math.floor(arr.length / 2)
  const val = arr[mid]
  const id = `bst_${val}`
  nodeList.push({ id, value: val, position_x: x, position_y: y })

  const leftArr = arr.slice(0, mid)
  const rightArr = arr.slice(mid + 1)

  if (leftArr.length) {
    const leftX = x - 80 / (depth + 1)
    const leftY = y + 70
    const leftId = buildBST(leftArr, depth + 1, leftX, leftY, nodeList, edgeList)
    if (leftId) edgeList.push({ from: id, to: leftId })
  }
  if (rightArr.length) {
    const rightX = x + 80 / (depth + 1)
    const rightY = y + 70
    const rightId = buildBST(rightArr, depth + 1, rightX, rightY, nodeList, edgeList)
    if (rightId) edgeList.push({ from: id, to: rightId })
  }
  return id
}

// =================== Canvas 初始化 ===================
function initCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  ctx = canvas.getContext('2d')
  resizeCanvas()

  resizeObserver = new ResizeObserver(() => {
    resizeCanvas()
    drawCanvas()
  })
  if (canvasWrapperRef.value) {
    resizeObserver.observe(canvasWrapperRef.value)
  }

  canvas.addEventListener('mousedown', handleMouseDown)
  canvas.addEventListener('mousemove', handleMouseMove)
  canvas.addEventListener('mouseup', handleMouseUp)
  canvas.addEventListener('mouseleave', handleMouseUp)
}

function resizeCanvas() {
  const canvas = canvasRef.value
  const wrapper = canvasWrapperRef.value
  if (!canvas || !wrapper) return
  canvas.width = wrapper.clientWidth
  canvas.height = wrapper.clientHeight
}

// =================== Canvas 绘制 ===================
function drawCanvas() {
  if (!ctx || !canvasRef.value) return
  const canvas = canvasRef.value
  const colors = getCanvasColors()

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  drawGrid(colors)

  const drawNodes = isPlayback.value ? playbackNodes.value : nodes.value
  const drawEdges = isPlayback.value ? playbackEdges.value : edges.value
  const drawPointers = isPlayback.value ? playbackPointers.value : pointers.value

  if (drawNodes.length === 0) return
  drawEdgesFn(drawEdges, drawNodes, colors)
  drawNodes.forEach(node => drawNodeFn(node, colors))
  drawPointersFn(drawPointers, drawNodes, colors)

  if (!isPlayback.value && selectedNodeId.value) {
    const node = drawNodes.find(n => n.id === selectedNodeId.value)
    if (node) drawSelectionRingFn(node, colors)
  }
}

function drawGrid(colors) {
  const canvas = canvasRef.value
  ctx.strokeStyle = colors.gridLine
  ctx.lineWidth = 1
  const gridSize = 30
  for (let x = 0; x < canvas.width; x += gridSize) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
  }
  for (let y = 0; y < canvas.height; y += gridSize) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
  }
}

function drawEdgesFn(edgeList, nodeList, colors) {
  edgeList.forEach(edge => {
    const fromNode = nodeList.find(n => n.id === edge.from)
    const toNode = nodeList.find(n => n.id === edge.to)
    if (!fromNode || !toNode) return

    const fx = fromNode.position_x, fy = fromNode.position_y
    const tx = toNode.position_x, ty = toNode.position_y

    const isHL = isPlayback.value &&
      (highlightedNodes.value.includes(edge.from) || highlightedNodes.value.includes(edge.to))
    ctx.strokeStyle = isHL ? colors.edgeHighlight : colors.edgeDefault
    ctx.lineWidth = isHL ? 3 : 2
    ctx.beginPath()
    ctx.moveTo(fx, fy)
    ctx.lineTo(tx, ty)
    ctx.stroke()

    const angle = Math.atan2(ty - fy, tx - fx)
    const arrowSize = 8
    ctx.fillStyle = isHL ? colors.edgeHighlight : colors.edgeDefault
    ctx.beginPath()
    ctx.moveTo(tx, ty)
    ctx.lineTo(tx - arrowSize * Math.cos(angle - 0.4), ty - arrowSize * Math.sin(angle - 0.4))
    ctx.lineTo(tx - arrowSize * Math.cos(angle + 0.4), ty - arrowSize * Math.sin(angle + 0.4))
    ctx.closePath()
    ctx.fill()
  })
}

function drawNodeFn(node, colors) {
  const x = node.position_x, y = node.position_y
  const radius = 24
  const isHL = isPlayback.value && highlightedNodes.value.includes(node.id)

  // 外发光
  const glowColor = isHL ? colors.glowHighlight : colors.glowNormal
  const gradient = ctx.createRadialGradient(x, y, radius * 0.5, x, y, radius * (isHL ? 2.5 : 2))
  gradient.addColorStop(0, glowColor)
  gradient.addColorStop(1, isHL ? 'rgba(240,147,251,0)' : 'rgba(102,126,234,0)')
  ctx.fillStyle = gradient
  ctx.beginPath()
  ctx.arc(x, y, radius * (isHL ? 2.5 : 2), 0, Math.PI * 2)
  ctx.fill()

  // 节点主体
  const nodeGrad = ctx.createLinearGradient(x - radius, y - radius, x + radius, y + radius)
  if (isHL) {
    nodeGrad.addColorStop(0, colors.nodeHighlightStart)
    nodeGrad.addColorStop(1, colors.nodeHighlightEnd)
  } else {
    nodeGrad.addColorStop(0, colors.nodeGradStart)
    nodeGrad.addColorStop(1, colors.nodeGradEnd)
  }
  ctx.fillStyle = nodeGrad
  ctx.beginPath()
  ctx.arc(x, y, radius, 0, Math.PI * 2)
  ctx.fill()

  // 边框
  ctx.strokeStyle = isHL ? colors.nodeBorderHighlight : colors.nodeBorder
  ctx.lineWidth = isHL ? 3 : 2
  ctx.stroke()

  // 高亮脉冲
  if (isHL) {
    const pulse = Math.sin(Date.now() / 200) * 4 + 32
    ctx.strokeStyle = 'rgba(240,147,251,0.5)'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(x, y, pulse, 0, Math.PI * 2)
    ctx.stroke()
  }

  // 值文字
  ctx.fillStyle = colors.nodeText
  ctx.font = 'bold 14px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(String(node.value), x, y)

  // ID 文字
  ctx.fillStyle = colors.nodeIdText
  ctx.font = '10px monospace'
  ctx.fillText(node.id, x, y + radius + 14)
}

function drawPointersFn(ptrs, nodeList, colors) {
  if (!ptrs) return
  Object.entries(ptrs).forEach(([name, targetId]) => {
    const node = nodeList.find(n => n.id === targetId)
    if (!node) return

    const x = node.position_x
    const y = node.position_y - 38

    ctx.fillStyle = colors.pointerBg
    ctx.font = 'bold 10px monospace'
    const textWidth = ctx.measureText(name).width
    const labelW = textWidth + 12
    const labelH = 20
    ctx.beginPath()
    ctx.roundRect(x - labelW / 2, y - labelH / 2, labelW, labelH, 6)
    ctx.fill()

    ctx.fillStyle = colors.pointerText
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(name, x, y)

    ctx.strokeStyle = colors.pointerLine
    ctx.lineWidth = 2
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(x, y + labelH / 2)
    ctx.lineTo(x, node.position_y - 24)
    ctx.stroke()
    ctx.setLineDash([])
  })
}

function drawSelectionRingFn(node, colors) {
  ctx.strokeStyle = colors.selectionRing
  ctx.lineWidth = 3
  ctx.setLineDash([6, 4])
  ctx.beginPath()
  ctx.arc(node.position_x, node.position_y, 30, 0, Math.PI * 2)
  ctx.stroke()
  ctx.setLineDash([])
}

// =================== 拖拽处理 ===================
function getCanvasPos(e) {
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / Math.max(1, rect.width)
  const scaleY = canvas.height / Math.max(1, rect.height)
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY
  }
}

function handleMouseDown(e) {
  const { x, y } = getCanvasPos(e)
  const node = nodes.value.find(n => {
    const dx = x - n.position_x
    const dy = y - n.position_y
    return dx * dx + dy * dy < 30 * 30
  })

  if (node) {
    draggingId.value = node.id
    dragOffset.x = x - node.position_x
    dragOffset.y = y - node.position_y
    selectedNodeId.value = node.id
  } else {
    selectedNodeId.value = null
  }
  drawCanvas()
}

function handleMouseMove(e) {
  if (!draggingId.value) return
  const { x, y } = getCanvasPos(e)
  const canvas = canvasRef.value
  const node = nodes.value.find(n => n.id === draggingId.value)
  if (node) {
    node.position_x = Math.max(30, Math.min(canvas.width - 30, x - dragOffset.x))
    node.position_y = Math.max(30, Math.min(canvas.height - 30, y - dragOffset.y))
    drawCanvas()
  }
}

function handleMouseUp() {
  if (draggingId.value) {
    draggingId.value = null
  }
}

// =================== 操作执行 ===================
function isInsertOp(op) {
  if (!op) return false
  return op.includes('insert') || op === 'push' || op === 'enqueue'
}

function isDeleteOp(op) {
  if (!op) return false
  return op.includes('delete') || op === 'pop' || op === 'dequeue' || op === 'delete_max'
}

function getDefaultOperation(action) {
  const map = {
    'singly_linked_list': { insert: 'insert_at_tail', delete: 'delete_by_value' },
    'doubly_linked_list': { insert: 'insert_at_tail', delete: 'delete_at_tail' },
    'circular_linked_list': { insert: 'insert_at_tail', delete: 'delete_by_value' },
    'stack': { insert: 'push', delete: 'pop' },
    'queue': { insert: 'enqueue', delete: 'dequeue' },
    'binary_search_tree': { insert: 'insert', delete: 'delete' },
    'avl_tree': { insert: 'insert', delete: 'delete' },
    'red_black_tree': { insert: 'insert', delete: 'delete' },
    'heap': { insert: 'insert', delete: 'delete_max' },
    'hash_table': { insert: 'insert', delete: 'delete' },
  }
  const ops = map[currentStructureKey.value]
  if (ops && ops[action]) return ops[action]
  return action === 'insert' ? 'insert' : 'delete'
}

async function callBackendOperation(opType, params) {
  loading.value = true
  try {
    const reqBody = {
      structure_key: currentStructureKey.value,
      operation_type: opType,
      params: params,
      current_state: {
        nodes: JSON.parse(JSON.stringify(nodes.value)),
        edges: JSON.parse(JSON.stringify(edges.value)),
        pointers: JSON.parse(JSON.stringify(pointers.value))
      }
    }
    const data = await executeOperationApi(reqBody)
    loading.value = false
    if (data && data.success) {
      addOperationToHistory(data.data, params)
      return true
    }
    ElMessage.error(data?.error || data?.detail || '执行失败')
    return false
  } catch (e) {
    loading.value = false
    ElMessage.error('执行失败: ' + (e.message || e))
    return false
  }
}

async function executeSelectedOperation() {
  if (!hasStructure.value || !hasOperation.value) {
    ElMessage.error('请先选择数据结构和操作')
    return
  }
  const params = {}
  const op = operations.value.find(o => o.key === currentOperation.value)
  if (op && op.params && op.params.length > 0) {
    const raw = paramInput.value.trim()
    params.value = raw ? parseInt(raw) : Math.floor(Math.random() * 90) + 10
    if (isNaN(params.value)) {
      ElMessage.error('请输入有效的数字')
      return
    }
  }

  const ok = await callBackendOperation(currentOperation.value, params)
  if (ok) {
    ElMessage.success('操作执行成功！代码已生成')
    if (paramInput.value.trim()) paramInput.value = ''
  }
}

async function removeNode() {
  if (!selectedNodeId.value) {
    ElMessage.error('请先选中要删除的节点')
    return
  }
  const node = nodes.value.find(n => n.id === selectedNodeId.value)
  if (!node) return

  const op = (currentOperation.value && isDeleteOp(currentOperation.value))
    ? currentOperation.value
    : getDefaultOperation('delete')
  const ok = await callBackendOperation(op, { value: node.value, node_id: node.id })
  if (ok) {
    selectedNodeId.value = null
    ElMessage.success(`已删除节点 ${node.value}`)
  }
}

// =================== 自定义操作（AI） ===================
async function executeCustomOperation() {
  if (!hasStructure.value) {
    ElMessage.error('请先选择数据结构')
    return
  }
  const desc = customOpInput.value.trim()
  if (!desc) {
    ElMessage.error('请描述要执行的操作')
    return
  }

  customOpLoading.value = true
  loading.value = true
  try {
    const data = await executeCustomOperationApi({
      structure_key: currentStructureKey.value,
      operation_description: desc,
      params: {},
      current_state: {
        nodes: JSON.parse(JSON.stringify(nodes.value)),
        edges: JSON.parse(JSON.stringify(edges.value)),
        pointers: JSON.parse(JSON.stringify(pointers.value))
      },
      user_id: userId.value
    })
    loading.value = false
    customOpLoading.value = false

    if (data && data.success) {
      addOperationToHistory(data.data, {}, desc)
      ElMessage.success('AI生成成功！代码已添加')
      customOpInput.value = ''
    } else {
      ElMessage.error(data?.error || '生成失败')
    }
  } catch (e) {
    loading.value = false
    customOpLoading.value = false
    ElMessage.error('生成失败: ' + (e.message || e))
  }
}

// =================== 自定义数据结构 ===================
function openAddStructDialog() {
  newStructName.value = ''
  newStructDesc.value = ''
  newStructCategory.value = '自定义'
  showAddStructDialog.value = true
}

function closeAddStructDialog() {
  showAddStructDialog.value = false
}

async function addCustomStructure() {
  const name = newStructName.value.trim()
  const desc = newStructDesc.value.trim()
  const category = newStructCategory.value.trim() || '自定义'

  if (!name) {
    ElMessage.error('请输入数据结构名称')
    return
  }

  addStructLoading.value = true
  try {
    const data = await addCustomStructureApi({
      user_id: userId.value,
      name,
      description: desc,
      category
    })
    addStructLoading.value = false

    if (data && data.success) {
      ElMessage.success(`数据结构「${name}」添加成功`)
      closeAddStructDialog()
      await loadStructures()
    } else {
      ElMessage.error(data?.detail || data?.message || '添加失败')
    }
  } catch (e) {
    addStructLoading.value = false
    ElMessage.error('添加失败: ' + (e.message || e))
  }
}

async function deleteCustomStructure(key, name) {
  try {
    await ElMessageBox.confirm(`确定删除自定义数据结构「${name}」？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    const data = await deleteCustomStructureApi(userId.value, key)
    if (data && data.success) {
      ElMessage.success('删除成功')
      await loadStructures()
    } else {
      ElMessage.error(data?.detail || '删除失败')
    }
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.message || e))
  }
}

// =================== 操作历史 ===================
function addOperationToHistory(result, params, customDesc) {
  const steps = result.steps || []
  const opName = customDesc || result.pseudocode?.title || result.operation_type || '操作'

  const baseStepId = allSteps.value.length
  steps.forEach((s, i) => {
    s.global_step_id = baseStepId + i + 1
    s.operation_name = opName
  })

  const historyEntry = {
    id: operationHistory.value.length + 1,
    name: opName,
    params,
    pseudocode: result.pseudocode,
    steps,
    step_range: [baseStepId, baseStepId + Math.max(0, steps.length - 1)],
    state_before: {
      nodes: JSON.parse(JSON.stringify(nodes.value)),
      edges: JSON.parse(JSON.stringify(edges.value)),
      pointers: JSON.parse(JSON.stringify(pointers.value))
    }
  }

  operationHistory.value.push(historyEntry)
  allSteps.value = allSteps.value.concat(steps)

  // 应用 final_state
  if (result.final_state) {
    const fs = result.final_state
    if (Array.isArray(fs.nodes)) {
      const canvas = canvasRef.value
      const W = canvas ? canvas.width : 800
      const H = canvas ? canvas.height : 400
      const margin = 50
      const usableW = W - 2 * margin
      const usableH = H - 2 * margin

      if (fs.nodes.length > 0) {
        const xs = fs.nodes.map(n => n.position_x || 100)
        const ys = fs.nodes.map(n => n.position_y || 180)
        let minX = Math.min(...xs), maxX = Math.max(...xs)
        let minY = Math.min(...ys), maxY = Math.max(...ys)
        let spanX = maxX - minX
        let spanY = maxY - minY

        let scale = 1
        if (spanX > usableW && spanX > 0) scale = Math.min(scale, usableW / spanX)
        if (spanY > usableH && spanY > 0) scale = Math.min(scale, usableH / spanY)

        if (scale < 1) {
          fs.nodes.forEach(n => {
            n.position_x = minX + (n.position_x - minX) * scale
            n.position_y = minY + (n.position_y - minY) * scale
          })
          maxX = minX + spanX * scale
          maxY = minY + spanY * scale
        }

        const dx = margin + (usableW - (maxX - minX)) / 2 - minX
        const dy = margin + (usableH - (maxY - minY)) / 2 - minY
        nodes.value = fs.nodes.map(n => ({
          ...n,
          position_x: (n.position_x || 100) + dx,
          position_y: (n.position_y || 180) + dy
        }))
      } else {
        nodes.value = []
      }
    }
    if (Array.isArray(fs.edges)) edges.value = fs.edges
    if (fs.pointers) pointers.value = fs.pointers
  }

  exitPlayback()
  drawCanvas()
  updateHistory()
  updateStepControls()
}

function updateHistory() {
  // 由 computed 驱动
}

// =================== 伪代码 & 步骤 ===================
const currentPseudocode = ref(null)
const stepDescription = ref('')
const highlightedLine = ref(-1)

function renderPseudocode(pseudocode) {
  if (!pseudocode) return
  currentPseudocode.value = pseudocode
}

function resetCodePanel() {
  currentPseudocode.value = null
  highlightedLine.value = -1
  stepDescription.value = ''
  currentStepIndex.value = -1
  allSteps.value = []
  operationHistory.value = []
}

function updateStepControls() {
  // 由 computed 驱动
}

function highlightLine(lineNum) {
  highlightedLine.value = lineNum
}

function nextStep() {
  if (currentStepIndex.value >= allSteps.value.length - 1) {
    stopPlay()
    return
  }
  currentStepIndex.value++
  updateStepUI()
}

function prevStep() {
  if (currentStepIndex.value <= 0) {
    currentStepIndex.value = -1
    exitPlayback()
    stepDescription.value = ''
    highlightedLine.value = -1
    return
  }
  currentStepIndex.value--
  updateStepUI()
}

function updateStepUI() {
  const step = allSteps.value[currentStepIndex.value]
  if (!step) return

  const op = operationHistory.value.find(o =>
    currentStepIndex.value >= o.step_range[0] && currentStepIndex.value <= o.step_range[1]
  )
  if (op?.pseudocode) {
    renderPseudocode(op.pseudocode)
  }

  highlightLine(step.code_line)

  stepDescription.value = step.description || step.message || ''

  updateHistory()
  buildPlaybackState(currentStepIndex.value)
}

// =================== 播放状态重建 ===================
function buildPlaybackState(stepIndex) {
  const step = allSteps.value[stepIndex]
  if (!step) { exitPlayback(); return }

  const op = operationHistory.value.find(o =>
    stepIndex >= o.step_range[0] && stepIndex <= o.step_range[1]
  )
  if (!op?.state_before) { exitPlayback(); return }

  let pNodes = JSON.parse(JSON.stringify(op.state_before.nodes || []))
  let pEdges = JSON.parse(JSON.stringify(op.state_before.edges || []))
  let pPointers = JSON.parse(JSON.stringify(op.state_before.pointers || {}))

  const startStep = op.step_range[0]
  for (let i = startStep; i <= stepIndex; i++) {
    const s = allSteps.value[i]
    if (!s) continue

    if (s.node_changes) {
      for (const change of s.node_changes) {
        pNodes = applyNodeChange(pNodes, pEdges, change)
      }
    }
    if (s.pointer_changes) {
      for (const pc of s.pointer_changes) {
        if (pc.target === null || pc.target === undefined) {
          delete pPointers[pc.pointer]
        } else {
          pPointers[pc.pointer] = pc.target
        }
      }
    }
  }

  isPlayback.value = true
  playbackNodes.value = pNodes
  playbackEdges.value = pEdges
  playbackPointers.value = pPointers
  highlightedNodes.value = step.highlight_nodes || []

  drawCanvas()

  if (highlightedNodes.value.length > 0 && isPlaying.value) {
    if (pulseAnim) cancelAnimationFrame(pulseAnim)
    const animate = () => {
      if (!isPlayback.value || !isPlaying.value) return
      drawCanvas()
      pulseAnim = requestAnimationFrame(animate)
    }
    pulseAnim = requestAnimationFrame(animate)
  }
}

function applyNodeChange(nodeList, edgeList, change) {
  const action = change.action
  if (action === 'create') {
    if (!nodeList.find(n => n.id === change.node_id)) {
      const finalNode = nodes.value.find(n => n.id === change.node_id)
      nodeList.push({
        id: change.node_id,
        value: change.value !== undefined ? change.value : (finalNode ? finalNode.value : '?'),
        position_x: finalNode ? finalNode.position_x : (change.position_x ?? 200 + Math.random() * 100),
        position_y: finalNode ? finalNode.position_y : (change.position_y ?? 180),
        ...(finalNode ? Object.fromEntries(Object.entries(finalNode).filter(([k]) =>
          !['id', 'value', 'position_x', 'position_y'].includes(k))) : {})
      })
    }
  } else if (action === 'delete') {
    const idx = nodeList.findIndex(n => n.id === change.node_id)
    if (idx >= 0) nodeList.splice(idx, 1)
    for (let i = edgeList.length - 1; i >= 0; i--) {
      if (edgeList[i].from === change.node_id || edgeList[i].to === change.node_id) {
        edgeList.splice(i, 1)
      }
    }
  } else if (action === 'link') {
    if (!edgeList.find(e => e.from === change.from && e.to === change.to)) {
      edgeList.push({ from: change.from, to: change.to, type: change.type || 'next' })
    }
  } else if (action === 'unlink') {
    for (let i = edgeList.length - 1; i >= 0; i--) {
      if (edgeList[i].from === change.from && edgeList[i].to === change.to) {
        edgeList.splice(i, 1)
      }
    }
  } else if (action === 'update') {
    const node = nodeList.find(n => n.id === change.node_id)
    if (node && change.value !== undefined) {
      node.value = change.value
    }
  }
  return nodeList
}

function exitPlayback() {
  isPlayback.value = false
  highlightedNodes.value = []
  playbackNodes.value = []
  playbackEdges.value = []
  playbackPointers.value = {}
  if (pulseAnim) {
    cancelAnimationFrame(pulseAnim)
    pulseAnim = null
  }
  drawCanvas()
}

// =================== 播放控制 ===================
function playAll() {
  if (isPlaying.value) {
    stopPlay()
    return
  }
  if (allSteps.value.length === 0) {
    ElMessage.error('暂无可播放的步骤')
    return
  }
  isPlaying.value = true
  currentStepIndex.value = -1
  playNext()
}

function playNext() {
  if (!isPlaying.value) return
  if (currentStepIndex.value < allSteps.value.length - 1) {
    nextStep()
    playTimer = setTimeout(playNext, speed.value)
  } else {
    stopPlay()
    ElMessage.success('播放完成')
  }
}

function stopPlay() {
  isPlaying.value = false
  if (playTimer) {
    clearTimeout(playTimer)
    playTimer = null
  }
  exitPlayback()
}

// =================== 工具函数 ===================
function resetCanvas() {
  nodes.value = []
  edges.value = []
  pointers.value = {}
  selectedNodeId.value = null
  operationHistory.value = []
  allSteps.value = []
  currentStepIndex.value = -1
  exitPlayback()

  if (currentStructureKey.value) {
    initFallbackState(currentStructureKey.value)
    drawCanvas()
  } else {
    const canvas = canvasRef.value
    if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height)
  }

  resetCodePanel()
  ElMessage.info('画布已重置')
}

function clearHistory() {
  operationHistory.value = []
  allSteps.value = []
  currentStepIndex.value = -1
  stopPlay()
  exitPlayback()
  resetCodePanel()
  ElMessage.info('操作历史已清空')
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// =================== 主题监听 ===================
let themeObserver = null

// =================== 生命周期 ===================
onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const loginUser = JSON.parse(userStr)
      if (loginUser?.id) userId.value = loginUser.id
    } catch (e) { /* ignore */ }
  }

  loadStructures()
  nextTick(() => {
    initCanvas()
  })

  // 监听主题变化
  themeObserver = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.attributeName === 'class') {
        isDark.value = document.documentElement.classList.contains('dark')
        drawCanvas()
      }
    }
  })
  themeObserver.observe(document.documentElement, { attributes: true })
})

onBeforeUnmount(() => {
  const canvas = canvasRef.value
  if (canvas) {
    canvas.removeEventListener('mousedown', handleMouseDown)
    canvas.removeEventListener('mousemove', handleMouseMove)
    canvas.removeEventListener('mouseup', handleMouseUp)
    canvas.removeEventListener('mouseleave', handleMouseUp)
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (themeObserver) {
    themeObserver.disconnect()
    themeObserver = null
  }
  if (pulseAnim) {
    cancelAnimationFrame(pulseAnim)
  }
  if (playTimer) {
    clearTimeout(playTimer)
  }
})
</script>

<template>
  <div class="al-container">
    <!-- 装饰光斑 -->
    <div class="al-blob"></div>

    <!-- Header -->
    <div class="title">
      <h1><el-icon class="header-icon"><MagicStick /></el-icon> 算法实验室</h1>
      <p class="subtitle">拖拽节点移动 · 操作实时生成代码 · 播放完整执行过程 · 自定义算法</p>
    </div>

    <!-- 主布局 -->
    <div class="al-main-layout">
      <!-- 左侧边栏 -->
      <aside class="al-sidebar">
        <div class="al-sidebar-title">数据结构</div>
        <div class="al-structure-list">
          <div
            v-for="s in structures"
            :key="s.key"
            class="al-structure-item"
            :class="{ active: currentStructureKey === s.key }"
            @click="selectStructure(s)"
          >
            {{ s.name }}
            <span class="al-cat">{{ s.category }}</span>
            <span v-if="s.is_custom" class="al-custom-tag">自定义</span>
          </div>
        </div>

        <button class="al-add-struct-btn" @click="openAddStructDialog">
          <el-icon><Plus /></el-icon> 添加自定义数据结构
        </button>

        <!-- 操作区域 -->
        <div v-if="hasStructure" class="al-operation-section">
          <div class="al-operation-section-title">选择操作</div>
          <div class="al-operation-list">
            <button
              v-for="op in operations"
              :key="op.key"
              class="al-operation-btn"
              :class="{ active: currentOperation === op.key }"
              @click="selectOperation(op)"
            >{{ op.name }}</button>
          </div>
          <input
            v-model="paramInput"
            class="al-param-input"
            placeholder="输入数值（用于插入/删除/查找）..."
            @keyup.enter="executeSelectedOperation"
          />
        </div>

        <!-- 自定义操作 -->
        <div v-if="hasStructure" class="al-custom-op-section">
          <div class="al-operation-section-title">自定义操作 (LLM生成)</div>
          <textarea
            v-model="customOpInput"
            class="al-custom-op-input"
            placeholder="描述你想执行的操作，例如：&#10;- 将所有奇数节点移到前面&#10;- 反转链表&#10;- 合并两个有序链表"
          ></textarea>
          <button
            class="al-custom-op-btn"
            :disabled="customOpLoading"
            @click="executeCustomOperation"
          >
          <el-icon v-if="customOpLoading"><Loading /></el-icon>
          <el-icon v-else><MagicStick /></el-icon>
          {{ customOpLoading ? 'AI生成中...' : 'AI生成并执行' }}
        </button>
        </div>
      </aside>

      <!-- 中间画布 -->
      <main class="al-canvas-area">
        <div class="al-canvas-header">
          <div class="al-canvas-title">
            {{ currentStructureName ? currentStructureName + (currentStructureIsCustom ? ' (自定义)' : '') : '选择一个数据结构开始' }}
          </div>
          <div class="al-canvas-subtitle">
            {{ currentStructureName ? `${currentStructureName} - ${nodes.length} 个节点` : '支持拖拽移动、插入删除、代码同步' }}
          </div>
        </div>

        <div ref="canvasWrapperRef" class="al-canvas-wrapper">
          <!-- 加载条 -->
          <div v-if="loading" class="al-loading-bar"></div>
          <canvas ref="canvasRef"></canvas>
          <div v-if="canvasEmpty" class="al-canvas-overlay">
            <div class="al-canvas-empty">
              <div class="al-canvas-empty-icon"><el-icon size="66"><TrendCharts /></el-icon></div>
              <div>点击左侧数据结构创建可视化</div>
            </div>
          </div>
          <div v-if="canvasHintVisible" class="al-canvas-hint">
            <el-icon><Promotion /></el-icon> 拖拽节点移动 · 点击选中 · 操作后查看右侧代码
          </div>
        </div>

        <div class="al-toolbar">
          <button
            class="al-toolbar-btn primary"
            :disabled="!canExecute"
            @click="executeSelectedOperation"
          >
            <span class="icon">▶️</span> {{ executeBtnText }}
          </button>
          <button
            class="al-toolbar-btn danger"
            :disabled="!canRemoveNode"
            title="先点击选中画布中的节点，再点击删除"
            @click="removeNode"
          >
            <el-icon><Minus /></el-icon> 删除选中
          </button>
          <button class="al-toolbar-btn" @click="resetCanvas">
            <el-icon><Refresh /></el-icon> 重置画布
          </button>
          <button class="al-toolbar-btn" title="清空所有操作历史" @click="clearHistory">
            <el-icon><Delete /></el-icon> 清空历史
          </button>
        </div>
      </main>

      <!-- 右侧代码面板 -->
      <aside class="al-code-panel">
        <div class="al-code-header">
          <div class="al-code-title">算法伪代码</div>
          <div class="al-code-steps">{{ currentStepDisplay }}</div>
        </div>

        <div class="al-code-tabs">
          <button
            class="al-code-tab"
            :class="{ active: activeTab === 'code' }"
            @click="activeTab = 'code'"
          >代码</button>
          <button
            class="al-code-tab"
            :class="{ active: activeTab === 'history' }"
            @click="activeTab = 'history'"
          >操作历史 ({{ historyCount }})</button>
        </div>

        <!-- 代码标签页 -->
        <div v-show="activeTab === 'code'" class="al-code-content">
          <template v-if="currentPseudocode && currentPseudocode.code_lines">
            <div
              v-for="line in currentPseudocode.code_lines"
              :key="line.line"
              class="al-code-line"
              :class="{
                highlight: highlightedLine === line.line,
                'method-def': line.is_method,
                comment: line.code && line.code.trim().startsWith('#')
              }"
            >
              <span class="line-num">{{ line.line }}</span>
              <span class="line-code">{{ line.code || '&nbsp;' }}</span>
            </div>
          </template>
          <div v-else class="al-code-empty">
            // 选择操作并执行后，此处将显示代码
          </div>
        </div>

        <!-- 历史标签页 -->
        <div v-show="activeTab === 'history'" class="al-history-list">
          <template v-if="operationHistory.length > 0">
            <div
              v-for="(op, idx) in operationHistory"
              :key="op.id"
              class="al-history-item"
              :class="{
                current: currentStepIndex >= op.step_range[0] && currentStepIndex <= op.step_range[1]
              }"
              @click="currentStepIndex = op.step_range[0] - 1; activeTab = 'code'; nextStep()"
            >
              <div class="step-num">{{ idx + 1 }}</div>
              <div style="flex:1;">
                <div class="history-name">{{ op.name }}</div>
                <div class="history-range">步骤 {{ op.step_range[0] + 1 }}-{{ op.step_range[1] + 1 }}</div>
              </div>
            </div>
          </template>
          <div v-else class="al-history-empty">暂无操作历史</div>
        </div>

        <!-- 步骤描述 -->
        <div class="al-step-description">
          <template v-if="stepDescription">
            <div class="step-dot">{{ currentStepIndex + 1 }}</div>
            <div class="step-text" v-html="stepDescription"></div>
          </template>
          <template v-else>
            <div class="step-placeholder">执行操作后，此处将显示步骤描述</div>
          </template>
        </div>

        <!-- 播放控制 -->
        <div class="al-controls">
          <button class="al-ctrl-btn" :disabled="currentStepIndex <= 0" @click="prevStep"><el-icon><Back /></el-icon></button>
          <button
            class="al-ctrl-btn play-all"
            :disabled="totalSteps === 0"
            @click="playAll"
          >
            <el-icon v-if="isPlaying"><VideoPause /></el-icon>
            <el-icon v-else><VideoPlay /></el-icon>
            {{ isPlaying ? '暂停' : '从头播放' }}
          </button>
          <button class="al-ctrl-btn" :disabled="currentStepIndex >= totalSteps - 1" @click="nextStep"><el-icon><Right /></el-icon></button>
          <select v-model="speed" class="al-speed-select">
            <option :value="2000">慢速</option>
            <option :value="1200">正常</option>
            <option :value="600">快速</option>
          </select>
        </div>
      </aside>
    </div>

    <!-- 添加自定义数据结构对话框 -->
    <div v-if="showAddStructDialog" class="al-modal-overlay" @click.self="closeAddStructDialog">
      <div class="al-modal">
        <h3><el-icon><Plus /></el-icon> 添加自定义数据结构</h3>
        <div class="al-modal-field">
          <label>名称 *</label>
          <input v-model="newStructName" placeholder="如：跳表、Trie树、并查集..." />
        </div>
        <div class="al-modal-field">
          <label>描述（用于AI生成代码和可视化）</label>
          <textarea v-model="newStructDesc" placeholder="描述该数据结构的特点、组成方式、关键操作等，描述越详细AI生成越准确"></textarea>
        </div>
        <div class="al-modal-field">
          <label>分类</label>
          <input v-model="newStructCategory" placeholder="如：高级结构" />
        </div>
        <div class="al-modal-actions">
          <button class="al-modal-cancel" @click="closeAddStructDialog">取消</button>
          <button class="al-modal-confirm" :disabled="addStructLoading" @click="addCustomStructure">
            {{ addStructLoading ? '添加中...' : '添加' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.al-container {
  position: relative;
  min-height: 100vh;
  background: transparent;
  overflow: hidden;
}

.al-blob {
  position: fixed;
  width: 500px;
  height: 500px;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.08;
  z-index: 0;
  pointer-events: none;
  background: var(--primary);
  top: -200px;
  right: -100px;
  animation: al-float-bg 25s ease-in-out infinite;
}

@keyframes al-float-bg {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-30px, 50px) scale(1.05); }
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

/* 主布局 */
.al-main-layout {
  display: grid;
  grid-template-columns: 240px 1fr 420px;
  gap: 16px;
  position: relative;
  z-index: 2;
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 16px 16px;
  height: calc(100vh - 100px);
}

/* 侧边栏 */
.al-sidebar {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  height: 100%;
  min-height: 0;
}

.al-sidebar-title {
  color: var(--text-title);
  font-size: 14px;
  font-weight: 600;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.al-structure-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.al-structure-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--bgc-light);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.25s;
  color: var(--text-body);
  font-size: 13px;
}

.al-structure-item:hover {
  background: var(--primary-light);
  color: var(--text-title);
}

.al-structure-item.active {
  background: var(--grad-primary);
  color: var(--btn-text);
  border-color: transparent;
  box-shadow: var(--shadow-brand);
}

.al-cat {
  font-size: 11px;
  opacity: 0.6;
  margin-left: 6px;
}

.al-custom-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--coming);
  color: var(--btn-text);
  margin-left: 6px;
}

.al-add-struct-btn {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--purple), var(--purple-hover));
  color: var(--btn-text);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s;
}

.al-add-struct-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--purple-shadow);
}

.al-operation-section {
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.al-operation-section-title {
  color: var(--text-gray);
  font-size: 12px;
  margin-bottom: 8px;
}

.al-operation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.al-operation-btn {
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--bgc-light);
  border: 1px solid var(--border-color);
  color: var(--text-body);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.al-operation-btn:hover {
  background: var(--primary-light);
  color: var(--text-title);
  border-color: var(--primary);
}

.al-operation-btn.active {
  background: var(--primary);
  color: var(--btn-text);
  border-color: transparent;
}

.al-param-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: 8px;
  color: var(--text-title);
  font-size: 12px;
  margin-top: 8px;
  outline: none;
}

.al-param-input:focus {
  border-color: var(--primary);
}

.al-custom-op-section {
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.al-custom-op-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  border-radius: 8px;
  color: var(--text-title);
  font-size: 12px;
  outline: none;
  resize: vertical;
  min-height: 60px;
  font-family: inherit;
}

.al-custom-op-input:focus {
  border-color: var(--primary);
}

.al-custom-op-btn {
  width: 100%;
  padding: 8px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--purple), var(--purple-hover));
  color: var(--btn-text);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
  transition: all 0.25s;
}

.al-custom-op-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--purple-shadow);
}

.al-custom-op-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 画布区域 */
.al-canvas-area {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  min-height: 0;
}

.al-canvas-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.al-canvas-title {
  color: var(--text-title);
  font-size: 16px;
  font-weight: 600;
}

.al-canvas-subtitle {
  color: var(--text-gray);
  font-size: 12px;
}

.al-canvas-wrapper {
  flex: 1;
  position: relative;
  background: var(--canvas-bg);
  overflow: hidden;
  min-height: 300px;
}

.al-canvas-wrapper canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: default;
}

.al-canvas-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--canvas-empty-text);
  font-size: 14px;
  pointer-events: none;
}

.al-canvas-empty {
  text-align: center;
}

.al-canvas-empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.al-canvas-hint {
  position: absolute;
  bottom: 12px;
  left: 12px;
  background: var(--canvas-hint-bg);
  color: var(--canvas-hint-text);
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  backdrop-filter: blur(8px);
}

.al-loading-bar {
  position: absolute;
  top: 0;
  left: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--purple));
  width: 0%;
  z-index: 3;
  animation: al-loading-anim 1.5s ease-in-out infinite;
}

@keyframes al-loading-anim {
  0% { width: 0%; }
  50% { width: 70%; }
  100% { width: 100%; }
}

/* 工具栏 */
.al-toolbar {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  background: var(--bgc-light);
}

.al-toolbar-btn {
  padding: 8px 14px;
  border-radius: 10px;
  background: var(--bgc-light);
  border: 1px solid var(--border-color);
  color: var(--text-body);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.25s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.al-toolbar-btn:hover:not(:disabled) {
  background: var(--primary-light);
  color: var(--text-title);
  border-color: var(--primary);
}

.al-toolbar-btn.primary {
  background: var(--grad-primary);
  color: var(--btn-text);
  border-color: transparent;
}

.al-toolbar-btn.primary:hover:not(:disabled) {
  box-shadow: var(--shadow-brand);
  transform: translateY(-1px);
}

.al-toolbar-btn.danger {
  background: var(--main-fail-status);
  color: var(--main-delete);
  border-color: var(--primary-disa-border);
}

.al-toolbar-btn.danger:hover:not(:disabled) {
  background: var(--main-fail-status-hover);
}

.al-toolbar-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.al-toolbar-btn .el-icon {
  font-size: 16px;
}

/* 代码面板 */
.al-code-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  min-height: 0;
}

.al-code-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.al-code-title {
  color: var(--text-title);
  font-size: 14px;
  font-weight: 600;
}

.al-code-steps {
  color: var(--text-gray);
  font-size: 12px;
}

.al-code-tabs {
  display: flex;
  gap: 4px;
  padding: 0 12px;
  background: var(--bgc-light);
  border-bottom: 1px solid var(--border-color);
}

.al-code-tab {
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: var(--text-gray);
  cursor: pointer;
  font-size: 12px;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.al-code-tab:hover {
  color: var(--text-title);
}

.al-code-tab.active {
  color: var(--text-title);
  border-bottom-color: var(--primary);
}

.al-code-content {
  flex: 1;
  overflow-y: auto;
  background: var(--bgc-light);
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  min-height: 0;
}

.al-code-empty {
  color: var(--text-gray);
  text-align: center;
  padding: 40px 0;
  opacity: 0.5;
}

.al-code-line {
  display: flex;
  padding: 1px 0;
  border-radius: 4px;
  transition: all 0.25s;
}

.al-code-line .line-num {
  width: 36px;
  color: var(--text-gray);
  text-align: right;
  padding-right: 12px;
  user-select: none;
  flex-shrink: 0;
  opacity: 0.5;
}

.al-code-line .line-code {
  color: var(--text-body);
  white-space: pre;
}

.al-code-line.highlight {
  background: linear-gradient(90deg, var(--primary-light), transparent);
  border-left: 3px solid var(--primary);
}

.al-code-line.method-def .line-code {
  color: var(--pass);
  font-weight: 600;
}

.al-code-line.comment .line-code {
  color: var(--text-gray);
  font-style: italic;
  opacity: 0.6;
}

/* 操作历史 */
.al-history-list {
  padding: 8px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.al-history-item {
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bgc-light);
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--text-body);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.al-history-item:hover {
  background: var(--primary-light);
}

.al-history-item .step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--btn-text);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

.al-history-item.current {
  background: var(--primary-light);
  border-left: 3px solid var(--primary);
}

.history-name {
  color: var(--text-title);
  font-size: 12px;
}

.history-range {
  color: var(--text-gray);
  font-size: 11px;
  opacity: 0.6;
}

.al-history-empty {
  color: var(--text-gray);
  text-align: center;
  padding: 20px;
  font-size: 12px;
  opacity: 0.5;
}

/* 步骤描述 */
.al-step-description {
  padding: 12px 16px;
  background: var(--primary-light);
  border-top: 1px solid var(--border-color);
  color: var(--text-body);
  font-size: 13px;
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.step-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--btn-text);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.step-text {
  line-height: 1.5;
}

.step-placeholder {
  color: var(--text-gray);
  opacity: 0.5;
}

/* 播放控制 */
.al-controls {
  padding: 10px 12px;
  background: var(--bgc-light);
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
}

.al-ctrl-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--bgc-light);
  border: 1px solid var(--border-color);
  color: var(--text-body);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  font-size: 14px;
}

.al-ctrl-btn:hover:not(:disabled) {
  background: var(--primary);
  color: var(--btn-text);
  border-color: transparent;
}

.al-ctrl-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.al-ctrl-btn.play-all {
  width: auto;
  padding: 0 16px;
  border-radius: 17px;
  background: var(--grad-primary);
  color: var(--btn-text);
  font-size: 12px;
  font-weight: 600;
  border: none;
}

.al-ctrl-btn.play-all:hover:not(:disabled) {
  box-shadow: var(--shadow-brand);
}

.al-speed-select {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  color: var(--text-body);
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  outline: none;
}

.al-speed-select option {
  background: var(--bg-card);
  color: var(--text-title);
}

/* 对话框 */
.al-modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--bgc-dark);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3;
}

.al-modal {
  background: var(--bg-card);
  border-radius: 14px;
  padding: 24px;
  width: 90%;
  max-width: 440px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-normal);
}

.al-modal h3 {
  color: var(--text-title);
  margin-bottom: 16px;
  font-size: 18px;
}

.al-modal-field {
  margin-bottom: 12px;
}

.al-modal-field label {
  color: var(--text-gray);
  font-size: 13px;
  display: block;
  margin-bottom: 6px;
}

.al-modal-field input,
.al-modal-field textarea {
  width: 100%;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-input);
  color: var(--text-title);
  font-size: 14px;
  outline: none;
}

.al-modal-field textarea {
  min-height: 80px;
  resize: vertical;
  font-size: 13px;
}

.al-modal-field input:focus,
.al-modal-field textarea:focus {
  border-color: var(--primary);
}

.al-modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
}

.al-modal-cancel {
  padding: 9px 18px;
  border: none;
  border-radius: 8px;
  background: var(--bgc-light);
  color: var(--text-body);
  cursor: pointer;
  font-size: 14px;
}

.al-modal-confirm {
  padding: 9px 18px;
  border: none;
  border-radius: 8px;
  background: var(--grad-primary);
  color: var(--btn-text);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.al-modal-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 响应式 */
@media (max-width: 1200px) {
  .al-main-layout {
    grid-template-columns: 200px 1fr 340px;
  }
}

@media (max-width: 900px) {
  .al-main-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }

  .al-sidebar {
    max-height: 200px;
  }

  .al-code-panel {
    max-height: 280px;
  }
}
</style>
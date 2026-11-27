<!-- 视频思维导图组件 -->
<template>
  <div class="mindmap-viewer">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="controls">
        <button class="btn" @click="zoomOut" title="缩小">
          <span class="icon">−</span>
        </button>
        <button class="btn" @click="resetZoom" title="重置">
          <span class="icon">⟲</span>
        </button>
        <button class="btn" @click="zoomIn" title="放大">
          <span class="icon">+</span>
        </button>
        <span class="divider"></span>
        <button 
          class="btn" 
          :class="isFullscreen ? 'btn-danger' : 'btn-primary'"
          @click="toggleFullscreen" 
          :title="isFullscreen ? '退出全屏' : '全屏'"
        >
          <span class="icon">{{ isFullscreen ? '✕' : '⛶' }}</span>
        </button>
        <button class="btn btn-success" @click="refreshChart" title="刷新">
          <span class="icon">⟳</span>
        </button>
      </div>
    </div>
    
    <!-- 图表容器 -->
    <div class="chart-wrapper" ref="chartWrapper">
      <div class="chart-container" ref="chartContainer">
        <!-- 加载状态 -->
        <div v-if="loading" class="status-overlay">
          <div class="spinner"></div>
          <span>加载中...</span>
        </div>
        
        <!-- 错误状态 -->
        <div v-else-if="error" class="status-overlay error">
          <div class="icon">❌</div>
          <div>{{ error }}</div>
          <div class="hint">请查看控制台</div>
        </div>
        
        <!-- SVG 渲染区 (v-html) -->
        <div v-else v-html="svgContent" class="svg-wrapper"></div>
      </div>
      
      <!-- 缩放指示器 -->
      <div class="zoom-indicator" :class="{ show: showZoomIndicator }">
        {{ Math.round(currentScale * 100) }}%
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import mermaid from 'mermaid'

// ======================== Props ========================
const props = defineProps({
  mindmapData: {
    type: Object,
    default: () => null
  }
})

// ======================== Emits ========================
const emit = defineEmits(['rendered', 'error'])

// ======================== 响应式状态 ========================
const chartWrapper = ref(null)
const chartContainer = ref(null)
const svgContent = ref('')
const loading = ref(false)
const error = ref('')
const currentScale = ref(1)
const showZoomIndicator = ref(false)
const isFullscreen = ref(false)
const svgViewBox = ref('')
let zoomTimer = null

// ======================== 常量 ========================
const MIN_SCALE = 0.3
const MAX_SCALE = 3
const STEP = 0.1

// ======================== Mermaid 初始化 ========================
let mermaidInitialized = false

const initMermaid = () => {
  if (mermaidInitialized) return
  try {
    mermaid.initialize({
      theme: 'default',
      themeVariables: {
        primaryColor: '#409EFF',
        primaryTextColor: '#303133',
        primaryBorderColor: '#DCDFE6',
        lineColor: '#409EFF',
        secondaryColor: '#F0F2F5',
        tertiaryColor: '#fff',
        fontSize: '14px',
        fontFamily: 'Arial, sans-serif'
      },
      mindmap: {
        padding: 15,
        maxNodeWidth: 300,
        useMaxWidth: true
      },
      startOnLoad: false,
      securityLevel: 'loose'
    })
    mermaidInitialized = true
    console.log('✅ Mermaid 初始化成功')
  } catch (err) {
    console.error('❌ Mermaid 初始化失败:', err)
    error.value = 'Mermaid 初始化失败: ' + err.message
  }
}

// ======================== 生成 Mermaid 语法 ========================
const generateMindmapSyntax = (data) => {
  if (!data) return ''

  const convertNode = (node, depth = 0) => {
    if (!node) return ''
    const indent = '  '.repeat(depth)
    let result = ''
    const nodeName = String(node.name || '未命名').trim()

    if (depth === 0) {
      result += indent + 'root((' + nodeName + '))'
    } else {
      result += indent + nodeName
    }

    if (node.content) {
      const content = String(node.content).trim()
      const display = content.length > 60 ? content.substring(0, 60) + '...' : content
      if (display) {
        result += '\n' + indent + '  [' + display + ']'
      }
    }

    if (node.children && node.children.length > 0) {
      node.children.forEach(child => {
        const childStr = convertNode(child, depth + 1)
        if (childStr) {
          result += '\n' + childStr
        }
      })
    }

    return result
  }

  const content = convertNode(data, 0)
  if (!content) return ''
  return 'mindmap\n' + content
}

// ======================== 渲染图表 ========================
const renderChart = async () => {
  if (!props.mindmapData) {
    error.value = '请提供思维导图数据'
    return
  }

  loading.value = true
  error.value = ''
  svgContent.value = ''

  try {
    await nextTick()
    
    initMermaid()

    const syntax = generateMindmapSyntax(props.mindmapData)
    if (!syntax || syntax.trim() === '') {
      throw new Error('生成的语法为空')
    }

    console.log('📝 渲染语法:\n', syntax)

    const id = 'mermaid-chart-' + Date.now()
    const result = await mermaid.render(id, syntax)
    
    console.log('✅ 渲染成功, SVG 长度:', result.svg.length)

    // 使用 v-html 渲染 SVG
    svgContent.value = result.svg
    
    // 等待 DOM 更新后应用样式
    await nextTick()
    
    // 获取 SVG 元素并适配容器
    const svg = getSvgElement()
    if (svg) {
      // 保存原始 viewBox
      let viewBox = svg.getAttribute('viewBox')
      if (!viewBox) {
        const w = parseFloat(svg.getAttribute('width')) || 800
        const h = parseFloat(svg.getAttribute('height')) || 600
        viewBox = `0 0 ${w} ${h}`
        svg.setAttribute('viewBox', viewBox)
      }
      svgViewBox.value = viewBox
      
      // 【关键】让 SVG 占满容器
      svg.removeAttribute('width')
      svg.removeAttribute('height')
      svg.style.width = '100%'
      svg.style.height = '100%'
      svg.style.display = 'block'
      svg.style.background = '#ffffff'
      
      // 使用 preserveAspectRatio 让内容适配容器
      svg.setAttribute('preserveAspectRatio', 'xMidYMid meet')
      
      // 重置缩放状态
      currentScale.value = 1
    }

    emit('rendered', result.svg)

  } catch (err) {
    console.error('❌ 渲染失败:', err)
    error.value = '渲染失败: ' + err.message
    emit('error', err)
  } finally {
    loading.value = false
  }
}

// ======================== DOM 操作 ========================
const getSvgElement = () => {
  const container = chartContainer.value
  if (!container) return null
  return container.querySelector('svg')
}

// 获取 SVG 原始尺寸（从 viewBox）
const getSvgSize = () => {
  const svg = getSvgElement()
  if (!svg) return { width: 800, height: 600 }
  
  const viewBox = svg.getAttribute('viewBox') || svgViewBox.value
  if (viewBox) {
    const parts = viewBox.split(' ').map(Number)
    if (parts.length === 4) {
      return { width: parts[2], height: parts[3] }
    }
  }
  return { width: 800, height: 600 }
}

const applyScale = (svg) => {
  if (!svg) return
  
  if (currentScale.value === 1) {
    // 缩放为 1 时，使用 CSS 让 SVG 填满容器
    svg.style.width = '100%'
    svg.style.height = '100%'
    svg.style.transform = 'none'
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet')
  } else {
    // 缩放时，固定尺寸并应用 transform
    const size = getSvgSize()
    svg.style.width = size.width + 'px'
    svg.style.height = size.height + 'px'
    svg.style.transform = `scale(${currentScale.value})`
    svg.style.transformOrigin = 'top left'
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet')
  }
  
  showZoomIndicator.value = true
  clearTimeout(zoomTimer)
  zoomTimer = setTimeout(() => {
    showZoomIndicator.value = false
  }, 1500)
}

// ======================== 缩放控制 ========================
const zoomIn = () => {
  const svg = getSvgElement()
  if (!svg) return
  // 如果当前是 1，先切换到缩放模式
  if (currentScale.value === 1) {
    const size = getSvgSize()
    svg.style.width = size.width + 'px'
    svg.style.height = size.height + 'px'
  }
  currentScale.value = Math.min(currentScale.value + STEP, MAX_SCALE)
  applyScale(svg)
}

const zoomOut = () => {
  const svg = getSvgElement()
  if (!svg) return
  // 如果当前是 1，先切换到缩放模式
  if (currentScale.value === 1) {
    const size = getSvgSize()
    svg.style.width = size.width + 'px'
    svg.style.height = size.height + 'px'
  }
  currentScale.value = Math.max(currentScale.value - STEP, MIN_SCALE)
  applyScale(svg)
}

const resetZoom = () => {
  const svg = getSvgElement()
  if (!svg) return
  currentScale.value = 1
  // 恢复为填满容器
  svg.style.width = '100%'
  svg.style.height = '100%'
  svg.style.transform = 'none'
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet')
  
  showZoomIndicator.value = true
  clearTimeout(zoomTimer)
  zoomTimer = setTimeout(() => {
    showZoomIndicator.value = false
  }, 1500)
  
  if (chartContainer.value) {
    chartContainer.value.scrollTop = 0
    chartContainer.value.scrollLeft = 0
  }
}

// ======================== 全屏控制 ========================
const toggleFullscreen = () => {
  const wrapper = chartWrapper.value
  if (!wrapper) return

  if (!isFullscreen.value) {
    if (wrapper.requestFullscreen) {
      wrapper.requestFullscreen()
    } else if (wrapper.webkitRequestFullscreen) {
      wrapper.webkitRequestFullscreen()
    } else if (wrapper.msRequestFullscreen) {
      wrapper.msRequestFullscreen()
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen()
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen()
    } else if (document.msExitFullscreen) {
      document.msExitFullscreen()
    }
  }
}

// 监听全屏变化
const handleFullscreenChange = () => {
  const isFull = document.fullscreenElement || 
                 document.webkitFullscreenElement || 
                 document.msFullscreenElement
  isFullscreen.value = !!isFull
}

// ======================== 刷新 ========================
const refreshChart = () => {
  currentScale.value = 1
  renderChart()
}

// ======================== 监听数据变化 ========================
watch(() => props.mindmapData, (newData) => {
  if (newData) {
    renderChart()
  }
}, { deep: true })

// ======================== 生命周期 ========================
onMounted(() => {
  // 注册全屏事件监听
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('webkitfullscreenchange', handleFullscreenChange)
  document.addEventListener('msfullscreenchange', handleFullscreenChange)

  // 键盘快捷键
  document.addEventListener('keydown', handleKeydown)
  
  // 鼠标滚轮缩放
  const container = chartContainer.value
  if (container) {
    container.addEventListener('wheel', handleWheel, { passive: false })
  }

  if (props.mindmapData) {
    renderChart()
  }
})

// ======================== 事件处理 ========================
const handleKeydown = (e) => {
  if (e.ctrlKey && e.key === '=') {
    e.preventDefault()
    zoomIn()
  } else if (e.ctrlKey && e.key === '-') {
    e.preventDefault()
    zoomOut()
  } else if (e.ctrlKey && e.key === '0') {
    e.preventDefault()
    resetZoom()
  } else if (e.key === 'f' || e.key === 'F') {
    if (!e.ctrlKey && !e.metaKey) {
      e.preventDefault()
      toggleFullscreen()
    }
  }
}

const handleWheel = (e) => {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault()
    if (e.deltaY < 0) {
      zoomIn()
    } else {
      zoomOut()
    }
  }
}

// ======================== 暴露方法 ========================
defineExpose({
  renderChart,
  refreshChart,
  zoomIn,
  zoomOut,
  resetZoom,
  toggleFullscreen
})
</script>

<style scoped>
.mindmap-viewer {
  width: 100%;
  height: 100%;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ===== 工具栏 ===== */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 6px 10px;
  background: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
  min-height: 44px;
}

.toolbar .controls {
  display: flex;
  gap: 2px;
  align-items: center;
}

.toolbar .controls .divider {
  width: 1px;
  height: 22px;
  background: #dcdfe6;
  margin: 0 4px;
}

.btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: transparent;
  color: #606266;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: inherit;
  line-height: 1;
}

.btn:hover {
  background: #ecf5ff;
  color: #409EFF;
}

.btn:active {
  transform: scale(0.92);
}

.btn-primary {
  background: #409EFF;
  color: #fff;
}

.btn-primary:hover {
  background: #66b1ff;
  color: #fff;
}

.btn-danger {
  background: #f56c6c;
  color: #fff;
}

.btn-danger:hover {
  background: #f78989;
  color: #fff;
}

.btn-success {
  background: #67c23a;
  color: #fff;
}

.btn-success:hover {
  background: #85ce61;
  color: #fff;
}

.btn .icon {
  font-size: 18px;
  line-height: 1;
}

/* ===== 图表容器 ===== */
.chart-wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
  background: #ffffff;
  overflow: hidden;
}

.chart-container {
  width: 100%;
  height: 100%;
  overflow: auto;
  padding: 0;
  background: #ffffff;
  position: relative;
}

/* ===== 状态覆盖层 ===== */
.status-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 300px;
  color: #909399;
  font-size: 14px;
}

.status-overlay.error {
  color: #f56c6c;
}

.status-overlay .icon {
  font-size: 48px;
}

.status-overlay .hint {
  font-size: 12px;
  color: #909399;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e4e7ed;
  border-top-color: #409EFF;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== SVG 样式 ===== */
.svg-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.svg-wrapper :deep(svg) {
  display: block;
  background: #ffffff;
  transition: transform 0.25s ease, width 0.25s ease, height 0.25s ease;
  transform-origin: top left;
  max-width: 100%;
  max-height: 100%;
}

/* ===== 缩放指示器 ===== */
.zoom-indicator {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.75);
  color: #fff;
  padding: 4px 14px;
  border-radius: 12px;
  font-size: 12px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s ease;
  font-family: monospace;
  z-index: 10;
}

.zoom-indicator.show {
  opacity: 1;
}

/* ===== 全屏模式 ===== */
.chart-wrapper:fullscreen {
  border-radius: 0;
  padding: 0;
}

.chart-wrapper:-webkit-full-screen {
  border-radius: 0;
  padding: 0;
}

.chart-wrapper:-ms-fullscreen {
  border-radius: 0;
  padding: 0;
}

.chart-wrapper:fullscreen .toolbar {
  padding: 6px 12px;
}

/* ===== 滚动条美化 ===== */
.chart-container::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.chart-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.chart-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.chart-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>
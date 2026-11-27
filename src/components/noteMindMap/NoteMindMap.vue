<template>
  <div class="mindmap-overlay" :class="{ show: visible }" @click.self="close">
    <div class="mindmap-modal">
      <!-- 头部 -->
      <div class="mindmap-modal-header">
        <h3>🧠 笔记思维导图</h3>
        <div style="display:flex;gap:8px;">
          <button class="btn-export" @click="exportImage">💾 保存为图片</button>
          <button class="btn-close" @click="close">×</button>
        </div>
      </div>

      <!-- 主体 -->
      <div class="mindmap-modal-body" ref="bodyRef">
        <!-- 加载态 -->
        <div v-if="loading" class="mindmap-loading">
          <div class="spinner"></div>
          <div>AI 正在生成思维导图...</div>
        </div>

        <!-- 内容 -->
        <div v-else-if="mindmapData" class="mindmap-container" ref="containerRef">
          <MindmapNode
            :node="mindmapData"
            :level="0"
            @navigate="handleNavigate"
            @edit="handleEdit"
          />
        </div>

        <!-- 空状态 -->
        <div v-else class="mindmap-empty">
          <div style="font-size:48px;opacity:0.3;margin-bottom:12px;">📊</div>
          <div style="color:#999;">暂无思维导图数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import html2canvas from 'html2canvas'
import MindmapNode from './MindmapNode.vue'

// ==================== Props ====================
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  data: {
    type: Object,
    default: null
  }
})

// ==================== Emits ====================
const emit = defineEmits(['close', 'navigate', 'edit'])

// ==================== State ====================
const loading = ref(true)
const mindmapData = ref(null)
const bodyRef = ref(null)
const containerRef = ref(null)

// ==================== Watch ====================
watch(
  () => props.visible,
  (val) => {
    if (val) {
      loading.value = true
      mindmapData.value = null
    } else {
      mindmapData.value = null
      loading.value = false
    }
  },
  { immediate: true }
)

// 监听数据变化
watch(
  () => props.data,
  (val) => {
    if (val && props.visible) {
      mindmapData.value = val
      loading.value = false
    }
  }
)

// ==================== 默认示例数据 ====================
function getDefaultMindmap() {
  return {
    name: '变量基础概念与使用规则详解',
    keywords: ['变量基础概念', '使用规则'],
    children: [
      {
        name: '变量基本概念',
        keywords: ['变量基本概念', '作用', '类型特点'],
        children: [
          { name: '作用', keywords: ['存放各类数据', '起一个名字', '方便后续调用'] },
          { name: '类型特点', keywords: ['动态类型', '无需提前定义', '自动识别'] }
        ]
      },
      {
        name: '变量使用规则',
        keywords: ['变量使用规则', '赋值规则', '命名规范'],
        children: [
          { name: '赋值规则', keywords: ['等号=', '赋值', '数学中的等于号含义不同'] },
          { name: '命名规范', keywords: ['字母数字下划线', '不能以数字开头', '区分大小写'] },
          { name: '使用方式', keywords: ['直接写变量名', '取出数据', 'print'] }
        ]
      }
    ]
  }
}

// ==================== Methods ====================
function close() {
  emit('close')
}

async function exportImage() {
  if (!containerRef.value) return
  try {
    const canvas = await html2canvas(containerRef.value, {
      backgroundColor: '#fafbfc',
      scale: 2,
      allowTaint: false,
      useCORS: true,
      logging: false,
    })
    const link = document.createElement('a')
    link.download = `思维导图_${new Date().toISOString().slice(0, 10)}.png`
    link.href = canvas.toDataURL('image/png')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (e) {
    console.error('导出图片失败:', e)
  }
}

function handleNavigate(node) {
  emit('navigate', node)
}

function handleEdit(node) {
  emit('edit', node)
}

defineExpose({
  setData: (data) => {
    mindmapData.value = data
    loading.value = false
  },
  showLoading: () => {
    loading.value = true
    mindmapData.value = null
  },
  hideLoading: () => {
    loading.value = false
  }
})
</script>

<style scoped>
.mindmap-overlay {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 30000;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  align-items: center;
  justify-content: center;
}
.mindmap-overlay.show {
  display: flex;
}

.mindmap-modal {
  background: #fff;
  border-radius: 16px;
  width: 90vw;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

.mindmap-modal-header {
  padding: 16px 24px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.mindmap-modal-header h3 {
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.btn-export {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: pointer;
  font-weight: 600;
  transition: opacity 0.2s;
}
.btn-export:hover {
  opacity: 0.85;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  color: #999;
  padding: 0 4px;
}
.btn-close:hover {
  color: #333;
}

.mindmap-modal-body {
  flex: 1;
  overflow: auto;
  padding: 24px;
  background: #fafbfc;
}

.mindmap-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;
  gap: 12px;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e0e0e0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.mindmap-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
}

.mindmap-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px;
}

/* 夜间模式 */
:root.dark .mindmap-modal {
  background: #1e293b;
}

:root.dark .mindmap-modal-header {
  border-bottom-color: #334155;
  color: #e2e8f0;
}

:root.dark .mindmap-modal-body {
  background: #0f172a;
}

:root.dark .mindmap-loading {
  color: #94a3b8;
}

:root.dark .spinner {
  border-color: #334155;
  border-top-color: #667eea;
}

:root.dark .btn-close {
  color: #94a3b8;
}

:root.dark .btn-close:hover {
  color: #e2e8f0;
}
</style>
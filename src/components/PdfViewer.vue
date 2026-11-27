<template>
  <div class="pdf-viewer">
    <div class="pdf-toolbar">
      <button @click="prevPage" :disabled="currentPage <= 1">上一页</button>
      <span>{{ currentPage }} / {{ totalPages }}</span>
      <button @click="nextPage" :disabled="currentPage >= totalPages">下一页</button>
      <button @click="zoomOut">-</button>
      <span>{{ Math.round(scale * 100) }}%</span>
      <button @click="zoomIn">+</button>
    </div>
    <div class="pdf-container" ref="pdfContainer">
      <canvas v-for="page in renderedPages" :key="page" :ref="el => setCanvasRef(el, page)" class="pdf-page"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'

// 使用本地worker文件
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js'

const props = defineProps({
  url: {
    type: String,
    required: true
  }
})

const pdfContainer = ref(null)
const currentPage = ref(1)
const totalPages = ref(0)
const scale = ref(1.8)
const renderedPages = ref([])
const canvasRefs = {}
let pdfDoc = null

const setCanvasRef = (el, page) => {
  if (el) {
    canvasRefs[page] = el
  }
}

// 将外部URL转换为代理URL
const getProxyUrl = (url) => {
  if (url.includes('wha-whaghw.oss-cn-beijing.aliyuncs.com')) {
    // 提取OSS路径部分
    const ossPath = url.split('aliyuncs.com')[1]
    return '/oss-proxy' + ossPath
  }
  return url
}

const loadPdf = async () => {
  try {
    const proxyUrl = getProxyUrl(props.url)
    pdfDoc = await pdfjsLib.getDocument(proxyUrl).promise
    totalPages.value = pdfDoc.numPages
    renderedPages.value = [1]
    await renderPage(1)
  } catch (error) {
    console.error('PDF加载失败:', error)
  }
}

const renderPage = async (pageNum) => {
  await nextTick()
  const canvas = canvasRefs[pageNum]
  if (!canvas || !pdfDoc) return

  const page = await pdfDoc.getPage(pageNum)
  const viewport = page.getViewport({ scale: scale.value })
  
  const context = canvas.getContext('2d')
  canvas.height = viewport.height
  canvas.width = viewport.width

  await page.render({
    canvasContext: context,
    viewport: viewport
  }).promise
}

const prevPage = async () => {
  if (currentPage.value > 1) {
    currentPage.value--
    renderedPages.value = [currentPage.value]
    await renderPage(currentPage.value)
  }
}

const nextPage = async () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    renderedPages.value = [currentPage.value]
    await renderPage(currentPage.value)
  }
}

const zoomIn = async () => {
  scale.value += 0.2
  await renderPage(currentPage.value)
}

const zoomOut = async () => {
  if (scale.value > 0.5) {
    scale.value -= 0.2
    await renderPage(currentPage.value)
  }
}

onMounted(() => {
  loadPdf()
})

watch(() => props.url, () => {
  loadPdf()
})
</script>

<style scoped>
.pdf-viewer {
  width: 70%;
  margin: 0 auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--bg-card);
}

.pdf-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px;
  background-color: var(--bg-input);
  border-bottom: 1px solid var(--border-color);
}

.pdf-toolbar button {
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--bg-card);
  color: var(--text-body);
  cursor: pointer;
  font-size: 14px;
}

.pdf-toolbar button:hover:not(:disabled) {
  background-color: var(--primary);
  color: white;
  border-color: var(--primary);
}

.pdf-toolbar button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pdf-toolbar span {
  font-size: 14px;
  color: var(--text-body);
  min-width: 60px;
  text-align: center;
}

.pdf-container {
  display: flex;
  justify-content: center;
  padding: 20px;
  background-color: #f5f5f5;
  overflow: auto;
  /* max-height: 800px; */
}

.pdf-page {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  margin-bottom: 10px;
}
</style>

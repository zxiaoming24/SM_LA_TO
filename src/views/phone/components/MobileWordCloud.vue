<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import 'echarts-wordcloud'
import { getWordCloudApi } from '@/api/mainApi/draw'

const props = defineProps({
  userId: { type: [String, Number], required: true }
})

const typeNameMap = {
  MIND_MAP: '思维导图', ANIMATION: '动画', PAPER: '试卷',
  READING: '阅读资料', VIDEO: '教学视频', PPT: 'PPT',
  WORD: 'Word', CODE: '编程题', PATHPLAN: '智学路径',
  EVALUATE: '智评优化', AI_ANSWER: 'AI答疑', POST: '帖子',
  PARTNERS: '学伴', WRONG_QUESTION: '错题本'
}

const chartRef = ref(null)
let chartInstance = null
const hasData = ref(false)

const initChart = (data) => {
  if (!chartRef.value || !data.length) return

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  chartInstance = echarts.init(chartRef.value)

  const isDark = document.documentElement.classList.contains('dark')
  const tooltipBg = isDark ? 'rgba(30,41,59,0.95)' : 'rgba(255,255,255,0.95)'
  const tooltipText = isDark ? '#e2e8f0' : '#333'

  const wordData = data.map(item => ({
    name: typeNameMap[item.resourceType] || item.resourceType,
    value: item.clickCount
  }))

  const dataCount = wordData.length
  let sizeRange
  if (dataCount <= 3) sizeRange = [18, 40]
  else if (dataCount <= 6) sizeRange = [14, 32]
  else sizeRange = [12, 28]

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: tooltipBg,
      textStyle: { color: tooltipText },
      formatter: params => {
        const target = data.find(d => typeNameMap[d.resourceType] === params.name)
        return `${params.name}<br/>点击次数：${target?.clickCount || 0}<br/>占比：${target?.percentage || 0}%`
      }
    },
    series: [{
      type: 'wordCloud',
      shape: 'circle',
      left: 'center',
      top: 'center',
      width: '100%',
      height: '100%',
      sizeRange,
      rotationRange: [-30, 30],
      rotationStep: 15,
      gridSize: dataCount <= 5 ? 16 : 8,
      drawOutOfBound: false,
      shrinkToFit: true,
      textStyle: {
        fontFamily: 'Microsoft YaHei',
        fontWeight: 'bold',
        color: () => {
          const colors = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#722ED1', '#13C2C2']
          return colors[Math.floor(Math.random() * colors.length)]
        }
      },
      data: wordData
    }]
  }

  chartInstance.setOption(option)
}

const loadData = async () => {
  try {
    const res = await getWordCloudApi(props.userId)
    if (res.code && res.data && res.data.length) {
      hasData.value = true
      await nextTick()
      setTimeout(() => {
        initChart(res.data)
      }, 150)
    }
  } catch (e) {
    console.error('词云图加载失败:', e)
  }
}

const handleResize = () => chartInstance?.resize()

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})

defineExpose({ refresh: loadData })
</script>

<template>
  <div class="mobile-chart-card">
    <div class="chart-title">资源点击量词云</div>
    <div ref="chartRef" class="chart-container" style="height: 280px;"></div>
    <div v-if="!hasData" class="chart-empty">
      <van-icon name="chart-trending-o" size="32" />
      <span>暂无词云数据</span>
    </div>
  </div>
</template>

<style scoped>
.mobile-chart-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 12px;
  border: 1px solid var(--border-color);
  margin-bottom: 12px;
  position: relative;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 8px;
  padding-left: 4px;
}
.chart-container {
  width: 100%;
}
.chart-empty {
  position: absolute;
  top: 40px;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--bg-card);
  color: var(--text-gray);
  font-size: 13px;
}
</style>

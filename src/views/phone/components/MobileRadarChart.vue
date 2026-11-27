<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getRadarApi } from '@/api/mainApi/draw'

const props = defineProps({
  userId: { type: [String, Number], required: true }
})

const chartRef = ref(null)
let chartInstance = null
const hasData = ref(false)

const initChart = (resData) => {
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  chartInstance = echarts.init(chartRef.value)
  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#e2e8f0' : '#333'
  const axisColor = isDark ? '#475569' : '#e0e0e0'
  const splitLineColor = isDark ? '#475569' : 'rgb(180, 180, 180)'
  const splitAreaColors = isDark ? ['#1e293b', '#334155'] : ['#fff', '#f9f9f9']

  const defaultDimensions = [
    { name: '学术背景', max: 100 },
    { name: '学习行为', max: 100 },
    { name: '目标动机', max: 100 },
    { name: '认知能力', max: 100 },
    { name: '情绪状态', max: 100 },
    { name: '社交互动', max: 100 },
    { name: '时间管理', max: 100 },
    { name: '创新创造', max: 100 }
  ]

  const dataArr = resData.data || resData
  const name = resData.name || ''

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: '能力分析',
      left: 'center',
      top: 8,
      textStyle: { color: textColor, fontSize: 18, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark ? 'rgba(30,41,59,0.95)' : 'rgba(255,255,255,0.95)',
      textStyle: { color: textColor }
    },
    radar: {
      shape: 'circle',
      radius: '55%',
      center: ['50%', '52%'],
      indicator: defaultDimensions,
      axisName: { color: textColor, fontSize: 11 },
      axisLine: { lineStyle: { color: axisColor } },
      splitArea: { areaStyle: { color: splitAreaColors } },
      splitLine: { lineStyle: { color: splitLineColor } }
    },
    legend: {
      top: 'bottom',
      data: dataArr.map(d => d.name),
      textStyle: { color: textColor, fontSize: 11 }
    },
    series: [{
      name: '能力分布',
      type: 'radar',
      data: dataArr.map((d, i) => ({
        value: d.value,
        name: d.name,
        areaStyle: { color: i === 0 ? 'rgba(230,100,50,0.1)' : 'rgba(30,107,184,0.1)' },
        lineStyle: { color: i === 0 ? 'rgb(243,163,131)' : 'rgba(30,107,184,1)', width: 2 },
        itemStyle: { color: i === 0 ? '#e69575' : '#4A90E2' }
      }))
    }]
  }

  chartInstance.setOption(option)
}

const loadData = async () => {
  try {
    const res = await getRadarApi(props.userId)
    if (res.code && res.data) {
      hasData.value = true
      await nextTick()
      setTimeout(() => {
        initChart(res.data)
      }, 150)
    }
  } catch (e) {
    console.error('雷达图加载失败:', e)
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
    <div class="chart-title">能力雷达图</div>
    <div ref="chartRef" class="chart-container" style="height: 280px;"></div>
    <div v-if="!hasData" class="chart-empty">
      <van-icon name="chart-trending-o" size="32" />
      <span>暂无雷达图数据</span>
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

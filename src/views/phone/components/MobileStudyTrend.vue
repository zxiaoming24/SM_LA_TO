<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getSevenDaysStudyTimeApi } from '@/api/mainApi/draw'

const props = defineProps({
  userId: { type: [String, Number], required: true }
})

const chartRef = ref(null)
let chartInstance = null
const hasData = ref(false)

const initChart = (list) => {
  if (!chartRef.value || !list.length) return

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  chartInstance = echarts.init(chartRef.value)

  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#e2e8f0' : '#333'
  const axisLineColor = isDark ? '#475569' : '#ccc'
  const splitLineColor = isDark ? '#334155' : '#eee'
  const tooltipBg = isDark ? 'rgba(30,41,59,0.95)' : 'rgba(255,255,255,0.95)'

  const xAxisData = list.map(item => item.statDate.slice(5))
  const hourData = list.map(item => Number((Number(item.totalSeconds) / 3600).toFixed(2)))

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: tooltipBg,
      textStyle: { color: textColor },
      formatter: params => {
        const idx = params[0].dataIndex
        const raw = list[idx]
        const totalSec = Number(raw.totalSeconds)
        const h = Math.floor(totalSec / 3600)
        const m = Math.floor((totalSec % 3600) / 60)
        return `${raw.statDate}<br/>学习时长：${h}时${m}分`
      }
    },
    grid: { left: 45, right: 12, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: xAxisData,
      boundaryGap: false,
      axisLabel: { color: textColor, fontSize: 11 },
      axisLine: { lineStyle: { color: axisLineColor } }
    },
    yAxis: {
      type: 'value',
      name: '时长(h)',
      nameTextStyle: { color: textColor, fontSize: 11 },
      axisLabel: { color: textColor, fontSize: 11 },
      axisLine: { lineStyle: { color: axisLineColor } },
      splitLine: { lineStyle: { type: 'dashed', color: splitLineColor } }
    },
    series: [{
      name: '学习时长',
      type: 'line',
      data: hourData,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color: '#2D7DDB' },
      areaStyle: { color: 'rgba(45,125,219,0.12)' }
    }]
  }

  chartInstance.setOption(option)
}

const loadData = async () => {
  try {
    const res = await getSevenDaysStudyTimeApi(props.userId)
    if (res.code && res.data && res.data.length) {
      hasData.value = true
      await nextTick()
      setTimeout(() => {
        initChart(res.data)
      }, 150)
    }
  } catch (e) {
    console.error('学习趋势图加载失败:', e)
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
    <div class="chart-title">近七日学习时长</div>
    <div ref="chartRef" class="chart-container" style="height: 280px;"></div>
    <div v-if="!hasData" class="chart-empty">
      <van-icon name="chart-trending-o" size="32" />
      <span>暂无学习时长数据</span>
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

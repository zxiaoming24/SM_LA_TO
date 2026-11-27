<!-- @/components/planProgressMap.vue -->
<!-- draw画像页：学习计划进度 -->
<template>
  <div class="page-container">
    <h1 class="page-title">{{ title }}</h1>
    <div class="container">
      <!-- 左侧多层环形总览图 -->
      <div class="chart-card">
        <div ref="ringChartRef" class="ring-chart"></div>
      </div>
      <!-- 右侧计划列表卡片 - 添加滚动 -->
      <div class="plan-list-wrap">
        <div class="plan-list-scroll">
          <div 
            v-for="(plan, index) in plans" 
            :key="index"
            class="plan-card"
            :style="getCardStyle(index)"
          >
            <div class="plan-head">
              <div class="plan-name">{{ plan.name }}</div>
              <div class="plan-day-tag">第 {{ plan.remainingDays }} 阶段进行中</div>
            </div>
            <div class="progress-row">
              <div class="progress-bar-wrap">
                <div 
                  class="progress-fill" 
                  :style="{
                    width: plan.progress + '%',
                    background: plan.gradient || 'linear-gradient(90deg, #22d3ee, #0ea5e9)'
                  }"
                ></div>
              </div>
              <div class="percent-text">{{ plan.progress }}%</div>
            </div>
            <div class="plan-footer">已完成 {{ plan.completed }} / 总任务 {{ plan.total }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

// 定义 Props
const props = defineProps({
  title: {
    type: String,
    default: '我的学习计划进度总览'
  },
  plans: {
    type: Array,
    default: () => [
      {
        name: 'Python 算法专项计划（样例）',
        remainingDays: 12,
        progress: 68,
        completed: 30,
        total: 45,
        gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        color: ['#f093fb', '#f5576c']
      },
      {
        name: 'Java 后端实训计划（样例）',
        remainingDays: 2,
        progress: 42,
        completed: 16,
        total: 40,
        gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        color: ['#4facfe', '#00f2fe']
      },
      {
        name: 'Vue 前端学习计划（样例）',
        remainingDays: 2,
        progress: 85,
        completed: 34,
        total: 40,
        gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
        color: ['#43e97b', '#38f9d7']
      }
    ]
  },
  ringConfig: {
    type: Object,
    default: () => ({
      showTooltip: true,
      radiusGap: 16,
      startRadiusRatio: 0.20
    })
  }
})

const ringChartRef = ref(null)
let ringChartInstance = null

// 高级渐变色板
const colorPalettes = [
  // 粉紫渐变
  { colors: ['#f093fb', '#f5576c'], gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
  // 蓝青渐变
  { colors: ['#4facfe', '#00f2fe'], gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' },
  // 翠绿渐变
  { colors: ['#43e97b', '#38f9d7'], gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' },
  // 橙黄渐变
  { colors: ['#f6d365', '#fda085'], gradient: 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)' },
  // 紫蓝渐变
  { colors: ['#a18cd1', '#fbc2eb'], gradient: 'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)' },
  // 红橙渐变
  { colors: ['#ffecd2', '#fcb69f'], gradient: 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)' },
  // 青紫渐变
  { colors: ['#89f7fe', '#66a6ff'], gradient: 'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)' },
  // 粉蓝渐变
  { colors: ['#fbc2eb', '#a6c1ee'], gradient: 'linear-gradient(135deg, #fbc2eb 0%, #a6c1ee 100%)' }
]

// 获取配色方案
const getColorPalette = (index) => {
  return colorPalettes[index % colorPalettes.length]
}

// 生成渐变色（ECharts 渐变色）
const createEChartsGradient = (colorStops) => {
  return new echarts.graphic.LinearGradient(0, 0, 1, 1, 
    colorStops.map((color, index) => ({
      offset: index / (colorStops.length - 1),
      color: color
    }))
  )
}

// 生成环形图配置
const getRingOption = () => {
  const { radiusGap, startRadiusRatio } = props.ringConfig
  const totalPlans = props.plans.length
  
  // 计算每个环的半径
  const ringRadius = []
  const innerStart = 0.15
  const outerEnd = 0.85
  
  for (let i = 0; i < totalPlans; i++) {
    const inner = innerStart + (i / totalPlans) * (outerEnd - innerStart - 0.06)
    const outer = inner + (outerEnd - innerStart) / totalPlans - 0.02
    ringRadius.push([`${Math.round(inner * 100)}%`, `${Math.round(outer * 100)}%`])
  }
  ringRadius.reverse()

  const series = props.plans.map((plan, index) => {
    // 使用随机调色板颜色
    const palette = getColorPalette(index)
    const colors = palette.colors
    const gradient = createEChartsGradient(colors)
    
    return {
      name: plan.name,
      type: 'pie',
      radius: ringRadius[index] || ['76%', '90%'],
      avoidLabelOverlap: false,
      itemStyle: { 
        borderRadius: 12
      },
      label: { 
        show: false 
      },
      emphasis: {
        scale: true,
        scaleSize: 10,
        label: { show: false }
      },
      data: [
        { 
          value: plan.progress, 
          itemStyle: { 
            color: gradient,
            borderRadius: 12
          } 
        },
        { 
          value: 100 - plan.progress, 
          itemStyle: { 
            color: 'rgba(255,255,255,0.04)',
            borderRadius: 12
          } 
        }
      ]
    }
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      show: props.ringConfig.showTooltip,
      trigger: 'item',
      backgroundColor: 'rgba(15,23,42,0.92)',
      borderColor: 'rgba(255,255,255,0.08)',
      borderWidth: 1,
      borderRadius: 8,
      padding: [10, 14],
      textStyle: { 
        color: '#e2e8f0', 
        fontSize: 13,
        lineHeight: 1.6
      },
      formatter: (params) => {
        const planName = params.seriesName
        const progress = params.data.value
        return `<div style="font-weight:600;margin-bottom:4px;">${planName}</div><div style="color:#94a3b8;">进度: <span style="color:#f1f5f9;font-weight:600;">${progress}%</span></div>`
      }
    },
    legend: {
      show: false
    },
    series: series
  }
}

// 初始化图表
const initChart = () => {
  if (!ringChartRef.value) return
  
  if (ringChartInstance) {
    ringChartInstance.dispose()
  }
  
  ringChartInstance = echarts.init(ringChartRef.value)
  ringChartInstance.setOption(getRingOption())
}

// 更新图表
const updateChart = () => {
  if (ringChartInstance) {
    ringChartInstance.setOption(getRingOption(), true)
  }
}

// 窗口自适应
const handleResize = () => {
  ringChartInstance?.resize()
}

// 卡片悬浮样式
const getCardStyle = (index) => {
  return {
    animationDelay: `${index * 0.1}s`
  }
}

// 暴露方法
defineExpose({
  updateChart,
  resize: handleResize,
  getInstance: () => ringChartInstance
})

// 生命周期
onMounted(() => {
  nextTick(() => {
    initChart()
    window.addEventListener('resize', handleResize)
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  ringChartInstance?.dispose()
})

// 监听数据变化
watch(
  () => props.plans,
  () => {
    updateChart()
  },
  { deep: true }
)
</script>

<style scoped>
.page-container {
  background: transparent;
  padding: 20px;
  max-height: 100vh;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 32px;
  color: var(--text-gray);
}

.container {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
  align-items: start;
}

/* 环形总览卡片 */
.chart-card {
  background: transparent;
  backdrop-filter: none;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 4px;
  height: 360px;
  flex-shrink: 0;
}

.ring-chart {
  width: 100%;
  height: 100%;
}

/* 计划列表区域 */
.plan-list-wrap {
  display: flex;
  flex-direction: column;
  height: 360px;
  overflow: hidden;
}

.plan-list-scroll {
  flex: 1;
  overflow-y: auto;
  padding-right: 6px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 自定义滚动条样式 */
.plan-list-scroll::-webkit-scrollbar {
  width: 4px;
}

.plan-list-scroll::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 99px;
}

.plan-list-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 99px;
  transition: background 0.3s ease;
}

.plan-list-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}

/* Firefox 滚动条 */
.plan-list-scroll {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) rgba(255, 255, 255, 0.05);
}

/* 单个学习计划卡片 */
.plan-card {
  background: transparent;
  backdrop-filter: none;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 20px 24px;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.plan-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 0 22px rgba(34, 211, 238, 0.16);
  border-color: rgba(34, 211, 238, 0.25);
}

.plan-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.plan-name {
  font-size: 17px;
  font-weight: 500;
}

.plan-day-tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(34, 211, 238, 0.12);
  color: #22d3ee;
  white-space: nowrap;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.progress-bar-wrap {
  flex: 1;
  height: 7px;
  background: var(--border-color);
  border-radius: 99px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 99px;
  transition: width 0.7s cubic-bezier(0.2, 0, 0.2, 1);
}

.percent-text {
  font-size: 20px;
  font-weight: 600;
  min-width: 52px;
  text-align: right;
}

.plan-footer {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-gray);
}

/* ===== 深色模式 ===== */
.dark .page-title {
  color: #e2e8f0;
}

.dark .plan-name {
  color: #e2e8f0;
}

.dark .percent-text {
  color: #e2e8f0;
}

.dark .plan-footer {
  color: #94a3b8;
}

.dark .plan-card:hover {
  box-shadow: 0 0 22px rgba(96, 165, 250, 0.16);
  border-color: rgba(96, 165, 250, 0.25);
}

.dark .plan-list-scroll::-webkit-scrollbar-track {
  background: rgba(51, 65, 85, 0.5);
}

.dark .plan-list-scroll::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
}

.dark .plan-list-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.5);
}

.dark .plan-list-scroll {
  scrollbar-color: rgba(148, 163, 184, 0.3) rgba(51, 65, 85, 0.5);
}
</style>
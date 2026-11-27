<script setup>
import { ref, onMounted, onUnmounted, nextTick, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getUserStatisticsApi, getResourceStatisticsApi, getResourceRankApi, getResourceTrendApi } from '@/api/backstage/adIndex.js'

const userStats = reactive({
  totalUsers: 0,
  newUsers: 0,
  dailyActiveUsers: 0,
  portraitConstructedUsers: 0
})

const resourceStats = reactive({
  totalResources: 0,
  newResources: 0
})

const animatedStats = reactive({
  totalUsers: 0,
  newUsers: 0,
  dailyActiveUsers: 0,
  portraitConstructedUsers: 0,
  totalResources: 0,
  newResources: 0
})

const rankData = ref([])

const animateNumber = (key, targetValue) => {
  const startValue = animatedStats[key] || 0
  const duration = 1500
  const startTime = Date.now()
  
  const animate = () => {
    const elapsed = Date.now() - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeOut = 1 - Math.pow(1 - progress, 3)
    animatedStats[key] = Math.floor(startValue + (targetValue - startValue) * easeOut)
    
    if (progress < 1) {
      requestAnimationFrame(animate)
    } else {
      animatedStats[key] = targetValue
    }
  }
  
  requestAnimationFrame(animate)
}

const animateAllNumbers = () => {
  setTimeout(() => {
    animateNumber('totalUsers', userStats.totalUsers)
    animateNumber('newUsers', userStats.newUsers)
    animateNumber('dailyActiveUsers', userStats.dailyActiveUsers)
    animateNumber('portraitConstructedUsers', userStats.portraitConstructedUsers)
    animateNumber('totalResources', resourceStats.totalResources)
    animateNumber('newResources', resourceStats.newResources)
  }, 300)
}

const trendChartRef = ref(null)
let trendChartInstance = null

const currentRange = ref('month')
const rangeOptions = [
  { label: '近一周', value: 'week' },
  { label: '近三月', value: 'month' },
  { label: '近一年', value: 'year' }
]

const resourceTypeMap = {
  MIND_MAP: '思维导图',
  ANIMATION: '动画',
  PAPER: '试卷',
  READING: '阅读资料',
  VIDEO: '教学视频',
  PPT: 'PPT',
  WORD: 'Word',
  CODE: '编程题',
  PATHPLAN: '智学路径',
  EVALUATE: '智评优化',
  AI_ANSWER: 'AI智能助手答疑',
  POST: '帖子',
  PARTNERS: '学伴',
  WRONG_QUESTION: '错题本'
}

const resourceIconMap = {
  MIND_MAP: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  ANIMATION: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
  PAPER: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><path d="M9 3v18"/><path d="M15 3v18"/></svg>',
  READING: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
  VIDEO: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
  PPT: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
  WORD: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',
  CODE: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  PATHPLAN: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
  EVALUATE: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
  AI_ANSWER: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  POST: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
  PARTNERS: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  WRONG_QUESTION: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
}

const getResourceTypeName = (type) => {
  return resourceTypeMap[type] || type
}

const getResourceIcon = (type) => {
  return resourceIconMap[type] || '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>'
}

const fetchUserStatistics = async () => {
  try {
    const res = await getUserStatisticsApi()
    if (res.code === 1 && res.data) {
      userStats.totalUsers = res.data.totalUsers || 0
      userStats.newUsers = res.data.newUsers || 0
      userStats.dailyActiveUsers = res.data.dailyActiveUsers || 0
      userStats.portraitConstructedUsers = res.data['portraitConstructedUsers'] || 0
    }
  } catch (error) {
    console.error('获取用户统计失败:', error)
  }
}

const fetchResourceStatistics = async () => {
  try {
    const res = await getResourceStatisticsApi()
    if (res.code === 1 && res.data) {
      resourceStats.totalResources = res.data.totalResources || 0
      resourceStats.newResources = res.data.newResources || 0
    }
  } catch (error) {
    console.error('获取资源统计失败:', error)
  }
}

const fetchResourceRank = async () => {
  try {
    const res = await getResourceRankApi()
    if (res.code === 1 && res.data) {
      rankData.value = res.data
    }
  } catch (error) {
    console.error('获取资源排行失败:', error)
  }
}

const initTrendChart = () => {
  if (!trendChartRef.value) return
  trendChartInstance = echarts.init(trendChartRef.value)
  updateTrendChart()
  window.addEventListener('resize', handleChartResize)
}

const handleChartResize = () => {
  trendChartInstance?.resize()
}

const updateTrendChart = async () => {
  try {
    const res = await getResourceTrendApi(currentRange.value)
    if (res.code !== 1 || !res.data?.chartData) return

    const chartData = res.data.chartData
    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: {
            color: '#999'
          }
        },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        textStyle: {
          color: '#334155'
        }
      },
      legend: {
        data: ['生成量', '累计量'],
        top: 0,
        textStyle: {
          color: '#64748B'
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: '15%',
        containLabel: true
      },
      xAxis: [
        {
          type: 'category',
          data: chartData.dates,
          axisPointer: {
            type: 'shadow'
          },
          axisLine: {
            lineStyle: {
              color: '#e2e8f0'
            }
          },
          axisLabel: {
            color: '#64748B'
          }
        }
      ],
      yAxis: [
        {
          type: 'value',
          name: '生成量',
          min: 0,
          axisLabel: {
            color: '#64748B'
          },
          axisLine: {
            show: false
          },
          splitLine: {
            lineStyle: {
              color: '#e2e8f0',
              type: 'dashed'
            }
          }
        },
        {
          type: 'value',
          name: '累计量',
          min: 0,
          axisLabel: {
            color: '#64748B'
          },
          axisLine: {
            show: false
          },
          splitLine: {
            show: false
          }
        }
      ],
      series: [
        {
          name: '生成量',
          type: 'bar',
          data: chartData.values,
          barWidth: '50%',
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#2D7DDB' },
              { offset: 1, color: '#5094E4' }
            ]),
            borderRadius: [4, 4, 0, 0]
          },
          emphasis: {
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#4A90E2' },
                { offset: 1, color: '#6BB3F0' }
              ])
            }
          }
        },
        {
          name: '累计量',
          type: 'line',
          yAxisIndex: 1,
          data: chartData.cumulativeValues,
          smooth: true,
          lineStyle: {
            width: 3,
            color: '#E6A23C'
          },
          itemStyle: {
            color: '#E6A23C'
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(230, 162, 60, 0.3)' },
              { offset: 1, color: 'rgba(230, 162, 60, 0.05)' }
            ])
          },
          symbol: 'circle',
          symbolSize: 6
        }
      ]
    }
    trendChartInstance.setOption(option)
  } catch (error) {
    console.error('获取趋势数据失败:', error)
    ElMessage.error('获取趋势数据失败')
  }
}

const handleRangeChange = (val) => {
  currentRange.value = val
  updateTrendChart()
}

onMounted(async () => {
  await Promise.all([
    fetchUserStatistics(),
    fetchResourceStatistics(),
    fetchResourceRank()
  ])
  animateAllNumbers()
  await nextTick()
  initTrendChart()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleChartResize)
  trendChartInstance?.dispose()
})
</script>

<template>
  <div class="index-container">
    <div class="left-panel">
      <div class="stats-grid">
        <div class="stat-card user-total">
          <div class="stat-bg-decoration"></div>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ animatedStats.totalUsers }}</div>
            <div class="stat-label">用户总计</div>
          </div>
        </div>

        <div class="stat-card user-new">
          <div class="stat-bg-decoration"></div>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <line x1="20" y1="8" x2="20" y2="14"/>
              <line x1="23" y1="11" x2="17" y2="11"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ animatedStats.newUsers }}</div>
            <div class="stat-label">近七天新增用户量</div>
          </div>
        </div>

        <div class="stat-card user-active">
          <div class="stat-bg-decoration"></div>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ animatedStats.dailyActiveUsers }}</div>
            <div class="stat-label">今日活跃用户数</div>
          </div>
        </div>

        <div class="stat-card user-portrait">
          <div class="stat-bg-decoration"></div>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20.385 3.488C15.482 2.352 10.278 2.352 5.375 3.488"/>
              <path d="M12 13.954c-3.61 0-6.545-3.167-6.545-7.069 0-3.902 2.935-7.069 6.545-7.069 3.61 0 6.545 3.167 6.545 7.069 0 3.902-2.935 7.069-6.545 7.069z"/>
              <path d="M12 19.948c-4.963 0-8.987-4.396-8.987-9.809 0-5.413 4.024-9.809 8.987-9.809s8.987 4.396 8.987 9.809c0 5.413-4.024 9.809-8.987 9.809z"/>
              <path d="M12 15.956c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ animatedStats.portraitConstructedUsers }}</div>
            <div class="stat-label">已构建画像用户数</div>
          </div>
        </div>

        <div class="stat-card resource-total">
          <div class="stat-bg-decoration"></div>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ animatedStats.totalResources }}</div>
            <div class="stat-label">资源总量</div>
          </div>
        </div>

        <div class="stat-card resource-new">
          <div class="stat-bg-decoration"></div>
          <div class="stat-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="9" y1="15" x2="15" y2="15"/>
            </svg>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ animatedStats.newResources }}</div>
            <div class="stat-label">今日新增资源数</div>
          </div>
        </div>
      </div>

      <div class="chart-section">
        <div class="chart-header">
          <h3>资源生成趋势</h3>
          <div class="range-selector">
            <button
              v-for="opt in rangeOptions"
              :key="opt.value"
              :class="['range-btn', { active: currentRange === opt.value }]"
              @click="handleRangeChange(opt.value)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <div ref="trendChartRef" class="trend-chart"></div>
      </div>
    </div>

    <div class="right-panel">
      <div class="rank-section">
        <h3>Agent资源总点击量排行</h3>
        <div class="rank-list">
          <div v-for="(item, index) in rankData" :key="index" class="rank-item" :style="{ animationDelay: (index * 0.1) + 's' }">
            <div class="rank-num" :class="'rank-' + (index + 1)">
              <span v-if="index < 3" class="medal-icon">
                <svg v-if="index === 0" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                <svg v-else-if="index === 1" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              </span>
              <span v-else>{{ index + 1 }}</span>
            </div>
            <div class="rank-icon" v-html="getResourceIcon(item.resourceType)"></div>
            <div class="rank-info">
              <div class="rank-name">{{ getResourceTypeName(item.resourceType) }}</div>
              <div class="rank-bar">
                <div class="rank-progress" :style="{ width: item.percentage + '%' }"></div>
              </div>
            </div>
            <div class="rank-stats">
              <div class="rank-count">{{ item.clickCount }} 次</div>
              <div class="rank-percent">{{ item.percentage }}%</div>
            </div>
          </div>
          <div v-if="rankData.length === 0" class="empty-rank">
            <span>暂无排行数据</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.index-container {
  width: 100%;
  min-width: 1000px;
  height: 100%;
  display: flex;
  gap: 20px;
  padding: 10px;
  background-color: var(--bg-page);
  overflow: hidden;
}

.left-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.right-panel {
  width: 380px;
  flex-shrink: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 16px;
  flex-shrink: 0;
}

.stat-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  opacity: 0;
  transform: translateY(20px);
  animation: stat-card-in 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

.stat-card:nth-child(1) { animation-delay: 0.1s; }
.stat-card:nth-child(2) { animation-delay: 0.2s; }
.stat-card:nth-child(3) { animation-delay: 0.3s; }
.stat-card:nth-child(4) { animation-delay: 0.4s; }
.stat-card:nth-child(5) { animation-delay: 0.5s; }
.stat-card:nth-child(6) { animation-delay: 0.6s; }

@keyframes stat-card-in {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stat-card:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.stat-card:active {
  transform: translateY(-2px) scale(1.01);
}

.stat-bg-decoration {
  position: absolute;
  top: -50%;
  right: -50%;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  opacity: 0.06;
  z-index: 0;
}

.user-total .stat-bg-decoration {
  background: radial-gradient(circle, var(--primary) 0%, transparent 70%);
}

.resource-total .stat-bg-decoration {
  background: radial-gradient(circle, #0ea5e9 0%, transparent 70%);
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.stat-card:hover .stat-icon {
  transform: scale(1.1) rotate(5deg);
}

.user-total .stat-icon {
  background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
  color: var(--primary);
}

.user-new .stat-icon {
  background: linear-gradient(135deg, #effbe8 0%, #d9f99d 100%);
  color: var(--pass);
}

.user-active .stat-icon {
  background: linear-gradient(135deg, #fcf4e8 0%, #fde68a 100%);
  color: var(--coming);
}

.user-portrait .stat-icon {
  background: linear-gradient(135deg, #fef0f0 0%, #fecaca 100%);
  color: var(--main-delete);
}

.resource-total .stat-icon {
  background: linear-gradient(135deg, #f0f9ff 0%, #bae6fd 100%);
  color: #0ea5e9;
}

.resource-new .stat-icon {
  background: linear-gradient(135deg, #faf5ff 0%, #d8b4fe 100%);
  color: #8b5cf6;
}

.user-total .stat-bg-decoration {
  background: radial-gradient(circle, var(--primary) 0%, transparent 70%);
}

.user-new .stat-bg-decoration {
  background: radial-gradient(circle, var(--pass) 0%, transparent 70%);
}

.user-active .stat-bg-decoration {
  background: radial-gradient(circle, var(--coming) 0%, transparent 70%);
}

.user-portrait .stat-bg-decoration {
  background: radial-gradient(circle, var(--main-delete) 0%, transparent 70%);
}

.resource-total .stat-bg-decoration {
  background: radial-gradient(circle, #0ea5e9 0%, transparent 70%);
}

.resource-new .stat-bg-decoration {
  background: radial-gradient(circle, #8b5cf6 0%, transparent 70%);
}

.stat-content {
  flex: 1;
  min-width: 0;
  position: relative;
  z-index: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-title);
  line-height: 1.2;
  font-family: 'Inter', -apple-system, sans-serif;
  letter-spacing: -0.5px;
  transition: color 0.3s ease;
}

.stat-card:hover .stat-value {
  color: var(--primary);
}

.stat-label {
  font-size: 13px;
  color: var(--text-gray);
  margin-top: 4px;
}

.chart-section {
  flex: 1;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  margin: 0;
}

.range-selector {
  display: flex;
  gap: 8px;
}

.range-btn {
  padding: 6px 16px;
  font-size: 13px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: transparent;
  color: var(--text-body);
  cursor: pointer;
  transition: all 0.25s;
}

.range-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.range-btn.active {
  background: var(--grad-primary);
  border-color: var(--primary);
  color: #fff;
}

.trend-chart {
  flex: 1;
  width: 100%;
  min-height: 300px;
}

.right-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.rank-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--border-color);
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.rank-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  margin: 0 0 16px 0;
}

.rank-list {
  flex: 1;
  overflow-y: auto;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color);
  opacity: 0;
  transform: translateX(-20px);
  animation: rank-item-in 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

@keyframes rank-item-in {
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.rank-item:last-child {
  border-bottom: none;
}

.rank-item:hover {
  background: linear-gradient(90deg, rgba(45, 125, 219, 0.03) 0%, transparent 100%);
  padding-left: 8px;
  margin-left: -8px;
}

.rank-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  background: var(--bgc-light);
  color: var(--text-gray);
  flex-shrink: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rank-num:hover {
  transform: scale(1.15);
}

.rank-num.rank-1 {
  background: linear-gradient(135deg, #FCD34D 0%, #F59E0B 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4);
}

.rank-num.rank-2 {
  background: linear-gradient(135deg, #E5E7EB 0%, #9CA3AF 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(156, 163, 175, 0.4);
}

.rank-num.rank-3 {
  background: linear-gradient(135deg, #FECACA 0%, #DC2626 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(220, 38, 38, 0.4);
}

.rank-num.rank-1:hover {
  animation: gold-bounce 0.6s ease-in-out;
}

@keyframes gold-bounce {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}

.medal-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.rank-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%);
  color: var(--primary);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rank-item:hover .rank-icon {
  background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
  transform: scale(1.1) rotate(5deg);
}

.rank-info {
  flex: 1;
  min-width: 0;
}

.rank-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-body);
  margin-bottom: 6px;
  transition: color 0.3s ease;
}

.rank-item:hover .rank-name {
  color: var(--primary);
}

.rank-bar {
  height: 6px;
  background: var(--bgc-light);
  border-radius: 3px;
  overflow: hidden;
}

.rank-progress {
  height: 100%;
  background: var(--grad-primary);
  border-radius: 3px;
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.rank-progress::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.rank-stats {
  text-align: right;
  flex-shrink: 0;
}

.rank-count {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  transition: color 0.3s ease;
}

.rank-item:hover .rank-count {
  color: var(--primary);
}

.rank-percent {
  font-size: 12px;
  color: var(--text-gray);
}

.empty-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: var(--text-gray);
  font-size: 14px;
}
</style>
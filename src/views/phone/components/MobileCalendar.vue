<script setup>
import { ref, computed, onMounted } from 'vue'
import { getCanlendarApi } from '@/api/mainApi/draw'

const props = defineProps({
  userId: { type: [String, Number], required: true }
})

const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth() + 1)
const calendarData = ref([])

// 月份统计
const monthStats = computed(() => {
  const monthData = calendarData.value.filter(item => {
    const d = new Date(item.date)
    return d.getFullYear() === currentYear.value && d.getMonth() + 1 === currentMonth.value
  })
  const learningDays = monthData.filter(d => d.totalSeconds > 0).length
  const totalSeconds = monthData.reduce((sum, d) => sum + (d.totalSeconds || 0), 0)
  const totalHours = (totalSeconds / 3600).toFixed(1)
  const avgHours = learningDays > 0 ? (totalSeconds / 3600 / learningDays).toFixed(1) : '0'
  const totalReviews = monthData.reduce((sum, d) => sum + (d.reviewCount || 0), 0)
  return { learningDays, totalHours, avgHours, totalReviews }
})

// 生成日历网格
const calendarDays = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value
  const firstDay = new Date(year, month - 1, 1).getDay()
  const daysInMonth = new Date(year, month, 0).getDate()
  const days = []

  // 填充前面的空白
  for (let i = 0; i < firstDay; i++) {
    days.push({ day: null, date: null, level: 0 })
  }

  // 填充日期
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const item = calendarData.value.find(c => c.date === dateStr)
    const seconds = item?.totalSeconds || 0
    const hours = seconds / 3600
    const reviewCount = item?.reviewCount || 0
    let level = 0
    if (hours > 0) level = 1
    if (hours >= 2) level = 2
    if (hours >= 4) level = 3
    if (hours >= 6) level = 4
    days.push({ day: d, date: dateStr, level, hours: hours.toFixed(1), reviewCount })
  }

  return days
})

const weekLabels = ['日', '一', '二', '三', '四', '五', '六']

const prevMonth = () => {
  if (currentMonth.value === 1) {
    currentMonth.value = 12
    currentYear.value--
  } else {
    currentMonth.value--
  }
  loadData()
}

const nextMonth = () => {
  if (currentMonth.value === 12) {
    currentMonth.value = 1
    currentYear.value++
  } else {
    currentMonth.value++
  }
  loadData()
}

const loadData = async () => {
  const res = await getCanlendarApi(props.userId, currentYear.value, currentMonth.value)
  if (res.code) {
    const existingDates = new Set(calendarData.value.map(item => item.date))
    const newItems = res.data.filter(item => !existingDates.has(item.date))
    calendarData.value = [...calendarData.value, ...newItems].sort((a, b) => a.date.localeCompare(b.date))
  }
}

onMounted(() => loadData())

defineExpose({ refresh: loadData })
</script>

<template>
  <div class="mobile-chart-card">
    <div class="chart-title">学习日历</div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-item">
        <span class="stat-value">{{ monthStats.learningDays }}</span>
        <span class="stat-label">学习天数</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ monthStats.avgHours }}h</span>
        <span class="stat-label">日均时长</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ monthStats.totalHours }}h</span>
        <span class="stat-label">总时长</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ monthStats.totalReviews }}</span>
        <span class="stat-label">复习次数</span>
      </div>
    </div>

    <!-- 月份切换 -->
    <div class="month-nav">
      <button class="nav-btn" @click="prevMonth">
        <van-icon name="arrow-left" />
      </button>
      <span class="month-text">{{ currentYear }}年{{ currentMonth }}月</span>
      <button class="nav-btn" @click="nextMonth">
        <van-icon name="arrow" />
      </button>
    </div>

    <!-- 日历网格 -->
    <div class="calendar-grid">
      <div class="week-header">
        <span v-for="w in weekLabels" :key="w" class="week-label">{{ w }}</span>
      </div>
      <div class="days-grid">
        <div
          v-for="(day, idx) in calendarDays"
          :key="idx"
          class="day-cell"
          :class="{
            'level-1': day.level === 1,
            'level-2': day.level === 2,
            'level-3': day.level === 3,
            'level-4': day.level === 4,
            'day-unqualified': day.day && (day.hours <= 0.5 || day.reviewCount <= 1) && (day.hours > 0 || day.reviewCount > 0)
          }"
        >
          <span v-if="day.day && day.reviewCount > 0" class="day-reviews" :class="{ 'review-low': day.reviewCount <= 1 }">复习{{ day.reviewCount > 99 ? '99次+' : day.reviewCount+'次' }}</span>
          <span v-if="day.day" class="day-num">{{ day.day }}</span>
          <span v-if="day.day && day.hours > 0" class="day-hours">{{ day.hours }}h</span>
        </div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="legend">
      <span class="legend-label">少</span>
      <span class="legend-box level-0"></span>
      <span class="legend-box level-1"></span>
      <span class="legend-box level-2"></span>
      <span class="legend-box level-3"></span>
      <span class="legend-box level-4"></span>
      <span class="legend-label">多</span>
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
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 12px;
  padding-left: 4px;
}

.stats-row {
  display: flex;
  justify-content: space-around;
  margin-bottom: 16px;
  padding: 10px 0;
  background: var(--primary-light);
  border-radius: var(--radius-md);
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--primary);
}
.stat-label {
  font-size: 11px;
  color: var(--text-gray);
}

.month-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 12px;
}
.nav-btn {
  background: none;
  border: 1px solid var(--border-color);
  border-radius: 50%;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-body);
}
.nav-btn:active {
  background: var(--bg-hover);
}
.month-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-title);
}

.calendar-grid {
  margin-bottom: 8px;
}
.week-header {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: 4px;
}
.week-label {
  text-align: center;
  font-size: 11px;
  color: var(--text-gray);
  padding: 4px 0;
}
.days-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 3px;
}
.day-cell {
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--bg-hover);
  font-size: 14px;
  overflow: hidden;
  white-space: nowrap;
  border: 1px solid transparent;
  box-sizing: border-box;
}
.day-cell.day-unqualified {
  border-color: var(--main-delete);
}
.day-cell.level-1 { background: rgba(45, 125, 219, 0.15); }
.day-cell.level-2 { background: rgba(45, 125, 219, 0.3); }
.day-cell.level-3 { background: rgba(45, 125, 219, 0.5); }
.day-cell.level-4 { background: rgba(45, 125, 219, 0.75); }
.day-num {
  color: var(--text-body);
  font-weight: 700;
}
.level-3 .day-num,
.level-4 .day-num {
  color: #fff;
}
.day-hours {
  font-size: 9px;
  color: var(--text-gray);
}
.level-3 .day-hours,
.level-4 .day-hours {
  color: rgba(255, 255, 255, 0.8);
}
.day-reviews {
  font-size: 8px;
  color: var(--pass);
}
.day-reviews.review-low {
  color: var(--main-delete);
}
.level-3 .day-reviews,
.level-4 .day-reviews {
  font-weight: 900;
  color: var(--pass-shadow);
}

.legend {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 3px;
  padding: 4px 0;
}
.legend-label {
  font-size: 11px;
  color: var(--text-gray);
  margin: 0 4px;
}
.legend-box {
  width: 14px;
  height: 14px;
  border-radius: 3px;
}
.legend-box.level-0 { background: var(--bg-hover); }
.legend-box.level-1 { background: rgba(45, 125, 219, 0.15); }
.legend-box.level-2 { background: rgba(45, 125, 219, 0.3); }
.legend-box.level-3 { background: rgba(45, 125, 219, 0.5); }
.legend-box.level-4 { background: rgba(45, 125, 219, 0.75); }
</style>

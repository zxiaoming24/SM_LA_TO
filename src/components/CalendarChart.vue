<!-- src/components/CalendarChart.vue -->
 <!-- 画像页：日历 -->
<template>
  <div class="calendar-container" ref="containerRef">
    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-item">
        <svg class="stat-icon" viewBox="0 0 1024 1024" width="20" height="20">
          <path d="M870.4 12.8H153.6A140.9024 140.9024 0 0 0 12.8 153.6v716.8A140.9024 140.9024 0 0 0 153.6 1011.2h504.32a38.4 38.4 0 0 0 0-76.8H153.6c-35.2768 0-64-28.7232-64-64V153.6c0-35.2768 28.7232-64 64-64h716.8c35.2768 0 64 28.7232 64 64v716.8c0 35.2768-28.7232 64-64 64h-11.4688a38.4 38.4 0 0 0 0 76.8H870.4A140.9024 140.9024 0 0 0 1011.2 870.4V153.6A140.9024 140.9024 0 0 0 870.4 12.8z" fill="currentColor"/>
          <path d="M256 371.2a38.4 38.4 0 0 0-38.4 38.4v409.6a38.4 38.4 0 0 0 76.8 0V409.6A38.4 38.4 0 0 0 256 371.2zM473.6 256v512a38.4 38.4 0 0 0 76.8 0V256a38.4 38.4 0 0 0-76.8 0zM768 576a38.4 38.4 0 0 0-38.4 38.4v204.8a38.4 38.4 0 0 0 76.8 0v-204.8a38.4 38.4 0 0 0-38.4-38.4zM257.024 217.6h-0.512c-21.1968 0-38.144 17.2032-38.144 38.4s17.4592 38.4 38.656 38.4a38.4 38.4 0 0 0 0-76.8z" fill="currentColor"/>
        </svg>
        <div class="stat-info">
          <span class="stat-label">本月学习天数</span>
          <span class="stat-value">{{ monthStats.learningDays }}天</span>
        </div>
      </div>
      <div class="stat-item">
        <svg class="stat-icon" viewBox="0 0 1024 1024" width="20" height="20">
          <path d="M896 896H96a32 32 0 0 1-32-32V224a32 32 0 0 1 64 0v608h768a32 32 0 1 1 0 64z" fill="currentColor"/>
          <path d="M247.008 640a32 32 0 0 1-20.992-56.192l200.992-174.24a32 32 0 0 1 42.272 0.288l172.128 153.44 229.088-246.304a32 32 0 0 1 46.88 43.616l-250.432 269.216a31.936 31.936 0 0 1-44.704 2.08l-174.56-155.52-179.744 155.84a31.872 31.872 0 0 1-20.928 7.776z" fill="currentColor"/>
        </svg>
        <div class="stat-info">
          <span class="stat-label">本月日均学习时长</span>
          <span class="stat-value">{{ monthStats.avgHours }}h</span>
        </div>
      </div>
      <div class="stat-item">
        <svg class="stat-icon" viewBox="0 0 1024 1024" width="20" height="20">
          <path d="M784 304C710.4 233.6 620.8 195.2 512 192c-108.8 3.2-198.4 41.6-272 112S131.2 467.2 128 576c3.2 108.8 41.6 198.4 112 272S403.2 956.8 512 960c108.8-3.2 198.4-41.6 272-112S892.8 684.8 896 576c-3.2-108.8-41.6-198.4-112-272z m-44.8 499.2C678.4 864 601.6 892.8 512 896c-89.6-3.2-166.4-32-227.2-92.8C224 742.4 195.2 665.6 192 576c3.2-89.6 32-166.4 92.8-227.2C345.6 288 422.4 259.2 512 256c89.6 3.2 166.4 32 227.2 92.8C800 409.6 832 483.2 832 576c-3.2 89.6-32 166.4-92.8 227.2z" fill="currentColor"/>
          <path d="M512 320c9.6 0 16 3.2 22.4 9.6 6.4 6.4 9.6 12.8 9.6 22.4V576c0 9.6-3.2 16-9.6 22.4-6.4 6.4-12.8 9.6-22.4 9.6-9.6 0-16-3.2-22.4-9.6-6.4-6.4-9.6-12.8-9.6-22.4V352c0-9.6 3.2-16 9.6-22.4 6.4-6.4 12.8-9.6 22.4-9.6z" fill="currentColor"/>
          <path d="M448 576c0 19.2 6.4 32 19.2 44.8 12.8 12.8 25.6 19.2 44.8 19.2 19.2 0 32-6.4 44.8-19.2 12.8-12.8 19.2-25.6 19.2-44.8 0-19.2-6.4-32-19.2-44.8-12.8-12.8-25.6-19.2-44.8-19.2-19.2 0-32 6.4-44.8 19.2-12.8 12.8-19.2 25.6-19.2 44.8zM544 128v128h-64V128H384c-9.6 0-16-3.2-22.4-9.6-6.4-6.4-9.6-12.8-9.6-22.4 0-9.6 3.2-16 9.6-22.4 6.4-6.4 12.8-9.6 22.4-9.6h256c9.6 0 16 3.2 22.4 9.6 6.4 6.4 9.6 12.8 9.6 22.4 0 9.6-3.2 16-9.6 22.4-6.4 6.4-12.8 9.6-22.4 9.6H544z" fill="currentColor"/>
        </svg>
        <div class="stat-info">
          <span class="stat-label">本月总学习时长</span>
          <span class="stat-value">{{ monthStats.totalHours }}h</span>
        </div>
      </div>
      <div class="stat-item">
        <svg class="stat-icon" viewBox="0 0 1024 1024" width="20" height="20">
          <path d="M512 14.222222A497.777778 497.777778 0 1 0 1009.777778 512a42.666667 42.666667 0 1 0-85.333334 0A412.444444 412.444444 0 1 1 512 99.555556a42.666667 42.666667 0 1 0 0-85.333334z" fill="currentColor"/>
          <path d="M505.116444 505.742222L374.328889 374.897778a42.666667 42.666667 0 0 0-60.359111 60.302222l160.881778 160.995556a42.666667 42.666667 0 0 0 60.359111 0l402.261333-402.318223a42.666667 42.666667 0 1 0-60.302222-60.302222l-372.110222 372.053333z" fill="currentColor"/>
        </svg>
        <div class="stat-info">
          <span class="stat-label">本月总复习次数</span>
          <span class="stat-value">{{ monthStats.totalReviews }}次</span>
        </div>
      </div>
    </div>

    <!-- 头部 -->
    <div class="calendar-header">
      <button class="nav-btn" @click="goToPrevMonth">
        ‹
      </button>
      <span class="calendar-title">
        <svg class="header-icon" viewBox="0 0 1024 1024" width="20" height="20">
          <path d="M725.333333 170.666667h74.709334C864.853333 170.666667 917.333333 223.189333 917.333333 288.096V799.893333C917.333333 864.757333 864.832 917.333333 800.042667 917.333333H223.957333C159.146667 917.333333 106.666667 864.810667 106.666667 799.904V288.106667C106.666667 223.242667 159.168 170.666667 223.957333 170.666667H298.666667v-32a32 32 0 0 1 64 0v32h298.666666v-32a32 32 0 0 1 64 0v32z m0 64v32a32 32 0 0 1-64 0v-32H362.666667v32a32 32 0 0 1-64 0v-32h-74.709334A53.354667 53.354667 0 0 0 170.666667 288.096V799.893333A53.301333 53.301333 0 0 0 223.957333 853.333333h576.085334A53.354667 53.354667 0 0 0 853.333333 799.904V288.106667A53.301333 53.301333 0 0 0 800.042667 234.666667H725.333333z m-10.666666 224a32 32 0 0 1 0 64H309.333333a32 32 0 0 1 0-64h405.333334zM586.666667 618.666667a32 32 0 0 1 0 64H309.333333a32 32 0 0 1 0-64h277.333334z" fill="currentColor"/>
        </svg>
        {{ currentYear }}年 {{ currentMonth + 1 }}月
      </span>
      <button class="nav-btn" @click="goToNextMonth">
        ›
      </button>
    </div>

    <!-- 达标条件 -->
    <div class="conditions">
      <span class="condition-item">
        <span class="condition-dot time-dot"></span>
        时长达标 > {{ timeThreshold }}h
      </span>
      <span class="condition-item">
        <span class="condition-dot review-dot"></span>
        复习达标 > {{ reviewThreshold }}次
      </span>
    </div>

    <!-- 星期行 -->
    <div class="weekday-row">
      <div
        v-for="(day, index) in weekDays"
        :key="index"
        class="weekday"
        :class="{ weekend: index === 5 || index === 6 }"
      >
        {{ day }}
      </div>
    </div>

    <!-- 日历网格 -->
    <div class="grid-wrapper">
      <div
        v-for="(row, rowIndex) in calendarRows"
        :key="rowIndex"
        class="grid-row"
      >
        <div
          v-for="day in row"
          :key="day.date"
          class="day-cell"
          :class="{
            'is-today': day.isToday,
            'is-other-month': !day.isCurrentMonth,
            'has-data': day.hasData,
            'empty': day.isEmpty,
            'weekend': day.weekday === 0 || day.weekday === 6,
          }"
          @click="handleDayClick(day)"
          @mouseenter="handleMouseEnter(day, $event)"
          @mousemove="handleMouseMove($event)"
          @mouseleave="handleMouseLeave"
        >
          <span class="day-number">{{ day.isEmpty ? '' : day.day }}</span>

          <div v-if="!day.isEmpty" class="day-content">
            <template v-if="day.showTimeIcon || day.showReviewIcon">
              <!-- 两个图标并排 -->
              <div v-if="day.showTimeIcon && day.showReviewIcon" class="icons-row">
                <div class="icon-wrapper time">
                  <svg class="icon-svg" viewBox="0 0 1024 1024" width="16" height="16">
                    <path d="M784 304C710.4 233.6 620.8 195.2 512 192c-108.8 3.2-198.4 41.6-272 112S131.2 467.2 128 576c3.2 108.8 41.6 198.4 112 272S403.2 956.8 512 960c108.8-3.2 198.4-41.6 272-112S892.8 684.8 896 576c-3.2-108.8-41.6-198.4-112-272z m-44.8 499.2C678.4 864 601.6 892.8 512 896c-89.6-3.2-166.4-32-227.2-92.8C224 742.4 195.2 665.6 192 576c3.2-89.6 32-166.4 92.8-227.2C345.6 288 422.4 259.2 512 256c89.6 3.2 166.4 32 227.2 92.8C800 409.6 832 483.2 832 576c-3.2 89.6-32 166.4-92.8 227.2z" fill="currentColor"/>
                    <path d="M512 320c9.6 0 16 3.2 22.4 9.6 6.4 6.4 9.6 12.8 9.6 22.4V576c0 9.6-3.2 16-9.6 22.4-6.4 6.4-12.8 9.6-22.4 9.6-9.6 0-16-3.2-22.4-9.6-6.4-6.4-9.6-12.8-9.6-22.4V352c0-9.6 3.2-16 9.6-22.4 6.4-6.4 12.8-9.6 22.4-9.6z" fill="currentColor"/>
                    <path d="M448 576c0 19.2 6.4 32 19.2 44.8 12.8 12.8 25.6 19.2 44.8 19.2 19.2 0 32-6.4 44.8-19.2 12.8-12.8 19.2-25.6 19.2-44.8 0-19.2-6.4-32-19.2-44.8-12.8-12.8-25.6-19.2-44.8-19.2-19.2 0-32 6.4-44.8 19.2-12.8 12.8-19.2 25.6-19.2 44.8zM544 128v128h-64V128H384c-9.6 0-16-3.2-22.4-9.6-6.4-6.4-9.6-12.8-9.6-22.4 0-9.6 3.2-16 9.6-22.4 6.4-6.4 12.8-9.6 22.4-9.6h256c9.6 0 16 3.2 22.4 9.6 6.4 6.4 9.6 12.8 9.6 22.4 0 9.6-3.2 16-9.6 22.4-6.4 6.4-12.8 9.6-22.4 9.6H544z" fill="currentColor"/>
                  </svg>
                  <span class="icon-label">{{ day.studyHours.toFixed(1) }}h</span>
                </div>
                <div class="icon-wrapper review">
                  <svg class="icon-svg" viewBox="0 0 1024 1024" width="16" height="16">
                    <path d="M512 14.222222A497.777778 497.777778 0 1 0 1009.777778 512a42.666667 42.666667 0 1 0-85.333334 0A412.444444 412.444444 0 1 1 512 99.555556a42.666667 42.666667 0 1 0 0-85.333334z" fill="currentColor"/>
                    <path d="M505.116444 505.742222L374.328889 374.897778a42.666667 42.666667 0 0 0-60.359111 60.302222l160.881778 160.995556a42.666667 42.666667 0 0 0 60.359111 0l402.261333-402.318223a42.666667 42.666667 0 1 0-60.302222-60.302222l-372.110222 372.053333z" fill="currentColor"/>
                  </svg>
                  <span class="icon-label">{{ day.reviewCount }}次</span>
                </div>
              </div>
              <!-- 单个图标 -->
              <div v-else class="icon-wrapper" :class="day.showTimeIcon ? 'time' : 'review'">
                <svg v-if="day.showTimeIcon" class="icon-svg" viewBox="0 0 1024 1024" width="18" height="18">
                  <path d="M784 304C710.4 233.6 620.8 195.2 512 192c-108.8 3.2-198.4 41.6-272 112S131.2 467.2 128 576c3.2 108.8 41.6 198.4 112 272S403.2 956.8 512 960c108.8-3.2 198.4-41.6 272-112S892.8 684.8 896 576c-3.2-108.8-41.6-198.4-112-272z m-44.8 499.2C678.4 864 601.6 892.8 512 896c-89.6-3.2-166.4-32-227.2-92.8C224 742.4 195.2 665.6 192 576c3.2-89.6 32-166.4 92.8-227.2C345.6 288 422.4 259.2 512 256c89.6 3.2 166.4 32 227.2 92.8C800 409.6 832 483.2 832 576c-3.2 89.6-32 166.4-92.8 227.2z" fill="currentColor"/>
                  <path d="M512 320c9.6 0 16 3.2 22.4 9.6 6.4 6.4 9.6 12.8 9.6 22.4V576c0 9.6-3.2 16-9.6 22.4-6.4 6.4-12.8 9.6-22.4 9.6-9.6 0-16-3.2-22.4-9.6-6.4-6.4-9.6-12.8-9.6-22.4V352c0-9.6 3.2-16 9.6-22.4 6.4-6.4 12.8-9.6 22.4-9.6z" fill="currentColor"/>
                  <path d="M448 576c0 19.2 6.4 32 19.2 44.8 12.8 12.8 25.6 19.2 44.8 19.2 19.2 0 32-6.4 44.8-19.2 12.8-12.8 19.2-25.6 19.2-44.8 0-19.2-6.4-32-19.2-44.8-12.8-12.8-25.6-19.2-44.8-19.2-19.2 0-32 6.4-44.8 19.2-12.8 12.8-19.2 25.6-19.2 44.8zM544 128v128h-64V128H384c-9.6 0-16-3.2-22.4-9.6-6.4-6.4-9.6-12.8-9.6-22.4 0-9.6 3.2-16 9.6-22.4 6.4-6.4 12.8-9.6 22.4-9.6h256c9.6 0 16 3.2 22.4 9.6 6.4 6.4 9.6 12.8 9.6 22.4 0 9.6-3.2 16-9.6 22.4-6.4 6.4-12.8 9.6-22.4 9.6H544z" fill="currentColor"/>
                </svg>
                <svg v-else class="icon-svg" viewBox="0 0 1024 1024" width="18" height="18">
                  <path d="M512 14.222222A497.777778 497.777778 0 1 0 1009.777778 512a42.666667 42.666667 0 1 0-85.333334 0A412.444444 412.444444 0 1 1 512 99.555556a42.666667 42.666667 0 1 0 0-85.333334z" fill="currentColor"/>
                  <path d="M505.116444 505.742222L374.328889 374.897778a42.666667 42.666667 0 0 0-60.359111 60.302222l160.881778 160.995556a42.666667 42.666667 0 0 0 60.359111 0l402.261333-402.318223a42.666667 42.666667 0 1 0-60.302222-60.302222l-372.110222 372.053333z" fill="currentColor"/>
                </svg>
                <span class="icon-label">
                  {{ day.showTimeIcon ? day.studyHours.toFixed(1) + 'h' : day.reviewCount + '次' }}
                </span>
              </div>
            </template>
            <div v-else-if="day.isCurrentMonth" class="empty-state">·</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'

// ======================= Props ======================
const props = defineProps({
  data: {
    type: Array,
    default: () => [],
  },
  timeThreshold: {
    type: Number,
    default: 0.5,
  },
  reviewThreshold: {
    type: Number,
    default: 1,
  },
  firstDayOfWeek: {
    type: Number,
    default: 1,
  },
  weekDays: {
    type: Array,
    default: () => ['一', '二', '三', '四', '五', '六', '日'],
  },
  currentDate: {
    type: String,
    default: '',
  },
})

// ======================= Emits ======================
const emit = defineEmits([
  'day-click',
  'month-change',
  'data-request',
])

// ======================= 状态 ======================
const containerRef = ref(null)
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth())

// Tooltip 状态
const tooltip = ref(null)
const tooltipTimer = ref(null)

// ======================= 数据映射 ======================
const dataMap = ref(new Map())

const updateDataMap = () => {
  dataMap.value = new Map(props.data.map(item => [item.date, item]))
}

const getItem = (dateStr) => {
  return dataMap.value.get(dateStr) || null
}

const getStudyHours = (dateStr) => {
  const item = getItem(dateStr)
  return item ? (item.totalSeconds || 0) / 3600 : 0
}

const getReviewCount = (dateStr) => {
  const item = getItem(dateStr)
  return item ? (item.reviewCount || 0) : 0
}

const hasData = (dateStr) => {
  return dataMap.value.has(dateStr)
}

const shouldShowTimeIcon = (dateStr) => {
  return getStudyHours(dateStr) > props.timeThreshold
}

const shouldShowReviewIcon = (dateStr) => {
  return getReviewCount(dateStr) > props.reviewThreshold
}

// ======================= 月份统计 ======================
const monthStats = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value
  const monthStr = `${year}-${String(month + 1).padStart(2, '0')}`
  
  const monthData = props.data.filter(item => 
    item.date.startsWith(monthStr) && item.totalSeconds > 0
  )
  
  const learningDays = monthData.length
  const totalSeconds = monthData.reduce((sum, item) => sum + item.totalSeconds, 0)
  const totalHours = totalSeconds / 3600
  const totalReviews = monthData.reduce((sum, item) => sum + item.reviewCount, 0)
  const avgHours = learningDays > 0 ? totalHours / learningDays : 0

  return {
    learningDays,
    totalHours: totalHours.toFixed(1),
    totalReviews,
    avgHours: avgHours.toFixed(1),
  }
})

// ======================= 生成日历数据 ======================
const calendarRows = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value

  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

  const offset = (firstDay - props.firstDayOfWeek + 7) % 7
  const days = []

  // 上个月填充
  const prevMonth = month === 0 ? 11 : month - 1
  const prevYear = month === 0 ? year - 1 : year
  const daysInPrevMonth = new Date(prevYear, prevMonth + 1, 0).getDate()

  for (let i = offset - 1; i >= 0; i--) {
    const day = daysInPrevMonth - i
    const dateStr = `${prevYear}-${String(prevMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    days.push(createDayData(dateStr, day, false, prevYear, prevMonth))
  }

  // 当前月
  for (let i = 1; i <= daysInMonth; i++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`
    const isToday = dateStr === todayStr
    days.push(createDayData(dateStr, i, true, year, month, isToday))
  }

  // 下个月填充
  const remaining = 42 - days.length
  const nextMonth = month === 11 ? 0 : month + 1
  const nextYear = month === 11 ? year + 1 : year

  for (let i = 1; i <= remaining; i++) {
    const dateStr = `${nextYear}-${String(nextMonth + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`
    days.push(createDayData(dateStr, i, false, nextYear, nextMonth))
  }

  const rows = []
  for (let i = 0; i < days.length; i += 7) {
    rows.push(days.slice(i, i + 7))
  }

  return rows
})

// 创建日期数据对象
const createDayData = (dateStr, day, isCurrentMonth, year, month, isToday = false) => {
  const dateObj = new Date(year, month, day)
  const hours = getStudyHours(dateStr)
  const count = getReviewCount(dateStr)

  return {
    day,
    date: dateStr,
    isCurrentMonth,
    isToday,
    isEmpty: false,
    hasData: hasData(dateStr),
    studyHours: hours,
    reviewCount: count,
    showTimeIcon: shouldShowTimeIcon(dateStr),
    showReviewIcon: shouldShowReviewIcon(dateStr),
    weekday: dateObj.getDay(),
    dataItem: getItem(dateStr),
  }
}

// ======================= Tooltip 方法 ======================
const getTooltipContent = (day) => {
  if (!day.dataItem) {
    return `<div style="font-weight:500;">${day.date}</div><div style="color:#aaa;font-size:12px;">暂无学习数据</div>`
  }

  const item = day.dataItem
  const hours = item.totalSeconds / 3600
  const reviewCount = item.reviewCount || 0
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const dateObj = new Date(day.date)
  const weekday = weekdays[dateObj.getDay()]

  let content = `
    <div style="font-weight:600;font-size:14px;margin-bottom:4px;">${day.date}</div>
    <div style="color:#aaa;font-size:12px;margin-bottom:4px;">${weekday}</div>
    <div style="display:flex;flex-direction:column;gap:2px;font-size:13px;">
  `

  if (item.totalSeconds > 0) {
    const isQualified = hours > props.timeThreshold
    content += `
      <div>
        学习时长: <span style="color:${isQualified ? '#52c41a' : '#ff4d4f'};font-weight:500;">${hours.toFixed(1)}</span> 小时
        ${isQualified ? ' ✅' : ' ❌'}
      </div>
    `
  } else {
    content += `<div style="color:#aaa;">学习时长: 无数据</div>`
  }

  if (reviewCount > 0) {
    const isQualified = reviewCount > props.reviewThreshold
    content += `
      <div style="margin-top:2px;">
        复习次数: <span style="color:${isQualified ? '#52c41a' : '#ff4d4f'};font-weight:500;">${reviewCount}</span> 次
        ${isQualified ? ' ✅' : ' ❌'}
      </div>
    `
  } else {
    content += `<div style="color:#aaa;margin-top:2px;">复习次数: 无数据</div>`
  }

  if (item.firstLogin) {
    content += `<div style="color:#aaa;font-size:12px;margin-top:2px;">首次: ${item.firstLogin}</div>`
  }
  if (item.lastActive) {
    content += `<div style="color:#aaa;font-size:12px;">最后: ${item.lastActive}</div>`
  }

  content += `</div>`
  return content
}

const showTooltip = (event, content) => {
  if (!content) return

  clearTimeout(tooltipTimer.value)
  tooltipTimer.value = setTimeout(() => {
    createTooltip()
    const el = tooltip.value
    el.innerHTML = content
    el.style.display = 'block'
    el.style.opacity = '1'

    const rect = el.getBoundingClientRect()
    const padding = 15
    let left = event.clientX + 15
    let top = event.clientY + 15

    if (left + rect.width + padding > window.innerWidth) {
      left = event.clientX - rect.width - 15
    }
    if (left < padding) left = padding
    if (top + rect.height + padding > window.innerHeight) {
      top = event.clientY - rect.height - 15
    }
    if (top < padding) top = padding

    el.style.left = left + 'px'
    el.style.top = top + 'px'
  }, 300)
}

const moveTooltip = (event) => {
  if (!tooltip.value) return
  const content = tooltip.value.innerHTML
  if (content) {
    const el = tooltip.value
    const rect = el.getBoundingClientRect()
    const padding = 15
    let left = event.clientX + 15
    let top = event.clientY + 15

    if (left + rect.width + padding > window.innerWidth) {
      left = event.clientX - rect.width - 15
    }
    if (left < padding) left = padding
    if (top + rect.height + padding > window.innerHeight) {
      top = event.clientY - rect.height - 15
    }
    if (top < padding) top = padding

    el.style.left = left + 'px'
    el.style.top = top + 'px'
  }
}

const hideTooltip = () => {
  clearTimeout(tooltipTimer.value)
  if (tooltip.value) {
    tooltip.value.style.display = 'none'
    tooltip.value.style.opacity = '0'
  }
}

const createTooltip = () => {
  if (tooltip.value) return

  const el = document.createElement('div')
  el.className = 'calendar-tooltip'
  el.style.cssText = `
    position: fixed;
    display: none;
    background: rgba(0, 0, 0, 0.88);
    color: #fff;
    padding: 14px 18px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.8;
    max-width: 320px;
    min-width: 200px;
    pointer-events: none;
    z-index: 9999;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(8px);
    transition: opacity 0.15s ease;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    border: 1px solid rgba(255, 255, 255, 0.1);
  `
  document.body.appendChild(el)
  tooltip.value = el
}

// ======================= 事件处理 ======================
const handleDayClick = (day) => {
  if (day.isEmpty) return
  emit('day-click', {
    date: day.date,
    data: day.dataItem,
    studyHours: day.studyHours,
    reviewCount: day.reviewCount,
  })
}

const handleMouseEnter = (day, event) => {
  if (day.isEmpty) return
  const content = getTooltipContent(day)
  showTooltip(event, content)
}

const handleMouseMove = (event) => {
  moveTooltip(event)
}

const handleMouseLeave = () => {
  hideTooltip()
}

const goToPrevMonth = () => {
  if (currentMonth.value === 0) {
    currentMonth.value = 11
    currentYear.value--
  } else {
    currentMonth.value--
  }
  emitMonthChange()
}

const goToNextMonth = () => {
  if (currentMonth.value === 11) {
    currentMonth.value = 0
    currentYear.value++
  } else {
    currentMonth.value++
  }
  emitMonthChange()
}

const goToToday = () => {
  const today = new Date()
  currentYear.value = today.getFullYear()
  currentMonth.value = today.getMonth()
  emitMonthChange()
}

const goToMonth = (year, month) => {
  currentYear.value = year
  currentMonth.value = month
  emitMonthChange()
}

const emitMonthChange = () => {
  emit('data-request', {
    year: currentYear.value,
    month: currentMonth.value,
  })
  emit('month-change', {
    year: currentYear.value,
    month: currentMonth.value,
  })
}

// ======================= 生命周期 ======================

watch(
  () => props.data,
  () => {
    updateDataMap()
  },
  { deep: true, immediate: true }
)

watch(
  () => props.currentDate,
  (val) => {
    if (val) {
      const parts = val.split('-').map(Number)
      currentYear.value = parts[0]
      currentMonth.value = parts[1] - 1
    }
  },
  { immediate: true }
)

onMounted(() => {
  updateDataMap()
  if (props.currentDate) {
    const parts = props.currentDate.split('-').map(Number)
    currentYear.value = parts[0]
    currentMonth.value = parts[1] - 1
  }
})

onBeforeUnmount(() => {
  if (tooltip.value && tooltip.value.parentNode) {
    tooltip.value.parentNode.removeChild(tooltip.value)
  }
  tooltip.value = null
  clearTimeout(tooltipTimer.value)
})

// ======================= 暴露方法 ======================
defineExpose({
  goToPrevMonth,
  goToNextMonth,
  goToToday,
  goToMonth,
  getCurrentDate: () => ({
    year: currentYear.value,
    month: currentMonth.value,
  }),
  refresh: () => {
    updateDataMap()
  },
  getTooltipContent,
})
</script>

<style scoped>
.calendar-container {
  border: 1px solid var(--border-color);
  width: 100%;
  height: 100%;
  padding: 12px 15px 10px 15px;
  background: #ffffff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  overflow: hidden;
  position: relative;
  min-height: 420px;
}

/* ===== 统计卡片 ===== */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  min-width: 0;
}

.stat-icon {
  flex-shrink: 0;
  color: #1890ff;
}

.stat-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.stat-label {
  font-size: 10px;
  color: #999;
  line-height: 1.2;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  line-height: 1.3;
}

/* ===== 头部 ===== */
.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0 6px 0;
  flex-shrink: 0;
}

.nav-btn {
  background: none;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 2px 12px;
  cursor: pointer;
  font-size: 16px;
  color: #333;
  transition: all 0.2s;
  line-height: 1.4;
}

.nav-btn:hover {
  background: #f0f2f5;
  border-color: #d0d0d0;
}

.calendar-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-icon {
  color: #1890ff;
}

/* ===== 达标条件 ===== */
.conditions {
  display: flex;
  gap: 16px;
  padding: 4px 0 6px 0;
  flex-shrink: 0;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 4px;
}

.condition-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #666;
}

.condition-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.condition-dot.time-dot {
  background: #1890ff;
  opacity: 0.5;
  border: 1px solid #1890ff;
}

.condition-dot.review-dot {
  background: #52c41a;
  opacity: 0.5;
  border: 1px solid #52c41a;
}

/* ===== 星期行 ===== */
.weekday-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  padding: 4px 0 4px 0;
  flex-shrink: 0;
}

.weekday {
  text-align: center;
  font-weight: 500;
  color: #666;
  font-size: 11px;
  padding: 2px 0;
}

.weekday.weekend {
  color: #ff4d4f;
}

/* ===== 网格 ===== */
.grid-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
}

.grid-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  flex: 1;
  min-height: 0;
}

/* ===== 单元格 ===== */
.day-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 2px 1px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
  border: 2px solid transparent;
  position: relative;
  overflow: hidden;
  min-height: 0;
  height: 100%;
}

.day-cell.empty {
  cursor: default;
  background: transparent;
}

.day-cell.is-today {
  background: #fff7e6;
  border-color: #faad14;
}

.day-cell.has-data {
  background: #f8f9fa;
}

.day-cell.is-other-month {
  opacity: 0.3;
  background: transparent;
}

.day-cell.weekend .day-number {
  color: #ff4d4f;
}

.day-cell:not(.empty):hover {
  background: #e6f7ff;
  border-color: #1890ff;
  transform: scale(1.02);
  z-index: 1;
}

.day-number {
  font-size: 12px;
  font-weight: 500;
  color: #333;
  line-height: 1.2;
  flex-shrink: 0;
}

.day-cell.is-today .day-number {
  font-size: 13px;
  font-weight: 700;
  color: #faad14;
}

/* ===== 内容区域 ===== */
.day-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  flex: 1;
  min-height: 0;
  gap: 1px;
}

/* 图标行（两个图标并排） */
.icons-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 100%;
  flex: 1;
}

.icons-row .icon-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1px 2px;
  border-radius: 3px;
  font-size: 9px;
  flex: 1;
  min-width: 0;
  gap: 0;
}

.icons-row .icon-wrapper.time {
  background: #1890ff14;
  border: 1px solid #1890ff26;
  color: #1890ff;
}

.icons-row .icon-wrapper.review {
  background: #52c41a14;
  border: 1px solid #52c41a26;
  color: #52c41a;
}

.icons-row .icon-svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  display: block;
}

.icons-row .icon-label {
  font-size: 7px;
  font-weight: 500;
  white-space: nowrap;
  line-height: 1.2;
  flex-shrink: 0;
}

/* 单个图标 */
.day-content .icon-wrapper:not(.icons-row *) {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1px 3px;
  border-radius: 3px;
  font-size: 9px;
  flex: 1;
  min-width: 0;
  gap: 0;
  width: 100%;
}

.day-content .icon-wrapper.time {
  background: #1890ff14;
  border: 1px solid #1890ff26;
  color: #1890ff;
}

.day-content .icon-wrapper.review {
  background: #52c41a14;
  border: 1px solid #52c41a26;
  color: #52c41a;
}

.day-content .icon-wrapper .icon-svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  display: block;
}

.day-content .icon-wrapper .icon-label {
  font-size: 8px;
  font-weight: 500;
  white-space: nowrap;
  line-height: 1.2;
  flex-shrink: 0;
}

.day-content .empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #d9d9d9;
  font-size: 12px;
  line-height: 1;
  flex: 1;
}

/* ===== 深色模式 ===== */
.dark .calendar-container {
  background: #1e293b;
}

.dark .stat-item {
  background: #334155;
  border-color: #475569;
}

.dark .stat-icon {
  color: #60a5fa;
}

.dark .stat-label {
  color: #94a3b8;
}

.dark .stat-value {
  color: #e2e8f0;
}

.dark .nav-btn {
  border-color: #475569;
  color: #e2e8f0;
}

.dark .nav-btn:hover {
  background: #475569;
  border-color: #64748b;
}

.dark .calendar-title {
  color: #e2e8f0;
}

.dark .header-icon {
  color: #60a5fa;
}

.dark .conditions {
  border-bottom-color: #475569;
}

.dark .condition-item {
  color: #94a3b8;
}

.dark .weekday {
  color: #94a3b8;
}

.dark .weekday.weekend {
  color: #f87171;
}

.dark .day-cell {
  background: #334155;
}

.dark .day-cell.empty {
  background: transparent;
}

.dark .day-cell.is-today {
  background: #1e293b;
  border-color: #fbbf24;
}

.dark .day-cell.has-data {
  background: #334155;
}

.dark .day-cell:not(.empty):hover {
  background: #475569;
  border-color: #60a5fa;
}

.dark .day-number {
  color: #e2e8f0;
}

.dark .day-cell.is-today .day-number {
  color: #fbbf24;
}

.dark .day-cell.weekend .day-number {
  color: #f87171;
}

.dark .day-content .empty-state {
  color: #475569;
}

.dark .icons-row .icon-wrapper.time,
.dark .day-content .icon-wrapper.time {
  background: rgba(96, 165, 250, 0.15);
  border-color: rgba(96, 165, 250, 0.3);
  color: #60a5fa;
}

.dark .icons-row .icon-wrapper.review,
.dark .day-content .icon-wrapper.review {
  background: rgba(74, 222, 128, 0.15);
  border-color: rgba(74, 222, 128, 0.3);
  color: #4ade80;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .calendar-container {
    padding: 8px 8px 6px 8px;
    min-height: 340px;
  }

  .stats-row {
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
  }

  .stat-item {
    padding: 4px 6px;
    gap: 4px;
  }

  .stat-icon {
    width: 14px;
    height: 14px;
  }

  .stat-label {
    font-size: 8px;
  }

  .stat-value {
    font-size: 11px;
  }

  .calendar-title {
    font-size: 13px;
  }

  .header-icon {
    width: 16px;
    height: 16px;
  }

  .nav-btn {
    font-size: 14px;
    padding: 1px 8px;
  }

  .conditions {
    gap: 10px;
  }

  .condition-item {
    font-size: 9px;
  }

  .condition-dot {
    width: 6px;
    height: 6px;
  }

  .day-number {
    font-size: 10px;
  }

  .day-cell.is-today .day-number {
    font-size: 11px;
  }

  .icons-row .icon-svg {
    width: 11px !important;
    height: 11px !important;
  }

  .icons-row .icon-label {
    font-size: 6px;
  }

  .day-content .icon-wrapper .icon-svg {
    width: 13px !important;
    height: 13px !important;
  }

  .day-content .icon-wrapper .icon-label {
    font-size: 7px;
  }

  .weekday {
    font-size: 9px;
  }
}

@media (max-width: 480px) {
  .calendar-container {
    padding: 4px 4px 4px 4px;
    min-height: 280px;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 3px;
  }

  .stat-item {
    padding: 3px 5px;
  }

  .stat-icon {
    width: 12px;
    height: 12px;
  }

  .stat-label {
    font-size: 7px;
  }

  .stat-value {
    font-size: 10px;
  }

  .calendar-title {
    font-size: 11px;
  }

  .header-icon {
    width: 14px;
    height: 14px;
  }

  .nav-btn {
    font-size: 12px;
    padding: 0 6px;
  }

  .conditions {
    gap: 6px;
    padding: 2px 0 4px 0;
  }

  .condition-item {
    font-size: 8px;
  }

  .condition-dot {
    width: 5px;
    height: 5px;
  }

  .day-cell {
    padding: 1px 0;
    border-width: 1px;
  }

  .day-number {
    font-size: 9px;
  }

  .day-cell.is-today .day-number {
    font-size: 10px;
  }

  .icons-row .icon-svg {
    width: 9px !important;
    height: 9px !important;
  }

  .icons-row .icon-label {
    font-size: 5px;
  }

  .day-content .icon-wrapper .icon-svg {
    width: 11px !important;
    height: 11px !important;
  }

  .day-content .icon-wrapper .icon-label {
    font-size: 6px;
  }

  .weekday {
    font-size: 8px;
    padding: 1px 0;
  }

  .day-content .empty-state {
    font-size: 10px;
  }
}
</style>
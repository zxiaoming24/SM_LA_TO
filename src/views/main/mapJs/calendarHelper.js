// src/utils/calendarHelper.js

/**
 * 格式化日期为 YYYY-MM-DD
 */
export const formatDate = (date) => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/**
 * 解析日期字符串
 */
export const parseDate = (dateStr) => {
  const parts = dateStr.split('-').map(Number)
  return new Date(parts[0], parts[1] - 1, parts[2])
}

/**
 * 获取某月天数
 */
export const getDaysInMonth = (year, month) => {
  return new Date(year, month + 1, 0).getDate()
}

/**
 * 获取某月第一天是星期几
 */
export const getFirstDayOfMonth = (year, month) => {
  return new Date(year, month, 1).getDay()
}

/**
 * 获取指定日期的数据
 */
export const getDataByDate = (date, data) => {
  return data.find(item => item.date === date) || null
}

/**
 * 获取指定月份的数据
 */
export const getDataByMonth = (year, month, data) => {
  const monthStr = `${year}-${String(month + 1).padStart(2, '0')}`
  return data.filter(item => item.date.startsWith(monthStr))
}

/**
 * 获取学习时长（小时）
 */
export const getStudyHours = (date, data) => {
  const item = getDataByDate(date, data)
  return item ? (item.totalSeconds || 0) / 3600 : 0
}

/**
 * 获取复习次数
 */
export const getReviewCount = (date, data) => {
  const item = getDataByDate(date, data)
  return item ? (item.reviewCount || 0) : 0
}

/**
 * 检查日期是否有数据
 */
export const hasData = (date, data) => {
  return data.some(item => item.date === date)
}

/**
 * 获取统计数据
 */
export const getStatistics = (data) => {
  const validData = data.filter(item => item.totalSeconds > 0)
  const totalDays = validData.length
  const totalSeconds = validData.reduce((sum, item) => sum + item.totalSeconds, 0)
  const totalHours = totalSeconds / 3600
  const totalReviews = validData.reduce((sum, item) => sum + item.reviewCount, 0)
  const avgHours = totalDays > 0 ? totalHours / totalDays : 0
  const avgReviews = totalDays > 0 ? totalReviews / totalDays : 0

  const timeQualifiedDays = validData.filter(item => item.totalSeconds / 3600 > 0.5).length
  const reviewQualifiedDays = validData.filter(item => item.reviewCount > 1).length

  return {
    totalDays,
    totalHours: totalHours.toFixed(1),
    totalReviews,
    avgHours: avgHours.toFixed(1),
    avgReviews: avgReviews.toFixed(1),
    timeQualifiedDays,
    reviewQualifiedDays,
    timeQualifiedRate: totalDays > 0 ? ((timeQualifiedDays / totalDays) * 100).toFixed(1) : 0,
    reviewQualifiedRate: totalDays > 0 ? ((reviewQualifiedDays / totalDays) * 100).toFixed(1) : 0,
  }
}

/**
 * 生成模拟数据
 */
export const generateMockData = (year, month, count = 15) => {
  const data = []
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const today = new Date()
  const todayStr = formatDate(today)

  const selectedDays = []
  while (selectedDays.length < Math.min(count, daysInMonth)) {
    const day = Math.floor(Math.random() * daysInMonth) + 1
    if (!selectedDays.includes(day)) {
      selectedDays.push(day)
    }
  }

  selectedDays.sort((a, b) => a - b)

  selectedDays.forEach(day => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const totalSeconds = Math.floor(Math.random() * 14400) + 1800
    const reviewCount = Math.floor(Math.random() * 10)

    data.push({
      id: data.length + 1,
      userId: 1,
      date: dateStr,
      firstLogin: `${dateStr} ${String(Math.floor(Math.random() * 4) + 8).padStart(2, '0')}:${String(Math.floor(Math.random() * 60)).padStart(2, '0')}`,
      lastActive: `${dateStr} ${String(Math.floor(Math.random() * 4) + 17).padStart(2, '0')}:${String(Math.floor(Math.random() * 60)).padStart(2, '0')}`,
      totalSeconds,
      reviewCount,
    })
  })

  if (!data.some(item => item.date === todayStr) && todayStr.startsWith(`${year}-${String(month + 1).padStart(2, '0')}`)) {
    data.push({
      id: data.length + 1,
      userId: 1,
      date: todayStr,
      firstLogin: `${todayStr} 08:00`,
      lastActive: `${todayStr} 18:00`,
      totalSeconds: 28800,
      reviewCount: 5,
    })
  }

  return data
}

/**
 * 合并数据（新数据覆盖旧数据）
 */
export const mergeCalendarData = (existingData, newData) => {
  const map = new Map(existingData.map(item => [item.date, item]))
  newData.forEach(item => {
    map.set(item.date, item)
  })
  return Array.from(map.values())
}

/**
 * 过滤有效数据（有学习时长的）
 */
export const filterValidData = (data) => {
  return data.filter(item => item.totalSeconds > 0)
}

/**
 * 按日期排序
 */
export const sortByDate = (data) => {
  return [...data].sort((a, b) => a.date.localeCompare(b.date))
}
import * as echarts from 'echarts'

/**
 * 近七日学习时长折线图（秒自动换算小时，修复坐标轴对齐）
 * @param {HTMLElement} dom 容器DOM
 * @param {Array} list 后端原始学习统计数组
 * @returns echarts实例
 */
export function createStudyTrendChart(dom, list) {
  const chart = echarts.init(dom)

  // 检查是否为深色模式
  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#e2e8f0' : '#333'
  const axisLineColor = isDark ? '#475569' : '#ccc'
  const splitLineColor = isDark ? '#334155' : '#eee'
  const tooltipBg = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'

  const xAxisData = []
  const hourData = []
  // 指定主题配色数组
  const colorList = ['#2D7DDB', '#4A90E2', '#1E6BB8', '#F56C6C', '#E6A23C']

  list.forEach(item => {
    xAxisData.push(item.statDate.slice(5))
    // 后端字符串秒转数字，再换算小时保留两位小数
    const sec = Number(item.totalSeconds)
    const hour = Number((sec / 3600).toFixed(2))
    hourData.push(hour)
  })

  const option = {
    backgroundColor: 'transparent',
    color: colorList,
    tooltip: {
      trigger: 'axis',
      backgroundColor: tooltipBg,
      textStyle: {
        color: textColor
      },
      axisPointer: {
        type: 'line',
        align: 'auto',
        lineStyle: {
          color: axisLineColor
        }
      },
      formatter: params => {
        const idx = params[0].dataIndex
        const raw = list[idx]
        const totalSec = Number(raw.totalSeconds)
        const h = Math.floor(totalSec / 3600)
        const m = Math.floor((totalSec % 3600) / 60)
        const s = totalSec % 60
        const formatHour = (totalSec / 3600).toFixed(2)
        return `
日期：${raw.statDate}<br/>
在线时长：${h}时${m}分${s}秒（${formatHour}小时）<br/>
首次登录：${raw.firstLogin}<br/>
最后活跃：${raw.lastActive}
        `
      }
    },
    grid: { left: 60, right: 20, top: 40, bottom: 60 },
    xAxis: {
      type: 'category',
      data: xAxisData,
      boundaryGap: false, // 关键：消除两边空白，刻度和日期对齐
      axisTick: {
        alignWithLabel: true // 刻度竖线和文字强制对齐
      },
      axisLabel: {
        rotate: 20,
        color: textColor
      },
      axisLine: {
        lineStyle: {
          color: axisLineColor
        }
      }
    },
    yAxis: {
      type: 'value',
      name: '近七天学习时长(h)',
      nameTextStyle: {
        color: textColor
      },
      axisLabel: {
        color: textColor
      },
      axisLine: {
        lineStyle: {
          color: axisLineColor
        }
      },
      splitLine: {
        lineStyle: {
          type: 'dashed',
          color: splitLineColor
        }
      }
    },
    series: [
      {
        name: '每日学习时长',
        type: 'line',
        data: hourData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        itemStyle: { color: '#2D7DDB' },
        areaStyle: { color: 'rgba(45, 125, 219, 0.12)' },
        markPoint: {
          data: [
            { type: 'max', name: '最大值' },
            { type: 'min', name: '最小值' }
          ]
        }
      }
    ]
  }

  chart.setOption(option)
  return chart
}
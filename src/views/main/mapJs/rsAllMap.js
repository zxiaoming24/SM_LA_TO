// @/utils/rsAllMap.js
import * as echarts from 'echarts'

/**
 * 资源统计图表
 * @param {HTMLElement} dom 图表容器
 * @param {Object} options 配置选项
 */
export function RsChart(dom, options = {}) {
  const {
    resourceNames = [
      'PPT', '思维导图', '讲解文档', '拓展阅读',
      '编程题', '视频', '动画', '试卷', '学习计划'
    ],
    resourceData = [216, 652, 987, 435, 1246, 720, 318, 569, 287],
    colors = ['#ff4444', '#ff9900', '#ffdd00', '#33cc33', '#00bbdd', '#3366ff', '#9955ff'],
    showLabel = true,
    onChartReady = null
  } = options

  const chart = echarts.init(dom)

  // 检查是否为深色模式
  const isDark = document.documentElement.classList.contains('dark')
  const textColor = isDark ? '#e2e8f0' : '#444'
  const axisLineColor = isDark ? '#475569' : '#ddd'
  const splitLineColor = isDark ? '#334155' : '#eee'
  const tooltipBg = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
  const labelColor = isDark ? '#e2e8f0' : '#222'

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: tooltipBg,
      textStyle: {
        color: textColor
      },
      axisPointer: { type: 'shadow' }
    },
    grid: {
      left: '8%',
      right: '8%',
      bottom: '28%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: resourceNames,
      axisLine: { lineStyle: { color: axisLineColor } },
      axisLabel: {
        color: textColor,
        fontSize: 9,
        rotate: 35
      },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: axisLineColor } },
      axisLabel: { color: textColor, fontSize: 10 },
      splitLine: { lineStyle: { color: splitLineColor } }
    },
    series: [
      {
        name: '累计总量',
        type: 'bar',
        barWidth: 22,
        itemStyle: {
          color: (params) => colors[params.dataIndex % colors.length],
          borderRadius: 4
        },
        label: {
          show: showLabel,
          position: 'top',
          color: labelColor,
          fontSize: 8
        },
        data: resourceData
      }
    ]
  }

  chart.setOption(option)

  // 自适应
  const resizeHandler = () => chart.resize()
  window.addEventListener('resize', resizeHandler)

  // 回调
  if (onChartReady) {
    onChartReady(chart)
  }

  // 返回销毁函数
  return {
    chart,
    destroy: () => {
      window.removeEventListener('resize', resizeHandler)
      chart.dispose()
    },
    resize: resizeHandler,
    update: (newData) => {
      chart.setOption({
        series: [{ data: newData || resourceData }]
      })
    }
  }
}
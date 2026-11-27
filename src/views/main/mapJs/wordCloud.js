// src/utils/wordCloudUtil.js
import * as echarts from 'echarts'
import 'echarts-wordcloud'

// 资源类型映射中文
const typeNameMap = {
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
  WRONG_QUESTION: '错题本',
}

/**
 * 初始化资源 词云图
 * @param {HTMLElement} dom 容器dom
 * @param {Array} data 接口原始数组
 * @returns echarts实例
 */
export function createResourceWordCloud(dom, data) {
  const chart = echarts.init(dom)

  // 检查是否为深色模式
  const isDark = document.documentElement.classList.contains('dark')
  const tooltipBg = isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)'
  const tooltipText = isDark ? '#e2e8f0' : '#333'

  // 格式化词云数据
  const wordData = data.map(item => ({
    name: typeNameMap[item.resourceType] || item.resourceType,
    value: item.clickCount
  }))

  // 计算动态大小范围 - 根据数据量调整
  const dataCount = wordData.length
  // 数据量少时使用较大的字号，保证所有词都能显示
  let sizeRange
  if (dataCount <= 3) {
    sizeRange = [24, 60]
  } else if (dataCount <= 6) {
    sizeRange = [18, 50]
  } else if (dataCount <= 10) {
    sizeRange = [14, 40]
  } else {
    sizeRange = [12, 36]
  }

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: tooltipBg,
      textStyle: {
        color: tooltipText
      },
      formatter: params => {
        const target = data.find(d => typeNameMap[d.resourceType] === params.name)
        return `${params.name}<br/>点击次数：${target?.clickCount || 0}<br/>占比：${target?.percentage || 0}%`
      }
    },
    series: [
      {
        type: 'wordCloud',
        shape: 'circle',
        left: 'center',
        top: 'center',
        width: '100%',
        height: '100%',
        sizeRange: sizeRange,
        rotationRange: [-45, 45],
        rotationStep: 15,
        gridSize: dataCount <= 5 ? 20 : 8, // 数据少时增大间距，避免重叠
        drawOutOfBound: false,
        // 关键配置：确保所有词都被绘制
        shrinkToFit: true, // 如果词太多，缩小字号以适应画布
        textStyle: {
          fontFamily: 'Microsoft YaHei',
          fontWeight: 'bold',
          color: () => {
            const colorList = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#722ED1', '#13C2C2', '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
            return colorList[Math.floor(Math.random() * colorList.length)]
          }
        },
        emphasis: {
          textStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0,0,0,0.25)'
          }
        },
        data: wordData
      }
    ]
  }

  chart.setOption(option)

  // 如果数据量很少，可以强制刷新确保显示
  if (dataCount <= 5) {
    setTimeout(() => {
      chart.resize()
    }, 100)
  }

  return chart
}
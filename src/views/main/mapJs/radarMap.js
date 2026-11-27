//雷达图
// src/views/main/mapJs/radarMap.js
import * as echarts from 'echarts'


export const initRadarChart = (dom, data = {}) => {
  if (!dom) {
    console.error('ECharts 初始化失败：DOM 元素不存在')
    return null
  }

  // 如果已经初始化过，先销毁实例防止内存泄漏
  let myChart = echarts.getInstanceByDom(dom)
  if (myChart) {
    myChart.dispose()
  }

  // 初始化实例
  myChart = echarts.init(dom)

  // 检查是否为深色模式
  const isDark = document.documentElement.classList.contains('dark')

  // 颜色配置
  const textColor = isDark ? '#e2e8f0' : '#333'
  const axisColor = isDark ? '#475569' : '#e0e0e0'
  const splitLineColor = isDark ? '#475569' : 'rgb(180, 180, 180)'
  const splitAreaColors = isDark ? ['#1e293b', '#334155'] : ['#fff', '#f9f9f9']

  // 默认数据
  const defaultData = {
    name: '学生',
    dimensions: [
      { name: '学术背景', max: 100 },
      { name: '学习行为', max: 100 },
      { name: '目标动机', max: 100 },
      { name: '认知能力', max: 100 },
      { name: '情绪状态', max: 100 },
      { name: '社交互动', max: 100 },
      { name: '时间管理', max: 100 },
      { name: '创新创造', max: 100 }
    ]
  }

  const finalData = { ...defaultData, ...data }// 合并数据,相同覆盖
  console.log(finalData)

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: `${finalData.name} - 学生能力分析`,
      left: 'center',
      top: 17,
      textStyle: {
        color: textColor,
        fontSize: 20,
        fontWeight: 'bold',
        fontFamily: '抖音美好体, sans-serif'
      }
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
      textStyle: {
        color: textColor
      }
    },
    radar: {
      shape: 'circle',
      // 雷达图大小
      radius: '60%',
      // 雷达图位置
      center: ['50%', '55%'],
      // 维度信息数据
      indicator: finalData.dimensions,
      // 维度名样式
      axisName: {
        color: textColor,
        fontSize: 14
      },
      // 维度坐标轴轴线
      axisLine: {
        lineStyle: {
          color: axisColor
        }
      },
      // 分隔区域样式
      splitArea: {
        areaStyle: {
          color: splitAreaColors
        }
      },
      // 分隔线样式
      splitLine: {
        lineStyle: {
          color: splitLineColor
        }
      },
    },
    legend: {
      //位置
      top: 'bottom',
      data: [finalData.data[0].name, finalData.data[1].name],
      textStyle: {
        color: textColor
      }
    },
    series: [
      {
        name: '能力分布',
        type: 'radar',
        data: [
          {
            value: finalData.data[0].value,
            name: finalData.data[0].name,
            // 区域填充样式
            areaStyle: {
              color: 'rgba(230, 100, 50, 0.1)'
            },
            // 线条样式
            lineStyle: {
              color: 'rgb(243, 163, 131)',
              width: 2
            },
            // 数据点样式
            itemStyle: {
              color: '#e69575'
            },
            // 高亮时的样式
            emphasis: {
              itemStyle: {
                color: '#D9531E',
                borderWidth: 2,
                shadowBlur: 10,
                shadowColor: 'rgba(0, 0, 0, 0.2)'
              },
              areaStyle: {
                color: 'rgba(230, 100, 50, 0.4)'
              },
              lineStyle: {
                color: 'rgba(230, 100, 50, 0.7)',
                width: 2
              },
            }
          },
          {
            value: finalData.data[1].value,
            name: finalData.data[1].name,
            areaStyle: {
              color: 'rgba(30, 107, 184, 0.1)'
            },
            lineStyle: {
              color: 'rgba(30, 107, 184, 1)',
              width: 2
            },
            itemStyle: {
              color: '#4A90E2'
            },
            emphasis: {
              itemStyle: {
                color: '#1E6BB8',
                borderWidth: 2,
                shadowBlur: 10,
                shadowColor: 'rgba(0, 0, 0, 0.2)'
              },
              areaStyle: {
                color: 'rgba(30, 107, 184, 0.4)'
              },
              lineStyle: {
                color: 'rgba(30, 107, 184, 0.7)',
                width: 2
              },
            }
          }
        ]
      }
    ]
  }

  myChart.setOption(option)

  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    myChart.resize()
  })

  return myChart
}
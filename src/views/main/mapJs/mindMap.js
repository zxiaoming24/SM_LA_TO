//思维导图
// src/views/main/mapJs/mindMap.js
import * as echarts from 'echarts'


export const initMindMapChart = (dom, data = {}) => {
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

  const option = {
    tooltip: {
      trigger: 'item',
      confine: true,
      extraCssText: 'max-width:350px; white-space:normal; word-break:break-all;',
      formatter: (params) => `
      <div style="padding:4px 0;">
        <strong>${params.data.name}</strong><br/>
        ${params.data.content || ''}
      </div>
    `
    },
    series: [
      {
        type: 'tree',
        data: [data],
        top: '1%',
        left: '12%',
        bottom: '1%',
        right: '20%',
        symbolSize: 8,
        // 普通节点
        label: {
          position: 'left',
          verticalAlign: 'middle',
          align: 'right',
          fontSize: 12,
          width: 100,
          overflow: 'break',
        },

        // 叶子节点
        leaves: {
          label: {
            position: 'right',
            verticalAlign: 'middle',
            align: 'left',
            fontSize: 12,
            width: 180,
            overflow: 'break',
          },
        },

        //自动撑开间距，绝不重叠
        // initialTreeDepth: 1,//只显示一级内容
        expandAndCollapse: true,
        nodePadding: 25,     // 节点上下间距
        layerPadding: 50,    // 层级间距
        animationDuration: 550,
        animationDurationUpdate: 750
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
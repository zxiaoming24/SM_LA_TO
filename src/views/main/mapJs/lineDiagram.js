// 已掌握折线图
import * as echarts from 'echarts';

/**
 * 检测是否为暗色模式
 */
function isDarkMode() {
  return document.documentElement.classList.contains('dark');
}

/**
 * 获取主题色配置
 */
function getThemeColors() {
  const dark = isDarkMode();
  return {
    backgroundColor: dark ? 'transparent' : '#ffffff',
    titleColor: dark ? '#e2e8f0' : '#2c3e50',
    textColor: dark ? '#94a3b8' : '#6b7280',
    axisLineColor: dark ? '#475569' : '#e5e7eb',
    splitLineColor: dark ? '#334155' : '#f3f4f6',
    tooltipBg: dark ? 'rgba(30,41,59,0.95)' : 'rgba(255,255,255,0.95)',
    tooltipBorder: dark ? '#475569' : '#e5e7eb',
    tooltipText: dark ? '#e2e8f0' : '#333',
    lineColor: dark ? '#60a5fa' : '#4096ff',
    areaColorStart: dark ? 'rgba(96,165,250,0.35)' : 'rgba(64,150,255,0.35)',
    areaColorEnd: dark ? 'rgba(96,165,250,0.05)' : 'rgba(64,150,255,0.05)',
    successColor: dark ? '#4ade80' : '#52c41a',
    errorColor: dark ? '#f87171' : '#ff4d4f',
    markPointColor: dark ? '#60a5fa' : '#2D7DDB',
    highlightRing: dark ? 'rgba(96,165,250,0.4)' : 'rgba(64,150,255,0.4)',
    borderColor: dark ? '#1e293b' : '#fff'
  };
}

/**
 * 错题本：渲染编程题作答得分趋势图
 * @param {string} domId - 图表容器DOM id
 * @param {Object} recordData - 答题记录数据（包含 attempts、question_data）
 */
export function renderAnswerChart(domId, recordData) {
  const chartDom = document.getElementById(domId);
  if (!chartDom || !recordData || !Array.isArray(recordData.attempts)) {
    console.warn('图表容器或答题数据不合法');
    return;
  }

  // 解析数据
  const attempts = recordData.attempts;
  const xData = attempts.map(item => `第${item.attempt_number}次作答`);
  const scoreData = attempts.map(item => item.score);
  const statusData = attempts.map(item => item.verdict);
  const title = recordData.question_data?.title || '重练作答得分趋势';

  // 主题色
  const tc = getThemeColors();

  // 初始化实例
  const myChart = echarts.init(chartDom);

  const option = {
    backgroundColor: tc.backgroundColor,
    title: {
      text: `${title} - 重练作答得分趋势`,
      left: 'center',
      top: 16,
      textStyle: {
        fontSize: 18,
        fontWeight: 600,
        color: tc.titleColor,
        margin: 50
      }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tc.tooltipText },
      padding: 12,
      borderRadius: 8,
      shadowBlur: 10,
      shadowColor: 'rgba(0,0,0,0.1)',
      formatter: function (params) {
        const idx = params[0].dataIndex;
        const statusText = statusData[idx] === 'Accepted' ? '✅ 作答正确' : '❌ 答案错误';
        return `${xData[idx]}<br/>得分：${scoreData[idx]} 分<br/>状态：${statusText}`;
      }
    },
    legend: {
      data: ['单次得分'],
      top: 50,
      left: 'center',
      textStyle: { color: tc.textColor }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '18%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: tc.axisLineColor } },
      axisTick: { alignWithLabel: true, lineStyle: { color: tc.axisLineColor } },
      axisLabel: { color: tc.textColor, fontSize: 13 }
    },
    yAxis: {
      type: 'value',
      name: '得分',
      min: 0,
      max: 100,
      splitNumber: 5,
      nameTextStyle: { color: tc.textColor, fontSize: 13 },
      axisLine: { lineStyle: { color: tc.axisLineColor } },
      splitLine: { lineStyle: { color: tc.splitLineColor } },
      axisLabel: { color: tc.textColor, fontSize: 13 }
    },
    series: [
      {
        name: '单次得分',
        type: 'line',
        data: scoreData,
        smooth: true,
        lineStyle: { color: tc.lineColor, width: 3 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: tc.areaColorStart },
            { offset: 1, color: tc.areaColorEnd }
          ])
        },
        symbol: 'circle',
        symbolSize: function (value, params) {
          return params.dataIndex === myChart.__highlightIdx__ ? 16 : 10;
        },
        itemStyle: {
          color: function (params) {
            return statusData[params.dataIndex] === 'Accepted' ? tc.successColor : tc.errorColor;
          },
          borderColor: tc.borderColor,
          borderWidth: 2,
          shadowBlur: function (params) {
            return params.dataIndex === myChart.__highlightIdx__ ? 12 : 0;
          },
          shadowColor: tc.highlightRing
        },
        markPoint: {
          data: [
            { type: 'max', name: '最高分' },
            { type: 'min', name: '最低分' }
          ],
          itemStyle: { color: tc.markPointColor }
        }
      }
    ]
  };

  myChart.setOption(option);

  // 默认高亮第一个
  myChart.__highlightIdx__ = 0;
  myChart.setOption({
    series: [{
      data: scoreData.map((val, idx) => ({
        value: val,
        symbolSize: idx === 0 ? 16 : 10,
        itemStyle: idx === 0 ? { shadowBlur: 12, shadowColor: tc.highlightRing } : {}
      }))
    }]
  });

  // 窗口自适应
  const resizeHandler = () => {
    myChart.resize();
  };
  window.addEventListener('resize', resizeHandler);

  // 保存引用（供 highlightAttempt 使用）
  chartDom.__echartsInstance__ = myChart;
  chartDom.__resizeHandler__ = resizeHandler;
  chartDom.__themeColors__ = tc;
  chartDom.__scoreData__ = scoreData;
  chartDom.__statusData__ = statusData;
}

/**
 * 高亮指定作答次数
 * @param {string} domId - 图表容器DOM id
 * @param {number} idx - 要高亮的作答下标（从0开始）
 */
export function highlightAttempt(domId, idx) {
  const dom = document.getElementById(domId);
  if (!dom || !dom.__echartsInstance__) return;

  const myChart = dom.__echartsInstance__;
  const tc = dom.__themeColors__ || getThemeColors();
  const scoreData = dom.__scoreData__;
  if (!scoreData) return;

  myChart.__highlightIdx__ = idx;

  // 更新数据点样式：高亮的点放大并加阴影
  myChart.setOption({
    series: [{
      data: scoreData.map((val, i) => ({
        value: val,
        symbolSize: i === idx ? 16 : 10,
        itemStyle: i === idx
          ? { shadowBlur: 12, shadowColor: tc.highlightRing }
          : {}
      }))
    }]
  });

  // 显示 tooltip
  myChart.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: idx
  });
}

/**
 * 销毁图表实例（组件销毁时调用）
 * @param {string} domId - 图表容器DOM id
 */
export function destroyAnswerChart(domId) {
  const dom = document.getElementById(domId);
  if (dom && dom.__echartsInstance__) {
    dom.__echartsInstance__.dispose();
    window.removeEventListener('resize', dom.__resizeHandler__);
    delete dom.__echartsInstance__;
    delete dom.__resizeHandler__;
    delete dom.__themeColors__;
    delete dom.__scoreData__;
    delete dom.__statusData__;
  }
}

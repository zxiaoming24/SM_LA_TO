// 移动端错题本折线图
import * as echarts from 'echarts';

function isDarkMode() {
  return document.documentElement.classList.contains('dark');
}

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

export function renderAnswerChart(domId, recordData) {
  const chartDom = document.getElementById(domId);
  if (!chartDom || !recordData || !Array.isArray(recordData.attempts)) {
    return;
  }

  const attempts = recordData.attempts;
  const xData = attempts.map(item => `第${item.attempt_number}次`);
  const scoreData = attempts.map(item => item.score);
  const statusData = attempts.map(item => item.verdict);
  const title = recordData.question_data?.title || '作答得分趋势';

  const tc = getThemeColors();
  const myChart = echarts.init(chartDom);

  const option = {
    backgroundColor: tc.backgroundColor,
    tooltip: {
      trigger: 'axis',
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tc.tooltipText, fontSize: 12 },
      padding: 10,
      borderRadius: 8,
      formatter: function (params) {
        const idx = params[0].dataIndex;
        const statusText = statusData[idx] === 'Accepted' ? '✓ 正确' : '✗ 错误';
        return `${xData[idx]}<br/>得分：${scoreData[idx]} 分<br/>状态：${statusText}`;
      }
    },
    grid: {
      left: '8%',
      right: '5%',
      bottom: '0%',
      top: '20%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: tc.axisLineColor } },
      axisTick: { alignWithLabel: true, lineStyle: { color: tc.axisLineColor } },
      axisLabel: { color: tc.textColor, fontSize: 11, interval: 0, rotate: 0 }
    },
    yAxis: {
      type: 'value',
      name: '得分',
      min: 0,
      max: 100,
      splitNumber: 4,
      nameTextStyle: { color: tc.textColor, fontSize: 11 },
      axisLine: { lineStyle: { color: tc.axisLineColor } },
      splitLine: { lineStyle: { color: tc.splitLineColor } },
      axisLabel: { color: tc.textColor, fontSize: 11 }
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
          return params.dataIndex === myChart.__highlightIdx__ ? 14 : 9;
        },
        itemStyle: {
          color: function (params) {
            return statusData[params.dataIndex] === 'Accepted' ? tc.successColor : tc.errorColor;
          },
          borderColor: tc.borderColor,
          borderWidth: 2,
          shadowBlur: function (params) {
            return params.dataIndex === myChart.__highlightIdx__ ? 10 : 0;
          },
          shadowColor: tc.highlightRing
        },
        markPoint: {
          data: [
            { type: 'max', name: '最高' },
            { type: 'min', name: '最低' }
          ],
          itemStyle: { color: tc.markPointColor },
          label: { fontSize: 10 }
        }
      }
    ]
  };

  myChart.setOption(option);

  myChart.__highlightIdx__ = 0;
  myChart.setOption({
    series: [{
      data: scoreData.map((val, idx) => ({
        value: val,
        symbolSize: idx === 0 ? 14 : 9,
        itemStyle: idx === 0 ? { shadowBlur: 10, shadowColor: tc.highlightRing } : {}
      }))
    }]
  });

  const resizeHandler = () => { myChart.resize(); };
  window.addEventListener('resize', resizeHandler);

  chartDom.__echartsInstance__ = myChart;
  chartDom.__resizeHandler__ = resizeHandler;
  chartDom.__themeColors__ = tc;
  chartDom.__scoreData__ = scoreData;
  chartDom.__statusData__ = statusData;
}

export function highlightAttempt(domId, idx) {
  const dom = document.getElementById(domId);
  if (!dom || !dom.__echartsInstance__) return;

  const myChart = dom.__echartsInstance__;
  const tc = dom.__themeColors__ || getThemeColors();
  const scoreData = dom.__scoreData__;
  if (!scoreData) return;

  myChart.__highlightIdx__ = idx;

  myChart.setOption({
    series: [{
      data: scoreData.map((val, i) => ({
        value: val,
        symbolSize: i === idx ? 14 : 9,
        itemStyle: i === idx
          ? { shadowBlur: 10, shadowColor: tc.highlightRing }
          : {}
      }))
    }]
  });

  myChart.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: idx
  });
}

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

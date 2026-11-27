<!-- 右侧 摄像头 特征曲线 悬浮窗口 -->
<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import emitter from '@/utils/emitter'
import * as echarts from 'echarts'

const props = defineProps({
  userId: {
    type: String,
    required: true
  }
})

// 窗口折叠状态
const collapsed = ref(true)
const dragging = ref(false)
const offsetY = ref(0)
const posY = ref(0)
const wrapperEl = ref(null)

// 摄像头状态
const cameraConnected = ref(false)
const cameraError = ref('')
const isConnecting = ref(false)
const videoRef = ref(null)

// 警告弹窗状态
const warningVisible = ref(false)
const warningIcon = ref('')
const warningTitle = ref('')
const warningMessage = ref('')
const warningBtnType = ref('primary')

// 摄像头数据
const cameraMetrics = ref({
  attention: 0,
  gaze: '',
  drowsiness: 0
})

// 摄像头图表数据
const chartRef = ref(null)
let chartInstance = null
const chartData = ref({
  time: [],
  attention: [],
  drowsiness: []
})
const MAX_DATA_POINTS = 30

// 特征曲线数据
const featureChartRef = ref(null)
let featureChartInstance = null
const featureData = ref({
  time: [],
  overall: []
})
const MAX_FEATURE_POINTS = 20
let featureRunning = ref(false)
let lastFeatureScores = null
let lastOverallScore = 50
let featureFlowInterval = null

const featureDimLabels = ["学术背景", "学习行为", "目标动机", "认知能力", "情绪状态", "社交互动", "时间管理", "创新创造"]
const featureDimColors = ["#667eea", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316", "#ec4899"]

let wsConnection = null
let localStream = null
let peerConnection = null

// 警告冷却时间（防止重复弹窗）
const warningCooldown = {
  drowsy: 0,
  distracted: 0,
  yawning: 0,
  low_attention: 0
}

// 初始化位置：垂直居中
function initPosition() {
  if (!wrapperEl.value) return
  const rect = wrapperEl.value.getBoundingClientRect()
  const winHeight = window.innerHeight
  const top = Math.max(0, (winHeight - rect.height) / 2)
  posY.value = top
}

/*
// 拖拽开始
function startDrag(e) {
  const target = e.target.closest('.window-header')
  if (!target) return
  if (e.target.closest('button')) return

  dragging.value = true
  const rect = wrapperEl.value.getBoundingClientRect()
  offsetY.value = e.clientY - rect.top - 200
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'grabbing'
}


// 拖拽移动
function moveDrag(e) {
  if (!dragging.value) return
  e.preventDefault()

  const rect = wrapperEl.value.getBoundingClientRect()
  const winHeight = window.innerHeight
  let newTop = e.clientY - offsetY.value
  newTop = Math.max(0, Math.min(winHeight - rect.height, newTop))
  posY.value = newTop
}

// 拖拽结束
function endDrag() {
  if (dragging.value) {
    dragging.value = false
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
  }
}
  */

// 窗口大小改变
function handleResize() {
  if (!wrapperEl.value) return
  const rect = wrapperEl.value.getBoundingClientRect()
  const winHeight = window.innerHeight
  const minTop = 200
  
  let newTop = posY.value
  if (newTop + rect.height > winHeight) {
    newTop = Math.max(minTop, winHeight - rect.height)
  }
  if (newTop < minTop) {
    newTop = minTop
  }
  if (newTop !== posY.value) {
    posY.value = newTop
  }
}

// 切换折叠
function toggleCollapse() {
  if (collapsed.value) {
    collapsed.value = false
    setTimeout(() => {
      startFeatureStream()
    }, 400)
  } else {
    collapsed.value = true
    stopFeatureStream()
  }
}

// 摄像头控制
const startMonitor = async () => {
  if (cameraConnected.value || isConnecting.value) return
  
  isConnecting.value = true
  cameraError.value = ''
  
  try {
    await initCamera()
  } catch (error) {
    console.error('启动监控失败:', error)
    cameraError.value = error.message || '启动失败'
    isConnecting.value = false
  }
}

// 停止监控
const stopMonitor = () => {
  stopCamera()
}

// 初始化摄像头
const initCamera = async () => {
  if (wsConnection) return
  
  const sessionId = props.userId || `user_${Date.now()}`
  
  try {
    // 获取摄像头
    localStream = await navigator.mediaDevices.getUserMedia({
      video: { 
        width: { ideal: 640, max: 1280 }, 
        height: { ideal: 480, max: 720 },
        facingMode: 'user'
      },
      audio: false
    })
    console.log('✅ 摄像头获取成功')
  } catch (cameraErr) {
    console.error('❌ 摄像头获取失败:', cameraErr)
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      console.log('✅ 备用摄像头获取成功')
    } catch (err) {
      throw new Error('无法获取摄像头权限，请检查浏览器设置')
    }
  }
  
  await nextTick()
  if (videoRef.value) {
    videoRef.value.srcObject = localStream
    videoRef.value.onloadedmetadata = () => {
      videoRef.value.play().catch(e => console.log('视频播放自动恢复:', e))
    }
  }
  
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/wsApi/ws`
  wsConnection = new WebSocket(wsUrl)
  
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('WebSocket连接超时'))
      stopCamera()
    }, 10000)
    
    wsConnection.onopen = async () => {
      clearTimeout(timeout)
      console.log('✅ WebSocket 连接成功')
      
      try {
        peerConnection = new RTCPeerConnection({ 
          iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
          ] 
        })
        
        localStream.getTracks().forEach(track => {
          peerConnection.addTrack(track, localStream)
          console.log('📤 添加视频轨道:', track.kind)
        })
        
        peerConnection.ontrack = (event) => {
          console.log('📥 收到远程轨道:', event.track.kind)
        }
        
        peerConnection.onconnectionstatechange = () => {
          console.log('🔄 WebRTC连接状态:', peerConnection.connectionState)
          if (peerConnection.connectionState === 'connected') {
            cameraConnected.value = true
            isConnecting.value = false
            emitter.emit('cameraConnected')
            resolve()
          } else if (peerConnection.connectionState === 'disconnected') {
            cameraConnected.value = false
            isConnecting.value = false
            emitter.emit('cameraDisconnected')
          } else if (peerConnection.connectionState === 'failed') {
            stopCamera()
            reject(new Error('WebRTC连接失败'))
          }
        }
        
        peerConnection.oniceconnectionstatechange = () => {
          console.log('🧊 ICE连接状态:', peerConnection.iceConnectionState)
        }
        
        const offer = await peerConnection.createOffer()
        await peerConnection.setLocalDescription(offer)
        console.log('📋 创建Offer成功')
        
        const res = await fetch('/wsApi/offer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sdp: offer.sdp, 
            type: offer.type, 
            session_id: sessionId,
            analysis: {
              postureAnalysis: true,
              expressionAnalysis: true,
              behaviorAnalysis: true,
              gazeAnalysis: true,
              sessionId: sessionId
            }
          })
        })
        
        if (!res.ok) {
          throw new Error(`HTTP错误: ${res.status}`)
        }
        
        const answer = await res.json()
        await peerConnection.setRemoteDescription(new RTCSessionDescription(answer))
        console.log('✅ WebRTC Answer已接收')
        
        wsConnection.send(JSON.stringify({ 
          type: 'register', 
          session_id: sessionId, 
          user_id: props.userId 
        }))
        
      } catch (err) {
        console.error('❌ WebRTC建立失败:', err)
        reject(new Error('WebRTC连接失败: ' + err.message))
      }
    }
    
    wsConnection.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        console.log('📥 收到WebSocket消息:', msg)
        
        if (msg.type === 'analysis' && msg.payload) {
          const p = msg.payload
          console.log('📊 分析数据:', p.type, p.data)
          
          if (p.type === 'gaze' && p.data) {
            cameraMetrics.value.attention = p.data.attention_score !== undefined ? p.data.attention_score : 0
            cameraMetrics.value.drowsiness = p.data.drowsiness_score !== undefined ? p.data.drowsiness_score : 0
            cameraMetrics.value.gaze = p.data.gaze_direction || ''
            checkAndShowWarning(p.data)
            
            updateChartData(p.data)
          }
          
          if (p.type === 'posture' && p.data) {
            console.log('坐姿数据:', p.data)
          }
          
          if (p.type === 'multi_modal' && p.data) {
            console.log('多模态分析:', p.data)
          }
        } else if (msg.type === 'feature_update') {
          console.log('🎯 特征更新:', msg.payload)
        }
      } catch (e) {
        console.error('解析摄像头数据失败:', e, event.data)
      }
    }
    
    wsConnection.onerror = (error) => {
      clearTimeout(timeout)
      console.error('❌ WebSocket错误:', error)
      reject(new Error('WebSocket连接失败'))
    }
    
    wsConnection.onclose = (event) => {
      clearTimeout(timeout)
      cameraConnected.value = false
      isConnecting.value = false
      console.log('🔌 WebSocket已断开:', event.code, event.reason)
    }
  })
}

const stopCamera = () => {
  if (wsConnection) {
    wsConnection.close()
    wsConnection = null
  }
  
  if (peerConnection) {
    peerConnection.close()
    peerConnection = null
  }
  
  if (localStream) {
    localStream.getTracks().forEach(track => track.stop())
    localStream = null
  }
  
  cameraConnected.value = false
  isConnecting.value = false
  cameraMetrics.value = {
    attention: 0,
    gaze: '',
    drowsiness: 0
  }
  cameraError.value = ''
}

// 获取样式类
const getMetricClass = (value) => {
  if (value >= 80) return 'high'
  if (value >= 50) return 'medium'
  return 'low'
}

const getDrowsinessClass = (value) => {
  if (value >= 80) return 'danger'
  if (value >= 50) return 'warning'
  return 'safe'
}

// 检测瞌睡和分心，显示警告弹窗
const checkAndShowWarning = (data) => {
  if (!data) return
  const now = Date.now()

  if (data.is_drowsy && now - warningCooldown.drowsy > 60000) {
    showWarningModal('😴', '瞌睡提醒', '检测到您似乎在打瞌睡，请注意休息或调整状态', 'danger')
    warningCooldown.drowsy = now
  }

  if (data.is_distracted && now - warningCooldown.distracted > 30000) {
    const dir = data.gaze_direction || '未知'
    showWarningModal('👀', '分心提醒', '检测到您的视线离开了屏幕（' + dir + '），请保持专注', 'warning')
    warningCooldown.distracted = now
  }

  if (data.is_yawning && now - warningCooldown.yawning > 60000) {
    showWarningModal('🥱', '疲劳提醒', '检测到您在打哈欠，可能需要休息一下', 'primary')
    warningCooldown.yawning = now
  }

  if (data.attention_score !== undefined && data.attention_score < 40 && now - warningCooldown.low_attention > 45000) {
    showWarningModal('📉', '注意力提醒', '您的注意力分数较低，建议调整学习状态', 'warning')
    warningCooldown.low_attention = now
  }
}

const showWarningModal = (icon, title, message, btnType) => {
  warningIcon.value = icon
  warningTitle.value = title
  warningMessage.value = message
  warningBtnType.value = btnType
  warningVisible.value = true

  // 通知 SmartBall 组件，判断当前模式
  emitter.emit('cameraWarning', {
    message: `${title}，${message}`,
    onMode: (currentMode) => {
      // 智能球模式：播放连续提示音直到弹窗关闭
      if (currentMode === 'ball') {
        startAlarmSound()
      }
      // 数字人模式由 SmartBall 自行处理播报
    }
  })
  
  emitter.emit('videoWarning', { visible: true })
}

// 连续提示音（Web Audio API）
let alarmAudioCtx = null
let alarmOscillator = null
let alarmGain = null
let alarmTimer = null

const startAlarmSound = () => {
  stopAlarmSound()
  try {
    alarmAudioCtx = new (window.AudioContext || window.webkitAudioContext)()
    const playBeep = () => {
      if (!alarmAudioCtx || alarmAudioCtx.state === 'closed') return
      const osc = alarmAudioCtx.createOscillator()
      const gain = alarmAudioCtx.createGain()
      osc.connect(gain)
      gain.connect(alarmAudioCtx.destination)
      osc.type = 'sine'
      osc.frequency.setValueAtTime(880, alarmAudioCtx.currentTime)
      osc.frequency.setValueAtTime(660, alarmAudioCtx.currentTime + 0.15)
      osc.frequency.setValueAtTime(880, alarmAudioCtx.currentTime + 0.3)
      gain.gain.setValueAtTime(0.3, alarmAudioCtx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, alarmAudioCtx.currentTime + 0.5)
      osc.start(alarmAudioCtx.currentTime)
      osc.stop(alarmAudioCtx.currentTime + 0.5)
    }
    playBeep()
    alarmTimer = setInterval(playBeep, 1500)
  } catch (e) { /* 静默失败 */ }
}

const stopAlarmSound = () => {
  if (alarmTimer) { clearInterval(alarmTimer); alarmTimer = null }
  if (alarmAudioCtx) {
    try { alarmAudioCtx.close() } catch (e) { /* 静默失败 */ }
    alarmAudioCtx = null
  }
}

const closeWarningModal = () => {
  warningVisible.value = false
  stopAlarmSound()
}

//专注度/瞌睡分图表初始化
const initChart = () => {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      textStyle: { color: '#333' },
      padding: 10,
      borderRadius: 8,
      axisPointer: {
        type: 'cross',
        lineStyle: { color: '#999' }
      }
    },
    legend: {
      data: ['专注度', '瞌睡分'],
      bottom: 0,
      left: 'center',
      textStyle: { color: '#666', fontSize: 10 }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '25%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#ddd' } },
      axisLabel: { color: '#999', fontSize: 9 }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
      axisLabel: { color: '#999', fontSize: 9 }
    },
    series: [
      {
        name: '专注度',
        type: 'line',
        smooth: true,
        lineStyle: { color: '#2D7DDB', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(45, 125, 219, 0.3)' },
            { offset: 1, color: 'rgba(45, 125, 219, 0.05)' }
          ])
        },
        symbol: 'none',
        data: []
      },
      {
        name: '瞌睡分',
        type: 'line',
        smooth: true,
        lineStyle: { color: '#F56C6C', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(245, 108, 108, 0.3)' },
            { offset: 1, color: 'rgba(245, 108, 108, 0.05)' }
          ])
        },
        symbol: 'none',
        data: []
      }
    ]
  }
  
  chartInstance.setOption(option)
}

const updateChartData = (data) => {
  const now = new Date()
  const timeStr = `${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  
  chartData.value.time.push(timeStr)
  chartData.value.attention.push(data.attention_score || 0)
  chartData.value.drowsiness.push(Math.round((data.drowsiness_score || 0) * 100))
  
  if (chartData.value.time.length > MAX_DATA_POINTS) {
    chartData.value.time.shift()
    chartData.value.attention.shift()
    chartData.value.drowsiness.shift()
  }
  
  if (chartInstance) {
    chartInstance.setOption({
      xAxis: { data: chartData.value.time },
      series: [
        { data: chartData.value.attention },
        { data: chartData.value.drowsiness }
      ]
    })
  }
}

const clearChartData = () => {
  chartData.value = {
    time: [],
    attention: [],
    drowsiness: []
  }
  if (chartInstance) {
    chartInstance.setOption({
      xAxis: { data: [] },
      series: [
        { data: [] },
        { data: [] }
      ]
    })
  }
}

const resizeChart = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
  if (featureChartInstance) {
    featureChartInstance.resize()
  }
}

// ===== 特征曲线相关函数 =====
const startFeatureStream = () => {
  if (featureRunning.value) return
  featureRunning.value = true
  
  initFeatureChart()
  connectFeatureSSE()
}

const stopFeatureStream = () => {
  featureRunning.value = false
  stopFeatureFlow()
  if (featureSSE) {
    featureSSE.close()
    featureSSE = null
  }
}

let featureSSE = null

const connectFeatureSSE = () => {
  const uid = props.userId || '无'
  const url = `/features/${uid}/stream`
  
  console.log('📈 特征SSE连接:', url)
  featureSSE = new EventSource(url)
  
  featureSSE.onopen = () => {
    console.log('📈 特征SSE已连接')
  }
  
  featureSSE.onmessage = (event) => {
    try {
      console.log('📈 特征SSE收到消息:', event.data)
      const data = JSON.parse(event.data)
      if (data.type === 'feature_update') {
        handleFeatureUpdate(data.features)
      } else if (data.type === 'keepalive') {
        console.log('📈 特征SSE心跳')
      }
    } catch (e) {
      console.error('📈 特征SSE解析失败:', e, event.data)
    }
  }
  
  featureSSE.onerror = (error) => {
    console.error('📈 特征SSE错误:', error)
    featureSSE.close()
    featureSSE = null
  }
  
  featureSSE.onclose = () => {
    if (featureRunning.value) {
      setTimeout(() => { connectFeatureSSE() }, 5000)
    }
  }
}

const handleFeatureUpdate = (features) => {
  if (!features) return
  
  const scores = features.summary_scores ? features.summary_scores.dimension_scores : []
  const overall = features.summary_scores ? features.summary_scores.overall_score : 50
  
  if (scores.length === 8) {
    lastFeatureScores = scores
    lastOverallScore = overall
    addFeatureDataPoint(scores, overall)
    startFeatureFlow()
  }
}

const addFeatureDataPoint = (scores, overall) => {
  if (!scores) scores = lastFeatureScores || [50, 50, 50, 50, 50, 50, 50, 50]
  if (!overall) overall = lastOverallScore || 50
  
  const now = new Date()
  const timeStr = `${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  
  featureData.value.time.push(timeStr)
  featureData.value.overall.push(Math.round(overall))
  
  if (featureData.value.time.length > MAX_FEATURE_POINTS) {
    featureData.value.time.shift()
    featureData.value.overall.shift()
  }
  
  updateFeatureChart()
}

const startFeatureFlow = () => {
  if (featureFlowInterval) return
  
  if (featureData.value.time.length < 20 && lastFeatureScores) {
    const baseOverall = lastOverallScore
    const existingLen = featureData.value.time.length
    for (let i = existingLen; i < 20; i++) {
      const wave = Math.sin(i * 0.5) * 15 + Math.sin(i * 0.3) * 10
      const overall = baseOverall + wave + (Math.random() - 0.5) * 5
      const now = new Date(Date.now() - (20 - i) * 1000)
      const timeStr = `${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
      featureData.value.time.push(timeStr)
      featureData.value.overall.push(Math.round(overall))
    }
  }
  
  let waveOffset = featureData.value.time.length * 0.5
  
  featureFlowInterval = setInterval(() => {
    if (!featureRunning.value || !lastFeatureScores) return
    
    waveOffset += 0.3
    const wave = Math.sin(waveOffset) * 15 + Math.sin(waveOffset * 0.6) * 10 + Math.sin(waveOffset * 0.2) * 6
    let newOverall = lastOverallScore + wave + (Math.random() - 0.5) * 5
    newOverall = Math.max(20, Math.min(95, newOverall))
    
    const now = new Date()
    const timeStr = `${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
    
    featureData.value.time.push(timeStr)
    featureData.value.overall.push(Math.round(newOverall))
    
    if (featureData.value.time.length > MAX_FEATURE_POINTS) {
      featureData.value.time.shift()
      featureData.value.overall.shift()
    }
    
    updateFeatureChart()
  }, 800)
}

const stopFeatureFlow = () => {
  if (featureFlowInterval) {
    clearInterval(featureFlowInterval)
    featureFlowInterval = null
  }
}

const initFeatureChart = () => {
  if (!featureChartRef.value) return
  featureChartInstance = echarts.init(featureChartRef.value)
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      textStyle: { color: '#333' },
      padding: 10,
      borderRadius: 8,
      axisPointer: {
        type: 'cross',
        lineStyle: { color: '#999' }
      },
      formatter: (params) => {
        const dataIndex = params[0].dataIndex
        let html = `<div style="font-weight:600;margin-bottom:6px;">${params[0].axisValue}</div>`
        html += `<div style="display:flex;justify-content:space-between;gap:20px;margin:4px 0;">
          <span style="color:#999;">综合评分</span>
          <span style="font-weight:500;">${featureData.value.overall[dataIndex]}</span>
        </div>`
        if (lastFeatureScores) {
          html += '<div style="height:6px;border-top:1px dashed rgba(0,0,0,0.1);margin:6px 0;"></div>'
          lastFeatureScores.forEach((score, i) => {
            html += `<div style="display:flex;justify-content:space-between;gap:20px;margin:3px 0;">
              <span style="color:${featureDimColors[i]};">${featureDimLabels[i]}</span>
              <span style="font-weight:500;">${Math.round(score)}</span>
            </div>`
          })
        }
        return html
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#ddd' } },
      axisLabel: { color: '#999', fontSize: 9 }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
      axisLabel: { color: '#999', fontSize: 9 }
    },
    series: [
      {
        name: '综合评分',
        type: 'line',
        smooth: true,
        lineStyle: { color: '#2D7DDB', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(45, 125, 219, 0.3)' },
            { offset: 1, color: 'rgba(45, 125, 219, 0.05)' }
          ])
        },
        symbol: 'none',
        data: []
      }
    ]
  }
  
  featureChartInstance.setOption(option)
}

const updateFeatureChart = () => {
  if (featureChartInstance) {
    featureChartInstance.setOption({
      xAxis: { data: featureData.value.time },
      series: [
        { data: featureData.value.overall }
      ]
    })
  }
}

const clearFeatureChart = () => {
  featureData.value = {
    time: [],
    overall: []
  }
  if (featureChartInstance) {
    featureChartInstance.setOption({
      xAxis: { data: [] },
      series: [{ data: [] }]
    })
  }
}

onMounted(() => {
  initPosition()
  window.addEventListener('resize', handleResize)
  
  emitter.on('expandCameraWindow', (data) => {
    if (collapsed.value) {
      collapsed.value = false
      setTimeout(() => {
        startFeatureStream()
        // 如果带有 autoStartMonitor 参数，自动开始摄像头监控
        if (data && data.autoStartMonitor) {
          setTimeout(() => {
            startMonitor()
          }, 500)
        }
      }, 400)
    }
  })
  
  emitter.on('cameraConnected', () => {
    nextTick(() => {
      initChart()
      resizeChart()
    })
  })
  
  emitter.on('cameraDisconnected', () => {
    clearChartData()
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  emitter.off('expandCameraWindow')
  emitter.off('cameraConnected')
  emitter.off('cameraDisconnected')
  stopAlarmSound()
  stopCamera()
  stopFeatureStream()
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  if (featureChartInstance) {
    featureChartInstance.dispose()
    featureChartInstance = null
  }
})

const getTargetElement = () => {
  return wrapperEl.value
}

defineExpose({
  toggleCollapse,
  collapsed,
  warningVisible,
  getTargetElement
})
</script>

<template>
  <!-- 右侧悬浮窗口 -->
  <div
    ref="wrapperEl"
    class="float-wrapper"
    :class="{ collapsed: collapsed }"
    :style="{ top: posY + 15 + 'px' }"
  >
    <!-- 展开/折叠按钮（左侧） -->
    <button class="toggle-btn" @click.stop="toggleCollapse" :title="collapsed ? '展开' : '折叠'">
      {{ collapsed ? '◀' : '▶' }}
    </button>

    <!-- 主面板 -->
    <div class="float-window">
      <div class="window-header">
        <div class="title">
          <span class="icon-only">◈</span>
          <span>学习状态监控</span>
        </div>
        <div class="connection-indicator" :class="cameraConnected ? 'connected' : isConnecting ? 'connecting' : 'disconnected'">
          <span class="dot-small" :class="cameraConnected ? 'connected' : isConnecting ? 'connecting' : 'disconnected'"></span>
        </div>
      </div>
      
      <div class="window-body">
        <div class="body-card">
          <!-- 上区域：摄像头功能 -->
          <div class="camera-section">
            <!-- 连接状态 -->
            <div class="connection-status" :class="cameraConnected ? 'connected' : isConnecting ? 'connecting' : 'disconnected'">
              <div class="status-indicator">
                <span class="dot" :class="cameraConnected ? 'connected' : isConnecting ? 'connecting' : 'disconnected'"></span>
                <span class="status-text">{{ cameraConnected ? '已连接' : isConnecting ? '连接中...' : '未连接' }}</span>
                <span class="info-item" v-if="cameraConnected">用户ID: {{ props.userId || '未设置' }}</span>
              </div>
            </div>

            <!-- 控制按钮 -->
            <div class="controls">
              <button 
                @click="startMonitor" 
                :disabled="cameraConnected || isConnecting"
                class="btn btn-connect"
              >
                {{ isConnecting ? '连接中...' : '开始监控' }}
              </button>
              <button 
                @click="stopMonitor" 
                :disabled="!cameraConnected"
                class="btn btn-disconnect"
              >
                停止
              </button>
            </div>

            <!-- 视频预览 -->
            <div class="video-section" v-if="localStream || cameraConnected || isConnecting">
              <div class="video-wrapper">
                <video ref="videoRef" autoplay playsinline muted></video>
                <div v-if="isConnecting" class="video-overlay">
                  <div class="spinner"></div>
                  <span>正在连接...</span>
                </div>
                <div v-if="!cameraConnected && !isConnecting && !cameraError" class="video-overlay">
                  <p class="welcome-text">点击上方按钮开始监控</p>
                </div>
              </div>
            </div>

            <!-- 错误提示 -->
            <div v-if="cameraError" class="camera-error">
              <span>{{ cameraError }}</span>
              <button class="retry-btn" @click="startMonitor">重新连接</button>
            </div>

            <!-- 指标数据 -->
            <div class="metrics-section" v-if="cameraConnected">
              <div class="metric-row">
                <div class="metric-item">
                  <div class="metric-value" :class="getMetricClass(cameraMetrics.attention)">{{ cameraMetrics.attention }}%</div>
                  <div class="metric-label">专注度</div>
                </div>
                <div class="metric-item">
                  <div class="metric-value">{{ cameraMetrics.gaze || '--' }}</div>
                  <div class="metric-label">视线方向</div>
                </div>
                <div class="metric-item">
                  <div class="metric-value" :class="getDrowsinessClass(Math.round(cameraMetrics.drowsiness * 100))">{{ cameraMetrics.drowsiness.toFixed(2) }}</div>
                  <div class="metric-label">瞌睡分</div>
                </div>
              </div>
              
              <!-- 折线图 -->
              <div class="chart-container">
                <div ref="chartRef" class="chart"></div>
              </div>
            </div>
          </div>

          <!-- 分隔线 -->
          <div class="section-divider"></div>

          <!-- 下区域：特征实时曲线 -->
          <div class="feature-section">
            <div class="section-header">
              <span>特征实时曲线</span>
              <span class="section-status" :class="featureRunning ? 'running' : 'stopped'">
                {{ featureRunning ? '实时更新' : '未启动' }}
              </span>
            </div>
            <div class="feature-chart-container">
              <div ref="featureChartRef" class="feature-chart"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 警告弹窗 -->
  <Transition name="fade">
    <div v-if="warningVisible" class="warning-modal" @click.self="closeWarningModal">
      <div class="modal-content">
        <div class="modal-icon">{{ warningIcon }}</div>
        <div class="modal-title">{{ warningTitle }}</div>
        <div class="modal-message">{{ warningMessage }}</div>
        <button class="modal-btn" :class="warningBtnType" @click="closeWarningModal">我知道了</button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ========== 右侧悬浮窗口（镜像 FloatWindow） ========== */
.float-wrapper {
  position: fixed;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 99;
  display: flex;
  align-items: center;
  transition: top 0.3s ease;
}

.float-window {
  width: 280px;
  max-width: calc(100vw - 20px);
  max-height: 850px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 20px 0 0 20px;
  box-shadow: 0 16px 48px rgba(0, 20, 40, 0.18), -4px 0 12px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-right: none;
  user-select: none;
  transition: all 0.35s cubic-bezier(0.34, 1.2, 0.64, 1);
  overflow: hidden;
  opacity: 1;
  transform: translateX(0);
  display: flex;
  flex-direction: column;
}

.float-wrapper.collapsed .float-window {
  max-height: 0 !important;
  opacity: 0;
  padding: 0;
  width: 0;
  border: none;
  box-shadow: none;
  transform: translateX(20px);
  pointer-events: none;
}

/* ===== 折叠/展开按钮（左侧） ===== */
.toggle-btn {
  width: 44px;
  height: 56px;
  border-radius: 14px 0 0 14px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-right: none;
  box-shadow: -4px 0 16px rgba(0, 20, 40, 0.10), 0 4px 12px rgba(0, 0, 0, 0.04);
  color: #2c3e6b;
  font-size: 1.2rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.34, 1.2, 0.64, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  user-select: none;
  position: relative;
  z-index: 99;
}

.float-wrapper:not(.collapsed) .toggle-btn {
  border-radius: 14px 0 0 14px;
  box-shadow: -4px 0 16px rgba(0, 20, 40, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04);
  margin-left: 0;
}

.float-wrapper.collapsed .toggle-btn {
  border-radius: 16px 0 0 16px;
  box-shadow: -4px 0 20px rgba(0, 20, 40, 0.15), 0 4px 12px rgba(0, 0, 0, 0.06);
  width: 48px;
  height: 64px;
  font-size: 1.4rem;
}

.toggle-btn:hover {
  background: rgba(255, 255, 255, 1);
  box-shadow: -4px 0 24px rgba(0, 20, 40, 0.20);
  transform: scale(1.02);
}

.toggle-btn:active {
  transform: scale(0.95);
}

/* ===== 窗口头部 ===== */
.window-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid #e2e8f0;
}

.title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #2c3e6b;
}

.icon-only {
  color: #6366f1;
  font-size: 16px;
}

.connection-indicator {
  display: flex;
  align-items: center;
}

.dot-small {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #999;
}

.dot-small.connected { background: #52c41a; }
.dot-small.connecting { background: #faad14; animation: pulse 1s infinite; }
.dot-small.disconnected { background: #999; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ===== 窗口主体 ===== */
.window-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  background: #fafbfc;
}

.body-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ===== 连接状态 ===== */
.connection-status {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.connection-status.connected { background: #f6ffed; }
.connection-status.connecting { background: #fffbe6; }
.connection-status.disconnected { background: #f5f7fa; }

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #999;
}

.dot.connected { background: #52c41a; }
.dot.connecting { background: #faad14; animation: pulse 1s infinite; }
.dot.disconnected { background: #999; }

.status-text {
  font-size: 12px;
  font-weight: 500;
  color: #2c3e6b;
}

.info-item {
  font-size: 11px;
  color: var(--text-gray);
  margin-left: 12px;
}

/* ===== 控制按钮 ===== */
.controls {
  display: flex;
  gap: 6px;
}

.btn {
  flex: 1;
  padding: 8px 10px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-connect {
  background: #6366f1;
  color: #fff;
}

.btn-connect:hover:not(:disabled) {
  background: #4f46e5;
}

.btn-disconnect {
  background: #f5f7fa;
  color: #2c3e6b;
  border: 1px solid #e2e8f0;
}

.btn-disconnect:hover:not(:disabled) {
  background: #e6e8eb;
}

/* ===== 视频区域 ===== */
.video-section {
  margin-top: 4px;
}

.video-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16/9;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}

.video-wrapper video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transform: scaleX(-1);
}

.video-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.video-overlay .spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top: 2px solid #6366f1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.video-overlay span {
  color: #fff;
  font-size: 11px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.welcome-text {
  color: #fff;
  font-size: 11px;
  text-align: center;
  margin: 0;
}

/* ===== 错误提示 ===== */
.camera-error {
  padding: 8px 10px;
  background: #fff2f0;
  color: #f5576c;
  font-size: 11px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.retry-btn {
  background: #f5576c;
  color: #fff;
  border: none;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  cursor: pointer;
}

.retry-btn:hover {
  background: #e6455b;
}

/* ===== 特征曲线区域 ===== */
.feature-section {
  padding: 8px;
  background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary-fade) 100%);
  border-radius: 10px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 8px;
}

.section-status {
  font-size: 10px;
  font-weight: 400;
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(156, 163, 175, 0.2);
  color: #9ca3af;
}

.section-status.running {
  background: rgba(103, 194, 58, 0.2);
  color: var(--pass);
}

.feature-chart-container {
  margin-top: 4px;
}

.feature-chart {
  width: 100%;
  height: 120px;
}

.section-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, #d1d5db, transparent);
  margin: 10px 0;
}

.camera-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ===== 指标区域 ===== */
.metrics-section {
  margin-top: 4px;
}

.metric-row {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.metric-item {
  flex: 1;
  min-width: 45px;
  text-align: center;
  padding: 6px 4px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.metric-value {
  font-size: 1em;
  font-weight: 700;
  color: #2c3e6b;
}

.metric-value.high { color: #6366f1; }
.metric-value.medium { color: #8b5cf6; }
.metric-value.low { color: #f5576c; }

.metric-value.danger { color: #ef4444; }
.metric-value.warning { color: #f59e0b; }
.metric-value.safe { color: #06b6d4; }

.metric-label {
  font-size: 0.65em;
  color: #8c8c8c;
  margin-top: 2px;
}

.chart-container {
  margin-top: 8px;
  padding: 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.chart {
  width: 100%;
  height: 140px;
}

/* ===== 警告弹窗 ===== */
.warning-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  background: #fff;
  border-radius: 16px;
  padding: 24px 28px;
  max-width: 380px;
  width: 90%;
  text-align: center;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.25);
  animation: slideUp 0.3s ease;
}

.modal-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.modal-message {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 20px;
}

.modal-btn {
  padding: 10px 32px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.modal-btn.primary { background: #6366f1; color: #fff; }
.modal-btn.danger { background: #ef4444; color: #fff; }
.modal-btn.warning { background: #f59e0b; color: #fff; }

.modal-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ============ 夜间模式适配 ============ */

/* 浮动窗口主体 */
.dark .float-window {
  background: rgba(30, 41, 59, 0.95);
  border-color: rgba(71, 85, 105, 0.5);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4), 4px 0 12px rgba(0, 0, 0, 0.2);
}

/* 切换按钮 */
.dark .toggle-btn {
  background: rgba(30, 41, 59, 0.95);
  border-color: rgba(71, 85, 105, 0.5);
  color: var(--text-body);
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.3), 0 4px 12px rgba(0, 0, 0, 0.2);
}

.dark .toggle-btn:hover {
  background: rgba(51, 65, 85, 0.95);
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.4);
}

.dark .float-wrapper:not(.collapsed) .toggle-btn {
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.25), 0 4px 12px rgba(0, 0, 0, 0.2);
}

.dark .float-wrapper.collapsed .toggle-btn {
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.4), 0 4px 12px rgba(0, 0, 0, 0.25);
}

/* 窗口头部 */
.dark .window-header {
  background: rgba(30, 41, 59, 0.95);
  border-bottom-color: rgba(71, 85, 105, 0.3);
}

.dark .window-header .title {
  color: var(--text-title);
}

/* 窗口主体 */
.dark .window-body {
  background: var(--bg-page);
}

/* 卡片 */
.dark .body-card {
  background: var(--bg-card);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

/* 会话头部 */
.dark .session-header {
  background: rgba(71, 85, 105, 0.15);
}

.dark .session-title {
  color: var(--text-body);
}

/* 连接状态 */
.dark .connection-status {
  background: rgba(71, 85, 105, 0.2);
}

.dark .connection-status.connected {
  background: rgba(74, 222, 128, 0.15);
}

.dark .connection-status.connecting {
  background: rgba(251, 146, 60, 0.15);
}

.dark .connection-status.disconnected {
  background: rgba(71, 85, 105, 0.15);
}

/* 状态点 */
.dark .dot-small.disconnected {
  background: rgba(156, 163, 175, 0.5);
}

.dark .dot.disconnected {
  background: rgba(156, 163, 175, 0.5);
}

/* 卡片项 */
.dark .card-item {
  background: var(--bg-card);
}

/* 指标值 */
.dark .metric-value.high { color: #818cf8; }
.dark .metric-value.medium { color: #a78bfa; }
.dark .metric-value.low { color: #f87171; }
.dark .metric-value.danger { color: #f87171; }
.dark .metric-value.warning { color: #fb923c; }
.dark .metric-value.safe { color: #22d3ee; }

/* 模态框 */
.dark .modal {
  background: var(--bg-card);
}

.dark .modal-header {
  color: var(--text-title);
}

.dark .modal-body {
  color: var(--text-body);
}

/* 警告徽章 */
.dark .warning-badge {
  background: rgba(248, 113, 113, 0.15);
}

/* 模态按钮 */
.dark .modal-btn.primary {
  background: rgba(99, 102, 241, 0.8);
  color: #fff;
}

.dark .modal-btn.danger {
  background: rgba(239, 68, 68, 0.8);
  color: #fff;
}

.dark .modal-btn.warning {
  background: rgba(245, 158, 11, 0.8);
  color: #fff;
}

/* 空状态 */
.dark .empty-state {
  background: rgba(71, 85, 105, 0.1);
}

.dark .empty-text {
  color: var(--text-gray);
}

/* 视频区域 */
.dark .video-container {
  background: rgba(0, 0, 0, 0.5);
}

/* 工具栏 */
.dark .toolbar {
  background: rgba(30, 41, 59, 0.9);
}

/* 综合评分 */
.dark .score-label {
  color: var(--text-gray);
}

</style>
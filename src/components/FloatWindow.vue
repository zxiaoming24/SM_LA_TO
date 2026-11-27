<!-- 左侧SSE窗口 -->

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { connectSSE, disconnectSSE } from '@/api/mainApi/floatWindow.js'
import PlanSelector from './PlanSelector.vue'

const router = useRouter()

// 组件属性
const props = defineProps({
  title: {
    type: String,
    default: 'Agent思维链'
  },
  defaultCollapsed: {
    type: Boolean,
    default: true
  },
  userId: {
    type: String,
    default: ''
  }
})

const isForcedOpen = ref(false)// 是否强制打开窗口（aiAnswer页画像未构建完全）
// 强制打开后，折叠/展开按钮会隐藏

// 事件处理
const emit = defineEmits([
  'update:collapsed',
  'toggle',
  'connected',
  'disconnected',
  'message',
  'error'
])

const collapsed = ref(props.defaultCollapsed)// 是否折叠
const wrapperEl = ref(null)// 窗口DOM引用

const isConnected = ref(false)// 是否已连接
const isConnecting = ref(false)// 是否正在连接
const connectionStatus = ref('disconnected')// 连接状态（disconnected/connected）
const eventSource = ref(null)// SSE事件源
const connectStartTime = ref(null)// 连接开始时间
const durationTimer = ref(null)// 连接持续时间定时器
const connectionDuration = ref('0s')// 连接持续时间

const sessions = ref([])// 会话列表
const activeSessionId = ref(null)// 当前会话ID
const viewMode = ref('content')// 当前视图模式（content/thinking）
const nodesContainer = ref(null)// 节点容器DOM引用
const thinkingContainer = ref(null)// 思考容器DOM引用
const projectCounter = ref(0)// 项目计数器

// 缓存 task start 之前到达的前导节点和思考内容
const pendingNodes = ref([])// 前导节点缓存
const pendingThinking = ref([])// 思考内容缓存

const planOptions = ref([])// 计划选项列表
const showPlanDialog = ref(false)// 是否显示计划选择弹窗

// 节点元数据
const NODE_META = {
  'intent_recognition': { icon: '🎯', label: '意图识别' },
  'conduct_layer': { icon: '⚙️', label: '执行层' },
  'task': { icon: '📋', label: '任务' },
  'router': { icon: '🔀', label: '路由' },
  'practice': { icon: '💻', label: '编程练习' },
  'integrator': { icon: '🔗', label: '整合' },
  'chat': { icon: '💬', label: '对话' },
  'doc_gen': { icon: '📄', label: '文档生成' },
  'question_gen': { icon: '❓', label: '题目生成' },
  'video': { icon: '📹', label: '视频搜索' },
  'mindmap': { icon: '🗺️', label: '思维导图' },
  'extension': { icon: '📚', label: '拓展阅读' },
  'super': { icon: '🚀', label: '启动超级智能体' },
  'super_super_agent': { icon: '▶️', label: '超级智能体开始任务' },
  'super_think': { icon: '🤔', label: '超级智能体思考' },
  'super_action': { icon: '🔧', label: '超级智能体执行' },
  'mindmap_stream': { icon: '🗺️', label: '思维导图' },
  'animation_stream': { icon: '🎬', label: '动画' },
  'chat_stream': { icon: '💬', label: '对话' },
  'extension_stream': { icon: '📚', label: '拓展阅读' },
  'paper_stream': { icon: '📝', label: '理论题' },
  'practice_stream': { icon: '💻', label: '编程题' },
  'video_stream': { icon: '📹', label: '视频' },
  'word_stream': { icon: '📄', label: 'Word文档' },
  'des_layer': { icon: '🧩', label: '构建层' },
  'des_user_info_extractor': { icon: '👤', label: '构建层-用户信息提取' },
  'des_router': { icon: '🔀', label: '构建层-路由' },
  'des_question_refiner': { icon: '🔍', label: '构建层-问题精炼' },
  'des_feature_extractor': { icon: '🧬', label: '构建层-特征提取' },
  'des_teacher': { icon: '👨‍🏫', label: '构建层-教师结点' },
  'des_integrator': { icon: '🔗', label: '构建层-整合' },
  'study_plan': { icon: '⏰', label: '学习计划' },
  'ppt': { icon: '✨', label: 'ppt' },
}

// 当前会话
const activeSession = computed(() => {
  return sessions.value.find(s => s.id === activeSessionId.value) || null
})

// 会话列表按时间排序
const sortedSessions = computed(() => {
  return [...sessions.value].sort((a, b) => b.timestamp - a.timestamp)
})

// 连接状态文本（无用）
const statusText = computed(() => {
  const map = {
    'connected': '已连接',
    'connecting': '连接中',
    'disconnected': '未连接',
    'error': '连接错误'
  }
  return map[connectionStatus.value] || '未知状态'
})

// 节点状态样式
const getNodeStatusClass = (status) => {
  const map = {
    'start': 'active',
    'complete': 'completed',
    'running': 'active',
    'error': 'error',
    'pending': 'pending',
    'idle': 'idle'
  }
  return map[status] || 'idle'
}

// 节点状态文本（无用）
const getNodeStatusText = (status) => {
  const map = {
    'start': '开始',
    'complete': '完成',
    'running': '运行中',
    'error': '错误'
  }
  return map[status] || status
}

// 会话状态文本
const getSessionStatusText = (status) => {
  const map = {
    'running': '运行中',
    'completed': '已完成'
  }
  return map[status] || status
}

// 获取节点元数据
const getNodeMeta = (nodeName) => {
  return NODE_META[nodeName] || { icon: '⚙️', label: nodeName }
}

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = typeof timestamp === 'number' ? new Date(timestamp) : timestamp
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

// 高亮思考内容（markdown转换）
const highlightThinkingContent = (content) => {
  if (!content) return ''
  let html = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  
  html = html.replace(/\[LLM 开始推理\]/g, '<span class="thinking-llm-start">[LLM 开始推理]</span>')
  html = html.replace(/\[LLM 推理完成\]/g, '<span class="thinking-llm-end">[LLM 推理完成]</span>')
  html = html.replace(/\[LLM 错误\]/g, '<span class="thinking-llm-error">[LLM 错误]</span>')
  
  html = html.replace(/`([^`]+)`/g, '<code class="thinking-code">$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="thinking-link">$1</a>')
  html = html.replace(/^###\s+(.*)$/gm, '<h3 class="thinking-h3">$1</h3>')
  html = html.replace(/^##\s+(.*)$/gm, '<h2 class="thinking-h2">$1</h2>')
  html = html.replace(/^#\s+(.*)$/gm, '<h1 class="thinking-h1">$1</h1>')
  html = html.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li class="thinking-li">$1</li>')
  html = html.replace(/^\d+\.\s+(.*)$/gm, '<li class="thinking-li">$1</li>')
  html = html.replace(/((?:<li class="thinking-li">.*?<\/li>\n?)+)/g, '<ul class="thinking-ul">$1</ul>')
  html = html.replace(/^&gt;\s+(.*)$/gm, '<blockquote class="thinking-blockquote">$1</blockquote>')
  
  const lines = html.split('\n')
  const out = []
  for (const line of lines) {
    const t = line.trim()
    if (!t) {
      out.push('<br>')
      continue
    }
    if (/^<(h[1-3]|ul|\/ul|li|blockquote|\/blockquote|code|a|span)/.test(t)) {
      out.push(t)
    } else {
      out.push('<p class="thinking-p">' + t + '</p>')
    }
  }
  html = out.join('')
  html = html.replace(/<p class="thinking-p"><ul/g, '<ul')
  html = html.replace(/<\/ul><\/p>/g, '</ul>')
  html = html.replace(/<p class="thinking-p"><li/g, '<li')
  html = html.replace(/<\/li><\/p>/g, '</li>')
  
  return html
}

// 创建新会话
const createNewSession = (timestamp) => {
  projectCounter.value++
  const newSessionId = String(timestamp)
  const session = {
    id: newSessionId,
    projectNumber: projectCounter.value,
    timestamp: timestamp,
    status: 'running',
    nodes: [],
    thinking: [],
    detail: ''
  }
  sessions.value.push(session)
  activeSessionId.value = newSessionId
  return session
}

// 处理SSE消息
const processMessage = (eventType, rawData) => {
  console.log(`📨 处理消息 [${eventType}]:`, rawData)
  
  try {
    // 解析数据
    const data = typeof rawData === 'string' ? JSON.parse(rawData) : rawData
    const realType = data.type || eventType
    const timestamp = data.timestamp || Date.now()
    
    // 连接状态消息
    if (realType === 'connection') {
      if (data.status === 'connected' || data.success === true) {
        isConnected.value = true
        isConnecting.value = false
        connectionStatus.value = 'connected'
        startDurationTimer()
        emit('connected', { data })
      }
      return
    }
    
    // 任务完成消息
    if (realType === 'done') {
      const runningSession = sessions.value.find(s => s.status === 'running')
      if (runningSession) {
        runningSession.status = 'completed'
      }
      return
    }
    
    // 节点状态消息
    if (realType === 'node_status') {
      let targetSession = sessions.value.find(s => s.status === 'running')
      
      // 如果是开始事件且没有活跃会话，创建新会话
      if (data.status === 'start' && !targetSession) {
        sessions.value.forEach(s => {
          if (s.status === 'running') {
            s.status = 'completed'
          }
        })
        
        targetSession = createNewSession(timestamp)
        targetSession.detail = data.detail || ''
        
        // 添加当前节点
        targetSession.nodes.push({
          node: data.node,
          status: data.status,
          detail: data.detail || '',
          timestamp: timestamp
        })
        
        // 应用缓存的思考内容
        if (pendingThinking.value.length > 0) {
          targetSession.thinking.push(...pendingThinking.value)
          pendingThinking.value = []
        }
      } else if (targetSession) {
        // 有活跃会话，添加/更新节点
        const existingNode = targetSession.nodes.find(n => n.node === data.node)
        if (existingNode) {
          existingNode.status = data.status
          existingNode.detail = data.detail || ''
          existingNode.timestamp = timestamp
        } else {
          targetSession.nodes.push({
            node: data.node,
            status: data.status,
            detail: data.detail || '',
            timestamp: timestamp
          })
        }
        
        // task完成则会话完成
        if (data.node === 'task' && data.status === 'complete') {
          targetSession.status = 'completed'
        }
      } else {
        // 没有活跃会话，缓存节点
        pendingNodes.value.push({
          node: data.node,
          status: data.status,
          detail: data.detail || '',
          timestamp: timestamp
        })
      }
      
      scrollToRight(nodesContainer)
      emit('message', { type: 'node_status', data })
      return
    }
    
    // 思考内容消息
    if (realType === 'thinking' && data.content) {
      let targetSession = sessions.value.find(s => s.status === 'running')
      
      if (targetSession) {
        targetSession.thinking.push({
          node: data.node || '',
          content: data.content,
          timestamp: timestamp
        })
        
        // 限制思考内容数量
        if (targetSession.thinking.length > 500) {
          targetSession.thinking = targetSession.thinking.slice(-200)
        }
        
        scrollToBottom(thinkingContainer)
      } else {
        // 没有活跃会话，缓存思考内容
        pendingThinking.value.push({
          node: data.node || '',
          content: data.content,
          timestamp: timestamp
        })
      }
      
      emit('message', { type: 'thinking', data })
      return
    }
    
    // 任务结果/对话流消息
    if (realType === 'task_result' || realType === 'chat_stream') {
      emit('message', { type: 'task_result', data })
      console.log('📋 task_result/chat_stream 数据:', JSON.stringify(data, null, 2).substring(0, 500))
      
      // 提取方案选择数据
      let planData = null
      if (data.result && data.result.data && data.result.data.plan_options) {
        planData = data.result.data.plan_options
      } else if (data.data && data.data.plan_options) {
        planData = data.data.plan_options
      } else if (data.result && data.result.plan_options) {
        planData = data.result.plan_options
      }
      
      // 打开方案选择弹窗
      if (planData) {
        planOptions.value = planData
        showPlanDialog.value = true
      }
      
      // 处理学习计划状态和薄弱环节信息
      const studyPlanResult = data.result && data.result.study_plan_status
      const weakPointsInfo = data.result && data.result.weak_points_info
      if (studyPlanResult || weakPointsInfo) {
        emit('study_plan_result', {
          status: studyPlanResult,
          weak_points_info: weakPointsInfo,
          student_features: data.result && data.result.student_features,
          metadata: data.result && data.result.metadata
        })
      }
      
      return
    }
    
    // 心跳消息
    if (realType === 'heartbeat') {
      connectionStatus.value = 'connected'
      return
    }
    
  } catch (e) {
    console.error('处理消息失败:', e)
  }
}

// 滚动到内容的底部
const scrollToBottom = (containerRef) => {
  nextTick(() => {
    if (containerRef.value) {
      containerRef.value.scrollTop = containerRef.value.scrollHeight
    }
  })
}

// 滚动到链条的右侧
const scrollToRight = (containerRef) => {
  nextTick(() => {
    if (containerRef.value) {
      containerRef.value.scrollLeft = containerRef.value.scrollWidth
    }
  })
}

// 连接SSE服务器
const connect = async (forceReconnect = false) => {
  if (isConnecting.value) return // 避免重复连接
  
  isConnecting.value = true
  connectionStatus.value = 'connecting'
  
  try {
    // 如果已有连接，先断开
    if (isConnected.value || eventSource.value) {
      await disconnect()
    }

    // 创建SSE连接
    const es = connectSSE(props.userId)

    // 校验连接对象是否有效
    if (!es || typeof es.addEventListener !== 'function') {
      throw new Error('connectSSE 返回的不是有效的 EventSource')
    }
    
    eventSource.value = es
    
    // 封装连接成功/失败的Promise
    const connectPromise = new Promise((resolve, reject) => {
      es.onopen = () => {
        console.log('✅ SSE连接成功')
        resolve('success')
      }
      
      es.onerror = (error) => {
        console.error('❌ SSE错误:', error)
        if (es.readyState === 2) {
          console.log('连接已关闭')
          reject('closed')
          return
        }
        reject(error)
      }
    })
    
    // 监听默认消息
    es.onmessage = (event) => {
      console.log('📨 [onmessage] 原始数据:', event.data)
      try {
        let data = JSON.parse(event.data)
        if (typeof data === 'string') {
          data = JSON.parse(data)
        }
        if (data.type) {
          processMessage(data.type, data)
        } else {
          processMessage('message', data)
        }
      } catch (e) {
        console.error('JSON解析失败:', e, '原始数据:', event.data)
        processMessage('message', event.data)
      }
    }
    
    // 监听各类自定义事件
    const eventTypes = ['connection', 'disconnect', 'message', 'json', 'heartbeat', 
      'mindmap_stream', 'animation_stream', 'chat_stream', 'extension_stream', 
      'paper_stream', 'practice_stream', 'video_stream', 'word_stream', 'stream',
      'study_plan_stream', 'super_agent_stream', 'ppt_stream']
    eventTypes.forEach(type => {
      es.addEventListener(type, (event) => {
        console.log(`📨 [${type}] 原始数据:`, event.data)
        try {
          let data = JSON.parse(event.data)
          if (typeof data === 'string') {
            data = JSON.parse(data)
          }
          console.log(`📨 [${type}] 解析后 data.type:`, data.type)
          processMessage(data.type || type, data)
        } catch (e) {
          console.error(`[${type}] JSON解析失败:`, e)
          processMessage(type, event.data)
        }
      })
    })
    
    try {
      // 等待连接结果
      await connectPromise
      isConnected.value = true
      connectionStatus.value = 'connected'
      startDurationTimer()
      
      // 强制重连模式：成功后断开再连一次
      if (forceReconnect) {
        await new Promise(resolve => setTimeout(resolve, 1500))
        await disconnect()
        await connect(false)
      }
    } catch (error) {
      isConnected.value = false
      connectionStatus.value = 'error'
      emit('error', error)
      
      // 强制重连模式：失败后重试一次
      if (forceReconnect) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        await connect(false)
      }
    }
    
  } catch (error) {
    console.error('创建SSE连接失败:', error)
    isConnecting.value = false
    connectionStatus.value = 'error'
    emit('error', error)
    
    // 创建连接失败也重试一次
    if (forceReconnect) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      await connect(false)
    }
  } finally {
    isConnecting.value = false
  }
}

// 断开SSE连接
const disconnect = async () => {
  if (!isConnected.value && !eventSource.value) return
  
  // 关闭EventSource
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
  
  // 更新连接状态
  isConnected.value = false
  isConnecting.value = false
  connectionStatus.value = 'disconnected'
  stopDurationTimer()
  
  // 通知服务器断开
  try {
    await disconnectSSE(true, props.userId)
    emit('disconnected', { userId: props.userId })
  } catch (error) {
    console.warn('通知服务器断开失败:', error)
  }
}

// 选择会话
const selectSession = (sessionId) => {
  activeSessionId.value = sessionId
  viewMode.value = 'content'
}

// 清除单个会话
const clearSession = (sessionId) => {
  const index = sessions.value.findIndex(s => s.id === sessionId)
  if (index !== -1) {
    sessions.value.splice(index, 1)
    // 如果删除的是当前会话，切换到第一个或null
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = sessions.value.length > 0 ? sessions.value[0].id : null
    }
  }
}

// 清除所有会话
const clearAllSessions = () => {
  sessions.value = []
  activeSessionId.value = null
  projectCounter.value = 0
  pendingNodes.value = []
  pendingThinking.value = []
}

// 启动计时器
const startDurationTimer = () => {
  stopDurationTimer()
  connectStartTime.value = Date.now()
  durationTimer.value = setInterval(() => {
    if (connectStartTime.value) {
      const diff = Math.floor((Date.now() - connectStartTime.value) / 1000)
      if (diff < 60) {
        connectionDuration.value = diff + 's'
      } else if (diff < 3600) {
        connectionDuration.value = Math.floor(diff / 60) + 'm ' + (diff % 60) + 's'
      } else {
        connectionDuration.value = Math.floor(diff / 3600) + 'h ' + 
          Math.floor((diff % 3600) / 60) + 'm'
      }
    }
  }, 1000)
}

// 停止计时器
const stopDurationTimer = () => {
  if (durationTimer.value) {
    clearInterval(durationTimer.value)
    durationTimer.value = null
  }
  connectionDuration.value = '0s'
}

// 切换悬浮窗展开/折叠
async function toggleCollapse() {
  // 强制打开模式下不能折叠
  if (isForcedOpen.value && !collapsed.value) {
    return
  }
  
  if(collapsed.value){
    // 展开：先更新UI，再连接SSE（强制重连）
    collapsed.value = false
    emit('update:collapsed', collapsed.value)
    emit('toggle', collapsed.value)
    await connect(true)
  }else{
    // 折叠：先断开SSE，再更新UI
    await disconnect()
    collapsed.value = true
    emit('update:collapsed', collapsed.value)
    emit('toggle', collapsed.value)
  }
}

// 处理学习方案选择
const handlePlanSelect = (plan) => {
  console.log('选择了学习方案:', plan)
}

// 获取目标元素（用于滚动）
const getTargetElement = () => {
  return wrapperEl.value
}

// 暴露方法（用于父组件调用）
defineExpose({
  toggleCollapse,
  collapsed,
  connect,
  disconnect,
  isConnected,
  isConnecting,
  connectionStatus,
  connectionDuration,
  sessions,
  activeSessionId,
  planOptions,
  handlePlanSelect,
  getTargetElement
})

let observer = null

onMounted(async () => {
  // 监听节点容器变化，滚动到右侧
  observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.addedNodes.length > 0) {
        nextTick(() => {
          if (nodesContainer.value) {
            nodesContainer.value.scrollLeft = nodesContainer.value.scrollWidth
          }
        })
      }
    })
  })
  
  if (nodesContainer.value) {
    observer.observe(nodesContainer.value, { childList: true })
  }
  
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      if (router.currentRoute.value.path.includes('aiAnswer') && user.isBuildProfile === 0) {
        isForcedOpen.value = true
        if (collapsed.value) {
          await new Promise(resolve => setTimeout(resolve, 3000))
          collapsed.value = false
          await connect()
        }
      }
    } catch (e) {
      console.error('解析用户信息失败:', e)
    }
  }
  
  watch(() => router.currentRoute.value.path, async (newPath) => {
    const userStr = localStorage.getItem('loginUser')
    if (userStr) {
      try {
        const user = JSON.parse(userStr)
        if (newPath.includes('aiAnswer') && user.isBuildProfile === 0) {
          isForcedOpen.value = true
          if (collapsed.value) {
            await new Promise(resolve => setTimeout(resolve, 3000))
            collapsed.value = false
            await connect()
          }
        } else {
          isForcedOpen.value = false
        }
      } catch (e) {
        console.error('解析用户信息失败:', e)
      }
    }
  })
})

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
  
  stopDurationTimer()
  
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
  
})

</script>

<template>
  <div
    ref="wrapperEl"
    class="float-wrapper"
    :class="{ collapsed: collapsed }"
  >
    <div class="float-window">
      <div class="window-header">
        <div class="title">
          <span class="icon-only">◈</span>
          <span>{{ title }}</span>
        </div>
        <div class="header-right">
          <div class="connection-indicator" :class="connectionStatus">
            <span class="dot-small" :class="connectionStatus"></span>
          </div>
          <button 
            @click.stop="connect" 
            :disabled="isConnected || isConnecting"
            class="header-btn btn-connect"
            :title="'建立连接'"
          >
            {{ isConnecting ? '稍后' : '连接' }}
          </button>
          <button 
            @click.stop="disconnect" 
            :disabled="!isConnected"
            class="header-btn btn-disconnect"
            :title="'断开连接'"
          >
            断开
          </button>
          <button 
            class="session-list-btn" 
            @click.stop="viewMode = viewMode === 'content' ? 'list' : 'content'"
            :title="'项目列表'"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
              <line x1="15" y1="3" x2="15" y2="21"/>
            </svg>
            <span v-if="sessions.length > 0" class="session-count">{{ sessions.length }}</span>
          </button>
        </div>
      </div>

      <div class="window-body">
        <div class="body-card">
          <template v-if="viewMode === 'list'">
            <div class="list-header">
              <span>项目列表</span>
              <button @click="clearAllSessions" class="list-clear" v-if="sessions.length > 0">清空</button>
            </div>
            <div class="list-container">
              <div 
                v-for="session in sortedSessions" 
                :key="session.id"
                class="list-item"
                :class="{ active: session.id === activeSessionId }"
                @click="selectSession(session.id)"
              >
                <div class="list-item-left">
                  <span class="list-item-icon">{{ session.status === 'running' ? '●' : '○' }}</span>
                  <div class="list-item-info">
                    <span class="list-item-id">第{{ session.projectNumber }}个项目链</span>
                    <span class="list-item-time">{{ formatTime(session.timestamp) }}</span>
                  </div>
                </div>
                <span class="list-item-status" :class="session.status">{{ getSessionStatusText(session.status) }}</span>
                <button @click.stop="clearSession(session.id)" class="list-item-delete">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
              <div v-if="sessions.length === 0" class="empty-section">
                暂无项目数据
              </div>
            </div>
          </template>

          <template v-else>
            <div v-if="activeSession" class="session-header">
              <span class="session-title">第{{ activeSession.projectNumber }}个项目</span>
              <span class="session-status-badge" :class="activeSession.status">{{ getSessionStatusText(activeSession.status) }}</span>
            </div>

            <div class="node-pipeline" ref="nodesContainer">
              <template v-if="activeSession?.nodes.length > 0">
                <template v-for="(node, index) in activeSession.nodes" :key="node.node">
                  <div 
                    class="pipe-node"
                    :class="getNodeStatusClass(node.status)"
                  >
                    <span class="pipe-icon">{{ getNodeMeta(node.node).icon }}</span>
                    <span class="pipe-label">{{ getNodeMeta(node.node).label }}</span>
                    <span class="node-status-dot"></span>
                  </div>
                  <div v-if="index < activeSession.nodes.length - 1" class="pipe-arrow">→</div>
                </template>
              </template>
              <div v-else class="empty-section">
                暂无节点数据
              </div>
            </div>

            <div class="thinking-panel">
              <div class="thinking-header">
                <span>🧠 LLM 实时思考</span>
                <span class="thinking-node-badge">{{ activeSession?.thinking[activeSession.thinking.length - 1]?.node || '-' }}</span>
              </div>
              <div class="thinking-body" ref="thinkingContainer" v-html="activeSession?.thinking.map(t => highlightThinkingContent(t.content)).join('\n') || '暂无思考内容'"></div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <button 
      v-if="!isForcedOpen" 
      class="toggle-btn" 
      @click.stop="toggleCollapse" 
      :title="collapsed ? '展开' : '折叠'"
    >
      {{ collapsed ? '▶' : '◀' }}
    </button>
  </div>

  <Transition name="fade">
    <div 
      v-if="showPlanDialog" 
      class="plan-dialog-mask" 
      @click="planOptions.length > 0 ? () => {} : (showPlanDialog = false)"
    >
      <div class="plan-dialog" @click.stop>
        <button 
          v-if="planOptions.length === 0" 
          class="plan-dialog-close" 
          @click.stop="showPlanDialog = false"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
        <PlanSelector 
          :plans="planOptions" 
          :user-id="props.userId"
          :is-view-mode="planOptions.length === 0"
          @select="(plan) => { handlePlanSelect(plan); showPlanDialog = false; }" 
        />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.float-wrapper {
  position: fixed;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 99;
  display: flex;
  align-items: center;
}

.float-window {
  width: 320px;
  max-width: calc(100vw - 20px);
  max-height: 600px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 0 20px 20px 0;
  box-shadow: 0 16px 48px rgba(0, 20, 40, 0.18), 4px 0 12px rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-left: none;
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
  transform: translateX(-20px);
  pointer-events: none;
}

.toggle-btn {
  width: 44px;
  height: 56px;
  border-radius: 0 14px 14px 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-left: none;
  box-shadow: 4px 0 16px rgba(0, 20, 40, 0.10), 0 4px 12px rgba(0, 0, 0, 0.04);
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
  border-radius: 0 14px 14px 0;
  box-shadow: 4px 0 16px rgba(0, 20, 40, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04);
  margin-left: 0;
}

.float-wrapper.collapsed .toggle-btn {
  border-radius: 0 16px 16px 0;
  box-shadow: 4px 0 20px rgba(0, 20, 40, 0.15), 0 4px 12px rgba(0, 0, 0, 0.06);
  width: 48px;
  height: 64px;
  font-size: 1.4rem;
}

.toggle-btn:hover {
  background: rgba(255, 255, 255, 1);
  box-shadow: 4px 0 24px rgba(0, 20, 40, 0.20);
  transform: scale(1.02);
}

.window-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px 12px 20px;
  background: transparent;
  min-height: 48px;
  border-bottom: 1px solid rgba(44, 62, 107, 0.06);
  flex-shrink: 0;
  position: relative;
}

.window-header .title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 0.95rem;
  color: #1f2a3f;
  pointer-events: none;
}

.window-header .title .icon-only {
  background: linear-gradient(135deg, #2D7DDB, #5094E4);
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.connection-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.connection-indicator.connected {
  background: #22c55e;
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
  animation: pulse 2s ease-in-out infinite;
}

.connection-indicator.connecting {
  background: #f59e0b;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.5);
  animation: pulse 1s ease-in-out infinite;
}

.connection-indicator.disconnected {
  background: #94a3b8;
}

.connection-indicator.error {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

.dot-small {
  display: none;
}

.session-list-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(44, 62, 107, 0.05);
  border-radius: 8px;
  color: #2c3e6b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: all 0.2s;
}

.session-list-btn:hover {
  background: rgba(44, 62, 107, 0.1);
}

.session-list-btn svg {
  width: 18px;
  height: 18px;
}

.session-count {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 16px;
  height: 16px;
  background: #ef4444;
  color: white;
  font-size: 10px;
  font-weight: 600;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
}

.header-btn {
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.header-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.header-btn.btn-connect {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.header-btn.btn-connect:hover:not(:disabled) {
  background: rgba(34, 197, 94, 0.25);
}

.header-btn.btn-disconnect {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.header-btn.btn-disconnect:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.25);
}

.window-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.body-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: rgba(44, 62, 107, 0.05);
  border-radius: 8px;
  margin-bottom: 16px;
}

.session-title {
  font-size: 13px;
  font-weight: 600;
  color: #2c3e6b;
}

.session-status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.session-status-badge.running {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.session-status-badge.completed {
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
}

.node-pipeline { 
  padding: 16px 30px; 
  background: #f8f9ff; 
  border-radius: 10px;
  margin-bottom: 16px;
  overflow-x: auto;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 2px solid #eef0ff;
}

.pipe-node {
  display: inline-flex; 
  align-items: center; 
  gap: 6px;
  padding: 6px 14px; 
  border-radius: 20px;
  font-size: 12px; 
  font-weight: 500;
  background: #f0f0f0; 
  color: #999;
  border: 2px solid transparent;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.pipe-node .pipe-icon { 
  font-size: 14px; 
}

.pipe-arrow { 
  display: flex;
  align-items: center;
  justify-content: center;
  color: #aaa; 
  font-size: 14px; 
  font-weight: bold;
  width: 20px;
  min-width: 20px;
  height: 20px;
  flex-shrink: 0;
  flex-grow: 0;
}

.pipe-node.idle { 
  background: #f0f0f0; 
  color: #bbb; 
  border-color: transparent; 
}

.pipe-node.pending { 
  background: #fff3cd; 
  color: #856404; 
  border-color: #ffc107; 
}

.pipe-node.active {
  background: linear-gradient(135deg, #2D7DDB 0%, #5094E4 100%);
  color: #fff;
  border-color: #2D7DDB;
  box-shadow: 0 0 20px rgba(45,125,219,0.5);
  animation: nodePulse 1.2s ease-in-out infinite;
}

.pipe-node.completed { 
  background: #d4edda; 
  color: #155724; 
  border-color: #28a745; 
}

.pipe-node.error { 
  background: #f8d7da; 
  color: #721c24; 
  border-color: #dc3545; 
  animation: nodeShake 0.5s ease-in-out; 
}

@keyframes nodePulse {
  0%, 100% { box-shadow: 0 0 10px rgba(45,125,219,0.4); transform: scale(1); }
  50% { box-shadow: 0 0 25px rgba(45,125,219,0.7); transform: scale(1.05); }
}

@keyframes nodeShake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}

.node-status-dot {
  width: 8px; 
  height: 8px; 
  border-radius: 50%; 
  display: inline-block;
}

.pipe-node.active .node-status-dot {
  background: #fff; 
  animation: dotFlash 0.6s ease-in-out infinite;
}

.pipe-node.completed .node-status-dot { 
  background: #28a745; 
}

.pipe-node.error .node-status-dot { 
  background: #dc3545; 
}

@keyframes dotFlash {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.thinking-panel {
  background: #1a1a2e;
  border: 1px solid #2d2d5e;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}

.thinking-header {
  display: flex; 
  align-items: center; 
  justify-content: space-between;
  padding: 10px 16px;
  background: linear-gradient(135deg, #2D7DDB22, #5094E422);
  border-bottom: 1px solid #2d2d5e;
  font-size: 13px; 
  font-weight: 600; 
  color: #a8b2ff;
}

.thinking-node-badge {
  background: #2D7DDB44;
  padding: 2px 10px; 
  border-radius: 10px;
  font-size: 11px; 
  color: #c8d0ff;
}

.thinking-body {
  padding: 12px 16px;
  max-height: 300px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.7;
  color: #e0e0ff;
  font-family: 'Menlo', 'Monaco', 'Cascadia Code', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

.thinking-body::-webkit-scrollbar {
  width: 6px;
}

.thinking-body::-webkit-scrollbar-thumb {
  background: #2d2d5e; 
  border-radius: 3px;
}

.thinking-body::-webkit-scrollbar-track {
  background: transparent;
}

.thinking-body :deep(.thinking-h1),
.thinking-body :deep(.thinking-h2),
.thinking-body :deep(.thinking-h3) {
  font-weight: 600;
  margin-top: 10px;
  margin-bottom: 5px;
  line-height: 1.4;
}
.thinking-body :deep(.thinking-h1) { font-size: 16px; color: #fff; }
.thinking-body :deep(.thinking-h2) { font-size: 15px; color: #e8e8ff; }
.thinking-body :deep(.thinking-h3) { font-size: 14px; color: #d0d0ff; }
.thinking-body :deep(.thinking-p) {
  margin: 3px 0;
  line-height: 1.7;
}
.thinking-body :deep(strong) {
  font-weight: 600;
  color: #fff;
}
.thinking-body :deep(em) {
  font-style: italic;
  color: #b0b8ff;
}
.thinking-body :deep(.thinking-code) {
  background: #1a1a3e;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  color: #48dbfb;
  border: 1px solid #2d2d5e;
}
.thinking-body :deep(.thinking-ul) {
  padding-left: 20px;
  margin: 5px 0;
}
.thinking-body :deep(.thinking-li) {
  margin: 3px 0;
  line-height: 1.6;
}
.thinking-body :deep(.thinking-blockquote) {
  border-left: 3px solid #48dbfb;
  padding-left: 10px;
  margin: 6px 0;
  color: #a0a8ff;
  font-style: italic;
}
.thinking-body :deep(.thinking-link) {
  color: #48dbfb;
  text-decoration: none;
}
.thinking-body :deep(.thinking-link:hover) {
  text-decoration: underline;
}

.thinking-tag {
  display: inline-block;
  font-size: 10px; 
  padding: 0 6px; 
  border-radius: 3px;
  background: #5094E444; 
  color: #5094E4;
  margin-right: 6px;
}

.thinking-llm-start {
  color: #48dbfb; 
  font-weight: 600;
}

.thinking-llm-end {
  color: #ff9ff3; 
  font-weight: 600;
}

.thinking-llm-error {
  color: #ff6b6b; 
  font-weight: 600;
}

.thinking-token {
  color: #a8e6cf;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #f1f3f5;
  font-size: 14px;
  font-weight: 600;
  color: #2c3e6b;
  margin-bottom: 8px;
}

.list-clear {
  font-size: 11px;
  color: #94a3b8;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px 6px;
}

.list-clear:hover {
  color: #ef4444;
}

.list-container {
  max-height: 400px;
  overflow-y: auto;
}

.list-item {
  display: flex;
  align-items: center;
  padding: 12px;
  cursor: pointer;
  transition: background 0.2s;
  border-radius: 8px;
  margin-bottom: 4px;
}

.list-item:hover {
  background: #f8fafc;
}

.list-item.active {
  background: #e0f2fe;
}

.list-item-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.list-item-icon {
  font-size: 10px;
}

.list-item.active .list-item-icon {
  color: #22c55e;
}

.list-item-info {
  display: flex;
  flex-direction: column;
}

.list-item-id {
  font-size: 13px;
  font-weight: 500;
  color: #2c3e6b;
}

.list-item-time {
  font-size: 11px;
  color: #94a3b8;
}

.list-item-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  margin-right: 8px;
}

.list-item-status.running {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.list-item-status.completed {
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
}

.list-item-delete {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;
}

.list-item:hover .list-item-delete {
  opacity: 1;
}

.list-item-delete:hover {
  background: rgba(239, 68, 68, 0.1);
}

.list-item-delete svg {
  width: 14px;
  height: 14px;
  color: #94a3b8;
}

.list-item-delete:hover svg {
  color: #ef4444;
}

.empty-section {
  text-align: center;
  padding: 20px;
  color: #94a3b8;
  font-size: 13px;
}

.plan-dialog-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

.plan-dialog {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  max-width: 900px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  position: relative;
  animation: slideUp 0.3s ease;
}

.plan-dialog-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  transition: all 0.2s;
}

.plan-dialog-close:hover {
  background: rgba(0, 0, 0, 0.1);
  color: #1f2a3f;
}

.plan-dialog-close svg {
  width: 18px;
  height: 18px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
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
  border-bottom-color: rgba(71, 85, 105, 0.3);
}

.dark .window-header .title {
  color: var(--text-title);
}

/* 会话列表按钮 */
.dark .session-list-btn {
  background: rgba(71, 85, 105, 0.2);
  color: var(--text-body);
}

.dark .session-list-btn:hover {
  background: rgba(71, 85, 105, 0.35);
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

/* 节点管线 */
.dark .node-pipeline {
  background: rgba(59, 130, 246, 0.05);
  border-bottom-color: rgba(59, 130, 246, 0.2);
}

/* 管道节点 */
.dark .pipe-node {
  background: rgba(71, 85, 105, 0.3);
  color: var(--text-gray);
}

.dark .pipe-arrow {
  color: var(--text-gray);
}

.dark .pipe-node.idle {
  background: rgba(71, 85, 105, 0.2);
  color: var(--text-gray);
}

.dark .pipe-node.pending {
  background: rgba(251, 146, 60, 0.15);
  color: #fb923c;
  border-color: rgba(251, 146, 60, 0.3);
}

.dark .pipe-node.completed {
  background: rgba(74, 222, 128, 0.15);
  color: #4ade80;
  border-color: rgba(74, 222, 128, 0.3);
}

.dark .pipe-node.error {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.3);
}

/* 规划对话框 */
.dark .plan-dialog {
  background: var(--bg-card);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.dark .plan-dialog-close {
  background: rgba(71, 85, 105, 0.2);
  color: var(--text-gray);
}

.dark .plan-dialog-close:hover {
  background: rgba(71, 85, 105, 0.4);
  color: var(--text-body);
}

</style>

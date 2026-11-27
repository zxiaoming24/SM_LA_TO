<!-- src/utils/RadarScanner.vue -->
<!-- 雷达扫描样式 -->
<script setup>
import { ref, computed, watch, onMounted } from 'vue'

// ==================== Props 定义 ====================
const props = defineProps({
  // 扫描到的目标数量
  targetCount: {
    type: Number,
    default: 0
  },
  // 是否正在扫描
  scanning: {
    type: Boolean,
    default: false
  },
  // 自定义标签文字
  label: {
    type: String,
    default: 'SCANNING'
  },
  // 是否显示状态文字
  showStatus: {
    type: Boolean,
    default: true
  },
  // 容器尺寸 (px)
  size: {
    type: Number,
    default: 280
  },
  // 主色调
  color: {
    type: String,
    default: '#2D7DDB'
  }
})

// ==================== 响应式数据 ====================
const radarContainer = ref(null)// 雷达容器
const activeTargets = ref([])// 当前显示的目标
let targetIdCounter = 0// 目标 ID 计数器
const currentStatus = ref('等待扫描...')

// ==================== 计算属性 ====================
const displayLabel = computed(() => {// 显示的标签文字
  return props.scanning ? props.label : 'SCAN COMPLETE'
})

// ==================== 内部方法 ====================
// 生成随机位置坐标
const generateRandomPosition = () => {
  const center = props.size / 2
  const maxRadius = props.size * 0.4
  const minRadius = 20
  
  const angle = Math.random() * 360
  const radius = minRadius + Math.random() * (maxRadius - minRadius)
  const radian = (angle * Math.PI) / 180
  
  return {
    x: center + radius * Math.cos(radian),
    y: center + radius * Math.sin(radian)
  }
}

// 添加一个目标光点
const addTarget = () => {
  const { x, y } = generateRandomPosition()
  const delay = activeTargets.value.length * 0.1
  
  const newTarget = {
    id: targetIdCounter++,
    x: x,
    y: y,
    visible: false,
    pulsing: false,
    delay: delay
  }
  
  activeTargets.value.push(newTarget)
  
  // 延迟显示并添加脉冲动画
  setTimeout(() => {
    const target = activeTargets.value.find(t => t.id === newTarget.id)
    if (target) {
      target.visible = true
      setTimeout(() => {
        if (target) target.pulsing = true
      }, 100)
    }
  }, 300)
  
  return newTarget.id
}

// 移除最后一个目标光点
const removeTarget = () => {
  if (activeTargets.value.length > 0) {
    activeTargets.value.pop()
  }
}

// 清除所有目标
const clearTargets = () => {
  activeTargets.value = []
  targetIdCounter = 0
}

// 批量添加目标
const addTargets = (count) => {
  for (let i = 0; i < count; i++) {
    setTimeout(() => {
      addTarget()
    }, i * 200)
  }
}

// 设置状态文字
const setStatus = (text) => {
  currentStatus.value = text
}

// 重置雷达
const reset = () => {
  clearTargets()
  currentStatus.value = '等待扫描...'
}

// ==================== 监听器 ====================
watch(() => props.targetCount, (newVal, oldVal) => {
  if (newVal > oldVal) {
    addTarget()
  } else if (newVal < oldVal) {
    removeTarget()
  }
})

watch(() => props.scanning, (newVal) => {
  currentStatus.value = newVal ? '正在扫描...' : '扫描完成'
})

// ==================== 生命周期 ====================
onMounted(() => {
  // 设置 CSS 变量
  if (radarContainer.value) {
    radarContainer.value.style.setProperty('--primary', props.color)
  }
})

// ==================== 暴露方法 ====================
defineExpose({
  addTarget,
  removeTarget,
  clearTargets,
  addTargets,
  setStatus,
  reset
})
</script>


<template>
  <div class="radar-scanner">
    <div 
      ref="radarContainer" 
      class="radar-container"
      :style="{ width: size + 'px', height: size + 'px' }"
    >
      <!-- 网格线 -->
      <div class="radar-grid">
        <div class="ring"></div>
        <div class="ring"></div>
        <div class="ring"></div>
        <div class="ring"></div>
      </div>
      
      <!-- 扫描扇形 -->
      <div class="radar-sweep"></div>
      
      <!-- 中心点 -->
      <div class="radar-center"></div>
      
      <!-- 扫描到的目标光点 -->
      <div
        v-for="target in activeTargets"
        :key="target.id"
        class="radar-blip"
        :class="{ 
          found: target.visible, 
          pulsing: target.pulsing 
        }"
        :style="{
          left: target.x + 'px',
          top: target.y + 'px',
          transitionDelay: target.delay + 's'
        }"
      ></div>
      
      <!-- 底部标签 -->
      <div class="radar-label">{{ displayLabel }}</div>
    </div>
    
    <!-- 状态信息 -->
    <div v-if="showStatus" class="radar-status">{{ currentStatus }}</div>
  </div>
</template>

<style scoped>
.radar-scanner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.radar-container {
  position: relative;
  border-radius: 50%;
  background: #0a1628;
  overflow: hidden;
  border: 2px solid var(--primary, #2D7DDB);
  box-shadow: 0 0 30px rgba(45, 125, 219, 0.15);
}

/* 扫描扇形 */
.radar-sweep {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 50%;
  height: 2px;
  background: linear-gradient(90deg, var(--primary, #2D7DDB), transparent);
  transform-origin: left center;
  animation: radarSpin 2s linear infinite;
  z-index: 2;
}

.radar-sweep::after {
  content: '';
  position: absolute;
  right: 0;
  top: -4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--primary, #2D7DDB);
  box-shadow: 0 0 10px var(--primary, #2D7DDB);
}

@keyframes radarSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 网格线 */
.radar-grid {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  z-index: 0;
}

.ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(45, 125, 219, 0.15);
}

.ring:nth-child(1) { inset: 20%; }
.ring:nth-child(2) { inset: 40%; }
.ring:nth-child(3) { inset: 60%; }
.ring:nth-child(4) { inset: 80%; }

/* 中心点 */
.radar-center {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 8px;
  height: 8px;
  background: var(--primary, #2D7DDB);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  box-shadow: 0 0 8px var(--primary, #2D7DDB);
}

/* 底部标签 */
.radar-label {
  position: absolute;
  bottom: 12px;
  left: 0;
  right: 0;
  text-align: center;
  color: rgba(45, 125, 219, 0.7);
  font-size: 10px;
  z-index: 2;
  font-family: monospace;
  letter-spacing: 2px;
  font-weight: bold;
}

/* 目标光点 */
.radar-blip {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--primary, #2D7DDB);
  box-shadow: 0 0 8px var(--primary, #2D7DDB);
  z-index: 2;
  transform: translate(-50%, -50%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.radar-blip.found {
  opacity: 1;
}

.radar-blip.pulsing {
  animation: blipPulse 1.2s ease-in-out infinite;
}

@keyframes blipPulse {
  0%, 100% { 
    box-shadow: 0 0 5px var(--primary, #2D7DDB);
    transform: translate(-50%, -50%) scale(1);
  }
  50% { 
    box-shadow: 0 0 18px var(--primary, #2D7DDB), 0 0 30px rgba(45, 125, 219, 0.5);
    transform: translate(-50%, -50%) scale(1.3);
  }
}

/* 状态文字 */
.radar-status {
  text-align: center;
  font-size: 13px;
  color: #64748B;
  margin-top: 12px;
}

/* ===== 深色模式 ===== */
.dark .radar-status {
  color: #94a3b8;
}
</style>
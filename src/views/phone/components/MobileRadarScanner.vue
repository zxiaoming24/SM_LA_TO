<!-- 移动端雷达扫描样式 -->
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
  // 容器尺寸 (px) - 移动端默认更小
  size: {
    type: Number,
    default: 220
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
const displayLabel = computed(() => {
  return props.scanning ? props.label : 'SCAN COMPLETE'
})

// 容器样式
const containerStyle = computed(() => ({
  width: props.size + 'px',
  height: props.size + 'px'
}))

// ==================== 内部方法 ====================
// 生成随机位置坐标
const generateRandomPosition = () => {
  const center = props.size / 2
  const maxRadius = props.size * 0.4
  const minRadius = 15

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

// 清除所有目标
const clearTargets = () => {
  activeTargets.value = []
  targetIdCounter = 0
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
    if (activeTargets.value.length > 0) {
      activeTargets.value.pop()
    }
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
  reset,
  setStatus
})
</script>

<template>
  <div class="mobile-radar-scanner">
    <div
      ref="radarContainer"
      class="radar-container"
      :style="containerStyle"
    >
      <!-- 网格环线 -->
      <div class="radar-grid">
        <div class="ring"></div>
        <div class="ring"></div>
        <div class="ring"></div>
        <div class="ring"></div>
        <div class="cross-line horizontal"></div>
        <div class="cross-line vertical"></div>
      </div>

      <!-- 扫描扇形（旋转 conic-gradient） -->
      <div class="radar-sweep" v-if="scanning"></div>

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
.mobile-radar-scanner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  /* 防止移动端点击高亮 */
  -webkit-tap-highlight-color: transparent;
}

.radar-container {
  position: relative;
  border-radius: 50%;
  background: radial-gradient(circle, #0d1f38 0%, #081428 100%);
  overflow: hidden;
  border: 2px solid var(--primary, #2D7DDB);
  box-shadow: 0 0 20px rgba(45, 125, 219, 0.2), inset 0 0 20px rgba(45, 125, 219, 0.05);
  /* 移动端触控优化 */
  touch-action: manipulation;
}

/* 扫描扇形 - conic-gradient 旋转 */
.radar-sweep {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    transparent 0deg,
    rgba(45, 125, 219, 0) 270deg,
    rgba(45, 125, 219, 0.15) 320deg,
    var(--primary, #2D7DDB) 360deg
  );
  animation: radarSpin 2.5s linear infinite;
  z-index: 1;
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
  border: 1px solid rgba(45, 125, 219, 0.18);
}

.ring:nth-child(1) { inset: 10%; }
.ring:nth-child(2) { inset: 25%; }
.ring:nth-child(3) { inset: 40%; }
.ring:nth-child(4) { inset: 50%; }

/* 十字交叉线 */
.cross-line {
  position: absolute;
  background: rgba(45, 125, 219, 0.12);
}

.cross-line.horizontal {
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  transform: translateY(-50%);
}

.cross-line.vertical {
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  transform: translateX(-50%);
}

/* 中心点 */
.radar-center {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  background: var(--primary, #2D7DDB);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  box-shadow: 0 0 6px var(--primary, #2D7DDB);
}

/* 底部标签 */
.radar-label {
  position: absolute;
  bottom: 10px;
  left: 0;
  right: 0;
  text-align: center;
  color: rgba(45, 125, 219, 0.75);
  font-size: 9px;
  z-index: 2;
  font-family: monospace;
  letter-spacing: 1.5px;
  font-weight: bold;
}

/* 目标光点 */
.radar-blip {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary, #2D7DDB);
  box-shadow: 0 0 6px var(--primary, #2D7DDB);
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
    box-shadow: 0 0 4px var(--primary, #2D7DDB);
    transform: translate(-50%, -50%) scale(1);
  }
  50% {
    box-shadow: 0 0 14px var(--primary, #2D7DDB), 0 0 22px rgba(45, 125, 219, 0.5);
    transform: translate(-50%, -50%) scale(1.4);
  }
}

/* 状态文字 */
.radar-status {
  text-align: center;
  font-size: 12px;
  color: #64748B;
  margin-top: 10px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ===== 深色模式 ===== */
.dark .radar-status {
  color: #94a3b8;
}

/* ===== 移动端小屏适配 ===== */
@media screen and (max-width: 360px) {
  .radar-label {
    font-size: 8px;
    letter-spacing: 1px;
  }

  .radar-status {
    font-size: 11px;
  }

  .radar-blip {
    width: 7px;
    height: 7px;
  }

  .radar-center {
    width: 5px;
    height: 5px;
  }
}
</style>

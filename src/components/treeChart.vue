<!-- 学习计划版本树 -->
<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElLoading, ElMessageBox } from 'element-plus'
import { changeVersionApi } from '@/api/mainApi/pathPlan.js'
import emitter from '@/utils/emitter.js'

const props = defineProps({
  versions: {
    type: Array,
    default: () => []
  },
  activePlanId: {
    type: String,
    default: ''
  },
  activeVersion: {
    type: Number,
    default: 0
  },
  userId: {
    type: String,
    default: ''
  }
})

const treeWrapper = ref(null)
const treeContainer = ref(null)
const activeDisplay = ref(null)

const typeColorMap = {
  initial: { label: '原始' },
  phase_completed: { label: '阶段完成' },
  phase_regenerated: { label: '重新生成' }
}

const buildLevels = (versions) => {
  if (!versions || versions.length === 0) return []

  const nodeMap = {}
  versions.forEach(v => {
    nodeMap[v.plan_id] = { ...v, children: [] }
  })

  let root = null
  versions.forEach(v => {
    const node = nodeMap[v.plan_id]
    if (v.parent_plan_id && nodeMap[v.parent_plan_id]) {
      nodeMap[v.parent_plan_id].children.push(node)
    } else {
      if (!root) root = node
    }
  })

  if (!root && versions.length > 0) {
    root = nodeMap[versions[0].plan_id]
  }

  const levels = []
  if (root) {
    const queue = [{ node: root, level: 0 }]
    while (queue.length > 0) {
      const { node, level } = queue.shift()
      if (!levels[level]) levels[level] = []
      levels[level].push(node)
      if (node.children && node.children.length > 0) {
        node.children.forEach(child => {
          queue.push({ node: child, level: level + 1 })
        })
      }
    }
  }
  return levels
}

const levels = computed(() => {
  return buildLevels(props.versions)
})

const calculateLevelHeights = (levels) => {
  if (!levels || levels.length === 0) return {}
  const heights = {}
  const NODE_HEIGHT = 120
  const GAP = 50
  levels.forEach((nodes, index) => {
    const count = nodes.length
    heights[index] = count * NODE_HEIGHT + (count - 1) * GAP
  })
  return heights
}

const getTriggerLabel = (triggerType) => {
  return typeColorMap[triggerType]?.label || '未知'
}

const drawConnections = () => {
  if (!treeContainer.value || !treeWrapper.value) return

  const container = treeContainer.value
  const wrapper = treeWrapper.value

  const oldSvg = document.getElementById('connectionsSvg')
  if (oldSvg) oldSvg.remove()

  const cards = container.querySelectorAll('.node-card')
  if (cards.length < 2) return

  const wrapperRect = wrapper.getBoundingClientRect()

  const nodePos = {}
  cards.forEach(card => {
    const rect = card.getBoundingClientRect()
    const planId = card.dataset.planId
    const level = parseInt(card.dataset.level) || 0
    nodePos[planId] = {
      x: rect.left - wrapperRect.left + rect.width / 2,
      yBottom: rect.top - wrapperRect.top + rect.height,
      yTop: rect.top - wrapperRect.top,
      yCenter: rect.top - wrapperRect.top + rect.height / 2,
      left: rect.left - wrapperRect.left,
      right: rect.left - wrapperRect.left + rect.width,
      width: rect.width,
      height: rect.height,
      level: level
    }
  })

  const versions = props.versions
  const parentMap = {}
  versions.forEach(v => {
    if (v.parent_plan_id) {
      if (!parentMap[v.parent_plan_id]) parentMap[v.parent_plan_id] = []
      parentMap[v.parent_plan_id].push(v.plan_id)
    }
  })

  const svgWidth = wrapper.scrollWidth || wrapper.clientWidth
  const svgHeight = wrapper.scrollHeight || wrapper.clientHeight

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('id', 'connectionsSvg')
  svg.setAttribute('class', 'connections-svg')
  svg.setAttribute('width', svgWidth)
  svg.setAttribute('height', svgHeight)
  svg.setAttribute('viewBox', `0 0 ${svgWidth} ${svgHeight}`)
  svg.style.position = 'absolute'
  svg.style.top = '0'
  svg.style.left = '0'
  svg.style.pointerEvents = 'none'
  svg.style.zIndex = '1'

  Object.keys(parentMap).forEach(parentId => {
    const parent = nodePos[parentId]
    if (!parent) return

    const children = parentMap[parentId]

    const childPositions = []
    children.forEach(childId => {
      const child = nodePos[childId]
      if (child) {
        childPositions.push({
          id: childId,
          y: child.yCenter,
          x: child.left,
          pos: child
        })
      }
    })

    if (childPositions.length === 0) return

    const minY = Math.min(...childPositions.map(c => c.y))
    const maxY = Math.max(...childPositions.map(c => c.y))
    const spreadY = (minY + maxY) / 2

    const startX = parent.x
    const minChildLeft = Math.min(...childPositions.map(c => c.x))

    const trunkPath = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    const trunkD = `M ${startX} ${parent.yBottom} L ${startX} ${spreadY}`
    trunkPath.setAttribute('d', trunkD)
    trunkPath.setAttribute('stroke', 'var(--tree-stroke, #c5d0e0)')
    trunkPath.setAttribute('stroke-width', '2')
    trunkPath.setAttribute('fill', 'none')
    trunkPath.setAttribute('stroke-linejoin', 'round')
    trunkPath.setAttribute('stroke-linecap', 'round')
    svg.appendChild(trunkPath)

    childPositions.forEach((childInfo) => {
      const child = childInfo.pos
      const childX = child.left
      const childY = child.yCenter

      const branchPath = document.createElementNS('http://www.w3.org/2000/svg', 'path')
      const branchD = `M ${startX} ${spreadY} L ${childX} ${spreadY} L ${childX} ${childY}`
      branchPath.setAttribute('d', branchD)
      branchPath.setAttribute('stroke', 'var(--tree-stroke, #c5d0e0)')
      branchPath.setAttribute('stroke-width', '2')
      branchPath.setAttribute('fill', 'none')
      branchPath.setAttribute('stroke-linejoin', 'round')
      branchPath.setAttribute('stroke-linecap', 'round')
      svg.appendChild(branchPath)

      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
      dot.setAttribute('cx', childX)
      dot.setAttribute('cy', childY)
      dot.setAttribute('r', '4')
      dot.setAttribute('fill', 'var(--tree-dot-fill, #a0b2cc)')
      svg.appendChild(dot)
    })
  })

  wrapper.style.position = 'relative'
  wrapper.appendChild(svg)
}

const triggerDrawConnections = () => {
  nextTick(() => {
    setTimeout(drawConnections, 50)
  })
}

watch(() => props.versions, () => {
  triggerDrawConnections()
}, { deep: true })

watch(() => props.activePlanId, () => {
  triggerDrawConnections()
})

let resizeTimer = null

onMounted(() => {
  triggerDrawConnections()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeTimer) clearTimeout(resizeTimer)
})

const handleResize = () => {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    drawConnections()
  }, 200)
}

const handleNodeClick = async (planId) => {
  if (!props.userId || !planId) return
  if (planId === props.activePlanId) {
    ElMessage.info('当前已是该版本')
    return
  }

  let loadingInstance = null
  try {
    await ElMessageBox.confirm(
      '确认切换到该版本？当前学习进度将被保存。',
      '切换版本',
      {
        confirmButtonText: '确认切换',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    loadingInstance = ElLoading.service({
      fullscreen: true,
      text: '切换版本中...',
      background: 'rgba(255, 255, 255, 0.9)'
    })

    const res = await changeVersionApi(props.userId, planId)
    if (res.code === 1) {
      ElMessage.success('版本切换成功')
      emitter.emit('versionChanged', {
        planId: planId,
        data: res.data
      })
    } else {
      ElMessage.error(res.msg || '版本切换失败')
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('切换版本异常', err)
      ElMessage.error('操作失败，请重试')
    }
  } finally {
    if (loadingInstance) loadingInstance.close()
  }
}

const formatVersionDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}
</script>

<template>
  <div class="container">

    <div class="tree-wrapper" ref="treeWrapper">
      <div class="tree-container" ref="treeContainer">
        <div v-if="versions.length === 0" class="empty-state">暂无版本数据</div>
        <template v-else>
          <div 
            v-for="(levelNodes, levelIndex) in levels" 
            :key="levelIndex"
            class="tree-level"
            :class="{ 'tree-level-root': levelIndex === 0 }"
            :style="levelIndex === 0 ? { paddingTop: (Math.max(...Object.values(calculateLevelHeights(levels)), 0) - (calculateLevelHeights(levels)[0] || 0)) / 2 + 'px' } : {}"
          >
            <div
              v-for="node in levelNodes"
              :key="node.plan_id"
              class="node-card"
              :class="[
                `type-${node.trigger_type}`,
                { 'is-active': node.plan_id === activePlanId || node.is_active }
              ]"
              :data-plan-id="node.plan_id"
              :data-parent-id="node.parent_plan_id || ''"
              :data-level="levelIndex"
              :style="{ marginLeft: levelIndex === 0 ? '0' : '30px' }"
              @click="handleNodeClick(node.plan_id)"
            >
              <div class="node-version">v{{ node.version_number }}</div>
              <div class="node-trigger">{{ node.trigger_description || getTriggerLabel(node.trigger_type) }}</div>
              <div class="phase-dots">
                <div
                  v-for="i in (node.phase_count || 0)"
                  :key="i"
                  class="phase-dot"
                  :class="{ completed: i <= (node.completed_phase_count || 0), incomplete: i > (node.completed_phase_count || 0) }"
                  :data-index="i"
                ></div>
              </div>
              <div class="node-meta">
                <span>{{ node.completed_phase_count || 0 }}/{{ node.phase_count || 0 }}</span>
                <span>{{ getTriggerLabel(node.trigger_type) }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.container {
  width: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 0 6px;
  flex-wrap: wrap;
  gap: 12px;
}

.tree-wrapper {
  width: 100%;
  overflow-x: auto;
  overflow-y: visible;
  padding: 10px 4px 10px 4px;
  position: relative;
}

.tree-container {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: center;
  min-width: fit-content;
  gap: 80px;
  padding: 30px 40px 60px 40px;
  position: relative;
}

.tree-level {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 50px;
  position: relative;
  min-width: 160px;
  z-index: 2;
}

.tree-level-root {
  justify-content: center;
}

.node-card {
  background: var(--tree-card-bg, white);
  border-radius: 14px;
  padding: 16px 20px 18px 20px;
  min-width: 140px;
  max-width: 190px;
  width: fit-content;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
  border: 2px solid var(--tree-card-border, #e9edf4);
  transition: background 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
  cursor: pointer;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  will-change: background, box-shadow, border-color;
  z-index: 5;
}

.node-card:not(.tree-level-root .node-card) {
  margin-left: 30px;
}

.node-card:hover {
  box-shadow: 0 6px 20px rgba(0, 20, 40, 0.08);
  border-color: var(--tree-card-hover-border, #b8c8dd);
  z-index: 10;
}

.dark .node-card:hover {
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.node-card.type-initial {
  border-left: 5px solid #2d7ddb;
}
.node-card.type-phase_completed {
  border-left: 5px solid #00b894;
}
.node-card.type-phase_regenerated {
  border-left: 5px solid #f39c12;
}

.node-card.is-active {
  background: #eef3ff;
  border-color: #1a5cff;
  box-shadow: 0 4px 20px rgba(26, 92, 255, 0.15);
}

.dark .node-card.is-active {
  background: rgba(59, 130, 246, 0.15);
  border-color: #3b82f6;
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.25);
}

.dark .node-card.is-active .node-version {
  color: #60a5fa;
}

.node-version {
  font-weight: 700;
  font-size: 19px;
  color: var(--tree-node-version, #0b1a2e);
  margin-bottom: 2px;
  transition: color 0.25s ease;
}

.node-trigger {
  font-size: 11px;
  color: var(--tree-node-trigger-text, #4d5f7a);
  background: var(--tree-node-trigger-bg, #f2f5fc);
  padding: 2px 14px;
  border-radius: 30px;
  font-weight: 500;
  margin: 4px 0 10px 0;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.phase-dots {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 4px;
  padding: 2px 0;
}

.phase-dot {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: var(--tree-phase-dot-bg, #eef2f7);
  border: 1.5px solid var(--tree-phase-dot-border, #d6dfe9);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  color: var(--tree-phase-dot-text, #8899b4);
  transition: background 0.2s, border-color 0.2s;
}

.phase-dot.completed {
  background: #00b894;
  border-color: #00a381;
  color: white;
}

.phase-dot.completed::after {
  content: "✓";
  font-size: 12px;
}

.phase-dot.incomplete {
  background: var(--tree-phase-dot-bg, #f0f4fe);
  border-color: var(--tree-phase-dot-border, #d6dfe9);
  color: var(--tree-phase-dot-text, #5a6f8c);
}

.phase-dot.incomplete::after {
  content: attr(data-index);
}

.node-meta {
  font-size: 10px;
  color: var(--tree-meta-text, #7b8aa3);
  margin-top: 6px;
  display: flex;
  gap: 10px;
  justify-content: center;
}

.node-meta span {
  background: var(--tree-meta-bg, #f4f7fd);
  padding: 0 8px;
  border-radius: 12px;
}

.empty-state {
  padding: 60px 20px;
  text-align: center;
  color: var(--tree-empty-text, #7b8aa3);
}

.connections-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}

.tree-level {
  z-index: 2;
}

@media (max-width: 1000px) {
  .tree-container {
    gap: 40px;
    padding: 20px 20px 40px 20px;
  }
  .tree-level {
    gap: 35px;
    min-width: 120px;
  }
}

@media (max-width: 700px) {
  .tree-container {
    gap: 24px;
    padding: 16px 12px 30px 12px;
  }
  .tree-level {
    gap: 24px;
    min-width: 90px;
  }
  .node-card {
    min-width: 80px;
    padding: 10px 12px 12px 12px;
  }
  .node-version {
    font-size: 15px;
  }
  .phase-dot {
    width: 18px;
    height: 18px;
    font-size: 8px;
  }
  .node-trigger {
    font-size: 9px;
    padding: 1px 8px;
  }
}
</style>
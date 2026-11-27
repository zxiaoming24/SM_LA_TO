<template>
  <div class="mindmap-level-wrapper">
    <!-- 节点 -->
    <div
      class="mindmap-node"
      :class="[
        `mindmap-level-${level}`,
        { 'has-children': hasChildren, collapsed: isCollapsed }
      ]"
      @click="handleClick"
      @dblclick="handleDblClick"
      :title="titleText"
    >
      <span class="node-label">{{ node.name }}</span>
      <span
        v-if="hasChildren"
        class="collapse-toggle"
        @click.stop="toggleCollapse"
      >
        {{ isCollapsed ? '+' : '−' }}
      </span>
    </div>

    <!-- 连接线 -->
    <div v-if="hasChildren && !isCollapsed" class="mindmap-connector"></div>

    <!-- 子节点 -->
    <div v-if="hasChildren && !isCollapsed" class="mindmap-level" :class="`mindmap-level-${level + 1}`">
      <MindmapNode
        v-for="(child, index) in node.children"
        :key="index"
        :node="child"
        :level="level + 1"
        @navigate="$emit('navigate', $event)"
        @edit="$emit('edit', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  level: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['navigate', 'edit'])

const isCollapsed = ref(false)

const hasChildren = computed(() => {
  return props.node.children && props.node.children.length > 0
})

const titleText = computed(() => {
  const kws = props.node.keywords || []
  return kws.length ? `关键词: ${kws.join('、')}` : ''
})

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function handleClick() {
  emit('navigate', props.node)
}

function handleDblClick() {
  emit('edit', props.node)
}
</script>

<style scoped>
.mindmap-level-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mindmap-node {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 60px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  position: relative;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 6px;
}

.mindmap-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.mindmap-level-0 .mindmap-node {
  padding: 10px 24px;
  background: #667eea;
  color: #fff;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
}

.mindmap-level-1 .mindmap-node {
  background: #eef0ff;
  border: 1px solid #d0d5ff;
  color: #444;
}

.mindmap-level-2 .mindmap-node {
  background: #fff;
  border: 1px solid #e0e0e0;
  color: #666;
  font-size: 12px;
}

.mindmap-node .collapse-toggle {
  width: 18px;
  height: 18px;
  background: #667eea;
  color: #fff;
  border: 2px solid #fff;
  border-radius: 50%;
  font-size: 11px;
  line-height: 14px;
  text-align: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.2s;
}
.mindmap-node .collapse-toggle:hover {
  transform: scale(1.1);
}

.mindmap-node.has-children .collapse-toggle {
  display: inline-block;
}
.mindmap-node:not(.has-children) .collapse-toggle {
  display: none;
}

.mindmap-node.collapsed .collapse-toggle {
  background: #999;
}

.mindmap-connector {
  width: 2px;
  height: 16px;
  background: #d0d5ff;
}

.mindmap-level {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 0;
}

.mindmap-level-1 {
  gap: 16px;
}
.mindmap-level-2 {
  gap: 10px;
}

/* 夜间模式 */
:root.dark .mindmap-node {
  background: #334155;
  border-color: #475569;
  color: #e2e8f0;
}

:root.dark .mindmap-level-0 .mindmap-node {
  background: #667eea;
  color: #fff;
}

:root.dark .mindmap-level-1 .mindmap-node {
  background: #1e293b;
  border-color: #475569;
  color: #cbd5e1;
}

:root.dark .mindmap-level-2 .mindmap-node {
  background: #334155;
  border-color: #475569;
  color: #94a3b8;
}

:root.dark .mindmap-node .collapse-toggle {
  background: #667eea;
  border-color: #1e293b;
}

:root.dark .mindmap-node.collapsed .collapse-toggle {
  background: #64748b;
}

:root.dark .mindmap-connector {
  background: #475569;
}
</style>
<!-- 视频思维导图递归节点组件 -->
<script>
import { ref, computed } from 'vue'

export default {
  name: 'MindmapNode',
  props: {
    node: {
      type: Object,
      required: true
    },
    depth: {
      type: Number,
      default: 0
    }
  },
  setup(props) {
    // 每个节点自己管理展开状态
    const isExpanded = ref(false)

    const hasChildren = computed(() => {
      return props.node.children && props.node.children.length > 0
    })

    const depthColors = [
      '#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399'
    ]

    const nodeColor = computed(() => {
      return depthColors[props.depth % depthColors.length]
    })

    const handleToggle = () => {
      if (hasChildren.value) {
        isExpanded.value = !isExpanded.value
      }
    }

    return {
      isExpanded,
      hasChildren,
      nodeColor,
      handleToggle
    }
  }
}
</script>

<template>
  <div class="mindmap-node" :class="{ 'is-root': depth === 0 }">
    <div class="node-header" @click="handleToggle">
      <div class="node-indicator" :style="{ backgroundColor: nodeColor }">
        <van-icon
          v-if="hasChildren"
          :name="isExpanded ? 'arrow-down' : 'arrow'"
          size="12"
          color="#fff"
        />
        <span v-else class="node-dot"></span>
      </div>
      <div class="node-content">
        <div class="node-name">{{ node.name || '未命名' }}</div>
        <div v-if="node.content" class="node-desc">{{ node.content }}</div>
      </div>
    </div>

    <div v-if="hasChildren && isExpanded" class="node-children">
      <MindmapNode
        v-for="(child, index) in node.children"
        :key="index"
        :node="child"
        :depth="depth + 1"
      />
    </div>
  </div>
</template>

<style scoped>
.mindmap-node {
  margin-left: 0;
}

.mindmap-node.is-root {
  margin-left: 0;
}

.node-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-page, #f7f8fa);
  border-radius: 8px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.node-header:active {
  background: var(--border-color, #eee);
}

.node-indicator {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.node-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
}

.node-content {
  flex: 1;
  min-width: 0;
}

.node-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title, #323233);
  line-height: 1.5;
}

.is-root .node-name {
  font-size: 16px;
  font-weight: 600;
}

.node-desc {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 4px;
  line-height: 1.6;
}

.node-children {
  margin-left: 20px;
  padding-left: 12px;
  border-left: 2px solid var(--border-color, #eee);
}
</style>

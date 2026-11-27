<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// 功能列表
const features = [
  {
    category: '智能工具',
    items: [
      { name: 'AI 图解', icon: 'photo-o', color: 'var(--primary)', bg: 'var(--primary-light)', path: '/phone/ai-image' },
      { name: '知识图谱', icon: 'cluster-o', color: 'var(--purple)', bg: 'var(--purple-bg)', path: '/phone/knowledge-map' },
      { name: '笔记', icon: 'notes-o', color: 'var(--pass)', bg: 'var(--pass-bg-color)', path: '/phone/note' },
      { name: '错题本', icon: 'failure', color: 'var(--main-delete)', bg: 'var(--main-fail-status)', path: '/phone/wrongQuestions' },
      { name: '学习计划', icon: 'clock-o', color: 'var(--coming)', bg: 'var(--coming-bg-color)', path: '/phone/pathPlan' },
      { name: '学习评估', icon: 'todo-list-o', color: 'var(--primary)', bg: 'var(--primary-light)', path: '/phone/evaluate' },
    ]
  },
  {
    category: '互动助学',
    items: [
      { name: '学伴', icon: 'friends-o', color: 'var(--pass)', bg: 'var(--pass-bg-color)', path: '/phone/partners' },
      { name: '帖子社区', icon: 'bullhorn-o', color: 'var(--purple)', bg: 'var(--purple-bg)', path: '/phone/post' },
      { name: '总排行榜', icon: 'medal-o', color: 'var(--main-delete)', bg: 'var(--main-fail-status)', path: '/phone/rank' },
      { name: '我的收藏', icon: 'star-o', color: 'var(--coming)', bg: 'var(--coming-bg-color)', path: '/phone/collection' }
    ]
  },
  {
    category: '资源库',
    items: [
      { name: '试卷', icon: 'orders-o', color: 'var(--primary)', bg: 'var(--primary-light)', path: '/phone/resource/paper' },
      { name: '拓展阅读', icon: 'label-o', color: 'var(--pass)', bg: 'var(--pass-bg-color)', path: '/phone/resource/reading' },
      { name: 'PPT', icon: 'notes-o', color: 'var(--main-delete)', bg: 'var(--main-fail-status)', path: '/phone/resource/ppt' },
      { name: '视频微课', icon: 'video-o', color: 'var(--coming)', bg: 'var(--coming-bg-color)', path: '/phone/resource/video' },
      { name: '思维导图', icon: 'cluster-o', color: 'var(--purple)', bg: 'var(--purple-bg)', path: '/phone/resource/mindmap' },
      { name: '讲解文档', icon: 'chat-o', color: 'var(--primary)', bg: 'var(--primary-light)', path: '/phone/resource/word' },
      { name: '编程练习', icon: 'aim', color: 'var(--pass)', bg: 'var(--pass-bg-color)', path: '/phone/resource/code' },
      { name: '动画', icon: 'flower-o', color: 'var(--main-delete)', bg: 'var(--main-fail-status)', path: '/phone/resource/anima' },
      { name: '知识点对比', icon: 'fire-o', color: 'var(--coming)', bg: 'var(--coming-bg-color)', path: '/phone/knowledge-comparison' },
      { name: '算法实验室', icon: 'points', color: 'var(--purple)', bg: 'var(--purple-bg)', path: '/phone/algorithm-lab' },
    ]
  },
]

// 点击功能项
const handleFeatureClick = (item) => {
  if (['/phone/ai-image', '/phone/rank', '/phone/post', '/phone/note', '/phone/evaluate', '/phone/partners', '/phone/resource/paper', '/phone/resource/reading', '/phone/resource/ppt', '/phone/resource/video', '/phone/resource/word', '/phone/resource/anima', '/phone/resource/mindmap', '/phone/resource/code', '/phone/knowledge-comparison', '/phone/algorithm-lab', '/phone/wrongQuestions', '/phone/pathPlan', '/phone/collection'].includes(item.path)) {
    router.push(item.path)
  } else {
    alert(`功能"${item.name}"正在开发中`)
  }
}
</script>

<template>
  <div class="phone-function">
    <div class="page-header">
      <img src="@/assets/logo/Logo.png" class="intro-logo" />
      <div class="header-text">
        <h2 class="page-title">功能中心</h2>
        <p class="page-desc">探索更多学习功能</p>
      </div>
    </div>

    <div class="function-content">
      <div v-for="group in features" :key="group.category" class="feature-group">
        <div class="group-title">{{ group.category }}</div>
        <div class="feature-grid">
          <div
            v-for="item in group.items"
            :key="item.name"
            class="feature-card"
            @click="handleFeatureClick(item)"
          >
            <div class="feature-icon" :style="{ background: item.bg, color: item.color }">
              <van-icon :name="item.icon" size="28" />
            </div>
            <span class="feature-name">{{ item.name }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-function {
  padding: 16px;
  padding-bottom: 60px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.intro-logo {
  width: 60px;
  height: 60px;
  flex-shrink: 0;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 4px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-gray);
}

.function-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.feature-group {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--border-color);
}

.group-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 16px;
  padding-left: 4px;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0px;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
}

.feature-card:active {
  background: var(--bg-hover);
  transform: scale(0.95);
}

.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-name {
  font-size: 12px;
  color: var(--text-body);
  text-align: center;
}
</style>

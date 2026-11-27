<script setup>
import { ref, onMounted } from 'vue'
import MobileRadarChart from './components/MobileRadarChart.vue'
import MobileStudyTrend from './components/MobileStudyTrend.vue'
import MobileWordCloud from './components/MobileWordCloud.vue'
import MobileCalendar from './components/MobileCalendar.vue'

const loginUser = ref(null)

onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser.value = JSON.parse(userStr)
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
})
</script>

<template>
  <div class="phone-home">
    <!-- 顶部欢迎 -->
    <div class="home-header">
      <div class="welcome-text">
        <h2>你好，{{ loginUser?.username || '同学' }}</h2>
        <p>今天也要加油学习哦</p>
      </div>
      <div class="avatar-wrap">
        <img v-if="loginUser?.avatar" :src="loginUser.avatar" class="user-avatar" />
        <div v-else class="avatar-placeholder">{{ (loginUser?.username || 'U').charAt(0) }}</div>
      </div>
    </div>

    <!-- 功能入口 -->
    <!-- <div class="feature-grid">
      <div class="feature-card">
        <div class="feature-icon" style="background: var(--primary-light); color: var(--primary);">
          <van-icon name="notes-o" size="28" />
        </div>
        <span class="feature-name">知识图谱</span>
      </div>
      <div class="feature-card">
        <div class="feature-icon" style="background: var(--pass-bg-color); color: var(--pass);">
          <van-icon name="question-o" size="28" />
        </div>
        <span class="feature-name">错题本</span>
      </div>
      <div class="feature-card">
        <div class="feature-icon" style="background: var(--coming-bg-color); color: var(--coming);">
          <van-icon name="chart-trending-o" size="28" />
        </div>
        <span class="feature-name">学习路径</span>
      </div>
      <div class="feature-card">
        <div class="feature-icon" style="background: var(--purple-bg); color: var(--purple);">
          <van-icon name="friends-o" size="28" />
        </div>
        <span class="feature-name">学习小组</span>
      </div>
    </div> -->

    <!-- 系统介绍 -->
    <div class="intro-card">
      <div class="intro-title">
        <img src="@/assets/logo/Logo.png" class="intro-logo" />
        <span>知行优课</span>
      </div>
      <p class="intro-desc">
        基于大模型的多智能体个性化学习系统，为你提供智能答疑、知识图谱构建、学习路径规划、错题分析等全方位学习服务。
      </p>
    </div>

    <!-- 您的画像 -->
    <div v-if="loginUser?.id" class="profile-section">
      <div class="section-title">
        <van-icon name="chart-trending-o" />
        <span>学情画像</span>
      </div>

      <!-- 学习日历 -->
      <MobileCalendar :user-id="loginUser.id" />

      <!-- 能力雷达图 -->
      <MobileRadarChart :user-id="loginUser.id" />

      <!-- 近七日学习时长 -->
      <MobileStudyTrend :user-id="loginUser.id" />


      <!-- 资源点击量词云 -->
      <MobileWordCloud :user-id="loginUser.id" />
    </div>
  </div>
</template>

<style scoped>
.phone-home {
  padding: 16px;
}

.home-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--grad-primary);
  border-radius: var(--radius-lg);
  color: #fff;
}

.welcome-text h2 {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}

.welcome-text p {
  font-size: 13px;
  opacity: 0.85;
}

.user-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(255, 255, 255, 0.5);
}

.avatar-placeholder {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

/* 功能入口 */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 8px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
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
  font-weight: 500;
}

/* 介绍卡片 */
.intro-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--border-color);
}

.intro-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 12px;
  font-family: "抖音美好体", "三极行楷简体-粗", sans-serif;
}

.intro-logo {
  width: 32px;
  height: 32px;
}

.intro-desc {
  font-size: 14px;
  color: var(--text-gray);
  line-height: 1.7;
}

/* 画像区域 */
.profile-section {
  margin-top: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
  margin-bottom: 12px;
  padding: 0 4px;
}

.section-title .van-icon {
  color: var(--primary);
}
</style>

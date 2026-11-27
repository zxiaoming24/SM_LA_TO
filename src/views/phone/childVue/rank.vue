<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getGlobalRankingApi, getUserInfoApi } from '@/api/mainApi/index.js'

const router = useRouter()
const goBack = () => router.back()

const rankList = ref([])
const rankLoading = ref(false)
const rankStats = ref({ total_users: 0, user_rank: 0, user_score: 0, top_score: 0 })
const rankWeights = ref({})
const expandedItem = ref(-1)

const userId = ref('')

const getDimensionPercent = (value) => {
  if (!value) return '0%'
  const percent = value > 1 ? value : value * 100
  return Math.min(percent, 100) + '%'
}

const getDimensionValue = (value) => {
  if (!value) return '0'
  const displayValue = value > 1 ? value : value * 100
  return Math.min(displayValue, 100).toFixed(0)
}

const fetchRanking = async () => {
  if (rankLoading.value) return
  rankLoading.value = true
  try {
    const res = await getGlobalRankingApi(100, userId.value)
    if (res.success || res.code === 1) {
      const data = res.data || res
      const rankings = data.rankings || []

      if (data.total_users !== undefined) rankStats.value.total_users = data.total_users
      if (data.user_rank !== undefined) rankStats.value.user_rank = data.user_rank
      const myRanking = rankings.find(r => String(r.user_id) === String(userId.value))
      if (myRanking && myRanking.composite_score !== undefined) {
        rankStats.value.user_score = myRanking.composite_score
      } else if (data.user_score !== undefined) {
        rankStats.value.user_score = data.user_score
      }
      if (rankings.length > 0) rankStats.value.top_score = rankings[0].composite_score

      if (data.weights) rankWeights.value = data.weights

      const userIdList = [...new Set(rankings.map(r => r.user_id))]
      if (userIdList.length > 0) {
        try {
          const userRes = await getUserInfoApi({ userIdList })
          if (userRes.code) {
            const userMap = {}
            userRes.data.forEach(u => { userMap[u.userId] = u })
            rankings.forEach(r => {
              const user = userMap[r.user_id]
              if (user) {
                r.username = user.username
                r.avatar = user.avatar
              } else {
                r.username = r.user_id
                r.avatar = ''
              }
            })
          }
        } catch (e) {
          console.error('获取排行榜用户信息失败:', e)
          rankings.forEach(r => { r.username = r.user_id; r.avatar = '' })
        }
      }

      const mappedList = rankings.map((r, idx) => ({
        id: r.user_id,
        username: r.username || r.user_id,
        avatar: r.avatar || '',
        score: r.composite_score,
        rank: r.rank || idx + 1,
        dimension_scores: r.dimension_scores || {},
        submission_stats: r.submission_stats || {}
      }))

      rankList.value = mappedList
    }
  } catch (e) {
    console.error('获取排行榜失败:', e)
  } finally {
    rankLoading.value = false
  }
}

const toggleExpand = (index) => {
  expandedItem.value = expandedItem.value === index ? -1 : index
}

const getMedalColor = (index) => {
  if (index === 0) return '#FFD700'
  if (index === 1) return '#C0C0C0'
  if (index === 2) return '#CD7F32'
  return ''
}

onMounted(() => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      const loginUser = JSON.parse(userStr)
      if (loginUser) userId.value = loginUser.id || loginUser.userId || ''
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  fetchRanking()
})
</script>

<template>
  <div class="phone-rank">
    <!-- 顶部导航栏 -->
    <div class="mobile-header">
      <div class="header-left" @click="goBack">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="header-title">积分排行榜</div>
      <div class="header-right"></div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row" v-if="rankStats.total_users > 0">
      <div class="stat-card">
        <div class="stat-value">{{ rankStats.total_users }}</div>
        <div class="stat-label">总用户</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ rankStats.user_rank || '-' }}</div>
        <div class="stat-label">我的排名</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ rankStats.user_score || '-' }}</div>
        <div class="stat-label">我的分数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ rankStats.top_score || '-' }}</div>
        <div class="stat-label">最高分</div>
      </div>
    </div>

    <!-- 权重信息 -->
    <div class="weights-row" v-if="rankWeights.coding_score">
      <span class="weights-title">评分权重:</span>
      <span class="weight-tag">编程 {{ (rankWeights.coding_score * 100).toFixed(0) }}%</span>
      <span class="weight-tag">准确 {{ (rankWeights.accuracy_score * 100).toFixed(0) }}%</span>
      <span class="weight-tag">时长 {{ (rankWeights.learning_time_score * 100).toFixed(0) }}%</span>
      <span class="weight-tag">做题 {{ (rankWeights.problem_count_score * 100).toFixed(0) }}%</span>
    </div>

    <!-- 排行列表 -->
    <van-loading v-if="rankLoading" class="loading" size="24px" vertical>加载中...</van-loading>

    <div v-else-if="rankList.length" class="rank-list">
      <div
        v-for="(item, index) in rankList"
        :key="item.id"
        class="rank-item"
        :class="{ 'is-expanded': expandedItem === index }"
        @click="toggleExpand(index)"
      >
        <div class="rank-left">
          <!-- 奖牌/序号 -->
          <div v-if="index < 3" class="medal" :style="{ color: getMedalColor(index) }">
            <van-icon name="medal-o" size="28" />
          </div>
          <div v-else class="rank-num">{{ index + 1 }}</div>

          <!-- 用户信息 -->
          <div class="user-info">
            <div class="avatar" :style="{ background: index < 3 ? getMedalColor(index) + '33' : 'var(--primary-light)' }">
              <img v-if="item.avatar" :src="item.avatar" class="avatar-img" />
              <span v-else class="avatar-text">{{ item.username.charAt(0) }}</span>
            </div>
            <div class="user-detail">
              <span class="user-name">{{ item.username }}</span>
              <span class="user-score">{{ item.score }} 分</span>
            </div>
          </div>
        </div>

        <!-- 展开详情 -->
        <div class="rank-detail" :class="{ 'detail-show': expandedItem === index }">
          <div class="dimension-bars">
            <div class="dim-item" v-for="dim in [
              { label: '编程', key: 'coding_score', cls: 'coding' },
              { label: '准确', key: 'accuracy_score', cls: 'accuracy' },
              { label: '时长', key: 'learning_time_score', cls: 'time' },
              { label: '做题', key: 'problem_count_score', cls: 'count' }
            ]" :key="dim.key">
              <span class="dim-label">{{ dim.label }}</span>
              <div class="dim-bar">
                <div :class="['dim-fill', dim.cls]" :style="{ width: getDimensionPercent(item.dimension_scores?.[dim.key]) }">
                  <span class="dim-value">{{ getDimensionValue(item.dimension_scores?.[dim.key]) }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="submission-stats" v-if="item.submission_stats">
            <div class="sub-item">
              <span class="sub-label">提交</span>
              <span class="sub-value">{{ item.submission_stats.total_submissions || 0 }}</span>
            </div>
            <div class="sub-item">
              <span class="sub-label">通过</span>
              <span class="sub-value">{{ item.submission_stats.accepted_count || 0 }}</span>
            </div>
            <div class="sub-item">
              <span class="sub-label">均分</span>
              <span class="sub-value">{{ (item.submission_stats.avg_score || 0).toFixed(1) }}</span>
            </div>
            <div class="sub-item">
              <span class="sub-label">准确率</span>
              <span class="sub-value">{{ (item.submission_stats.accuracy || 0).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <van-icon name="medal-o" size="64" color="var(--text-gray)" />
      <p>暂无排名</p>
    </div>
  </div>
</template>

<style scoped>
.phone-rank {
  padding: 16px;
  padding-top: 73px;
  padding-bottom: 60px;
}

.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-left,
.header-right {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  cursor: pointer;
  transition: background 0.2s;
}

.header-left:active,
.header-right:active {
  background: var(--bg-hover);
}

.header-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title);
  letter-spacing: 0.5px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.stat-card {
  text-align: center;
  padding: 10px 4px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
}

.stat-label {
  font-size: 11px;
  color: var(--text-gray);
  margin-top: 2px;
}

.weights-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
  align-items: center;
}

.weights-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-body);
  margin-right: 4px;
}

.weight-tag {
  padding: 4px 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-body);
}

.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.rank-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rank-item {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  padding: 12px;
  transition: all 0.3s;
}

.rank-item:active {
  background: var(--bg-hover);
}

.rank-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.medal {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.rank-num {
  width: 28px;
  height: 28px;
  line-height: 28px;
  text-align: center;
  font-weight: 700;
  font-size: 14px;
  color: var(--primary-act);
  background: var(--primary-light);
  border-radius: 6px;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary);
}

.user-detail {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-title);
}

.user-score {
  font-size: 12px;
  color: var(--text-gray);
}

.rank-detail {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 0.3s ease, opacity 0.3s ease, margin 0.3s ease, padding 0.3s ease;
  margin-top: 0;
  padding-top: 0;
}

.rank-detail.detail-show {
  max-height: 200px;
  opacity: 1;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color);
}

.dimension-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dim-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dim-label {
  font-size: 11px;
  color: var(--text-gray);
  width: 28px;
  text-align: right;
  flex-shrink: 0;
}

.dim-bar {
  flex: 1;
  height: 14px;
  background: var(--bg-hover, #e8e8e8);
  border-radius: 7px;
  overflow: hidden;
}

.dim-fill {
  height: 100%;
  border-radius: 7px;
  transition: width 0.5s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.dim-fill.coding { background: linear-gradient(90deg, var(--primary), #764ba2); }
.dim-fill.accuracy { background: linear-gradient(90deg, #10b981, #059669); }
.dim-fill.time { background: linear-gradient(90deg, #f59e0b, #d97706); }
.dim-fill.count { background: linear-gradient(90deg, #ec4899, #db2777); }

.dim-value {
  font-size: 9px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
  padding-right: 4px;
  white-space: nowrap;
}

.submission-stats {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-color);
}

.sub-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.sub-label {
  font-size: 10px;
  color: var(--text-gray);
}

.sub-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-gray);
  font-size: 14px;
}
</style>

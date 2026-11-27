<!-- 移动端思维导图组件 -->
<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import * as echarts from 'echarts'
import { initMindMapChart } from '@/views/main/mapJs/mindMap.js'
import {
  getListByUserIdApi,
  getValueByMindMapIdApi,
  changeMindMapApi,
  submitGetMindMapIdApi,
  getProgressApi,
  deleteByMindMapIdApi
} from '@/api/mainApi/resourceMindMap.js'
import { isSkip, removeSkip } from '@/utils/skip.js'

const router = useRouter()

// =================== 用户 =====================
let loginUser = null
const userId = ref(null)

onMounted(async () => {
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser && loginUser.id) {
        userId.value = loginUser.id
      }
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
  await getList()
  // 检查是否有跳转信息需要自动打开思维导图
  const skipInfo = isSkip(1)
  if (skipInfo && skipInfo.resourceId) {
    await changePageByList(skipInfo.resourceId)
    removeSkip(1)
  } else {
    await getValue()
    await nextTick()
    initChart()
    showLoading.value = false
  }
  await checkList()
})

onUnmounted(() => {
  // 清理列表预览 echarts
  if (mindMapChartRef.value) {
    const inst1 = echarts.getInstanceByDom(mindMapChartRef.value)
    if (inst1) {
      inst1.dispose()
    }
  }
  // 清理全屏预览 echarts
  if (previewChartRef.value) {
    const inst2 = echarts.getInstanceByDom(previewChartRef.value)
    if (inst2) {
      inst2.dispose()
    }
  }
})

// =================== 数据 =====================
const mindMapList = ref([])
const mindMapValue = ref({})
const showData = ref({})
const proObject = ref(null)
const showLoading = ref(true)
const listData = ref([])

const mindMapData = ref({ userId: null, text: '' })
const btnDisvisible = ref(false)

// =================== Echarts =====================
const mindMapChartRef = ref(null)
const previewChartRef = ref(null)
let chartInstance = null

const initChart = async () => {
  if (!mindMapChartRef.value) return
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  if (mindMapValue.value.status === 2 && showData.value) {
    await nextTick()
    initMindMapChart(mindMapChartRef.value, showData.value)
    // 等 DOM 渲染完毕后再 resize，确保容器有正确尺寸
    setTimeout(() => {
      const inst = echarts.getInstanceByDom(mindMapChartRef.value)
      if (inst) inst.resize()
    }, 100)
  }
}

// =================== 接口 =====================
const getList = async () => {
  try {
    const result = await getListByUserIdApi(userId.value)
    if (result.code) {
      mindMapList.value = result.data || []
      listData.value = mindMapList.value.slice(0, 20)
    } else {
      showFailToast('获取信息表失败')
    }
  } catch (e) {
    console.error('获取信息表失败', e)
  }
}

const getValue = async () => {
  if (!mindMapList.value || mindMapList.value.length === 0) return
  try {
    const result = await getValueByMindMapIdApi(mindMapList.value[0].id)
    if (result.code) {
      mindMapValue.value = result.data
      if (result.data.value) {
        try {
          showData.value = typeof result.data.value === 'string'
            ? JSON.parse(result.data.value)
            : result.data.value
        } catch (e) {
          console.error('思维导图数据解析失败', e)
          showData.value = {}
        }
      } else {
        showData.value = {}
      }
    } else {
      showFailToast('获取信息失败')
    }
  } catch (e) {
    console.error('获取单个思维导图信息失败', e)
  }
}

const getProgress = async (taskId) => {
  try {
    const result = await getProgressApi(taskId)
    if (result.code) {
      proObject.value = result.data
    } else {
      showFailToast('获取生成进度失败')
    }
  } catch (e) {
    console.error('获取思维导图进度失败', e)
  }
}

const delMindMap = async (mindMapId, isTip = true) => {
  if (isTip) {
    try {
      await showConfirmDialog({ title: '提示', message: '是否删除该思维导图？' })
    } catch (e) {
      return
    }
  }
  try {
    const result = await deleteByMindMapIdApi(mindMapId)
    if (result.code) {
      showSuccessToast('删除成功')
      await getList()
      if (mindMapValue.value.id == mindMapId) {
        showLoading.value = true
        await getValue()
        showLoading.value = false
        await nextTick()
        initChart()
      }
    } else {
      showFailToast('删除失败')
    }
  } catch (e) {
    console.error('删除思维导图失败', e)
    showFailToast('删除失败')
  }
}

const changePage = async (operation) => {
  if (mindMapValue.value.id == mindMapList.value[0]?.id) {
    if (operation == 0) {
      showToast('已经是第一页了')
      return
    }
  } else if (mindMapValue.value.id == mindMapList.value[mindMapList.value.length - 1]?.id) {
    if (operation == 1) {
      showToast('已经是最后一页了')
      return
    }
  }
  try {
    showLoading.value = true
    const result = await changeMindMapApi(mindMapValue.value.id, userId.value, operation)
    if (result.code) {
      mindMapValue.value = result.data
      if (mindMapValue.value.status == 2) {
        if (result.data.value) {
          try {
            showData.value = typeof result.data.value === 'string'
              ? JSON.parse(result.data.value)
              : result.data.value
          } catch (e) {
            showData.value = {}
          }
        }
        await nextTick()
        initChart()
      }
      showLoading.value = false
    } else {
      showFailToast('操作失败')
      showLoading.value = false
    }
  } catch (e) {
    console.error('换页失败', e)
    showLoading.value = false
  }
}

const changePageByList = async (mindMapId) => {
  if (mindMapValue.value.id == mindMapId) return
  try {
    showLoading.value = true
    const result = await getValueByMindMapIdApi(mindMapId)
    if (result.code) {
      mindMapValue.value = result.data
      if (mindMapValue.value.status == 2) {
        if (result.data.value) {
          try {
            showData.value = typeof result.data.value === 'string'
              ? JSON.parse(result.data.value)
              : result.data.value
          } catch (e) {
            showData.value = {}
          }
        }
        await nextTick()
        initChart()
      }
      showLoading.value = false
    } else if (result.code === 2) {
      showFailToast('未找到对应资源，可能已被删除')
      showLoading.value = false
    }
  } catch (e) {
    console.error('获取单个思维导图信息失败', e)
    showLoading.value = false
  }
}

// =================== 提交 =====================
const submit = async () => {
  if (!mindMapData.value.text || !mindMapData.value.text.trim()) {
    showToast('请输入主题/知识点')
    return
  }
  if (mindMapData.value.text.length > 30) {
    showToast('长度不能超过30个字符')
    return
  }

  btnDisvisible.value = true
  mindMapData.value.userId = userId.value

  try {
    const result = await submitGetMindMapIdApi(mindMapData.value)
    if (result.code) {
      showSuccessToast('提交成功')
      if (result.data.status == 1 || result.data.status == null) {
        let nowNum = 0
        const maxNum = 40

        try {
          await getProgress(result.data.taskId)
          if (proObject.value.status == null) {
            await delMindMap(result.data.taskId, false)
            proObject.value = {}
          }
        } catch (e) {
          console.error('首次查询进度失败', e)
        }

        await getList()

        while (proObject.value.status == 1 && nowNum < maxNum) {
          nowNum++
          await new Promise(resolve => setTimeout(resolve, 10000))
          try {
            await getProgress(result.data.taskId)
          } catch (e) {
            console.error('轮询进度失败', e)
          }
        }

        if (proObject.value.status == 2) {
          showSuccessToast('思维导图生成成功！')
          await getList()
          await getValue()
          await nextTick()
          initChart()
          proObject.value = {}
        } else {
          await getList()
          await getValue()
          await nextTick()
          initChart()
          proObject.value = {}
        }
      } else if (result.data.status == 2 || result.data.status == 3) {
        await getList()
        await getValue()
        await nextTick()
        initChart()
      }
      mindMapData.value = { userId: null, text: '' }
    } else {
      showFailToast('提交失败')
    }
  } catch (e) {
    console.error('提交失败', e)
    showFailToast('提交失败')
  } finally {
    btnDisvisible.value = false
  }
}

// =================== 检查截断任务 =====================
const checkList = async () => {
  for (let i = 0; i < mindMapList.value.length; i++) {
    const item = mindMapList.value[i]
    if (item.status == 1 || item.status == null) {
      let nowNum = 0
      const maxNum = 40

      try {
        await getProgress(item.id)
        if (proObject.value.status == null) {
          item.status = 3
          await delMindMap(item.id, false)
          await getList()
          if (i == 0) await getValue()
          proObject.value = {}
          continue
        }
      } catch (e) {
        continue
      }

      while (proObject.value.status == 1 && nowNum < maxNum) {
        nowNum++
        await new Promise(resolve => setTimeout(resolve, 10000))
        try {
          await getProgress(item.id)
        } catch (e) {
          break
        }
      }

      if (proObject.value.status == 2) {
        showSuccessToast('思维导图生成成功！')
        await getList()
        await getValue()
        await nextTick()
        initChart()
        proObject.value = {}
      } else {
        await getList()
        await getValue()
        await nextTick()
        initChart()
        proObject.value = {}
      }
    }
  }
}

// =================== 列表 =====================
const isOpenList = ref(false)

const moreList = () => {
  listData.value = [...mindMapList.value]
}
const lessList = () => {
  listData.value = mindMapList.value.slice(0, 20)
}

// =================== 预览 =====================
const isShowPreview = ref(false)

const openPreview = () => {
  if (mindMapValue.value.status != 2) {
    showToast('该思维导图尚未生成完成')
    return
  }
  isShowPreview.value = true
  nextTick(() => {
    // 横屏预览时重新初始化 echarts
    if (previewChartRef.value && showData.value) {
      initMindMapChart(previewChartRef.value, showData.value)
    }
  })
}

const closePreview = () => {
  isShowPreview.value = false
}

// =================== 工具函数 =====================
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  return timeStr.replace('T', ' ').substring(0, 19)
}
</script>

<template>
  <div class="phone-mindmap">
    <!-- 顶部导航 -->
    <div class="page-nav">
      <div class="nav-side" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </div>
      <div class="nav-title">思维导图</div>
      <div class="nav-side"></div>
    </div>

    <!-- 列表页 -->
    <div class="mindmap-list-page">
      <!-- <div class="page-header">
        <h2 class="page-title">思维导图 智能生成</h2>
        <p class="page-desc">输入学习主题，一键生成精细化思维导图</p>
      </div> -->

      <!-- 输入区 -->
      <div class="input-section">
        <van-field
          v-model="mindMapData.text"
          placeholder="例如：python基础"
          maxlength="30"
          show-word-limit
          clearable
          class="mindmap-input"
        />
        <van-button
          type="primary"
          block
          :loading="btnDisvisible"
          loading-text="生成中..."
          @click="submit"
          class="submit-btn"
        >
          立即生成
        </van-button>
        <p class="input-tips">*点击结点可展开或收起</p>
      </div>

      <!-- 当前思维导图预览（小卡片） -->
      <div v-if="mindMapList.length > 0" class="current-preview">
        <div class="preview-header">
          <span class="preview-title">{{ mindMapValue.text || '思维导图' }}</span>
          <van-icon name="expand-o" class="expand-icon" @click="openPreview" />
        </div>
        <div class="preview-chart-wrap">
          <!-- 加载遮罩 -->
          <div v-if="showLoading" class="chart-loading">
            <van-loading type="spinner" color="#9B59B6" />
            <span>加载中...</span>
          </div>
          <!-- echarts 容器 -->
          <div
            v-show="mindMapValue.status === 2 && !showLoading"
            ref="mindMapChartRef"
            class="mindmap-chart"
          ></div>
          <!-- 生成中 -->
          <div v-if="mindMapValue.status == 1 || mindMapValue.status == null" class="chart-status generating">
            <van-icon name="loading" size="40" class="spin-icon" />
            <span>生成中...</span>
          </div>
          <!-- 失败 -->
          <div v-else-if="mindMapValue.status == 3" class="chart-status failed">
            <van-icon name="warning-o" size="40" color="#F56C6C" />
            <span>生成失败</span>
          </div>
        </div>
        <!-- 底部导航 -->
        <div class="chart-nav">
          <van-icon name="arrow-left" class="nav-arrow" @click="changePage(0)" />
          <div class="nav-info">
            <div class="nav-text">{{ mindMapValue.text }}</div>
            <div class="nav-time">{{ formatTime(mindMapValue.createTime) }}</div>
          </div>
          <van-icon name="arrow" class="nav-arrow" @click="changePage(1)" />
        </div>
      </div>

      <!-- 列表 -->
      <div class="list-section">
        <div class="list-header">
          <van-icon name="notes-o" size="18" color="#9B59B6" />
          <span>最近生成</span>
        </div>
        <div v-if="mindMapList.length > 0" class="list-wrap">
          <div
            v-for="item in (isOpenList ? mindMapList : listData)"
            :key="item.id"
            class="list-item"
            :class="{
              'item-active': mindMapValue.id == item.id,
              'item-loading': item.status == 1 || item.status == null,
              'item-fail': item.status == 3
            }"
          >
            <!-- 成功状态 -->
            <div v-if="item.status == 2" class="item-content" @click="changePageByList(item.id)">
              <div class="item-icon">
                <van-icon name="cluster-o" size="28" color="#9B59B6" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text }}</div>
                <div class="item-time">{{ formatTime(item.createTime) }}</div>
              </div>
              <div class="item-actions">
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="delMindMap(item.id)" />
              </div>
            </div>

            <!-- 生成中状态 -->
            <div v-else-if="item.status == 1 || item.status == null" class="item-content item-generating" @click="changePageByList(item.id)">
              <div class="item-icon generating">
                <van-icon name="loading" size="28" class="spin-icon" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text }}</div>
                <div class="item-time">
                  <span class="status-text">生成中...</span>
                </div>
              </div>
            </div>

            <!-- 失败状态 -->
            <div v-else-if="item.status == 3" class="item-content item-failed" @click="changePageByList(item.id)">
              <div class="item-icon failed">
                <van-icon name="warning-o" size="28" color="#F56C6C" />
              </div>
              <div class="item-info">
                <div class="item-name">{{ item.text }}</div>
                <div class="item-time">
                  <span class="fail-text">生成失败</span>
                </div>
              </div>
              <div class="item-actions">
                <van-icon name="delete-o" class="action-icon delete-icon" @click.stop="delMindMap(item.id)" />
              </div>
            </div>
          </div>
          <div v-if="mindMapList.length > 20" class="expand-btn" @click="isOpenList ? lessList() : moreList()">
            {{ isOpenList ? '收起' : '查看更多' }}
          </div>
        </div>
        <div v-else class="empty-state">
          <van-empty description="暂无生成内容" />
        </div>
      </div>
    </div>

    <!-- 横屏预览页 -->
    <div v-if="isShowPreview" class="mindmap-preview-page">
      <!-- 顶部操作栏 -->
      <div class="preview-nav">
        <div class="nav-side" @click="closePreview">
          <van-icon name="arrow-left" size="20" />
        </div>
        <div class="nav-title">{{ mindMapValue.text || '思维导图预览' }}</div>
        <div class="nav-side"></div>
      </div>

      <!-- echarts 预览区域 -->
      <div class="preview-chart-area">
        <div ref="previewChartRef" class="preview-echarts"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-mindmap {
  min-height: 100vh;
  background: var(--bg-page, #f7f8fa);
  padding-bottom: 60px;
}

/* 顶部导航 */
.page-nav, .preview-nav {
  display: flex;
  align-items: center;
  padding: 12px 0;
  background: var(--bg-card, #fff);
  border-bottom: 1px solid var(--border-color, #eee);
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-side {
  width: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-title {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  text-align: center;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-title, #323233);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 列表页 */
.mindmap-list-page {
  padding: 16px;
}
.page-header {
  margin-bottom: 16px;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-title, #323233);
  margin: 0 0 4px;
}
.page-desc {
  font-size: 13px;
  color: var(--text-gray, #969799);
  margin: 0;
}

/* 输入区 */
.input-section {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid var(--border-color, #eee);
}
.submit-btn {
  margin-top: 12px;
  font-weight: 600;
}
.input-tips {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin: 8px 0 0;
}

/* 当前预览卡片 */
.current-preview {
  background: var(--bg-card, #fff);
  border-radius: 12px;
  border: 1px solid var(--border-color, #eee);
  overflow: hidden;
  margin-bottom: 16px;
}
.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, #eee);
}
.preview-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-title, #323233);
}
.expand-icon {
  font-size: 20px;
  color: #9B59B6;
  padding: 4px;
}
.preview-chart-wrap {
  height: 250px;
  position: relative;
  background: #fff;
}
.mindmap-chart {
  width: 100%;
  height: 100%;
}
.chart-loading {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--bg-card, #fff);
  z-index: 2;
  font-size: 13px;
  color: var(--text-gray, #969799);
}
.chart-status {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
}
.chart-status.generating {
  background: rgba(155, 89, 182, 0.05);
  color: #9B59B6;
}
.chart-status.failed {
  background: rgba(245, 108, 108, 0.05);
  color: #F56C6C;
}
.chart-nav {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-top: 1px solid var(--border-color, #eee);
  background: var(--bg-card, #fff);
}
.nav-arrow {
  font-size: 20px;
  color: var(--text-body, #646566);
  padding: 8px;
  flex-shrink: 0;
}
.nav-arrow:active {
  color: #9B59B6;
}
.nav-info {
  flex: 1;
  text-align: center;
  overflow: hidden;
}
.nav-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-body, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-time {
  font-size: 11px;
  color: var(--text-gray, #969799);
  margin-top: 2px;
}

/* 列表 */
.list-section {
  margin-top: 8px;
}
.list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-title, #323233);
}
.list-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.list-item {
  background: var(--bg-card, #fff);
  border-radius: 10px;
  border: 1px solid var(--border-color, #eee);
  overflow: hidden;
  transition: all 0.2s;
}
.list-item:active {
  transform: scale(0.98);
}
.item-active {
  border-color: #9B59B6;
  box-shadow: 0 0 0 1px #9B59B6;
}
.item-content {
  display: flex;
  align-items: center;
  padding: 12px;
  gap: 10px;
}
.item-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(155, 89, 182, 0.1);
}
.item-icon.generating {
  background: rgba(155, 89, 182, 0.08);
}
.item-icon.failed {
  background: rgba(245, 108, 108, 0.08);
}
.item-info {
  flex: 1;
  min-width: 0;
}
.item-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-body, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-time {
  font-size: 12px;
  color: var(--text-gray, #969799);
  margin-top: 2px;
}
.status-text {
  font-size: 12px;
  color: #9B59B6;
  font-weight: 500;
}
.fail-text {
  font-size: 12px;
  color: #F56C6C;
  font-weight: 500;
}
.item-actions {
  flex-shrink: 0;
}
.action-icon {
  font-size: 18px;
  padding: 4px;
}
.delete-icon {
  color: #F56C6C;
}
.expand-btn {
  text-align: center;
  padding: 12px;
  font-size: 14px;
  color: var(--text-gray, #969799);
}
.empty-state {
  padding: 40px 0;
}

.spin-icon {
  animation: spin 1s linear infinite;
  color: #9B59B6;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 横屏预览页 */
.mindmap-preview-page {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--bg-page, #f7f8fa);
  z-index: 100;
  display: flex;
  flex-direction: column;
}

.preview-nav {
  flex-shrink: 0;
}

.preview-chart-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.preview-echarts {
  width: 100%;
  height: 100%;
}

/* 横屏模式：竖屏时旋转预览区域 */
@media screen and (orientation: portrait) {
  .mindmap-preview-page {
    transform: rotate(90deg);
    transform-origin: center center;
    position: fixed;
    top: calc(50% - 50vw);
    left: calc(50% - 50vh);
    width: 100vh;
    height: 100vw;
  }
}
</style>

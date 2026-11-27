<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router' 
import { ElMessage,ElMessageBox } from 'element-plus'
import { House, User, Files, MessageBox, Collection, EditPen, Setting, Compass,  Memo } from '@element-plus/icons-vue'
import AdFloatWindow from '@/components/backstage/adFloatWindow.vue'//右侧悬浮窗面板
import { getApplyListApi,agreeApplyApi,refuseApplyApi } from '@/api/backstage/adLayout.js'
import { closeTourApi } from '@/api/mainApi/layout.js'
import { exitApi } from '@/api/login.js'//登出
const router = useRouter() // 用于跳转
const route = useRoute()   // 用于获取路由信息

const pageTitle = ref('首页') // 默认标题
const loginName = ref('')//用户信息
const loginAvatar = ref('')//头像
const userId = ref('')//用户id
let loginUser = null//登录用户
const activeMenu = ref(route.path)

const applyList = ref([])
const applyCount = ref(0)
const showApplyDropdown = ref(false)
let applyPollingTimer = null
let isApplyPollingActive = true

// 侧边栏收缩
const collapsed = ref(false)
const toggleCollapse = () => {
  collapsed.value = !collapsed.value
}

// 漫游式引导
const floatWindowRef = ref(null)
const tourVisible = ref(false)
const tourCurrent = ref(0)

// 引导步骤对应的路由和标题
const tourSteps = [
  { target: 'float-window-target', title: '智能管理助手', content: '点击这里可以展开智能管理助手面板，AI助手可以帮你管理资源、查看权重配置、管理知识库等自动化操作。' },
  { target: 'menu-index', title: '首页', content: '首页主要展示 系统概览数据 和 各Agent资源总点击量的排行榜信息。', route: '/admin/index' },
  { target: 'menu-users', title: '用户管理', content: '管理主系统用户，查看用户信息和权限。', route: '/admin/users' },
  { target: 'menu-adMedia', title: '媒体素材管理', content: '管理视频等智能球问答检索的媒体素材文件，支持上传和预览。', route: '/admin/adMedia' },
  { target: 'menu-adResource', title: '资源管理', content: '管理试卷理论题、编程题和视频资源。', route: '/admin/adResource' },
  { target: 'menu-adKnowledge', title: '知识库管理', content: '管理系统知识库文件，可同步到向量库。', route: '/admin/adKnowledge' },
  { target: 'menu-adAgentDraw', title: 'Agent画像', content: '查看Agent工作状态及画像排行榜等信息。', route: '/admin/adAgentDraw' },
  { target: 'menu-adOpSetting', title: 'Agent权重配置', content: '配置Agent各项权重参数指标。', route: '/admin/adOpSetting' },
  { target: 'menu-adRank', title: '总排行榜权重配置', content: '配置全局排行榜的权重参数指标。', route: '/admin/adRank' }
]

// 引导目标元素 refs
const tourTargetRefs = {}
const setTourTargetRef = (key) => (el) => {
  if (el) tourTargetRefs[key] = el
}

// 获取引导目标元素
const getTourTarget = (targetId) => {
  return () => {
    // 悬浮窗特殊处理：从组件获取实际可见元素
    if (targetId === 'float-window-target' && floatWindowRef.value) {
      const el = floatWindowRef.value.getTargetElement()
      if (el) return el
    }
    // 优先从 refs 获取
    if (tourTargetRefs[targetId]) {
      return tourTargetRefs[targetId].$el || tourTargetRefs[targetId]
    }
    // 回退到 DOM 查询
    const el = document.getElementById(targetId)
    if (el) return el
    return document.body
  }
}

// 打开引导
const startTour = async () => {
  tourCurrent.value = 0
  tourVisible.value = true
}

// 引导步骤变化
const onTourChange = async (current) => {
  const step = tourSteps[current]
  
  // 如果有路由，先跳转并等待DOM更新
  if (step && step.route) {
    await router.push(step.route)
    await nextTick()
    // 等待页面渲染完成
    await new Promise(resolve => setTimeout(resolve, 400))
  }
  
  tourCurrent.value = current
}

// 关闭引导
const onTourClose = () => {
  tourVisible.value = false
}

onMounted(async () => {
  // 管理端强制日间模式
  document.documentElement.classList.remove('dark')
  
  loginUser = JSON.parse(localStorage.getItem('loginUser'))
  if(loginUser && loginUser.username){
    // 判断用户类型
    if(loginUser.isNew && loginUser.type == -3){
      localStorage.removeItem('loginUser')
      ElMessage.info('已申请为管理员，请等待管理员审核')
      router.push('/login')
    }else if(loginUser.isNew == false && loginUser.isBuildProfile == 0){
      ElMessage.warning('用户您好，请进行画像构建~')
      router.push('/aiAnswer')
    }else if(loginUser.isNew == false && loginUser.type == 1){
      ElMessage.success('用户您好，为您跳转用户端首页~')
      router.push('/index')
    }else if(loginUser.isNew && loginUser.type == -2){
      ElMessage.info('请完善信息')
      router.push('/info')
    }
    userId.value = typeof loginUser.id === 'string' ? loginUser.id : String(loginUser.id)
    loginName.value = loginUser.username
    loginAvatar.value = loginUser.avatar
    if(loginUser.tour === 1){
      startTour()
      const res = await closeTourApi(userId.value)
      if(res.code === 1){
        loginUser.tour = 0
        // 更新本地存储中的用户信息状态
        localStorage.setItem('loginUser', JSON.stringify(loginUser))
      }
    }
  }else{
    ElMessage.error('非法闯入！')
    router.push('/login')
  }
  fetchApplyList()
  startApplyPolling()
  document.addEventListener('click', handleClickOutside)

})

onUnmounted(() => {
  stopApplyPolling()
  document.removeEventListener('click', handleClickOutside)
})

const handleClickOutside = (event) => {
  const mesElement = document.querySelector('.mes')
  if (mesElement && !mesElement.contains(event.target)) {
    showApplyDropdown.value = false
  }
}

// 获取申请列表
const fetchApplyList = async () => {
  try {
    const res = await getApplyListApi()
    if (res.code === 1) {
      applyList.value = res.data || []
      applyCount.value = applyList.value.length
    }
  } catch (error) {
    console.error('获取申请列表失败:', error)
  }
}
// 轮询申请列表
const startApplyPolling = () => {
  isApplyPollingActive = true
  fetchApplyList()
  applyPollingTimer = setInterval(() => {
    if (isApplyPollingActive) {
      fetchApplyList()
    }
  }, 10000)
}
// 停止轮询申请列表
const stopApplyPolling = () => {
  isApplyPollingActive = false
  if (applyPollingTimer) {
    clearInterval(applyPollingTimer)
    applyPollingTimer = null
  }
}
// 切换申请列表下拉框显示状态
const toggleApplyDropdown = () => {
  showApplyDropdown.value = !showApplyDropdown.value
  if (showApplyDropdown.value) {
    fetchApplyList()
  }
}
// 同意申请
const handleAgreeApply = async (userId) => {
  try {
    const res = await agreeApplyApi(userId)
    if (res.code === 1) {
      ElMessage.success('同意申请成功')
      fetchApplyList()
    } else {
      ElMessage.error(res.msg || '同意申请失败')
    }
  } catch (error) {
    ElMessage.error('同意申请失败')
  }
}
// 拒绝申请
const handleRefuseApply = async (userId) => {
  try {
    const res = await refuseApplyApi(userId)
    if (res.code === 1) {
      ElMessage.success('拒绝申请成功')
      fetchApplyList()
    } else {
      ElMessage.error(res.msg || '拒绝申请失败')
    }
  } catch (error) {
    ElMessage.error('拒绝申请失败')
  }
}

// 监听路由变化，更新页面标题和菜单高亮
watch(
  () => route.path,
  (newPath) => {
    activeMenu.value = newPath
    const newTitle = route.meta.title
    if (newTitle) {
      pageTitle.value = newTitle
    }
  },
  { immediate: true }
)

// 跳转用户中心
// const toUserCenter = () => {
//   router.push('/admin/userCenter')
// }
// 退出登录
const exitLogin = async () => {
  try{
    const res = await exitApi(userId.value)
    if(res.code){
      localStorage.removeItem('loginUser')
      ElMessage.success('退出登录成功')
      router.push('/login')
    }else{
      ElMessage.error(res.msg)
    }
  }catch(error){
    ElMessage.error('退出登录失败')
  }
}


</script>

<template>
  <div class="common-layout" :class="{ 'sidebar-collapsed': collapsed }">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside z-index="3">
        <el-menu
          router='true'
          :collapse="collapsed"
          :default-active="activeMenu"
          text-color="var(--aside-text-color)"
          background-color="var(--aside-bg-color)"
          active-text-color="var(--aside-active-text-color)"
        >
          <div class="aside-header">
            <div class="logo" title="知行优课后台管理系统">
              <img src="@/assets/logo/Logo.png" alt="知行优课logo"></img>
              <div class="logo-text" v-show="!collapsed">
                <div>知行优课</div>
                <h1>后台管理系统</h1>
              </div>
            </div>
          </div>
          <el-menu-item index="/admin/index" :ref="setTourTargetRef('menu-index')">
            <el-icon><House /></el-icon>
            <template #title><span>首页</span></template>
          </el-menu-item>
          <el-menu-item index="/admin/users" :ref="setTourTargetRef('menu-users')">
            <el-icon><User /></el-icon>
            <template #title><span>用户管理</span></template>
          </el-menu-item>
          <el-menu-item index="/admin/adMedia" :ref="setTourTargetRef('menu-adMedia')">
            <el-icon><Files /></el-icon>
            <template #title><span>媒体素材管理</span></template>
          </el-menu-item>
          <el-menu-item index="/admin/adResource" :ref="setTourTargetRef('menu-adResource')">
            <el-icon><MessageBox /></el-icon>
            <template #title><span>资源管理</span></template>
          </el-menu-item>
          <el-menu-item index="/admin/adKnowledge" :ref="setTourTargetRef('menu-adKnowledge')">
            <el-icon><Collection /></el-icon>
            <template #title><span>知识库管理</span></template>
          </el-menu-item>
          <el-menu-item index="/admin/adAgentDraw" :ref="setTourTargetRef('menu-adAgentDraw')">
            <el-icon><EditPen /></el-icon>
            <template #title><span>Agent画像</span></template>
          </el-menu-item>
          <el-menu-item index="/admin/adOpSetting" :ref="setTourTargetRef('menu-adOpSetting')">
            <el-icon><Setting /></el-icon>
            <template #title><span>Agent权重配置</span></template>
          </el-menu-item>
          <el-menu-item index="/admin/adRank" :ref="setTourTargetRef('menu-adRank')">
            <el-icon><Memo /></el-icon>
            <template #title><span>总排行榜权重配置</span></template>
          </el-menu-item>
        </el-menu>
        <div class="collapse-btn" @click="toggleCollapse">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path v-if="!collapsed" d="M11 19l-7-7 7-7M18 19l-7-7 7-7"/>
            <path v-else d="M13 5l7 7-7 7M6 5l7 7-7 7"/>
          </svg>
          <span v-show="!collapsed">{{ collapsed ? '展开' : '收起' }}</span>
        </div>
      </el-aside>
      <el-container>
        <!-- 顶部导航栏 -->
        <el-header z-index="3">
          <div class="nav">
            <div class="left-box">
              <h2 :key="pageTitle" class="title-transition">{{ pageTitle }}</h2>
            </div>
            <div class="right-box">
              <button class="tour-btn" @click="startTour" title="功能引导">
                <el-icon><Compass /></el-icon>
                <span>功能引导</span>
              </button>
              <!-- 消息 -->
              <div :class="['mes', { 'has-notification': applyCount > 0 }]" @click="toggleApplyDropdown">
                <el-badge v-if="applyCount > 0" :value="applyCount" :max="99" class="huizhang"></el-badge>
                <el-icon><Bell /></el-icon>
                <div :class="['apply-dropdown', { show: showApplyDropdown }]">
                  <div class="dropdown-header">
                    <span>管理员申请列表</span>
                    <span class="count">({{ applyCount }})</span>
                  </div>
                  <div class="dropdown-content">
                    <div v-if="applyList.length === 0" class="empty-tip">
                      暂无申请
                    </div>
                    <div v-for="item in applyList" :key="item.userId" class="apply-item">
                      <div class="apply-info">
                        <span class="username">{{ item.username }}</span>
                        <span class="remark">{{ item.remark }}</span>
                      </div>
                      <div class="apply-actions">
                        <button class="btn-agree" @click.stop="handleAgreeApply(item.userId)">同意</button>
                        <button class="btn-refuse" @click.stop="handleRefuseApply(item.userId)">拒绝</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 用户信息 -->
              <div class="info">
                <!-- 头像 -->
                <div class="avatar">
                  <el-avatar :src="loginAvatar">x</el-avatar>
                </div>
                <!-- 用户信息 -->
                <div class="user">
                  <a href="javascript:void(0)">{{ loginName }}</a>
                  <el-icon><arrow-down /></el-icon>
                  <ul class="dropdown">
                    <!-- <li><a href="javascript:void(0)" @click="toUserCenter()">用户中心</a></li> -->
                    <li><a href="javascript:void(0)" @click="exitLogin()">退出登录</a></li>
                  </ul>
                </div> 
              </div>  

            </div>
          </div>
        </el-header>
        <!-- 主显示区域 -->
        <el-main z-index="0">
          <router-view></router-view>
        </el-main>
      </el-container>
    </el-container>

    <!-- 管理助手悬浮窗 -->
    <AdFloatWindow ref="floatWindowRef" />

    <!-- 漫游式引导 -->
    <el-tour
      v-model="tourVisible"
      :current="tourCurrent"
      @change="onTourChange"
      @close="onTourClose"
    >
      <el-tour-step
        v-for="(step, index) in tourSteps"
        :key="index"
        :target="getTourTarget(step.target)"
        :title="step.title"
        :description="step.content"
      />
    </el-tour>
  </div>
</template>

<style scoped>
.common-layout {
  --aside-width: 245px;
  --aside-collapsed-width: 64px;
  --header-height: 70px;
}

/* 禁止用户选中文本 */
/* * {
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
} */

.common-layout {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

:deep(.el-container) {
  width: 100%;
  height: 100%;
}

:deep(.el-aside) {
  width: var(--aside-width);
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-normal);
  transition: width 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  overflow: hidden;
}

.sidebar-collapsed :deep(.el-aside) {
  width: var(--aside-collapsed-width);
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.15);
}

:deep(.el-menu) {
  width: 100%;
  height: 100%;
}

:deep(.el-menu-item:hover) {
  background-color: var(--aside-hover-bg-color);
}

:deep(.el-menu-item){
  border-bottom: 1px solid var(--aside-border-color);
  height: 66px;
  line-height: 66px;
  font-size: 16px;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

:deep(.el-menu-item [class^=el-icon]){
  font-size: 20px;
  margin-right: 16px;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

:deep(.el-menu-item span){
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.sidebar-collapsed :deep(.el-menu-item span){
  opacity: 0;
  transform: translateX(-10px);
}

:deep(.el-menu-item.is-active){
  background-color: var(--aside-hover-bg-color);
}

.aside-header {
  height: var(--header-height);
  border-bottom: 1px solid var(--aside-border-color);
}

.logo {
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo:hover {
  cursor: pointer;
}

.logo img {
  width: 70px;
  height: 70px;
  margin-left: 3px;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.logo .logo-text {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-collapsed .logo .logo-text {
  opacity: 0;
  transform: scale(0.8);
  pointer-events: none;
}

.logo .logo-text h1,
.logo .logo-text div {
  color: var(--aside-text-color);
  font-size: 25px;
  font-family: "抖音美好体","三极行楷简体-粗",sans-serif;
}

.logo .logo-text div { 
  margin-top: 5px;
  font-size: 18px;
}

:deep(.el-header) {
  padding: 0;
  height: var(--header-height);
  position: fixed;
  left: var(--aside-width);
  top: 0;
  right: 0;
  z-index: 99;
  transition: left 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.sidebar-collapsed :deep(.el-header) {
  left: var(--aside-collapsed-width);
}

.nav { 
  min-width: 1000px;
  width: 100%;
  height: 100%;
  background-color: var(--nav);
  box-shadow: var(--shadow-normal);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  padding-right: 40px;
}

.nav .right-box,
.nav .left-box { 
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
}
.nav .right-box .info {
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav .left-box { 
  color: var(--text-body);
  padding-left: 20px;
}

.tour-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1.5px solid var(--primary);
  border-radius: 20px;
  background: var(--primary-light);
  color: var(--primary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  white-space: nowrap;
  margin-right: 15px;
}

.tour-btn:hover {
  background: var(--primary);
  color: #fff;
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
  transform: translateY(-1px);
}

.tour-btn:active {
  transform: translateY(0);
}

.tour-btn .el-icon {
  font-size: 20px;
}

/* 漫游式引导样式 */
:deep(.el-tour__content) {
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

:deep(.el-tour__header) {
  padding: 16px 20px 8px;
}

:deep(.el-tour__title) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-title);
}

:deep(.el-tour__body) {
  padding: 8px 20px 16px;
}

:deep(.el-tour__description) {
  font-size: 14px;
  color: var(--text-body);
  line-height: 1.6;
}

:deep(.el-tour__footer) {
  padding: 12px 20px;
  border-top: 1px solid var(--border-color);
}

:deep(.el-tour__indicators) {
  color: var(--text-gray);
  font-size: 13px;
}

:deep(.el-tour__closebtn) {
  color: var(--text-gray);
}

:deep(.el-tour__closebtn:hover) {
  color: var(--primary);
}

:deep(.el-button--primary) {
  background: var(--grad-primary);
  border: none;
}

:deep(.el-button--primary:hover) {
  background: var(--primary-hv);
}

.title-transition {
  animation: fadeIn 0.3s ease-in-out;
  font-family: "三极行楷简体-粗","抖音美好体",sans-serif;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.nav .right-box .mes { 
  cursor: pointer;
  margin-right: 20px;
  display: flex;
  align-items: center;
}
/* 徽章 */
.huizhang {
  z-index: 4;
  position: absolute;
  top: -8px;
  right: -12px;
}

.mes .el-icon { 
  font-size: 18px;
}

.mes {
  position: relative;
}

.apply-dropdown {
  position: absolute;
  top: 100%;
  right: -50px;
  margin-top: 8px;
  width: 350px;
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border: 1.5px solid var(--border-color);
  border-radius: 8px;
  z-index: 1000;
  overflow: hidden;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.dropdown-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  color: var(--text-body);
  display: flex;
  align-items: center;
  gap: 4px;
}

.dropdown-header .count {
  color: var(--primary);
  font-weight: 400;
  font-size: 14px;
}

.dropdown-content {
  max-height: 400px;
  overflow-y: auto;
}

.empty-tip {
  padding: 24px;
  text-align: center;
  color: var(--text-placeholder);
  font-size: 14px;
}

.apply-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.apply-item:last-child {
  border-bottom: none;
}

.apply-info {
  flex: 1;
  min-width: 0;
}

.apply-info .username {
  display: block;
  font-weight: 500;
  color: var(--text-body);
  margin-bottom: 4px;
}

.apply-info .remark {
  display: block;
  font-size: 13px;
  color: var(--text-placeholder);
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
}

.apply-actions {
  display: flex;
  gap: 8px;
  margin-left: 12px;
}

.btn-agree,
.btn-refuse {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  border: none;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-agree {
  background: var(--grad-primary);
  color: #fff;
  box-shadow: 0 2px 6px rgba(45, 125, 219, 0.25);
}

.btn-agree:hover {
  background: var(--primary-hv);
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.35);
  transform: translateY(-1px);
}

.btn-agree:active {
  transform: translateY(0);
}

.btn-refuse {
  background: linear-gradient(135deg, var(--main-delete) 0%, #f78a8a 100%);
  color: #fff;
  box-shadow: 0 2px 6px rgba(245, 108, 108, 0.25);
}

.btn-refuse:hover {
  background: linear-gradient(135deg, var(--main-delete-hover) 0%, #ff9999 100%);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.35);
  transform: translateY(-1px);
}

.btn-refuse:active {
  transform: translateY(0);
}

.nav .right-box .avatar { 
  margin-right: 10px;
  margin-top: 7px;
}

.user { 
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
}

.user a {
  color: var(--text-body);
}

.user:hover>a,
.user:hover .el-icon,
.mes:hover .el-icon {
  color: var(--primary);
  text-decoration: none;
}

ul,
li {
  list-style: none;
}

.dropdown {
  min-width: 100px;
  background-color: var(--bg-card);
  box-shadow: var(--shadow-normal);
  border: 1.5px solid var(--border-color);
  border-radius: 8px;
  position: absolute;
  top: 100%;
  right: -10px;
  margin-top: 8px;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1000;
  overflow: hidden;
}

.dropdown li a { 
  text-decoration: none;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  width: 100%;
  height: 40px;
  color: var(--text-body);
  font-size: 14px;
}

.dropdown li a:hover {
  background-color: var(--primary-light);
  color: var(--primary);
}

.user:hover .dropdown {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.apply-dropdown.show {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

:deep(.el-main) {
  margin-top: var(--header-height);
  margin-left: var(--aside-width);
  height: calc(100vh - var(--header-height));
  overflow-y: auto;
  overflow-x: auto;
  padding: 10px 20px;
  min-width: 1000px;
  transition: margin-left 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.sidebar-collapsed :deep(.el-main) {
  margin-left: var(--aside-collapsed-width);
}

:deep(.el-menu-item) {
  position: relative;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-menu-item::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) scaleY(0);
  width: 4px;
  height: 36px;
  background: var(--aside-active-text-color);
  border-radius: 0 2px 2px 0;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-menu-item.is-active::before) {
  transform: translateY(-50%) scaleY(1);
}

:deep(.el-menu-item:hover) {
  background-color: var(--aside-hover-bg-color);
}

:deep(.el-menu-item:hover [class^=el-icon]) {
  transform: translateX(3px);
}

:deep(.el-menu-item [class^=el-icon]) {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.mes.has-notification .el-icon {
  animation: bell-shake 1.5s ease-in-out infinite;
}

@keyframes bell-shake {
  0%, 100% {
    transform: rotate(0);
  }
  10%, 30%, 50%, 70%, 90% {
    transform: rotate(-5deg);
  }
  20%, 40%, 60%, 80% {
    transform: rotate(5deg);
  }
}

.apply-dropdown,
.dropdown {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.apply-dropdown.show,
.user:hover .dropdown {
  opacity: 1;
  visibility: visible;
  transform: translateY(0) scale(1);
}

.apply-dropdown,
.dropdown {
  opacity: 0;
  visibility: hidden;
  transform: translateY(-8px) scale(0.98);
}

.avatar {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.user:hover .avatar {
  transform: scale(1.08);
}

:deep(.el-avatar) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.user:hover :deep(.el-avatar) {
  box-shadow: 0 4px 12px rgba(45, 125, 219, 0.3);
}

.apply-item {
  transition: all 0.2s ease;
}

.apply-item:hover {
  background-color: var(--primary-light);
  padding-left: 20px;
}

.btn-agree,
.btn-refuse {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-agree:hover {
  transform: translateY(-2px) scale(1.05);
}

.btn-refuse:hover {
  transform: translateY(-2px) scale(1.05);
}

.btn-agree:active,
.btn-refuse:active {
  transform: translateY(0) scale(1);
}

/* 侧边栏收缩按钮 */
.collapse-btn {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  color: var(--aside-text-color);
  border-top: 1px solid var(--aside-border-color);
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  font-size: 14px;
  opacity: 0.7;
}

.collapse-btn:hover {
  opacity: 1;
  background-color: var(--aside-hover-bg-color);
  transform: translateY(-2px);
}

.collapse-btn svg {
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.collapse-btn:hover svg {
  transform: scale(1.2);
}

.sidebar-collapsed .collapse-btn {
  justify-content: center;
}

/* 收缩时：只隐藏文字，图标保持原位 */
.sidebar-collapsed :deep(.el-menu-item) {
  padding: 0 20px;
}

.sidebar-collapsed :deep(.el-menu-item [class^=el-icon]) {
  margin-right: 16px;
}

.sidebar-collapsed .logo img {
  width: 40px;
  height: 40px;
  margin-left: 0;
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.sidebar-collapsed .logo {
  justify-content: center;
}

.sidebar-collapsed .aside-header {
  display: flex;
  align-items: center;
  justify-content: center;
}

</style>

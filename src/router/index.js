// import { createRouter, createWebHistory } from 'vue-router'

// // ================= 页面组件导入 =================

// // 登录页
// import LoginView from '@/views/login.vue'
// // 用户信息补充
// import InfoView from '@/views/info.vue'


// // ========================= 平台页面 =================
// import LayoutView from '@/views/main/layout.vue'
// import IndexView from '@/views/main/index.vue'


// import DrawView from '@/views/main/draw.vue'
// import PathPlanView from '@/views/main/pathPlan.vue'
// // import AiAnswerView from '@/views/main/aiAnswer.vue'
// import EvaluateView from '@/views/main/evaluate.vue'
// import UserCenterView from '@/views/main/userCenter.vue'
// import WrongQuestionsView from '@/views/main/wrongQuestions.vue'
// import PartnersView from '@/views/main/partners.vue'

// import ResourceView from '@/views/main/resource.vue'

// import PptView from '@/views/main/resourceNav/ppt.vue'
// import MindMapView from '@/views/main/resourceNav/mindMap.vue'
// import WordView from '@/views/main/resourceNav/word.vue'
// import ReadingView from '@/views/main/resourceNav/reading.vue'
// import CodeView from '@/views/main/resourceNav/code.vue'
// import VideoView from '@/views/main/resourceNav/video.vue'
// import AnimaView from '@/views/main/resourceNav/anima.vue'
// import PaperView from '@/views/main/resourceNav/paper.vue'


// // ================= 后台管理系统 =================

// import AdminLayoutView from '@/views/backstage/adLayout.vue'
// import AdminIndexView from '@/views/backstage/adIndex.vue'
// import AdminUsersView from '@/views/backstage/adUsers.vue'
// import AdminResourceView from '@/views/backstage/adResource.vue'



// // ================= 创建路由实例 =================
// const router = createRouter({
//   history: createWebHistory(import.meta.env.BASE_URL),// 在routes中维护 路径与组件之间的关系
//   routes: [
//     // 登录页
//     { path: '/login', name: 'login', component: LoginView },
//     // 用户信息补充
//     { path: '/info', name: 'info', component: InfoView },
//     // 平台页面
//     {
//       path: '/',
//       name: '',
//       component: LayoutView,
//       redirect: '/index',
//       children: [
//         { path: '/index', name: 'index', component: IndexView },
//         { path: '/draw', name: 'draw', component: DrawView },

//         {
//           path: '/resource',
//           name: 'resource',
//           component: ResourceView,
//           redirect: '/ppt',
//           children: [
//             { path: '/ppt', name: 'ppt', component: PptView },
//             { path: '/mindMap', name: 'mindMap', component: MindMapView },
//             { path: '/word', name: 'word', component: WordView },
//             { path: '/reading', name: 'reading', component: ReadingView },
//             { path: '/code', name: 'code', component: CodeView },
//             { path: '/video', name: 'video', component: VideoView },
//             { path: '/anima', name: 'anima', component: AnimaView },
//             { path: '/paper', name: 'paper', component: PaperView },
//           ]
//         },
//         { path: '/pathPlan', name: 'pathPlan', component: PathPlanView },
//         { path: '/evaluate', name: 'evaluate', component: EvaluateView },
//         { path: '/userCenter', name: 'userCenter', component: UserCenterView },
//         { path: '/wrongQuestions', name: 'wrongQuestions', component: WrongQuestionsView },
//         { path: '/partners', name: 'partners', component: PartnersView },
//         // AiAnswerView 使用动态导入: AiAnswerView，而这个组件内部可能引用了某些在初始化时还不存在的资源（特别是数字人SDK）。将 AiAnswerView 改为动态导入。
//         {
//           path: '/aiAnswer',
//           name: 'aiAnswer',
//           component: () => import('@/views/main/aiAnswer.vue')
//         },
//       ]
//     },




//     // 后台管理系统
//     {
//       path: '/admin',
//       name: '',
//       component: AdminLayoutView,
//       redirect: '/admin/index',
//       children: [
//         { path: '/admin/index', name: 'adIndex', component: AdminIndexView, meta: { title: '首页' } },
//         { path: '/admin/users', name: 'adUsers', component: AdminUsersView, meta: { title: '用户管理' } },
//         { path: '/admin/resource', name: 'adResource', component: AdminResourceView, meta: { title: '资源管理' } },

//       ]
//     }
//   ],
//   // 添加滚动行为配置
//   scrollBehavior(to, from, savedPosition) {
//     if (savedPosition) {
//       return savedPosition
//     }
//     // 如果有锚点
//     if (to.hash) {
//       return {
//         el: to.hash,
//         behavior: 'smooth',
//       }
//     }
//     // 默认滚动到顶部
//     return { top: 0, left: 0, behavior: 'smooth' }
//   }

// })

// // 添加全局守卫
// router.beforeEach((to, from, next) => {
//   // 确保body可以滚动
//   document.body.style.overflow = ''
//   document.documentElement.style.overflow = ''
//   document.body.style.position = ''
//   next()
// })

// router.afterEach(() => {
//   // 每次路由切换后滚动到顶部
//   setTimeout(() => {
//     window.scrollTo({ top: 0, behavior: 'smooth' })
//   }, 100)
// })


// export default router


// =============================================================================
import { createRouter, createWebHistory } from 'vue-router'

// ================= 页面组件导入 =================

// 登录页和用户信息补充改为异步导入，避免循环依赖
const LoginView = () => import('@/views/login.vue')
const InfoView = () => import('@/views/info.vue')

// ========================= 平台页面 =================
// 布局和首页改为异步导入，避免循环依赖
const LayoutView = () => import('@/views/main/layout.vue')
const IndexView = () => import('@/views/main/index.vue')

// 其他页面改为异步导入（按需加载）
const DrawView = () => import('@/views/main/draw.vue')
const PathPlanView = () => import('@/views/main/pathPlan.vue')
// const AiAnswerView = () => import('@/views/main/aiAnswer.vue') // 已在下文动态导入
const EvaluateView = () => import('@/views/main/evaluate.vue')
const UserCenterView = () => import('@/views/main/userCenter.vue')
const WrongQuestionsView = () => import('@/views/main/wrongQuestions.vue')
const PartnersView = () => import('@/views/main/partners.vue')

const ResourceView = () => import('@/views/main/resource.vue')

// 资源子组件全部改为异步导入 - 这是解决循环依赖的关键！
const PptView = () => import('@/views/main/resourceNav/ppt.vue')
const MindMapView = () => import('@/views/main/resourceNav/mindMap.vue')
const WordView = () => import('@/views/main/resourceNav/word.vue')
const ReadingView = () => import('@/views/main/resourceNav/reading.vue')
const CodeView = () => import('@/views/main/resourceNav/code.vue')
const VideoView = () => import('@/views/main/resourceNav/video.vue')
const AnimaView = () => import('@/views/main/resourceNav/anima.vue')
const PaperView = () => import('@/views/main/resourceNav/paper.vue')

const KnowledgeComparisonView = () => import('@/views/main/resourceNav/knowledgeComparison.vue')
const AlgorithmLabView = () => import('@/views/main/resourceNav/algorithmLab.vue')

// ================= 后台管理系统 =================
// 后台页面改为异步导入
const AdminLayoutView = () => import('@/views/backstage/adLayout.vue')
const AdminIndexView = () => import('@/views/backstage/adIndex.vue')
const AdminUsersView = () => import('@/views/backstage/adUsers.vue')
const AdminResourceView = () => import('@/views/backstage/adResource.vue')
const AdminOpSettingView = () => import('@/views/backstage/adOpSetting.vue')
const AdminKnowledgeView = () => import('@/views/backstage/adKnowledge.vue')
const AdminAgentDrawView = () => import('@/views/backstage/adAgentDraw.vue')
const AdminMediaView = () => import('@/views/backstage/adMedia.vue')
const AdminRankView = () => import('@/views/backstage/adRank.vue')

// ================= 移动端 =================
const PhoneLoginView = () => import('@/views/phone/login.vue')
const PhoneLayoutView = () => import('@/views/phone/layout.vue')
const PhoneHomeView = () => import('@/views/phone/home.vue')
const PhoneFunctionView = () => import('@/views/phone/function.vue')
const PhoneUserCenterView = () => import('@/views/phone/userCenter.vue')

// ================= 创建路由实例 =================
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // 登录页
    { path: '/login', name: 'login', component: LoginView },
    // 用户信息补充
    { path: '/info', name: 'info', component: InfoView },
    // 平台页面
    {
      path: '/',
      name: '',
      component: LayoutView,
      redirect: '/index',
      children: [
        { path: '/index', name: 'index', component: IndexView },
        { path: '/draw', name: 'draw', component: DrawView },
        {
          path: '/resource',
          name: 'resource',
          component: ResourceView,
          redirect: '/code',
          children: [
            { path: '/ppt', name: 'ppt', component: PptView },
            { path: '/mindMap', name: 'mindMap', component: MindMapView },
            { path: '/word', name: 'word', component: WordView },
            { path: '/reading', name: 'reading', component: ReadingView },
            { path: '/code', name: 'code', component: CodeView },
            { path: '/video', name: 'video', component: VideoView },
            { path: '/anima', name: 'anima', component: AnimaView },
            { path: '/paper', name: 'paper', component: PaperView },
            { path: '/knowledgeComparison', name: 'knowledgeComparison', component: KnowledgeComparisonView },
            { path: '/algorithmLab', name: 'algorithmLab', component: AlgorithmLabView },
          ]
        },
        { path: '/pathPlan', name: 'pathPlan', component: PathPlanView },
        { path: '/evaluate', name: 'evaluate', component: EvaluateView },
        { path: '/userCenter', name: 'userCenter', component: UserCenterView },
        { path: '/wrongQuestions', name: 'wrongQuestions', component: WrongQuestionsView },
        { path: '/partners', name: 'partners', component: PartnersView },
        // AiAnswerView 使用动态导入
        {
          path: '/aiAnswer',
          name: 'aiAnswer',
          component: () => import('@/views/main/aiAnswer.vue')
        },
      ]
    },
    // 后台管理系统
    {
      path: '/admin',
      name: '',
      component: AdminLayoutView,
      redirect: '/admin/index',
      children: [
        { path: '/admin/index', name: 'adIndex', component: AdminIndexView, meta: { title: '首页' } },
        { path: '/admin/users', name: 'adUsers', component: AdminUsersView, meta: { title: '用户管理' } },
        { path: '/admin/adMedia', name: 'adMedia', component: AdminMediaView, meta: { title: '媒体素材管理' } },
        { path: '/admin/adResource', name: 'adResource', component: AdminResourceView, meta: { title: '资源管理' } },
        { path: '/admin/adOpSetting', name: 'adOpSetting', component: AdminOpSettingView, meta: { title: 'Agent权重配置' } },
        { path: '/admin/adKnowledge', name: 'adKnowledge', component: AdminKnowledgeView, meta: { title: '知识库管理' } },
        { path: '/admin/adAgentDraw', name: 'adAgentDraw', component: AdminAgentDrawView, meta: { title: 'Agent画像' } },
        { path: '/admin/adRank', name: 'adRank', component: AdminRankView, meta: { title: '总排行榜权重配置' } },
      ]
    },
    // 移动端
    {
      path: '/phone/login',
      name: 'phoneLogin',
      component: PhoneLoginView
    },
    {
      path: '/phone',
      name: 'phone',
      component: PhoneLayoutView,
      redirect: '/phone/index',
      children: [
        { path: '/phone/index', name: 'phoneIndex', component: PhoneHomeView },
        { path: '/phone/chat', name: 'phoneChat', component: () => import('@/views/phone/childVue/chat.vue') },
        { path: '/phone/function', name: 'phoneFunction', component: PhoneFunctionView },
        { path: '/phone/userCenter', name: 'phoneUserCenter', component: PhoneUserCenterView },
        { path: '/phone/ai-image', name: 'phoneAiImage', component: () => import('@/views/phone/childVue/ai-image.vue') },
        { path: '/phone/rank', name: 'phoneRank', component: () => import('@/views/phone/childVue/rank.vue') },
        { path: '/phone/post', name: 'phonePost', component: () => import('@/views/phone/childVue/post.vue') },
        { path: '/phone/note', name: 'phoneNote', component: () => import('@/views/phone/childVue/note.vue') },
        { path: '/phone/partners', name: 'phonePartners', component: () => import('@/views/phone/childVue/partners.vue') },
        { path: '/phone/evaluate', name: 'phoneEvaluate', component: () => import('@/views/phone/childVue/evaluate.vue') },
        { path: '/phone/resource/paper', name: 'phonePaper', component: () => import('@/views/phone/childVue/paper.vue') },
        { path: '/phone/resource/reading', name: 'phoneReading', component: () => import('@/views/phone/childVue/reading.vue') },
        { path: '/phone/resource/ppt', name: 'phonePpt', component: () => import('@/views/phone/childVue/ppt.vue') },
        { path: '/phone/resource/video', name: 'phoneVideo', component: () => import('@/views/phone/childVue/video.vue') },
        { path: '/phone/resource/word', name: 'phoneWord', component: () => import('@/views/phone/childVue/word.vue') },
        { path: '/phone/resource/anima', name: 'phoneAnima', component: () => import('@/views/phone/childVue/anima.vue') },
        { path: '/phone/resource/mindmap', name: 'phoneMindmap', component: () => import('@/views/phone/childVue/mindmap.vue') },
        { path: '/phone/resource/code', name: 'phoneCode', component: () => import('@/views/phone/childVue/code.vue') },
        { path: '/phone/knowledge-comparison', name: 'phoneKnowledgeComparison', component: () => import('@/views/phone/childVue/knowledgeComparison.vue') },
        { path: '/phone/algorithm-lab', name: 'phoneAlgorithmLab', component: () => import('@/views/phone/childVue/algorithmLab.vue') },
        { path: '/phone/wrongQuestions', name: 'phoneWrongQuestions', component: () => import('@/views/phone/childVue/wrongQuestions.vue') },
        { path: '/phone/pathPlan', name: 'phonePathPlan', component: () => import('@/views/phone/childVue/pathPlan.vue') },
        { path: '/phone/notification', name: 'phoneNotification', component: () => import('@/views/phone/childVue/notification.vue') },
        { path: '/phone/collection', name: 'phoneCollection', component: () => import('@/views/phone/childVue/collection.vue') }
      ]
    }
  ],
  // 添加滚动行为配置
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    if (to.hash) {
      return {
        el: to.hash,
        behavior: 'smooth',
      }
    }
    return { top: 0, left: 0, behavior: 'smooth' }
  }
})

router.beforeEach((to, from, next) => {
  document.body.style.overflow = ''
  document.documentElement.style.overflow = ''
  document.body.style.position = ''

  const userStr = localStorage.getItem('loginUser')
  const isLoggedIn = !!userStr

  if (to.path === '/login' || to.path === '/phone/login') {
    if (isLoggedIn) {
      const user = JSON.parse(userStr)
      next(user.type === 0 ? '/admin/index' : '/index')
    } else {
      next()
    }
  } else if (!isLoggedIn) {
    next(to.path.startsWith('/phone') ? '/phone/login' : '/login')
  } else {
    try {
      const user = JSON.parse(userStr)
      const TOKEN_EXPIRE_MS = 24 * 60 * 60 * 1000
      if (user.loginTime && (Date.now() - user.loginTime > TOKEN_EXPIRE_MS)) {
        localStorage.removeItem('loginUser')
        next(to.path.startsWith('/phone') ? '/phone/login' : '/login')
        return
      }
    } catch (e) {
      localStorage.removeItem('loginUser')
      next(to.path.startsWith('/phone') ? '/phone/login' : '/login')
      return
    }
    next()
  }
})

router.afterEach(() => {
  setTimeout(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, 100)
})

export default router
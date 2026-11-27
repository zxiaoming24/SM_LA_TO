// axios请求封装

//===============================第一版============================

// import axios from 'axios'
// import { ElMessage } from 'element-plus'
// import router from '@/router'

// const request = axios.create({
//   baseURL: '/api',
//   timeout: 180000
// })


// // axios请求拦截器 request
// request.interceptors.request.use(
//   (config) => {//成功回调
//     //获取token
//     const loginUser = JSON.parse(localStorage.getItem('loginUser'))
//     if (loginUser && loginUser.token) {
//       //将本地存储器的token设置给请求头
//       config.headers.token = loginUser.token
//     }
//     return config//返回config，使他继续传给后端
//   },
//   (error) => {//失败回调
//     return Promise.reject(error)//抛出错误
//   }
// )

// //axios响应拦截器 response
// request.interceptors.response.use(
//   (response) => {//成功回调
//     return response.data
//   },
//   (error) => {//失败回调
//     if (error.response.status === 401) {
//       ElMessage.warning('登录已过期，请重新登录')
//       redirectToLogin()
//     } else {
//       ElMessage.error('回调出现异常！')
//     }
//     return Promise.reject(error)//抛出错误
//   }
// )

// export default request


//================================第二版============================
// import axios from 'axios'
// import { ElMessage } from 'element-plus'
// import router from '@/router'

// const request = axios.create({
//   baseURL: '/api',
//   timeout: 180000
// })

// // 请求拦截
// request.interceptors.request.use(
//   (config) => {
//     const loginUser = JSON.parse(localStorage.getItem('loginUser'))
//     if (loginUser && loginUser.token) {
//       config.headers.token = loginUser.token
//     }
//     return config
//   },
//   (error) => Promise.reject(error)
// )

// // 响应拦截【修复重点】
// request.interceptors.response.use(
//   (response) => response.data,
//   (error) => {
//     // 先判断response是否存在
//     if (error.response) {
//       const status = error.response.status
//       if (status === 401) {
//         ElMessage.warning('登录已过期，请重新登录')
//         // 替换你的redirectToLogin逻辑
//         localStorage.removeItem('loginUser')
//         router.push('/login')
//       } else {
//         ElMessage.error(`请求错误：${status}`)
//         console.log(`请求错误：${status}`)
//       }
//     } else {
//       // 无响应：超时、断网、后端没启动
//       ElMessage.error('服务器连接失败或请求超时')
//     }
//     return Promise.reject(error)
//   }
// )

// export default request


//=================================第三版============================
// axios请求封装
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { showToast, showNotify } from 'vant'
import router from '@/router'

// 统一消息提示：移动端用 vant，PC 端用 element-plus
const notify = {
  warning: (msg) => {
    if (isPhoneRoute()) showNotify({ type: 'warning', message: msg, position: 'top', duration: 3000 })
    else ElMessage.warning(msg)
  },
  error: (msg) => {
    if (isPhoneRoute()) showNotify({ type: 'danger', message: msg, position: 'top', duration: 3000 })
    else ElMessage.error(msg)
  }
}

// 创建请求实例
const request = axios.create({
  baseURL: '/api',
  timeout: 600000
})

const requestPython = axios.create({
  baseURL: '/py',
  timeout: 600000,
  responseType: 'blob'
})
const requestPythonAll = axios.create({
  baseURL: '/py',
  timeout: 600000,
})

// 防止重复提示
let isShowing401 = false
let isShowingError = false
let isShowingServer = false

// 判断当前是否处于移动端路由
const isPhoneRoute = () => {
  try {
    return router.currentRoute.value && router.currentRoute.value.path && router.currentRoute.value.path.startsWith('/phone')
  } catch (e) {
    return false
  }
}

// 通用拦截器配置函数
const setupInterceptors = (instance) => {
  // 请求拦截
  instance.interceptors.request.use(
    (config) => {
      //配置请求头
      const loginUser = JSON.parse(localStorage.getItem('loginUser') || 'null')
      if (loginUser && loginUser.token) {
        config.headers.token = loginUser.token
      }
      return config
    },
    (error) => Promise.reject(error)
  )

  // 响应拦截
  instance.interceptors.response.use(
    (response) => response.data,
    (error) => {
      // 先判断response是否存在
      if (error.response) {
        const status = error.response.status
        if (status === 401) {
          if (!isShowing401) {
            isShowing401 = true
            notify.warning('登录已过期，请重新登录')
            localStorage.removeItem('loginUser')
            router.push(isPhoneRoute() ? '/phone/login' : '/login')
            setTimeout(() => { isShowing401 = false }, 3000)
          }
        } else {
          if (!isShowingError) {
            isShowingError = true
            notify.error(`请求错误：${status}`)
            console.log(`请求错误：${status}`)
            setTimeout(() => { isShowingError = false }, 3000)
          }
        }
      } else {
        // 无响应：超时、断网、后端没启动
        if (!isShowingServer) {
          isShowingServer = true
          notify.error('服务器连接失败或请求超时')
          setTimeout(() => { isShowingServer = false }, 3000)
        }
      }
      return Promise.reject(error)
    }
  )
}

// 为实例应用拦截器
setupInterceptors(request)
setupInterceptors(requestPython)
setupInterceptors(requestPythonAll)

export default request
export { requestPython, requestPythonAll }
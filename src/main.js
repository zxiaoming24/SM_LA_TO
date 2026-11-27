import { createApp } from 'vue'//引入Vue
import App from './App.vue'//导入根组件

//路由配置
import router from './router'

//ElementPlus 组件库
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

//Vant 组件库（移动端）
import Vant from 'vant'
import 'vant/lib/index.css'

//ElementPlus 图标
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

//全局样式
import './assets/main.css'
import './assets/font.css'

//element的primarycss
import '@/assets/style/elPrimaryBtn.css'

// 引入全局弹窗组件
import GlobalPop from '@/components/GlobalPop.vue'
//pinia状态管理
import { createPinia } from 'pinia'
const pinia = createPinia()

//创建应用实例
const app = createApp(App)

// 全局注册
app.component('GlobalPop', GlobalPop)//写在APP.vue的html

//配置路由
app.use(router)
//注册 Pinia
app.use(pinia)
//配置ElementPlus
app.use(ElementPlus, { locale: zhCn })
//配置Vant
app.use(Vant)
//注册ElementPlus图标组件
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

//挂载应用实例到index.html
app.mount('#app')

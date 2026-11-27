<script setup>
import { useRouter } from 'vue-router'
import { ref,onMounted } from 'vue'
import { ElMessage,ElMessageBox } from 'element-plus'
const router = useRouter()
let loginUser = null
onMounted(() => {
  // 获取用户名
  const userStr = localStorage.getItem('loginUser')
  if (userStr) {
    try {
      loginUser = JSON.parse(userStr)
      if (loginUser) {
        // 判断登录用户类型
        if(loginUser.isNew == false && loginUser.isBuildProfile == 0){
          ElMessage.warning('请进行画像构建~')
          router.push('/aiAnswer')
        }
      }
      
    } catch (e) {
      console.error('用户信息解析失败', e)
    }
  }
})


</script>

<template>
  <div class="container">
    <div class="nav">
      <ul>
        <li><router-link to="/code">编程练习</router-link></li>
        <li><router-link to="/video">视频</router-link></li>
        <li><router-link to="/paper">试卷</router-link></li>
        <li><router-link to="/mindMap">思维导图</router-link></li>
        <li><router-link to="/ppt">PPT</router-link></li>
        <li><router-link to="/word">讲解文档</router-link></li>
        <li><router-link to="/reading">拓展阅读</router-link></li> 
        <li><router-link to="/anima">可视化动画</router-link></li> 
        <li><router-link to="/knowledgeComparison">知识点对比</router-link></li> 
        <li><router-link to="/algorithmLab">算法实验室</router-link></li> 
        <!-- <li><router-link to="/cases">实操案例</router-link></li>
        <li><router-link to="/studyMaterials">实践项目学习材料</router-link></li> -->
      </ul>
    </div>
    <div class="content"> 
      <router-view></router-view>
    </div>
  </div>
</template>

<style scoped>
.container{
  min-width: 1314px;
  width: 100%;
  background: transparent;
}
a,a:hover {
  text-decoration: none;
  color: var(--text-body);
  transition: all 0.3s;
}
/* 导航栏部分 */
.nav {
  width: 100%;
  height: 70px;
  /* border-bottom: 1px solid orange; */
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s;
  
}
.nav ul {
  min-width: 1000px;
  width: 100%;
  height: 100%;
  display: flex;
  flex-wrap: nowrap;
  justify-content: center;
  align-items: center;
  gap: 20px;
}

.nav ul li {
  border: 1px solid var(--primary);
  border-radius: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav ul li a {
  color: var(--primary);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0 12px;
  width: 100%;
  height: 100%;
  border-radius: 20px;
  font-size: 20px;
  font-weight: 500;
  transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav ul li a:hover {
  background-color: var(--primary);
  color: var(--bg-page);
}

.nav ul > li:has(a.router-link-active) {
  transform: translateY(-2px);
  background-color: var(--primary);
  border-color: var(--primary);
  box-shadow: var(--shadow-brand);
}

.nav ul > li a.router-link-active {
  color: var(--bg-page);
}

.nav ul li:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-brand);
}

/* 夜间模式适配 */
.dark .nav ul li {
  border-color: rgba(96, 165, 250, 0.4);
}

.dark .nav ul li a {
  color: #60a5fa;
}

.dark .nav ul li a:hover {
  background-color: rgba(59, 130, 246, 0.25);
  color: #93c5fd;
}

.dark .nav ul > li:has(a.router-link-active) {
  background-color: rgba(59, 130, 246, 0.3);
  border-color: rgba(96, 165, 250, 0.5);
}

.dark .nav ul > li a.router-link-active {
  color: #93c5fd;
}

/* 内容部分 */
.content {
  width: 100%;
  /* border: 1px solid blue; */
}
</style>

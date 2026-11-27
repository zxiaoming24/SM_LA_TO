<script setup>
import { onMounted } from 'vue'
import { useThemeStore } from '@/stores/theme.js'

onMounted(() => {
  const themeStore = useThemeStore()
  themeStore.initTheme()
})
</script>

<template>
  <!-- 根据路由匹配 -->
  <router-view></router-view>

  <!-- 全局弹窗组件 -->
  <GlobalPop />
</template>

<style scoped>
/* login全局primary按钮颜色*/
:deep(.el-button--primary){
  --el-button-bg-color: var(--primary);
  --el-button-border-color: var(--primary);

  --el-button-hover-bg-color: var(--primary-hv);
  --el-button-hover-border-color: var(--primary-hv);

  --el-button-active-color: var(--primary-act);
  --el-button-active-bg-color: var(--primary-act);
  --el-button-active-border-color: var(--primary-act);

  --el-button-disabled-bg-color: var(--primary-disa-bgc);
  --el-button-disabled-border-color: var(--primary-disa-border);
}


/* login全局表单 */
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary) inset;
}
:deep(.el-form-item--label-top .el-form-item__label){
  margin-bottom: 0px;
}
:deep(.el-form-item){
  margin-bottom: 10px;
}


</style>

<style>

/* 全局隐藏自带滚动条 */
/* 注意：这里没有 scoped 属性，表示全局样式 */

/* 隐藏全局滚动条 (Chrome, Safari, Edge) */
::-webkit-scrollbar {
  display: none;
}

/* 隐藏全局滚动条 (Firefox) */
* {
  scrollbar-width: none;
}

/* 隐藏全局滚动条 (IE/Edge 旧版) */
* {
  -ms-overflow-style: none;
}


</style>

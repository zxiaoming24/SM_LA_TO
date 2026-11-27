import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
// 主题管理
export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)

  const toggleTheme = () => {
    isDark.value = !isDark.value
  }

  const setTheme = (dark) => {
    isDark.value = dark
  }

  watch(isDark, (newVal) => {
    const html = document.documentElement
    if (newVal) {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }
    localStorage.setItem('theme', newVal ? 'dark' : 'light')
  })

  const initTheme = () => {
    const saved = localStorage.getItem('theme')
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches

    if (saved) {
      isDark.value = saved === 'dark'
    } else {
      isDark.value = systemDark
    }
  }

  return {
    isDark,
    toggleTheme,
    setTheme,
    initTheme
  }
})
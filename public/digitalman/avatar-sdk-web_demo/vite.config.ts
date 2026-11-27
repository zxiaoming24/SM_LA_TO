import { defineConfig } from 'vite'
import path from 'path'
import react from '@vitejs/plugin-react'

const BUILD_ID = process.env.BUILD_ID ?? 1001
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 9000,
    proxy: {
      '/api': {
        target: 'http://192.168.0.241:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    extensions: ['.js', '.ts', '.jsx', '.tsx', '.scss', '.css'], // 添加扩展名支持
  },
  define: {
    'process.env': {
      version: `${process.env.npm_package_version}.${BUILD_ID}`,
      buildTime: new Date().toISOString(),
    },
  },
  // css: {
  //   preprocessorOptions: {
  //     scss: {
  //       additionalData: '@import "@/assets/styles/utils.scss";',
  //     },
  //   },
  // },
})

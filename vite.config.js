// import { fileURLToPath, URL } from 'node:url'

// import { defineConfig } from 'vite'
// import vue from '@vitejs/plugin-vue'

// // https://vitejs.dev/config/
// export default defineConfig({
//   plugins: [vue()],
//   resolve: {
//     alias: {
//       '@': fileURLToPath(new URL('./src', import.meta.url))
//     }
//   },


//   server: {
//     host: '0.0.0.0',  // 允许局域网访问
//     port: 5173,
//     proxy: {
//       '/api': {
//         target: 'http://192.168.0.234:8080',  // 后端服务地址
//         secure: false, // 不验证SSL证书
//         changeOrigin: true, // 修改请求头中的 Origin 字段
//         rewrite: (path) => path.replace(/^\/api/, '') // 将请求路径中的 /api 替换为空
//       },
//       '/py': {
//         target: 'http://192.168.0.234:8000',  // 后端服务地址
//         secure: false, // 不验证SSL证书
//         changeOrigin: true, // 修改请求头中的 Origin 字段
//         rewrite: (path) => path.replace(/^\/py/, '') // 将请求路径中的 /py 替换为空
//       }
//     }
//   }
// })

//===============================new==========================================
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端网址
const javaIP = '8.159.134.28'
const pyIP = '8.159.134.28'

// 自签名 HTTPS 证书（用于局域网手机访问，解决 WebRTC 安全上下文限制）
// 证书由一次性命令预生成，详见 README 或运行：npx selfsigned-cli
const certDir = path.resolve(process.cwd(), '.dev-certs')
const keyPath = path.join(certDir, 'key.pem')
const certPath = path.join(certDir, 'cert.pem')

let httpsConfig = false
try {
  if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    httpsConfig = {
      key: fs.readFileSync(keyPath),
      cert: fs.readFileSync(certPath),
    }
    console.log('🔐 已加载自签名 HTTPS 证书')
  } else {
    console.warn('⚠️ 未找到 HTTPS 证书。请运行: node -e "const fs=require(\'fs\'),path=require(\'path\'),s=require(\'selfsigned\');const d=path.resolve(\'.dev-certs\');if(!fs.existsSync(d))fs.mkdirSync(d);s.generate([{name:\'commonName\',value:\'localhost\'}],{keySize:2048,days:365,extensions:[{name:\'subjectAltName\',altNames:[{type:2,value:\'localhost\'},{type:7,ip:\'127.0.0.1\'}]}]}).then(p=>{fs.writeFileSync(path.join(d,\'key.pem\'),p.private);fs.writeFileSync(path.join(d,\'cert.pem\'),p.cert);console.log(\'证书已生成\')})"')
  }
} catch (e) {
  console.warn('⚠️ HTTPS 证书加载失败，回退到 HTTP:', e.message)
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  assetsInclude: ['**/*.lottie'],//把Lottie文件当作静态处理
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  optimizeDeps: {
    include: ['pdfjs-dist', 'vis-network/standalone', 'html2canvas']//pdf预览插件和知识图谱
  },

  server: {
    host: '0.0.0.0',
    port: 5173,
    https: httpsConfig,
    proxy: {
      // OSS文件代理（解决CORS问题）（pdf预览）
      '/oss-proxy': {
        target: 'https://wha-whaghw.oss-cn-beijing.aliyuncs.com',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/oss-proxy/, '')
      },
      // 普通JAVA API请求
      '/api': {
        target: `http://${javaIP}:8080`,
        secure: false,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      // WebSocket通话代理（同时支持HTTP和WebSocket）（java端）
      '/wsJava1Api': {
        target: `http://${javaIP}:8082`,
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/wsJava1Api/, '')
      },
      // WebSocket全局代理（同时支持HTTP和WebSocket）（java端）
      '/wsJava2Api': {
        target: `http://${javaIP}:8083`,
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/wsJava2Api/, '')
      },
      // SSE专用代理（独立路径）（java端SSE）
      '/sseApi': {
        target: `http://${javaIP}:8080`,
        secure: false,
        changeOrigin: true,
        buffer: false,
        timeout: 0,
        rewrite: (path) => path.replace(/^\/sseApi/, ''),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log('🔗 SSE请求:', req.url)
            proxyReq.setHeader('Connection', 'keep-alive')
            proxyReq.setHeader('Cache-Control', 'no-cache')
            proxyReq.setHeader('Accept', 'text/event-stream')
          })
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('📡 SSE响应:', req.url)
            res.setHeader('Content-Type', 'text/event-stream')
            res.setHeader('Cache-Control', 'no-cache')
            res.setHeader('Connection', 'keep-alive')
            res.setHeader('Content-Encoding', 'identity')
            res.setHeader('X-Accel-Buffering', 'no')
            res.setTimeout(0)
          })
        }
      },
      // Python API流请求
      '/py': {
        target: `http://${pyIP}:8000`,
        secure: false,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/py/, '')
      },
      // WebSocket摄像头服务代理（同时支持HTTP和WebSocket）（python端）
      '/wsApi': {
        target: `http://${pyIP}:8081`,
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/wsApi/, '')
      },
      // 特征实时曲线SSE代理（python端SSE）
      '/features': {
        target: `http://${pyIP}:8000`,
        secure: false,
        changeOrigin: true,
        buffer: false,
        timeout: 0,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log('🔗 特征曲线SSE请求:', req.url)
            proxyReq.setHeader('Connection', 'keep-alive')
            proxyReq.setHeader('Cache-Control', 'no-cache')
            proxyReq.setHeader('Accept', 'text/event-stream')
          })
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('📡 特征曲线SSE响应:', req.url)
            res.setHeader('Content-Type', 'text/event-stream')
            res.setHeader('Cache-Control', 'no-cache')
            res.setHeader('Connection', 'keep-alive')
            res.setHeader('Content-Encoding', 'identity')
            res.setHeader('X-Accel-Buffering', 'no')
            res.setTimeout(0)
          })
        }
      }
    }
  }
})
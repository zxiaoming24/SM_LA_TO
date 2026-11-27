// 无用

const isDev = import.meta.env.DEV

const SERVER = {
  java: isDev ? '' : (import.meta.env.VITE_JAVA_URL || ''),
  python: isDev ? '' : (import.meta.env.VITE_PY_URL || ''),
  ws1: isDev ? '' : (import.meta.env.VITE_WS1_URL || ''),
  ws2: isDev ? '' : (import.meta.env.VITE_WS2_URL || '')
}

export default SERVER

// 独立 WebSocket 连接测试（Node.js 端）
import crypto from 'crypto';

const APP_ID = 'd70f5fa7';
const API_KEY = 'DD15443262db70AC863015F7681cc6D7';
const API_SECRET = 'Yzg1Yjg1YzM1YTA2OTg1N2Y5MGQ1MmZm';
const SERVER_URL = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact';

// 生成签名 URL（与 SDK 的 Oe 函数相同算法）
function buildSignedUrl(url, apiKey, apiSecret) {
  const match = url.match(/^wss?:\/\/([^\/]+)(\/.*)/);
  const host = match[1];
  const path = match[2];
  const date = new Date().toUTCString();
  const sigOrigin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
  const sig = crypto.createHmac('sha256', apiSecret).update(sigOrigin).digest('base64');
  const authOrigin = `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${sig}"`;
  const auth = Buffer.from(authOrigin).toString('base64');
  return `${url}?authorization=${encodeURIComponent(auth)}&date=${encodeURIComponent(date)}&host=${host}`;
}

const signedUrl = buildSignedUrl(SERVER_URL, API_KEY, API_SECRET);
console.log('=== 测试 1: 签名 URL ===');
console.log(signedUrl);

// 引入 ws
const { default: WebSocket } = await import('ws');

// 测试1: 使用签名 URL
console.log('\n=== 测试 1: 签名 URL 连接 ===');
try {
  const ws1 = new WebSocket(signedUrl);
  ws1.on('open', () => {
    console.log('✅ 测试1 连接成功！');
    ws1.close();
  });
  ws1.on('error', (err) => {
    console.log('❌ 测试1 错误:', err.message);
  });
  ws1.on('close', (code, reason) => {
    console.log(`测试1 关闭 code=${code} reason=${reason}`);
  });
  await new Promise(r => setTimeout(r, 5000));
} catch(e) {
  console.log('❌ 测试1 异常:', e.message);
}

// 测试2: 使用原始 URL（无签名）
console.log('\n=== 测试 2: 原始 URL（无签名）=== ');
try {
  const ws2 = new WebSocket(SERVER_URL);
  ws2.on('open', () => {
    console.log('✅ 测试2 连接成功！');
    ws2.close();
  });
  ws2.on('error', (err) => {
    console.log('❌ 测试2 错误:', err.message);
  });
  ws2.on('close', (code, reason) => {
    console.log(`测试2 关闭 code=${code} reason=${reason}`);
  });
  await new Promise(r => setTimeout(r, 5000));
} catch(e) {
  console.log('❌ 测试2 异常:', e.message);
}

console.log('\n=== 所有测试完成 ===');

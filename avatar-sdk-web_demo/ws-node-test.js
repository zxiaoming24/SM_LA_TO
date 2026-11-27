// Node.js WebSocket 测试脚本
// 运行: node ws-node-test.js

const WebSocket = require('ws');
const crypto = require('crypto');

const appId = 'bc33bf7e';
const apiKey = '77730F3d7f3e084dc37c93af656105d1';
const apiSecret = 'MGVIY2Y3M2VhMmFIY2RIYTkxMDk3MzQ0';
const serverUrl = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact';

function hmacSha256(message, secret) {
  return crypto.createHmac('sha256', secret).update(message).digest('base64');
}

function buildAuthUrl() {
  const url = new URL(serverUrl);
  const host = url.host;
  const path = url.pathname;
  const date = new Date().toUTCString();

  // 讯飞官方鉴权格式
  const signatureOrigin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
  const signatureSha = hmacSha256(signatureOrigin, apiSecret);

  const authorizationOrigin = `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${signatureSha}"`;
  const authorization = Buffer.from(authorizationOrigin).toString('base64');

  const authUrl = `${serverUrl}?authorization=${encodeURIComponent(authorization)}&date=${encodeURIComponent(date)}&host=${encodeURIComponent(host)}`;

  console.log('=== 讯飞数字人 WebSocket 测试 (Node.js) ===');
  console.log('签名原文:\n', signatureOrigin);
  console.log('HMAC签名:', signatureSha);
  console.log('授权串:', authorizationOrigin);
  console.log('base64 authorization:', authorization);
  console.log('\n完整URL:\n', authUrl);
  
  return authUrl;
}

const wsUrl = buildAuthUrl();
console.log('\n正在连接...');

const ws = new WebSocket(wsUrl);

ws.on('open', function() {
  console.log('\n✅ WebSocket 连接成功！');
  
  // 发送启动消息
  const startMsg = {
    common: { appId },
    business: { sceneId: '326300423554207744' },
    data: {}
  };
  ws.send(JSON.stringify(startMsg));
  console.log('📤 发送启动消息:', JSON.stringify(startMsg));
});

ws.on('message', function(data) {
  console.log('📨 收到消息:', data.toString());
});

ws.on('close', function(code, reason) {
  console.log('\n🔌 连接关闭');
  console.log('  code:', code);
  console.log('  reason:', reason.toString() || '(无)');
  
  if (code === 1006) {
    console.error('\n❌ 1006 错误：连接异常关闭，可能原因:');
    console.error('  1. 鉴权失败（API Key/Secret 错误）');
    console.error('  2. 服务未激活或已过期');
    console.error('  3. IP 被限制');
    console.error('  4. 服务端拒绝连接');
  }
});

ws.on('error', function(error) {
  console.error('\n❌ WebSocket 错误:', error.message);
  console.error('  error.code:', error.code);
  console.error('  error.address:', error.address);
  console.error('  error.port:', error.port);
});
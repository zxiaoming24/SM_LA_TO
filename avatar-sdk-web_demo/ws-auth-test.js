// 讯飞数字人 WebSocket 完整鉴权测试
// 粘贴到浏览器控制台执行

const appId = 'D70F5FA7';
const apiKey = 'DD15443262db70AC863015F7681cc6D7';
const apiSecret = 'Yzg1Yjg1YzM1YTA2OTg1N2Y5MGQ1MmZm';
const serverUrl = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact';

// HMAC-SHA256 签名函数
async function hmacSha256(message, secret) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return btoa(String.fromCharCode(...new Uint8Array(signature)));
}

async function base64Encode(str) {
  // 标准 base64 编码
  return btoa(str);
}

async function buildAuthUrl() {
  const url = new URL(serverUrl);
  const host = url.host;
  const path = url.pathname;
  
  const now = new Date();
  const date = now.toUTCString();
  
  const signatureOrigin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`;
  const signatureSha = await hmacSha256(signatureOrigin, apiSecret);
  // signatureSha 已经是 base64 编码，不需要再次编码
  const signatureBase64 = signatureSha;
  
  const authorizationOrigin = `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${signatureBase64}"`;
  const authorization = await base64Encode(authorizationOrigin);
  
  const params = new URLSearchParams({
    authorization,
    date,
    host,
    appId  // 也加上 appId
  });
  
  console.log('\n鉴权过程调试:');
  console.log('  date:', date);
  console.log('  host:', host);
  console.log('  signatureOrigin:', signatureOrigin);
  console.log('  signatureSha (HMAC result):', signatureSha);
  console.log('  authorizationOrigin:', authorizationOrigin.substring(0, 100) + '...');
  console.log('  authorization:', authorization.substring(0, 80) + '...');
  
  return `${serverUrl}?${params.toString()}`;
}

async function testConnection() {
  console.log('=== 开始测试讯飞数字人 WebSocket 连接 ===');
  console.log('参数:');
  console.log('  appId:', appId);
  console.log('  apiKey:', apiKey.substring(0, 10) + '...');
  console.log('  apiSecret:', apiSecret.substring(0, 10) + '...');
  console.log('  serverUrl:', serverUrl);
  
  try {
    const authUrl = await buildAuthUrl();
    console.log('\n完整的认证 URL:');
    console.log(authUrl);
    
    console.log('\n正在连接...');
    const ws = new WebSocket(authUrl);
    
    ws.onopen = () => {
      console.log('\n✅ WebSocket 连接成功！');
      console.log('等待服务端响应...');
    };
    
    ws.onmessage = (event) => {
      console.log('\n📨 收到消息:', event.data);
      ws.close();
    };
    
    ws.onerror = (error) => {
      console.log('\n❌ WebSocket 错误:', error);
    };
    
    ws.onclose = (event) => {
      console.log('\n🔌 连接关闭, code:', event.code, 'reason:', event.reason || '(无)');
    };
    
  } catch (error) {
    console.error('\n❌ 构建 URL 失败:', error);
  }
}

// 执行测试
testConnection();

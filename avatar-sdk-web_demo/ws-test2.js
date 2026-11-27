// 测试 1：直接在 URL 传 appId
console.log('=== 测试 1: URL传 appId ===');
var ws1 = new WebSocket('wss://avatar.cn-huadong-1.xf-yun.com/v1/interact?appId=D70F5FA7');
ws1.onopen = function() { console.log(' 测试1 成功！'); };
ws1.onerror = function(e) { console.log(' 测试1 错误:', e.type); };
ws1.onclose = function(e) { console.log(' 测试1 关闭 code:', e.code); };

// 测试 2：尝试 xf-yun.com 接口鉴权方式（header 形式）
console.log('=== 测试 2: apiKey= 形式 ===');
var ws2 = new WebSocket('wss://avatar.cn-huadong-1.xf-yun.com/v1/interact?appId=D70F5FA7&apiKey=DD15443262db70AC863015F7681cc6D7');
ws2.onopen = function() { console.log(' 测试2 成功！'); };
ws2.onerror = function(e) { console.log(' 测试2 错误:', e.type); };
ws2.onclose = function(e) { console.log(' 测试2 关闭 code:', e.code); };

// 测试 3：CryptoJS 的另一种签名方式
console.log('=== 测试 3: 备选签名 ===');
// 尝试通过 fetch 获取 token
fetch('https://avatar.cn-huadong-1.xf-yun.com/v1/interact', {
  headers: { 'appId': 'D70F5FA7', 'apiKey': 'DD15443262db70AC863015F7681cc6D7' }
}).then(r => console.log('fetch 状态:', r.status)).catch(e => console.log('fetch 错误:', e));

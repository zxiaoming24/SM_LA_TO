// ==========================================
// 讯飞形影 WebSocket 签名测试（独立版）
// 复制以下全部代码到浏览器 Console 执行
// ==========================================

const apiKey = 'DD15443262db70AC863015F7681cc6D7';
const apiSecret = 'Yzg1Yjg1YzM1YTA2OTg1N2Y5MGQ1MmZm';
const serverUrl = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact';

// 加载 crypto-js
if (typeof CryptoJS === 'undefined') {
  var script = document.createElement('script');
  script.src = 'https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.2.0/crypto-js.min.js';
  document.head.appendChild(script);
  await new Promise(function(r) { script.onload = r; });
}

function buildSignedUrl(url, key, secret) {
  var match = url.match(/^wss?:\/\/([^\/]+)(\/.*)/);
  var host = match[1];
  var path = match[2];
  var date = new Date().toUTCString();
  var sigOrigin = 'host: ' + host + '\ndate: ' + date + '\nGET ' + path + ' HTTP/1.1';
  var sig = CryptoJS.enc.Base64.stringify(CryptoJS.HmacSHA256(sigOrigin, secret));
  var authOrigin = 'api_key="' + key + '", algorithm="hmac-sha256", headers="host date request-line", signature="' + sig + '"';
  var auth = CryptoJS.enc.Base64.stringify(CryptoJS.enc.Utf8.parse(authOrigin));
  return url + '?authorization=' + encodeURIComponent(auth) + '&date=' + encodeURIComponent(date) + '&host=' + host;
}

var signedUrl = buildSignedUrl(serverUrl, apiKey, apiSecret);
console.log('=== 签名 URL ===');
console.log(signedUrl);

// 测试连接
console.log('=== 开始测试 WebSocket 连接 ===');
var ws = new WebSocket(signedUrl);
ws.onopen = function() { console.log(' WebSocket 连接成功！'); };
ws.onerror = function(e) { console.log(' WebSocket 错误:', e.type); };
ws.onclose = function(e) { console.log('WebSocket 关闭, code:', e.code, 'reason:', e.reason); };

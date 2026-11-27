const http = require('http');

http.get('http://localhost:4490/api/algorithms', (res) => {
  let data = '';
  
  res.on('data', (chunk) => {
    data += chunk;
  });
  
  res.on('end', () => {
    console.log('Status Code:', res.statusCode);
    console.log('Content-Type:', res.headers['content-type']);
    console.log('Response (first 500 chars):', data.substring(0, 500));
  });
}).on('error', (err) => {
  console.error('Error:', err.message);
});

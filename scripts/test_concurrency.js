const axios = require('axios');
const https = require('https');

// 创建axios实例
const apiClient = axios.create({
  httpsAgent: new https.Agent({  
    rejectUnauthorized: false
  }),
  timeout: 30000
});

// API配置
const API_BASE_URL = 'http://localhost:8000';
const MODEL = 'glm-5.1';

// 测试参数
const TEST_PROMPT = '请简短回答：考研数学的重点是什么？';
const MAX_CONCURRENT_REQUESTS = 2;

// 测试结果
const results = {
  totalRequests: 0,
  successfulRequests: 0,
  rateLimitedRequests: 0,
  otherErrors: 0,
  firstRequestTime: null,
  lastRequestTime: null,
  concurrentResults: []
};

// 检查是否是限流错误
function isRateLimitError(error) {
  if (error.response) {
    const status = error.response.status;
    return status === 429 || status === 1302;
  }
  return false;
}

// 发送单个API请求
async function sendApiRequest(requestId) {
  const startTime = Date.now();
  results.totalRequests++;
  
  try {
    console.log(`[${requestId}] 开始请求...`);
    
    const response = await apiClient.post(`${API_BASE_URL}/api/chat/send/stream`, {
      session_id: 'test-session',
      content: TEST_PROMPT,
      model: MODEL
    }, {
      headers: {
        'Content-Type': 'application/json'
      }
    });

    const endTime = Date.now();
    const duration = endTime - startTime;
    
    results.successfulRequests++;
    results.concurrentResults.push({
      requestId,
      status: 'success',
      duration,
      timestamp: new Date().toISOString()
    });
    
    console.log(`[${requestId}] ✅ 成功完成，耗时: ${duration}ms`);
    return { success: true, duration };
    
  } catch (error) {
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    if (isRateLimitError(error)) {
      results.rateLimitedRequests++;
      results.concurrentResults.push({
        requestId,
        status: 'rate_limited',
        duration,
        error: error.response?.status || 'unknown',
        timestamp: new Date().toISOString()
      });
      console.log(`[${requestId}] ❌ 限流错误 (${error.response?.status})，耗时: ${duration}ms`);
    } else {
      results.otherErrors++;
      results.concurrentResults.push({
        requestId,
        status: 'error',
        duration,
        error: error.message,
        timestamp: new Date().toISOString()
      });
      console.log(`[${requestId}] ❌ 其他错误: ${error.message}，耗时: ${duration}ms`);
    }
    
    return { success: false, duration, error };
  }
}

// 并发测试
async function runConcurrencyTest() {
  console.log('🚀 开始并发测试...');
  console.log(`📊 测试配置: 模型=${MODEL}, 并发数=${MAX_CONCURRENT_REQUESTS}, 提示=${TEST_PROMPT}`);
  console.log('----------------------------------------');
  
  const promises = [];
  
  for (let i = 1; i <= MAX_CONCURRENT_REQUESTS; i++) {
    promises.push(sendApiRequest(i));
  }
  
  // 记录开始时间
  results.firstRequestTime = Date.now();
  
  // 等待所有请求完成
  await Promise.all(promises);
  
  // 记录结束时间
  results.lastRequestTime = Date.now();
  
  // 计算总耗时
  const totalTime = results.lastRequestTime - results.firstRequestTime;
  
  // 打印测试结果
  console.log('\n📊 测试结果:');
  console.log('----------------------------------------');
  console.log(`📈 总请求数: ${results.totalRequests}`);
  console.log(`✅ 成功: ${results.successfulRequests}`);
  console.log(`❌ 限流: ${results.rateLimitedRequests}`);
  console.log(`❌ 其他错误: ${results.otherErrors}`);
  console.log(`⏱️  总耗时: ${totalTime}ms`);
  console.log(`📊 平均响应时间: ${results.successfulRequests > 0 ? 
    (results.concurrentResults.filter(r => r.status === 'success').reduce((sum, r) => sum + r.duration, 0) / results.successfulRequests).toFixed(2) : 0}ms`);
  
  console.log('\n📋 详细结果:');
  console.log('----------------------------------------');
  results.concurrentResults.forEach(result => {
    const statusEmoji = result.status === 'success' ? '✅' : 
                      result.status === 'rate_limited' ? '❌' : '⚠️';
    console.log(`[${result.requestId}] ${statusEmoji} ${result.status.toUpperCase()} - 耗时: ${result.duration}ms - ${result.timestamp}`);
  });
  
  console.log('\n🔍 分析结论:');
  console.log('----------------------------------------');
  
  if (results.rateLimitedRequests > 0) {
    console.log('⚠️  检测到限流错误，实际并发上限可能为1');
    console.log('💡 建议: 启用串行请求，避免并发');
  } else {
    console.log('✅ 未检测到限流错误，可能支持更高并发');
    console.log('💡 建议: 可以考虑增加并发数进行进一步测试');
  }
  
  console.log('\n📝 对比说明:');
  console.log('----------------------------------------');
  console.log('📄 网页显示: 10并发 (纸面配置)');
  console.log('🔧 真实并发: ' + (results.rateLimitedRequests > 0 ? '1' : '≥2') + ' (实测结果)');
  console.log('📊 测试结论: ' + (results.rateLimitedRequests > 0 ? '需要串行执行' : '可以并发执行'));
}

// 运行测试
runConcurrencyTest().catch(error => {
  console.error('❌ 测试执行失败:', error);
});
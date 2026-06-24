import requests
import time
import concurrent.futures
from datetime import datetime

# API配置
API_BASE_URL = "http://localhost:8000"
MODEL = "glm-5.1"

# 测试参数
TEST_PROMPT = "请简短回答：考研数学的重点是什么？"
MAX_CONCURRENT_REQUESTS = 10  # 最大测试并发数

# 测试结果
results = {
    "total_requests": 0,
    "successful_requests": 0,
    "rate_limited_requests": 0,
    "other_errors": 0,
    "concurrent_results": []
}

# 检查是否是限流错误
def is_rate_limit_error(response):
    if response.status_code == 429 or response.status_code == 1302:
        return True
    return False

# 发送单个API请求
def send_api_request(request_id):
    start_time = time.time()
    results["total_requests"] += 1
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/chat/send/stream",
            json={
                "session_id": "test-session",
                "content": TEST_PROMPT,
                "model": MODEL
            },
            timeout=30
        )
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # 转换为毫秒
        
        results["successful_requests"] += 1
        results["concurrent_results"].append({
            "request_id": request_id,
            "status": "success",
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })
        
        return {"success": True, "duration": duration}
        
    except requests.exceptions.RequestException as error:
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # 转换为毫秒
        
        if hasattr(error, 'response') and is_rate_limit_error(error.response):
            results["rate_limited_requests"] += 1
            results["concurrent_results"].append({
                "request_id": request_id,
                "status": "rate_limited",
                "duration": duration,
                "error": error.response.status_code,
                "timestamp": datetime.now().isoformat()
            })
        else:
            results["other_errors"] += 1
            results["concurrent_results"].append({
                "request_id": request_id,
                "status": "error",
                "duration": duration,
                "error": str(error),
                "timestamp": datetime.now().isoformat()
            })
        
        return {"success": False, "duration": duration, "error": error}

# 测试glm-5.1并发限制
def test_glm5_1_concurrency():
    print(f"开始测试 glm-5.1 并发限制...")
    print(f"测试配置: 模型={MODEL}, 提示={TEST_PROMPT}")
    print("----------------------------------------")
    
    # 从1开始逐步增加并发数
    for concurrent in range(1, MAX_CONCURRENT_REQUESTS + 1):
        print(f"\n测试并发数: {concurrent}")
        print("----------------------------------------")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = []
            
            for i in range(1, concurrent + 1):
                futures.append(executor.submit(send_api_request, i))
            
            # 等待所有请求完成
            concurrent.futures.wait(futures)
        
        # 计算成功率
        success_rate = (results["successful_requests"] / results["total_requests"]) * 100 if results["total_requests"] > 0 else 0
        
        print(f"并发数 {concurrent} 结果:")
        print(f"成功: {results['successful_requests']}")
        print(f"限流: {results['rate_limited_requests']}")
        print(f"其他错误: {results['other_errors']}")
        print(f"成功率: {success_rate:.2f}%")
        
        # 如果出现限流错误，说明达到了并发上限
        if results["rate_limited_requests"] > 0:
            print(f"\n在并发数 {concurrent} 时检测到限流错误")
            print(f"glm-5.1 实际并发上限: {concurrent - 1}")
            return concurrent - 1
    
    # 如果所有测试都通过了
    print(f"\n所有测试都通过，glm-5.1 实际并发上限 ≥ {MAX_CONCURRENT_REQUESTS}")
    return MAX_CONCURRENT_REQUESTS

# 设计glm-5.1专用请求控制方案
def design_glm5_1_control():
    print("\nglm-5.1 专用请求控制方案:")
    print("----------------------------------------")
    
    max_concurrent = test_glm5_1_concurrency()
    
    if max_concurrent == 1:
        print("方案: 严格单并发控制 (glm-5.1)")
        print("  - 使用队列管理所有请求")
        print("  - 每次只允许1个请求执行")
        print("  - 请求间隔: 2000ms + 随机抖动(0-600ms)")
        print("  - 指数退避重试: 最多5次")
        print("  - 熔断机制: 连续3次限流切换到glm-4.6")
        print("  - 模型降级: 自动切换备用模型")
    elif max_concurrent <= 3:
        print("方案: 轻度并发控制 (glm-5.1)")
        print(f"  - 最大并发数: {max_concurrent}")
        print("  - 使用令牌桶算法限制速率")
        print("  - 请求间隔: 1000ms + 随机抖动")
        print("  - 智能重试: 根据错误类型调整")
        print("  - 模型监控: 实时监控glm-5.1状态")
    else:
        print("方案: 优化并发控制 (glm-5.1)")
        print(f"  - 最大并发数: {max_concurrent}")
        print("  - 使用漏桶算法平滑流量")
        print("  - 动态调整: 根据成功率自动调整")
        print("  - 优先级队列: 重要请求优先")
        print("  - 模型负载均衡: 多模型协同工作")

# 运行测试
if __name__ == "__main__":
    design_glm5_1_control()
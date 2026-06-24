import requests
import time
import concurrent.futures
import random
from datetime import datetime, timedelta
from collections import deque

# API配置
API_BASE_URL = "http://localhost:8000"
MODEL = "glm-5.1"

# 测试参数
TEST_PROMPT = "请简短回答：考研数学的重点是什么？"
MAX_CONCURRENT_REQUESTS = 20  # 最大测试并发数
TEST_DURATION = 60  # 测试持续时间（秒）

# 测试结果
results = {
    "total_requests": 0,
    "successful_requests": 0,
    "rate_limited_requests": 0,
    "other_errors": 0,
    "concurrent_results": [],
    "request_times": deque(maxlen=60)  # 记录最近60秒的请求时间
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
        results["request_times"].append(datetime.now())
        
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

# 测试并发限制
def test_concurrency_limit():
    print(f"🚀 测试并发限制...")
    print(f"📊 测试配置: 模型={MODEL}, 提示={TEST_PROMPT}")
    print("----------------------------------------")
    
    # 从1开始逐步增加并发数
    for concurrent in range(1, MAX_CONCURRENT_REQUESTS + 1):
        print(f"\n📊 测试并发数: {concurrent}")
        print("----------------------------------------")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = []
            
            for i in range(1, concurrent + 1):
                futures.append(executor.submit(send_api_request, i))
            
            # 等待所有请求完成
            concurrent.futures.wait(futures)
        
        # 计算成功率
        success_rate = (results["successful_requests"] / results["total_requests"]) * 100 if results["total_requests"] > 0 else 0
        
        print(f"📊 并发数 {concurrent} 结果:")
        print(f"✅ 成功: {results['successful_requests']}")
        print(f"❌ 限流: {results['rate_limited_requests']}")
        print(f"❌ 其他错误: {results['other_errors']}")
        print(f"📊 成功率: {success_rate:.2f}%")
        
        # 如果出现限流错误，说明达到了并发上限
        if results["rate_limited_requests"] > 0:
            print(f"\n⚠️  在并发数 {concurrent} 时检测到限流错误")
            print(f"🔍 实际并发上限: {concurrent - 1}")
            return concurrent - 1
    
    # 如果所有测试都通过了
    print(f"\n✅ 所有测试都通过，实际并发上限 ≥ {MAX_CONCURRENT_REQUESTS}")
    return MAX_CONCURRENT_REQUESTS

# 测试RPM限制
def test_rpm_limit():
    print(f"\n🚀 测试RPM限制...")
    print(f"📊 测试配置: 模型={MODEL}, 持续时间={TEST_DURATION}秒")
    print("----------------------------------------")
    
    start_time = time.time()
    request_count = 0
    
    while time.time() - start_time < TEST_DURATION:
        request_count += 1
        send_api_request(f"rpm_{request_count}")
        
        # 随机延迟，模拟真实使用场景
        time.sleep(random.uniform(0.5, 2.0))
    
    # 计算RPM
    elapsed_time = time.time() - start_time
    rpm = (request_count / elapsed_time) * 60
    
    print(f"\n📊 RPM测试结果:")
    print(f"✅ 总请求数: {request_count}")
    print(f"⏱️  测试时间: {elapsed_time:.2f}秒")
    print(f"📊 实际RPM: {rpm:.2f}")
    print(f"❌ 限流: {results['rate_limited_requests']}")
    
    if results["rate_limited_requests"] > 0:
        print(f"\n⚠️  检测到限流错误，实际RPM上限: {request_count / elapsed_time * 60:.2f}")
        return request_count / elapsed_time * 60
    else:
        print(f"\n✅ 未检测到限流错误，RPM上限 ≥ {rpm:.2f}")
        return rpm

# 分析所有限制因素
def analyze_all_limits():
    print("\n分析所有限制因素:")
    print("----------------------------------------")
    
    # 计算平均响应时间
    successful_results = [r for r in results["concurrent_results"] if r["status"] == "success"]
    avg_response_time = sum(r["duration"] for r in successful_results) / len(successful_results) if successful_results else 0
    
    # 计算最近60秒的请求数
    now = datetime.now()
    recent_requests = sum(1 for t in results["request_times"] if now - t <= timedelta(seconds=60))
    
    print(f"🔍 并发上限: {test_concurrency_limit()}")
    print(f"🔍 RPM上限: {test_rpm_limit():.2f}")
    print(f"🔍 平均响应时间: {avg_response_time:.2f}ms")
    print(f"🔍 最近60秒请求数: {recent_requests}")
    
    # 分析限制因素
    print("\n🔍 限制因素分析:")
    print("----------------------------------------")
    
    if results["rate_limited_requests"] > 0:
        print("⚠️  检测到限流错误，主要限制因素:")
        print("  - 并发数限制")
        print("  - RPM限制")
        print("  - 可能的其他因素")
    else:
        print("✅ 未检测到限流错误，系统性能良好")

# 设计智能请求控制方案
def design_smart_request_control():
    print("\n📝 智能请求控制方案设计:")
    print("----------------------------------------")
    
    # 基于分析结果设计方案
    if results["rate_limited_requests"] > 0:
        print("🔧 方案: 严格流量控制")
        print("  - 单并发队列: 确保不触发并发限制")
        print("  - RPM限制: 每分钟不超过实测上限的80%")
        print("  - 请求间隔: 2000ms + 随机抖动(0-600ms)")
        print("  - 指数退避重试: 最多5次")
        print("  - 熔断机制: 连续3次限流切换到备用模型")
        print("  - 动态调整: 根据成功率自动调整请求速率")
    else:
        print("🔧 方案: 优化流量控制")
        print("  - 最大并发数: 3 (安全边际)")
        print("  - RPM限制: 每分钟不超过实测上限的90%")
        print("  - 令牌桶算法: 平滑请求流量")
        print("  - 智能重试: 根据错误类型调整")
        print("  - 优先级队列: 重要请求优先处理")

# 运行测试
if __name__ == "__main__":
    analyze_all_limits()
    design_smart_request_control()
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
        print(f"[{request_id}] 开始请求...")
        
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
        
        print(f"[{request_id}] ✅ 成功完成，耗时: {duration:.2f}ms")
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
            print(f"[{request_id}] ❌ 限流错误 ({error.response.status_code})，耗时: {duration:.2f}ms")
        else:
            results["other_errors"] += 1
            results["concurrent_results"].append({
                "request_id": request_id,
                "status": "error",
                "duration": duration,
                "error": str(error),
                "timestamp": datetime.now().isoformat()
            })
            print(f"[{request_id}] ❌ 其他错误: {str(error)}，耗时: {duration:.2f}ms")
        
        return {"success": False, "duration": duration, "error": error}

# 并发测试
def run_concurrency_test(max_concurrent):
    print(f"🚀 开始并发测试 (最大并发数: {max_concurrent})...")
    print(f"📊 测试配置: 模型={MODEL}, 提示={TEST_PROMPT}")
    print("----------------------------------------")
    
    # 逐步增加并发数
    for concurrent in range(1, max_concurrent + 1):
        print(f"\n📊 测试并发数: {concurrent}")
        print("----------------------------------------")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = []
            
            for i in range(1, concurrent + 1):
                futures.append(executor.submit(send_api_request, i))
            
            # 记录开始时间
            start_time = time.time()
            
            # 等待所有请求完成
            concurrent.futures.wait(futures)
        
        # 记录结束时间
        end_time = time.time()
        total_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        # 计算成功率
        success_rate = (results["successful_requests"] / results["total_requests"]) * 100 if results["total_requests"] > 0 else 0
        
        print(f"\n📊 并发数 {concurrent} 测试结果:")
        print("----------------------------------------")
        print(f"📈 总请求数: {results['total_requests']}")
        print(f"✅ 成功: {results['successful_requests']}")
        print(f"❌ 限流: {results['rate_limited_requests']}")
        print(f"❌ 其他错误: {results['other_errors']}")
        print(f"⏱️  总耗时: {total_time:.2f}ms")
        print(f"📊 成功率: {success_rate:.2f}%")
        
        # 计算平均响应时间
        successful_results = [r for r in results["concurrent_results"] if r["status"] == "success"]
        if successful_results:
            avg_time = sum(r["duration"] for r in successful_results) / len(successful_results)
            print(f"📊 平均响应时间: {avg_time:.2f}ms")
        
        # 检查是否达到并发上限
        if results["rate_limited_requests"] > 0:
            print(f"\n⚠️  在并发数 {concurrent} 时检测到限流错误，实际并发上限可能为 {concurrent - 1}")
            break
    
    # 打印详细结果
    print("\n📋 详细结果:")
    print("----------------------------------------")
    for result in results["concurrent_results"]:
        status_text = "成功" if result["status"] == "success" else "限流" if result["status"] == "rate_limited" else "错误"
        print(f"[{result['request_id']}] {status_text} - 耗时: {result['duration']:.2f}ms - {result['timestamp']}")

# 运行测试
if __name__ == "__main__":
    run_concurrency_test(MAX_CONCURRENT_REQUESTS)
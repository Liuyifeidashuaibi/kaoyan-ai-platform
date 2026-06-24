#!/usr/bin/env pwsh

# 测试配置
$API_BASE_URL = "http://localhost:8000"
$MODEL = "glm-5.1"
$TEST_PROMPT = "请简短回答：考研数学的重点是什么？"
$MAX_CONCURRENT_REQUESTS = 2

# 测试结果
$results = @{
    totalRequests = 0
    successfulRequests = 0
    rateLimitedRequests = 0
    otherErrors = 0
    concurrentResults = @()
}

# 检查是否是限流错误
function Is-RateLimitError($response) {
    if ($response.StatusCode -eq 429 -or $response.StatusCode -eq 1302) {
        return $true
    }
    return $false
}

# 发送单个API请求
function Send-ApiRequest($requestId) {
    $startTime = Get-Date
    $results.totalRequests++
    
    try {
        Write-Host "[$requestId] 开始请求..."
        
        $response = Invoke-RestMethod -Uri "$API_BASE_URL/api/chat/send/stream" -Method Post -Body @{
            session_id = "test-session"
            content = $TEST_PROMPT
            model = $MODEL
        } -ContentType "application/json" -TimeoutSec 30
        
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        $results.successfulRequests++
        $results.concurrentResults += @{
            requestId = $requestId
            status = "success"
            duration = $duration
            timestamp = (Get-Date).ToString("o")
        }
        
        Write-Host "[$requestId] ✅ 成功完成，耗时: $duration ms"
        return @{ success = $true; duration = $duration }
        
    } catch {
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalMilliseconds
        
        if (Is-RateLimitError $_.Exception.Response) {
            $results.rateLimitedRequests++
            $results.concurrentResults += @{
                requestId = $requestId
                status = "rate_limited"
                duration = $duration
                error = $_.Exception.Response.StatusCode
                timestamp = (Get-Date).ToString("o")
            }
            Write-Host "[$requestId] ❌ 限流错误 ($($_.Exception.Response.StatusCode))，耗时: $duration ms"
        } else {
            $results.otherErrors++
            $results.concurrentResults += @{
                requestId = $requestId
                status = "error"
                duration = $duration
                error = $_.Exception.Message
                timestamp = (Get-Date).ToString("o")
            }
            Write-Host "[$requestId] ❌ 其他错误: $($_.Exception.Message)，耗时: $duration ms"
        }
        
        return @{ success = $false; duration = $duration; error = $_ }
    }
}

# 并发测试
function Run-ConcurrencyTest {
    Write-Host "🚀 开始并发测试..."
    Write-Host "📊 测试配置: 模型=$MODEL, 并发数=$MAX_CONCURRENT_REQUESTS, 提示=$TEST_PROMPT"
    Write-Host "----------------------------------------"
    
    $promises = @()
    
    for ($i = 1; $i -le $MAX_CONCURRENT_REQUESTS; $i++) {
        $promises += Send-ApiRequest $i
    }
    
    # 记录开始时间
    $startTime = Get-Date
    
    # 等待所有请求完成
    $promises | ForEach-Object { $_.Wait() }
    
    # 记录结束时间
    $endTime = Get-Date
    $totalTime = ($endTime - $startTime).TotalMilliseconds
    
    # 打印测试结果
    Write-Host "`n📊 测试结果:"
    Write-Host "----------------------------------------"
    Write-Host "📈 总请求数: $($results.totalRequests)"
    Write-Host "✅ 成功: $($results.successfulRequests)"
    Write-Host "❌ 限流: $($results.rateLimitedRequests)"
    Write-Host "❌ 其他错误: $($results.otherErrors)"
    Write-Host "⏱️  总耗时: $totalTime ms"
    
    $successfulResults = $results.concurrentResults | Where-Object { $_.status -eq "success" }
    if ($successfulResults.Count -gt 0) {
        $avgTime = ($successfulResults | Measure-Object -Property duration -Average).Average
        Write-Host "📊 平均响应时间: $([math]::Round($avgTime, 2)) ms"
    }
    
    Write-Host "`n📋 详细结果:"
    Write-Host "----------------------------------------"
    $results.concurrentResults | ForEach-Object {
        $statusEmoji = if ($_.status -eq "success") { "✅" } elseif ($_.status -eq "rate_limited") { "❌" } else { "⚠️" }
        Write-Host "[$($_.requestId)] $statusEmoji $($_.status.ToUpper()) - 耗时: $($_.duration) ms - $($_.timestamp)"
    }
    
    Write-Host "`n🔍 分析结论:"
    Write-Host "----------------------------------------"
    
    if ($results.rateLimitedRequests -gt 0) {
        Write-Host "⚠️  检测到限流错误，实际并发上限可能为1"
        Write-Host "💡 建议: 启用串行请求，避免并发"
    } else {
        Write-Host "✅ 未检测到限流错误，可能支持更高并发"
        Write-Host "💡 建议: 可以考虑增加并发数进行进一步测试"
    }
    
    Write-Host "`n📝 对比说明:"
    Write-Host "----------------------------------------"
    Write-Host "📄 网页显示: 10并发 (纸面配置)"
    Write-Host "🔧 真实并发: " + ($results.rateLimitedRequests -gt 0 ? '1' : '≥2') + " (实测结果)"
    Write-Host "📊 测试结论: " + ($results.rateLimitedRequests -gt 0 ? '需要串行执行' : '可以并发执行')
}

# 运行测试
Run-ConcurrencyTest
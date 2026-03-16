import aiohttp
import asyncio
import json
import time
import os
from datetime import datetime

async def test_c5_new_api():
    """测试新的C5Game API接口并保存原始响应"""
    
    # 硬编码参数 - 你可以修改这些值
    APP_KEY = "2c813df99211431888709d3c6f47eee6"  # 替换为你的API Key
    MARKET_HASH_NAME = "FAMAS | Half Sleeve (Field-Tested)"  # 商品哈希名
    APP_ID = 730  # CS2
    
    # 筛选参数（测试这些是否实际可用）
    MAX_PRICE = 0.3  # 价格上限
    MIN_WEAR = 0.15   # 最低磨损
    MAX_WEAR = 0.35   # 最高磨损
    
    # 分页参数
    PAGE_NUM = 1
    PAGE_SIZE = 2
    
    # API端点
    BASE_URL = "https://openapi.c5game.com"
    ENDPOINT = "/merchant/market/v2/products/list"
    
    # 创建保存目录
    save_dir = "api_responses"
    os.makedirs(save_dir, exist_ok=True)
    
    # 构建请求
    url = f"{BASE_URL}{ENDPOINT}"
    params = {"app-key": APP_KEY}
    
    # 测试用例
    request_bodies = [
        {
            "name": "文档标准版",
            "body": {
                "marketHashName": MARKET_HASH_NAME,
                "appId": APP_ID,
                "pageNum": PAGE_NUM,
                "pageSize": PAGE_SIZE
            }
        },
        {
            "name": "包含隐藏参数版",
            "body": {
                "marketHashName": MARKET_HASH_NAME,
                "appId": APP_ID,
                "pageNum": PAGE_NUM,
                "pageSize": PAGE_SIZE,
                "maxPrice": MAX_PRICE,
                "minWear": MIN_WEAR,
                "maxWear": MAX_WEAR
            }
        }
    ]
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with aiohttp.ClientSession() as session:
        for i, test_case in enumerate(request_bodies):
            print(f"\n{'='*60}")
            print(f"测试 {i+1}: {test_case['name']}")
            print(f"{'='*60}")
            
            try:
                start_time = time.perf_counter()
                
                async with session.post(
                    url=url,
                    params=params,
                    json=test_case['body'],
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    elapsed = (time.perf_counter() - start_time) * 1000
                    
                    print(f"状态码: {response.status}")
                    print(f"响应时间: {elapsed:.2f}ms")
                    
                    # 获取完整的原始响应
                    raw_response = await response.text()
                    
                    # 生成文件名
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    filename = f"{save_dir}/response_{i+1}_{timestamp}.txt"
                    
                    # 保存完整的原始响应信息
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("=" * 80 + "\n")
                        f.write("请求信息:\n")
                        f.write("=" * 80 + "\n")
                        f.write(f"测试名称: {test_case['name']}\n")
                        f.write(f"请求时间: {datetime.now().isoformat()}\n")
                        f.write(f"URL: {url}\n\n")
                        
                        f.write("请求参数:\n")
                        f.write(json.dumps(params, indent=2) + "\n\n")
                        
                        f.write("请求头:\n")
                        f.write(json.dumps(headers, indent=2) + "\n\n")
                        
                        f.write("请求体:\n")
                        f.write(json.dumps(test_case['body'], indent=2) + "\n\n")
                        
                        f.write("=" * 80 + "\n")
                        f.write("响应信息:\n")
                        f.write("=" * 80 + "\n")
                        f.write(f"状态码: {response.status}\n")
                        f.write(f"响应时间: {elapsed:.2f}ms\n\n")
                        
                        f.write("响应头:\n")
                        for key, value in response.headers.items():
                            f.write(f"  {key}: {value}\n")
                        f.write("\n")
                        
                        f.write("=" * 80 + "\n")
                        f.write("原始响应内容:\n")
                        f.write("=" * 80 + "\n")
                        f.write(raw_response)
                    
                    print(f"✅ 原始响应已保存到: {filename}")
                    
                    # 尝试解析JSON以便在控制台显示摘要
                    try:
                        data = json.loads(raw_response)
                        success = data.get("success", False)
                        print(f"API成功: {success}")
                        
                        if success:
                            api_data = data.get("data", {})
                            item_list = api_data.get("list", [])
                            print(f"返回商品数量: {len(item_list)}")
                            if item_list:
                                print("前3个商品:")
                                for j, item in enumerate(item_list[:3]):
                                    price = item.get("price", "N/A")
                                    product_id = item.get("productId", "N/A")
                                    print(f"  {j+1}. ID: {product_id}, 价格: {price}")
                    except:
                        print("响应内容不是JSON格式")
                    
            except Exception as e:
                print(f"❌ 请求失败: {e}")
                # 保存错误信息
                error_filename = f"{save_dir}/error_{i+1}_{datetime.now().strftime('%H%M%S')}.txt"
                with open(error_filename, 'w', encoding='utf-8') as f:
                    f.write(f"请求失败: {str(e)}\n")
                    f.write(f"测试用例: {test_case['name']}\n")
                    f.write(f"时间: {datetime.now().isoformat()}\n")
                print(f"✅ 错误信息已保存到: {error_filename}")
            
            # 等待一下，避免请求过快
            await asyncio.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"测试完成！所有响应已保存到 '{save_dir}' 目录")
    print(f"{'='*60}")

async def main():
    print("🧪 C5Game API接口测试 - 保存原始响应")
    print("开始测试...")
    
    await test_c5_new_api()

if __name__ == "__main__":
    asyncio.run(main())
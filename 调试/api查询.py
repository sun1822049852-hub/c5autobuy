import asyncio
import aiohttp
import json

class C5MarketAPIScannerTester:
    """C5MarketAPIScanner 单次请求测试器"""
    
    @staticmethod
    async def test():
        """执行单次测试"""
        # ========== 在这里修改参数 ==========
        API_KEY = "2c813df99211431888709d3c6f47eee6"  # 替换为您的API密钥
        MARKET_HASH_NAME = "FAMAS | Half Sleeve (Field-Tested)"
        MAX_PRICE = 0.5
        MIN_WEAR = 0.15
        MAX_WEAR = 0.23
        # ==================================
        
        # 构建请求
        url = "https://openapi.c5game.com/merchant/market/v2/products/condition/hash/name"
        params = {"app-key": API_KEY}
        request_body = {
            "pageNum": 1,
            "pageSize": 20,
            "appId": 730,
            "marketHashName": MARKET_HASH_NAME,
            "maxPrice": MAX_PRICE,
            "minWear": MIN_WEAR,
            "maxWear": MAX_WEAR
        }
        
        # 保存请求体
        with open("request.json", "w", encoding="utf-8") as f:
            json.dump(request_body, f, indent=2, ensure_ascii=False)
        print("✅ 请求体已保存到: request.json")
        
        # 发送请求
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=url,
                    params=params,
                    json=request_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    # 保存响应
                    text = await response.text()
                    with open("response.json", "w", encoding="utf-8") as f:
                        f.write(text)
                    
                    print(f"✅ 响应已保存到: response.json")
                    print(f"📊 状态码: {response.status}")
                    print(f"📏 响应大小: {len(text)} 字节")
                    
        except Exception as e:
            print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    asyncio.run(C5MarketAPIScannerTester.test())
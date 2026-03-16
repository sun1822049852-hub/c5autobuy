# dome.py
import os
from xsign import XSignWrapper

# 创建生成器实例
gen = XSignWrapper(wasm_path='test.wasm')

# 生成x_sign（确保参数正确）
try:
    x_sign = gen.generate(
        path="pay/order/v1/pay",        # 路径
        method="POST",              # HTTP方法
        timestamp="1766729392773",    # 时间戳
        token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1aWQiOjEwMDM0NDYyNDgsImN0ZSI6MTc2NjQ3OTMxMCwic2N0IjoiYzVnYW1lIn0.jWS0LCqM1Uzblz1CEgcnsLQygQlU0J-n2z6oqzUAWRU"  # token
    )
    
    print(f"✅ 生成的x_sign: {x_sign}")
    print(f"x_sign长度: {len(x_sign)}")
    
    # 显示结果详情
    if x_sign:
        print(f"结果类型: {type(x_sign)}")
        print(f"是否为字符串: {isinstance(x_sign, str)}")
        
        # 检查格式
        if x_sign:
            if len(x_sign) == 32 and all(c in '0123456789abcdefABCDEF' for c in x_sign):
                print("格式: 32位十六进制 (MD5)")
    else:
        print("⚠️ 警告: x_sign不合法")
        
except Exception as e:
    print(f"❌ 错误信息: {e}")
    import traceback
    traceback.print_exc()

# 调试信息
print(f"\n🔍 调试信息:")
print(f"WASM文件路径: {gen.wasm_path}")
print(f"WASM文件是否存在: {os.path.exists(gen.wasm_path)}")
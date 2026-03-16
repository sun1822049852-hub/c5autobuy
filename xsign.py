import subprocess
import json
import tempfile
import os
import threading
import uuid
import queue
import time
from typing import Union

class XSignWrapper:
    """
    x-sign生成器 - 常驻Node.js进程模式
    """
    
    def __init__(self, wasm_path: str = 'test.wasm', 
                 persistent: bool = True, 
                 timeout: int = 10):
        """
        初始化x-sign生成器
        
        Args:
            wasm_path: WASM文件路径
            persistent: 是否使用常驻进程模式
            timeout: 单次执行超时时间(秒)
        """
        self.wasm_path = os.path.abspath(wasm_path)
        self.timeout = timeout
        self.persistent = persistent
        
        # 检查WASM文件
        if not os.path.exists(self.wasm_path):
            raise FileNotFoundError(f"❌ WASM文件不存在: {self.wasm_path}")
        
        # 检查Node.js
        self._check_nodejs()
        
        # 常驻进程相关
        self._process = None
        self._response_queue = queue.Queue()
        self._pending_requests = {}  # id -> (event, callback)
        self._lock = threading.Lock()
        self._reader_thread = None
        self._running = False
        
        # 如果启用常驻模式，启动进程
        if self.persistent:
            self._start_persistent_process()
    
    def _check_nodejs(self):
        """检查Node.js是否可用"""
        try:
            subprocess.run(['node', '--version'], 
                          capture_output=True, 
                          timeout=5, 
                          text=True,
                          check=True)
        except FileNotFoundError:
            raise RuntimeError("❌ 未找到Node.js，请先安装Node.js并添加到PATH")
        except Exception as e:
            raise RuntimeError(f"❌ Node.js检查失败: {e}")
    
    def _start_persistent_process(self):
        """启动常驻Node.js进程"""
        # 创建Node.js常驻服务代码
        node_code = '''
const fs = require('fs');
const { TextEncoder } = require('util');

// 🔴 复用你原有的编码和签名生成函数
function encodeStringToMemory(str, malloc, realloc, exports) {
    const encoder = new TextEncoder();
    
    if (realloc === undefined) {
        const bytes = encoder.encode(str);
        const pointer = malloc(bytes.length, 1);
        const memory = new Uint8Array(exports.memory.buffer);
        for (let i = 0; i < bytes.length; i++) {
            memory[pointer + i] = bytes[i];
        }
        return { pointer, length: bytes.length };
    }
    
    const strLength = str.length;
    let pointer = malloc(strLength, 1);
    const memory = new Uint8Array(exports.memory.buffer);
    
    let asciiCount = 0;
    for (; asciiCount < strLength; asciiCount++) {
        const charCode = str.charCodeAt(asciiCount);
        if (charCode > 127) break;
        memory[pointer + asciiCount] = charCode;
    }
    
    if (asciiCount !== strLength) {
        if (asciiCount !== 0) {
            str = str.slice(asciiCount);
        }
        const estimatedSize = asciiCount + 3 * str.length;
        pointer = realloc(pointer, strLength, estimatedSize, 1);
        const targetMemory = new Uint8Array(memory.buffer, pointer + asciiCount, estimatedSize - asciiCount);
        const encodeResult = encoder.encodeInto(str, targetMemory);
        const actualSize = asciiCount + encodeResult.written;
        pointer = realloc(pointer, estimatedSize, actualSize, 1);
        return { pointer, length: actualSize };
    }
    
    return { pointer, length: strLength };
}

function calculateSignature(path, method, timestamp, token, exports) {
    // 编码路径
    const { pointer: pathPtr, length: pathLen } = encodeStringToMemory(
        path, exports.__wbindgen_malloc, exports.__wbindgen_realloc, exports
    );
    
    // 编码方法（大写）
    const { pointer: methodPtr, length: methodLen } = encodeStringToMemory(
        method.toUpperCase(), exports.__wbindgen_malloc, exports.__wbindgen_realloc, exports
    );
    
    // 编码时间戳
    const { pointer: timestampPtr, length: timestampLen } = encodeStringToMemory(
        timestamp.toString(), exports.__wbindgen_malloc, exports.__wbindgen_realloc, exports
    );
    
    // 编码token
    const { pointer: tokenPtr, length: tokenLen } = encodeStringToMemory(
        token, exports.__wbindgen_malloc, exports.__wbindgen_realloc, exports
    );
    
    // 调用WASM函数
    const signatureResult = exports.sg(
        pathPtr, pathLen,
        methodPtr, methodLen,
        timestampPtr, timestampLen,
        tokenPtr, tokenLen
    );
    
    if (Array.isArray(signatureResult) && signatureResult.length >= 2) {
        const [resultPointer, resultLength] = signatureResult;
        const memory = new Uint8Array(exports.memory.buffer);
        let signatureStr = '';
        
        for (let i = 0; i < resultLength && i < 1000; i++) {
            const byte = memory[resultPointer + i];
            if (byte === 0) break;
            signatureStr += String.fromCharCode(byte);
        }
        
        if (exports.__wbindgen_free) {
            exports.__wbindgen_free(resultPointer, resultLength, 1);
        }
        
        return signatureStr;
    }
    
    return null;
}

// 🔴 WASM实例（全局唯一，常驻内存）
let wasmExports = null;

async function loadWasm(wasmPath) {
    const buffer = fs.readFileSync(wasmPath);
    const bytes = new Uint8Array(buffer).buffer;
    
    const imports = {
        wbg: {
            __wbg_log_fd9bb94dca9f855e: () => {},
            __wbindgen_init_externref_table: () => {}
        }
    };
    
    const { instance } = await WebAssembly.instantiate(bytes, imports);
    const exports = instance.exports;
    
    if (exports.__wbindgen_start) {
        exports.__wbindgen_start();
    }
    
    return exports;
}

// 🔴 主服务循环
async function main() {
    try {
        const wasmPath = process.argv[2];
        wasmExports = await loadWasm(wasmPath);
        
        console.error("✅ WASM加载完成，常驻进程已就绪");
        
        // 监听标准输入（请求）
        process.stdin.setEncoding('utf8');
        let buffer = '';
        
        process.stdin.on('data', (chunk) => {
            buffer += chunk;
            const lines = buffer.split('\\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const request = JSON.parse(line);
                        const { id, path, method, timestamp, token } = request;
                        
                        // 🔴 使用常驻的WASM实例生成签名
                        const xsign = calculateSignature(path, method, timestamp, token, wasmExports);
                        
                        // 返回结果（UTF-8编码）
                        console.log(JSON.stringify({
                            id: id,
                            success: true,
                            x_sign: xsign
                        }));
                    } catch (error) {
                        console.log(JSON.stringify({
                            id: request?.id,
                            success: false,
                            error: error.message
                        }));
                    }
                }
            }
        });
        
        // 保持进程运行
        process.stdin.on('end', () => {
            process.exit(0);
        });
        
    } catch (error) {
        console.error("❌ 常驻进程启动失败:", error);
        process.exit(1);
    }
}

// 启动服务
main();
'''
        
        # 创建临时Node.js文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(node_code)
            node_file = f.name
        
        try:
            # 启动常驻Node.js进程（字节模式）
            self._process = subprocess.Popen(
                ['node', node_file, self.wasm_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0 # 字节模式
            )
            
            self._running = True
            
            # 启动输出读取线程（字节模式）
            self._reader_thread = threading.Thread(target=self._read_output_loop_bytes, daemon=True)
            self._reader_thread.start()
            
            # 等待WASM加载完成
            loaded = False
            for _ in range(50):  # 最多等待5秒
                try:
                    line = self._process.stderr.readline()
                    if not line:
                        break
                    decoded_line = line.decode('utf-8', errors='replace')
                    if "✅ WASM加载完成" in decoded_line:
                        loaded = True
                        break
                except Exception as e:
                    print(f"⚠️  读取进程输出时出错: {e}")
                time.sleep(0.1)
            
            if not loaded:
                print("⚠️  XSign常驻进程启动可能失败")
            
        finally:
            # 清理临时文件
            try:
                os.unlink(node_file)
            except:
                pass
    
    def _read_output_loop_bytes(self):
        """读取Node.js进程的输出（字节模式）"""
        while self._running and self._process:
            try:
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break
                
                if line:
                    try:
                        decoded_line = line.decode('utf-8', errors='replace').strip()
                        if decoded_line:
                            result = json.loads(decoded_line)
                            request_id = result.get('id')
                            if request_id in self._pending_requests:
                                event, callback = self._pending_requests.pop(request_id)
                                if callback:
                                    callback(result)
                                event.set()
                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        # 忽略解码错误
                        pass
            except Exception as e:
                print(f"⚠️  读取输出循环异常: {e}")
                break
    
    def _validate_parameters(self, path: str, method: str, timestamp: Union[str, int, float], token: str):
        """验证参数（保持原有逻辑）"""
        if not all([path, method, timestamp, token]):
            raise ValueError("❌ 生成x-sign缺少必要的参数")
        
        path = str(path).strip()
        method = str(method).strip().upper()
        timestamp_str = str(timestamp).strip()
        token = str(token).strip()
        
        if not path:
            raise ValueError("❌ path参数不能为空")
        
        if not path.startswith('/'):
            path = '/' + path
        
        valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        if method not in valid_methods:
            raise ValueError(f"❌ 不支持的HTTP方法: {method}")
        
        if not timestamp_str.isdigit():
            raise ValueError(f"❌ 时间戳格式错误，应为数字: {timestamp_str}")
        
        if not token:
            raise ValueError("❌ token参数不能为空")
        
        return path, method, timestamp_str, token
    
    def _generate_one_shot(self, path: str, method: str, timestamp: str, token: str) -> str:
        """一次性生成模式（兼容原有逻辑）"""
        # 🔴 原有的一次性生成逻辑
        js_code = self._create_js_code()  # 保持原有JS代码生成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(js_code)
            js_file = f.name
        
        try:
            params = {
                'path': path,
                'method': method,
                'timestamp': timestamp,
                'token': token,
                'wasmPath': self.wasm_path
            }
            
            cmd = ['node', js_file, json.dumps(params, ensure_ascii=False)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',  # 使用UTF-8编码
                errors='replace',   # 编码错误时替换
                universal_newlines=True
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or "未知错误"
                raise RuntimeError(f"Node.js执行失败: {error_msg}")
            
            data = json.loads(result.stdout.strip())
            
            if not data.get('success'):
                error_msg = data.get('error', '未知错误')
                raise RuntimeError(f"WASM生成失败: {error_msg}")
            
            x_sign = data['x_sign']
            
            if not x_sign or not isinstance(x_sign, str):
                raise RuntimeError("生成的x-sign无效")
            
            return x_sign
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Node.js执行超时 ({self.timeout}秒)")
        finally:
            try:
                os.unlink(js_file)
            except:
                pass
    
    def _create_js_code(self):
        """创建JS执行代码"""
        return '''
const fs = require('fs');
const { TextEncoder } = require('util');

function encodeStringToMemory(str, malloc, realloc, exports) {
    const encoder = new TextEncoder();
    
    // 情况1：只有malloc函数（没有realloc）
    if (realloc === undefined) {
        const bytes = encoder.encode(str);
        const pointer = malloc(bytes.length, 1);
        const memory = new Uint8Array(exports.memory.buffer);
        
        for (let i = 0; i < bytes.length; i++) {
            memory[pointer + i] = bytes[i];
        }
        
        return { pointer, length: bytes.length };
    }
    
    // 情况2：有malloc和realloc函数（优化处理ASCII字符）
    const strLength = str.length;
    let pointer = malloc(strLength, 1);
    const memory = new Uint8Array(exports.memory.buffer);
    
    let asciiCount = 0;
    for (; asciiCount < strLength; asciiCount++) {
        const charCode = str.charCodeAt(asciiCount);
        if (charCode > 127) break;  // 遇到非ASCII字符
        memory[pointer + asciiCount] = charCode;
    }
    
    // 如果字符串包含非ASCII字符
    if (asciiCount !== strLength) {
        if (asciiCount !== 0) {
            str = str.slice(asciiCount);  // 跳过已处理的ASCII部分
        }
        
        // UTF-8编码最多3字节/字符
        const estimatedSize = asciiCount + 3 * str.length;
        pointer = realloc(pointer, strLength, estimatedSize, 1);
        
        // 编码剩余部分
        const targetMemory = new Uint8Array(memory.buffer, pointer + asciiCount, estimatedSize - asciiCount);
        const encodeResult = encoder.encodeInto(str, targetMemory);
        
        // 调整到实际大小
        const actualSize = asciiCount + encodeResult.written;
        pointer = realloc(pointer, estimatedSize, actualSize, 1);
        
        return { pointer, length: actualSize };
    }
    
    return { pointer, length: strLength };
}

function calculateSignature(path, method, timestamp, token, exports) {
    // 1. 编码路径字符串
    const { pointer: pathPtr, length: pathLen } = encodeStringToMemory(
        path, 
        exports.__wbindgen_malloc, 
        exports.__wbindgen_realloc, 
        exports
    );
    
    // 2. 编码HTTP方法（转为大写）
    const methodUpper = method.toUpperCase();
    const { pointer: methodPtr, length: methodLen } = encodeStringToMemory(
        methodUpper, 
        exports.__wbindgen_malloc, 
        exports.__wbindgen_realloc, 
        exports
    );
    
    // 3. 编码时间戳字符串
    const timestampStr = timestamp.toString();
    const { pointer: timestampPtr, length: timestampLen } = encodeStringToMemory(
        timestampStr, 
        exports.__wbindgen_malloc, 
        exports.__wbindgen_realloc, 
        exports
    );
    
    // 4. 编码token字符串（必填参数）
    const { pointer: tokenPtr, length: tokenLen } = encodeStringToMemory(
        token, 
        exports.__wbindgen_malloc, 
        exports.__wbindgen_realloc, 
        exports
    );
    
    // 5. 调用WASM的签名生成函数
    const signatureResult = exports.sg(
        pathPtr, pathLen,
        methodPtr, methodLen,
        timestampPtr, timestampLen,
        tokenPtr, tokenLen
    );
    
    // 6. 处理返回结果
    if (Array.isArray(signatureResult) && signatureResult.length >= 2) {
        const [resultPointer, resultLength] = signatureResult;
        const memory = new Uint8Array(exports.memory.buffer);
        let signatureStr = '';
        
        // 从内存读取签名字符串
        for (let i = 0; i < resultLength && i < 1000; i++) {
            const byte = memory[resultPointer + i];
            if (byte === 0) break;  // 遇到字符串结束符
            signatureStr += String.fromCharCode(byte);
        }
        
        // 7. 释放返回结果的内存
        if (exports.__wbindgen_free) {
            exports.__wbindgen_free(resultPointer, resultLength, 1);
        }
        
        return signatureStr;
    }
    
    return null;
}

async function main() {
    try {
        const args = JSON.parse(process.argv[2]);
        const { path, method, timestamp, token, wasmPath } = args;
        
        // 加载WASM模块
        const buffer = fs.readFileSync(wasmPath);
        const bytes = new Uint8Array(buffer).buffer;
        
        const imports = {
            wbg: {
                __wbg_log_fd9bb94dca9f855e: () => {},
                __wbindgen_init_externref_table: () => {}
            }
        };
        
        const { instance } = await WebAssembly.instantiate(bytes, imports);
        const exports = instance.exports;
        
        // 初始化WASM
        if (exports.__wbindgen_start) {
            exports.__wbindgen_start();
        }
        
        // 计算签名
        const xsign = calculateSignature(path, method, timestamp, token, exports);
        
        console.log(JSON.stringify({
            success: true,
            x_sign: xsign
        }));
        
    } catch (error) {
        console.log(JSON.stringify({
            success: false,
            error: error.message
        }));
        process.exit(1);
    }
}

main();
'''
    
    def generate(self, 
                 path: str, 
                 method: str, 
                 timestamp: Union[str, int, float], 
                 token: str) -> str:
        """
        生成x-sign签名
        
        Args:
            path: 请求路径（必填）
            method: HTTP方法（必填）
            timestamp: 时间戳（必填）
            token: 访问令牌（必填）
            
        Returns:
            x_sign字符串
        """
        # 1. 验证参数
        path, method, timestamp, token = self._validate_parameters(
            path, method, timestamp, token
        )
        
        # 2. 根据模式选择生成方式
        if self.persistent and self._process and self._running:
            # 🔴 常驻进程模式
            return self._generate_persistent(path, method, timestamp, token)
        else:
            # 一次性模式（回退）
            return self._generate_one_shot(path, method, timestamp, token)
    
    def _generate_persistent(self, path: str, method: str, timestamp: str, token: str) -> str:
        """通过常驻进程生成签名（字节模式）"""
        request_id = str(uuid.uuid4())[:8]
        event = threading.Event()
        result_container = {'data': None}
        
        def callback(result):
            result_container['data'] = result
        
        with self._lock:
            self._pending_requests[request_id] = (event, callback)
            
            # 发送请求（UTF-8编码字节）
            request = {
                "id": request_id,
                "path": path,
                "method": method,
                "timestamp": timestamp,
                "token": token
            }
            
            try:
                request_bytes = (json.dumps(request) + '\n').encode('utf-8')
                self._process.stdin.write(request_bytes)
                self._process.stdin.flush()
            except Exception as e:
                # 进程可能已终止，回退到一次性模式
                self._running = False
                raise RuntimeError(f"常驻进程通信失败: {e}")
        
        # 等待响应（带超时）
        if not event.wait(self.timeout):
            with self._lock:
                if request_id in self._pending_requests:
                    del self._pending_requests[request_id]
            raise RuntimeError(f"等待响应超时 ({self.timeout}秒)")
        
        result = result_container['data']
        if not result:
            raise RuntimeError("未收到响应")
        
        if not result.get('success'):
            error_msg = result.get('error', '未知错误')
            raise RuntimeError(f"WASM生成失败: {error_msg}")
        
        x_sign = result.get('x_sign')
        if not x_sign:
            raise RuntimeError("响应中缺少x-sign")
        
        return x_sign
    
    def close(self):
        """完全安全的close方法"""
        # 设置停止标志
        self._running = False
        
        # 获取当前线程
        import threading
        current_thread = threading.current_thread()
        
        # 安全关闭进程
        if hasattr(self, '_process') and self._process:
            try:
                # 先尝试温和终止
                if self._process.poll() is None:
                    self._process.terminate()
                
                # 等待很短时间
                import time
                for _ in range(5):  # 最多等0.5秒
                    if self._process.poll() is not None:
                        break
                    time.sleep(0.1)
                
                # 如果还没终止，强制杀死
                if self._process.poll() is None:
                    self._process.kill()
                    
            except Exception as e:
                # 忽略所有异常
                pass
            finally:
                self._process = None
        
        # 安全处理线程 - 这是关键修复！
        if hasattr(self, '_reader_thread') and self._reader_thread:
            try:
                # 检查是否是当前线程
                if self._reader_thread.ident != current_thread.ident:
                    # 不是当前线程，可以尝试join
                    if self._reader_thread.is_alive():
                        self._reader_thread.join(timeout=0.1)
                else:
                    # 是当前线程，不join
                    pass
            except RuntimeError as e:
                # 如果是"cannot join current thread"错误，安全忽略
                if "cannot join current thread" not in str(e):
                    print(f"⚠️  关闭reader线程时出错: {e}")
            except Exception as e:
                print(f"⚠️  关闭reader线程时出错: {e}")
            finally:
                self._reader_thread = None
        
        # 清理其他资源
        if hasattr(self, '_pending_requests'):
            self._pending_requests.clear()
        
        if hasattr(self, '_response_queue'):
            try:
                while not self._response_queue.empty():
                    self._response_queue.get_nowait()
                    self._response_queue.task_done()
            except Exception:
                pass

    def __del__(self):
        """析构函数 """
        try:

            self.close()
        except Exception:
            pass
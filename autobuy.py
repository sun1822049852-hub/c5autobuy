import asyncio
import aiohttp
import json
import time
import os
import sys
from urllib.parse import urlparse, unquote
from xsign import XSignWrapper
import database_setup as db
from datetime import datetime
import pytz
import random 
from urllib.parse import unquote
from typing import Optional, Dict, List, Optional, Any, Tuple
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
import heapq
GLOBAL_XSIGN_WRAPPER = XSignWrapper(
    wasm_path='test.wasm',
    persistent=True,  # 使用常驻进程模式
    timeout=10
)

# 配置文件路径
CONFIG_DIR = "config"
ACCOUNT_DIR = "account"
PRODUCT_CONFIG_FILE = os.path.join(CONFIG_DIR, "product_configs.json")
DB_FILE = "csgo_items.db"
# 确保配置目录存在
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
# 确保账户目录存在
if not os.path.exists(ACCOUNT_DIR):
    os.makedirs(ACCOUNT_DIR)



#查询调度器 接收所有查询组的就绪通知 并分配商品进行查询
class QueryScheduler:
    """基于时间预约的分布式查询调度器"""
    
    def __init__(self, product_pool: List[str], min_cooldown: float = 0.1):
        self.product_pool = product_pool
        self.min_cooldown = min_cooldown
        self.pointer = 0
        self.product_states = {}
        
        for product_id in product_pool:
            self.product_states[product_id] = 0.0
        
        self.scheduled_queue = []
        self.group_ready_callbacks = {}
        self.lock = asyncio.Lock()
        self.running = False
        self.scheduler_task = None
        
        print(f"✅ 查询调度器初始化完成")
        print(f"   商品池大小: {len(product_pool)}")
        print(f"   商品最小冷却: {min_cooldown}秒")
    
    def register_group(self, group_id: str, group_type: str, on_ready_callback):
        """注册查询组到调度器"""
        self.group_ready_callbacks[group_id] = (group_type, on_ready_callback)
        print(f"✅ 查询组注册: {group_id} ({group_type})")
    
    async def notify_group_ready(self, group_id: str):
        """接收到查询组就绪通知（冷却结束）为其调度任务"""
        if group_id not in self.group_ready_callbacks:
            print(f"⚠️  未知的查询组: {group_id}")
            return
        
        async with self.lock:
            if not self.product_pool:
                print("⚠️  商品池为空")
                return
            
            product_id = self.product_pool[self.pointer]
            current_time = time.time_ns() / 1_000_000_000
            product_available_time = self.product_states[product_id]
            
            if current_time >= product_available_time:
                execute_time = current_time
            else:
                execute_time = product_available_time
            
            self.product_states[product_id] = execute_time + self.min_cooldown
            self.pointer = (self.pointer + 1) % len(self.product_pool)
            
            group_type, callback = self.group_ready_callbacks[group_id]
            self._schedule_execution(group_id, product_id, execute_time, callback)
            
            delay = execute_time - current_time
            if delay <= 0.001:
                print(f"⚡ 立即调度: {group_id} -> {product_id}")
            else:
                print(f"⏰ 预约调度: {group_id} -> {product_id} (等待: {delay:.3f}秒)")
    
    def _schedule_execution(self, group_id: str, product_id: str, execute_time: float, callback):
        """将任务加入调度队列"""
        heapq.heappush(self.scheduled_queue, (execute_time, group_id, product_id, callback))
    
    async def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        print(f"🚀 查询调度器已启动")
    
    async def stop(self):
        """停止调度器"""
        if not self.running:
            return
        
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        print(f"🛑 查询调度器已停止")
    
    async def _scheduler_loop(self):
        """调度器主循环"""
        print(f"⏰ 调度器开始运行，监听预约任务...")
        
        while self.running:
            try:
                async with self.lock:
                    if not self.scheduled_queue:
                        await asyncio.sleep(0.001)
                        continue
                    
                    earliest_time, group_id, product_id, callback = self.scheduled_queue[0]
                    current_time = time.time_ns() / 1_000_000_000
                    
                    if current_time >= earliest_time - 0.001:
                        heapq.heappop(self.scheduled_queue)
                        asyncio.create_task(
                            self._execute_scheduled_task(group_id, product_id, callback, current_time)
                        )
                    else:
                        wait_time = earliest_time - current_time
                        if wait_time > 0.001:
                            await asyncio.sleep(min(wait_time, 0.1))
                
                await asyncio.sleep(0.001)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 调度器循环错误: {e}")
                await asyncio.sleep(0.1)
        
        print(f"🛑 调度器循环已停止")
    
    async def _execute_scheduled_task(self, group_id: str, product_id: str, callback, execute_time: float):
        """执行已调度的任务"""
        try:
            current_time = time.time_ns() / 1_000_000_000
            actual_delay = current_time - execute_time
            
            if actual_delay > 0.01:
                print(f"⏱️  任务 {group_id}->{product_id} 延迟执行: {actual_delay*1000:.1f}ms")
            
            await callback(product_id, execute_time)
            
        except Exception as e:
            print(f"❌ 执行调度任务失败: {e}")
    
    def get_stats(self):
        """获取调度器统计信息"""
        current_time = time.time_ns() / 1_000_000_000
        available_products = 0
        cooling_products = 0
        earliest_available = float('inf')
        
        for product_id, available_time in self.product_states.items():
            if current_time >= available_time:
                available_products += 1
            else:
                cooling_products += 1
                earliest_available = min(earliest_available, available_time - current_time)
        
        return {
            'running': self.running,
            'product_pool_size': len(self.product_pool),
            'registered_groups': len(self.group_ready_callbacks),
            'scheduled_tasks': len(self.scheduled_queue),
            'available_products': available_products,
            'cooling_products': cooling_products,
            'next_pointer': self.pointer,
            'earliest_available_in': earliest_available if earliest_available != float('inf') else 0
        }
    
    def display_status(self):
        """显示调度器状态"""
        stats = self.get_stats()
        
        print(f"\n📊 查询调度器状态:")
        print(f"   运行状态: {'✅ 运行中' if stats['running'] else '❌ 已停止'}")
        print(f"   商品池: {stats['product_pool_size']} 个商品")
        print(f"   注册组数: {stats['registered_groups']} 个")
        print(f"   待执行任务: {stats['scheduled_tasks']} 个")
        print(f"   可用商品: {stats['available_products']} 个")
        print(f"   冷却中商品: {stats['cooling_products']} 个")
        print(f"   当前指针: {stats['next_pointer']}")
        
        if stats['scheduled_tasks'] > 0 and self.scheduled_queue:
            next_time, next_group, next_product, _ = self.scheduled_queue[0]
            wait_time = next_time - time.time_ns() / 1_000_000_000
            if wait_time > 0:
                print(f"   下一个任务: {next_group}->{next_product} (等待: {wait_time:.3f}秒)")

#查询组 管理单个账户的一种查询类型的商品集合
class QueryGroup:
    """
    查询组 - 一个账户的一种查询类型的商品集合调用即查询
    支持时间窗口管理：在窗口内查询，窗口外完全休眠
    """
    
    def __init__(self, group_id: str, group_type: str, account_manager, product_items: List[ProductItem], query_scanner_class, result_callback):
        self.group_id = group_id
        self.group_type = group_type
        self.account_manager = account_manager
        self.product_items = product_items
        self.query_scanner_class = query_scanner_class
        self.result_callback = result_callback
        
        # 冷却管理
        if self.group_type == "new":
            # 新查询组：固定1秒
            self.cooldown_range = (1.0, 1.0)
        elif self.group_type == "fast":
            # 高速查询组：固定0.2秒
            self.cooldown_range = (2000, 2000)
        else:
            # 旧查询组：从AccountManager获取冷却时间范围
            self.cooldown_range = account_manager.get_query_cooldown()
        
        
        self.original_cooldown_range = self.cooldown_range  # 保存最初始的范围
        self.next_ready_time = 0
        self.cooldown_task = None
        
        # 查询器缓存
        self.query_scanners = {}
        # 统计信息
        self.running = False
        self.query_count = 0
        self.found_count = 0
        
        # 时间窗口相关
        self.time_config = account_manager.get_query_time_config()
        if group_type in ["new", "fast"]:
             # 新查询组和高速查询组：不受时间窗口限制
            self.in_time_window = True
            print(f"⏰ {group_type.upper()}查询组 {group_id}：不受时间窗口限制，总是可查询")
        else:
            # 旧查询组：受时间窗口限制
            self.in_time_window = False
            print(f"⏰ 旧查询组 {group_id}：受时间窗口限制")
        self.next_window_start = 0
        self.next_window_end = 0
        self.window_monitor_task = None
        self.scheduled_start_task = None
        
        # 限流状态管理 
        self.rate_limit_end_time = 0  # 限流结束时间戳
        self.rate_limit_increment = 0.0  # 累计增加的秒数
        self.rate_limit_timer = None  # 限流计时器

        
        print(f"✅ 查询组创建: {group_id}")
        print(f"   类型: {group_type}")
        print(f"   商品数量: {len(product_items)}")
        print(f"   初始冷却范围: {self.cooldown_range}")
    
    async def start(self):
        """启动查询组 - 按时间窗口管理"""
        if self.running:
            return
        
        self.running = True
        
        # 初始化查询器缓存
        await self._initialize_scanners()
        
        # 对于新查询组，不受时间窗口限制
        if self.group_type in ["new", "fast"]:
            group_name = "新查询" if self.group_type == "new" else "高速查询"
            # 直接启动冷却循环
            self._start_cooldown()
            print(f"✅ {group_name}组启动: {self.group_id}")
            return
        
        # 对于旧查询组，按时间窗口管理
        self.time_config = self.account_manager.get_query_time_config()
        
        if self.time_config and self.time_config['enabled']:
            # 启用时间窗口，计算时间
            self._calculate_window_times()
            
            if self.in_time_window:
                # 当前在时间窗口内，立即启动
                print(f"⏰ {self.group_id} 当前在时间窗口内，立即启动查询")
                self._start_cooldown()
                
                # 启动窗口结束监控
                self.window_monitor_task = asyncio.create_task(self._monitor_window_end())
            else:
                # 当前不在时间窗口内，安排定时启动
                print(f"⏰ {self.group_id} 当前不在时间窗口内，安排定时启动")
                self.scheduled_start_task = asyncio.create_task(self._schedule_window_start())
        else:
            # 未启用时间窗口，不启动查询
            print(f"⏰ {self.group_id} 未启用时间窗口，不启动查询")
            self.running = False
        
        print(f"✅ 查询组启动: {self.group_id}")
    
    async def stop(self):
        """停止查询组"""
        if not self.running:
            return
        
        print(f"🛑 查询组正在停止: {self.group_id}")
        self.running = False
        
        # 停止冷却任务
        if self.cooldown_task and not self.cooldown_task.done():
            self.cooldown_task.cancel()
            try:
                await self.cooldown_task
            except asyncio.CancelledError:
                pass
        
        # 停止定时启动任务
        if self.scheduled_start_task and not self.scheduled_start_task.done():
            self.scheduled_start_task.cancel()
            try:
                await self.scheduled_start_task
            except asyncio.CancelledError:
                pass
        
        # 停止窗口监控任务
        if self.window_monitor_task and not self.window_monitor_task.done():
            self.window_monitor_task.cancel()
            try:
                await self.window_monitor_task
            except asyncio.CancelledError:
                pass
        
        # 停止限流计时器
        if self.rate_limit_timer and not self.rate_limit_timer.done():
            self.rate_limit_timer.cancel()
            try:
                await self.rate_limit_timer
            except asyncio.CancelledError:
                pass
        
        # 清理查询器
        for scanner in self.query_scanners.values():
            if hasattr(scanner, 'cleanup'):
                await scanner.cleanup()
        
        print(f"✅ 查询组已停止: {self.group_id}")
    
    async def _initialize_scanners(self):
        """初始化查询器缓存"""
        for product_item in self.product_items:
            scanner = self.query_scanner_class(self.account_manager, product_item)
            self.query_scanners[product_item.item_id] = scanner
    
    def _calculate_window_times(self):
        """计算时间窗口的开始和结束时间"""
        if not self.time_config or not self.time_config['enabled']:
            self.in_time_window = False
            return
        
        import datetime
        current_time = time.time()
        now = datetime.datetime.now()
        
        # 解析时间窗口配置
        start_hour = self.time_config['start_hour']
        start_minute = self.time_config['start_minute']
        end_hour = self.time_config['end_hour']
        end_minute = self.time_config['end_minute']
        
        # 转换为分钟数
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        
        if start_minutes == end_minutes:
            # 全天
            self.in_time_window = True
            self.next_window_start = current_time
            self.next_window_end = current_time + 86400
            return
        
        # 计算今天的时间窗口开始和结束
        today_start = datetime.datetime(now.year, now.month, now.day, start_hour, start_minute)
        today_end = datetime.datetime(now.year, now.month, now.day, end_hour, end_minute)
        
        if end_minutes > start_minutes:
            # 同一天的时间窗口
            if now >= today_start and now < today_end:
                # 当前在窗口内
                self.in_time_window = True
                self.next_window_start = today_start.timestamp()
                self.next_window_end = today_end.timestamp()
                print(f"⏰ {self.group_id} 在时间窗口内 ({start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d})")
            else:
                # 当前在窗口外
                self.in_time_window = False
                if now < today_start:
                    # 等待今天开始
                    self.next_window_start = today_start.timestamp()
                    self.next_window_end = today_end.timestamp()
                    print(f"⏰ {self.group_id} 等待今天窗口开始 ({start_hour:02d}:{start_minute:02d})")
                else:
                    # 已经结束，等待明天开始
                    tomorrow = now + datetime.timedelta(days=1)
                    tomorrow_start = datetime.datetime(
                        tomorrow.year, tomorrow.month, tomorrow.day, start_hour, start_minute
                    )
                    tomorrow_end = datetime.datetime(
                        tomorrow.year, tomorrow.month, tomorrow.day, end_hour, end_minute
                    )
                    self.next_window_start = tomorrow_start.timestamp()
                    self.next_window_end = tomorrow_end.timestamp()
                    print(f"⏰ {self.group_id} 等待明天窗口开始 ({start_hour:02d}:{start_minute:02d})")
        else:
            # 跨天的时间窗口
            if now >= today_start or now < today_end:
                # 在窗口内
                self.in_time_window = True
                self.next_window_start = today_start.timestamp()
                
                if now < today_end:
                    # 还在今天的结束时间前
                    self.next_window_end = today_end.timestamp()
                else:
                    # 已经过了今天的结束时间，结束时间是明天
                    self.next_window_end = today_end.timestamp() + 86400
                print(f"⏰ {self.group_id} 在跨天窗口内 ({start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d})")
            else:
                # 在窗口外
                self.in_time_window = False
                if now < today_start:
                    # 等待今天开始
                    self.next_window_start = today_start.timestamp()
                    self.next_window_end = today_end.timestamp()
                    print(f"⏰ {self.group_id} 等待今天窗口开始 ({start_hour:02d}:{start_minute:02d})")
                else:
                    # 等待明天开始
                    tomorrow = now + datetime.timedelta(days=1)
                    tomorrow_start = datetime.datetime(
                        tomorrow.year, tomorrow.month, tomorrow.day, start_hour, start_minute
                    )
                    tomorrow_end = datetime.datetime(
                        tomorrow.year, tomorrow.month, tomorrow.day, end_hour, end_minute
                    )
                    self.next_window_start = tomorrow_start.timestamp()
                    self.next_window_end = tomorrow_end.timestamp()
                    print(f"⏰ {self.group_id} 等待明天窗口开始 ({start_hour:02d}:{start_minute:02d})")
    
    async def _schedule_window_start(self):
        """安排窗口开始时的启动"""
        if not self.running:
            return
        
        self._calculate_window_times()
        
        wait_time = self.next_window_start - time.time()
        
        if wait_time <= 0:
            # 立即进入窗口
            self.in_time_window = True
            print(f"⏰ {self.group_id} 进入时间窗口")
            self._start_cooldown()
            return
        
        print(f"⏰ {self.group_id} 等待进入时间窗口: {wait_time:.1f}秒")
        
        try:
            await asyncio.sleep(wait_time)
            
            if self.running:
                # 窗口开始
                self.in_time_window = True
                print(f"⏰ {self.group_id} 进入时间窗口，开始查询")
                self._start_cooldown()
                
                # 启动窗口结束监控
                self.window_monitor_task = asyncio.create_task(self._monitor_window_end())
        except asyncio.CancelledError:
            print(f"⏰ {self.group_id} 窗口启动任务被取消")
        except Exception as e:
            print(f"❌ {self.group_id} 窗口启动任务错误: {e}")
    
    async def _monitor_window_end(self):
        """监控窗口结束"""
        if not self.running or not self.in_time_window:
            return
        
        self._calculate_window_times()
        
        wait_time = self.next_window_end - time.time()
        
        if wait_time <= 0:
            # 窗口已结束
            await self._handle_window_end()
            return
        
        print(f"⏰ {self.group_id} 距离窗口结束还有: {wait_time:.1f}秒")
        
        try:
            await asyncio.sleep(wait_time)
            
            if self.running and self.in_time_window:
                await self._handle_window_end()
        except asyncio.CancelledError:
            print(f"⏰ {self.group_id} 窗口监控任务被取消")
        except Exception as e:
            print(f"❌ {self.group_id} 窗口监控任务错误: {e}")
    
    async def _handle_window_end(self):
        """处理窗口结束"""
        print(f"⏰ {self.group_id} 离开时间窗口，停止查询")
        self.in_time_window = False
        
        # 停止当前冷却任务
        if self.cooldown_task and not self.cooldown_task.done():
            self.cooldown_task.cancel()
            try:
                await self.cooldown_task
            except asyncio.CancelledError:
                pass
        
        # 重新计算下次窗口时间
        self._calculate_window_times()
        
        # 安排下次窗口开始
        if self.running and self.next_window_start > 0:
            self.scheduled_start_task = asyncio.create_task(self._schedule_window_start())
    
    def _start_cooldown(self):
        """开始冷却 """
        if not self.running or not self.in_time_window:
            return
        
        # 检查是否在限流期间
        in_rate_limit = (self.rate_limit_end_time > time.time())
        
        # 从当前冷却范围中取值
        min_time, max_time = self.cooldown_range
        
        # 根据组类型选择冷却时间
        if self.group_type in ["new", "fast"]:
            # 新查询组和高速查询组：取最小值（因为范围是相等的）
            current_cooldown = min_time
        else:
            # 旧查询组：从范围中随机取值
            current_cooldown = random.uniform(min_time, max_time)
        
        self.next_ready_time = time.time() + current_cooldown
        self.cooldown_task = asyncio.create_task(self._cooldown_timer(current_cooldown))
        
        # 打印详细信息
        if in_rate_limit:
            remaining = self.rate_limit_end_time - time.time()
            print(f"🚦 {self.group_id} 限流中，冷却: {current_cooldown:.3f}秒 (剩余{remaining:.0f}秒)")
        elif self.group_type in ["new", "fast"]:
            group_name = "新查询" if self.group_type == "new" else "高速查询"
            print(f"⏰ {self.group_id} ({group_name}) 开始冷却: {current_cooldown:.3f}秒")
        else:
            if min_time == max_time:
                print(f"⏰ {self.group_id} 在窗口内开始冷却: {current_cooldown:.3f}秒")
            else:
                print(f"⏰ {self.group_id} 在窗口内开始冷却: {current_cooldown:.3f}秒 (范围: {min_time:.3f} - {max_time:.3f}秒)")
    
    async def _cooldown_timer(self, cooldown_time: float):
        """冷却计时器"""
        try:
            await asyncio.sleep(cooldown_time)
            
            # 双重检查：确保仍在窗口内且运行中
            if self.running:
                if self.group_type == "old" and not self.in_time_window:
                    # 旧查询组不在窗口内，不通知调度器
                    print(f"⏰ {self.group_id} 冷却结束但不在窗口内，跳过查询")
                    return
                elif self.group_type in ["new", "fast"]:
                    # 新查询组和高速查询组总是可查询
                    pass  # 继续执行
                # 通知调度器
                scheduler = QueryCoordinator.get_global_scheduler()
                if scheduler:
                    await scheduler.notify_group_ready(self.group_id)
                else:
                    print(f"⚠️  {self.group_id} 无法获取全局调度器")
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ {self.group_id} 冷却计时器错误: {e}")
    
    async def on_ready_for_query(self, product_id: str = None, scheduled_time: float = None):
        """
        查询组就绪回调函数（由调度器调用）
        """
        if not self.running:
            return
        
        # 新查询组不受时间窗口限制
        if self.group_type in ["new", "fast"]:
            # 没有指定商品，表示这是就绪通知（等待调度器分配）
            if product_id is None:
                scheduler = QueryCoordinator.get_global_scheduler()
                if scheduler:
                    await scheduler.notify_group_ready(self.group_id)
                return
            
            # 执行查询
            await self._execute_query(product_id, scheduled_time)
            
            # 查询完成后重新开始冷却
            self._start_cooldown()
            return
        
        # 旧查询组：检查时间窗口
        if self.group_type == "old":
            if not self.in_time_window:
                print(f"⏰ {self.group_id} 已离开时间窗口，跳过查询")
                # 重新安排窗口开始
                self._calculate_window_times()
                if self.running and self.next_window_start > 0:
                    self.scheduled_start_task = asyncio.create_task(self._schedule_window_start())
                return
            
            # 没有指定商品，通知调度器就绪
            if product_id is None:
                scheduler = QueryCoordinator.get_global_scheduler()
                if scheduler:
                    await scheduler.notify_group_ready(self.group_id)
                return
            
            # 执行查询
            await self._execute_query(product_id, scheduled_time)
            
            # 查询完成后重新开始冷却（仍在窗口内）
            if self.in_time_window:
                self._start_cooldown()
    
    async def _execute_query(self, product_id: str, scheduled_time: float):
        """执行查询"""
        try:
            self.query_count += 1
            
            # 获取对应的商品和查询器
            product_item = None
            for item in self.product_items:
                if item.item_id == product_id:
                    product_item = item
                    break
            
            if not product_item:
                print(f"❌ {self.group_id} 找不到商品: {product_id}")
                return
            
            scanner = self.query_scanners.get(product_id)
            if not scanner:
                scanner = self.query_scanner_class(self.account_manager, product_item)
                self.query_scanners[product_id] = scanner
            
            # 执行查询
            print(f"🚀 {self.group_id} 查询商品: {product_item.item_name or product_id}")
            
            # 根据查询器类型调用不同的方法
            if self.group_type == "new":
                # 新查询组
                success, match_count, product_list, total_price_sum, total_wear_sum, error = \
                    await scanner.execute_query()
            elif self.group_type == "fast":
                # 高速查询组
                success, match_count, product_list, total_price_sum, total_wear_sum, error = \
                    await scanner.execute_query()
            else:
                # 旧查询组
                session = await self.account_manager.get_global_session()
                success, match_count, product_list, total_price_sum, total_wear_sum, error = \
                    await scanner.execute_query(session)
            
            # 处理查询结果
            if success and match_count > 0:
                self.found_count += match_count
                
                result_data = {
                    'group_id': self.group_id,
                    'group_type': self.group_type,
                    'account_id': self.account_manager.current_user_id,
                    'item_id': product_id,
                    'item_name': product_item.item_name or product_id,
                    'query_type': self.group_type,
                    'product_list': product_list,
                    'total_price': total_price_sum,
                    'total_wear_sum': total_wear_sum,
                    'product_url': product_item.url,
                    'query_time': scheduled_time if scheduled_time else time.time(),
                    'scheduled_delay': time.time() - scheduled_time if scheduled_time else 0,
                }
                
                if self.result_callback:
                    await self.result_callback(result_data)
            
            # 错误处理
            if error:
                if "HTTP 403" in error:
                    print(f"🚫 {self.group_id} 检测到403错误，{self.group_type}查询将被禁用")
                    self.running = False
                elif "HTTP 429" in error:
                    # 处理429限流
                    await self._handle_rate_limit()
                else:
                    print(f"⚠️  {self.group_id} 查询错误: {error}")
                    
        except Exception as e:
            print(f"❌ {self.group_id} 查询执行异常: {e}")
    
    async def _handle_rate_limit(self):
        """处理限流 - 累加式策略"""
        import time
        
        # 刷新限流结束时间（当前时间 + 10分钟）
        current_time = time.time()
        self.rate_limit_end_time = current_time + 600  # 10分钟后
        
        # 累加延迟（每次增加0.05秒）
        self.rate_limit_increment += 0.05
        
        # 计算新的冷却范围 = 原始范围 + 累计延迟
        original_min, original_max = self.original_cooldown_range
        self.cooldown_range = (
            original_min + self.rate_limit_increment,
            original_max + self.rate_limit_increment
        )
        
        print(f"⚠️  {self.group_id} 触发限流，延迟增加0.05秒")
        print(f"    累计延迟: {self.rate_limit_increment:.2f}秒")
        print(f"    新冷却范围: {self.cooldown_range[0]:.3f} - {self.cooldown_range[1]:.3f}秒")
        print(f"    限流状态将持续10分钟（直到 {time.strftime('%H:%M:%S', time.localtime(self.rate_limit_end_time))}）")
        
        # 启动或重置限流计时器
        await self._start_rate_limit_timer()
    
    async def _start_rate_limit_timer(self):
        """启动限流计时器，10分钟后恢复原始冷却时间"""
        # 取消已有的计时器（如果有）
        if self.rate_limit_timer and not self.rate_limit_timer.done():
            self.rate_limit_timer.cancel()
            try:
                await self.rate_limit_timer
            except asyncio.CancelledError:
                pass
        
        # 启动新的计时器
        self.rate_limit_timer = asyncio.create_task(self._rate_limit_timer_worker())
    
    async def _rate_limit_timer_worker(self):
        """限流计时器工作函数"""
        try:
            # 计算需要等待的时间
            wait_time = self.rate_limit_end_time - time.time()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # 限流时间到，恢复原始冷却范围
            self._reset_rate_limit()
            
        except asyncio.CancelledError:
            # 计时器被取消（可能是新的限流刷新了时间）
            pass
        except Exception as e:
            print(f"❌ {self.group_id} 限流计时器错误: {e}")
    
    def _reset_rate_limit(self):
        """重置限流状态，恢复原始冷却范围"""
        if self.rate_limit_increment > 0:
            # 恢复原始冷却范围
            self.cooldown_range = self.original_cooldown_range
            self.rate_limit_increment = 0.0
            self.rate_limit_end_time = 0
            
            print(f"🔄 {self.group_id} 限流状态已结束，恢复原始冷却范围: {self.cooldown_range}")
    
    def _check_time_window(self):
        """检查时间窗口状态 - 已弃用，使用in_time_window属性"""
        return self.in_time_window
    
    def get_stats(self):
        """获取统计信息"""
        stats = {
            'group_id': self.group_id,
            'group_type': self.group_type,
            'running': self.running,
            'cooldown_range': self.cooldown_range,
            'original_cooldown_range': self.original_cooldown_range,
            'query_count': self.query_count,
            'found_count': self.found_count,
            'product_count': len(self.product_items),
            'in_time_window': self.in_time_window,
            'scanner_count': len(self.query_scanners),
            'rate_limit_active': self.rate_limit_end_time > time.time(),
            'rate_limit_increment': self.rate_limit_increment,
        }
        
        # 时间窗口信息
        if self.time_config and self.time_config['enabled']:
            stats['time_window_enabled'] = True
            stats['window_start'] = f"{self.time_config['start_hour']:02d}:{self.time_config['start_minute']:02d}"
            stats['window_end'] = f"{self.time_config['end_hour']:02d}:{self.time_config['end_minute']:02d}"
            
            if not self.in_time_window and self.next_window_start > 0:
                import datetime
                next_start = datetime.datetime.fromtimestamp(self.next_window_start)
                stats['next_window_start'] = next_start.strftime("%Y-%m-%d %H:%M:%S")
        else:
            stats['time_window_enabled'] = False
        
        return stats

#账户专属购买工作者池
class AccountPurchaseWorkerPool:
    """
    账户专属购买工作者池 - 管理单个账户被RoundRobinScheduler分配任务后的购买任务分配和执行"""
    
    def __init__(self, account_manager, scheduler):
        self.account_manager = account_manager
        self.scheduler = scheduler
        self.task_queue = asyncio.Queue()
        self.workers = []
        self.running = False
        self.account_id = account_manager.current_user_id



    async def start(self, worker_count=3):
        """启动工作者池"""
        self.running = True
        for i in range(worker_count):
            worker_task = asyncio.create_task(
                self._worker_loop(i)
            )
            self.workers.append(worker_task)
        print(f"✅ 账户 {self.account_manager.current_account_name} 购买工作者池已启动 ({worker_count} workers)")
        
    async def stop(self):
        """停止工作者池"""
        self.running = False
        for worker in self.workers:
            worker.cancel()
        print(f"🛑 账户 {self.account_manager.current_account_name} 购买工作者池已停止")
        
    async def assign_task(self, batch_info):
        """调度器分配任务给这个账户"""
        await self.task_queue.put(batch_info)
        
    async def _worker_loop(self, worker_id):
        """工作者主循环"""
        print(f"  🛒 账户 {self.account_manager.current_account_name} Worker {worker_id} 已启动")
        
        while self.running:
            try:
                # 从专属队列获取任务
                batch_info = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=2.0
                )
                
                # 记录任务开始
                item_name = batch_info.get('item_name', '未知商品')
                item_count = len(batch_info.get('product_list', []))
                print(f"🔄 Worker {worker_id} 开始处理: {item_name} ({item_count}件)")
                
                # 执行购买（只关注购买本身）
                # 修改点：接收详细的购买结果
                purchase_result = await self._execute_purchase_only(batch_info, worker_id)
                success_count = purchase_result.get("success_count", 0)
                status = purchase_result.get("status", "unknown")
                
                # 记录任务结果 - 根据状态显示不同的日志
                if success_count > 0:
                    print(f"✅ Worker {worker_id} 购买成功: {success_count}/{item_count} 件")
                elif status == "payment_success_no_items":
                    print(f"🔄 Worker {worker_id} 支付成功但没买到商品 (0/{item_count})")
                elif status == "payment_failed":
                    print(f"❌ Worker {worker_id} 支付失败")
                elif status == "order_failed":
                    print(f"❌ Worker {worker_id} 订单创建失败")
                elif status == "no_inventory":
                    print(f"❌ Worker {worker_id} 无可用仓库")
                elif status == "exception":
                    print(f"❌ Worker {worker_id} 执行异常")
                else:
                    print(f"⚠️  Worker {worker_id} 其他失败")
                
                # 统一回调给调度器 - 保持接口不变，只传success_count
                await self.scheduler.on_purchase_completed(
                    account_id=self.account_manager.current_user_id,
                    success_count=success_count,
                    batch_info=batch_info
                )
                
                # 标记任务完成
                self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                # 超时继续等待（无任务时的正常等待）
                continue
                
            except asyncio.CancelledError:  
                # 任务被取消（停止时）
                print(f"🛑 Worker {worker_id} 收到取消信号")
                break
                
            except Exception as e:
                # 捕获所有其他异常
                print(f"❌ Worker {worker_id} 处理异常: {str(e)[:100]}")
                
                # 异常情况下也回调调度器（成功数量为0）
                try:
                    if 'batch_info' in locals():
                        await self.scheduler.on_purchase_completed(
                            account_id=self.account_manager.current_user_id,
                            success_count=0,
                            batch_info=batch_info
                        )
                        
                        # 如果从队列中取出了任务，需要标记完成
                        if not self.task_queue.empty():
                            try:
                                self.task_queue.task_done()
                            except ValueError:
                                # 可能已经被标记过了
                                pass
                                
                except Exception as callback_error:
                    print(f"❌ Worker {worker_id} 回调调度器失败: {callback_error}")
                    
                # 继续循环，不停止worker
                continue
                    
        print(f"  🛒 账户 {self.account_manager.current_account_name} Worker {worker_id} 已停止")    
    
    async def _execute_purchase_only(self, batch_info, worker_id):
        """执行购买"""
        try:
            # 使用账户专属的组件
            order_creator = OrderCreator(self.account_manager)
            payment_processor = PaymentProcessor(self.account_manager)
            
            # 获取当前仓库
            inventory_selector = self.account_manager.get_inventory_selector()
            if not inventory_selector:
                return {
                    "success_count": 0,
                    "status": "no_inventory"
                }
                
            selected_inventory = inventory_selector.get_current_inventory()
            if not selected_inventory:
                return {
                    "success_count": 0,
                    "status": "no_inventory"
                }
                
            steam_id = selected_inventory.get('steamId')
            
            # 创建订单
            order_success, order_id, order_error = await order_creator.create_order(
                item_id=batch_info['item_id'],
                total_price=batch_info['total_price'],
                steam_id=steam_id,
                product_list=batch_info['product_list'],
                product_url=batch_info['product_url']
            )
            
            if not order_success:
                print(f"❌ 账户 {self.account_manager.current_account_name} 创建订单失败: {order_error}")
                return {
                    "success_count": 0,
                    "status": "order_failed"
                }
                
            # 支付订单
            payment_success, success_count, payment_error = await payment_processor.process_payment(
                order_id=order_id,
                pay_amount=batch_info['total_price'],
                steam_id=steam_id,
                product_url=batch_info['product_url']
            )
            
            if payment_success:
                if success_count > 0:
                    # 支付成功且买到商品
                    return {
                        "success_count": success_count,
                        "status": "success"
                    }
                else:
                    # 支付成功但没买到商品
                    print(f"🔄 账户 {self.account_manager.current_account_name} 支付成功但没买到商品")
                    return {
                        "success_count": 0,
                        "status": "payment_success_no_items"
                    }
            else:
                # 支付失败
                print(f"❌ 账户 {self.account_manager.current_account_name} 支付失败: {payment_error}")
                return {
                    "success_count": 0,
                    "status": "payment_failed"
                }
                
        except Exception as e:
            print(f"❌ 购买执行异常: {e}")
            return {
                "success_count": 0,
                "status": "exception"
            }










# 购买任务调度管理器（接收并过滤查询器提交的商品批次，分配购买任务给账户，处理购买结果，更新账户仓库状态）
class RoundRobinScheduler:
    
    
    def __init__(self):
        self.account_pool = {}  # account_id -> AccountInfo
        self.purchase_pools = {}  # account_id -> AccountPurchaseWorkerPool
        self.task_queue = asyncio.Queue(maxsize=500)
        self.available_accounts = []  # 可用账户ID列表（轮询用）
        self.account_status = {}  # 账户状态
        self.current_index = 0  # 轮询指针
        self.running = False
        # 5秒缓存机制
        self.cache = {}  # wear_sum_str -> timestamp
        self.cache_duration = 5.0  # 5秒缓存

        self.cache_lock = asyncio.Lock()
        self.last_cache_cleanup = time.time()
        self.cache_cleanup_interval = 60.0  # 每30秒清理一次过期缓存
        self.has_task_event = asyncio.Event()  # 事件对象
        self.event_lock = asyncio.Lock()       # 事件锁
        self.processed_not_login_events = {}  
        self.event_ttl = 60.0  # 事件TTL，单位秒

    def register_account(self, account_manager):
        """注册账户到调度器 - 带库存检查（改进版）"""
        account_id = account_manager.current_user_id
        
        if not account_id:
            print("❌ 账户没有user_id，无法注册")
            return False
            
        if account_id in self.account_pool:
            print(f"⚠️  账户 {account_id} 已注册")
            return False
        
        account_name = account_manager.get_account_name()
        print(f"🔄 注册账户到调度器: {account_name} (ID: {account_id})")
        
        # 1. 检查账户是否有库存
        has_inventory = False
        inventory_selector = account_manager.get_inventory_selector()
        
        if inventory_selector:
            # 检查库存选择器是否有可用库存
            has_inventory = inventory_selector.has_available_inventory()
            
            # 如果无库存，打印详细信息
            if not has_inventory:
                print(f"📊 库存检查: 账户 {account_name} 无可用库存")
            else:
                print(f"📊 库存检查: 账户 {account_name} 有可用库存")
        else:
            print(f"❌ 账户 {account_name} 无库存选择器")
        
        # 2. 注册账户到池
        self.account_pool[account_id] = account_manager
        self.account_status[account_id] = {
            'available': has_inventory,  # 根据库存状态设置
            'disabled_reason': 'no_available_inventory' if not has_inventory else None,
            'total_purchased': 0
        }
        
        # 3. 只有有库存的账户才添加到可用列表
        if has_inventory:
            self.available_accounts.append(account_id)
            print(f"✅ 账户 {account_name} 已注册到调度器（状态: 可用）")
        else:
            print(f"✅ 账户 {account_name} 已注册到调度器（状态: 不可用-无库存）")
        
        # 4. 为账户创建购买工作者池
        purchase_pool = AccountPurchaseWorkerPool(account_manager, self)
        self.purchase_pools[account_id] = purchase_pool
        
        # 5. 设置库存回调
        self.setup_inventory_callbacks(account_manager)
        
        # 6. 显示当前统计
        stats = self.get_stats()
        print(f"📊 调度器状态: {stats['available_accounts']}/{stats['total_accounts']} 个账户可用")
        
        return True   
    async def start(self):
        """启动调度器"""
        self.running = True
        
        # 启动所有账户的购买工作者池
        for account_id, purchase_pool in self.purchase_pools.items():
            await purchase_pool.start(worker_count=3)
            
        # 启动调度循环
        asyncio.create_task(self._dispatch_loop())
        print(f"🚀 轮询调度器已启动，管理 {len(self.account_pool)} 个账户")
        
    async def stop(self):
        """停止调度器"""
        self.running = False
        
        # 停止所有购买工作者池
        for account_id, purchase_pool in self.purchase_pools.items():
            await purchase_pool.stop()
            
        # 清空缓存
        async with self.cache_lock:
            self.cache.clear()
            
        print("🛑 轮询调度器已停止")
        
    async def submit_batch(self, batch_info):
        """
        提交批次到调度器 - 带5秒缓存检查
        
        参数:
            batch_info: 批次数据，必须包含 'total_wear_sum' 字段
        
        返回: 
            True - 提交成功
            False - 被缓存跳过
        """
        if not batch_info:
            return False
            
        try:
            # 1. 提取总磨损和作为标识符
            total_wear_sum = batch_info.get('total_wear_sum')
            
            if total_wear_sum is None:
                # 无磨损信息，直接提交
                await self.task_queue.put(batch_info)
                
                # 立即触发事件，通知调度器有任务
                self.has_task_event.set()
                
                return True
            
            # 2. 转换为高精度字符串作为缓存键
            # 保留12位小数确保唯一性
            wear_key = f"{total_wear_sum:.12f}"
            
            async with self.cache_lock:
                current_time = time.time()
                
                # 3. 定期清理过期缓存
                if current_time - self.last_cache_cleanup > self.cache_cleanup_interval:
                    self._clean_expired_cache_sync(current_time)
                    self.last_cache_cleanup = current_time
                
                # 4. 检查缓存
                if wear_key in self.cache:
                    cache_time = self.cache[wear_key]
                    
                    # 检查是否在5秒缓存期内
                    if current_time - cache_time < self.cache_duration:
                        
                        return False
                    else:
                        # 缓存过期，更新缓存时间并提交
                        self.cache[wear_key] = current_time
                        
                        
                    
                else:
                    # 新标识符，添加到缓存
                    self.cache[wear_key] = current_time
                    
            
            # 5. 提交到任务队列
            await self.task_queue.put(batch_info)
            
            # 立即触发事件，通知调度器有任务需要处理
            self.has_task_event.set()
            
            return True
            
        except Exception as e:
            print(f"❌ 提交批次失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _clean_expired_cache_sync(self, current_time):
        """同步清理过期缓存"""
        expired_keys = []
        for wear_key, cache_time in self.cache.items():
            if current_time - cache_time >= self.cache_duration:
                expired_keys.append(wear_key)
        
        if expired_keys:
            for key in expired_keys:
                del self.cache[key]
            
    async def _dispatch_loop(self):
        """调度主循环 - 事件驱动版本"""
        print("⚡ 事件驱动调度器开始轮询分发任务...")
        
        while self.running:
            try:
                # 核心修改：等待事件而不是固定sleep
                
                # 方案1：有事件立即处理
                try:
                    # 等待事件（最多100ms防止饿死）
                    await asyncio.wait_for(
                        self.has_task_event.wait(),
                        timeout=0.1  # 100ms超时
                    )
                except asyncio.TimeoutError:
                    # 超时继续检查（防止事件丢失）
                    pass
                
                # 重置事件（准备接收下一个事件）
                if self.has_task_event.is_set():
                    self.has_task_event.clear()
                
                # 方案2：处理所有积压任务
                processed_count = 0
                while not self.task_queue.empty() and processed_count < 10:
                    try:
                        # 获取任务（非阻塞）
                        batch_info = self.task_queue.get_nowait()
                        if not batch_info:
                            self.task_queue.task_done()
                            continue
                        
                        # 轮询选择账户
                        account_id = await self._select_account_by_round_robin()
                        if not account_id:
                            # 没有可用账户，放回队列
                            await self.task_queue.put(batch_info)
                            self.task_queue.task_done()
                            await asyncio.sleep(0.01)
                            break
                        
                        # 分发给账户的购买工作者
                        purchase_pool = self.purchase_pools.get(account_id)
                        if purchase_pool:
                            # 立即分发
                            await purchase_pool.assign_task(batch_info)
                            
                            # 显示调度信息
                            item_name = batch_info.get('item_name', '未知商品')
                            item_count = len(batch_info.get('product_list', []))
                            total_wear = batch_info.get('total_wear_sum', 0)
                            account_name = self.account_pool[account_id].get_account_name()
                            print(f"⚡ 事件分发: {item_name} ({item_count}件, wear={total_wear:.6f}) → 账户 {account_name}")
                        else:
                            print(f"❌ 账户 {account_id} 没有购买工作者池")
                        
                        self.task_queue.task_done()
                        processed_count += 1
                        
                    except asyncio.QueueEmpty:
                        break
                    except Exception as e:
                        print(f"❌ 处理任务时出错: {e}")
                        self.task_queue.task_done()
                        continue
                
                # 如果没有处理任何任务，短暂暂停
                if processed_count == 0:
                    await asyncio.sleep(0.01)
                    
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"❌ 调度器错误: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.1)
                
        print("🛑 调度器已停止")
      
    async def _select_account_by_round_robin(self):
        """指针轮询选择账户"""
        if not self.available_accounts:
            return None
            
        # 从当前位置开始找下一个可用账户
        start_index = self.current_index
        checked_count = 0
        
        while checked_count < len(self.available_accounts):
            account_id = self.available_accounts[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.available_accounts)
            checked_count += 1
            
            # 检查账户是否可用
            if self.account_status[account_id]['available']:
                return account_id
                
        return None  # 没有可用账户
        
    async def on_purchase_completed(self, account_id, success_count, batch_info):
        """购买完成回调 - 由购买工作者调用"""
        if account_id not in self.account_pool:
            return
            
        # 更新统计
        self.account_status[account_id]['total_purchased'] += success_count
        
        if success_count > 0:
            # 通知库存选择器进行检查
            account_manager = self.account_pool[account_id]
            inventory_selector = account_manager.get_inventory_selector()
            
            if inventory_selector:
                # 异步触发库存检查
                asyncio.create_task(
                    self._trigger_inventory_check(account_id, inventory_selector, success_count)
                )
        else:
            # 购买失败，可以记录或处理
            pass
            
    async def _trigger_inventory_check(self, account_id, inventory_selector, purchased_count):
        """触发库存检查"""
        try:
            print(f"🔍 触发账户 {account_id} 的购买后库存检查...")
            has_inventory, message = await inventory_selector.check_after_purchase(purchased_count)
            
            if not has_inventory:
                print(f"⚠️  购买后检查: {message}")
            else:
                print(f"✅ 购买后检查: 账户仍有可用库存")
                
        except Exception as e:
            print(f"❌ 触发库存检查失败: {e}")
        
    async def _update_account_inventory(self, account_id, purchased_count):
        """更新账户仓库信息（调度器统一处理）"""
        account_manager = self.account_pool[account_id]
        inventory_selector = account_manager.get_inventory_selector()
        
        if inventory_selector:
            # 调用仓库选择器的更新方法
            inventory_selector.update_after_purchase(purchased_count)
            
            # 更新账户统计
            account_manager.stats['total_purchased'] += purchased_count
            
    async def _check_account_has_available_inventory(self, account_id):
        """检查账户是否有可用仓库"""
        account_manager = self.account_pool[account_id]
        inventory_selector = account_manager.get_inventory_selector()
        
        if not inventory_selector:
            return False
            
        return inventory_selector.has_available_inventory()
        
    def get_stats(self):
        """获取调度器统计"""
        total_accounts = len(self.account_pool)
        available_accounts = len(self.available_accounts)
        disabled_accounts = total_accounts - available_accounts
        
        total_purchased = 0
        for status in self.account_status.values():
            total_purchased += status.get('total_purchased', 0)
            
        # 缓存统计
        cache_size = len(self.cache)
        
        return {
            'total_accounts': total_accounts,
            'available_accounts': available_accounts,
            'disabled_accounts': disabled_accounts,
            'queue_size': self.task_queue.qsize(),
            'total_purchased': total_purchased,
            'cache_size': cache_size,  # 缓存大小
            'cache_duration': self.cache_duration
        }
        
    def display_cache_info(self):
        """显示缓存信息"""
        if not self.cache:
            print("🧹 缓存: 空")
            return
            
        current_time = time.time()
        active_count = 0
        expired_count = 0
        
        for wear_key, cache_time in self.cache.items():
            if current_time - cache_time < self.cache_duration:
                active_count += 1
            else:
                expired_count += 1
        
        print(f"📊 缓存统计:")
        print(f"   总条目数: {len(self.cache)}")
        print(f"   活跃条目: {active_count} (5秒内)")
        print(f"   过期条目: {expired_count}")
        print(f"   最近清理: {time.strftime('%H:%M:%S', time.localtime(self.last_cache_cleanup))}")
        
        # 显示前几个缓存条目
        if active_count > 0:
            print(f"   前3个活跃条目:")
            count = 0
            for wear_key, cache_time in self.cache.items():
                if current_time - cache_time < self.cache_duration:
                    age = current_time - cache_time
                    print(f"     - {wear_key[:15]}... (年龄: {age:.1f}秒)")
                    count += 1
                    if count >= 3:
                        break

    # 库存事件处理方法
    def setup_inventory_callbacks(self, account_manager):
        """
        为账户设置库存事件回调
        
        参数:
            account_manager: AccountInfo 对象
        """
        account_id = account_manager.current_user_id
        inventory_selector = account_manager.get_inventory_selector()
        
        if inventory_selector:
            # 设置回调函数
            inventory_selector.set_callbacks(
                on_no_inventory=self.handle_account_no_inventory,
                on_has_inventory=self.handle_account_has_inventory,
                on_not_login=self.handle_account_not_login
            )
            print(f"✅ 为账户 {account_manager.current_account_name} 设置库存回调")
    
    async def handle_account_no_inventory(self, account_id):
        """
        处理账户无可用库存事件
        
        参数:
            account_id: 账户ID
        """
        print(f"🔄 处理账户无库存事件: {account_id}")
        
        if account_id not in self.account_pool:
            print(f"ℹ️  账户 {account_id} 还未注册到调度器，忽略事件")
            return
        
        # 从可用列表中移除
        if account_id in self.available_accounts:
            self.available_accounts.remove(account_id)
            
            # 调整轮询指针
            if self.current_index >= len(self.available_accounts):
                self.current_index = 0
            
            print(f"🚫 从调度器移除账户: {self.account_pool[account_id].get_account_name()}")
        
        # 更新账户状态
        self.account_status[account_id]['available'] = False
        self.account_status[account_id]['disabled_reason'] = 'no_available_inventory'
        
        # 显示当前状态
        stats = self.get_stats()
        print(f"📊 调度器状态: 可用账户 {stats['available_accounts']}/{stats['total_accounts']}")
    
    async def handle_account_has_inventory(self, account_id):
        """
        处理账户有可用库存事件
        
        参数:
            account_id: 账户ID
        """
        print(f"🔄 处理账户有库存事件: {account_id}")
        
        if account_id not in self.account_pool:
            print(f"ℹ️  账户 {account_id} 还未注册到调度器，忽略事件")
            return
        
        # 检查是否已在可用列表中
        if account_id in self.available_accounts:
            print(f"ℹ️  账户已在可用列表中: {account_id}")
            return
        
        # 添加到可用列表末尾（公平调度）
        self.available_accounts.append(account_id)
        
        # 更新账户状态
        self.account_status[account_id]['available'] = True
        self.account_status[account_id]['disabled_reason'] = None
        
        print(f"✅ 恢复账户到调度器: {self.account_pool[account_id].get_account_name()}")
        
        # 显示当前状态
        stats = self.get_stats()
        print(f"📊 调度器状态: 可用账户 {stats['available_accounts']}/{stats['total_accounts']}")
    
    async def handle_account_not_login(self, account_id):
        """
        处理账户未登录事件
        
        参数:
            account_id: 账户ID
        """
        print(f"🔐 处理账户未登录事件: {account_id}")
        current_time = time.time()
        
        # 检查是否在60秒内已经处理过该账户的未登录事件
        if account_id in self.processed_not_login_events:
            last_time = self.processed_not_login_events[account_id]
            if current_time - last_time < self.event_ttl:
                print(f"⏭️  跳过重复的未登录事件: {account_id} (上次处理: {current_time-last_time:.1f}秒前)")
                return  # 直接返回，不处理重复事件
        
        # 记录本次事件处理时间
        self.processed_not_login_events[account_id] = current_time
        
        # 定期清理过期的事件记录（每5次处理清理一次）
        if len(self.processed_not_login_events) > 50:  # 简单限制大小
            self._clean_expired_not_login_events(current_time)

        if account_id not in self.account_pool:
            print(f"ℹ️  账户 {account_id} 还未注册到调度器，忽略事件")
            return
        
        account_name = self.account_pool[account_id].get_account_name()
        
        # 从可用列表中移除（与无库存事件相同的操作）
        if account_id in self.available_accounts:
            self.available_accounts.remove(account_id)
            
            # 调整轮询指针
            if self.current_index >= len(self.available_accounts):
                self.current_index = 0
            
            print(f"🚫 因未登录从调度器移除账户: {account_name}")
        else:
            print(f"ℹ️  账户 {account_name} 已不在可用列表中")
        
        # 更新账户状态
        self.account_status[account_id]['available'] = False
        self.account_status[account_id]['disabled_reason'] = 'not_login'  # 区别于无库存
        
        # 显示当前状态
        stats = self.get_stats()
        print(f"📊 调度器状态: 可用账户 {stats['available_accounts']}/{stats['total_accounts']}")
        print(f"⚠️  需要手动处理账户 {account_name} 的登录问题")
    
    def _clean_expired_not_login_events(self, current_time=None):
        """
        清理过期的未登录事件记录
        
        参数:
            current_time: 当前时间，默认为当前时间戳
        """
        if current_time is None:
            current_time = time.time()
        
        expired_accounts = []
        for account_id, event_time in self.processed_not_login_events.items():
            if current_time - event_time >= self.event_ttl:
                expired_accounts.append(account_id)
        
        if expired_accounts:
            for account_id in expired_accounts:
                del self.processed_not_login_events[account_id]
            print(f"🧹 清理了 {len(expired_accounts)} 个过期的未登录事件记录")

#多账号管理总控中心：
class MultiAccountCoordinator:
    """多账户全局管理中心（查询系统的入口和控制中心）"""
    
    def __init__(self):
        self.scheduler = RoundRobinScheduler()
        self.query_coordinators = {}  
        self.configs = {}  # 商品配置缓存
        self.account_pool = {}  # account_id -> account_manager
        self.account_status = {}  # 账户状态
        self.running = False
        
        print(f"✅ 多账户协调器初始化完成")
        print(f"   调度器类型: {type(self.scheduler).__name__}")
    
    def register_account(self, account_manager):
        """注册账户到购买调度器
        
        注意：如果账户的登录状态为 False，则不注册该账户，也不创建购买工作者池
        """
        try:
            account_id = account_manager.current_user_id
            
            if not account_id:
                print("❌ 账户没有user_id，无法注册")
                return False
            
            # 检查账户是否已注册
            if account_id in self.account_pool:
                print(f"⚠️  账户 {account_id} 已注册，跳过重复注册")
                return True
            
            # 检查账户登录状态 
            if not account_manager.login_status:
                print(f"⏭️  账户 {account_id} 登录状态为 False，跳过注册")
                return False
            
            account_name = account_manager.get_account_name()
            print(f"🔄 注册账户到购买调度器: {account_name} (ID: {account_id})")
            
            scheduler_success = self.scheduler.register_account(account_manager)
            if not scheduler_success:
                print(f"❌ 注册到购买调度器失败")
                return False
            
            self.account_pool[account_id] = account_manager
            
            if account_id in self.scheduler.account_status:
                scheduler_status = self.scheduler.account_status[account_id]
                self.account_status[account_id] = {
                    'available': scheduler_status.get('available', False),
                    'total_purchased': scheduler_status.get('total_purchased', 0),
                    'disabled_reason': scheduler_status.get('disabled_reason'),
                    # 协调器特有的字段
                    'registered_time': time.time(),
                    'name': account_name,
                    # 添加一个标记，表明这是协调器的状态副本
                    'is_sync_from_scheduler': True
                }
            else:
                # 如果调度器没有状态，创建基本状态
                self.account_status[account_id] = {
                    'available': True,
                    'total_purchased': 0,
                    'disabled_reason': None,
                    'registered_time': time.time(),
                    'name': account_name,
                    'is_sync_from_scheduler': False
                }
            
            print(f"✅ 账户注册成功: {account_name}")
            return True
            
        except Exception as e:
            print(f"❌ 注册账户失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def initialize_account(self, account_manager, config_name):
        """初始化单个账户并注册到调度器"""
        try:
            # 检查单个账户是否有效
            if not account_manager:
                print("❌ 账户管理器为空")
                return False
            
            # 获取账户ID
            account_id = account_manager.current_user_id
            
            if not account_id:
                print("❌ 账户没有user_id，无法注册")
                return False
            
            print(f"🔄 正在初始化账户: {account_manager.get_account_name()} (ID: {account_id})")
            
            # 检查是否已注册
            if account_id in self.account_pool:
                print(f"⚠️  账户 {account_id} 已注册，跳过重复注册")
                return True
            
            # 验证账户状态
            if not hasattr(account_manager, 'get_x_access_token'):
                print(f"❌ 账户管理器缺少必要方法")
                return False
            
            access_token = account_manager.get_x_access_token()
            if not access_token:
                print(f"❌ 账户缺少access_token")
                return False
            
            # 验证仓库选择器
            inventory_selector = account_manager.get_inventory_selector()
            if not inventory_selector:
                print(f"❌ 账户没有仓库选择器，正在创建...")
                account_manager.inventory_selector = SteamInventorySelector(account_manager)
                inventory_success, _ = await account_manager.inventory_selector.query_and_select_inventory()
                if not inventory_success:
                    print(f"⚠️  仓库选择器初始化失败，但继续注册")
            
            # 检查是否有可用仓库
            has_inventory = account_manager.has_available_inventory()
            if not has_inventory:
                print(f"⚠️  账户 {account_id} 当前无可用仓库")
            
            # 注册账户到协调器
            register_success = self.register_account(account_manager)
            if not register_success:
                print(f"❌ 账户注册失败")
                return False
            
            # 为该账户创建查询协调器（先创建空列表）
            self.query_coordinators[account_id] = []
            print(f"📋 查询协调器列表已初始化")
            
            # 添加商品配置
            if config_name not in self.configs:
                self.configs[config_name] = {
                    'products': [],
                    'created_at': time.time()
                }
            
            print(f"🎉 账户 {account_manager.get_account_name()} 初始化完成")
            print(f"   账户ID: {account_id}")
            print(f"   配置名称: {config_name}")
            print(f"   可用状态: {'✅ 可用' if has_inventory else '❌ 无库存'}")
            print(f"   注册时间: {time.strftime('%H:%M:%S')}")
            
            return True
            
        except Exception as e:
            print(f"❌ 初始化账户失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def add_products_to_account(self, account_manager, product_items, config_name):
        """
        为账户批量添加商品查询
        """
        account_id = account_manager.current_user_id
        if not account_id:
            print(f"❌ 账户没有user_id，无法添加商品")
            return False

        try:
            print(f"🔄 为账户 {account_id} 添加 {len(product_items)} 个商品...")
            
            # 检查是否已为该账户创建过协调器
            if account_id not in self.query_coordinators:
                self.query_coordinators[account_id] = []
            
            # 创建查询组管理器（一个账户对应一个QueryCoordinator）
            coordinator = QueryCoordinator(
                config_name, 
                product_items,  # 传递商品列表而不是单个商品
                account_manager
            )
                        # 设置回调到调度器
            coordinator.set_result_callback(self._on_query_result)
            
            # 启动查询组管理器
            success = await coordinator.start()
            if success:
                self.query_coordinators[account_id].append(coordinator)
                print(f"✅ 账户 {account_id} 已添加 {len(product_items)} 个商品")
                
                # 显示商品信息
                if product_items:
                    print(f"📦 商品列表:")
                    for i, product in enumerate(product_items[:5], 1):  # 只显示前5个
                        print(f"   {i}. {product.item_name or '未命名'} (ID: {product.item_id})")
                    if len(product_items) > 5:
                        print(f"   ... 还有 {len(product_items)-5} 个商品")
                
                # 更新配置缓存
                if config_name not in self.configs:
                    self.configs[config_name] = {
                        'products': [item.item_id for item in product_items],
                        'created_at': time.time()
                    }
                
                return True
            else:
                print(f"❌ 查询组管理器启动失败")
                return False
                
        except Exception as e:
            print(f"❌ 添加商品失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _on_query_result(self, result_data):
        """查询结果回调到任务池"""
        try:
            # 提交到任务分配器（带缓存检查）
            await self.scheduler.submit_batch(result_data)
            
            # 更新账户统计
            account_id = result_data.get('account_id')
            if account_id and account_id in self.account_status:
                match_count = len(result_data.get('product_list', []))
                if match_count > 0:
                    print(f"📊 账户 {account_id} 发现 {match_count} 个商品")
                    
        except Exception as e:
            print(f"❌ 提交查询结果失败: {e}")

    async def start_all(self):
        """启动所有组件"""
        try:
            print(f"🚀 正在启动多账户查询系统...")
            
            # 1. 启动购买调度器
            await self.scheduler.start()
            
            # 2. 启动所有购买工作者池
            print(f"👷 启动购买工作者池...")
            for account_id, purchase_pool in self.scheduler.purchase_pools.items():
                try:
                    await purchase_pool.start(worker_count=3)
                except Exception as e:
                    print(f"   ❌ 账户 {account_id} 购买工作者池启动失败: {e}")
            
            # 3. 启动所有查询调度器器
            print(f"🔍 启动查询协调器...")
            started_count = 0
            for account_id, coordinators in self.query_coordinators.items():
                for coordinator in coordinators:
                    try:
                        await coordinator.start()
                        started_count += 1
                    except Exception as e:
                        print(f"   ❌ 账户 {account_id} 查询协调器启动失败: {e}")
            
            self.running = True
            
            print(f"✅ 多账户协调器已启动")
            print(f"   管理账户: {len(self.account_pool)} 个")
            print(f"   查询协调器: {started_count} 个已启动")
            print(f"   购买工作者池: {len(self.scheduler.purchase_pools)} 个") 
            
            return True
            
        except Exception as e:
            print(f"❌ 启动多账户协调器失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def stop_all(self):
        """停止所有组件"""
        try:
            print(f"🛑 正在停止多账户协调器...")
            self.running = False
            
            # 1. 停止调度器
            await self.scheduler.stop()
            
            # 2. 停止所有查询协调器
            print(f"🔍 停止查询协调器...")
            stopped_count = 0
            for account_id, coordinators in self.query_coordinators.items():
                for coordinator in coordinators:
                    try:
                        await coordinator.stop()
                        stopped_count += 1
                    except Exception as e:
                        print(f"   ⚠️  停止账户 {account_id} 查询协调器失败: {e}")
            
            # 3. 停止所有购买工作者池
            print(f"👷 停止购买工作者池...")
            for account_id, purchase_pool in self.scheduler.purchase_pools.items():
                try:
                    await purchase_pool.stop()
                except Exception as e:
                    print(f"   ⚠️  停止账户 {account_id} 购买工作者池失败: {e}")
            
            # 4. 关闭所有账户的session
            print(f"🔌 关闭账户会话...")
            for account_id, account_manager in self.account_pool.items():
                try:
                    await account_manager.close_global_session()
                    await account_manager.close_api_session()
                except Exception as e:
                    print(f"   ⚠️  关闭账户 {account_id} 会话失败: {e}")
            
            print(f"✅ 多账户协调器已停止")
            print(f"   停止查询协调器: {stopped_count} 个")
            
            return True
            
        except Exception as e:
            print(f"❌ 停止多账户协调器失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_stats(self):
        """获取协调器统计信息"""
        # 基础统计
        stats = {
            'running': self.running,
            'total_accounts': len(self.account_pool),  # 协调器注册的账户总数
            'total_coordinators': sum(len(coordinators) for coordinators in self.query_coordinators.values()),
            'total_configs': len(self.configs),
        }
        
        # 从调度器获取统计信息
        if hasattr(self, 'scheduler') and self.scheduler:
            scheduler_stats = self.scheduler.get_stats()
            
            # 调度器管理的账户统计
            stats.update({
                'scheduler_total_accounts': scheduler_stats.get('total_accounts', 0),
                'available_accounts': scheduler_stats.get('available_accounts', 0),  # 可用账户数
                'disabled_accounts': scheduler_stats.get('disabled_accounts', 0),    # 禁用账户数
                'total_purchase_pools': len(self.scheduler.purchase_pools) if hasattr(self.scheduler, 'purchase_pools') else 0,
            })
            
            # 调度器其他统计
            stats.update({
                'scheduler_queue_size': scheduler_stats.get('queue_size', 0),
                'scheduler_total_purchased': scheduler_stats.get('total_purchased', 0),
                'scheduler_cache_size': scheduler_stats.get('cache_size', 0),
                'scheduler_cache_duration': scheduler_stats.get('cache_duration', 0),
            })
        else:
            # 如果没有调度器，设为0
            stats.update({
                'scheduler_total_accounts': 0,
                'available_accounts': 0,
                'disabled_accounts': 0,
                'total_purchase_pools': 0,
                'scheduler_queue_size': 0,
                'scheduler_total_purchased': 0,
                'scheduler_cache_size': 0,
                'scheduler_cache_duration': 0,
            })
        
        # 账户详情信息
        account_details = {}
        for account_id, account_manager in self.account_pool.items():
            # 从协调器获取状态
            coord_status = self.account_status.get(account_id, {})
            
            # 从调度器获取状态（如果可用）
            scheduler_status = {}
            if hasattr(self, 'scheduler') and self.scheduler:
                scheduler_status = self.scheduler.account_status.get(account_id, {})
            
            account_details[account_id] = {
                'name': account_manager.get_account_name(),
                'has_api_key': account_manager.has_api_key(),
                'has_inventory': account_manager.has_available_inventory(),
                'login_status': account_manager.login_status,
                # 协调器状态
                'coordinator_status': {
                    'registered_time': coord_status.get('registered_time'),
                    'name': coord_status.get('name'),
                },
                # 调度器状态
                'scheduler_status': {
                    'available': scheduler_status.get('available', False),
                    'disabled_reason': scheduler_status.get('disabled_reason'),
                    'total_purchased': scheduler_status.get('total_purchased', 0),
                },
                # 综合状态
                'combined_status': '可用' if scheduler_status.get('available', False) else '不可用',
                'status_reason': scheduler_status.get('disabled_reason') or '正常',
            }
        
        stats['account_details'] = account_details
        
        # 计算统计数据差异
        if hasattr(self, 'scheduler') and self.scheduler:
            stats['registration_diff'] = len(self.account_pool) - stats['scheduler_total_accounts']
            if stats['registration_diff'] != 0:
                stats['registration_warning'] = f"协调器和调度器账户数不一致，差异: {stats['registration_diff']}"
        
        return stats

    def display_status(self):
        """显示协调器状态"""
        stats = self.get_stats()
        
        print(f"\n🌐 多账户协调器状态:")
        print(f"   运行状态: {'✅ 运行中' if stats['running'] else '❌ 已停止'}")
        print(f"   注册账户: {stats['total_accounts']} 个")
        
        # 显示调度器统计
        if stats['scheduler_total_accounts'] > 0:
            print(f"   调度账户: {stats['scheduler_total_accounts']} 个")
            print(f"   可用账户: {stats['available_accounts']} 个")
            print(f"   禁用账户: {stats['disabled_accounts']} 个")
            
            # 显示差异警告
            if 'registration_diff' in stats and stats['registration_diff'] != 0:
                diff = stats['registration_diff']
                if diff > 0:
                    print(f"   ⚠️  警告: 有 {diff} 个账户注册到协调器但未注册到调度器")
                else:
                    print(f"   ⚠️  警告: 有 {-diff} 个账户注册到调度器但未注册到协调器")
        
        print(f"   查询协调器: {stats['total_coordinators']} 个")
        print(f"   购买工作者池: {stats['total_purchase_pools']} 个")
        print(f"   商品配置: {stats['total_configs']} 个")
        
        # 显示调度器详情
        if stats['scheduler_queue_size'] > 0 or stats['scheduler_total_purchased'] > 0:
            print(f"\n📦 购买调度器:")
            print(f"   任务队列: {stats['scheduler_queue_size']} 批次")
            print(f"   成功购买: {stats['scheduler_total_purchased']} 件")
            print(f"   缓存条目: {stats['scheduler_cache_size']} 个")
        
        # 显示账户列表
        if stats['account_details']:
            print(f"\n👥 账户列表:")
            for i, (account_id, details) in enumerate(stats['account_details'].items(), 1):
                name = details['name']
                api_status = '🔑' if details['has_api_key'] else '🖥️'
                inventory_status = '✅' if details['has_inventory'] else '❌'
                login_status = '✅' if details['login_status'] else '❌'
                scheduler_status = '✅' if details['scheduler_status']['available'] else '❌'
                purchased = details['scheduler_status']['total_purchased']
                reason = details['status_reason']
                
                status_symbol = scheduler_status
                status_text = f"调度:{status_symbol} 库存:{inventory_status} 登录:{login_status} 购买:{purchased}件"
                
                if reason != '正常':
                    status_text += f" ({reason})"
                
                print(f"   {i}. {name} {api_status} {status_text}")
    
# 数据库检查
def initialize_database():
    """初始化数据库"""
    
    if not db.check_database_exists(DB_FILE):
        print("📊 数据库不存在，正在创建...")
        if db.create_csgo_database(DB_FILE):
            print("✅ 数据库创建成功")
            return True
        else:
            print("❌ 数据库创建失败")
            return False
    else:
        return True

# 数据库保存函数 
def save_to_database(product_data, update_if_exists=True):
    """
    保存商品信息到SQLite数据库
    
    参数:
        product_data: 商品数据字典
        update_if_exists: 如果itemId已存在是否更新 (默认为True)
    
    返回: True/False
    """
    if not product_data:
        print("❌ 商品数据为空，无法保存到数据库")
        return False
    
    if 'itemId' not in product_data:
        print("❌ 商品数据缺少itemId字段")
        return False
    
    try:
        connection = db.get_connection(DB_FILE)
        if not connection:
            print("❌ 无法连接到数据库")
            return False
        
        cursor = connection.cursor()
        
        # 检查商品是否已存在
        check_sql = "SELECT COUNT(*) FROM items WHERE itemId = ?"
        cursor.execute(check_sql, (product_data['itemId'],))
        result = cursor.fetchone()
        count = result['COUNT(*)'] if isinstance(result, dict) else result[0]
        
        if count > 0:
            if not update_if_exists:
                print(f"ℹ️  商品 itemId={product_data['itemId']} 已存在于数据库，跳过保存")
                cursor.close()
                connection.close()
                return True
            
            # 执行更新操作
            print(f"🔄 商品 itemId={product_data['itemId']} 已存在，执行更新...")
            
            update_sql = """
            UPDATE items SET
                url = ?,
                itemSetName = ?,
                rarityName = ?,
                itemName = ?,
                marketHashName = ?,
                grade = ?,
                minPrice = ?,
                minwear = ?,
                maxwear = ?,
                lastModified = ?
            WHERE itemId = ?
            """
            
            values = (
                product_data['url'],
                product_data['itemSetName'] if product_data.get('itemSetName') else None,
                product_data['rarityName'] if product_data.get('rarityName') else None,
                product_data['itemName'],
                product_data['marketHashName'] if product_data.get('marketHashName') else None,
                product_data['grade'] if product_data.get('grade') else None,
                product_data.get('minPrice'),
                product_data['minwear'] if product_data.get('minwear') else None,
                product_data['maxwear'] if product_data.get('maxwear') else None,
                product_data['lastModified'] if product_data.get('lastModified') else None,
                product_data['itemId']
            )
            
            cursor.execute(update_sql, values)
            connection.commit()
            
            print(f"✅ 商品信息已更新 (itemId: {product_data['itemId']})")
            
        else:
            # 插入新记录
            insert_sql = """
            INSERT INTO items (
                url, itemSetName, rarityName, itemName, marketHashName, 
                itemId, grade, minPrice, minwear, maxwear, lastModified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            values = (
                product_data['url'],
                product_data['itemSetName'] if product_data.get('itemSetName') else None,
                product_data['rarityName'] if product_data.get('rarityName') else None,
                product_data['itemName'],
                product_data['marketHashName'] if product_data.get('marketHashName') else None,
                product_data['itemId'],
                product_data['grade'] if product_data.get('grade') else None,
                product_data.get('minPrice'),
                product_data['minwear'] if product_data.get('minwear') else None,
                product_data['maxwear'] if product_data.get('maxwear') else None,
                product_data['lastModified'] if product_data.get('lastModified') else None
            )
            
            cursor.execute(insert_sql, values)
            connection.commit()
            
            print(f"✅ 商品信息已保存到数据库 (itemId: {product_data['itemId']})")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 数据库查询函数
def query_item_from_database(item_id):
    """从数据库查询商品信息"""
    try:
        connection = db.get_connection(DB_FILE)
        if not connection:
            print("❌ 无法连接到数据库")
            return None
        
        cursor = connection.cursor()
        
        query_sql = """
        SELECT url, itemName, minwear, maxwear, minPrice , marketHashName
        FROM items 
        WHERE itemId = ?
        """
        
        cursor.execute(query_sql, (item_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            # 转换为字典
            if isinstance(result, dict):
                return dict(result)
            else:
                return {
                    'url': result[0],
                    'itemName': result[1],
                    'minwear': result[2],
                    'maxwear': result[3],
                    'minPrice': result[4],
                    'marketHashName': result[5]
                }
        else:
            return None
            
    except Exception as e:
        print(f"❌ 数据库查询失败: {e}")
        return None
#================================================================================
# 单个商品类（对特定的商品进行修改）
class ProductItem:
    """商品信息处理类"""
    
    def __init__(self, url=None, item_id=None, 
                 minwear=None, max_wear=None, max_price=None,  
                 item_name=None,market_hash_name=None, created_at=None, last_modified=None):
        self.url = url
        self.item_id = item_id
        self.minwear = minwear      
        self.max_wear = max_wear
        self.max_price = max_price
        self.item_name = item_name
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.market_hash_name = market_hash_name
        self.last_modified = last_modified

    def to_dict(self):
        """转换为字典"""
        return {
            "url": self.url,
            "item_id": self.item_id,
            "minwear": self.minwear,      
            "max_wear": self.max_wear,
            "max_price": self.max_price,
            "item_name": self.item_name,
            "created_at": self.created_at,
            "market_hash_name": self.market_hash_name,
            "last_modified": self.last_modified 
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建商品项目对象"""
        return cls(
            url=data.get("url"),
            item_id=data.get("item_id"),
            minwear=data.get("minwear"),  
            max_wear=data.get("max_wear"),
            max_price=data.get("max_price"),
            item_name=data.get("item_name"),
            created_at=data.get("created_at"),
            market_hash_name=data.get("market_hash_name"),
            last_modified=data.get("last_modified")
        )
    
    def display_info(self, index=None):
        """显示商品信息"""
        if index is not None:
            print(f"\n📦 商品 {index}:")
        else:
            print(f"\n📦 商品信息:")
        
        if self.item_name:
            print(f"   名称: {self.item_name}")
        print(f"   URL: {self.url[:80]}..." if self.url and len(self.url) > 80 else f"   URL: {self.url}")
        print(f"   ItemID: {self.item_id}")
        if self.minwear is not None and self.max_wear is not None:
            print(f"   磨损范围: {self.minwear:.2f} ~ {self.max_wear:.2f}")  # 改为显示范围
        elif self.max_wear is not None:
            print(f"   最大磨损: {self.max_wear}")
        if self.max_price is not None:
            print(f"   最大价格: {self.max_price}")
        if self.last_modified: 
            print(f"   最后更新: {self.last_modified}")
        print(f"   添加时间: {self.created_at}")

#商品配置详情处理类（处理配置内的商品）
class ProductConfig:
    
    def __init__(self, name=None, created_at=None, last_updated=None):
        self.name = name  # 配置名称（唯一）
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_updated = last_updated or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.products = []  # 商品项目列表
    
    def add_product(self, product_item):
        """添加商品项目"""
        self.products.append(product_item)
        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return True
    
    def remove_product(self, index):
        """移除指定索引的商品项目"""
        if 0 <= index < len(self.products):
            self.products.pop(index)
            self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True
        return False
    
    def update_product(self, index, **kwargs):
        """更新指定商品项目的参数"""
        if 0 <= index < len(self.products):
            product = self.products[index]
            for key, value in kwargs.items():
                if hasattr(product, key):
                    setattr(product, key, value)
            self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True
        return False
    
    def get_product(self, index):
        """获取指定商品项目"""
        if 0 <= index < len(self.products):
            return self.products[index]
        return None
    
    def get_all_products(self):
        """获取所有商品项目"""
        return self.products
    
    def has_product_with_item_id(self, item_id):
        """检查是否包含指定item_id的商品"""
        for product in self.products:
            if product.item_id == item_id:
                return True
        return False
    
    def to_dict(self):
        """转换为字典"""
        return {
            "name": self.name,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "products": [product.to_dict() for product in self.products]
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建配置对象"""
        config = cls(
            name=data.get("name"),
            created_at=data.get("created_at"),
            last_updated=data.get("last_updated")
        )
        
        # 添加商品项目
        for product_data in data.get("products", []):
            product = ProductItem.from_dict(product_data)
            config.products.append(product)
        
        return config
    
    def display_info(self):
        """显示配置信息"""
        print(f"\n📁 配置名称: {self.name}")
        print(f"📅 创建时间: {self.created_at}")
        print(f"📦 包含商品: {len(self.products)} 个")
        
        if self.products:
            print("\n商品列表:")
            for i, product in enumerate(self.products, 1):
                product.display_info(i)
        else:
            print("ℹ️  暂无商品")

#  商品配置管理器类 （管理总的商品的配置）
class ProductConfigManager:

    
    def __init__(self, config_file=PRODUCT_CONFIG_FILE):
        self.config_file = config_file
        self.configs = []  # 存储ProductConfig对象
        self.load_configs()
    
    def load_configs(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.configs = []
                for config_data in data.get("configs", []):
                    config = ProductConfig.from_dict(config_data)
                    self.configs.append(config)
                
                print(f"✅ 已加载 {len(self.configs)} 个商品配置")
                return True
            else:
                self.configs = []
                self.save_configs()
                print("ℹ️  配置文件不存在，已创建新文件")
                return True
                
        except Exception as e:
            print(f"❌ 加载配置失败: {e}")
            self.configs = []
            return False
  
  
    def save_configs(self):
        """保存所有配置到文件"""
        try:
            data = {
                "configs": [config.to_dict() for config in self.configs],

            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 已保存 {len(self.configs)} 个商品配置")
            return True
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
            return False
    
    def add_config(self, config):
        """添加新配置"""
        # 检查名称是否唯一
        if self.get_config_by_name(config.name):
            print(f"❌ 配置名称 '{config.name}' 已存在")
            return False
        
        self.configs.append(config)
        self.save_configs()
        return True
    
    def update_config(self, index, **kwargs):
        """更新指定索引的配置"""
        if 0 <= index < len(self.configs):
            config = self.configs[index]
            
            # 如果要更新名称，检查是否唯一
            if 'name' in kwargs and kwargs['name'] != config.name:
                if self.get_config_by_name(kwargs['name']):
                    print(f"❌ 配置名称 '{kwargs['name']}' 已存在")
                    return False
            
            # 更新字段
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # 更新最后修改时间
            config.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.save_configs()
            return True
        return False
    
    def delete_config(self, index):
        """删除指定配置"""
        if 0 <= index < len(self.configs):
            config = self.configs.pop(index)
            self.save_configs()
            return True, config.name
        return False, None
    
    def get_config(self, index):
        """获取指定配置"""
        if 0 <= index < len(self.configs):
            return self.configs[index]
        return None
    
    def get_config_by_name(self, name):
        """根据名称获取配置"""
        for config in self.configs:
            if config.name == name:
                return config
        return None
    
    def get_all_configs(self):
        """获取所有配置"""
        return self.configs
    
    def display_configs_list(self):
        """显示配置列表"""
        if not self.configs:
            print("ℹ️  暂无商品配置")
            return
        
        
        for i, config in enumerate(self.configs, 1):
            print(f"\n{i}. {config.name}")
            print(f"   创建时间: {config.created_at}")
            print(f"   最后更新: {config.last_updated}")
            print(f"   包含商品: {len(config.products)} 个")
            
            # 显示前3个商品
            if config.products:
                print(f"   商品列表:", end="")
                for j, product in enumerate(config.products[:3], 1):
                    if product.item_name:
                        print(f" {product.item_name}", end="")
                    else:
                        print(f" ItemID:{product.item_id}", end="")
                    if j < len(config.products[:3]):
                        print(",", end="")
                if len(config.products) > 3:
                    print(f" ...等{len(config.products)}个商品")
                else:
                    print()
        
        print(f"\n共 {len(self.configs)} 个配置")
        print("=" * 60)

# 商品磨损最低价格更新收集类 
class ProductDetailCollector:
    """商品磨损最低价格更新器"""
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.item_id = None
        self.product_url = None
        
    def set_item(self, item_id, product_url):
        """设置要查询的商品"""
        self.item_id = str(item_id)
        self.product_url = product_url
        return self
    
    def get_api_path(self):
        """获取API路径（用于生成x-sign）"""
        return f"support/trade/product/batch/v1/preview/{self.item_id}"
    
    def get_request_url(self):
        """获取完整请求URL"""
        api_path = self.get_api_path()
        return f"https://www.c5game.com/api/v1/{api_path}"
    
    def build_request_body(self):
        """构建请求体JSON"""
        return {"itemId": str(self.item_id)}
    
    def get_request_headers_exact(self, timestamp, x_sign):
        """
        构建精确的请求头 - 按照浏览器成功格式
        使用OrderedDict保持顺序
        """
        from collections import OrderedDict
        
        access_token = self.account_manager.get_x_access_token()
        device_id = self.account_manager.get_x_device_id()
        
        if not all([access_token, device_id, x_sign, self.product_url]):
            return None
        
        # 使用OrderedDict确保顺序与浏览器完全一致
        headers = OrderedDict()
        
        # 第1部分：标准HTTP头（完全复制浏览器顺序）
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = self.product_url
        headers["Content-Type"] = "application/json"
        headers["Connection"] = "keep-alive"
        headers["Cookie"] = self.account_manager.get_cookie_header_exact()
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"  
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = device_id
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = access_token
        headers["Priority"] = "u=4"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        
        return headers
    
    def extract_wear_range(self, wear_range_data):
        """从wearRange提取磨损范围"""
        if not wear_range_data or not isinstance(wear_range_data, list):
            return None, None
        
        if len(wear_range_data) == 0:
            return None, None
        
        # 第一个start作为minwear
        first_item = wear_range_data[0]
        minwear = first_item.get("start")
        
        # 最后一个end作为maxwear
        last_item = wear_range_data[-1]
        maxwear = last_item.get("end")
        
        return minwear, maxwear
    
    def process_response(self, response_data):
        """处理响应数据（只处理商品信息，不处理仓库）"""
        try:
            if isinstance(response_data, str):
                data = json.loads(response_data)
            else:
                data = response_data
            
            if not data.get("success", False):
                return None, f"请求失败: {data.get('errorMsg', '未知错误')}"
            
            response_data = data.get("data", {})
            
            # 提取磨损范围
            wear_range_data = response_data.get("wearRange", [])
            minwear, maxwear = self.extract_wear_range(wear_range_data)
            
            # 提取最低价格
            min_price = response_data.get("minPrice")
            
            # 提取商品信息
            product_info = {
                "minwear": minwear,
                "maxwear": maxwear,
                "minPrice": min_price,
                "wearRange": wear_range_data,  
                "sellCount": response_data.get("sellCount", 0),
                "itemName": response_data.get("itemName", ""),
                "itemId": response_data.get("itemId", ""),
                "wearAble": response_data.get("wearAble", 0)
            }
            
            return product_info, None
            
        except json.JSONDecodeError:
            return None, "响应不是有效的JSON格式"
        except Exception as e:
            return None, f"解析响应失败: {e}"
    
    
    async def fetch_product_detail(self):
        """
        获取商品详情 - 只获取价格和磨损信息
        返回: (product_info, error_message)
        """
        if not self.item_id or not self.product_url:
            return None, "缺少必要参数"
        
        # 构建请求体
        request_body = self.build_request_body()
        if not request_body:
            return None, "构建请求体失败"
        
        # 生成时间戳和x-sign
        access_token = self.account_manager.get_x_access_token()
        current_timestamp = str(int(time.time() * 1000))
        
        try:
            xsign_wrapper = GLOBAL_XSIGN_WRAPPER
            x_sign = xsign_wrapper.generate(
                path=self.get_api_path(),
                method="POST",
                timestamp=current_timestamp,
                token=access_token
            )
        except Exception as e:
            return None, f"x-sign生成失败: {e}"
        
        # 构建精确的请求头
        headers = self.get_request_headers_exact(current_timestamp, x_sign)
        if not headers:
            return None, "构建请求头失败"
        
        url = self.get_request_url()
        
        # 获取全局Session
        session = await self.account_manager.get_global_session()
        
        # 发送请求
        try:
            
            start_time = time.perf_counter()
            
            async with session.post(
                url=url,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"✅ 商品详情请求完成 - 耗时: {elapsed:.0f}ms")
                print(f"状态码: {status}")
                
                
                # 处理响应（只处理商品信息）
                product_info, error = self.process_response(text)
                
                if error:
                    return None, error
                
                return product_info, None
                
        except asyncio.TimeoutError:
            return None, "请求超时"
        except Exception as e:
            return None, f"请求失败: {e}"



    def debug_request_headers(self, timestamp, x_sign):
        """
        调试用：显示生成的请求头
        """
        headers = self.get_request_headers_exact(timestamp, x_sign)
        
        if not headers:
            print("❌ 无法生成请求头")
            return
        
        print("\n🔍 ProductDetailCollector请求头检查:")
        print("-" * 60)
        
        # 检查关键字段
        key_checks = {
            "Sec-Fetch-Mode": ("no-cors", "应该是 'no-cors'"),
            "Priority": ("u=4", "应该是 'u=4'"),
            "Cookie": (None, "应该存在"),
            "x-sign": (None, "应该存在"),
            "x-access-token": (None, "应该存在"),
            "Content-Type": ("application/json", "POST请求需要"),
        }
        
        for i, (key, value) in enumerate(headers.items()):
            check_mark = ""
            
            if key in key_checks:
                expected, desc = key_checks[key]
                if expected and value == expected:
                    check_mark = " ✅"
                elif not expected and value:
                    check_mark = " ✅"
                else:
                    check_mark = f" ❌ ({desc})"
            
            print(f"{i+1:2d}. {key:25s}: {value[:50]}{'...' if len(str(value)) > 50 else ''}{check_mark}")
        
        print("-" * 60)
        print(f"总计 {len(headers)} 个请求头")
        
        # 特别检查Cookie
        cookie_header = headers.get("Cookie", "")
        if cookie_header:
            print(f"\n🍪 Cookie分析:")
            print(f"   长度: {len(cookie_header)} 字符")
            print(f"   包含_csrf: {'_csrf' in cookie_header}")
            print(f"   包含cf_clearance: {'cf_clearance' in cookie_header}")
            print(f"   包含PHPSESSID: {'PHPSESSID' in cookie_header}")
            print(f"   包含NC5_accessToken: {'NC5_accessToken' in cookie_header}")
            
            # 检查_csrf编码
            import re
            csrf_match = re.search(r'_csrf=([^;]+)', cookie_header)
            if csrf_match:
                csrf_value = csrf_match.group(1)
                if '%' in csrf_value:
                    print(f"   ⚠️  _csrf是URL编码的: {csrf_value[:50]}...")
                else:
                    print(f"   ✅ _csrf已解码")   

#=================================================================================
# 仓库管理器类
class SteamInventorySelector:
    """仓库选择器 - 集成查询、选择、管理功能，完全硬编码仓库查询"""
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.available_inventories = []
        self.selected_inventory = None
        self.min_capacity_threshold = 50  # 最小剩余容量阈值
        
        # 事件回调
        self.on_no_inventory = None
        self.on_has_inventory = None
        self.on_not_login = None  # 未登录事件
        # 恢复定时器
        self.recovery_timers = {}  # account_id -> asyncio.Task
        
        # 账户ID
        self.account_id = None
        if account_manager and hasattr(account_manager, 'current_user_id'):
            self.account_id = f"account_{account_manager.current_user_id}"
    
    def set_callbacks(self, on_no_inventory, on_has_inventory, on_not_login=None):
        """
        设置事件回调函数
        
        参数:
            on_no_inventory: 账户无可用仓库时的回调函数
            on_has_inventory: 账户有可用仓库时的回调函数
        """
        self.on_no_inventory = on_no_inventory
        self.on_has_inventory = on_has_inventory
        self.on_not_login = on_not_login
        
    async def query_and_select_inventory(self):
        """
        查询并选定仓库 - 完全硬编码
        返回: (success, message)
        """
        print("🔍 查询仓库...")
        
        # 完全硬编码的参数
        item_id = "1380979899390267393"
        product_url = "https://www.c5game.com/csgo/1380979899390267393/P90%20%7C%20%E6%BB%A1%E6%98%8F%E4%BD%9C%E5%93%81%20(%E4%B9%85%E7%BB%8F%E6%B2%99%E5%9C%BA)/sell?sort=0"
        
        # 执行仓库查询
        success, steam_inventories, error = await self._query_inventory_details(
            item_id, product_url
        )
        
        if not success:
            print(f"❌ 查询仓库失败: {error}")
            if error and error.strip() == "Not login":  
                print(f"🔐 检测到账户未登录: {error}") 
                # 发布未登录事件（不启动恢复定时器）
                await self._publish_not_login() 
                return False, error
        
        if not steam_inventories:
            print("⚠️  未获取到仓库信息")
            # 发布无库存事件
            await self._publish_no_inventory()
            return False, "未获取到仓库信息"
        
        # 更新账户管理器的仓库信息
        self.account_manager.update_steam_inventories(steam_inventories)
        
        # 筛选可用仓库
        available_count = self._refresh_available_inventories(steam_inventories)
        
        if available_count == 0:
            print("⚠️  没有可用仓库")
            # 发布无库存事件
            await self._publish_no_inventory()
            return False, "没有可用仓库"
        
        # 选定最佳仓库（占用最少的）
        self.selected_inventory = self.available_inventories[0]
        
        print(f"✅ 仓库查询完成")
        print(f"   共 {len(steam_inventories)} 个仓库，{available_count} 个可用")

        self.display_current_status()
        
        return True, "仓库查询成功"
    
    async def _query_inventory_details(self, item_id, product_url):
        """
        内部方法：查询仓库详情
        返回: (success, steam_inventories, error_message)
        """
        # 设置要查询的商品
        self.item_id = str(item_id)
        self.product_url = product_url
        
        # 构建请求体
        request_body = self._build_request_body()
        if not request_body:
            return False, None, "构建请求体失败"
        
        # 生成时间戳和x-sign
        access_token = self.account_manager.get_x_access_token()
        current_timestamp = str(int(time.time() * 1000))
        
        try:
            xsign_wrapper = GLOBAL_XSIGN_WRAPPER
            x_sign = xsign_wrapper.generate(
                path=self._get_api_path(),
                method="POST",
                timestamp=current_timestamp,
                token=access_token
            )
        except Exception as e:
            return False, None, f"x-sign生成失败: {e}"
        
        # 构建精确的请求头
        headers = self._get_request_headers_exact(current_timestamp, x_sign)
        if not headers:
            return False, None, "构建请求头失败"
        
        url = self._get_request_url()
        
        # 获取全局Session
        session = await self.account_manager.get_global_session()
        
        # 发送请求
        try:
            start_time = time.perf_counter()
            
            async with session.post(
                url=url,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"✅ 仓库查询请求完成 - 耗时: {elapsed:.0f}ms")
                print(f"状态码: {status}")
                
                # 处理响应
                return self._process_inventory_response(text)
                
        except asyncio.TimeoutError:
            return False, None, "请求超时"
        except Exception as e:
            return False, None, f"请求失败: {e}"
    
    def _get_api_path(self):
        """获取API路径（用于生成x-sign）"""
        return f"support/trade/product/batch/v1/preview/{self.item_id}"
    
    def _get_request_url(self):
        """获取完整请求URL"""
        api_path = self._get_api_path()
        return f"https://www.c5game.com/api/v1/{api_path}"
    
    def _build_request_body(self):
        """构建请求体JSON"""
        return {"itemId": str(self.item_id)}
    
    def _get_request_headers_exact(self, timestamp, x_sign):
        """
        构建精确的请求头 - 按照浏览器成功格式
        """
        from collections import OrderedDict
        
        access_token = self.account_manager.get_x_access_token()
        device_id = self.account_manager.get_x_device_id()
        
        if not all([access_token, device_id, x_sign, self.product_url]):
            return None
        
        headers = OrderedDict()
        
        # 第1部分：标准HTTP头（完全复制浏览器顺序）
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = self.product_url
        headers["Content-Type"] = "application/json"
        headers["Connection"] = "keep-alive"
        headers["Cookie"] = self.account_manager.get_cookie_header_exact()
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"  
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = device_id
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = access_token
        headers["Priority"] = "u=4"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        
        return headers
    
    def _process_inventory_response(self, response_data):
        """处理仓库查询响应"""
        try:
            if isinstance(response_data, str):
                data = json.loads(response_data)
            else:
                data = response_data
            
            if not data.get("success", False):
                error_msg = data.get('errorMsg', '未知错误')
                
                
                if error_msg and error_msg.strip() == "Not login":  
                    return False, None, "Not login"  # 返回精确的"Not login" ← 添加这行
                
                return False, None, f"请求失败: {error_msg}"
            response_data = data.get("data", {})
            
            # 提取Steam仓库信息
            receive_steam_list = response_data.get("receiveSteamList", [])
            steam_inventories = self._extract_steam_inventories(receive_steam_list)
            
            return True, steam_inventories, None
            
        except json.JSONDecodeError:
            return False, None, "响应不是有效的JSON格式"
        except Exception as e:
            return False, None, f"解析响应失败: {e}"
    
    def _extract_steam_inventories(self, receive_steam_list):
        """提取Steam仓库信息"""
        if not receive_steam_list or not isinstance(receive_steam_list, list):
            return []
        
        inventories = []
        for steam_info in receive_steam_list:
            inventory = {
                "nickname": steam_info.get("nickname", ""),
                "steamId": steam_info.get("steamId", ""),
                "avatar": steam_info.get("avatar", ""),
                "inventory_num": steam_info.get("inventoryNum", 0),
                "inventory_max": steam_info.get("inventoryMaxNum", 1000),
                "status": steam_info.get("status", 0),
                "type": steam_info.get("type", 1)
            }
            inventories.append(inventory)
        
        return inventories
    
    def get_current_inventory(self):
        """获取当前选定的仓库"""
        return self.selected_inventory
    
    def get_current_steam_id(self):
        """获取当前选定仓库的Steam ID"""
        if self.selected_inventory:
            return self.selected_inventory.get('steamId')
        return None
    
    async def check_after_purchase(self, purchased_count):
        """
        购买后检查库存状态
        
        参数:
            purchased_count: 本次购买的数量
        
        返回:
            (has_inventory, message)
        """
        try:
            # 1. 更新库存计数
            success, message = self.update_after_purchase(purchased_count)
            if not success:
                return False, f"库存更新失败: {message}"
            
            # 2. 检查是否有可用库存
            has_inventory = self.has_available_inventory()
            
            # 3. 如果无可用库存，调用API确认
            if not has_inventory:
                print(f"⚠️ 账户 {self.account_id} 缓存显示无可用仓库，调用API确认...")
                await self._check_inventory_with_api()
            
            return has_inventory, "检查完成"
            
        except Exception as e:
            print(f"❌ 购买后库存检查失败: {e}")
            return False, f"检查失败: {e}"
    
    def update_after_purchase(self, purchased_count):
        """
        购买后更新仓库状态
        返回: (success, message)
        """
        if not self.selected_inventory:
            return False, "没有选定的仓库"
        
        # 获取当前数据
        steam_id = self.selected_inventory.get('steamId')
        current_num = self.selected_inventory.get('inventory_num', 0)
        inventory_max = self.selected_inventory.get('inventory_max', 1000)
        
        # 更新计数
        new_num = current_num + purchased_count
        self.selected_inventory['inventory_num'] = new_num
        
        # 计算剩余容量
        remaining = inventory_max - new_num
        
        # 更新账户管理器中的仓库信息（保持同步）
        self._sync_to_account_manager()
        
        # 如果剩余容量不足，重新选择
        if remaining < self.min_capacity_threshold:
            print(f"⚠️  仓库容量不足，重新选择...")
            
            # 从可用列表中移除当前仓库
            self.available_inventories = [
                inv for inv in self.available_inventories 
                if inv.get('steamId') != steam_id
            ]
            
            # 重新选择
            if self.available_inventories:
                self.selected_inventory = self.available_inventories[0]
                print(f"🔄 切换到新仓库: {self.selected_inventory['nickname']}")
                return True, f"已切换到新仓库: {self.selected_inventory['nickname']}"
            else:
                self.selected_inventory = None
                print("❌ 没有可用仓库了")
                
                # 立即检查并可能发布事件
                asyncio.create_task(self._handle_no_inventory_situation())
                
                return False, "没有可用仓库了"
        
        return True, "仓库更新成功"
    
    def _sync_to_account_manager(self):
        """将当前仓库状态同步到账户管理器"""
        all_inventories = self.account_manager.get_steam_inventories()
        
        if not self.selected_inventory:
            return
        
        steam_id = self.selected_inventory.get('steamId')
        
        # 更新账户管理器中的对应仓库
        for i, inv in enumerate(all_inventories):
            if inv.get('steamId') == steam_id:
                all_inventories[i] = self.selected_inventory.copy()
                break
        
        # 更新账户管理器
        self.account_manager.update_steam_inventories(all_inventories)
    
    def has_available_inventory(self):
        """检查是否有可用仓库"""
        if not self.available_inventories:
            self._refresh_available_inventories()
        
        return bool(self.available_inventories)
    
    def display_current_status(self):
        """显示当前仓库状态"""
        if self.selected_inventory:
            print(f"🏭 当前仓库: {self.selected_inventory['nickname']}")
            current = self.selected_inventory.get('inventory_num', 0)
            max_capacity = self.selected_inventory.get('inventory_max', 1000)
            remaining = max_capacity - current
            print(f"   占用: {current}/{max_capacity} (剩余: {remaining})")
            
            if remaining < self.min_capacity_threshold:
                print(f"⚠️  警告: 剩余容量不足{self.min_capacity_threshold}")
        else:
            print("⚠️  当前没有选定的仓库")
    
    def display_available_inventories(self):
        """显示可用仓库列表"""
        if not self.available_inventories:
            self._refresh_available_inventories()
        
        if not self.available_inventories:
            print("⚠️  没有可用仓库")
            return
        
        print("\n📊 可用仓库列表:")
        print("-" * 60)
        for i, inv in enumerate(self.available_inventories, 1):
            nickname = inv.get('nickname', '未知')
            steam_id = inv.get('steamId', '未知')
            current = inv.get('inventory_num', 0)
            max_capacity = inv.get('inventory_max', 1000)
            remaining = max_capacity - current
            
            selected = " ✅" if self.selected_inventory and inv['steamId'] == self.selected_inventory['steamId'] else ""
            
            print(f"{i}. {nickname}{selected}")
            print(f"   SteamID: {steam_id}")
            print(f"   占用: {current}/{max_capacity} (剩余: {remaining})")
            print()
    
    def _refresh_available_inventories(self, inventories=None):
        """
        刷新可用仓库列表
        返回: 可用仓库数量
        """
        if inventories is None:
            inventories = self.account_manager.get_steam_inventories()
        
        self.available_inventories = []
        
        for inv in inventories:
            inventory_num = inv.get('inventory_num', 0)
            inventory_max = inv.get('inventory_max', 1000)
            remaining = inventory_max - inventory_num
            
            # 排除条件：未启用(占用为0)或剩余容量不足
            if inventory_num > 0 and remaining >= self.min_capacity_threshold:
                inv['remaining_capacity'] = remaining
                self.available_inventories.append(inv)
        
        # 按占用率排序（占用少的优先）
        self.available_inventories.sort(key=lambda x: x['inventory_num'], reverse=True)
        
        return len(self.available_inventories)
    
    async def _check_inventory_with_api(self, is_recovery_check=False):
        """
        调用API检查库存状态
        
        参数:
            is_recovery_check: 是否为恢复定时器触发的检查
        
        返回:
            (api_success, has_inventory, error_message)
        """
        if not self.account_id:
            return False, False, "无账户ID"
        
        try:
            print(f"🔍 {'恢复检查' if is_recovery_check else 'API确认'}库存...")
            
            # 调用现有的仓库查询方法
            success, steam_inventories, error = await self._query_inventory_details(
                item_id="1380979899390267393",
                product_url="https://www.c5game.com/csgo/1380979899390267393/P90%20%7C%20%E6%BB%A1%E6%98%8F%E4%BD%9C%E5%93%81%20(%E4%B9%85%E7%BB%8F%E6%B2%99%E5%9C%BA)/sell?sort=0"
            )
            
            if not success:
                print(f"❌ API调用失败: {error}")
                return False, False, f"API调用失败: {error}"
            
            # 更新库存信息
            self.account_manager.update_steam_inventories(steam_inventories)
            
            # 刷新可用库存列表
            available_count = self._refresh_available_inventories(steam_inventories)
            has_inventory = available_count > 0
            
            if has_inventory:
                # 自动选择最佳仓库
                self.selected_inventory = self.available_inventories[0]
                print(f"✅ API检查: 账户有 {available_count} 个可用仓库")
            else:
                print(f"⚠️  API检查: 账户无可用仓库")
            
            return True, has_inventory, None
            
        except Exception as e:
            print(f"❌ 库存API检查异常: {e}")
            return False, False, f"检查异常: {e}"
    
    async def _publish_no_inventory(self):
        """发布账户无可用仓库事件"""
        if self.on_no_inventory and self.account_id:
            try:
                print(f"📢 发布事件: account_no_inventory for {self.account_id}")
                await self.on_no_inventory(self.account_id)
                
                # 启动恢复定时器
                await self._start_recovery_timer()
            except Exception as e:
                print(f"❌ 发布无库存事件失败: {e}")
    
    async def _publish_has_inventory(self):
        """发布账户有可用仓库事件"""
        if self.on_has_inventory and self.account_id:
            try:
                print(f"📢 发布事件: account_has_inventory for {self.account_id}")
                await self.on_has_inventory(self.account_id)
                
                # 取消恢复定时器
                self._cancel_recovery_timer()
            except Exception as e:
                print(f"❌ 发布有库存事件失败: {e}")
    
    async def _start_recovery_timer(self):
        """为当前账户启动30-40分钟恢复定时器"""
        if not self.account_id:
            return
        
        # 如果已有定时器，先取消
        self._cancel_recovery_timer()
        
        # 30-40分钟随机间隔
        delay_minutes = random.uniform(30, 40)
        delay_seconds = delay_minutes * 60
        
        print(f"⏰ 为账户 {self.account_id} 启动恢复定时器: {delay_minutes:.1f}分钟后检查")
        
        # 创建定时任务
        timer_task = asyncio.create_task(
            self._recovery_check_task(delay_seconds)
        )
        
        self.recovery_timers[self.account_id] = timer_task
    
    def _cancel_recovery_timer(self):
        """取消当前账户的恢复定时器"""
        if not self.account_id:
            return
        
        if self.account_id in self.recovery_timers:
            timer_task = self.recovery_timers[self.account_id]
            if not timer_task.done():
                timer_task.cancel()
                print(f"⏹️  取消账户 {self.account_id} 的恢复定时器")
            del self.recovery_timers[self.account_id]
    
    async def _recovery_check_task(self, delay_seconds):
        """恢复定时器任务"""
        try:
            # 等待随机延迟
            await asyncio.sleep(delay_seconds)
            
            print(f"🔄 恢复定时器触发，检查账户 {self.account_id} 的库存...")
            
            # 调用API检查库存
            api_success, has_inventory, error = await self._check_inventory_with_api(is_recovery_check=True)
            
            if api_success:
                if has_inventory:
                    # 有可用库存，发布恢复事件
                    await self._publish_has_inventory()
                else:
                    # 仍然无库存，重新启动定时器
                    print(f"⏳ 账户 {self.account_id} 仍无可用库存，重新启动定时器")
                    await self._start_recovery_timer()
            else:
                # API调用失败，重新启动定时器
                print(f"❌ 恢复检查API失败，重新启动定时器: {error}")
                await self._start_recovery_timer()
                
        except asyncio.CancelledError:
            print(f"⏹️  账户 {self.account_id} 的恢复定时器被取消")
        except Exception as e:
            print(f"❌ 恢复检查任务异常: {e}")
            # 异常时也重新启动定时器
            try:
                await self._start_recovery_timer()
            except:
                pass
    
    async def _handle_no_inventory_situation(self):
        """处理无库存情况"""
        # 检查是否真的无库存
        if not self.has_available_inventory():
            print(f"⚠️  账户 {self.account_id} 无可用仓库，调用API确认...")
            
            # 调用API确认
            api_success, has_inventory, error = await self._check_inventory_with_api()
            
            if api_success:
                if not has_inventory:
                    # API确认无库存，发布事件
                    await self._publish_no_inventory()
                else:
                    # API显示有库存，更新状态
                    print(f"✅ API显示有库存，已更新缓存")
            else:
                # API调用失败，信任缓存并发布事件
                print(f"⚠️  API调用失败，信任缓存: {error}")
                await self._publish_no_inventory()
                
    async def _publish_not_login(self):
        """发布账户未登录事件（无恢复定时器） ← 添加这个方法"""
        if self.on_not_login and self.account_id:
            try:
                print(f"📢 发布事件: account_not_login for {self.account_id}")
                await self.on_not_login(self.account_id)
                # 注意：这里不启动恢复定时器
            except Exception as e:
                print(f"❌ 发布未登录事件失败: {e}")



    async def cleanup(self):
        """清理资源"""
        for account_id, timer_task in list(self.recovery_timers.items()):
            if not timer_task.done():
                timer_task.cancel()
        self.recovery_timers.clear()

# 订单创建类 
class OrderCreator:
    """订单创建器（精确复制浏览器格式）"""
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
    
    def format_price(self, price):
        """格式化价格字符串（保持原有格式）"""
        try:
            return format(float(price), '.2f')
        except (ValueError, TypeError):
            return "0.00"
    
    def build_order_request_body(self, item_id, total_price, steam_id, product_list):
        """
        构建订单创建请求体
        
        参数:
        - item_id: 商品item_id
        - total_price: 总价
        - steam_id: Steam仓库ID
        - product_list: 商品列表，已经在查询阶段格式化好的订单数据
        """
        # 格式化总价
        formatted_total_price = self.format_price(total_price)
        
        # 使用预格式化的商品列表
        request_body = {
            "type": 4,  # 订单类型固定
            "productId": str(item_id),  # 主商品ID
            "price": formatted_total_price,  # 字符串格式的总价
            "delivery": 0,  # 发货方式固定
            "pageSource": "",  # 页面来源
            "receiveSteamId": str(steam_id),  # Steam仓库ID
            "productList": product_list,  # 直接使用预格式化的商品列表
            "actRebateAmount": 0  # 返利金额固定为0
        }
        
        return request_body
    
    def get_api_path(self):
        """获取API路径"""
        return "support/trade/order/buy/v2/create"
    
    def get_request_url(self):
        """获取完整请求URL"""
        return f"https://www.c5game.com/api/v1/{self.get_api_path()}"
    
    def get_request_headers_exact(self, timestamp, x_sign, referer_url):
        """
        精确复制浏览器订单创建的请求头格式和顺序
        """
        from collections import OrderedDict
        
        access_token = self.account_manager.get_x_access_token()
        device_id = self.account_manager.get_x_device_id()
        
        if not all([access_token, device_id, x_sign, referer_url]):
            return None
        
        # 使用OrderedDict保持精确顺序
        headers = OrderedDict()
        
        # 严格按照浏览器POST请求的顺序
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = referer_url
        headers["Content-Type"] = "application/json"
        headers["Connection"] = "keep-alive"
        
        # Cookie（保持原始顺序，不修改）
        cookie_header = self.account_manager.get_cookie_header_exact()
        headers["Cookie"] = cookie_header
        
        # Sec-Fetch系列
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"  # POST请求也是no-cors
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        
        # x-系列头
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = device_id
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = access_token
        
        # 缓存控制头（在最后）
        headers["Priority"] = "u=4"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        
        
        
        return headers
    
    async def create_order(self, item_id, total_price, steam_id, product_list, product_url):
        """
        创建订单 - 使用精确的浏览器格式
        
        参数:
        - item_id: 商品item_id
        - total_price: 总价
        - steam_id: Steam仓库ID
        - product_list: 商品列表（预格式化）
        - product_url: 商品页面URL（用于Referer）
        
        返回: (success, order_id, error_message)
        """
        
        print(f"🛒 创建订单")
        print(f"商品ID: {item_id}")
        print(f"商品数量: {len(product_list)} 件")
        print(f"目标仓库: {steam_id}")
        
        # 1. 构建请求体
        request_body = self.build_order_request_body(item_id, total_price, steam_id, product_list)
        
        # 2. 生成时间戳和x-sign
        access_token = self.account_manager.get_x_access_token()
        current_timestamp = str(int(time.time() * 1000))
        
        try:
            xsign_wrapper = GLOBAL_XSIGN_WRAPPER
            x_sign = xsign_wrapper.generate(
                path=self.get_api_path(),
                method="POST",
                timestamp=current_timestamp,
                token=access_token
            )
        except Exception as e:
            print(f"❌ 生成x-sign失败: {e}")
            return False, None, f"生成x-sign失败: {e}"
        
        # 3. 构建精确的请求头
        headers = self.get_request_headers_exact(current_timestamp, x_sign, product_url)
        if not headers:
            print("❌ 构建请求头失败")
            return False, None, "构建请求头失败"
        
        url = self.get_request_url()
        
        # 4. 发送请求 - 使用全局Session（只负责连接）
        try:
            # 获取全局Session（不复建连接）
            session = await self.account_manager.get_global_session()
            
            
            start_time = time.perf_counter()
            
            async with session.post(
                url=url,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"✅ 订单请求完成 - 耗时: {elapsed:.0f}ms")
                print(f"状态码: {status}")
                
                
                # 5. 解析响应
                success, order_id, error = self.parse_order_response(text)
                
                if success:
                    pass
                else:
                    print(f"❌ 订单创建失败: {error}")
                
                return success, order_id, error
                
        except asyncio.TimeoutError:
            error_msg = "订单创建请求超时"
            print(f"❌ {error_msg}")
            return False, None, error_msg
        except Exception as e:
            error_msg = f"订单创建请求失败: {e}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return False, None, error_msg
    
    def parse_order_response(self, response_text):
        """解析订单创建响应"""
        try:
            response_data = json.loads(response_text)
            
            if not response_data.get("success", False):
                error_msg = response_data.get("errorMsg", "未知错误")
                return False, None, f"创建订单失败: {error_msg}"
            
            # 提取订单号
            order_id = response_data.get("data")
            if not order_id:
                return False, None, "响应中没有订单号"
            
            return True, order_id, None
            
        except json.JSONDecodeError:
            return False, None, "响应不是有效的JSON格式"
        except Exception as e:
            return False, None, f"解析响应失败: {e}"
    
    def debug_request_info(self, item_id, total_price, steam_id, product_list):
        """调试请求信息"""
        print(f"\n🔍 订单调试信息:")
        print(f"  item_id: {item_id}")
        print(f"  total_price: {total_price}")
        print(f"  steam_id: {steam_id}")
        print(f"  product_list长度: {len(product_list)}")
        
        # 显示前几个商品
        for i, product in enumerate(product_list[:3], 1):
            print(f"  商品{i}: ID={product.get('productId')}, 价格={product.get('price')}")
        
        if len(product_list) > 3:
            print(f"  ... 还有{len(product_list)-3}个商品")

# 订单支付类 
class PaymentProcessor:
    """支付处理器"""
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
    
    def get_api_path(self):
        """获取API路径"""
        return "pay/order/v1/pay"
    
    def get_request_url(self):
        """获取完整请求URL"""
        return f"https://www.c5game.com/api/v1/{self.get_api_path()}"
    
    def build_payment_request_body(self, order_id, pay_amount, steam_id):
        """
        构建支付请求体
        
        参数:
        - order_id: 订单号
        - pay_amount: 支付金额
        - steam_id: Steam仓库ID
        """
        return {
            "bizOrderId": str(order_id),
            "orderType": 4,  # 硬编码
            "payAmount": format(float(pay_amount), '.2f'),  # 字符串格式
            "receiveSteamId": str(steam_id)
        }
    
    def get_request_headers_exact(self, timestamp, x_sign, referer_url):
        """
        构建精确的请求头 - 按照浏览器成功格式
        使用OrderedDict保持顺序
        """
        from collections import OrderedDict
        
        access_token = self.account_manager.get_x_access_token()
        device_id = self.account_manager.get_x_device_id()
        
        if not all([access_token, device_id, x_sign]):
            return None
        
        headers = OrderedDict()
        
        # 严格按照浏览器成功请求的顺序
        # 第1部分：标准HTTP头
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = referer_url
        headers["Content-Type"] = "application/json"
        headers["Connection"] = "keep-alive"
        
        # 第2部分：Cookie（在特定位置）
        headers["Cookie"] = self.account_manager.get_cookie_header_exact()
        
        # 第3部分：Sec-Fetch系列
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"  
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        
        # 第4部分：x-系列头
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = device_id
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = access_token
        
        # 第5部分：缓存控制头（在最后）
        headers["Priority"] = "u=4"  
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        
        return headers
    
    def get_request_headers(self, timestamp, x_sign, referer_url):
        """兼容旧版本的方法"""
        return self.get_request_headers_exact(timestamp, x_sign, referer_url)
    
    async def process_payment(self, order_id, pay_amount, steam_id, product_url):
        """处理支付 - 使用精确的请求头格式"""
        
        # 1. 构建请求体
        request_body = self.build_payment_request_body(order_id, pay_amount, steam_id)
        
        # 2. 生成时间戳和x-sign
        access_token = self.account_manager.get_x_access_token()
        current_timestamp = str(int(time.time() * 1000))
        
        try:
            xsign_wrapper = GLOBAL_XSIGN_WRAPPER
            x_sign = xsign_wrapper.generate(
                path=self.get_api_path(),
                method="POST",
                timestamp=current_timestamp,
                token=access_token
            )
        except Exception as e:
            return False, 0, f"生成x-sign失败: {e}"
        
        # 3. 构建精确的请求头
        headers = self.get_request_headers_exact(current_timestamp, x_sign, product_url)
        if not headers:
            return False, 0, "构建请求头失败"
        
        url = self.get_request_url()
        
        # 4. 发送请求 - 使用全局Session（只负责连接）
        try:
            # 获取全局Session（不复建连接）
            session = await self.account_manager.get_global_session()

            start_time = time.perf_counter()
            
            async with session.post(
                url=url,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"✅ 支付请求完成 - 耗时: {elapsed:.0f}ms")
                print(f"状态码: {status}")
                
                
                # 5. 解析响应
                return self.parse_payment_response(text)
                
        except asyncio.TimeoutError:
            return False, 0, "请求超时"
        except Exception as e:
            return False, 0, f"请求失败: {e}"
    
    def parse_payment_response(self, response_text):
        """解析支付响应"""
        try:
            response_data = json.loads(response_text)
            
            if not response_data.get("success", False):
                error_msg = response_data.get("errorMsg", "未知错误")
                return False, 0, f"支付失败: {error_msg}"
            
            # 提取成功数量
            success_count = response_data.get("data", {}).get("successCount", 0)
            
            return True, success_count, None
            
        except json.JSONDecodeError:
            return False, 0, "响应不是有效的JSON格式"
        except Exception as e:
            return False, 0, f"解析响应失败: {e}"
    
    async def process_payment_with_details(self, order_id, pay_amount, steam_id, product_url, order_details=None):
        """
        处理支付 - 带详细日志
        参数:
        - order_id: 订单号
        - pay_amount: 支付金额
        - steam_id: Steam仓库ID
        - product_url: 商品URL（用于Referer）
        - order_details: 可选，订单详情用于日志
        """
        print(f"\n{'='*50}")
        print(f"💰 支付处理开始")
        print(f"{'='*50}")
        
        if order_details:
            print(f"订单详情:")
            print(f"  商品: {order_details.get('product_name', '未知')}")
            print(f"  数量: {order_details.get('item_count', 0)} 件")
            print(f"  总价: {pay_amount}")
        else:
            print(f"支付信息:")
            print(f"  订单号: {order_id}")
            print(f"  支付金额: {pay_amount}")
            print(f"  Steam ID: {steam_id}")
        
        # 执行支付
        success, success_count, error = await self.process_payment(
            order_id, pay_amount, steam_id, product_url
        )
        
        if success:
            print(f"\n✅ 支付成功!")
            print(f"  成功支付数量: {success_count}")
            print(f"  订单号: {order_id}")
        else:
            print(f"\n❌ 支付失败: {error}")
        
        print(f"{'='*50}")
        
        return success, success_count, error

# 浏览器接口扫货查询类
class ProductQueryScanner:
    
    def __init__(self, account_manager, product_item):
        self.account_manager = account_manager
        self.product_item = product_item
        self.product_url = product_item.url
        self.item_id = product_item.item_id
        self.on_not_login = None
        self.disabled = False  # 查询是否被禁用
        self.disabled_reason = None  # 禁用原因
        self.disabled_time = None  # 禁用时间（用于去重）



    def set_not_login_callback(self, callback):
        """设置未登录事件回调"""
        self.on_not_login = callback

    async def _publish_not_login(self):
        """发布未登录事件"""
        if self.on_not_login:
            try:
                # 获取账户标识（与SteamInventorySelector保持一致）
                if self.account_manager and hasattr(self.account_manager, 'current_user_id'):
                    account_id = f"account_{self.account_manager.current_user_id}"
                    print(f"📢 发布事件: account_not_login for {account_id}")
                    await self.on_not_login(account_id)
            except Exception as e:
                print(f"❌ 发布未登录事件失败: {e}")


    async def execute_query(self, session):
        """使用传入的Session执行查询 - 用于循环查询"""
        if self.disabled:
            reason = self.disabled_reason or "未知原因"
            print(f"⛔ 查询被禁用: {reason}")
            return False, 0, [], 0, 0.0, f"查询被禁用: {reason}"
        # 1. 构建请求体
        request_body = self._build_request_body()
        if not request_body:
            return False, 0, [], 0, 0.0, "构建请求体失败"
        
        # 2. 生成时间戳和x-sign
        access_token = self.account_manager.get_x_access_token()
        current_timestamp = str(int(time.time() * 1000))
        
        try:
            xsign_wrapper = GLOBAL_XSIGN_WRAPPER
            x_sign = xsign_wrapper.generate(
                path=self._get_api_path(),
                method="POST",
                timestamp=current_timestamp,
                token=access_token
            )
        except Exception as e:
            print(f"❌ x-sign生成失败: {e}")
            return False, 0, [], 0, 0.0, f"x-sign生成失败: {e}"
        
        # 3. 构建精确的请求头
        headers = self._get_request_headers_exact(current_timestamp, x_sign)
        if not headers:
            return False, 0, [], 0, 0.0, "构建请求头失败"
        
        url = self._get_request_url()
        
        # 4. 发送查询请求
        try:
            
            start_time = time.perf_counter()
            
            async with session.post(
                url=url,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"查询完成 - 耗时: {elapsed:.0f}ms")
                print(f"状态码: {status}")
                
                if status == 403:
                    print(f"🚫 检测到HTTP 403 Forbidden")
                    self.disabled = True
                    self.disabled_reason = "HTTP 403 Forbidden"
                    return False, 0, [], 0, 0.0, "HTTP 403 Forbidden"
                # 5. 解析响应
                return await self._parse_response(text)
                
        except asyncio.TimeoutError:
            print("❌ 查询请求超时")
            return False, 0, [], 0, 0.0, "请求超时"
        except Exception as e:
            print(f"❌ 查询请求过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False, 0, [], 0, 0.0, f"请求错误: {e}"
    async def handle_account_not_login(self, account_id):
        """
        接收并处理Not login事件（与403相同处理方式）
        
        参数:
            account_id: 账户ID
        """
        # 验证账户ID（只处理当前账户的事件）
        if not self.account_manager or not hasattr(self.account_manager, 'current_user_id'):
            return
        
        current_account_id = f"account_{self.account_manager.current_user_id}"
        if current_account_id != account_id:
            # 不是当前账户的事件，忽略
            return
        current_time = time.time()
    
    # 如果已经在60秒内处理过，跳过
        if self.disabled and self.disabled_time:
            if current_time - self.disabled_time < 60.0:
                print(f"⏭️  ProductQueryScanner 已处理过未登录事件，跳过重复处理")
                return
        
        print(f"🔐 ProductQueryScanner 收到Not login事件，禁用查询")
        
        # 禁用查询（与403相同处理方式）
        self.disabled = True
        self.disabled_reason = "Not login"
        self.disabled_time = current_time  # 记录禁用时间



        print(f"🔐 ProductQueryScanner 收到Not login事件，禁用查询")
        
        # 禁用查询（与403相同）
        self.disabled = True
        self.disabled_reason = "Not login"

    def _get_api_path(self):
        """获取API路径（用于生成x-sign）"""
        return "support/trade/product/batch/v1/sell/query"
    
    def _get_request_url(self):
        """获取完整请求URL"""
        api_path = self._get_api_path()
        return f"https://www.c5game.com/api/v1/{api_path}"
    
    def _build_request_body(self):
        """构建请求体JSON"""
        if not all([self.item_id, self.product_item.minwear, 
                   self.product_item.max_wear, self.product_item.max_price]):
            print("❌ 查询参数不完整，无法构建请求体")
            return None
        
        # 构建请求体
        request_body = {
            "itemId": str(self.item_id),
            "maxPrice": str(self.product_item.max_price),  # 字符串格式
            "delivery": 0,
            "minWear": float(self.product_item.minwear),
            "maxWear": float(self.product_item.max_wear),
            "limit": "200",
            "giftBuy": ""
        }
        
        return request_body
    
    def _get_request_headers_exact(self, timestamp, x_sign):
        """
        构建精确的请求头 - 完全复制浏览器成功的格式
        使用OrderedDict保持顺序
        """
        from collections import OrderedDict
        
        access_token = self.account_manager.get_x_access_token()
        device_id = self.account_manager.get_x_device_id()
        
        if not all([access_token, device_id, x_sign, self.product_url]):
            return None
        
        headers = OrderedDict()

        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = self.product_url
        headers["Cookie"] = self.account_manager.get_cookie_header_exact()
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"  
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = device_id
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = access_token
        headers["Priority"] = "u=4" 
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        
        return headers
    
    async def _parse_response(self, response_data):
        """
        解析响应数据
        返回: (success, match_count, product_list, total_price_sum, total_wear_sum, error_message)
        """
        try:
            if isinstance(response_data, str):
                data = json.loads(response_data)
            else:
                data = response_data
            
            if not data.get("success", False):
                error_msg = data.get("errorMsg", "未知错误")
                return False, 0, [], 0, 0.0, f"请求失败: {error_msg}"
            
            # 提取matchCount
            match_count = data.get("data", {}).get("matchCount", 0)
            
            # 提取sellList中的商品信息，并直接格式化为订单所需格式
            sell_list = data.get("data", {}).get("sellList", [])
            product_list = []  # 直接存储格式化后的订单数据
            total_price_sum = 0.0
            total_wear_sum = 0.0  # 总磨损和缓存后作为去重依据
            
            for item in sell_list:
                item_id = item.get("id")
                price = item.get("price")
                
                # 提取磨损值
                wear = None
                asset_info = item.get("assetInfo", {})
                if asset_info:
                    wear_str = asset_info.get("wear")
                    if wear_str:
                        try:
                            wear = float(wear_str)
                            total_wear_sum += wear  # 累加总磨损和
                        except (ValueError, TypeError):
                            wear = None
                
                if item_id and price is not None:
                    try:
                        # 先将字符串转换为浮点数
                        price_float = float(price)
                        # 四舍五入到两位小数
                        formatted_price = round(price_float, 2)
                        
                        # 直接构建为订单需要的格式
                        product_list.append({
                            "productId": str(item_id),  # 字符串格式
                            "price": formatted_price,   # 浮点数（两位小数）
                            "actRebateAmount": 0        # 固定值
                        })
                        
                        total_price_sum += formatted_price
                        
                    except (ValueError, TypeError) as e:
                        print(f"⚠️  价格转换失败: {price}, 错误: {e}")
                        continue
            
            # 显示找到的商品详情
            if product_list:
                print(f"📋 找到 {len(product_list)} 个具体商品:")
                print(f"  总价: {total_price_sum:.2f}")
                print(f"  总磨损和: {total_wear_sum:.12f}")
            
            return True, match_count, product_list, total_price_sum, total_wear_sum, None
            
        except json.JSONDecodeError:
            if isinstance(response_data, str) and "Not login" in response_data:
                    current_time = time.time()
            should_publish = True
            
            # 检查是否已经处于禁用状态且时间较短
            if self.disabled and self.disabled_time:
                if current_time - self.disabled_time < 5.0:  # 5秒内刚处理过
                    print(f"⏭️  短时间内已处理过Not login，跳过重复发布")
                    should_publish = False
            
            if should_publish:
                # 禁用查询
                self.disabled = True
                self.disabled_reason = "Not login"
                self.disabled_time = current_time
                
                # 发布未登录事件
                await self._publish_not_login()
                    
                return False, 0, [], 0, 0.0, "响应不是有效的JSON格式"
        except Exception as e:
            return False, 0, [], 0, 0.0, f"解析响应失败: {e}"
        
    
# 官方api接口高速扫货查询类
class C5MarketAPIFastScanner:
    """C5Game OpenAPI 高速查询类 - 使用新列表接口，优化版本"""
    
    def __init__(self, account_manager, product_item):
        """
        初始化高速查询类
        
        Args:
            account_manager: 账户管理器
            product_item: ProductItem对象
        """
        self.account_manager = account_manager
        self.product_item = product_item
        self.product_url = product_item.url
        
        # 检查是否有market_hash_name
        if not hasattr(product_item, 'market_hash_name'):
            self.market_hash_name = None
            self.is_valid = False
            print(f"⚠️  OpenAPI高速查询器初始化失败: product_item缺少market_hash_name属性")
            return
        
        self.market_hash_name = product_item.market_hash_name
        
        if not self.market_hash_name:
            self.market_hash_name = None
            self.is_valid = False
            print(f"⚠️  OpenAPI高速查询器初始化失败: 商品market_hash_name为空")
            return
            
        self.is_valid = True
        
        # 从product_item获取筛选条件
        self.max_price = float(getattr(product_item, 'max_price', 0))
        self.min_wear = float(getattr(product_item, 'minwear', 0))
        self.max_wear = float(getattr(product_item, 'max_wear', 1))
        
        # API配置
        self.base_url = "https://openapi.c5game.com"
        self.app_key = None
        
        if account_manager and hasattr(account_manager, 'get_api_key'):
            self.app_key = account_manager.get_api_key()
        
        # 统计信息
        self.query_count = 0
        self.total_found = 0
        self.last_query_time = 0
        self.enabled = bool(self.app_key)  # 有API Key才启用
        
        if self.enabled:
            print(f"✅ OpenAPI高速查询器初始化完成")
            print(f"  商品: {self.market_hash_name}")
            print(f"  价格上限: {self.max_price if self.max_price > 0 else '无限制'}")
            print(f"  磨损范围: {self.min_wear:.4f} ~ {self.max_wear:.4f}")
            print(f"  状态: 已启用 (API Key可用)")
        else:
            print(f"⚠️  OpenAPI高速查询器初始化失败: 无API Key")
    
    def _build_request_url(self):
        """构建请求URL - 使用新接口端点"""
        return f"{self.base_url}/merchant/market/v2/products/list"
    
    def _build_request_params(self):
        """构建请求参数"""
        if not self.app_key:
            return {}
        return {"app-key": self.app_key}
    
    def _build_request_body(self, page_size=50):
        """构建请求体 - 根据新接口文档实现"""
        request_body = {
            "pageSize": min(page_size, 50),  # 新接口最大50
            "pageNum": 1,                    # 默认第一页
            "appId": 730,                    # CS:GO
            "marketHashName": self.market_hash_name,
            "delivery": 1,                   # 1-人工发货
            "assetType": 1                   # 1-普通商品
        }
        
        # 注意：新接口本身不支持价格和磨损筛选
        # 这些筛选将在客户端解析时进行
        
        return request_body
    
    def _build_request_headers(self):
        """构建请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def execute_query(self) -> Tuple[bool, int, List, float, float, Optional[str]]:
        """
        执行查询 - 返回格式与C5MarketAPIScanner完全相同
        
        返回: (success, match_count, product_list, total_price_sum, total_wear_sum, error_message)
        """
        # 检查是否启用
        if not self.enabled:
            return False, 0, [], 0.0, 0.0, "OpenAPI高速查询未启用 (无API Key)"
        
        # 检查有效性
        if not self.is_valid:
            return False, 0, [], 0.0, 0.0, "查询器无效 (缺少market_hash_name)"
        
        # 获取Session
        session = None
        try:
            if hasattr(self.account_manager, 'get_api_session'):
                session = await self.account_manager.get_api_session()
        except Exception as e:
            print(f"⚠️  获取API会话失败: {e}")
        
        # 如果获取失败，尝试强制创建新会话
        if session is None:
            try:
                if hasattr(self.account_manager, 'get_api_session'):
                    session = await self.account_manager.get_api_session(force_new=True)
            except Exception as e:
                print(f"⚠️  强制创建API会话失败: {e}")
        
        if session is None:
            return False, 0, [], 0.0, 0.0, "无法创建OpenAPI会话"
        
        # 检查会话是否关闭
        if hasattr(session, 'closed') and session.closed:
            try:
                session = await self.account_manager.get_api_session(force_new=True)
            except Exception as e:
                print(f"⚠️  重新创建已关闭会话失败: {e}")
                return False, 0, [], 0.0, 0.0, "OpenAPI会话已关闭且无法重新创建"
        
        # 构建请求参数
        url = self._build_request_url()
        params = self._build_request_params()
        request_body = self._build_request_body()
        headers = self._build_request_headers()
        
        self.query_count += 1
        self.last_query_time = time.time()
        
        try:
            print(f"🚀 OpenAPI高速查询开始")
            print(f"  商品: {self.market_hash_name}")
            print(f"  接口: /merchant/market/v2/products/list")
            print(f"  价格筛选: <= {self.max_price if self.max_price > 0 else '无限制'}")
            print(f"  磨损筛选: {self.min_wear:.4f} ~ {self.max_wear:.4f}")
            
            start_time = time.perf_counter()
            
            async with session.post(
                url=url,
                params=params,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"⚡ 高速查询完成: {elapsed:.0f}ms, 状态码: {status}")
                
                # 检查HTTP状态码
                if status == 429:
                    return False, 0, [], 0.0, 0.0, "HTTP 429 Too Many Requests"
                
                if status != 200:
                    error_msg = f"HTTP {status} 请求失败"
                    print(f"❌ HTTP错误: {error_msg}")
                    if status == 403:
                        error_msg += " (可能IP未加入白名单)"
                    return False, 0, [], 0.0, 0.0, error_msg
                
                # 调用优化后的解析响应方法
                success, match_count, product_list, total_price_sum, total_wear_sum, error = \
                    self._parse_response(text)
                
                if success:
                    if match_count > 0:
                        self.total_found += match_count
                        print(f"🎯 发现 {match_count} 个符合条件商品 (累计: {self.total_found})")
                        print(f"   总价格: {total_price_sum:.2f}, 总磨损: {total_wear_sum:.4f}")
                    else:
                        print(f"📭 未发现符合条件的商品")
                
                return success, match_count, product_list, total_price_sum, total_wear_sum, error
                    
        except asyncio.TimeoutError:
            error_msg = "请求超时 (8秒)"
            print(f"❌ OpenAPI高速查询超时")
            return False, 0, [], 0.0, 0.0, error_msg
        except aiohttp.ClientError as e:
            error_msg = f"网络错误: {e}"
            print(f"❌ OpenAPI高速查询网络错误: {e}")
            return False, 0, [], 0.0, 0.0, error_msg
        except Exception as e:
            error_msg = f"请求失败: {e}"
            print(f"❌ OpenAPI高速请求异常: {e}")
            return False, 0, [], 0.0, 0.0, error_msg
    
    def _parse_response(self, response_text: str) -> Tuple[bool, int, List, float, float, Optional[str]]:
        """
        解析响应数据 - 优化版本：使用快速处理函数
        
        返回: (success, match_count, product_list, total_price_sum, total_wear_sum, error_message)
        
        关键优化：
        1. 使用_quick_process_item快速处理每个商品
        2. 批量处理统计信息
        3. 减少中间变量和重复计算
        """
        try:
            # 解析JSON响应
            if isinstance(response_text, str):
                data = json.loads(response_text)
            else:
                data = response_text
            
            # 检查API是否成功
            if not data.get("success", False):
                error_msg = data.get("errorMsg", "未知错误")
                error_code = data.get("errorCode")
                if error_code:
                    error_msg = f"{error_msg} (代码: {error_code})"
                return False, 0, [], 0.0, 0.0, f"API请求失败: {error_msg}"
            
            # 获取分页数据
            page_data = data.get("data", {})
            item_list = page_data.get("list", [])
            has_more = page_data.get("hasMore", False)
            page_num = page_data.get("pageNum", 1)
            
            print(f"📄 解析响应: 第{page_num}页, 共{len(item_list)}个商品, 是否有更多: {has_more}")
            
            # 使用快速处理函数处理所有商品
            processed_results = []
            filtered_count = 0
            
            for item in item_list:
                result = self._quick_process_item(item)
                if result is None:
                    filtered_count += 1
                    continue
                processed_results.append(result)
            
            # 如果没有符合条件的商品
            if not processed_results:
                if filtered_count > 0:
                    print(f"  筛选掉 {filtered_count} 个不符合条件的商品")
                print(f"📭 未发现符合条件的商品")
                return True, 0, [], 0.0, 0.0, None
            
            # 批量处理统计信息
            product_list = []
            total_price_sum = 0.0
            total_wear_sum = 0.0
            
            for product_info, price, wear in processed_results:
                product_list.append(product_info)
                total_price_sum += price
                if wear is not None:
                    total_wear_sum += wear
            
            match_count = len(product_list)
            
            # 打印筛选统计
            if filtered_count > 0:
                print(f"  筛选掉 {filtered_count} 个不符合条件的商品")
            
            return True, match_count, product_list, total_price_sum, total_wear_sum, None
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            print(f"   响应文本: {response_text[:200]}...")
            return False, 0, [], 0.0, 0.0, "响应不是有效的JSON格式"
        except Exception as e:
            print(f"❌ 解析响应失败: {e}")
            return False, 0, [], 0.0, 0.0, f"解析响应失败: {e}"
    
    def _quick_process_item(self, item: dict) -> Optional[tuple]:
        """
        快速处理单个商品项 - 返回None或(product_info, price, wear)元组
        
        优化点：
        1. 一次性检查所有条件
        2. 减少重复字典访问
        3. 提前返回无效数据
        4. 减少类型转换次数
        
        返回: None 或 (product_info, price, wear)
        """
        # 1. 基本字段检查
        product_id = item.get("productId")
        price_str = item.get("price")
        
        # 没有ID或价格，立即返回
        if not product_id or price_str is None:
            return None
        
        # 2. 价格处理
        try:
            price = float(price_str)
            # 价格筛选
            if self.max_price > 0 and price > self.max_price:
                return None
        except (ValueError, TypeError):
            return None
        
        # 3. 磨损处理
        wear = None
        need_wear_check = self.min_wear > 0 or self.max_wear < 1
        
        # 获取磨损信息（减少字典访问次数）
        asset_info = item.get("assetInfo")
        if asset_info:
            wear_value = asset_info.get("floatWear")
            if wear_value is not None:
                try:
                    wear = float(wear_value)
                    # 磨损筛选
                    if need_wear_check and (wear < self.min_wear or wear > self.max_wear):
                        return None
                except (ValueError, TypeError):
                    # 磨损值转换失败
                    if need_wear_check:
                        return None  # 需要磨损但转换失败 → 剔除
                    # 不需要磨损检查，可以继续
        elif need_wear_check:
            # 需要磨损信息但没有 → 剔除
            return None
        
        # 4. 构建商品信息
        formatted_price = round(price, 2)
        
        product_info = {
            "productId": str(product_id),
            "price": formatted_price,
            "actRebateAmount": 0
        }
        
        
        
        # 返回元组：商品信息、价格、磨损值
        return (product_info, formatted_price, wear)
    
    def get_stats(self):
        """获取统计信息"""
        return {
            'enabled': self.enabled,
            'valid': self.is_valid,
            'query_count': self.query_count,
            'total_found': self.total_found,
            'market_hash_name': self.market_hash_name,
            'max_price': self.max_price,
            'min_wear': self.min_wear,
            'max_wear': self.max_wear,
            'last_query_time': self.last_query_time,
            'scanner_type': 'fast_api',  # 标记为高速查询类型
            'api_endpoint': '/merchant/market/v2/products/list'
        }
    
    async def cleanup(self):
        """
        清理资源
        """
        try:
            print(f"🧹 清理高速查询器资源")
            
            # 重置统计信息
            self.query_count = 0
            self.total_found = 0
            self.last_query_time = 0
            
            # 清理会话（如果需要）
            if self.account_manager and hasattr(self.account_manager, 'session'):
                try:
                    session = self.account_manager.session
                    if session and not session.closed:
                        # 不直接关闭，由账户管理器管理
                        pass
                except Exception as e:
                    print(f"⚠️  检查会话时出错: {e}")
            
            print(f"✅ OpenAPI高速查询器清理完成")
        except Exception as e:
            print(f"❌ 清理OpenAPI高速查询器时出错: {e}")






# 官方api接口扫货查询类
class C5MarketAPIScanner:
    """C5Game OpenAPI 商品查询类 - 优化版本，100%保持原始格式"""
    
    def __init__(self, account_manager, product_item):
        """
        初始化查询类
        
        Args:
            account_manager: 账户管理器
            product_item: ProductItem对象
        """
        self.account_manager = account_manager
        self.product_item = product_item
        self.product_url = product_item.url
        
        # 检查是否有market_hash_name
        if not hasattr(product_item, 'market_hash_name') or not product_item.market_hash_name:
            self.market_hash_name = None
            self.is_valid = False
            print(f"⚠️  OpenAPI查询器初始化失败: 商品缺少market_hash_name")
            return
            
        self.market_hash_name = product_item.market_hash_name
        self.is_valid = True
        
        # API配置
        self.base_url = "https://openapi.c5game.com"
        self.app_key = account_manager.get_api_key() if account_manager else None
      
        # 统计信息
        self.query_count = 0
        self.total_found = 0
        self.last_query_time = 0
        self.enabled = bool(self.app_key)  # 有API Key才启用
        
        if self.enabled:
            print(f"✅ OpenAPI查询器初始化完成")
            print(f"  商品: {self.market_hash_name}")
            print(f"  状态: 已启用 (有API Key)")
        else:
            print(f"⚠️  OpenAPI查询器初始化失败: 无API Key")
    

    def _build_request_url(self):
        """构建请求URL"""
        return f"{self.base_url}/merchant/market/v2/products/search"
    
    def _build_request_params(self):
        """构建请求参数"""
        return {"app-key": self.app_key}
    
    def _build_request_body(self,page_size=50):
        """构建请求体"""
        request_body = {
            "pageSize": page_size,
            "appId": 730,  
            "marketHashName": self.market_hash_name,
            "priceMax": float(self.product_item.max_price),   
            "wearMin": float(self.product_item.minwear),      
            "wearMax": float(self.product_item.max_wear)      
        }
        
        return request_body
    
    def _build_request_headers(self):
        """构建请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def execute_query(self) -> Tuple[bool, int, List, float, float, Optional[str]]:
        """
        执行查询 - 现在返回6元组
        
        返回: (success, match_count, product_list, total_price_sum, total_wear_sum, error_message)
        """
        # 检查是否启用
        if not self.enabled:
            return False, 0, [], 0.0, 0.0, "OpenAPI查询未启用 (无API Key)"
        
        # 检查有效性
        if not self.is_valid:
            return False, 0, [], 0.0, 0.0, "查询器无效 (缺少market_hash_name)"
        
        # 创建或检查Session
        session = await self.account_manager.get_api_session()
        if session is None:
            # 尝试强制创建新会话
            session = await self.account_manager.get_api_session(force_new=True)
            if session is None:
                return False, 0, [], 0.0, 0.0, "无法创建OpenAPI会话"
        
        # 检查会话是否关闭
        if hasattr(session, 'closed') and session.closed:
            # 尝试获取新会话
            session = await self.account_manager.get_api_session(force_new=True)
            if session is None:
                return False, 0, [], 0.0, 0.0, "OpenAPI会话已关闭且无法重新创建"
        
        # 构建请求参数
        url = self._build_request_url()
        params = self._build_request_params()
        request_body = self._build_request_body()
        headers = self._build_request_headers()
        
        self.query_count += 1
        
        try:
            print(f"🚀 OpenAPI查询开始")
            print(f"  商品: {self.market_hash_name}")
            print(f"  价格上限: {request_body.get('priceMax', '无限制')}")
            print(f"  磨损范围: {self.product_item.minwear:.2f} ~ {self.product_item.max_wear:.2f}")
            
            start_time = time.perf_counter()
            
            async with session.post(
                url=url,
                params=params,
                json=request_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"⚡ 查询完成: {elapsed:.0f}ms, 状态码: {status}")
                
                # 检查HTTP状态码
                if status == 429:
                    return False, 0, [], 0.0, 0.0, "HTTP 429 Too Many Requests"
                
                # 其他非200状态码
                if status != 200:
                    error_msg = f"HTTP {status} 请求失败"
                    print(f"❌ HTTP错误: {error_msg}")
                    return False, 0, [], 0.0, 0.0, error_msg
                
                # ⭐⭐ 修改：现在接收6个返回值
                success, match_count, product_list, total_price_sum, total_wear_sum, error = self._parse_response_fast(text)
                
                if success and match_count > 0:
                    self.total_found += match_count
                    print(f"🎯 发现 {match_count} 个商品 (累计: {self.total_found})")
                
                # ⭐⭐ 修改：返回6个值
                return success, match_count, product_list, total_price_sum, total_wear_sum, error
                    
        except asyncio.TimeoutError:
            error_msg = "请求超时"
            print(f"❌ OpenAPI查询超时")
            return False, 0, [], 0.0, 0.0, error_msg  # ⭐⭐ 修改：返回6个值
        except aiohttp.ClientError as e:
            error_msg = f"网络错误: {e}"
            print(f"❌ OpenAPI网络错误: {e}")
            return False, 0, [], 0.0, 0.0, error_msg  # ⭐⭐ 修改：返回6个值
        except Exception as e:
            error_msg = f"请求失败: {e}"
            print(f"❌ OpenAPI请求异常: {e}")
            return False, 0, [], 0.0, 0.0, error_msg  # ⭐⭐ 修改：返回6个值


    def _parse_response_fast(self, response_text: str) -> Tuple[bool, int, List, float, float, Optional[str]]:
        """
        解析响应数据 - 优化版本
        
        返回: (success, match_count, product_list, total_price_sum, total_wear_sum, error_message)
        
        优化点：
        1. 使用快速处理函数
        2. 批量处理统计信息
        3. 保持100%原始product_info格式
        """
        try:
            # 解析JSON响应
            if isinstance(response_text, str):
                data = json.loads(response_text)
            else:
                data = response_text
            
            # 检查API是否成功
            if not data.get("success", False):
                error_msg = data.get("errorMsg", "未知错误")
                error_code = data.get("errorCode")
                if error_code:
                    error_msg = f"{error_msg} (代码: {error_code})"
                return False, 0, [], 0.0, 0.0, f"API请求失败: {error_msg}"
            
            # 获取商品列表
            item_list = data.get("data", {}).get("list", [])
            
            print(f"📄 解析响应: 共{len(item_list)}个商品")
            
            # 使用快速处理函数
            processed_results = []
            
            for item in item_list:
                result = self._quick_process_item(item)
                if result is not None:
                    processed_results.append(result)
            
            # 批量处理统计信息
            if not processed_results:
                return True, 0, [], 0.0, 0.0, None
            
            product_list = []
            total_price_sum = 0.0
            total_wear_sum = 0.0
            
            for product_info, price, wear in processed_results:
                product_list.append(product_info)
                total_price_sum += price
                if wear is not None:
                    total_wear_sum += wear
            
            match_count = len(product_list)
            
            if product_list:
                print(f"✅ 找到 {len(product_list)} 个符合条件商品")
            
            return True, match_count, product_list, total_price_sum, total_wear_sum, None
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return False, 0, [], 0.0, 0.0, "响应不是有效的JSON格式"
        except Exception as e:
            print(f"❌ 解析响应失败: {e}")
            return False, 0, [], 0.0, 0.0, f"解析响应失败: {e}"
    
    def _quick_process_item(self, item: dict) -> Optional[tuple]:
        """
        快速处理单个商品项 - 100%保持原始格式
        
        返回: None 或 (product_info, price, wear)
        
        product_info 必须保持原始格式：
        {
            "productId": str,      # 字符串
            "price": float,        # 两位小数
            "actRebateAmount": 0   # 固定0，绝对不能改！
        }
        """
        # 一次性获取必要字段
        product_id = item.get("productId")
        price_str = item.get("price")
        
        # 快速检查必要字段
        if not product_id or price_str is None:
            return None
        
        # 价格处理
        try:
            price = float(price_str)
            formatted_price = round(price, 2)
        except (ValueError, TypeError):
            return None
        
        # 磨损处理（仅用于统计，不添加到product_info）
        wear = None
        asset_info = item.get("assetInfo")
        if asset_info:
            wear_value = asset_info.get("floatWear")
            if wear_value is not None:
                try:
                    wear = float(wear_value)
                except (ValueError, TypeError):
                    pass  # 磨损转换失败，但商品仍然有效
        
        # ⭐⭐⭐ 关键：保持100%原始格式！
        product_info = {
            "productId": str(product_id),
            "price": formatted_price,
            "actRebateAmount": 0  # 固定值，绝对不能改！
        }
        
        # ❌ 不添加任何额外字段！
        # ❌ 不修改字段名称！
        # ❌ 不修改字段值类型！
        
        return (product_info, formatted_price, wear)

    # 保留原始_parse_response方法，但调用优化版本
    def _parse_response(self, response_text: str) -> Tuple[bool, int, List, float, float, Optional[str]]:
        """
        原始解析方法 - 调用优化版本保持兼容
        """
        return self._parse_response_fast(response_text)

   
    def get_stats(self):
        """获取统计信息"""
        return {
            'enabled': self.enabled,
            'valid': self.is_valid,
            'query_count': self.query_count,
            'total_found': self.total_found,
            'market_hash_name': self.market_hash_name
        }
    
    async def cleanup(self):
        """
        清理资源 
        """
        try:
            print(f"🧹 清理OpenAPI扫描器资源")
            
            # 如果有关联的账户管理器，清理会话
            if self.account_manager and hasattr(self.account_manager, 'session'):
                try:
                    session = self.account_manager.session
                    if session and not session.closed:
                        await session.close()
                        print(f"✅ 已关闭账户管理器会话")
                except Exception as e:
                    print(f"⚠️  关闭账户管理器会话时出错: {e}")
            
            # 重置统计信息
            self.query_count = 0
            self.total_found = 0
            
            print(f"✅ OpenAPI扫描器清理完成")
        except Exception as e:
            print(f"❌ 清理OpenAPI扫描器时出错: {e}")



# 查询器创建处理器

class QueryCoordinator:
    """
    查询组管理器 
    负责创建和管理查询组，并将其与全局查询调度器关联
    """
    
    # 类级全局调度器
    _global_query_scheduler = None
    
    # 类级组注册表
    _query_groups = {}  # 组ID -> QueryGroup实例
    
    @classmethod
    def set_global_scheduler(cls, scheduler: QueryScheduler):
        """设置全局查询调度器"""
        cls._global_query_scheduler = scheduler
        print(f"✅ 已设置全局查询调度器")
    
    @classmethod
    def get_global_scheduler(cls) -> Optional[QueryScheduler]:
        """获取全局查询调度器"""
        return cls._global_query_scheduler
    
    @classmethod
    async def start_global_scheduler(cls):
        """启动全局调度器"""
        if cls._global_query_scheduler:
            await cls._global_query_scheduler.start()
    
    @classmethod
    async def stop_global_scheduler(cls):
        """停止全局调度器"""
        if cls._global_query_scheduler:
            await cls._global_query_scheduler.stop()
    
    @classmethod
    def get_all_groups(cls):
        """获取所有查询组"""
        return cls._query_groups
    
    def __init__(self, config_name: str, product_items, account_manager):
        """
        初始化查询协调器（现在改为查询组管理器）
        
        参数:
        - config_name: 配置名称
        - product_items: ProductItem对象列表（一个账户的所有商品）
        - account_manager: 账户管理器
        """
        self.config_name = config_name
        self.product_items = product_items  # 改为复数，一个账户的所有商品
        self.account_manager = account_manager
        
        # 查询组
        self.new_query_group = None  # 新查询组
        self.old_query_group = None  # 旧查询组
        self.fast_query_group = None  # 高速查询组

        # 状态
        self.running = False
        self.account_id = account_manager.current_user_id
        
        # 结果回调函数
        self.on_query_result_callback = None
        
        print(f"🔄 [查询组管理器] 初始化: 账户 {self.account_id}")
        print(f"   商品数量: {len(product_items)}")
    
    def set_result_callback(self, callback):
        """设置查询结果回调函数"""
        self.on_query_result_callback = callback
        print(f"✅ 设置结果回调: 账户 {self.account_id}")
    
    async def initialize(self):
        """初始化查询组"""
        print(f"🔄 [查询组管理器] 创建查询组: 账户 {self.account_id}")
        
        # 获取时间配置
        time_config = self.account_manager.get_query_time_config()
        # ✅ 获取登录状态
        login_status = getattr(self.account_manager, 'login_status', True)

        # 创建新查询组（如果有API Key）- 新查询不受时间窗口限制
        if (self.account_manager.has_api_key() and 
            any(hasattr(item, 'market_hash_name') and item.market_hash_name 
                for item in self.product_items)):
            
            self.new_query_group = QueryGroup(
                group_id=f"N_{self.account_id}",
                group_type="new",
                account_manager=self.account_manager,
                product_items=self.product_items,
                query_scanner_class=C5MarketAPIScanner,
                result_callback=self._on_group_query_result
            )
            print(f"🔑 [查询组管理器] 创建新查询组: N_{self.account_id}")
            self.fast_query_group = QueryGroup(
                group_id=f"F_{self.account_id}",
                group_type="fast",
                account_manager=self.account_manager,
                product_items=self.product_items,
                query_scanner_class=C5MarketAPIFastScanner,
                result_callback=self._on_group_query_result
          )
            print(f"⚡ [查询组管理器] 创建高速查询组: F_{self.account_id}")
        else:
            print(f"⚠️  账户 {self.account_id} 无API Key，跳过新查询组和高速查询组创建")


        if login_status:  # ✅ 只有已登录账户才创建旧查询组
            if time_config and time_config['enabled']:
                # 启用时间窗口：创建旧查询组
                self.old_query_group = QueryGroup(
                    group_id=f"O_{self.account_id}",
                    group_type="old",
                    account_manager=self.account_manager,
                    product_items=self.product_items,
                    query_scanner_class=ProductQueryScanner,
                    result_callback=self._on_group_query_result
                )
                print(f"🔍 [查询组管理器] 创建旧查询组: O_{self.account_id}")
            else:
                # 未启用时间窗口：不创建旧查询组
                print(f"⏰ 账户 {self.account_id} 未启用时间窗口，跳过旧查询组创建")
                self.old_query_group = None
        else:
            # ✅ 未登录账户不创建旧查询组
            print(f"🔒 账户 {self.account_id} 状态为未登录，跳过旧查询组创建")
            self.old_query_group = None
            # 注册到全局管理器
            
        if self.new_query_group:
            self._query_groups[self.new_query_group.group_id] = self.new_query_group
        if self.old_query_group:
            self._query_groups[self.old_query_group.group_id] = self.old_query_group
        if self.fast_query_group:
            self._query_groups[self.fast_query_group.group_id] = self.fast_query_group
        return True
    
    async def _on_group_query_result(self, result_data):
        """处理查询组的查询结果"""
        if self.on_query_result_callback:
            await self.on_query_result_callback(result_data)
    
    async def start(self):
        """启动查询组"""
        if self.running:
            return False
        
        # 初始化查询组
        if not await self.initialize():
            return False
        
        self.running = True
        
        # 注册到全局调度器
        scheduler = self.get_global_scheduler()
        if not scheduler:
            print(f"❌ 全局调度器未设置")
            return False
        
        # 注册新查询组（不受时间窗口限制）
        if self.new_query_group:
            scheduler.register_group(
                group_id=self.new_query_group.group_id,
                group_type="new",
                on_ready_callback=self.new_query_group.on_ready_for_query
            )
            # 立即启动（新查询不受时间窗口限制）
            await self.new_query_group.start()
        if self.fast_query_group:
            scheduler.register_group(
                group_id=self.fast_query_group.group_id,
                group_type="fast",
                on_ready_callback=self.fast_query_group.on_ready_for_query
            )
            # 立即启动（高速查询不受时间窗口限制）
            await self.fast_query_group.start()
        # 注册旧查询组（受时间窗口控制）
        if self.old_query_group:
            scheduler.register_group(
                group_id=self.old_query_group.group_id,
                group_type="old",
                on_ready_callback=self.old_query_group.on_ready_for_query
            )
            # 让QueryGroup自己管理时间窗口启动
            await self.old_query_group.start()
        
        print(f"✅ [查询组管理器] 已启动: 账户 {self.account_id}")
        return True
    
    async def stop(self):
        """停止查询组"""
        if not self.running:
            return
        
        print(f"🛑 [查询组管理器] 正在停止: 账户 {self.account_id}")
        self.running = False
        
        # 停止新查询组
        if self.new_query_group:
            await self.new_query_group.stop()
            # 从全局管理器移除
            if self.new_query_group.group_id in self._query_groups:
                del self._query_groups[self.new_query_group.group_id]
        # 停止高速查询组
        if self.fast_query_group:
            await self.fast_query_group.stop()
            # 从全局管理器移除
            if self.fast_query_group.group_id in self._query_groups:
                del self._query_groups[self.fast_query_group.group_id]
        if self.old_query_group:
            await self.old_query_group.stop()
            # 从全局管理器移除
            if self.old_query_group.group_id in self._query_groups:
                del self._query_groups[self.old_query_group.group_id]
        
        print(f"✅ [查询组管理器] 已停止: 账户 {self.account_id}")
    
    def get_stats(self):
        """获取统计信息"""
        stats = {
            'account_id': self.account_id,
            'config_name': self.config_name,
            'running': self.running,
            'product_count': len(self.product_items),
            'has_new_group': self.new_query_group is not None,
            'has_fast_group': self.fast_query_group is not None,  
            'has_old_group': self.old_query_group is not None,
        }
        
        if self.new_query_group:
            stats.update({
                'new_group_stats': self.new_query_group.get_stats(),
                'new_group_id': self.new_query_group.group_id,
            })
        
        if self.old_query_group:
            stats.update({
                'old_group_stats': self.old_query_group.get_stats(),
                'old_group_id': self.old_query_group.group_id,
            })
        if self.fast_query_group:
            stats.update({
                'fast_group_stats': self.fast_query_group.get_stats(),
                'fast_group_id': self.fast_query_group.group_id,
            })
        return stats
    
    def display_stats(self):
        """显示统计信息"""
        stats = self.get_stats()
        
        print(f"\n📊 查询组管理器统计:")
        print(f"   账户ID: {stats['account_id']}")
        print(f"   配置名称: {stats['config_name']}")
        print(f"   运行状态: {'✅ 运行中' if stats['running'] else '❌ 已停止'}")
        print(f"   商品数量: {stats['product_count']}")
        print(f"   新查询组: {'✅ 已启用' if stats['has_new_group'] else '❌ 未启用'}")
        print(f"   高速查询组: {'✅ 已启用' if stats['has_fast_group'] else '❌ 未启用'}") 
        print(f"   旧查询组: {'✅ 已启用' if stats['has_old_group'] else '❌ 未启用'}")
        
        group_types = [
            ('new', '新查询组', stats.get('new_group_id'), stats.get('new_group_stats')),
            ('fast', '高速查询组', stats.get('fast_group_id'), stats.get('fast_group_stats')),  # 新增
            ('old', '旧查询组', stats.get('old_group_id'), stats.get('old_group_stats'))
             ]
        for group_type, group_name, group_id, group_stats in group_types:
            if group_id and group_stats:
                print(f"\n   {'📱' if group_type == 'new' else '⚡' if group_type == 'fast' else '🖥️'}  {group_name} ({group_id}):")
                print(f"      状态: {'✅ 运行中' if group_stats['running'] else '❌ 已停止'}")
                print(f"      冷却时间: {group_stats['cooldown']:.1f}秒" if 'cooldown' in group_stats else f"      冷却范围: {group_stats['cooldown_range'][0]:.1f}-{group_stats['cooldown_range'][1]:.1f}秒")
                print(f"      查询次数: {group_stats['query_count']}")
                print(f"      发现次数: {group_stats['found_count']}")
                if group_type in ['new', 'fast']:
                    print(f"      是否在时间窗口: ⏰ 不受限制")
                else:
                    print(f"      是否在时间窗口: {'✅ 在窗口' if group_stats.get('in_time_window', False) else '❌ 不在窗口'}")

    
    @classmethod
    def get_all_stats(cls):
        """获取所有管理器的统计信息"""
        all_stats = []
        for group_id, group in cls._query_groups.items():
            if hasattr(group, 'get_stats'):
                all_stats.append(group.get_stats())
        
        scheduler_stats = None
        if cls._global_query_scheduler:
            scheduler_stats = cls._global_query_scheduler.get_stats()
        
        return {
            'total_groups': len(cls._query_groups),
            'scheduler_running': scheduler_stats['running'] if scheduler_stats else False,
            'groups': all_stats,
            'scheduler_stats': scheduler_stats
        }
    
    @classmethod
    def display_global_status(cls):
        """显示全局状态"""
        print(f"\n🌐 全局查询系统状态")
        print(f"=" * 50)
        
        # 调度器状态
        scheduler = cls.get_global_scheduler()
        if scheduler:
            scheduler.display_status()
        else:
            print(f"❌ 全局调度器未设置")
        
        # 统计各类查询组数量
        new_count = sum(1 for group_id in cls._query_groups.keys() if group_id.startswith('N_'))
        fast_count = sum(1 for group_id in cls._query_groups.keys() if group_id.startswith('F_'))
        old_count = sum(1 for group_id in cls._query_groups.keys() if group_id.startswith('O_'))
        
        print(f"\n📋 查询组状态 (共{len(cls._query_groups)}个):")
        print(f"   新查询组: {new_count}个")
        print(f"   高速查询组: {fast_count}个")  # 新增高速查询组显示
        print(f"   旧查询组: {old_count}个")
        
        # 所有查询组状态
        for group_id, group in cls._query_groups.items():
            if hasattr(group, 'get_stats'):
                stats = group.get_stats()
                status_icon = '✅' if stats['running'] else '❌'
                
                # 确定组类型图标
                if group_id.startswith('N_'):
                    type_icon = '📱'
                elif group_id.startswith('F_'):  # 新增高速查询组图标
                    type_icon = '⚡'
                else:
                    type_icon = '🖥️'
                
                # 时间窗口状态
                if group_id.startswith('N_') or group_id.startswith('F_'):  # 修改：包含F_
                    window_icon = '⏰'
                    window_text = '不受限'
                else:
                    window_icon = '⏰' if stats.get('in_time_window', False) else '🕒'
                    window_text = '在窗口' if stats.get('in_time_window', False) else '等待中' if stats['running'] else '已停止'
                
                print(f"   {status_icon}{type_icon} {group_id}: {stats['query_count']}次查询, {stats['found_count']}次发现 {window_icon}{window_text}")



class SessionManager:
    """独立的 HTTP/2 Session 管理器 - 单账户版本"""
    
    def __init__(self, user_id: str, account_manager=None): 
        self.user_id = user_id  # ✅ 存储用户ID
        self.account_manager = account_manager
        self._session = None  
        self._proxy = None    
        self._session_lock = asyncio.Lock()
        
    async def get_session(self, force_new=False):  # ✅ 移除account_id参数
        """
        获取Session - 专属于特定用户
        """
        if not self.account_manager or not self.user_id:  # ✅ 使用self.user_id
            return None
        
        # ✅ 获取这个用户对应的代理IP
        proxy_address = self.account_manager.account_proxies.get(self.user_id)  # ✅ 使用self.user_id
        
        async with self._session_lock:
            # ✅ 检查是否需要新session（只针对这个用户）
            need_new = (
                force_new or
                self._session is None or
                self._session.closed or
                proxy_address != self._proxy  # 代理变化检查
            )
            
            if need_new:
                # ✅ 关闭旧Session
                await self._close_session_safe(self._session)
                
                # 创建新Session
                session = await self._create_proxy_session(proxy_address)
                if session:
                    self._session = session
                    self._proxy = proxy_address
                    print(f"✅ 为用户 {self.user_id} 创建新Session，代理: {proxy_address}")  # ✅ 添加日志
            
        async with self._session_lock:
            # ✅ 修改检查逻辑：针对单个session
            need_new = (
                force_new or
                self._session is None or
                self._session.closed or
                proxy_address != self._proxy  # ✅ 代理变化检查
            )
            
            if need_new:
                # ✅ 关闭旧Session
                await self._close_session_safe(self._session)
                
                # 创建新Session
                session = await self._create_proxy_session(proxy_address)
                if session:
                    self._session = session
                    self._proxy = proxy_address
            
            return self._session
    
    # ✅ 添加公有close_session方法
    async def close_session(self):
        """关闭当前session"""
        async with self._session_lock:
            await self._close_session_safe(self._session)
            self._session = None
            self._proxy = None
    
    # 以下方法保持不变
    async def _create_proxy_session(self, proxy_address):
        """创建带有代理的Session"""
        try:
            connector = aiohttp.TCPConnector(
                ssl=False,
                limit=30,
                limit_per_host=5,
                force_close=False,
            )
            
            session = aiohttp.ClientSession(
                connector=connector,
                proxy=proxy_address,
                timeout=aiohttp.ClientTimeout(total=30),
                cookie_jar=None,
            )
            
            return session
            
        except Exception as e:
            print(f"❌ 创建代理Session失败: {e}")
            return None
    
    async def _close_session_safe(self, session):
        """安全关闭Session"""
        try:
            if session and not session.closed:
                await session.close()
        except:
            pass

# APISessionManager管理类
class APISessionManager:
    """OpenAPI专用的Session管理器 - 单账户版本"""
    
    def __init__(self, user_id: str, account_manager=None): 
        self.user_id = user_id  # ✅ 存储用户ID
        self.account_manager = account_manager
        self._session = None  
        self._proxy = None    
        self._session_lock = asyncio.Lock()
    
    async def get_session(self, force_new=False):  # ✅ 移除account_id参数
        """
        获取OpenAPI Session - 专属于特定用户
        """
        if not self.account_manager or not self.user_id:  # ✅ 使用self.user_id
            return None
        
        # 检查是否有API Key
        if not self.account_manager.has_api_key():  # ✅ 保持原检查
            return None
        
        # ✅ 获取这个用户对应的代理IP
        proxy_address = self.account_manager.account_proxies.get(self.user_id)  # ✅ 使用self.user_id
        
        async with self._session_lock:
            need_new = (
                force_new or
                self._session is None or
                self._session.closed or
                proxy_address != self._proxy 
            )
            
            if need_new:
                await self._close_session_safe(self._session)
                session = await self._create_api_proxy_session(proxy_address)
                if session:
                    self._session = session
                    self._proxy = proxy_address
                    print(f"✅ 为用户 {self.user_id} 创建新API Session，代理: {proxy_address}")  # ✅ 添加日志
        
        async with self._session_lock:
           
            need_new = (
                force_new or
                self._session is None or
                self._session.closed or
                proxy_address != self._proxy 
            )
            
            if need_new:
                
                await self._close_session_safe(self._session)
                
                session = await self._create_api_proxy_session(proxy_address)
                if session:
                    self._session = session
                    self._proxy = proxy_address
            
            return self._session
    
    
    async def close_session(self):
        """关闭API session"""
        async with self._session_lock:
            await self._close_session_safe(self._session)
            self._session = None
            self._proxy = None
    
    
    async def _create_api_proxy_session(self, proxy_address):
        """创建OpenAPI专用的带代理Session"""
        try:
            connector = aiohttp.TCPConnector(
                ssl=False,
                limit=15,
                limit_per_host=3,
            )
            
            session = aiohttp.ClientSession(
                connector=connector,
                proxy=proxy_address,
                timeout=aiohttp.ClientTimeout(total=20),
                cookie_jar=None,
            )
            
            return session
            
        except Exception as e:
            print(f"❌ 创建API代理Session失败: {e}")
            return None
    
    async def _close_session_safe(self, session):
        """安全关闭Session"""
        try:
            if session and not session.closed:
                await session.close()
        except:
            pass


class SeleniumLoginManager:
    """Selenium登录管理器 """
    
    def __init__(self):
        self.driver = None
        self.target_request_data = None
        self.login_api_url = "https://www.c5game.com/login?return_url=%2Fuser%2Fuser%2F"
        self.success_url_pattern = "https://www.c5game.com/user/user/"
        self._browser_closed_by_user = False
        self.proxy_plugin_file = None

    def get_anti_debug_script(self):
        """获取反反调试脚本"""
        anti_debug_script = """
        // ==UserScript==
        // @name         Anti Anti Debug for C5Game
        // @description  绕过C5Game的反调试技术
        // @author       Selenium Automation
        // @run-at       document-start
        // ==/UserScript==
        
        (function() {
            'use strict';
            
            // 标记脚本已加载
            if (window.__C5GAME_ANTI_ANTI_DEBUG_LOADED__) {
                return;
            }
            window.__C5GAME_ANTI_ANTI_DEBUG_LOADED__ = true;
            
            console.log('C5Game反反调试脚本已加载');
            
            // 1. 处理debugger语句
            try {
                // 重写Function构造函数
                const OriginalFunction = Function;
                window.Function = function(...args) {
                    const body = args[args.length - 1];
                    if (typeof body === 'string') {
                        const patchedBody = body.replace(/debugger\\s*;/gi, '// debugger removed;');
                        args[args.length - 1] = patchedBody;
                    }
                    return OriginalFunction.apply(this, args);
                };
                window.Function.prototype = OriginalFunction.prototype;
            } catch (e) {}
            
            // 2. 防止console检测
            try {
                // 保存原始console方法
                const originalConsole = {
                    clear: console.clear,
                    table: console.table
                };
                
                // 重写可能被检测的方法
                console.clear = function() {};
                console.table = function() {};
                
                // 防止被覆盖
                Object.defineProperty(window, 'console', {
                    value: console,
                    writable: false,
                    configurable: false
                });
            } catch (e) {}
            
        })();
        """
        return anti_debug_script
    

    def setup_request_monitor(self):
        """设置专门的C5Game用户信息API监控"""
        monitor_script = self.get_anti_debug_script() + """
        // C5Game专用用户信息API监控
        (function() {
            'use strict';
            
            // 创建监控对象
            window.__C5GAME_USERINFO_MONITOR__ = {
                requestData: null,
                loginDetected: false,
                lastUrl: location.href
            };
            
            console.log('C5Game用户信息监控已启动');
            
            // 监听URL变化
            const checkUrlChange = () => {
                const currentUrl = location.href;
                if (currentUrl !== window.__C5GAME_USERINFO_MONITOR__.lastUrl) {
                    window.__C5GAME_USERINFO_MONITOR__.lastUrl = currentUrl;
                    console.log('URL变化:', currentUrl);
                    
                    // 如果跳转到用户页面，标记为登录成功
                    if (currentUrl.includes('/user/user/')) {
                        console.log('✅ 检测到登录成功跳转');
                        window.__C5GAME_USERINFO_MONITOR__.loginDetected = true;
                        
                        // 页面跳转到用户页面后，主动触发用户信息API检查
                        setTimeout(() => {
                            console.log('🔄 用户页面已加载，等待API请求...');
                        }, 1000);
                    }
                }
            };
            
            setInterval(checkUrlChange, 1000);
            
            // 监控用户信息API请求
            const originalFetch = window.fetch;
            window.fetch = function(input, init) {
                const url = input.url || input;
                
                // 监控用户信息API请求
                if (url && (url.includes('/api/v1/user/v2/userInfo') || 
                        url.includes('user/v2/userInfo'))) {
                    console.log('🔍 监控到用户信息API请求:', url);
                    
                    // 记录请求详细信息
                    const requestInfo = {
                        url: url,
                        method: init && init.method ? init.method : 'GET',
                        headers: init && init.headers ? init.headers : {},
                        timestamp: Date.now()
                    };
                    console.log('请求详情:', requestInfo);
                    
                    return originalFetch(input, init).then(response => {
                        if (response.status === 200) {
                            return response.clone().text().then(text => {
                                try {
                                    const data = JSON.parse(text);
                                    console.log('用户信息API响应状态:', data.success);
                                    
                                    if (data.success && data.data && data.data.personalData) {
                                        console.log('✅ 成功捕获用户信息API响应');
                                        console.log('用户ID:', data.data.personalData.userId);
                                        console.log('昵称:', data.data.personalData.nickName);
                                        
                                        window.__C5GAME_USERINFO_MONITOR__.requestData = {
                                            response: text,
                                            cookies: document.cookie,
                                            url: url,
                                            requestInfo: requestInfo,
                                            timestamp: Date.now(),
                                            hasUserData: true
                                        };
                                    } else {
                                        console.log('⚠️ API响应格式异常:', data);
                                        window.__C5GAME_USERINFO_MONITOR__.requestData = {
                                            response: text,
                                            cookies: document.cookie,
                                            url: url,
                                            timestamp: Date.now(),
                                            hasUserData: false
                                        };
                                    }
                                } catch (e) {
                                    console.log('解析响应失败:', e);
                                    window.__C5GAME_USERINFO_MONITOR__.requestData = {
                                        response: text,
                                        cookies: document.cookie,
                                        url: url,
                                        timestamp: Date.now(),
                                        error: e.toString()
                                    };
                                }
                                return response;
                            });
                        } else {
                            console.log('❌ API请求失败，状态码:', response.status);
                            return response;
                        }
                    }).catch(error => {
                        console.log('❌ API请求异常:', error);
                        return Promise.reject(error);
                    });
                }
                
                // 同时监控其他可能的相关API
                if (url && (url.includes('/user/') || url.includes('/api/v1/user/'))) {
                    console.log('📡 监控到其他用户相关API:', url);
                }
                
                return originalFetch(input, init);
            };
            
            // 也监控XMLHttpRequest
            if (window.XMLHttpRequest) {
                const originalOpen = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
                    this._url = url;
                    return originalOpen.apply(this, arguments);
                };
                
                const originalSend = XMLHttpRequest.prototype.send;
                XMLHttpRequest.prototype.send = function(body) {
                    const url = this._url || '';
                    
                    if (url && (url.includes('/api/v1/user/v2/userInfo') || 
                            url.includes('user/v2/userInfo'))) {
                        console.log('🔍 监控到XHR用户信息API请求:', url);
                        
                        this.addEventListener('load', function() {
                            if (this.status === 200) {
                                try {
                                    const data = JSON.parse(this.responseText);
                                    console.log('XHR用户信息API响应状态:', data.success);
                                    
                                    if (data.success && data.data && data.data.personalData) {
                                        console.log('✅ 成功捕获XHR用户信息API响应');
                                        
                                        window.__C5GAME_USERINFO_MONITOR__.requestData = {
                                            response: this.responseText,
                                            cookies: document.cookie,
                                            url: url,
                                            timestamp: Date.now(),
                                            hasUserData: true
                                        };
                                    }
                                } catch (e) {
                                    console.log('解析XHR响应失败:', e);
                                }
                            }
                        });
                    }
                    
                    return originalSend.apply(this, arguments);
                };
            }
            
            // 提供调试接口
            window.debugC5GameMonitor = function() {
                console.log('=== C5Game监控调试信息 ===');
                console.log('监控对象:', window.__C5GAME_USERINFO_MONITOR__);
                console.log('当前URL:', location.href);
                console.log('Cookie:', document.cookie);
                console.log('=======================');
                return window.__C5GAME_USERINFO_MONITOR__;
            };
            
            // 页面加载完成后自动检查一次
            if (document.readyState === 'complete') {
                console.log('页面已加载完成，初始化监控检查');
            } else {
                window.addEventListener('load', function() {
                    console.log('页面加载完成，初始化监控检查');
                    if (location.href.includes('/user/user/')) {
                        console.log('✅ 检测到用户页面');
                        window.__C5GAME_USERINFO_MONITOR__.loginDetected = true;
                    }
                });
            }
            
        })();
        """
        
        try:
            # 在页面加载前注入脚本
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': monitor_script
            })
            print("✅ C5Game用户信息API监控脚本已注入")
            
            # 同时执行一次以确保当前页面也生效
            try:
                self.driver.execute_script(monitor_script)
                print("✅ 监控脚本已立即执行")
            except:
                pass
            
        except Exception as e:
            print(f"⚠️  注入脚本失败: {e}")


    async def wait_for_login_success(self, timeout=300):
        """等待登录成功 - 修复数据传递问题"""
        start_time = time.time()
        print(f"⏳ 等待用户扫码登录... (超时: {timeout}秒)")
        
        while time.time() - start_time < timeout:
            try:
                # 检查浏览器状态
                if not self._is_browser_alive():
                    print("⚠️  浏览器已被用户关闭")
                    self._browser_closed_by_user = True
                    return False
                
                # 1. 检查当前URL
                current_url = self.driver.current_url
                
                # 2. 检查是否跳转到用户页面
                if self.success_url_pattern in current_url:
                    print(f"✅ 检测到登录成功跳转: {current_url}")
                    print("🔄 等待页面完全加载...")
                    await asyncio.sleep(3)
                    
                    # 🔴 🔴 🔴 核心修改开始：直接执行JavaScript获取数据
                    print("🔍 正在从JavaScript获取监控数据...")
                    try:
                        # 直接执行JavaScript获取 window.__C5GAME_USERINFO_MONITOR__.requestData
                        js_data = self.driver.execute_script("""
                            try {
                                // 检查监控对象是否存在
                                if (typeof window.__C5GAME_USERINFO_MONITOR__ === 'undefined') {
                                    console.log('监控对象未定义');
                                    return null;
                                }
                                
                                const monitor = window.__C5GAME_USERINFO_MONITOR__;
                                
                                // 检查是否有请求数据
                                if (!monitor.requestData) {
                                    console.log('没有请求数据');
                                    return null;
                                }
                                
                                console.log('成功获取监控数据');
                                return monitor.requestData;
                                
                            } catch(e) {
                                console.error('获取监控数据失败:', e);
                                return null;
                            }
                        """)
                        
                        if js_data:
                            print(f"✅ 成功从JavaScript获取监控数据")
                            print(f"   响应长度: {len(js_data.get('response', ''))} 字符")
                            print(f"   包含用户数据: {js_data.get('hasUserData', False)}")
                            
                            # 🔴 关键：将JavaScript数据赋值给Python变量
                            self.target_request_data = js_data
                            
                            # 立即尝试提取用户信息
                            user_info = self.extract_user_info_from_response()
                            if user_info and user_info.get('userId'):
                                print(f"✅ 用户信息提取成功: {user_info['userId']}")
                                return True
                            else:
                                print("⚠️  提取用户信息失败，继续尝试其他方法")
                        else:
                            print("⚠️  JavaScript中没有监控数据")
                    except Exception as js_error:
                        print(f"⚠️  执行JavaScript失败: {js_error}")
                    # 🔴 🔴 🔴 核心修改结束
                    
                    # 3. 如果直接获取失败，使用原来的get_monitor_data方法
                    print("尝试通过get_monitor_data获取数据...")
                    monitor_data = await self.get_monitor_data()
                    if monitor_data and monitor_data.get('requestData'):
                        print("✅ 通过get_monitor_data获取到数据")
                        self.target_request_data = monitor_data['requestData']
                        return True
                    
                    # 4. 如果监控脚本没有数据，尝试直接获取用户信息
                    print("⚠️  监控脚本无数据，尝试直接获取用户信息...")
                    user_info = await self.extract_user_info_directly()
                    if user_info:
                        print(f"✅ 直接提取用户信息成功: {user_info['userId']}")
                        return True
                    
                    # 5. 即使没有用户信息，只要跳转成功也算登录成功
                    print("✅ URL跳转成功，登录已完成")
                    return True
                
                # 6. 提前检查监控脚本是否有数据（优化版）
                try:
                    # 直接执行简单检查
                    has_data = self.driver.execute_script("""
                        try {
                            return window.__C5GAME_USERINFO_MONITOR__?.requestData?.hasUserData || false;
                        } catch(e) {
                            return false;
                        }
                    """)
                    
                    if has_data:
                        print("✅ 提前检测到用户信息数据")
                        # 获取完整数据
                        js_data = self.driver.execute_script("""
                            return window.__C5GAME_USERINFO_MONITOR__.requestData;
                        """)
                        
                        if js_data:
                            self.target_request_data = js_data
                            print(f"✅ 提前捕获到完整的用户信息数据")
                            return True
                            
                except Exception as e:
                    # 忽略检查时的错误
                    pass
                
                # 7. 显示等待状态
                elapsed = int(time.time() - start_time)
                if elapsed % 10 == 0:
                    print(f"⏳ 等待登录中... {elapsed}秒 (URL: {current_url[:60]}...)")
                
            except Exception as e:
                # 检查是否浏览器相关错误
                if self._is_browser_error(e):
                    print("⚠️  浏览器连接异常，可能已被关闭")
                    self._browser_closed_by_user = True
                    return False
                else:
                    print(f"⚠️  检查登录状态时出错: {e}")
            
            await asyncio.sleep(2)
        
        print(f"⏰ 登录超时 ({timeout}秒)")
        return False

    
    
    def _is_browser_alive(self):
        """检查浏览器是否还在运行"""
        if not self.driver:
            return False
        
        try:
            # 尝试获取一个简单的属性来检查连接
            _ = self.driver.session_id
            return True
        except Exception:
            return False
    
    def _is_browser_error(self, exception):
        """检查异常是否由浏览器关闭引起"""
        error_str = str(exception).lower()
        browser_error_keywords = [
            'web view not found',
            'session not found',
            'no such window',
            'invalid session id',
            'chrome not reachable',
            'target frame detached',
            'browser disconnected'
        ]
        
        for keyword in browser_error_keywords:
            if keyword in error_str:
                return True
        return False
    
    async def get_monitor_data(self):
        """获取监控脚本的数据 - 增强版"""
        try:
            # 首先检查浏览器状态
            if not self._is_browser_alive():
                print("❌ 浏览器不可用，无法获取监控数据")
                return None
            
            print("🔍 尝试获取监控数据...")
            
            # 尝试获取监控数据
            try:
                monitor_data = self.driver.execute_script("""
                    try {
                        // 1. 首先检查监控对象是否存在
                        if (typeof window.__C5GAME_USERINFO_MONITOR__ === 'undefined') {
                            return {error: '监控对象未定义', status: 'not_initialized'};
                        }
                        
                        const monitor = window.__C5GAME_USERINFO_MONITOR__;
                        
                        // 2. 收集调试信息
                        const debugInfo = {
                            monitorExists: true,
                            hasRequestData: !!monitor.requestData,
                            loginDetected: monitor.loginDetected,
                            lastUrl: monitor.lastUrl,
                            currentUrl: window.location.href,
                            cookieCount: document.cookie.split(';').length,
                            timestamp: Date.now()
                        };
                        
                        // 3. 如果有请求数据，记录详细信息
                        if (monitor.requestData) {
                            debugInfo.requestData = {
                                url: monitor.requestData.url,
                                timestamp: monitor.requestData.timestamp,
                                hasUserData: monitor.requestData.hasUserData || false,
                                responseLength: monitor.requestData.response ? monitor.requestData.response.length : 0,
                                cookieLength: monitor.requestData.cookies ? monitor.requestData.cookies.length : 0
                            };
                            
                            // 检查响应是否包含用户信息
                            if (monitor.requestData.response) {
                                try {
                                    const data = JSON.parse(monitor.requestData.response);
                                    debugInfo.requestData.hasSuccess = data.success || false;
                                    debugInfo.requestData.hasPersonalData = !!(data.data && data.data.personalData);
                                    debugInfo.requestData.userId = data.data?.personalData?.userId;
                                    debugInfo.requestData.nickName = data.data?.personalData?.nickName;
                                } catch(e) {
                                    debugInfo.requestData.parseError = e.toString();
                                }
                            }
                        }
                        
                        // 4. 返回完整信息
                        return {
                            monitorData: monitor,
                            debugInfo: debugInfo,
                            status: 'success'
                        };
                        
                    } catch(e) {
                        return {error: '获取监控数据异常: ' + e.toString(), status: 'error'};
                    }
                """)
                
            except Exception as js_error:
                print(f"❌ 执行JavaScript失败: {js_error}")
                return None
            
            # 分析返回的数据
            if isinstance(monitor_data, dict):
                if monitor_data.get('status') == 'success':
                    # 成功获取数据
                    monitor_obj = monitor_data.get('monitorData')
                    debug_info = monitor_data.get('debugInfo', {})
                    
                    print(f"📊 监控数据状态:")
                    print(f"   - 监控对象存在: {debug_info.get('monitorExists', False)}")
                    print(f"   - 登录检测: {debug_info.get('loginDetected', False)}")
                    print(f"   - 有请求数据: {debug_info.get('hasRequestData', False)}")
                    print(f"   - 当前URL: {debug_info.get('currentUrl', '未知')}")
                    
                    if debug_info.get('hasRequestData'):
                        request_debug = debug_info.get('requestData', {})
                        print(f"   - 请求URL: {request_debug.get('url', '未知')}")
                        print(f"   - 响应长度: {request_debug.get('responseLength', 0)} 字符")
                        print(f"   - 包含用户数据: {request_debug.get('hasUserData', False)}")
                        print(f"   - 成功状态: {request_debug.get('hasSuccess', False)}")
                        print(f"   - 有个人信息: {request_debug.get('hasPersonalData', False)}")
                        
                        if request_debug.get('userId'):
                            print(f"   - 用户ID: {request_debug['userId']}")
                        if request_debug.get('nickName'):
                            print(f"   - 昵称: {request_debug['nickName']}")
                    
                    # 返回监控对象
                    return monitor_obj
                    
                elif monitor_data.get('status') == 'not_initialized':
                    print("⚠️  监控脚本未初始化或未加载")
                    return None
                    
                elif monitor_data.get('status') == 'error':
                    error_msg = monitor_data.get('error', '未知错误')
                    print(f"❌ 监控脚本执行错误: {error_msg}")
                    return None
                    
                else:
                    print(f"⚠️  未知的监控数据状态: {monitor_data}")
                    return None
                    
            elif monitor_data is None:
                print("⚠️  监控脚本返回None")
                return None
                
            else:
                print(f"⚠️  监控数据格式异常: {type(monitor_data)}")
                # 尝试直接返回（兼容旧格式）
                if hasattr(monitor_data, 'requestData'):
                    return monitor_data
                return None
                
        except Exception as e:
            print(f"❌ 获取监控数据过程中出错: {e}")
            return None






    async def extract_user_info_directly(self):
        """直接提取用户信息"""
        try:
            # 检查浏览器状态
            if not self._is_browser_alive():
                return None
                
            print("🔍 尝试直接获取用户信息...")
            
            # 方法1：检查页面中是否包含用户信息
            page_source = self.driver.page_source
            
            # 查找可能的用户信息
            import re
            
            # 尝试匹配用户ID
            user_id_patterns = [
                r'"userId":\s*(\d+)',
                r'userId["\']?\s*:\s*["\']?(\d+)',
                r'user["\']?\s*id["\']?\s*:\s*["\']?(\d+)'
            ]
            
            user_id = None
            for pattern in user_id_patterns:
                match = re.search(pattern, page_source)
                if match:
                    user_id = match.group(1)
                    break
            
            # 尝试匹配昵称
            nickname_patterns = [
                r'"nickName":\s*"([^"]+)"',
                r'nickName["\']?\s*:\s*["\']([^"\']+)["\']',
                r'nickname["\']?\s*:\s*["\']([^"\']+)["\']'
            ]
            
            nick_name = None
            for pattern in nickname_patterns:
                match = re.search(pattern, page_source)
                if match:
                    nick_name = match.group(1)
                    break
            
            if user_id or nick_name:
                user_info = {
                    'userId': user_id or '未知',
                    'nickName': nick_name or '未知'
                }
                print(f"✅ 从页面提取到用户信息: {user_info}")
                return user_info
            
            return None
            
        except Exception as e:
            print(f"❌ 直接提取用户信息失败: {e}")
            return None
    
    def extract_user_info_from_response(self):
        """从API响应中提取用户信息 - 简化版（仅监控脚本）"""
        try:
            print("🔍 开始提取用户信息...")
            
            # 只保留监控脚本提取方法
            print("  检查监控脚本数据...")
            try:
                monitor_data = self.driver.execute_script("""
                    try {
                        if (typeof window.__C5GAME_USERINFO_MONITOR__ !== 'undefined' && 
                            window.__C5GAME_USERINFO_MONITOR__.requestData) {
                            return window.__C5GAME_USERINFO_MONITOR__.requestData;
                        }
                        return null;
                    } catch(e) {
                        return {error: e.toString()};
                    }
                """)
                
                if monitor_data and not monitor_data.get('error'):
                    print(f"   ✅ 从监控脚本获取到数据")
                    print(f"     响应长度: {len(monitor_data.get('response', ''))} 字符")
                    print(f"     包含用户数据: {monitor_data.get('hasUserData', False)}")
                    
                    response_text = monitor_data.get('response', '')
                    if response_text:
                        try:
                            data = json.loads(response_text)
                            print(f"   ✅ 成功解析JSON响应")
                            
                            if data.get('success', False):
                                personal_data = data.get('data', {}).get('personalData', {})
                                
                                user_info = {
                                    'userId': str(personal_data.get('userId', '')),
                                    'nickName': personal_data.get('nickName', ''),
                                    'userName': personal_data.get('userName', ''),
                                    'avatar': personal_data.get('avatar', ''),
                                    'level': personal_data.get('level', 0)
                                }
                                
                                if user_info['userId']:
                                    print(f"   ✅ 成功提取用户信息")
                                    print(f"     ID: {user_info['userId']}")
                                    print(f"     昵称: {user_info['nickName']}")
                                    print(f"     等级: {user_info['level']}")
                                    return user_info
                                else:
                                    print(f"   ⚠️  JSON中没有userId字段")
                            else:
                                error_msg = data.get('errorMsg', '未知错误')
                                print(f"   ⚠️  API返回失败: {error_msg}")
                                
                        except json.JSONDecodeError as e:
                            print(f"   ❌ 解析监控数据JSON失败: {e}")
                            print(f"     响应预览: {response_text[:200]}")
                else:
                    if monitor_data and monitor_data.get('error'):
                        print(f"   ⚠️  执行脚本错误: {monitor_data.get('error')}")
                    else:
                        print(f"   ℹ️  监控脚本中没有请求数据")
            except Exception as e:
                print(f"   ⚠️  执行JavaScript失败: {e}")
            
            print(f"   ❌ 从监控脚本提取用户信息失败")
            return None
                
        except Exception as e:
            print(f"❌ 提取用户信息过程中发生未知错误: {e}")
            import traceback
            traceback.print_exc()
            return None



    
    async def login_with_proxy(self, proxy_address):
        """
        使用代理IP进行C5Game登录 - 集成代理认证插件
        代理格式: http://username:password@host:port
        """
        import re
        import zipfile
        import os
        import random
        import asyncio
        from selenium.webdriver.edge.service import Service
        
        try:
            print(f"🚀 C5Game登录流程开始 (代理: {proxy_address})...")
            
            # Edge浏览器选项
            edge_options = Options()
            edge_options.add_argument('--log-level=3')  # 只显示FATAL级别日志
            edge_options.add_argument('--silent')       # 静默模式
            edge_options.add_argument('--disable-logging')  # 禁用日志
            edge_options.add_experimental_option('excludeSwitches', ['enable-logging'])  # 排除日志开关
            
            # 额外抑制特定组件的日志
            edge_options.add_argument('--disable-component-extensions-with-background-pages')
            edge_options.add_argument('--disable-default-apps')
            edge_options.add_argument('--disable-notifications')
            edge_options.add_argument('--no-first-run')
            edge_options.add_argument('--no-default-browser-check')
            
            # 🔴🔴🔴 关键修复：通过环境变量完全禁用日志输出
            os.environ['WDM_LOG_LEVEL'] = '0'
            os.environ['WEBDRIVER_CHROME_LOG'] = 'false'
            os.environ['EDGE_LOG_LEVEL'] = '0'
            # 🔴 核心修改：使用代理认证插件
            if proxy_address and proxy_address != 'direct':
                try:
                    # 解析代理URL
                    pattern = r'^(?:https?://)?(?:(.+?):(.+?)@)?([^:]+)(?::(\d+))?$'
                    match = re.match(pattern, proxy_address.replace('http://', '').replace('https://', ''))
                    
                    if match:
                        username, password, host, port = match.groups()
                        
                        # 默认端口
                        if not port:
                            port = '80'
                        
                        # 创建代理认证插件
                        manifest_json = """
                        {
                            "version": "1.0.0",
                            "manifest_version": 2,
                            "name": "Proxy Auth",
                            "permissions": [
                                "proxy", "tabs", "unlimitedStorage", "storage",
                                "<all_urls>", "webRequest", "webRequestBlocking"
                            ],
                            "background": {"scripts": ["background.js"]}
                        }
                        """
                        
                        if username and password:
                            background_js = f"""
                            var config = {{
                                mode: "fixed_servers",
                                rules: {{
                                    singleProxy: {{
                                        scheme: "http",
                                        host: "{host}",
                                        port: parseInt({port})
                                    }},
                                    bypassList: ["localhost", "127.0.0.1", "<local>"]
                                }}
                            }};
                            chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
                            function callbackFn(details) {{
                                return {{
                                    authCredentials: {{
                                        username: "{username}",
                                        password: "{password}"
                                    }}
                                }};
                            }}
                            chrome.webRequest.onAuthRequired.addListener(
                                callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']
                            );
                            """
                        else:
                            background_js = f"""
                            var config = {{
                                mode: "fixed_servers",
                                rules: {{
                                    singleProxy: {{
                                        scheme: "http",
                                        host: "{host}",
                                        port: parseInt({port})
                                    }},
                                    bypassList: ["localhost", "127.0.0.1", "<local>"]
                                }}
                            }};
                            chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
                            """
                        
                        # 创建插件文件
                        self.proxy_plugin_file = f'proxy_auth_plugin_{int(time.time())}.zip'
                        with zipfile.ZipFile(self.proxy_plugin_file, 'w') as zp:
                            zp.writestr("manifest.json", manifest_json)
                            zp.writestr("background.js", background_js)
                        
                        print(f"✅ 代理认证插件创建成功: {self.proxy_plugin_file}")
                        edge_options.add_extension(self.proxy_plugin_file)
                        print(f"✅ 代理认证插件已添加到浏览器")
                        
                except Exception as e:
                    print(f"⚠️  创建代理插件失败: {e}")
                    # 回退方案
                    pure_proxy = re.sub(r'https?://[^@]*@', '', proxy_address)
                    pure_proxy = re.sub(r'^https?://', '', pure_proxy)
                    edge_options.add_argument(f'--proxy-server={pure_proxy}')
                    print(f"   使用无认证代理: {pure_proxy}")
            
            # 防止被检测
            edge_options.add_argument('--disable-blink-features=AutomationControlled')
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option('useAutomationExtension', False)
            edge_options.add_argument('--log-level=3') 
            edge_options.add_argument('--silent') 
            # 其他优化选项
            edge_options.add_argument('--no-sandbox')
            edge_options.add_argument('--disable-dev-shm-usage')
            edge_options.add_argument('--window-size=1200,800')
            edge_options.add_argument('--disable-gpu')
            edge_options.add_argument('--ignore-certificate-errors')
            edge_options.add_argument('--disable-web-security')
            
            # 随机User-Agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0'
            ]
            edge_options.add_argument(f'--user-agent={random.choice(user_agents)}')
            
            # 查找驱动
            script_dir = os.path.dirname(os.path.abspath(__file__))
            driver_path = os.path.join(script_dir, "msedgedriver.exe")
            
            if not os.path.exists(driver_path):
                print(f"❌ 未找到驱动: {driver_path}")
                return False, None, None, "未找到Edge驱动"
            
            print(f"✅ 找到驱动: {driver_path}")
            
            # 启动浏览器
            try:
                service = Service(driver_path)
                self.driver = webdriver.Edge(service=service, options=edge_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                print("✅ Edge浏览器启动成功")
                
                # 测试代理
                if proxy_address and proxy_address != 'direct':
                    try:
                        self.driver.set_page_load_timeout(10)
                        self.driver.get("http://httpbin.org/ip")
                        print("✅ 代理连接测试成功")
                        await asyncio.sleep(1)
                    except:
                        print("⚠️  代理连接测试失败，但继续尝试...")
                        
            except Exception as driver_error:
                print(f"❌ 启动失败: {driver_error}")
                return False, None, None, f"浏览器启动失败: {driver_error}"
            
            # 设置监控脚本
            self.setup_request_monitor()
            
            # 访问登录页面
            print(f"🌐 正在访问登录页面: {self.login_api_url}")
            self.driver.get(self.login_api_url)
            
            await asyncio.sleep(5)
            
            print("\n" + "="*60)
            print("📱 请使用手机扫描页面上的二维码登录")
            print("💡 提示: 如果不想登录，可以直接关闭浏览器窗口")
            print("⏳ 等待扫码登录... (300秒超时)")
            print("="*60 + "\n")
            
            # 等待登录成功
            login_success = await self.wait_for_login_success(timeout=300)
            
            if not login_success:
                if self._browser_closed_by_user:
                    print("ℹ️  用户取消了登录")
                    return False, None, None, "用户取消了登录"
                else:
                    print("❌ 登录失败或超时")
                    return False, None, None, "登录失败或超时"
            
            # 提取用户信息
            user_info = None
            cookie = None
            
            if self.target_request_data:
                user_info = self.extract_user_info_from_response()
                cookie = self.target_request_data.get('cookies', '') or self.target_request_data.get('Cookie', '')
            
            if not user_info:
                user_info = await self.extract_user_info_directly()
            
            if not user_info or not user_info.get('userId'):
                return False, None, None, "无法提取用户信息"
            
            if not cookie:
                try:
                    browser_cookies = self.driver.get_cookies()
                    cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in browser_cookies])
                    cookie = cookie_str
                except Exception as e:
                    print(f"⚠️  获取cookie失败: {e}")
                    cookie = ""
            
            print(f"✅ 登录成功!")
            print(f"   用户ID: {user_info['userId']}")
            print(f"   昵称: {user_info['nickName']}")
            
            return True, user_info, cookie, None
                
        except Exception as e:
            print(f"❌ 登录过程中出错: {e}")
            import traceback
            traceback.print_exc()
            
            if self._is_browser_error(e):
                return False, None, None, "用户取消了登录"
            else:
                return False, None, None, f"登录过程中出错: {e}"
        
        finally:
            self._safe_close_browser()
            # 清理代理插件文件
            if self.proxy_plugin_file and os.path.exists(self.proxy_plugin_file):
                try:
                    os.remove(self.proxy_plugin_file)
                    print(f"✅ 代理插件临时文件已删除")
                except:
                    pass



    def _safe_close_browser(self):
        """安全关闭浏览器，忽略所有错误"""
        if self.driver:
            try:
                # 先尝试简单检查浏览器是否还存在
                try:
                    # 快速检查，不等待
                    _ = self.driver.session_id
                    
                    # 尝试获取标题，如果失败说明浏览器已关闭
                    try:
                        title = self.driver.title
                        print(f"🔄 正在关闭浏览器... (当前标题: {title[:30]}...)")
                    except:
                        print("⚠️  浏览器窗口可能已被用户关闭")
                        self.driver = None
                        return
                    
                    # 正常关闭
                    self.driver.quit()
                    print("✅ 浏览器已正常关闭")
                    
                except Exception as check_error:
                    # 浏览器已经关闭或不可访问
                    print("⚠️  浏览器已关闭或无法访问")
                    
            except Exception as quit_error:
                # 忽略所有关闭相关的错误
                error_msg = str(quit_error)
                if "web view not found" in error_msg or "session not found" in error_msg:
                    print("ℹ️  浏览器窗口已被关闭")
                else:
                    print(f"⚠️  关闭浏览器时出错（已忽略）: {quit_error}")
                    
            finally:
                # 确保driver被清空
                self.driver = None
        else:
            print("ℹ️  没有需要关闭的浏览器")

#账号管理门面类
class AccountManager:
    def __init__(self):
        # 基础属性
        self.cookies = {}
        self.nc5_cross_access_token = None
        self.nc5_device_id = None
        self.last_cookie_save_time = None
        self.current_user_id = None  # 使用user_id作为唯一标识符
        self.current_account_name = None  # 显示名称
        self.current_account_file = None
        self.steam_inventories = [] 
        self.random_delay_min_ms = 0.0  
        self.random_delay_max_ms = 2000.0
        self.not_login_callback = None  # Not login事件回调
        self.processed_not_login_events = {}  # 已处理的未登录事件记录
        self.event_ttl = 300.0  # 事件记录保留300秒（5分钟）
        # 代理IP管理
        self.account_proxies = {}  # user_id -> proxy_address
        # Selenium登录管理器
        self.selenium_login_manager = SeleniumLoginManager()
        # Session管理器
        self._session_managers = {}  # user_id -> SessionManager实例
        self._api_session_managers = {}  # user_id -> APISessionManager实例
        self.login_status = True
        self._raw_cookie_string = "" 
        self._original_cookie_order = []  
        self.api_key = None
        self.inventory_selector = None
        self._DEFAULT_QUERY_COOLDOWN = 1.0
        self._DEFAULT_RANDOM_DELAY_ENABLED = False
        self._DEFAULT_RANDOM_DELAY_MIN = 0.0
        self._DEFAULT_RANDOM_DELAY_MAX = 2.0
        self._DEFAULT_QUERY_TIME_CONFIG = {
            'enabled': False,
            'start_hour': 0,
            'start_minute': 0,
            'end_hour': 0,
            'end_minute': 0
        }
        # 初始化当前配置为默认值
        self.query_cooldown = self._DEFAULT_QUERY_COOLDOWN
        self.random_delay_enabled = self._DEFAULT_RANDOM_DELAY_ENABLED
        self.random_delay_min = self._DEFAULT_RANDOM_DELAY_MIN
        self.random_delay_max = self._DEFAULT_RANDOM_DELAY_MAX
        self.query_time_config = self._DEFAULT_QUERY_TIME_CONFIG.copy()
        
    
    # ==================== 核心方法 ====================
    def set_not_login_callback(self, callback):
        """
        设置Not login事件回调
        
        参数:
            callback: 回调函数，格式为 async def callback(account_id)
        """
        self.not_login_callback = callback
        print(f"✅ AccountManager 已设置Not login事件回调")

    async def create_account_via_selenium(self, proxy_address):
        """
        使用Selenium自动登录创建或更新账户
        """
        try:
            self.reset_current_account()
            print(f"🚀 C5Game登录流程开始 (代理: {proxy_address})...")
            
            # ============ 调用Selenium登录管理器 ============
            # 让专业的SeleniumLoginManager处理登录过程
            success, user_info, cookies, error = await self.selenium_login_manager.login_with_proxy(proxy_address)
            
            if not success:
                print(f"❌ Selenium登录失败: {error}")
                return False, None, error
            
            user_id = user_info.get('userId')
            nick_name = user_info.get('nickName', f"用户{user_id}")
            
            if not user_id:
                return False, None, "无法获取用户ID"
            
            print(f"✅ Selenium登录成功!")
            print(f"   用户ID: {user_id}")
            print(f"   昵称: {nick_name}")
            print(f"   Cookie长度: {len(cookies)} 字符")
            
            # ============ 更新device_id ============
            updated_cookie = self._update_device_id_in_cookie(cookies)
            print(f"✅ 已自动更新device_id")
            
            # ============ 检查账户是否已存在 ============
            existing_account = self._find_account_file_by_user_id(user_id)
            current_time = self._get_beijing_time()
            
            if existing_account:
                # 读取现有配置
                try:
                    with open(existing_account, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except Exception as e:
                    print(f"❌ 读取现有账户失败: {e}")
                    return False, None, f"读取现有账户失败: {e}"
                
                old_name = existing_data.get('name', '未知')
                old_proxy = existing_data.get('proxy', '直连')
                new_proxy = proxy_address if proxy_address != 'direct' else '直连'
                
                print(f"\n🔍 检测到已有账户: {old_name} (ID: {user_id})")
                print(f"   原代理: {old_proxy}")
                print(f"   新代理: {new_proxy}")
                print(f"✅ 已更新账户: {old_name} → {nick_name}")

                old_api_key = existing_data.get('api_key')
                # 更新账户数据（保留用户配置）
                account_data = {
                    'name': nick_name,  # 更新昵称
                    'userId': user_id,
                    'proxy': proxy_address if proxy_address != 'direct' else None,  # 更新代理
                    'cookie': updated_cookie,  # 使用已更新device_id的Cookie
                    'created_at': existing_data.get('created_at', current_time),  # 保留创建时间
                    'last_updated': current_time,  # 更新最后修改时间
                    'last_used': current_time,  # 更新最后使用时间
                    'login': True,
                    'query_cooldown': existing_data.get('query_cooldown', self.query_cooldown),  # 保留用户设置
                    'random_delay_enabled': existing_data.get('random_delay_enabled', self.random_delay_enabled),
                    'random_delay_min': existing_data.get('random_delay_min', self.random_delay_min),
                    'random_delay_max': existing_data.get('random_delay_max', self.random_delay_max),
                    'api_key': old_api_key,  # 保留API Key
                    'query_time_config': existing_data.get('query_time_config', self.query_time_config.copy()),  # 保留时间配置
                    'steam_inventories': existing_data.get('steam_inventories', [])  # 保留仓库信息
                }
            else:
                # 新账户：创建完整配置
                account_data = {
                    'name': nick_name,
                    'userId': user_id,
                    'proxy': proxy_address if proxy_address != 'direct' else None,
                    'cookie': updated_cookie,  # 使用已更新device_id的Cookie
                    'created_at': current_time,
                    'last_updated': current_time,
                    'last_used': current_time,
                    'login': True,
                    'query_cooldown': self._DEFAULT_QUERY_COOLDOWN,
                    'random_delay_enabled': self._DEFAULT_RANDOM_DELAY_ENABLED,
                    'random_delay_min': self._DEFAULT_RANDOM_DELAY_MIN,
                    'random_delay_max': self._DEFAULT_RANDOM_DELAY_MAX,
                    'api_key':None,
                    'query_time_config': self._DEFAULT_QUERY_TIME_CONFIG.copy(),
                    'steam_inventories': []
                }
                
                
            
            # ============ 保存账户文件 ============
            account_filename = f"account_{user_id}.json"
            account_file = os.path.join(ACCOUNT_DIR, account_filename)
            self.current_account_file = account_file
            
            try:
                with open(account_file, 'w', encoding='utf-8') as f:
                    json.dump(account_data, f, ensure_ascii=False, indent=2)
                
                print(f"✅ 账户{'更新' if existing_account else '创建'}成功 (ID: {user_id})")
                print(f"   昵称: {nick_name}")
                print(f"   代理: {proxy_address if proxy_address != 'direct' else '直连'}")
                if existing_account and account_data.get('api_key'):
                     masked_key = account_data['api_key'][:8] + "..." + account_data['api_key'][-8:] if len(account_data['api_key']) > 16 else account_data['api_key']
                     print(f"   API Key: 已保留原账户的API Key")
                elif not existing_account:
                    print(f"   API Key: 未设置（新账户）")
                # 设置当前账户
                self.current_user_id = user_id
                self.current_account_name = nick_name
                
                # 设置Cookie（已包含更新的device_id）
                self.set_cookie_string(updated_cookie, user_id)
                self.api_key = account_data.get('api_key')  # 设置当前API Key
                self.query_cooldown = account_data.get('query_cooldown', self._DEFAULT_QUERY_COOLDOWN)
                # 保存代理映射
                if proxy_address and proxy_address != 'direct':
                    self.account_proxies[user_id] = proxy_address
                
                return True, account_data, None
                
            except Exception as e:
                print(f"❌ 保存账户文件失败: {e}")
                return False, None, f"保存账户失败: {e}"
                    
        except Exception as e:
            print(f"❌ 账户创建过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False, None, f"账户创建过程中出错: {e}"

    async def load_account_by_id(self, user_id: str, config_only: bool = False) -> bool:
        """根据用户ID加载账户
        
        参数:
            user_id: 用户ID
            config_only: 是否只加载配置信息（不加载仓库等额外数据），默认False
        """
        print(f"🔍 正在加载账户: {user_id}")
        
        try:
            self.reset_current_account()
            # 查找账户文件
            account_file = self._find_account_file_by_user_id(user_id)
            if not account_file:
                print(f"❌ 未找到账户文件 (ID: {user_id})")
                return False
            
            # 读取账户数据
            with open(account_file, 'r', encoding='utf-8') as f:
                account_data = json.load(f)
            
            # 读取登录状态
            login_status = account_data.get('login', True)  # 默认值为True
            self.login_status = login_status
            login_text = "已登录" if login_status else "未登录"
            
            # 设置账户信息
            self.current_user_id = user_id
            self.current_account_name = account_data.get('name', f"用户{user_id}")
            self.current_account_file = account_file
            self.login_status = login_status  # 保存登录状态
            
            # 获取Cookie（即使未登录也要获取，用于API查询）
            cookie_str = account_data.get("cookie")
            if not cookie_str:
                print(f"❌ 账户数据中缺少cookie字段")
                return False
            
            # 调用set_cookie_string解析Cookie
            if not self.set_cookie_string(cookie_str, user_id):
                print(f"❌ Cookie解析失败")
                return False
            
            # 设置代理
            proxy = account_data.get('proxy')
            if proxy:
                self.account_proxies[user_id] = proxy
                print(f"🌐 代理IP: {proxy}")
            else:
                print("🌐 代理IP: 直连")
            
            # 设置账户配置
            self.api_key = account_data.get("api_key") # 不提供默认值，None表示未设置
            self.query_cooldown = account_data.get('query_cooldown', 5.0)
            self.random_delay_enabled = account_data.get('random_delay', False)
            self.query_time_config = account_data.get('query_time_config', [])
            
            print(f"✅ 账户加载成功:")
            print(f"   名称: {self.current_account_name}")
            print(f"   登录状态: {login_text}") 
            print(f"   冷却时间: {self.query_cooldown}秒")
            print(f"   随机延迟: {'启用' if self.random_delay_enabled else '禁用'}")
            print(f"   API Key: {'已设置' if self.api_key else '未设置'}")
            
            # ✅ 根据登录状态决定是否加载库存信息
            if not config_only and login_status:  
                # ✅ 已登录账户：正常加载库存信息
                print(f"🔧 初始化库存选择器（已登录账户）...")
                
                # 创建SteamInventorySelector实例
                self.inventory_selector = SteamInventorySelector(self)
                
                # 查询并选择库存
                print(f"🔍 查询库存...")
                start_time = time.time()
                
                # 使用inventory_selector查询库存
                if self.inventory_selector:
                    await self.inventory_selector.query_and_select_inventory()
                    
                    # 从选择器获取库存信息
                    if hasattr(self.inventory_selector, 'available_inventories'):
                        self.steam_inventories = self.inventory_selector.available_inventories
                        
                        if self.steam_inventories:
                            print(f"✅ 已加载 {len(self.steam_inventories)} 个Steam库存")
                            print(f"🏭 可用库存: {len(self.steam_inventories)} 个")
                        else:
                            print(f"⚠️ 没有可用库存")
                            self.steam_inventories = []
                    
                    print(f"✅ 库存查询完成 - 耗时: {int((time.time()-start_time)*1000)}ms")
                else:
                    print(f"❌ 库存选择器初始化失败")
                
                print(f"✅ 账户 {user_id} 加载完成")
                
                # 保存更新后的账户数据（如果有变化）
                self.save_account_changes()
                print(f"💾 账户配置已保存")
                
            elif not login_status:
                # ✅ 未登录账户不加载库存信息
                print(f"⚠️  账户状态为未登录，跳过库存加载")
                self.steam_inventories = []  # 清空库存信息
                self.inventory_selector = None  # 不初始化库存选择器
                
            else:
                # ✅ config_only=True 且已登录：配置模式下不加载库存
                print(f"✅ 账户配置加载完成 (ID: {user_id})")
            
            return True
            
        except Exception as e:
            print(f"❌ 加载账户失败 (ID: {user_id}): {e}")
            import traceback
            traceback.print_exc()
            return False

    def reset_current_account(self):
        """
        重置当前账户的状态，避免状态污染
        """
        print(f"🔄 重置账户管理器状态...")
        
        # 记录之前的账户信息（用于日志）
        old_user_id = self.current_user_id
        old_account_name = self.current_account_name
        
        # 1. 重置当前账户信息
        self.current_user_id = None
        self.current_account_name = None
        self.current_account_file = None
        self.login_status = True  # 重置为默认登录状态
        
        # 2. 重置认证信息（避免API Key泄漏）
        self.cookies.clear()
        self.nc5_cross_access_token = None
        self.nc5_device_id = None
        self._raw_cookie_string = ""
        self._original_cookie_order.clear()
        self.api_key = None  # ⭐ 关键：清除API Key！
        
        # 3. 重置库存信息
        self.steam_inventories.clear()
        if self.inventory_selector:
            try:
                self.inventory_selector.cleanup()
            except:
                pass
            self.inventory_selector = None
        
        # 4. 重置配置为默认值
        self.query_cooldown = self._DEFAULT_QUERY_COOLDOWN
        self.random_delay_enabled = self._DEFAULT_RANDOM_DELAY_ENABLED
        self.random_delay_min = self._DEFAULT_RANDOM_DELAY_MIN
        self.random_delay_max = self._DEFAULT_RANDOM_DELAY_MAX
        self.query_time_config = self._DEFAULT_QUERY_TIME_CONFIG.copy()
        
        # 5. 日志输出
        if old_user_id:
            print(f"✅ 已从账户 {old_account_name} (ID: {old_user_id}) 重置状态")
            print(f"   API Key已清除，配置已恢复默认值")
        else:
            print(f"✅ 账户管理器状态已重置")
        
        return True


    def save_account_changes(self) -> bool:
        """保存当前账户的变更"""
        if not self.current_user_id:
            print("❌ 没有当前账户，无法保存")
            return False
        
        try:
            if not self.current_account_file:
                self.current_account_file = os.path.join(ACCOUNT_DIR, f"account_{self.current_user_id}.json")
            
            # 读取现有数据
            account_data = {}
            if os.path.exists(self.current_account_file):
                with open(self.current_account_file, 'r', encoding='utf-8') as f:
                    account_data = json.load(f)
            
            # 更新数据
            current_time = self._get_beijing_time()
            
            # 准备Steam仓库数据
            steam_inventories_to_save = []
            if self.inventory_selector and hasattr(self.inventory_selector, 'available_inventories'):
                steam_inventories_to_save = self.inventory_selector.available_inventories
            elif self.steam_inventories:
                steam_inventories_to_save = self.steam_inventories
            
            account_data.update({
                "name": self.current_account_name or f"用户{self.current_user_id}",
                "userId": self.current_user_id,
                "last_updated": current_time,
                "last_used": current_time,
                "login": self.login_status,
                "query_cooldown": self.query_cooldown,
                "random_delay_enabled": self.random_delay_enabled,
                "random_delay_min": self.random_delay_min,
                "random_delay_max": self.random_delay_max,
                "random_delay_min_ms": self.random_delay_min_ms,
                "random_delay_max_ms": self.random_delay_max_ms,
                "api_key": self.api_key,
                "query_time_config": self.query_time_config.copy(),
                "cookie": self.get_cookie_header_exact(),
                "proxy": self.account_proxies.get(self.current_user_id),
                "steam_inventories": steam_inventories_to_save
            })
            
            # 添加选定的Steam ID
            if (self.inventory_selector and 
                hasattr(self.inventory_selector, 'selected_inventory') and 
                self.inventory_selector.selected_inventory):
                selected_steam_id = self.inventory_selector.selected_inventory.get('steamId')
                if selected_steam_id:
                    account_data["selected_steam_id"] = selected_steam_id
            
            # 确保有创建时间
            if "created_at" not in account_data:
                account_data["created_at"] = current_time
            
            # 保存
            with open(self.current_account_file, 'w', encoding='utf-8') as f:
                json.dump(account_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 账户设置已保存 (ID: {self.current_user_id})")
            return True
            
        except Exception as e:
            print(f"❌ 保存账户失败: {e}")
            return False
    
    # ==================== Cookie管理方法 ====================
    
    def set_cookie_string(self, cookie_string, user_id=None):
        """设置Cookie字符串并解析"""
        try:
            print(f"🔧 设置Cookie字符串，长度: {len(cookie_string)} 字符")
            # 保存原始Cookie字符串
            self._raw_cookie_string = cookie_string
            
            # 解析Cookie字符串
            self._parse_cookie_string(cookie_string)
            # 设置用户ID
            self.current_user_id = user_id
            # 更新保存时间
            self.last_cookie_save_time = time.time()
            
            print(f"✅ Cookie设置成功")
            print(f"   Cookie数量: {len(self.cookies)}")
            print(f"   当前用户ID: {self.current_user_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ 设置Cookie失败: {e}")
            return False
    
    def _parse_cookie_string(self, cookie_string):
        """解析Cookie字符串"""
        try:
            # 清空现有Cookie
            self.cookies = {}
            self._original_cookie_order = []
            
            # 按分号分割Cookie
            cookie_items = [item.strip() for item in cookie_string.split(';')]
            
            for item in cookie_items:
                if '=' in item:
                    key, value = item.split('=', 1)
                    key = key.strip()
                    
                    # 保存到cookies字典
                    self.cookies[key] = value
                    # 保存原始顺序
                    self._original_cookie_order.append(key)
            
            # 提取关键字段
            self.nc5_cross_access_token = self.cookies.get('NC5_accessToken')
            self.nc5_device_id = self.cookies.get('NC5_deviceId')
            
            # 解码_csrf字段（如果有）
            if '_csrf' in self.cookies:
                csrf_value = self.cookies['_csrf']
                if '%' in csrf_value:
                    try:
                        
                        self.cookies['_csrf'] = unquote(csrf_value)
                    except:
                        pass
            
            # 检查关键Cookie是否存在
            if self.nc5_cross_access_token:
                pass
            else:
                print(f"   ⚠️  未找到NC5_accessToken")
            if self.nc5_device_id:
                pass
            else:
                print(f"   ⚠️  未找到NC5_deviceId")
            
            return True
            
        except Exception as e:
            print(f"❌ 解析Cookie失败: {e}")
            return False
    
    def _update_device_id_in_cookie(self, cookie_string):
        """在Cookie字符串中更新device_id（只在保存时调用）"""
        try:
            cookie_items = [item.strip() for item in cookie_string.split(';')]
            cookie_dict = {}
            
            for item in cookie_items:
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookie_dict[key.strip()] = value.strip()
            
            if 'NC5_deviceId' in cookie_dict:
                old_id = cookie_dict['NC5_deviceId']
                
                # 生成新的device_id
                timestamp = int(time.time() * 1000)
                random_part = random.randint(0, 99999)
                new_id = f"{timestamp}{random_part:05d}"
                
                # 更新
                cookie_dict['NC5_deviceId'] = new_id
                
                print(f"🔧 更新device_id: {old_id[:10]}... → {new_id}")
                
                # 重新构建Cookie字符串
                updated_cookie = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                return updated_cookie
            else:
                print("⚠️  Cookie中缺少NC5_deviceId字段")
                return cookie_string
            
        except Exception as e:
            print(f"⚠️  更新device_id失败: {e}")
            return cookie_string

    def get_cookie_header_exact(self):
        """生成精确的Cookie头部（保持原始顺序）"""
        try:
            if not self._original_cookie_order:
                # 如果没有原始顺序，使用任意顺序
                return '; '.join([f"{k}={v}" for k, v in self.cookies.items()])
            
            # 按照原始顺序构建Cookie字符串
            cookie_parts = []
            for key in self._original_cookie_order:
                if key in self.cookies:
                    cookie_parts.append(f"{key}={self.cookies[key]}")
            
            return '; '.join(cookie_parts)
            
        except Exception as e:
            print(f"❌ 生成Cookie头部失败: {e}")
            return ""
    
    def get_cookie_header_with_decoded_csrf(self) -> str:
        """返回Cookie字符串，只解码_csrf"""
        if not self._raw_cookie_string:
            return ""
        
        
        items = []
        for item in self._raw_cookie_string.split('; '):
            item = item.strip()
            if not item:
                continue
            
            if '=' in item:
                key, value = item.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 只解码_csrf
                if key == '_csrf' and '%' in value:
                    try:
                        value = unquote(value)
                    except:
                        pass
                
                items.append(f"{key}={value}")
            else:
                items.append(item)
        
        return '; '.join(items)
    
    def get_cookie_dict(self) -> Dict[str, str]:
        """获取Cookie字典"""
        return self.cookies.copy()
    
    def get_cookie_header(self) -> str:
        """获取Cookie头字符串（简化版，不保持顺序）"""
        return '; '.join([f'{k}={v}' for k, v in self.cookies.items()])
    
    def get_cookie_info_detailed(self) -> Dict[str, Any]:
        """获取详细的Cookie信息"""
        info = {
            "raw_length": len(self._raw_cookie_string),
            "parsed_count": len(self.cookies),
            "has_csrf": '_csrf' in self.cookies,
            "has_cf_clearance": 'cf_clearance' in self.cookies,
            "has_access_token": bool(self.nc5_cross_access_token),
            "has_device_id": bool(self.nc5_device_id),
            "cookie_order_preserved": len(self._original_cookie_order) > 0,
        }
        
        if '_csrf' in self.cookies:
            csrf_value = self.cookies['_csrf']
            info['csrf_encoded'] = '%' in csrf_value
            info['csrf_length'] = len(csrf_value)
        
        return info
    
    
    def _find_account_file_by_user_id(self, user_id: str) -> Optional[str]:
        """根据user_id查找账户文件"""
        if not os.path.exists(ACCOUNT_DIR):
            return None
        
        # 尝试文件名匹配
        possible_filename = f"account_{user_id}.json"
        possible_file = os.path.join(ACCOUNT_DIR, possible_filename)
        if os.path.exists(possible_file):
            return possible_file
        
        # 搜索所有文件
        for filename in os.listdir(ACCOUNT_DIR):
            if not filename.endswith('.json'):
                continue
            
            account_file = os.path.join(ACCOUNT_DIR, filename)
            try:
                with open(account_file, 'r', encoding='utf-8') as f:
                    account_data = json.load(f)
                
                if account_data.get('userId') == user_id:
                    return account_file
                    
            except:
                continue
        
        return None
    
    def _get_beijing_time(self):
        """获取北京时间"""
        try:
            beijing_tz = pytz.timezone('Asia/Shanghai')
            beijing_time = datetime.now(beijing_tz)
            return beijing_time.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_account_id(self):
        """获取当前账户ID"""
        return self.current_user_id
    
    def get_account_name(self):
        """获取当前账户显示名称"""
        return self.current_account_name or (f"用户{self.current_user_id}" if self.current_user_id else None)
    
    def get_current_proxy(self):
        """获取当前账户的代理IP"""
        if not self.current_user_id:
            return None
        return self.account_proxies.get(self.current_user_id)
    
    def get_account_info_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """根据user_id获取账户信息"""
        try:
            account_file = self._find_account_file_by_user_id(user_id)
            if account_file and os.path.exists(account_file):
                with open(account_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"❌ 获取账户信息失败: {e}")
        
        return None
    
    # ==================== Session管理方法 ====================
    
    async def get_global_session(self, force_new: bool = False):
        """获取当前账户的Session"""
        if not self.current_user_id:
            return None
        if not self.login_status:
            print(f"⚠️  账户 {self.current_user_id} 状态为未登录，无法提供浏览器session")
            return None
        # ✅ 懒加载：为当前用户创建SessionManager
        if self.current_user_id not in self._session_managers:
            self._session_managers[self.current_user_id] = SessionManager(
                user_id=self.current_user_id,  # ✅ 传递user_id
                account_manager=self
            )
            print(f"📝 为用户 {self.current_user_id} 创建SessionManager")
        
        # ✅ 获取专属的Session
        return await self._session_managers[self.current_user_id].get_session(
            force_new=force_new
        )

    async def close_global_session(self):
        """关闭当前账户的Session"""
        if self.current_user_id and self.current_user_id in self._session_managers:
            await self._session_managers[self.current_user_id].close_session()
            print(f"✅ 已关闭用户 {self.current_user_id} 的Session")

    async def get_api_session(self, force_new=False):
        """获取当前账户的API Session"""
        if not self.current_user_id or not self.has_api_key():
            print(f"⚠️  账户 {self.current_user_id} 缺少API Key或用户ID")
            return None
        
        # ✅ 懒加载：为当前用户创建APISessionManager
        if self.current_user_id not in self._api_session_managers:
            self._api_session_managers[self.current_user_id] = APISessionManager(
                user_id=self.current_user_id,  # ✅ 传递user_id
                account_manager=self
            )
            print(f"📝 为用户 {self.current_user_id} 创建APISessionManager")
        
        # ✅ 获取专属的API Session
        return await self._api_session_managers[self.current_user_id].get_session(
            force_new=force_new
        )

    async def close_api_session(self):
        """关闭当前账户的API Session"""
        if self.current_user_id and self.current_user_id in self._api_session_managers:
            await self._api_session_managers[self.current_user_id].close_session()
            print(f"✅ 已关闭用户 {self.current_user_id} 的API Session")

    async def close_all_sessions(self):
        """关闭所有session"""
        # 直接清理，不检查
        for manager in self._session_managers.values():
            try:
                await manager.close_session()
            except:
                pass
        
        for manager in self._api_session_managers.values():
            try:
                await manager.close_session()
            except:
                pass
        
        self._session_managers.clear()
        self._api_session_managers.clear()
        print("✅ 所有Session已关闭")
        
    async def handle_account_not_login(self, account_id):
        """
        处理账户未登录事件（单例多账户版本）
        
        参数:
            account_id: 账户ID，格式为 "account_{user_id}"
        
        返回:
            bool: 是否成功处理
        """
        try:
            # 提取user_id
            if not account_id.startswith("account_"):
                print(f"❌ 无效的账户ID格式: {account_id}")
                return False
            
            user_id = account_id.replace("account_", "")
            
            print(f"🔐 AccountManager 收到未登录事件: {account_id} (用户ID: {user_id})")
            
            # ============== 事件去重检查 ==============
            current_time = time.time()
            
            if user_id in self.processed_not_login_events:
                last_time = self.processed_not_login_events[user_id]
                if current_time - last_time < self.event_ttl:
                    print(f"⏭️  跳过重复的未登录事件: {account_id} (上次处理: {current_time-last_time:.1f}秒前)")
                    return True  # 已经处理过，返回成功但跳过
            
            # 记录事件时间
            self.processed_not_login_events[user_id] = current_time
            # ============== 结束去重检查 ==============
            
            # ============== 更新账户文件 ==============
            print(f"📝 开始更新账户 {user_id} 的登录状态...")
            
            # 1. 查找账户文件
            account_file = self._find_account_file_by_user_id(user_id)
            if not account_file:
                print(f"❌ 未找到账户文件: {user_id}")
                return False
            
            # 2. 读取账户数据
            try:
                with open(account_file, 'r', encoding='utf-8') as f:
                    account_data = json.load(f)
            except Exception as e:
                print(f"❌ 读取账户文件失败: {e}")
                return False
            
            # 3. 获取账户名称（用于日志）
            account_name = account_data.get('name', f"用户{user_id}")
            
            # 4. 检查是否需要更新（已经是未登录状态）
            current_login_status = account_data.get('login', True)
            if current_login_status == False:
                print(f"ℹ️  账户 {account_name} 已经标记为未登录，无需更新")
                return True
            
            # 5. 更新登录状态
            current_time_str = self._get_beijing_time()
            old_status = "已登录" if current_login_status else "未登录"
            
            account_data['login'] = False
            account_data['last_updated'] = current_time_str
            account_data['not_login_detected_at'] = current_time_str  # 新增字段，记录检测时间
            
            # 6. 保存更新后的数据
            try:
                with open(account_file, 'w', encoding='utf-8') as f:
                    json.dump(account_data, f, ensure_ascii=False, indent=2)
                
                print(f"✅ 账户状态已更新: {account_name}")
                print(f"   状态变更: {old_status} → 未登录")
                print(f"   账户文件: {os.path.basename(account_file)}")
                print(f"   更新时间: {current_time_str}")
                print(f"   更新原因: Not login事件")
            except Exception as e:
                print(f"❌ 保存账户文件失败: {e}")
                return False
           
            
            # 注意：这里只是检查和清理当前加载的数据，不影响其他账户
            if self.current_user_id == user_id:
                print(f"⚠️  当前加载的账户已标记为未登录，正在清理内存数据...")
                
                # 清理当前账户的内存数据（不影响其他账户）
                await self._clean_current_account_data()
                print(f"✅ 当前账户内存数据已清理")
            else:
                print(f"ℹ️  该账户不是当前加载的账户，只更新文件状态")
            
            
            
            self._clean_expired_not_login_events()
            
            return True
            
        except Exception as e:
            print(f"❌ 处理未登录事件失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _clean_current_account_data(self):
        """
        清理当前加载账户的内存数据（不删除文件）
        """
        try:
            # 1. 关闭所有Session
            await self.close_all_sessions()
            
            # 2. 清理库存信息
            self.steam_inventories = []
            
            # 3. 清理选择器
            if self.inventory_selector:
                try:
                    await self.inventory_selector.cleanup()
                except:
                    pass
                self.inventory_selector = None
            
            # 4. 清理Cookie信息
            self.cookies = {}
            self.nc5_cross_access_token = None
            self.nc5_device_id = None
            self._raw_cookie_string = ""
            self._original_cookie_order = []
 
        except Exception as e:
            print(f"⚠️  清理当前账户数据时出错: {e}")


    
    # ==================== 账户配置管理方法 ====================
    
    def set_query_cooldown(self, cooldown_seconds: float) -> bool:
        """设置查询冷却时间"""
        try:
            cooldown = float(cooldown_seconds)
            if cooldown < 0: cooldown = 0
            elif cooldown > 60: cooldown = 60
                
            self.query_cooldown = cooldown
            print(f"✅ 查询冷却时间已设置为: {cooldown}秒")
            
            if self.current_user_id:
                self.save_account_changes()
            
            return True
        except ValueError:
            print("❌ 请输入有效的数字")
            return False
    
    def set_random_delay(self, enabled: bool, min_delay: Optional[float] = None, max_delay: Optional[float] = None) -> bool:
        """设置随机延迟"""
        try:
            self.random_delay_enabled = bool(enabled)
            
            if min_delay is not None:
                self.random_delay_min = float(min_delay)
                self.random_delay_min_ms = self.random_delay_min * 1000
            
            if max_delay is not None:
                self.random_delay_max = float(max_delay)
                self.random_delay_max_ms = self.random_delay_max * 1000
            
            # 确保最小值不大于最大值
            if self.random_delay_min > self.random_delay_max:
                self.random_delay_min, self.random_delay_max = self.random_delay_max, self.random_delay_min
                self.random_delay_min_ms, self.random_delay_max_ms = self.random_delay_max_ms, self.random_delay_min_ms
            
            print(f"✅ 随机延迟设置:")
            print(f"   启用状态: {'是' if self.random_delay_enabled else '否'}")
            if self.random_delay_enabled:
                print(f"   随机延迟范围: {self.random_delay_min:.1f} ~ {self.random_delay_max:.1f} 秒")
                print(f"   总延迟范围: {self.query_cooldown + self.random_delay_min:.1f} ~ {self.query_cooldown + self.random_delay_max:.1f} 秒")
            
            if self.current_user_id:
                self.save_account_changes()
            
            return True
        except Exception as e:
            print(f"❌ 设置随机延迟失败: {e}")
            return False
    
    def set_api_key(self, api_key: str) -> bool:
        """设置API Key"""
        self.api_key = api_key.strip() if api_key else None
        
        if self.api_key:
            masked = self.api_key[:8] + "..." + self.api_key[-8:] if len(self.api_key) > 16 else self.api_key
            print(f"✅ API Key已设置: {masked}")
        else:
            print("✅ API Key已清除")
        
        if self.current_user_id:
            self.save_account_changes()
        
        return True
    
    def clear_api_key(self) -> bool:
        """清除API Key"""
        self.api_key = None
        print("✅ API Key已清除")
        
        if self.current_user_id:
            self.save_account_changes()
        
        return True
    
    def get_api_key(self) -> Optional[str]:
        """获取API Key"""
        return self.api_key
    
    def has_api_key(self) -> bool:
        """检查是否有API Key"""
        return bool(self.api_key)
    
    def set_query_time_window(self, enabled: bool, 
                             start_hour: Optional[int] = None, 
                             start_minute: Optional[int] = None,
                             end_hour: Optional[int] = None,
                             end_minute: Optional[int] = None) -> bool:
        """设置查询时间窗口"""
        try:
            self.query_time_config['enabled'] = bool(enabled)
            
            if enabled:
                # 验证并设置开始时间
                if start_hour is not None:
                    hour = int(start_hour)
                    if 0 <= hour <= 23:
                        self.query_time_config['start_hour'] = hour
                    else:
                        print(f"❌ 开始小时必须在0-23之间")
                        return False
                
                if start_minute is not None:
                    minute = int(start_minute)
                    if 0 <= minute <= 59:
                        self.query_time_config['start_minute'] = minute
                    else:
                        print(f"❌ 开始分钟必须在0-59之间")
                        return False
                
                # 验证并设置结束时间
                if end_hour is not None:
                    hour = int(end_hour)
                    if 0 <= hour <= 23:
                        self.query_time_config['end_hour'] = hour
                    else:
                        print(f"❌ 结束小时必须在0-23之间")
                        return False
                
                if end_minute is not None:
                    minute = int(end_minute)
                    if 0 <= minute <= 59:
                        self.query_time_config['end_minute'] = minute
                    else:
                        print(f"❌ 结束分钟必须在0-59之间")
                        return False
            
            if self.current_user_id:
                self.save_account_changes()
            
            return True
            
        except Exception as e:
            print(f"❌ 设置时间窗口失败: {e}")
            return False
    
    def get_query_time_config(self) -> Dict[str, Any]:
        """获取查询时间配置"""
        return self.query_time_config.copy()
    
    def clear_query_time_window(self) -> bool:
        """清除时间窗口配置"""
        self.query_time_config = {
            'enabled': False,
            'start_hour': 0,
            'start_minute': 0,
            'end_hour': 0,
            'end_minute': 0,
        }
        print("✅ 时间窗口配置已清除")
        
        if self.current_user_id:
            self.save_account_changes()
        
        return True
    
    # ==================== 账户信息获取方法 ====================
    
    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """获取所有账户信息"""
        accounts = []
        try:
            for filename in os.listdir(ACCOUNT_DIR):
                if filename.endswith('.json'):
                    account_file = os.path.join(ACCOUNT_DIR, filename)
                    try:
                        with open(account_file, 'r', encoding='utf-8') as f:
                            account_data = json.load(f)
                        
                        account_data['file'] = account_file
                        accounts.append(account_data)
                    except Exception as e:
                        print(f"⚠️  读取账户文件失败 {filename}: {e}")
            
            accounts.sort(key=lambda x: x.get('created_at', ''))
            return accounts
        except Exception as e:
            print(f"❌ 获取账户列表失败: {e}")
            return []
    
    def get_current_account_info(self) -> Optional[Dict[str, Any]]:
        """获取当前账户信息"""
        if not self.current_user_id:
            return None
        
        return self.get_account_info_by_id(self.current_user_id)
    
    def get_cookie_info(self) -> Dict[str, Any]:
        """获取Cookie信息"""
        info = {
            "has_cookie": bool(self.cookies),
            "cookie_count": len(self.cookies),
            "has_access_token": bool(self.nc5_cross_access_token),
            "has_device_id": bool(self.nc5_device_id),
            "current_user_id": self.current_user_id,
            "current_account_name": self.current_account_name,
            "last_updated": self.last_cookie_save_time,
            "query_cooldown": self.query_cooldown,
            "random_delay_enabled": self.random_delay_enabled,
            "random_delay_min": self.random_delay_min,
            "random_delay_max": self.random_delay_max,
            "steam_inventories_count": len(self.steam_inventories),
            "raw_cookie_length": len(self._raw_cookie_string),
            "cookie_order_preserved": len(self._original_cookie_order) > 0,
        }
        
        if self.last_cookie_save_time:
            from datetime import datetime
            last_time = datetime.fromtimestamp(self.last_cookie_save_time)
            info["last_updated_str"] = last_time.strftime("%Y-%m-%d %H:%M:%S")
        
        return info
      
    def get_inventory_selector(self) -> Optional[SteamInventorySelector]:
        """获取仓库选择器实例"""
        return self.inventory_selector
    
    def has_available_inventory(self) -> bool:
        """检查是否有可用仓库"""
        if self.inventory_selector:
            return self.inventory_selector.has_available_inventory()
        return False
    
    def delete_account(self, user_id: str) -> bool:
        """删除指定账户并清除所有相关数据"""
        try:
            # 1. 查找账户文件
            account_file = self._find_account_file_by_user_id(user_id)
            if not account_file or not os.path.exists(account_file):
                print(f"❌ 账户文件不存在 (ID: {user_id})")
                return False
            
            # 2. 删除物理文件
            os.remove(account_file)
            print(f"✅ 已删除账户文件 (ID: {user_id})")
            
            # 3. 检查是否删除的是当前账户
            is_current_account = (self.current_user_id == user_id)
            
            # 4. 清除该账户的所有内存信息
            
            # A. 清除当前账户信息（如果匹配）
            if is_current_account:
                self.current_user_id = None
                self.current_account_name = None
                self.current_account_file = None
                print("⚠️  已清除当前账户信息")
            
            # B. 清除该账户的会话数据（如果删除的是当前账户）
            if is_current_account:
                self.cookies = {}
                self.nc5_cross_access_token = None
                self.nc5_device_id = None
                self._raw_cookie_string = ""
                self._original_cookie_order = []
                print("⚠️  已清除当前会话")
            
            # C. 清除该账户的缓存数据
            self._clear_account_cache(user_id)
            
            
           
            
            return True
            
        except Exception as e:
            print(f"❌ 删除账户失败: {e}")
            return False

    def _clear_account_cache(self, user_id: str) -> None:
        """清除指定账户的缓存数据"""
        # 清除库存缓存
        original_count = len(self.steam_inventories)
        self.steam_inventories = [
            inv for inv in self.steam_inventories 
            if inv.get('user_id') != user_id
        ]
        removed_count = original_count - len(self.steam_inventories)
        
        if removed_count > 0:
            print(f"✅ 已清除账户 {user_id} 的 {removed_count} 条缓存数据")
    




    # ==================== 其他必要方法 ====================
    
    def get_x_access_token(self):
        """获取Access Token"""
        return self.nc5_cross_access_token
    
    def get_x_device_id(self):
        """获取Device ID"""
        return self.nc5_device_id
    
    def get_query_cooldown(self) -> tuple[float, float]:
        """
        获取查询冷却时间范围 (min_time, max_time)
        
        返回:
            (min_time, max_time): 最小冷却时间和最大冷却时间
            如果没有随机延迟，则 min_time = max_time = 基础冷却时间
            如果有随机延迟，则 min_time = 基础冷却时间 + 最小随机延迟
                        max_time = 基础冷却时间 + 最大随机延迟
        """
        base_time = self.query_cooldown  # 基础冷却时间，例如1.0
        
        if not self.random_delay_enabled:
            # 没有随机延迟：返回固定的时间
            return (base_time, base_time)
        
        # 有随机延迟：返回时间范围
        min_time = base_time + self.random_delay_min
        max_time = base_time + self.random_delay_max
        
        return (min_time, max_time)
    
   
    def update_steam_inventories(self, inventories: List[Dict[str, Any]]) -> bool:
        """更新Steam仓库信息"""
        if not inventories or not isinstance(inventories, list):
            return False
        
        self.steam_inventories = inventories
        print(f"✅ 已更新 {len(inventories)} 个Steam仓库信息")
        
        if self.inventory_selector:
            try:
                available_count = self.inventory_selector._refresh_available_inventories(inventories)
                
                if not self.inventory_selector.selected_inventory and available_count > 0:
                    self.inventory_selector.selected_inventory = self.inventory_selector.available_inventories[0]
                    print(f"🎯 自动选定仓库: {self.inventory_selector.selected_inventory.get('nickname', '未知')}")
            except Exception as e:
                print(f"⚠️  更新仓库选择器失败: {e}")
        else:
            print("ℹ️  仓库选择器未初始化，将在下次使用时创建")
        
        return True
    
    def get_steam_inventories(self) -> List[Dict[str, Any]]:
        """获取Steam仓库信息"""
        return self.steam_inventories

#===============================================================================
# 商品基础信息收集类（查询商品获取关键字段将其储存到数据库）
class ProductInfoCollector:
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.product_url = None
        self.item_id = None
        self.collected_data = {}
        
    def parse_and_set_url(self, product_url):
        self.product_url = product_url
        self.item_id = self._parse_url(product_url)
        return self
        
    def _parse_url(self, product_url):
        if not product_url:
            return None
            
        parsed_url = urlparse(product_url)
        path_parts = parsed_url.path.split('/')
        
        for part in path_parts:
            if part.isdigit() and 10 <= len(part) <= 20:
                return part
        
        if not self.item_id:
            decoded_path = unquote(parsed_url.path)
            decoded_parts = decoded_path.split('/')
            for part in decoded_parts:
                if part.isdigit() and 10 <= len(part) <= 20:
                    return part
        
        return None
    
    def get_product_url(self):
        return self.product_url
    
    def get_item_id(self):
        return self.item_id
    
    def is_valid(self):
        return bool(self.product_url and self.item_id)
    
    def check_item_in_database(self):
        """检查商品是否在数据库中"""
        if not self.item_id:
            return None
        
        item_data = query_item_from_database(self.item_id)
        return item_data
    
    def display_item_info(self, item_data):
        """显示商品信息"""
        if not item_data:
            print("❌ 商品信息为空")
            return
        
        print("\n" + "=" * 60)
        print("                   商品信息")
        print("=" * 60)
        
        # 格式化显示信息
        item_name = item_data.get('itemName', '未更新')
        minwear = item_data.get('minwear')
        maxwear = item_data.get('maxwear')
        minprice = item_data.get('minPrice')
        
        # 格式化磨损范围
        if minwear is not None and maxwear is not None:
            wear_range = f"({minwear:.2f}~{maxwear:.2f})"
        else:
            wear_range = "(未更新)"
        
        # 格式化价格
        if minprice is not None:
            price_info = f"在售最低价{minprice}"
        else:
            price_info = "在售最低价未更新"
        
        # 显示完整信息
        print(f"📦 商品名称: {item_name}")
        print(f"📏 磨损范围: {wear_range}")
        print(f"💰 价格信息: {price_info}")
        print(f"🌐 商品URL: {item_data.get('url', '未更新')}")
        print("=" * 60)
    
    def get_api_path(self):
        if self.item_id:
            return f"search/v2/sell/{self.item_id}/list"
        return None
    
    def get_request_params(self):
        if self.item_id:
            return {
                "itemId": self.item_id,
                "page": 1,
                "limit": 10
            }
        return None
    
    def get_request_headers(self, timestamp, x_sign):
        """
        精确复制浏览器成功的GET请求头格式
        使用OrderedDict保持顺序
        """
        from collections import OrderedDict
        
        access_token = self.account_manager.get_x_access_token()
        device_id = self.account_manager.get_x_device_id()
        
        if not all([self.product_url, access_token, device_id, x_sign]):
            return None
        
        # 使用OrderedDict保持浏览器原始顺序
        headers = OrderedDict()
        
        # 第1部分：标准HTTP头（严格按照浏览器顺序）
        headers["Host"] = "www.c5game.com"
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0"
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Accept-Language"] = "zh-CN"
        headers["Accept-Encoding"] = "gzip, deflate, br, zstd"
        headers["Referer"] = self.product_url
        
        # 注意：GET请求没有Content-Type
        headers["Connection"] = "keep-alive"
        
        # 第2部分：Cookie（在特定位置）
        headers["Cookie"] = self.account_manager.get_cookie_header_exact()
        
        # 第3部分：Sec-Fetch系列（GET请求）
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "no-cors"  
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["TE"] = "trailers"
        
        # 第4部分：x-系列自定义头
        headers["x-app-channel"] = "WEB"
        headers["x-device-id"] = device_id
        headers["x-start-req-time"] = timestamp
        headers["x-source"] = "1"
        headers["x-sign"] = x_sign
        headers["x-access-token"] = access_token
        
        # 第5部分：缓存控制头（在最后）
        headers["Priority"] = "u=4"
        headers["Pragma"] = "no-cache"
        headers["Cache-Control"] = "no-cache"
        
        return headers
    
    def get_request_url(self):
        api_path = self.get_api_path()
        if api_path:
            return f"https://www.c5game.com/api/v1/{api_path}"
        return None
    
    def process_collected_data(self, response_data):
        try:
            if isinstance(response_data, str):
                data = json.loads(response_data)
            else:
                data = response_data
            
            if not data.get("success", False):
                return None
            
            item_list = data.get("data", {}).get("list", [])
            if not item_list:
                return None
            
            first_item = item_list[0]
            item_info = first_item.get("itemInfo", {})
            
            market_hash_name = first_item.get("marketHashName", "")
            
            
            processed_data = {
                "url": self.product_url,
                "itemSetName": item_info.get("itemSetName", ""),
                "rarityName": item_info.get("rarityName", ""),
                "itemName": first_item.get("itemName", ""),
                "marketHashName": market_hash_name,
                "itemId": self.item_id,
                "grade": "",
                "lastModified": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.collected_data = processed_data
            return processed_data
            
        except json.JSONDecodeError:
            return None
        except Exception:
            return None
    
    def get_collected_data(self):
        return self.collected_data
    
    def clear_collected_data(self):
        self.collected_data = {}
    
    async def execute_product_query(self):
        """执行商品查询 - 使用精确的浏览器格式"""
        print("🔍 正在查询商品信息...")
        
        if not self.is_valid():
            return False, "商品URL或item_id无效"
        
        api_path = self.get_api_path()
        access_token = self.account_manager.get_x_access_token()
        
        if not all([api_path, access_token]):
            return False, "缺少必要参数"
        
        # 生成时间戳（精确到毫秒）
        current_timestamp = str(int(time.time() * 1000))
        
        try:
            xsign_wrapper = GLOBAL_XSIGN_WRAPPER
            x_sign = xsign_wrapper.generate(
                path=api_path,
                method="GET",  # 注意：这里是GET方法
                timestamp=current_timestamp,
                token=access_token
            )
        except Exception as e:
            return False, f"生成x-sign失败: {e}"
        
        # 构建精确的请求头
        headers = self.get_request_headers(current_timestamp, x_sign)
        if not headers:
            return False, "构建请求头失败"
        
        url = self.get_request_url()
        params = self.get_request_params()
        
        try:
            # 获取全局Session
            session = await self.account_manager.get_global_session()
            
            print(f"🚀 发送HTTP/2商品查询请求（精确浏览器格式）...")
            print(f"  URL: {url}")
            print(f"  参数: {params}")
            print(f"  签名: {x_sign[:20]}...")
            
            start_time = time.perf_counter()
            
            async with session.get(
                url=url,
                params=params,
                headers=headers,  # 使用精确格式的headers
                timeout=aiohttp.ClientTimeout(total=8)
            ) as response:
                
                elapsed = (time.perf_counter() - start_time) * 1000
                status = response.status
                text = await response.text()
                
                print(f"✅ 商品查询完成 - 耗时: {elapsed:.0f}ms")
                print(f"  状态码: {status}")
                print(f"  HTTP版本: {response.version}")
                
                # 输出调试信息
                if status != 200:
                    print(f"⚠️  非200响应，可能存在问题")
                    print(f"  响应头: {dict(response.headers)}")
                
                return True, text
                
        except asyncio.TimeoutError:
            print("❌ 商品查询请求超时")
            return False, "请求超时"
        except Exception as e:
            print(f"❌ 商品查询请求失败: {e}")
            import traceback
            traceback.print_exc()
            return False, f"请求失败: {e}"

# UI管理
class UIManager:
    def __init__(self):
        self.account_manager = AccountManager()
        self.product_collector = ProductInfoCollector(self.account_manager)
        self.config_manager = ProductConfigManager()
        self.running = True
        
    def display_header(self):
        """显示程序头部"""
        print("           C5GAME商品配置管理系统")
        print()
    
    def display_main_menu(self):
        """显示主菜单"""
        print("\n" + "=" * 60)
        print("                     主菜单")
        print("=" * 60)
        print("1. 账户管理")
        print("2. 商品配置管理")
        print("3. 退出程序")
        print("=" * 60)
        
        choice = self.safe_input("请选择操作 (1-3): ").strip()
        return choice
    
    async def display_account_menu(self):
        """显示账户管理菜单"""
        print("\n" + "=" * 60)
        print("                   账户管理")
        print("=" * 60)
        
        # 显示当前状态
        current_account_name = self.account_manager.current_account_name
        print(f"当前选用账户: {current_account_name or '无'}") 
        proxy = self.account_manager.get_current_proxy()
        print(f"代理IP: {proxy or '直连'}")
        
        print("\n请选择操作:")
        print("1. Selenium自动登录新增账户")
        print("2. 删除账户")
        print("3. 选择账户配置")
        print("4. 设置查询冷却时间")
        print("5. 设置随机延迟")
        print("6. API Key管理")
        print("7. 查询时间窗口设置")
        print("8. 返回主菜单") 
        print("=" * 60)
        
        choice = self.safe_input("请选择操作 (1-8): ").strip()  
        return choice
    
    def safe_input(self, prompt=""):
        """安全的输入函数，清除可能存在的粘贴缓冲区内容"""
        try:
            # 清除输入缓冲区（避免粘贴多行内容被一次性读取）
            import sys
            import select
            
            # 检查是否有待读取的输入（可能是粘贴的内容）
            while sys.stdin in select.select([sys.stdin], [], [], 0.01)[0]:
                # 读取并丢弃缓冲区中的内容
                sys.stdin.readline()
                
        except Exception:
            # 如果 select 不可用，尝试其他方法
            try:
                import termios
                import fcntl
                import os
                
                # 尝试非阻塞读取
                fd = sys.stdin.fileno()
                oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
                
                try:
                    while True:
                        ch = sys.stdin.read(1)
                        if not ch:
                            break
                except:
                    pass
                finally:
                    fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
            except:
                # 如果都失败了，至少让程序能正常运行
                pass
        
        # 正常获取输入
        return input(prompt)
    
    async def add_account(self):
        """Selenium自动登录新增账户"""
        print("\n" + "=" * 60)
        print("                   Selenium自动登录新增账户")
        print("=" * 60)
        
        print("💡 请输入代理IP地址，格式如: http://127.0.0.1:8080")
        print("   输入 'direct' 使用直连，留空取消")
        
        proxy_address = input("\n代理IP地址: ").strip()
        
        if not proxy_address:
            print("❌ 已取消操作")
            return
        
        if proxy_address.lower() == 'direct':
            proxy_address = 'direct'
            print("ℹ️  将使用直连（无代理）")
        elif not proxy_address.startswith(('http://', 'https://')):
            proxy_address = f"http://{proxy_address}"
        
        print(f"\n🚀 启动Selenium登录流程...")
        
        try:
            success, account_data, error = await self.account_manager.create_account_via_selenium(proxy_address)
            
            if not success:
                
                print(f"❌ 账户创建失败: {error}")   
            else:
                pass
                
        except Exception as e:
            print(f"❌ 账户创建过程中出错: {e}")
    
    def switch_account(self):
        """切换账户"""
        print("\n" + "=" * 60)
        print("                   切换账户")
        print("=" * 60)
        
        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            print("ℹ️  当前没有账户")
            return
        
        print("可用账户:")
        for i, acc in enumerate(accounts, 1):
            user_id = acc.get('userId', '未知')
            name = acc.get('name', f"用户{user_id}")
            current_mark = " ✅" if user_id == self.account_manager.current_user_id else ""
            print(f"  {i}. {name} (ID: {user_id}){current_mark}")
        
        print(f"  0. 取消")
        
        try:
            choice = int(input("\n请选择要切换的账户序号: ").strip())
            if choice == 0:
                return
            
            if 1 <= choice <= len(accounts):
                selected_account = accounts[choice-1]
                user_id = selected_account.get('userId')
                
                if user_id:
                    if self.account_manager.load_account_by_id(user_id):
                        print(f"✅ 已切换到账户 (ID: {user_id})")
                else:
                    print("❌ 选择的账户没有user_id")
            else:
                print("❌ 无效的选择")
        except ValueError:
            print("❌ 请输入有效的数字")
   
    async def handle_cookie_menu(self):
        """处理账户菜单选择"""
        while True:
            choice = await self.display_account_menu()
            
            if choice == '1':
                await self.add_account()
            elif choice == '2':
                await self.delete_account()
            elif choice == '3':
                await self.switch_account(config_only=True)
            elif choice == '4':
                await self.set_query_cooldown_menu()
            elif choice == '5':
                await self.set_random_delay_menu()
            elif choice == '6':  
                await self.api_key_menu()
            elif choice == '7':
                await self.query_time_window_menu()
            elif choice == '8':  # 原来的第10项改为第8项
                break
            else:
                print("❌ 无效选择，请重新输入")



    def query_time_window_menu(self):
        """查询时间窗口设置菜单"""
        current_account = self.account_manager.current_user_id
        if not current_account:
            print("❌ 请先加载一个账户")
            input("按Enter键返回...")
            return
        
        while True:
            print("\n" + "=" * 60)
            print(f"                   查询时间窗口设置 - {current_account}")
            print("=" * 60)
            
            # 显示当前设置
            time_config = self.account_manager.get_query_time_config()
            
            if time_config['enabled']:
                start_str = f"{time_config['start_hour']:02d}:{time_config['start_minute']:02d}"
                end_str = f"{time_config['end_hour']:02d}:{time_config['end_minute']:02d}"
                
                # 计算时间窗口类型
                start_time = time_config['start_hour'] * 60 + time_config['start_minute']
                end_time = time_config['end_hour'] * 60 + time_config['end_minute']
                
                if start_time == end_time:
                    window_type = "全天 (24小时)"
                elif end_time > start_time:
                    window_type = "同一天"
                else:
                    window_type = "跨天"
                
                print(f"当前设置: ✅ 已启用")
                print(f"时间窗口: {start_str} ~ {end_str} ({window_type})")
            else:
                print(f"当前设置: ❌ 未启用 (不查询)")
            
            print("\n💡 时间窗口说明:")
            print("  - 格式: 开始时间 ~ 结束时间 (24小时制)")
            print("  - 示例1: 09:00 ~ 17:00 (9点到17点，同一天)")
            print("  - 示例2: 21:00 ~ 08:00 (21点到次日8点，跨天)")
            print("  - 示例3: 12:00 ~ 12:00 (全天24小时)")
            print("  - 不启用: 不查询")
            print("\n请选择操作:")
            print("1. 启用/设置时间窗口")
            print("2. 禁用时间窗口")
            print("3. 查看当前时间状态")
            print("4. 返回账户管理")
            print("=" * 60)
            
            choice = input("请选择操作 (1-4): ").strip()
            
            if choice == '1':
                self.set_query_time_window()
            elif choice == '2':
                self.disable_query_time_window()
            elif choice == '3':
                self.show_current_time_status()
            elif choice == '4':
                break
            else:
                print("❌ 无效选择")
    
    def set_query_time_window(self):
        """设置查询时间窗口"""
        print("\n" + "=" * 60)
        print("                   设置查询时间窗口")
        print("=" * 60)
        
        # 获取当前设置
        time_config = self.account_manager.get_query_time_config()
        
        print("💡 请输入时间 (24小时制，范围 0-23:0-59)")
        print("   例如: 开始=9:0, 结束=17:30 表示 09:00~17:30")
        print("   例如: 开始=21:0, 结束=8:0 表示 21:00~次日08:00")
        print("   如果开始和结束相同，表示全天查询")
        
        # 获取开始时间
        while True:
            start_input = input(f"\n请输入开始时间 (HH:MM) [当前: {time_config['start_hour']:02d}:{time_config['start_minute']:02d}]: ").strip()
            
            if not start_input:
                # 使用当前值
                break
            
            if ':' not in start_input:
                print("❌ 请输入正确的格式，如 9:0 或 09:00")
                continue
            
            try:
                hour_str, minute_str = start_input.split(':', 1)
                hour = int(hour_str.strip())
                minute = int(minute_str.strip())
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_config['start_hour'] = hour
                    time_config['start_minute'] = minute
                    break
                else:
                    print("❌ 时间范围不正确，小时(0-23)，分钟(0-59)")
            except ValueError:
                print("❌ 请输入有效的数字")
        
        # 获取结束时间
        while True:
            end_input = input(f"请输入结束时间 (HH:MM) [当前: {time_config['end_hour']:02d}:{time_config['end_minute']:02d}]: ").strip()
            
            if not end_input:
                # 使用当前值
                break
            
            if ':' not in end_input:
                print("❌ 请输入正确的格式，如 17:30 或 08:00")
                continue
            
            try:
                hour_str, minute_str = end_input.split(':', 1)
                hour = int(hour_str.strip())
                minute = int(minute_str.strip())
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_config['end_hour'] = hour
                    time_config['end_minute'] = minute
                    break
                else:
                    print("❌ 时间范围不正确，小时(0-23)，分钟(0-59)")
            except ValueError:
                print("❌ 请输入有效的数字")
        
        # 启用时间窗口
        success = self.account_manager.set_query_time_window(
            enabled=True,
            start_hour=time_config['start_hour'],
            start_minute=time_config['start_minute'],
            end_hour=time_config['end_hour'],
            end_minute=time_config['end_minute']
        )
        
        if success:
            print("✅ 时间窗口设置成功")
            input("按Enter键继续...")
    
    def disable_query_time_window(self):
        """禁用时间窗口"""
        confirm = input("确定要禁用时间窗口吗？(y/n): ").strip().lower()
        if confirm == 'y':
            self.account_manager.clear_query_time_window()
            print("✅ 时间窗口已禁用")
        else:
            print("❌ 已取消操作")
        
        input("按Enter键继续...")
    
    def show_current_time_status(self):
        """显示当前时间状态"""
        import datetime
        
        current_time = datetime.datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute
        current_seconds = current_time.second
        
        time_config = self.account_manager.get_query_time_config()
        
        print(f"\n🕐 当前系统时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if time_config['enabled']:
            start_str = f"{time_config['start_hour']:02d}:{time_config['start_minute']:02d}"
            end_str = f"{time_config['end_hour']:02d}:{time_config['end_minute']:02d}"
            
            # 计算当前时间在分钟数
            current_time_minutes = current_hour * 60 + current_minute
            start_time_minutes = time_config['start_hour'] * 60 + time_config['start_minute']
            end_time_minutes = time_config['end_hour'] * 60 + time_config['end_minute']
            
            # 判断是否在时间窗口内
            if start_time_minutes == end_time_minutes:
                # 全天
                is_in_window = True
                next_change = "全天窗口，无需切换"
            elif end_time_minutes > start_time_minutes:
                # 同一天
                is_in_window = start_time_minutes <= current_time_minutes < end_time_minutes
                if is_in_window:
                    # 计算距离结束还有多久
                    remaining_minutes = end_time_minutes - current_time_minutes - 1
                    remaining_seconds = 60 - current_seconds
                    next_change = f"距离结束: {remaining_minutes}分{remaining_seconds}秒"
                else:
                    if current_time_minutes < start_time_minutes:
                        # 还没开始
                        remaining_minutes = start_time_minutes - current_time_minutes - 1
                        remaining_seconds = 60 - current_seconds
                        next_change = f"距离开始: {remaining_minutes}分{remaining_seconds}秒"
                    else:
                        # 已经结束，等明天
                        next_change = "等待明天"
            else:
                # 跨天
                is_in_window = (current_time_minutes >= start_time_minutes) or (current_time_minutes < end_time_minutes)
                if is_in_window:
                    if current_time_minutes >= start_time_minutes:
                        # 今天晚上段
                        remaining_minutes = (1440 - current_time_minutes) + end_time_minutes - 1
                        remaining_seconds = 60 - current_seconds
                        next_change = f"距离结束: {remaining_minutes}分{remaining_seconds}秒"
                    else:
                        # 明天早上段
                        remaining_minutes = end_time_minutes - current_time_minutes - 1
                        remaining_seconds = 60 - current_seconds
                        next_change = f"距离结束: {remaining_minutes}分{remaining_seconds}秒"
                else:
                    # 在中间空白段
                    remaining_minutes = start_time_minutes - current_time_minutes - 1
                    remaining_seconds = 60 - current_seconds
                    next_change = f"距离开始: {remaining_minutes}分{remaining_seconds}秒"
            
            status = "✅ 在时间窗口内" if is_in_window else "❌ 不在时间窗口内"
            
            print(f"⏰ 设置的时间窗口: {start_str} ~ {end_str}")
            print(f"📊 状态: {status}")
            print(f"⏳ 下一次切换: {next_change}")
        else:
            print(f"⏰ 时间窗口: 未设置 (全天查询)")
            print(f"📊 状态: ✅ 全天查询中")
        
        input("\n按Enter键返回...")            
   
    async def api_key_menu(self):
        """API Key管理菜单"""
        current_account = self.account_manager.current_user_id
        if not current_account:
            print("❌ 请先加载一个账户")
            input("按Enter键返回...")
            return
        
        while True:
            print("\n" + "=" * 60)
            print(f"                   API Key管理 - {current_account}")
            print("=" * 60)
            

            # 显示当前状态
            if self.account_manager.has_api_key():
                api_key = self.account_manager.get_api_key()
                masked = api_key[:8] + "..." + api_key[-8:] if len(api_key) > 16 else api_key
                print(f"当前状态: ✅ 已设置")
                print(f"掩码显示: {masked}")
                print(f"完整长度: {len(api_key)} 字符")
            else:
                print(f"当前状态: ❌ 未设置")
            
            print("\n请选择操作:")
            print("1. 设置/替换API Key")
            print("2. 查看完整API Key")
            print("3. 清除API Key")
            print("4. 返回账户管理")
            print("=" * 60)
            
            choice = self.safe_input("请选择操作 (1-4): ").strip()
            
            if choice == '1':
                self.set_api_key()
            elif choice == '2':
                self.show_api_key()
            elif choice == '3':
                self.clear_api_key()
            elif choice == '4':
                break
            else:
                print("❌ 无效选择")
    
    def set_api_key(self):
        """设置API Key"""
        print("\n" + "=" * 60)
        print("                   设置API Key")
        print("=" * 60)
        
        if self.account_manager.has_api_key():
            api_key = self.account_manager.get_api_key()
            masked = api_key[:8] + "..." + api_key[-8:] if len(api_key) > 16 else api_key
            print(f"⚠️  当前已存在API Key: {masked}")
            confirm = input("\n确定要替换吗？(y/n): ").strip().lower()
            if confirm != 'y':
                print("❌ 已取消操作")
                return
        
        print("\n💡 提示: API Key将保存到账户配置中")
        api_key = input("请输入API Key : ").strip()
        
        if not api_key:
            print("❌ 已取消操作")
            return
        
        if self.account_manager.set_api_key(api_key):
            print("✅ API Key设置成功")
        else:
            print("❌ 设置失败")
    
    def show_api_key(self):
        """查看完整API Key"""
        if not self.account_manager.has_api_key():
            print("❌ 当前账户没有设置API Key")
            return
        
        api_key = self.account_manager.get_api_key()
        print("                   完整API Key")
        print(api_key)
        print(f"长度: {len(api_key)} 字符")
    
    def clear_api_key(self):
        """清除API Key"""
        if not self.account_manager.has_api_key():
            print("❌ 当前账户没有设置API Key")
            return
        
        confirm = input(" 确定要清除API Key吗？(y/n): ").strip().lower()
        if confirm == 'y':
            if self.account_manager.clear_api_key():
                print("✅ API Key已清除")
            else:
                print("清除失败")
        else:
            print("已取消操作")

    def set_query_cooldown_menu(self):
        """设置查询冷却时间菜单"""
        print("                   设置查询冷却时间")   
        current_account = self.account_manager.current_user_id
        if not current_account:
            print(" 请先加载一个账户")
            input("按Enter键返回...")
            return
        
        current_cooldown = self.account_manager.get_query_cooldown()
        print(f"当前账户: {current_account}")
        print(f"当前查询冷却时间: {current_cooldown}秒")
        
        print("\n💡 提示:")
        print("  - 查询冷却时间是指每次查询之间的等待时间")
        print("  - 建议设置为1-5秒，避免请求过于频繁")
        print("  - 设置为0表示无冷却时间")
        
        while True:
            cooldown_input = input(f"\n请输入新的查询冷却时间 (秒): ").strip()
            
            if not cooldown_input:
                print("❌ 输入不能为空")
                continue
            
            try:
                cooldown = float(cooldown_input)
                success = self.account_manager.set_query_cooldown(cooldown)
                if success:
                    print(f"✅ 查询冷却时间已设置为: {cooldown}秒")
                break
            except ValueError:
                print("❌ 请输入有效的数字")
        
        input("\n按Enter键返回...")

    async def set_random_delay_menu(self):
        """设置随机延迟（毫秒级精度）"""
        print("\n" + "=" * 60)
        print("                   设置随机延迟（毫秒级精度）")
        print("=" * 60)
        
        current_account = self.account_manager.current_user_id
        if not current_account:
            print("❌ 请先加载一个账户")
            input("按Enter键返回...")
            return
        
        # 获取当前设置
        cookie_info = self.account_manager.get_cookie_info()
        current_enabled = cookie_info['random_delay_enabled']
        current_min = cookie_info['random_delay_min']
        current_max = cookie_info['random_delay_max']
        
        print(f"当前账户: {current_account}")
        
        # 获取查询冷却时间（应该是元组 (min_cooldown, max_cooldown)）
        cooldown_range = self.account_manager.get_query_cooldown()
        
        if isinstance(cooldown_range, tuple) and len(cooldown_range) == 2:
            min_cooldown, max_cooldown = cooldown_range
            print(f"基础查询冷却时间: {min_cooldown:.1f} ~ {max_cooldown:.1f} 秒")
        else:
            # 如果返回的不是元组，转换为元组处理
            try:
                min_cooldown = float(cooldown_range)
                max_cooldown = min_cooldown
                print(f"基础查询冷却时间: {min_cooldown:.1f} 秒")
            except:
                min_cooldown = 1.0  # 默认值
                max_cooldown = 1.0
                print(f"基础查询冷却时间: 1.0 秒（默认）")
        
        print(f"\n当前随机延迟设置:")
        print(f"  启用状态: {'✅ 已启用' if current_enabled else '❌ 未启用'}")
        if current_enabled:
            print(f"  用户输入范围: {current_min:.3f} ~ {current_max:.3f} 秒")
            print(f"  实际执行范围: {current_min*1000:.0f} ~ {current_max*1000:.0f} 毫秒")
            
            # 计算总延迟范围 - 基础冷却 + 随机延迟
            total_min = min_cooldown + current_min
            total_max = max_cooldown + current_max
            print(f"  总延迟范围: {total_min:.3f} ~ {total_max:.3f} 秒")
        
        print("\n💡 提示:")
        print("  - 启用随机延迟可以避免固定的查询频率被识别")
        print("  - 支持小数，如：0.5-1.5秒（500-1500毫秒）")
        print("  - 设置0表示无随机延迟")
        
        print("\n1. 启用/禁用随机延迟")
        print("2. 设置随机延迟范围")
        print("3. 返回")
        print("=" * 60)
        
        sub_choice = input("请选择操作 (1-3): ").strip()
        
        if sub_choice == '1':
            # 切换启用状态
            new_enabled = not current_enabled
            success = self.account_manager.set_random_delay(
                enabled=new_enabled,
                min_delay=current_min,
                max_delay=current_max
            )
            
            if success:
                if new_enabled:
                    print(f"✅ 随机延迟已启用")
                else:
                    print(f"✅ 随机延迟已禁用")
            
        elif sub_choice == '2':
            # 设置随机延迟范围
            print("\n设置随机延迟范围:")
            
            while True:
                min_input = input(f"请输入最小随机延迟 (当前: {current_min:.3f}秒, 输入回车保持原值): ").strip()
                if not min_input:
                    min_delay = current_min
                    break
                
                try:
                    min_delay = float(min_input)
                    if min_delay < 0:
                        print("❌ 最小延迟不能为负数")
                        continue
                    break
                except ValueError:
                    print("❌ 请输入有效的数字")
            
            while True:
                max_input = input(f"请输入最大随机延迟 (当前: {current_max:.3f}秒, 输入回车保持原值): ").strip()
                if not max_input:
                    max_delay = current_max
                    break
                
                try:
                    max_delay = float(max_input)
                    if max_delay < 0:
                        print("❌ 最大延迟不能为负数")
                        continue
                    if max_delay < min_delay:
                        print("❌ 最大延迟不能小于最小延迟")
                        continue
                    break
                except ValueError:
                    print("❌ 请输入有效的数字")
            
            # 启用随机延迟并设置范围
            success = self.account_manager.set_random_delay(
                enabled=True,
                min_delay=min_delay,
                max_delay=max_delay
            )
            
            if success:
                print(f"✅ 随机延迟范围已更新:")
                print(f"   用户输入: {min_delay:.3f} ~ {max_delay:.3f} 秒")
                print(f"   实际执行: {min_delay*1000:.0f} ~ {max_delay*1000:.0f} 毫秒")
                
                # 重新计算并显示总延迟范围
                cooldown_range = self.account_manager.get_query_cooldown()
                if isinstance(cooldown_range, tuple) and len(cooldown_range) == 2:
                    min_cooldown, max_cooldown = cooldown_range
                    print(f"   总延迟: {min_cooldown :.3f} ~ {max_cooldown:.3f} 秒")
            
        elif sub_choice == '3':
            return
        else:
            print("❌ 无效选择")
        
        input("\n按Enter键返回...")

    async def show_scan_preparation_page(self, config):
        """扫货准备页面 - 只对12小时前的价格进行更新"""
        from datetime import datetime  # 在方法顶部导入
        
        while True:
            print("\n" + "=" * 70)
            print(f"             扫货准备页面 - 配置: {config.name}")
            print("=" * 70)
            
            # 1. 智能更新商品价格（仅更新12小时前的）
            print("🔍 检查商品价格更新需求（12小时阈值）...")
            updated_count = 0
            skipped_count = 0
            items_to_update = []
            
            # 第一阶段：收集需要更新的商品
            for i, product_item in enumerate(config.products, 1):
                print(f"  {i}. {product_item.item_name or '未命名商品'}", end="")
                
                # 直接使用 product_item.last_modified
                last_updated_str = product_item.last_modified
                
                # 检查是否需要更新
                if not last_updated_str:
                    print(f" - 无更新时间记录，需要更新")
                    items_to_update.append((i, product_item))
                    continue
                
                try:
                    last_updated = datetime.strptime(last_updated_str, "%Y-%m-%d %H:%M:%S")
                    now = datetime.now()
                    hours_passed = (now - last_updated).total_seconds() / 3600
                    
                    if hours_passed >= 12:
                        print(f" - {hours_passed:.1f}小时前更新，需要更新")
                        items_to_update.append((i, product_item))
                    else:
                        print(f" - {hours_passed:.1f}小时前更新，跳过")
                        skipped_count += 1
                except Exception as e:
                    print(f" - 解析时间失败: {e}")
                    items_to_update.append((i, product_item))
            
            # 第二阶段：批量更新需要更新的商品
            if items_to_update:
                print(f"\n🔄 开始更新 {len(items_to_update)} 个商品...")
                
                for index_in_list, product_item in items_to_update:
                    print(f"\n  [{index_in_list}] 正在更新: {product_item.item_name or '未命名商品'}")
                    
                    detail_collector = ProductDetailCollector(self.account_manager)
                    detail_collector.set_item(product_item.item_id, product_item.url)
                    product_info, error = await detail_collector.fetch_product_detail()
                    
                    if product_info and not error:
                        # 更新数据库
                        connection = db.get_connection(DB_FILE)
                        if connection:
                            try:
                                cursor = connection.cursor()
                                update_sql = """
                                UPDATE items 
                                SET minwear = ?, maxwear = ?, minPrice = ?, lastModified = ?
                                WHERE itemId = ?
                                """
                                
                                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                cursor.execute(update_sql, (
                                    product_info.get("minwear"),
                                    product_info.get("maxwear"),
                                    product_info.get("minPrice"),
                                    current_time,
                                    product_item.item_id
                                ))
                                connection.commit()
                                
                                # 更新 ProductItem 对象的 last_modified
                                product_item.last_modified = current_time
                                updated_count += 1
                                
                                cursor.close()
                                connection.close()
                                print(f"      ✅ 价格已更新")
                            except Exception as e:
                                print(f"      ❌ 更新数据库失败: {e}")
                        else:
                            print(f"      ❌ 数据库连接失败")
                    else:
                        print(f"      ❌ 获取商品信息失败: {error}")
            else:
                print(f"\n✅ 所有商品都是最新的（12小时内已更新）")
            
            print(f"\n📊 价格更新统计:")
            print(f"   已更新: {updated_count} 个商品")
            print(f"   已跳过: {skipped_count} 个商品")
            if items_to_update:
                print(f"   失败: {len(items_to_update) - updated_count} 个商品")
            
            # 保存更新后的配置（包含新的 last_modified）
            self.config_manager.save_configs()
            
            # 2. 显示配置中所有商品的信息
            print("\n📦 配置商品列表:")
            print("-" * 70)
            
            if not config.products:
                print("⚠️  配置中暂无商品")
            else:
                for i, product_item in enumerate(config.products, 1):
                    # 从数据库中查询最新信息（包含实时价格）
                    item_data = query_item_from_database(product_item.item_id)
                    
                    if item_data:
                        # 显示商品信息
                        print(f"\n{i}. {item_data.get('itemName', '未命名商品')}")
                        print(f"   ItemID: {product_item.item_id}")
                        print(f"   URL: {product_item.url[:60]}..." if len(product_item.url) > 60 else f"   URL: {product_item.url}")
                        
                        # 显示数据库中的实时信息
                        db_minwear = item_data.get('minwear')
                        db_maxwear = item_data.get('maxwear')
                        db_minprice = item_data.get('minPrice')
                        
                        if db_minwear is not None and db_maxwear is not None:
                            print(f"   📏 完整磨损范围: {db_minwear:.2f} ~ {db_maxwear:.2f}")
                        
                        if db_minprice is not None:
                            print(f"   💰 实时最低价格: {db_minprice}")
                        
                        # 显示当前设置的扫货参数
                        print(f"   ⚙️  当前扫货设置:")
                        print(f"     最小磨损: {product_item.minwear if product_item.minwear is not None else '未设置'}")
                        print(f"     最大磨损: {product_item.max_wear if product_item.max_wear is not None else '未设置'}")
                        print(f"     最大价格: {product_item.max_price if product_item.max_price is not None else '未设置'}")
                        
                        # 显示最后更新时间
                        if product_item.last_modified:
                            try:
                                last_updated = datetime.strptime(product_item.last_modified, "%Y-%m-%d %H:%M:%S")
                                now = datetime.now()
                                hours_passed = (now - last_updated).total_seconds() / 3600
                                print(f"   ⏰ 最后更新: {product_item.last_modified} ({hours_passed:.1f}小时前)")
                            except:
                                print(f"   ⏰ 最后更新: {product_item.last_modified}")
                    else:
                        print(f"\n{i}. 商品信息获取失败 (ItemID: {product_item.item_id})")
            
            print("\n操作选项:")
            print("1. 添加新商品到配置")
            print("2. 编辑商品参数")
            print("3. 从配置中移除商品")
            print("4. 重新更新所有价格")
            print("5. 确认扫货（开始无限轮询）")
            print("6. 返回配置列表")
            
            choice = input("请选择操作 (1-6): ").strip()
            
            if choice == '1':
                await self.add_product_to_config(config)
                # 保存配置
                self.config_manager.save_configs()
            elif choice == '2':
                await self.edit_product_in_config(config)
                # 保存配置
                self.config_manager.save_configs()
            elif choice == '3':
                self.delete_product_from_config(config)
                # 保存配置
                self.config_manager.save_configs()
            elif choice == '4':
                # 重新更新价格（通过继续循环）
                continue
            elif choice == '5':
                print("\n🎯 确认开始扫货...")
                await self.execute_infinite_scan(config)
                return  # 扫货结束后返回配置列表
            elif choice == '6':
                print("返回配置列表...")
                return
            else:
                print("❌ 无效选择，请重新输入")

    def delete_account(self):
        """删除账户"""
        print("\n" + "=" * 60)
        print("                   删除账户")
        print("=" * 60)
        
        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            print("ℹ️  当前没有账户")
            return
        
        print("现有账户:")
        for i, acc in enumerate(accounts, 1):
            print(f"  {i}. {acc['name']} (创建于: {acc.get('created_at', '未知')})")
        print(f"  0. 取消")
        
        try:
            choice = int(input("\n请选择要删除的账户序号: ").strip())
            if choice == 0:
                print("❌ 已取消操作")
                return
            
            if 1 <= choice <= len(accounts):
                account_id = accounts[choice-1]['userId'] 
                account_name = accounts[choice-1]['name']
                confirm = input(f"确定要删除账户 '{account_name}' 吗？此操作不可恢复！(y/n): ").strip().lower()
                if confirm == 'y':
                    if self.account_manager.delete_account(account_id):
                        print("✅ 账户已删除")
                    else:
                        print("❌ 账户删除失败")
                else:
                    print("❌ 已取消删除操作")
            else:
                print("❌ 无效的选择")
        except ValueError:
            print("❌ 请输入有效的数字")
    
    async def switch_account(self, config_only: bool = False):
        """选择账户配置
        
        参数:
            config_only: 是否只加载配置信息，默认False（完整加载）
              为True时只用于配置修改，不加载仓库信息
        """
        print("\n" + "=" * 60)
        if config_only:
            print("                   选择账户配置")
        else:
            print("                   切换账户")
        print("=" * 60)
        
        accounts = self.account_manager.get_all_accounts()
        if not accounts:
            print("ℹ️  当前没有账户")
            return
        
        print("可用账户:")
        for i, acc in enumerate(accounts, 1):
            user_id = acc.get('userId', '未知')
            name = acc.get('name', f"用户{user_id}")
            current_mark = " ✅" if user_id == self.account_manager.current_user_id else ""
            print(f"  {i}. {name} (ID: {user_id}){current_mark}")
        
        print(f"  0. 取消")
        
        try:
            prompt = "\n请选择要配置的账户序号: " if config_only else "\n请选择要切换的账户序号: "
            choice = int(input(prompt).strip())
            if choice == 0:
                return
            
            if 1 <= choice <= len(accounts):
                selected_account = accounts[choice-1]
                user_id = selected_account.get('userId')
                
                if user_id:
                    # 调用账户管理器加载账户，传入config_only参数
                    if config_only:
                        print(f"🔄 正在准备配置账户 (ID: {user_id})...")
                    else:
                        print(f"🔄 正在准备切换账户 (ID: {user_id})...")
                    if await self.account_manager.load_account_by_id(user_id, config_only=config_only):
                        if config_only:
                            print(f"✅ 已选择账户配置 (ID: {user_id})")
                        else:
                            print(f"✅ 已切换到账户 (ID: {user_id})")
                    else:
                        print(f"❌ 加载账户失败 (ID: {user_id})")
                else:
                    print("❌ 选择的账户没有user_id")
            else:
                print("❌ 无效的选择")
        except ValueError:
            print("❌ 请输入有效的数字")
        
        
    async def product_config_management(self):
        """商品配置管理页面"""
        print("\n" + "=" * 60)
        print("                   商品配置管理")
        print("=" * 60)
            
        while True:
            # 显示配置列表
            self.config_manager.display_configs_list()
                
            print("\n请选择操作:")
            print("1. 添加配置")
            print("2. 查看/修改配置")
            print("3. 删除配置")
            print("4. 执行扫货")
            print("5. 返回主菜单")
            print("=" * 60)
            
            choice = input("请选择操作 (1-5): ").strip()
                
            if choice == '1':
                await self.add_config()
            elif choice == '2':
                await self.edit_config()
            elif choice == '3':
                self.delete_config()
            elif choice == '4':
                await self.execute_purchase_scan()
            elif choice == '5':
                break
            else:
                print("❌ 无效选择，请重新输入")
        
    async def edit_product_in_config(self, config):
            """编辑配置中的商品"""
            products = config.get_all_products()
            if not products:
                print("ℹ️  配置中暂无商品")
                input("按Enter键返回...")
                return
            
            print("\n" + "=" * 60)
            print("                   编辑商品")
            print("=" * 60)
            
            # 显示商品列表
            for i, product in enumerate(products, 1):
                print(f"{i}. {product.item_name or '未命名'} (ItemID: {product.item_id})")
            
            print(f"0. 取消")
            
            try:
                choice = int(input("\n请选择要编辑的商品序号: ").strip())
                if choice == 0:
                    print("❌ 已取消操作")
                    return
                
                if 1 <= choice <= len(products):
                    product_index = choice - 1
                    product = products[product_index]
                    
                    print(f"\n📦 正在编辑商品: {product.item_name or '未命名'}")
                    product.display_info()
                    
                    # 查询数据库获取商品信息
                    item_data = query_item_from_database(product.item_id)
                    if not item_data:
                        print("⚠️  无法获取商品信息，请重新添加该商品")
                        return
                    
                    db_minwear = item_data.get('minwear')
                    db_maxwear = item_data.get('maxwear')
                    
                    if db_minwear is None or db_maxwear is None:
                        print("❌ 数据库中没有完整的磨损值")
                        return
                    
                    print(f"📏 数据库磨损范围: {db_minwear:.2f} ~ {db_maxwear:.2f}")
                    print(f"💡 最小磨损将自动使用最佳值: {db_minwear:.2f}")
                    
                    # 自动更新最小磨损为数据库的最佳值
                    product.minwear = float(f"{db_minwear:.2f}")
                    print(f"✅ 自动更新最小磨损为: {db_minwear:.2f}")
                    
                    # 获取最大磨损值
                    current_max_wear = product.max_wear
                    new_max_wear = input(f"最大磨损值 [{current_max_wear if current_max_wear else '未设置'}]: ").strip()
                    if new_max_wear:
                        try:
                            max_wear = float(new_max_wear)
                            max_wear = float(f"{max_wear:.2f}")
                            
                            # 验证是否在数据库磨损范围内
                            if not (db_minwear < max_wear <= db_maxwear):
                                print(f"❌ 最大磨损值({max_wear:.2f})必须在范围 ({db_minwear:.2f}, {db_maxwear:.2f}] 内")
                                return
                            
                            product.max_wear = max_wear
                            print(f"✅ 最大磨损值更新为: {max_wear}")
                        except ValueError:
                            print("❌ 无效的数字格式，保持原值")
                    
                    # 获取最大价格
                    current_max_price = product.max_price
                    new_max_price = input(f"最大价格 [{current_max_price if current_max_price else '未设置'}]: ").strip()
                    if new_max_price:
                        try:
                            max_price = float(new_max_price)
                            max_price = float(f"{max_price:.2f}")
                            
                            if max_price <= 0:
                                print("❌ 最大价格必须大于0")
                                return
                            
                            product.max_price = max_price
                            print(f"✅ 最大价格更新为: {max_price}")
                        except ValueError:
                            print("❌ 无效的数字格式，保持原值")
                    
                    # 保存配置
                    config.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.config_manager.save_configs()
                    print(f"\n✅ 商品参数已更新")
                    print(f"  最小磨损（自动）: {product.minwear:.2f}")
                    print(f"  最大磨损: {product.max_wear if product.max_wear else '未设置'}")
                    print(f"  最大价格: {product.max_price if product.max_price else '未设置'}")
                    
                else:
                    print("❌ 无效的选择")
            except ValueError:
                print("❌ 请输入有效的数字")

    async def add_config(self):
        """添加新配置"""
        print("\n" + "=" * 60)
        print("                   添加新配置")
        print("=" * 60)
        
        # 获取配置名称
        config_name = input("请输入配置名称: ").strip()
        if not config_name:
            print("❌ 配置名称不能为空")
            return
        
        # 检查名称是否唯一
        if self.config_manager.get_config_by_name(config_name):
            print(f"❌ 配置名称 '{config_name}' 已存在")
            return
        
        # 创建新配置
        config = ProductConfig(name=config_name)
        
        # 询问是否立即添加商品
        add_product = input("是否立即添加商品到配置中？(y/n): ").strip().lower()
        if add_product == 'y' or add_product == '':
            await self.add_product_to_config(config)
        
        # 保存配置
        if self.config_manager.add_config(config):
            print(f"✅ 配置 '{config_name}' 已创建")
            if config.products:
                print(f"✅ 已添加 {len(config.products)} 个商品到配置中")
        else:
            print("❌ 创建配置失败")
    
    async def edit_config(self):
        """编辑配置"""
        configs = self.config_manager.get_all_configs()
        if not configs:
            print("ℹ️  暂无商品配置")
            input("按Enter键返回...")
            return
        
        print("\n" + "=" * 60)
        print("                   编辑配置")
        print("=" * 60)
        
        # 显示配置列表
        for i, config in enumerate(configs, 1):
            print(f"{i}. {config.name} (包含商品: {len(config.products)}个)")
        
        print(f"0. 取消")
        
        try:
            choice = int(input("\n请选择要编辑的配置序号: ").strip())
            if choice == 0:
                print("❌ 已取消操作")
                return
            
            if 1 <= choice <= len(configs):
                config_index = choice - 1
                config = configs[config_index]
                
                await self.config_editor(config, config_index)
            else:
                print("❌ 无效的选择")
        except ValueError:
            print("❌ 请输入有效的数字")
    
    async def config_editor(self, config, config_index):
        """配置编辑器"""
        while True:
            print(f"\n📁 正在编辑配置: {config.name}")
            print("=" * 40)
            
            # 显示配置信息
            config.display_info()
            
            print("\n请选择操作:")
            print("1. 添加商品")
            print("2. 编辑商品")
            print("3. 删除商品")
            print("4. 修改配置名称")
            print("5. 返回配置列表")
            print("=" * 40)
            
            choice = input("请选择操作 (1-5): ").strip()
            
            if choice == '1':
                await self.add_product_to_config(config)
                # 保存配置
                self.config_manager.save_configs()
            elif choice == '2':
                await self.edit_product_in_config(config)
            elif choice == '3':
                self.delete_product_from_config(config)
            elif choice == '4':
                self.update_config_name(config, config_index)
            elif choice == '5':
                break
            else:
                print("❌ 无效选择，请重新输入")
   
    async def add_product_to_config(self, config):
        """向配置中添加商品"""
        print("\n" + "=" * 60)
        print("                   添加商品")
        print("=" * 60)
        
        # 2获取和解析URL
        product_url = input("请输入商品URL: ").strip()
        if not product_url:
            print("❌ 未输入商品URL")
            return
        
        self.product_collector.parse_and_set_url(product_url)
        if not self.product_collector.is_valid():
            print("❌ 无效的商品URL，无法提取item_id")
            return
        
        item_id = self.product_collector.get_item_id()
        print(f"✅ 解析成功: item_id = {item_id}")
        
        #  检查配置中是否已存在该商品
        if config.has_product_with_item_id(item_id):
            print(f"⚠️  该商品已存在于配置 '{config.name}' 中")
            overwrite = input("是否覆盖？(y/n): ").strip().lower()
            if overwrite != 'y':
                print("❌ 已取消操作")
                return
            else:
                print("🔄 将覆盖现有商品记录")
        
        #  检查数据库并决定是否调用API
        item_data = query_item_from_database(item_id)
        need_api_query = True  # 默认需要API查询
        api_failed = False
        
        # 定义必要字段
        required_fields = ['minwear', 'maxwear', 'marketHashName']
        
        if item_data:
            print(f"✅ 数据库中已有此商品记录")
            
            # 调试：打印所有字段
            print(f"   数据库字段: {list(item_data.keys())}")
            
            # 检查必要字段是否完整且有效
            missing_fields = []
            for field in required_fields:
                field_value = item_data.get(field)
                
                
                # 判断是否缺失或无效
                is_missing = field not in item_data
                is_none = field_value is None
                is_empty_string = isinstance(field_value, str) and field_value.strip() == ""
                
                if is_missing or is_none or is_empty_string:
                    missing_fields.append(field)
                    print(f"     ❌ 字段 '{field}' 无效")
               
            
            if not missing_fields:
                # 数据库数据完整，直接使用，不调用API
                print(f"✅ 数据库包含完整必要字段，直接使用数据库数据")
                print(f"   商品名称: {item_data.get('itemName', '未知')}")
                print(f"   磨损范围: {item_data.get('minwear', 0):.2f} ~ {item_data.get('maxwear', 0):.2f}")
                print(f"   市场名称: '{item_data.get('marketHashName', '未知')}'")
                
                need_api_query = False  # 不调用API
            else:
                # 数据库缺少必要字段，需要API查询
                print(f"⚠️  数据库记录缺少必要字段: {', '.join(missing_fields)}")
                print("🔄 将查询最新信息并更新数据库")
                need_api_query = True
        else:
            # 数据库中无记录，需要API查询
            print("📝 数据库中无此商品记录，需要查询商品信息")
            need_api_query = True
        
        product_info = {}  # 存储ProductDetailCollector获取的数据（磨损和价格）
        processed_data = {}  # 存储ProductInfoCollector获取的数据（其他商品信息）
        
        # 5. API查询逻辑
        if need_api_query:
            print("\n🔍 正在获取商品信息...")
            
            try:
                # 5.1 获取磨损和价格（ProductDetailCollector）
                print("  1. 获取磨损和价格信息...")
                detail_collector = ProductDetailCollector(self.account_manager)
                detail_collector.set_item(item_id, product_url)
                product_info, error = await detail_collector.fetch_product_detail()
                
                if error or not product_info:
                    print(f"❌ 获取商品磨损和价格失败: {error}")
                    api_failed = True
                else:
                    print("   ✅ 获取磨损和价格成功")
                    
                    # 5.2 获取完整商品信息（ProductInfoCollector）
                    print("  2. 获取完整商品信息...")
                    info_collector = ProductInfoCollector(self.account_manager)
                    info_collector.parse_and_set_url(product_url)
                    success, response_data = await info_collector.execute_product_query()
                    
                    if success and response_data:
                        processed_data = info_collector.process_collected_data(response_data)
                        if processed_data:
                            print("   ✅ 获取完整商品信息成功")
                        else:
                            print("   ⚠️  获取完整商品信息失败，将使用基础信息")
                    else:
                        print("   ⚠️  无法获取完整商品信息，将使用基础信息")
                        
            except Exception as e:
                print(f"❌ API查询过程中发生错误: {e}")
                api_failed = True
            
            # 6. 处理查询结果
            if api_failed:
                print("❌ 无法获取商品信息，添加失败")
                return
            else:
                # 查询成功，更新数据库
                print("💾 正在更新数据库...")
                
                db_data = {
                    "url": product_url,
                    "itemSetName": processed_data.get("itemSetName", "") if processed_data else "",
                    "rarityName": processed_data.get("rarityName", "") if processed_data else "",
                    "itemName": processed_data.get("itemName", "") if processed_data else product_info.get("itemName", ""),
                    "marketHashName": processed_data.get("marketHashName", "") if processed_data else "",
                    "itemId": item_id,
                    "grade": processed_data.get("grade", "") if processed_data else "",
                    "minPrice": product_info.get("minPrice"),
                    "minwear": product_info.get("minwear"),
                    "maxwear": product_info.get("maxwear"),
                    "lastModified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                if save_to_database(db_data, update_if_exists=True):
                    print("✅ 商品信息已保存到数据库")
                    item_data = db_data  # 更新item_data为最新数据
                else:
                    print("❌ 保存到数据库失败")
                    # 创建临时的item_data用于后续处理
                    item_data = {
                        "itemName": processed_data.get("itemName", "") if processed_data else product_info.get("itemName", ""),
                        "marketHashName": processed_data.get("marketHashName", "") if processed_data else "",
                        "minwear": product_info.get("minwear"),
                        "maxwear": product_info.get("maxwear"),
                        "minPrice": product_info.get("minPrice")
                    }
        else:
            # 7. 直接使用数据库数据的情况
            print("\n✅ 直接使用数据库中的完整信息")
            # 从item_data创建product_info和processed_data用于后续处理
            product_info = {
                'minwear': item_data.get('minwear'),
                'maxwear': item_data.get('maxwear'),
                'minPrice': item_data.get('minPrice'),
                'itemName': item_data.get('itemName', '')
            }
            processed_data = item_data
        
        # 8. 确保item_data是字典格式且包含必要信息
        if not isinstance(item_data, dict):
            if isinstance(product_info, dict):
                item_data = product_info.copy()
            elif isinstance(processed_data, dict):
                item_data = processed_data.copy()
            else:
                item_data = {}
        
        # 9. 显示商品信息
        print("\n📊 商品信息汇总:")
        print("=" * 50)
        
        # 显示商品名称
        item_name = item_data.get('itemName', '') 
        if not item_name and product_info.get('itemName'):
            item_name = product_info.get('itemName')
        if item_name:
            print(f"   名称: {item_name}")
        else:
            print(f"   名称: 未知")
        
        # 显示磨损范围
        minwear = item_data.get('minwear')
        maxwear = item_data.get('maxwear')
        if minwear is not None and maxwear is not None:
            print(f"   完整磨损范围: {minwear:.2f} ~ {maxwear:.2f}")
        else:
            minwear_api = product_info.get('minwear')
            maxwear_api = product_info.get('maxwear')
            if minwear_api is not None and maxwear_api is not None:
                print(f"   完整磨损范围: {minwear_api:.2f} ~ {maxwear_api:.2f}")
            else:
                print(f"   ⚠️  磨损范围: 信息不完整")
                minwear = minwear_api
                maxwear = maxwear_api
        
        # 显示价格
        price_val = item_data.get('minPrice')
        if price_val is None:
            price_val = product_info.get('minPrice')
        print(f"   实时最低价格: {price_val if price_val is not None else '未知'}")
        
        # 显示市场名称
        market_hash_name = ""
        if item_data:
            # 方法1：直接获取
            market_hash_name = item_data.get('marketHashName', '')
            
            # 方法2：如果上面获取不到，可能是键名问题
            if not market_hash_name:
                for key, value in item_data.items():
                    if 'market' in key.lower():
                        market_hash_name = value
                        break
        
        print("=" * 50)
        
        # 10. 获取用户输入的扫货参数
        # 使用最可靠的数据源来获取磨损信息
        param_source = {}
        
        # 优先使用product_info（API获取的最新数据）
        if isinstance(product_info, dict) and product_info.get('minwear') is not None and product_info.get('maxwear') is not None:
            param_source = product_info
            print("🔍 使用API获取的最新磨损信息进行参数设置")
        # 其次使用item_data（数据库数据）
        elif isinstance(item_data, dict) and item_data.get('minwear') is not None and item_data.get('maxwear') is not None:
            param_source = item_data
            print("🔍 使用数据库中的磨损信息进行参数设置")
        # 最后使用processed_data
        elif isinstance(processed_data, dict) and processed_data.get('minwear') is not None and processed_data.get('maxwear') is not None:
            param_source = processed_data
            print("🔍 使用处理后的商品信息进行参数设置")
        else:
            print("❌ 无法获取有效的磨损信息，无法设置扫货参数")
            return
        
        user_params = self.get_user_input(param_source)
        
        if not user_params:
            print("❌ 用户输入取消")
            return
        last_modified_value = None
        if item_data and 'lastModified' in item_data:
            last_modified_value = item_data['lastModified']
        elif processed_data and 'lastModified' in processed_data:
            last_modified_value = processed_data['lastModified']
        else:
            last_modified_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 11. 创建商品项目
        product_item = ProductItem(
            url=product_url,
            item_id=item_id,
            minwear=user_params['minwear'],
            max_wear=user_params['max_wear'],
            max_price=user_params['max_price'],
            item_name=item_name,
            market_hash_name=market_hash_name,
            last_modified=last_modified_value 
        )
        
        # 12. 添加到配置
        if config.add_product(product_item):
            print(f"\n✅ 商品已成功添加到配置 '{config.name}'")
            print(f"   ItemID: {item_id}")
            if product_item.item_name:
                print(f"   名称: {product_item.item_name}")
            print(f"   磨损设置: {product_item.minwear:.2f} ~ {product_item.max_wear:.2f}")
            print(f"   价格上限: {product_item.max_price}")
            
            # 保存配置
            self.config_manager.save_configs()
        else:
            print("❌ 添加商品失败")

    def delete_product_from_config(self, config):
        """从配置中删除商品"""
        products = config.get_all_products()
        if not products:
            print("ℹ️  配置中暂无商品")
            return
        
        print("\n" + "=" * 60)
        print("                   删除商品")
        print("=" * 60)
        
        # 显示商品列表
        for i, product in enumerate(products, 1):
            print(f"{i}. {product.item_name or '未命名'} (ItemID: {product.item_id})")
        
        print(f"0. 取消")
        
        try:
            choice = int(input("\n请选择要删除的商品序号: ").strip())
            if choice == 0:
                print("❌ 已取消操作")
                return
            
            if 1 <= choice <= len(products):
                product_index = choice - 1
                product = products[product_index]
                
                confirm = input(f"确定要删除商品 '{product.item_name or product.item_id}' 吗？(y/n): ").strip().lower()
                if confirm == 'y':
                    if config.remove_product(product_index):
                        self.config_manager.save_configs()
                        print(f"✅ 商品已从配置中删除")
                    else:
                        print("❌ 删除商品失败")
                else:
                    print("❌ 已取消删除操作")
            else:
                print("❌ 无效的选择")
        except ValueError:
            print("❌ 请输入有效的数字")
    
    def update_config_name(self, config, config_index):
        """修改配置名称"""
        print("\n" + "=" * 60)
        print("                   修改配置名称")
        print("=" * 60)
        
        print(f"当前配置名称: {config.name}")
        
        new_name = input("请输入新的配置名称: ").strip()
        if not new_name:
            print("❌ 配置名称不能为空")
            return
        
        if new_name == config.name:
            print("ℹ️  配置名称未改变")
            return
        
        # 检查名称是否唯一
        if self.config_manager.get_config_by_name(new_name):
            print(f"❌ 配置名称 '{new_name}' 已存在")
            return
        
        # 更新配置名称
        if self.config_manager.update_config(config_index, name=new_name):
            print(f"✅ 配置名称已更新为: {new_name}")
        else:
            print("❌ 更新配置名称失败")
    
    def delete_config(self):
        """删除配置"""
        configs = self.config_manager.get_all_configs()
        if not configs:
            print("ℹ️  暂无商品配置")
            input("按Enter键返回...")
            return
        
        print("\n" + "=" * 60)
        print("                   删除配置")
        print("=" * 60)
        
        # 显示配置列表
        for i, config in enumerate(configs, 1):
            print(f"{i}. {config.name} (包含商品: {len(config.products)}个)")
        
        print(f"0. 取消")
        
        try:
            choice = int(input("\n请选择要删除的配置序号: ").strip())
            if choice == 0:
                print("❌ 已取消操作")
                return
            
            if 1 <= choice <= len(configs):
                config_index = choice - 1
                config = configs[config_index]
                
                confirm = input(f"确定要删除配置 '{config.name}' 吗？(y/n): ").strip().lower()
                if confirm == 'y':
                    success, config_name = self.config_manager.delete_config(config_index)
                    if success:
                        print(f"✅ 配置 '{config_name}' 已删除")
                    else:
                        print("❌ 删除配置失败")
                else:
                    print("❌ 已取消删除操作")
            else:
                print("❌ 无效的选择")
        except ValueError:
            print("❌ 请输入有效的数字")
    
    async def execute_purchase_scan(self):
        """执行扫货 - 跳转到准备页面"""
        configs = self.config_manager.get_all_configs()
        if not configs:
            print("ℹ️  暂无商品配置")
            input("按Enter键返回...")
            return
        
        print("\n" + "=" * 60)
        print("                   选择扫货配置")
        print("=" * 60)
        
        # 显示配置列表
        for i, config in enumerate(configs, 1):
            print(f"{i}. {config.name} (包含商品: {len(config.products)}个)")
        
        print(f"0. 取消")
        
        try:
            choice = int(input("\n请选择要扫货的配置序号: ").strip())
            if choice == 0:
                print("❌ 已取消操作")
                return
            
            if 1 <= choice <= len(configs):
                config_index = choice - 1
                config = configs[config_index]
                
                # 检查配置中是否有商品
                if not config.products:
                    print(f"❌ 配置 '{config.name}' 中没有商品，请先添加商品")
                    input("按Enter键返回...")
                    return
                
                # 进入扫货准备页面
                await self.show_scan_preparation_page(config)
            else:
                print("❌ 无效的选择")
        except ValueError:
            print("❌ 请输入有效的数字")

    async def execute_infinite_scan(self, config):
        """执行无限轮询扫货 - 多账户架构（完整版）"""
        print(f"\n{'='*70}")
        print(f"           C5GAME 多账户扫货系统")
        print(f"{'='*70}")
        
        # 1. 获取所有账户
        all_accounts_data = self.account_manager.get_all_accounts()
        if not all_accounts_data:
            print("❌ 没有找到任何账户")
            input("按Enter键返回...")
            return
        
        print(f"配置名称: {config.name}")
        print(f"商品数量: {len(config.products)}")
        print(f"找到账户数: {len(all_accounts_data)} 个")
        
        # 2. 创建商品池（从配置中提取商品ID）
        product_pool = [item.item_id for item in config.products]
        
        # 3. 创建全局查询调度器
        print(f"\n📅 正在创建查询调度器...")
        query_scheduler = QueryScheduler(product_pool, min_cooldown=0.1)
        QueryCoordinator.set_global_scheduler(query_scheduler)
        print(f"✅ 查询调度器创建完成，商品池大小: {len(product_pool)}")
        
        # 4. 创建多账户协调器
        print(f"🤝 正在创建多账户协调器...")
        multi_account_coordinator = MultiAccountCoordinator()
        print(f"✅ 多账户协调器创建完成")
        
        # 5. 批量加载所有账户到协调器
        loaded_accounts = []
        failed_accounts = []
        print(f"\n🔧 正在批量加载所有账户...")
        print("-" * 60)
        
        for i, account_data in enumerate(all_accounts_data, 1):
            try:
                user_id = account_data.get('userId')
                if not user_id:
                    print(f"❌ [{i}] 跳过无用户ID的账户")
                    failed_accounts.append(f"账户{i}: 无用户ID")
                    continue
                
                account_name = account_data.get('name', f"用户{user_id}")
                print(f"[{i}] 正在加载: {account_name} (ID: {user_id})", end="")
                
                # 为每个账户创建独立的账户管理器
                account_manager = AccountManager()
                
                # 加载账户数据
                print("...", end="", flush=True)
                loaded_manager = await account_manager.load_account_by_id(user_id)
                
                if loaded_manager:
                    print(" ✅")
                    
                    try:
                        # 分离查询和购买注册逻辑
                        account_name = account_manager.get_account_name()
                        has_api_key = account_manager.has_api_key()
                        is_logged_in = account_manager.login_status

                        print(f"   🔍 检查账户状态...", end="", flush=True)

                        if has_api_key:
                            print(" ✅ (有API Key)")
                            
                            # 只要有API Key，就尝试创建查询组
                            print(f"   📦 创建查询组...", end="", flush=True)
                            try:
                                product_success = await multi_account_coordinator.add_products_to_account(
                                    account_manager,
                                    config.products,
                                    config.name
                                )
                                
                                if product_success:
                                    print(" ✅")
                                    
                                    # 如果已登录，再注册购买功能
                                    if is_logged_in:
                                        print(f"   🛒 注册购买功能...", end="", flush=True)
                                        purchase_success = multi_account_coordinator.register_account(account_manager)
                                        if purchase_success:
                                            print(" ✅")
                                            loaded_accounts.append({
                                                'id': user_id,
                                                'name': account_name,
                                                'manager': account_manager,
                                                'can_purchase': True,
                                                'can_query': True,
                                                'query_type': 'API'
                                            })
                                            print("   ✅ 账户初始化完成 (查询+购买)")
                                        else:
                                            print(" ⚠️")
                                            loaded_accounts.append({
                                                'id': user_id,
                                                'name': account_name,
                                                'manager': account_manager,
                                                'can_purchase': False,
                                                'can_query': True,
                                                'query_type': 'API'
                                            })
                                            print("   ✅ 账户初始化完成 (仅查询)")
                                    else:
                                        # 未登录但有API Key：只创建查询组，不注册购买
                                        loaded_accounts.append({
                                            'id': user_id,
                                            'name': account_name,
                                            'manager': account_manager,
                                            'can_purchase': False,
                                            'can_query': True,
                                            'query_type': 'API (未登录)'
                                        })
                                        print("   ✅ 账户初始化完成 (仅API查询)")
                                        
                                else:
                                    print(" ❌")
                                    failed_accounts.append(f"{account_name}: 创建查询组失败")
                                    
                            except Exception as e:
                                print(f" ❌ 错误: {e}")
                                failed_accounts.append(f"{account_name}: {str(e)[:50]}...")
                                
                        elif is_logged_in:
                            # 已登录但没有API Key：只能使用浏览器查询
                            print(" ⚠️ (已登录但无API Key)")
                            
                            print(f"   📦 创建浏览器查询组...", end="", flush=True)
                            try:
                                product_success = await multi_account_coordinator.add_products_to_account(
                                    account_manager,
                                    config.products,
                                    config.name
                                )
                                
                                if product_success:
                                    print(" ✅")
                                    
                                    # 注册购买功能
                                    print(f"   🛒 注册购买功能...", end="", flush=True)
                                    purchase_success = multi_account_coordinator.register_account(account_manager)
                                    if purchase_success:
                                        print(" ✅")
                                        loaded_accounts.append({
                                            'id': user_id,
                                            'name': account_name,
                                            'manager': account_manager,
                                            'can_purchase': True,
                                            'can_query': True,
                                            'query_type': '浏览器'
                                        })
                                        print("   ✅ 账户初始化完成 (浏览器查询+购买)")
                                    else:
                                        print(" ⚠️")
                                        loaded_accounts.append({
                                            'id': user_id,
                                            'name': account_name,
                                            'manager': account_manager,
                                            'can_purchase': False,
                                            'can_query': True,
                                            'query_type': '浏览器'
                                        })
                                        print("   ✅ 账户初始化完成 (仅浏览器查询)")
                                else:
                                    print(" ❌")
                                    failed_accounts.append(f"{account_name}: 创建查询组失败")
                                    
                            except Exception as e:
                                print(f" ❌ 错误: {e}")
                                failed_accounts.append(f"{account_name}: {str(e)[:50]}...")
                                
                        else:
                            # 既未登录又无API Key：完全无法使用
                            print(" ❌ (未登录且无API Key)")
                            failed_accounts.append(f"{account_name}: 未登录且无API Key")
                            
                    except Exception as init_error:
                        print(f" ❌ 初始化错误: {init_error}")
                        failed_accounts.append(f"{account_name}: {str(init_error)[:50]}...")
                else:
                    print(" ❌")
                    print(f"    → 账户加载失败")
                    failed_accounts.append(f"{account_name}: 加载失败")
                    
            except Exception as e:
                print(f"\n[{i}] ❌ 加载失败: {e}")
                failed_accounts.append(f"账户{i}: {str(e)[:50]}...")
        
        print("-" * 60)
        
        # 显示加载结果
        if not loaded_accounts:
            print("❌ 没有成功加载任何账户")
            if failed_accounts:
                print("失败原因:")
                for fail in failed_accounts:
                    print(f"  - {fail}")
            input("按Enter键返回...")
            return
        
        print(f"\n✅ 成功加载 {len(loaded_accounts)}/{len(all_accounts_data)} 个账户")
        if failed_accounts:
            print(f"❌ 失败账户: {len(failed_accounts)} 个")
            print("失败原因:")
            for fail in failed_accounts[:5]:  # 只显示前5个失败原因
                print(f"  - {fail}")
            if len(failed_accounts) > 5:
                print(f"  ... 还有 {len(failed_accounts)-5} 个失败账户")
        
        # 6. 启动多账户购买协调器
        start_success = await multi_account_coordinator.start_all()
        if not start_success:
            print("❌ 启动多账户购买协调器失败")
            input("按Enter键返回...")
            return
        
        # 7. 启动全局查询调度器
        print(f"📅 正在启动查询调度器...")
        await QueryCoordinator.start_global_scheduler()
        
        print(f"\n🚀 多账户扫货系统已启动！")
        print(f"{'='*70}")
        print(f"📊 系统配置:")
        print(f"   调度器类型: 时间预约调度器")
        print(f"   商品池大小: {len(product_pool)} 个商品")
        print(f"   已加载账户: {len(loaded_accounts)} 个")
        
        # 计算总查询组数量
        total_groups = 0
        new_groups = 0
        old_groups = 0
        
        # 从全局查询协调器获取所有组
        all_groups = QueryCoordinator.get_all_groups()
        if isinstance(all_groups, dict):
            for group_id, group in all_groups.items():
                if hasattr(group, 'group_type'):
                    if group.group_type == "new":
                        new_groups += 1
                    elif group.group_type == "old":
                        old_groups += 1
            total_groups = len(all_groups)
        
        print(f"   查询组数量: {total_groups} 个 (新:{new_groups} 旧:{old_groups})")
        
        # 获取购买调度器统计
        if hasattr(multi_account_coordinator, 'scheduler'):
            try:
                purchase_stats = multi_account_coordinator.scheduler.get_stats()
                available = purchase_stats.get('available_accounts', 0)
                total = purchase_stats.get('total_accounts', 0)
                print(f"   可用购买账户: {available}/{total}")
            except:
                print(f"   购买账户状态: 无法获取")
                
        print(f"\n📋 账户列表:")
        print("-" * 50)
        
        for i, acc in enumerate(loaded_accounts, 1):
            account_manager = acc['manager']
            can_purchase = acc.get('can_purchase', False)
            can_query = acc.get('can_query', False)
            query_type = acc.get('query_type', '未知')
            
            # 检查是否有库存
            has_inventory = account_manager.has_available_inventory()
            
            # 查询状态图标
            if can_query:
                query_icon = "🔍"
                if "API" in query_type:
                    query_text = "API查询"
                elif "浏览器" in query_type:
                    query_text = "浏览器查询"
                else:
                    query_text = "查询"
            else:
                query_icon = "🚫"
                query_text = "无查询"
            
            # 购买状态图标
            if can_purchase:
                purchase_icon = "🛒"
                purchase_text = "有购买权限"
            else:
                purchase_icon = "🚫"
                purchase_text = "无购买权限"
            
            # 库存状态
            if has_inventory:
                inventory_text = "🏭有库存"
            else:
                inventory_text = "🚫无库存"
            
            # 时间窗口状态
            time_config = account_manager.get_query_time_config()
            if time_config['enabled']:
                start_str = f"{time_config['start_hour']:02d}:{time_config['start_minute']:02d}"
                end_str = f"{time_config['end_hour']:02d}:{time_config['end_minute']:02d}"
                time_text = f"⏰{start_str}-{end_str}"
            else:
                time_text = "未启用"
            
            print(f"{i:2d}. {acc['name'][:15]:<15} {query_icon}{query_text:<8} {purchase_icon}{purchase_text:<8} {inventory_text:<8} {time_text}")
        
        print(f"{'='*70}")
        print(f"💡 提示: 按Ctrl+C停止扫货")
        print(f"{'='*70}")
        
        start_time = time.time()
        last_stats_time = start_time #开始时间
        last_clear_time = start_time # 清屏时间记录
        
        try:
            # 主运行循环
            while True:
                current_time = time.time()
                elapsed_seconds = int(current_time - start_time)
                if current_time - last_clear_time >= 2.0:
                    # 清屏（移动光标到开头）
                    print("\033[H\033[J", end="")
                    last_clear_time = current_time
                # 每60秒显示一次精简状态
                if current_time - last_stats_time >= 60.0:
                    
                    
                    print(f"{'='*60}")
                    print(f"📈 C5GAME多账户扫货系统 - 运行 {elapsed_seconds//60:02d}:{elapsed_seconds%60:02d}")
                    print(f"{'='*60}")
                    
                    # 查询调度器状态
                    scheduler = QueryCoordinator.get_global_scheduler()
                    if scheduler:
                        stats = scheduler.get_stats()
                        if stats['running']:
                            print(f"📅 查询调度器: ✅运行中")
                            print(f"   商品池: {stats['product_pool_size']}个商品")
                            print(f"   可用商品: {stats['available_products']}个")
                            print(f"   冷却商品: {stats['cooling_products']}个")
                            print(f"   待执行任务: {stats['scheduled_tasks']}个")
                    
                    # 查询组统计
                    groups = QueryCoordinator.get_all_groups()
                    if groups:
                        new_groups = [g for g in groups.values() if hasattr(g, 'group_type') and g.group_type == "new"]
                        old_groups = [g for g in groups.values() if hasattr(g, 'group_type') and g.group_type == "old"]
                        
                        active_new = sum(1 for g in new_groups if g.get_stats().get('running', False))
                        active_old = sum(1 for g in old_groups if g.get_stats().get('running', False))
                        
                        total_queries = sum(g.get_stats().get('query_count', 0) for g in groups.values() if hasattr(g, 'get_stats'))
                        total_found = sum(g.get_stats().get('found_count', 0) for g in groups.values() if hasattr(g, 'get_stats'))
                        
                        print(f"🔍 查询组: {len(groups)}个 (新:{len(new_groups)}/{active_new}活跃 旧:{len(old_groups)}/{active_old}活跃)")
                        print(f"   总查询: {total_queries}次, 发现商品: {total_found}次")
                        print(f"   查询频率: {total_queries/elapsed_seconds:.1f}次/秒")
                    
                    # 购买调度器状态
                    if hasattr(multi_account_coordinator, 'scheduler'):
                        try:
                            purchase_stats = multi_account_coordinator.scheduler.get_stats()
                            available = purchase_stats.get('available_accounts', 0)
                            total = purchase_stats.get('total_accounts', 0)
                            
                            print(f"🛒 购买调度器:")
                            print(f"   可用账户: {available}/{total}")
                            print(f"   任务队列: {purchase_stats.get('queue_size', 0)}批次")
                            print(f"   成功购买: {purchase_stats.get('total_purchased', 0)}件")
                            print(f"   缓存条目: {purchase_stats.get('cache_size', 0)}个")
                        except:
                            print(f"🛒 购买调度器: 状态获取失败")
                    print(f"{'='*60}")
                    print(f"💡 按Ctrl+C停止 ")
                    
                    last_stats_time = current_time
                
                
                
                await asyncio.sleep(0.5)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 用户中断扫货")
        except Exception as e:
            print(f"\n\n❌ 扫货过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 停止所有组件
            print(f"\n{'='*70}")
            print(f"🛑 正在安全停止所有组件...")
            print(f"{'='*70}")
            
            # 1. 停止多账户协调器
            try:
                print(f"⏹️  停止多账户协调器...", end="", flush=True)
                await multi_account_coordinator.stop_all()
                print(" ✅")
            except Exception as e:
                print(f" ❌ 出错: {e}")
            
            # 2. 停止全局查询调度器
            try:
                print(f"⏹️  停止查询调度器...", end="", flush=True)
                await QueryCoordinator.stop_global_scheduler()
                print(" ✅")
            except Exception as e:
                print(f" ❌ 出错: {e}")
            
            # 3. 关闭所有账户的session
            print(f"🔌 正在关闭所有账户连接...")
            close_count = 0
            for account_info in loaded_accounts:
                try:
                    await account_info['manager'].close_global_session()
                    await account_info['manager'].close_api_session()
                    close_count += 1
                    print(f"  ✅ 已关闭 {account_info['name']}")
                except Exception as e:
                    print(f"  ❌ 关闭账户 {account_info['name']} 失败: {e}")
            
            print(f"✅ 已关闭 {close_count}/{len(loaded_accounts)} 个账户的连接")
            
            # 4. 显示最终统计
            elapsed = time.time() - start_time
            elapsed_minutes = elapsed / 60
            
            print(f"\n{'='*70}")
            print(f"🎉 扫货任务完成")
            print(f"{'='*70}")
            print(f"⏱️  总运行时间: {elapsed_minutes:.1f} 分钟 ({elapsed:.0f}秒)")
            print(f"👥 账户统计: {len(loaded_accounts)}/{len(all_accounts_data)} 个成功加载")
            print(f"📊 商品配置: {config.name} ({len(config.products)}个商品)")
            
            # 获取最终购买统计
            if hasattr(multi_account_coordinator, 'scheduler'):
                try:
                    final_stats = multi_account_coordinator.scheduler.get_stats()
                    available = final_stats.get('available_accounts', 0)
                    total = final_stats.get('total_accounts', 0)
                    
                    print(f"🛒 购买统计:")
                    print(f"   可用账户: {available}/{total}")
                    print(f"   成功购买: {final_stats.get('total_purchased', 0)} 件商品")
                    print(f"   剩余队列: {final_stats.get('queue_size', 0)} 批次")
                    print(f"   缓存命中: {final_stats.get('cache_size', 0)} 条")
                except:
                    print(f"🛒 购买统计: 无法获取")
            
            # 查询统计
            groups = QueryCoordinator.get_all_groups()
            if groups:
                total_queries = sum(g.get_stats().get('query_count', 0) for g in groups.values() if hasattr(g, 'get_stats'))
                total_found = sum(g.get_stats().get('found_count', 0) for g in groups.values() if hasattr(g, 'get_stats'))
                print(f"🔍 查询统计:")
                print(f"   总查询次数: {total_queries}")
                print(f"   发现商品次数: {total_found}")
                if elapsed > 0:
                    print(f"   平均查询频率: {total_queries/elapsed:.1f} 次/秒")
            
            print(f"{'='*70}")
            
            input("\n按Enter键返回主菜单...")


    async def _display_real_time_stats(self, coordinator, start_time):
        """显示实时统计"""
        stats = coordinator.get_stats()
        elapsed = time.time() - start_time
        
        print(f"\r📊 实时统计 | 运行: {elapsed:.0f}s | 队列: {stats['queue_size']} | "
            f"账户: {stats['available_accounts']}/{stats['total_accounts']} | "
            f"购买: {stats['total_purchased']}件", end="", flush=True)
        
    async def _display_final_stats(self, coordinator, start_time, config):
        """显示最终统计"""
        elapsed = time.time() - start_time
        elapsed_minutes = elapsed / 60
        
        stats = coordinator.get_stats()
        
        print(f"\n{'='*70}")
        print(f"📊 扫货完成统计")
        print(f"{'='*70}")
        print(f"总运行时间: {elapsed_minutes:.1f} 分钟")
        print(f"总账户数: {stats['total_accounts']} 个")
        print(f"可用账户: {stats['available_accounts']} 个")
        print(f"禁用账户: {stats['disabled_accounts']} 个")
        print(f"成功购买: {stats['total_purchased']} 件商品")
        print(f"队列剩余: {stats['queue_size']} 批次")
        
        # 显示商品统计
        print(f"\n📦 商品统计:")
        for product in config.products:
            print(f"  - {product.item_name or product.item_id}")
        
        print(f"{'='*70}")

    def get_user_input(self, product_info):
        """获取用户输入"""
        print("\n" + "=" * 60)
        print("                   参数设置")
        print("=" * 60)
        
        # 从product_info获取完整磨损范围
        db_minwear = product_info.get("minwear")
        db_maxwear = product_info.get("maxwear")
        
        if db_minwear is None or db_maxwear is None:
            print("❌ 无法获取完整的磨损值")
            return None
        
        print(f"📏 商品完整磨损范围: {db_minwear:.2f} ~ {db_maxwear:.2f}")
        print("💡 提示：最小磨损将自动使用最佳值")
        print(f"💡 自动设置最小磨损为: {db_minwear:.2f}")
        print("=" * 60)
        
        # 自动使用数据库的 minwear 作为最佳磨损
        minwear = float(f"{db_minwear:.2f}")
        
        # 只让用户输入最大磨损值
        while True:
            max_wear_input = input(f"请输入最高接受磨损值 (范围: {db_minwear:.2f}~{db_maxwear:.2f}): ").strip()
            
            if not max_wear_input:
                print("❌ 输入不能为空")
                continue
            
            try:
                # 转换为浮点数并保留2位小数
                max_wear_float = float(max_wear_input)
                max_wear = float(f"{max_wear_float:.2f}")
                
                # 验证是否在合理范围内
                if not (db_minwear < max_wear <= db_maxwear):
                    print(f"❌ 最大磨损值({max_wear:.2f})必须在范围 ({db_minwear:.2f}, {db_maxwear:.2f}] 内")
                    continue
                
                print(f"✅ 最大磨损值: {max_wear:.2f}")
                break
                
            except ValueError:
                print("❌ 请输入有效的数字")
        
        # 获取扫货价
        while True:
            max_price_input = input("请输入扫货价 (例如: 100.5): ").strip()
            
            if not max_price_input:
                print("❌ 输入不能为空")
                continue
            
            try:
                max_price_float = float(max_price_input)
                max_price = float(f"{max_price_float:.2f}")
                
                if max_price <= 0:
                    print("❌ 扫货价必须大于0")
                    continue
                
                print(f"✅ 扫货价: {max_price:.2f}")
                break
                
            except ValueError:
                print("❌ 请输入有效的数字")
        
        print("=" * 60)
        print(f"📊 参数设置完成:")
        print(f"  自动设置最小磨损（最佳值）: {minwear:.2f}")
        print(f"  用户设置最大磨损: {max_wear:.2f}")
        print(f"  用户设置扫货价: {max_price:.2f}")
        print("=" * 60)
        
        return {
            'minwear': minwear,      # 自动使用数据库的最佳值
            'max_wear': max_wear,    # 用户输入
            'max_price': max_price   # 用户输入
        } 
    
    def exit_program(self):
        """退出程序"""
        print("\n感谢使用C5GAME商品配置管理系统！")
        print("程序即将退出...")
        self.running = False
    
    async def run(self):
        """运行主程序 """
        self.display_header()
        
        
        while self.running:
            choice = self.display_main_menu()
            
            if choice == '1':
                await self.handle_cookie_menu()
            elif choice == '2':
                await self.product_config_management()
            elif choice == '3':
                self.exit_program()
            else:
                print("❌ 无效选择，请重新输入")

#  主程序入口 
async def main():
    """主程序入口"""
    print("           C5GAME商品配置管理系统")
    
    # 初始化UI管理器
    ui_manager = UIManager()
    
    try:
        # 1. 初始化数据库
        if not initialize_database():
            print("❌ 数据库初始化失败，程序无法继续")
            return          
        
        # 2. 检查账户数量（不自动加载）
        accounts = ui_manager.account_manager.get_all_accounts()
        if accounts:
            print(f"📊 系统状态: 发现 {len(accounts)} 个账户")
            print("-" * 50)
            
            # 显示账户列表（简略信息）
            for i, acc in enumerate(accounts, 1):
                name = acc.get('name', f"账户{i}")
               #user_id = acc.get('userId', '未知')
                api_key = "🔑 有API" if acc.get('api_key') else "❌ 无API"
                created = acc.get('created_at', '未知')
                login_status = "✅ 已登录" if acc.get('login') else "❌ 未登录"
                # 显示简略信息
                print(f"  {i:2d}. {name[:20]:<20} {api_key:<8} 登录: {login_status:<10} 创建: {created}")
            
            print("-" * 50)
            print("💡 提示: 在扫货时会自动加载所有账户")
        else:
            print("⚠️  警告: 没有找到任何账户")
            print("     请在主菜单选择 1.账户管理 -> 1.Selenium自动登录新增账户")
        
        print() 
        
        # 3. 检查商品配置
        config_manager = ProductConfigManager()
        configs = config_manager.get_all_configs()
        if configs:
            print(f"📁 发现 {len(configs)} 个商品配置")
        else:
            print("⚠️  没有商品配置，请先创建配置")
        
        print()  # 空行
        
        # 4. 运行主循环
        await ui_manager.run()
        
    except KeyboardInterrupt:
        print("\n🛑 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("正在清理资源...")
        
        # 关键修复：等待所有异步任务完成
        try:
            # 获取所有未完成的任务（除了当前任务）
            tasks = [t for t in asyncio.all_tasks() 
                    if t is not asyncio.current_task()]
            
            if tasks:
                print(f"🔄 正在取消 {len(tasks)} 个未完成的任务...")
                # 取消所有任务
                for task in tasks:
                    task.cancel()
                
                # 等待任务取消完成（设置超时避免无限等待）
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=3.0  # 最多等待3秒
                    )
                    print("✅ 所有任务已安全取消")
                except asyncio.TimeoutError:
                    print("⚠️  部分任务取消超时，强制继续清理")
                except Exception as e:
                    print(f"⚠️  等待任务取消时出错: {e}")
        except Exception as e:
            print(f"⚠️  取消任务时出错: {e}")
        
        # 5. 清理资源（现在可以安全执行）
        try:
            await QueryCoordinator.stop_global_scheduler()
            print("✅ 调度器已停止")
        except Exception as e:
            print(f"⚠️  停止调度器时出错: {e}")
        
        # 关闭Session
        try:
            await ui_manager.account_manager.close_global_session()
            print("✅ Global Session已关闭")
        except Exception as e:
            print(f"⚠️  关闭global session时出错: {e}")
            
        try:
            await ui_manager.account_manager.close_api_session()
            print("✅ API Session已关闭")
        except Exception as e:
            print(f"⚠️  关闭api session时出错: {e}")
        
        print("✅ 程序已安全退出")



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"程序运行出错: {e}")     

def signal_handler(signum):
    """处理退出信号"""
    print(f"\n📡 接收到退出信号 {signum}，正在退出...")
    
# 注册信号处理（只在直接运行主程序时）
if __name__ == "__main__":
    # 注册Ctrl+C信号处理
    
    # 运行主程序
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"\n💥 程序崩溃: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

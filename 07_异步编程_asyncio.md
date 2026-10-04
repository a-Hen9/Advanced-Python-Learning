# 第 7 章 异步编程 asyncio

> **本章目标**：建立"单线程事件循环"的心智模型；掌握 async/await、Task、gather/TaskGroup 的并发组织方式；学会异步超时与并发数控制；理解"协程里绝不能阻塞"的深层原因，并能规避常见错误。
>
> 前置：第 2 章生成器（协程的前身）、第 5 章 GIL（为什么 asyncio 不加速 CPU）。

---

## 7.1 心智模型：一个勤快的服务员

同步模型像**一个服务员盯一桌客人从点菜到结账**，期间干不了别的；多线程像**雇很多服务员**，人多了有管理成本；asyncio 则是**一个服务员同时招呼几十桌**——谁在等菜（IO），就先去照顾别人，菜好了（事件就绪）再回来上菜：

```
同步:    任务A [请求1][等待.........][响应1][请求2][等待.........][响应2]   总时长 = 累加
asyncio: 任务A [请求1]      [响应1]
         任务B   [请求2]      [响应2]                                        总时长 ≈ 最慢的那个
          ↑ 等待期间事件循环切换去执行其他任务
```

三个关键词：

1. **单线程**：整个程序只有一个线程（协程之间是"协作式"让出，不存在第 5 章的竞态条件）；
2. **事件循环**：一个 while 循环，不断问"哪个 socket 有数据了？哪个定时器到点了？"然后把 CPU 分给对应协程；
3. **await = 让出控制权**：`await` 的地方是协程唯一可能被切换的点——这也是 asyncio 代码"线程安全"的原因：**没有 await 的代码段是原子的**。

适用判断：**等待多、每次等待期间没多少计算 → asyncio 封神（千级并发连接）；CPU 计算 → 该用多进程（第 6 章）。**

## 7.2 基础语法

### 7.2.1 协程函数与 await

```python
import asyncio

async def fetch_data(delay: float) -> str:
    """async def 定义协程函数；调用它返回协程对象，并不执行！"""
    print(f"开始请求（等待 {delay}s）")
    await asyncio.sleep(delay)       # await：让出控制权给事件循环
    print("数据到达")
    return "数据"

async def main():
    result = await fetch_data(1.0)   # await 才真正执行协程，拿到返回值
    print("得到:", result)

asyncio.run(main())                  # 事件循环的启动入口（程序里只调用一次）
# 开始请求（等待 1.0s）
# 数据到达
# 得到: 数据
```

三条铁规则：

1. `async def` 函数**必须被 await（或包装成 Task）才会执行**，直接调用只创建协程对象（忘 await 会得到 `RuntimeWarning: coroutine ... was never awaited`）。
2. `await` 只能出现在 `async def` 内部。
3. **await 后面必须是 awaitable**：协程、Task、Future，或支持 `__await__` 的对象。

### 7.2.2 并发执行：顺序 await ≠ 并发

初学者最大误区：连续 `await` 是**串行**的：

```python
async def main_bad():
    await fetch_data(1)      # 先等 1s
    await fetch_data(2)      # 再等 2s     总计 3s —— 并没有并发！

async def main_good():
    # 方式一：gather —— 最常用
    results = await asyncio.gather(
        fetch_data(1),
        fetch_data(2),
        fetch_data(3),
    )
    print(results)           # ['数据', '数据', '数据']，总耗时 ≈ 2s（最慢者）

    # 方式二：create_task —— 立刻"点火"让协程跑起来，之后随时 await
    task = asyncio.create_task(fetch_data(5))    # 已在后台运行
    await asyncio.sleep(1)                        # 此期间 fetch_data(5) 也在推进
    print("先干点别的...")
    print(await task)                             # 等 task 完成
```

`gather(return_exceptions=True)` 会把异常作为结果收集而不是中断整批；默认（False）则一个失败立即抛出（其余任务并不会被取消——这是 gather 的著名陷阱）。

### 7.2.3 TaskGroup：结构化并发（Python 3.11+，推荐）

```python
async def main():
    async with asyncio.TaskGroup() as tg:            # 3.11+
        t1 = tg.create_task(fetch_data(1))
        t2 = tg.create_task(fetch_data(2))
    # 离开 async with 时：要么全部成功，要么全部取消——不可能漏网
    print(t1.result(), t2.result())

    # 任一任务抛异常 → 退出块时抛 ExceptionGroup，且其他任务已被自动取消
```

对比 gather，TaskGroup 的"块内任务全生命周期受管"正是**结构化并发**思想：没有孤儿任务、没有泄漏的后台协程。3.11+ 的新项目优先用它。

### 7.2.4 超时控制

```python
# 方式一：wait_for（经典）
try:
    result = await asyncio.wait_for(fetch_data(10), timeout=2.0)
except TimeoutError:                       # 3.11+ 原生 TimeoutError
    print("超时，任务已被取消")

# 方式二：asyncio.timeout 上下文管理器（3.11+，可包住多个 await）
async with asyncio.timeout(2.0):
    r1 = await fetch_data(1)
    r2 = await fetch_data(5)               # r1 耗掉 1s 预算，r2 将超时
```

## 7.3 异步生态：与阻塞势不两立

### 7.3.1 大敌当前：协程里的阻塞调用

事件循环是单线程的——**任何协程阻塞超过几毫秒，所有任务全部停摆**：

```python
async def bad():
    time.sleep(2)                # 灾难！同步 sleep 阻塞整个循环，其他任务全卡
    requests.get(url)            # 同样灾难：同步 HTTP 库
    with open("big.bin", "rb") as f:  # 小文件尚可，大文件 IO 同样阻塞
        f.read()

async def good():
    await asyncio.sleep(2)               # 异步 sleep：让出控制权
    await asyncio.to_thread(requests.get, url)   # 3.9+：把阻塞调用丢进线程池
    result = await loop.run_in_executor(None, cpu_func)  # CPU 任务丢进程池更佳
```

异步生态的正确姿势：HTTP 用 `httpx`（async 模式）或 `aiohttp`、数据库用 `asyncpg`/`aiomysql`/异步 ORM（SQLAlchemy 2.0 async）、文件用 `aiofiles`。**混用同步库是 asyncio 第一大坑**——排查方法：程序"卡死但 CPU 空闲"，八成是某处同步阻塞。

### 7.3.2 异步 HTTP 并发下载（需 `pip install httpx`）

```python
import asyncio
import httpx

async def fetch(client: httpx.AsyncClient, url: str) -> tuple[str, int]:
    resp = await client.get(url)
    return url, resp.status_code

async def main():
    urls = [f"https://httpbin.org/delay/1" for _ in range(10)]
    async with httpx.AsyncClient(timeout=10) as client:   # 复用连接池
        results = await asyncio.gather(
            *(fetch(client, u) for u in urls), return_exceptions=True
        )
    for r in results:
        print(r if not isinstance(r, Exception) else f"失败: {r}")

asyncio.run(main())
# 10 个"各等 1 秒"的请求，总耗时约 1~2 秒（而非 10 秒+）
```

### 7.3.3 并发数限制：Semaphore

不设限地 gather 一万个请求 = 自己打出 DDoS。信号量限流：

```python
sem = asyncio.Semaphore(10)                  # 最多 10 个并发请求

async def bounded_fetch(client, url):
    async with sem:                          # 拿不到令牌就排队
        return await fetch(client, url)

# results = await asyncio.gather(*(bounded_fetch(client, u) for u in urls))
```

## 7.4 异步迭代器与异步上下文管理器

async 版协议与第 2/3 章的同步协议一一对应：

```python
import asyncio

class AsyncTicker:
    """异步迭代器：每秒产出一个计数（async for 消费）"""
    def __init__(self, stop):
        self.stop, self.i = stop, 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.i >= self.stop:
            raise StopAsyncIteration
        await asyncio.sleep(0.5)
        self.i += 1
        return self.i

async def main():
    async for tick in AsyncTicker(3):
        print("tick", tick)

    # 异步上下文管理器：__aenter__ / __aexit__
    # async with httpx.AsyncClient() as client: ...   ← 前面已经在用

asyncio.run(main())
```

异步生成器（`async def` + `yield`）可以直接写 `async for` 的数据源；注意它需要 `contextlib.aclosing()` 或显式 `aclose()` 做清理。

## 7.5 实战：带限流、超时、重试的并发抓取器

```python
import asyncio
import random
from dataclasses import dataclass

@dataclass
class Result:
    url: str
    ok: bool
    detail: str

async def fetch_once(url: str, sem: asyncio.Semaphore) -> str:
    async with sem:
        # 用纯标准库模拟一次"网络请求"（真实场景替换为 httpx）
        await asyncio.sleep(random.uniform(0.1, 0.8))
        if random.random() < 0.3:
            raise ConnectionError("模拟网络抖动")
        return f"{url} 的内容({len(url) * 100} bytes)"

async def fetch_with_retry(url: str, sem: asyncio.Semaphore,
                           retries: int = 3) -> Result:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with asyncio.timeout(1.0):          # 单次尝试 1s 超时
                body = await fetch_once(url, sem)
            return Result(url, True, body)
        except (TimeoutError, ConnectionError) as e:
            last_err = e
            await asyncio.sleep(0.2 * attempt)        # 指数退避的简化版
    return Result(url, False, f"重试 {retries} 次仍失败: {last_err}")

async def main():
    urls = [f"https://api.example.com/item/{i}" for i in range(15)]
    sem = asyncio.Semaphore(5)                        # 全局并发上限 5
    results = await asyncio.gather(
        *(fetch_with_retry(u, sem) for u in urls)
    )
    ok = [r for r in results if r.ok]
    print(f"成功 {len(ok)}/{len(results)}")
    for r in results:
        if not r.ok:
            print("失败:", r.url, r.detail)

if __name__ == "__main__":
    asyncio.run(main())
```

这个"**Semaphore 限流 + timeout 超时 + 重试退避 + gather 汇总**"的四件套，就是生产级异步 IO 任务的骨架。

## 7.6 常见陷阱清单

1. **忘记 await**：`fetch_data(1)` 直接调用什么都不会发生，只有 `RuntimeWarning` 提示。
2. **协程中调用阻塞函数**（`time.sleep`、`requests`、重 CPU 计算）：整个循环卡死。阻塞任务丢 `asyncio.to_thread`，CPU 任务丢进程池。
3. **顺序 await 误当并发**：`await a(); await b()` 是串行；并发用 gather/TaskGroup/create_task。
4. **gather 一个失败、其余任务成为孤儿**：需要"全有或全无"时用 TaskGroup 或 `return_exceptions=True` 后统一处理。
5. **一程序多次 `asyncio.run()` / 在已有循环里再 run**：`asyncio.run` 每次新建事件循环，一个程序通常只在入口调一次；库代码不要自己 run。
6. **无限 gather**：一万并发打爆自己与对方，务必 Semaphore 限流。
7. **在任务里引用了即将销毁的对象/忘记持引用**：`create_task` 返回的 Task 若不保存引用，可能被垃圾回收导致任务神秘消失——保存到集合或变量里。
8. **混用同步与异步世界**：同步框架（Flask）里调 async 函数、异步框架里调同步重库，都是事故源。

## 7.7 本章小结

- asyncio = **单线程 + 事件循环 + await 让出**；await 点是唯一的切换点，没有 await 的代码段天然原子。
- 并发组织：gather（简单批量）、TaskGroup（3.11+ 结构化并发，推荐）、create_task（后台点火）；超时用 `wait_for`/`asyncio.timeout`；限流用 Semaphore。
- 协程里**绝不阻塞**：同步库换异步库，或 `to_thread`/`run_in_executor` 委托；"CPU 密集 → 进程池"的边界永不改变。
- 四件套骨架（限流 + 超时 + 重试 + gather）覆盖绝大多数异步 IO 场景。

## 7.8 练习

1. 写一个异步"心跳监控器"：并发探测 20 个虚拟主机（`asyncio.sleep` 模拟 RTT），每 2 秒输出一轮存活率，用 `create_task` + 循环实现，Ctrl+C 可干净退出（提示：捕获 `KeyboardInterrupt`，`tg` 或 cancel 所有任务）。
2. 把 7.5 的抓取器改为"生产者-消费者"结构：一个协程生成 URL 放进 `asyncio.Queue`，5 个 worker 协程消费并抓取（对比 gather 与 Queue+worker 两种并发的适用差异）。
3. 用 `asyncio.as_completed` 实现 fastest-proxy：并发请求 5 个镜像源，谁先返回用谁的（对照第 5 章练习 2 的线程版）。
4. 故意制造一次阻塞事故：协程里放 `time.sleep(3)` 并同时跑 5 个任务，观察总耗时；再改为 `await asyncio.sleep(3)` 对比。把观察写进代码注释。
5. 思考题：asyncio 单线程为什么不怕竞态条件？什么情况下 asyncio 程序依然需要锁？（提示：`async with asyncio.Lock` 的存在意义——await 点之间仍可能交错）

package com.dhi.wha.utils;

import org.springframework.stereotype.Component;
import java.util.concurrent.*;

@Component
public class AsyncUtil {

    // 全局唯一的安全线程池，所有接口共用
    private static final ThreadPoolExecutor EXECUTOR;

    static {
        // 生产环境安全配置
        int corePoolSize = 10;
        int maximumPoolSize = 30;
        long keepAliveTime = 60L;
        TimeUnit unit = TimeUnit.SECONDS;
        BlockingQueue<Runnable> workQueue = new LinkedBlockingQueue<>(200);
        ThreadFactory threadFactory = Executors.defaultThreadFactory();
        RejectedExecutionHandler handler = new ThreadPoolExecutor.CallerRunsPolicy();

        EXECUTOR = new ThreadPoolExecutor(
                corePoolSize, maximumPoolSize, keepAliveTime, unit,
                workQueue, threadFactory, handler
        );
    }

    // 执行异步任务
    public static void execute(Runnable task) {
        EXECUTOR.submit(task);
    }

    /*
    * 1. **轻量异步辅助**：用于 Python 回调后的画像更新、学习行为日志写入、定时补偿小任务；
      2. **和 MQ 分工**：
        - MQ：处理视频、动画、大批量题库生成**重度耗时任务**；
        - AsyncUtil 线程池：处理回调解析、数据清洗、缓存更新等**轻量异步操作**；
      3. 价值：由你 Java 后端实现全局异步线程管理，统一管控系统所有异步逻辑，保障多智能体任务回调、学情数据落库稳定不阻塞主线程，是整套调度体系重要支撑。
    * */
}
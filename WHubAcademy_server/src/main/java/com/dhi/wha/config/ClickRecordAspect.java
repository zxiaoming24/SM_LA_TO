package com.dhi.wha.config;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.context.BaseContext;
import com.dhi.wha.entity.ResourceClick;
import com.dhi.wha.mapper.ResourceClickMapper;
import com.dhi.wha.utils.AsyncUtil;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.time.LocalDateTime;

@Slf4j
@Aspect
@Component
public class ClickRecordAspect {

    @Resource
    private ResourceClickMapper resourceClickMapper;

    @Around("@annotation(clickRecord)")
    public Object around(ProceedingJoinPoint joinPoint, ClickRecord clickRecord) throws Throwable {
        // 先执行原方法，不影响业务
        Object result = joinPoint.proceed();

        try {
            Long userId = BaseContext.getCurrentId();
            if (userId == null) return result;

            // 从方法参数中尝试提取资源ID，提取不到则默认为0（表示访问了该类型资源）
            MethodSignature signature = (MethodSignature) joinPoint.getSignature();
            String[] paramNames = signature.getParameterNames();
            Object[] args = joinPoint.getArgs();

            Long resourceId = 0L;
            for (int i = 0; i < paramNames.length; i++) {
                if (paramNames[i].equals(clickRecord.resourceIdParam())) {
                    try {
                        resourceId = Long.valueOf(args[i].toString());
                    } catch (NumberFormatException ignored) {
                    }
                    break;
                }
            }

            // 异步记录，不阻塞接口响应
            Long finalResourceId = resourceId;
            AsyncUtil.execute(() -> {
                try {
                    ResourceClick click = new ResourceClick();
                    click.setUserId(userId);
                    click.setResourceType(clickRecord.resourceType());
                    click.setResourceId(finalResourceId);
                    click.setClickTime(LocalDateTime.now());
                    resourceClickMapper.insert(click);
                } catch (Exception e) {
                    log.error("记录资源点击失败", e);
                }
            });
        } catch (Exception e) {
            log.error("点击记录切面异常", e);
        }

        return result;
    }
}

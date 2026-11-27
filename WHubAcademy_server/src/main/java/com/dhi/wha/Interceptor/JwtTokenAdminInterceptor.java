package com.dhi.wha.Interceptor;

import com.dhi.wha.constant.JwtClaimsConstant;
import com.dhi.wha.context.BaseContext;
import com.dhi.wha.properties.JwtProperties;
import com.dhi.wha.util.OnlineTimeUtil;
import com.dhi.wha.utils.JwtUtil;
import com.dhi.wha.mapper.UserOnlineMapper;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/**
 * jwt令牌校验的拦截器
 */
@Component
@Slf4j
public class JwtTokenAdminInterceptor implements HandlerInterceptor {

    @Autowired
    private JwtProperties jwtProperties;

    @Autowired
    private OnlineTimeUtil onlineTimeUtil; // 注入在线时长工具

    @Autowired
    private StringRedisTemplate stringRedisTemplate; // 注入Redis模板用于token黑名单校验

    /**
     * 校验jwt
     *
     * @param request
     * @param response
     * @param handler
     * @return
     * @throws Exception
     */
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        //判断当前拦截到的是 Controller 的方法还是其他资源
        if (!(handler instanceof HandlerMethod)) {
            //当前拦截到的不是动态方法，直接放行
            return true;
        }

        //1、从请求头中获取令牌
        String token = request.getHeader(jwtProperties.getAdminTokenName());

        //2、校验令牌
        try {
            log.info("jwt 校验:{}", token);
            Claims claims = JwtUtil.parseJWT(jwtProperties.getAdminSecretKey(), token);

            //3、检查token是否在黑名单中
            Boolean isBlacklisted = stringRedisTemplate.hasKey("token:blacklist:" + token);
            if (Boolean.TRUE.equals(isBlacklisted)) {
                log.warn("token已被拉黑，拒绝访问");
                response.setStatus(401);
                return false;
            }

            // 获取用户 ID 并设置到上下文
            Object empIdObj = claims.get(JwtClaimsConstant.EMP_ID);
            if (empIdObj != null) {
                Long empId = Long.valueOf(empIdObj.toString());
                log.info("当前员工 id：{}", empId);
                BaseContext.setCurrentId(empId);

                // ====================== 新增：记录在线时长 ======================
                // 只在JWT校验成功后记录，不影响原有逻辑
                onlineTimeUtil.recordActive(empId);
                // ==============================================================
            }

            return true;
        } catch (Exception ex) {
            log.error("jwt 校验失败：{}", ex.getMessage());
            //4、不通过，响应 401 状态码
            response.setStatus(401);
            return false;
        }
    }
}
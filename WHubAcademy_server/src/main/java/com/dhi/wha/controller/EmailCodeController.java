package com.dhi.wha.controller;

import com.dhi.wha.result.Result;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.Random;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/email")
public class EmailCodeController {

    // 邮件发送器
    @Resource
    private JavaMailSender mailSender;

    @Resource(name = "stringRedisTemplate")
    private StringRedisTemplate redisTemplate;

    // 邮箱验证码 前缀
    private static final String EMAIL_CODE_KEY = "email:code:";
    // 邮箱限流 前缀
    private static final String EMAIL_LIMIT_KEY = "email:limit:";
    // 验证码有效期 5分钟
    private static final int CODE_EXPIRE = 5;
    // 发送冷却 60秒
    private static final int LIMIT_EXPIRE = 60;

    /**
     * 发送邮箱验证码
     */
    @GetMapping("/sendCode")
    public Result sendEmailCode(@RequestParam String email) {
        // 1. 校验60秒限流
        Boolean limitHas = redisTemplate.hasKey(EMAIL_LIMIT_KEY + email);
        if (Boolean.TRUE.equals(limitHas)) {
            return Result.error("发送过于频繁，请60秒后再试");
        }

        // 2. 生成6位纯数字验证码
        String code = String.format("%06d", new Random().nextInt(1000000));

        // 3. 存入Redis：验证码 + 限流标记
        redisTemplate.opsForValue().set(EMAIL_CODE_KEY + email, code, CODE_EXPIRE, TimeUnit.MINUTES);
        redisTemplate.opsForValue().set(EMAIL_LIMIT_KEY + email, "1", LIMIT_EXPIRE, TimeUnit.SECONDS);

        // 4. 构建邮件内容
        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom("3924356197@qq.com"); // 和配置文件username一致
        message.setTo(email);
        message.setSubject("聚智优学 - 邮箱验证码");
        message.setText("您好！你的邮箱验证码为：" + code + "，有效期5分钟，请勿泄露。");

        // 5. 发送邮件
        try {
            mailSender.send(message);
            return Result.success("验证码发送成功");
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("邮件发送失败，请检查邮箱是否正确");
        }
    }

    /**
     * 校验邮箱验证码 工具方法
     * 登录/注册接口直接调用
     */
    public boolean checkEmailCode(String email, String inputCode) {
        String key = EMAIL_CODE_KEY + email;
        String realCode = redisTemplate.opsForValue().get(key);
        // 验证码不存在 / 过期 / 不一致
        if (realCode == null || !realCode.equals(inputCode)) {
            return false;
        }
        // 校验通过，删除验证码（一次性）
        redisTemplate.delete(key);
        return true;
    }
}

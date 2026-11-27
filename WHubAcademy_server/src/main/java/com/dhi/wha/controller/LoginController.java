package com.dhi.wha.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.dhi.wha.constant.JwtClaimsConstant;
import com.dhi.wha.dto.UserAdminApplyDTO;
import com.dhi.wha.dto.UserAdminUpdateDTO;
import com.dhi.wha.dto.UserDTO;
import com.dhi.wha.dto.UserInfoDTO;
import com.dhi.wha.dto.UserListQueryDTO;
import com.dhi.wha.entity.User;
import com.dhi.wha.server.UserOnlineService;
import com.dhi.wha.vo.UserAdminApplyVO;
import com.dhi.wha.properties.JwtProperties;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.LoginService;
import com.dhi.wha.server.UserAdminApplyService;
import com.dhi.wha.utils.JwtUtil;
import com.dhi.wha.vo.UserListVO;
import com.dhi.wha.vo.UserVO;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.bind.annotation.*;

import javax.servlet.http.HttpServletRequest;
import java.util.Date;
import java.util.concurrent.TimeUnit;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
public class LoginController {

    @Autowired
    private JwtProperties jwtProperties;

    @Resource
    private EmailCodeController emailCodeController;

    @Autowired
    private LoginService loginService;

    @Autowired
    private UserAdminApplyService userAdminApplyService;

    @Resource
    private UserOnlineService userOnlineService;

    @Autowired
    private com.dhi.wha.utils.PythonRestClient pythonRestClient;

    @Autowired
    private com.dhi.wha.mapper.LoginMapper loginMapper;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;


    /**
     * 登录
     */
    @PostMapping("/login")
    public Result<UserVO> login(@RequestBody UserDTO user) {
        log.info("用户登录：{}", user);
        User employee = loginService.login(user);

        //登录成功后，生成 jwt 令牌
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.EMP_ID, employee.getId());

        String token = JwtUtil.createJWT(
                jwtProperties.getAdminSecretKey(),
                jwtProperties.getAdminTtl(),
                claims);

       UserVO userVO = UserVO.builder()
                .id(employee.getId()) // 用户id
                .username(employee.getUsername())
                .isNew(employee.getIsNew())
                .tour(employee.getTour())
                .email(employee.getEmail())
                .avatar(employee.getAvatar())
                .isBuildProfile(employee.getIsBuildProfile())  //是否已经构建好画像
                .age(employee.getAge())
                .grade(employee.getGrade())
                .sex(employee.getSex())
                .major(employee.getMajor())
                .token(token)
                .type(employee.getType()) // 身份 0-管理员  1-学生  2-教师
                .build();

        // 发送用户昨日在线时长到Python端（仅老用户且有在线时长时才发送）
        Boolean isNew = employee.getIsNew();
        if (isNew == null || !isNew) {
            Long yesterdayDuration = userOnlineService.getYesterdayOnlineDuration(employee.getId());
            if (yesterdayDuration != null && yesterdayDuration > 0) {
                java.util.Map<String, Object> durationBody = new java.util.HashMap<>();
                durationBody.put("duration_seconds", yesterdayDuration);
                try {
                    pythonRestClient.postWithPathParam("/time-dimension/{user_id}/check-in", durationBody, employee.getId());
                    log.info("发送昨日在线时长到Python端成功, userId: {}, duration: {}秒", employee.getId(), yesterdayDuration);
                } catch (Exception e) {
                    log.warn("发送昨日在线时长到Python端失败, userId: {}", employee.getId(), e);
                }
            } else {
                log.info("用户昨日无在线时长，跳过发送, userId: {}", employee.getId());
            }
        } else {
            log.info("新用户跳过发送昨日在线时长, userId: {}", employee.getId());
        }

        return Result.success(userVO);
    }

    /**
     * 注册/忘记密码
     */
    @PostMapping("/register")
    public Result register(@RequestBody UserDTO user) {
        try {
            // 校验邮箱验证码
            boolean check = emailCodeController.checkEmailCode(user.getEmail(), String.valueOf(user.getVerificationCode()));
            if (!check) {
                return Result.error("验证码错误或已过期");
            }
            // 调用注册/忘记密码服务
            loginService.register(user);

            return Result.success("注册成功");
        }catch (Exception e){
            log.error("注册失败",e);
            return Result.error("注册失败");
        }
    }


    @PostMapping("/submitInfo")
    public Result insertInformation(@RequestBody UserInfoDTO userInfoDTO){
        log.info("insertInformation:信息完善");
        loginService.updateInformation(userInfoDTO);
        return Result.success();
    }

    /**
     * 用户列表筛选查询
     * @param queryDTO 查询条件
     * @return 分页用户列表
     */
    @PostMapping("/adUsersList")
    public Result<IPage<UserListVO>> getUserList(@RequestBody UserListQueryDTO queryDTO){
        log.info("用户列表筛选查询, queryDTO: {}", queryDTO);
        IPage<UserListVO> userList = loginService.getUserList(queryDTO);
        return Result.success(userList);
    }


    /**
     * 申请管理员
     * @param userAdminApplyDTO 申请管理员信息
     * @return
     */
    @PostMapping("/applyAdministrator")
    public Result<Object> applyAdministrator(
            @RequestBody UserAdminApplyDTO userAdminApplyDTO
            ){
        log.info("申请管理员, userAdminApplyDTO: {}", userAdminApplyDTO);
        loginService.applyAdministrator(userAdminApplyDTO);
        return Result.success();
    }


    /**
     * 接受管理员申请
     * @param userId 用户id
     * @return
     */
    @PutMapping("/acceptRequest/{userId}")
    public Result<Object> acceptRequest(
            @PathVariable Integer userId
    ){
        log.info("接受管理员申请");
        loginService.acceptRequest(userId);
        return Result.success();
    }


    /**
     * 拒绝管理员申请
     * @param userId 用户id
     * @return
     */
    @PutMapping("/rejectRequest/{userId}")
    public Result<Object> rejectRequest(
            @PathVariable Integer userId
    ){
        log.info("拒绝管理员申请");
        loginService.rejectRequest(userId);
        return Result.success();
    }


    /**
     * 获取管理员申请列表
     * @return
     */
    @GetMapping("/applyAdminList")
    public Result<Object> getApplyAdminList(){
        log.info("获取管理员申请列表");
        List<UserAdminApplyVO> userAdminApplyList = userAdminApplyService.getApplyAdminList();
        return Result.success(userAdminApplyList);
    }

    /**
     * 后台管理员修改用户信息
     * @param dto
     * @return
     */
    @PutMapping("/userInfoUpdate")
    public Result<Object> updateUserInfo(@RequestBody UserAdminUpdateDTO dto){
        log.info("后台管理员修改用户信息, dto: {}", dto);
        loginService.updateUserInfoByAdmin(dto);
        return Result.success();
    }

    /**
     * 删除用户
     * @param userId
     * @return
     */
    @DeleteMapping("/deleteUser/{userId}")
    public Result<Object> deleteUser(@PathVariable Long userId){
        log.info("删除用户, userId: {}", userId);
        loginService.deleteUser(userId);
        return Result.success();
    }

    /**
     * 重置密码
     * @param userId
     * @return
     */
    @PutMapping("/replacePwd/{userId}")
    public Result<Object> resetPassword(@PathVariable Long userId){
        log.info("重置密码, userId: {}", userId);
        loginService.resetPassword(userId);
        return Result.success();
    }

    /**
     * 退出登录
     * @param userId
     * @return
     */
    @PutMapping("/exit/{userId}")
    public Result<Object> logout(@PathVariable String userId, HttpServletRequest request){
        log.info("退出登录, userId: {}", userId);
        try {
            // 从请求头获取token
            String token = request.getHeader(jwtProperties.getAdminTokenName());
            if (token != null && !token.isEmpty()) {
                // 解析token获取过期时间
                Claims claims = JwtUtil.parseJWT(jwtProperties.getAdminSecretKey(), token);
                Date expiration = claims.getExpiration();
                long ttlMillis = expiration.getTime() - System.currentTimeMillis();

                if (ttlMillis > 0) {
                    // 将token加入黑名单，过期时间为token剩余有效期
                    stringRedisTemplate.opsForValue().set(
                            "token:blacklist:" + token,
                            "1",
                            ttlMillis,
                            TimeUnit.MILLISECONDS
                    );
                    log.info("token已加入黑名单, userId: {}, 有效期: {}ms", userId, ttlMillis);
                }
            }
        } catch (Exception e) {
            log.warn("退出登录处理token失败, userId: {}", userId, e);
        }
        return Result.success();
    }

    /**
     * 新用户漫游引导关闭
     * @param userId
     * @return
     */
    @PutMapping("/cancelTour/{userId}")
    public Result<Object> cancelTour(@PathVariable Long userId){
        log.info("关闭新手指引, userId: {}", userId);
        try {
            User user = loginMapper.selectById(userId);
            if (user != null) {
                user.setTour(0);
                loginMapper.updateById(user);
                log.info("用户{}的新手指引已关闭", userId);
            } else {
                log.warn("用户{}不存在", userId);
                return Result.error("用户不存在");
            }
        } catch (Exception e) {
            log.error("关闭新手指引失败, userId: {}", userId, e);
            return Result.error("关闭新手指引失败");
        }
        return Result.success();
    }
}

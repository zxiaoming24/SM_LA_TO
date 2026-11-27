package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.dhi.wha.constant.MessageConstant;
import com.dhi.wha.dto.UserAdminApplyDTO;
import com.dhi.wha.dto.UserAdminUpdateDTO;
import com.dhi.wha.dto.UserDTO;
import com.dhi.wha.dto.UserInfoDTO;
import com.dhi.wha.dto.UserListQueryDTO;
import com.dhi.wha.entity.RadarChart;
import com.dhi.wha.entity.User;
import com.dhi.wha.entity.UserAdminApply;
import com.dhi.wha.entity.UserRadarMap;
import com.dhi.wha.exception.AccountNotFoundException;
import com.dhi.wha.exception.PasswordErrorException;
import com.dhi.wha.mapper.LoginMapper;
import com.dhi.wha.mapper.RadarChartMapper;
import com.dhi.wha.mapper.UserAdminApplyMapper;
import com.dhi.wha.mapper.UserRadarMapMapper;
import com.dhi.wha.server.LoginService;
import com.dhi.wha.server.RadarChartService;
import com.dhi.wha.server.UserAdminApplyService;
import com.dhi.wha.vo.UserCommentVO;
import com.dhi.wha.vo.UserListVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.DigestUtils;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static java.util.List.of;

@Service
@Slf4j
public class LoginServiceImpl implements LoginService {

    @Autowired
    private LoginMapper loginMapper;

    @Autowired
    private RadarChartMapper radarChartMapper;

    @Autowired
    private UserRadarMapMapper userRadarMapMapper;

    @Autowired
    private UserAdminApplyMapper userAdminApplyMapper;

    /**
     * 注册/忘记密码
     *
     * @param user
     */
    @Transactional
    @Override
    public void register(UserDTO user) {
        //如果用户名为空，则表示忘记密码
        if (user.getUsername() == null) {
            //忘记密码
            //先将密码加密
            user.setPassword(DigestUtils.md5DigestAsHex(user.getPassword().getBytes()));
            loginMapper.forgetPasswordByEmail(user);
        }
        //用户名称不为空，则表示注册,isNew需要设置成为新用户。
        else {
            //3、新增用户
            User user1 = User.builder()
                    .username(user.getUsername())
                    .password(DigestUtils.md5DigestAsHex(user.getPassword().getBytes()))
                    .email(user.getEmail())
                    .isNew(true)
                    .type(-2)
                    .tour(1)   //需要新手指引
                    .isBuildProfile(0)  //注册的时候就设为0，为完善
                    .createTime(LocalDateTime.now())
                    .avatar("https://wha-whaghw.oss-cn-beijing.aliyuncs.com/db8f73f1-c000-4f57-af77-4f8660177455.png")
                    .build();
            loginMapper.insert(user1);
            // 创建雷达图并设置初始值
            RadarChart radarChart = new RadarChart();
            radarChart.setPreData(Arrays.asList(0, 0, 0, 0, 0, 0, 0, 0));
            radarChart.setCurData(Arrays.asList(0, 0, 0, 0, 0, 0, 0, 0));
            radarChartMapper.insert(radarChart);       // 插入后 id 会被自动回填

            // 关联用户和雷达图
            UserRadarMap userRadarMap = new UserRadarMap();
            userRadarMap.setUserId(user1.getId());
            userRadarMap.setRadarMapId(radarChart.getId());  // 此时 radarChart.getId() 有值
            userRadarMapMapper.insert(userRadarMap);
        }
    }

    /**
     * 登录
     *
     * @param user
     * @return
     */
    @Override
    public User login(UserDTO user) {

        String password;

        //如果用户名为空，邮箱不为空，则表示邮箱登录
        if (user.getUsername() == null && user.getEmail() != null) {

            User user1 = loginMapper.loginByEmail(user.getEmail());
            if (user1 == null) {
                log.info("用户不存在");
                throw  new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
            }

            //对前端传递过来的密码加密
            password = DigestUtils.md5DigestAsHex(user.getPassword().getBytes());
            if (!password.equals(user1.getPassword())) {
                //密码错误
                throw new PasswordErrorException(MessageConstant.PASSWORD_ERROR);
            }

            return user1;

        }
        //否则，用户名不为空，但是邮箱为空，则表示用户名登录
        else if (user.getUsername() != null && user.getEmail() == null) {
            User user1 = loginMapper.loginByUsername(user.getUsername());

            if (user1 == null) {
                log.info("用户名不存在");
                throw  new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
            }

            password = DigestUtils.md5DigestAsHex(user.getPassword().getBytes());
            if (!password.equals(user1.getPassword())) {
                //密码错误
                throw new PasswordErrorException(MessageConstant.PASSWORD_ERROR);
            }

            return user1;
        }
        else{
            log.info("用户名或邮箱不能为空");
            throw new RuntimeException(MessageConstant.USERNAME_OR_EMAIL_NOT_NULL);
        }
    }

    /**
     * 完善用户信息
     * @param userInfoDTO
     */
    @Override
    public void updateInformation(UserInfoDTO userInfoDTO) {
        //1.获取用户id，查询对应的用户信息
        User user = loginMapper.selectById(userInfoDTO.getId());
        //2.将该用户信息更新到数据库中
        BeanUtils.copyProperties(userInfoDTO,user);
        user.setIsNew(false);
        loginMapper.updateById(user);
    }

    @Override
    public List<UserCommentVO> getUserByUserIdList(List<String> userIdList) {
        List<Long> longList = new ArrayList<>();
        for (String userId : userIdList) {
            if (!isNumber(userId)) {
                //用户id不是数字
                log.info("用户id格式错误");
            }else{
                longList.add(Long.parseLong(userId));
            }
        }
        if (longList.isEmpty()) {
            return of();
        }
        return loginMapper.getUserByUserIdList(longList);
    }

    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    @Override
    public IPage<UserListVO> getUserList(UserListQueryDTO queryDTO) {
        // 1. 安全处理分页参数，限制最小为1
        Integer pageNum = queryDTO.getCurrentPage();
        Integer size = queryDTO.getPageSize();
        long currentPage = (pageNum == null || pageNum < 1) ? 1L : pageNum.longValue();
        long pageSize = (size == null || size < 1) ? 10L : size.longValue();
        Page<User> page = new Page<>(currentPage, pageSize);

        // 2. 转换type字符串为数字
        Integer type = null;
        String typeStr = queryDTO.getType();
        if (typeStr != null && !typeStr.isBlank()) {
            try {
                type = Integer.parseInt(typeStr.trim());
            } catch (NumberFormatException e) {
                log.info("用户类型参数格式错误，value={}", typeStr);
            }
        }

        // 3. 构建查询条件
        LambdaQueryWrapper<User> wrapper = Wrappers.lambdaQuery();

        // 用户名模糊查询
        String username = queryDTO.getUsername();
        if (username != null && !username.isBlank()) {
            wrapper.like(User::getUsername, username.trim());
        }

        // 类型筛选，-1代表不筛选
        if (type != null && type != -1) {
            wrapper.eq(User::getType, type);
        }

        // 4. 时间范围：调用DTO封装好的方法，不再强转createTime
        List<String> createTimeList = queryDTO.getCreateTimeList();
        if (createTimeList.size() >= 2) {
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
            String startTimeStr = createTimeList.get(0).trim();
            String endTimeStr = createTimeList.get(1).trim();
            try {
                LocalDateTime startTime = LocalDateTime.parse(startTimeStr, formatter);
                LocalDateTime endTime = LocalDateTime.parse(endTimeStr, formatter);
                wrapper.ge(User::getCreateTime, startTime)
                        .le(User::getCreateTime, endTime);
            } catch (Exception e) {
                log.warn("时间范围解析失败，start={},end={},err={}", startTimeStr, endTimeStr, e.getMessage());
            }
        }

        // 按创建时间倒序
        wrapper.orderByDesc(User::getCreateTime);

        // 分页查询数据库
        IPage<User> userPage = loginMapper.selectPage(page, wrapper);

        // entity 转 VO 分页返回
        return userPage.convert(user -> {
            UserListVO vo = new UserListVO();
            BeanUtils.copyProperties(user, vo);
            return vo;
        });
    }


    /**
     * 申请管理员
     * @param userAdminApplyDTO
     * @return
     */
    @Transactional
    @Override
    public void applyAdministrator(UserAdminApplyDTO userAdminApplyDTO) {
        //创建一个申请对象
        UserAdminApply userAdminApply = new UserAdminApply();
        userAdminApply.setUserId(userAdminApplyDTO.getId());
        userAdminApply.setUser_name(userAdminApplyDTO.getUsername());
        userAdminApply.setRemark(userAdminApplyDTO.getRemark());
        userAdminApplyMapper.insert(userAdminApply);
        //修改用户状态
        User user1 = User.builder()
                .id(userAdminApplyDTO.getId())
                .username(userAdminApplyDTO.getUsername())
                .email(userAdminApplyDTO.getEmail())
                .isNew(true)
                .type(-3)
                .build();
        loginMapper.updateById(user1);
    }

    /**
     * 接受申请
     * @param userId
     */
    @Override
    @Transactional
    public void acceptRequest(Integer userId) {
        //修改用户类型
        User user = User.builder()
                .id(Long.valueOf(userId))
                .isNew(false)
                .type(0)
                .build();
        loginMapper.updateById(user);
        //删除申请记录
        userAdminApplyMapper.deleteByUserId(userId);
    }

    /**
     * 拒绝申请
     * @param userId
     */
    @Override
    @Transactional
    public void rejectRequest(Integer userId) {
        //修改用户类型
        User user = User.builder()
                .id(Long.valueOf(userId))
                .isNew(true)
                .type(-2)
                .build();
        loginMapper.updateById(user);
        //删除申请记录
        userAdminApplyMapper.deleteByUserId(userId);
    }

    @Override
    public void updateUserInfoByAdmin(UserAdminUpdateDTO dto) {
        User user = loginMapper.selectById(dto.getUserId());
        if (user == null) {
            return;
        }
        if (dto.getUsername() != null) {
            user.setUsername(dto.getUsername());
        }
        if (dto.getAvatar() != null) {
            user.setAvatar(dto.getAvatar());
        }
        if (dto.getSex() != null) {
            user.setSex(dto.getSex());
        }
        if (dto.getGrade() != null) {
            user.setGrade(dto.getGrade());
        }
        if (dto.getMajor() != null) {
            user.setMajor(dto.getMajor());
        }
        loginMapper.updateById(user);
    }

    @Override
    public void deleteUser(Long userId) {
        loginMapper.deleteById(userId);
    }

    @Override
    public void resetPassword(Long userId) {
        String defaultPassword = "123456";
        String encryptedPassword = DigestUtils.md5DigestAsHex(defaultPassword.getBytes());
        User user = new User();
        user.setId(userId);
        user.setPassword(encryptedPassword);
        loginMapper.updateById(user);
    }
}

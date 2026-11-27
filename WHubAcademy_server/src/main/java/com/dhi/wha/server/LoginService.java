package com.dhi.wha.server;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.dhi.wha.dto.UserAdminApplyDTO;
import com.dhi.wha.dto.UserAdminUpdateDTO;
import com.dhi.wha.dto.UserDTO;
import com.dhi.wha.dto.UserInfoDTO;
import com.dhi.wha.dto.UserListQueryDTO;
import com.dhi.wha.entity.User;
import com.dhi.wha.vo.UserCommentVO;
import com.dhi.wha.vo.UserListVO;

import java.util.List;

public interface LoginService{
    /**
     * 注册
     * @param user
     */
    void register(UserDTO user);

    /**
     * 登录
     * @param user
     * @return
     */
    User login(UserDTO user);

    /**
     * 完善用户信息
     * @param userInfoDTO
     */
    void updateInformation(UserInfoDTO userInfoDTO);

    /**
     * 获取用户信息
     * @param userIdList
     * @return
     */
    List<UserCommentVO> getUserByUserIdList(List<String> userIdList);

    /**
     * 用户列表筛选查询（分页）
     * @param queryDTO 查询条件
     * @return 分页用户列表
     */
    IPage<UserListVO> getUserList(UserListQueryDTO queryDTO);

    /**
     * 申请管理员
     * @param userAdminApplyDTO
     */
    void applyAdministrator(UserAdminApplyDTO userAdminApplyDTO);

    /**
     * 接受管理员申请
     * @param userId
     */
    void acceptRequest(Integer userId);

    /**
     * 拒绝管理员申请
     * @param userId
     */
    void rejectRequest(Integer userId);

    /**
     * 后台管理员修改用户信息
     * @param dto
     */
    void updateUserInfoByAdmin(UserAdminUpdateDTO dto);

    /**
     * 删除用户
     * @param userId
     */
    void deleteUser(Long userId);

    /**
     * 重置密码
     * @param userId
     */
    void resetPassword(Long userId);
}

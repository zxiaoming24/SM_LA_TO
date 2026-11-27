package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.dto.UserDTO;
import com.dhi.wha.entity.User;
import com.dhi.wha.vo.RankingVO;
import com.dhi.wha.vo.UserCommentVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface LoginMapper extends BaseMapper<User> {




    /**
     * 邮箱登录
     * @param
     * @return
     */
    @Select("select * from user where email = #{email}")
    User loginByEmail(String email);

    /**
     * 用户名登录
     * @param
     * @return
     */
    @Select("select * from user where username = #{username}")
    User loginByUsername(String username);

    /**
     * 忘记密码
     * @param
     * @return
     */
    void forgetPasswordByEmail(UserDTO user);

    /**
     * 获取用户名与头像
     * @param
     * @return
     */
    @Select("select username,avatar from user where id = #{id}")
    RankingVO getUsernameAndAvatarById(Long id);

    /**
     * 获取用户名与头像
     * @param
     * @return
     */
    List<UserCommentVO> getUserByUserIdList(List<Long> userIdList);

    /**
     * 获取对应的用户就行
     * @param
     * @return
     */
    @Select("select * from user where id = #{userId}")
    User getById(Long userId);
}

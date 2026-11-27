package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.UserAdminApply;
import com.dhi.wha.vo.UserAdminApplyVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface UserAdminApplyMapper extends BaseMapper<UserAdminApply> {
    @Select("SELECT * FROM user_admin_apply")
    List<UserAdminApplyVO> getApplyAdminList();

    @Select("DELETE FROM user_admin_apply WHERE user_id = #{userId}")
    void deleteByUserId(Integer userId);
}

package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.UserRadarMap;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface UserRadarMapMapper extends BaseMapper<UserRadarMap> {
    /**
     * 根据用户id查询对应的雷达图id
     * @param userId
     * @return
     */
    @Select("select radar_map_id from user_radar_map where user_id = #{userId}")
    Long selectByUserId(Long userId);
}

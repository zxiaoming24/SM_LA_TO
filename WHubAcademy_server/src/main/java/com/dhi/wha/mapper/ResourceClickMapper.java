package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.ResourceClick;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

@Mapper
public interface ResourceClickMapper extends BaseMapper<ResourceClick> {

    @Select("SELECT resource_type AS resourceType, COUNT(*) AS clickCount " +
            "FROM resource_click WHERE user_id = #{userId} " +
            "GROUP BY resource_type ORDER BY clickCount DESC")
    List<Map<String, Object>> countByResourceType(@Param("userId") Long userId);

    @Select("SELECT resource_type AS resourceType, COUNT(*) AS clickCount " +
            "FROM resource_click " +
            "GROUP BY resource_type ORDER BY clickCount DESC")
    List<Map<String, Object>> countAllByResourceType();
}

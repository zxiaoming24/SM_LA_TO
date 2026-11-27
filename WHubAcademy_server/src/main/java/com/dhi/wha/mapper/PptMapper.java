package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.Ppt;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface PptMapper extends BaseMapper<Ppt> {


    /**
     * 根据用户id查询PPT
     * @param userId
     * @return
     */
    @Select("select * from ppt where user_id = #{userId} order by created_at desc")
    List<Ppt> getByUserId(Long userId);

    /**
     * 根据ID获取resourceId
     * @param id
     * @return resourceId
     */
    @Select("SELECT resource_id FROM ppt WHERE id = #{id}")
    String getResourceIdById(Long id);

    /**
     * 根据resourceId查询PPT
     * @param resourceId
     * @return
     */
    @Select("select * from ppt where resource_id = #{resourceId} LIMIT 1")
    Ppt getPptByResourceId(String resourceId);

}

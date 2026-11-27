package com.dhi.wha.mapper;


import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.ExtensionReading;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.ExtensionReadingVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface ExtensionReadingMapper extends BaseMapper<ExtensionReading> {

    /**
     * 获取用户所有拓展阅读列表
     * @param userId
     * @return
     */
    @Select("SELECT id, text,user_id, status, create_time FROM extension_reading WHERE user_id = #{userId} ORDER BY create_time DESC")
    List<ExtensionReadingVO> getExtensionReadingList(Long userId);

    /**
     * 获取拓展阅读详情
     * @param taskId
     * @return
     */
    @Select("select id,status,text,create_time from extension_reading where id = #{taskId}")
    ChatResourceVO getExtensionInfoById(Integer taskId);

    /**
     * 根据标题查询拓展阅读
     * @param title 标题
     * @return 拓展阅读
     */
    ExtensionReading getByTitle(String title);

    /**
     * 根据ID获取resourceId
     * @param id
     * @return resourceId
     */
    @Select("SELECT resource_id FROM extension_reading WHERE id = #{id}")
    String getResourceIdById(Long id);

    /**
     * 根据resourceId获取拓展阅读
     * @param id
     * @return 拓展阅读
     */
    @Select("SELECT * FROM extension_reading WHERE resource_id = #{id} LIMIT 1")
    ExtensionReading getByResourceId(String id);

    /**
     * 根据ID获取标题
     * @param l
     * @return 标题
     */
    @Select("SELECT title FROM extension_reading WHERE id = #{l}")
    String getTitleById(long l);
}

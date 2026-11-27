package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.MindMap;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.MindMapVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface MindMapMapper extends BaseMapper<MindMap> {


    /**
     * 获取用户思维导图列表
     * @param userId 用户ID
     * @return 思维导图列表
     */
    List<MindMapVO> getMindMapList(Long userId);

    /**
     * 根据用户ID查询思维导图
     * @param userId 用户ID
     * @return 思维导图列表
     */
    List<MindMap> selectByUserId(Long userId);

    /**
     * 根据任务ID查询思维导图信息
     * @param taskId 任务ID
     * @return 思维导图信息
     */
    @Select("SELECT id,status,text,create_time FROM mind_map WHERE id = #{taskId}")
    ChatResourceVO getMindMapInfoById(Integer taskId);

    /**
     * 根据标题查询思维导图
     * @param text 标题
     * @return 思维导图
     */
    MindMap getByText(String text);

    /**
     * 根据ID获取resourceId
     * @param id
     * @return resourceId
     */
    @Select("SELECT resource_id FROM mind_map WHERE id = #{id}")
    String getResourceIdById(Long id);


    /**
     * 根据resourceId获取思维导图
     * @param mindMapId resourceId
     * @return 思维导图
     */
    @Select("SELECT * FROM mind_map WHERE resource_id = #{mindMapId} LIMIT 1")
    MindMap getByResourceId(String mindMapId);

    /**
     * 根据ID获取标题
     * @param l
     * @return 标题
     */
    @Select("SELECT text FROM mind_map WHERE id = #{l}")
    String getTitleById(long l);
}

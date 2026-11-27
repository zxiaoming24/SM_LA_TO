package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.PaperPO;
import com.dhi.wha.vo.ChatResourceVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface PaperMapper extends BaseMapper<PaperPO> {
    /**
     * 获取指定用户下的所有试卷
     * @param userId
     * @return
     */
    @Select("select * from paper where user_id = #{userId}")
    List<PaperPO> getPaperById(Long userId);

    /**
     * 获取指定用户下的指定任务下的试卷信息
     * @param taskId
     * @return
     */
    ChatResourceVO getPaperInfoByUserIdAndTaskId(Integer taskId);

    /**
     * 根据ID获取resourceId
     * @param id
     * @return resourceId
     */
    @Select("SELECT resource_id FROM paper WHERE id = #{id}")
    String getResourceIdById(Long id);

    /**
     * 根据resourceId获取试卷
     * @param resourceId
     * @return 试卷
     */
    @Select("SELECT * FROM paper WHERE resource_id = #{resourceId} LIMIT 1")
    PaperPO getByResourceId(String resourceId);

    /**
     * 根据ID获取标题
     * @param l
     * @return 标题
     */
    @Select("SELECT paper_name FROM paper WHERE id = #{l}")
    String getTitleById(long l);
}

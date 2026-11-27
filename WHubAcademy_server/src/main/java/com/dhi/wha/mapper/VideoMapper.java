package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.Video;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.VideoVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface VideoMapper extends BaseMapper<Video> {

    /**
     * 根据用户ID获取视频列表
     * @param userId 用户ID
     * @return 视频列表
     */
    List<VideoVO> getListByUserId(Long userId);

    /**
     * 根据任务ID获取视频信息
     * @param taskId 任务ID
     * @return 视频信息
     */
    ChatResourceVO getVideoInfoById(String taskId);

    /**
     * 根据URL查询视频
     * @param url 视频URL
     * @return 视频
     */
    Video getByUrl(String url);

    /**
     * 根据ID获取resourceId
     * @param id
     * @return resourceId
     */
    @Select("SELECT resource_id FROM video WHERE id = #{id}")
    String getResourceIdById(Long id);

    /**
     * 根据resourceId获取视频
     * @param resourceId
     * @return 视频
     */
    @Select("select * from video where resource_id = #{resourceId} LIMIT 1")
    Video getByResourceId(String resourceId);

    /**
     * 根据ID获取标题
     * @param l
     * @return 标题
     */
    @Select("SELECT title FROM video WHERE id = #{l}")
    String getTitleById(long l);
}

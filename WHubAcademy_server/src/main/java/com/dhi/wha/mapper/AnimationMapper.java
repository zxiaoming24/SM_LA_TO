package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.Animation;
import com.dhi.wha.vo.ChatResourceVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface AnimationMapper extends BaseMapper<Animation> {
    /**
     * 获取指定动画
     * @param id
     * @return
     */
    @Select("select * from animation where id = #{id}")
    Animation pollAnimation(Long id);

    /**
     * 获取指定资源ID的动画
     * @param resourceId
     * @return
     */
    @Select("select * from animation where resource_id = #{resourceId} LIMIT 1")
    Animation pollAnimationByResourceId(String resourceId);

    /**
     * 获取指定用户的所有动画
     * @param userId
     * @return
     */
    @Select("select * from animation where user_id = #{userId} ORDER BY create_time DESC")
    List<Animation> listByUserId(Long userId);

    /**
     * 获取指定动画信息
     * @param taskId
     * @return
     */
    @Select("select id,status,text,create_time from animation where id = #{taskId}")
    ChatResourceVO getAnimationInfoById(Integer taskId);

    /**
     * 根据ID获取resourceId
     * @param id
     * @return resourceId
     */
    @Select("SELECT resource_id FROM animation WHERE id = #{id}")
    String getResourceIdById(Long id);

    /**
     * 根据resourceId获取动画
     * @param
     * @return 动画
     */
    @Select("SELECT text FROM animation WHERE id = #{l}")
    String getTitleById(long l);
}

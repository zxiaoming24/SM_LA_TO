package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.AnimationDTO;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.entity.Animation;
import com.dhi.wha.vo.ChatResourceVO;

import java.util.List;
import java.util.Map;

public interface AnimationService extends IService<Animation> {
    /**
     * 生成动画
     * @param animationDTO
     * @return
     */
    Map<String, Object> generateAnimation(AnimationDTO animationDTO);

    /**
     * 获取指定动画
     * @param id
     * @return
     */
    Animation pollAnimation(String id);

    /**
     * 保存动画
     */
    Long saveAnimation(ChatDTO chatDTO);

    /**
     * 获取指定用户的所有动画
     */
    List<Animation> listByUserId(Long userId);

    /**
     * 获取动画信息
     */
    ChatResourceVO getAnimationInfoById(Integer taskId);
}

package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.AnimationDTO;
import com.dhi.wha.entity.Animation;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.AnimationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/animation")
public class AnimationController {

    @Autowired
    private AnimationService animationService;


    /**
     * 生成动画html
     * @param animationDTO
     * @return
     */
    @PostMapping("/generateAnimation")
    public Result<Object> generateAnimation(@RequestBody AnimationDTO animationDTO){
         log.info("生成动画html");
        Map<String,Object> respMap = animationService.generateAnimation(animationDTO);
        return Result.success(respMap);
    }


    /**
     * 获取动画
     * @param id
     * @return
     */
    @ClickRecord(resourceType = "ANIMATION", resourceIdParam = "id")
    @GetMapping("/poll/{id}")
    public Result<Animation> pollAnimation(@PathVariable String id){
        log.info("获取动画");
        Animation animation = animationService.pollAnimation(id);
        if (animation == null) {
            return Result.error("找不到对应资源");
        }
        return Result.success(animation);
    }

    /**
     * 删除动画
     * @param id
     * @return
     */
    @DeleteMapping("/deleteAnimation/{id}")
    public Result<Object> deleteById(@PathVariable Long id){
        log.info("根据id删除动画");
        animationService.removeById(id);
        return Result.success();
    }

    /**
     * 获取动画列表
     * @param userId
     * @return
     */
    @ClickRecord(resourceType = "ANIMATION", resourceIdParam = "")
    @GetMapping("/getList/{userId}")
    public Result<List<Animation>> getAnimationList(@PathVariable Long userId){
        log.info("获取动画列表");
        List<Animation> animationList = animationService.listByUserId(userId);
        return Result.success(animationList);
    }
}

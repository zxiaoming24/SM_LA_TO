package com.dhi.wha.controller;


import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.WrongQuestionsService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/WrongQuestions")
@Slf4j
public class WrongQuestionsController {

    @Autowired
    private WrongQuestionsService wrongQuestionsService;


    /**
     * 获取错题列表
     * @param page
     * @param pageSize
     * @param question_type
     * @param userId
     * @return
     */
    @GetMapping("/getList/{page}/{pageSize}/{question_type}/{userId}")
    public Result<Object> getWrongQuestionsList(
            @PathVariable Integer page,
            @PathVariable Integer pageSize,
            @PathVariable Integer question_type,
            @PathVariable Long userId
    )
    {
        log.info("获取错题列表");
        return Result.success(wrongQuestionsService.getWrongQuestionsList(page, pageSize, question_type, userId));
    }


    /**
     * 获取错题统计
     * @param userId
     * @return
     */
    @GetMapping("/getStats/{userId}")
    public Result<Object> getWrongQuestionsStats(@PathVariable Long userId){
        log.info("获取错题统计");
        return Result.success(wrongQuestionsService.getWrongQuestionsStats(userId));
    }


    /**
     * 获取已掌握的错题列表
     * @param page
     * @param pageSize
     * @param userId
     * @return
     */
    @ClickRecord(resourceType = "WRONG_QUESTION", resourceIdParam = "")
    @GetMapping("/Mastered/{page}/{pageSize}/{userId}")
    public Result<Object> getMasteredWrongQuestionsList(
            @PathVariable Integer page,
            @PathVariable Integer pageSize,
            @PathVariable Long userId
    ){
         log.info("获取已掌握的错题列表");
         return Result.success(wrongQuestionsService.getMasteredWrongQuestionsList(page, pageSize, userId));
    }


    /**
     * 删除错题
     * @param userId
     * @param recordId
     * @return
     */
    @DeleteMapping("/deleteById/{recordId}/{userId}")
    public Result<Object> deleteByUserIdAndRecordId(@PathVariable Long userId,@PathVariable String recordId){
        log.info("删除错题");
        return Result.success(wrongQuestionsService.deleteByUserIdAndRecordId(userId, recordId));
    }


    /**
     * 获取推荐资源错题
     * @param recordId
     * @param userId
     * @return
     */
    @GetMapping("/getRecommendedResources/{recordId}/{userId}")
    public Result<Object> getMasteredList(
            @PathVariable String recordId,
            @PathVariable String userId
    ){
        log.info("获取推荐资源错题");
        return Result.success(wrongQuestionsService.getMasteredList(recordId, userId));
    }

    /**
     * AI生成推荐材料
     * @param requestMap 包含 user_id, record_id, knowledge_points, resource_types, difficulty
     * @return 推荐材料结果
     */
    @ClickRecord(resourceType = "WRONG_QUESTION", resourceIdParam = "")
    @PostMapping("/getAiRecommend")
    public Result<Object> llmGenerateRecommendedResources(@RequestBody Map<String, Object> requestMap) {
        log.info("AI生成推荐材料, request: {}", requestMap);
        return Result.success(wrongQuestionsService.llmGenerateRecommendedResources(requestMap));
    }

    /**
     * 获取易错题列表
     * @param userId 用户id
     * @return 易错题列表
     */
    @GetMapping("/getList/frequently-wrong/{page}/{pageSize}/{userId}")
    public Result<Object> getFrequentlyWrongList(
            @PathVariable Integer page,
            @PathVariable Integer pageSize,
            @PathVariable Long userId
    ) {
        log.info("获取易错题列表");
        return Result.success(wrongQuestionsService.getFrequentlyWrongList(userId,page,pageSize));
    }

    /**
     * 获取易错题统计
     * @param userId 用户id
     * @return 易错题统计
     */
    @GetMapping("/getList/frequently-wrong/{userId}/stats")
    public Result<Object> getFrequentlyWrongStats(@PathVariable Long userId) {
        log.info("获取易错题统计");
        return Result.success(wrongQuestionsService.getFrequentlyWrongStats(userId));
    }
}

package com.dhi.wha.server;

import java.util.Map;

public interface WrongQuestionsService {
    /**
     * 获取错题列表
     * @param page
     * @param pageSize
     * @param questionType
     * @param userId
     * @return
     */
    Object getWrongQuestionsList(Integer page, Integer pageSize, Integer questionType, Long userId);

    /**
     * 获取错题统计
     * @param userId
     * @return
     */
    Object getWrongQuestionsStats(Long userId);

    /**
     * 获取已掌握的错题列表
     * @param page
     * @param pageSize
     * @param userId
     * @return
     */
    Object getMasteredWrongQuestionsList(Integer page, Integer pageSize, Long userId);

    /**
     * 删除用户指定错题记录
     * @param userId
     * @param recordId
     * @return
     */
    Object deleteByUserIdAndRecordId(Long userId, String recordId);

    /**
     * 获取已掌握的错题列表
     * @param recordId
     * @param userId
     * @return
     */
    Object getMasteredList(String recordId, String userId);

    /**
     * AI生成推荐材料
     * @param requestMap 包含 user_id, record_id, knowledge_points, resource_types, difficulty
     * @return 推荐材料结果
     */
    Object llmGenerateRecommendedResources(Map<String, Object> requestMap);

    /**
     * 获取易错题列表
     * @param userId 用户id
     * @return 易错题列表
     */
    Object getFrequentlyWrongList(Long userId,Integer page,Integer pageSize);

    /**
     * 获取易错题统计
     * @param userId 用户id
     * @return 易错题统计
     */
    Object getFrequentlyWrongStats(Long userId);
}

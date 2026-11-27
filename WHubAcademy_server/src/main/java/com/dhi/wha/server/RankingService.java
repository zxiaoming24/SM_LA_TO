package com.dhi.wha.server;

import com.dhi.wha.entity.ranking;

import java.util.List;

public interface RankingService {
    /**
     * 获取排行榜列表
     * @param practiceId
     * @return
     */
    List<ranking> getRankingList(Long practiceId);
}

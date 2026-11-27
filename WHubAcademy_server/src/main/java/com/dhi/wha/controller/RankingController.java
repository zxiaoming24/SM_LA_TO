package com.dhi.wha.controller;

import com.dhi.wha.entity.ranking;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.RankingService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Slf4j
@RestController
public class RankingController {

    @Autowired
    private RankingService rankingService;

    @GetMapping("/rank/codeExamine/{practiceId}")
    public Result<List<ranking>> getRankingList(@PathVariable Long practiceId){
        log.info("获取排行榜列表");
        List<ranking> rankingList = rankingService.getRankingList(practiceId);
        return Result.success(rankingList);
    }
}

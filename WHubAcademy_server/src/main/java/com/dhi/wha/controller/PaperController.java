package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.PaperDTO;
import com.dhi.wha.dto.QuestionSubmitDTO;
import com.dhi.wha.entity.PaperPO;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.PaperService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/paper")
public class PaperController {

    @Autowired
    private PaperService paperService;


    /**
     * 生成试卷
     * @param paperDTO
     * @return
     */
    @PostMapping("/generatePaper")
    public Result<Object> generatePaper(@RequestBody PaperDTO paperDTO){
        log.info("生成试卷");
        Map<String,Object> respMap = paperService.generatePaper(paperDTO);
        return Result.success(respMap);
    }

    /**
     * 获取指定试卷
     * @param id 可以是Java端数字ID或Python端resourceId
     * @return
     */
    @ClickRecord(resourceType = "PAPER", resourceIdParam = "id")
    @GetMapping("/getPaperInfoById/{id}")
    public Result<Object> getPaperInfoById(@PathVariable String id){
        log.info("获取指定试卷, id: {}", id);
        Map<String,Object> paperInfo = paperService.getPaperInfoById(id);
        if (paperInfo == null || paperInfo.isEmpty()) {
            return Result.error("找不到对应的资源");
        }
        return Result.success(paperInfo);
    }

    /**
     * 获取指定试卷信息
     * @param userId
     * @return
     */
    @ClickRecord(resourceType = "PAPER", resourceIdParam = "")
    @GetMapping("/getPaperById/{userId}")
    public Result<List<PaperPO>> getPaperById(@PathVariable Long userId){
        log.info("获取指定试卷信息");
        List<PaperPO> paperList = paperService.getPaperById(userId);
        return Result.success(paperList);
    }

    /**
     * 删除指定试卷
     * @param id
     * @return
     */
    @DeleteMapping("/deleteById/{id}")
    public Result del(@PathVariable Integer id){
        paperService.deletePaper(id);
        return Result.success();
    }



    /**
     * 提交试卷
     */
    @PostMapping("/theory/submit")
    public Result<Object> submitPaper(
         @RequestBody QuestionSubmitDTO questionSubmitDTO
    ){
        try {
            log.info("提交试卷");
            return Result.success(paperService.submitPaper(questionSubmitDTO));
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("提交失败");
        }
    }
}

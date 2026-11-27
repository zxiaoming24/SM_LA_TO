package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.WordDTO;
import com.dhi.wha.entity.Word;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.WordService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/word")
@Slf4j
public class WordController {

    @Autowired
    private WordService wordService;


    /**
     * 获取任务ID
     * 前端调用：/word/submit
     */
    @PostMapping("/submit")
    public Result<Object> generateWord(@RequestBody WordDTO request) {
        log.info("生成讲解文档");
        try {
            Map<String,Object> respMap = wordService.submitTask(request);
            return Result.success(respMap);
        } catch (Exception e) {
            return Result.error("提交任务失败：" + e.getMessage());
        }
    }

    /**
     * 获取任务状态
     * 前端调用：/word/getProgress/{id}
     */
    @GetMapping("/getProgress/{id}")
    public Result<Object> getStatus(@PathVariable String id) {
        try{
            log.info("获取任务状态");
            Map<String,Object> statusInfo = wordService.getStatus(id);
            if (statusInfo == null || statusInfo.isEmpty()) {
                return Result.error("找不到对应资源");
            }
            return Result.success(statusInfo);
        }catch (Exception e) {
            System.out.println("获取任务状态失败：" + e.getMessage());
            return Result.error("获取任务状态失败：" + e.getMessage());
        }
    }

    /**
     * 获取用户讲解文档列表
     * 前端调用：/word/getList/{userId}
     */
    @ClickRecord(resourceType = "WORD", resourceIdParam = "")
    @GetMapping("/getList/{userId}")
    public Result<List<Word>> getWordList(@PathVariable Long userId){
        log.info("获取用户讲解文档列表");
        List<Word> wordList = wordService.getByUserId(userId);
        return Result.success(wordList);
    }


    /**
     * 删除用户讲解文档
     * 前端调用：/word/delete/{id}
     */
    @DeleteMapping("/delete/{id}")
    public Result deleteWordById(@PathVariable Long id){
        log.info("删除用户讲解文档");
        wordService.deleteWordById(id);
        return Result.success();
    }
}

package com.dhi.wha.controller;

import com.alibaba.fastjson.JSONObject;
import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.PptDTO;
import com.dhi.wha.dto.PptDownloadDTO;
import com.dhi.wha.entity.Ppt;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.PptService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/ppt")
public class PptController {

    @Autowired
    private PptService pptService;

    /**
     * 1. 创建PPT → 返回任务ID → 异步调用Python /chat接口
     */
    @PostMapping("/getId/{userId}")
    public Result<Map<String, Object>> createPPT(
            @RequestBody PptDTO pptDTO,
            @PathVariable String userId
    ) {
        log.info("创建PPT任务, text={}, userId={}", pptDTO.getText(), userId);
        try {
            Map<String, Object> result = pptService.createPPT(pptDTO,userId);
            return Result.success(result);
        } catch (Exception e) {
            log.error("创建PPT任务失败", e);
            return Result.error("创建PPT任务失败：" + e.getMessage());
        }
    }

    /**
     * 2. 查询进度 → 从数据库查询结果
     */
    @ClickRecord(resourceType = "PPT", resourceIdParam = "")
    @GetMapping("/getProgress/{taskId}")
    public Result<Map<String, Object>> getPPTResult(@PathVariable String taskId) {
        try {
            Map<String, Object> result = pptService.getProgress(taskId);
            return Result.success(result);
        } catch (Exception e) {
            log.error("查询PPT结果失败", e);
            return Result.error("查询PPT结果失败：" + e.getMessage());
        }
    }

    /**
     * 3. 获取下载链接 → 返回原始JSON
     */
    @PostMapping("/getDownload")
    public Result<JSONObject> downloadPPT(
            @RequestBody PptDownloadDTO pptDownloadDTO
    ) {
        log.info("获取下载地址");
        try {
            JSONObject json = pptService.getDownload(pptDownloadDTO.getId(), pptDownloadDTO.getType());
            return Result.success(json);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("获取下载地址失败：" + e.getMessage());
        }
    }


    /**
     * 4. 获取表格数据
     */
    @GetMapping("/getTable/{userId}")
    public Result<List<Ppt>> getByUserId(@PathVariable Long userId){
        log.info("根据id获取ppt表的数据");
        return Result.success(pptService.getByUserId(userId));
    }


    @DeleteMapping("/delPPT/{pptId}")
    public Result deleteTable(@PathVariable Long pptId){
        log.info("delPPT{}", pptId);
        pptService.deleteTable(pptId);
        return Result.success();
    }
}
package com.dhi.wha.controller;


import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.ExtensionReadingDTO;
import com.dhi.wha.dto.MindMapInsertDTO;
import com.dhi.wha.entity.ExtensionReading;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.ExtensionReadingService;
import com.dhi.wha.utils.HtmlGenerator;
import com.dhi.wha.vo.ExtensionReadingVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/reading")
public class ExtensionReadingController {

    @Resource
    private ExtensionReadingService readingService;

    /**
     * 根据用户id查询对应的列表
     */
    @ClickRecord(resourceType = "READING", resourceIdParam = "")
    @GetMapping(value = "/{userId}")
    public Result<List<ExtensionReadingVO>> getReadingHtml(@PathVariable Long userId) {
        log.info("查询用户id对应的拓展阅读");
        List<ExtensionReadingVO> readingHtml = readingService.getExtensionReadingList(userId);
        return Result.success(readingHtml);
    }

    /**
     * 获取任务ID
     */
    @PostMapping("/getId")
    public Result<Object> generateExtensionReading(@RequestBody ExtensionReadingDTO request) {
        log.info("生成拓展阅读材料");
        try {
            Map<String,Object> respMap = readingService.submitGenerateTask(request);
            return Result.success(respMap);
        } catch (Exception e) {
            return Result.error("提交任务失败：" + e.getMessage());
        }
    }

    /**
     * 获取拓展阅读生成状态
     */
    @GetMapping("/getProgress/{id}")
    public Result<Object> getMindMapStatus(@PathVariable String id){
        log.info("查询指定任务进度-拓展阅读");
        Map<String,Object> statusInfo = readingService.getStatus(id);
        // 判断为空：null 或者 空Map
        if (statusInfo == null || statusInfo.isEmpty()) {
            return Result.error("找不到对应资源");
        }
        return Result.success(statusInfo);
    }


    /**
     * 删除拓展阅读
     */
    @DeleteMapping("/delete/{id}")
    public Result deleteById(@PathVariable Long id) {
        log.info("删除指定的拓展阅读");
        readingService.removeById(id);
        return Result.success();
    }


    /**
     * 获取拓展阅读
     */
    @ClickRecord(resourceType = "READING", resourceIdParam = "id")
    @GetMapping("/getHtml/{id}")
    public Result<Object> getHtmlById(@PathVariable String id){
        log.info("根据id查询对应的拓展阅读材料");
        Map<String,Object> statusInfo = readingService.getStatus(id);
        return Result.success(statusInfo);
    }

}

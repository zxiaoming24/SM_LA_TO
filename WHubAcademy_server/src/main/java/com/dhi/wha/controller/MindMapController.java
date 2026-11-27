package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.MindMapInsertDTO;
import com.dhi.wha.entity.MindMap;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.MindMapService;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.vo.MindMapVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/mindMap")
public class MindMapController {

    @Autowired
    private MindMapService mindMapService;

    /**
     * 获取任务ID
     * 前端调用：/mindmap/getTaskId
     */
    @PostMapping("/getTaskId")
    public Result<Object> generateMindMap(@RequestBody MindMapInsertDTO request) {
        log.info("生成思维导图");
        try {
            Map<String,Object> respMap = mindMapService.submitGenerateTask(request);
            return Result.success(respMap);
        } catch (Exception e) {
            return Result.error("提交任务失败：" + e.getMessage());
        }
    }


    /**
     * 获取思维导图生成状态
     * 前端调用：/mindmap/getProgress/{taskId}
     */
    @GetMapping("/getProgress/{taskId}")
    public Result<Object> getMindMapStatus(@PathVariable Long taskId){
        log.info("查询指定任务进度");
        Map<String,Object> statusInfo = mindMapService.getStatus(taskId);
        if (statusInfo == null || statusInfo.isEmpty()) {
            return Result.error("找不到对应的资源");
        }
        return Result.success(statusInfo);
    }


    /**
     * 获取思维导图列表
     * 前端调用：/mindmap/getList/{userId}
     */
    @ClickRecord(resourceType = "MIND_MAP", resourceIdParam = "")
    @GetMapping("/getList/{userId}")
    public Result<List<MindMapVO>> getMindMapList(@PathVariable Long userId){
        log.info("查询对应用户的思维导图列表");
        List<MindMapVO> mindMapList = mindMapService.getMindMapList(userId);
        return Result.success(mindMapList);
    }


    /**
     * 获取思维导图
     * 前端调用：/mindmap/getValue/{mindMapId}
     */
    @ClickRecord(resourceType = "MIND_MAP", resourceIdParam = "mindMapId")
    @GetMapping("/getValue/{mindMapId}")
    public Result<MindMap> getMindMapById(@PathVariable String mindMapId){
        log.info("查询指定的思维导图");
        MindMap mindMap = mindMapService.getById(mindMapId);
        return Result.success(mindMap);
    }

    /**
     * 删除思维导图
     * 前端调用：/mindmap/delete/{mindMapId}
     */
    @DeleteMapping("/delete/{mindMapId}")
    public Result deleteMindMapById(@PathVariable Long mindMapId){
        log.info("删除指定的思维导图");
        mindMapService.deleteMindMapById(mindMapId);
        return Result.success();
    }


    /**
     * 获取思维导图上/下页数据
     * 前端调用：/mindmap/page/{mindMapId}/{userId}/{operation}
     */
    @ClickRecord(resourceType = "MIND_MAP", resourceIdParam = "mindMapId")
    @GetMapping("/page/{mindMapId}/{userId}/{operation}")
    public Result<MindMap> getMindMapPage(
            @PathVariable Long mindMapId,
            @PathVariable Long userId,
            @PathVariable Long operation
    ){
           log.info("获取思维导图上/下页数据");
           MindMap mindMap = mindMapService.getMindMapPage(mindMapId, userId, operation);
           return Result.success(mindMap);
    }

}
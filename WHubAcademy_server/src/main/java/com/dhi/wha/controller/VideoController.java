package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.RewindReportDTO;
import com.dhi.wha.dto.VideoDTO;
import com.dhi.wha.dto.VideoQuizDTO;
import com.dhi.wha.dto.VideoWatchDTO;
import com.dhi.wha.entity.Video;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.VideoService;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.vo.VideoVO;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/video")
public class VideoController {

    @Autowired
    private VideoService videoService;

    @Autowired
    private PythonRestClient pythonRestClient;


    // 静态下划线Mapper，只在这里用
    private static final ObjectMapper SNAKE_CASE_MAPPER;
    static {
        SNAKE_CASE_MAPPER = new ObjectMapper();
        // 序列化输出下划线
        SNAKE_CASE_MAPPER.setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
    }

    /**
     * 根据用户输入的文本搜索视频资源
     * @param videoDTO
     * @return
     */
    @PostMapping("/getVideoByText")
    public Result<Object> getVideoByText(@RequestBody VideoDTO videoDTO){
        log.info("搜索用户需要的视频资源");
        try {
            Map<String,Object> respMap = videoService.getVideoByText(videoDTO);
            return Result.success(respMap);
        } catch (Exception e) {
            return Result.error("搜索任务失败：" + e.getMessage());
        }
    }


    /**
     * 根据批次ID查询视频列表
     * @param batchId
     * @return
     */
    @GetMapping("/poll")
    public Result<List<Video>> listByBatchId(@RequestParam String batchId){
        log.info("查询批次ID为{}的视频列表", batchId);
        List<Video> videoList = videoService.pollVideoByBatchId(batchId);
        return Result.success(videoList);
    }

    /**
     * 根据资源ID查询视频
     * @param resourceId
     * @return
     */
    @GetMapping("/getVideoById/{resourceId}")
    public Result<Video> getVideoById(@PathVariable String resourceId){
        log.info("查询视频ID为{}的视频",resourceId);
        return Result.success(videoService.getByResourceId(resourceId));
    }

    /**
     * 删除视频
     * @param batchId
     * @return
     */
    @DeleteMapping("/deleteVideo/{batchId}")
    public Result deleteById(@PathVariable String batchId) {
        log.info("删除视频ID为{}的视频", batchId);
        videoService.deleteByBatchId(batchId);
        return Result.success();
    }

    /**
     * 根据用户ID查询视频列表
     * @param userId
     * @return
     */
    @ClickRecord(resourceType = "VIDEO", resourceIdParam = "")
    @GetMapping("/getList/{userId}")
    public Result<List<VideoVO>> getListByUserId(@PathVariable Long userId) {
        log.info("查询用户ID为{}的视频列表", userId);
        List<VideoVO> videoList = videoService.getListByUserId(userId);
        return Result.success(videoList);
    }


    /**
     * 上报用户行为数据给python
     * @param watchDTO
     * @return
     */
    @PostMapping("/userBehaviour")
    public Result<Object> userBehaviour(@RequestBody VideoWatchDTO watchDTO) throws Exception {
        log.info("上报用户数据给python端，原始DTO");
        String pythonApiPath = "/video/report-watch";

        // 核心：DTO -> 下划线JSON字符串，直接传字符串给post
        String snakeJson = SNAKE_CASE_MAPPER.writeValueAsString(watchDTO);
        Object pythonResponse = pythonRestClient.post(pythonApiPath, snakeJson);

        return Result.success(pythonResponse);
    }


    /**
     * 获取视频信息
     * @param bvid
     * @param page
     * @return
     */
    @GetMapping("/playInfo/{bvid}/{page}")
    public Result<Object> getVideoInfo(
            @PathVariable String bvid,
            @PathVariable Integer page
    ){
        try{
            log.info("获取视频信息");
            return Result.success(videoService.getVideoInfo(bvid, page));
        }catch (Exception e){
            return Result.error("获取视频信息失败：" + e.getMessage());
        }
    }


    /**
     * 上报回溯事件给python
     * @param dto
     * @return
     */
    @PostMapping("/reportRewindEvent")
    public Result<Object> reportRewindEvent(
            @RequestBody RewindReportDTO dto
    ){
        log.info("接收回溯上报数据");
        String pythonPath = "/video/rewind-event";
        try {
            // DTO驼峰 → 下划线JSON字符串
            String snakeJson = SNAKE_CASE_MAPPER.writeValueAsString(dto);
            Object resp = pythonRestClient.post(pythonPath, snakeJson);
            return Result.success(resp);
        } catch (Exception e) {
            log.error("上报回溯事件异常", e);
            return Result.error("同步回溯数据失败");
        }
    }

    /**
     * 视频观看完成后生成小测试
     * @param videoQuizDTO 视频小测试请求参数
     * @return 测试题数据
     */
    @PostMapping("/postVideoQuiz")
    public Result<Object> postVideoQuiz(@RequestBody VideoQuizDTO videoQuizDTO){
        log.info("视频观看完成后生成小测试");
        try {
            Object result = videoService.postVideoQuiz(videoQuizDTO);
            return Result.success(result);
        } catch (Exception e) {
            log.error("生成视频小测试失败", e);
            return Result.error("生成测试题失败：" + e.getMessage());
        }
    }

    /**
     * 获取视频综述
     * @param params 请求参数（包含bvid和page）
     * @return 视频综述数据
     */
    @PostMapping("/getSummary")
    public Result<Object> getSummary(@RequestBody Map<String, Object> params){
        log.info("获取视频综述");
        try {
            Object result = videoService.getSummary(params);
            return Result.success(result);
        } catch (Exception e) {
            log.error("获取视频综述失败", e);
            return Result.error("获取视频综述失败：" + e.getMessage());
        }
    }

    /**
     * 获取视频思维导图
     * @param params 请求参数（包含bvid和page）
     * @return 视频思维导图数据
     */
    @PostMapping("/getMindmap")
    public Result<Object> getMindmap(@RequestBody Map<String, Object> params){
        log.info("获取视频思维导图");
        try {
            Object result = videoService.getMindmap(params);
            return Result.success(result);
        } catch (Exception e) {
            log.error("获取视频思维导图失败", e);
            return Result.error("获取视频思维导图失败：" + e.getMessage());
        }
    }
}

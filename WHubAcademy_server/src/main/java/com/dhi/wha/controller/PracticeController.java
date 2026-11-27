package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.CompareDTO;
import com.dhi.wha.dto.PracticeAnswerDTO;
import com.dhi.wha.dto.PracticeDTO;
import com.dhi.wha.dto.VisualizationDTO;
import com.dhi.wha.entity.Practice;
import com.dhi.wha.entity.PracticeAnswer;
import com.dhi.wha.entity.Visualization;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.PracticeAnswerService;
import com.dhi.wha.server.PracticeService;
import com.dhi.wha.server.VisualizationService;
import com.dhi.wha.vo.PracticeAnswerListVO;
import com.dhi.wha.vo.PracticeAnswerVO;
import com.dhi.wha.vo.PracticeVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/code")
public class PracticeController {

    @Autowired
    private PracticeService practiceService;

    @Autowired
    private PracticeAnswerService practiceAnswerService;

    @Autowired
    private VisualizationService visualizationService;

    /**
     * 提交任务
     * @param request
     * @return
     */
    @PostMapping("/getId")
    public Result<Object> generatePractice(@RequestBody PracticeDTO request) {
        log.info("生成编程练习题");
        try {
            Map<String,Object> respMap = practiceService.submitGenerateTask(request);
            return Result.success(respMap);
        } catch (Exception e) {
            return Result.error("提交任务失败：" + e.getMessage());
        }
    }


    /**
     * 查询指定任务进度
     * @param id
     * @return
     */
    @GetMapping("/getProgress/{id}")
    public Result<Practice> getPracticeStatus(@PathVariable Long id){
        log.info("查询指定任务进度-编程练习题的");
        Practice practice = practiceService.getPracticeById(id);
        if (practice == null) {
            return Result.error("找不到对应的资源");
        }
        return Result.success(practice);
    }

    /**
     * 查询指定任务结果
     * @param id
     * @return
     */
    @ClickRecord(resourceType = "CODE", resourceIdParam = "")
    @GetMapping("/getPractice/{id}")
    public Result<Practice> getPracticeById(@PathVariable String id){
        log.info("根据id查询对应的编程练习题");
        return Result.success(practiceService.getPractice(id));
    }

    /**
     * 查询用户对应的所有的编程练习题列表
     * @param userId
     * @return
     */
    @GetMapping("/{userId}")
    public Result<List<PracticeVO>> getPracticeList(@PathVariable Long userId){
        log.info("查询用户对应的所有的编程练习题列表");
        List<PracticeVO> practiceList = practiceService.getPracticeList(userId);
        return Result.success(practiceList);
    }


    /**
     * 删除对应的编程练习题
     * @param id
     * @return
     */
    @DeleteMapping("/delete/{id}")
    public Result deletePracticeById(@PathVariable Long id){
        log.info("删除对应的编程练习题");
        //删除要删除两张表，所以不能直接删除编程练习题的表
        practiceService.deletePracticeById(id);
        return Result.success();
    }

    /**
     * 获取编程练习题的答案
     * @param request
     * @return
     */
    @PostMapping("/submit/answer")
    public Result<Object> getPracticeAnswer(@RequestBody PracticeAnswerDTO request) {
        log.info("获取编程练习题的答案");
        try {
            Map<String,Object> respMap = practiceAnswerService.getPracticeAnswer(request);
            return Result.success(respMap);
        } catch (Exception e) {
            return Result.error("获取答案失败：" + e.getMessage());
        }
    }


    /**
     * 根据id查询对应编程题的答案
     * @param id
     * @return
     */
    @GetMapping("/getSubmitResult/{id}")
    public Result<PracticeAnswerVO> getPracticeAnswerVOById(@PathVariable Long id){
        log.info("根据id查询对应的编程练习题的答案");
        PracticeAnswerVO practiceAnswerVO = practiceAnswerService.getPracticeAnswerById(id);
        return Result.success(practiceAnswerVO);
    }

    /**
     * 根据id查询对应编程题的答案-所有内容
     * @param id
     * @return
     */
    @GetMapping("/getSubmitResultById/{id}")
    public Result<PracticeAnswer> getPracticeAnswerById(@PathVariable Long id){
        log.info("根据id查询对应的编程练习题的答案-所有内容");
        PracticeAnswer practiceAnswer = practiceAnswerService.getById(id);
        return Result.success(practiceAnswer);
    }

    /**
     * 根据id查询对应的编程题的答案列表
     * @param practiceId
     * @return
     */
    @GetMapping("/practiceAnswerList/{practiceId}/{userId}")
    public Result<List<PracticeAnswerListVO>> getPracticeAnswerList(
            @PathVariable Long practiceId,
            @PathVariable Long userId
    ){
        log.info("根据id查询对应的编程练习题的答案列表");
        List<PracticeAnswerListVO> practiceAnswerListVO = practiceAnswerService.getPracticeAnswerList(practiceId, userId);
        return Result.success(practiceAnswerListVO);
    }


    /**
     * 删除对应的编程练习题的答案
     * @param id
     * @return
     */
    @DeleteMapping("/deleteAnswer/{id}")
    public Result deletePracticeAnswerById(@PathVariable Long id){
        log.info("删除对应的编程练习题的答案");
        practiceAnswerService.deletePracticeAnswerById(id);
        return Result.success();
    }


    /**
     * 获取可视化结果
     * @param visualizationDTO
     * @return
     */
    @PostMapping("/visualize/transform")
    public Result<Visualization> getVisualization(@RequestBody VisualizationDTO visualizationDTO){
        log.info("获取可视化结果");
        Visualization visualization = visualizationService.getVisualization(visualizationDTO);
        return Result.success(visualization);
    }

    /**
     * 比较分析两个人的编程题
     * @param compareDTO 比较请求参数
     * @return 比较结果数据
     */
    @PostMapping("/compare")
    public Result<List<Object>> comparePracticeAnswers(@RequestBody CompareDTO compareDTO){
        log.info("比较分析编程题, compareDTO: {}", compareDTO);
        try {
            List<Object> result = practiceAnswerService.comparePracticeAnswers(compareDTO);
            return Result.success(result);
        } catch (Exception e) {
            log.error("比较分析编程题失败", e);
            return Result.error("比较分析失败：" + e.getMessage());
        }
    }

}

package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.RadarChart;
import com.dhi.wha.mapper.AnimationMapper;
import com.dhi.wha.mapper.ExtensionReadingMapper;
import com.dhi.wha.mapper.MindMapMapper;
import com.dhi.wha.mapper.PaperMapper;
import com.dhi.wha.mapper.PptMapper;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.mapper.RadarChartMapper;
import com.dhi.wha.mapper.UserRadarMapMapper;
import com.dhi.wha.mapper.VideoMapper;
import com.dhi.wha.mapper.WordMapper;
import com.dhi.wha.server.RadarChartService;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.vo.RadarChartVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

import static java.util.List.of;

@Service
public class RadarChartServiceImpl extends ServiceImpl<RadarChartMapper, RadarChart>
        implements RadarChartService {

    @Autowired
    private RadarChartMapper radarChartMapper;

    @Autowired
    private UserRadarMapMapper userRadarMapMapper;

    @Autowired
    private PythonRestClient pythonRestClient;

    @Autowired
    private PptMapper pptMapper;

    @Autowired
    private MindMapMapper mindMapMapper;

    @Autowired
    private WordMapper wordMapper;

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private AnimationMapper animationMapper;

    @Autowired
    private PaperMapper paperMapper;


    /**
     * 获取雷达图数据
     * @param userId
     * @return
     */
    @Override
    public List<RadarChartVO> getRadarChartData(Long userId) {
        //1. 根据用户id查询中间表，获取对应的雷达图id
        Long radarMapId = userRadarMapMapper.selectByUserId(userId);

        //2. 根据雷达图id查询对应的雷达图数据
        RadarChart radarChart = radarChartMapper.selectByRadarMapId(radarMapId);

        //3. 向python端请求并更新数据,记得之后要改用户id哦，这里写死了！！！
        try {
            Object pythonRes = pythonRestClient.getWithPathParam("/features/{user_id}", userId.toString());
            Map<String, Object> rootMap = (Map<String, Object>) pythonRes;

            // 拿到 features
            Map<String, Object> features = (Map<String, Object>) rootMap.get("features");
            // 拿到 summary_scores
            Map<String, Object> summaryScores = (Map<String, Object>) features.get("summary_scores");

            // 目标数组 dimension_scores
            List<Object> scoreArr = (List<Object>) summaryScores.get("dimension_scores");

            // 转为 Integer 列表使用
            List<Integer> dimensionScores = new ArrayList<>();
            for (Object obj : scoreArr) {
                dimensionScores.add((Integer) obj);
            }


            if(!java.util.Objects.equals(radarChart.getCurData(), dimensionScores)){
                // 更新雷达图数据
                radarChart.setPreData(radarChart.getCurData());
                radarChart.setCurData(dimensionScores);
                radarChartMapper.updateById(radarChart);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }

        //4. 封装数据并返回
        List<RadarChartVO> radarChartVOList = new ArrayList<>();



        RadarChartVO vo = new RadarChartVO();
        RadarChartVO vo1 = new RadarChartVO();

        vo.setName("更新前");
        vo.setValue(radarChart.getPreData());
        radarChartVOList.add(vo);

        vo1.setName("更新后");
        vo1.setValue(radarChart.getCurData());
        radarChartVOList.add(vo1);

        return radarChartVOList;
    }

    /**
     * 查询资源总量信息
     * @param userId
     * @return 资源总量列表 [ppt, 思维导图, 讲解文档, 拓展阅读, 编程题, 视频, 动画, 试卷, 学习计划]
     */
    @Override
    public List<Integer> getResourceTotalCount(Long userId) {
        List<Integer> resourceCounts = new ArrayList<>();

        // 0. PPT数量
        Integer pptCount = pptMapper.getByUserId(userId) != null ? pptMapper.getByUserId(userId).size() : 0;
        resourceCounts.add(pptCount);

        // 1. 思维导图数量
        Integer mindMapCount = mindMapMapper.selectByUserId(userId) != null ? mindMapMapper.selectByUserId(userId).size() : 0;
        resourceCounts.add(mindMapCount);

        // 2. 讲解文档数量
        Integer wordCount = wordMapper.getWordListByUserId(userId) != null ? wordMapper.getWordListByUserId(userId).size() : 0;
        resourceCounts.add(wordCount);

        // 3. 拓展阅读数量
        Integer extensionReadingCount = extensionReadingMapper.getExtensionReadingList(userId) != null ? extensionReadingMapper.getExtensionReadingList(userId).size() : 0;
        resourceCounts.add(extensionReadingCount);

        // 4. 编程题数量
        Integer practiceCount = practiceMapper.getPracticeList(userId) != null ? practiceMapper.getPracticeList(userId).size() : 0;
        resourceCounts.add(practiceCount);

        // 5. 视频数量
        Integer videoCount = videoMapper.getListByUserId(userId) != null ? videoMapper.getListByUserId(userId).size() : 0;
        resourceCounts.add(videoCount);

        // 6. 动画数量
        Integer animationCount = animationMapper.listByUserId(userId) != null ? animationMapper.listByUserId(userId).size() : 0;
        resourceCounts.add(animationCount);

        // 7. 试卷数量
        Integer paperCount = paperMapper.getPaperById(userId) != null ? paperMapper.getPaperById(userId).size() : 0;
        resourceCounts.add(paperCount);

        // 8. 学习计划数量 - 调用Python接口获取
        Integer studyPlanCount = 0;
        try {
            Object pythonRes = pythonRestClient.getWithPathParam("/study_plans/{user_id}", userId.toString());
            if (pythonRes != null) {
                Map<String, Object> resultMap = (Map<String, Object>) pythonRes;
                List<Object> studyPlans = (List<Object>) resultMap.get("plans");
                studyPlanCount = studyPlans != null ? studyPlans.size() : 0;
            }
        } catch (Exception e) {
            e.printStackTrace();
            studyPlanCount = 0;
        }
        resourceCounts.add(studyPlanCount);

        return resourceCounts;
    }

    /**
     * 查询学习计划进度信息
     * @param userId
     * @return 学习计划进度列表
     */
    @Override
    public List<Map<String, Object>> getPlanProgressMsg(Long userId) {
        List<Map<String, Object>> planProgressList = new ArrayList<>();

        try {
            // 1. 获取学习计划列表
            Object planListRes = pythonRestClient.getWithPathParam("/study_plans/{user_id}", userId.toString());
            if (planListRes == null) {
                return planProgressList;
            }

            Map<String, Object> planListMap = (Map<String, Object>) planListRes;
            List<Map<String, Object>> plans = (List<Map<String, Object>>) planListMap.get("plans");

            if (plans == null || plans.isEmpty()) {
                return planProgressList;
            }

            // 2. 遍历每个学习计划
            for (Map<String, Object> plan : plans) {
                String planId = (String) plan.get("plan_id");
                String title = (String) plan.get("title");

                //(1)先将该计划置为活跃状态
                Map<String, Object> body = new HashMap<>();
                body.put("plan_id", planId);
                pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body, userId);

                if (planId == null || planId.isEmpty()) {
                    continue;
                }

                // 3. 获取计划详情，计算知识点总数和已完成数
                int totalKps = 0;
                int completedKps = 0;

                try {
                    Object planDetailRes = pythonRestClient.getWithPathAndQueryParam("/study_plan/{user_id}?plan_id={pathId}", userId.toString(), planId);
                    if (planDetailRes != null) {
                        Map<String, Object> planDetailMap = (Map<String, Object>) planDetailRes;
                        Map<String, Object> planData = (Map<String, Object>) planDetailMap.get("plan");

                        if (planData != null) {
                            List<Map<String, Object>> phases = (List<Map<String, Object>>) planData.get("phases");
                            if (phases != null) {
                                for (Map<String, Object> phase : phases) {
                                    List<Object> kps = (List<Object>) phase.get("knowledge_points");
                                    if (kps != null) {
                                        totalKps += kps.size();
                                    }
                                    List<Object> completedKpsList = (List<Object>) phase.get("completed_kps");
                                    if (completedKpsList != null) {
                                        completedKps += completedKpsList.size();
                                    }
                                }
                            }
                        }
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }

                // 4. 获取当前进度，计算进度百分比和当前阶段
                int progress = 0;
                int remainingDays = 0;

                try {
                    Object progressRes = pythonRestClient.getWithPathParam("/study_plan/{user_id}/progress", userId.toString());
                    if (progressRes != null) {
                        Map<String, Object> progressMap = (Map<String, Object>) progressRes;
                        List<Map<String, Object>> phases = (List<Map<String, Object>>) progressMap.get("phases");

                        if (phases != null && !phases.isEmpty()) {
                            int totalKnowledgePoints = 0;
                            int completedKnowledgePoints = 0;

                            for (Map<String, Object> phase : phases) {
                                Integer totalKp = Optional.ofNullable(phase)
                                        .map(m -> (Integer) m.get("total_knowledge_points"))
                                        .orElse(null);

                                Integer completedKp = Optional.ofNullable(phase)
                                        .map(m -> (Integer) m.get("completed_kps"))
                                        .orElse(null);

                                if (totalKp != null) {
                                    totalKnowledgePoints += totalKp;
                                }
                                if (completedKp != null) {
                                    completedKnowledgePoints += completedKp;
                                }

                                if (remainingDays == 0) {
                                    String status = (String) phase.get("status");
                                    if ("进行中".equals(status)) {
                                        Integer phaseIndex = (Integer) phase.get("phase_index");
                                        remainingDays = phaseIndex != null ? phaseIndex + 1 : 1;
                                    }
                                }
                            }

                            if (totalKnowledgePoints > 0) {
                                progress = (completedKnowledgePoints * 100) / totalKnowledgePoints;
                            }
                        }
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }

                // 5. 组装返回数据
                Map<String, Object> progressItem = new HashMap<>();
                progressItem.put("name", title != null ? title : "未知计划");
                progressItem.put("remainingDays", remainingDays);
                progressItem.put("progress", progress);
                progressItem.put("completed", completedKps);
                progressItem.put("total", totalKps);

                planProgressList.add(progressItem);
            }

        } catch (Exception e) {
            e.printStackTrace();
        }

        return planProgressList;
    }
}

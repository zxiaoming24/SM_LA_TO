package com.dhi.wha.server.Impl;

import com.dhi.wha.entity.ranking;
import com.dhi.wha.mapper.LoginMapper;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.server.RankingService;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.vo.RankingVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;


@Service
public class RankingServiceImpl implements RankingService {

    @Autowired
    private PracticeMapper practiceMapper;

    @Resource
    private PythonRestClient pythonRestClient;

    @Resource
    private LoginMapper loginMapper;


    /**
     * 获取排行榜列表
     * @param practiceId
     * @return
     */
    @Override
    public List<ranking> getRankingList(Long practiceId) {
        //1.根据practiceId查询对应的problemId
        String problemId = practiceMapper.getProblemId(practiceId);

        //2.定义一个Ranking的列表用来存储对象
        List<ranking> rankingList = new ArrayList<>();

        //3.封装给python端的数据
        try {
            Object pythonRes = pythonRestClient.getWithPathParam("/leaderboard/{problem_id}", problemId);
            Map<String, Object> rootMap = (Map<String, Object>) pythonRes;

            // 2. 获取 top_submissions 数组
            List<Map<String, Object>> topSubmissions = (List<Map<String, Object>>) rootMap.get("top_submissions");

            // 3. 遍历数组，逐个提取目标字段
            for (Map<String, Object> item : topSubmissions) {
                // 提取所需字段：user_id、score、code_preview
                String userIdObj = (String) item.get("user_id");
                Integer score = (Integer) item.get("score");
                Integer submissionId = (Integer) item.get("submission_id");

                //根据submissionId查询完整代码
                Object codeRes = pythonRestClient.getWithPathParam("/leaderboard/submission/{submission_id}/code", submissionId);
                String codePreview = null;
                if (codeRes instanceof Map) {
                    codePreview = (String) ((Map<String, Object>) codeRes).get("full_code");
                }
                

                // 将用户id转换成Long类型的数据(测试的时候需要注释)
                Long userId = null;
                if (userIdObj != null) {
                    // 先转字符串，再转Long（兼容 数字/字符串格式id）
                    userId = Long.parseLong(userIdObj.toString());
                }

                RankingVO rankingVO = loginMapper.getUsernameAndAvatarById(userId);

                // 创建一个Ranking对象，并设置字段
                ranking ranking = new ranking();
                ranking.setUserId(userId);
                ranking.setUsername(rankingVO.getUserName());
                ranking.setScore(score);
                ranking.setSubmissionId(submissionId);
                ranking.setCodePreview(codePreview);
                ranking.setAvatar(rankingVO.getAvatar());
                rankingList.add(ranking);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return rankingList;
    }
}

package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.ResourceClick;
import com.dhi.wha.mapper.ResourceClickMapper;
import com.dhi.wha.server.ResourceClickService;
import com.dhi.wha.vo.ResourceClickVO;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class ResourceClickServiceImpl extends ServiceImpl<ResourceClickMapper, ResourceClick> implements ResourceClickService {

    // 所有资源类型
    private static final String[] ALL_RESOURCE_TYPES = {
            "MIND_MAP", "ANIMATION", "PAPER", "READING", "VIDEO", "PPT", "WORD", "CODE",
            "PATHPLAN", "EVALUATE", "AI_ANSWER", "POST", "PARTNERS", "WRONG_QUESTION"
    };

    @Override
    public List<ResourceClickVO> getUserClickStats(Long userId) {
        // SQL聚合查询：直接在数据库层 GROUP BY
        List<Map<String, Object>> statsList = baseMapper.countByResourceType(userId);

        // 将查询结果转为Map，方便后续查找
        Map<String, Long> clickMap = new HashMap<>();
        long total = 0;
        if (statsList != null) {
            for (Map<String, Object> row : statsList) {
                String type = (String) row.get("resourceType");
                long count = ((Number) row.get("clickCount")).longValue();
                clickMap.put(type, count);
                total += count;
            }
        }

        // 构建返回结果，包含所有类型，没有点击的返回0
        long finalTotal = total;
        List<ResourceClickVO> result = new ArrayList<>();
        for (String type : ALL_RESOURCE_TYPES) {
            long count = clickMap.getOrDefault(type, 0L);
            double percentage = finalTotal > 0 ? Math.round(count * 10000.0 / finalTotal) / 100.0 : 0.0;
            result.add(ResourceClickVO.builder()
                    .resourceType(type)
                    .clickCount(count)
                    .percentage(percentage)
                    .build());
        }

        return result;
    }
}

package com.dhi.wha.server;

import com.dhi.wha.vo.ResourceBasicInfoVO;
import com.dhi.wha.vo.ResourceClickVO;
import com.dhi.wha.vo.ResourceGenerationTrendVO;
import com.dhi.wha.vo.UserBasicInfoVO;

import java.util.List;

public interface AdminIndexService {
    UserBasicInfoVO getUserBasicInfo();
    ResourceBasicInfoVO getResourceBasicInfo();
    List<ResourceClickVO> getPopularResourcesRank();
    ResourceGenerationTrendVO getResourceGenerationTrend(String rangeType);
}

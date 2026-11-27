package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.entity.ResourceClick;
import com.dhi.wha.vo.ResourceClickVO;

import java.util.List;

public interface ResourceClickService extends IService<ResourceClick> {

    /**
     * 查询用户所有资源类型的点击统计
     * @param userId 用户ID
     * @return 各资源类型点击量和占比，按点击量降序
     */
    List<ResourceClickVO> getUserClickStats(Long userId);
}

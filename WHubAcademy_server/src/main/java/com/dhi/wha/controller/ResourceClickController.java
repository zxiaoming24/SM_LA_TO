package com.dhi.wha.controller;

import com.dhi.wha.result.Result;
import com.dhi.wha.server.ResourceClickService;
import com.dhi.wha.vo.ResourceClickVO;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;
import java.util.List;

@RestController
@RequestMapping("/click")
public class ResourceClickController {

    @Resource
    private ResourceClickService resourceClickService;

    /**
     * 查询用户所有资源的点击量统计
     */
    @GetMapping("/stats/{userId}")
    public Result<List<ResourceClickVO>> getUserClickStats(@PathVariable Long userId) {
        return Result.success(resourceClickService.getUserClickStats(userId));
    }
}

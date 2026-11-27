package com.dhi.wha.controller;

import com.dhi.wha.entity.UserOnline;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.UserOnlineService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.annotation.Resource;
import java.util.List;

@RestController
@RequestMapping("/user/online")
public class UserOnlineController {

    @Resource
    private UserOnlineService userOnlineService;

    /**
     * 查询近7天在线时长
     */
    @GetMapping("/{userId}")
    public Result<List<UserOnline>> getLast7DaysOnline(@PathVariable Long userId) {
        return Result.success(userOnlineService.getLast7DaysOnline(userId));
    }
}
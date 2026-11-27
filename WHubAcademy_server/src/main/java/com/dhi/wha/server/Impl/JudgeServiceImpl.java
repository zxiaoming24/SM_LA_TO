package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.JudgePO;
import com.dhi.wha.mapper.JudgeMapper;
import com.dhi.wha.server.JudgeService;
import org.springframework.stereotype.Service;

@Service
public class JudgeServiceImpl extends ServiceImpl<JudgeMapper, JudgePO> implements JudgeService {}

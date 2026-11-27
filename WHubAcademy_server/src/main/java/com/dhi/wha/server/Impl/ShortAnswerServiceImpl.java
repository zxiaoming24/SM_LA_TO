package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.ShortAnswerPO;
import com.dhi.wha.mapper.ShortAnswerMapper;
import com.dhi.wha.server.ShortAnswerService;
import org.springframework.stereotype.Service;

@Service
public class ShortAnswerServiceImpl extends ServiceImpl<ShortAnswerMapper, ShortAnswerPO> implements ShortAnswerService {}

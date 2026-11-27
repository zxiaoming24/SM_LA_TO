package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.MultipleChoicePO;
import com.dhi.wha.mapper.MultipleChoiceMapper;
import com.dhi.wha.server.MultipleChoiceService;
import org.springframework.stereotype.Service;

@Service
public class MultipleChoiceServiceImpl extends ServiceImpl<MultipleChoiceMapper, MultipleChoicePO> implements MultipleChoiceService {}

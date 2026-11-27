package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.Example;
import com.dhi.wha.mapper.ExampleMapper;
import com.dhi.wha.server.ExampleService;
import org.springframework.stereotype.Service;

@Service
public class ExampleServiceImpl extends ServiceImpl<ExampleMapper, Example> implements ExampleService {
}
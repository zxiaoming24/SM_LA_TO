package com.dhi.wha.dto;

import lombok.Data;

import java.util.Map;

@Data
public class ChatContextDTO {
    private String user_id;
    private String user_input;
    private Map<String, String> page_context;
}
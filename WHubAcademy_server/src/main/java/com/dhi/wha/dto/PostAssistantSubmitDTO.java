package com.dhi.wha.dto;

import lombok.Data;
import java.util.List;

@Data
public class PostAssistantSubmitDTO {
    private String user_id;
    private String resource_type;
    private String resource_title;
    private String resource_content;
    private String title;
    private String content;
    private List<String> tags;
    private String zone;
}
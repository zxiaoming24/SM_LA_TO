package com.dhi.wha.dto;

import lombok.Data;

@Data
public class UpdateCodeDTO {
    private Integer invitationId;
    private String userId;
    private String codeContent;
    private String language;
}
package com.dhi.wha.dto;

import lombok.Data;

@Data
public class SendMessageDTO {
    private Integer invitationId;
    private String senderId;
    private String content;
}

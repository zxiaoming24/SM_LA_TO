package com.dhi.wha.dto;

import lombok.Data;

@Data
public class SendInvitationDTO {
    private String inviterId;
    private String inviteeId;
    private String mode;
    private String resourceType;
    private Integer resourceId;
}
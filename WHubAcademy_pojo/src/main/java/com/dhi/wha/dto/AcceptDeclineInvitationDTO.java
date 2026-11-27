package com.dhi.wha.dto;

import lombok.Data;

@Data
public class AcceptDeclineInvitationDTO {
    private Integer inviteId;
    private Boolean accept;
}

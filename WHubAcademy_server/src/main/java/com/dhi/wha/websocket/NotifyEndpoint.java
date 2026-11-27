package com.dhi.wha.websocket;


import com.alibaba.fastjson2.JSON;
import javax.websocket.*;
import javax.websocket.server.ServerEndpoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;

@Component
@ServerEndpoint("/ws/notify")
public class NotifyEndpoint {
    // 用户会话池，聊天室里面的别的名字
    public static final Map<String, Session> NOTIFY_SESSION_MAP = new ConcurrentHashMap<>();
    // 全局定时线程池（心跳超时检测）
    private static final ScheduledExecutorService SCHEDULER = Executors.newScheduledThreadPool(8);

    private String userId;
    private Session session;
    // 当前连接的超时任务
    private ScheduledFuture<?> heartbeatCheckTask;
    // 心跳超时时间 35秒
    private static final long HEARTBEAT_TIMEOUT_SECOND = 35;

    @OnOpen
    public void onOpen(Session session) {
        String query = session.getQueryString();
        if (query == null || !query.startsWith("userId=")) {
            try {
                session.close();
            } catch (IOException e) {}
            return;
        }
        this.userId = query.split("=")[1];
        this.session = session;
        NOTIFY_SESSION_MAP.put(userId, session);
        System.out.println("[通知通道上线] userId = " + userId);
        // 启动心跳超时检测
        startHeartbeatCheck();
    }

    @OnMessage
    public void onMessage(String msgStr) {
        try {
            // 先检查当前会话是否还活着
            if (session == null || !session.isOpen()) {
                System.out.println("[通知通道] 会话已关闭，忽略消息");
                return;
            }

            NotifyMessage msg = JSON.parseObject(msgStr, NotifyMessage.class);

            // 处理心跳 ping
            if ("ping".equals(msg.getType())) {
                resetHeartbeatTimer();
                // 返回 pong
                NotifyMessage pong = new NotifyMessage();
                pong.setType("pong");
                pong.setFrom(msg.getTo());
                pong.setTo(msg.getFrom());
                pong.setRoomId(msg.getRoomId());
                sendSafe(session, JSON.toJSONString(pong));
                return;
            }

            // 被叫拒绝一对一通话，清除呼叫超时定时任务
            if ("VOICE_CALL_REJECT".equals(msg.getType())) {
                String rejectUserId = msg.getFrom();
                String callerUserId = msg.getTo();
                for (Map.Entry<String, SignalEndpoint.CallSession> entry
                        : SignalEndpoint.CALL_SESSION_CACHE.entrySet()) {
                    SignalEndpoint.CallSession cs = entry.getValue();
                    if (cs.callerId.equals(callerUserId) && cs.targetId.equals(rejectUserId)) {
                        cs.cancelTask();
                        SignalEndpoint.CALL_SESSION_CACHE.remove(entry.getKey());
                        System.out.println("[呼叫拒绝，清除超时任务] callId:" + entry.getKey());
                        break;
                    }
                }
            }

            // 处理房间邀请接受
            if ("ROOM_INVITE_ACCEPT".equals(msg.getType())) {
                handleRoomInviteAccept(msg);
                return;
            }

            // 处理房间邀请拒绝
            if ("ROOM_INVITE_REJECT".equals(msg.getType())) {
                handleRoomInviteReject(msg);
                return;
            }

            // 正常业务消息直接转发
            Session target = NOTIFY_SESSION_MAP.get(msg.getTo());
            if (target != null && target.isOpen()) {
                sendSafe(target, msgStr);
            } else {
                System.out.println("[通知通道] 目标会话不存在或已关闭，转发失败 targetId=" + msg.getTo());
            }
        } catch (Exception e) {
            System.out.println("[通知通道] 消息处理异常: " + e.getMessage());
        }
    }

    /**
     * 处理房间邀请接受
     */
    private void handleRoomInviteAccept(NotifyMessage msg) {
        String from = msg.getFrom();
        String to = msg.getTo();
        String roomId = msg.getRoomId();

        System.out.println("[房间邀请接受] from=" + from + " to=" + to + " roomId=" + roomId);

        // 通知邀请者：对方已接受邀请
        NotifyMessage acceptMsg = new NotifyMessage();
        acceptMsg.setType("ROOM_INVITE_ACCEPTED");
        acceptMsg.setFrom(from);
        acceptMsg.setTo(to);
        acceptMsg.setRoomId(roomId);
        Map<String, Object> data = new HashMap<>();
        data.put("roomId", roomId);
        data.put("userId", from);
        acceptMsg.setData(data);
        sendNotify(to, acceptMsg);
    }

    /**
     * 处理房间邀请拒绝
     */
    private void handleRoomInviteReject(NotifyMessage msg) {
        String from = msg.getFrom();
        String to = msg.getTo();
        String roomId = msg.getRoomId();

        System.out.println("[房间邀请拒绝] from=" + from + " to=" + to + " roomId=" + roomId);

        // 通知邀请者：对方已拒绝邀请
        NotifyMessage rejectMsg = new NotifyMessage();
        rejectMsg.setType("ROOM_INVITE_REJECTED");
        rejectMsg.setFrom(from);
        rejectMsg.setTo(to);
        rejectMsg.setRoomId(roomId);
        Map<String, Object> data = new HashMap<>();
        data.put("roomId", roomId);
        data.put("userId", from);
        rejectMsg.setData(data);
        sendNotify(to, rejectMsg);
    }

    /**
     * 安全发送消息，避免会话关闭时抛出异常
     */
    private void sendSafe(Session target, String json) {
        if (target == null || !target.isOpen()) {
            return;
        }
        try {
            target.getBasicRemote().sendText(json);
        } catch (IllegalStateException | IOException e) {
            System.out.println("[通知通道] 发送失败，会话可能已关闭: " + e.getMessage());
        }
    }

    @OnClose
    public void onClose(CloseReason reason) {
        // 取消心跳定时任务
        cancelHeartbeatTask();
        if (userId != null) {
            NOTIFY_SESSION_MAP.remove(userId);
            String reasonText = reason.getReasonPhrase();
            if ("LOGOUT".equals(reasonText)) {
                System.out.println("[通知通道下线] " + userId + " >>> 用户主动退出登录");
            } else {
                System.out.println("[通知通道下线] " + userId + " >>> 离线原因:" + reasonText);
            }
        }
    }

    @OnError
    public void onError(Session session, Throwable throwable) {
        throwable.printStackTrace();
    }

    /**
     * 开启心跳超时检测
     */
    private void startHeartbeatCheck() {
        heartbeatCheckTask = SCHEDULER.schedule(() -> {
            try {
                if (session.isOpen()) {
                    System.out.println("[心跳超时断开] userId:" + userId);
                    session.close(new CloseReason(CloseReason.CloseCodes.PROTOCOL_ERROR, "heartbeat timeout"));
                }
            } catch (IOException e) {
                e.printStackTrace();
            }
        }, HEARTBEAT_TIMEOUT_SECOND, TimeUnit.SECONDS);
    }

    /**
     * 收到ping，重置计时器
     */
    private void resetHeartbeatTimer() {
        cancelHeartbeatTask();
        startHeartbeatCheck();
    }

    /**
     * 销毁定时任务
     */
    private void cancelHeartbeatTask() {
        if (heartbeatCheckTask != null && !heartbeatCheckTask.isDone()) {
            heartbeatCheckTask.cancel(true);
        }
    }

    /**
     * 服务端主动推送消息对外暴露静态方法（给SignalEndpoint调用）
     */
    public static void sendNotify(String targetUserId, NotifyMessage message) {
        Session session = NOTIFY_SESSION_MAP.get(targetUserId);
        if (session == null || !session.isOpen()) {
            System.out.println("[通知通道] 目标会话不存在或已关闭，发送失败 targetId=" + targetUserId);
            return;
        }
        try {
            String json = JSON.toJSONString(message);
            session.getBasicRemote().sendText(json);
        } catch (IllegalStateException | IOException e) {
            System.out.println("[通知通道] 发送失败，会话可能已关闭 targetId=" + targetUserId + ", error=" + e.getMessage());
            NOTIFY_SESSION_MAP.remove(targetUserId);
        }
    }

    /**
     * 向房间内所有成员广播通知
     */
    public static void broadcastToRoom(String roomId, NotifyMessage message) {
        SignalEndpoint.Room room = SignalEndpoint.ROOM_MAP.get(roomId);
        if (room == null) {
            System.out.println("[通知通道] 房间不存在，广播失败 roomId=" + roomId);
            return;
        }

        String json = JSON.toJSONString(message);
        for (String participant : room.getParticipants()) {
            Session session = NOTIFY_SESSION_MAP.get(participant);
            if (session != null && session.isOpen()) {
                try {
                    session.getBasicRemote().sendText(json);
                } catch (IllegalStateException | IOException e) {
                    System.out.println("[通知通道] 广播发送失败 userId=" + participant + ", error=" + e.getMessage());
                }
            }
        }
    }

    /**
     * 检查用户是否在线
     */
    public static boolean isUserOnline(String userId) {
        Session session = NOTIFY_SESSION_MAP.get(userId);
        return session != null && session.isOpen();
    }

    public static class NotifyMessage {
        private String type;
        private String from;
        private String to;
        private Object data;
        private String roomId;

        public String getType() {return type;}
        public void setType(String type) {this.type = type;}
        public String getFrom() {return from;}
        public void setFrom(String from) {this.from = from;}
        public String getTo() {return to;}
        public void setTo(String to) {this.to = to;}
        public Object getData() {return data;}
        public void setData(Object data) {this.data = data;}
        public String getRoomId() {return roomId;}
        public void setRoomId(String roomId) {this.roomId = roomId;}
    }
}

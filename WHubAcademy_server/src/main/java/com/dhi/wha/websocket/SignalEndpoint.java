package com.dhi.wha.websocket;


import com.alibaba.fastjson2.JSON;
import javax.websocket.*;
import javax.websocket.server.ServerEndpoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;

@Component
@ServerEndpoint("/ws/signal")
public class SignalEndpoint {
    public static final Map<String, Session> SIGNAL_SESSION_MAP = new ConcurrentHashMap<>();
    // 呼叫会话缓存 key:callId (一对一通话)
    public static final Map<String, CallSession> CALL_SESSION_CACHE = new ConcurrentHashMap<>();
    private static final ScheduledExecutorService CALL_SCHEDULER = Executors.newScheduledThreadPool(4);
    // 呼叫邀请超时时间：120秒
    private static final long INVITE_TIMEOUT_SECOND = 120;

    // ========== 多人通话房间相关 ==========
    // 房间缓存 key:roomId
    public static final Map<String, Room> ROOM_MAP = new ConcurrentHashMap<>();
    // 用户所在房间缓存 key:userId -> roomId
    public static final Map<String, String> USER_ROOM_MAP = new ConcurrentHashMap<>();
    private static final ScheduledExecutorService ROOM_SCHEDULER = Executors.newScheduledThreadPool(4);
    // 房间空闲超时时间：30分钟
    private static final long ROOM_TIMEOUT_MINUTES = 30;

    private String userId;

    /**
     * 一对一呼叫会话实体
     */
    public static class CallSession {
        private String callId;
        String callerId;
        String targetId;
        private ScheduledFuture<?> timeoutTask;

        public CallSession(String callId, String callerId, String targetId, ScheduledFuture<?> task) {
            this.callId = callId;
            this.callerId = callerId;
            this.targetId = targetId;
            this.timeoutTask = task;
        }

        public void cancelTask() {
            if (timeoutTask != null && !timeoutTask.isDone()) {
                timeoutTask.cancel(true);
            }
        }
    }

    /**
     * 多人通话房间实体
     * topology: "mesh" - 端到端Mesh拓扑 | "sfu" - SFU服务端转发拓扑
     */
    public static class Room {
        private String roomId;
        private String creatorId;
        private Set<String> participants;
        private long createdAt;
        private ScheduledFuture<?> timeoutTask;
        private String topology; // "mesh" 或 "sfu"
        private String sfuEndpoint; // SFU连接地址（仅sfu模式）

        public Room(String roomId, String creatorId) {
            this(roomId, creatorId, "mesh");
        }

        public Room(String roomId, String creatorId, String topology) {
            this.roomId = roomId;
            this.creatorId = creatorId;
            this.participants = ConcurrentHashMap.newKeySet();
            this.participants.add(creatorId);
            this.createdAt = System.currentTimeMillis();
            this.topology = topology;
        }

        public String getRoomId() { return roomId; }
        public String getCreatorId() { return creatorId; }
        public Set<String> getParticipants() { return participants; }
        public long getCreatedAt() { return createdAt; }
        public String getTopology() { return topology; }
        public void setTopology(String topology) { this.topology = topology; }
        public String getSfuEndpoint() { return sfuEndpoint; }
        public void setSfuEndpoint(String sfuEndpoint) { this.sfuEndpoint = sfuEndpoint; }

        public boolean isEmpty() {
            return participants.isEmpty();
        }

        public int getParticipantCount() {
            return participants.size();
        }

        public void addParticipant(String userId) {
            participants.add(userId);
        }

        public void removeParticipant(String userId) {
            participants.remove(userId);
        }

        public void setTimeoutTask(ScheduledFuture<?> task) {
            this.timeoutTask = task;
        }

        public void cancelTimeoutTask() {
            if (timeoutTask != null && !timeoutTask.isDone()) {
                timeoutTask.cancel(true);
            }
        }
    }

    //建立websocket连接的时候调用
    @OnOpen
    public void onOpen(Session session) {
        String query = session.getQueryString();
        if (query == null || !query.startsWith("userId=")) {
            try {
                session.close();
            } catch (IOException e) {}
            return;
        }
        userId = query.split("=")[1];
        SIGNAL_SESSION_MAP.put(userId, session);
        System.out.println("[语音信令上线] " + userId);
    }

    //接收到浏览器消息的时候调用
    @OnMessage
    public void onMessage(String msgStr) {
        try {
            SignalMessage msg = JSON.parseObject(msgStr, SignalMessage.class);
            String type = msg.getType();
            String from = msg.getFrom();
            String targetId = msg.getTo();

            // ========== 多人通话：创建房间 ==========
            if ("CREATE_ROOM".equals(type) || "CREATE_SFU_ROOM".equals(type)) {
                handleCreateRoom(from, msg);
                return;
            }

            // ========== 多人通话：加入房间 ==========
            if ("JOIN_ROOM".equals(type)) {
                handleJoinRoom(from, msg);
                return;
            }

            // ========== 多人通话：离开房间 ==========
            if ("LEAVE_ROOM".equals(type)) {
                handleLeaveRoom(from, msg);
                return;
            }

            // ========== 多人通话：房间邀请 ==========
            if ("ROOM_INVITE".equals(type)) {
                handleRoomInvite(from, msg);
                return;
            }

            // ========== 多人通话：获取房间成员 ==========
            if ("GET_ROOM_PARTICIPANTS".equals(type)) {
                handleGetRoomParticipants(from, msg);
                return;
            }

            // ========== 一对一：发起呼叫 invite ==========
            if ("invite".equals(type)) {
                handleInvite(from, targetId, msg);
                return;
            }

            // ========== 一对一：接听 accept 清除超时任务 ==========
            if ("accept".equals(type)) {
                clearCallTimeoutTask(from, targetId);
            }

            // ========== 多人通话信令转发（room offer/answer/candidate/hangup） ==========
            if (msg.getRoomId() != null && !msg.getRoomId().isEmpty()) {
                handleRoomSignaling(msg);
                return;
            }

            // ========== 一对一信令透传 ==========
            Session targetSession = SIGNAL_SESSION_MAP.get(targetId);
            if (targetSession != null && targetSession.isOpen()) {
                try {
                    targetSession.getBasicRemote().sendText(msgStr);
                } catch (IllegalStateException | IOException e) {
                    System.out.println("[信令通道] 发送失败，会话可能已关闭 targetId=" + targetId);
                }
            } else {
                System.out.println("[信令通道] 目标会话不存在或已关闭 targetId=" + targetId);
            }
        } catch (Exception e) {
            System.out.println("[信令通道] 消息处理异常: " + e.getMessage());
        }
    }

    /**
     * 处理创建房间（Mesh或SFU）
     */
    private void handleCreateRoom(String from, SignalMessage msg) {
        String roomId = msg.getRoomId();
        if (roomId == null || roomId.isEmpty()) {
            roomId = UUID.randomUUID().toString().substring(0, 8);
        }

        String topology = "mesh";
        if ("CREATE_SFU_ROOM".equals(msg.getType())) {
            topology = (String) ((Map<String, Object>) msg.getData()).get("topology");
            if (topology == null) {
                topology = "sfu";
            }
        }

        Room room = new Room(roomId, from, topology);
        ROOM_MAP.put(roomId, room);
        USER_ROOM_MAP.put(from, roomId);

        // 如果是SFU房间，构造SFU连接地址
        if ("sfu".equals(topology)) {
            // 创建对应的SFU房间
            SfuEndpoint.SfuRoom sfuRoom = new SfuEndpoint.SfuRoom(roomId);
            SfuEndpoint.SFU_ROOMS.put(roomId, sfuRoom);

            // WS: /ws/sfu?roomId=xxx&userId=xxx 的连接地址由前端拼接
            String sfuEndpointPath = "/ws/sfu";
            room.setSfuEndpoint(sfuEndpointPath);
            System.out.println("[SFU房间] 创建SFU房间 roomId=" + roomId + " creator=" + from);
        }

        // 重置房间超时计时器
        resetRoomTimeout(roomId);

        System.out.println("[" + topology + "房间] 创建房间 roomId=" + roomId + " creator=" + from);

        // 通知创建者房间已创建
        SignalMessage resp = new SignalMessage();
        resp.setType("ROOM_CREATED");
        resp.setFrom("server");
        resp.setTo(from);
        resp.setRoomId(roomId);
        Map<String, Object> data = new HashMap<>();
        data.put("roomId", roomId);
        data.put("participants", new ArrayList<>(room.getParticipants()));
        data.put("topology", topology);
        if (room.getSfuEndpoint() != null) {
            data.put("sfuEndpoint", room.getSfuEndpoint());
        }
        resp.setData(data);
        sendToUser(from, resp);
    }

    /**
     * 处理加入房间
     */
    private void handleJoinRoom(String from, SignalMessage msg) {
        String roomId = msg.getRoomId();
        Room room = ROOM_MAP.get(roomId);

        if (room == null) {
            // 房间不存在，通知加入者房间不存在
            SignalMessage resp = new SignalMessage();
            resp.setType("ROOM_NOT_FOUND");
            resp.setFrom("server");
            resp.setTo(from);
            resp.setRoomId(roomId);
            resp.setData("房间不存在或已解散");
            sendToUser(from, resp);
            return;
        }

        // 将用户加入房间
        room.addParticipant(from);
        USER_ROOM_MAP.put(from, roomId);
        resetRoomTimeout(roomId);

        System.out.println("[多人通话] 用户加入房间 roomId=" + roomId + " userId=" + from);

        // 通知加入者：加入成功，返回当前房间成员列表
        SignalMessage joinedResp = new SignalMessage();
        joinedResp.setType("ROOM_JOINED");
        joinedResp.setFrom("server");
        joinedResp.setTo(from);
        joinedResp.setRoomId(roomId);
        Map<String, Object> joinedData = new HashMap<>();
        joinedData.put("roomId", roomId);
        joinedData.put("participants", new ArrayList<>(room.getParticipants()));
        joinedData.put("topology", room.getTopology());
        if ("sfu".equals(room.getTopology()) && room.getSfuEndpoint() != null) {
            joinedData.put("sfuEndpoint", room.getSfuEndpoint());
        }
        joinedResp.setData(joinedData);
        sendToUser(from, joinedResp);

        // 通知房间内其他成员：有新成员加入
        for (String participant : room.getParticipants()) {
            if (!participant.equals(from)) {
                SignalMessage notifyMsg = new SignalMessage();
                notifyMsg.setType("PARTICIPANT_JOINED");
                notifyMsg.setFrom(from);
                notifyMsg.setTo(participant);
                notifyMsg.setRoomId(roomId);
                Map<String, Object> notifyData = new HashMap<>();
                notifyData.put("userId", from);
                notifyData.put("participants", new ArrayList<>(room.getParticipants()));
                notifyMsg.setData(notifyData);
                sendToUser(participant, notifyMsg);
            }
        }
    }

    /**
     * 处理离开房间
     */
    private void handleLeaveRoom(String from, SignalMessage msg) {
        String roomId = msg.getRoomId();
        Room room = ROOM_MAP.get(roomId);

        if (room == null) {
            USER_ROOM_MAP.remove(from);
            return;
        }

        // 从房间移除用户
        room.removeParticipant(from);
        USER_ROOM_MAP.remove(from);

        System.out.println("[多人通话] 用户离开房间 roomId=" + roomId + " userId=" + from);

        // 通知房间内其他成员：有成员离开
        for (String participant : room.getParticipants()) {
            SignalMessage notifyMsg = new SignalMessage();
            notifyMsg.setType("PARTICIPANT_LEFT");
            notifyMsg.setFrom(from);
            notifyMsg.setTo(participant);
            notifyMsg.setRoomId(roomId);
            Map<String, Object> notifyData = new HashMap<>();
            notifyData.put("userId", from);
            notifyData.put("participants", new ArrayList<>(room.getParticipants()));
            notifyMsg.setData(notifyData);
            sendToUser(participant, notifyMsg);
        }

        // 如果房间为空，销毁房间
        if (room.isEmpty()) {
            destroyRoom(roomId);
        } else {
            resetRoomTimeout(roomId);
        }
    }

    /**
     * 处理房间邀请
     */
    private void handleRoomInvite(String from, SignalMessage msg) {
        String roomId = msg.getRoomId();
        String targetId = msg.getTo();

        Room room = ROOM_MAP.get(roomId);
        if (room == null) {
            SignalMessage resp = new SignalMessage();
            resp.setType("ROOM_NOT_FOUND");
            resp.setFrom("server");
            resp.setTo(from);
            resp.setRoomId(roomId);
            resp.setData("房间不存在或已解散");
            sendToUser(from, resp);
            return;
        }

        // 检查被邀请者是否在线
        if (!SIGNAL_SESSION_MAP.containsKey(targetId)) {
            // 被邀请者不在线，通知邀请者
            SignalMessage resp = new SignalMessage();
            resp.setType("USER_OFFLINE");
            resp.setFrom(targetId);
            resp.setTo(from);
            resp.setRoomId(roomId);
            resp.setData("对方尚未登录，无法邀请");
            sendToUser(from, resp);
            return;
        }

        // 发送房间邀请通知给被邀请者（通过NotifyEndpoint）
        NotifyEndpoint.NotifyMessage inviteNotify = new NotifyEndpoint.NotifyMessage();
        inviteNotify.setType("ROOM_INVITE");
        inviteNotify.setFrom(from);
        inviteNotify.setTo(targetId);
        Map<String, Object> inviteData = new HashMap<>();
        inviteData.put("roomId", roomId);
        inviteData.put("roomParticipants", new ArrayList<>(room.getParticipants()));
        inviteData.put("creatorId", room.getCreatorId());
        inviteData.put("topology", room.getTopology());
        if ("sfu".equals(room.getTopology()) && room.getSfuEndpoint() != null) {
            inviteData.put("sfuEndpoint", room.getSfuEndpoint());
        }
        inviteNotify.setData(inviteData);
        NotifyEndpoint.sendNotify(targetId, inviteNotify);

        // 通知邀请者：邀请已发送
        SignalMessage resp = new SignalMessage();
        resp.setType("ROOM_INVITE_SENT");
        resp.setFrom("server");
        resp.setTo(from);
        resp.setRoomId(roomId);
        resp.setData("邀请已发送给 " + targetId);
        sendToUser(from, resp);
    }

    /**
     * 处理获取房间成员列表
     */
    private void handleGetRoomParticipants(String from, SignalMessage msg) {
        String roomId = msg.getRoomId();
        Room room = ROOM_MAP.get(roomId);

        SignalMessage resp = new SignalMessage();
        resp.setType("ROOM_PARTICIPANTS");
        resp.setFrom("server");
        resp.setTo(from);
        resp.setRoomId(roomId);

        if (room != null) {
            Map<String, Object> data = new HashMap<>();
            data.put("roomId", roomId);
            data.put("participants", new ArrayList<>(room.getParticipants()));
            data.put("participantCount", room.getParticipantCount());
            resp.setData(data);
        } else {
            resp.setData(null);
        }
        sendToUser(from, resp);
    }

    /**
     * 处理多人通话信令转发
     */
    private void handleRoomSignaling(SignalMessage msg) {
        String roomId = msg.getRoomId();
        String from = msg.getFrom();
        String targetId = msg.getTo();
        String type = msg.getType();

        Room room = ROOM_MAP.get(roomId);
        if (room == null) {
            System.out.println("[多人通话] 房间不存在 roomId=" + roomId);
            return;
        }

        // 如果指定了目标用户，直接转发给目标
        if (targetId != null && !targetId.isEmpty()) {
            sendToUser(targetId, msg);
        } else {
            // 广播给房间内所有其他成员（用于offer广播等）
            for (String participant : room.getParticipants()) {
                if (!participant.equals(from)) {
                    sendToUser(participant, msg);
                }
            }
        }
    }

    /**
     * 一对一呼叫处理
     */
    private void handleInvite(String from, String targetId, SignalMessage msg) {
        // 判断目标用户是否在线（通知通道是否存在）
        if (!NotifyEndpoint.NOTIFY_SESSION_MAP.containsKey(targetId)) {
            NotifyEndpoint.NotifyMessage offlineMsg = new NotifyEndpoint.NotifyMessage();
            offlineMsg.setType("USER_OFFLINE");
            offlineMsg.setFrom(targetId);
            offlineMsg.setTo(from);
            offlineMsg.setData("对方尚未登录，暂时无法发起语音通话");
            NotifyEndpoint.sendNotify(from, offlineMsg);
            return;
        }

        String callId = UUID.randomUUID().toString();
        // 构建超时任务
        ScheduledFuture<?> task = CALL_SCHEDULER.schedule(() -> {
            CallSession session = CALL_SESSION_CACHE.remove(callId);
            if (session == null) return;
            System.out.println("呼叫超时 callId:" + callId + " caller:" + session.callerId + " target:" + session.targetId);
            // 通知发起方 呼叫超时
            NotifyEndpoint.NotifyMessage notifyCaller = new NotifyEndpoint.NotifyMessage();
            notifyCaller.setType("CALL_INVITE_TIMEOUT");
            notifyCaller.setFrom(session.targetId);
            notifyCaller.setTo(session.callerId);
            notifyCaller.setData("对方可能在忙，请等会再通话");
            NotifyEndpoint.sendNotify(session.callerId, notifyCaller);

            // 通知被叫清理弹窗
            NotifyEndpoint.NotifyMessage notifyTarget = new NotifyEndpoint.NotifyMessage();
            notifyTarget.setType("CALL_INVITE_TIMEOUT");
            notifyTarget.setFrom(session.callerId);
            notifyTarget.setTo(session.targetId);
            notifyTarget.setData("呼叫已超时");
            NotifyEndpoint.sendNotify(session.targetId, notifyTarget);
        }, INVITE_TIMEOUT_SECOND, TimeUnit.SECONDS);

        CallSession callSession = new CallSession(callId, from, targetId, task);
        CALL_SESSION_CACHE.put(callId, callSession);

        // 推送来电通知给被叫
        NotifyEndpoint.NotifyMessage notify = new NotifyEndpoint.NotifyMessage();
        notify.setType("VOICE_CALL_INVITE");
        notify.setFrom(from);
        notify.setTo(targetId);
        notify.setData("对方请求语音通话");
        NotifyEndpoint.sendNotify(targetId, notify);
    }

    /**
     * 根据呼叫双方清除呼叫超时任务
     */
    private void clearCallTimeoutTask(String targetId, String callerId) {
        for (Map.Entry<String, CallSession> entry : CALL_SESSION_CACHE.entrySet()) {
            CallSession cs = entry.getValue();
            if (cs.callerId.equals(callerId) && cs.targetId.equals(targetId)) {
                cs.cancelTask();
                CALL_SESSION_CACHE.remove(entry.getKey());
                break;
            }
        }
    }

    /**
     * 向指定用户发送消息
     */
    private void sendToUser(String userId, SignalMessage msg) {
        Session session = SIGNAL_SESSION_MAP.get(userId);
        if (session == null || !session.isOpen()) {
            System.out.println("[信令通道] 目标会话不存在或已关闭 userId=" + userId);
            return;
        }
        try {
            session.getBasicRemote().sendText(JSON.toJSONString(msg));
        } catch (IllegalStateException | IOException e) {
            System.out.println("[信令通道] 发送失败 userId=" + userId + ", error=" + e.getMessage());
        }
    }

    /**
     * 重置房间超时计时器
     */
    private void resetRoomTimeout(String roomId) {
        Room room = ROOM_MAP.get(roomId);
        if (room == null) return;

        room.cancelTimeoutTask();

        ScheduledFuture<?> task = ROOM_SCHEDULER.schedule(() -> {
            Room timeoutRoom = ROOM_MAP.get(roomId);
            if (timeoutRoom != null && !timeoutRoom.isEmpty()) {
                // 房间还有成员，再检查一次（可能刚有新成员加入）
                System.out.println("[房间超时] roomId=" + roomId + " 但还有成员，重新计时");
                resetRoomTimeout(roomId);
            } else {
                destroyRoom(roomId);
            }
        }, ROOM_TIMEOUT_MINUTES, TimeUnit.MINUTES);

        room.setTimeoutTask(task);
    }

    /**
     * 销毁房间
     */
    private void destroyRoom(String roomId) {
        Room room = ROOM_MAP.remove(roomId);
        if (room != null) {
            room.cancelTimeoutTask();
            // 清理用户房间映射
            for (String participant : room.getParticipants()) {
                USER_ROOM_MAP.remove(participant);
            }
            // 如果是SFU房间，同步清理SFU房间
            if ("sfu".equals(room.getTopology())) {
                SfuEndpoint.SfuRoom sfuRoom = SfuEndpoint.SFU_ROOMS.remove(roomId);
                if (sfuRoom != null) {
                    System.out.println("[SFU房间] 同步销毁 roomId=" + roomId);
                }
            }
            System.out.println("[房间销毁] roomId=" + roomId);
        }
    }

    //断开websocket连接的时候调用
    @OnClose
    public void onClose() {
        if (userId != null) {
            // 如果用户在房间中，自动离开房间
            String roomId = USER_ROOM_MAP.get(userId);
            if (roomId != null) {
                Room room = ROOM_MAP.get(roomId);
                if (room != null) {
                    room.removeParticipant(userId);
                    USER_ROOM_MAP.remove(userId);

                    // 通知房间内其他成员
                    for (String participant : room.getParticipants()) {
                        SignalMessage notifyMsg = new SignalMessage();
                        notifyMsg.setType("PARTICIPANT_LEFT");
                        notifyMsg.setFrom(userId);
                        notifyMsg.setTo(participant);
                        notifyMsg.setRoomId(roomId);
                        Map<String, Object> notifyData = new HashMap<>();
                        notifyData.put("userId", userId);
                        notifyData.put("participants", new ArrayList<>(room.getParticipants()));
                        notifyMsg.setData(notifyData);
                        sendToUser(participant, notifyMsg);
                    }

                    if (room.isEmpty()) {
                        destroyRoom(roomId);
                    } else {
                        resetRoomTimeout(roomId);
                    }
                }
            }

            SIGNAL_SESSION_MAP.remove(userId);
            System.out.println("[语音信令下线] " + userId);
        }
    }

    //异常的时候调用
    @OnError
    public void onError(Session session, Throwable throwable) {
        throwable.printStackTrace();
    }

    public static class SignalMessage {
        private String from;
        private String to;
        private String type;
        private Object data;
        private String roomId;

        public String getFrom() {return from;}
        public void setFrom(String from) {this.from = from;}
        public String getTo() {return to;}
        public void setTo(String to) {this.to = to;}
        public String getType() {return type;}
        public void setType(String type) {this.type = type;}
        public Object getData() {return data;}
        public void setData(Object data) {this.data = data;}
        public String getRoomId() {return roomId;}
        public void setRoomId(String roomId) {this.roomId = roomId;}
    }
}

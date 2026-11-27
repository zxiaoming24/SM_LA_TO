package com.dhi.wha.websocket;

import com.alibaba.fastjson2.JSON;
import javax.websocket.*;
import javax.websocket.server.ServerEndpoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArraySet;

/**
 * SFU（Selective Forwarding Unit）端点
 * 负责多人语音/视频通话的媒体流转发
 *
 * 文本信令消息：
 *   JOIN_SFU_ROOM  - 加入SFU房间
 *   LEAVE_SFU_ROOM - 离开SFU房间
 *   PUBLISH_STREAM - 发布媒体流
 *   UNPUBLISH_STREAM - 取消发布媒体流
 *   SUBSCRIBE_ALL  - 订阅房间内所有流
 *   SUBSCRIBE      - 订阅指定流
 *   UNSUBSCRIBE    - 取消订阅指定流
 *
 * 服务端推送信令：
 *   SFU_JOINED         - 加入房间成功，返回房间信息
 *   SFU_STREAM_ADDED   - 有新的媒体流可用
 *   SFU_STREAM_REMOVED - 有媒体流被移除
 *   SFU_PARTICIPANT_JOINED - 新参与者加入
 *   SFU_PARTICIPANT_LEFT   - 参与者离开
 *
 * 二进制消息格式（媒体转发）：
 *   [2字节 streamId长度] [N字节 streamId UTF-8] [剩余字节 = RTP媒体数据]
 *   说明：streamId为可变长度，最大65535字节
 */
@Component
@ServerEndpoint("/ws/sfu")
public class SfuEndpoint {

    // ========== 房间和参与者管理 ==========
    public static final Map<String, SfuRoom> SFU_ROOMS = new ConcurrentHashMap<>();
    // 用户所在SFU房间映射
    private static final Map<String, String> USER_SFU_ROOM_MAP = new ConcurrentHashMap<>();

    // ========== 流信息管理 ==========
    // streamId -> StreamInfo
    private static final Map<String, StreamInfo> STREAM_INFO_MAP = new ConcurrentHashMap<>();

    private String userId;
    private String roomId;
    private Session session;

    @OnOpen
    public void onOpen(Session session) {
        String query = session.getQueryString();
        if (query == null) {
            try { session.close(); } catch (IOException ignored) {}
            return;
        }

        // 解析参数: roomId=xxx&userId=xxx
        Map<String, String> params = parseQueryString(query);
        this.userId = params.get("userId");
        this.roomId = params.get("roomId");

        if (userId == null || roomId == null) {
            System.out.println("[SFU] 参数不完整，拒绝连接 roomId=" + roomId + " userId=" + userId);
            try { session.close(); } catch (IOException ignored) {}
            return;
        }

        this.session = session;
        System.out.println("[SFU连接上线] roomId=" + roomId + " userId=" + userId);
    }

    /**
     * 处理文本信令消息
     */
    @OnMessage
    public void onTextMessage(String text) {
        try {
            if (session == null || !session.isOpen()) {
                return;
            }

            SfuMessage msg = JSON.parseObject(text, SfuMessage.class);
            String type = msg.getType();

            switch (type) {
                case "JOIN_SFU_ROOM":
                    handleJoinRoom(msg);
                    break;
                case "LEAVE_SFU_ROOM":
                    handleLeaveRoom(msg);
                    break;
                case "PUBLISH_STREAM":
                    handlePublishStream(msg);
                    break;
                case "UNPUBLISH_STREAM":
                    handleUnpublishStream(msg);
                    break;
                case "SUBSCRIBE_ALL":
                    handleSubscribeAll(msg);
                    break;
                case "SUBSCRIBE":
                    handleSubscribe(msg);
                    break;
                case "UNSUBSCRIBE":
                    handleUnsubscribe(msg);
                    break;
                default:
                    System.out.println("[SFU] 未知信令类型: " + type + " userId=" + userId);
            }
        } catch (Exception e) {
            System.out.println("[SFU] 信令处理异常 userId=" + userId + " error=" + e.getMessage());
        }
    }

    /**
     * 处理二进制媒体数据，转发给订阅者
     *
     * 二进制格式：
     *   [2字节 streamId长度] [N字节 streamId UTF-8] [剩余字节 = 媒体数据]
     */
    @OnMessage
    public void onBinaryMessage(byte[] binaryData) {
        if (binaryData == null || binaryData.length < 3) {
            return; // 至少2字节长度 + 1字节streamId
        }

        try {
            // 解析streamId
            ByteBuffer buffer = ByteBuffer.wrap(binaryData);
            int streamIdLen = buffer.getShort() & 0xFFFF;

            if (streamIdLen <= 0 || streamIdLen > binaryData.length - 2) {
                return;
            }

            byte[] streamIdBytes = new byte[streamIdLen];
            buffer.get(streamIdBytes);
            String streamId = new String(streamIdBytes, StandardCharsets.UTF_8);

            // 计算媒体数据部分
            int mediaOffset = 2 + streamIdLen;
            int mediaLen = binaryData.length - mediaOffset;
            if (mediaLen <= 0) {
                return;
            }

            // 获取流信息
            StreamInfo streamInfo = STREAM_INFO_MAP.get(streamId);
            if (streamInfo == null) {
                return;
            }

            // 查找房间
            String roomId = USER_SFU_ROOM_MAP.get(userId);
            if (roomId == null) {
                return;
            }

            SfuRoom room = SFU_ROOMS.get(roomId);
            if (room == null) {
                return;
            }

            // 构造转发数据（复用原始消息，避免拷贝）
            byte[] forwardData = binaryData;

            // 转发给房间内所有订阅了该流的其他参与者
            for (Map.Entry<String, SfuParticipant> entry : room.participants.entrySet()) {
                String targetUserId = entry.getKey();
                if (targetUserId.equals(userId)) {
                    continue; // 不转发给发送者自己
                }

                SfuParticipant target = entry.getValue();
                if (target.session == null || !target.session.isOpen()) {
                    continue;
                }

                // 检查该参与者是否订阅了这个流
                if (target.subscribedStreams.contains(streamId) || target.subscribeAll) {
                    try {
                        synchronized (target.session) {
                            target.session.getBasicRemote().sendBinary(ByteBuffer.wrap(forwardData));
                        }
                    } catch (IllegalStateException | IOException e) {
                        System.out.println("[SFU] 转发失败 userId=" + targetUserId + " error=" + e.getMessage());
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("[SFU] 媒体转发异常 userId=" + userId + " error=" + e.getMessage());
        }
    }

    // ==================== 信令处理方法 ====================

    /**
     * 加入SFU房间
     */
    private void handleJoinRoom(SfuMessage msg) {
        String targetRoomId = msg.getRoomId() != null ? msg.getRoomId() : this.roomId;
        if (targetRoomId == null) {
            sendError("roomId不能为空");
            return;
        }

        this.roomId = targetRoomId;

        // 获取或创建房间
        SfuRoom room = SFU_ROOMS.computeIfAbsent(targetRoomId, k -> new SfuRoom(targetRoomId));

        // 如果用户已在其他房间，先离开
        String oldRoomId = USER_SFU_ROOM_MAP.get(userId);
        if (oldRoomId != null && !oldRoomId.equals(targetRoomId)) {
            SfuRoom oldRoom = SFU_ROOMS.get(oldRoomId);
            if (oldRoom != null) {
                oldRoom.removeParticipant(userId);
            }
        }

        // 检查是否已经在房间中
        if (room.participants.containsKey(userId)) {
            // 更新session
            room.participants.get(userId).session = this.session;
        } else {
            // 新参与者
            SfuParticipant participant = new SfuParticipant(userId, this.session);
            room.addParticipant(participant);
            USER_SFU_ROOM_MAP.put(userId, targetRoomId);
        }

        System.out.println("[SFU] 用户加入房间 roomId=" + targetRoomId + " userId=" + userId +
                " 当前人数=" + room.getParticipantCount());

        // 获取所有可用流
        List<Map<String, Object>> streamList = new ArrayList<>();
        for (StreamInfo si : STREAM_INFO_MAP.values()) {
            if (room.participants.containsKey(si.userId)) {
                Map<String, Object> sMap = new HashMap<>();
                sMap.put("streamId", si.streamId);
                sMap.put("userId", si.userId);
                sMap.put("kind", si.kind);
                streamList.add(sMap);
            }
        }

        // 获取参与者列表
        List<String> participantList = new ArrayList<>(room.participants.keySet());

        // 返回加入成功消息
        Map<String, Object> data = new HashMap<>();
        data.put("roomId", targetRoomId);
        data.put("streams", streamList);
        data.put("participants", participantList);

        SfuMessage resp = new SfuMessage();
        resp.setType("SFU_JOINED");
        resp.setFrom("server");
        resp.setTo(userId);
        resp.setRoomId(targetRoomId);
        resp.setData(data);
        sendToSelf(resp);

        // 通知房间内其他用户：有新参与者加入
        for (SfuParticipant p : room.participants.values()) {
            if (!p.userId.equals(userId)) {
                SfuMessage notify = new SfuMessage();
                notify.setType("SFU_PARTICIPANT_JOINED");
                notify.setFrom(userId);
                notify.setTo(p.userId);
                notify.setRoomId(targetRoomId);
                Map<String, Object> notifyData = new HashMap<>();
                notifyData.put("userId", userId);
                notifyData.put("participants", participantList);
                notify.setData(notifyData);
                sendToUser(p.userId, notify);
            }
        }
    }

    /**
     * 离开SFU房间
     */
    private void handleLeaveRoom(SfuMessage msg) {
        leaveRoom(userId);
    }

    /**
     * 发布媒体流
     */
    private void handlePublishStream(SfuMessage msg) {
        String streamId = msg.getStreamId();
        String kind = msg.getKind();

        if (streamId == null || streamId.isEmpty()) {
            sendError("streamId不能为空");
            return;
        }

        if (kind == null) {
            kind = "video"; // 默认video
        }

        String targetRoomId = msg.getRoomId() != null ? msg.getRoomId() : this.roomId;
        if (targetRoomId == null) {
            sendError("不在房间中，无法发布流");
            return;
        }

        SfuRoom room = SFU_ROOMS.get(targetRoomId);
        if (room == null) {
            sendError("房间不存在");
            return;
        }

        SfuParticipant participant = room.participants.get(userId);
        if (participant == null) {
            sendError("未加入房间");
            return;
        }

        // 注册流信息
        StreamInfo streamInfo = new StreamInfo(streamId, userId, kind);
        STREAM_INFO_MAP.put(streamId, streamInfo);
        participant.publishingStreams.add(streamId);

        System.out.println("[SFU] 发布流 roomId=" + targetRoomId + " userId=" + userId +
                " streamId=" + streamId + " kind=" + kind);

        // 通知房间内其他用户：有新流可用
        for (SfuParticipant p : room.participants.values()) {
            if (!p.userId.equals(userId)) {
                SfuMessage notify = new SfuMessage();
                notify.setType("SFU_STREAM_ADDED");
                notify.setFrom(userId);
                notify.setTo(p.userId);
                notify.setRoomId(targetRoomId);
                notify.setStreamId(streamId);
                notify.setKind(kind);
                Map<String, Object> notifyData = new HashMap<>();
                notifyData.put("streamId", streamId);
                notifyData.put("userId", userId);
                notifyData.put("kind", kind);
                notify.setData(notifyData);
                sendToUser(p.userId, notify);
            }
        }

        // 确认发布成功
        SfuMessage resp = new SfuMessage();
        resp.setType("STREAM_PUBLISHED");
        resp.setFrom("server");
        resp.setTo(userId);
        resp.setRoomId(targetRoomId);
        resp.setStreamId(streamId);
        resp.setData("流发布成功: " + streamId);
        sendToSelf(resp);
    }

    /**
     * 取消发布媒体流
     */
    private void handleUnpublishStream(SfuMessage msg) {
        String streamId = msg.getStreamId();
        if (streamId == null) {
            return;
        }

        String targetRoomId = msg.getRoomId() != null ? msg.getRoomId() : this.roomId;
        SfuRoom room = targetRoomId != null ? SFU_ROOMS.get(targetRoomId) : null;

        // 移除流信息
        STREAM_INFO_MAP.remove(streamId);
        if (room != null) {
            SfuParticipant participant = room.participants.get(userId);
            if (participant != null) {
                participant.publishingStreams.remove(streamId);
            }
        }

        System.out.println("[SFU] 取消发布流 userId=" + userId + " streamId=" + streamId);

        // 通知房间内其他用户
        if (room != null) {
            for (SfuParticipant p : room.participants.values()) {
                if (!p.userId.equals(userId)) {
                    SfuMessage notify = new SfuMessage();
                    notify.setType("SFU_STREAM_REMOVED");
                    notify.setFrom(userId);
                    notify.setTo(p.userId);
                    notify.setRoomId(targetRoomId);
                    notify.setStreamId(streamId);
                    notify.setData("流已移除: " + streamId);
                    sendToUser(p.userId, notify);
                }
            }
        }

        SfuMessage resp = new SfuMessage();
        resp.setType("STREAM_UNPUBLISHED");
        resp.setFrom("server");
        resp.setTo(userId);
        resp.setStreamId(streamId);
        sendToSelf(resp);
    }

    /**
     * 订阅房间内所有流
     */
    private void handleSubscribeAll(SfuMessage msg) {
        String targetRoomId = msg.getRoomId() != null ? msg.getRoomId() : this.roomId;
        SfuRoom room = targetRoomId != null ? SFU_ROOMS.get(targetRoomId) : null;

        if (room == null) {
            sendError("房间不存在");
            return;
        }

        SfuParticipant participant = room.participants.get(userId);
        if (participant == null) {
            sendError("未加入房间");
            return;
        }

        participant.subscribeAll = true;
        participant.subscribedStreams.clear();

        // 通知用户当前所有可用的流（除了自己的）
        List<Map<String, Object>> streamList = new ArrayList<>();
        for (StreamInfo si : STREAM_INFO_MAP.values()) {
            if (room.participants.containsKey(si.userId) && !si.userId.equals(userId)) {
                participant.subscribedStreams.add(si.streamId);
                Map<String, Object> sMap = new HashMap<>();
                sMap.put("streamId", si.streamId);
                sMap.put("userId", si.userId);
                sMap.put("kind", si.kind);
                streamList.add(sMap);
            }
        }

        System.out.println("[SFU] 订阅房间所有流 userId=" + userId + " count=" + streamList.size());

        SfuMessage resp = new SfuMessage();
        resp.setType("SUBSCRIBED_ALL");
        resp.setFrom("server");
        resp.setTo(userId);
        resp.setRoomId(targetRoomId);
        Map<String, Object> data = new HashMap<>();
        data.put("streams", streamList);
        data.put("count", streamList.size());
        resp.setData(data);
        sendToSelf(resp);
    }

    /**
     * 订阅指定流
     */
    private void handleSubscribe(SfuMessage msg) {
        String streamId = msg.getStreamId();
        if (streamId == null) {
            sendError("streamId不能为空");
            return;
        }

        String targetRoomId = msg.getRoomId() != null ? msg.getRoomId() : this.roomId;
        SfuRoom room = targetRoomId != null ? SFU_ROOMS.get(targetRoomId) : null;
        if (room == null) {
            sendError("房间不存在");
            return;
        }

        SfuParticipant participant = room.participants.get(userId);
        if (participant == null) {
            sendError("未加入房间");
            return;
        }

        participant.subscribedStreams.add(streamId);
        System.out.println("[SFU] 订阅流 userId=" + userId + " streamId=" + streamId);

        SfuMessage resp = new SfuMessage();
        resp.setType("SUBSCRIBED");
        resp.setFrom("server");
        resp.setTo(userId);
        resp.setStreamId(streamId);
        sendToSelf(resp);
    }

    /**
     * 取消订阅流
     */
    private void handleUnsubscribe(SfuMessage msg) {
        String streamId = msg.getStreamId();

        String targetRoomId = msg.getRoomId() != null ? msg.getRoomId() : this.roomId;
        SfuRoom room = targetRoomId != null ? SFU_ROOMS.get(targetRoomId) : null;
        if (room == null) return;

        SfuParticipant participant = room.participants.get(userId);
        if (participant == null) return;

        if (streamId != null) {
            participant.subscribedStreams.remove(streamId);
        }

        SfuMessage resp = new SfuMessage();
        resp.setType("UNSUBSCRIBED");
        resp.setFrom("server");
        resp.setTo(userId);
        resp.setStreamId(streamId);
        sendToSelf(resp);
    }

    // ==================== 辅助方法 ====================

    /**
     * 离开房间（断线或主动离开）
     */
    private void leaveRoom(String userId) {
        String targetRoomId = USER_SFU_ROOM_MAP.remove(userId);
        if (targetRoomId == null) return;

        SfuRoom room = SFU_ROOMS.get(targetRoomId);
        if (room == null) return;

        // 移除该用户发布的所有流
        SfuParticipant participant = room.participants.get(userId);
        if (participant != null) {
            for (String streamId : participant.publishingStreams) {
                STREAM_INFO_MAP.remove(streamId);
            }
        }

        room.removeParticipant(userId);

        // 为其他参与者取消订阅该用户的流
        for (SfuParticipant p : room.participants.values()) {
            p.subscribedStreams.removeIf(sid -> {
                StreamInfo si = STREAM_INFO_MAP.get(sid);
                return si != null && si.userId.equals(userId);
            });
        }

        // 通知房间内其他用户
        List<String> participantList = new ArrayList<>(room.participants.keySet());
        for (SfuParticipant p : room.participants.values()) {
            SfuMessage notify = new SfuMessage();
            notify.setType("SFU_PARTICIPANT_LEFT");
            notify.setFrom(userId);
            notify.setTo(p.userId);
            notify.setRoomId(targetRoomId);
            Map<String, Object> notifyData = new HashMap<>();
            notifyData.put("userId", userId);
            notifyData.put("participants", participantList);
            notify.setData(notifyData);
            sendToUser(p.userId, notify);
        }

        System.out.println("[SFU] 用户离开房间 roomId=" + targetRoomId + " userId=" + userId +
                " 剩余人数=" + room.getParticipantCount());

        // 如果房间为空，清理
        if (room.isEmpty()) {
            SFU_ROOMS.remove(targetRoomId);
            System.out.println("[SFU] 房间已清空，销毁 roomId=" + targetRoomId);
        }
    }

    /**
     * 向自己发送消息
     */
    private void sendToSelf(SfuMessage msg) {
        if (session == null || !session.isOpen()) return;
        try {
            synchronized (session) {
                session.getBasicRemote().sendText(JSON.toJSONString(msg));
            }
        } catch (IllegalStateException | IOException e) {
            System.out.println("[SFU] 发送失败 userId=" + userId + " error=" + e.getMessage());
        }
    }

    /**
     * 向指定用户发送消息
     */
    private void sendToUser(String targetUserId, SfuMessage msg) {
        // 查找该用户的SFU会话
        String targetRoomId = USER_SFU_ROOM_MAP.get(targetUserId);
        if (targetRoomId == null) return;

        SfuRoom room = SFU_ROOMS.get(targetRoomId);
        if (room == null) return;

        SfuParticipant participant = room.participants.get(targetUserId);
        if (participant == null || participant.session == null || !participant.session.isOpen()) {
            return;
        }

        try {
            synchronized (participant.session) {
                participant.session.getBasicRemote().sendText(JSON.toJSONString(msg));
            }
        } catch (IllegalStateException | IOException e) {
            System.out.println("[SFU] 发送失败 targetUserId=" + targetUserId + " error=" + e.getMessage());
        }
    }

    /**
     * 发送错误消息
     */
    private void sendError(String message) {
        SfuMessage error = new SfuMessage();
        error.setType("ERROR");
        error.setFrom("server");
        error.setTo(userId);
        error.setData(message);
        sendToSelf(error);
    }

    /**
     * 解析查询字符串
     */
    private Map<String, String> parseQueryString(String query) {
        Map<String, String> params = new HashMap<>();
        if (query == null) return params;

        String[] pairs = query.split("&");
        for (String pair : pairs) {
            String[] kv = pair.split("=", 2);
            if (kv.length == 2) {
                params.put(kv[0], kv[1]);
            } else if (kv.length == 1) {
                params.put(kv[0], "");
            }
        }
        return params;
    }

    @OnClose
    public void onClose() {
        if (userId != null) {
            leaveRoom(userId);
            System.out.println("[SFU连接下线] userId=" + userId);
        }
    }

    @OnError
    public void onError(Session session, Throwable throwable) {
        System.out.println("[SFU错误] userId=" + userId + " error=" + throwable.getMessage());
    }

    // ==================== 数据模型 ====================

    /**
     * SFU房间
     */
    public static class SfuRoom {
        private final String roomId;
        private final Map<String, SfuParticipant> participants = new ConcurrentHashMap<>();

        public SfuRoom(String roomId) {
            this.roomId = roomId;
        }

        public String getRoomId() { return roomId; }
        public Map<String, SfuParticipant> getParticipants() { return participants; }

        public void addParticipant(SfuParticipant p) {
            participants.put(p.userId, p);
        }

        public void removeParticipant(String userId) {
            participants.remove(userId);
        }

        public boolean isEmpty() {
            return participants.isEmpty();
        }

        public int getParticipantCount() {
            return participants.size();
        }
    }

    /**
     * SFU参与者
     */
    public static class SfuParticipant {
        private final String userId;
        private Session session;
        private final Set<String> publishingStreams = ConcurrentHashMap.newKeySet();
        private final Set<String> subscribedStreams = ConcurrentHashMap.newKeySet();
        private volatile boolean subscribeAll = false;

        public SfuParticipant(String userId, Session session) {
            this.userId = userId;
            this.session = session;
        }

        public String getUserId() { return userId; }
        public Session getSession() { return session; }
        public Set<String> getPublishingStreams() { return publishingStreams; }
        public Set<String> getSubscribedStreams() { return subscribedStreams; }
        public boolean isSubscribeAll() { return subscribeAll; }
    }

    /**
     * 流信息
     */
    public static class StreamInfo {
        private final String streamId;
        private final String userId;
        private final String kind; // "audio", "video", "screen"

        public StreamInfo(String streamId, String userId, String kind) {
            this.streamId = streamId;
            this.userId = userId;
            this.kind = kind;
        }

        public String getStreamId() { return streamId; }
        public String getUserId() { return userId; }
        public String getKind() { return kind; }
    }

    /**
     * SFU信令消息
     */
    public static class SfuMessage {
        private String type;
        private String from;
        private String to;
        private String roomId;
        private String streamId;
        private String kind;
        private Object data;

        public String getType() { return type; }
        public void setType(String type) { this.type = type; }
        public String getFrom() { return from; }
        public void setFrom(String from) { this.from = from; }
        public String getTo() { return to; }
        public void setTo(String to) { this.to = to; }
        public String getRoomId() { return roomId; }
        public void setRoomId(String roomId) { this.roomId = roomId; }
        public String getStreamId() { return streamId; }
        public void setStreamId(String streamId) { this.streamId = streamId; }
        public String getKind() { return kind; }
        public void setKind(String kind) { this.kind = kind; }
        public Object getData() { return data; }
        public void setData(Object data) { this.data = data; }
    }
}

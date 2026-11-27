/**
 * WebRTC 核心逻辑封装
 * 支持一对一通话和多人通话
 */

export class WebRTCManager {
  constructor(config = {}) {
    this.peerConnection = null;
    this.localStream = null;
    this.remoteStream = null;
    this.isCaller = false;
    this.audioContext = null;
    this.analyser = null;
    this.dataArray = null;

    this.iceServers = config.iceServers || [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' },
      { urls: 'stun:stun2.l.google.com:19302' }
    ];

    this.onLocalStream = config.onLocalStream || (() => { });
    this.onRemoteStream = config.onRemoteStream || (() => { });
    this.onIceCandidate = config.onIceCandidate || (() => { });
    this.onConnectionStateChange = config.onConnectionStateChange || (() => { });
    this.onAudioLevel = config.onAudioLevel || (() => { });
    this.onError = config.onError || (() => { });
  }

  async getLocalStream() {
    if (this.localStream) return this.localStream;

    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        },
        video: false
      });
      console.log('🎤 获取本地音频流成功');
      this.onLocalStream(this.localStream);
      return this.localStream;
    } catch (error) {
      console.error('❌ 获取麦克风失败:', error);
      let errorMsg = '无法访问麦克风';
      if (error.name === 'NotAllowedError') errorMsg = '用户拒绝了麦克风权限';
      else if (error.name === 'NotFoundError') errorMsg = '未找到麦克风设备';
      this.onError(errorMsg);
      throw error;
    }
  }

  async getLocalVideoStream() {
    if (this.localStream) {
      const videoTracks = this.localStream.getVideoTracks();
      if (videoTracks.length > 0) return this.localStream;
    }

    try {
      const videoStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        },
        audio: false
      });

      if (this.localStream) {
        this.localStream.addTrack(videoStream.getVideoTracks()[0]);
      } else {
        this.localStream = videoStream;
      }

      console.log('📹 获取本地视频流成功');
      this.onLocalStream(this.localStream);
      return this.localStream;
    } catch (error) {
      console.error('❌ 获取摄像头失败:', error);
      let errorMsg = '无法访问摄像头';
      if (error.name === 'NotAllowedError') errorMsg = '用户拒绝了摄像头权限';
      else if (error.name === 'NotFoundError') errorMsg = '未找到摄像头设备';
      this.onError(errorMsg);
      throw error;
    }
  }

  createPeerConnection(isCaller = false, options = {}) {
    this.isCaller = isCaller;
    const enableVideo = options.enableVideo || false;

    const config = {
      iceServers: this.iceServers,
      iceTransportPolicy: 'all',
      bundlePolicy: 'max-bundle',
      rtcpMuxPolicy: 'require'
    };

    this.peerConnection = new RTCPeerConnection(config);
    console.log('📞 PeerConnection 已创建');

    this.peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        this.onIceCandidate(event.candidate);
      }
    };

    this.peerConnection.oniceconnectionstatechange = () => {
      const state = this.peerConnection.iceConnectionState;
      console.log('🔗 ICE 连接状态:', state);
      this.onConnectionStateChange('ice', state);
    };

    this.peerConnection.onconnectionstatechange = () => {
      const state = this.peerConnection.connectionState;
      console.log('🔗 连接状态:', state);
      this.onConnectionStateChange('connection', state);
    };

    this.peerConnection.ontrack = (event) => {
      console.log('📡 收到远端 track:', event.track.kind, 'streams:', event.streams ? event.streams.length : 0);

      let stream;
      if (event.streams && event.streams.length > 0) {
        stream = event.streams[0];
      } else {
        stream = new MediaStream([event.track]);
      }

      if (!this.remoteStream) {
        // 首次收到远端流
        this.remoteStream = stream;
        // 监听轨道移除（对方关闭摄像头时触发）
        this._setupRemoteStreamListeners();
      } else if (event.track.kind === 'video' && !this.remoteStream.getVideoTracks().length) {
        // 远端新增视频轨道（如对方在通话中开启摄像头）
        // 创建新的 MediaStream 对象（包含已有音频 + 新视频），确保 UI 层能检测到引用变化
        const newStream = new MediaStream();
        this.remoteStream.getTracks().forEach(t => newStream.addTrack(t));
        stream.getTracks().forEach(t => {
          if (!newStream.getTracks().includes(t)) newStream.addTrack(t);
        });
        this.remoteStream = newStream;
        this._setupRemoteStreamListeners();
        console.log('📹 远端流升级为音视频流（新 MediaStream 对象）');
      } else if (stream !== this.remoteStream) {
        stream.getTracks().forEach(t => {
          if (!this.remoteStream.getTracks().includes(t)) {
            this.remoteStream.addTrack(t);
          }
        });
      }

      this.remoteStream.getAudioTracks().forEach(track => {
        track.enabled = true;
      });

      this.onRemoteStream(this.remoteStream);

      if (event.track.kind === 'audio') {
        this.startAudioAnalysis(this.remoteStream);
      }
    };

    this.enableVideo = enableVideo;
    return this.peerConnection;
  }

  // 监听远端 MediaStream 的轨道变化（对方开启/关闭摄像头时触发）
  _setupRemoteStreamListeners() {
    if (!this.remoteStream) return;
    // 移除旧的监听器（避免重复绑定）
    if (this._remoteStreamRemovetrackHandler) {
      this.remoteStream.removeEventListener('removetrack', this._remoteStreamRemovetrackHandler);
    }
    this._remoteStreamRemovetrackHandler = (event) => {
      console.log('📹 远端轨道移除:', event.track.kind);
      if (event.track.kind === 'video') {
        // 对方关闭摄像头，创建新的 MediaStream（只含音频），触发 Vue 响应式更新
        const newStream = new MediaStream();
        this.remoteStream.getTracks().forEach(t => newStream.addTrack(t));
        this.remoteStream = newStream;
        this._setupRemoteStreamListeners();
        this.onRemoteStream(this.remoteStream);
        console.log('📹 远端流降级为纯音频流（新 MediaStream 对象）');
      }
    };
    this.remoteStream.addEventListener('removetrack', this._remoteStreamRemovetrackHandler);
  }

  addLocalTracks(options = {}) {
    if (!this.peerConnection || !this.localStream) {
      console.warn('⚠️ PeerConnection 或本地流未初始化');
      return false;
    }

    const enableVideo = options.enableVideo !== undefined ? options.enableVideo : this.enableVideo;
    const existingSenders = this.peerConnection.getSenders();
    const existingTracks = new Set(existingSenders.map(s => s.track));

    this.localStream.getAudioTracks().forEach(track => {
      if (!existingTracks.has(track)) {
        this.peerConnection.addTrack(track, this.localStream);
      }
    });

    if (enableVideo) {
      const videoTracks = this.localStream.getVideoTracks();
      videoTracks.forEach(track => {
        if (!existingTracks.has(track)) {
          this.peerConnection.addTrack(track, this.localStream);
        }
      });
    }

    return true;
  }

  async createOffer() {
    if (!this.peerConnection) throw new Error('PeerConnection 未创建');
    const offer = await this.peerConnection.createOffer({
      offerToReceiveAudio: true,
      offerToReceiveVideo: this.enableVideo || false
    });
    await this.peerConnection.setLocalDescription(offer);
    return offer;
  }

  async createAnswer(offerSdp) {
    if (!this.peerConnection) throw new Error('PeerConnection 未创建');
    const offer = new RTCSessionDescription(offerSdp);
    await this.peerConnection.setRemoteDescription(offer);
    // 从 offer SDP 检测是否包含视频，确保 answer 正确响应
    const offerSdpStr = offer.sdp || '';
    const hasVideo = /m=video/.test(offerSdpStr);
    const answer = await this.peerConnection.createAnswer({
      offerToReceiveAudio: true,
      offerToReceiveVideo: hasVideo || this.enableVideo || false
    });
    await this.peerConnection.setLocalDescription(answer);
    return answer;
  }

  async handleAnswer(answerSdp) {
    if (!this.peerConnection) throw new Error('PeerConnection 未创建');
    const answer = new RTCSessionDescription(answerSdp);
    await this.peerConnection.setRemoteDescription(answer);
  }

  async addIceCandidate(candidateData) {
    if (!this.peerConnection) return;
    try {
      const candidate = new RTCIceCandidate(candidateData);
      await this.peerConnection.addIceCandidate(candidate);
    } catch (error) {
      console.error('❌ 添加 ICE 候选失败:', error);
    }
  }

  startAudioAnalysis(stream) {
    try {
      if (this.audioContext) {
        this.audioContext.close();
      }
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      const source = this.audioContext.createMediaStreamSource(stream);
      source.connect(this.analyser);
      this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      this.analyzeAudio();
    } catch (error) {
      console.warn('音频分析启动失败:', error);
    }
  }

  analyzeAudio() {
    if (!this.analyser) return;
    this.analyser.getByteFrequencyData(this.dataArray);
    let sum = 0;
    for (let i = 0; i < this.dataArray.length; i++) {
      sum += this.dataArray[i];
    }
    const avg = sum / this.dataArray.length;
    const level = Math.min(avg / 128, 1);
    this.onAudioLevel(level);
    requestAnimationFrame(() => this.analyzeAudio());
  }

  toggleMute() {
    if (!this.localStream) return false;
    const audioTrack = this.localStream.getAudioTracks()[0];
    if (audioTrack) {
      audioTrack.enabled = !audioTrack.enabled;
      return audioTrack.enabled;
    }
    return false;
  }

  isMuted() {
    if (!this.localStream) return false;
    const audioTrack = this.localStream.getAudioTracks()[0];
    return audioTrack ? !audioTrack.enabled : false;
  }

  toggleVideo() {
    if (!this.localStream) return false;
    const videoTracks = this.localStream.getVideoTracks();
    if (videoTracks.length > 0) {
      const track = videoTracks[0];
      track.enabled = !track.enabled;
      return track.enabled;
    }
    return false;
  }

  isVideoEnabled() {
    if (!this.localStream) return false;
    const videoTracks = this.localStream.getVideoTracks();
    return videoTracks.length > 0 && videoTracks[0].enabled;
  }

  addVideoTrackToPeerConnection() {
    if (!this.peerConnection || !this.localStream) return;
    const videoTracks = this.localStream.getVideoTracks();
    videoTracks.forEach(track => {
      const sender = this.peerConnection.getSenders().find(s => s.track === track);
      if (!sender) {
        this.peerConnection.addTrack(track, this.localStream);
      }
    });
  }

  removeVideoTrackFromPeerConnection() {
    if (!this.peerConnection) return;
    const senders = this.peerConnection.getSenders();
    senders.forEach(sender => {
      if (sender.track && sender.track.kind === 'video') {
        this.peerConnection.removeTrack(sender);
      }
    });
  }

  async updateLocalStream(enableVideo) {
    if (enableVideo) {
      if (!this.localStream) {
        await this.getLocalStream();
      }
      const videoTracks = this.localStream.getVideoTracks();
      if (videoTracks.length > 0) {
        videoTracks[0].enabled = true;
      } else {
        await this.getLocalVideoStream();
        this.addVideoTrackToPeerConnection();
      }
      this.enableVideo = true;
    } else {
      if (this.localStream) {
        const videoTracks = this.localStream.getVideoTracks();
        videoTracks.forEach(track => {
          track.stop();
          this.localStream.removeTrack(track);
        });
      }
      this.removeVideoTrackFromPeerConnection();
      this.enableVideo = false;
    }
  }

  // 翻转摄像头（前置 ↔ 后置）
  async flipCamera() {
    if (!this.localStream) return false;
    const videoTracks = this.localStream.getVideoTracks();
    if (videoTracks.length === 0) return false;

    const currentTrack = videoTracks[0];
    const settings = currentTrack.getSettings();
    const currentFacingMode = settings.facingMode || 'user';
    const newFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';

    try {
      // 停止当前视频轨道
      currentTrack.stop();
      this.localStream.removeTrack(currentTrack);

      // 获取新摄像头流
      const videoStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: newFacingMode
        },
        audio: false
      });

      const newTrack = videoStream.getVideoTracks()[0];
      this.localStream.addTrack(newTrack);

      // 替换 PeerConnection 中的视频轨道
      if (this.peerConnection) {
        const sender = this.peerConnection.getSenders().find(s => s.track && s.track.kind === 'video');
        if (sender) {
          await sender.replaceTrack(newTrack);
        } else {
          this.peerConnection.addTrack(newTrack, this.localStream);
        }
      }

      console.log('📹 摄像头已翻转:', newFacingMode);
      this.onLocalStream(this.localStream);
      return true;
    } catch (error) {
      console.error('❌ 翻转摄像头失败:', error);
      // 恢复原轨道（如果新轨道获取失败）
      this.localStream.addTrack(currentTrack);
      return false;
    }
  }

  hangUp() {
    if (this.peerConnection) {
      this.peerConnection.close();
      this.peerConnection = null;
    }
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }
    this.remoteStream = null;
    this.isCaller = false;
    this.enableVideo = false;
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    console.log('📴 通话已挂断');
  }

  static isSupported() {
    return !!(navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia &&
      window.RTCPeerConnection);
  }
}

/**
 * 多人通话房间管理器
 * 使用 Mesh 架构：每个参与者与所有其他参与者建立点对点连接
 */
export class RoomManager {
  constructor(config = {}) {
    this.roomId = null;
    this.myUserId = null;
    this.isHost = false;
    this.participants = new Map(); // userId -> { pc, stream, isVideoEnabled }

    this.localStream = null;
    this.isMuted = false;
    this.isVideoEnabled = false;
    this.isScreenSharing = false;

    this.iceServers = config.iceServers || [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' },
      { urls: 'stun:stun2.l.google.com:19302' }
    ];

    this.onParticipantJoined = config.onParticipantJoined || (() => { });
    this.onParticipantLeft = config.onParticipantLeft || (() => { });
    this.onRemoteStream = config.onRemoteStream || (() => { });
    this.onLocalStream = config.onLocalStream || (() => { });
    this.onConnectionStateChange = config.onConnectionStateChange || (() => { });
    this.onError = config.onError || (() => { });
    this.onParticipantsUpdate = config.onParticipantsUpdate || (() => { });
  }

  async initLocalStream(enableVideo = false) {
    try {
      const constraints = {
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        },
        video: enableVideo ? {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        } : false
      };

      this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
      this.isVideoEnabled = enableVideo;
      console.log(`🎤 本地流已获取，视频: ${enableVideo}`);
      this.onLocalStream(this.localStream);
      return this.localStream;
    } catch (error) {
      console.error('❌ 获取本地流失败:', error);
      this.onError('获取本地流失败: ' + error.message);
      throw error;
    }
  }

  async updateLocalStream(enableVideo) {
    if (!this.localStream) {
      return this.initLocalStream(enableVideo);
    }

    if (enableVideo && !this.isVideoEnabled) {
      try {
        const videoStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            facingMode: 'user'
          },
          audio: false
        });
        this.localStream.addTrack(videoStream.getVideoTracks()[0]);
        this.isVideoEnabled = true;

        // 更新所有远端 PeerConnection
        this.participants.forEach((participant, userId) => {
          const pc = participant.pc;
          const videoTrack = videoStream.getVideoTracks()[0];

          // 检查是否已有视频 transceiver
          const videoTransceiver = pc.getTransceivers().find(t => t.kind === 'video');
          if (videoTransceiver) {
            // 如果有 recvonly 视频 transceiver，改为 sendrecv 并添加 sender
            if (videoTransceiver.direction === 'recvonly' || videoTransceiver.direction === 'inactive') {
              // 移除旧的 transceiver（如果没有 sender）
              if (!videoTransceiver.sender) {
                // 创建新的 transceiver 替代
                const newSender = pc.addTrack(videoTrack, this.localStream);
              } else {
                // 已有 sender，直接替换 track
                videoTransceiver.sender.replaceTrack(videoTrack);
              }
            } else if (videoTransceiver.sender) {
              videoTransceiver.sender.replaceTrack(videoTrack);
            }
          } else {
            // 没有视频 transceiver，通过 addTrack 添加
            pc.addTrack(videoTrack, this.localStream);
          }
        });

        this.onLocalStream(this.localStream);
      } catch (error) {
        console.error('❌ 开启视频失败:', error);
        this.onError('开启视频失败: ' + error.message);
      }
    } else if (!enableVideo && this.isVideoEnabled) {
      const videoTracks = this.localStream.getVideoTracks();
      videoTracks.forEach(track => {
        this.participants.forEach((participant) => {
          const pc = participant.pc;
          const sender = pc.getSenders().find(s => s.track === track);
          if (sender) {
            pc.removeTrack(sender);
            // 确保视频 transceiver 存在且为 recvonly
            const videoTransceiver = pc.getTransceivers().find(t => t.kind === 'video');
            if (videoTransceiver) {
              videoTransceiver.direction = 'recvonly';
            } else {
              pc.addTransceiver('video', { direction: 'recvonly' });
            }
          }
        });
        track.stop();
        this.localStream.removeTrack(track);
      });
      this.isVideoEnabled = false;
      this.onLocalStream(this.localStream);
    }
  }

  createPeerConnectionForParticipant(participantId) {
    const pc = new RTCPeerConnection({
      iceServers: this.iceServers
    });

    const participant = {
      pc: pc,
      stream: null,
      userId: participantId,
      pendingIceCandidates: [],
      remoteDescriptionSet: false,
      localDescriptionSet: false
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        const candidateObj = {
          candidate: event.candidate.candidate,
          sdpMid: event.candidate.sdpMid,
          sdpMLineIndex: event.candidate.sdpMLineIndex,
          foundation: event.candidate.foundation,
          priority: event.candidate.priority,
          protocol: event.candidate.protocol,
          ip: event.candidate.ip,
          port: event.candidate.port,
          type: event.candidate.type
        };
        console.log(`📤 ICE candidate [${participantId}]: ${candidateObj.candidate.substring(0, 60)}...`);
        this.onIceCandidate(participantId, candidateObj);
      } else {
        console.log(`📤 ICE gathering complete [${participantId}]`);
      }
    };

    pc.oniceconnectionstatechange = () => {
      const state = pc.iceConnectionState;
      console.log(`🔗 ICE 状态 [${participantId}]:`, state);
      this.onConnectionStateChange(participantId, 'ice', state);
      if (state === 'failed' || state === 'disconnected' || state === 'closed') {
        this.handleParticipantDisconnected(participantId);
      }
      if (state === 'connected' || state === 'completed') {
        console.log(`✅ ICE 连接成功 [${participantId}]`);
      }
    };

    pc.onconnectionstatechange = () => {
      const state = pc.connectionState;
      console.log(`🔗 连接状态 [${participantId}]:`, state);
      this.onConnectionStateChange(participantId, 'connection', state);
    };

    pc.ontrack = (event) => {
      console.log(`📡 收到远端 track [${participantId}]:`, event.track.kind);

      // 直接使用 event.streams[0]（参考工作代码）
      if (event.streams && event.streams.length > 0) {
        participant.stream = event.streams[0];
      } else {
        // 如果没有关联流，手动创建（兜底）
        if (!participant.stream) {
          participant.stream = new MediaStream();
        }
        participant.stream.addTrack(event.track);
      }

      console.log(`📡 远端流 [${participantId}] 轨道数: ${participant.stream.getTracks().length} (音频: ${participant.stream.getAudioTracks().length}, 视频: ${participant.stream.getVideoTracks().length})`);
      this.onRemoteStream(participantId, participant.stream);
    };

    // 添加本地流轨道（addTrack 会自动创建 transceiver）
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach(track => {
        pc.addTrack(track, this.localStream);
      });
      if (this.isVideoEnabled) {
        this.localStream.getVideoTracks().forEach(track => {
          pc.addTrack(track, this.localStream);
        });
      }
    }

    // 仅当本地视频未启用时，添加 recvonly 视频 transceiver 以接收远端视频
    // 当本地视频已启用时，addTrack 已创建了 sendrecv 视频 transceiver
    if (!this.isVideoEnabled) {
      const hasVideoTransceiver = pc.getTransceivers().some(t => t.kind === 'video');
      if (!hasVideoTransceiver) {
        pc.addTransceiver('video', { direction: 'recvonly' });
        console.log(`📹 添加 recvonly 视频 transceiver [${participantId}]`);
      }
    }

    this.participants.set(participantId, participant);
    this.onParticipantsUpdate(this.getParticipantList());
    return pc;
  }

  async createOfferForParticipant(participantId) {
    const participant = this.participants.get(participantId);
    if (!participant || !participant.pc) return;

    try {
      // 参考工作代码：使用 offerToReceiveAudio/Video 确保接收远端音视频
      const offer = await participant.pc.createOffer({
        offerToReceiveAudio: true,
        offerToReceiveVideo: true
      });
      await participant.pc.setLocalDescription(offer);
      return offer;
    } catch (error) {
      console.error(`❌ 创建 Offer 失败 [${participantId}]:`, error);
      throw error;
    }
  }

  async handleOffer(participantId, offerDesc) {
    let participant = this.participants.get(participantId);

    if (!participant) {
      this.createPeerConnectionForParticipant(participantId);
      participant = this.participants.get(participantId);
    }

    try {
      // 参考工作代码：setRemoteDescription 接受完整 {type, sdp} 对象
      await participant.pc.setRemoteDescription(offerDesc);
      participant.remoteDescriptionSet = true;
      await this.flushPendingIceCandidates(participantId);

      const answer = await participant.pc.createAnswer();
      await participant.pc.setLocalDescription(answer);
      return answer;
    } catch (error) {
      console.error(`❌ 处理 Offer 失败 [${participantId}]:`, error);
      throw error;
    }
  }

  async handleAnswer(participantId, answerDesc) {
    const participant = this.participants.get(participantId);
    if (!participant || !participant.pc) return;

    try {
      // 参考工作代码：setRemoteDescription 接受完整 {type, sdp} 对象
      await participant.pc.setRemoteDescription(answerDesc);
      participant.remoteDescriptionSet = true;
      await this.flushPendingIceCandidates(participantId);
      console.log(`✅ Answer 处理完成 [${participantId}]`);
    } catch (error) {
      console.error(`❌ 处理 Answer 失败 [${participantId}]:`, error);
    }
  }

  async handleIceCandidate(participantId, candidateData) {
    const participant = this.participants.get(participantId);
    if (!participant || !participant.pc) {
      console.warn(`⚠️ 添加 ICE 候选失败: 参与者不存在 [${participantId}]`);
      return;
    }

    if (!participant.remoteDescriptionSet) {
      console.log(`⏳ 远端描述未设置，缓存 ICE 候选 [${participantId}]`);
      participant.pendingIceCandidates.push(candidateData);
      return;
    }

    try {
      const candidate = new RTCIceCandidate(candidateData);
      await participant.pc.addIceCandidate(candidate);
      console.log(`✅ ICE candidate 已添加 [${participantId}]: ${candidate.candidate.substring(0, 50)}...`);
    } catch (error) {
      console.error(`❌ 添加 ICE 候选失败 [${participantId}]:`, error);
      console.error('  candidateData:', JSON.stringify(candidateData));
    }
  }

  async flushPendingIceCandidates(participantId) {
    const participant = this.participants.get(participantId);
    if (!participant || !participant.pendingIceCandidates || participant.pendingIceCandidates.length === 0) {
      return;
    }
    console.log(`🔄 刷新缓冲的 ICE 候选 [${participantId}]: ${participant.pendingIceCandidates.length} 个`);
    while (participant.pendingIceCandidates.length > 0) {
      const candidateData = participant.pendingIceCandidates.shift();
      await this.handleIceCandidate(participantId, candidateData);
    }
  }

  onIceCandidate(participantId, candidate) {
    // 由外部通过回调处理
  }

  handleParticipantDisconnected(participantId) {
    const participant = this.participants.get(participantId);
    if (participant) {
      console.log(`🔌 参与者断开连接: ${participantId}`);
      this.removeParticipant(participantId);
      this.onParticipantLeft(participantId);
    }
  }

  removeParticipant(participantId) {
    const participant = this.participants.get(participantId);
    if (participant) {
      if (participant.pc) {
        participant.pc.close();
      }
      this.participants.delete(participantId);
      this.onParticipantsUpdate(this.getParticipantList());
    }
  }

  addTrackToPeerConnection(pc, track) {
    if (!pc || !track) return;
    const existingSender = pc.getSenders().find(s => s.track === track);
    if (!existingSender) {
      pc.addTrack(track, this.localStream);
    }
    // 确保视频 transceiver 存在
    const hasVideo = pc.getTransceivers().some(t => t.kind === 'video');
    if (!hasVideo) {
      pc.addTransceiver('video', { direction: 'recvonly' });
    }
  }

  toggleMute() {
    if (!this.localStream) return false;
    const audioTrack = this.localStream.getAudioTracks()[0];
    if (audioTrack) {
      audioTrack.enabled = !audioTrack.enabled;
      this.isMuted = !audioTrack.enabled;
      return audioTrack.enabled;
    }
    return false;
  }

  toggleVideo() {
    if (this.isVideoEnabled) {
      this.updateLocalStream(false);
      return false;
    } else {
      this.updateLocalStream(true);
      return true;
    }
  }

  async toggleScreenShare() {
    if (this.isScreenSharing) {
      this.stopScreenShare();
      return false;
    }

    try {
      const screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false
      });

      const screenTrack = screenStream.getVideoTracks()[0];
      screenTrack.onended = () => {
        this.stopScreenShare();
      };

      // 用屏幕共享轨道替换摄像头轨道
      this.participants.forEach((participant) => {
        const sender = participant.pc.getSenders().find(s => s.track && s.track.kind === 'video');
        if (sender) {
          sender.replaceTrack(screenTrack);
        } else {
          participant.pc.addTrack(screenTrack, this.localStream);
        }
      });

      // 将屏幕轨道添加到本地流
      this.localStream.addTrack(screenTrack);
      this.screenTrack = screenTrack;
      this.isScreenSharing = true;
      this.onLocalStream(this.localStream);
      return true;
    } catch (error) {
      console.error('❌ 屏幕共享失败:', error);
      this.onError('屏幕共享失败: ' + error.message);
      return false;
    }
  }

  stopScreenShare() {
    if (this.screenTrack) {
      this.screenTrack.stop();
      this.localStream.removeTrack(this.screenTrack);
      this.screenTrack = null;

      // 恢复摄像头轨道
      if (this.isVideoEnabled) {
        const videoTrack = this.localStream.getVideoTracks()[0];
        this.participants.forEach((participant) => {
          const sender = participant.pc.getSenders().find(s => s.track && s.track.kind === 'video');
          if (sender) {
            sender.replaceTrack(videoTrack);
          }
        });
      }

      this.isScreenSharing = false;
      this.onLocalStream(this.localStream);
    }
  }

  getRemoteStream(participantId) {
    const participant = this.participants.get(participantId);
    return participant ? participant.stream : null;
  }

  getParticipantList() {
    return Array.from(this.participants.keys());
  }

  getParticipantCount() {
    return this.participants.size;
  }

  isParticipantConnected(participantId) {
    const participant = this.participants.get(participantId);
    return participant && participant.pc &&
      (participant.pc.iceConnectionState === 'connected' ||
        participant.pc.iceConnectionState === 'completed');
  }

  leaveRoom() {
    // 关闭所有远端连接
    this.participants.forEach((participant, userId) => {
      if (participant.pc) {
        participant.pc.close();
      }
    });
    this.participants.clear();
    this.onParticipantsUpdate([]);

    // 停止本地流
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }
    this.isVideoEnabled = false;
    this.isMuted = false;
    this.isScreenSharing = false;
    this.screenTrack = null;

    console.log('📴 已离开房间');
  }

  static isSupported() {
    return !!(navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia &&
      window.RTCPeerConnection);
  }
}

/**
 * H5P Seek Blocker & Telemetry - Advanced Version
 */

(function () {
  var state = {
    totalQuestions: 0,
    answeredIds: new Set(),
    contentType: 'unknown'
  };

  function waitForH5P() {
    if (typeof H5P === 'undefined' || (typeof H5P.InteractiveVideo === 'undefined' && typeof H5P.instances === 'undefined')) {
      setTimeout(waitForH5P, 100);
      return;
    }

    // Khởi tạo thông tin content
    initializeContentInfo();

    var IV = H5P.InteractiveVideo;
    if (IV) {
      var lastSeekData = null;
      var isMousedown = false;
      var seekNotifyTimer = null;

      // Theo dõi trạng thái chuột
      document.addEventListener('mousedown', function() { isMousedown = true; });
      document.addEventListener('mouseup', function() { 
        isMousedown = false; 
        if (lastSeekData) {
          // Thả chuột phát là chốt log ngay
          sendSeekLog(lastSeekData);
          lastSeekData = null;
        }
      });

      function sendSeekLog(data) {
        if (seekNotifyTimer) clearTimeout(seekNotifyTimer);
        window.parent.postMessage({ type: 'SEEK_DEBUG', data: data }, '*');
      }

      IV.prototype.isSkippingProhibited = function (targetTime) {
        var mode = this.preventSkippingMode || 'none';
        var currentTime = this.video.getCurrentTime();
        var maxWatched = this.maxTimeReached || 0;

        var currentData = {
          mode: mode,
          from: currentTime.toFixed(2),
          to: targetTime.toFixed(2),
          maxReached: maxWatched.toFixed(2),
          isForward: targetTime > currentTime
        };

        // Nếu đang đè chuột (drag), chỉ lưu lại chứ chưa gửi
        if (isMousedown) {
          lastSeekData = currentData;
        } else {
          // Nếu click thẳng hoặc dùng phím, dùng debounce ngắn để chốt
          if (seekNotifyTimer) clearTimeout(seekNotifyTimer);
          seekNotifyTimer = setTimeout(function() {
            sendSeekLog(currentData);
          }, 200);
        }

        if (mode === 'none') return false;
        if (mode === 'both') return true;
        if (mode === 'full') {
          if (targetTime <= maxWatched + 0.2) return false; 
          return true;
        }
        return false;
      };
    }

    console.log('[SeekBlocker] Advanced Telemetry activated');
    window.parent.postMessage({ type: 'SEEK_BLOCKER_READY' }, '*');

    // ── BẮT TƯƠNG TÁC CHI TIẾT (xAPI) ──
    if (H5P.externalDispatcher) {
      H5P.externalDispatcher.on('xAPI', function (event) {
        var statement = event.data.statement;
        var verb = statement.verb.display['en-US'];
        var subContentId = statement.object.id.split('subContentId=')[1];

        // Nếu là sự kiện trả lời, ghi lại ID câu hỏi
        if (verb === 'answered' || verb === 'completed') {
          if (subContentId) state.answeredIds.add(subContentId);
        }

        // Trích xuất dữ liệu "sạch" để làm báo cáo Excel/JSON dễ đọc
        var cleanedData = {
          time: getCurrentTime(),
          action: verb,
          question: extractQuestionText(statement),
          answer: extractAnswerText(statement),
          correct: statement.result ? statement.result.success : null,
          score: statement.result && statement.result.score ? statement.result.score.raw : null,
          maxScore: statement.result && statement.result.score ? statement.result.score.max : null,
          subContentId: subContentId
        };

        window.parent.postMessage({
          type: 'H5P_STASH_EVENT',
          data: cleanedData,
          raw: statement
        }, '*');
      });
    }

    // ── ĐỒNG BỘ TRẠNG THÁI MỖI GIÂY ──
    setInterval(function() {
      if (H5P.instances && H5P.instances.length > 0) {
        var inst = H5P.instances[0];
        
        // Gắn listener cho Video nếu chưa gắn (để bắt Play/Pause/Error)
        if (inst.video && !inst.video.hasTrackingAdded) {
          inst.video.on('stateChange', function (event) {
            var stateCode = event.data;
            var action = 'unknown';
            if (stateCode === H5P.Video.PLAYING) action = 'played';
            if (stateCode === H5P.Video.PAUSED) action = 'paused';
            if (stateCode === H5P.Video.ENDED) action = 'finished';
            if (stateCode === H5P.Video.BUFFERING) action = 'buffering';
            
            if (action !== 'unknown') {
              sendStashEvent(action, { time: getCurrentTime() });
            }
          });
          
          inst.video.on('error', function (event) {
            sendStashEvent('error', { time: getCurrentTime(), error: event.data });
          });
          
          inst.video.hasTrackingAdded = true;
          console.log('[SeekBlocker] Video status tracking attached');
        }

        var currentTime = getCurrentTime();
        var duration = getDuration();
        
        // Tính toán trạng thái hoàn thành
        var isVideoFinished = duration > 0 ? (currentTime >= duration - 1) : true;
        var areQuestionsFinished = state.totalQuestions > 0 ? (state.answeredIds.size >= state.totalQuestions) : true;
        
        var isCompleted = false;
        if (state.contentType === 'InteractiveVideo') {
          isCompleted = isVideoFinished && areQuestionsFinished;
        } else {
          isCompleted = areQuestionsFinished;
        }

        window.parent.postMessage({
          type: 'H5P_SYNC_STATE',
          data: {
            currentTime: currentTime,
            maxTimeReached: inst.maxTimeReached || 0,
            duration: duration,
            mode: inst.preventSkippingMode || 'none',
            totalQuestions: state.totalQuestions,
            answeredCount: state.answeredIds.size,
            isCompleted: isCompleted,
            contentType: state.contentType
          }
        }, '*');
      }
    }, 1000);
  }

  function sendStashEvent(action, extraData) {
    var data = {
      time: getCurrentTime(),
      action: action,
      question: '',
      answer: '',
      correct: null,
      score: null,
      maxScore: null
    };
    // Gộp thêm dữ liệu extra nếu có
    Object.assign(data, extraData);

    window.parent.postMessage({
      type: 'H5P_STASH_EVENT',
      data: data
    }, '*');
  }

  function initializeContentInfo() {
    if (!H5P.instances || H5P.instances.length === 0) return;
    var inst = H5P.instances[0];

    // Xác định loại content
    if (inst instanceof H5P.InteractiveVideo) {
      state.contentType = 'InteractiveVideo';
      state.totalQuestions = (inst.interactions || []).filter(function(i) {
        // Chỉ đếm các tương tác là tác vụ (có thư mục con và không phải label đơn thuần)
        return i.action && i.action.library && !i.action.library.includes('H5P.Label');
      }).length;
    } else {
      state.contentType = 'Other';
      // Thử đếm số câu hỏi cho các dạng khác (ví dụ QuestionSet)
      state.totalQuestions = inst.questions ? inst.questions.length : 0;
    }
    console.log('[SeekBlocker] Content Type:', state.contentType, '| Total Questions:', state.totalQuestions);
  }

  function getCurrentTime() {
    if (!H5P.instances || H5P.instances.length === 0) return 0;
    var inst = H5P.instances[0];
    if (inst.video && inst.video.getCurrentTime) return inst.video.getCurrentTime();
    if (inst.getCurrentTime) return inst.getCurrentTime();
    return 0;
  }

  function getDuration() {
    if (!H5P.instances || H5P.instances.length === 0) return 0;
    var inst = H5P.instances[0];
    if (inst.video && inst.video.getDuration) return inst.video.getDuration();
    if (inst.getDuration) return inst.getDuration();
    return 0;
  }

  function extractQuestionText(statement) {
    if (statement.object && statement.object.definition) {
      var def = statement.object.definition;
      // Thử lấy name trước, không có thì lấy description
      var name = def.name ? (def.name['en-US'] || def.name['vi-VN'] || '') : '';
      var desc = def.description ? (def.description['en-US'] || def.description['vi-VN'] || '') : '';
      var text = name || desc;
      return text.replace(/<[^>]*>/g, '').trim();
    }
    return '';
  }

  function extractAnswerText(statement) {
    if (!statement.result || statement.result.response === undefined) return '';
    
    var response = String(statement.result.response);
    var def = statement.object.definition;

    // Trường hợp 1: Có danh sách lựa chọn (Multiple Choice, v.v.)
    if (def && def.choices) {
      // response có thể là "0" hoặc "0[,]1" cho nhiều lựa chọn
      var ids = response.split('[,]');
      var labels = ids.map(function(id) {
        var choice = def.choices.find(function(c) { return c.id === id; });
        return choice && choice.description ? (choice.description['en-US'] || choice.description['vi-VN'] || id) : id;
      });
      return labels.join(', ').replace(/<[^>]*>/g, '').trim();
    }

    // Trường hợp 2: Đúng/Sai (True/False)
    if (response === 'true') return 'Đúng';
    if (response === 'false') return 'Sai';

    // Trường hợp 3: Khác (điền vào chỗ trống, v.v.)
    return response.replace(/<[^>]*>/g, '').trim();
  }

  // Lắng nghe lệnh điều khiển
  window.addEventListener('message', function (event) {
    if (!event.data || !event.data.type) return;
    if (event.data.type === 'SET_SEEK_MODE') {
      if (window.H5P && H5P.instances) {
        H5P.instances.forEach(function (inst) { inst.preventSkippingMode = event.data.mode; });
      }
    }
    if (event.data.type === 'RESET_PROGRESS') {
      if (window.H5P && H5P.instances) {
        H5P.instances.forEach(function (inst) {
          inst.maxTimeReached = 0;
          state.answeredIds.clear();
          if (inst.video && inst.video.seek) inst.video.seek(0);
        });
      }
    }
  });

  waitForH5P();
})();

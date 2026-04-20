/**
 * H5P Seek Blocker - Debug Version
 */

(function () {
  function waitForH5P() {
    if (typeof H5P === 'undefined' || typeof H5P.InteractiveVideo === 'undefined') {
      setTimeout(waitForH5P, 100);
      return;
    }

    var IV = H5P.InteractiveVideo;

    IV.prototype.isSkippingProhibited = function (targetTime) {
      // 1. Lấy thông số
      var mode = this.preventSkippingMode || 'none';
      var currentTime = this.video.getCurrentTime();
      var maxWatched = this.maxTimeReached || 0;

      // 2. Gửi log ra trang cha để mình nhìn thấy
      window.parent.postMessage({
        type: 'SEEK_DEBUG',
        data: {
          mode: mode,
          from: currentTime.toFixed(2),
          to: targetTime.toFixed(2),
          maxReached: maxWatched.toFixed(2),
          isForward: targetTime > currentTime
        }
      }, '*');

      // 3. Logic chặn
      if (mode === 'none') return false;
      
      if (mode === 'both') return true;

      if (mode === 'full') {
        // CHỈ cho phép nếu targetTime nhỏ hơn hoặc bằng mốc đã từng xem
        // Bỏ +1 giây để kiểm tra chính xác tuyệt đối
        if (targetTime <= maxWatched + 0.2) { 
          return false; 
        }
        return true; // Chặn nếu vượt mốc maxReached
      }

      return false;
    };

    console.log('[SeekBlocker] Debug mode activated');
    window.parent.postMessage({ type: 'SEEK_BLOCKER_READY' }, '*');

    // ── MỚI: BẮT TOÀN BỘ SỰ KIỆN TƯƠNG TÁC (xAPI) ──
    if (H5P.externalDispatcher) {
      H5P.externalDispatcher.on('xAPI', function (event) {
        // Gửi toàn bộ dữ liệu chuẩn xAPI (chứa điểm, câu trả lời, tiến độ) ra index.html
        window.parent.postMessage({
          type: 'H5P_XAPI_EVENT',
          data: event.data.statement
        }, '*');
      });
    } else {
      console.warn('[SeekBlocker] Không tìm thấy H5P.externalDispatcher để bắt xAPI');
    }

    // ── MỚI: ĐỒNG BỘ TRẠNG THÁI VIDEO MỖI GIÂY ──
    setInterval(function() {
      if (H5P.instances && H5P.instances.length > 0) {
        var inst = H5P.instances[0];
        if (inst.video && typeof inst.video.getCurrentTime === 'function') {
          window.parent.postMessage({
            type: 'H5P_SYNC_STATE',
            data: {
              currentTime: inst.video.getCurrentTime(),
              maxTimeReached: inst.maxTimeReached || 0,
              duration: inst.video.getDuration ? inst.video.getDuration() : 0,
              mode: inst.preventSkippingMode || 'none'
            }
          }, '*');
        }
      }
    }, 1000);
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
          if (inst.video && inst.video.seek) inst.video.seek(0);
        });
      }
    }
  });

  waitForH5P();
})();

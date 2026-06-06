(function () {
    function ensureToastContainer() {
        return document.getElementById('monitorToastContainer');
    }

    function getToastThemeClass(level) {
        if (level === 'success') {
            return 'monitor-toast-success';
        }
        if (level === 'error' || level === 'danger') {
            return 'monitor-toast-danger';
        }
        if (level === 'warning') {
            return 'monitor-toast-warning';
        }
        return 'monitor-toast-info';
    }

    function showToast(options) {
        const container = ensureToastContainer();
        if (!container || !window.bootstrap) {
            return;
        }

        const level = options.level || 'info';
        const toast = document.createElement('div');
        toast.className = `toast border-0 shadow-lg ${getToastThemeClass(level)}`;
        toast.role = 'alert';
        toast.ariaLive = 'assertive';
        toast.ariaAtomic = 'true';
        toast.innerHTML = `
            <div class="toast-header bg-transparent border-0">
                <i class="bi ${options.icon || 'bi-bell-fill'} me-2"></i>
                <strong class="me-auto">${options.title || 'Monitoring update'}</strong>
                <small>${options.smallText || 'now'}</small>
                <button type="button" class="btn-close ms-2" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body pt-0">${options.message || ''}</div>
        `;
        container.appendChild(toast);
        const instance = new window.bootstrap.Toast(toast, {
            delay: options.delay || 3000,
            autohide: options.autohide !== false,
        });
        toast.addEventListener('hidden.bs.toast', function () {
            toast.remove();
        });
        instance.show();
    }

    function playTone(options) {
        const contextClass = window.AudioContext || window.webkitAudioContext;
        if (!contextClass) {
            return;
        }
        const context = new contextClass();
        const oscillator = context.createOscillator();
        const gainNode = context.createGain();

        oscillator.type = options.type || 'sine';
        oscillator.frequency.value = options.frequency || 660;
        gainNode.gain.value = options.volume || 0.03;

        oscillator.connect(gainNode);
        gainNode.connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + (options.duration || 0.18));
        oscillator.onended = function () {
            context.close();
        };
    }

    function playSuccessTone() {
        playTone({ frequency: 880, duration: 0.12, type: 'triangle', volume: 0.025 });
        setTimeout(function () {
            playTone({ frequency: 1175, duration: 0.15, type: 'triangle', volume: 0.02 });
        }, 140);
    }

    function playErrorTone() {
        playTone({ frequency: 240, duration: 0.18, type: 'sawtooth', volume: 0.03 });
        setTimeout(function () {
            playTone({ frequency: 180, duration: 0.2, type: 'sawtooth', volume: 0.025 });
        }, 170);
    }

    window.monitorFeedback = {
        showToast: showToast,
        playTone: playTone,
        playSuccessTone: playSuccessTone,
        playErrorTone: playErrorTone,
    };
})();

(function () {
    const root = document.getElementById('telegram-test-live-root');
    if (!root) {
        return;
    }

    const liveUrl = root.dataset.liveUrl;
    const autoKey = 'telegram-test-auto-refresh';
    const feedback = window.monitorFeedback;
    const refreshIntervalMs = (parseInt(root.dataset.autoSeconds || '30', 10) || 30) * 1000;
    let timerId = null;
    let refreshInFlight = false;

    function notify(options) {
        if (feedback && typeof feedback.showToast === 'function') {
            feedback.showToast(options);
        }
    }

    function playSuccess() {
        if (feedback && typeof feedback.playSuccessTone === 'function') {
            feedback.playSuccessTone();
        }
    }

    function playError() {
        if (feedback && typeof feedback.playErrorTone === 'function') {
            feedback.playErrorTone();
        }
    }

    function getAutoEnabled() {
        return localStorage.getItem(autoKey) === 'true';
    }

    function syncToggle() {
        const toggle = root.querySelector('.js-telegram-auto-toggle');
        if (toggle) {
            toggle.checked = getAutoEnabled();
        }
    }

    function setUpdatingState(isUpdating) {
        refreshInFlight = isUpdating;
        root.classList.toggle('is-refreshing', isUpdating);
        root.querySelectorAll('.js-telegram-refresh-btn').forEach(function (button) {
            button.disabled = isUpdating;
            if (isUpdating) {
                button.dataset.originalHtml = button.dataset.originalHtml || button.innerHTML;
                button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Testing';
            } else if (button.dataset.originalHtml) {
                button.innerHTML = button.dataset.originalHtml;
            }
        });
        const label = root.querySelector('.js-telegram-update-label');
        if (label) {
            label.textContent = isUpdating ? 'Telegram test is running...' : 'Live Telegram diagnostics ready';
        }
    }

    function applyAutoState(enabled) {
        if (timerId) {
            window.clearInterval(timerId);
            timerId = null;
        }
        if (enabled) {
            timerId = window.setInterval(function () {
                refreshTelegramData(true);
            }, refreshIntervalMs);
        }
    }

    async function refreshTelegramData(runTest) {
        if (refreshInFlight) {
            return;
        }
        setUpdatingState(true);
        try {
            const response = await fetch(`${liveUrl}?run_test=${runTest ? 1 : 0}`, {
                method: 'GET',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const payload = await response.json();
            root.innerHTML = payload.html;
            syncToggle();
            applyAutoState(getAutoEnabled());
            notify({
                title: payload.success ? 'Telegram sent' : 'Telegram error',
                message: payload.message,
                level: payload.success ? 'success' : 'danger',
                icon: payload.success ? 'bi-send-check-fill' : 'bi-exclamation-octagon-fill',
                delay: 2600,
            });

            if (payload.success) {
                playSuccess();
            } else {
                playError();
            }
        } catch (error) {
            console.error('Telegram live update error:', error);
            const label = root.querySelector('.js-telegram-update-label');
            if (label) {
                label.textContent = 'Telegram live update failed';
            }
            notify({
                title: 'Telegram update failed',
                message: 'Telegram diagnostika sahifasini yangilab bo‘lmadi.',
                level: 'danger',
                icon: 'bi-bug-fill',
                delay: 3200,
            });
            playError();
        } finally {
            setUpdatingState(false);
        }
    }

    document.addEventListener('click', function (event) {
        const button = event.target.closest('.js-telegram-refresh-btn');
        if (!button || !root.contains(button)) {
            return;
        }
        event.preventDefault();
        refreshTelegramData(true);
    });

    document.addEventListener('change', function (event) {
        if (!event.target.classList.contains('js-telegram-auto-toggle') || !root.contains(event.target)) {
            return;
        }
        localStorage.setItem(autoKey, String(event.target.checked));
        applyAutoState(event.target.checked);
        notify({
            title: event.target.checked ? 'Telegram auto refresh enabled' : 'Telegram auto refresh paused',
            message: event.target.checked ? 'Bot diagnostikasi avtomatik tekshiriladi.' : 'Avtomatik Telegram testi to‘xtatildi.',
            level: event.target.checked ? 'info' : 'warning',
            icon: event.target.checked ? 'bi-bell-fill' : 'bi-bell-slash-fill',
            delay: 1800,
        });
    });

    syncToggle();
    applyAutoState(getAutoEnabled());
})();

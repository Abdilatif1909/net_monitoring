(function () {
    const liveRoot = document.getElementById('target-check-live-root');
    if (!liveRoot) {
        return;
    }

    const liveUrl = liveRoot.dataset.liveUrl;
    const liveMode = liveRoot.dataset.liveMode === '1';
    const autoRefreshKey = 'target-check-auto-refresh';
    const feedback = window.monitorFeedback;
    let refreshIntervalMs = (parseInt(liveRoot.dataset.autoSeconds || '30', 10) || 30) * 1000;
    let pingChart = null;
    let responseChart = null;
    let timerId = null;
    let refreshInFlight = false;
    let previousStatus = liveRoot.querySelector('.status-pulse')?.classList.contains('is-online') ? 'online' : 'offline';
    let chartPayload = window.monitorTargetInitialCharts || { labels: [], ping_values: [], response_values: [] };

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

    function buildCharts() {
        const pingCtx = document.getElementById('pingTrendChart');
        if (pingCtx && window.Chart) {
            if (pingChart) {
                pingChart.destroy();
            }
            pingChart = new window.Chart(pingCtx, {
                type: 'line',
                data: {
                    labels: chartPayload.labels,
                    datasets: [{
                        label: 'Ping (ms)',
                        data: chartPayload.ping_values,
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.15)',
                        tension: 0.35,
                        fill: true,
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        const responseCtx = document.getElementById('responseTrendChart');
        if (responseCtx && window.Chart) {
            if (responseChart) {
                responseChart.destroy();
            }
            responseChart = new window.Chart(responseCtx, {
                type: 'bar',
                data: {
                    labels: chartPayload.labels,
                    datasets: [{
                        label: 'Response time (ms)',
                        data: chartPayload.response_values,
                        backgroundColor: 'rgba(25, 135, 84, 0.8)',
                        borderRadius: 10,
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }

    function getAutoRefreshEnabled() {
        const saved = localStorage.getItem(autoRefreshKey);
        return saved === null ? liveMode : saved === 'true';
    }

    function syncAutoRefreshToggle() {
        const toggle = liveRoot.querySelector('.js-auto-refresh-toggle');
        if (toggle) {
            toggle.checked = getAutoRefreshEnabled();
        }
    }

    function setUpdatingState(isUpdating) {
        refreshInFlight = isUpdating;
        liveRoot.classList.toggle('is-refreshing', isUpdating);
        liveRoot.querySelectorAll('.js-live-refresh-btn').forEach(function (button) {
            button.disabled = isUpdating;
            if (isUpdating) {
                button.dataset.originalHtml = button.dataset.originalHtml || button.innerHTML;
                button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Refreshing';
            } else if (button.dataset.originalHtml) {
                button.innerHTML = button.dataset.originalHtml;
            }
        });
        const label = liveRoot.querySelector('.js-live-update-label');
        if (label) {
            label.textContent = isUpdating ? 'AJAX update in progress...' : 'Live AJAX update ready';
        }
    }

    function applyAutoRefreshState(enabled) {
        if (timerId) {
            window.clearInterval(timerId);
            timerId = null;
        }
        if (enabled) {
            timerId = window.setInterval(function () {
                refreshLiveData({ runCheck: 1, updateUrl: false });
            }, refreshIntervalMs);
        }
    }

    function handleStatusFeedback(nextStatus, options) {
        if (!nextStatus) {
            return;
        }
        const statusChanged = previousStatus && previousStatus !== nextStatus;
        previousStatus = nextStatus;

        if (statusChanged) {
            const isOnline = nextStatus === 'online';
            notify({
                title: isOnline ? 'Target restored' : 'Target offline',
                message: isOnline ? 'Website yana online holatga qaytdi.' : 'Website offline holatga tushdi.',
                level: isOnline ? 'success' : 'danger',
                icon: isOnline ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill',
            });
            if (isOnline) {
                playSuccess();
            } else {
                playError();
            }
            return;
        }

        if (options.runCheck === 1) {
            notify({
                title: 'Monitoring refreshed',
                message: nextStatus === 'online' ? 'Target muvaffaqiyatli tekshirildi.' : 'Target tekshirildi, ammo offline holatda.',
                level: nextStatus === 'online' ? 'info' : 'warning',
                icon: nextStatus === 'online' ? 'bi-arrow-repeat' : 'bi-exclamation-circle',
                delay: 2200,
            });
        }
    }

    async function refreshLiveData(options = {}) {
        if (refreshInFlight) {
            return;
        }
        const params = new URLSearchParams(options.search || window.location.search);
        params.set('run_check', String(options.runCheck ?? 1));
        setUpdatingState(true);
        try {
            const response = await fetch(`${liveUrl}?${params.toString()}`, {
                method: 'GET',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const payload = await response.json();
            liveRoot.innerHTML = payload.html;
            chartPayload = payload.charts;
            refreshIntervalMs = (parseInt(liveRoot.dataset.autoSeconds || '30', 10) || 30) * 1000;
            if (options.updateUrl !== false) {
                const url = new URL(window.location.href);
                params.delete('run_check');
                url.search = params.toString();
                window.history.replaceState({}, '', url.toString());
            }
            syncAutoRefreshToggle();
            applyAutoRefreshState(getAutoRefreshEnabled());
            buildCharts();
            handleStatusFeedback(payload.status, options);
        } catch (error) {
            console.error('Target live update error:', error);
            const label = liveRoot.querySelector('.js-live-update-label');
            if (label) {
                label.textContent = 'Live update failed';
            }
            notify({
                title: 'Live update failed',
                message: 'Monitoring ma’lumotlarini yangilab bo‘lmadi.',
                level: 'danger',
                icon: 'bi-wifi-off',
                delay: 3200,
            });
            playError();
        } finally {
            setUpdatingState(false);
        }
    }

    document.addEventListener('click', function (event) {
        const refreshButton = event.target.closest('.js-live-refresh-btn');
        if (refreshButton && liveRoot.contains(refreshButton)) {
            event.preventDefault();
            refreshLiveData({ runCheck: 1, updateUrl: false });
            return;
        }

        const pageLink = event.target.closest('.js-target-live-nav');
        if (pageLink && liveRoot.contains(pageLink)) {
            event.preventDefault();
            refreshLiveData({
                search: pageLink.getAttribute('href') || '',
                runCheck: parseInt(pageLink.dataset.runCheck || '0', 10),
                updateUrl: true,
            });
        }
    });

    document.addEventListener('change', function (event) {
        if (!event.target.classList.contains('js-auto-refresh-toggle') || !liveRoot.contains(event.target)) {
            return;
        }
        localStorage.setItem(autoRefreshKey, String(event.target.checked));
        applyAutoRefreshState(event.target.checked);
        notify({
            title: event.target.checked ? 'Auto refresh enabled' : 'Auto refresh paused',
            message: event.target.checked ? 'Sahifa endi fon rejimida yangilanadi.' : 'Avtomatik yangilanish vaqtincha to‘xtatildi.',
            level: event.target.checked ? 'success' : 'warning',
            icon: event.target.checked ? 'bi-play-circle-fill' : 'bi-pause-circle-fill',
            delay: 1800,
        });
    });

    syncAutoRefreshToggle();
    applyAutoRefreshState(getAutoRefreshEnabled());
    buildCharts();
})();

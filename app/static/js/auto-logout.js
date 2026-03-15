// Auto-logout after 5 minutes of inactivity
(function () {
    const INACTIVITY_TIMEOUT = 5 * 60 * 1000; // 5 minutes in milliseconds
    const WARNING_TIME = 30 * 1000; // Show warning 30 seconds before logout
    let inactivityTimer;
    let warningTimer;
    let warningShown = false;

    function resetInactivityTimer() {
        // Clear existing timers
        clearTimeout(inactivityTimer);
        clearTimeout(warningTimer);
        warningShown = false;
        hideWarning();

        // Set warning timer (30 seconds before logout)
        warningTimer = setTimeout(() => {
            showWarning();
        }, INACTIVITY_TIMEOUT - WARNING_TIME);

        // Set logout timer
        inactivityTimer = setTimeout(() => {
            performLogout();
        }, INACTIVITY_TIMEOUT);
    }

    function showWarning() {
        if (warningShown) return;
        warningShown = true;

        // Create warning banner
        const warning = document.createElement('div');
        warning.id = 'inactivityWarning';
        warning.className = 'alert alert-warning alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3';
        warning.style.zIndex = '9999';
        warning.style.maxWidth = '500px';
        warning.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        warning.innerHTML = `
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            <strong>Inactivity Warning:</strong> You will be logged out in 30 seconds due to inactivity.
            <button type="button" class="btn-close" data-bs-dismiss="alert" onclick="window.resetInactivityTimer()"></button>
        `;
        document.body.appendChild(warning);

        // Auto-hide warning if user becomes active
        setTimeout(() => {
            if (warningShown) {
                hideWarning();
            }
        }, WARNING_TIME);
    }

    function hideWarning() {
        const warning = document.getElementById('inactivityWarning');
        if (warning) {
            warning.remove();
        }
    }

    function performLogout() {
        // Show logout message
        const logoutMsg = document.createElement('div');
        logoutMsg.className = 'alert alert-info position-fixed top-50 start-50 translate-middle';
        logoutMsg.style.zIndex = '10000';
        logoutMsg.style.padding = '1.5rem 2rem';
        logoutMsg.style.boxShadow = '0 8px 24px rgba(0,0,0,0.2)';
        logoutMsg.innerHTML = '<i class="bi bi-info-circle-fill me-2"></i><strong>Logging out due to inactivity...</strong>';
        document.body.appendChild(logoutMsg);

        // Redirect to logout
        setTimeout(() => {
            window.location.href = '/logout';
        }, 1000);
    }

    // Track user activity
    const activityEvents = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    activityEvents.forEach(event => {
        document.addEventListener(event, resetInactivityTimer, true);
    });

    // Make resetInactivityTimer available globally for the warning button
    window.resetInactivityTimer = resetInactivityTimer;

    // Initialize timer on page load
    resetInactivityTimer();

    console.log('Auto-logout initialized: 5 minutes inactivity timeout');
})();

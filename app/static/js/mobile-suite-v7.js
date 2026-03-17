/**
 * NATIVE PRO MOBILE SUITE V7 (Optimized)
 * Pure Javascript Interactions. DOM is now Server-Side Rendered (SSR) for 0ms latency.
 */

(function () {
    'use strict';

    if (window.innerWidth > 992) return;

    console.log('📱 Mobile Suite: Native Core Initialized. SSR Active.');

    // 1. CLEANUP OLD JS SUITES (If any linger from cache)
    document.querySelectorAll('.mobile-header, .mobile-bottom-nav-v2, .mobile-fab, .mobile-nav-v5, .dashboard-v5-container').forEach(el => el.remove());

    // Hide Desktop Sidebar & Force content display
    const sidebar = document.getElementById('mainSidebar');
    if (sidebar) sidebar.style.display = 'none';

    // 2. TOGGLE APP MENU OVERLAY
    window.toggleAppMenuOverlay = function (e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        const overlay = document.getElementById('appMenuOverlay');
        const backdrop = document.querySelector('.menu-backdrop');

        if (overlay) overlay.classList.toggle('active');
        if (backdrop) backdrop.classList.toggle('active');

        // Prevent body scroll when open
        if (overlay && overlay.classList.contains('active')) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
    };

    // 3. ZOOM ENGINE
    let currentScale = 1.0;
    const minScale = 0.8;
    const maxScale = 1.3;

    window.applyMobileZoom = function (adjustment) {
        currentScale += adjustment;
        if (currentScale < minScale) currentScale = minScale;
        if (currentScale > maxScale) currentScale = maxScale;

        const bodyWrap = document.getElementById('mainContentArea');
        if (bodyWrap) {
            bodyWrap.style.transform = `scale(${currentScale})`;
            bodyWrap.style.transformOrigin = 'top center';
            bodyWrap.style.transition = 'transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)';

            if (currentScale < 1) {
                bodyWrap.style.width = (100 / currentScale) + '%';
            } else {
                bodyWrap.style.width = '100%';
            }
        }
    };

    // 4. "PULL TO REFRESH" ADVANCED ENGINE
    let touchstartY = 0;
    let currentY = 0;
    let isPulling = false;
    let pTrIndicator = document.getElementById('pullToRefreshIndicator');

    // Only enable if we are at the absolute top of the page
    document.addEventListener('touchstart', e => {
        if (window.scrollY === 0) {
            touchstartY = e.touches[0].clientY;
            isPulling = true;
        }
    }, { passive: true });

    document.addEventListener('touchmove', e => {
        if (!isPulling) return;
        currentY = e.touches[0].clientY;
        let pullDistance = currentY - touchstartY;

        // If pulling down
        if (pullDistance > 10 && window.scrollY === 0) {
            if (pTrIndicator) {
                pTrIndicator.style.display = 'flex';
                let pullOffset = Math.min(pullDistance / 2, 70) - 60; // Max slide down is 10px below top
                pTrIndicator.style.top = pullOffset + 'px';
            }
        }
    }, { passive: true });

    document.addEventListener('touchend', e => {
        if (!isPulling) return;
        isPulling = false;

        let pullDistance = currentY - touchstartY;

        // Threshold reached - Refresh!
        if (pullDistance > 120 && window.scrollY === 0) {
            if (pTrIndicator) {
                pTrIndicator.style.top = '15px';
                pTrIndicator.querySelector('span').textContent = "Updating...";
            }
            // Trigger haptic feedback if available (Advanced Mobile Feature)
            if (navigator.vibrate) navigator.vibrate(50);

            setTimeout(() => {
                window.location.reload();
            }, 500);
        } else {
            // Cancel pull
            if (pTrIndicator) {
                pTrIndicator.style.top = '-60px';
                setTimeout(() => pTrIndicator.style.display = 'none', 200);
            }
        }
    }, { passive: true });

    // 5. Responsive Fixes
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
    }, 500);

})();

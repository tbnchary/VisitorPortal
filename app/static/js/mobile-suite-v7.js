/**
 * MOBILE SUITE V7 - "NATIVE PRO" ENGINE
 * Features: Bottom Nav, Rich Menu Overlay, Responsive Dashboard Adaptation.
 */

(function () {
    'use strict';

    if (window.innerWidth > 992) return;

    console.log('📱 Mobile Suite V7: Initializing Native Pro Interface...');

    // 1. CLEANUP PREVIOUS SUITES
    document.querySelectorAll('.mobile-header, .mobile-bottom-nav, .mobile-fab, .mobile-header-v2, .mobile-background, .pro-header, .crystal-nav, .dock-nav, .mobile-nav-v2, .mobile-nav-v5, .mobile-header-v5, .dashboard-v5-container, .mobile-desktop-mirror-js, .mobile-top-bar, .sidebar-overlay').forEach(el => el.remove());

    // 2. FORCE SHOW DESKTOP ELEMENTS (BUT HIDE SIDEBAR)
    const sidebar = document.getElementById('mainSidebar');
    if (sidebar) sidebar.style.display = 'none'; // Replaced by Bottom Nav/Menu

    const dashboard = document.querySelector('.dashboard-grid-container') || document.querySelector('.dashboard-container');
    if (dashboard) {
        dashboard.style.display = 'block';
        dashboard.style.visibility = 'visible';
        dashboard.style.opacity = '1';
        dashboard.style.height = 'auto';
    }

    // 3. INJECT STICKY APP HEADER
    if (!document.querySelector('.app-header')) {
        const header = document.createElement('header');
        header.className = 'app-header';

        const userInitial = document.querySelector('.sidebar-avatar')?.textContent || 'A';
        const pageTitle = document.title.split('|')[0].trim();

        header.innerHTML = `
            <div class="app-brand">
                <i class="bi bi-grid-fill"></i>
                <span>${pageTitle}</span>
            </div>
            <div class="app-actions">
                <div class="zoom-controls">
                    <button id="mobileZoomOut" class="zoom-btn" title="Zoom Out"><i class="bi bi-dash-circle"></i></button>
                    <button id="mobileZoomIn" class="zoom-btn" title="Zoom In"><i class="bi bi-plus-circle"></i></button>
                    <div class="zoom-divider"></div>
                </div>
                <div class="header-avatar">${userInitial}</div>
            </div>
        `;
        document.body.prepend(header);
    }

    // 4. INJECT BOTTOM NAVIGATION
    if (!document.querySelector('.app-bottom-nav')) {
        const nav = document.createElement('nav');
        nav.className = 'app-bottom-nav';

        const path = location.pathname;

        // Structure: Dash | Users | [APP] | Logs | Exit
        nav.innerHTML = `
            <a href="/" class="nav-tab ${path === '/' ? 'active' : ''}">
                <i class="bi bi-grid-fill"></i>
                <span>Dash</span>
            </a>
            
            <a href="/groups" class="nav-tab ${path.includes('/groups') ? 'active' : ''}">
                <i class="bi bi-people-fill"></i>
                <span>Users</span>
            </a>
            
            <div class="nav-tab center-fab">
                <div class="fab-button" onclick="window.toggleMenuOverlay(event)"><i class="bi bi-grid-3x3-gap-fill"></i></div>
            </div>
            
            <a href="/logs" class="nav-tab ${path.includes('/logs') ? 'active' : ''}">
                <i class="bi bi-clock-history"></i>
                <span>Logs</span>
            </a>

            <a href="/logout" class="nav-tab exit-tab">
                <i class="bi bi-box-arrow-right"></i>
                <span>Exit</span>
            </a>
        `;
        document.body.appendChild(nav);
    }

    // 5. INJECT "MORE" MENU DRAWER
    if (!document.querySelector('.menu-overlay')) {
        // Backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'menu-backdrop';
        backdrop.onclick = function (e) { window.toggleMenuOverlay(e); };
        document.body.appendChild(backdrop);

        // Sidebar Drawer
        const overlay = document.createElement('div');
        overlay.className = 'menu-overlay';
        overlay.id = 'appMenuOverlay';

        const path = location.pathname;
        const userInitial = document.querySelector('.sidebar-avatar')?.textContent || 'A';
        const userName = document.querySelector('.sidebar-user-name')?.textContent || 'Administrator';

        // Stats (simulated grab from desktop sidebar if available)
        const onSite = document.getElementById('sidebarActiveCount')?.textContent || '0';
        const today = document.getElementById('sidebarTodayCount')?.textContent || '0';

        overlay.innerHTML = `
            <div style="display:flex; align-items:center; gap:8px; padding-bottom:24px; border-bottom:1px solid rgba(255,255,255,0.1); margin-bottom:20px;">
                <div style="width:32px; height:32px; background:#4f46e5; border-radius:8px; display:flex; align-items:center; justify-content:center; color:white;"><i class="bi bi-building"></i></div>
                <h3 style="margin:0; font-size:16px; font-weight:700; color:white;">Visitor Portal</h3>
            </div>
            
            <div class="menu-search">
                <i class="bi bi-search"></i>
                <input type="text" placeholder="Quick search..." readonly onclick="window.location.href='/logs'">
            </div>
            
            <div class="menu-list">
                <a href="/" class="menu-item ${path === '/' ? 'active' : ''}">
                    <i class="bi bi-grid-1x2"></i>
                    <span>Dashboard</span>
                    ${path === '/' ? '<span style="margin-left:auto; background:rgba(255,255,255,0.2); padding:2px 6px; border-radius:4px; font-size:10px;">0</span>' : ''}
                </a>
                <a href="/logs" class="menu-item ${path.includes('/logs') ? 'active' : ''}">
                    <i class="bi bi-clock-history"></i>
                    <span>Visitor Logs</span>
                </a>
                <a href="/groups" class="menu-item ${path.includes('/groups') ? 'active' : ''}">
                    <i class="bi bi-people-fill"></i>
                    <span>Visitor Groups</span>
                </a>
                <a href="/add" class="menu-item ${path.includes('/add') ? 'active' : ''}">
                    <i class="bi bi-person-plus"></i>
                    <span>Add Visitor</span>
                </a>
                <a href="/export_csv" class="menu-item ${path.includes('/export') ? 'active' : ''}">
                    <i class="bi bi-download"></i>
                    <span>Export Data</span>
                </a>

                <a href="/settings" class="menu-item ${path.includes('/settings') ? 'active' : ''}">
                    <i class="bi bi-envelope-gear"></i>
                    <span>Email Config</span>
                </a>
                <a href="/users" class="menu-item ${path.includes('/users') ? 'active' : ''}">
                    <i class="bi bi-people"></i>
                    <span>User Management</span>
                </a>
            </div>

            <div class="menu-footer">
                <div class="menu-stats-row">
                    <div class="menu-stat">
                        <div class="menu-stat-lbl">On-Site</div>
                        <div class="menu-stat-val" style="color:#22c55e;">${onSite}</div>
                    </div>
                    <div class="menu-stat">
                        <div class="menu-stat-lbl">Today</div>
                        <div class="menu-stat-val">${today}</div>
                    </div>
                </div>

                <div class="menu-profile" onclick="window.location.href='/profile'">
                    <div class="menu-avatar">${userInitial}</div>
                    <div class="menu-user-info">
                        <div>${userName}</div>
                        <div>My Profile</div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    // 6. TOGGLE FUNCTION (Global)
    window.toggleMenuOverlay = function (e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        console.log('Toggle Menu Clicked');
        const el = document.getElementById('appMenuOverlay');
        const bd = document.querySelector('.menu-backdrop');

        if (el) {
            el.classList.toggle('active');
            console.log('Overlay Toggled', el.classList.contains('active'));
        } else {
            console.error('Overlay Element Not Found');
        }

        if (bd) bd.classList.toggle('active');
    };

    // 7. ZOOM ENGINE
    let currentScale = 1.0;
    const minScale = 0.8;
    const maxScale = 1.5;

    function applyZoom() {
        const bodyWrap = document.querySelector('.main-content') || document.body;
        bodyWrap.style.transform = `scale(${currentScale})`;
        bodyWrap.style.transformOrigin = 'top center';
        bodyWrap.style.transition = 'transform 0.2s ease';

        // Adjust padding to compensate for scale shrink/expand
        if (currentScale < 1) {
            bodyWrap.style.width = (100 / currentScale) + '%';
        } else {
            bodyWrap.style.width = '100%';
        }
    }

    const zoomInBtn = document.getElementById('mobileZoomIn');
    const zoomOutBtn = document.getElementById('mobileZoomOut');

    if (zoomInBtn && zoomOutBtn) {
        zoomInBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (currentScale < maxScale) {
                currentScale += 0.1;
                applyZoom();
            }
        });

        zoomOutBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (currentScale > minScale) {
                currentScale -= 0.1;
                applyZoom();
            }
        });
    }

    // 8. Responsive Fixes for Charts
    setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
        // Fix table horizontal scroll
        const cardBody = document.querySelector('.table-card > div, .table-responsive');
        if (cardBody) cardBody.style.overflowX = 'auto';
    }, 500);

})();

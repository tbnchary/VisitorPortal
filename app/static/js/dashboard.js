// ═══════════════════════════════════════════════════════════════
// DASHBOARD ENGINE  dashboard.js  –  2026-02-24
// RAW data is set by inline <script> in the template before this loads
// ═══════════════════════════════════════════════════════════════
(function () {
    'use strict';

    // ── State ────────────────────────────────────────────────────────────
    window.onerror = function (msg, url, line, col, error) {
        var el = document.getElementById('purposeInsight');
        if (el) el.innerHTML = '<i class="bi bi-bug-fill text-danger me-1"></i>JS Error: ' + msg;
        return false;
    };

    try {
        if (typeof ChartDataLabels !== 'undefined' && typeof Chart !== 'undefined') {
            Chart.register(ChartDataLabels);
        }
    } catch (e) { console.warn('Global registration skipped', e); }

    var labelsVisible = true;
    var trendChart = null;
    var purposeChart = null;
    var hourlyChart = null;
    var maximizedChart = null;
    var DRI_STACK = [];
    var PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6', '#ec4899'];
    var showAvgLine = false;
    var showPeakPin = false;
    var currentAvg = 0;

    // ── Custom Plugin: Doughnut Center Text ────────────────────────────────
    var centerTextPlugin = {
        id: 'centerText',
        afterDraw: function (chart) {
            if (chart.config.type !== 'doughnut') return;
            var ctx = chart.ctx;
            var width = chart.width;
            var height = chart.height;
            var fontSize = (height / 160).toFixed(2);
            ctx.restore();
            ctx.font = "bold " + fontSize + "em 'Plus Jakarta Sans'";
            ctx.textBaseline = "middle";
            ctx.fillStyle = "#1e293b";

            var total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
            var text = total.toString();
            var textX = Math.round((width - ctx.measureText(text).width) / 2);
            var textY = height / 2 - 5;
            ctx.fillText(text, textX, textY);

            ctx.font = "600 0.8em 'Plus Jakarta Sans'";
            ctx.fillStyle = "#64748b";
            var label = "TOTAL";
            var labelX = Math.round((width - ctx.measureText(label).width) / 2);
            var labelY = height / 2 + 15;
            ctx.fillText(label, labelX, labelY);
            ctx.save();
        }
    };
    try {
        if (typeof Chart !== 'undefined') {
            Chart.register(centerTextPlugin);
        }
    } catch (e) { console.warn('Center text plugin registration failed', e); }

    var trendDates = [];
    var trendCounts = [];
    var purposeData = [];            // [{label, value}]
    var hourlyData = new Array(24).fill(0);

    var _trendType = 'line';
    var _purposeType = 'polarArea';
    var _hourlyType = 'bar';
    var REFRESH_INT = 60000; // 60s
    var refreshTimer = null;

    // ── Parse RAW data ───────────────────────────────────────────────────
    function parseData() {
        var raw = window.DASH_RAW || {};
        trendDates = (raw.dates || []).map(String);
        trendCounts = (raw.counts || []).map(Number);
        currentAvg = Number(raw.avg) || 0;

        purposeData = (raw.purpose || []).map(function (p) {
            if (p && typeof p === 'object') {
                return { label: p.purpose || 'Other', value: Number(p.count) || 0 };
            }
            return { label: 'Other', value: 0 };
        });
        hourlyData.fill(0);
        (raw.hourly || []).forEach(function (h) {
            if (h && typeof h === 'object' && h.hour >= 0 && h.hour < 24) {
                hourlyData[h.hour] = Number(h.count) || 0;
            }
        });
    }

    // ── Label config ─────────────────────────────────────────────────────
    function labelCfg(anchor, align, offset, color) {
        return {
            display: function (ctx) {
                if (!labelsVisible) return false;
                var v = ctx.dataset.data[ctx.dataIndex];
                return (v !== null && v !== undefined && Number(v) > 0);
            },
            color: color || '#1e293b',
            font: { weight: 'bold', size: 11 },
            formatter: function (v) {
                return (v !== null && v !== undefined && Number.isFinite(Number(v))) ? Number(v) : '';
            },
            anchor: anchor || 'start',
            align: align || 'end',
            offset: (offset !== undefined) ? offset : 5,
            clip: false
        };
    }

    // ── TREND CHART ──────────────────────────────────────────────────────
    function createTrendChart(type) {
        if (type) _trendType = type;
        var canvas = document.getElementById('trendChart');
        if (!canvas) return;
        if (trendChart) { trendChart.destroy(); trendChart = null; }
        if (!trendDates.length) {
            console.log('No trend data to display');
            return;
        }

        var isLine = (_trendType === 'line');
        var ctx = canvas.getContext('2d');
        var grad = ctx.createLinearGradient(0, 0, 0, 200);
        grad.addColorStop(0, 'rgba(79, 70, 229, 0.4)');
        grad.addColorStop(1, 'rgba(79, 70, 229, 0.0)');

        trendChart = new Chart(canvas, {
            type: _trendType,
            plugins: [ChartDataLabels],
            data: {
                labels: trendDates,
                datasets: [{
                    label: 'Visitors',
                    data: trendCounts,
                    borderColor: '#4f46e5',
                    borderWidth: isLine ? 3 : 0,
                    backgroundColor: isLine ? grad : '#6366f1',
                    fill: isLine,
                    tension: 0.4,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#4f46e5',
                    pointBorderWidth: 2,
                    pointRadius: isLine ? 4 : 0,
                    pointHoverRadius: 6,
                    borderRadius: isLine ? 0 : 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: isLine ? 30 : 5, right: 20, left: 10, bottom: 5 } },
                plugins: {
                    legend: { display: false },
                    datalabels: labelCfg('end', 'top', 8, '#1e293b'),
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        padding: 12,
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        callbacks: {
                            label: function (ctx) { return ' ' + ctx.raw + ' Visitors'; }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0, 0, 0, 0.05)', drawBorder: false },
                        ticks: { color: '#94a3b8', font: { size: 10, weight: '600' } }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#64748b', font: { size: 10, weight: '600' } }
                    }
                },
                onClick: (e, els, chart) => {
                    if (els && els.length > 0) {
                        const index = els[0].index;
                        const label = chart.data.labels[index];
                        if (window.showTrendDetails) window.showTrendDetails(label);
                    }
                }
            }
        });

        // Apply any existing search filter to the new chart
        filterTrendChart();
    }

    // ── PURPOSE CHART ────────────────────────────────────────────────────
    function createPurposeChart(type) {
        if (type) _purposeType = type;
        var canvas = document.getElementById('purposeChart');
        if (!canvas) return;
        if (purposeChart) { purposeChart.destroy(); purposeChart = null; }

        var insightEl = document.getElementById('purposeInsight');
        if (insightEl) {
            if (purposeData.length > 0) {
                insightEl.style.display = 'inline-flex';
                insightEl.innerHTML = '<i class="bi bi-clock-history me-1"></i>Analyzing patterns...';
            } else {
                insightEl.style.display = 'none';
            }
        }

        if (!purposeData.length) return;

        var isBar = (_purposeType === 'bar');
        var isRadial = !isBar;
        var labels = purposeData.map(function (p) { return p.label; });
        var values = purposeData.map(function (p) { return p.value; });
        var total = values.reduce((a, b) => a + b, 0);

        // Update custom legend
        var leg = document.getElementById('purposeCustomLegend');
        if (leg && isRadial) {
            leg.innerHTML = labels.map(function (l, i) {
                return '<div class="custom-legend-item" data-index="' + i + '">' +
                    '<span class="legend-dot" style="background:' + PALETTE[i % PALETTE.length] + '"></span>' +
                    '<span>' + l + '</span></div>';
            }).join('');

            // Sync hover
            leg.querySelectorAll('.custom-legend-item').forEach(function (item) {
                item.onmouseenter = function () {
                    if (purposeChart) {
                        purposeChart.setActiveElements([{ datasetIndex: 0, index: parseInt(this.dataset.index) }]);
                        purposeChart.update();
                    }
                };
                item.onmouseleave = function () {
                    if (purposeChart) {
                        purposeChart.setActiveElements([]);
                        purposeChart.update();
                    }
                };
            });
        } else if (leg) { leg.innerHTML = ''; }

        if (insightEl && purposeData.length > 0) {
            var top = purposeData[0] || { label: '—', value: 0 };
            var pct = total > 0 ? Math.round((top.value / total) * 100) : 0;
            insightEl.innerHTML = '<i class="bi bi-lightning-charge-fill me-1"></i>Most visits: <b>' + top.label + '</b> (' + pct + '%)';
        }

        purposeChart = new Chart(canvas, {
            type: isBar ? 'bar' : _purposeType,
            plugins: [ChartDataLabels],
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: PALETTE,
                    borderColor: '#ffffff',
                    borderWidth: 2,
                    hoverOffset: 15,
                    cutout: '70%' // Thinner lines for premium look
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: isBar ? 'y' : 'x',
                layout: { padding: isBar ? { top: 5, right: 60, bottom: 5, left: 5 } : 30 },
                plugins: {
                    legend: { display: false },
                    datalabels: isBar
                        ? labelCfg('end', 'right', 5, '#1e293b')
                        : {
                            display: labelsVisible,
                            color: '#fff',
                            font: { weight: 'bold', size: 10 },
                            formatter: function (v, ctx) {
                                var p = Math.round((v / total) * 100);
                                return p > 5 ? p + '%' : '';
                            }
                        },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.9)',
                        padding: 12,
                        callbacks: {
                            label: function (ctx) {
                                var v = ctx.raw;
                                var p = Math.round((v / total) * 100);
                                return ' ' + ctx.label + ': ' + v + ' (' + p + '%)';
                            }
                        }
                    }
                },
                scales: isBar ? {
                    x: { display: false },
                    y: { grid: { display: false }, ticks: { font: { weight: '700' } } }
                } : {},
                onClick: (e, els, chart) => {
                    if (els && els.length > 0) {
                        const index = els[0].index;
                        const label = chart.data.labels[index];
                        if (window.openDrill) window.openDrill('purpose', label);
                    }
                }
            }
        });
    }

    // ── HOURLY CHART ─────────────────────────────────────────────────────
    function createHourlyChart(type) {
        if (type) _hourlyType = type;
        var canvas = document.getElementById('hourlyChart');
        if (!canvas) return;
        if (hourlyChart) { hourlyChart.destroy(); hourlyChart = null; }

        var isRadar = (_hourlyType === 'radar');
        var isLine = (_hourlyType === 'line');
        var labels = hourlyData.map(function (_, i) { return i + ':00'; });

        var ctx = canvas.getContext('2d');
        var grad = ctx.createLinearGradient(0, 0, 0, 200);
        grad.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
        grad.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

        hourlyChart = new Chart(canvas, {
            type: _hourlyType,
            plugins: [ChartDataLabels],
            data: {
                labels: labels,
                datasets: [{
                    label: 'Traffic',
                    data: hourlyData,
                    backgroundColor: isRadar ? 'rgba(79,70,229,0.12)' : (isLine ? grad : '#4f46e5'),
                    borderColor: '#6366f1',
                    borderWidth: (isRadar || isLine) ? 3 : 0,
                    fill: (isRadar || isLine),
                    tension: 0.4,
                    borderRadius: (isRadar || isLine) ? 0 : 6,
                    pointRadius: isLine ? 4 : 0,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#6366f1',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: isRadar ? 40 : 20, bottom: 10, left: 10, right: 10 } },
                plugins: {
                    legend: { display: false },
                    datalabels: isRadar
                        ? labelCfg('center', 'center', 0, '#1e293b')
                        : labelCfg('end', 'top', 8, '#1e293b'),
                    tooltip: { backgroundColor: 'rgba(15,23,42,0.9)', padding: 12 }
                },
                scales: isRadar ? {} : {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.05)', drawBorder: false },
                        ticks: { color: '#94a3b8', font: { size: 10, weight: '600' }, maxTicksLimit: 5 }
                    },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 10, weight: '600' } } }
                },
                onClick: (e, els, chart) => {
                    if (els && els.length > 0) {
                        const index = els[0].index;
                        if (window.openDrill) window.openDrill('hour', index);
                    }
                }
            }
        });
    }

    // ── TYPE SWITCHERS (exposed globally) ────────────────────────────────
    window.setTrendType = function (t, btn) {
        document.querySelectorAll('#trend-type-toggles .chart-toggle-btn').forEach(function (b) { b.classList.remove('active'); });
        if (btn) btn.classList.add('active');
        createTrendChart(t);
    };
    window.setPurposeType = function (t, btn) {
        document.querySelectorAll('#purpose-type-toggles .chart-toggle-btn').forEach(function (b) { b.classList.remove('active'); });
        if (btn) btn.classList.add('active');
        createPurposeChart(t);
    };
    window.setHourlyType = function (t, btn) {
        document.querySelectorAll('#hourly-type-toggles .chart-toggle-btn').forEach(function (b) { b.classList.remove('active'); });
        if (btn) btn.classList.add('active');
        createHourlyChart(t);
    };

    // ── LABEL TOGGLE ─────────────────────────────────────────────────────
    window.toggleAllLabels = function () {
        labelsVisible = !labelsVisible;
        [trendChart, purposeChart, hourlyChart].forEach(function (c) { if (c) c.update(); });
        var btn = document.getElementById('labelToggleBtn');
        var span = btn && btn.querySelector('span');
        if (span) span.innerText = labelsVisible ? 'Hide Data Labels' : 'Show Data Labels';
    };

    // ── MAXIMIZE ─────────────────────────────────────────────────────────
    window.maximizeChart = function (name) {
        var sources = { trend: trendChart, purpose: purposeChart, hourly: hourlyChart };
        var source = sources[name];
        var overlay = document.getElementById('maximizeOverlay');
        if (!overlay || !source) return;

        document.getElementById('maximizeTitle').innerText = name.charAt(0).toUpperCase() + name.slice(1) + ' Analysis';
        overlay.querySelector('.maximize-content').innerHTML =
            '<canvas id="maximizedCanvas" style="display:block;width:100%;height:100%;"></canvas>';

        document.body.style.overflow = 'hidden';
        overlay.style.display = 'flex';
        overlay.style.opacity = '0';
        requestAnimationFrame(function () {
            requestAnimationFrame(function () { overlay.style.opacity = '1'; });
        });

        setTimeout(function () {
            if (maximizedChart) { maximizedChart.destroy(); maximizedChart = null; }
            var canvas = document.getElementById('maximizedCanvas');
            if (!canvas) return;

            var srcType = source.config.type;
            var isRadial = ['pie', 'polarArea', 'doughnut', 'radar'].indexOf(srcType) >= 0;
            var srcData = JSON.parse(JSON.stringify(source.data));
            if (srcType === 'line' && srcData.datasets) {
                srcData.datasets.forEach(function (ds) {
                    if (typeof ds.backgroundColor !== 'string') {
                        ds.backgroundColor = 'rgba(79,70,229,0.2)';
                    }
                });
            }

            maximizedChart = new Chart(canvas, {
                type: srcType,
                plugins: [ChartDataLabels],
                data: srcData,
                options: {
                    responsive: true, maintainAspectRatio: false,
                    layout: { padding: isRadial ? 80 : 40 },
                    plugins: {
                        legend: {
                            display: true,
                            position: isRadial ? 'right' : 'top',
                            labels: { color: '#1e293b', font: { size: 13, weight: 'bold' }, padding: 16 }
                        },
                        datalabels: isRadial
                            ? labelCfg('center', 'center', 0, '#1e293b')
                            : (srcType === 'line'
                                ? labelCfg('end', 'top', 4, '#1e293b')
                                : labelCfg('end', 'top', 8, '#1e293b'))
                    },
                    scales: isRadial ? {} : {
                        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.06)' }, ticks: { color: '#475569' } },
                        x: { grid: { display: false }, ticks: { color: '#475569' } }
                    }
                }
            });
        }, 380);
    };

    window.closeMaximizeModal = function () {
        var overlay = document.getElementById('maximizeOverlay');
        if (!overlay) return;
        overlay.style.opacity = '0';
        setTimeout(function () { overlay.style.display = 'none'; }, 380);
        document.body.style.overflow = '';
        if (maximizedChart) { maximizedChart.destroy(); maximizedChart = null; }
    };

    // ── DRILLTHROUGH ─────────────────────────────────────────────────────
    var DRILL_TITLES = {
        total: 'Total Records', active: 'Currently On-Site',
        today: "Today's Check-ins", avg_duration: 'Duration Insights',
        sheds_avail: 'Available Sheds', rooms_ready: 'Rooms Ready',
        rooms_blocked: 'Blocked Rooms', active_shed: 'Shed Visitors'
    };

    window.openDrill = function (type, value) {
        var title = DRILL_TITLES[type] ||
            (type === 'host' ? 'Host: ' + value :
                type === 'company' ? 'Company: ' + value :
                    type === 'purpose' ? 'Purpose: ' + value :
                        type === 'hour' ? value + ':00 Activity' :
                            type === 'trend' ? 'Traffic on ' + value : 'Details');
        DRI_STACK.push({ type: type, value: value, title: title });
        fetchDrill(type, value, title);
    };
    window.openDrawer = function (type) { window.openDrill(type, null); };
    window.openDrillDown = function (t, v) { window.openDrill(t, v); };
    window.showTrendDetails = function (d) { window.openDrill('trend', d); };
    window.showDetails = function (id) { fetchVisitorDetails(id); };

    window.goBackDrill = function () {
        if (DRI_STACK.length <= 1) {
            DRI_STACK.length = 0;
            if (window.closeGlobalDrawer) window.closeGlobalDrawer();
            return;
        }
        DRI_STACK.pop();
        var prev = DRI_STACK[DRI_STACK.length - 1];
        fetchDrill(prev.type, prev.value, prev.title);
    };

    function clearDrawerPadding() {
        var b = document.getElementById('globalDrawerBody');
        if (b) b.style.padding = '0';
    }

    function fetchDrill(type, value, title) {
        var spinner = '<div class="p-5 text-center"><div class="spinner-border text-primary"></div></div>';
        if (window.openGlobalDrawer) window.openGlobalDrawer(title, spinner);
        clearDrawerPadding();

        var url = '/api/analytics/drilldown?type=' + encodeURIComponent(type);
        if (value !== null && value !== undefined) url += '&value=' + encodeURIComponent(value);

        fetch(url)
            .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
            .then(function (result) { renderDrawer(title, result); })
            .catch(function (err) {
                console.error('Drilldown error', err);
                if (window.openGlobalDrawer) {
                    window.openGlobalDrawer(title,
                        '<div class="p-4 text-danger"><i class="bi bi-exclamation-triangle me-2"></i>Failed to load. Please try again.</div>');
                }
            });
    }

    function renderDrawer(title, result) {
        var category = result.category || '';
        var data = result.data || [];
        var backBtn = DRI_STACK.length > 1
            ? '<button onclick="goBackDrill()" class="btn btn-sm btn-light rounded-circle me-2"><i class="bi bi-arrow-left"></i></button>'
            : '';

        var html = '<div class="p-3 border-bottom sticky-top bg-white" style="z-index:10;">' +
            '<div class="d-flex justify-content-between align-items-center">' +
            '<div class="d-flex align-items-center">' + backBtn +
            '<h5 class="fw-800 mb-0" style="font-size:1.1rem;color:#1e293b;">' + escHtml(title) + '</h5>' +
            '</div><span class="badge text-bg-primary rounded-pill px-3">' + data.length + '</span>' +
            '</div></div><div class="list-group list-group-flush">';

        if (!data.length) {
            html += '<div class="text-center py-5 text-muted">' +
                '<i class="bi bi-search fs-1 mb-3 d-block opacity-25"></i>' +
                '<p>No entries found.</p></div>';
        } else {
            data.forEach(function (item) {
                if (category === 'visitors') {
                    html += renderVisitorRow(item);
                } else if (category === 'logistics') {
                    html += renderLogisticsRow(item);
                }
            });
        }
        html += '</div>';

        if (window.openGlobalDrawer) {
            window.openGlobalDrawer(title, html);
            clearDrawerPadding();
        }
    }

    function escHtml(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function renderVisitorRow(item) {
        var initial = item.visitor_name ? item.visitor_name[0].toUpperCase() : '?';
        var statusBg = item.status === 'IN' ? 'bg-success' : 'bg-secondary';
        var dur = item.duration && item.duration !== '--'
            ? '<span class="chip"><i class="bi bi-clock me-1"></i>' + escHtml(item.duration) + '</span>' : '';
        var dt = item.check_in_date
            ? '<span class="chip"><i class="bi bi-calendar3 me-1"></i>' + escHtml(item.check_in_date) + '</span>' : '';
        var co = escHtml(item.company || 'Direct');
        var host = escHtml(item.person_to_meet || '—');

        return '<div class="list-group-item list-group-item-action py-3 px-3 d-flex align-items-center gap-3" ' +
            'style="cursor:pointer;" onclick="fetchVisitorDetails(' + item.id + ')">' +
            '<div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#4f46e5,#818cf8);' +
            'color:#fff;display:flex;align-items:center;justify-content:center;font-size:1rem;font-weight:700;flex-shrink:0;">' +
            initial + '</div>' +
            '<div class="flex-grow-1 min-w-0">' +
            '<div class="d-flex justify-content-between align-items-center">' +
            '<span class="fw-700" style="color:#1e293b;">' + escHtml(item.visitor_name || '—') + '</span>' +
            '<span class="badge ' + statusBg + ' ms-2" style="font-size:.65rem;">' + escHtml(item.status || '') + '</span>' +
            '</div>' +
            '<div class="d-flex gap-1 mt-1 flex-wrap">' +
            '<span class="chip" data-drilltype="company" data-drillval="' + co + '"><i class="bi bi-building me-1"></i>' + co + '</span>' +
            '<span class="chip" data-drilltype="host"    data-drillval="' + host + '"><i class="bi bi-person me-1"></i>' + host + '</span>' +
            dur + dt +
            '</div></div>' +
            '<i class="bi bi-chevron-right text-muted small"></i></div>';
    }

    function renderLogisticsRow(item) {
        var isShed = item.type === 'SHED';
        return '<div class="list-group-item py-3 px-3 d-flex align-items-center gap-3">' +
            '<div style="width:42px;height:42px;border-radius:12px;background:' +
            (isShed ? '#e0f2fe' : '#dcfce7') + ';color:' + (isShed ? '#0369a1' : '#15803d') +
            ';display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0;">' +
            '<i class="bi bi-' + (isShed ? 'building-up' : 'door-open') + '"></i></div>' +
            '<div class="flex-grow-1"><div class="fw-700" style="color:#1e293b;">' + escHtml(item.name || '—') + '</div>' +
            '<div class="text-muted small">' + escHtml(item.status || '') +
            (item.extra ? ' &bull; ' + escHtml(item.extra) : '') + '</div></div>' +
            '<span class="badge bg-light text-secondary border">ID: ' + item.id + '</span></div>';
    }

    // Chip click delegation (company/host drill)
    document.addEventListener('click', function (e) {
        var chip = e.target.closest('[data-drilltype]');
        if (chip) {
            e.stopPropagation();
            openDrill(chip.dataset.drilltype, chip.dataset.drillval);
        }
    });

    // ── VISITOR DETAIL ────────────────────────────────────────────────────
    window.fetchVisitorDetails = function (id) {
        var spinner = '<div class="p-5 text-center"><div class="spinner-border text-primary"></div></div>';
        if (window.openGlobalDrawer) window.openGlobalDrawer('Visitor Profile', spinner);
        clearDrawerPadding();

        fetch('/api/visitor/details/' + id)
            .then(function (r) { if (!r.ok) throw new Error('Not found'); return r.json(); })
            .then(function (v) {
                var initial = v.visitor_name ? v.visitor_name[0].toUpperCase() : '?';
                var statusClass = v.status === 'IN' ? 'status-in' : 'status-out';
                var statusText = v.status === 'IN' ? 'ACTIVE' : 'DEPARTED';

                var html =
                    '<div class="profile-drawer-content">' +
                    '<!-- Header -->' +
                    '<div class="profile-header">' +
                    '<div class="profile-avatar">' + initial + '</div>' +
                    '<h2 class="profile-name">' + escHtml(v.visitor_name || '—') + '</h2>' +
                    '<div class="d-flex justify-content-center gap-2 mb-2">' +
                    '<span class="badge-status ' + statusClass + '">' + statusText + '</span>' +
                    '<span class="badge" style="background:#dbeafe;color:#2563eb;font-weight:700;padding:0.4rem 0.8rem;border-radius:30px;">ID #' + (8000 + v.id) + '</span>' +
                    '</div>' +
                    '</div>' +

                    '<!-- Info Grid -->' +
                    '<div class="info-grid">' +
                    '<div class="info-item"><span class="info-label">Company</span><span class="info-value">' + escHtml(v.company || 'Direct') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">Contact</span><span class="info-value">' + escHtml(v.phone || '—') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">Host</span><span class="info-value">' + escHtml(v.person_to_meet || '—') + '</span></div>' +
                    '<div class="info-item"><span class="info-label">Purpose</span><span class="info-value">' + escHtml(v.purpose || 'Meeting') + '</span></div>' +
                    '</div>' +

                    '<!-- Stats Row -->' +
                    '<div class="stats-row">' +
                    '<div class="stat-box"><div class="stat-box-label">Total Visits</div><div class="stat-box-value">' + (v.total_visits || 1) + '</div></div>' +
                    '<div class="stat-box"><div class="stat-box-label">Status</div><div><span class="badge bg-primary px-2" style="font-size:0.65rem;">' + (v.total_visits > 3 ? 'REGULAR' : 'VISITOR') + '</span></div></div>' +
                    '<div class="stat-box"><div class="stat-box-label">Group</div><div class="stat-box-value" style="font-size:0.85rem;color:#1e293b;">' + escHtml(v.group_name || 'GENERAL') + '</div></div>' +
                    '</div>' +

                    '<!-- Arrival Card -->' +
                    '<div class="arrival-card">' +
                    '<div>' +
                    '<div class="info-label mb-1">Arrived At</div>' +
                    '<div class="arrival-time-large">' + (v.check_in_time || '--:--') + '</div>' +
                    '<div class="text-sub small">' + (v.check_in_date || '') + '</div>' +
                    '</div>' +
                    '<div class="qr-mini">' +
                    (v.custom_qr ? '<img src="' + v.custom_qr + '" style="width:100%;height:100%;object-fit:contain;">' : '<i class="bi bi-qr-code fs-2 opacity-25"></i>') +
                    '</div>' +
                    '</div>' +

                    '<!-- Security Assets -->' +
                    '<div class="security-section">' +
                    '<span class="section-title">Security Assets</span>' +
                    '<div class="asset-row">' +
                    '<span class="asset-label">Priority</span>' +
                    '<span class="badge" style="background:#22d3ee;color:white;font-weight:700;">' + escHtml(v.visit_priority || 'Normal') + '</span>' +
                    '</div>' +
                    '<div class="asset-row">' +
                    '<span class="asset-label">Laptop Serial</span>' +
                    '<span class="asset-value">' + escHtml(v.laptop_serial || 'None') + '</span>' +
                    '</div>' +
                    '</div>' +

                    '<!-- Footer -->' +
                    '<div class="profile-footer">' +
                    '<a href="/badge/' + v.id + '" target="_blank" class="btn-print"><i class="bi bi-printer-fill"></i> Print Badge</a>' +
                    (DRI_STACK.length > 0 ? '<button class="btn btn-sm btn-outline-secondary w-100 mb-2" onclick="goBackDrill()"><i class="bi bi-arrow-left me-1"></i>Back to list</button>' : '') +
                    '<button onclick="window.closeGlobalDrawer()" class="btn-dismiss">Dismiss</button>' +
                    '</div>' +
                    '</div>';

                if (window.openGlobalDrawer) {
                    window.openGlobalDrawer('Visitor Profile', html);
                    clearDrawerPadding();
                }
            })
            .catch(function (e) {
                console.error('Visitor detail error', e);
                if (window.openGlobalDrawer) {
                    window.openGlobalDrawer('Error',
                        '<div class="p-4 text-danger"><i class="bi bi-exclamation-triangle me-2"></i>Visitor profiles not found.</div>');
                }
            });
    };

    function field(label, value) {
        return '<div class="list-group-item px-0">' +
            '<small class="text-muted d-block text-uppercase" style="font-size:.7rem;letter-spacing:.05em;">' + label + '</small>' +
            '<strong>' + escHtml(value || '—') + '</strong></div>';
    }

    window.fetchAndShowDetails = window.fetchVisitorDetails;

    // ── TABLE FILTER ──────────────────────────────────────────────────────
    window.filterTable = function () {
        var input = document.getElementById('searchInput');
        if (!input) return;
        var q = input.value.toLowerCase();
        var rows = document.querySelectorAll('#visitorTableBody tr');
        var vis = 0;

        rows.forEach(function (r) {
            // Include data-search attributes if needed, but innerText is usually enough
            var match = r.innerText.toLowerCase().indexOf(q) >= 0;
            r.style.display = match ? '' : 'none';
            if (match) vis++;
        });

        var nr = document.getElementById('noResults');
        if (nr) nr.classList.toggle('d-none', vis > 0);
    };

    function updateVisitorTable(visitors) {
        var tbody = document.getElementById('visitorTableBody');
        if (!tbody) return;
        if (!visitors || !visitors.length) {
            tbody.innerHTML = '';
            document.getElementById('noResults').classList.remove('d-none');
            return;
        }

        var html = '';
        visitors.forEach(function (v) {
            var name = v.visitor_name || 'Unknown';
            var initial = name.charAt(0).toUpperCase();
            var checkInStr = v.check_in ? new Date(v.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-';
            var statusHtml = v.status === 'IN'
                ? '<span class="badge-status status-in"><span class="pulse-dot" style="width:6px;height:6px;background:#10b981;border-radius:50%;display:inline-block;"></span> ACTIVE</span>'
                : '<span class="badge-status status-out">DEPARTED</span>';

            html += '<tr class="clickable-row">' +
                '<td onclick="showDetails(' + v.id + ')">' +
                '<div class="d-flex align-items-center gap-3">' +
                '<div class="avatar" style="width:36px;height:36px;font-size:0.9rem;">' + initial + '</div>' +
                '<div>' +
                '<div class="fw-600 text-main">' + escHtml(name) + '</div>' +
                '<div class="text-sub" style="font-size:0.75rem;">' + escHtml(v.company || '-') + '</div>' +
                '</div>' +
                '</div>' +
                '</td>' +
                '<td onclick="openDrill(\'host\', \'' + (v.person_to_meet || '') + '\')">' +
                '<div class="text-main fw-600 border-bottom border-primary border-opacity-10 d-inline-block">' + escHtml(v.person_to_meet || '-') + '</div>' +
                '</td>' +
                '<td><div class="text-main fw-500">' + checkInStr + '</div></td>' +
                '<td>' + statusHtml + '</td>' +
                '<td class="text-end" onclick="showDetails(' + v.id + ')"><i class="bi bi-chevron-right text-sub small"></i></td>' +
                '</tr>';
        });
        tbody.innerHTML = html;
        document.getElementById('noResults').classList.add('d-none');
        // Re-apply current search if any
        filterTable();
    }

    // ── TREND FILTER & PERIOD ─────────────────────────────────────────────
    window.filterTrendChart = function () {
        if (!trendChart) return;
        var q = ((document.getElementById('trendSearchInput') || {}).value || '').toLowerCase();

        if (!q) {
            trendChart.data.labels = trendDates.slice();
            trendChart.data.datasets.forEach(function (ds) {
                if (ds.label === 'Visitors') ds.data = trendCounts.slice();
                else if (ds.label === 'Average') ds.data = new Array(trendDates.length).fill(currentAvg);
            });
        } else {
            var idxs = trendDates.reduce(function (a, d, i) {
                if (d.toLowerCase().indexOf(q) >= 0) a.push(i);
                return a;
            }, []);

            trendChart.data.labels = idxs.map(function (i) { return trendDates[i]; });
            trendChart.data.datasets.forEach(function (ds) {
                if (ds.label === 'Visitors') {
                    ds.data = idxs.map(function (i) { return trendCounts[i]; });
                } else if (ds.label === 'Average') {
                    ds.data = new Array(idxs.length).fill(currentAvg);
                }
            });
        }
        trendChart.update();
    };

    window.updatePeriod = function (days, btn) {
        var group = document.querySelector('.filter-group');
        if (group) {
            group.querySelectorAll('.filter-btn').forEach(function (b) { b.classList.remove('active'); });
        }
        if (btn) btn.classList.add('active');

        fetch('/api/chart-data/' + days)
            .then(function (r) { if (!r.ok) throw new Error('API Error'); return r.json(); })
            .then(function (data) {
                trendDates = (data.dates || []).map(String);
                trendCounts = (data.counts || []).map(Number);
                currentAvg = data.avg || 0;

                // Update UI Stat Cards
                var totEl = document.getElementById('stat-total-visits');
                if (totEl) totEl.innerText = data.total || 0;

                // Update Table
                updateVisitorTable(data.visitors);

                // Re-create the chart with new data
                createTrendChart();
                filterTrendChart();
            })
            .catch(function (e) {
                console.error('Period update failed:', e);
            });
    };

    window.toggleDateRange = function () {
        var container = document.getElementById('dateRangeContainer');
        var btn = document.getElementById('customBtn');
        if (container.classList.contains('d-none')) {
            container.classList.remove('d-none');
            btn.classList.add('active');
        } else {
            container.classList.add('d-none');
            btn.classList.remove('active');
        }
    };

    window.applyDateRange = function () {
        var start = document.getElementById('startDate').value;
        var end = document.getElementById('endDate').value;
        if (!start || !end) return alert('Please select both start and end dates');

        fetch('/api/chart-data/0?start=' + start + '&end=' + end)
            .then(function (r) { if (!r.ok) throw new Error('API Error'); return r.json(); })
            .then(function (data) {
                trendDates = (data.dates || []).map(String);
                trendCounts = (data.counts || []).map(Number);
                currentAvg = data.avg || 0;

                // Update UI Stat Cards
                var totEl = document.getElementById('stat-total-visits');
                if (totEl) totEl.innerText = data.total || 0;

                // Update Table
                updateVisitorTable(data.visitors);

                createTrendChart();
                filterTrendChart();
            })
            .catch(function (e) { console.error('Date range failed', e); });
    };

    window.toggleAverageLine = function () {
        showAvgLine = !showAvgLine;
        if (!trendChart) return;

        if (showAvgLine) {
            var val = currentAvg || (trendCounts.length ? trendCounts.reduce((a, b) => a + b, 0) / trendCounts.length : 0);
            var avgData = new Array(trendDates.length).fill(val);
            trendChart.data.datasets.push({
                label: 'Average',
                data: avgData,
                borderColor: 'rgba(239, 68, 68, 0.6)',
                borderWidth: 2,
                borderDash: [10, 5],
                pointRadius: 0,
                fill: false,
                datalabels: { display: false }
            });
        } else {
            trendChart.data.datasets = trendChart.data.datasets.filter(ds => ds.label !== 'Average');
        }
        trendChart.update();
    };

    window.togglePeakAnnotation = function () {
        showPeakPin = !showPeakPin;
        if (!trendChart) return;

        var peakVal = Math.max(...trendCounts);
        trendChart.options.plugins.datalabels.display = function (ctx) {
            if (!labelsVisible) return false;
            if (showPeakPin) {
                return ctx.dataset.data[ctx.dataIndex] === peakVal && peakVal > 0;
            }
            return ctx.dataset.data[ctx.dataIndex] > 0;
        };
        trendChart.update();
    };

    window.exportChart = function (name, format) {
        var canvas = document.getElementById(name + 'Chart');
        if (!canvas) return;
        var link = document.createElement('a');
        link.download = 'analytics_' + name + '_' + new Date().getTime() + '.' + format;
        link.href = canvas.toDataURL('image/' + format);
        link.click();
    };

    window.downloadTrendCSV = function () {
        var csv = 'Date,Count\n';
        trendDates.forEach(function (d, i) {
            csv += d + ',' + trendCounts[i] + '\n';
        });
        var blob = new Blob([csv], { type: 'text/csv' });
        var url = window.URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', 'visitor_trends.csv');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    // ── INIT ──────────────────────────────────────────────────────────────
    function init() {
        console.log('Dashboard Ultra-Safe Init Starting...');
        try {
            Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
            parseData();
        } catch (e) {
            console.error('Data parsing failed:', e);
            return;
        }

        try { createTrendChart(); } catch (e) { console.error('Trend Chart failed:', e); }
        try { createPurposeChart(); } catch (e) { console.error('Purpose Chart failed:', e); }
        try { createHourlyChart(); } catch (e) { console.error('Hourly Chart failed:', e); }

        var dd = document.getElementById('currentDate');
        if (dd) dd.innerText = new Date().toLocaleDateString('en-US',
            { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(function () {
            window.location.reload();
        }, REFRESH_INT);
        console.log('Dashboard Init Completed Successfully');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());

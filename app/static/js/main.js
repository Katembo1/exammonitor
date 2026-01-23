// ==================== GLOBAL STATE ====================
let socket;
let soundEnabled = true;
let isMonitoring = true;
let alerts = [];
let startTime = Date.now();

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', function() {
    initializeWebSocket();
    initializeEventListeners();
    initializeStats();
    loadHistoricalData();
    startUptimeCounter();
});

// ==================== WEBSOCKET CONNECTION ====================
function initializeWebSocket() {
    socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    
    socket.on('connect', function() {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
    });
    
    socket.on('disconnect', function() {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
    });
    
    socket.on('new_alert', function(data) {
        handleNewAlert(data);
    });
    
    socket.on('stats_update', function(data) {
        updateStats(data);
    });
    
    // Request stats every 5 seconds
    setInterval(() => {
        if (socket.connected) {
            socket.emit('request_stats');
        }
    }, 5000);
}

function updateConnectionStatus(connected) {
    const statusIndicator = document.querySelector('.status-indicator');
    const statusDot = document.querySelector('.status-dot');
    const statusText = statusIndicator.querySelector('span');
    
    if (connected) {
        statusIndicator.style.background = 'rgba(16, 185, 129, 0.1)';
        statusIndicator.style.borderColor = 'var(--success)';
        statusIndicator.style.color = 'var(--success)';
        statusDot.style.background = 'var(--success)';
        statusText.textContent = 'Live';
    } else {
        statusIndicator.style.background = 'rgba(239, 68, 68, 0.1)';
        statusIndicator.style.borderColor = 'var(--danger)';
        statusIndicator.style.color = 'var(--danger)';
        statusDot.style.background = 'var(--danger)';
        statusText.textContent = 'Offline';
    }
}

// ==================== EVENT LISTENERS ====================
function initializeEventListeners() {
    // Sound toggle
    const soundToggle = document.getElementById('soundToggle');
    soundToggle.addEventListener('click', toggleSound);
    
    // Monitoring toggle
    const monitoringToggle = document.getElementById('monitoringToggle');
    monitoringToggle.addEventListener('click', toggleMonitoring);
    
    // Clear alerts
    const clearAlerts = document.getElementById('clearAlerts');
    clearAlerts.addEventListener('click', clearAllAlerts);
    
    // Tab switching
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    
    // Add camera button
    const addCamera = document.getElementById('addCamera');
    addCamera.addEventListener('click', showAddCameraDialog);
    
    // Export history
    const exportHistory = document.getElementById('exportHistory');
    exportHistory.addEventListener('click', exportHistoricalData);
    
    // History filters
    const filterBehavior = document.getElementById('filterBehavior');
    const filterReviewed = document.getElementById('filterReviewed');
    filterBehavior.addEventListener('change', filterHistory);
    filterReviewed.addEventListener('change', filterHistory);
}

// ==================== ALERT HANDLING ====================
function handleNewAlert(data) {
    alerts.unshift(data);
    
    // Limit to 50 alerts
    if (alerts.length > 50) {
        alerts = alerts.slice(0, 50);
    }
    
    // Add to live alerts display
    addAlertToUI(data);
    
    // Play sound if enabled
    if (soundEnabled) {
        playAlertSound();
    }
    
    // Flash notification
    flashNotification(data);
    
    // Update stats
    fetchStats();
}

function addAlertToUI(alert) {
    const container = document.getElementById('alertsContainer');
    
    // Remove "no alerts" message if present
    const noAlerts = container.querySelector('.no-alerts');
    if (noAlerts) {
        noAlerts.remove();
    }
    
    const alertElement = createAlertElement(alert);
    container.insertBefore(alertElement, container.firstChild);
}

function createAlertElement(alert) {
    const div = document.createElement('div');
    div.className = 'alert-item';
    div.dataset.alertId = alert.incident_id || Date.now();
    
    const behaviorClass = alert.behavior.toLowerCase().includes('cheating') ? 'danger' : 
                         alert.behavior.toLowerCase().includes('good') ? 'success' : 'warning';
    
    const timestamp = new Date(alert.timestamp);
    const timeString = timestamp.toLocaleTimeString();
    
    div.innerHTML = `
        <div class="alert-header">
            <span class="alert-title">${alert.student_id}</span>
            <span class="alert-badge badge-${behaviorClass}">${alert.behavior}</span>
        </div>
        <div class="alert-details">
            <div class="alert-detail">
                <strong>Time:</strong> ${timeString}
            </div>
            <div class="alert-detail">
                <strong>Confidence:</strong> ${(alert.confidence * 100).toFixed(1)}%
            </div>
            <div class="alert-detail">
                <strong>Camera:</strong> Camera ${alert.camera_id}
            </div>
        </div>
        <div class="alert-actions">
            <button class="btn-small btn-success" onclick="reviewAlert(${alert.incident_id || 0})">
                Mark Reviewed
            </button>
            <button class="btn-small" onclick="viewDetails(${alert.incident_id || 0})">
                View Details
            </button>
        </div>
    `;
    
    return div;
}

function playAlertSound() {
    const audio = document.getElementById('alertSound');
    if (audio) {
        audio.currentTime = 0;
        audio.play().catch(e => console.log('Could not play alert sound:', e));
    }
}

function flashNotification(alert) {
    // Create a temporary notification flash
    const flash = document.createElement('div');
    flash.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        z-index: 1000;
        animation: slideInRight 0.3s ease-out;
        max-width: 350px;
    `;
    
    flash.innerHTML = `
        <div style="font-weight: 600; margin-bottom: 0.5rem;">⚠️ New Alert</div>
        <div style="font-size: 0.875rem;">${alert.student_id} - ${alert.behavior}</div>
    `;
    
    document.body.appendChild(flash);
    
    setTimeout(() => {
        flash.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => flash.remove(), 300);
    }, 4000);
}

// ==================== CONTROL FUNCTIONS ====================
function toggleSound() {
    soundEnabled = !soundEnabled;
    const soundIcon = document.getElementById('soundIcon');
    const btn = document.getElementById('soundToggle');
    
    if (soundEnabled) {
        soundIcon.innerHTML = `
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
        `;
        btn.style.borderColor = 'var(--success)';
    } else {
        soundIcon.innerHTML = `
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
            <line x1="23" y1="9" x2="17" y2="15"></line>
            <line x1="17" y1="9" x2="23" y2="15"></line>
        `;
        btn.style.borderColor = 'var(--danger)';
    }
}

function toggleMonitoring() {
    isMonitoring = !isMonitoring;
    const btn = document.getElementById('monitoringToggle');
    const text = document.getElementById('monitoringText');
    
    if (isMonitoring) {
        btn.classList.remove('monitoring-inactive');
        btn.classList.add('monitoring-active');
        text.textContent = 'Active';
        btn.querySelector('svg').innerHTML = `
            <circle cx="12" cy="12" r="10"></circle>
            <polygon points="10 8 16 12 10 16 10 8"></polygon>
        `;
    } else {
        btn.classList.remove('monitoring-active');
        btn.classList.add('monitoring-inactive');
        text.textContent = 'Paused';
        btn.querySelector('svg').innerHTML = `
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="10" y1="15" x2="10" y2="9"></line>
            <line x1="14" y1="15" x2="14" y2="9"></line>
        `;
    }
}

function clearAllAlerts() {
    const container = document.getElementById('alertsContainer');
    container.innerHTML = `
        <div class="no-alerts">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <p>No alerts yet</p>
            <p class="text-muted">System is monitoring...</p>
        </div>
    `;
    alerts = [];
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    if (tabName === 'live') {
        document.getElementById('liveTab').classList.add('active');
    } else if (tabName === 'history') {
        document.getElementById('historyTab').classList.add('active');
        loadHistoricalData();
    }
}

// ==================== API FUNCTIONS ====================
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        updateStats(data);
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

function updateStats(data) {
    document.getElementById('totalAlerts').textContent = data.total_alerts || 0;
    document.getElementById('activeCameras').textContent = data.active_cameras || 0;
    document.getElementById('cheatingAlerts').textContent = data.cheating_alerts || 0;
}

function initializeStats() {
    fetchStats();
    setInterval(fetchStats, 10000); // Update every 10 seconds
}

function startUptimeCounter() {
    setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
        const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
        const seconds = (elapsed % 60).toString().padStart(2, '0');
        document.getElementById('uptime').textContent = `${hours}:${minutes}:${seconds}`;
    }, 1000);
}

async function loadHistoricalData() {
    const container = document.getElementById('historyContainer');
    container.innerHTML = '<div class="loading">Loading incidents...</div>';
    
    try {
        const response = await fetch('/api/alerts?limit=50');
        const incidents = await response.json();
        
        container.innerHTML = '';
        
        if (incidents.length === 0) {
            container.innerHTML = `
                <div class="no-alerts">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 3h18v18H3z"></path>
                    </svg>
                    <p>No historical data</p>
                    <p class="text-muted">Incidents will appear here</p>
                </div>
            `;
        } else {
            incidents.forEach(incident => {
                const alertElement = createHistoricalAlertElement(incident);
                container.appendChild(alertElement);
            });
        }
    } catch (error) {
        console.error('Error loading historical data:', error);
        container.innerHTML = '<div class="loading">Error loading data</div>';
    }
}

function createHistoricalAlertElement(incident) {
    const div = document.createElement('div');
    div.className = 'alert-item' + (incident.reviewed_status ? ' reviewed' : '');
    div.dataset.alertId = incident.incident_id;
    div.dataset.behavior = incident.behavior.toLowerCase();
    div.dataset.reviewed = incident.reviewed_status;
    
    const behaviorClass = incident.behavior.toLowerCase().includes('cheating') ? 'danger' : 
                         incident.behavior.toLowerCase().includes('good') ? 'success' : 'warning';
    
    const timestamp = new Date(incident.timestamp);
    const timeString = timestamp.toLocaleString();
    
    div.innerHTML = `
        <div class="alert-header">
            <span class="alert-title">${incident.student_id}</span>
            <span class="alert-badge badge-${behaviorClass}">${incident.behavior}</span>
        </div>
        <div class="alert-details">
            <div class="alert-detail">
                <strong>Time:</strong> ${timeString}
            </div>
            <div class="alert-detail">
                <strong>Confidence:</strong> ${(incident.confidence * 100).toFixed(1)}%
            </div>
            <div class="alert-detail">
                <strong>Camera:</strong> Camera ${incident.camera_id}
            </div>
            <div class="alert-detail">
                <strong>Status:</strong> ${incident.reviewed_status ? 'Reviewed ✓' : 'Pending Review'}
            </div>
        </div>
        <div class="alert-actions">
            ${!incident.reviewed_status ? `
                <button class="btn-small btn-success" onclick="reviewAlert(${incident.incident_id})">
                    Mark Reviewed
                </button>
            ` : ''}
            <button class="btn-small" onclick="viewDetails(${incident.incident_id})">
                View Details
            </button>
        </div>
    `;
    
    return div;
}

async function reviewAlert(incidentId) {
    try {
        const response = await fetch(`/api/alerts/${incidentId}/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Update UI
            const alertElement = document.querySelector(`[data-alert-id="${incidentId}"]`);
            if (alertElement) {
                alertElement.classList.add('reviewed');
                const actions = alertElement.querySelector('.alert-actions');
                const reviewBtn = actions.querySelector('.btn-success');
                if (reviewBtn) {
                    reviewBtn.remove();
                }
                
                // Update status in details
                const statusDetail = alertElement.querySelector('.alert-detail:last-child');
                if (statusDetail) {
                    statusDetail.innerHTML = '<strong>Status:</strong> Reviewed ✓';
                }
            }
            
            // Show success notification
            showNotification('Alert marked as reviewed', 'success');
        }
    } catch (error) {
        console.error('Error reviewing alert:', error);
        showNotification('Failed to review alert', 'error');
    }
}

function viewDetails(incidentId) {
    // Placeholder for viewing detailed information
    showNotification(`Viewing details for incident #${incidentId}`, 'info');
    // In a full implementation, this would open a modal with more details
}

function filterHistory() {
    const behaviorFilter = document.getElementById('filterBehavior').value.toLowerCase();
    const reviewedFilter = document.getElementById('filterReviewed').value;
    
    const alertItems = document.querySelectorAll('#historyContainer .alert-item');
    
    alertItems.forEach(item => {
        const behavior = item.dataset.behavior;
        const reviewed = item.dataset.reviewed;
        
        let showItem = true;
        
        if (behaviorFilter && !behavior.includes(behaviorFilter)) {
            showItem = false;
        }
        
        if (reviewedFilter && reviewed !== reviewedFilter) {
            showItem = false;
        }
        
        item.style.display = showItem ? 'block' : 'none';
    });
}

// ==================== CAMERA MANAGEMENT ====================
function showAddCameraDialog() {
    const cameraId = prompt('Enter Camera ID (number):');
    const source = prompt('Enter Camera Source (0 for webcam, or RTSP URL):');
    
    if (cameraId && source) {
        addCamera(parseInt(cameraId), isNaN(source) ? source : parseInt(source));
    }
}

async function addCamera(cameraId, source) {
    try {
        const response = await fetch('/api/cameras', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                camera_id: cameraId,
                source: source
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Add camera to video grid
            const videoGrid = document.getElementById('videoGrid');
            const cameraDiv = document.createElement('div');
            cameraDiv.className = 'video-container';
            cameraDiv.dataset.camera = cameraId;
            
            cameraDiv.innerHTML = `
                <div class="video-wrapper">
                    <img src="/video_feed/${cameraId}" alt="Camera ${cameraId}" class="video-feed">
                    <div class="video-overlay">
                        <span class="camera-label">Camera ${cameraId}</span>
                        <span class="recording-indicator">● REC</span>
                    </div>
                </div>
            `;
            
            videoGrid.appendChild(cameraDiv);
            showNotification(`Camera ${cameraId} added successfully`, 'success');
            fetchStats();
        } else {
            showNotification('Failed to add camera: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error adding camera:', error);
        showNotification('Failed to add camera', 'error');
    }
}

// ==================== EXPORT FUNCTIONALITY ====================
async function exportHistoricalData() {
    try {
        const response = await fetch('/api/alerts?limit=1000');
        const incidents = await response.json();
        
        // Convert to CSV
        const headers = ['Incident ID', 'Timestamp', 'Student ID', 'Behavior', 'Confidence', 'Camera ID', 'Reviewed'];
        const rows = incidents.map(inc => [
            inc.incident_id,
            inc.timestamp,
            inc.student_id,
            inc.behavior,
            (inc.confidence * 100).toFixed(1) + '%',
            inc.camera_id,
            inc.reviewed_status ? 'Yes' : 'No'
        ]);
        
        let csv = headers.join(',') + '\n';
        rows.forEach(row => {
            csv += row.map(cell => `"${cell}"`).join(',') + '\n';
        });
        
        // Download CSV
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `incidents_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification('Data exported successfully', 'success');
    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Failed to export data', 'error');
    }
}

// ==================== UTILITY FUNCTIONS ====================
function showNotification(message, type = 'info') {
    const colors = {
        success: 'linear-gradient(135deg, #10b981, #059669)',
        error: 'linear-gradient(135deg, #ef4444, #dc2626)',
        info: 'linear-gradient(135deg, #3b82f6, #2563eb)',
        warning: 'linear-gradient(135deg, #f59e0b, #d97706)'
    };
    
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: ${colors[type]};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        z-index: 1000;
        animation: slideInRight 0.3s ease-out;
        max-width: 350px;
    `;
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add animation keyframes to document
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
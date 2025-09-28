// Trust-Minimized AI Agent Marketplace Dashboard JavaScript

class MarketplaceDashboard {
    constructor() {
        this.ws = null;
        this.currentJobId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }

    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.loadInitialData();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = (event) => {
                console.log('WebSocket connected');
                this.updateConnectionStatus('connected');
                this.reconnectAttempts = 0;
                this.addActivityMessage('Connected to marketplace', 'success');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket closed');
                this.updateConnectionStatus('disconnected');
                this.scheduleReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('disconnected');
            };

        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateConnectionStatus('disconnected');
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
            
            this.updateConnectionStatus('connecting');
            setTimeout(() => {
                console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
                this.connectWebSocket();
            }, delay);
        } else {
            this.addActivityMessage('Connection failed after multiple attempts', 'error');
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'job_update':
                this.handleJobUpdate(data);
                break;
            case 'error':
                this.addActivityMessage(data.message, 'error');
                break;
            case 'connected':
                this.addActivityMessage(data.message, 'success');
                break;
            case 'heartbeat':
                // Keep connection alive
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    handleJobUpdate(data) {
        this.currentJobId = data.job_id;
        
        // Show current job card if hidden
        const jobCard = document.getElementById('currentJobCard');
        if (jobCard.style.display === 'none') {
            jobCard.style.display = 'block';
            jobCard.classList.add('fade-in');
        }

        // Update job ID and status
        document.getElementById('jobId').textContent = `Job ID: ${data.job_id.substring(0, 12)}...`;
        document.getElementById('jobStatus').textContent = data.status;
        document.getElementById('jobStatus').className = `badge status-${data.status.toLowerCase()}`;

        // Update progress bar
        const progressBar = document.getElementById('progressBar');
        switch (data.status) {
            case 'REQUESTED':
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
                progressBar.style.width = '10%';
                break;
            case 'QUOTED':
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated step-quote';
                progressBar.style.width = '20%';
                break;
            case 'ACCEPTED':
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated step-accept';
                progressBar.style.width = '40%';
                break;
            case 'IN_PROGRESS':
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated step-execute';
                progressBar.style.width = '60%';
                break;
            case 'COMPLETED':
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated step-verify';
                progressBar.style.width = '80%';
                break;
            case 'VERIFIED':
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated step-complete';
                progressBar.style.width = '90%';
                break;
            case 'PAID':
                progressBar.className = 'progress-bar step-complete';
                progressBar.style.width = '100%';
                break;
            case 'FAILED':
                progressBar.className = 'progress-bar bg-danger';
                progressBar.style.width = '100%';
                break;
        }

        // Update current step
        document.getElementById('currentStep').textContent = data.message;

        // Show issue link if available
        if (data.issue_url) {
            const issueLink = document.getElementById('issueLink');
            issueLink.style.display = 'block';
            issueLink.querySelector('a').href = data.issue_url;
        }

        // Add to activity feed
        let activityClass = 'info';
        if (data.status === 'FAILED') {
            activityClass = 'error';
        } else if (data.status === 'PAID' || data.status === 'VERIFIED') {
            activityClass = 'success';
        } else if (data.status === 'IN_PROGRESS') {
            activityClass = 'warning';
        }

        this.addActivityMessage(data.message, activityClass);

        // If job is final, update the jobs table
        if (data.final || data.status === 'PAID' || data.status === 'FAILED') {
            setTimeout(() => {
                this.refreshJobsTable();
            }, 1000);
        }
    }

    addActivityMessage(message, type = 'info') {
        const feed = document.getElementById('activityFeed');
        const timestamp = new Date().toLocaleTimeString();
        
        const activityItem = document.createElement('div');
        activityItem.className = `activity-item ${type} slide-in`;
        
        let icon = 'fas fa-info-circle';
        switch (type) {
            case 'success':
                icon = 'fas fa-check-circle text-success';
                break;
            case 'error':
                icon = 'fas fa-exclamation-circle text-danger';
                break;
            case 'warning':
                icon = 'fas fa-exclamation-triangle text-warning';
                break;
        }

        activityItem.innerHTML = `
            <div class="activity-time">${timestamp}</div>
            <div class="activity-message">
                <i class="${icon} me-2"></i>
                ${message}
            </div>
        `;

        // Insert at the top
        feed.insertBefore(activityItem, feed.firstChild);

        // Keep only last 10 items
        while (feed.children.length > 10) {
            feed.removeChild(feed.lastChild);
        }

        // Auto-scroll to top
        feed.scrollTop = 0;
    }

    updateConnectionStatus(status) {
        const statusEl = document.getElementById('connectionStatus');
        statusEl.className = `badge ${status}`;
        
        switch (status) {
            case 'connected':
                statusEl.textContent = 'Connected';
                break;
            case 'connecting':
                statusEl.textContent = 'Connecting...';
                break;
            case 'disconnected':
                statusEl.textContent = 'Disconnected';
                break;
        }
    }

    setupEventListeners() {
        // Form submission
        const form = document.getElementById('createIssueForm');
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitCreateIssue();
        });

        // Heartbeat to keep connection alive
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({type: 'heartbeat'}));
            }
        }, 30000);
    }

    async submitCreateIssue() {
        const form = document.getElementById('createIssueForm');
        const formData = new FormData(form);
        const submitBtn = document.getElementById('createBtn');

        // Show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Creating...';
        document.body.classList.add('loading');

        try {
            const response = await fetch('/create-issue', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                this.addActivityMessage(`Job ${result.job_id} submitted successfully`, 'success');
                form.reset();
                form.elements.labels.value = 'innovationlab,hackathon,demo';
            } else {
                throw new Error(result.detail || 'Failed to create issue');
            }

        } catch (error) {
            console.error('Error creating issue:', error);
            this.addActivityMessage(`Error: ${error.message}`, 'error');
        } finally {
            // Reset loading state
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Issue';
            document.body.classList.remove('loading');
        }
    }

    async loadInitialData() {
        try {
            // Load agent status
            const agentResponse = await fetch('/agent-status');
            const agentStatus = await agentResponse.json();
            
            // Update system status (this could be expanded)
            console.log('Agent status:', agentStatus);
            
            // Load recent jobs
            await this.refreshJobsTable();
            
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }

    async refreshJobsTable() {
        try {
            const response = await fetch('/jobs');
            const data = await response.json();
            
            if (data.jobs) {
                const tbody = document.querySelector('#jobsTable tbody');
                tbody.innerHTML = '';
                
                data.jobs.forEach(job => {
                    const row = document.createElement('tr');
                    row.classList.add('fade-in');
                    
                    const createdTime = job.created_at ? 
                        new Date(job.created_at).toLocaleTimeString() : 'N/A';
                    
                    row.innerHTML = `
                        <td><code>${job.job_id.substring(job.job_id.length - 8)}</code></td>
                        <td>${job.title.substring(0, 30)}${job.title.length > 30 ? '...' : ''}</td>
                        <td><span class="badge status-${job.status.toLowerCase()}">${job.status}</span></td>
                        <td>${createdTime}</td>
                        <td>
                            <button class="btn btn-sm btn-outline-info" onclick="dashboard.showJobDetails('${job.job_id}')">
                                <i class="fas fa-eye"></i>
                            </button>
                        </td>
                    `;
                    
                    tbody.appendChild(row);
                });
            }
            
        } catch (error) {
            console.error('Error refreshing jobs table:', error);
        }
    }

    showJobDetails(jobId) {
        // This could open a modal with detailed job information
        this.addActivityMessage(`Viewing details for job ${jobId.substring(0, 8)}...`, 'info');
        console.log('Show job details for:', jobId);
    }
}

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new MarketplaceDashboard();
});

// Global functions
window.showJobDetails = function(jobId) {
    if (dashboard) {
        dashboard.showJobDetails(jobId);
    }
};
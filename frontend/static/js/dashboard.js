// Trust-Minimized AI Agent Marketplace Dashboard JavaScript

class MarketplaceDashboard {
    constructor() {
        this.ws = null;
        this.currentJobId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.toolAgents = {};
        
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
        console.log('WebSocket message received:', data);
        switch (data.type) {
            case 'job_update':
                this.handleJobUpdate(data);
                // Check if this event has balance update
                if (data.extra && data.extra.balance !== undefined) {
                    console.log('Balance from job_update:', data.extra.balance);
                    this.updateBalance({balance: data.extra.balance});
                }
                break;
            case 'agent_update':
                this.handleAgentUpdate(data);
                break;
            case 'balance_update':
                console.log('Balance update event received:', data);
                // Handle balance updates from periodic checks
                if (data.extra && data.extra.balance !== undefined) {
                    console.log('Updating balance from extra:', data.extra.balance);
                    this.updateBalance({balance: data.extra.balance});
                } else if (data.balance !== undefined) {
                    console.log('Updating balance directly:', data.balance);
                    this.updateBalance({balance: data.balance});
                }
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
            case 'BONDED':
                progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated step-accept';
                progressBar.style.width = '50%';
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
        const sourcePrefix = data.source ? `[${data.source.toUpperCase()}] ` : '';
        document.getElementById('currentStep').textContent = sourcePrefix + data.message;

        // Show action link if available (for issues or translations)
        // Commented out - action link removed from UI
        /*
        if (data.issue_url) {
            const actionLink = document.getElementById('actionLink');
            if (actionLink) {
                actionLink.style.display = 'block';
                const actionButton = actionLink.querySelector('a');
                if (actionButton) {
                    actionButton.href = data.issue_url;
                    const actionText = document.getElementById('actionText');
                    // Customize button based on task type
                    if (data.issue_url.includes('github.com')) {
                        actionButton.innerHTML = '<i class="fab fa-github me-1"></i>View GitHub Issue';
                    } else {
                        actionButton.innerHTML = '<i class="fas fa-external-link-alt me-1"></i>View Result';
                    }
                }
            }
        }
        */

        // Add to activity feed
        let activityClass = 'info';
        if (data.status === 'FAILED') {
            activityClass = 'error';
        } else if (data.status === 'PAID' || data.status === 'VERIFIED') {
            activityClass = 'success';
        } else if (data.status === 'IN_PROGRESS' || data.status === 'BONDED' || data.status === 'ACCEPTED') {
            activityClass = 'warning';
        }

        let msg = (data.source ? `[${data.source}] ` : '') + data.message;
        if (data.tx_hash) {
            msg += ` (tx: ${String(data.tx_hash).substring(0, 12)}...)`;
        }
        this.addActivityMessage(msg, activityClass);

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
        // Create Issue form
        const form = document.getElementById('createIssueForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitCreateIssue();
            });
        }
        // Translate form
        const tform = document.getElementById('translateForm');
        if (tform) {
            tform.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitTranslate();
            });
        }
        // Ask Client form
        const aform = document.getElementById('askForm');
        if (aform) {
            aform.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitAskClient();
            });
        }

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

            let result = null;
            let text = '';
            try {
                result = await response.json();
            } catch (e) {
                try { text = await response.text(); } catch (_) {}
            }

            if (response.ok) {
                this.addActivityMessage(`Create issue request submitted to client`, 'success');
                form.reset();
                form.elements.labels.value = 'innovationlab,hackathon,demo';
            } else {
                const msg = (result && (result.detail || result.message)) || text || 'Failed to create issue';
                throw new Error(msg);
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

    async submitTranslate() {
        const form = document.getElementById('translateForm');
        const formData = new FormData(form);
        const submitBtn = document.getElementById('translateBtn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Translating...';
        document.body.classList.add('loading');
        try {
            const response = await fetch('/translate', { method: 'POST', body: formData });
            let result = null; let text = '';
            try {
                result = await response.json();
            } catch (e) {
                try { text = await response.text(); } catch (_) {}
            }
            if (response.ok) {
                this.addActivityMessage(`Translate request submitted`, 'success');
            } else {
                const msg = (result && (result.detail || result.message)) || text || 'Failed to submit translate request';
                throw new Error(msg);
            }
        } catch (error) {
            console.error('Error translating:', error);
            this.addActivityMessage(`Error: ${error.message}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Translate';
            document.body.classList.remove('loading');
        }
    }

    async submitAskClient() {
        const form = document.getElementById('askForm');
        const formData = new FormData(form);
        const submitBtn = document.getElementById('askBtn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Submitting...';
        document.body.classList.add('loading');
        try {
            const response = await fetch('/ask-client', { method: 'POST', body: formData });
            let result = null; let text = '';
            try {
                result = await response.json();
            } catch (e) {
                try { text = await response.text(); } catch (_) {}
            }
            if (response.ok) {
                this.addActivityMessage(`Ask submitted to client`, 'success');
                form.reset();
            } else {
                const msg = (result && (result.detail || result.message)) || text || 'Failed to submit ask';
                throw new Error(msg);
            }
        } catch (error) {
            console.error('Error asking client:', error);
            this.addActivityMessage(`Error: ${error.message}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-magic me-2"></i>Ask Client';
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
    handleAgentUpdate(data) {
        const agent = data.agent || {};
        const addr = agent.address || agent.wallet_address || 'unknown';
        if (!addr) return;
        this.toolAgents[addr] = agent;
        this.renderToolAgents();
        
        // Update balance if it's the client agent (multiple possible data structures)
        if (data.agent && data.agent.balance_atestfet !== undefined) {
            this.updateBalance({balance: data.agent.balance_atestfet});
        } else if (data.agent_info && data.agent_info.balance_atestfet !== undefined) {
            this.updateBalance({balance: data.agent_info.balance_atestfet});
        } else if (data.extra && data.extra.agent_info && data.extra.agent_info.balance_atestfet !== undefined) {
            this.updateBalance({balance: data.extra.agent_info.balance_atestfet});
        }
    }
    
    updateBalance(data) {
        console.log('updateBalance called with:', data);
        const balanceEl = document.getElementById('walletBalance');
        console.log('Balance element found:', balanceEl);
        if (balanceEl && data.balance !== undefined) {
            const balanceInFET = (data.balance / 1e18).toFixed(2);
            console.log('Setting balance to:', balanceInFET, 'testFET');
            balanceEl.textContent = `${balanceInFET} testFET`;
            
            // Color code based on balance
            if (data.balance < 1e18) {  // Less than 1 FET
                balanceEl.className = 'text-danger';
            } else if (data.balance < 5e18) {  // Less than 5 FET
                balanceEl.className = 'text-warning';
            } else {
                balanceEl.className = 'text-success';
            }
        } else {
            console.log('Balance update failed - element:', balanceEl, 'balance:', data.balance);
        }
    }

    renderToolAgents() {
        const listEl = document.getElementById('toolAgentsList');
        const countEl = document.getElementById('toolAgentCount');
        if (!listEl) return;
        const agents = Object.values(this.toolAgents);
        if (countEl) countEl.textContent = agents.length;
        listEl.innerHTML = '';
        agents.forEach(a => {
            const div = document.createElement('div');
            div.className = 'mb-2 p-2 border rounded';
            const caps = (a.capabilities || []).join(', ');
            const name = a.name || a.address?.substring(0, 12) + '...';
            const price = a.price ? `${a.price / 1e18} testFET` : '-';
            div.innerHTML = `
                <div><strong>${name}</strong></div>
                <div><small>Address: <code>${a.address || '-'}</code></small></div>
                <div><small>Capabilities: ${caps || '-'}</small></div>
                <div><small>Price: ${price}, Bond: ${a.bond ? a.bond / 1e18 : '-'} testFET</small></div>
            `;
            listEl.appendChild(div);
        });
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
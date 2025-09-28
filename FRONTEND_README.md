# 🌐 Trust-Minimized Marketplace - Demo Frontend

An interactive web dashboard that shows the complete trust-minimized workflow in real-time.

## 🎯 Overview

This frontend demonstrates the **Trust-Minimized AI Agent Marketplace** with live job tracking, real-time agent interactions, and visual verification of the complete workflow:

1. **Quote Phase** - Client requests service from tool agent
2. **Execution Phase** - Tool agent creates GitHub issue  
3. **Verification Phase** - Independent API verification
4. **Payment Phase** - FET tokens transferred only after verification

## 🚀 Quick Start

### Start the Demo Frontend
```bash
# Make sure you're in the project directory
cd mhacks25

# Activate virtual environment
source venv/bin/activate

# Start the frontend server
python run_frontend.py
```

### Open in Browser
Navigate to: **http://localhost:8000**

## 📱 Dashboard Features

### 🔄 Real-Time Updates
- **WebSocket Connection**: Live updates with automatic reconnection
- **Activity Feed**: Real-time job status updates with timestamps
- **Progress Bar**: Visual progress through workflow stages
- **Status Indicators**: Live agent and system status

### 🎮 Interactive Controls
- **Create Issue Form**: Submit GitHub issue creation jobs
- **Job Tracking**: Monitor current job progress
- **Job History**: View recent marketplace transactions
- **System Status**: Monitor agent availability

### 📊 Live Visualization
- **Workflow Progress**: 5-stage progress bar (Quote → Accept → Execute → Verify → Pay)
- **Status Badges**: Color-coded job status indicators
- **Activity Timeline**: Chronological feed of all marketplace events
- **GitHub Integration**: Direct links to created issues

## 🎪 Perfect for Demonstrations

### For Judges/Audiences:
1. **Open the dashboard** - Shows professional marketplace interface
2. **Submit a job** - Fill in issue title and click "Create Issue"
3. **Watch real-time progress** - See each step of the workflow
4. **View created issue** - Click link to see actual GitHub issue
5. **Inspect verification** - Shows independent API verification

### Demo Flow:
```
User Input → Quote Request → Tool Execution → Issue Creation → 
API Verification → Payment Simulation → Final Status
```

## 🔧 Technical Features

### Backend (FastAPI)
- **WebSocket Support**: Real-time bidirectional communication
- **RESTful APIs**: Job management and status endpoints  
- **State Management**: SQLite job tracking
- **GitHub Integration**: Live API calls for issue creation
- **Error Handling**: Comprehensive error reporting

### Frontend (Modern Web)
- **Bootstrap 5**: Responsive, mobile-friendly design
- **WebSocket Client**: Auto-reconnecting real-time updates
- **Font Awesome**: Professional icons and indicators
- **CSS Animations**: Smooth transitions and progress indicators
- **Fetch API**: Modern asynchronous HTTP requests

## 📊 Dashboard Sections

### 1. System Status Card
- Tool Agent status (Online/Offline)
- Client Agent status (Online/Offline)  
- GitHub API configuration
- Connection indicators with pulse animations

### 2. Create Issue Form
- **Title**: Issue title (required)
- **Body**: Issue description (optional)
- **Labels**: Comma-separated labels (pre-filled with hackathon badges)
- **Submit Button**: Triggers complete workflow

### 3. Live Activity Feed
- **Real-time events** with timestamps
- **Color-coded messages** (success/warning/error)
- **Auto-scrolling** to latest events
- **Connection status** indicator

### 4. Current Job Progress
- **Job ID** with short identifier
- **Progress Bar** showing current workflow stage
- **Current Step** description
- **Issue Link** (appears when job completes)
- **Status Badge** with color coding

### 5. Recent Jobs Table
- **Job History** with status badges
- **Quick Actions** for job details
- **Timestamps** for job creation
- **Truncated Titles** for readability

## 🎨 UI/UX Design

### Color Scheme
- **Primary**: `#3D8BD3` (Innovation Lab blue)
- **Secondary**: `#5F43F1` (Hackathon purple)
- **Success**: Green for completed jobs
- **Warning**: Yellow for in-progress jobs
- **Danger**: Red for failed jobs

### Animations
- **Pulse**: Status indicators and connection badges
- **Slide-in**: New activity feed items
- **Fade-in**: New table rows and cards
- **Progress**: Animated progress bars
- **Spin**: Loading button indicators

### Responsive Design
- **Mobile-friendly**: Works on phones and tablets
- **Adaptive Layout**: Adjusts to screen size
- **Touch-friendly**: Large clickable areas
- **Readable Fonts**: Clear typography

## 🔗 Integration with Agents

### Workflow Integration
The frontend simulates the complete agent workflow:

1. **Form Submission** → Creates QuoteRequest
2. **Quote Phase** → Shows quote acceptance
3. **Execution** → Calls real GitHub API
4. **Verification** → Independent API verification
5. **Payment** → Simulates FET token transfer

### Real GitHub Issues
- Creates **actual GitHub issues** in test repository
- Issues include **hackathon badges** and demo information
- **Verifiable results** through GitHub API
- **Direct links** to created issues for judges

## 🏆 Hackathon Impact

### For Judges
- **Visual Impact**: Professional, polished interface
- **Real Functionality**: Actually creates GitHub issues
- **Complete Workflow**: Shows entire trust-minimized process
- **Live Demonstration**: No pre-recorded content

### Technical Merit
- **Full Stack**: Frontend, backend, database, APIs
- **Real-time Updates**: WebSocket implementation
- **Error Handling**: Robust error management
- **State Management**: Persistent job tracking
- **API Integration**: Live GitHub API usage

### Innovation Showcase
- **Trust-Minimized**: Payment only after verification
- **Agent Simulation**: Realistic agent behavior
- **Blockchain Ready**: Designed for FET token integration
- **Production Quality**: Professional UI/UX

## 🚀 Running the Full Demo

### Complete Setup
```bash
# Terminal 1 - Frontend
python run_frontend.py

# Terminal 2 - Tool Agent (optional)
python run_tool_agent.py  

# Terminal 3 - Client Agent (optional)
python run_client_agent.py
```

### Demo Sequence
1. **Open Dashboard** → http://localhost:8000
2. **Show System Status** → All components online
3. **Create GitHub Issue** → Fill form and submit
4. **Watch Progress** → Real-time workflow updates
5. **View Created Issue** → Click GitHub link
6. **Show Job History** → Previous transactions

## 🎯 Key Selling Points

- ✅ **Real GitHub Integration** - Creates actual issues
- ✅ **Trust-Minimized Workflow** - Payment after verification  
- ✅ **Real-time Updates** - WebSocket live updates
- ✅ **Professional UI** - Production-quality interface
- ✅ **Complete Workflow** - End-to-end demonstration
- ✅ **Hackathon Compliant** - Innovation lab badges
- ✅ **Verifiable Results** - Judges can verify GitHub issues
- ✅ **Error Handling** - Robust failure management

---

**Perfect for hackathon demonstrations and judge evaluations!** 🏆
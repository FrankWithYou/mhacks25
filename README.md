# Trust-Minimized AI Agent Marketplace

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

A decentralized marketplace where client agents pay tool agents to perform real tasks with independent verification and payment only upon successful completion.

## 🎯 Project Overview

This project implements a **trust-minimized marketplace** where:
- **Client agents** request services from tool agents
- **Tool agents** provide quotes and execute tasks (e.g., create GitHub issues)
- **Payment only occurs** after independent verification by the client
- All agents are registered on **Agentverse** with **ASI:One** integration

### Example Workflow
1. Client requests: "Create a GitHub issue in repo X and return the URL"
2. Tool provides quote: "I'll do it for 5 testFET with 1 testFET bond"
3. Client accepts and sends task details
4. Tool creates GitHub issue and returns signed receipt
5. Client independently verifies the issue exists via GitHub API
6. Client sends payment only if verification passes ✅

## 🏗️ Architecture

```
┌─────────────────┐    QuoteRequest     ┌─────────────────┐
│                 │ ──────────────────> │                 │
│  Client Agent   │                     │   Tool Agent    │
│   (Buyer)       │ <─────────────────  │   (Seller)      │
│                 │   QuoteResponse     │                 │
└─────────────────┘                     └─────────────────┘
         │                                        │
         │ PerformRequest                         │
         │ ──────────────────────────────────────>│
         │                                        │
         │                                        │ GitHub API
         │                                        │ ────────────> [Issue Created]
         │                    Receipt             │
         │ <──────────────────────────────────────│
         │                                        │
         │ Verification (GitHub API)              │
         │ ────────────> [Check Issue]            │
         │                                        │
         │ Payment (FET tokens)                   │
         │ ──────────────────────────────────────>│
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- GitHub account and personal access token
- GitHub repository for testing

### 1. Setup Environment

```bash
# Clone and setup
git clone <repo-url>
cd mhacks25
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# GitHub API configuration (REQUIRED)
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=your-username/your-test-repo

# ASI:One API Key (provided)
ASI_ONE_API_KEY=sk_5278f9069cb144f18b1fcec8204c647d0da8583ead154fe9b46adc9caf0ec680

# Other settings (optional)
DEFAULT_BOND_AMOUNT=1000000000000000000   # 1 testFET
DEFAULT_TASK_PRICE=5000000000000000000    # 5 testFET
```

### 3. Run Demo

```bash
# Quick demo of the workflow
python demo.py
```

This will:
- Create a real GitHub issue in your repo
- Show the complete quote→perform→verify→pay workflow
- Demonstrate independent verification

### 4. Run Agents

**Terminal 1 - Tool Agent:**
```bash
python run_tool_agent.py
```

**Terminal 2 - Client Agent:**
```bash
python run_client_agent.py
```

Both agents will:
- Register on Agentverse (with `publish_manifest=True`)
- Enable chat protocol for ASI:One discovery
- Show their addresses for direct communication

## 🎪 Chat Integration (ASI:One)

Both agents support the chat protocol and can be discovered through ASI:One:

**Tool Agent Chat Commands:**
- `"create issue: Your Title Here"` - Request GitHub issue creation
- Natural language requests work too!

**Client Agent Chat Commands:**
- `"create issue: Your Title Here"` - Request service from tool agents
- `"status"` - Check latest job status  
- `"balance"` - Check FET token balance

## 🔧 Technical Features

### Trust-Minimized Design
- **No blind trust**: Client never pays until verification passes
- **Cryptographic signatures**: All receipts are signed by tool agents
- **Independent verification**: Client checks GitHub API directly
- **Bonding system**: Tool agents post bonds to discourage fraud

### Fetch.ai Stack Integration
- **uAgents**: Core agent framework with message passing
- **Agentverse**: Agent registration and discovery
- **ASI:One**: Chat protocol for natural language interaction
- **FET Tokens**: Native payment rail with testnet support
- **CosmPy**: Blockchain integration for payments

### Message Protocol
```python
# 1. Quote Phase
QuoteRequest → QuoteResponse

# 2. Execution Phase  
PerformRequest → Receipt

# 3. Verification & Payment
VerificationResult → PaymentNotification
```

## 📁 Project Structure

```
mhacks25/
├── src/
│   ├── models/           # Pydantic message schemas
│   │   └── messages.py
│   ├── utils/            # Core utilities
│   │   ├── github_api.py     # GitHub integration
│   │   ├── crypto.py         # Signatures & hashing
│   │   ├── payment.py        # FET token handling
│   │   ├── verifier.py       # Independent verification
│   │   └── state_manager.py  # SQLite job tracking
│   ├── tool/             # Tool agent implementation
│   │   └── github_tool_agent.py
│   └── client/           # Client agent implementation
│       └── marketplace_client_agent.py
├── run_tool_agent.py     # Tool agent entry point
├── run_client_agent.py   # Client agent entry point
├── demo.py              # Workflow demonstration
└── README.md
```

## 🏆 Hackathon Alignment

### 🥇 Best Use of Fetch.ai ($1250)
- ✅ Agents registered on Agentverse
- ✅ Chat protocol enabled  
- ✅ ASI:One as reasoning engine
- ✅ Full end-to-end tech stack integration

### 🥈 Best Deployment on Agentverse ($750)
- ✅ Multiple useful, discoverable agents
- ✅ Well-documented with clear descriptions
- ✅ Easy to find and use via chat interface

### 🥉 Best Use of ASI:One ($500)  
- ✅ ASI:One powers agent interactions
- ✅ Natural language task requests
- ✅ Smart routing between agents
- ✅ Effective decision-making workflows

## 🧪 Testing Scenarios

The system handles multiple test cases:

### ✅ Success Path
1. Tool creates valid GitHub issue
2. Client verifies issue exists with correct title
3. Payment processed automatically

### ❌ Failure Cases
- **Tool lies**: Returns fake URL → verification fails → no payment
- **Timeout**: Tool doesn't respond → job canceled  
- **Invalid receipt**: Signature verification fails → no payment

### 🔁 Security Features
- Terms hash prevents quote manipulation
- Job IDs prevent replay attacks
- Independent verification prevents fraud
- Bonding discourages bad actors

## 📊 Demo Output Example

```
🎯 TRUST-MINIMIZED AI AGENT MARKETPLACE DEMO
===============================================

✅ GitHub configuration found
📁 Target repository: your-username/test-repo

1️⃣  QUOTE PHASE
   📤 QuoteRequest created:
      Task: CREATE_GITHUB_ISSUE
      Price: 5000000000000000000 atestfet (5.0 testFET)

2️⃣  EXECUTION PHASE  
   🔨 Tool agent executing task...
   ✅ GitHub issue created successfully!
      Issue URL: https://github.com/your-username/test-repo/issues/123

3️⃣  VERIFICATION PHASE
   🔍 Client agent verifying task completion...
   ✅ Verification passed!

4️⃣  PAYMENT PHASE
   💰 Client sends 5.0 testFET to tool agent
   
🎉 DEMO COMPLETE!
```

## 🔮 Future Extensions

- **Multi-task support**: Translation, weather, etc.
- **Escrow contracts**: On-chain payment guarantees  
- **Reputation system**: Agent performance tracking
- **Discovery protocol**: Dynamic tool agent finding
- **Advanced verification**: ML-powered result checking

## 🤝 Contributing

This project was built for the M-Hacks hackathon. The core workflow demonstrates trust-minimized transactions between AI agents with real-world task execution and verification.

## 📜 License

MIT License - see LICENSE file for details.

---

**Built with ❤️ for M-Hacks 2025 using the Fetch.ai ecosystem**
mhacks 2025 !!!!

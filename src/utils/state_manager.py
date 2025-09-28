"""
State management for the marketplace agents.
Uses SQLite for persistent job tracking and status management.
"""

import sqlite3
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from models.messages import JobRecord, JobStatus, TaskType, Receipt, VerificationResult

logger = logging.getLogger(__name__)


class StateManager:
    """SQLite-based state manager for agent job tracking"""
    
    def __init__(self, db_path: str = "marketplace.db"):
        """
        Initialize state manager with SQLite database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    client_address TEXT,
                    tool_address TEXT,
                    price INTEGER,
                    bond_amount INTEGER,
                    quote_timestamp TEXT,
                    perform_timestamp TEXT,
                    completion_timestamp TEXT,
                    verification_timestamp TEXT,
                    payment_timestamp TEXT,
                    receipt TEXT,
                    verification_result TEXT,
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_client ON jobs(client_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tool ON jobs(tool_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")
            
            conn.commit()
    
    def create_job(self, job_record: JobRecord) -> bool:
        """
        Create a new job record
        
        Args:
            job_record: Job record to create
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO jobs (
                        job_id, task, payload, status, client_address, tool_address,
                        price, bond_amount, quote_timestamp, perform_timestamp,
                        completion_timestamp, verification_timestamp, payment_timestamp,
                        receipt, verification_result, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_record.job_id,
                    job_record.task.value,
                    json.dumps(job_record.payload),
                    job_record.status.value,
                    job_record.client_address,
                    job_record.tool_address,
                    job_record.price,
                    job_record.bond_amount,
                    job_record.quote_timestamp.isoformat() if job_record.quote_timestamp else None,
                    job_record.perform_timestamp.isoformat() if job_record.perform_timestamp else None,
                    job_record.completion_timestamp.isoformat() if job_record.completion_timestamp else None,
                    job_record.verification_timestamp.isoformat() if job_record.verification_timestamp else None,
                    job_record.payment_timestamp.isoformat() if job_record.payment_timestamp else None,
                    job_record.receipt.model_dump_json() if job_record.receipt else None,
                    job_record.verification_result.model_dump_json() if job_record.verification_result else None,
                    job_record.notes
                ))
                conn.commit()
                logger.info(f"Created job record: {job_record.job_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create job record {job_record.job_id}: {e}")
            return False
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a job record
        
        Args:
            job_id: Job identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not updates:
                return True
                
            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field in ['receipt', 'verification_result'] and value is not None:
                    # Serialize pydantic models
                    if hasattr(value, 'model_dump_json'):
                        value = value.model_dump_json()
                    else:
                        value = json.dumps(value)
                elif field == 'payload' and isinstance(value, dict):
                    value = json.dumps(value)
                elif field == 'status' and hasattr(value, 'value'):
                    value = value.value
                elif field == 'task' and hasattr(value, 'value'):
                    value = value.value
                elif isinstance(value, datetime):
                    value = value.isoformat()
                
                set_clauses.append(f"{field} = ?")
                values.append(value)
            
            # Always update the updated_at timestamp
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            
            query = f"UPDATE jobs SET {', '.join(set_clauses)} WHERE job_id = ?"
            values.append(job_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, values)
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated job {job_id} with {len(updates)} fields")
                    return True
                else:
                    logger.warning(f"No job found with ID {job_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """
        Retrieve a job record by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            JobRecord if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_job_record(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve job {job_id}: {e}")
            return None
    
    def get_jobs_by_status(self, status: JobStatus, agent_address: str = None) -> List[JobRecord]:
        """
        Retrieve jobs by status, optionally filtered by agent address
        
        Args:
            status: Job status to filter by
            agent_address: Optional agent address (client or tool)
            
        Returns:
            List of matching job records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if agent_address:
                    query = """
                        SELECT * FROM jobs 
                        WHERE status = ? AND (client_address = ? OR tool_address = ?)
                        ORDER BY created_at DESC
                    """
                    cursor = conn.execute(query, (status.value, agent_address, agent_address))
                else:
                    cursor = conn.execute(
                        "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC",
                        (status.value,)
                    )
                
                return [self._row_to_job_record(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to retrieve jobs by status {status}: {e}")
            return []
    
    def get_jobs_by_agent(self, agent_address: str, role: str = "any") -> List[JobRecord]:
        """
        Retrieve jobs for a specific agent
        
        Args:
            agent_address: Agent address
            role: Filter by role ("client", "tool", or "any")
            
        Returns:
            List of job records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if role == "client":
                    query = "SELECT * FROM jobs WHERE client_address = ? ORDER BY created_at DESC"
                elif role == "tool":
                    query = "SELECT * FROM jobs WHERE tool_address = ? ORDER BY created_at DESC"
                else:
                    query = """
                        SELECT * FROM jobs 
                        WHERE client_address = ? OR tool_address = ?
                        ORDER BY created_at DESC
                    """
                
                if role == "any":
                    cursor = conn.execute(query, (agent_address, agent_address))
                else:
                    cursor = conn.execute(query, (agent_address,))
                
                return [self._row_to_job_record(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to retrieve jobs for agent {agent_address}: {e}")
            return []
    
    def _row_to_job_record(self, row: sqlite3.Row) -> JobRecord:
        """Convert SQLite row to JobRecord"""
        receipt = None
        if row['receipt']:
            receipt_data = json.loads(row['receipt'])
            receipt = Receipt(**receipt_data)
        
        verification_result = None
        if row['verification_result']:
            verification_data = json.loads(row['verification_result'])
            verification_result = VerificationResult(**verification_data)
        
        return JobRecord(
            job_id=row['job_id'],
            task=TaskType(row['task']),
            payload=json.loads(row['payload']),
            status=JobStatus(row['status']),
            client_address=row['client_address'],
            tool_address=row['tool_address'],
            price=row['price'],
            bond_amount=row['bond_amount'],
            quote_timestamp=datetime.fromisoformat(row['quote_timestamp']) if row['quote_timestamp'] else None,
            perform_timestamp=datetime.fromisoformat(row['perform_timestamp']) if row['perform_timestamp'] else None,
            completion_timestamp=datetime.fromisoformat(row['completion_timestamp']) if row['completion_timestamp'] else None,
            verification_timestamp=datetime.fromisoformat(row['verification_timestamp']) if row['verification_timestamp'] else None,
            payment_timestamp=datetime.fromisoformat(row['payment_timestamp']) if row['payment_timestamp'] else None,
            receipt=receipt,
            verification_result=verification_result,
            notes=row['notes'] or ""
        )
    
    def cleanup_old_jobs(self, days: int = 30) -> int:
        """
        Clean up completed or failed jobs older than specified days
        
        Args:
            days: Number of days to retain jobs
            
        Returns:
            Number of jobs deleted
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM jobs 
                    WHERE (status = 'paid' OR status = 'failed' OR status = 'cancelled')
                    AND created_at < ?
                """, (cutoff_date,))
                conn.commit()
                
                deleted_count = cursor.rowcount
                logger.info(f"Cleaned up {deleted_count} old jobs")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0
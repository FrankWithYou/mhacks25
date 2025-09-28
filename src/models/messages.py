"""
Message schemas for the trust-minimized agent marketplace.
Defines all message types used in the quote/perform/verify/pay flow.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TaskType(str, Enum):
    """Supported task types"""
    CREATE_GITHUB_ISSUE = "create_github_issue"
    TRANSLATE_TEXT = "translate_text"
    GET_WEATHER = "get_weather"


class JobStatus(str, Enum):
    """Job status tracking"""
    REQUESTED = "requested"
    QUOTED = "quoted"
    ACCEPTED = "accepted"
    BONDED = "bonded"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"



class BondAction(str, Enum):
    """Bond workflow actions"""
    POSTED = "posted"
    RETURNED = "returned"

class QuoteRequest(BaseModel):
    """Request for a quote to perform a task"""
    task: TaskType = Field(..., description="The type of task to be performed")
    payload: Dict[str, Any] = Field(..., description="Task-specific parameters")
    client_address: str = Field(..., description="Client agent address for responses")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QuoteResponse(BaseModel):
    """Response with pricing and terms for a task"""
    job_id: str = Field(..., description="Unique identifier for this job")
    price: int = Field(..., description="Price in atestfet (smallest unit)")
    denom: str = Field(default="atestfet", description="Token denomination")
    ttl: int = Field(..., description="Time to live in seconds")
    terms_hash: str = Field(..., description="Hash of the terms for integrity")
    bond_required: int = Field(..., description="Bond amount required in atestfet")
    tool_address: str = Field(..., description="Tool agent address")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PerformRequest(BaseModel):
    """Request to perform the quoted task"""
    job_id: str = Field(..., description="Job ID from the quote")
    payload: Dict[str, Any] = Field(..., description="Task parameters (should match quote)")
    terms_hash: str = Field(..., description="Terms hash for verification")
    client_signature: str = Field(..., description="Client signature for authenticity")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Receipt(BaseModel):
    """Receipt/proof of task completion"""
    job_id: str = Field(..., description="Job identifier")
    output_ref: str = Field(..., description="Reference to the created output (e.g., URL)")
    verifier_url: str = Field(..., description="URL for independent verification")
    verifier_params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for verification")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_signature: str = Field(..., description="Tool's signature over job_id|output_ref|timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BondNotification(BaseModel):
    """Notification related to job bond transfers"""
    job_id: str = Field(..., description="Job identifier")
    tx_hash: str = Field(..., description="Transaction hash of the bond transfer")
    amount: int = Field(..., description="Bond amount in atestfet")
    action: BondAction = Field(..., description="Bond action type (posted or returned)")
    sender: str = Field(..., description="Address that initiated the transfer")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaymentNotification(BaseModel):
    """Notification of job payment"""
    job_id: str = Field(..., description="Job identifier")
    tx_hash: str = Field(..., description="Transaction hash of payment")
    amount: int = Field(..., description="Payment amount in atestfet")
    sender: str = Field(..., description="Address that sent payment")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VerificationResult(BaseModel):
    """Result of client verification"""
    job_id: str = Field(..., description="Job identifier")
    verified: bool = Field(..., description="Whether verification passed")
    details: str = Field(..., description="Human-readable verification details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class JobRecord(BaseModel):
    """Internal job tracking record"""
    job_id: str
    task: TaskType
    payload: Dict[str, Any]
    status: JobStatus
    client_address: Optional[str] = None
    tool_address: Optional[str] = None
    price: Optional[int] = None
    bond_amount: Optional[int] = None
    terms_hash: Optional[str] = None
    bond_tx_hash: Optional[str] = None
    bond_posted_timestamp: Optional[datetime] = None
    bond_return_tx_hash: Optional[str] = None
    bond_return_timestamp: Optional[datetime] = None
    payment_tx_hash: Optional[str] = None
    quote_timestamp: Optional[datetime] = None
    perform_timestamp: Optional[datetime] = None
    completion_timestamp: Optional[datetime] = None
    verification_timestamp: Optional[datetime] = None
    payment_timestamp: Optional[datetime] = None
    receipt: Optional[Receipt] = None
    verification_result: Optional[VerificationResult] = None
    notes: str = ""
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

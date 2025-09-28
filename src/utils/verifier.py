"""
Verification system for the marketplace.
Handles independent verification of task completion before payment.
"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime

from .github_api import GitHubAPI
from .crypto import verify_job_signature
from models.messages import Receipt, VerificationResult, TaskType

logger = logging.getLogger(__name__)


class TaskVerifier:
    """Independent task verification system"""
    
    def __init__(self, github_api: GitHubAPI = None):
        """
        Initialize verifier
        
        Args:
            github_api: GitHub API client for verification
        """
        self.github_api = github_api
    
    async def verify_task_completion(self, receipt: Receipt, task_type: TaskType, 
                                   tool_public_key: str) -> VerificationResult:
        """
        Verify task completion independently
        
        Args:
            receipt: Receipt from tool agent
            task_type: Type of task that was performed
            tool_public_key: Tool agent's public key for signature verification
            
        Returns:
            VerificationResult with verification status and details
        """
        logger.info(f"Verifying task completion for job {receipt.job_id}")
        
        try:
            # Verify tool signature first
            signature_valid = verify_job_signature(
                receipt.job_id,
                receipt.output_ref,
                receipt.timestamp,
                receipt.tool_signature,
                tool_public_key
            )
            
            if not signature_valid:
                return VerificationResult(
                    job_id=receipt.job_id,
                    verified=False,
                    details="Tool signature verification failed",
                    timestamp=datetime.utcnow()
                )
            
            # Perform task-specific verification
            if task_type == TaskType.CREATE_GITHUB_ISSUE:
                return await self._verify_github_issue(receipt)
            elif task_type == TaskType.TRANSLATE_TEXT:
                return await self._verify_translation(receipt)
            elif task_type == TaskType.GET_WEATHER:
                return await self._verify_weather(receipt)
            else:
                return VerificationResult(
                    job_id=receipt.job_id,
                    verified=False,
                    details=f"Unsupported task type for verification: {task_type}",
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error during verification: {e}")
            return VerificationResult(
                job_id=receipt.job_id,
                verified=False,
                details=f"Verification error: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _verify_github_issue(self, receipt: Receipt) -> VerificationResult:
        """Verify GitHub issue creation"""
        if not self.github_api:
            return VerificationResult(
                job_id=receipt.job_id,
                verified=False,
                details="GitHub API not available for verification",
                timestamp=datetime.utcnow()
            )
        
        try:
            # Extract expected parameters
            verifier_params = receipt.verifier_params or {}
            expected_title = verifier_params.get("expected_title", "")
            expected_repo = verifier_params.get("expected_repo", "")
            
            # Use verifier URL (API endpoint) for verification
            verification_result = await self.github_api.verify_issue(
                receipt.verifier_url,
                expected_title,
                None  # We don't verify creator for MVP
            )
            
            # Build detailed verification result
            details = f"GitHub issue verification: {verification_result['details']}"
            
            if verification_result["verified"]:
                details += f"\\nIssue URL: {receipt.output_ref}"
                if "raw_details" in verification_result:
                    raw_details = verification_result["raw_details"]
                    details += f"\\nIssue #{raw_details.get('issue_number', 'unknown')}"
                    details += f"\\nState: {raw_details.get('issue_state', 'unknown')}"
                    details += f"\\nCreated: {raw_details.get('created_at', 'unknown')}"
            
            return VerificationResult(
                job_id=receipt.job_id,
                verified=verification_result["verified"],
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"GitHub issue verification failed: {e}")
            return VerificationResult(
                job_id=receipt.job_id,
                verified=False,
                details=f"GitHub verification error: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _verify_translation(self, receipt: Receipt) -> VerificationResult:
        """Verify text translation (placeholder for future implementation)"""
        # For the MVP, we'll implement basic verification
        # In a production system, this would re-translate and compare results
        
        try:
            # Basic checks - ensure output_ref contains translated text
            output_ref = receipt.output_ref
            
            if not output_ref or len(output_ref.strip()) == 0:
                return VerificationResult(
                    job_id=receipt.job_id,
                    verified=False,
                    details="Translation output is empty",
                    timestamp=datetime.utcnow()
                )
            
            # Check if output seems like translated text (basic heuristic)
            # In production, you'd use language detection and quality metrics
            if len(output_ref) < 5:
                return VerificationResult(
                    job_id=receipt.job_id,
                    verified=False,
                    details="Translation output too short",
                    timestamp=datetime.utcnow()
                )
            
            return VerificationResult(
                job_id=receipt.job_id,
                verified=True,
                details=f"Translation verification passed. Output: {output_ref[:100]}...",
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return VerificationResult(
                job_id=receipt.job_id,
                verified=False,
                details=f"Translation verification error: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _verify_weather(self, receipt: Receipt) -> VerificationResult:
        """Verify weather data (placeholder for future implementation)"""
        # For the MVP, we'll implement basic verification
        # In a production system, this would cross-check with weather APIs
        
        try:
            output_ref = receipt.output_ref
            
            # Basic checks - ensure output contains weather-like data
            if not output_ref:
                return VerificationResult(
                    job_id=receipt.job_id,
                    verified=False,
                    details="Weather output is empty",
                    timestamp=datetime.utcnow()
                )
            
            # Look for weather-related keywords (basic heuristic)
            weather_keywords = ["temperature", "weather", "celsius", "fahrenheit", 
                              "sunny", "cloudy", "rain", "wind", "humidity"]
            
            output_lower = output_ref.lower()
            keyword_found = any(keyword in output_lower for keyword in weather_keywords)
            
            if not keyword_found:
                return VerificationResult(
                    job_id=receipt.job_id,
                    verified=False,
                    details="Output doesn't contain weather-related information",
                    timestamp=datetime.utcnow()
                )
            
            return VerificationResult(
                job_id=receipt.job_id,
                verified=True,
                details=f"Weather verification passed. Data: {output_ref[:100]}...",
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return VerificationResult(
                job_id=receipt.job_id,
                verified=False,
                details=f"Weather verification error: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    @classmethod
    def create_github_verifier(cls) -> 'TaskVerifier':
        """Create a verifier with GitHub API support"""
        try:
            github_api = GitHubAPI.from_env()
            return cls(github_api=github_api)
        except Exception as e:
            logger.warning(f"Could not initialize GitHub API for verification: {e}")
            return cls()
    
    def can_verify_task_type(self, task_type: TaskType) -> bool:
        """Check if verifier can handle a specific task type"""
        if task_type == TaskType.CREATE_GITHUB_ISSUE:
            return self.github_api is not None
        elif task_type in [TaskType.TRANSLATE_TEXT, TaskType.GET_WEATHER]:
            return True  # Basic verification available
        else:
            return False
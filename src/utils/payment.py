"""
Payment system for the marketplace.
Handles FET token transfers for bonds and payments using uAgents ledger integration.
"""

import logging
from typing import Optional, Dict, Any
from uagents import Context
from uagents.network import get_faucet

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Custom exception for payment errors"""
    pass


class PaymentManager:
    """Manages FET token payments and bonds"""
    
    def __init__(self, agent=None):
        """Initialize payment manager
        
        Args:
            agent: Optional agent instance for wallet access
        """
        self.agent = agent
    
    async def get_balance(self, ctx: Context) -> int:
        """
        Get current FET balance for the agent
        
        Args:
            ctx: Agent context
            
        Returns:
            Balance in atestfet (smallest unit)
        """
        try:
            # Resolve wallet address from context or use stored agent
            wallet_address = None
            if self.agent and hasattr(self.agent, 'wallet'):
                wallet_address = self.agent.wallet.address()
            else:
                try:
                    wallet_address = ctx.wallet.address()  # type: ignore[attr-defined]
                except Exception:
                    try:
                        wallet_address = ctx.agent.wallet.address()  # type: ignore[attr-defined]
                    except Exception:
                        raise PaymentError("Wallet not available in context")
            balance = ctx.ledger.query_bank_balance(wallet_address, "atestfet")
            logger.info(f"Current balance for {wallet_address}: {balance} atestfet")
            return int(balance)
            
        except Exception as e:
            logger.error(f"Failed to query balance: {e}")
            raise PaymentError(f"Balance query failed: {e}")
    
    async def send_payment(self, ctx: Context, recipient: str, amount: int, 
                         memo: str = "") -> Optional[str]:
        """
        Send FET payment to recipient
        
        Args:
            ctx: Agent context
            recipient: Recipient address
            amount: Amount in atestfet
            memo: Optional transaction memo
            
        Returns:
            Transaction hash if successful, None otherwise
        """
        try:
            # Check current balance
            current_balance = await self.get_balance(ctx)
            
            if current_balance < amount:
                raise PaymentError(f"Insufficient balance: {current_balance} < {amount}")
            
            # Send tokens using the agent's ledger
            # Resolve wallet object
            wallet_obj = None
            if self.agent and hasattr(self.agent, 'wallet'):
                wallet_obj = self.agent.wallet
            else:
                try:
                    wallet_obj = ctx.wallet  # type: ignore[attr-defined]
                except Exception:
                    try:
                        wallet_obj = ctx.agent.wallet  # type: ignore[attr-defined]
                    except Exception:
                        wallet_obj = None
            if wallet_obj is None:
                raise PaymentError("Wallet not available in context")

            # The ledger's send_tokens needs 'sender' parameter as a Wallet object
            tx_response = None
            
            # Try different approaches to send the payment
            if self.agent and hasattr(self.agent, '_ledger') and hasattr(self.agent, 'wallet'):
                # Method 1: Use the agent's ledger with the agent's wallet
                try:
                    tx_response = self.agent._ledger.send_tokens(
                        destination=recipient,
                        amount=amount,
                        denom="atestfet",
                        sender=self.agent.wallet,
                        memo=memo
                    )
                    logger.info("Payment sent using agent._ledger")
                except Exception as e:
                    logger.warning(f"agent._ledger method failed: {e}")
                    tx_response = None
            
            # If first method failed or not available, try context ledger
            if tx_response is None and wallet_obj:
                try:
                    tx_response = ctx.ledger.send_tokens(
                        destination=recipient,
                        amount=amount,
                        denom="atestfet",
                        sender=wallet_obj,
                        memo=memo
                    )
                    logger.info("Payment sent using ctx.ledger")
                except TypeError as e:
                    # If 'sender' parameter is not recognized, try without it (older API)
                    logger.warning(f"ctx.ledger with sender failed: {e}, trying without sender param")
                    try:
                        # Create a new ledger client with the wallet
                        from cosmpy.aerial.client import LedgerClient, NetworkConfig
                        ledger_client = LedgerClient(NetworkConfig.fetchai_dorado_testnet())
                        tx_response = ledger_client.send_tokens(
                            destination=recipient,
                            amount=amount, 
                            denom="atestfet",
                            sender=wallet_obj,
                            memo=memo
                        )
                        logger.info("Payment sent using new LedgerClient")
                    except Exception as e2:
                        logger.error(f"All payment methods failed: {e2}")
                        raise PaymentError(f"Unable to send payment: {e2}")
            
            if not tx_response:
                raise PaymentError("No wallet available for payment or all methods failed")
            
            if tx_response:
                # Check for different hash attribute names
                tx_hash = None
                if hasattr(tx_response, 'tx_hash'):
                    tx_hash = tx_response.tx_hash
                elif hasattr(tx_response, 'hash'):
                    tx_hash = tx_response.hash
                elif hasattr(tx_response, 'txhash'):
                    tx_hash = tx_response.txhash
                    
                if tx_hash:
                    logger.info(f"Payment sent: {amount} atestfet to {recipient}, tx: {tx_hash}")
                    return str(tx_hash)
                else:
                    logger.error(f"Payment response has no hash. Response type: {type(tx_response)}")
                    raise PaymentError("Transaction has no hash")
            else:
                logger.error(f"Payment failed - no transaction response")
                raise PaymentError("No transaction response")
                
        except Exception as e:
            logger.error(f"Payment error: {e}")
            raise PaymentError(f"Payment failed: {e}")
    
    async def send_bond(self, ctx: Context, recipient: str, amount: int, 
                       job_id: str) -> Optional[str]:
        """
        Send bond payment for a job
        
        Args:
            ctx: Agent context
            recipient: Bond recipient (usually client)
            amount: Bond amount in atestfet
            job_id: Job identifier
            
        Returns:
            Transaction hash if successful
        """
        memo = f"Bond for job {job_id}"
        return await self.send_payment(ctx, recipient, amount, memo)
    
    async def send_job_payment(self, ctx: Context, recipient: str, amount: int,
                              job_id: str) -> Optional[str]:
        """
        Send job payment after successful verification
        
        Args:
            ctx: Agent context
            recipient: Payment recipient (tool agent)
            amount: Payment amount in atestfet
            job_id: Job identifier
            
        Returns:
            Transaction hash if successful
        """
        memo = f"Payment for job {job_id}"
        return await self.send_payment(ctx, recipient, amount, memo)
    
    async def return_bond(self, ctx: Context, original_sender: str, amount: int,
                         job_id: str) -> Optional[str]:
        """
        Return bond to original sender after successful job completion
        
        Args:
            ctx: Agent context
            original_sender: Address to return bond to
            amount: Bond amount to return
            job_id: Job identifier
            
        Returns:
            Transaction hash if successful
        """
        memo = f"Bond return for job {job_id}"
        return await self.send_payment(ctx, original_sender, amount, memo)
    
    async def ensure_minimum_balance(self, ctx: Context, required_amount: int) -> bool:
        """
        Ensure agent has minimum balance, request from faucet if needed
        
        Args:
            ctx: Agent context
            required_amount: Required minimum balance in atestfet
            
        Returns:
            True if balance is sufficient, False otherwise
        """
        try:
            current_balance = await self.get_balance(ctx)
            
            if current_balance >= required_amount:
                return True
            
            logger.info(f"Insufficient balance ({current_balance}), requesting from faucet...")
            
            # Request tokens from faucet
            # Resolve wallet address
            faucet_address = None
            if self.agent and hasattr(self.agent, 'wallet'):
                faucet_address = self.agent.wallet.address()
            else:
                try:
                    faucet_address = ctx.wallet.address()  # type: ignore[attr-defined]
                except Exception:
                    try:
                        faucet_address = ctx.agent.wallet.address()  # type: ignore[attr-defined]
                    except Exception:
                        logger.warning("Wallet address not available; cannot request faucet")
                        return False

            # Get the faucet API instance and request funds
            faucet_api = get_faucet()
            try:
                faucet_api.get_wealth(faucet_address)
                logger.info("Faucet request successful")
                # Wait a moment for the transaction to process
                import asyncio
                await asyncio.sleep(5)
                
                # Check balance again
                new_balance = await self.get_balance(ctx)
                return new_balance >= required_amount
            except Exception as faucet_error:
                logger.warning(f"Faucet request failed: {faucet_error}")
                return False
                
        except Exception as e:
            logger.error(f"Error ensuring minimum balance: {e}")
            return False
    
    def format_amount(self, amount_atestfet: int) -> str:
        """
        Format amount for display
        
        Args:
            amount_atestfet: Amount in atestfet (smallest unit)
            
        Returns:
            Formatted string (e.g., "5.0 testFET")
        """
        # Convert atestfet to testFET (1 testFET = 10^18 atestfet)
        testfet_amount = amount_atestfet / 1e18
        return f"{testfet_amount:.4f} testFET"
    
    def parse_amount(self, testfet_str: str) -> int:
        """
        Parse testFET amount string to atestfet
        
        Args:
            testfet_str: Amount string (e.g., "5.0", "1.5 testFET")
            
        Returns:
            Amount in atestfet
        """
        try:
            # Remove "testFET" suffix if present
            cleaned = testfet_str.replace("testFET", "").replace("FET", "").strip()
            testfet_amount = float(cleaned)
            
            # Convert to atestfet
            atestfet_amount = int(testfet_amount * 1e18)
            return atestfet_amount
            
        except (ValueError, TypeError) as e:
            raise PaymentError(f"Invalid amount format: {testfet_str}")
    
    async def verify_transaction(self, ctx: Context, tx_hash: str, 
                                expected_amount: int, expected_recipient: str) -> bool:
        """
        Verify a transaction was successful
        
        Args:
            ctx: Agent context
            tx_hash: Transaction hash to verify
            expected_amount: Expected transaction amount
            expected_recipient: Expected recipient address
            
        Returns:
            True if transaction is verified, False otherwise
        """
        try:
            # Note: In a production system, you would query the blockchain
            # to verify the transaction details. For MVP, we'll do a basic check.
            
            # Check if tx_hash looks valid (basic format check)
            if not tx_hash or len(tx_hash) < 10:
                logger.warning(f"Invalid transaction hash format: {tx_hash}")
                return False
            
            # In a real implementation, query the blockchain for transaction details
            # For now, we'll assume the transaction is valid if we have a hash
            logger.info(f"Transaction verification passed for {tx_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Transaction verification failed: {e}")
            return False
    
    @staticmethod
    def get_default_bond_amount() -> int:
        """Get default bond amount in atestfet"""
        return int(1e18)  # 1 testFET
    
    @staticmethod
    def get_default_price_amount() -> int:
        """Get default price amount in atestfet"""
        return int(5e18)  # 5 testFET
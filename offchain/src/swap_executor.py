"""Swap execution engine for atomic arbitrage transactions."""

import time
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal

import structlog
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solders.instruction import Instruction, AccountMeta
from solders.system_program import ID as SYS_PROGRAM_ID
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed, Finalized
from solana.rpc.types import TxOpts
from anchorpy import Provider, Program, Context
from anchorpy.error import ProgramError
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID

from .config import settings

logger = structlog.get_logger(__name__)


class SwapExecutor:
    """Executes atomic arbitrage swaps using the on-chain program."""
    
    def __init__(self, provider: Provider, program_id: Pubkey):
        self.provider = provider
        self.program_id = program_id
        self.logger = logger.bind(component="SwapExecutor")
        
        # Load the program (would normally load from IDL)
        self.program = None  # Would be initialized with actual IDL
        
        # Transaction tracking
        self.pending_transactions: Dict[str, Dict] = {}
        self.execution_stats = {
            "total_attempts": 0,
            "successful_swaps": 0,
            "failed_swaps": 0,
            "total_gas_used": 0,
            "average_execution_time": 0.0
        }
        
        self.logger.info(
            "Swap executor initialized",
            program_id=str(program_id),
            wallet=str(provider.wallet.public_key)
        )
    
    async def initialize_program(
        self,
        min_profit_threshold: int,
        max_slippage_bps: int
    ) -> bool:
        """Initialize the swap agent program if not already initialized."""
        try:
            # Check if already initialized
            swap_agent_pda, bump = self._get_swap_agent_pda()
            
            try:
                # Try to fetch existing account
                account_info = await self.provider.connection.get_account_info(
                    swap_agent_pda,
                    commitment=Confirmed
                )
                
                if account_info.value:
                    self.logger.info("Swap agent already initialized", pda=str(swap_agent_pda))
                    return True
            
            except Exception:
                pass  # Account doesn't exist, need to initialize
            
            # Initialize the program
            self.logger.info("Initializing swap agent program...")
            
            # Build initialization instruction
            init_instruction = await self._build_initialize_instruction(
                min_profit_threshold,
                max_slippage_bps,
                swap_agent_pda,
                bump
            )
            
            # Send transaction
            tx_result = await self._send_transaction([init_instruction])
            
            if tx_result:
                self.logger.info(
                    "Swap agent initialized successfully",
                    signature=tx_result["signature"],
                    pda=str(swap_agent_pda)
                )
                return True
            
        except Exception as e:
            self.logger.error("Error initializing swap agent", error=str(e))
        
        return False
    
    async def execute_arbitrage_swap(
        self,
        token_a: str,
        token_b: str,
        swap_amount: int,
        dex_path: List[str],
        min_profit: int
    ) -> Optional[Dict[str, Any]]:
        """Execute an atomic arbitrage swap."""
        start_time = time.time()
        
        self.execution_stats["total_attempts"] += 1
        
        try:
            self.logger.info(
                "Executing arbitrage swap",
                token_pair=f"{token_a[:8]}.../{token_b[:8]}...",
                amount=swap_amount,
                dex_path=dex_path,
                min_profit=min_profit
            )
            
            # Build swap data
            swap_data = await self._build_swap_data(
                token_a,
                token_b,
                swap_amount,
                dex_path,
                min_profit
            )
            
            if not swap_data:
                self.logger.error("Failed to build swap data")
                self.execution_stats["failed_swaps"] += 1
                return None
            
            # Get required accounts
            accounts = await self._get_swap_accounts(token_a, token_b)
            
            if not accounts:
                self.logger.error("Failed to get required accounts")
                self.execution_stats["failed_swaps"] += 1
                return None
            
            # Build swap instruction
            swap_instruction = await self._build_arbitrage_instruction(
                swap_data,
                accounts
            )
            
            # Execute the swap
            tx_result = await self._send_transaction(
                [swap_instruction],
                compute_budget=300_000  # Higher compute for complex swaps
            )
            
            if tx_result:
                execution_time = time.time() - start_time
                
                # Update statistics
                self.execution_stats["successful_swaps"] += 1
                self.execution_stats["total_gas_used"] += tx_result.get("gas_used", 0)
                self._update_average_execution_time(execution_time)
                
                result = {
                    "signature": tx_result["signature"],
                    "slot": tx_result.get("slot", 0),
                    "actual_profit": tx_result.get("actual_profit", 0),
                    "gas_used": tx_result.get("gas_used", 0),
                    "execution_time": execution_time,
                    "dex_path": dex_path
                }
                
                self.logger.info(
                    "Arbitrage swap executed successfully",
                    **result
                )
                
                return result
            
            else:
                self.execution_stats["failed_swaps"] += 1
                self.logger.error("Swap transaction failed")
        
        except Exception as e:
            self.execution_stats["failed_swaps"] += 1
            self.logger.error("Error executing arbitrage swap", error=str(e))
        
        return None
    
    async def _build_swap_data(
        self,
        token_a: str,
        token_b: str,
        swap_amount: int,
        dex_path: List[str],
        min_profit: int
    ) -> Optional[Dict[str, Any]]:
        """Build swap data structure for the smart contract."""
        try:
            # Map DEX names to enum values
            dex_type_map = {
                "jupiter": 0,  # DexType::Jupiter
                "raydium": 1,   # DexType::Raydium
                "phoenix": 2,   # DexType::Phoenix
                "meteora": 3    # DexType::Meteora
            }
            
            swap_instructions = []
            current_amount = swap_amount
            
            # Build swap instructions for each step in the path
            for i, dex_name in enumerate(dex_path):
                if dex_name.lower() not in dex_type_map:
                    self.logger.error("Unknown DEX in path", dex=dex_name)
                    return None
                
                # Determine input/output tokens for this step
                if i == 0:
                    # First swap: token_a -> token_b
                    input_token = token_a
                    output_token = token_b
                elif i == len(dex_path) - 1:
                    # Last swap: token_b -> token_a (complete the arbitrage)
                    input_token = token_b
                    output_token = token_a
                else:
                    # Intermediate swaps (if multi-hop)
                    input_token = token_b
                    output_token = token_a
                
                # Calculate minimum output amount (with slippage protection)
                slippage_factor = (10000 - settings.max_slippage_bps) / 10000
                min_amount_out = int(current_amount * slippage_factor)
                
                swap_instruction = {
                    "dex_type": dex_type_map[dex_name.lower()],
                    "amount_in": current_amount,
                    "minimum_amount_out": min_amount_out,
                    "token_mint_in": input_token,
                    "token_mint_out": output_token
                }
                
                swap_instructions.append(swap_instruction)
                
                # Update amount for next instruction (estimated)
                current_amount = min_amount_out
            
            return {
                "expected_profit": min_profit,
                "slippage_bps": settings.max_slippage_bps,
                "swap_instructions": swap_instructions
            }
        
        except Exception as e:
            self.logger.error("Error building swap data", error=str(e))
            return None
    
    async def _get_swap_accounts(self, token_a: str, token_b: str) -> Optional[Dict[str, Any]]:
        """Get all required accounts for the swap."""
        try:
            wallet_pubkey = self.provider.wallet.public_key
            
            # Get swap agent PDA
            swap_agent_pda, _ = self._get_swap_agent_pda()
            
            # Get associated token accounts
            token_a_account = await self._get_associated_token_account(token_a, wallet_pubkey)
            token_b_account = await self._get_associated_token_account(token_b, wallet_pubkey)
            
            return {
                "swap_agent": swap_agent_pda,
                "user": wallet_pubkey,
                "user_token_account_a": token_a_account,
                "user_token_account_b": token_b_account,
                "token_mint_a": Pubkey.from_string(token_a),
                "token_mint_b": Pubkey.from_string(token_b),
                "token_program": TOKEN_PROGRAM_ID,
                "associated_token_program": ASSOCIATED_TOKEN_PROGRAM_ID,
                "system_program": SYS_PROGRAM_ID
            }
        
        except Exception as e:
            self.logger.error("Error getting swap accounts", error=str(e))
            return None
    
    async def _build_initialize_instruction(
        self,
        min_profit_threshold: int,
        max_slippage_bps: int,
        swap_agent_pda: Pubkey,
        bump: int
    ) -> Instruction:
        """Build the program initialization instruction."""
        # This would use the actual program IDL to build the instruction
        # For now, we'll create a placeholder instruction
        
        accounts = [
            AccountMeta(pubkey=swap_agent_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=self.provider.wallet.public_key, is_signer=True, is_writable=True),
            AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        ]
        
        # Build instruction data (would use anchor serialization)
        instruction_data = bytes([
            0,  # Instruction discriminator for initialize
            *min_profit_threshold.to_bytes(8, 'little'),
            *max_slippage_bps.to_bytes(2, 'little'),
        ])
        
        return Instruction(
            program_id=self.program_id,
            accounts=accounts,
            data=instruction_data
        )
    
    async def _build_arbitrage_instruction(
        self,
        swap_data: Dict[str, Any],
        accounts: Dict[str, Any]
    ) -> Instruction:
        """Build the arbitrage swap instruction."""
        # Build account metas
        account_metas = [
            AccountMeta(pubkey=accounts["swap_agent"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["user"], is_signer=True, is_writable=True),
            AccountMeta(pubkey=accounts["user_token_account_a"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["user_token_account_b"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["token_mint_a"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts["token_mint_b"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts["token_program"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts["associated_token_program"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts["system_program"], is_signer=False, is_writable=False),
        ]
        
        # Serialize swap data (would use anchor serialization in real implementation)
        instruction_data = self._serialize_swap_data(swap_data)
        
        return Instruction(
            program_id=self.program_id,
            accounts=account_metas,
            data=instruction_data
        )
    
    def _serialize_swap_data(self, swap_data: Dict[str, Any]) -> bytes:
        """Serialize swap data for the instruction."""
        # This would use proper anchor serialization
        # For now, we'll create a simple serialization
        
        data = bytearray()
        data.append(1)  # Instruction discriminator for execute_arbitrage_swap
        
        # Serialize expected_profit (8 bytes)
        data.extend(swap_data["expected_profit"].to_bytes(8, 'little'))
        
        # Serialize slippage_bps (2 bytes)
        data.extend(swap_data["slippage_bps"].to_bytes(2, 'little'))
        
        # Serialize swap_instructions
        instructions = swap_data["swap_instructions"]
        data.extend(len(instructions).to_bytes(4, 'little'))  # Number of instructions
        
        for instruction in instructions:
            data.extend(instruction["dex_type"].to_bytes(1, 'little'))
            data.extend(instruction["amount_in"].to_bytes(8, 'little'))
            data.extend(instruction["minimum_amount_out"].to_bytes(8, 'little'))
            data.extend(bytes(Pubkey.from_string(instruction["token_mint_in"])))
            data.extend(bytes(Pubkey.from_string(instruction["token_mint_out"])))
        
        return bytes(data)
    
    async def _send_transaction(
        self,
        instructions: List[Instruction],
        compute_budget: int = 200_000
    ) -> Optional[Dict[str, Any]]:
        """Send a transaction with the given instructions."""
        try:
            # Add compute budget instruction if needed
            if compute_budget > 200_000:
                compute_instruction = self._create_compute_budget_instruction(compute_budget)
                instructions = [compute_instruction] + instructions
            
            # Get recent blockhash
            blockhash_response = await self.provider.connection.get_latest_blockhash()
            recent_blockhash = blockhash_response.value.blockhash
            
            # Build transaction
            transaction = Transaction.new_with_payer(
                instructions,
                self.provider.wallet.public_key
            )
            transaction.recent_blockhash = recent_blockhash
            
            # Sign transaction
            transaction.sign([self.provider.wallet.payer])
            
            # Send transaction
            tx_response = await self.provider.connection.send_transaction(
                transaction,
                opts=TxOpts(
                    skip_preflight=False,
                    preflight_commitment=Confirmed,
                    max_retries=3
                )
            )
            
            signature = tx_response.value
            
            # Wait for confirmation
            confirmation = await self.provider.connection.confirm_transaction(
                signature,
                commitment=Confirmed
            )
            
            if confirmation.value[0].err:
                self.logger.error(
                    "Transaction failed",
                    signature=str(signature),
                    error=confirmation.value[0].err
                )
                return None
            
            # Get transaction details
            tx_details = await self.provider.connection.get_transaction(
                signature,
                commitment=Finalized
            )
            
            result = {
                "signature": str(signature),
                "slot": confirmation.value[1],
                "gas_used": tx_details.value.meta.fee if tx_details.value else 0
            }
            
            # Parse logs for profit information (would be more sophisticated)
            if tx_details.value and tx_details.value.meta.log_messages:
                for log in tx_details.value.meta.log_messages:
                    if "ArbitrageExecuted" in log:
                        # Parse profit from log (simplified)
                        result["actual_profit"] = 0  # Would parse from logs
            
            return result
        
        except Exception as e:
            self.logger.error("Error sending transaction", error=str(e))
            return None
    
    def _create_compute_budget_instruction(self, compute_units: int) -> Instruction:
        """Create a compute budget instruction."""
        # This would create an actual compute budget instruction
        # For now, return a placeholder
        return Instruction(
            program_id=SYS_PROGRAM_ID,
            accounts=[],
            data=bytes()
        )
    
    def _get_swap_agent_pda(self) -> tuple[Pubkey, int]:
        """Get the swap agent program derived address."""
        seeds = [
            b"swap_agent",
            bytes(self.provider.wallet.public_key)
        ]
        
        return Pubkey.find_program_address(seeds, self.program_id)
    
    async def _get_associated_token_account(
        self,
        token_mint: str,
        owner: Pubkey
    ) -> Pubkey:
        """Get associated token account for a mint and owner."""
        # This would use the actual ATA derivation
        # For now, return a placeholder
        return Pubkey.from_string("11111111111111111111111111111111")
    
    def _update_average_execution_time(self, execution_time: float):
        """Update the average execution time statistic."""
        total_successful = self.execution_stats["successful_swaps"]
        current_avg = self.execution_stats["average_execution_time"]
        
        # Calculate new average
        new_avg = ((current_avg * (total_successful - 1)) + execution_time) / total_successful
        self.execution_stats["average_execution_time"] = new_avg
    
    async def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total_attempts = self.execution_stats["total_attempts"]
        successful_swaps = self.execution_stats["successful_swaps"]
        
        success_rate = (successful_swaps / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            **self.execution_stats,
            "success_rate": success_rate,
            "pending_transactions": len(self.pending_transactions)
        }
    
    async def emergency_cancel_pending(self) -> List[str]:
        """Cancel all pending transactions (if possible)."""
        cancelled = []
        
        for tx_id in list(self.pending_transactions.keys()):
            try:
                # In a real implementation, this would attempt to cancel
                # pending transactions if they haven't been confirmed
                del self.pending_transactions[tx_id]
                cancelled.append(tx_id)
            except Exception as e:
                self.logger.error("Error cancelling transaction", tx_id=tx_id, error=str(e))
        
        return cancelled
"""Main Solana Swap Agent for automated arbitrage trading."""

import asyncio
import time
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

import structlog
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from anchorpy import Provider, Wallet

from .config import settings, DexConfig
from .dex_clients import JupiterClient, RaydiumClient, PhoenixClient, MeteoraClient
from .price_monitor import PriceMonitor
from .swap_executor import SwapExecutor
from .utils import calculate_profit, format_lamports

logger = structlog.get_logger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents a profitable arbitrage opportunity."""
    token_a: str
    token_b: str
    buy_dex: str
    sell_dex: str
    buy_price: Decimal
    sell_price: Decimal
    profit_percentage: float
    estimated_profit: Decimal
    swap_path: List[str]
    timestamp: float


class SolanaSwapAgent:
    """High-performance Solana arbitrage trading agent."""
    
    def __init__(self):
        self.logger = logger.bind(component="SwapAgent")
        
        # Initialize Solana connection
        self.rpc_client = AsyncClient(settings.solana_rpc_url)
        
        # Initialize wallet
        self.keypair = Keypair.from_base58_string(settings.wallet_private_key)
        self.wallet = Wallet(self.keypair)
        self.provider = Provider(self.rpc_client, self.wallet)
        
        # Initialize DEX clients
        self.jupiter_client = JupiterClient()
        self.raydium_client = RaydiumClient()
        self.phoenix_client = PhoenixClient()
        self.meteora_client = MeteoraClient()
        
        # Initialize components
        self.price_monitor = PriceMonitor(
            rpc_client=self.rpc_client,
            dex_clients={
                "jupiter": self.jupiter_client,
                "raydium": self.raydium_client,
                "phoenix": self.phoenix_client,
                "meteora": self.meteora_client,
            }
        )
        
        self.swap_executor = SwapExecutor(
            provider=self.provider,
            program_id=Pubkey.from_string(settings.swap_agent_program_id)
        )
        
        # Trading state
        self.active_positions = {}
        self.trading_enabled = True
        self.performance_stats = {
            "total_trades": 0,
            "successful_trades": 0,
            "total_profit": Decimal("0"),
            "average_profit": Decimal("0"),
            "largest_profit": Decimal("0"),
        }
        
        self.logger.info(
            "Swap agent initialized",
            wallet_address=str(self.keypair.pubkey()),
            monitored_tokens=len(settings.monitored_tokens)
        )
    
    async def start(self):
        """Start the trading agent."""
        self.logger.info("Starting Solana Swap Agent...")
        
        try:
            # Initialize program if needed
            await self.swap_executor.initialize_program(
                min_profit_threshold=int(settings.min_profit_threshold * 1e9),  # Convert to lamports
                max_slippage_bps=settings.max_slippage_bps
            )
            
            # Start price monitoring
            await self.price_monitor.start()
            
            # Start main trading loop
            await self.run_trading_loop()
            
        except Exception as e:
            self.logger.error("Error starting swap agent", error=str(e))
            raise
    
    async def stop(self):
        """Stop the trading agent."""
        self.logger.info("Stopping Solana Swap Agent...")
        self.trading_enabled = False
        await self.price_monitor.stop()
        await self.rpc_client.close()
    
    async def run_trading_loop(self):
        """Main trading loop that continuously looks for arbitrage opportunities."""
        self.logger.info("Starting trading loop...")
        
        while self.trading_enabled:
            try:
                # Find arbitrage opportunities
                opportunities = await self.find_arbitrage_opportunities()
                
                if opportunities:
                    self.logger.info(
                        "Found arbitrage opportunities",
                        count=len(opportunities)
                    )
                    
                    # Execute the most profitable opportunities
                    await self.execute_opportunities(opportunities)
                
                # Brief pause to prevent excessive CPU usage
                await asyncio.sleep(settings.price_update_interval)
                
            except Exception as e:
                self.logger.error("Error in trading loop", error=str(e))
                await asyncio.sleep(1.0)  # Longer pause on error
    
    async def find_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        """Find profitable arbitrage opportunities across DEXes."""
        opportunities = []
        current_time = time.time()
        
        # Get latest prices from all DEXes
        price_data = await self.price_monitor.get_latest_prices()
        
        if not price_data:
            return opportunities
        
        # Check each token pair for arbitrage opportunities
        for token_a in settings.monitored_tokens:
            for token_b in settings.monitored_tokens:
                if token_a == token_b:
                    continue
                
                # Find best buy and sell prices across DEXes
                best_buy_price = None
                best_sell_price = None
                best_buy_dex = None
                best_sell_dex = None
                
                for dex_name, dex_prices in price_data.items():
                    pair_key = f"{token_a}-{token_b}"
                    reverse_pair_key = f"{token_b}-{token_a}"
                    
                    if pair_key in dex_prices:
                        price = dex_prices[pair_key]["price"]
                        
                        # Check if this is the best buy price (lowest)
                        if best_buy_price is None or price < best_buy_price:
                            best_buy_price = price
                            best_buy_dex = dex_name
                        
                        # Check if this is the best sell price (highest)
                        if best_sell_price is None or price > best_sell_price:
                            best_sell_price = price
                            best_sell_dex = dex_name
                
                # Calculate profit potential
                if (best_buy_price and best_sell_price and 
                    best_buy_dex != best_sell_dex and 
                    best_sell_price > best_buy_price):
                    
                    profit_percentage = float(
                        (best_sell_price - best_buy_price) / best_buy_price * 100
                    )
                    
                    # Check if profit meets minimum threshold
                    if profit_percentage >= settings.min_profit_threshold:
                        estimated_profit = calculate_profit(
                            best_buy_price,
                            best_sell_price,
                            settings.max_position_size
                        )
                        
                        opportunity = ArbitrageOpportunity(
                            token_a=token_a,
                            token_b=token_b,
                            buy_dex=best_buy_dex,
                            sell_dex=best_sell_dex,
                            buy_price=best_buy_price,
                            sell_price=best_sell_price,
                            profit_percentage=profit_percentage,
                            estimated_profit=estimated_profit,
                            swap_path=[best_buy_dex, best_sell_dex],
                            timestamp=current_time
                        )
                        
                        opportunities.append(opportunity)
                        
                        self.logger.info(
                            "Found arbitrage opportunity",
                            token_pair=f"{token_a[:8]}.../{token_b[:8]}...",
                            buy_dex=best_buy_dex,
                            sell_dex=best_sell_dex,
                            profit_percentage=f"{profit_percentage:.3f}%",
                            estimated_profit=f"{estimated_profit:.6f} SOL"
                        )
        
        # Sort opportunities by profit percentage (descending)
        opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        return opportunities[:settings.max_concurrent_swaps]  # Limit concurrent trades
    
    async def execute_opportunities(self, opportunities: List[ArbitrageOpportunity]):
        """Execute arbitrage opportunities concurrently."""
        tasks = []
        
        for opportunity in opportunities:
            if len(tasks) >= settings.max_concurrent_swaps:
                break
            
            task = asyncio.create_task(
                self.execute_single_opportunity(opportunity)
            )
            tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(
                        "Error executing opportunity",
                        opportunity_index=i,
                        error=str(result)
                    )
                elif result:
                    self.logger.info("Successfully executed opportunity", result=result)
    
    async def execute_single_opportunity(self, opportunity: ArbitrageOpportunity) -> Optional[dict]:
        """Execute a single arbitrage opportunity."""
        try:
            self.logger.info(
                "Executing arbitrage opportunity",
                token_pair=f"{opportunity.token_a[:8]}.../{opportunity.token_b[:8]}...",
                profit_percentage=f"{opportunity.profit_percentage:.3f}%"
            )
            
            # Calculate optimal swap amounts
            swap_amount = min(
                settings.max_position_size,
                float(opportunity.estimated_profit) * 10  # Conservative sizing
            )
            
            # Execute the swap
            result = await self.swap_executor.execute_arbitrage_swap(
                token_a=opportunity.token_a,
                token_b=opportunity.token_b,
                swap_amount=int(swap_amount * 1e9),  # Convert to lamports
                dex_path=opportunity.swap_path,
                min_profit=int(float(opportunity.estimated_profit) * 1e9 * 0.8)  # 80% of estimated
            )
            
            if result:
                # Update performance statistics
                actual_profit = Decimal(str(result.get("actual_profit", 0))) / Decimal("1e9")
                await self.update_performance_stats(actual_profit, success=True)
                
                return {
                    "opportunity": opportunity,
                    "result": result,
                    "actual_profit": actual_profit,
                    "execution_time": time.time()
                }
            
        except Exception as e:
            self.logger.error(
                "Failed to execute opportunity",
                error=str(e),
                opportunity=opportunity
            )
            await self.update_performance_stats(Decimal("0"), success=False)
        
        return None
    
    async def update_performance_stats(self, profit: Decimal, success: bool):
        """Update trading performance statistics."""
        self.performance_stats["total_trades"] += 1
        
        if success:
            self.performance_stats["successful_trades"] += 1
            self.performance_stats["total_profit"] += profit
            
            if profit > self.performance_stats["largest_profit"]:
                self.performance_stats["largest_profit"] = profit
            
            # Calculate average profit
            if self.performance_stats["successful_trades"] > 0:
                self.performance_stats["average_profit"] = (
                    self.performance_stats["total_profit"] / 
                    self.performance_stats["successful_trades"]
                )
        
        # Log performance update every 10 trades
        if self.performance_stats["total_trades"] % 10 == 0:
            success_rate = (
                self.performance_stats["successful_trades"] / 
                self.performance_stats["total_trades"] * 100
            )
            
            self.logger.info(
                "Performance update",
                total_trades=self.performance_stats["total_trades"],
                success_rate=f"{success_rate:.1f}%",
                total_profit=f"{self.performance_stats['total_profit']:.6f} SOL",
                average_profit=f"{self.performance_stats['average_profit']:.6f} SOL"
            )
    
    async def get_account_balances(self) -> Dict[str, float]:
        """Get current account balances."""
        balances = {}
        
        try:
            # Get SOL balance
            sol_balance = await self.rpc_client.get_balance(
                self.keypair.pubkey(),
                commitment=Confirmed
            )
            balances["SOL"] = sol_balance.value / 1e9
            
            # Get token balances for monitored tokens
            for token_mint in settings.monitored_tokens:
                if token_mint == "So11111111111111111111111111111111111111112":  # SOL
                    continue
                
                # Get associated token account
                token_balance = await self.get_token_balance(token_mint)
                if token_balance > 0:
                    balances[token_mint[:8] + "..."] = token_balance
            
        except Exception as e:
            self.logger.error("Error getting account balances", error=str(e))
        
        return balances
    
    async def get_token_balance(self, token_mint: str) -> float:
        """Get balance for a specific token."""
        try:
            # This would implement actual token balance lookup
            # For now, return 0
            return 0.0
        except Exception:
            return 0.0


async def main():
    """Main entry point for the swap agent."""
    import signal
    
    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(colors=True)
            if settings.log_format == "text"
            else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib, settings.log_level.upper())
        ),
        cache_logger_on_first_use=True,
    )
    
    # Create and start the swap agent
    agent = SolanaSwapAgent()
    
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal", signal=signum)
        asyncio.create_task(agent.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
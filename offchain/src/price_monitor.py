"""Real-time price monitoring system for Solana DEXes."""

import asyncio
import time
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
from decimal import Decimal
import json

import structlog
import aioredis
from solana.rpc.async_api import AsyncClient

from .config import settings
from .dex_clients import BaseDexClient

logger = structlog.get_logger(__name__)


class PriceMonitor:
    """Monitors prices across multiple DEXes in real-time."""
    
    def __init__(self, rpc_client: AsyncClient, dex_clients: Dict[str, BaseDexClient]):
        self.rpc_client = rpc_client
        self.dex_clients = dex_clients
        self.logger = logger.bind(component="PriceMonitor")
        
        # Price storage
        self.latest_prices: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Redis for caching (optional)
        self.redis: Optional[aioredis.Redis] = None
        
        # Monitoring state
        self.monitoring = False
        self.update_tasks: List[asyncio.Task] = []
        
        # Performance tracking
        self.update_count = 0
        self.last_update_time = 0.0
        self.update_latencies: deque = deque(maxlen=50)
        
        self.logger.info(
            "Price monitor initialized",
            dex_count=len(dex_clients),
            monitored_tokens=len(settings.monitored_tokens)
        )
    
    async def start(self):
        """Start price monitoring."""
        self.logger.info("Starting price monitor...")
        
        try:
            # Initialize Redis connection if configured
            if settings.redis_url:
                self.redis = await aioredis.from_url(settings.redis_url)
                self.logger.info("Connected to Redis for price caching")
            
            # Start monitoring tasks for each DEX
            self.monitoring = True
            
            for dex_name, dex_client in self.dex_clients.items():
                task = asyncio.create_task(
                    self._monitor_dex_prices(dex_name, dex_client)
                )
                self.update_tasks.append(task)
                self.logger.info("Started price monitoring task", dex=dex_name)
            
            # Start performance monitoring task
            perf_task = asyncio.create_task(self._monitor_performance())
            self.update_tasks.append(perf_task)
            
            self.logger.info("Price monitoring started successfully")
            
        except Exception as e:
            self.logger.error("Error starting price monitor", error=str(e))
            await self.stop()
            raise
    
    async def stop(self):
        """Stop price monitoring."""
        self.logger.info("Stopping price monitor...")
        self.monitoring = False
        
        # Cancel all monitoring tasks
        for task in self.update_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to finish
        if self.update_tasks:
            await asyncio.gather(*self.update_tasks, return_exceptions=True)
        
        # Close Redis connection
        if self.redis:
            await self.redis.close()
        
        self.logger.info("Price monitor stopped")
    
    async def _monitor_dex_prices(self, dex_name: str, dex_client: BaseDexClient):
        """Monitor prices for a specific DEX."""
        dex_logger = self.logger.bind(dex=dex_name)
        consecutive_failures = 0
        max_failures = 5
        
        async with dex_client:
            while self.monitoring:
                try:
                    start_time = time.time()
                    
                    # Get all prices from this DEX
                    prices = await dex_client.get_all_prices()
                    
                    if prices:
                        # Update latest prices
                        self.latest_prices[dex_name] = prices
                        
                        # Store in price history
                        for pair_key, price_data in prices.items():
                            history_key = f"{dex_name}:{pair_key}"
                            self.price_history[history_key].append({
                                "price": float(price_data["price"]),
                                "timestamp": price_data["timestamp"],
                                "liquidity": price_data.get("liquidity", 0)
                            })
                        
                        # Cache in Redis if available
                        if self.redis:
                            await self._cache_prices(dex_name, prices)
                        
                        # Track update latency
                        latency = time.time() - start_time
                        self.update_latencies.append(latency)
                        
                        # Reset failure count on success
                        consecutive_failures = 0
                        
                        dex_logger.debug(
                            "Updated prices",
                            pair_count=len(prices),
                            latency=f"{latency:.3f}s"
                        )
                    
                    else:
                        consecutive_failures += 1
                        dex_logger.warning(
                            "No prices received",
                            consecutive_failures=consecutive_failures
                        )
                    
                    # Check if we should pause due to failures
                    if consecutive_failures >= max_failures:
                        dex_logger.error(
                            "Too many consecutive failures, pausing",
                            failures=consecutive_failures
                        )
                        await asyncio.sleep(30.0)  # Pause for 30 seconds
                        consecutive_failures = 0
                    
                    # Wait before next update
                    await asyncio.sleep(settings.price_update_interval)
                
                except asyncio.CancelledError:
                    dex_logger.info("Price monitoring cancelled")
                    break
                
                except Exception as e:
                    consecutive_failures += 1
                    dex_logger.error(
                        "Error updating prices",
                        error=str(e),
                        consecutive_failures=consecutive_failures
                    )
                    
                    # Exponential backoff on errors
                    sleep_time = min(30.0, 2 ** consecutive_failures)
                    await asyncio.sleep(sleep_time)
    
    async def _cache_prices(self, dex_name: str, prices: Dict[str, Dict[str, Any]]):
        """Cache prices in Redis."""
        try:
            # Cache individual prices
            for pair_key, price_data in prices.items():
                cache_key = f"price:{dex_name}:{pair_key}"
                cache_data = {
                    "price": str(price_data["price"]),
                    "liquidity": price_data.get("liquidity", 0),
                    "timestamp": price_data["timestamp"]
                }
                
                await self.redis.setex(
                    cache_key,
                    60,  # 1 minute TTL
                    json.dumps(cache_data)
                )
            
            # Cache aggregated data
            aggregated_key = f"prices:{dex_name}"
            aggregated_data = {
                pair_key: {
                    "price": str(price_data["price"]),
                    "liquidity": price_data.get("liquidity", 0),
                    "timestamp": price_data["timestamp"]
                }
                for pair_key, price_data in prices.items()
            }
            
            await self.redis.setex(
                aggregated_key,
                30,  # 30 seconds TTL
                json.dumps(aggregated_data)
            )
        
        except Exception as e:
            self.logger.warning("Error caching prices", error=str(e))
    
    async def _monitor_performance(self):
        """Monitor and log performance metrics."""
        while self.monitoring:
            try:
                await asyncio.sleep(60.0)  # Report every minute
                
                if self.update_latencies:
                    avg_latency = sum(self.update_latencies) / len(self.update_latencies)
                    max_latency = max(self.update_latencies)
                    
                    # Count active price feeds
                    active_feeds = sum(1 for prices in self.latest_prices.values() if prices)
                    total_pairs = sum(len(prices) for prices in self.latest_prices.values())
                    
                    self.logger.info(
                        "Performance metrics",
                        active_dexes=active_feeds,
                        total_pairs=total_pairs,
                        avg_latency=f"{avg_latency:.3f}s",
                        max_latency=f"{max_latency:.3f}s",
                        update_interval=settings.price_update_interval
                    )
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in performance monitoring", error=str(e))
    
    async def get_latest_prices(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get the latest prices from all DEXes."""
        return dict(self.latest_prices)
    
    async def get_price_for_pair(
        self,
        token_a: str,
        token_b: str,
        dex_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the latest price for a specific token pair."""
        pair_key = f"{token_a}-{token_b}"
        reverse_pair_key = f"{token_b}-{token_a}"
        
        if dex_name:
            # Get price from specific DEX
            dex_prices = self.latest_prices.get(dex_name, {})
            
            if pair_key in dex_prices:
                return dex_prices[pair_key]
            elif reverse_pair_key in dex_prices:
                # Return inverted price
                price_data = dex_prices[reverse_pair_key].copy()
                price_data["price"] = 1 / price_data["price"]
                return price_data
        
        else:
            # Get best price across all DEXes
            best_price = None
            best_data = None
            
            for dex_prices in self.latest_prices.values():
                if pair_key in dex_prices:
                    price_data = dex_prices[pair_key]
                    price = price_data["price"]
                    
                    if best_price is None or price > best_price:
                        best_price = price
                        best_data = price_data
                
                elif reverse_pair_key in dex_prices:
                    price_data = dex_prices[reverse_pair_key].copy()
                    price = 1 / price_data["price"]
                    
                    if best_price is None or price > best_price:
                        best_price = price
                        best_data = price_data
                        best_data["price"] = price
            
            return best_data
        
        return None
    
    async def get_price_history(
        self,
        token_a: str,
        token_b: str,
        dex_name: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get price history for a token pair on a specific DEX."""
        pair_key = f"{token_a}-{token_b}"
        history_key = f"{dex_name}:{pair_key}"
        
        history = list(self.price_history.get(history_key, []))
        return history[-limit:] if history else []
    
    async def get_arbitrage_opportunities(
        self,
        min_profit_percentage: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Find arbitrage opportunities across DEXes."""
        opportunities = []
        
        # Check each token pair across all DEXes
        for token_a in settings.monitored_tokens:
            for token_b in settings.monitored_tokens:
                if token_a == token_b:
                    continue
                
                pair_key = f"{token_a}-{token_b}"
                
                # Collect prices from all DEXes
                dex_prices = []
                for dex_name, prices in self.latest_prices.items():
                    if pair_key in prices:
                        price_data = prices[pair_key]
                        dex_prices.append({
                            "dex": dex_name,
                            "price": float(price_data["price"]),
                            "liquidity": price_data.get("liquidity", 0),
                            "timestamp": price_data["timestamp"]
                        })
                
                if len(dex_prices) >= 2:
                    # Find lowest and highest prices
                    min_price_entry = min(dex_prices, key=lambda x: x["price"])
                    max_price_entry = max(dex_prices, key=lambda x: x["price"])
                    
                    if min_price_entry["dex"] != max_price_entry["dex"]:
                        profit_percentage = (
                            (max_price_entry["price"] - min_price_entry["price"]) /
                            min_price_entry["price"] * 100
                        )
                        
                        if profit_percentage >= min_profit_percentage:
                            opportunities.append({
                                "token_pair": f"{token_a[:8]}.../{token_b[:8]}...",
                                "buy_dex": min_price_entry["dex"],
                                "sell_dex": max_price_entry["dex"],
                                "buy_price": min_price_entry["price"],
                                "sell_price": max_price_entry["price"],
                                "profit_percentage": profit_percentage,
                                "buy_liquidity": min_price_entry["liquidity"],
                                "sell_liquidity": max_price_entry["liquidity"],
                                "timestamp": time.time()
                            })
        
        # Sort by profit percentage (descending)
        opportunities.sort(key=lambda x: x["profit_percentage"], reverse=True)
        
        return opportunities
    
    async def get_market_stats(self) -> Dict[str, Any]:
        """Get market statistics across all monitored DEXes."""
        stats = {
            "active_dexes": len([d for d in self.latest_prices.values() if d]),
            "total_pairs": sum(len(prices) for prices in self.latest_prices.values()),
            "last_update": self.last_update_time,
            "avg_update_latency": 0.0,
            "dex_stats": {}
        }
        
        if self.update_latencies:
            stats["avg_update_latency"] = sum(self.update_latencies) / len(self.update_latencies)
        
        # Per-DEX statistics
        for dex_name, prices in self.latest_prices.items():
            if prices:
                total_liquidity = sum(
                    price_data.get("liquidity", 0) for price_data in prices.values()
                )
                avg_price_age = time.time() - (
                    sum(price_data["timestamp"] for price_data in prices.values()) / len(prices)
                )
                
                stats["dex_stats"][dex_name] = {
                    "pair_count": len(prices),
                    "total_liquidity": total_liquidity,
                    "avg_price_age": avg_price_age
                }
        
        return stats
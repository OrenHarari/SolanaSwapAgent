"""DEX client implementations for various Solana decentralized exchanges."""

import asyncio
import aiohttp
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from dataclasses import dataclass

import structlog
from solders.pubkey import Pubkey

from .config import settings, DexConfig

logger = structlog.get_logger(__name__)


@dataclass
class QuoteResponse:
    """Standard quote response format across all DEXes."""
    input_amount: int
    output_amount: int
    price_impact: float
    fee: int
    route: List[str]
    estimated_gas: int
    dex_name: str
    timestamp: float


@dataclass
class PoolInfo:
    """Pool information for a trading pair."""
    pool_id: str
    token_a: str
    token_b: str
    liquidity_a: int
    liquidity_b: int
    fee_rate: float
    dex_name: str


class BaseDexClient(ABC):
    """Abstract base class for DEX clients."""
    
    def __init__(self, name: str, api_url: str):
        self.name = name
        self.api_url = api_url
        self.logger = logger.bind(dex=name)
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter(requests_per_second=10)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5.0),
            headers={"User-Agent": "SolanaSwapAgent/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    @abstractmethod
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[QuoteResponse]:
        """Get a quote for swapping tokens."""
        pass
    
    @abstractmethod
    async def get_pools(self, token_a: str, token_b: str) -> List[PoolInfo]:
        """Get available pools for a token pair."""
        pass
    
    @abstractmethod
    async def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get prices for all monitored pairs."""
        pass
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make an HTTP request with rate limiting and error handling."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        await self.rate_limiter.acquire()
        
        url = f"{self.api_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            async with self.session.request(
                method, url, params=params, json=data
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    self.logger.warning(
                        "API request failed",
                        status=response.status,
                        url=url
                    )
                    return None
        
        except asyncio.TimeoutError:
            self.logger.warning("Request timeout", url=url)
            return None
        except Exception as e:
            self.logger.error("Request error", error=str(e), url=url)
            return None


class JupiterClient(BaseDexClient):
    """Jupiter Aggregator client."""
    
    def __init__(self):
        super().__init__("Jupiter", DexConfig.JUPITER["api_url"])
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[QuoteResponse]:
        """Get Jupiter quote for token swap."""
        params = {
            "inputMint": input_token,
            "outputMint": output_token,
            "amount": str(amount),
            "slippageBps": slippage_bps,
            "onlyDirectRoutes": "false",
            "asLegacyTransaction": "false"
        }
        
        response = await self._make_request("GET", "/quote", params=params)
        
        if response:
            try:
                return QuoteResponse(
                    input_amount=int(response["inAmount"]),
                    output_amount=int(response["outAmount"]),
                    price_impact=float(response.get("priceImpactPct", 0)),
                    fee=int(response.get("platformFee", {}).get("amount", 0)),
                    route=[r["swapInfo"]["label"] for r in response.get("routePlan", [])],
                    estimated_gas=50000,  # Jupiter estimate
                    dex_name=self.name,
                    timestamp=time.time()
                )
            except (KeyError, ValueError) as e:
                self.logger.error("Error parsing Jupiter quote", error=str(e))
        
        return None
    
    async def get_pools(self, token_a: str, token_b: str) -> List[PoolInfo]:
        """Get Jupiter route information (acts as pools)."""
        # Jupiter is an aggregator, so we get route info instead of direct pools
        quote = await self.get_quote(token_a, token_b, 1000000)  # 1 token for price
        
        if quote and quote.route:
            return [
                PoolInfo(
                    pool_id=f"jupiter-{token_a}-{token_b}",
                    token_a=token_a,
                    token_b=token_b,
                    liquidity_a=0,  # Not directly available
                    liquidity_b=0,
                    fee_rate=0.0,  # Jupiter doesn't charge direct fees
                    dex_name=self.name
                )
            ]
        
        return []
    
    async def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get prices for all monitored token pairs."""
        prices = {}
        
        # Get prices between all monitored token pairs
        for i, token_a in enumerate(settings.monitored_tokens):
            for token_b in settings.monitored_tokens[i+1:]:
                # Get both directions
                for input_token, output_token in [(token_a, token_b), (token_b, token_a)]:
                    quote = await self.get_quote(
                        input_token,
                        output_token,
                        1000000000  # 1 token (in smallest unit)
                    )
                    
                    if quote:
                        pair_key = f"{input_token}-{output_token}"
                        price = Decimal(quote.output_amount) / Decimal(quote.input_amount)
                        
                        prices[pair_key] = {
                            "price": price,
                            "liquidity": 0,  # Not available from Jupiter
                            "price_impact": quote.price_impact,
                            "timestamp": quote.timestamp
                        }
        
        return prices


class RaydiumClient(BaseDexClient):
    """Raydium DEX client."""
    
    def __init__(self):
        super().__init__("Raydium", DexConfig.RAYDIUM["api_url"])
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[QuoteResponse]:
        """Get Raydium quote for token swap."""
        # Raydium API endpoint for quotes
        params = {
            "inputMint": input_token,
            "outputMint": output_token,
            "amount": str(amount),
            "slippage": slippage_bps / 10000  # Convert bps to decimal
        }
        
        response = await self._make_request("GET", "/compute/swap", params=params)
        
        if response and response.get("success"):
            data = response["data"]
            try:
                return QuoteResponse(
                    input_amount=int(data["amountIn"]),
                    output_amount=int(data["amountOut"]),
                    price_impact=float(data.get("priceImpact", 0)),
                    fee=int(data.get("fee", 0)),
                    route=["Raydium"],
                    estimated_gas=int(data.get("gasEstimate", 100000)),
                    dex_name=self.name,
                    timestamp=time.time()
                )
            except (KeyError, ValueError) as e:
                self.logger.error("Error parsing Raydium quote", error=str(e))
        
        return None
    
    async def get_pools(self, token_a: str, token_b: str) -> List[PoolInfo]:
        """Get Raydium pools for token pair."""
        response = await self._make_request("GET", "/pairs")
        
        pools = []
        if response and response.get("success"):
            for pool_data in response.get("data", []):
                if ((pool_data["baseMint"] == token_a and pool_data["quoteMint"] == token_b) or
                    (pool_data["baseMint"] == token_b and pool_data["quoteMint"] == token_a)):
                    
                    pools.append(PoolInfo(
                        pool_id=pool_data["id"],
                        token_a=pool_data["baseMint"],
                        token_b=pool_data["quoteMint"],
                        liquidity_a=int(pool_data.get("baseReserve", 0)),
                        liquidity_b=int(pool_data.get("quoteReserve", 0)),
                        fee_rate=0.0025,  # 0.25% default Raydium fee
                        dex_name=self.name
                    ))
        
        return pools
    
    async def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get all Raydium prices."""
        response = await self._make_request("GET", "/pairs")
        prices = {}
        
        if response and response.get("success"):
            for pool_data in response.get("data", []):
                base_mint = pool_data["baseMint"]
                quote_mint = pool_data["quoteMint"]
                
                # Only include monitored tokens
                if base_mint in settings.monitored_tokens and quote_mint in settings.monitored_tokens:
                    base_reserve = Decimal(str(pool_data.get("baseReserve", 1)))
                    quote_reserve = Decimal(str(pool_data.get("quoteReserve", 1)))
                    
                    if base_reserve > 0 and quote_reserve > 0:
                        price = quote_reserve / base_reserve
                        
                        pair_key = f"{base_mint}-{quote_mint}"
                        prices[pair_key] = {
                            "price": price,
                            "liquidity": float(base_reserve + quote_reserve),
                            "price_impact": 0.0,
                            "timestamp": time.time()
                        }
        
        return prices


class PhoenixClient(BaseDexClient):
    """Phoenix DEX client."""
    
    def __init__(self):
        super().__init__("Phoenix", DexConfig.PHOENIX["api_url"])
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[QuoteResponse]:
        """Get Phoenix quote for token swap."""
        # Phoenix API implementation
        params = {
            "inputMint": input_token,
            "outputMint": output_token,
            "amount": str(amount),
            "slippage": slippage_bps
        }
        
        response = await self._make_request("GET", "/quote", params=params)
        
        if response:
            try:
                return QuoteResponse(
                    input_amount=amount,
                    output_amount=int(response.get("outputAmount", 0)),
                    price_impact=float(response.get("priceImpact", 0)),
                    fee=int(response.get("fee", 0)),
                    route=["Phoenix"],
                    estimated_gas=80000,
                    dex_name=self.name,
                    timestamp=time.time()
                )
            except (KeyError, ValueError) as e:
                self.logger.error("Error parsing Phoenix quote", error=str(e))
        
        return None
    
    async def get_pools(self, token_a: str, token_b: str) -> List[PoolInfo]:
        """Get Phoenix order books (acting as pools)."""
        # Phoenix uses order books, not AMM pools
        return []
    
    async def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get Phoenix market prices."""
        # Implementation would depend on Phoenix API
        # For now, return empty dict
        return {}


class MeteoraClient(BaseDexClient):
    """Meteora DEX client."""
    
    def __init__(self):
        super().__init__("Meteora", DexConfig.METEORA["api_url"])
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[QuoteResponse]:
        """Get Meteora quote for token swap."""
        params = {
            "inputMint": input_token,
            "outputMint": output_token,
            "amount": str(amount),
            "slippage": slippage_bps / 10000
        }
        
        response = await self._make_request("GET", "/swap/quote", params=params)
        
        if response:
            try:
                return QuoteResponse(
                    input_amount=amount,
                    output_amount=int(response.get("outAmount", 0)),
                    price_impact=float(response.get("priceImpact", 0)),
                    fee=int(response.get("fee", 0)),
                    route=["Meteora"],
                    estimated_gas=70000,
                    dex_name=self.name,
                    timestamp=time.time()
                )
            except (KeyError, ValueError) as e:
                self.logger.error("Error parsing Meteora quote", error=str(e))
        
        return None
    
    async def get_pools(self, token_a: str, token_b: str) -> List[PoolInfo]:
        """Get Meteora pools for token pair."""
        response = await self._make_request("GET", "/pools")
        
        pools = []
        if response:
            for pool_data in response:
                if ((pool_data.get("tokenA") == token_a and pool_data.get("tokenB") == token_b) or
                    (pool_data.get("tokenA") == token_b and pool_data.get("tokenB") == token_a)):
                    
                    pools.append(PoolInfo(
                        pool_id=pool_data["address"],
                        token_a=pool_data["tokenA"],
                        token_b=pool_data["tokenB"],
                        liquidity_a=int(pool_data.get("liquidityA", 0)),
                        liquidity_b=int(pool_data.get("liquidityB", 0)),
                        fee_rate=float(pool_data.get("feeRate", 0.0001)),
                        dex_name=self.name
                    ))
        
        return pools
    
    async def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """Get all Meteora prices."""
        response = await self._make_request("GET", "/pools")
        prices = {}
        
        if response:
            for pool_data in response:
                token_a = pool_data.get("tokenA")
                token_b = pool_data.get("tokenB")
                
                if (token_a in settings.monitored_tokens and 
                    token_b in settings.monitored_tokens):
                    
                    liquidity_a = Decimal(str(pool_data.get("liquidityA", 1)))
                    liquidity_b = Decimal(str(pool_data.get("liquidityB", 1)))
                    
                    if liquidity_a > 0 and liquidity_b > 0:
                        price = liquidity_b / liquidity_a
                        
                        pair_key = f"{token_a}-{token_b}"
                        prices[pair_key] = {
                            "price": price,
                            "liquidity": float(liquidity_a + liquidity_b),
                            "price_impact": 0.0,
                            "timestamp": time.time()
                        }
        
        return prices


class RateLimiter:
    """Simple rate limiter for API requests."""
    
    def __init__(self, requests_per_second: float):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request."""
        async with self._lock:
            now = time.time()
            time_since_last = now - self.last_request
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                await asyncio.sleep(sleep_time)
            
            self.last_request = time.time()


# Factory function to create DEX clients
def create_dex_clients() -> Dict[str, BaseDexClient]:
    """Create instances of all DEX clients."""
    return {
        "jupiter": JupiterClient(),
        "raydium": RaydiumClient(),
        "phoenix": PhoenixClient(),
        "meteora": MeteoraClient(),
    }
"""Configuration management for Solana Swap Agent."""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings."""
    
    # Solana RPC Configuration
    solana_rpc_url: str = Field(
        default="https://api.devnet.solana.com",
        description="Solana RPC endpoint URL"
    )
    solana_ws_url: str = Field(
        default="wss://api.devnet.solana.com",
        description="Solana WebSocket endpoint URL"
    )
    
    # Private key for wallet (base58 encoded)
    wallet_private_key: str = Field(
        description="Base58 encoded private key for trading wallet"
    )
    
    # Program configuration
    swap_agent_program_id: str = Field(
        default="BPF1111111111111111111111111111111111111111",
        description="Deployed swap agent program ID"
    )
    
    # Trading parameters
    min_profit_threshold: float = Field(
        default=0.01,
        description="Minimum profit threshold in SOL"
    )
    max_slippage_bps: int = Field(
        default=50,
        description="Maximum allowed slippage in basis points"
    )
    max_position_size: float = Field(
        default=1.0,
        description="Maximum position size in SOL"
    )
    
    # DEX configuration
    jupiter_api_url: str = Field(
        default="https://quote-api.jup.ag/v6",
        description="Jupiter API endpoint"
    )
    raydium_api_url: str = Field(
        default="https://api.raydium.io/v2",
        description="Raydium API endpoint"
    )
    
    # Monitoring tokens
    monitored_tokens: List[str] = Field(
        default=[
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        ],
        description="List of token mint addresses to monitor"
    )
    
    # Performance settings
    price_update_interval: float = Field(
        default=0.1,
        description="Price update interval in seconds"
    )
    max_concurrent_swaps: int = Field(
        default=5,
        description="Maximum number of concurrent swap operations"
    )
    
    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for caching"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    
    # Jito MEV configuration (optional)
    use_jito_bundles: bool = Field(
        default=False,
        description="Whether to use Jito bundles for MEV protection"
    )
    jito_tip_amount: Optional[float] = Field(
        default=None,
        description="Jito tip amount in SOL"
    )
    
    @validator('wallet_private_key')
    def validate_private_key(cls, v):
        """Validate private key format."""
        if not v:
            raise ValueError("Wallet private key is required")
        return v
    
    @validator('min_profit_threshold')
    def validate_profit_threshold(cls, v):
        """Validate profit threshold is positive."""
        if v <= 0:
            raise ValueError("Minimum profit threshold must be positive")
        return v
    
    @validator('max_slippage_bps')
    def validate_slippage(cls, v):
        """Validate slippage is reasonable."""
        if v < 0 or v > 1000:  # 0-10%
            raise ValueError("Slippage must be between 0 and 1000 basis points")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


class DexConfig:
    """DEX-specific configuration."""
    
    JUPITER = {
        "name": "Jupiter",
        "api_url": settings.jupiter_api_url,
        "swap_fee_bps": 0,  # Jupiter doesn't charge fees
        "supports_direct_routes": True,
    }
    
    RAYDIUM = {
        "name": "Raydium",
        "api_url": settings.raydium_api_url,
        "swap_fee_bps": 25,  # 0.25%
        "supports_direct_routes": True,
    }
    
    PHOENIX = {
        "name": "Phoenix",
        "api_url": "https://api.phoenix.trade",
        "swap_fee_bps": 5,  # 0.05%
        "supports_direct_routes": False,
    }
    
    METEORA = {
        "name": "Meteora",
        "api_url": "https://app.meteora.ag",
        "swap_fee_bps": 1,  # 0.01%
        "supports_direct_routes": True,
    }
    
    @classmethod
    def get_all_dexes(cls) -> List[dict]:
        """Get all DEX configurations."""
        return [cls.JUPITER, cls.RAYDIUM, cls.PHOENIX, cls.METEORA]
    
    @classmethod
    def get_dex_by_name(cls, name: str) -> Optional[dict]:
        """Get DEX configuration by name."""
        for dex in cls.get_all_dexes():
            if dex["name"].lower() == name.lower():
                return dex
        return None
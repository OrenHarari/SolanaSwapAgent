"""Basic tests to validate the Solana Swap Agent setup."""

import pytest
import asyncio
import os
from decimal import Decimal

# Add the offchain src directory to the path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'offchain', 'src'))

from config import Settings
from utils import calculate_profit, validate_pubkey, sol_to_lamports


class TestConfiguration:
    """Test configuration loading and validation."""
    
    def test_default_settings(self):
        """Test that default settings load correctly."""
        # Create minimal settings without requiring private key
        os.environ['WALLET_PRIVATE_KEY'] = 'test_key_for_validation'
        
        try:
            settings = Settings()
            assert settings.solana_rpc_url == "https://api.devnet.solana.com"
            assert settings.min_profit_threshold == 0.01
            assert settings.max_slippage_bps == 50
            assert len(settings.monitored_tokens) >= 3
        finally:
            # Clean up
            if 'WALLET_PRIVATE_KEY' in os.environ:
                del os.environ['WALLET_PRIVATE_KEY']
    
    def test_pubkey_validation(self):
        """Test public key validation."""
        # Valid Solana pubkey (SOL mint)
        valid_pubkey = "So11111111111111111111111111111111111111112"
        assert validate_pubkey(valid_pubkey) is True
        
        # Invalid pubkey
        invalid_pubkey = "invalid_key"
        assert validate_pubkey(invalid_pubkey) is False


class TestUtilities:
    """Test utility functions."""
    
    def test_profit_calculation(self):
        """Test profit calculation utility."""
        buy_price = Decimal("100")
        sell_price = Decimal("105")
        position_size = Decimal("1")
        
        profit = calculate_profit(buy_price, sell_price, position_size)
        assert profit == Decimal("5")
        
        # Test negative profit returns zero
        profit_negative = calculate_profit(sell_price, buy_price, position_size)
        assert profit_negative == Decimal("0")
    
    def test_sol_conversion(self):
        """Test SOL to lamports conversion."""
        sol_amount = 1.5
        lamports = sol_to_lamports(sol_amount)
        assert lamports == 1500000000  # 1.5 SOL = 1.5 * 10^9 lamports


@pytest.mark.asyncio
class TestDEXClients:
    """Test DEX client initialization (without actual API calls)."""
    
    async def test_jupiter_client_init(self):
        """Test Jupiter client initialization."""
        from dex_clients import JupiterClient
        
        client = JupiterClient()
        assert client.name == "Jupiter"
        assert "jup.ag" in client.api_url
    
    async def test_price_monitor_init(self):
        """Test price monitor initialization."""
        from price_monitor import PriceMonitor
        from dex_clients import create_dex_clients
        
        # Mock RPC client
        class MockRPCClient:
            pass
        
        dex_clients = create_dex_clients()
        monitor = PriceMonitor(MockRPCClient(), dex_clients)
        
        assert len(monitor.dex_clients) == 4  # Jupiter, Raydium, Phoenix, Meteora
        assert monitor.monitoring is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
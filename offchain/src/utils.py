"""Utility functions for the Solana Swap Agent."""

from decimal import Decimal
from typing import Union
import base58
from solders.pubkey import Pubkey


def calculate_profit(
    buy_price: Union[Decimal, float],
    sell_price: Union[Decimal, float],
    position_size: Union[Decimal, float]
) -> Decimal:
    """Calculate estimated profit from arbitrage opportunity."""
    buy_price = Decimal(str(buy_price))
    sell_price = Decimal(str(sell_price))
    position_size = Decimal(str(position_size))
    
    # Simple calculation: (sell_price - buy_price) * position_size
    # In reality, this would need to account for fees, slippage, etc.
    profit = (sell_price - buy_price) * position_size
    return max(profit, Decimal("0"))


def format_lamports(lamports: int) -> str:
    """Format lamports as SOL with proper decimal places."""
    sol = Decimal(lamports) / Decimal("1000000000")
    return f"{sol:.9f}"


def lamports_to_sol(lamports: int) -> Decimal:
    """Convert lamports to SOL."""
    return Decimal(lamports) / Decimal("1000000000")


def sol_to_lamports(sol: Union[Decimal, float]) -> int:
    """Convert SOL to lamports."""
    return int(Decimal(str(sol)) * Decimal("1000000000"))


def format_token_amount(amount: int, decimals: int = 6) -> str:
    """Format token amount with proper decimal places."""
    divisor = Decimal(10 ** decimals)
    formatted = Decimal(amount) / divisor
    return f"{formatted:.{decimals}f}"


def validate_pubkey(pubkey_str: str) -> bool:
    """Validate if a string is a valid Solana public key."""
    try:
        Pubkey.from_string(pubkey_str)
        return True
    except Exception:
        return False


def validate_private_key(private_key_str: str) -> bool:
    """Validate if a string is a valid base58 encoded private key."""
    try:
        decoded = base58.b58decode(private_key_str)
        return len(decoded) == 64  # Ed25519 private key is 64 bytes
    except Exception:
        return False


def calculate_slippage_amount(amount: int, slippage_bps: int) -> int:
    """Calculate minimum amount out accounting for slippage."""
    slippage_factor = (10000 - slippage_bps) / 10000
    return int(amount * slippage_factor)


def estimate_gas_cost(instruction_count: int, base_fee: int = 5000) -> int:
    """Estimate gas cost for a transaction."""
    # Simple estimation: base fee + (instruction_count * per_instruction_fee)
    per_instruction_fee = 1000
    return base_fee + (instruction_count * per_instruction_fee)


def truncate_address(address: str, start_chars: int = 4, end_chars: int = 4) -> str:
    """Truncate a Solana address for display."""
    if len(address) <= start_chars + end_chars:
        return address
    return f"{address[:start_chars]}...{address[-end_chars:]}"
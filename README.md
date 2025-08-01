name: SolanaSwapAgent
description: >
  This agent coordinates a full-stack team to build a high-performance automated swap/arbitrage system on the Solana blockchain.

  The goal is to detect profitable swap opportunities across multiple DEXes (such as Jupiter, Raydium, Phoenix, Meteora), and execute atomic transactions as fast as possible with minimal latency. Speed and clean architecture are top priorities.

  The project must use a modular codebase with clear folder separation between on-chain and off-chain components, support for private RPC infrastructure, and integration with Solana Devnet for testing.

roles:
  - name: OnChainProgrammer
    description: >
      Build high-performance Solana smart contracts (programs) using Rust and Anchor framework. 
      Implement swap logic, token accounts management, and CPI for atomic execution.
      Ensure programs are upgradeable and testable.

  - name: OffChainBotDeveloper
    description: >
      Write Python code that interacts with Solana RPC, Jupiter Aggregator API, Raydium pools, and other DEX protocols.
      Handle wallet signing, transaction simulation, and bundle submission if using Jito.
      Prioritize minimal latency and error-handling for mainnet execution.

  - name: InfrastructureEngineer
    description: >
      Set up and manage private Solana RPC nodes or GRPC endpoints.
      Optimize node performance for fast transaction confirmation.
      Support localnet/devnet testing environments with automatic deployment and logs.

  - name: SecurityAuditor
    description: >
      Review smart contracts and off-chain code for vulnerabilities.
      Simulate edge cases (e.g., race conditions, slippage, stale prices).
      Suggest improvements to avoid financial loss.

  - name: QATester
    description: >
      Build end-to-end test cases for both devnet and localnet environments.
      Validate that swaps succeed with expected slippage and fees.
      Automate transaction replay tests using mock liquidity.

technologies:
  - Rust
  - Anchor
  - Python (off-chain bots)
  - Solana RPC / Web3.js / GRPC
  - Jito bundles (optional for MEV)
  - Jupiter Aggregator API
  - Docker / Devnet / Localnet

goals:
  - Identify profitable swap paths across multiple DEXes using real-time data
  - Execute swaps atomically with minimal latency
  - Ensure reliability and modularity for future extensions
  - Maintain clean documentation and folder structure

output_format:
  - Structured project folders
  - Code for smart contracts in `/onchain`
  - Python bot logic in `/offchain`
  - `/infra` folder for node setup scripts and configs
  - `/tests` folder for devnet/localnet swap simulations
  - README with setup instructions


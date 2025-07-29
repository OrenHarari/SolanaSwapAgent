#!/usr/bin/env python3
"""
Simple test runner for Solana Swap Agent
Run this script to validate your setup before starting trading.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'solders', 'solana', 'anchorpy', 'aiohttp', 
        'structlog', 'pydantic', 'pytest'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ❌ {package}")
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("📦 Install them with: pip install -r offchain/requirements.txt")
        return False
    
    print("✅ All dependencies installed!\n")
    return True

def check_configuration():
    """Check if configuration is properly set up."""
    print("⚙️  Checking configuration...")
    
    env_file = Path("env.example")
    if not env_file.exists():
        print("❌ env.example file not found")
        return False
    
    print("✅ Configuration template found")
    print("📝 Remember to create .env file with your actual settings\n")
    return True

def run_basic_tests():
    """Run basic validation tests."""
    print("🧪 Running basic tests...")
    
    test_file = Path("tests/test_basic.py")
    if not test_file.exists():
        print("❌ Test file not found")
        return False
    
    try:
        # Run the tests
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            str(test_file), "-v", "--tb=short"
        ], capture_output=True, text=True, cwd=".")
        
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:", result.stderr)
        
        if result.returncode == 0:
            print("✅ All tests passed!\n")
            return True
        else:
            print("❌ Some tests failed\n")
            return False
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def check_solana_cli():
    """Check if Solana CLI is available."""
    print("🔗 Checking Solana CLI...")
    
    try:
        result = subprocess.run(['solana', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            return True
        else:
            print("❌ Solana CLI not found")
            print("📥 Install from: https://docs.solana.com/cli/install-solana-cli-tools")
            return False
    except FileNotFoundError:
        print("❌ Solana CLI not found")
        print("📥 Install from: https://docs.solana.com/cli/install-solana-cli-tools")
        return False

def main():
    """Main test runner."""
    print("🚀 Solana Swap Agent - Setup Validation")
    print("=" * 50)
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Configuration", check_configuration),
        ("Solana CLI", check_solana_cli),
        ("Basic Tests", run_basic_tests),
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        if check_func():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 Setup validation completed successfully!")
        print("\n📋 Next Steps:")
        print("1. Copy env.example to .env")
        print("2. Add your wallet private key to .env")
        print("3. Run: cd offchain && python -m src.swap_agent")
    else:
        print("⚠️  Please fix the issues above before proceeding")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
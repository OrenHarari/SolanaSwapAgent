# 🚀 מדריך הפעלה ראשונה - Solana Swap Agent

## שלב 1: הכנת הסביבה 🛠️

### א. התקנת Python Dependencies
```bash
# עבור לתיקיית הפרויקט
cd SolanaSwapAgent

# יצירת virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# או
venv\Scripts\activate     # Windows

# התקנת החבילות הנדרשות
pip install -r offchain/requirements.txt
```

### ב. התקנת Solana CLI
```bash
# Linux/Mac
curl -sSfL https://release.solana.com/v1.17.0/install | sh
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"

# Windows - הורד מהאתר הרשמי
# https://docs.solana.com/cli/install-solana-cli-tools
```

## שלב 2: יצירת ארנק Solana 🔑

### א. יצירת ארנק חדש
```bash
# יצירת ארנק חדש
solana-keygen new --outfile wallet.json

# שמירת הכתובת הציבורית (תצטרך אותה)
solana address -k wallet.json
```

### ב. קבלת SOL לפיתוח (Devnet)
```bash
# הגדרת Devnet
solana config set --url https://api.devnet.solana.com

# קבלת SOL חינמי לפיתוח
solana airdrop 2 $(solana address -k wallet.json)

# בדיקת יתרה
solana balance $(solana address -k wallet.json)
```

## שלב 3: הגדרת קונפיגורציה ⚙️

### א. יצירת קובץ .env
```bash
# העתקת קובץ הדוגמה
cp env.example .env

# עריכת הקובץ
nano .env  # או כל עורך טקסט אחר
```

### ב. הוספת המפתח הפרטי
```bash
# המרת המפתח הפרטי לפורמט base58
# אם יש לך קובץ wallet.json:
cat wallet.json | head -c 128 | xxd -r -p | base58

# או בPython:
python3 -c "
import json
import base58

# קריאת קובץ הארנק
with open('wallet.json', 'r') as f:
    keypair = json.load(f)

# המרה לbase58
private_key_bytes = bytes(keypair[:32])
private_key_base58 = base58.b58encode(private_key_bytes).decode()
print(f'WALLET_PRIVATE_KEY={private_key_base58}')
"
```

### ג. עדכון קובץ .env
```bash
# ערוך את .env והחלף:
WALLET_PRIVATE_KEY=your_actual_private_key_here
```

## שלב 4: הרצת בדיקה ראשונה 🧪

### א. בדיקת התקנה
```bash
# הרצת סקריפט הבדיקה
python run_tests.py
```

**מה הסקריפט בודק:**
- ✅ התקנת כל החבילות הנדרשות
- ✅ קיום קבצי הקונפיגורציה  
- ✅ זמינות Solana CLI
- ✅ פונקציונליות בסיסית של הקוד

### ב. בדיקת חיבור ל-Devnet
```bash
cd offchain

# בדיקה פשוטה של חיבור RPC
python3 -c "
import asyncio
from src.config import settings
from solana.rpc.async_api import AsyncClient

async def test_connection():
    client = AsyncClient(settings.solana_rpc_url)
    try:
        result = await client.get_health()
        print('✅ חיבור ל-Solana RPC הצליח')
        print(f'RPC URL: {settings.solana_rpc_url}')
    except Exception as e:
        print(f'❌ שגיאה בחיבור: {e}')
    finally:
        await client.close()

asyncio.run(test_connection())
"
```

## שלב 5: הרצת הבוט במצב ניסיון 🤖

### א. הפעלה ראשונה (ללא מסחר אמיתי)
```bash
cd offchain

# הרצה במצב debug עם logging מפורט
export LOG_LEVEL=DEBUG
export MIN_PROFIT_THRESHOLD=999999  # מניעת מסחר אמיתי

python -m src.swap_agent
```

**מה תראה:**
```
🚀 Starting Solana Swap Agent...
📊 Price monitor initialized
🔍 Monitoring 4 DEXes: Jupiter, Raydium, Phoenix, Meteora
💰 Wallet: [your_address]
📈 Checking for arbitrage opportunities...
```

### ב. בדיקת מציאת הזדמנויות
הבוט יתחיל לחפש הזדמנויות ארביטראז' אבל לא יבצע מסחר (בגלל threshold גבוה).

## שלב 6: מעקב ובדיקת ביצועים 📊

### א. לוגים ומידע
```bash
# צפייה בלוגים בזמן אמת
tail -f swap_agent.log

# בדיקת סטטיסטיקות (בטרמינל נוסף)
python3 -c "
from src.price_monitor import PriceMonitor
# הצגת נתונים על מחירים נוכחיים
"
```

### ב. בדיקת מחירים
```bash
# סקריפט בדיקה מהירה של מחירים
cd offchain
python3 -c "
import asyncio
from src.dex_clients import JupiterClient

async def check_prices():
    client = JupiterClient()
    async with client:
        # בדיקת מחיר SOL->USDC
        quote = await client.get_quote(
            'So11111111111111111111111111111111111111112',  # SOL
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
            1000000000  # 1 SOL
        )
        if quote:
            print(f'💰 Jupiter SOL->USDC: {quote.output_amount/1000000:.2f} USDC')
        else:
            print('❌ לא ניתן לקבל מחיר מJupiter')

asyncio.run(check_prices())
"
```

## שלב 7: הפעלת מסחר אמיתי (זהירות!) ⚠️

**רק לאחר שכל הבדיקות עברו בהצלחה:**

```bash
# עדכון .env למסחר אמיתי
nano .env

# שנה את:
MIN_PROFIT_THRESHOLD=0.01  # 1% רווח מינימלי
MAX_POSITION_SIZE=0.1      # עמדה מקסימלית של 0.1 SOL

# הפעלה
cd offchain
python -m src.swap_agent
```

## 🔧 פתרון בעיות נפוצות

### בעיה: "ModuleNotFoundError"
```bash
# ודא שאתה ב-virtual environment
source venv/bin/activate
pip install -r offchain/requirements.txt
```

### בעיה: "Invalid private key"
```bash
# בדוק שהמפתח הפרטי בפורמט נכון
python3 -c "
import base58
try:
    key = base58.b58decode('your_key_here')
    print(f'✅ מפתח תקין: {len(key)} bytes')
except:
    print('❌ מפתח לא תקין')
"
```

### בעיה: "Connection timeout"
```bash
# בדוק חיבור לאינטרנט ו-RPC
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' \
  https://api.devnet.solana.com
```

## 📋 רשימת בדיקות מהירה

- [ ] Python 3.8+ מותקן
- [ ] Virtual environment פעיל  
- [ ] כל החבילות מותקנות
- [ ] Solana CLI זמין
- [ ] ארנק נוצר וממומן ב-Devnet SOL
- [ ] קובץ .env מוגדר נכון
- [ ] בדיקות בסיסיות עוברות
- [ ] חיבור ל-RPC פועל
- [ ] הבוט מתחיל ומחפש הזדמנויות

---

## 🎯 מטרה: הבוט יתחיל לרוץ, יתחבר ל-DEXes השונים, ויחפש הזדמנויות ארביטראז' בזמן אמת!

**זכור:** התחל תמיד ב-Devnet עם סכומים קטנים! 🔒 
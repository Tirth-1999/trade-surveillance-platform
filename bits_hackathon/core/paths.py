from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

ARTIFACTS_DIR = ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

STUDENT_PACK = ROOT / "student-pack"
CRYPTO_MARKET = STUDENT_PACK / "crypto-market"
CRYPTO_TRADES = STUDENT_PACK / "crypto-trades"
EQUITY = STUDENT_PACK / "equity"

CRYPTO_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "LTCUSDT",
    "BATUSDT",
    "USDCUSDT",
]

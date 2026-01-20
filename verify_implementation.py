
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def verify():
    print("Verifying implementation...")
    
    # 1. Check imports
    try:
        import report_parser
        print("[Pass] report_parser imported")
    except ImportError as e:
        print(f"[Fail] report_parser import failed: {e}")
        
    try:
        import interface_frontend
        print("[Pass] interface_frontend imported (semantics only, run streamlit to test)")
    except ImportError as e:
        print(f"[Fail] interface_frontend import failed: {e}")
    except Exception:
        pass

    try:
        import report_service
        print("[Pass] report_service imported")
    except ImportError as e:
        print(f"[Fail] report_service import failed: {e}")

    # 2. Check templates
    templates = ["interactive_report_v2.html.j2", "report_print.html.j2"]
    for t in templates:
        p = Path(f"templates/{t}")
        if p.exists():
            print(f"[Pass] Template {t} exists")
        else:
            print(f"[Fail] Template {t} missing")

if __name__ == "__main__":
    verify()

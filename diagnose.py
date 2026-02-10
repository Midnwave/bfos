"""
BlockForge OS Diagnostic Tool
Run this to check for errors before starting the bot
"""

import sys
import importlib

def check_imports():
    """Check if all required imports work"""
    print("🔍 Checking imports...")
    
    required = [
        ('discord', 'discord.py'),
        ('aiosqlite', 'aiosqlite'),
    ]
    
    for module, name in required:
        try:
            importlib.import_module(module)
            print(f"  ✅ {name} - OK")
        except ImportError:
            print(f"  ❌ {name} - MISSING")
            print(f"     Install with: pip install {name}")
            return False
    
    return True

def check_files():
    """Check if all required files exist"""
    print("\n🔍 Checking files...")
    
    import os
    
    required_files = [
        'bot.py',
        'utils/config.py',
        'utils/database.py',
        'utils/colors.py',
        'cogs/terminal.py',
        'cogs/admin.py',
        'cogs/moderation.py'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - MISSING")
            all_exist = False
    
    return all_exist

def check_syntax():
    """Check for Python syntax errors"""
    print("\n🔍 Checking syntax...")
    
    files_to_check = [
        'bot.py',
        'utils/config.py',
        'utils/database.py',
        'cogs/terminal.py',
        'cogs/admin.py',
        'cogs/moderation.py'
    ]
    
    all_valid = True
    for file in files_to_check:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                compile(f.read(), file, 'exec')
            print(f"  ✅ {file}")
        except SyntaxError as e:
            print(f"  ❌ {file} - SYNTAX ERROR")
            print(f"     Line {e.lineno}: {e.msg}")
            all_valid = False
        except FileNotFoundError:
            print(f"  ⚠️  {file} - Not found")
    
    return all_valid

def check_token():
    """Check if bot token is set"""
    print("\n🔍 Checking bot token...")
    
    try:
        from utils.config import Config
        
        if Config.TOKEN == 'YOUR_BOT_TOKEN_HERE':
            print("  ❌ Bot token not set in utils/config.py")
            return False
        elif len(Config.TOKEN) < 50:
            print("  ⚠️  Bot token looks too short")
            return False
        else:
            print("  ✅ Bot token is set")
            return True
    except Exception as e:
        print(f"  ❌ Error checking token: {e}")
        return False

def main():
    """Run all diagnostics"""
    print("=" * 50)
    print("BlockForge OS Diagnostic Tool")
    print("=" * 50)
    
    checks = [
        ("Imports", check_imports),
        ("Files", check_files),
        ("Syntax", check_syntax),
        ("Token", check_token)
    ]
    
    results = []
    for name, check in checks:
        result = check()
        results.append((name, result))
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    print("=" * 50)
    
    all_pass = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:.<20} {status}")
        if not result:
            all_pass = False
    
    print("=" * 50)
    
    if all_pass:
        print("\n✅ All checks passed! Your bot should work.")
        print("Run: python bot.py")
    else:
        print("\n❌ Some checks failed. Fix the issues above before running the bot.")
    
    return all_pass

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

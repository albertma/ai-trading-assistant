"""快速测试 fundamental_analysis"""
import sys
sys.path.insert(0, '.')
from backend.routers.fundamental import router

# 手动调用
from backend.routers.fundamental import fundamental_analysis
result = fundamental_analysis('603799')
print('industry_outlook:', 'yes' if result.get('industry_outlook') else 'no')
print('financial:', 'yes' if result.get('financial_summary') else 'no')
print('sector:', result.get('sector'))
print('time: OK')

"""Profile fundamental_analysis timing - detailed"""
import sys, time
sys.path.insert(0, '.')
from backend.routers.fundamental import fundamental_analysis

# First call - includes module imports
t0 = time.time()
result = fundamental_analysis('603799')
t1 = time.time()
print(f"1st call: {t1-t0:.2f}s")

# Second call - should be cached
t2 = time.time()
result2 = fundamental_analysis('603799')
t3 = time.time()
print(f"2nd call: {t3-t2:.2f}s")

print(f"financial: {len(result2.get('financial_summary',{}).get('records',[]))} records")
print(f"industry: {'yes' if result2.get('industry_outlook') else 'no'}")

from services.benchmark_service import BenchmarkService

CODE_CPP = r"""
#include <bits/stdc++.h>
using namespace std;
int main(){ ios::sync_with_stdio(false); cin.tie(nullptr);
  long long n, s=0; if(!(cin>>n)) return 0;
  for(long long i=1;i<=n;i++) s+=i;
  cout<<s<<"\n"; return 0;
}
"""

CODE_PY = r"""
import sys
def main():
    data=sys.stdin.read().strip()
    if not data: return
    n=int(data); s=0
    for i in range(1, n+1): s+=i
    print(s)
if __name__=="__main__": main()
"""

# escolha um N que rode rápido no seu PC para o primeiro teste
INPUT = "2000000\n"  # 2e6

if __name__ == "__main__":
    svc = BenchmarkService()
    res = svc.run_benchmark(
        problem_id="sum_1_to_n",
        code_cpp=CODE_CPP,
        code_py=CODE_PY,
        input_data=INPUT,
    )
    print("benchmark salvo em:", f"benchmark_{res['problem_id']}.json")
    print("fator sugerido p/ Python:", res["adjustment_factor_python"])

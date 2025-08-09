import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from statistics import median
from subprocess import run, PIPE, CalledProcessError, TimeoutExpired

DOCKER = "docker"
PY_IMAGE = "adaptivejudge-python:latest"
CPP_IMAGE = "adaptivejudge-cpp:latest"

# limites básicos para reduzir ruído (ajuste na sua máquina)
CPU_LIMIT = "1"
MEM_LIMIT = "1g"

# 1 warm-up (descarta) + 5 execuções válidas
N_REPEATS = 5
# guarda-chuva para não travar benchmark (ex.: bug): 60s
HARD_TIMEOUT_SEC = 60.0

class ExecutionResult:
    def __init__(self, ok: bool, kind: str, elapsed: float | None, stderr: str = ""):
        self.ok = ok               # True = rodou e terminou
        self.kind = kind           # 'success' | 'tle' | 'rte' | 'stack_overflow' | 'ce'
        self.elapsed = elapsed     # tempo (s) quando ok=True
        self.stderr = stderr

def _sh(cmd: list[str], timeout: float | None = None) -> tuple[int, str, str]:
    """Executa um comando e retorna (returncode, stdout, stderr)."""
    p = run(cmd, stdout=PIPE, stderr=PIPE, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr

def _ensure_image(tag: str, dockerfile_path: str):
    # se a imagem não existir, faz o build
    code, _, _ = _sh([DOCKER, "image", "inspect", tag])
    if code != 0:
        build_dir = str(Path(dockerfile_path).parent)
        df_name = Path(dockerfile_path).name
        print(f"[build] {tag} (Dockerfile: {dockerfile_path})")
        code, out, err = _sh([DOCKER, "build", "-t", tag, "-f", df_name, build_dir])
        if code != 0:
            raise RuntimeError(f"Falha ao construir {tag}:\n{out}\n{err}")

def _percentile(values: list[float], p: float) -> float:
    """Percentil simples (p em [0,100])."""
    if not values:
        return float("nan")
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(vals) - 1)
    if f == c:
        return vals[f]
    d0 = vals[f] * (c - k)
    d1 = vals[c] * (k - f)
    return d0 + d1

def _classify_stderr(stderr: str) -> str:
    s = stderr.lower()
    if "maximum recursion depth exceeded" in s or "recursionerror" in s:
        return "stack_overflow"
    if "stack overflow" in s:
        return "stack_overflow"
    return "rte"

def _docker_run(image: str, workdir: Path, command: str, input_bytes: bytes | None,
                timeout: float) -> ExecutionResult:
    """
    Executa `command` no container.
    Mede tempo no host (wall-clock).
    Descarta stdout e usa stderr para classificar erro.
    """
    base = [
        DOCKER, "run", "--rm", "-i",
        f"--cpus={CPU_LIMIT}", f"--memory={MEM_LIMIT}",
        "-v", f"{str(workdir)}:/work",
        image, "bash", "-lc", command
    ]
    t0 = time.perf_counter()
    try:
        p = run(base, input=input_bytes, stdout=PIPE, stderr=PIPE, timeout=timeout)
    except TimeoutExpired:
        return ExecutionResult(False, "tle", None, "")
    elapsed = time.perf_counter() - t0

    if p.returncode == 0:
        return ExecutionResult(True, "success", elapsed, p.stderr.decode() if isinstance(p.stderr, bytes) else p.stderr)
    else:
        # 139 costuma ser segfault; trato como RTE genérico
        kind = "rte" if p.returncode != 124 else "tle"
        kind = _classify_stderr(p.stderr.decode() if isinstance(p.stderr, bytes) else p.stderr) if kind == "rte" else kind
        return ExecutionResult(False, kind, None, p.stderr.decode() if isinstance(p.stderr, bytes) else p.stderr)

class BenchmarkService:
    """
    Serviço que:
      - garante imagens
      - compila C++ (fora da medição)
      - faz 1 warm-up + 5 execuções
      - calcula median/p10/p90/IQR
      - classifica TLE/RTE/stack_overflow
      - salva JSON com o resultado
    """
    def __init__(self,
                 dockerfile_python: str = "docker/Dockerfile.python",
                 dockerfile_cpp: str = "docker/Dockerfile.cpp",
                 hard_timeout: float = HARD_TIMEOUT_SEC):
        self.dockerfile_python = dockerfile_python
        self.dockerfile_cpp = dockerfile_cpp
        self.hard_timeout = hard_timeout

    def _prepare_workspace(self, code_py: str, code_cpp: str, input_data: str) -> Path:
        work = Path(tempfile.mkdtemp(prefix="acj_bench_"))
        (work / "solution.py").write_text(code_py)
        (work / "solution.cpp").write_text(code_cpp)
        (work / "input.txt").write_text(input_data)
        return work

    def _compile_cpp(self, work: Path) -> None:
        cmd = "g++ -O2 -std=gnu++17 /work/solution.cpp -o /work/a.out"
        res = _docker_run(CPP_IMAGE, work, cmd, None, timeout=self.hard_timeout)
        if not res.ok:
            raise RuntimeError(f"Erro ao compilar C++: {res.kind}\n{res.stderr}")

    def _run_python_once(self, work: Path) -> ExecutionResult:
        cmd = "python3 /work/solution.py < /work/input.txt > /dev/null"
        return _docker_run(PY_IMAGE, work, cmd, None, timeout=self.hard_timeout)

    def _run_cpp_once(self, work: Path) -> ExecutionResult:
        cmd = "/work/a.out < /work/input.txt > /dev/null"
        return _docker_run(CPP_IMAGE, work, cmd, None, timeout=self.hard_timeout)

    def _repeated(self, runner, work: Path) -> dict:
        # aquecimento
        _ = runner(work)
        samples = []
        statuses = []
        for _i in range(N_REPEATS):
            r = runner(work)
            statuses.append(r.kind)
            if r.ok and r.elapsed is not None:
                samples.append(r.elapsed)

        agg = {}
        agg["runs"] = samples
        agg["counts"] = {k: statuses.count(k) for k in set(statuses)}
        if samples:
            agg["median"] = median(samples)
            p10 = _percentile(samples, 10)
            p90 = _percentile(samples, 90)
            p25 = _percentile(samples, 25)
            p75 = _percentile(samples, 75)
            agg["p10"] = p10
            agg["p90"] = p90
            agg["iqr"] = p75 - p25
            agg["status"] = "stable" if (p75 - p25) <= 0.05 * agg["median"] else "unstable"
        else:
            agg["median"] = None
            agg["p10"] = None
            agg["p90"] = None
            agg["iqr"] = None
            agg["status"] = "no_success"
        return agg

    def run_benchmark(self, problem_id: str, code_cpp: str, code_py: str, input_data: str,
                      factor_cap: float | None = 12.0) -> dict:
        """
        Roda o benchmark e escreve "benchmark_{problem_id}.json" no diretório atual.
        """
        _ensure_image(PY_IMAGE, self.dockerfile_python)
        _ensure_image(CPP_IMAGE, self.dockerfile_cpp)

        work = self._prepare_workspace(code_py, code_cpp, input_data)
        try:
            # compilo C++ fora da janela de medição
            self._compile_cpp(work)

            py = self._repeated(self._run_python_once, work)
            cp = self._repeated(self._run_cpp_once, work)

            # fator usando medianas quando possível
            factor = None
            notes = []
            if py["median"] is not None and cp["median"] is not None:
                factor = py["median"] / cp["median"] if cp["median"] > 0 else None
            elif py["median"] is None and cp["median"] is not None:
                notes.append("Python sem execuções bem-sucedidas (dados censurados).")
                if factor_cap is not None:
                    factor = factor_cap
                    notes.append(f"Fator truncado: {factor_cap}x.")
            else:
                notes.append("Bench incompleto: não foi possível calcular o fator.")

            result = {
                "problem_id": problem_id,
                "docker": {"cpus": CPU_LIMIT, "memory": MEM_LIMIT},
                "repeats": N_REPEATS,
                "python": py,
                "cpp": cp,
                "base_time_cpp": cp["median"],
                "adjustment_factor_python": factor,
                "notes": notes,
                "version": 1
            }

            out_path = Path(f"benchmark_{problem_id}.json")
            out_path.write_text(json.dumps(result, indent=2))
            return result
        finally:
            # deixo o workspace em /tmp para inspeção; se quiser remover, descomente:
            # import shutil; shutil.rmtree(work, ignore_errors=True)
            pass

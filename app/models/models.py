from sqlalchemy import (
    Column, Integer, BigInteger, Text, Boolean, TIMESTAMP, Float,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.core.db import Base


class Problem(Base):
    __tablename__ = "problems"
    id = Column(Integer, primary_key=True)
    problem_id = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    max_input_size = Column(BigInteger)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    test_cases = relationship("TestCase", back_populates="problem", cascade="all,delete")
    benchmarks = relationship("Benchmark", back_populates="problem", cascade="all,delete")


class TestCase(Base):
    __tablename__ = "test_cases"
    id = Column(Integer, primary_key=True)
    problem_id = Column(Text, ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False)
    description = Column(Text)
    input_data = Column(Text, nullable=False)
    expected_output = Column(Text)            # pode ser NULL para problemas "output-agnostic"
    weight = Column(Integer, nullable=False, default=1)
    is_max_case = Column(Boolean, nullable=False, default=False)

    problem = relationship("Problem", back_populates="test_cases")


class Benchmark(Base):
    __tablename__ = "benchmarks"
    id = Column(Integer, primary_key=True)
    problem_id = Column(Text, ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False)
    date_run = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # Medianas do maior caso
    base_time_cpp = Column(Float)             # mediana C++ (maior caso)
    cpp_median = Column(Float)
    python_median = Column(Float)
    adjustment_factor_python = Column(Float)

    # Amostras brutas (maior caso)
    python_runs = Column(JSONB)               # lista de floats
    cpp_runs = Column(JSONB)                  # lista de floats
    status_python = Column(Text)
    status_cpp = Column(Text)
    notes = Column(JSONB)                     # lista de strings

    # Espaço para evolução (buckets)
    small_summary = Column(JSONB)
    medium_summary = Column(JSONB)
    large_summary = Column(JSONB)

    problem = relationship("Problem", back_populates="benchmarks")


class ProblemBenchmarkActive(Base):
    __tablename__ = "problem_benchmark_active"
    problem_id = Column(Text, ForeignKey("problems.problem_id", ondelete="CASCADE"), primary_key=True)
    benchmark_id = Column(Integer, ForeignKey("benchmarks.id", ondelete="RESTRICT"), nullable=False)
    set_by = Column(Text)
    set_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    problem_id = Column(Text, ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False)
    language = Column(Text, nullable=False)           # 'cpp' | 'python' | ...
    source_code = Column(Text, nullable=False)
    execution_time_total = Column(Float)              # defina se é soma ou pior caso
    result = Column(Text)                             # 'success','tle','wa','rte','so','ce','mle'
    executed_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # Auditoria do benchmark usado
    benchmark_id_used = Column(Integer, ForeignKey("benchmarks.id", ondelete="SET NULL"))
    base_time_cpp_used = Column(Float)
    factor_used = Column(Float)
    time_limit_applied = Column(Float)


class SubmissionResult(Base):
    __tablename__ = "submission_results"
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    passed = Column(Boolean, nullable=False)
    execution_time = Column(Float)
    error_type = Column(Text)                         # 'WA','TLE','RTE','SO','CE','MLE' ou NULL
    stdout_preview = Column(Text)
    stderr_preview = Column(Text)

    __table_args__ = (
        UniqueConstraint("submission_id", "test_case_id", name="uq_submission_results"),
    )


class LanguagePolicy(Base):
    __tablename__ = "language_policy"
    language = Column(Text, primary_key=True)         # 'cpp','python',...
    factor_floor = Column(Float, nullable=False, default=1.0)
    factor_cap = Column(Float, nullable=False, default=12.0)
    cpu_limit = Column(Text, nullable=False, default='1')
    mem_limit = Column(Text, nullable=False, default='1g')
    stack_limit = Column(Text)                        # se aplicar (ulimit)
    iqr_stable_pct = Column(Float, nullable=False, default=0.05)  # 5%

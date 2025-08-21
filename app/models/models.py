from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON, DateTime, func

class Base(DeclarativeBase): pass

class Problem(Base):
    __tablename__ = "problems"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)

class TestCase(Base):
    __tablename__ = "test_cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    input_data: Mapped[str] = mapped_column(String, nullable=False)
    is_max_case: Mapped[bool] = mapped_column(Boolean, default=False)

class Benchmark(Base):
    __tablename__ = "benchmarks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey("problems.id"), index=True)
    base_time_cpp: Mapped[float] = mapped_column(Float)
    reference_python_time: Mapped[float] = mapped_column(Float)
    adjustment_factor_python: Mapped[float] = mapped_column(Float)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class ActiveBenchmark(Base):
    __tablename__ = "active_benchmarks"
    problem_id: Mapped[str] = mapped_column(String, primary_key=True)
    benchmark_id: Mapped[int] = mapped_column(Integer, nullable=False)

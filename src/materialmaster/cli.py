import argparse
import json
from pathlib import Path

from materialmaster.domain.engine import analyze
from materialmaster.domain.generator import write_dataset
from materialmaster.domain.validation import parse_upload, validate_rows
from materialmaster.evaluation.benchmark import benchmark
from materialmaster.services.storage import Base, database
from materialmaster.services.workflow import ingest, scan


def main():
    parser = argparse.ArgumentParser(description="MaterialMaster AI — deterministic material data quality")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Create a synthetic dataset and separate ground truth")
    generate.add_argument("--count", type=int, default=100000)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--output", type=Path, default=Path("data/generated/100k"))
    validate = commands.add_parser(
        "validate", help="Validate a file; exit 2 for invalid rows, 0 if schema-valid"
    )
    validate.add_argument("file", type=Path)
    validate.add_argument("--output", type=Path, default=Path("validation-report.json"))
    validate.add_argument("--analyze", action="store_true", help="Include computational findings")
    load = commands.add_parser("import", help="Persist validation, rows and optional scan")
    load.add_argument("file", type=Path)
    load.add_argument("--database-url", default=None)
    load.add_argument("--scan", action="store_true")
    bench = commands.add_parser("benchmark", help="Measure synthetic precision, recall and runtime")
    bench.add_argument("--count", type=int, default=100000)
    bench.add_argument("--seed", type=int, default=42)
    bench.add_argument("--output", type=Path, default=Path("output/benchmark"))
    bench.add_argument("--model-path", default=None)
    args = parser.parse_args()
    if args.command == "generate":
        result = write_dataset(args.output, args.count, args.seed)
    elif args.command == "benchmark":
        result = benchmark(args.count, args.seed, args.output, args.model_path)
    else:
        try:
            rows = parse_upload(args.file.read_bytes(), args.file.suffix.lower())
        except (ValueError, UnicodeError, OSError) as error:
            parser.exit(2, f"Cannot read input: {error}\n")
        if args.command == "validate":
            report = validate_rows(rows)
            result = report.model_dump(mode="json", exclude={"records"})
            if args.analyze:
                findings, metadata = analyze(report.records)
                result.update(findings=[item.model_dump(mode="json") for item in findings], metadata=metadata)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "total": report.total,
                        "valid": report.valid_count,
                        "invalid": report.invalid_count,
                        "output": str(args.output),
                    }
                )
            )
            raise SystemExit(2 if report.invalid_count else 0)
        engine, sessions = database(args.database_url)
        Base.metadata.create_all(engine)
        with sessions.begin() as session:
            result = ingest(session, rows, args.file.name)
            if args.scan:
                result["scan"] = scan(session, result["dataset_id"])
        engine.dispose()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

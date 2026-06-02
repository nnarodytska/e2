"""
Generate evaluation test cases from the book, using the Anthropic API.

For each requested chapter, the model reads the chapter text and writes Q&A test cases in
the book_eval.json schema. Useful for growing the eval set.

Usage:
    python3 gen_book_eval.py --chapter CPU --chapter Memory -n 4 -o book_eval_generated.json

Needs ANTHROPIC_API_KEY (in env or .env).
"""
import argparse
import json

from dotenv import load_dotenv

import eval_harness

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Generate book-grounded eval cases")
    parser.add_argument("--chapter", "-c", action="append", required=True,
                        help="Chapter title to generate from (repeatable), e.g. CPU")
    parser.add_argument("-n", type=int, default=4, help="Cases per chapter (default 4)")
    parser.add_argument("--out", "-o", default="book_eval_generated.json",
                        help="Output JSON file")
    args = parser.parse_args()

    client, chapters, _index, _titles, _skills = eval_harness.setup()

    all_cases = []
    for chapter in args.chapter:
        cases = eval_harness.generate_cases(client, chapter, chapters, n=args.n)
        print(f"{chapter}: generated {len(cases)} cases")
        all_cases.extend(cases)

    with open(args.out, "w") as f:
        json.dump(all_cases, f, indent=2)
    print(f"\nWrote {len(all_cases)} cases to {args.out}")


if __name__ == "__main__":
    main()

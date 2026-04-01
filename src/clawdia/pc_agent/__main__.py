from __future__ import annotations

import argparse
import asyncio
import os
import sys

from clawdia.pc_agent.agent import ComputerUseAgent


def main():
    parser = argparse.ArgumentParser(description="Clawdia PC Agent — Computer Use")
    parser.add_argument("--goal", required=True, help="The goal to accomplish")
    parser.add_argument("--context", default="", help="Knowledge base context")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY", ""), help="Anthropic API key")
    parser.add_argument("--model", default="claude-sonnet-4-6-20250514", help="Model to use")
    parser.add_argument("--max-iterations", type=int, default=30, help="Max iterations")
    args = parser.parse_args()

    if not args.api_key:
        print('{"success": false, "summary": "ANTHROPIC_API_KEY not set"}')
        sys.exit(1)

    agent = ComputerUseAgent(
        api_key=args.api_key,
        model=args.model,
        max_iterations=args.max_iterations,
    )

    result = asyncio.run(agent.run(args.goal, args.context))
    print(result.to_json())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()

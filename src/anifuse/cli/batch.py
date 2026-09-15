"""Custom TyperGroup enabling batch execution of chained subcommands within a single process."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any

import typer.core as tc


class BatchTyperGroup(tc.TyperGroup):
    """TyperGroup supporting delimiter-based multi-command chaining in a single invocation."""

    delimiter: str = "stitch"

    def main(
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        **extra: Any,
    ) -> Any:
        """Parse and sequentially execute chained command segments without process restart."""
        raw_args = list(sys.argv[1:]) if args is None else list(args)

        if raw_args and raw_args.count(self.delimiter) > 1:
            chunks: list[list[str]] = []
            current_chunk: list[str] = []

            for token in raw_args:
                if token == self.delimiter and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = [self.delimiter]
                else:
                    current_chunk.append(token)

            if current_chunk:
                chunks.append(current_chunk)

            last_result: Any = None
            for idx, chunk in enumerate(chunks):
                is_last = idx == len(chunks) - 1
                try:
                    last_result = super().main(
                        args=chunk,
                        prog_name=prog_name,
                        complete_var=complete_var,
                        standalone_mode=is_last if standalone_mode else False,
                        **extra,
                    )
                except SystemExit as exc:
                    if exc.code != 0 or is_last:
                        raise

            return last_result

        return super().main(
            args=raw_args,
            prog_name=prog_name,
            complete_var=complete_var,
            standalone_mode=standalone_mode,
            **extra,
        )

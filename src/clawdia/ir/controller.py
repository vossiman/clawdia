from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class IRController:
    """Controls IR sending/receiving via ir-ctl subprocess."""

    # Samsung IR protocol timing (microseconds)
    _SAMSUNG_HEADER_MARK = 4500
    _SAMSUNG_HEADER_SPACE = 4500
    _SAMSUNG_BIT_MARK = 560
    _SAMSUNG_ONE_SPACE = 1690
    _SAMSUNG_ZERO_SPACE = 560

    @staticmethod
    def generate_samsung_code(hex_code: int) -> str:
        """Convert a 32-bit Samsung IR hex code to ir-ctl raw pulse/space format.

        Example: generate_samsung_code(0xE0E040BF) -> "+4500 -4500 +560 -1690 ..."
        """
        parts = [
            f"+{IRController._SAMSUNG_HEADER_MARK}",
            f"-{IRController._SAMSUNG_HEADER_SPACE}",
        ]
        for i in range(31, -1, -1):
            bit = (hex_code >> i) & 1
            parts.append(f"+{IRController._SAMSUNG_BIT_MARK}")
            if bit:
                parts.append(f"-{IRController._SAMSUNG_ONE_SPACE}")
            else:
                parts.append(f"-{IRController._SAMSUNG_ZERO_SPACE}")
        # Trailing mark
        parts.append(f"+{IRController._SAMSUNG_BIT_MARK}")
        return " ".join(parts)

    def generate_code_file(self, command: str, hex_code: int, description: str = "") -> Path:
        """Generate an IR code file from a Samsung hex scancode and update metadata."""
        raw = self.generate_samsung_code(hex_code)
        path = self.codes_dir / f"{command}.txt"
        path.write_text(raw + "\n")
        if description:
            self._meta[command] = description
            self._save_meta()
        logger.info("Generated IR code: %s (0x%08X) -> %s", command, hex_code, path)
        return path

    def __init__(self, device_send: str = "/dev/lirc0", codes_dir: str = "ir-codes"):
        self.device_send = device_send
        self.codes_dir = Path(codes_dir)
        self.codes_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self.codes_dir / "commands.json"
        self._meta: dict[str, str] = self._load_meta()

    def _load_meta(self) -> dict[str, str]:
        if self._meta_path.is_file():
            return json.loads(self._meta_path.read_text())
        return {}

    def _save_meta(self) -> None:
        self._meta_path.write_text(json.dumps(self._meta, indent=2) + "\n")

    def list_commands(self) -> list[str]:
        """List all available IR command names."""
        return sorted(p.stem for p in self.codes_dir.glob("*.txt"))

    def list_commands_with_descriptions(self) -> list[tuple[str, str]]:
        """List commands with their descriptions."""
        return [
            (name, self._meta.get(name, ""))
            for name in self.list_commands()
        ]

    def has_command(self, command: str) -> bool:
        """Check if an IR command code file exists."""
        return (self.codes_dir / f"{command}.txt").is_file()

    def get_code_path(self, command: str) -> Path | None:
        """Get the path to an IR code file."""
        path = self.codes_dir / f"{command}.txt"
        return path if path.is_file() else None

    def set_description(self, command: str, description: str) -> None:
        """Set the description for a command."""
        self._meta[command] = description
        self._save_meta()

    async def send(self, command: str, repeat: int = 1) -> bool:
        """Send an IR command via ir-ctl.

        Returns True if successful, False otherwise.
        """
        code_path = self.get_code_path(command)
        if code_path is None:
            logger.warning("IR command '%s' not found in %s", command, self.codes_dir)
            return False

        for i in range(repeat):
            try:
                process = await asyncio.create_subprocess_exec(
                    "ir-ctl",
                    "-d", self.device_send,
                    f"--send={code_path}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    logger.error(
                        "ir-ctl send failed (code %d): %s",
                        process.returncode,
                        stderr.decode().strip(),
                    )
                    return False

                if repeat > 1 and i < repeat - 1:
                    await asyncio.sleep(0.1)

            except FileNotFoundError:
                logger.error("ir-ctl not found. Install v4l-utils: sudo apt install v4l-utils")
                return False

        logger.info("IR command '%s' sent successfully (repeat=%d)", command, repeat)
        return True

    async def record(self, command: str, timeout: float = 10.0) -> bool:
        """Record an IR code from the receiver.

        Returns True if a code was captured, False on timeout/error.
        """
        code_path = self.codes_dir / f"{command}.txt"

        try:
            process = await asyncio.create_subprocess_exec(
                "ir-ctl",
                "-d", self.device_send.replace("lirc0", "lirc1"),
                "-r", "--one-shot",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            if process.returncode == 0 and stdout:
                code_path.write_bytes(stdout)
                logger.info("IR code recorded: %s -> %s", command, code_path)
                return True

            logger.warning("IR recording returned no data for '%s'", command)
            return False

        except asyncio.TimeoutError:
            process.kill()
            logger.warning("IR recording timed out for '%s'", command)
            return False
        except FileNotFoundError:
            logger.error("ir-ctl not found. Install v4l-utils.")
            return False

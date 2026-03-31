from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PCResult:
    success: bool
    output: str


class PCController:
    """Executes commands on a remote Linux PC via SSH."""

    def __init__(
        self,
        ssh_host: str,
        ssh_user: str,
        ssh_key_path: str = "~/.ssh/id_ed25519",
        agent_path: str = "~/clawdia-agent",
    ):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_key_path = ssh_key_path
        self.agent_path = agent_path

    def _build_ssh_cmd(self, remote_cmd: str) -> list[str]:
        return [
            "ssh",
            "-i", self.ssh_key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            f"{self.ssh_user}@{self.ssh_host}",
            f"DISPLAY=:0 {remote_cmd}",
        ]

    async def _run_ssh(self, remote_cmd: str, timeout: float = 30.0) -> PCResult:
        cmd = self._build_ssh_cmd(remote_cmd)
        logger.info("SSH command: %s", " ".join(cmd))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error("SSH command timed out after %.0fs", timeout)
            return PCResult(success=False, output="Command timed out")
        except Exception as e:
            logger.exception("SSH command failed")
            return PCResult(success=False, output=str(e))

        if process.returncode == 0:
            return PCResult(success=True, output=stdout.decode().strip())
        else:
            error = stderr.decode().strip() or stdout.decode().strip()
            return PCResult(success=False, output=error)

    async def run_shell(self, command: str) -> PCResult:
        """Run a shell command on the remote PC.

        GUI apps are automatically backgrounded so SSH doesn't block waiting
        for them to exit.
        """
        # Background GUI app launches so SSH returns immediately
        gui_apps = {"firefox", "chromium", "google-chrome", "emby", "vlc", "mpv",
                    "nautilus", "thunar", "nemo", "xdg-open", "libreoffice",
                    "gimp", "inkscape", "code", "gedit", "xterm", "evince"}
        first_word = command.strip().split()[0].split("/")[-1] if command.strip() else ""
        if first_word in gui_apps and "nohup" not in command and "&" not in command:
            command = f"nohup {command} >/dev/null 2>&1 & sleep 0.5"
        return await self._run_ssh(command)

    async def run_computer_use(self, goal: str, knowledge_context: str) -> PCResult:
        """Invoke the PC agent for GUI interaction via computer use."""
        escaped_goal = goal.replace("'", "'\\''")
        escaped_ctx = knowledge_context.replace("'", "'\\''")
        remote_cmd = (
            f"cd {self.agent_path} && "
            f"python -m pc_agent --goal '{escaped_goal}' --context '{escaped_ctx}'"
        )
        result = await self._run_ssh(remote_cmd, timeout=300.0)

        if result.success:
            try:
                data = json.loads(result.output)
                return PCResult(success=data.get("success", False), output=data.get("summary", result.output))
            except json.JSONDecodeError:
                return result
        return result

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Librespot systemd service name pattern: device "clawdia-gernot" -> service "librespot-gernot"
_LIBRESPOT_PREFIX = "clawdia-"
_SERVICE_PREFIX = "librespot-"


def _service_name_for_device(device_name: str) -> str | None:
    """Derive the systemd service name from a librespot device name."""
    if device_name.startswith(_LIBRESPOT_PREFIX):
        suffix = device_name[len(_LIBRESPOT_PREFIX):]
        return f"{_SERVICE_PREFIX}{suffix}"
    return None


async def _restart_librespot(device_name: str) -> bool:
    """Restart the librespot systemd user service for a device."""
    service = _service_name_for_device(device_name)
    if not service:
        logger.warning("Cannot determine systemd service for device '%s'", device_name)
        return False

    logger.info("Restarting %s.service for device '%s'", service, device_name)
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "--user", "restart", service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            logger.info("Successfully restarted %s", service)
            return True
        else:
            logger.error("Failed to restart %s: %s", service, stderr.decode().strip())
            return False
    except asyncio.TimeoutError:
        logger.error("Timed out restarting %s", service)
        return False
    except Exception:
        logger.exception("Error restarting %s", service)
        return False


async def ensure_spotify_device(
    controller,
    device_name: str,
    max_retries: int = 2,
    wait_after_restart: float = 5.0,
) -> bool:
    """Check if a Spotify device is visible; restart librespot if not.

    Returns True if the device is available (possibly after restart).
    """
    if await controller.check_device_available():
        return True

    logger.warning("Spotify device '%s' not found, attempting librespot restart", device_name)

    for attempt in range(1, max_retries + 1):
        restarted = await _restart_librespot(device_name)
        if not restarted:
            return False

        await asyncio.sleep(wait_after_restart)

        if await controller.check_device_available():
            logger.info("Device '%s' is back after restart (attempt %d)", device_name, attempt)
            return True

        logger.warning(
            "Device '%s' still not visible after restart attempt %d/%d",
            device_name, attempt, max_retries,
        )

    return False


async def startup_health_check(
    *,
    music_controllers: dict[int, object] | None = None,
    pc=None,
    ir=None,
) -> list[str]:
    """Run health checks on all services. Returns list of issues (empty = all good)."""
    issues: list[str] = []

    # Check Spotify devices
    if music_controllers:
        for chat_id, mc in music_controllers.items():
            device_name = mc._device_name
            ok = await ensure_spotify_device(mc, device_name)
            if ok:
                logger.info("Spotify device '%s' (chat %d): OK", device_name, chat_id)
            else:
                msg = f"Spotify device '{device_name}' offline (chat {chat_id})"
                logger.error(msg)
                issues.append(msg)

    # Check PC reachability
    if pc:
        try:
            result = await pc.run_shell("echo ok")
            if result.success and "ok" in result.output:
                logger.info("PC remote control: OK")
            else:
                msg = f"PC remote control: unreachable ({result.output})"
                logger.error(msg)
                issues.append(msg)
        except Exception as e:
            msg = f"PC remote control: error ({e})"
            logger.error(msg)
            issues.append(msg)

    # Check IR device
    if ir:
        import os
        device_path = ir._device_send if hasattr(ir, "_device_send") else None
        if device_path and not os.path.exists(device_path):
            msg = f"IR device not found: {device_path}"
            logger.error(msg)
            issues.append(msg)
        else:
            logger.info("IR device: OK")

    return issues

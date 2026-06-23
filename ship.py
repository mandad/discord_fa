"""Ship position via the existing ship-position.py script (public mfphub AIS feed, no secret).

Calls `python3 ship-position.py --json --ship-name <NAME>` as a subprocess and parses the
JSON fix. Returns the script's dict, which includes lat, lon, utc, sog_kt, cog, heading,
_age_hours, _stale, _source.
"""
from __future__ import annotations

import asyncio
import json

import config


async def get_position(script_path: str = config.SHIP_SCRIPT_PATH,
                       ship_name: str = config.SHIP_NAME,
                       timeout: float = 60.0) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "python3", script_path, "--json", "--ship-name", ship_name,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()  # reap the killed process
        raise RuntimeError(f"ship-position.py timed out after {timeout:.0f}s")
    if proc.returncode != 0:
        raise RuntimeError(f"ship-position.py failed (rc={proc.returncode}): {err.decode().strip()}")
    try:
        return json.loads(out.decode())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"could not parse ship-position.py output: {e}\n{out.decode()[:300]}")


if __name__ == "__main__":  # smoke test
    async def _main():
        data = await get_position()
        print(json.dumps(data, indent=2))

    asyncio.run(_main())

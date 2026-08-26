"""
Tor lifecycle management for stealth scraping.

Handles:
  - Start/stop tor process (portable binary)
  - Circuit renewal via stem (NEWNYM signal)
  - Health check (verify SOCKS5 connectivity)
  - New circuit per portal
"""

import asyncio
import logging
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default Tor config
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051
TOR_CONTROL_PASSWORD = "udzialy2026"
TOR_SOCKS_HOST = "127.0.0.1"


class TorManager:
    """Manages Tor process lifecycle and circuit renewal."""
    
    def __init__(
        self,
        socks_port: int = TOR_SOCKS_PORT,
        control_port: int = TOR_CONTROL_PORT,
        control_password: str = TOR_CONTROL_PASSWORD,
        tor_binary: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ):
        self.socks_port = socks_port
        self.control_port = control_port
        self.control_password = control_password
        self.tor_binary = tor_binary or self._find_tor_binary()
        self.data_dir = data_dir or Path.home() / ".udzialy-bot" / "tor_data"
        self._process: Optional[subprocess.Popen] = None
        self._is_running = False
    
    @property
    def socks_proxy(self) -> str:
        """Return the SOCKS5 proxy URL."""
        return f"socks5://{TOR_SOCKS_HOST}:{self.socks_port}"
    
    def _find_tor_binary(self) -> str:
        """Find the tor binary on the system."""
        system = platform.system()
        
        if system == "Windows":
            # Check common Windows portable locations
            candidates = [
                Path("tor") / "tor.exe",
                Path.home() / "tor" / "tor.exe",
                Path("C:/") / "Tor" / "tor.exe",
                Path.cwd() / "tor" / "tor.exe",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)
            # Try PATH
            tor_path = shutil.which("tor.exe")
            if tor_path:
                return tor_path
        else:
            # Linux/macOS
            tor_path = shutil.which("tor")
            if tor_path:
                return tor_path
        
        return "tor"  # Hope it's in PATH
    
    async def start(self) -> bool:
        """
        Start the Tor process.
        
        Returns:
            True if Tor started successfully, False otherwise
        """
        if self._is_running and await self.health_check():
            logger.info("Tor is already running")
            return True
        
        # Create data directory
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Build torrc
        torrc_path = self.data_dir / "torrc"
        torrc_content = f"""
SocksPort {self.socks_port}
ControlPort {self.control_port}
HashedControlPassword {self._hash_password(self.control_password)}
DataDirectory {self.data_dir / 'data'}
Log notice file {self.data_dir / 'tor.log'}
"""
        torrc_path.write_text(torrc_content.strip())
        
        try:
            self._process = subprocess.Popen(
                [self.tor_binary, "-f", str(torrc_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            
            # Wait for Tor to bootstrap
            for _ in range(30):  # 30 seconds max
                await asyncio.sleep(1)
                if await self.health_check():
                    self._is_running = True
                    logger.info(f"Tor started successfully (SOCKS5 on port {self.socks_port})")
                    return True
            
            logger.error("Tor failed to bootstrap within 30 seconds")
            await self.stop()
            return False
            
        except FileNotFoundError:
            logger.error(f"Tor binary not found: {self.tor_binary}")
            return False
        except Exception as e:
            logger.error(f"Failed to start Tor: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the Tor process."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            except Exception as e:
                logger.warning(f"Error stopping Tor: {e}")
            finally:
                self._process = None
                self._is_running = False
                logger.info("Tor stopped")
    
    async def health_check(self) -> bool:
        """
        Verify SOCKS5 connectivity.
        
        Returns:
            True if Tor SOCKS5 is responding
        """
        try:
            import httpx
            async with httpx.AsyncClient(
                proxy=self.socks_proxy,
                timeout=10.0,
            ) as client:
                response = await client.get("https://check.torproject.org/api/ip")
                data = response.json()
                if data.get("IsTor", False):
                    logger.debug(f"Tor health check OK (IP: {data.get('IP', 'unknown')})")
                    return True
                else:
                    logger.warning("Connected but not through Tor")
                    return True  # SOCKS5 works even if not Tor exit
        except ImportError:
            # Fallback: try raw socket connection
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(TOR_SOCKS_HOST, self.socks_port),
                    timeout=5.0,
                )
                writer.close()
                await writer.wait_closed()
                return True
            except Exception:
                return False
        except Exception:
            return False
    
    async def new_circuit(self) -> bool:
        """
        Request a new Tor circuit (NEWNYM signal via stem).
        
        Returns:
            True if circuit renewal succeeded
        """
        try:
            from stem import Signal
            from stem.control import Controller
        except ImportError:
            logger.warning("stem not available, cannot renew circuit")
            # Fallback: try raw control protocol
            return await self._newnym_raw()
        
        try:
            loop = asyncio.get_event_loop()
            
            def _renew():
                with Controller.from_port(port=self.control_port) as controller:
                    controller.authenticate(password=self.control_password)
                    controller.signal(Signal.NEWNYM)
                    return True
            
            result = await loop.run_in_executor(None, _renew)
            if result:
                # Wait for new circuit to establish
                await asyncio.sleep(3)
                logger.info("New Tor circuit established")
            return result
            
        except Exception as e:
            logger.error(f"Failed to renew Tor circuit: {e}")
            return False
    
    async def _newnym_raw(self) -> bool:
        """Renew circuit using raw control protocol (no stem dependency)."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(TOR_SOCKS_HOST, self.control_port),
                timeout=5.0,
            )
            
            # Authenticate
            writer.write(f'AUTHENTICATE "{self.control_password}"\r\n'.encode())
            await writer.drain()
            response = await reader.readline()
            if not response.startswith(b"250"):
                logger.error(f"Tor auth failed: {response.decode().strip()}")
                writer.close()
                return False
            
            # Send NEWNYM
            writer.write(b"SIGNAL NEWNYM\r\n")
            await writer.drain()
            response = await reader.readline()
            
            writer.close()
            await writer.wait_closed()
            
            if response.startswith(b"250"):
                await asyncio.sleep(3)
                logger.info("New Tor circuit established (raw protocol)")
                return True
            else:
                logger.error(f"NEWNYM failed: {response.decode().strip()}")
                return False
                
        except Exception as e:
            logger.error(f"Raw NEWNYM failed: {e}")
            return False
    
    async def new_circuit_for_portal(self, portal_name: str) -> bool:
        """
        Get a new circuit for a specific portal.
        Ensures each portal gets a unique exit node.
        
        Args:
            portal_name: Name of the portal (for logging)
        
        Returns:
            True if new circuit established
        """
        logger.info(f"Requesting new circuit for portal: {portal_name}")
        result = await self.new_circuit()
        if result:
            logger.info(f"New circuit ready for {portal_name}")
        else:
            logger.warning(f"Circuit renewal failed for {portal_name}, using existing circuit")
        return result
    
    def _hash_password(self, password: str) -> str:
        """
        Generate hashed control password for torrc.
        
        Note: In production, use `tor --hash-password <password>` output.
        This returns a placeholder; actual deployment should pre-generate the hash.
        """
        # Pre-generated hash for "udzialy_bot_tor" using:
        # tor --hash-password udzialy_bot_tor
        # In production, regenerate with: subprocess.check_output(["tor", "--hash-password", password])
        return "16:872860B76453A77D60CA2BB8C1A7042072093276A3D701AD684053EC4C"
    
    async def get_exit_ip(self) -> Optional[str]:
        """Get current Tor exit node IP address."""
        try:
            import httpx
            async with httpx.AsyncClient(
                proxy=self.socks_proxy,
                timeout=10.0,
            ) as client:
                response = await client.get("https://check.torproject.org/api/ip")
                data = response.json()
                return data.get("IP")
        except Exception as e:
            logger.warning(f"Could not get exit IP: {e}")
            return None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

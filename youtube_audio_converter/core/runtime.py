import threading
import time
from typing import Callable


class DownloadStartGate:
    def __init__(self, max_downloads: int, start_delay: float):
        self._semaphore = threading.Semaphore(max(1, int(max_downloads or 1)))
        self._start_delay = max(0.0, float(start_delay or 0.0))
        self._lock = threading.Lock()
        self._next_start = 0.0

    def acquire(self, is_cancelled: Callable[[], bool]) -> bool:
        while not is_cancelled():
            if self._semaphore.acquire(timeout=0.2):
                break
        else:
            return False

        with self._lock:
            while not is_cancelled():
                wait = self._next_start - time.monotonic()
                if wait <= 0:
                    self._next_start = time.monotonic() + self._start_delay
                    return True
                time.sleep(min(wait, 0.2))

        self.release()
        return False

    def release(self):
        self._semaphore.release()


class DownloadRuntime:
    def __init__(self, concurrent_downloads: int, concurrent_converts: int, download_start_delay: float):
        self.download_gate = DownloadStartGate(concurrent_downloads, download_start_delay)
        self.conversion_gate = threading.Semaphore(max(1, int(concurrent_converts or 1)))

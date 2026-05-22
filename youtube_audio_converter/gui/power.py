import os
import time


class GUIPowerMixin:
    def _set_system_sleep_state(self, prevent: bool):
        import platform

        if platform.system() == "Windows":
            import ctypes

            es_continuous = 0x80000000
            es_system_required = 0x00000001
            if prevent:
                ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(es_continuous)

    def _execute_power_action(self, action: str):
        import platform

        if platform.system() != "Windows":
            self.log("SYSTEM", "Post-completion tasks are only supported on Windows.", "ERROR")
            return

        self.log("SYSTEM", f"Executing post-completion task: {action}", "WARNING")
        time.sleep(2)

        commands = {
            "Shutdown": r"%windir%\System32\shutdown.exe -s -t 15",
            "Reboot": r"%windir%\System32\shutdown.exe -r -t 15",
            "Logoff": r"%windir%\System32\shutdown.exe -l -t 15",
            "Sleep": r"%windir%\System32\rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "Hibernate": r"%windir%\System32\rundll32.exe powrprof.dll,SetSuspendState Hibernate",
        }
        command = commands.get(action)
        if command:
            os.system(command)
        else:
            self.log("SYSTEM", f"Unknown action: {action}", "ERROR")

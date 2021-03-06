# Copyright (C) 2012-2015 JoseMi "h0rm1" Holguin (@j0sm1), Accuvant, Inc. (bspengler@accuvant.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from lib.cuckoo.common.abstracts import Signature

class InjectionCRT(Signature):
    name = "injection_createremotethread"
    description = "Code injection with CreateRemoteThread in a remote process"
    severity = 3
    categories = ["injection"]
    authors = ["JoseMi Holguin", "nex", "Accuvant"]
    minimum = "1.0"
    evented = True

    def __init__(self, *args, **kwargs):
        Signature.__init__(self, *args, **kwargs)
        self.lastprocess = None

    filter_categories = set(["process","threading"])

    def on_call(self, call, process):
        if process is not self.lastprocess:
            self.sequence = 0
            self.process_handles = set()
            self.process_pids = set()
            self.lastprocess = process

        if call["api"] == "OpenProcess" and call["status"] == True:
            if self.get_argument(call, "ProcessId") != process["process_id"]:
                self.process_handles.add(call["return"])
                self.process_pids.add(self.get_argument(call, "ProcessId"))
        elif call["api"] == "NtOpenProcess" and call["status"] == True:
            if self.get_argument(call, "ProcessIdentifier") != process["process_id"]:
                self.process_handles.add(self.get_argument(call, "ProcessHandle"))
                self.process_pids.add(self.get_argument(call, "ProcessIdentifier"))
        elif (call["api"] == "NtMapViewOfSection") and self.sequence == 0:
            if self.get_argument(call, "ProcessHandle") in self.process_handles:
                self.sequence = 2
        elif (call["api"] == "VirtualAllocEx" or call["api"] == "NtAllocateVirtualMemory") and self.sequence == 0:
            if self.get_argument(call, "ProcessHandle") in self.process_handles:
                self.sequence = 1
        elif (call["api"] == "NtWriteVirtualMemory" or call["api"] == "WriteProcessMemory") and self.sequence == 1:
            if self.get_argument(call, "ProcessHandle") in self.process_handles:
                self.sequence = 2
        elif (call["api"] == "NtWriteVirtualMemory" or call["api"] == "WriteProcessMemory") and self.sequence == 2:
            if self.get_argument(call, "ProcessHandle") in self.process_handles:
                addr = int(self.get_argument(call, "BaseAddress"), 16)
                buf = self.get_argument(call, "Buffer")
                if addr >= 0x7c900000 and addr < 0x80000000 and buf.startswith("\\xe9"):
                    self.description = "Code injection via WriteProcessMemory-modified NTDLL code in a remote process"
                    return True
        elif (call["api"] == "CreateRemoteThread" or call["api"].startswith("NtCreateThread")) and self.sequence == 2:
            if self.get_argument(call, "ProcessHandle") in self.process_handles:
                return True
        elif call["api"] == "NtQueueApcThread" and self.sequence == 2:
            if self.get_argument(call, "ProcessId") in self.process_pids:
                self.description = "Code injection with NtQueueApcThread in a remote process"
                return True


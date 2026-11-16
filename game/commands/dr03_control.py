"""One remote drum-3 valve; qualified local crew has priority."""
import json
import re
from evennia.commands.command import Command
from world.ship_dr03_authority import DrumControlError

class CmdOxRemoteDr03(Command):
    key="oxdr3remote"
    locks="cmd:all()"
    def func(self):
        bits=self.args.strip().split()
        if len(bits)!=2 or re.fullmatch(r"[0-9a-f]{32}",bits[0]) is None or bits[1] not in {"open","closed"}:
            self.caller.msg("Usage: oxdr3remote <32-hex-request-id> <open|closed>")
            return
        from world.ship_dr03_authority_world import remote_dr03
        try:
            result=remote_dr03(self.caller,*bits)
        except (DrumControlError,PermissionError,ValueError):
            self.caller.msg("Drum-3 remote control unavailable or refused.")
            return
        self.caller.msg(ox_dr03_remote=([json.dumps(result,sort_keys=True)],{}))

class CmdOxLocalDr03(Command):
    key="oxdr3local"
    locks="cmd:all()"
    def func(self):
        bits=self.args.strip().split()
        if len(bits)!=2 or re.fullmatch(r"[0-9a-f]{32}",bits[0]) is None or bits[1] not in {"takeover","handback","open","closed"}:
            self.caller.msg("Usage: oxdr3local <32-hex-request-id> <takeover|handback|open|closed>")
            return
        from world.ship_dr03_authority_world import local_dr03
        nonce,value=bits
        op=value if value in {"takeover","handback"} else "switch"
        try:
            result=local_dr03(self.caller,nonce,op,
                None if op!="switch" else value)
        except (DrumControlError,PermissionError,ValueError):
            self.caller.msg("Drum-3 local console unavailable or refused.")
            return
        self.caller.msg(ox_dr03_local=([json.dumps(result,sort_keys=True)],{}))

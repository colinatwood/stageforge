"""Exercise the actual native dispatcher without authorizing any output."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
engine = root / 'build' / 'native' / ('Release/stageforge_engine.exe' if os.name == 'nt' else 'stageforge_engine')
token = 'stageforge-ci-stdio-dispatch-fixture'
commands = ['PING', 'AUTH wrong', 'AUTH ' + token, 'HELLO', 'PING', 'STATUS', 'NO_SUCH_COMMAND', 'QUIT']
with tempfile.TemporaryDirectory(prefix='stageforge-stdio-') as temporary:
    env = {k: v for k, v in os.environ.items() if not k.startswith('STAGEFORGE_')}
    env.update(STAGEFORGE_IPC_TOKEN=token, STAGEFORGE_DATA_DIR=temporary)
    result = subprocess.run([str(engine), '--stdio'], input='\n'.join(commands)+'\n',
                            capture_output=True, text=True, timeout=20, env=env)
lines = result.stdout.splitlines()
expected = ['ERR code=permission', 'ERR code=permission', 'OK authenticated=1',
            'OK engineVersion=', 'OK pong=1', 'OK ', 'ERR code=unsupported', 'OK bye=1']
if result.returncode != 0 or len(lines) != len(expected) or any(not line.startswith(prefix) for line, prefix in zip(lines, expected)):
    raise RuntimeError(f'native stdio contract failed: exit={result.returncode}, stdout={result.stdout[:2000]!r}, stderr={result.stderr[:1000]!r}')
if 'lightingNetworkArmed=0' not in lines[5]:
    raise RuntimeError('native status did not confirm disarmed lighting')
report = {'documentType':'org.upp.native-engine-stdio-smoke', 'schemaVersion':1,
          'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
          'githubRunId':os.environ.get('GITHUB_RUN_ID'), 'hostOs':platform.system(),
          'binarySha256':hashlib.sha256(engine.read_bytes()).hexdigest(),
          'status':'passed', 'unauthenticatedRejected':True, 'wrongTokenRejected':True,
          'authenticatedCommands':True, 'unknownCommandRejected':True, 'quitCompleted':True,
          'physicalOutputsArmed':False, 'physicalHardwareQualified':False}
Path('native-engine-smoke.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(json.dumps(report, indent=2))

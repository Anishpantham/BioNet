"""Graceful interruption of actual Python processes over localhost UDP."""
import queue
import signal
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from bionet import sender
from bionet.benchmark import local_receiver
from bionet.impairment import Channel
from bionet.protocol import DATA, decode


def line_with_timeout(process):
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    return lines.get(timeout=5).strip()


def stop_process(process):
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)


def test_receiver_sigint_during_sender_transfer(tmp_path, monkeypatch):
    code = '''import sys
from bionet.receiver import receive
try:
    receive(port=0, output=sys.argv[1], quiet=True, ready=lambda p: print(p, flush=True))
except KeyboardInterrupt:
    sys.exit(130)
'''
    process = subprocess.Popen([sys.executable, '-u', '-c', code, str(tmp_path/'out')],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = int(line_with_timeout(process))
        original = Channel.send; interrupted = False
        def stop_on_data(channel, packet, peer):
            nonlocal interrupted
            if decode(packet)[0] == DATA and not interrupted:
                interrupted = True; process.send_signal(signal.SIGINT)
                process.wait(timeout=5)
            return original(channel, packet, peer)
        monkeypatch.setattr(Channel, 'send', stop_on_data)
        source = tmp_path/'source'; source.write_bytes(b'x'*4096)
        with pytest.raises(TimeoutError):
            sender.send(source, port=port, timeout=.02, retries=2)
        assert process.returncode == 130 and interrupted
        assert not list((tmp_path/'out').iterdir())
    finally:
        stop_process(process)


def test_sender_sigint_and_receiver_idle_cleanup(tmp_path):
    code = '''import sys
from bionet.impairment import Channel
from bionet.protocol import decode, DATA
from bionet.cli import main
original = Channel.send
announced = False
def drop_data(self, packet, peer):
    global announced
    if decode(packet)[0] == DATA:
        if not announced: print('DATA started', flush=True); announced = True
        return False
    return original(self, packet, peer)
Channel.send = drop_data
main()
'''
    source = tmp_path/'source'; source.write_bytes(b'x'*4096)
    with local_receiver('udp', tmp_path/'out', idle_timeout=.1, quiet=True) as port:
        process = subprocess.Popen([sys.executable, '-u', '-c', code, 'sender',
            '--file', str(source), '--port', str(port)], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            assert line_with_timeout(process) == 'DATA started'
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 130 and 'interrupted' in stderr
            import time
            deadline = time.monotonic()+1
            while list((tmp_path/'out').iterdir()) and time.monotonic()<deadline:
                time.sleep(.01)
            assert not list((tmp_path/'out').iterdir())
        finally:
            stop_process(process)

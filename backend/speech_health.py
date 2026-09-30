"""Offline readiness checks, isolated from the web process and the media worker."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import wave
from backend import store

KEYS = ('model','fallback_model','device','compute_type','cpu_threads')
CHECK_RUNNING = threading.Event()


def fingerprint(config):
    models={name:[[f.name,f.stat().st_size,f.stat().st_mtime_ns] for f in cached_files(name)]
            for name in dict.fromkeys([config['model'],config['fallback_model']])}
    evidence=dict(settings={k:config[k] for k in KEYS},dependencies=versions(),models=models)
    return hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()


def versions():
    result = {}
    for name in ('faster-whisper','av','ctranslate2'):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def cached_files(name):
    direct = Path(name)
    hub = Path(os.getenv('HF_HUB_CACHE', str(Path(os.getenv('HF_HOME', str(Path.home()/'.cache/huggingface'))) / 'hub')))
    repo = name if '/' in name and not direct.is_dir() else 'Systran/faster-whisper-' + name
    candidates = [direct] if direct.is_dir() else list((hub / ('models--'+repo.replace('/','--')) / 'snapshots').glob('*'))
    for p in sorted(candidates):
        files=[p/f for f in ['config.json','model.bin','tokenizer.json']]
        vocabulary=list(p.glob('vocabulary.*'))
        if all(f.is_file() for f in files) and vocabulary:
            return files+vocabulary
    return []


def cached(name):
    return bool(cached_files(name))


def status():
    from backend import service
    config = store.settings()
    path = store.data_dir()/'speech-readiness.json'
    try:
        latest = json.loads(path.read_text())
    except (OSError,ValueError):
        latest = {'status':'not_checked'}
    if latest.get('status') == 'running' and not CHECK_RUNNING.is_set():
        latest = {**latest,'status':'failed','error':'A readiness check was interrupted. Run it again when processing is idle.'}
    return dict(models=[dict(name=name,cached=cached(name)) for name in dict.fromkeys([config['model'],config['fallback_model']])],
                dependencies=versions(), latest=latest, outdated=latest.get('fingerprint') != fingerprint(config),
                worker_busy=service.INFERENCE_LOCK.locked(),
                explanation='The runtime check decodes a short local audio sample with each model. It checks compatibility, not recognition accuracy.')


def run_check():
    from cli import bleeparr as cli
    config = store.settings()
    result = dict(status='passed', fingerprint=fingerprint(config), checked_at=time.time(), models=[],dependencies=versions())
    args = cli.parser().parse_args(['--input','readiness-sample'])
    for key in KEYS:
        setattr(args,key,config[key])
    with tempfile.TemporaryDirectory(prefix='speech-readiness-',dir=store.data_dir()) as folder:
        sample=Path(folder)/'sample.wav'
        with wave.open(str(sample),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*32000)
        for name in dict.fromkeys([config['model'],config['fallback_model']]):
            started=time.monotonic();model=None
            try:
                model=cli.load_speech_model(name,args)
                segments,_=model.transcribe(str(sample),word_timestamps=True,condition_on_previous_text=False)
                list(segments)  # Decode/inference exceptions may occur lazily.
                row=dict(name=name,status='passed')
            except Exception as exc:
                row=dict(name=name,status='failed',error=str(exc)[:1000]);result['status']='failed'
            finally:
                del model
                __import__('gc').collect()
            result['models'].append({**row,'elapsed_seconds':round(time.monotonic()-started,2)})
    return result


def start():
    from backend import service,output
    if not service.INFERENCE_LOCK.acquire(blocking=False):
        raise ValueError('A file or model check is already processing. Run this check when processing is idle.')
    try:
        config=store.settings();path=store.data_dir()/'speech-readiness.json'
        CHECK_RUNNING.set()
        output.write_receipt(path,dict(status='running',fingerprint=fingerprint(config),checked_at=time.time()))
        def check():
            try:
                done=subprocess.run([sys.executable,'-m','backend.speech_health','--run'],capture_output=True,text=True,timeout=300)
                result=json.loads(done.stdout) if done.returncode==0 else dict(status='failed',error='The isolated runtime check did not finish successfully.')
            except subprocess.TimeoutExpired:
                result=dict(status='failed',error='The runtime check exceeded five minutes.')
            except Exception:
                result=dict(status='failed',error='The runtime check could not complete.')
            try:
                result.setdefault('fingerprint',fingerprint(config));result.setdefault('checked_at',time.time())
                output.write_receipt(path,result)
                store.event('Speech-model readiness check '+result['status']+'.')
            finally:
                CHECK_RUNNING.clear();service.INFERENCE_LOCK.release();service.WAKE.set()
        threading.Thread(target=check,daemon=True).start()
    except Exception:
        CHECK_RUNNING.clear();service.INFERENCE_LOCK.release();raise
    return dict(message='Offline speech-model check started.',status='running')


if __name__=='__main__' and '--run' in sys.argv:
    print(json.dumps(run_check()))

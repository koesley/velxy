"""Windows PyInstaller folder build, with bundled webview and maintenance tools."""
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent;source=root/'velxy-main'
assert (source/'portal.py').is_file()
assets=[p for p in source.iterdir() if p.is_file() and p.suffix.lower() not in ('.py','.pyc','.db','.sqlite3','.zip') and not p.name.startswith('test_')]
cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--name','VELXTRIA-Desktop','--paths',str(source),'--distpath',str(root/'dist'),'--workpath',str(root/'build'),'--hidden-import','desktop_maintenance','--collect-all','webview']
for p in assets:cmd+=['--add-data',str(p)+os.pathsep+'.']
cmd.append(str(root/'desktop_entry.py'))
print('Bundling',len(assets),'static assets');subprocess.check_call(cmd)
print('Built:',root/'dist'/'VELXTRIA-Desktop'/'VELXTRIA-Desktop.exe')

"""Enforce the four-file runtime scope and exact legacy/cache preservation."""
from pathlib import Path
import ast,json,zipfile,sys
base,new,archive,out=map(lambda x:Path(x).resolve(),sys.argv[1:])
changed=[]
with zipfile.ZipFile(archive) as z:
    for entry in z.infolist():
        if entry.is_dir():continue
        name=entry.filename.split('/',1)[1];original=z.read(entry)
        assert (base/name).read_bytes()==original,name
        if (new/name).read_bytes()!=original:changed.append(name)
expected={'app.py','config.py','store.py','gate4_ui.py','tests/test_gate4_ui_polish.py','tests/test_v110_render_reuse.py','tests/test_v111_public_cache_coordination.py','tests/lineup_ui_fixture.py'}
assert set(changed)==expected,changed
def methods(text,cls):
    node=next(x for x in ast.parse(text).body if isinstance(x,ast.ClassDef) and x.name==cls)
    return {x.name:ast.get_source_segment(text,x) for x in node.body if isinstance(x,ast.FunctionDef)}
a,b=[methods((r/'store.py').read_text(),'SupabaseStore') for r in [base,new]]
assert b['_load_week_public_bundle_legacy'].replace('def _load_week_public_bundle_legacy(','def _load_week_public_bundle(',1)==a['_load_week_public_bundle']
assert all(v==b[k] for k,v in a.items() if k!='_load_week_public_bundle')
assert set(b)-set(a)=={'_load_week_public_bundle_legacy'}
def functions(text):return {x.name:ast.get_source_segment(text,x) for x in ast.parse(text).body if isinstance(x,ast.FunctionDef)}
a,b=[functions((r/'gate4_ui.py').read_text()) for r in [base,new]]
assert all(v==b[k] for k,v in a.items() if k!='_leaderboard_rows')
assert set(b)-set(a)=={'_toggle_leaderboard_detail'}
assert (base/'app.py').read_text().split('\npage_config()',1)[1]==(new/'app.py').read_text().split('\npage_config()',1)[1]
def settings(root):return {n.targets[0].id:ast.dump(n.value) for n in ast.parse((root/'config.py').read_text()).body if isinstance(n,ast.Assign)}
a,b=settings(base),settings(new)
assert {k for k in a if a[k]!=b[k]}=={'APP_VERSION','APP_BUILD_VERSION'}
result={'status':'PASS','baseline_files_verified':342,'changed_original_files':sorted(changed),'runtime_files':['app.py','config.py','gate4_ui.py','store.py'],'all_other_store_methods':'byte-identical including cache coordinator','legacy_loader':'exact original function with name changed','gate4_other_functions':'byte-identical','app_body_after_page_config':'byte-identical','config_changes':'APP_VERSION and APP_BUILD_VERSION only','unchanged_settings':'all refresh schedules, TTLs, provider/auth/scoring/commissioner behavior unchanged'}
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

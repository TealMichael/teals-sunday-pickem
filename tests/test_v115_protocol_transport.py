"""SDK RPC request shape, schema routing, and worker transport isolation."""
import json
import os
import httpx
from store import SupabaseStore

def test_protected_writes_use_typed_rpc_and_isolated_transport(monkeypatch):
 for key in os.environ:
  if key.lower().endswith("_proxy"):monkeypatch.delenv(key,raising=False)
 from postgrest._sync import client as pg
 clients=[];requests=[];original=pg.Client
 def handle(request):
  requests.append(request)
  return httpx.Response(200,json=[{'id':'synthetic-week'}])
 def client(*a,**kw):
  kw.update(transport=httpx.MockTransport(handle),trust_env=False)
  c=original(*a,**kw);clients.append(c);return c
 monkeypatch.setattr(pg,'Client',client)
 store=SupabaseStore('https://audit.invalid','synthetic-key');owned=store.new_refresh_store()
 try:
  assert owned.client is not store.client;assert owned.client.postgrest.session is not store.client.postgrest.session
  store._table('weeks').update({'data_message':'Test'}).eq('id','synthetic-week').execute()
  request=requests[-1];assert request.method=='POST';assert request.url.path=='/rest/v1/rpc/refresh_edit'
  assert request.headers['content-profile']=='pickem'
  assert json.loads(request.content)==dict(p_table='weeks',p_operation='update',p_rows=[{'data_message':'Test'}],p_filters=[{'column':'id','op':'eq','value':'synthetic-week'}],p_conflict='',p_claim=None)
  owned.close_refresh_store();assert owned.client.postgrest.session.is_closed
  assert not store.client.postgrest.session.is_closed
 finally:
  store.close_refresh_store()

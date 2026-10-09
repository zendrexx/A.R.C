const {test}=require('node:test');
const assert=require('node:assert/strict');
const http=require('node:http');
const {dashboardUrl,ensureDashboard}=require('../out/dashboard');
function server(database='db1'){
  return http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({service:'arc-dashboard',database_id:database}));});
}
const listen=s=>new Promise(resolve=>s.listen(0,'127.0.0.1',()=>resolve(s.address().port)));
const close=s=>new Promise(resolve=>s.close(resolve));
test('dashboard validates local configured URLs',()=>{
  assert.equal(dashboardUrl('http://localhost:9876').port,'9876');
  for(const url of ['https://example.com','http://127.0.0.1:0','http://user@localhost:9876','http://localhost:9876/other'])assert.throws(()=>dashboardUrl(url));
});
test('existing dashboard is reused at the actual configured port',async()=>{
  const s=server();const port=await listen(s);let starts=0;
  try{
    const backend={project:'/my project',request:async()=>({database_id:'db1'}),startDashboard:()=>{starts++;}};
    const url=await ensureDashboard(backend,`http://127.0.0.1:${port}`);
    assert.equal(new URL(url).port,String(port));assert.equal(new URL(url).searchParams.get('project'),'/my project');assert.equal(starts,0);
    await assert.rejects(ensureDashboard({...backend,request:async()=>({database_id:'another'})},`http://127.0.0.1:${port}`),/another dashboard or database/);
  }finally{await close(s);}
});
test('cold dashboard starts once for concurrent button clicks',async()=>{
  const reserve=server();const port=await listen(reserve);await close(reserve);
  const s=server();let starts=0;
  const backend={project:'/project',request:async()=>({database_id:'db1'}),startDashboard:p=>{starts++;s.listen(p,'127.0.0.1');}};
  try{await Promise.all([ensureDashboard(backend,`http://127.0.0.1:${port}`),ensureDashboard(backend,`http://127.0.0.1:${port}`)]);assert.equal(starts,1);}finally{await close(s);}
});

const test=require('node:test');
const assert=require('node:assert/strict');
const {merge}=require('../tender-feed');
test('tender feed supplements news without collapsing related services',()=>{
 const base={date:'2026-09-14',tag:'招投标'};
 const prefix='某基础设施公募REITs发行及相关服务采购项目';
 const news=[{...base,title:prefix+'法律服务',url:'https://old.example'}];
 const tenders=[{...base,title:prefix+'法律服务',url:'https://official.example'},{...base,title:prefix+'审计服务',url:'https://official.example/a'}];
 const rows=merge(news,tenders);
 assert.equal(rows.length,2);
 assert.equal(rows.find(x=>x.title.endsWith('法律服务')).url,'https://official.example');
 assert.equal(news[0].url,'https://old.example');
});

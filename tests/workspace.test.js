const test = require('node:test');
const assert = require('node:assert/strict');
const {normalizedSeries} = require('../workspace');
test('selected price interval rebases to 100 without mutating source', () => {
  const series={dates:['a','b','c','d'],market:[80,90,100,95]};
  assert.deepEqual(normalizedSeries(series,2),[{date:'c',value:100},{date:'d',value:95}]);
  assert.deepEqual(series.market,[80,90,100,95]);
});
test('invalid observations are excluded and missing series stays empty', () => {
  assert.deepEqual(normalizedSeries({dates:['a','b','c'],market:[null,0,80]},3),[{date:'c',value:100}]);
  assert.deepEqual(normalizedSeries(null,20),[]);
});
